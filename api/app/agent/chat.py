"""Text agent loop used by the WhatsApp channel (voice uses Vapi's own LLM loop + our tools)."""
import json

import anthropic

from .. import db
from ..config import get_settings
from .prompts import SYSTEM_PROMPT
from .tools import TOOLS, run_tool

MAX_TOOL_ROUNDS = 5


def reply(phone: str, text: str, business: str = "Acme Growth") -> str:
    s = get_settings()
    if not s.anthropic_api_key:
        return "[demo mode] Set ANTHROPIC_API_KEY to enable the agent."
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)

    db.append_message(phone, "user", text)
    history = db.load_history(phone)

    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.messages.create(
            model=s.llm_model,
            max_tokens=400,
            system=SYSTEM_PROMPT.format(business=business),
            tools=TOOLS,
            messages=history,
        )
        assistant = [b.model_dump(exclude_none=True) for b in resp.content]
        history.append({"role": "assistant", "content": assistant})
        db.append_message(phone, "assistant", assistant)

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip()

        results = [
            {"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(run_tool(b.name, b.input, phone, "whatsapp"))}
            for b in resp.content
            if b.type == "tool_use"
        ]
        history.append({"role": "user", "content": results})
        db.append_message(phone, "user", results)

    return "Thanks! A teammate will follow up shortly."
