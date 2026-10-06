from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from models.donation import Donation, DonationStatus
from models.match import Match, MatchOutcome, MatchStatus
from models.user import User, UserRole
from schemas.matches import CounterpartSummary, DonationSummary, MatchRejection, MatchResponse
from services.notifications import notify
from services.reliability import get_outcome_counts, reliability_sample_size, reliability_score
from utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/matches", tags=["matches"])

EXACT_LOCATION_STATUSES = (MatchStatus.accepted, MatchStatus.fulfilled)
APPROXIMATE_COORDINATE_DECIMALS = 2


def _counterpart(
    user: User | None, counts: dict[str, int], show_reliability: bool
) -> CounterpartSummary | None:
    if user is None:
        return None
    summary = CounterpartSummary(
        username=user.username,
        is_organization=bool(user.is_organization),
        verification_status=user.verification_status,
    )
    if show_reliability:
        summary.reliability_score = round(reliability_score(counts), 3)
        summary.reliability_sample_size = reliability_sample_size(counts)
    return summary


def _build_match_response(
    match: Match, viewer: User, users: dict[UUID, User], counts: dict[UUID, dict[str, int]]
) -> MatchResponse:
    donation = match.donation

    donation_summary = None
    if donation is not None:
        hide_exact_location = (
            viewer.role == UserRole.recipient and match.status not in EXACT_LOCATION_STATUSES
        )
        lat, lng = donation.location_lat, donation.location_lng
        if hide_exact_location:
            lat = round(lat, APPROXIMATE_COORDINATE_DECIMALS)
            lng = round(lng, APPROXIMATE_COORDINATE_DECIMALS)
        donation_summary = DonationSummary(
            donor_id=donation.donor_id,
            category=donation.category,
            description=donation.description,
            quantity=donation.quantity,
            location_lat=lat,
            location_lng=lng,
            location_is_approximate=hide_exact_location,
            expiry_time=donation.expiry_time,
        )

    counterpart = None
    if viewer.role == UserRole.recipient and donation is not None:
        counterpart = _counterpart(users.get(donation.donor_id), {}, show_reliability=False)
    elif viewer.role == UserRole.donor:
        counterpart = _counterpart(
            users.get(match.recipient_id), counts.get(match.recipient_id, {}), show_reliability=True
        )

    distance = (match.features or {}).get("distance_km")

    return MatchResponse(
        id=match.id,
        donation_id=match.donation_id,
        recipient_id=match.recipient_id,
        score=match.score,
        status=match.status,
        outcome=match.outcome,
        created_at=match.created_at,
        resolved_at=match.resolved_at,
        proposal_expires_at=match.proposal_expires_at,
        distance_km=round(float(distance), 1) if distance is not None else None,
        donation=donation_summary,
        counterpart=counterpart,
    )


def _build_match_responses(db: Session, matches: list[Match], viewer: User) -> list[MatchResponse]:
    if viewer.role == UserRole.recipient:
        counterpart_ids = {m.donation.donor_id for m in matches if m.donation is not None}
    elif viewer.role == UserRole.donor:
        counterpart_ids = {m.recipient_id for m in matches}
    else:
        counterpart_ids = set()

    users: dict[UUID, User] = {}
    if counterpart_ids:
        users = {u.id: u for u in db.query(User).filter(User.id.in_(list(counterpart_ids))).all()}

    counts: dict[UUID, dict[str, int]] = {}
    if viewer.role == UserRole.donor:
        counts = get_outcome_counts(db, list(counterpart_ids))

    return [_build_match_response(m, viewer, users, counts) for m in matches]


def _respond(db: Session, match: Match, viewer: User) -> MatchResponse:
    return _build_match_responses(db, [match], viewer)[0]


@router.get("", response_model=list[MatchResponse])
def get_my_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.recipient:
        matches = (
            db.query(Match)
            .options(joinedload(Match.donation))
            .filter(Match.recipient_id == current_user.id)
            .all()
        )
    elif current_user.role == UserRole.donor:
        matches = (
            db.query(Match)
            .options(joinedload(Match.donation))
            .join(Donation, Match.donation_id == Donation.id)
            .filter(Donation.donor_id == current_user.id)
            .all()
        )
    else:
        raise HTTPException(status_code=403, detail="Only donors and recipients have matches")

    return _build_match_responses(db, matches, current_user)


