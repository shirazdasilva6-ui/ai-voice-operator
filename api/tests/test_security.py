"""Each test proves one protection actually holds. None of them need the database."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import Settings, get_settings, production_problems
from app.security import secret_matches

NO_SECRETS = dict(_env_file=None, vapi_secret="", twilio_auth_token="", dashboard_token="")


def test_secret_matches_only_exact_value():
    assert secret_matches("s3cret", "s3cret")
    assert not secret_matches("s3creT", "s3cret")
    assert not secret_matches("", "s3cret")
    assert not secret_matches(None, "s3cret")


def test_development_never_blocks_startup():
    assert production_problems(Settings(app_env="development", **NO_SECRETS)) == []


def test_production_refuses_to_run_without_secrets():
    problems = production_problems(Settings(app_env="production", **NO_SECRETS))
    assert {"VAPI_SECRET is not set", "TWILIO_AUTH_TOKEN is not set", "DASHBOARD_TOKEN is not set"} <= set(problems)


def test_production_with_all_secrets_is_allowed():
    s = Settings(_env_file=None, app_env="production", vapi_secret="v", twilio_auth_token="t", dashboard_token="d")
    assert production_problems(s) == []


def test_upsert_lead_rejects_unknown_columns():
    # Column names go into SQL text, so anything unexpected must be refused before reaching the DB.
    with pytest.raises(ValueError):
        db.upsert_lead("+15550000000", **{"status; drop table leads": "x"})


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "dash-test")
    monkeypatch.setenv("VAPI_SECRET", "vapi-test")
    get_settings.cache_clear()
    from app.main import app

    yield TestClient(app)  # no `with`: skips lifespan, so no DB pool is opened
    get_settings.cache_clear()


@pytest.mark.parametrize("path", ["/metrics", "/calls", "/vapi/assistant-config"])
def test_private_endpoints_reject_missing_or_wrong_token(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_assistant_config_works_with_token(client):
    r = client.get("/vapi/assistant-config", headers={"Authorization": "Bearer dash-test"})
    assert r.status_code == 200
    assert "<VAPI_SECRET>" in r.text  # placeholder only; the real secret is never echoed


def test_webhook_rejects_wrong_secret(client):
    r = client.post("/vapi/webhook", json={"message": {"type": "status-update"}}, headers={"x-vapi-secret": "wrong"})
    assert r.status_code == 401


def test_webhook_accepts_right_secret(client):
    r = client.post("/vapi/webhook", json={"message": {"type": "status-update"}}, headers={"x-vapi-secret": "vapi-test"})
    assert r.status_code == 200
