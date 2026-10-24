"""PostgreSQL ORM records for identity-bound profiles and consent audit events."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Identity, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("identity_issuer", "identity_subject", name="uq_users_identity"),
        CheckConstraint("role IN ('blind_person', 'supervisor', 'admin')", name="ck_users_role"),
        CheckConstraint("preferred_language IN ('en', 'ar')", name="ck_users_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_issuer: Mapped[str] = mapped_column(Text, nullable=False)
    identity_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="VisionPath user")
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="blind_person", server_default="blind_person")
    preferred_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en", server_default="en")
    accessibility_preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ConsentEvent(Base):
    __tablename__ = "consent_events"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('cloud_questions', 'synchronization', 'sharing')",
            name="ck_consent_events_purpose",
        ),
        Index("ix_consent_events_user_purpose_sequence", "user_id", "purpose", "event_sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
