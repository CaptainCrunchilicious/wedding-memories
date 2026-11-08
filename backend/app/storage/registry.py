import logging

from fastapi import HTTPException, Request

from app.database.connection import get_database
from app.storage.base import PhotoStorage
from app.storage.google_drive import DriveConfigurationError

logger = logging.getLogger(__name__)


def storage_for(request: Request, provider: str) -> PhotoStorage:
    if provider == "local":
        local = request.app.state.local_photo_storage
        # Retain the existing test/application injection point when local storage is substituted.
        injected = getattr(request.app.state, "photo_storage", local)
        if injected is not local and getattr(injected, "provider", None) == "local":
            return injected
        return local
    if provider == "google_drive":
        return request.app.state.google_drive_storage
    raise HTTPException(503, "The configured photo storage provider is unavailable")


async def active_storage(request: Request) -> tuple[str, PhotoStorage]:
    try:
        database = get_database(request.app.state.mongo_connection)
        saved = await database["photo_settings"].find_one({"key": "storage_provider"})
    except RuntimeError:
        raise HTTPException(503, "Database service is unavailable") from None
    configured = saved.get("value") if saved else request.app.state.settings.photo_storage_provider
    if configured not in {"local", "google_drive"}:
        raise HTTPException(503, "The configured photo storage provider is invalid")
    request.app.state.photo_storage_provider = configured
    adapter = storage_for(request, configured)
    if configured == "google_drive":
        try:
            # Fail clearly before accepting files; never silently switch to local storage.
            await request.app.state.google_drive_storage.ensure_ready()
        except DriveConfigurationError as exc:
            logger.warning("Selected Google Drive storage is not ready (%s).", type(exc).__name__)
            raise HTTPException(503, "Photo storage is temporarily unavailable") from None
        except Exception:
            raise HTTPException(503, "Google Drive storage is unavailable") from None
    return configured, adapter
