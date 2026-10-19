from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from ..agent import chat
from ..config import get_settings
from ..integrations import twilio_client

router = APIRouter(tags=["whatsapp"])


@router.post("/whatsapp/webhook")
async def inbound(request: Request):
    form = {k: str(v) for k, v in (await request.form()).items()}
    url = f"{get_settings().public_base_url}/whatsapp/webhook"
    if not twilio_client.is_valid_signature(url, form, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "invalid Twilio signature")

    phone = form.get("From", "").removeprefix("whatsapp:")
    text = await run_in_threadpool(chat.reply, phone, form.get("Body", ""))
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(text)}</Message></Response>'
    return Response(twiml, media_type="application/xml")
