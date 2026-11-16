from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client():
    return TestClient(main.app)  # no `with`: skips lifespan, so no DB pool is opened


def test_health_is_ok_without_touching_the_database(client, monkeypatch):
    monkeypatch.setattr(main, "conn", lambda: (_ for _ in ()).throw(AssertionError("must not hit the DB")))
    assert client.get("/health").json() == {"ok": True}


def test_ready_reports_503_when_database_is_down(client, monkeypatch):
    @contextmanager
    def down():
        raise ConnectionError("db down")
        yield

    monkeypatch.setattr(main, "conn", down)
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["database"] == "unreachable"


def test_ready_is_ok_when_database_answers(client, monkeypatch):
    class Conn:
        def execute(self, sql):
            assert sql == "select 1"

    @contextmanager
    def up():
        yield Conn()

    monkeypatch.setattr(main, "conn", up)
    assert client.get("/ready").json() == {"ok": True, "database": "ok"}
