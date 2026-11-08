import hashlib
import hmac
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

import jwt
from bson import ObjectId
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from app.core.config import Settings
from app.database.connection import get_database
from app.services.photo_validation import InvalidPhotoError, validate_and_sanitize
from app.services.upload_guard import UploadGuard, UploadRateLimitError
from app.services.photo_delivery import image_response
from app.storage.registry import active_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public", tags=["public"])


def _clean_date(value):
    if isinstance(value, datetime):
        return (value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _cover(document):
    ref = document.get("cover_image")
    return {"url": ref.get("url"), "reference": ref.get("reference"), "alt_text": ref.get("alt_text")} if ref else None


def _public_album(document):
    return {
        "name": document["name"], "slug": document["slug"], "description": document.get("description"),
        "couple_names": document.get("couple_names"), "event_date": _clean_date(document.get("event_date")),
        "location": document.get("location"), "cover_image": _cover(document),
    }


def _public_event(document):
    return {
        "name": document["name"], "slug": document["slug"], "description": document.get("description"),
        "event_date": _clean_date(document.get("event_date")), "location": document.get("location"),
        "cover_image": _cover(document),
    }


def _public_photo(document, api_prefix: str):
    identifier = str(document["_id"])
    return {
        "id": identifier,
        "image_url": f"{api_prefix.rstrip('/')}/public/photos/{identifier}/image",
        "mime_type": document.get("mime_type"),
        "file_size": document.get("file_size"),
        "width": document.get("width"),
        "height": document.get("height"),
        "uploaded_at": _clean_date(document.get("uploaded_at") or document.get("created_at")),
    }


def _db(request: Request):
    try:
        return get_database(request.app.state.mongo_connection)
    except RuntimeError:
        raise HTTPException(503, "Database service is unavailable") from None


async def _active_album(database, album_slug: str):
    album = await database["photo_albums"].find_one({"slug": album_slug, "status": "active"})
    if not album:
        raise HTTPException(404, "Album not found")
    return album


async def _active_context(database, album_slug: str, event_slug: str):
    album = await _active_album(database, album_slug)
    event = await database["photo_events"].find_one(
        {"album_id": album["_id"], "slug": event_slug, "status": "active"}
    )
    if not event:
        raise HTTPException(404, "Event not found")
    return album, event


async def _navigation(database, album_id):
    cursor = database["photo_events"].find({"album_id": album_id, "status": "active"}).sort(
        [("display_order", 1), ("created_at", 1)]
    )
    return [{"name": e["name"], "slug": e["slug"]} for e in await cursor.to_list(length=200)]


@router.get("/albums/{album_slug}")
async def get_public_album(album_slug: str, request: Request):
    database = _db(request)
    album = await _active_album(database, album_slug)
    return {"album": _public_album(album), "events": await _navigation(database, album["_id"])}


@router.get("/albums/{album_slug}/events")
async def list_public_events(album_slug: str, request: Request):
    database = _db(request)
    album = await _active_album(database, album_slug)
    return {"album": _public_album(album), "events": await _navigation(database, album["_id"])}


@router.get("/albums/{album_slug}/events/{event_slug}")
async def get_public_event(album_slug: str, event_slug: str, request: Request):
    database = _db(request)
    album, event = await _active_context(database, album_slug, event_slug)
    return {"album": _public_album(album), "event": _public_event(event), "events": await _navigation(database, album["_id"])}


@router.get("/albums/{album_slug}/photos")
async def list_album_photos(
    album_slug: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=60),
):
    database = _db(request)
    album = await _active_album(database, album_slug)
    active_events = await database["photo_events"].find(
        {"album_id": album["_id"], "status": "active"}
    ).to_list(length=1000)
    event_ids = [event["_id"] for event in active_events]
    query = {"album_id": album["_id"], "status": "approved", "deletion_state": {"$ne": "pending"}, "event_id": {"$in": event_ids}}
    collection = database["photos"]
    total = await collection.count_documents(query) if event_ids else 0
    cursor = collection.find(query).sort("uploaded_at", -1).skip((page - 1) * page_size).limit(page_size)
    documents = await cursor.to_list(length=page_size) if event_ids else []
    prefix = request.app.state.settings.api_v1_prefix
    return {"items": [_public_photo(item, prefix) for item in documents], "total": total,
            "page": page, "page_size": page_size}


