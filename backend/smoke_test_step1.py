"""
Step 1 smoke test. Run from the backend folder:  python smoke_test_step1.py

Run it ONLY on a freshly reset DEV database (python reset_db.py), because the
matching round matches every active donation in the DB. Reset again afterwards.
Part A needs no database. Part B talks to your Postgres and calls the router
functions directly (no HTTP/auth needed).
"""

import sys
import uuid
from datetime import UTC, datetime, timedelta

from services.ml_features import CATEGORIES, build_features, normalize_category

failures = 0


def check(cond, msg):
    global failures
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        failures += 1


# ---------- Part A: pure logic ----------
def legacy(hours, dist, qty, cap, rel):
    u = 1 - max(0, min(hours, 48)) / 48
    p = max(0.0, 1 - dist / 10)
    c = max(0.0, 1 - abs(1 - qty / cap))
    return 0.4 * u + 0.25 * p + 0.15 * c + 0.2 * rel


for hours, dist, qty, cap, rel in [
    (10, 3, 8, 10, 0.7),
    (0.5, 9.9, 30, 10, 0.5),
    (100, 0, 10, 10, 1.0),
]:
    f = build_features(
        hours_to_expiry=hours,
        distance_km=dist,
        quantity=qty,
        capacity=cap,
        category="Cooked Meals",
        reliability=rel,
        is_organization=False,
        hour_of_day=12,
        weekday=2,
        history_counts=None,
    )
    check(
        abs(f["rule_score"] - legacy(hours, dist, qty, cap, rel)) < 1e-9,
        f"rule score identical to the original formula ({hours}h, {dist}km)",
    )

check(normalize_category("Cooked Meals") == "cooked_meals", "category 'Cooked Meals' normalizes")
check(normalize_category("bread") == "other", "unknown category becomes 'other'")
check(normalize_category(None) == "other", "missing category becomes 'other'")
check(set(CATEGORIES) >= {"other"}, "category list contains 'other'")

# ---------- Part B: database + routers ----------
from fastapi import HTTPException

from db.database import SessionLocal
from models.donation import Donation, DonationStatus
from models.match import PROPOSAL_TIMEOUT_MINUTES, Match, MatchOutcome, MatchStatus
from models.notification import Notification
from models.user import User, UserRole, VerificationStatus
from routers.matches import accept_match, confirm_pickup, decline_match, reject_match
from schemas.matches import MatchRejection
from services.matching_engine import run_matching_round

