from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.dispute import Dispute, DisputeStatus
from models.donation import Donation
from models.match import Match, MatchStatus
from models.user import User, UserRole
from schemas.disputes import DisputeCreate, DisputeResponse
from utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/disputes", tags=["disputes"])


@router.post("", response_model=DisputeResponse)
def flag_dispute(
    payload: DisputeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    match = db.query(Match).filter(Match.id == payload.match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    donation = db.query(Donation).filter(Donation.id == match.donation_id).first()
    is_recipient = match.recipient_id == current_user.id
    is_donor = donation is not None and donation.donor_id == current_user.id
    if not (is_recipient or is_donor):
        raise HTTPException(status_code=403, detail="You are not party to this match")

    if match.status == MatchStatus.proposed:
        raise HTTPException(
            status_code=400,
            detail="This match hasn't been acted on yet — nothing to dispute",
        )

    existing_open = (
        db.query(Dispute)
        .filter(Dispute.match_id == payload.match_id, Dispute.status == DisputeStatus.open)
        .first()
    )
    if existing_open:
        raise HTTPException(status_code=400, detail="An open dispute already exists for this match")

    dispute = Dispute(
        match_id=payload.match_id,
        reported_by=current_user.id,
        reason=payload.reason,
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


@router.get("", response_model=list[DisputeResponse])
def list_disputes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.coordinator)),
):
    return db.query(Dispute).filter(Dispute.status == DisputeStatus.open).all()


@router.post("/{dispute_id}/resolve", response_model=DisputeResponse)
def resolve_dispute(
    dispute_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.coordinator)),
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if dispute.status != DisputeStatus.open:
        raise HTTPException(status_code=400, detail="Dispute has already been resolved")

    dispute.status = DisputeStatus.resolved
    dispute.resolved_at = datetime.now(UTC)
    db.commit()
    db.refresh(dispute)
    return dispute
