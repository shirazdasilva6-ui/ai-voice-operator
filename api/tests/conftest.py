import pytest
from psycopg_pool import PoolTimeout

from app.db import pool


@pytest.fixture(scope="session")
def db():
    """Real Postgres for tests that need SQL. Opened once per run (a closed pool can't be reopened).

    Skips cleanly when no database is reachable, e.g. `pytest` outside docker compose.
    """
    try:
        pool.open(wait=True, timeout=3)
    except PoolTimeout:
        pytest.skip("no database available")
    yield
    pool.close()
