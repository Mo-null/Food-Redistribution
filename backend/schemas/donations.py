from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.donation import DonationCategory, DonationStatus
from schemas.common import Amount, Latitude, Longitude

MAX_EXPIRY_HOURS = 48 * 7


def _validate_future_aware_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return value
    if value.tzinfo is None:
        raise ValueError("expiry_time must include a timezone")
    now = datetime.now(UTC)
    if value <= now:
        raise ValueError("expiry_time must be in the future")
    if value > now + timedelta(hours=MAX_EXPIRY_HOURS):
        raise ValueError(f"expiry_time cannot be more than {MAX_EXPIRY_HOURS} hours from now")
    return value


class DonationCreate(BaseModel):
    category: DonationCategory
    description: str | None = Field(default=None, max_length=255)
    quantity: Amount
    location_lat: Latitude
    location_lng: Longitude
    expiry_time: datetime

    @field_validator("expiry_time")
    @classmethod
    def check_expiry(cls, v):
        return _validate_future_aware_expiry(v)


class DonationUpdate(BaseModel):
    category: DonationCategory | None = None
    description: str | None = Field(default=None, max_length=255)
    quantity: Amount | None = None
    expiry_time: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, data):
        if isinstance(data, dict):
            for field in ("category", "quantity", "expiry_time"):
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be explicitly set to null")
        return data

    @field_validator("expiry_time")
    @classmethod
    def check_expiry(cls, v):
        return _validate_future_aware_expiry(v)


class DonationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    donor_id: UUID
    category: DonationCategory
    description: str | None
    quantity: float
    location_lat: float
    location_lng: float
    posted_at: datetime
    expiry_time: datetime
    status: DonationStatus
