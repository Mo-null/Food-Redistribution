"""
Phase 2 checks. Run from the backend folder:  python phase2_checks.py

Part A needs no database.
Part B talks to Postgres and calls the router functions directly (no HTTP/auth needed).
Run it ONLY on a freshly reset DEV database (python reset_db.py). Reset again afterwards.
"""

import sys
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import inspect

from services.reliability import reliability_sample_size, reliability_score

failures = 0


def check(cond, msg):
    global failures
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        failures += 1


def close(a, b):
    return abs(a - b) < 1e-9


# ---------- Part A: reliability formula ----------
check(close(reliability_score(None), 0.5), "no history -> neutral 0.5")
check(
    close(reliability_score({"fulfilled": 1}), 0.55),
    "1 fulfilled pickup -> 0.55, not a perfect 1.0",
)
check(
    close(reliability_score({"fulfilled": 9, "no_show": 1}), 0.9),
    "9 of 10 with enough history -> raw ratio 0.9",
)
check(
    close(reliability_score({"fulfilled": 1, "declined": 5, "ignored": 5}), 0.55),
    "declines and ignored proposals do not change the score",
)
check(
    reliability_sample_size({"fulfilled": 3, "no_show": 2, "declined": 9}) == 5,
    "sample size counts only fulfilled + no_show",
)

# ---------- Part B: database + routers ----------
from db.database import SessionLocal, engine
from models.donation import Donation, DonationStatus
from models.match import Match, MatchStatus
from models.user import User, UserRole, VerificationStatus
from routers.matches import (
    accept_match,
    confirm_pickup,
    decline_match,
    get_match_detail,
    get_my_matches,
)
from routers.reliability import get_user_reliability

check(
    "reliability_records" not in inspect(engine).get_table_names(),
    "the old reliability_records table is gone",
)

db = SessionLocal()
try:
    tag = uuid.uuid4().hex[:8]
    now = datetime.now(UTC)
    LAT, LNG = 28.613912, 77.209021

    def make_user(label, role, **extra):
        u = User(
            username=f"p2_{label}_{tag}",
            email=f"p2_{label}_{tag}@example.com",
            hashed_password="x",
            role=role,
            is_organization=False,
            verification_status=VerificationStatus.not_applicable,
            **extra,
        )
        db.add(u)
        db.flush()
        return u

    def make_match(donor, recipient):
        don = Donation(
            donor_id=donor.id,
            category="cooked_meals",
            quantity=10,
            location_lat=LAT,
            location_lng=LNG,
            expiry_time=now + timedelta(hours=24),
            status=DonationStatus.matched,
        )
        db.add(don)
        db.flush()
        m = Match(
            donation_id=don.id,
            recipient_id=recipient.id,
            score=0.5,
            status=MatchStatus.proposed,
            features={"distance_km": 1.234},
        )
        db.add(m)
        db.commit()
        return m

    def find(responses, match_id):
        return next(r for r in responses if r.id == match_id)

    rec_loc = dict(location_lat=28.62, location_lng=77.21, capacity=10)
    donor = make_user("donor", UserRole.donor)
    r1 = make_user("r1", UserRole.recipient, **rec_loc)
    r2 = make_user("r2", UserRole.recipient, **rec_loc)
    stranger = make_user("stranger", UserRole.recipient, **rec_loc)
    coordinator = make_user("coord", UserRole.coordinator)
    db.commit()

    m1 = make_match(donor, r1)
    m2 = make_match(donor, r2)

    # --- recipient, proposed: approximate location only ---
    seen = find(get_my_matches(db=db, current_user=r1), m1.id)
    check(
        seen.donation.location_is_approximate is True,
        "proposed match: location is flagged approximate",
    )
    check(
        seen.donation.location_lat == round(LAT, 2) and seen.donation.location_lng == round(LNG, 2),
        "proposed match: coordinates are rounded to 2 decimals",
    )
    check(seen.distance_km == 1.2, "proposed match: distance is shown (rounded to 0.1 km)")
    check(
        seen.counterpart is not None and seen.counterpart.username == donor.username,
        "recipient sees the donor's username as counterpart",
    )
    check(
        seen.counterpart.reliability_score is None,
        "recipient is not shown any donor reliability score",
    )

    # --- accept reveals the exact location ---
    accepted = accept_match(m1.id, db=db, current_user=r1)
    check(
        accepted.donation.location_lat == LAT
        and accepted.donation.location_lng == LNG
        and accepted.donation.location_is_approximate is False,
        "accepted match: exact coordinates are revealed to the recipient",
    )

    # --- access control on a single match ---
    try:
        get_match_detail(m1.id, db=db, current_user=stranger)
        check(False, "an unrelated recipient cannot open someone else's match")
    except HTTPException as e:
        check(e.status_code == 403, "an unrelated recipient cannot open someone else's match")

    # --- donor and coordinator views ---
    as_donor = get_match_detail(m1.id, db=db, current_user=donor)
    check(
        as_donor.donation.location_lat == LAT
        and as_donor.donation.location_is_approximate is False,
        "donor always sees the exact location",
    )
    check(
        as_donor.counterpart.username == r1.username
        and as_donor.counterpart.reliability_score == 0.5
        and as_donor.counterpart.reliability_sample_size == 0,
        "donor sees the recipient's reliability (neutral 0.5, no history yet)",
    )

    as_coord = get_match_detail(m1.id, db=db, current_user=coordinator)
    check(
        as_coord.donation.location_lat == LAT and as_coord.counterpart is None,
        "coordinator sees exact location and no single counterpart",
    )

    # --- confirming a pickup feeds the single reliability source ---
    confirm_pickup(m1.id, db=db, current_user=donor)
    after = find(get_my_matches(db=db, current_user=donor), m1.id)
    check(
        after.counterpart.reliability_score == 0.55
        and after.counterpart.reliability_sample_size == 1,
        "after one fulfilled pickup the recipient scores 0.55 with a sample size of 1",
    )

    # --- a declined match does not keep the exact location ---
    decline_match(m2.id, db=db, current_user=r2)
    declined = find(get_my_matches(db=db, current_user=r2), m2.id)
    check(
        declined.donation.location_is_approximate is True,
        "declined match: location is approximate again",
    )

    # --- /reliability access ---
    try:
        get_user_reliability(r1.id, db=db, current_user=stranger)
        check(False, "another recipient cannot read someone's reliability")
    except HTTPException as e:
        check(e.status_code == 403, "another recipient cannot read someone's reliability")
    try:
        get_user_reliability(r1.id, db=db, current_user=donor)
        check(False, "a donor cannot read a recipient's reliability through the endpoint")
    except HTTPException as e:
        check(
            e.status_code == 403,
            "a donor cannot read a recipient's reliability through the endpoint",
        )

    own = get_user_reliability(r1.id, db=db, current_user=r1)
    check(
        own.fulfilled_count == 1 and own.no_show_count == 0 and own.score == 0.55,
        "a user can read their own reliability",
    )
    by_coord = get_user_reliability(r1.id, db=db, current_user=coordinator)
    check(by_coord.fulfilled_count == 1, "a coordinator can read any user's reliability")
    try:
        get_user_reliability(uuid.uuid4(), db=db, current_user=coordinator)
        check(False, "unknown user id returns 404")
    except HTTPException as e:
        check(e.status_code == 404, "unknown user id returns 404")
finally:
    db.close()

print()
print("ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED")
print("Remember: run  python reset_db.py  again to wipe the test data.")
sys.exit(1 if failures else 0)
