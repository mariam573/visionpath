"""OIDC access-token verification and identity-subject profile provisioning."""
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="OIDC access token")


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not settings.oidc_configured:
        raise RuntimeError("OIDC issuer, JWKS URL and audience are required")
    return PyJWKClient(
        settings.OIDC_JWKS_URL,
        cache_jwk_set=True,
        lifespan=300,
        timeout=5,
        cooldown_duration=0,
    )


def verify_access_token(token: str) -> dict[str, Any]:
    if not settings.oidc_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Managed identity is not configured",
        )
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.OIDC_AUDIENCE,
            issuer=settings.OIDC_ISSUER,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
            leeway=30,
        )
    except PyJWKClientConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Managed identity verification is temporarily unavailable",
        )
    except (PyJWKClientError, jwt.InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = claims.get("sub")
    issuer = claims.get("iss")
    if not isinstance(subject, str) or not subject or len(subject) > 255 or issuer != settings.OIDC_ISSUER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token identity is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    audience = claims.get("aud")
    if isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != settings.OIDC_AUDIENCE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token authorized party is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


def _identity_profile(claims: dict[str, Any]) -> tuple[str, str | None, bool]:
    raw_name = claims.get("name") or claims.get("preferred_username") or "VisionPath user"
    full_name = str(raw_name).strip()[:120] or "VisionPath user"
    raw_email = claims.get("email")
    verified = claims.get("email_verified") is True
    email = str(raw_email).strip().lower()[:254] if verified and raw_email else None
    return full_name, email, verified


def get_or_create_identity_user(db: Session, claims: dict[str, Any]) -> User:
    issuer = claims["iss"]
    subject = claims["sub"]
    full_name, email, verified = _identity_profile(claims)
    statement = (
        pg_insert(User)
        .values(
            identity_issuer=issuer,
            identity_subject=subject,
            full_name=full_name,
            email=email,
            email_verified=verified,
            role="blind_person",
            preferred_language="en",
            accessibility_preferences={},
        )
        .on_conflict_do_nothing(index_elements=["identity_issuer", "identity_subject"])
    )
    db.execute(statement)
    db.commit()
    user = db.scalar(
        select(User).where(User.identity_issuer == issuer, User.identity_subject == subject)
    )
    if user is None:
        raise HTTPException(status_code=503, detail="Profile could not be loaded")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This profile is disabled")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A managed identity access token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = verify_access_token(credentials.credentials)
    return get_or_create_identity_user(db, claims)
