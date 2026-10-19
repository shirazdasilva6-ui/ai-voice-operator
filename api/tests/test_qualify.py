from app.agent.qualify import LeadSignals, decide, score


def test_strong_lead_scores_100_and_qualifies():
    s = LeadSignals(budget_usd=8000, is_decision_maker=True, need="We miss calls after hours", timeline_days=14)
    assert score(s) == 100
    assert decide(s) == "qualified"


def test_budget_below_floor_disqualifies_before_other_fields():
    assert decide(LeadSignals(budget_usd=500)) == "disqualified"


def test_partial_info_needs_more():
    s = LeadSignals(budget_usd=3000)
    assert decide(s) == "needs_info"
    assert s.missing() == ["is_decision_maker", "need", "timeline_days"]


def test_weak_complete_lead_is_disqualified():
    s = LeadSignals(budget_usd=1500, is_decision_maker=False, need="just looking", timeline_days=180)
    assert score(s) == 45
    assert decide(s) == "disqualified"
