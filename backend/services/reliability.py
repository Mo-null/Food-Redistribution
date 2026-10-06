from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.match import Match

NEUTRAL_DEFAULT_SCORE = 0.5
CONFIDENT_AFTER_N_TRANSACTIONS = 10


def get_outcome_counts(db: Session, recipient_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
    if not recipient_ids:
        return {}
    rows = (
        db.query(Match.recipient_id, Match.outcome, func.count(Match.id))
        .filter(Match.recipient_id.in_(recipient_ids), Match.outcome.isnot(None))
        .group_by(Match.recipient_id, Match.outcome)
        .all()
    )
    counts: dict[UUID, dict[str, int]] = {}
    for recipient_id, outcome, n in rows:
        counts.setdefault(recipient_id, {})[outcome.value] = int(n)
    return counts


def reliability_sample_size(counts: dict[str, int] | None) -> int:
    c = counts or {}
    return c.get("fulfilled", 0) + c.get("no_show", 0)


def reliability_score(counts: dict[str, int] | None) -> float:
    total = reliability_sample_size(counts)
    if total == 0:
        return NEUTRAL_DEFAULT_SCORE

    raw_ratio = (counts or {}).get("fulfilled", 0) / total
    confidence = min(total / CONFIDENT_AFTER_N_TRANSACTIONS, 1.0)
    return (confidence * raw_ratio) + ((1 - confidence) * NEUTRAL_DEFAULT_SCORE)
