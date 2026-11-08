import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from pymongo import ReturnDocument

from app.core.security import get_current_admin
from app.database.connection import get_database
from app.services.photo_delivery import image_response
from app.storage.google_drive import DriveProviderError
from app.storage.registry import storage_for

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/admin/photos", tags=["admin photos"], dependencies=[Depends(get_current_admin)]
)
PhotoId = Annotated[str, Path(min_length=1, max_length=24)]
PhotoStatus = Literal["pending", "approved", "rejected"]
MAX_BULK_APPROVE = 50
DELETION_CLAIM_LEASE_SECONDS = 300


class BulkApproveRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=MAX_BULK_APPROVE)

    @field_validator("photo_ids")
    @classmethod
    def unique_photo_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("photo_ids must not contain duplicates")
        return values


def _database(request: Request):
    try:
        return get_database(request.app.state.mongo_connection)
    except RuntimeError:
        raise HTTPException(503, "Database service is unavailable") from None


def _object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "Photo not found")
    return ObjectId(value)


def _admin_identity(admin: dict) -> dict[str, str]:
    return {"id": str(admin["_id"]), "email": str(admin.get("email", ""))}


async def _admin_photo(database, document: dict) -> dict:
    album = await database["photo_albums"].find_one({"_id": document["album_id"]})
    event = await database["photo_events"].find_one({"_id": document["event_id"]})
    moderator = document.get("moderated_by") or {}
    return {
        "id": str(document["_id"]),
        "original_filename": document.get("original_filename", "photo"),
        "album": {"id": str(document["album_id"]), "name": album.get("name") if album else "Unavailable album",
                  "slug": album.get("slug") if album else None},
        "event": {"id": str(document["event_id"]), "name": event.get("name") if event else "Unavailable event",
                  "slug": event.get("slug") if event else None},
        "mime_type": document.get("mime_type"), "file_size": document.get("file_size"),
        "storage_provider": document.get("storage_provider", "local"),
        "width": document.get("width"), "height": document.get("height"),
        "status": document.get("status", "pending"),
        "deletion_state": document.get("deletion_state"),
        "uploaded_at": document.get("uploaded_at") or document.get("created_at"),
        "moderated_at": document.get("moderated_at"),
        "moderated_by": moderator.get("email") if isinstance(moderator, dict) else None,
    }


