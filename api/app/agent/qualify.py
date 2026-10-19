"""Lead qualification. The LLM only extracts signals; this module decides.

Kept free of I/O so it is trivially unit-testable and auditable by the business owner.
"""
from dataclasses import asdict, dataclass

MIN_BUDGET_USD = 1_000
QUALIFIED_THRESHOLD = 60


@dataclass
class LeadSignals:
    budget_usd: int | None = None
    is_decision_maker: bool | None = None
    need: str | None = None
    timeline_days: int | None = None

    def missing(self) -> list[str]:
        return [k for k, v in asdict(self).items() if v is None]


def score(s: LeadSignals) -> int:
    """BANT score 0-100."""
    pts = 0
    if s.budget_usd is not None:
        pts += 30 if s.budget_usd >= MIN_BUDGET_USD * 5 else 20 if s.budget_usd >= MIN_BUDGET_USD else 0
    if s.is_decision_maker:
        pts += 25
    if s.need and len(s.need.strip()) > 10:
        pts += 20
    if s.timeline_days is not None:
        pts += 25 if s.timeline_days <= 30 else 15 if s.timeline_days <= 90 else 5
    return pts


def decide(s: LeadSignals) -> str:
    if s.budget_usd is not None and s.budget_usd < MIN_BUDGET_USD:
        return "disqualified"  # hard floor: no point collecting the rest
    if s.missing():
        return "needs_info"
    return "qualified" if score(s) >= QUALIFIED_THRESHOLD else "disqualified"
