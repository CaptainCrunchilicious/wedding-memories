import logging

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.storage.registry import storage_for
from app.storage.google_drive import DriveProviderError
logger = logging.getLogger(__name__)
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def image_response(
    request, document: dict, *, private: bool, download: bool = False
) -> StreamingResponse:
    provider = document.get("storage_provider", "local")
    storage = storage_for(request, provider)
    file_id = document.get("storage_file_id")
    mime_type = document.get("mime_type")
    if not file_id or mime_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(404, "Photo image not found")
    try:
        content = await storage.open_read(file_id)
    except FileNotFoundError:
        raise HTTPException(404, "Photo image not found") from None
    except (ValueError, OSError) as exc:
        logger.warning("Photo image could not be opened (%s).", type(exc).__name__)
        raise HTTPException(404, "Photo image not found") from None
    except DriveProviderError:
        raise HTTPException(503, "Photo storage is temporarily unavailable") from None
    extension = "jpg" if mime_type == "image/jpeg" else mime_type.rsplit("/", 1)[-1]
    return StreamingResponse(
        content.chunks,
        media_type=mime_type,
        headers={
            "Content-Length": str(content.size or document.get("file_size") or 0),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store" if private else "public, max-age=60",
            "Content-Disposition": f"{'attachment' if download else 'inline'}; filename=photo.{extension}",
        },
    )
