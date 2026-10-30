from types import SimpleNamespace

import pytest

from app import provisioning as p
from app.routes.billing import client_country, should_provision

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

    def buy_number(country, customer_id):
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
        p.buy_number("ZA", "cust-1")


# --- review fixes ---------------------------------------------------------------------------------------------

def test_only_provisions_once_payment_has_cleared():
    assert should_provision({"payment_status": "paid"})
    assert should_provision({"payment_status": "no_payment_required"})  # e.g. 100% coupon
    assert not should_provision({"payment_status": "unpaid"})  # bank debit still pending: don't buy numbers yet
    assert not should_provision({})


def _fake_twilio(monkeypatch, owned):
    created = []
    numbers = SimpleNamespace(
        list=lambda friendly_name, limit: owned,
        create=lambda **kw: created.append(kw) or SimpleNamespace(phone_number="+15550009999", sid="PNnew"),
    )
    local = SimpleNamespace(list=lambda **kw: [SimpleNamespace(phone_number="+15550009999")])
    client = SimpleNamespace(incoming_phone_numbers=numbers, available_phone_numbers=lambda country: SimpleNamespace(local=local))
    monkeypatch.setattr(p, "Client", lambda sid, token: client)
    return created


def test_retry_after_crash_reuses_number_instead_of_buying_another(monkeypatch):
    # A previous run bought the number, then died before save(): Twilio still has it under the customer's tag.
    created = _fake_twilio(monkeypatch, owned=[SimpleNamespace(phone_number="+15550001111", sid="PNold")])
    assert p.buy_number("US", "cust-1") == ("+15550001111", "PNold")
    assert created == []


def test_new_number_is_tagged_with_customer_id(monkeypatch):
    created = _fake_twilio(monkeypatch, owned=[])
    assert p.buy_number("US", "cust-1") == ("+15550009999", "PNnew")
    assert created[0]["friendly_name"] == "vo-cust-1"


def test_onboarding_email_escapes_client_supplied_name():
    out = p.onboarding_html('<img src=x onerror="alert(1)">', "+15550001111")
    assert "<img" not in out and "&lt;img" in out


def test_save_rejects_unknown_columns():
    with pytest.raises(ValueError):
        p.save("cust-1", **{"status; drop table customers": "x"})
