"""Paid checkout -> live client: create the Vapi assistant, buy a local Twilio number, attach it, email onboarding.

Runs as a background task off the Stripe webhook. Every step saves its result on the customers row before the next
step starts, so a retry after a failure resumes where it stopped instead of buying a second number.
"""
import logging

import httpx
from twilio.rest import Client

from .config import get_settings
from .db import conn
from .routes.vapi import build_assistant

log = logging.getLogger(__name__)

VAPI = "https://api.vapi.ai"
# Stripe sends ISO 3166 alpha-2 codes. Twilio uses the same codes.
SUPPORTED = {"US", "GB", "AE", "AU"}


class NumberUnavailable(Exception):
    """No local number can be bought by API (no stock, or the country needs regulatory approval first)."""


def claim(customer_id: str) -> dict | None:
    """Atomically move a customer into 'provisioning'. Returns None if another run owns it or it is already done."""
    with conn() as c:
        return c.execute(
            """update customers set provisioning_status = 'provisioning', provisioning_error = null
               where id = %s and provisioning_status in ('pending', 'failed', 'needs_manual_number') returning *""",
            (customer_id,),
        ).fetchone()


def save(customer_id: str, **fields) -> None:
    sets = ", ".join(f"{k} = %s" for k in fields)
    with conn() as c:
        c.execute(f"update customers set {sets} where id = %s", (*fields.values(), customer_id))


def buy_number(country: str, business: str) -> tuple[str, str]:
    """Buy a local Twilio number in the client's country. Returns (e164, twilio_sid)."""
    s = get_settings()
    if country not in SUPPORTED:
        raise NumberUnavailable(f"country {country!r} not supported")
    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    available = client.available_phone_numbers(country).local.list(voice_enabled=True, limit=1)
    if not available:
        raise NumberUnavailable(f"no local voice numbers in stock for {country}")
    extra = {}
    if country in s.twilio_bundle_sids:
        extra["bundle_sid"] = s.twilio_bundle_sids[country]
    if country in s.twilio_address_sids:
        extra["address_sid"] = s.twilio_address_sids[country]
    try:
        n = client.incoming_phone_numbers.create(
            phone_number=available[0].phone_number, friendly_name=f"{business} Operator", **extra
        )
    except Exception as e:  # Twilio rejects GB/AU/AE purchases without an approved bundle
        raise NumberUnavailable(f"Twilio refused {country} number: {e}") from e
    return n.phone_number, n.sid


def vapi_post(path: str, body: dict) -> dict:
    r = httpx.post(
        f"{VAPI}{path}", json=body, headers={"Authorization": f"Bearer {get_settings().vapi_api_key}"}, timeout=30
    )
    r.raise_for_status()
    return r.json()


def send_email(to: str, subject: str, html: str) -> None:
    s = get_settings()
    if not s.resend_api_key:
        log.info("[demo mode] email to %s: %s", to, subject)
        return
    r = httpx.post(
        "https://api.resend.com/emails",
        json={"from": s.resend_from, "to": [to], "subject": subject, "html": html},
        headers={"Authorization": f"Bearer {s.resend_api_key}"},
        timeout=30,
    )
    r.raise_for_status()


def onboarding_html(business: str, number: str | None) -> str:
    if number:
        step = (
            f"<p>Your AI receptionist is live on <b>{number}</b>.</p>"
            "<p>Next: set call forwarding on your main line to this number for unanswered and after-hours calls. "
            "Then call it yourself to hear it.</p>"
        )
    else:
        step = "<p>We're reserving your local number now. You'll get it within one business day.</p>"
    return f"<p>Welcome aboard, {business}.</p>{step}<p>Reply to this email with any questions.</p>"


def provision_customer(customer_id: str) -> None:
    row = claim(customer_id)
    if row is None:
        return
    s = get_settings()
    business = row["business_name"] or row["email"] or "Your business"
    country = (row["country"] or "US").upper()
    try:
        assistant_id = row["vapi_assistant_id"]
        if not assistant_id:
            assistant_id = vapi_post("/assistant", build_assistant(business, s.vapi_secret, customer_id))["id"]
            save(customer_id, vapi_assistant_id=assistant_id)

        number = row["phone_number"]
        if not number:
            try:
                number, sid = buy_number(country, business)
                save(customer_id, phone_number=number, twilio_number_sid=sid)
            except NumberUnavailable as e:
                log.warning("customer %s: %s", customer_id, e)
                save(customer_id, provisioning_status="needs_manual_number", provisioning_error=str(e))
                if s.ops_email:
                    send_email(s.ops_email, f"Manual number needed: {business} ({country})", f"<p>{e}</p>")
                send_email(row["email"], f"Welcome to Voice Operator, {business}", onboarding_html(business, None))
                return

        if not row["vapi_phone_number_id"]:
            pn = vapi_post(
                "/phone-number",
                {
                    "provider": "twilio",
                    "number": number,
                    "twilioAccountSid": s.twilio_account_sid,
                    "twilioAuthToken": s.twilio_auth_token,
                    "assistantId": assistant_id,
                    "name": f"{business} ({country})",
                },
            )
            save(customer_id, vapi_phone_number_id=pn["id"])

        send_email(row["email"], f"Your AI receptionist is live, {business}", onboarding_html(business, number))
        save(customer_id, provisioning_status="live")
    except Exception as e:
        log.exception("provisioning failed for customer %s", customer_id)
        save(customer_id, provisioning_status="failed", provisioning_error=str(e)[:500])
        if s.ops_email:
            send_email(s.ops_email, f"Provisioning FAILED: {business}", f"<pre>{e}</pre>")
