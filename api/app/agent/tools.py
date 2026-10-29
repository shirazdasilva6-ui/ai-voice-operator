"""Single tool registry shared by the voice (Vapi) and WhatsApp channels."""
import logging
import time

from .. import db
from ..integrations import calendly, hubspot, twilio_client
from .qualify import LeadSignals, decide, score

log = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "qualify_lead",
        "description": "Record BANT signals learned so far. Returns status and which fields are still missing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "budget_usd": {"type": "integer", "description": "Monthly budget in USD"},
                "is_decision_maker": {"type": "boolean"},
                "need": {"type": "string", "description": "The problem they want solved, in their words"},
                "timeline_days": {"type": "integer", "description": "Days until they want to start"},
                "company": {"type": "string"},
            },
        },
    },
    {
        "name": "get_available_slots",
        "description": "Get the next open meeting times (ISO 8601, UTC). Only for qualified leads.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "book_meeting",
        "description": "Create a booking link for a qualified lead and send it to them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "preferred_slot": {"type": "string", "description": "ISO time the lead picked"},
            },
            "required": ["name", "email"],
        },
    },
]


def _qualify(args: dict, phone: str, simulated: bool) -> dict:
    existing = db.get_lead(phone) or {}
    signals = LeadSignals(
        budget_usd=args.get("budget_usd", existing.get("budget_usd")),
        is_decision_maker=args.get("is_decision_maker", existing.get("is_decision_maker")),
        need=args.get("need", existing.get("need")),
        timeline_days=args.get("timeline_days", existing.get("timeline_days")),
    )
    status, pts = decide(signals), score(signals)
    lead = db.upsert_lead(phone, **vars(signals), company=args.get("company"), score=pts, status=status)
    if not simulated:  # never push load-test leads into a real CRM
        hs_id = hubspot.upsert_contact(phone, {"company": lead.get("company")}, status)
        if hs_id and not lead.get("hubspot_id"):
            db.upsert_lead(phone, hubspot_id=hs_id)
    return {"status": status, "score": pts, "missing": signals.missing()}


def _book(args: dict, phone: str, channel: str, simulated: bool) -> dict:
    lead = db.get_lead(phone)
    if not lead or lead["status"] not in ("qualified", "booked"):
        return {"error": "Lead is not qualified. Do not book."}
    url = "https://calendly.com/demo/30min" if simulated else calendly.single_use_link()
    db.upsert_lead(phone, name=args["name"], email=args["email"], status="booked", booking_url=url)
    if simulated:
        return {"booked": True, "booking_url": url}
    hubspot.upsert_contact(phone, {"firstname": args["name"], "email": args["email"]}, "booked")
    if channel == "voice":
        twilio_client.send_sms(phone, f"Hi {args['name']}, here is your booking link: {url}")
        return {"booked": True, "delivery": "Link sent by SMS. Tell the caller to check their texts."}
    return {"booked": True, "booking_url": url}


def run_tool(name: str, args: dict, phone: str, channel: str, call_id: str | None = None) -> dict:
    simulated = (call_id or "").startswith("sim-")
    t0 = time.perf_counter()
    ok = True
    try:
        if name == "qualify_lead":
            return _qualify(args, phone, simulated)
        if name == "get_available_slots":
            return {"slots": calendly.available_slots()}
        if name == "book_meeting":
            return _book(args, phone, channel, simulated)
        ok = False
        return {"error": f"unknown tool {name}"}
    except Exception as e:  # tool errors go back to the model, never crash the call
        ok = False
        log.exception("tool %s failed", name)
        # The model may repeat this to the caller, so never pass internal details (URLs, stack text) through.
        return {"error": "That didn't work on our side. Tell the caller a teammate will follow up."}
    finally:
        db.log_tool_event(call_id, name, int((time.perf_counter() - t0) * 1000), ok)
