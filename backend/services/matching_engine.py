import logging
from datetime import UTC, datetime, timedelta

import numpy as np
from scipy.optimize import linear_sum_assignment
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import SessionLocal
from models.donation import Donation, DonationStatus
from models.match import PROPOSAL_TIMEOUT_MINUTES, Match, MatchOutcome, MatchStatus
from models.user import User, UserRole, VerificationStatus
from services.match_model import blend, predict_success_batch
from services.ml_features import MAX_MATCH_DISTANCE_KM, build_features, haversine_km
from services.notifications import notify
from services.reliability import get_outcome_counts, reliability_score

logger = logging.getLogger(__name__)

# One round at a time across all workers: the scheduler, new donations and a coordinator can each trigger one.
_MATCHING_ROUND_LOCK_KEY = 918273645

ACCEPTED_CONFIRMATION_GRACE_HOURS = 24


def _pair_features(
    donation: Donation,
    recipient: User,
    reliability: float,
    history_counts: dict[str, int] | None,
    now: datetime,
) -> dict | None:
    if (
        donation.location_lat is None
        or donation.location_lng is None
        or recipient.location_lat is None
        or recipient.location_lng is None
        or recipient.capacity is None
        or recipient.capacity <= 0
    ):
        return None

    distance_km = haversine_km(
        donation.location_lat,
        donation.location_lng,
        recipient.location_lat,
        recipient.location_lng,
    )
    if distance_km > MAX_MATCH_DISTANCE_KM:
        return None

    hours_remaining = (donation.expiry_time - now).total_seconds() / 3600

    return build_features(
        hours_to_expiry=hours_remaining,
        distance_km=distance_km,
        quantity=donation.quantity,
        capacity=recipient.capacity,
        category=donation.category,
        reliability=reliability,
        is_organization=bool(recipient.is_organization),
        hour_of_day=now.hour,
        weekday=now.weekday(),
        history_counts=history_counts,
    )


def _predict(features_list: list[dict]) -> list[float] | None:
    """Learned success probabilities, or None (=> rule score only) if unavailable or failing."""
    if not features_list:
        return None
    try:
        probs = predict_success_batch(features_list)
    except Exception:
        logger.exception("Match model failed; falling back to rule score")
        return None
    if probs is None or len(probs) != len(features_list):
        return None
    return [float(p) for p in probs]


def expire_stale_donations(db: Session) -> int:

    now = datetime.now(UTC)
    accepted_cutoff = now - timedelta(hours=ACCEPTED_CONFIRMATION_GRACE_HOURS)
    count = 0

    stale_active = (
        db.query(Donation)
        .filter(Donation.status == DonationStatus.active, Donation.expiry_time < now)
        .all()
    )
    for donation in stale_active:
        donation.status = DonationStatus.expired
        notify(db, donation.donor_id, f"Your donation ({donation.category}) expired unclaimed.")
        count += 1

    stale_matched = (
        db.query(Donation)
        .filter(Donation.status == DonationStatus.matched, Donation.expiry_time < now)
        .all()
    )
    for donation in stale_matched:
        open_match = (
            db.query(Match)
            .filter(
                Match.donation_id == donation.id,
                Match.status.in_([MatchStatus.proposed, MatchStatus.accepted]),
            )
            .first()
        )

        if open_match and open_match.status == MatchStatus.accepted:
            if donation.expiry_time > accepted_cutoff:
                continue

            # Nobody can tell whether the pickup happened, so neither side is penalised.
            open_match.status = MatchStatus.rejected
            open_match.outcome = MatchOutcome.withdrawn
            open_match.resolved_at = now
            donation.status = DonationStatus.expired
            notify(
                db,
                open_match.recipient_id,
                "Your accepted pickup was closed because the donation expired and was never confirmed.",
            )
            notify(
                db,
                donation.donor_id,
                f"Your donation ({donation.category}) expired and its accepted pickup was closed "
                "because it was never confirmed.",
            )
            count += 1
            continue

        if open_match:
            open_match.status = MatchStatus.rejected
            open_match.outcome = MatchOutcome.ignored
            open_match.resolved_at = now

        donation.status = DonationStatus.expired
        notify(db, donation.donor_id, f"Your donation ({donation.category}) expired unclaimed.")
        count += 1

    db.commit()
    return count


