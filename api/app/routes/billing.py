import stripe
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from ..config import get_settings
from ..db import conn
from ..provisioning import provision_customer

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout")
def checkout(body: dict):
    s = get_settings()
    if not s.stripe_secret_key:
        raise HTTPException(503, "Stripe not configured")
    stripe.api_key = s.stripe_secret_key
    country = (body.get("country") or "US").upper()
    line_items = [{"price": s.stripe_price_ids.get(country, s.stripe_price_id), "quantity": 1}]
    if country in s.stripe_setup_price_ids:
        line_items.append({"price": s.stripe_setup_price_ids[country], "quantity": 1})
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=line_items,
        customer_email=body.get("email"),
        billing_address_collection="required",
        metadata={"country": country, "business_name": body.get("business_name") or ""},
        success_url=f"{s.web_origin}/?billing=success",
        cancel_url=f"{s.web_origin}/?billing=cancel",
    )
    return {"url": session.url}


def client_country(session: dict) -> str:
    """Country the client chose at checkout, else their billing address, else US."""
    meta = session.get("metadata") or {}
    address = (session.get("customer_details") or {}).get("address") or {}
    return (meta.get("country") or address.get("country") or "US").upper()


@router.post("/webhook")
async def stripe_webhook(request: Request, background: BackgroundTasks):
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
            details = obj.get("customer_details") or {}
            row = c.execute(
                """insert into customers (email, stripe_customer_id, stripe_subscription_id, status, country, business_name)
                   values (%s, %s, %s, 'active', %s, %s)
                   on conflict (stripe_customer_id) do update
                   set stripe_subscription_id = excluded.stripe_subscription_id, status = 'active'
                   returning id""",
                (
                    details.get("email"), obj["customer"], obj.get("subscription"),
                    client_country(obj), (obj.get("metadata") or {}).get("business_name") or details.get("name"),
                ),
            ).fetchone()
            # Stripe needs a 2xx fast; provisioning calls Twilio + Vapi + Resend so it runs after the response.
            background.add_task(provision_customer, str(row["id"]))
        elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
            c.execute("update customers set status = %s where stripe_customer_id = %s", (obj["status"], obj["customer"]))
    return {"received": True}
