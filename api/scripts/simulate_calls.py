"""Load test: push N synthetic conversations through the real webhook -> tools -> scoring -> DB path.

Calls get ids prefixed `sim-`, so they are stored with simulated=true, skip HubSpot/SMS/Calendly,
and never mix with live metrics. No cost is reported for simulated calls; real cost only comes from Vapi.

    python -m scripts.simulate_calls --n 800
"""
import argparse
import json
import os
import random
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

NEEDS = [
    "Our inbound leads go to voicemail after 5pm",
    "We miss about a third of calls at peak hours",
    "Need someone to qualify demo requests before sales",
    "Just looking",
]
HEADERS = {"x-vapi-secret": os.getenv("VAPI_SECRET", "")}


def tool_call(client: httpx.Client, call: dict, name: str, args: dict) -> dict:
    payload = {"message": {"type": "tool-calls", "call": call,
                           "toolCallList": [{"id": str(uuid.uuid4()), "function": {"name": name, "arguments": args}}]}}
    r = client.post("/vapi/webhook", json=payload, headers=HEADERS)
    r.raise_for_status()
    return json.loads(r.json()["results"][0]["result"])


def one_call(i: int, base: str) -> str:
    call = {"id": f"sim-{uuid.uuid4()}", "customer": {"number": f"+1555{i:07d}"}}
    signals = {
        "budget_usd": random.choice([500, 1500, 3000, 8000]),
        "is_decision_maker": random.random() < 0.6,
        "need": random.choice(NEEDS),
        "timeline_days": random.choice([7, 30, 60, 180]),
    }
    with httpx.Client(base_url=base, timeout=30) as c:
        tool_call(c, call, "qualify_lead", {"need": signals["need"]})  # partial info first, like a real call
        res = tool_call(c, call, "qualify_lead", signals)
        if res.get("status") == "qualified":
            tool_call(c, call, "get_available_slots", {})
            tool_call(c, call, "book_meeting", {"name": f"Sim {i}", "email": f"sim{i}@example.com"})
        c.post("/vapi/webhook", headers=HEADERS, json={"message": {
            "type": "end-of-call-report", "call": call, "durationSeconds": random.randint(45, 240),
            "analysis": {"summary": f"Simulated lead -> {res.get('status')}"}}}).raise_for_status()
    return res.get("status", "error")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=800)
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--workers", type=int, default=16)
    a = p.parse_args()

    with ThreadPoolExecutor(a.workers) as ex:
        outcomes = list(ex.map(lambda i: one_call(i, a.base), range(a.n)))
    print({k: outcomes.count(k) for k in set(outcomes)})
    print(httpx.get(f"{a.base}/metrics").json())


if __name__ == "__main__":
    main()
