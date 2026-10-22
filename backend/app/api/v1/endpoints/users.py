"""User profile registration endpoint."""
import sqlite3
import hmac
from typing import Any, Dict, Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.database import create_user, get_user
from app.core.config import settings

router = APIRouter()


class UserRegistrationRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=3, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    preferred_language: str = Field(default="en", min_length=2, max_length=16)
    accessibility_preferences: Dict[str, Any] = Field(default_factory=dict)
    role: Literal["blind_person", "supervisor", "admin"] = "blind_person"

    @field_validator("full_name", "email", "preferred_language")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return value.lower()


class UserProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str | None
    role: str
    preferred_language: str
    accessibility_preferences: Dict[str, Any]
    created_at: str


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    request: UserRegistrationRequest,
    provisioning_key: str | None = Header(default=None, alias="X-Provisioning-Key"),
):
    """Create a profile; supervisor/admin roles require the provisioning key."""
    if request.role != "blind_person":
        if not settings.USER_PROVISIONING_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Privileged role provisioning is not configured",
            )
        if not hmac.compare_digest(
            provisioning_key or "", settings.USER_PROVISIONING_KEY
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A valid provisioning key is required for this role",
            )
    try:
        user_id = create_user(
            full_name=request.full_name,
            email=request.email,
            role=request.role,
            phone=request.phone,
            preferred_language=request.preferred_language,
            accessibility_preferences=request.accessibility_preferences,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=500, detail="Could not load the new profile")
    return user
