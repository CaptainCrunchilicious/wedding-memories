import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import PyMongoError
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.security import (
    JWTConfigurationError,
    create_access_token,
    get_current_admin,
    get_signing_key,
)
from app.database.connection import get_database
from app.schemas.admin import (
    AdministratorPublic,
    CurrentAdministratorResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)
from app.utils.passwords import verify_password

logger = logging.getLogger(__name__)
router = APIRouter()


def _database(request: Request) -> AsyncDatabase:
    try:
        return get_database(request.app.state.mongo_connection)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from None


def _public_admin(admin: dict[str, Any]) -> AdministratorPublic:
    return AdministratorPublic(email=admin["email"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    settings: Settings = request.app.state.settings
    try:
        get_signing_key(settings)
    except JWTConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from None

    database = _database(request)
    collection = database["administrators"]
    try:
        admin = await collection.find_one({"email": str(payload.email).lower()})
        password_matches = await verify_password(
            payload.password.get_secret_value(),
            admin.get("password_hash", "") if admin else None,
        )
        if admin is None or not password_matches or not admin.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token(admin, settings)
        now = datetime.now(UTC)
        await collection.update_one(
            {"_id": admin["_id"]},
            {"$set": {"last_login_at": now, "updated_at": now}},
        )
    except HTTPException:
        raise
    except PyMongoError as exc:
        logger.error("Administrator login database operation failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from None

    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        admin=_public_admin(admin),
    )


@router.get("/me", response_model=CurrentAdministratorResponse)
async def current_admin(
    admin: dict[str, Any] = Depends(get_current_admin),
) -> CurrentAdministratorResponse:
    return CurrentAdministratorResponse(admin=_public_admin(admin))


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> LogoutResponse:
    database = _database(request)
    try:
        result = await database["administrators"].update_one(
            {"_id": admin["_id"], "token_version": int(admin.get("token_version", 0))},
            {"$inc": {"token_version": 1}, "$set": {"updated_at": datetime.now(UTC)}},
        )
    except PyMongoError as exc:
        logger.error("Administrator logout database operation failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable",
        ) from None
    if result.modified_count != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return LogoutResponse()
