from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from models.user import User, UserRole
from services.matching_engine import run_matching_round
from utils.dependencies import require_role

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/run")
def trigger_matching_round(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.coordinator)),
):
    matches = run_matching_round(db)
    return {"matches_created": len(matches)}
