"""VisionPath backend application; PostgreSQL schema is managed by Alembic."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import check_database_readiness
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # A configured database must already be at the migration head before the
    # application starts serving. No tables are created at runtime.
    if settings.DATABASE_URL is not None:
        ready, reason = check_database_readiness()
        if not ready:
            raise RuntimeError(f"Database is not ready: {reason}. Apply Alembic migrations first.")
    else:
        logger.warning("PostgreSQL is not configured; protected API endpoints will fail closed")
    if not settings.oidc_configured:
        logger.warning("OIDC is not configured; protected API endpoints will fail closed")
    yield


app = FastAPI(
    title="VisionPath API",
    description="Managed-identity profile and consent foundation; optional cloud/data APIs are not implemented",
    version="0.2.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "visionpath-backend", "version": "0.2.0"}


@app.get("/ready")
async def readiness_check():
    database_ready, _ = check_database_readiness()
    if (
        not database_ready
        or not settings.oidc_configured
        or not settings.CONSENT_POLICY_VERSION
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend identity, PostgreSQL migrations, or consent policy are not ready",
        )
    return {"status": "ready", "service": "visionpath-backend"}


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting VisionPath API on {settings.HOST}:{settings.PORT}")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
