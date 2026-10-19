import logging

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from ..config import get_settings

log = logging.getLogger(__name__)


def send_sms(to: str, body: str) -> None:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_sms_from):
        log.info("[demo mode] SMS to %s: %s", to, body)
        return
    Client(s.twilio_account_sid, s.twilio_auth_token).messages.create(from_=s.twilio_sms_from, to=to, body=body)


def is_valid_signature(url: str, params: dict, signature: str) -> bool:
    s = get_settings()
    if not s.twilio_validate:
        return True
    if not s.twilio_auth_token:
        log.warning("TWILIO_AUTH_TOKEN unset: accepting unsigned webhook (demo mode only)")
        return True
    return RequestValidator(s.twilio_auth_token).validate(url, params, signature)
