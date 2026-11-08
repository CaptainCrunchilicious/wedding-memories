import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.database.connection import get_database

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


class JWTConfigurationError(RuntimeError):
    """Raised when a safe JWT signing key is not configured."""


def get_signing_key(settings: Settings) -> str:
    key = settings.jwt_secret.get_secret_value()
    minimum_bytes = {"HS256": 32, "HS384": 48, "HS512": 64}[settings.jwt_algorithm]
    if (
        len(key.encode("utf-8")) < minimum_bytes
        or len(set(key)) < 16
        or key != key.strip()
    ):
        raise JWTConfigurationError(
            f"JWT_SECRET must be a varied secret of at least {minimum_bytes} bytes"
        )
    return key


def create_access_token(admin: dict[str, Any], settings: Settings) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return jwt.encode(
        {
            "sub": str(admin["_id"]),
            "exp": expires_at,
            "iat": now,
            "jti": secrets.token_urlsafe(24),
            "token_version": int(admin.get("token_version", 0)),
        },
        get_signing_key(settings),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(
        token,
        get_signing_key(settings),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "iat", "jti", "token_version"]},
    )


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    settings: Settings = request.app.state.settings
    try:
        get_signing_key(settings)
    except JWTConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from None
    try:
        claims = decode_access_token(credentials.credentials, settings)
        subject = claims.get("sub")
        token_version = claims.get("token_version")
        if (
            not isinstance(subject, str)
            or not ObjectId.is_valid(subject)
            or not isinstance(token_version, int)
            or isinstance(token_version, bool)
        ):
            raise unauthorized
        admin_id = ObjectId(subject)
    except (InvalidTokenError, TypeError, ValueError):
        raise unauthorized from None

    try:
        database = get_database(request.app.state.mongo_connection)
        admin = await database["administrators"].find_one({"_id": admin_id})
    except (PyMongoError, RuntimeError) as exc:
        logger.error("Administrator lookup failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from None

    if admin is None:
        raise unauthorized
    if not admin.get("is_active", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator is inactive")
    if int(admin.get("token_version", 0)) != int(claims["token_version"]):
        raise unauthorized
    return admin
