from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from models.dispute import DisputeStatus


class DisputeCreate(BaseModel):
    match_id: UUID
    reason: str = Field(min_length=5, max_length=500)


class DisputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_id: UUID
    reported_by: UUID
    reason: str
    status: DisputeStatus
    created_at: datetime
    resolved_at: datetime | None = None
