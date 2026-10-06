from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import get_db
from models.user import User, UserRole, VerificationStatus
from schemas.users import (
    ChangePassword,
    OrganizationVerificationDecision,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from utils.auth import create_access_token
from utils.dependencies import get_current_user, require_role
from utils.security import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(User)
        .filter((User.username == payload.username) | (User.email == payload.email))
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    verification_status = (
        VerificationStatus.pending if payload.is_organization else VerificationStatus.not_applicable
    )

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_organization=payload.is_organization,
        verification_status=verification_status,
        location_lat=payload.location_lat,
        location_lng=payload.location_lng,
        capacity=payload.capacity,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or email already registered") from e
    db.refresh(user)
    return user


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updates = payload.model_dump(exclude_unset=True)

    if "username" in updates or "email" in updates:
        conflict = (
            db.query(User)
            .filter(
                User.id != current_user.id,
                (User.username == updates.get("username", current_user.username))
                | (User.email == updates.get("email", current_user.email)),
            )
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="Username or email already in use")

    for field, value in updates.items():
        setattr(current_user, field, value)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or email already in use") from e
    db.refresh(current_user)
    return current_user


@router.get("/pending-verifications", response_model=list[UserResponse])
def list_pending_verifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.coordinator)),
):
    """FR21 — Coordinators view organizations awaiting verification."""
    return db.query(User).filter(User.verification_status == VerificationStatus.pending).all()


@router.post("/{user_id}/verify", response_model=UserResponse)
def verify_organization(
    user_id: UUID,
    payload: OrganizationVerificationDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.coordinator)),
):
    """FR21 — Coordinator verifies or rejects a pending organization registration."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_organization:
        raise HTTPException(status_code=400, detail="User is not an organization account")
    if user.verification_status != VerificationStatus.pending:
        raise HTTPException(status_code=400, detail="User is not pending verification")

    user.verification_status = (
        VerificationStatus.verified if payload.approve else VerificationStatus.rejected
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/change-password", response_model=UserResponse)
def change_password(
    payload: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user
