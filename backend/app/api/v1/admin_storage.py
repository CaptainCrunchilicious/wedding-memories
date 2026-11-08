import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.security import get_current_admin
from app.database.connection import get_database
from app.storage.google_drive import DriveConfigurationError, DriveNotConnected, DriveProviderError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/storage", tags=["admin storage"])


class StorageProviderUpdate(BaseModel):
    provider: Literal["local", "google_drive"]


def _database(request: Request):
    try:
        return get_database(request.app.state.mongo_connection)
    except RuntimeError:
        raise HTTPException(503, "Database service is unavailable") from None


async def _current_provider(request: Request, database) -> str:
    saved = await database["photo_settings"].find_one({"key": "storage_provider"})
    provider = saved.get("value") if saved else request.app.state.settings.photo_storage_provider
    if provider not in {"local", "google_drive"}:
        provider = "local"
    request.app.state.photo_storage_provider = provider
    return provider


async def _drive_status(request: Request) -> dict:
    try:
        return await request.app.state.google_drive_storage.connection_status()
    except Exception as exc:
        logger.warning("Google Drive health check failed (%s).", type(exc).__name__)
        return {"configured": False, "connected": False, "operational": False,
                "connected_email": None, "folder_status": "unavailable", "last_successful_check": None}


@router.get("/status")
async def storage_status(request: Request, _admin=Depends(get_current_admin)):
    database = _database(request)
    return {"provider": await _current_provider(request, database), "google_drive": await _drive_status(request)}


@router.patch("/provider")
async def set_storage_provider(payload: StorageProviderUpdate, request: Request, _admin=Depends(get_current_admin)):
    database = _database(request)
    if payload.provider == "google_drive":
        try:
            await request.app.state.google_drive_storage.verify_connection()
        except DriveConfigurationError:
            raise HTTPException(409, "Google Drive configuration or folder access is invalid") from None
        except DriveNotConnected:
            raise HTTPException(409, "Connect a Google account before selecting Google Drive") from None
        except DriveProviderError:
            raise HTTPException(503, "Google Drive is temporarily unavailable") from None
    await database["photo_settings"].update_one(
        {"key": "storage_provider"},
        {"$set": {"value": payload.provider}},
        upsert=True,
    )
    request.app.state.photo_storage_provider = payload.provider
    return {"provider": payload.provider}
