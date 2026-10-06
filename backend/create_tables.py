from db.database import Base, engine
from models.dispute import Dispute  # noqa: F401
from models.donation import Donation  # noqa: F401
from models.match import Match  # noqa: F401
from models.notification import Notification  # noqa: F401
from models.user import User  # noqa: F401

Base.metadata.create_all(bind=engine)

print("Tables created.")