def expire_stale_proposals(db: Session) -> int:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=PROPOSAL_TIMEOUT_MINUTES)

    # skip_locked: if a recipient is accepting or declining this very proposal right now,
    # leave it alone. Their action wins, and the two never fight over the same row.
    stale = (
        db.query(Match)
        .filter(Match.status == MatchStatus.proposed, Match.created_at < cutoff)
        .with_for_update(skip_locked=True)
        .all()
    )
    for match in stale:
        match.status = MatchStatus.rejected
        match.outcome = MatchOutcome.ignored
        match.resolved_at = now

        donation = db.query(Donation).filter(Donation.id == match.donation_id).first()
        if donation and donation.status == DonationStatus.matched and donation.expiry_time > now:
            donation.status = DonationStatus.active

        notify(
            db,
            match.recipient_id,
            "Your pickup proposal expired because it was not answered in time.",
        )

    db.commit()
    return len(stale)


def run_matching_round(db: Session) -> list[Match]:

    engine = db.get_bind()
    lock_conn = engine.connect()
    lock_acquired = False
    try:
        lock_acquired = lock_conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": _MATCHING_ROUND_LOCK_KEY},
        ).scalar()

        if not lock_acquired:
            return []

        try:
            return _run_matching_round_locked(db)
        except Exception:
            db.rollback()
            raise
    finally:
        if lock_acquired:
            lock_conn.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": _MATCHING_ROUND_LOCK_KEY},
            )
        lock_conn.close()


def run_matching_round_in_new_session() -> None:
    db = SessionLocal()
    try:
        run_matching_round(db)
    finally:
        db.close()


def _run_matching_round_locked(db: Session) -> list[Match]:
    expired_donations = expire_stale_donations(db)
    expired_proposals = expire_stale_proposals(db)
    created_matches = _create_matches(db)

    if expired_donations or expired_proposals or created_matches:
        logger.info(
            "Matching round: %d match(es) created, %d donation(s) expired, %d proposal(s) expired",
            len(created_matches),
            expired_donations,
            expired_proposals,
        )
    return created_matches


def _create_matches(db: Session) -> list[Match]:
    active_donations = db.query(Donation).filter(Donation.status == DonationStatus.active).all()

    all_recipients = db.query(User).filter(User.role == UserRole.recipient).all()
    busy_recipient_ids = {
        m.recipient_id
        for m in db.query(Match)
        .filter(Match.status.in_([MatchStatus.proposed, MatchStatus.accepted]))
        .all()
    }
    recipients = [
        r
        for r in all_recipients
        if r.id not in busy_recipient_ids
        and not (r.is_organization and r.verification_status != VerificationStatus.verified)
    ]

    if not active_donations or not recipients:
        return []

    history_by_recipient = get_outcome_counts(db, [r.id for r in recipients])
    reliability_by_recipient = {
        r.id: reliability_score(history_by_recipient.get(r.id)) for r in recipients
    }

    blocked_pairs = {
        (donation_id, recipient_id)
        for donation_id, recipient_id in (
            db.query(Match.donation_id, Match.recipient_id)
            .filter(Match.outcome.in_(MatchOutcome.no_reoffer()))
            .all()
        )
    }

    now = datetime.now(UTC)

    candidates = []
    for i, donation in enumerate(active_donations):
        for j, recipient in enumerate(recipients):
            if (donation.id, recipient.id) in blocked_pairs:
                continue
            feats = _pair_features(
                donation,
                recipient,
                reliability_by_recipient[recipient.id],
                history_by_recipient.get(recipient.id),
                now,
            )
            if feats is not None:
                candidates.append((i, j, feats))

    if not candidates:
        return []

    probs = _predict([c[2] for c in candidates])

    n_donations, n_recipients = len(active_donations), len(recipients)
    cost_matrix = np.full((n_donations, n_recipients), fill_value=1e6)
    stored_features: dict = {}

    for k, (i, j, feats) in enumerate(candidates):
        p = probs[k] if probs is not None else None
        final = float(blend(feats["rule_score"], p))
        cost_matrix[i][j] = -final  # the solver minimizes, so a better score is a lower cost
        feats["model_p"] = p
        feats["final_score"] = final
        stored_features[(i, j)] = feats

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    created_matches: list[Match] = []
    for i, j in zip(row_ind, col_ind):
        if cost_matrix[i][j] >= 1e6:
            continue

        donation = active_donations[i]
        recipient = recipients[j]

        match = Match(
            donation_id=donation.id,
            recipient_id=recipient.id,
            score=float(-cost_matrix[i][j]),
            status=MatchStatus.proposed,
            features=stored_features[(i, j)],
        )
        donation.status = DonationStatus.matched
        db.add(match)
        created_matches.append(match)
        notify(db, recipient.id, "A new high-priority donation match is available for you.")

    db.commit()
    for m in created_matches:
        db.refresh(m)

    return created_matches
