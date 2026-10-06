import getpass

from db.database import SessionLocal
from models.user import User, UserRole, VerificationStatus
from utils.security import hash_password


def main():
    username = input("Coordinator username: ").strip().lower()
    email = input("Coordinator email: ").strip().lower()
    password = getpass.getpass("Coordinator password: ")

    db = SessionLocal()
    try:
        existing = (
            db.query(User).filter((User.username == username) | (User.email == email)).first()
        )
        if existing:
            print("A user with that username or email already exists.")
            return

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.coordinator,
            is_organization=False,
            verification_status=VerificationStatus.not_applicable,
        )
        db.add(user)
        db.commit()
        print(f"Coordinator account '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