@router.post("/{match_id}/accept", response_model=MatchResponse)
def accept_match(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.recipient)),
):
    match = db.query(Match).filter(Match.id == match_id).with_for_update().first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your match")
    if match.status != MatchStatus.proposed:
        raise HTTPException(status_code=400, detail="Match is not in a proposable state")
    if match.proposal_expires_at < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="This proposal has expired")

    donation = db.query(Donation).filter(Donation.id == match.donation_id).first()
    # A scheduled round could have expired this donation in the gap between the
    # match being proposed and the recipient acting on it.
    if not donation or donation.status != DonationStatus.matched:
        raise HTTPException(status_code=400, detail="This donation is no longer available")
    if donation.expiry_time < datetime.now(UTC):
        raise HTTPException(status_code=400, detail="This donation has expired")

    match.status = MatchStatus.accepted
    notify(
        db,
        donation.donor_id,
        "A recipient has accepted your donation. Please confirm pickup once completed.",
    )

    db.commit()
    db.refresh(match)
    return _respond(db, match, current_user)


@router.post("/{match_id}/decline", response_model=MatchResponse)
def decline_match(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.recipient)),
):
    """Recipient releases a proposed match without accepting it, freeing the donation for the next matching round."""
    match = db.query(Match).filter(Match.id == match_id).with_for_update().first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your match")
    if match.status != MatchStatus.proposed:
        raise HTTPException(status_code=400, detail="Only a proposed match can be declined")

    match.status = MatchStatus.rejected
    match.outcome = MatchOutcome.declined
    match.resolved_at = datetime.now(UTC)

    donation = db.query(Donation).filter(Donation.id == match.donation_id).first()
    if donation and donation.status == DonationStatus.matched:
        donation.status = DonationStatus.active

    db.commit()
    db.refresh(match)
    return _respond(db, match, current_user)


@router.post("/{match_id}/confirm", response_model=MatchResponse)
def confirm_pickup(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.donor)),
):
    match = db.query(Match).filter(Match.id == match_id).with_for_update().first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    donation = db.query(Donation).filter(Donation.id == match.donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Associated donation not found")
    if donation.donor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    if match.status != MatchStatus.accepted:
        raise HTTPException(
            status_code=400, detail="Match must be accepted before it can be confirmed"
        )
    if donation.status != DonationStatus.matched:
        raise HTTPException(status_code=400, detail="Donation is not awaiting pickup confirmation")

    match.status = MatchStatus.fulfilled
    match.outcome = MatchOutcome.fulfilled
    match.resolved_at = datetime.now(UTC)
    donation.status = DonationStatus.fulfilled
    notify(db, match.recipient_id, "Your pickup has been confirmed. Thank you!")

    db.commit()
    db.refresh(match)
    return _respond(db, match, current_user)


@router.post("/{match_id}/reject", response_model=MatchResponse)
def reject_match(
    match_id: UUID,
    payload: MatchRejection,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.donor)),
):
    """
    Donor reports that an accepted match did not end in a completed pickup.

    `recipient_at_fault=true` records a no-show against the recipient's reliability;
    `false` closes the match without penalty (e.g. the donor's own plans changed).
    """
    match = db.query(Match).filter(Match.id == match_id).with_for_update().first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    donation = db.query(Donation).filter(Donation.id == match.donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Associated donation not found")
    if donation.donor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    if match.status != MatchStatus.accepted:
        raise HTTPException(status_code=400, detail="Only an accepted match can be rejected")

    match.status = MatchStatus.rejected
    match.outcome = MatchOutcome.no_show if payload.recipient_at_fault else MatchOutcome.withdrawn
    match.resolved_at = datetime.now(UTC)
    if donation.status == DonationStatus.matched:
        donation.status = DonationStatus.active

    db.commit()
    db.refresh(match)
    return _respond(db, match, current_user)


@router.get("/{match_id}", response_model=MatchResponse)
def get_match_detail(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    donation = db.query(Donation).filter(Donation.id == match.donation_id).first()
    is_recipient = match.recipient_id == current_user.id
    is_donor = donation is not None and donation.donor_id == current_user.id
    is_coordinator = current_user.role == UserRole.coordinator
    if not (is_recipient or is_donor or is_coordinator):
        raise HTTPException(status_code=403, detail="Not your match")

    return _respond(db, match, current_user)
