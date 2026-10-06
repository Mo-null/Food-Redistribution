"""
Phase 1 checks. Run from the backend folder:  python phase1_checks.py

Part A needs no database.
Part B talks to Postgres: run it ONLY on a freshly reset DEV database
(python reset_db.py), because a matching round touches every donation in the DB.
Reset again afterwards.
"""

import sys
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from schemas.donations import DonationCreate
from schemas.users import ChangePassword, UserCreate

failures = 0


def check(cond, msg):
    global failures
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        failures += 1


def rejected(fn):
    try:
        fn()
        return False
    except ValidationError:
        return True


# ---------- Part A: validation ----------
future = datetime.now(UTC) + timedelta(hours=5)
base = dict(
    category="cooked_meals", quantity=10, location_lat=28.6, location_lng=77.2, expiry_time=future
)

check(not rejected(lambda: DonationCreate(**base)), "a normal donation is accepted")
check(
    rejected(lambda: DonationCreate(**{**base, "quantity": float("inf")})),
    "quantity=inf is rejected",
)
check(
    rejected(lambda: DonationCreate(**{**base, "quantity": float("nan")})),
    "quantity=nan is rejected",
)
check(
    rejected(lambda: DonationCreate(**{**base, "quantity": 10**9})), "absurd quantity is rejected"
)
check(rejected(lambda: DonationCreate(**{**base, "location_lat": 91})), "latitude 91 is rejected")
check(
    rejected(lambda: DonationCreate(**{**base, "location_lng": -181})), "longitude -181 is rejected"
)
check(
    rejected(
        lambda: DonationCreate(**{**base, "expiry_time": datetime.now(UTC) + timedelta(days=30)})
    ),
    "expiry more than 336 hours away is rejected",
)
check(
    rejected(
        lambda: DonationCreate.model_validate_json(
            '{"category":"bakery","quantity":Infinity,"location_lat":1,"location_lng":1,'
            f'"expiry_time":"{future.isoformat()}"}}'
        )
    ),
    "raw JSON 'Infinity' is rejected",
)

user = dict(username="Bob", email="Bob@Example.COM", password="secret1", role="donor")
created = UserCreate(**user)
check(
    created.username == "bob" and created.email == "bob@example.com",
    "username and email are lowercased",
)
check(
    rejected(lambda: UserCreate(**{**user, "password": "é" * 40})), "80-byte password is rejected"
)
check(
    not rejected(lambda: UserCreate(**{**user, "password": "a" * 72})),
    "72-byte password is accepted",
)
check(
    rejected(lambda: ChangePassword(current_password="x", new_password="é" * 40)),
    "change-password enforces the byte limit too",
)

from utils.security import verify_password

check(
    verify_password("é" * 40, "not-a-valid-hash") is False,
    "verify_password returns False on a bad hash",
)

# ---------- Part B: accepted match auto-close ----------
from db.database import SessionLocal
from models.donation import Donation, DonationStatus
from models.match import Match, MatchOutcome, MatchStatus
from models.notification import Notification
from models.user import User, UserRole, VerificationStatus
from services.matching_engine import ACCEPTED_CONFIRMATION_GRACE_HOURS, run_matching_round

db = SessionLocal()
try:
    tag = uuid.uuid4().hex[:8]
    now = datetime.now(UTC)

    def make_user(label, role, **extra):
        u = User(
            username=f"p1_{label}_{tag}",
            email=f"p1_{label}_{tag}@example.com",
            hashed_password="x",
            role=role,
            is_organization=False,
            verification_status=VerificationStatus.not_applicable,
            **extra,
        )
        db.add(u)
        db.flush()
        return u

    def accepted_pair(label, expired_hours_ago):
        donor = make_user(f"{label}_donor", UserRole.donor)
        recipient = make_user(
            f"{label}_rec",
            UserRole.recipient,
            location_lat=28.6139,
            location_lng=77.2090,
            capacity=10,
        )
        donation = Donation(
            donor_id=donor.id,
            category="cooked_meals",
            quantity=10,
            location_lat=28.6139,
            location_lng=77.2090,
            expiry_time=now - timedelta(hours=expired_hours_ago),
            status=DonationStatus.matched,
        )
        db.add(donation)
        db.flush()
        match = Match(
            donation_id=donation.id,
            recipient_id=recipient.id,
            score=0.5,
            status=MatchStatus.accepted,
        )
        db.add(match)
        db.commit()
        return donor, recipient, donation, match

    d_old, r_old, don_old, m_old = accepted_pair("old", ACCEPTED_CONFIRMATION_GRACE_HOURS + 1)
    d_new, r_new, don_new, m_new = accepted_pair("new", 2)

    run_matching_round(db)
    for obj in (m_old, don_old, m_new, don_new):
        db.refresh(obj)

    check(
        m_old.status == MatchStatus.rejected
        and m_old.outcome == MatchOutcome.withdrawn
        and m_old.resolved_at is not None,
        "accepted match 25h past expiry is closed as 'withdrawn'",
    )
    check(don_old.status == DonationStatus.expired, "its donation is marked expired")
    check(
        m_new.status == MatchStatus.accepted and don_new.status == DonationStatus.matched,
        "accepted match only 2h past expiry is left alone (still inside the grace period)",
    )

    def count_notes(user):
        return db.query(Notification).filter(Notification.user_id == user.id).count()

    check(count_notes(r_old) == 1 and count_notes(d_old) == 1, "both sides are notified once")
    run_matching_round(db)
    check(
        count_notes(r_old) == 1 and count_notes(d_old) == 1, "a second round does not notify again"
    )

    busy = (
        db.query(Match)
        .filter(
            Match.recipient_id == r_old.id,
            Match.status.in_([MatchStatus.proposed, MatchStatus.accepted]),
        )
        .count()
    )
    check(busy == 0, "the recipient is no longer 'busy'")
finally:
    db.close()

print()
print("ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED")
print("Remember: run  python reset_db.py  again to wipe the test data.")
sys.exit(1 if failures else 0)
