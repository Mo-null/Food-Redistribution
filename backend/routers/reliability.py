from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.user import User, UserRole
from schemas.reliability import ReliabilityResponse
from services.reliability import get_outcome_counts, reliability_score
from utils.dependencies import get_current_user

router = APIRouter(prefix="/reliability", tags=["reliability"])


@router.get("/{user_id}", response_model=ReliabilityResponse)
def get_user_reliability(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.role != UserRole.coordinator:
        raise HTTPException(status_code=403, detail="You can only view your own reliability")

    if db.query(User.id).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")

    counts = get_outcome_counts(db, [user_id]).get(user_id, {})
    return ReliabilityResponse(
        user_id=user_id,
        fulfilled_count=counts.get("fulfilled", 0),
        no_show_count=counts.get("no_show", 0),
        score=round(reliability_score(counts), 3),
    )
