"""Per-user consent history with explicit revocation and policy versioning."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.identity import get_current_user
from app.models import ConsentEvent, User

router = APIRouter(prefix="/me/consents", tags=["consent"])
ConsentPurpose = Literal["cloud_questions", "synchronization", "sharing"]


class ConsentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    granted: bool
    policy_version: str | None = Field(default=None, min_length=1, max_length=80)


class ConsentResponse(BaseModel):
    id: UUID
    purpose: str
    granted: bool
    active: bool
    policy_version: str | None
    recorded_at: datetime


def latest_consent(db: Session, user_id: UUID, purpose: str) -> ConsentEvent | None:
    return db.scalar(
        select(ConsentEvent)
        .where(ConsentEvent.user_id == user_id, ConsentEvent.purpose == purpose)
        .order_by(ConsentEvent.event_sequence.desc())
        .limit(1)
    )


def is_consent_active(db: Session, user_id: UUID, purpose: ConsentPurpose) -> bool:
    """A grant is active only until a later revocation or policy-version change."""
    if not settings.CONSENT_POLICY_VERSION:
        return False
    event = latest_consent(db, user_id, purpose)
    return bool(
        event
        and event.granted
        and event.policy_version == settings.CONSENT_POLICY_VERSION
    )


@router.get("", response_model=list[ConsentResponse])
def list_my_consents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConsentResponse]:
    rows = db.scalars(
        select(ConsentEvent)
        .where(ConsentEvent.user_id == user.id)
        .order_by(ConsentEvent.event_sequence.desc())
    ).all()
    latest_by_purpose: dict[str, ConsentEvent] = {}
    for row in rows:
        latest_by_purpose.setdefault(row.purpose, row)
    return [
        ConsentResponse(
            id=event.id,
            purpose=event.purpose,
            granted=event.granted,
            active=is_consent_active(db, user.id, event.purpose),
            policy_version=event.policy_version,
            recorded_at=event.recorded_at,
        )
        for event in latest_by_purpose.values()
    ]


@router.put("/{purpose}", response_model=ConsentResponse)
def set_my_consent(
    purpose: ConsentPurpose,
    change: ConsentChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentResponse:
    # Serialize grant/revoke events for this account. Sequence order then
    # reflects the order in which requests acquired the account lock.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    if change.granted:
        current_version = settings.CONSENT_POLICY_VERSION
        if current_version is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The reviewed consent policy version is not configured",
            )
        if change.policy_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Consent policy version is out of date; reload the current policy before granting",
            )
        recorded_version = current_version
    else:
        # Revocation is always available and is recorded against the most recent
        # grant's version when one exists, even if the active policy changed.
        previous = latest_consent(db, user.id, purpose)
        recorded_version = previous.policy_version if previous else None

    event = ConsentEvent(
        user_id=user.id,
        purpose=purpose,
        granted=change.granted,
        policy_version=recorded_version,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return ConsentResponse(
        id=event.id,
        purpose=event.purpose,
        granted=event.granted,
        active=is_consent_active(db, user.id, purpose),
        policy_version=event.policy_version,
        recorded_at=event.recorded_at,
    )