db = SessionLocal()
try:
    tag = uuid.uuid4().hex[:8]
    donor = User(
        username=f"smoke_donor_{tag}",
        email=f"smoke_donor_{tag}@example.com",
        hashed_password="x",
        role=UserRole.donor,
        is_organization=False,
        verification_status=VerificationStatus.not_applicable,
    )
    recipients = [
        User(
            username=f"smoke_r{k}_{tag}",
            email=f"smoke_r{k}_{tag}@example.com",
            hashed_password="x",
            role=UserRole.recipient,
            is_organization=False,
            verification_status=VerificationStatus.not_applicable,
            location_lat=28.6139 + k * 0.001,
            location_lng=77.2090,
            capacity=10,
        )
        for k in range(4)
    ]
    db.add(donor)
    db.add_all(recipients)
    db.commit()

    now = datetime.now(UTC)
    donations = [
        Donation(
            donor_id=donor.id,
            category="cooked_meals",
            quantity=10,
            location_lat=28.6139,
            location_lng=77.2090,
            expiry_time=now + timedelta(hours=24),
        )
        for _ in range(4)
    ]
    db.add_all(donations)
    db.commit()

    matches = run_matching_round(db)
    check(len(matches) == 4, f"first round created 4 matches (got {len(matches)})")
    required = {
        "rule_score",
        "urgency",
        "distance_km",
        "category",
        "r_n_prior",
        "model_p",
        "final_score",
    }
    check(
        all(m.features and required <= set(m.features) for m in matches),
        "every match stored a features snapshot",
    )
    check(all(m.outcome is None for m in matches), "new matches start with no outcome")

    by_recipient = {m.recipient_id: m for m in matches}
    r1, r2, r3, r4 = [by_recipient[r.id].recipient for r in recipients]
    m1, m2, m3, m4 = [by_recipient[r.id] for r in recipients]

    decline_match(m1.id, db=db, current_user=r1)
    db.refresh(m1)
    check(
        m1.outcome == MatchOutcome.declined and m1.status == MatchStatus.rejected,
        "decline -> outcome 'declined'",
    )

    accept_match(m2.id, db=db, current_user=r2)
    confirm_pickup(m2.id, db=db, current_user=donor)
    db.refresh(m2)
    check(
        m2.outcome == MatchOutcome.fulfilled and m2.status == MatchStatus.fulfilled,
        "confirm -> outcome 'fulfilled'",
    )

    accept_match(m3.id, db=db, current_user=r3)
    reject_match(m3.id, MatchRejection(recipient_at_fault=True), db=db, current_user=donor)
    db.refresh(m3)
    check(m3.outcome == MatchOutcome.no_show, "reject with fault -> outcome 'no_show'")

    d4 = db.get(Donation, m4.donation_id)
    d4.expiry_time = now - timedelta(hours=1)
    db.commit()

    blocked = {
        (m1.donation_id, m1.recipient_id),
        (m3.donation_id, m3.recipient_id),
        (m4.donation_id, m4.recipient_id),
    }
    new_matches = run_matching_round(db)
    db.refresh(m4)
    check(m4.outcome == MatchOutcome.ignored, "unactioned proposal expiring -> outcome 'ignored'")
    check(len(new_matches) >= 1, f"second round produced new matches (got {len(new_matches)})")
    check(
        all((m.donation_id, m.recipient_id) not in blocked for m in new_matches),
        "declined / no-show / ignored pairs are never re-offered",
    )

    # ---------- Part C: unanswered proposals time out ----------
    stale_age = now - timedelta(minutes=PROPOSAL_TIMEOUT_MINUTES + 1)
    fresh_age = now - timedelta(minutes=PROPOSAL_TIMEOUT_MINUTES - 5)

    def parked(label, status, created_at):
        rec = User(
            username=f"smoke_{label}_{tag}",
            email=f"smoke_{label}_{tag}@example.com",
            hashed_password="x",
            role=UserRole.recipient,
            is_organization=False,
            verification_status=VerificationStatus.not_applicable,
            location_lat=28.6139,
            location_lng=77.2090,
            capacity=10,
        )
        db.add(rec)
        db.flush()
        don = Donation(
            donor_id=donor.id,
            category="cooked_meals",
            quantity=10,
            location_lat=28.6139,
            location_lng=77.2090,
            expiry_time=now + timedelta(hours=24),
            status=DonationStatus.matched,
        )
        db.add(don)
        db.flush()
        m = Match(
            donation_id=don.id, recipient_id=rec.id, score=0.5, status=status, created_at=created_at
        )
        db.add(m)
        db.commit()
        return rec, don, m

    r_stale, d_stale, m_stale = parked("stale", MatchStatus.proposed, stale_age)
    r_fresh, d_fresh, m_fresh = parked("fresh", MatchStatus.proposed, fresh_age)
    r_acc, d_acc, m_acc = parked("acc", MatchStatus.accepted, stale_age)
    r_late, d_late, m_late = parked("late", MatchStatus.proposed, stale_age)

    try:
        accept_match(m_late.id, db=db, current_user=r_late)
        check(False, "accepting a proposal after its deadline is refused")
    except HTTPException as e:
        check(e.status_code == 400, "accepting a proposal after its deadline is refused")
    db.refresh(m_late)
    check(m_late.status == MatchStatus.proposed, "a refused late accept changes nothing")
    check(
        m_fresh.proposal_expires_at is not None and m_fresh.proposal_expires_at > now,
        "an open proposal exposes its deadline (proposal_expires_at)",
    )

    run_matching_round(db)
    for obj in (m_stale, d_stale, m_fresh, d_fresh, m_acc, d_acc, m_late, d_late):
        db.refresh(obj)

    check(
        m_stale.status == MatchStatus.rejected
        and m_stale.outcome == MatchOutcome.ignored
        and m_stale.resolved_at is not None,
        "an unanswered proposal past its deadline -> rejected / 'ignored'",
    )
    check(
        m_late.outcome == MatchOutcome.ignored,
        "a proposal that was refused a late accept is also swept",
    )
    live = (
        db.query(Match)
        .filter(
            Match.donation_id == d_stale.id,
            Match.status.in_([MatchStatus.proposed, MatchStatus.accepted]),
        )
        .count()
    )
    check(
        d_stale.status == DonationStatus.active or live == 1,
        "its donation is back in the pool (or already re-offered), never stuck 'matched' with a dead proposal",
    )
    check(
        db.query(Match)
        .filter(
            Match.donation_id == d_stale.id,
            Match.recipient_id == r_stale.id,
            Match.status == MatchStatus.proposed,
        )
        .count()
        == 0,
        "the recipient who ignored it is not offered the same donation again",
    )
    check(
        m_fresh.status == MatchStatus.proposed and d_fresh.status == DonationStatus.matched,
        "a proposal still inside its window is left alone",
    )
    check(
        m_acc.status == MatchStatus.accepted and d_acc.status == DonationStatus.matched,
        "an old but ACCEPTED match is never swept",
    )
    check(
        m_stale.proposal_expires_at is None,
        "proposal_expires_at disappears once the proposal is closed",
    )

    def expiry_notices(user):
        return (
            db.query(Notification)
            .filter(Notification.user_id == user.id, Notification.message.like("%expired%"))
            .count()
        )

    check(expiry_notices(r_stale) == 1, "the recipient is told their proposal expired")
    run_matching_round(db)
    check(
        expiry_notices(r_stale) == 1,
        "sweeping is idempotent (a second round does not notify again)",
    )
finally:
    db.close()

print()
print("ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED")
print("Remember: run  python reset_db.py  again to wipe the test data.")
sys.exit(1 if failures else 0)
