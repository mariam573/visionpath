"""Self-service profile endpoints bound to the verified OIDC subject."""
import json
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.identity import get_current_user
from app.models import User

router = APIRouter(prefix="/users", tags=["profiles"])


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    preferred_language: Literal["en", "ar"] | None = None
    accessibility_preferences: dict[str, Any] | None = None

    @field_validator("full_name")
    @classmethod
    def nonblank_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("full_name cannot be blank")
        return value.strip() if value is not None else None

    @field_validator("accessibility_preferences")
    @classmethod
    def bound_preferences(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None and len(json.dumps(value, ensure_ascii=False)) > 4096:
            raise ValueError("Accessibility preferences must be 4 KB or smaller")
        return value

    @model_validator(mode="after")
    def reject_null_for_required_profile_fields(self):
        for field in ("full_name", "preferred_language", "accessibility_preferences"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str | None
    email_verified: bool
    phone: str | None
    role: str
    preferred_language: str
    accessibility_preferences: dict[str, Any]
    created_at: datetime
    updated_at: datetime


def serialize_profile(user: User) -> ProfileResponse:
    return ProfileResponse(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        email_verified=user.email_verified,
        phone=user.phone,
        role=user.role,
        preferred_language=user.preferred_language,
        accessibility_preferences=user.accessibility_preferences,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/me", response_model=ProfileResponse)
def read_my_profile(user: User = Depends(get_current_user)) -> ProfileResponse:
    """Create or return only the profile belonging to the verified token subject."""
    return serialize_profile(user)


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(
    patch: ProfilePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No profile changes supplied")
    for field, value in updates.items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_profile(user)
