"""claim() is SQL, so test it against real Postgres. Skips when no database is reachable (e.g. CI without one)."""
import uuid

import pytest
from psycopg_pool import PoolTimeout

from app import provisioning as p
from app.db import conn, pool


@pytest.fixture(scope="module")
def db():
    try:
        pool.open(wait=True, timeout=3)
    except PoolTimeout:
        pytest.skip("no database available")
    yield
    pool.close()


def _customer(status: str, started_minutes_ago: int | None) -> str:
    tag = uuid.uuid4().hex  # email and stripe_customer_id are both unique columns
    with conn() as c:
        return str(c.execute(
            """insert into customers (email, stripe_customer_id, provisioning_status, provisioning_started_at)
               values (%s, %s, %s, case when %s::int is null then null else now() - make_interval(mins => %s::int) end)
               returning id""",
            (f"{tag}@example.com", f"cus_test_{tag}", status, started_minutes_ago, started_minutes_ago),
        ).fetchone()["id"])


def test_run_that_died_mid_way_can_be_reclaimed(db):
    stuck = _customer("provisioning", started_minutes_ago=60)  # server restarted an hour ago
    assert p.claim(stuck) is not None


def test_run_in_progress_is_not_stolen(db):
    busy = _customer("provisioning", started_minutes_ago=1)
    assert p.claim(busy) is None


def test_live_customer_is_never_reprovisioned(db):
    live = _customer("live", started_minutes_ago=60)
    assert p.claim(live) is None


def test_claim_stamps_start_time(db):
    cid = _customer("pending", started_minutes_ago=None)
    row = p.claim(cid)
    assert row["provisioning_status"] == "provisioning" and row["provisioning_started_at"] is not None
