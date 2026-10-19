import httpx

from ..config import get_settings

BASE = "https://api.hubapi.com/crm/v3/objects/contacts"

# Pipeline status -> HubSpot's built-in hs_lead_status enum
LEAD_STATUS = {
    "new": "NEW",
    "needs_info": "IN_PROGRESS",
    "qualified": "OPEN",
    "booked": "OPEN_DEAL",
    "disqualified": "UNQUALIFIED",
}


def upsert_contact(phone: str, props: dict, status: str) -> str | None:
    token = get_settings().hubspot_token
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    props = {k: v for k, v in props.items() if v} | {"hs_lead_status": LEAD_STATUS.get(status, "NEW")}

    with httpx.Client(headers=headers, timeout=10) as http:
        found = http.post(
            f"{BASE}/search",
            json={"filterGroups": [{"filters": [{"propertyName": "phone", "operator": "EQ", "value": phone}]}], "limit": 1},
        )
        found.raise_for_status()
        results = found.json().get("results", [])
        if results:
            cid = results[0]["id"]
            http.patch(f"{BASE}/{cid}", json={"properties": props}).raise_for_status()
            return cid
        created = http.post(BASE, json={"properties": {"phone": phone, **props}})
        created.raise_for_status()
        return created.json()["id"]
