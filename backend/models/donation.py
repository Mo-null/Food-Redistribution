import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db.database import Base


class DonationStatus(enum.StrEnum):
    active = "active"
    matched = "matched"
    fulfilled = "fulfilled"
    expired = "expired"
    cancelled = "cancelled"


class DonationCategory(enum.StrEnum):
    cooked_meals = "cooked_meals"
    raw_produce = "raw_produce"
    bakery = "bakery"
    packaged = "packaged"
    dairy_eggs = "dairy_eggs"
    meat_fish = "meat_fish"
    beverages = "beverages"
    other = "other"


class Donation(Base):
    __tablename__ = "donations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    donor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    category = Column(Enum(DonationCategory), nullable=False)
    description = Column(String(255), nullable=True)
    quantity = Column(Float, nullable=False)

    location_lat = Column(Float, nullable=False)
    location_lng = Column(Float, nullable=False)

    posted_at = Column(DateTime(timezone=True), server_default=func.now())
    expiry_time = Column(DateTime(timezone=True), nullable=False)

    status = Column(Enum(DonationStatus), default=DonationStatus.active, nullable=False)

    donor = relationship("User")