def _filters(
    *, album_id: str | None, event_id: str | None, search: str | None, status_filter: PhotoStatus | None
) -> dict:
    query: dict = {}
    for key, value in (("album_id", album_id), ("event_id", event_id)):
        if value:
            if not ObjectId.is_valid(value):
                raise HTTPException(400, f"Invalid {key.removesuffix('_id')} ID")
            query[key] = ObjectId(value)
    if status_filter:
        query["status"] = status_filter
    if search and search.strip():
        query["original_filename"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    return query


@router.post("/bulk-approve")
async def bulk_approve_photos(
    payload: BulkApproveRequest,
    request: Request,
    admin: dict = Depends(get_current_admin),
):
    database = _database(request)
    collection = database["photos"]
    identity = _admin_identity(admin)
    now = datetime.now(UTC)
    results = []
    for photo_id in payload.photo_ids:
        if not ObjectId.is_valid(photo_id):
            results.append({"photo_id": photo_id, "success": False, "error": "Invalid photo ID"})
            continue
        identifier = ObjectId(photo_id)
        current = await collection.find_one({"_id": identifier})
        if current is None:
            results.append({"photo_id": photo_id, "success": False, "error": "Photo not found"})
            continue
        if current.get("deletion_state") == "pending":
            results.append({"photo_id": photo_id, "success": False, "error": "Photo deletion is pending"})
            continue
        if current.get("status", "pending") != "pending":
            results.append({"photo_id": photo_id, "success": False, "error": "Photo is no longer pending"})
            continue
        updated = await collection.update_one(
            {"_id": identifier, "status": "pending", "deletion_state": {"$ne": "pending"}},
            {"$set": {"status": "approved", "moderated_at": now, "moderated_by": identity}},
        )
        if updated.matched_count:
            results.append({"photo_id": photo_id, "success": True, "status": "approved"})
        else:
            results.append({"photo_id": photo_id, "success": False, "error": "Photo changed during approval"})
    return {"results": results, "succeeded": sum(item["success"] for item in results),
            "failed": sum(not item["success"] for item in results)}


@router.get("")
async def list_admin_photos(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    status_filter: PhotoStatus | None = Query(default=None, alias="status"),
    deletion_state: Literal["pending"] | None = Query(default=None),
    album_id: str | None = Query(default=None, min_length=24, max_length=24),
    event_id: str | None = Query(default=None, min_length=24, max_length=24),
    search: str | None = Query(default=None, max_length=120),
):
    database = _database(request)
    collection = database["photos"]
    base_query = _filters(album_id=album_id, event_id=event_id, search=search, status_filter=None)
    if deletion_state == "pending":
        query = {**base_query, "deletion_state": "pending"}
    else:
        query = {**base_query, "deletion_state": {"$ne": "pending"}, **({"status": status_filter} if status_filter else {})}
    total = await collection.count_documents(query)
    cursor = collection.find(query).sort("uploaded_at", -1).skip((page - 1) * page_size).limit(page_size)
    documents = await cursor.to_list(length=page_size)
    counts = {key: await collection.count_documents({**base_query, "deletion_state": {"$ne": "pending"}, "status": key})
              for key in ("pending", "approved", "rejected")}
    deletion_pending = await collection.count_documents({**base_query, "deletion_state": "pending"})
    return {"items": [await _admin_photo(database, document) for document in documents], "total": total,
            "page": page, "page_size": page_size, "counts": {"all": sum(counts.values()) + deletion_pending,
            **counts, "deletion_pending": deletion_pending}}


@router.get("/{photo_id}")
async def get_admin_photo(photo_id: PhotoId, request: Request):
    document = await _database(request)["photos"].find_one({"_id": _object_id(photo_id)})
    if document is None:
        raise HTTPException(404, "Photo not found")
    return await _admin_photo(_database(request), document)


@router.get("/{photo_id}/image")
async def get_admin_photo_image(photo_id: PhotoId, request: Request):
    document = await _database(request)["photos"].find_one({"_id": _object_id(photo_id)})
    if document is None:
        raise HTTPException(404, "Photo not found")
    return await image_response(request, document, private=True)


async def _moderate(photo_id: str, target: Literal["approved", "rejected"], request: Request, admin: dict):
    database = _database(request)
    collection = database["photos"]
    identifier = _object_id(photo_id)
    document = await collection.find_one({"_id": identifier, "deletion_state": {"$ne": "pending"}})
    if document is None:
        raise HTTPException(404, "Photo not found")
    current = document.get("status", "pending")
    allowed = {"approved": {"pending", "rejected"}, "rejected": {"pending", "approved"}}[target]
    if current not in allowed:
        raise HTTPException(409, f"Photo cannot transition from {current} to {target}")
    result = await collection.update_one(
        {"_id": identifier, "status": current, "deletion_state": {"$ne": "pending"}},
        {"$set": {"status": target, "moderated_at": datetime.now(UTC), "moderated_by": _admin_identity(admin)}},
    )
    if not result.matched_count:
        raise HTTPException(409, "Photo changed during moderation; refresh and try again")
    updated = await collection.find_one({"_id": identifier})
    return await _admin_photo(database, updated)


@router.patch("/{photo_id}/approve")
async def approve_photo(photo_id: PhotoId, request: Request, admin: dict = Depends(get_current_admin)):
    return await _moderate(photo_id, "approved", request, admin)


@router.patch("/{photo_id}/reject")
async def reject_photo(photo_id: PhotoId, request: Request, admin: dict = Depends(get_current_admin)):
    return await _moderate(photo_id, "rejected", request, admin)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def permanently_delete_photo(photo_id: PhotoId, request: Request) -> Response:
    database = _database(request)
    collection = database["photos"]
    identifier = _object_id(photo_id)
    now = datetime.now(UTC)
    claim = uuid.uuid4().hex
    document = await collection.find_one_and_update(
        {
            "_id": identifier,
            "$or": [
                {"deletion_state": {"$ne": "pending"}},
                {"deletion_claimed_at": {"$lt": now - timedelta(seconds=DELETION_CLAIM_LEASE_SECONDS)}},
                {"deletion_claimed_at": {"$exists": False}},
            ],
        },
        {"$set": {"deletion_state": "pending", "deletion_claim": claim, "deletion_claimed_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        current = await collection.find_one({"_id": identifier})
        if current is None:
            raise HTTPException(404, "Photo not found")
        raise HTTPException(409, "Photo deletion is already in progress; retry shortly")

    async def release_claim() -> None:
        try:
            await collection.update_one(
                {"_id": identifier, "deletion_claim": claim},
                {"$unset": {"deletion_claim": "", "deletion_claimed_at": ""}},
            )
        except Exception as exc:
            logger.error("Photo deletion claim release failed (%s); retry after the claim expires.", type(exc).__name__)

    provider = document.get("storage_provider", "local")
    try:
        storage = storage_for(request, provider)
    except HTTPException:
        await release_claim()
        raise HTTPException(409, "Photo uses an unavailable storage provider") from None
    file_id = document.get("storage_file_id")
    if not file_id:
        await release_claim()
        raise HTTPException(409, "Photo has no storage identifier; metadata was retained")
    try:
        await storage.delete(file_id)
    except DriveProviderError:
        await release_claim()
        raise HTTPException(503, "Stored image could not be deleted; photo record was retained") from None
    except Exception as exc:
        logger.error("Photo deletion from storage failed (%s).", type(exc).__name__)
        await release_claim()
        raise HTTPException(503, "Stored image could not be deleted; photo record was retained") from None
    try:
        result = await collection.delete_one({"_id": identifier, "deletion_state": "pending", "deletion_claim": claim})
        if not result.deleted_count:
            if await collection.find_one({"_id": identifier}) is None:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            await release_claim()
            raise HTTPException(503, "Image was deleted but the photo record remains pending; retry deletion")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Photo metadata deletion failed after stored image deletion (%s).", type(exc).__name__)
        await release_claim()
        raise HTTPException(503, "Image was deleted but the photo record remains hidden; retry deletion") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
