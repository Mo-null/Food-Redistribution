from uuid import UUID

from pydantic import BaseModel


class ReliabilityResponse(BaseModel):
    user_id: UUID
    fulfilled_count: int
    no_show_count: int
    score: float