@router.get("/albums/{album_slug}/events/{event_slug}/photos")
async def list_event_photos(
    album_slug: str,
    event_slug: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=60),
):
    database = _db(request)
    album, event = await _active_context(database, album_slug, event_slug)
    collection = database["photos"]
    query = {"album_id": album["_id"], "event_id": event["_id"], "status": "approved", "deletion_state": {"$ne": "pending"}}
    total = await collection.count_documents(query)
    cursor = collection.find(query).sort("uploaded_at", -1).skip((page - 1) * page_size).limit(page_size)
    documents = await cursor.to_list(length=page_size)
    prefix = request.app.state.settings.api_v1_prefix
    return {"items": [_public_photo(item, prefix) for item in documents], "total": total,
            "page": page, "page_size": page_size}


@router.get("/photos/{photo_id}/image")
async def get_public_photo_image(photo_id: str, request: Request, download: bool = Query(default=False)):
    if not ObjectId.is_valid(photo_id):
        raise HTTPException(404, "Photo image not found")
    database = _db(request)
    photo = await database["photos"].find_one({"_id": ObjectId(photo_id), "status": "approved", "deletion_state": {"$ne": "pending"}})
    if photo is None:
        raise HTTPException(404, "Photo image not found")
    album = await database["photo_albums"].find_one(
        {"_id": photo.get("album_id"), "status": "active"}
    )
    event = await database["photo_events"].find_one(
        {"_id": photo.get("event_id"), "album_id": photo.get("album_id"), "status": "active"}
    )
    if album is None or event is None:
        raise HTTPException(404, "Photo image not found")
    return await image_response(request, photo, private=False, download=download)


def _upload_key(settings: Settings) -> bytes:
    secret = settings.jwt_secret.get_secret_value().encode()
    if len(secret) < 32:
        raise HTTPException(503, "Upload sessions are not configured")
    return hmac.new(secret, b"wedding-memories:photo-upload-session:v1", hashlib.sha256).digest()


def _guard(request: Request) -> UploadGuard:
    return request.app.state.upload_guard


def _client_ip(request: Request) -> str:
    # Use the direct peer, not an untrusted forwarded header.
    return request.client.host if request.client else "unknown"


@router.post("/albums/{album_slug}/events/{event_slug}/upload-session")
async def create_upload_session(album_slug: str, event_slug: str, request: Request):
    settings: Settings = request.app.state.settings
    try:
        await _guard(request).allow_ip("session", _client_ip(request), settings.upload_sessions_per_ip_per_hour)
    except UploadRateLimitError as exc:
        raise HTTPException(429, str(exc)) from None
    database = _db(request)
    await _active_context(database, album_slug, event_slug)
    expires = datetime.now(UTC) + timedelta(minutes=settings.upload_session_minutes)
    payload = {
        "sub": "guest-upload", "iss": "wedding-memories", "aud": "photo-upload", "token_use": "upload_session",
        "scope": ["photo:upload"], "album_slug": album_slug, "event_slug": event_slug,
        "jti": ObjectId().binary.hex(), "iat": datetime.now(UTC), "exp": expires,
    }
    token = jwt.encode(payload, _upload_key(settings), algorithm="HS256")
    return {"token": token, "expires_at": expires.isoformat(), "max_files": settings.upload_max_files_per_request,
            "max_file_bytes": settings.upload_max_file_bytes, "max_request_bytes": settings.upload_max_request_bytes}


def _decode_upload_token(token: str, settings: Settings, album_slug: str, event_slug: str):
    try:
        claims = jwt.decode(token, _upload_key(settings), algorithms=["HS256"], audience="photo-upload", issuer="wedding-memories")
    except (jwt.PyJWTError, HTTPException):
        raise HTTPException(401, "Invalid or expired upload session") from None
    if (claims.get("token_use") != "upload_session" or "photo:upload" not in claims.get("scope", [])
            or claims.get("album_slug") != album_slug or claims.get("event_slug") != event_slug
            or not claims.get("jti")):
        raise HTTPException(403, "Upload session does not match this event")
    return claims


