import json

from fastapi import APIRouter, Depends, Header, HTTPException

from .. import db
from ..agent.prompts import FIRST_MESSAGE, SYSTEM_PROMPT
from ..agent.tools import TOOLS, run_tool
from ..config import get_settings
from ..security import require_dashboard_token, secret_matches

router = APIRouter(prefix="/vapi", tags=["voice"])


@router.post("/webhook")
def webhook(payload: dict, x_vapi_secret: str | None = Header(default=None)):
    s = get_settings()
    if s.vapi_secret and not secret_matches(x_vapi_secret, s.vapi_secret):
        raise HTTPException(401, "bad secret")

    msg = payload.get("message", {})
    call = msg.get("call") or {}
    call_id = call.get("id")
    phone = (call.get("customer") or {}).get("number", "unknown")

    if msg.get("type") == "tool-calls":
        results = []
        for tc in msg.get("toolCallList", []):
            fn = tc.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            out = run_tool(fn.get("name", ""), args, phone, "voice", call_id)
            results.append({"toolCallId": tc["id"], "result": json.dumps(out)})
        return {"results": results}

    if msg.get("type") == "end-of-call-report" and call_id:
        db.save_call(
            call_id,
            "voice",
            phone,
            simulated=call_id.startswith("sim-"),
            duration_s=msg.get("durationSeconds"),
            cost_usd=msg.get("cost"),
            summary=(msg.get("analysis") or {}).get("summary"),
            transcript=msg.get("transcript"),
        )
    return {"ok": True}


@router.get("/assistant-config", dependencies=[Depends(require_dashboard_token)])  # exposes the full system prompt
def assistant_config(business: str = "Acme Growth"):
    """Vapi assistant definition generated from the same tool registry the WhatsApp agent uses."""
    return build_assistant(business, secret="<VAPI_SECRET>")


def build_assistant(business: str, secret: str, customer_id: str | None = None) -> dict:
    s = get_settings()
    url = f"{s.public_base_url}/vapi/webhook" + (f"?customer={customer_id}" if customer_id else "")
    server = {"url": url, "secret": secret}
    return {
        "name": f"{business} Operator",
        "firstMessage": FIRST_MESSAGE.format(business=business),
        "model": {
            "provider": "anthropic",
            "model": s.llm_model,  # check Vapi's supported model list
            "messages": [{"role": "system", "content": SYSTEM_PROMPT.format(business=business)}],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
                    "server": server,
                }
                for t in TOOLS
            ],
        },
        "server": server,
        "serverMessages": ["tool-calls", "end-of-call-report"],
    }
