from uuid import UUID

from sqlalchemy.orm import Session

from models.notification import Notification

MAX_MESSAGE_LENGTH = 255


def notify(db: Session, user_id: UUID, message: str) -> None:
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[: MAX_MESSAGE_LENGTH - 1] + "…"
    db.add(Notification(user_id=user_id, message=message))
    db.flush()
