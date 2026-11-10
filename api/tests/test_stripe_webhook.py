"""The Stripe webhook triggers real spending (auto-provisioning), so it must only trust events Stripe signed."""
import hashlib
import hmac
import json
import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.routes import billing

SECRET = "whsec_test"


def stripe_signature(payload: str, secret: str = SECRET, ts: int | None = None) -> str:
    ts = ts or int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def checkout_event(payment_status: str) -> str:
    return json.dumps({
        "id": "evt_1", "object": "event", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_1", "object": "checkout.session", "customer": "cus_1", "subscription": "sub_1",
            "payment_status": payment_status, "metadata": {"country": "GB", "business_name": "Acme"},
            "customer_details": {"email": "owner@acme.example", "name": "Acme"},
        }},
    })


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    provisioned, sql = [], []

    class FakeConn:
        def execute(self, query, params=None):
            sql.append(query)
            return type("R", (), {"fetchone": lambda self: {"id": "cust-1"}})()

    @contextmanager
    def fake_conn():
        yield FakeConn()

    monkeypatch.setattr(billing, "conn", fake_conn)
    monkeypatch.setattr(billing, "provision_customer", lambda cid: provisioned.append(cid))
    from app.main import app

    yield TestClient(app), provisioned, sql
    get_settings.cache_clear()


def test_unsigned_event_is_rejected(client):
    c, provisioned, sql = client
    r = c.post("/billing/webhook", content=checkout_event("paid"))
    assert r.status_code == 400 and provisioned == [] and sql == []


def test_event_signed_with_wrong_secret_is_rejected(client):
    c, provisioned, sql = client
    body = checkout_event("paid")
    r = c.post("/billing/webhook", content=body, headers={"stripe-signature": stripe_signature(body, "whsec_attacker")})
    assert r.status_code == 400 and provisioned == [] and sql == []


def test_tampered_payload_is_rejected(client):
    c, provisioned, sql = client
    sig = stripe_signature(checkout_event("unpaid"))
    r = c.post("/billing/webhook", content=checkout_event("paid"), headers={"stripe-signature": sig})
    assert r.status_code == 400 and provisioned == []


def test_replayed_old_event_is_rejected(client):
    c, provisioned, _ = client
    body = checkout_event("paid")
    old = stripe_signature(body, ts=int(time.time()) - 3600)  # Stripe's default tolerance is 5 minutes
    assert c.post("/billing/webhook", content=body, headers={"stripe-signature": old}).status_code == 400
    assert provisioned == []


def test_paid_checkout_triggers_provisioning(client):
    c, provisioned, _ = client
    body = checkout_event("paid")
    r = c.post("/billing/webhook", content=body, headers={"stripe-signature": stripe_signature(body)})
    assert r.status_code == 200 and provisioned == ["cust-1"]


def test_unpaid_checkout_is_recorded_but_not_provisioned(client):
    c, provisioned, sql = client
    body = checkout_event("unpaid")  # e.g. a bank debit that hasn't cleared yet
    r = c.post("/billing/webhook", content=body, headers={"stripe-signature": stripe_signature(body)})
    assert r.status_code == 200
    assert any("insert into customers" in q for q in sql)  # customer saved...
    assert provisioned == []  # ...but no money spent on numbers yet
