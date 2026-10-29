from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from .config import get_settings

pool = ConnectionPool(get_settings().database_url, kwargs={"row_factory": dict_row}, open=False)


@contextmanager
def conn():
    with pool.connection() as c:
        yield c


LEAD_COLUMNS = {
    "name", "email", "company", "budget_usd", "is_decision_maker", "need",
    "timeline_days", "score", "status", "hubspot_id", "booking_url",
}


def upsert_lead(phone: str, **fields) -> dict:
    fields = {k: v for k, v in fields.items() if v is not None}
    # Column names are interpolated into SQL (values never are), so only known columns may get through.
    if unknown := set(fields) - LEAD_COLUMNS:
        raise ValueError(f"unknown lead columns: {sorted(unknown)}")
    cols = ["phone", *fields]
    updates = ", ".join(f"{k} = excluded.{k}" for k in fields) or "phone = excluded.phone"
    with conn() as c:
        return c.execute(
            f"insert into leads ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))}) "
            f"on conflict (phone) do update set {updates}, updated_at = now() returning *",
            [phone, *fields.values()],
        ).fetchone()


def get_lead(phone: str) -> dict | None:
    with conn() as c:
        return c.execute("select * from leads where phone = %s", (phone,)).fetchone()


def log_tool_event(call_id: str | None, tool: str, latency_ms: int, ok: bool) -> None:
    with conn() as c:
        c.execute(
            "insert into tool_events (call_external_id, tool, latency_ms, ok) values (%s, %s, %s, %s)",
            (call_id, tool, latency_ms, ok),
        )


def save_call(external_id: str, channel: str, phone: str, simulated: bool, **fields) -> None:
    lead = get_lead(phone)
    with conn() as c:
        c.execute(
            """insert into calls (external_id, channel, lead_id, duration_s, cost_usd, outcome, summary, transcript, simulated)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               on conflict (external_id) do nothing""",
            (
                external_id, channel, lead["id"] if lead else None,
                fields.get("duration_s"), fields.get("cost_usd"),
                lead["status"] if lead else "no_lead",
                fields.get("summary"), fields.get("transcript"), simulated,
            ),
        )


def load_history(phone: str, limit: int = 40) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "select role, content from (select * from messages where phone = %s order by id desc limit %s) m order by id",
            (phone, limit),
        ).fetchall()
    msgs = [{"role": r["role"], "content": r["content"]} for r in rows]
    # Truncation must not start on a tool_result / assistant turn or the API rejects the history.
    while msgs and not (msgs[0]["role"] == "user" and isinstance(msgs[0]["content"], str)):
        msgs.pop(0)
    return msgs


def append_message(phone: str, role: str, content) -> None:
    with conn() as c:
        c.execute("insert into messages (phone, role, content) values (%s, %s, %s)", (phone, role, Jsonb(content)))
