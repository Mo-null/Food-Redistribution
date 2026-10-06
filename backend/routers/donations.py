import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.donation import Donation, DonationStatus
from models.user import User, UserRole, VerificationStatus
from schemas.donations import DonationCreate, DonationResponse, DonationUpdate
from schemas.parse import ParseRequest, ParseResult
from services.llm_parse import NotFoodDescription, parse_donation_text
from services.matching_engine import run_matching_round_in_new_session
from utils.dependencies import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/donations", tags=["donations"])


def _require_verified_if_organization(user: User) -> None:
    if user.is_organization and user.verification_status != VerificationStatus.verified:
        raise HTTPException(
            status_code=403,
            detail="Your organization must be verified before posting donations",
        )


@router.post("/parse", response_model=ParseResult)
def parse_donation(
    payload: ParseRequest,
    current_user: User = Depends(require_role(UserRole.donor)),
):
    _require_verified_if_organization(current_user)
    try:
        return parse_donation_text(payload.text)
    except NotFoodDescription as e:
        raise HTTPException(status_code=422, detail=e.reason) from e
    except RuntimeError as e:
        logger.exception("Donation text parsing is unavailable")
        raise HTTPException(
            status_code=503,
            detail="Automatic parsing is temporarily unavailable. Please fill the form manually.",
        ) from e
    except Exception as e:
        logger.exception("Donation text parsing failed")
        raise HTTPException(
            status_code=502,
            detail="Could not parse donation text right now. Please fill the form manually.",
        ) from e


@router.get("/mine", response_model=list[DonationResponse])
def get_my_donations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.donor)),
):
    return db.query(Donation).filter(Donation.donor_id == current_user.id).all()


@router.get("/{donation_id}", response_model=DonationResponse)
def get_donation(
    donation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.donor)),
):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")
    if donation.donor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    return donation


@router.post("", response_model=DonationResponse)
def create_donation(
    payload: DonationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.donor)),
):
    _require_verified_if_organization(current_user)
    donation = Donation(donor_id=current_user.id, **payload.model_dump())
    db.add(donation)
    db.commit()
    db.refresh(donation)
    background_tasks.add_task(run_matching_round_in_new_session)
    return donation


@router.patch("/{donation_id}", response_model=DonationResponse)
def update_donation(
    donation_id: UUID,
    payload: DonationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.donor)),
):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")
    if donation.donor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    if donation.status != DonationStatus.active:
        raise HTTPException(
            status_code=400, detail="Only active (unmatched) donations can be edited"
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(donation, field, value)
    db.commit()
    db.refresh(donation)
    return donation


@router.delete("/{donation_id}")
def cancel_donation(
    donation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.donor)),
):
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")
    if donation.donor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your donation")
    if donation.status != DonationStatus.active:
        raise HTTPException(
            status_code=400, detail="Only active (unmatched) donations can be cancelled"
        )

    donation.status = DonationStatus.cancelled
    db.commit()
    return {"detail": "Donation cancelled"}
