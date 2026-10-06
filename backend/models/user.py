import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, String, func
from sqlalchemy.dialects.postgresql import UUID

from db.database import Base


class UserRole(enum.StrEnum):
    donor = "donor"
    recipient = "recipient"
    coordinator = "coordinator"


class VerificationStatus(enum.StrEnum):
    not_applicable = "not_applicable"
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)

    role = Column(Enum(UserRole), nullable=False)

    is_organization = Column(Boolean, nullable=False, default=False)
    verification_status = Column(
        Enum(VerificationStatus), nullable=False, default=VerificationStatus.not_applicable
    )

    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)

    capacity = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
