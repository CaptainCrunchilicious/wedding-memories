import re
from datetime import UTC, date, datetime, time
from typing import Any

from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError
from pymongo.asynchronous.database import AsyncDatabase

from app.schemas.album import AlbumCreate, AlbumPage, AlbumPatch, AlbumResponse, CoverImageReference, ResourceStatus
from app.services.management_errors import (
    InvalidStateError,
    ResourceNotFoundError,
    SlugConflictError,
    UnsafeDeleteError,
)
from app.utils.slugs import normalize_slug, slugify_name


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _album_date_for_storage(value: date | None) -> datetime | None:
    return datetime.combine(value, time.min, tzinfo=UTC) if value is not None else None


def _cover_for_storage(value: CoverImageReference | None) -> dict[str, Any] | None:
    return value.model_dump(mode="json", exclude_none=True) if value is not None else None


def album_response(document: dict[str, Any], event_count: int = 0) -> AlbumResponse:
    stored_date = document.get("event_date")
    event_date = _utc(stored_date).date() if isinstance(stored_date, datetime) else stored_date
    return AlbumResponse(
        id=str(document["_id"]),
        name=document["name"],
        slug=document["slug"],
        description=document.get("description"),
        couple_names=document.get("couple_names"),
        event_date=event_date,
        location=document.get("location"),
        cover_image=document.get("cover_image"),
        status=document.get("status", ResourceStatus.ACTIVE),
        event_count=event_count,
        created_at=_utc(document["created_at"]),
        updated_at=_utc(document["updated_at"]),
    )


async def create_album(database: AsyncDatabase, payload: AlbumCreate) -> AlbumResponse:
    values = payload.model_dump()
    try:
        slug = normalize_slug(values["slug"]) if values.get("slug") else slugify_name(values["name"])
    except ValueError as exc:
        raise InvalidStateError(str(exc)) from None
    now = datetime.now(UTC)
    document = {
        **values,
        "slug": slug,
        "event_date": _album_date_for_storage(values.get("event_date")),
        "cover_image": _cover_for_storage(values.get("cover_image")),
        "status": ResourceStatus.ACTIVE.value,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await database["photo_albums"].insert_one(document)
    except DuplicateKeyError:
        raise SlugConflictError("An album with this slug already exists") from None
    document["_id"] = result.inserted_id
    return album_response(document)


async def list_albums(
    database: AsyncDatabase,
    *,
    page: int,
    page_size: int,
    status_filter: ResourceStatus | None = None,
    search: str | None = None,
) -> AlbumPage:
    query: dict[str, Any] = {}
    if status_filter is not None:
        query["status"] = status_filter.value
    if search and search.strip():
        query["name"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    albums = database["photo_albums"]
    total = await albums.count_documents(query)
    cursor = (
        albums.find(query)
        .sort("created_at", DESCENDING)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    documents = await cursor.to_list(length=page_size)
    event_collection = database["photo_events"]
    items = []
    for document in documents:
        count = await event_collection.count_documents({"album_id": document["_id"]})
        items.append(album_response(document, event_count=count))
    return AlbumPage(items=items, total=total, page=page, page_size=page_size)


async def get_album(database: AsyncDatabase, album_id: Any) -> AlbumResponse:
    document = await database["photo_albums"].find_one({"_id": album_id})
    if document is None:
        raise ResourceNotFoundError("Album not found")
    event_count = await database["photo_events"].count_documents({"album_id": album_id})
    return album_response(document, event_count=event_count)


async def update_album(database: AsyncDatabase, album_id: Any, payload: AlbumPatch) -> AlbumResponse:
    albums = database["photo_albums"]
    existing = await albums.find_one({"_id": album_id})
    if existing is None:
        raise ResourceNotFoundError("Album not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise InvalidStateError("Album name cannot be null")
    if "slug" in changes:
        try:
            changes["slug"] = (
                normalize_slug(changes["slug"])
                if changes["slug"] is not None
                else slugify_name(changes.get("name") or existing["name"])
            )
        except ValueError as exc:
            raise InvalidStateError(str(exc)) from None
    if "event_date" in changes:
        changes["event_date"] = _album_date_for_storage(changes["event_date"])
    if "cover_image" in changes:
        changes["cover_image"] = _cover_for_storage(changes["cover_image"])
    if changes:
        changes["updated_at"] = datetime.now(UTC)
        try:
            await albums.update_one({"_id": album_id}, {"$set": changes})
        except DuplicateKeyError:
            raise SlugConflictError("An album with this slug already exists") from None
    return await get_album(database, album_id)


async def set_album_archived(database: AsyncDatabase, album_id: Any, archived: bool) -> AlbumResponse:
    albums = database["photo_albums"]
    if await albums.find_one({"_id": album_id}) is None:
        raise ResourceNotFoundError("Album not found")
    await albums.update_one(
        {"_id": album_id},
        {"$set": {"status": "archived" if archived else "active", "updated_at": datetime.now(UTC)}},
    )
    return await get_album(database, album_id)


async def delete_album(database: AsyncDatabase, album_id: Any) -> None:
    albums = database["photo_albums"]
    if await albums.find_one({"_id": album_id}) is None:
        raise ResourceNotFoundError("Album not found")
    events = await database["photo_events"].count_documents({"album_id": album_id}, limit=1)
    photos = await database["photos"].count_documents({"album_id": album_id}, limit=1)
    contributors = await database["photo_contributors"].count_documents({"album_id": album_id}, limit=1)
    if events or photos or contributors:
        raise UnsafeDeleteError("Album has related events, photos, or contributors and cannot be deleted; archive it instead")
    await albums.delete_one({"_id": album_id})
