import enum
import uuid
from datetime import timedelta

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from db.database import Base


class MatchStatus(enum.StrEnum):
    proposed = "proposed"
    accepted = "accepted"
    fulfilled = "fulfilled"
    rejected = "rejected"


class MatchOutcome(enum.StrEnum):
    fulfilled = "fulfilled"
    declined = "declined"
    ignored = "ignored"
    no_show = "no_show"
    withdrawn = "withdrawn"

    @classmethod
    def no_reoffer(cls):
        return (cls.declined, cls.ignored, cls.no_show, cls.withdrawn)


PROPOSAL_TIMEOUT_MINUTES = 30


class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    donation_id = Column(UUID(as_uuid=True), ForeignKey("donations.id"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    score = Column(Float, nullable=False)
    status = Column(Enum(MatchStatus), default=MatchStatus.proposed, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    features = Column(JSONB, nullable=True)
    outcome = Column(Enum(MatchOutcome), nullable=True)

    donation = relationship("Donation")
    recipient = relationship("User")

    @property
    def proposal_expires_at(self):
        if self.status != MatchStatus.proposed or self.created_at is None:
            return None
        return self.created_at + timedelta(minutes=PROPOSAL_TIMEOUT_MINUTES)
