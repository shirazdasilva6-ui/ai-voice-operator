"""Vapi webhook against real Postgres: retries must not duplicate calls, and Vapi's payload quirks must work."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import conn


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.delenv("VAPI_SECRET", raising=False)
    get_settings.cache_clear()
    from app.main import app

    yield TestClient(app)  # no `with`: the session `db` fixture owns the pool
    get_settings.cache_clear()


def end_of_call(call_id: str, phone: str) -> dict:
    return {"message": {"type": "end-of-call-report", "call": {"id": call_id, "customer": {"number": phone}},
                        "durationSeconds": 95, "cost": 0.11, "analysis": {"summary": "test"}}}


def calls_with_id(call_id: str) -> int:
    with conn() as c:
        return c.execute("select count(*) as n from calls where external_id = %s", (call_id,)).fetchone()["n"]


def test_retried_end_of_call_report_is_stored_once(client):
    # Vapi retries webhooks; the README promises a retry can't create a duplicate call.
    call_id = f"sim-test-{uuid.uuid4()}"
    for _ in range(3):
        assert client.post("/vapi/webhook", json=end_of_call(call_id, "+15550000042")).status_code == 200
    assert calls_with_id(call_id) == 1


def test_tool_arguments_sent_as_a_json_string_are_parsed(client):
    # Vapi can send function arguments either as an object or as a JSON-encoded string.
    phone = f"+1666{uuid.uuid4().int % 10**7:07d}"
    payload = {"message": {"type": "tool-calls", "call": {"id": f"sim-test-{uuid.uuid4()}", "customer": {"number": phone}},
                           "toolCallList": [{"id": "t1", "function": {"name": "qualify_lead",
                                                                    "arguments": json.dumps({"budget_usd": 500})}}]}}
    r = client.post("/vapi/webhook", json=payload)
    assert r.status_code == 200
    result = json.loads(r.json()["results"][0]["result"])
    assert result["status"] == "disqualified"  # $500 is below the floor, so the string was really parsed
