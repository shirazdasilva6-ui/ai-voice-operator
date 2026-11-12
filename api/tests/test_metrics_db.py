"""/metrics against real Postgres: load-test data must never leak into the live numbers."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app import db as appdb
from app.config import get_settings


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    get_settings.cache_clear()
    from app.main import app

    yield TestClient(app)
    get_settings.cache_clear()


def test_simulated_calls_and_latency_stay_out_of_live_metrics(client):
    before = client.get("/metrics").json()
    tag = uuid.uuid4().hex[:8]

    appdb.save_call(f"live-{tag}", "voice", "+15551110001", simulated=False, cost_usd=0.10)
    appdb.save_call(f"sim-{tag}-a", "voice", "+15551110002", simulated=True, cost_usd=None)
    appdb.save_call(f"sim-{tag}-b", "voice", "+15551110003", simulated=True, cost_usd=None)
    appdb.log_tool_event(f"sim-{tag}-a", "qualify_lead", 99_999, True)  # absurd latency, only in the sim bucket

    after = client.get("/metrics").json()
    assert after["live"]["calls"] - before["live"]["calls"] == 1
    assert after["simulated"]["calls"] - before["simulated"]["calls"] == 2
    # A huge simulated latency must not move the live percentiles.
    assert after["tool_latency_ms"]["live"] == before["tool_latency_ms"]["live"]
    assert after["tool_latency_ms"]["simulated"]["p95"] is not None


def test_cost_saving_is_computed_against_the_human_baseline(client):
    m = client.get("/metrics").json()
    live = m["live"]
    if live["avg_cost_usd"] is not None:
        expected = round(100 * (1 - live["avg_cost_usd"] / m["human_cost_per_call"]), 1)
        assert abs(live["savings_pct"] - expected) <= 0.2  # avg is rounded to 3 dp before the % is computed
