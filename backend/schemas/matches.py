from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.donation import DonationCategory
from models.match import MatchOutcome, MatchStatus
from models.user import VerificationStatus


class MatchRejection(BaseModel):
    recipient_at_fault: bool


class DonationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donor_id: UUID
    category: DonationCategory
    description: str | None = None
    quantity: float
    location_lat: float
    location_lng: float
    location_is_approximate: bool = False
    expiry_time: datetime


class CounterpartSummary(BaseModel):
    username: str
    is_organization: bool
    verification_status: VerificationStatus
    reliability_score: float | None = None
    reliability_sample_size: int | None = None


class MatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    donation_id: UUID
    recipient_id: UUID
    score: float
    status: MatchStatus
    outcome: MatchOutcome | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    proposal_expires_at: datetime | None = None
    distance_km: float | None = None
    donation: DonationSummary | None = None
    counterpart: CounterpartSummary | None = None
