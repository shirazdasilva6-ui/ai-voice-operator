from datetime import datetime, timedelta, timezone

import httpx

from ..config import get_settings

BASE = "https://api.calendly.com"


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_settings().calendly_token}"}


def available_slots(n: int = 3) -> list[str]:
    s = get_settings()
    start = datetime.now(timezone.utc) + timedelta(minutes=10)
    if not s.calendly_token:
        day = (start + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
        return [(day + timedelta(days=i)).isoformat() for i in range(n)]  # demo mode
    r = httpx.get(
        f"{BASE}/event_type_available_times",
        params={
            "event_type": s.calendly_event_type_uri,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(days=7)).isoformat(),  # API max window is 7 days
        },
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    return [slot["start_time"] for slot in r.json()["collection"][:n]]


def single_use_link() -> str:
    s = get_settings()
    if not s.calendly_token:
        return "https://calendly.com/demo/30min"
    r = httpx.post(
        f"{BASE}/scheduling_links",
        json={"max_event_count": 1, "owner": s.calendly_event_type_uri, "owner_type": "EventType"},
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["resource"]["booking_url"]
