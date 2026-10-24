"""PostgreSQL session lifecycle. Schema changes are applied only via Alembic."""
from functools import lru_cache
from typing import Generator

from fastapi import HTTPException, status
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import BASE_DIR, settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    if settings.DATABASE_URL is None:
        raise RuntimeError("PostgreSQL DATABASE_URL is not configured")
    return create_engine(
        settings.DATABASE_URL.get_secret_value(),
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,
    )


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    if settings.DATABASE_URL is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL is not configured",
        )
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_readiness() -> tuple[bool, str]:
    """Confirm PostgreSQL is reachable and the database is at the migration head."""
    if settings.DATABASE_URL is None:
        return False, "database_not_configured"
    try:
        from alembic.config import Config
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory

        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            migration_context = MigrationContext.configure(connection)
            applied = set(migration_context.get_current_heads())
        alembic_config = Config(str(BASE_DIR / "alembic.ini"))
        expected = set(ScriptDirectory.from_config(alembic_config).get_heads())
        if not applied or applied != expected:
            return False, "database_migrations_not_current"
        return True, "ready"
    except Exception:
        return False, "database_unavailable_or_migration_error"
