from fastapi import APIRouter

from ..config import get_settings
from ..db import conn

router = APIRouter(tags=["metrics"])


def _bucket(row: dict | None, human_cost: float) -> dict:
    if not row:
        return {"calls": 0, "avg_cost_usd": None, "booked_rate": None, "savings_pct": None}
    avg = float(row["avg_cost"]) if row["avg_cost"] is not None else None
    return {
        "calls": row["calls"],
        "avg_cost_usd": round(avg, 3) if avg is not None else None,
        "booked_rate": round(row["booked"] / row["calls"], 3) if row["calls"] else None,
        "savings_pct": round(100 * (1 - avg / human_cost), 1) if avg is not None else None,
    }


@router.get("/metrics")
def metrics():
    human = get_settings().human_cost_per_call
    with conn() as c:
        calls = {
            r["simulated"]: r
            for r in c.execute(
                """select simulated, count(*) as calls, avg(cost_usd) as avg_cost,
                          count(*) filter (where outcome = 'booked') as booked
                   from calls group by simulated"""
            ).fetchall()
        }
        latency = {
            r["simulated"]: {"p50": r["p50"], "p95": r["p95"]}
            for r in c.execute(
                """select coalesce(call_external_id like 'sim-%%', false) as simulated,
                          percentile_cont(0.5) within group (order by latency_ms) as p50,
                          percentile_cont(0.95) within group (order by latency_ms) as p95
                   from tool_events where ok group by 1"""
            ).fetchall()
        }
        wa = c.execute("select count(distinct phone) as n from messages").fetchone()

    empty = {"p50": None, "p95": None}
    return {
        "live": _bucket(calls.get(False), human),
        "simulated": _bucket(calls.get(True), human),
        "human_cost_per_call": human,
        "tool_latency_ms": {"live": latency.get(False, empty), "simulated": latency.get(True, empty)},
        "whatsapp_conversations": wa["n"],
    }


@router.get("/calls")
def recent_calls(limit: int = 50):
    with conn() as c:
        rows = c.execute(
            """select c.created_at, c.channel, c.duration_s, c.cost_usd, c.outcome, c.summary, c.simulated,
                      right(l.phone, 4) as phone_last4, l.score
               from calls c left join leads l on l.id = c.lead_id
               order by c.created_at desc limit %s""",
            (min(limit, 200),),
        ).fetchall()
    return rows
