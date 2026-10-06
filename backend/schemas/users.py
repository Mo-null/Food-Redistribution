from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from models.user import UserRole, VerificationStatus
from schemas.common import Amount, Latitude, Longitude

MAX_PASSWORD_BYTES = 72


def _check_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes "
            "(non-ASCII characters take more than one byte)"
        )
    return value


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: Annotated[EmailStr, Field(max_length=100)]
    password: str = Field(min_length=6)
    role: Literal[UserRole.donor, UserRole.recipient]
    is_organization: bool = False
    location_lat: Latitude | None = None
    location_lng: Longitude | None = None
    capacity: Amount | None = Field(
        default=None,
        description="Recipients only: roughly how much surplus you can realistically take",
    )

    @field_validator("username", "email")
    @classmethod
    def lowercase_identity(cls, v):
        return v.lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, v):
        return _check_password_bytes(v)

    @model_validator(mode="after")
    def require_location_and_capacity_for_recipients(self):
        if self.role == UserRole.recipient:
            if self.location_lat is None or self.location_lng is None:
                raise ValueError(
                    "Recipients must provide location_lat and location_lng to be matchable"
                )
            if self.capacity is None:
                raise ValueError("Recipients must provide capacity to be matchable")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: EmailStr
    role: UserRole
    is_organization: bool
    verification_status: VerificationStatus
    location_lat: float | None = None
    location_lng: float | None = None
    capacity: float | None = None


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: Annotated[EmailStr, Field(max_length=100)] | None = None
    location_lat: Latitude | None = None
    location_lng: Longitude | None = None
    capacity: Amount | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, data):
        if isinstance(data, dict):
            for field in ("username", "email", "location_lat", "location_lng", "capacity"):
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be explicitly set to null")
        return data

    @field_validator("username", "email")
    @classmethod
    def lowercase_identity(cls, v):
        return v.lower() if v is not None else v


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v):
        return _check_password_bytes(v)


class OrganizationVerificationDecision(BaseModel):
    approve: bool
