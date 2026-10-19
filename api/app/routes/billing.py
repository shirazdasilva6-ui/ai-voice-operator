import stripe
from fastapi import APIRouter, HTTPException, Request

from ..config import get_settings
from ..db import conn

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout")
def checkout(body: dict):
    s = get_settings()
    if not s.stripe_secret_key:
        raise HTTPException(503, "Stripe not configured")
    stripe.api_key = s.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": s.stripe_price_id, "quantity": 1}],
        customer_email=body.get("email"),
        success_url=f"{s.web_origin}/?billing=success",
        cancel_url=f"{s.web_origin}/?billing=cancel",
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    s = get_settings()
    try:
        event = stripe.Webhook.construct_event(
            await request.body(), request.headers.get("stripe-signature", ""), s.stripe_webhook_secret
        )
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "invalid signature")

    obj = event["data"]["object"]
    with conn() as c:
        if event["type"] == "checkout.session.completed":
            c.execute(
                """insert into customers (email, stripe_customer_id, stripe_subscription_id, status)
                   values (%s, %s, %s, 'active')
                   on conflict (stripe_customer_id) do update
                   set stripe_subscription_id = excluded.stripe_subscription_id, status = 'active'""",
                ((obj.get("customer_details") or {}).get("email"), obj["customer"], obj.get("subscription")),
            )
        elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
            c.execute("update customers set status = %s where stripe_customer_id = %s", (obj["status"], obj["customer"]))
    return {"received": True}