@router.post("/albums/{album_slug}/events/{event_slug}/photos")
async def upload_photos(
    album_slug: str,
    event_slug: str,
    request: Request,
    upload_token: Annotated[str, Form()],
    upload_ids: Annotated[list[str], Form()],
    files: Annotated[list[UploadFile], File()],
):
    settings: Settings = request.app.state.settings
    claims = _decode_upload_token(upload_token, settings, album_slug, event_slug)
    if not files or len(files) != len(upload_ids) or len(files) > settings.upload_max_files_per_request:
        raise HTTPException(413, f"Choose between 1 and {settings.upload_max_files_per_request} photos per upload.")
    try:
        if any(str(uuid.UUID(value)) != value for value in upload_ids) or len(set(upload_ids)) != len(upload_ids):
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(422, "Each photo needs a unique valid upload ID.") from None
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.upload_max_request_bytes:
        raise HTTPException(413, "The upload request exceeds the allowed size.")
    try:
        await _guard(request).allow_ip("upload", _client_ip(request), settings.upload_requests_per_ip_per_hour)
    except UploadRateLimitError as exc:
        raise HTTPException(429, str(exc)) from None

    database = _db(request)
    album, event = await _active_context(database, album_slug, event_slug)
    results = []
    storage = None
    for file, client_upload_id in zip(files, upload_ids, strict=True):
        original = (file.filename or "photo").replace("\\", "/").split("/")[-1][:255] or "photo"
        file_id = None
        try:
            previous = await database["photos"].find_one({
                "client_upload_id": client_upload_id, "album_id": album["_id"], "event_id": event["_id"]
            })
            if previous:
                results.append({"success": True, "filename": original, "status": previous.get("status", "pending")})
                continue
            if storage is None:
                _, storage = await active_storage(request)
            if file.size is not None and file.size > settings.upload_max_file_bytes:
                raise InvalidPhotoError("This photo exceeds the per-file size limit.")
            raw = await file.read(settings.upload_max_file_bytes + 1)
            if len(raw) > settings.upload_max_file_bytes:
                raise InvalidPhotoError("This photo exceeds the per-file size limit.")
            cleaned, mime, width, height = validate_and_sanitize(raw, file.content_type)
            if len(cleaned) > settings.upload_max_file_bytes:
                raise InvalidPhotoError("The processed photo exceeds the per-file size limit.")
            try:
                await _guard(request).consume_session(
                    claims["jti"], 1, len(cleaned), settings.upload_max_files_per_session,
                    settings.upload_max_bytes_per_session, float(claims["exp"]),
                )
            except UploadRateLimitError as exc:
                raise InvalidPhotoError(str(exc)) from None
            stored = await storage.upload(
                cleaned, mime, client_upload_id=client_upload_id,
                album_slug=album["slug"], event_slug=event["slug"],
            )
            file_id = stored.file_id
            now = datetime.now(UTC)
            doc = {
                "album_id": album["_id"], "event_id": event["_id"], "storage_provider": stored.provider,
                "storage_file_id": stored.file_id, "original_filename": original, "mime_type": mime,
                "file_size": stored.size, "width": width, "height": height, "status": "pending",
                "uploaded_at": now, "created_at": now, "client_upload_id": client_upload_id,
            }
            await database["photos"].insert_one(doc)
            results.append({"success": True, "filename": original, "status": "pending"})
        except InvalidPhotoError as exc:
            results.append({"success": False, "filename": original, "error": str(exc)})
        except HTTPException:
            if file_id and storage is not None:
                try:
                    await storage.delete(file_id)
                except Exception as cleanup_exc:
                    logger.error("Photo storage cleanup failed (%s).", type(cleanup_exc).__name__)
            raise
        except Exception as exc:
            if file_id:
                try:
                    assert storage is not None
                    await storage.delete(file_id)
                except Exception as cleanup_exc:
                    logger.error("Stored photo cleanup failed (%s); an orphan may need investigation.", type(cleanup_exc).__name__)
            logger.error("Photo upload failed (%s).", type(exc).__name__)
            results.append({"success": False, "filename": original, "error": "This photo could not be saved. Please retry."})
        finally:
            await file.close()
    return {"results": results, "succeeded": sum(bool(result["success"]) for result in results),
            "failed": sum(not result["success"] for result in results)}
