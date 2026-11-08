import hashlib
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.core.security import get_current_admin
from app.database.connection import get_database
from app.services.token_encryption import TokenEncryptionError, validate_encryption_key
from app.storage.google_drive import DriveConfigurationError, DriveProviderError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations/google-drive", tags=["Google Drive integration"])
OAUTH_SCOPE = "https://www.googleapis.com/auth/drive.file"
STATE_TTL = timedelta(minutes=10)
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def _database(request: Request):
    try:
        return get_database(request.app.state.mongo_connection)
    except RuntimeError:
        raise HTTPException(503, "Database service is unavailable") from None


def _client_configured(request: Request) -> None:
    settings = request.app.state.settings
    if not (settings.google_drive_client_id.strip()
            and settings.google_drive_client_secret.get_secret_value().strip()
            and settings.google_drive_redirect_uri.strip()):
        raise HTTPException(503, "Google Drive OAuth is not configured on the backend")
    try:
        validate_encryption_key(settings)
    except TokenEncryptionError:
        raise HTTPException(503, "Google Drive token encryption is not configured correctly") from None


def _state_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _frontend_callback(request: Request, result: str) -> RedirectResponse:
    origin = request.app.state.settings.frontend_origins.split(",")[0].strip().rstrip("/")
    return RedirectResponse(f"{origin}/admin/settings?drive={result}", status_code=303)


@router.get("/status")
async def google_drive_status(request: Request, _admin=Depends(get_current_admin)):
    try:
        return await request.app.state.google_drive_storage.connection_status()
    except Exception as exc:
        logger.warning("Google Drive status check failed (%s).", type(exc).__name__)
        return {"configured": False, "connected": False, "operational": False,
                "connected_email": None, "folder_status": "unavailable", "last_successful_check": None}


@router.post("/connect")
async def begin_google_drive_connection(request: Request, admin=Depends(get_current_admin)):
    _client_configured(request)
    state = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    database = _database(request)
    await database["photo_settings"].delete_many({
        "purpose": "google_drive_oauth_state", "expires_at": {"$lte": now},
    })
    await database["photo_settings"].insert_one({
        "key": f"google_drive_oauth_state:{_state_hash(state)}",
        "purpose": "google_drive_oauth_state",
        "administrator_id": admin["_id"],
        "token_version": int(admin.get("token_version", 0)),
        "expires_at": now + STATE_TTL,
    })
    settings = request.app.state.settings
    params = {
        "client_id": settings.google_drive_client_id,
        "redirect_uri": settings.google_drive_redirect_uri,
        "response_type": "code",
        "scope": OAUTH_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return {"authorization_url": f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"}


@router.get("/callback")
async def google_drive_callback(
    request: Request,
    state: str = Query(min_length=32, max_length=256),
    code: str | None = Query(default=None, max_length=4096),
    error: str | None = Query(default=None, max_length=128),
):
    _client_configured(request)
    database = _database(request)
    key = f"google_drive_oauth_state:{_state_hash(state)}"
    transaction = await database["photo_settings"].find_one_and_delete({"key": key})
    now = datetime.now(UTC)
    if (transaction is None or transaction.get("purpose") != "google_drive_oauth_state"
            or transaction.get("expires_at") is None or _as_utc(transaction["expires_at"]) <= now):
        return _frontend_callback(request, "invalid_state")
    administrator = await database["administrators"].find_one({"_id": transaction.get("administrator_id")})
    if (administrator is None or not administrator.get("is_active")
            or int(administrator.get("token_version", 0)) != int(transaction.get("token_version", -1))):
        return _frontend_callback(request, "admin_changed")
    if error or not code:
        return _frontend_callback(request, "cancelled")

    settings = request.app.state.settings
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(GOOGLE_TOKEN_ENDPOINT, data={
                "code": code,
                "client_id": settings.google_drive_client_id,
                "client_secret": settings.google_drive_client_secret.get_secret_value(),
                "redirect_uri": settings.google_drive_redirect_uri,
                "grant_type": "authorization_code",
            })
        if response.status_code != 200:
            logger.warning("Google OAuth token exchange returned HTTP %s.", response.status_code)
            return _frontend_callback(request, "exchange_failed")
        payload = response.json()
        if not payload.get("access_token"):
            return _frontend_callback(request, "exchange_failed")
        tokens = {
            "access_token": payload["access_token"],
            "refresh_token": payload.get("refresh_token"),
            "expires_at": int(time.time()) + int(payload.get("expires_in", 3600)),
            "token_type": payload.get("token_type", "Bearer"),
            "scope": payload.get("scope", OAUTH_SCOPE),
        }
        storage = request.app.state.google_drive_storage
        await storage.save_tokens(tokens)
        await storage.verify_connection()
    except httpx.HTTPError as exc:
        logger.warning("Google OAuth callback failed (%s).", type(exc).__name__)
        return _frontend_callback(request, "exchange_failed")
    except DriveConfigurationError:
        logger.warning("Google Drive credentials could not be stored or validated.")
        return _frontend_callback(request, "credential_error")
    except DriveProviderError as exc:
        logger.warning("Google Drive connection validation failed (%s).", type(exc).__name__)
        return _frontend_callback(request, "connected_check_failed")
    except Exception as exc:
        logger.error("Google Drive OAuth callback failed (%s).", type(exc).__name__)
        return _frontend_callback(request, "connection_failed")
    return _frontend_callback(request, "connected")


@router.post("/disconnect")
async def disconnect_google_drive(request: Request, _admin=Depends(get_current_admin)):
    database = _database(request)
    await database["photo_settings"].delete_one({"key": "google_drive_credentials"})
    await database["photo_settings"].delete_many({"purpose": "google_drive_oauth_state"})
    await database["photo_settings"].update_one(
        {"key": "storage_provider"},
        {"$set": {"value": "local"}},
        upsert=True,
    )
    request.app.state.photo_storage_provider = "local"
    return {"disconnected": True, "provider": "local"}
