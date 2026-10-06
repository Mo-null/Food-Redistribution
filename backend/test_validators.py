from pydantic import ValidationError

from schemas.donations import DonationUpdate
from schemas.users import UserUpdate

CASES = [
    ("quantity=None", lambda: DonationUpdate(quantity=None)),
    ("expiry_time=None", lambda: DonationUpdate(expiry_time=None)),
    ("email=None", lambda: UserUpdate(email=None)),
    ("username=None", lambda: UserUpdate(username=None)),
    ("DonationUpdate() omitted", lambda: DonationUpdate()),
]


def main():
    for name, fn in CASES:
        try:
            fn()
            print(f"{name}: ACCEPTED")
        except ValidationError:
            print(f"{name}: REJECTED")


if __name__ == "__main__":
    main()
