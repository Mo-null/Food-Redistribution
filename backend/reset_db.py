from sqlalchemy import text

from db.database import Base, engine
from models.dispute import Dispute  # noqa: F401
from models.donation import Donation  # noqa: F401
from models.match import Match  # noqa: F401
from models.notification import Notification  # noqa: F401
from models.user import User  # noqa: F401

if (
    input("This DELETES ALL DATA in the database. Type 'yes' to continue: ").strip().lower()
    != "yes"
):
    raise SystemExit("Cancelled.")

# Dev databases created before the reliability merge still have this table, and its
# foreign key to users would block drop_all. Safe to delete this line once every dev DB has been reset.
with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS reliability_records"))

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Database reset. Now run: python create_coordinator.py")
