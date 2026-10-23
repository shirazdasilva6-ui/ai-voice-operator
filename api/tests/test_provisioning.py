import pytest

from app import provisioning as p
from app.routes.billing import client_country

ROW = {
    "email": "owner@agency.co.uk", "business_name": "Acme Lettings", "country": "GB",
    "vapi_assistant_id": None, "phone_number": None, "vapi_phone_number_id": None,
}


@pytest.fixture
def fake(monkeypatch):
    calls = {"vapi": [], "emails": [], "saved": {}, "bought": []}
    monkeypatch.setattr(p, "claim", lambda cid: dict(ROW))
    monkeypatch.setattr(p, "save", lambda cid, **f: calls["saved"].update(f))
    monkeypatch.setattr(p, "send_email", lambda to, subj, html: calls["emails"].append((to, subj)))

    def vapi_post(path, body):
        calls["vapi"].append((path, body))
        return {"id": "asst_1" if path == "/assistant" else "pn_1"}

    def buy_number(country, business):
        calls["bought"].append(country)
        return "+442071234567", "PN123"

    monkeypatch.setattr(p, "vapi_post", vapi_post)
    monkeypatch.setattr(p, "buy_number", buy_number)
    return calls


def test_happy_path_buys_number_in_client_country_and_goes_live(fake):
    p.provision_customer("cust-1")
    assert fake["bought"] == ["GB"]
    assert [path for path, _ in fake["vapi"]] == ["/assistant", "/phone-number"]
    assert fake["vapi"][1][1]["assistantId"] == "asst_1"
    assert "?customer=cust-1" in fake["vapi"][0][1]["server"]["url"]
    assert fake["saved"]["provisioning_status"] == "live"
    assert fake["emails"][0][0] == "owner@agency.co.uk"


def test_retry_skips_steps_already_done(fake, monkeypatch):
    monkeypatch.setattr(p, "claim", lambda cid: {**ROW, "vapi_assistant_id": "asst_0", "phone_number": "+15550001111"})
    p.provision_customer("cust-1")
    assert fake["bought"] == []
    assert [path for path, _ in fake["vapi"]] == ["/phone-number"]


def test_already_claimed_does_nothing(fake, monkeypatch):
    monkeypatch.setattr(p, "claim", lambda cid: None)
    p.provision_customer("cust-1")
    assert fake["vapi"] == [] and fake["emails"] == []


def test_no_number_available_flags_manual_and_still_onboards(fake, monkeypatch):
    def refuse(country, business):
        raise p.NumberUnavailable("needs bundle")

    monkeypatch.setattr(p, "buy_number", refuse)
    p.provision_customer("cust-1")
    assert fake["saved"]["provisioning_status"] == "needs_manual_number"
    assert len(fake["emails"]) == 1  # ops_email unset in tests, so only the client email


def test_vapi_failure_marks_failed(fake, monkeypatch):
    monkeypatch.setattr(p, "vapi_post", lambda path, body: (_ for _ in ()).throw(RuntimeError("vapi 500")))
    p.provision_customer("cust-1")
    assert fake["saved"]["provisioning_status"] == "failed"
    assert "vapi 500" in fake["saved"]["provisioning_error"]


def test_client_country_prefers_metadata_then_billing_address():
    assert client_country({"metadata": {"country": "ae"}}) == "AE"
    assert client_country({"metadata": {}, "customer_details": {"address": {"country": "AU"}}}) == "AU"
    assert client_country({}) == "US"


def test_unsupported_country_is_not_bought():
    with pytest.raises(p.NumberUnavailable):
        p.buy_number("ZA", "Acme")
