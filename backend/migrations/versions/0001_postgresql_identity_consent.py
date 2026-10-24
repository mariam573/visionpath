"""PostgreSQL identity-bound profiles and consent audit events.

Revision ID: 0001_postgresql_identity_consent
Revises:
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_postgresql_identity_consent"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("identity_issuer", sa.Text(), nullable=False),
        sa.Column("identity_subject", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False, server_default="VisionPath user"),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="blind_person"),
        sa.Column("preferred_language", sa.String(length=8), nullable=False, server_default="en"),
        sa.Column("accessibility_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("identity_issuer", "identity_subject", name="uq_users_identity"),
        sa.CheckConstraint("role IN ('blind_person', 'supervisor', 'admin')", name="ck_users_role"),
        sa.CheckConstraint("preferred_language IN ('en', 'ar')", name="ck_users_language"),
    )
    op.create_table(
        "consent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_sequence", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_consent_events_user_id_users"),
        sa.CheckConstraint("purpose IN ('cloud_questions', 'synchronization', 'sharing')", name="ck_consent_events_purpose"),
    )
    op.create_index("ix_consent_events_user_purpose_sequence", "consent_events", ["user_id", "purpose", "event_sequence"])
    op.execute("""
        CREATE FUNCTION prevent_consent_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'consent events are append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_consent_events_append_only
        BEFORE UPDATE OR DELETE ON consent_events
        FOR EACH ROW EXECUTE FUNCTION prevent_consent_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_consent_events_append_only ON consent_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_consent_event_mutation()")
    op.drop_index("ix_consent_events_user_purpose_sequence", table_name="consent_events")
    op.drop_table("consent_events")
    op.drop_table("users")
