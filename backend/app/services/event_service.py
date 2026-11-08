from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError
from pymongo.asynchronous.database import AsyncDatabase

from app.schemas.album import EventCreate, EventPage, EventPatch, EventResponse, ResourceStatus
from app.services.management_errors import (
    InvalidStateError,
    ResourceNotFoundError,
    SlugConflictError,
    UnsafeDeleteError,
)
from app.utils.slugs import normalize_slug, slugify_name


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _cover_for_storage(value) -> dict[str, Any] | None:
    return value.model_dump(mode="json", exclude_none=True) if value is not None else None


def event_response(document: dict[str, Any]) -> EventResponse:
    event_date = document.get("event_date")
    return EventResponse(
        id=str(document["_id"]),
        album_id=str(document["album_id"]),
        name=document["name"],
        slug=document["slug"],
        description=document.get("description"),
        event_date=_utc(event_date) if event_date is not None else None,
        location=document.get("location"),
        cover_image=document.get("cover_image"),
        status=document.get("status", ResourceStatus.ACTIVE),
        display_order=int(document.get("display_order", 0)),
        created_at=_utc(document["created_at"]),
        updated_at=_utc(document["updated_at"]),
    )


async def _require_album(database: AsyncDatabase, album_id: Any) -> dict[str, Any]:
    album = await database["photo_albums"].find_one({"_id": album_id})
    if album is None:
        raise ResourceNotFoundError("Album not found")
    return album


async def create_event(database: AsyncDatabase, album_id: Any, payload: EventCreate) -> EventResponse:
    album = await _require_album(database, album_id)
    if album.get("status", "active") != "active":
        raise InvalidStateError("Cannot create an event in an archived album")
    values = payload.model_dump()
    try:
        slug = normalize_slug(values["slug"]) if values.get("slug") else slugify_name(values["name"])
    except ValueError as exc:
        raise InvalidStateError(str(exc)) from None
    now = datetime.now(UTC)
    document = {
        **values,
        "album_id": album_id,
        "slug": slug,
        "cover_image": _cover_for_storage(values.get("cover_image")),
        "status": ResourceStatus.ACTIVE.value,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await database["photo_events"].insert_one(document)
    except DuplicateKeyError:
        raise SlugConflictError("An event with this slug already exists in this album") from None
    document["_id"] = result.inserted_id
    return event_response(document)


async def list_events(
    database: AsyncDatabase,
    album_id: Any,
    *,
    page: int,
    page_size: int,
    status_filter: ResourceStatus | None = None,
) -> EventPage:
    await _require_album(database, album_id)
    query: dict[str, Any] = {"album_id": album_id}
    if status_filter is not None:
        query["status"] = status_filter.value
    collection = database["photo_events"]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort([("display_order", ASCENDING), ("created_at", ASCENDING)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    documents = await cursor.to_list(length=page_size)
    return EventPage(
        items=[event_response(document) for document in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_event(database: AsyncDatabase, album_id: Any, event_id: Any) -> EventResponse:
    await _require_album(database, album_id)
    document = await database["photo_events"].find_one({"_id": event_id, "album_id": album_id})
    if document is None:
        raise ResourceNotFoundError("Event not found in this album")
    return event_response(document)


async def update_event(
    database: AsyncDatabase,
    album_id: Any,
    event_id: Any,
    payload: EventPatch,
) -> EventResponse:
    await _require_album(database, album_id)
    collection = database["photo_events"]
    existing = await collection.find_one({"_id": event_id, "album_id": album_id})
    if existing is None:
        raise ResourceNotFoundError("Event not found in this album")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise InvalidStateError("Event name cannot be null")
    if "slug" in changes:
        try:
            changes["slug"] = (
                normalize_slug(changes["slug"])
                if changes["slug"] is not None
                else slugify_name(changes.get("name") or existing["name"])
            )
        except ValueError as exc:
            raise InvalidStateError(str(exc)) from None
    if "cover_image" in changes:
        changes["cover_image"] = _cover_for_storage(changes["cover_image"])
    if changes:
        changes["updated_at"] = datetime.now(UTC)
        try:
            await collection.update_one(
                {"_id": event_id, "album_id": album_id},
                {"$set": changes},
            )
        except DuplicateKeyError:
            raise SlugConflictError("An event with this slug already exists in this album") from None
    return await get_event(database, album_id, event_id)


async def set_event_archived(
    database: AsyncDatabase,
    album_id: Any,
    event_id: Any,
    archived: bool,
) -> EventResponse:
    album = await _require_album(database, album_id)
    if not archived and album.get("status", "active") != "active":
        raise InvalidStateError("Cannot restore an event while its album is archived")
    collection = database["photo_events"]
    query = {"_id": event_id, "album_id": album_id}
    if await collection.find_one(query) is None:
        raise ResourceNotFoundError("Event not found in this album")
    await collection.update_one(
        query,
        {"$set": {"status": "archived" if archived else "active", "updated_at": datetime.now(UTC)}},
    )
    return await get_event(database, album_id, event_id)


async def delete_event(database: AsyncDatabase, album_id: Any, event_id: Any) -> None:
    await _require_album(database, album_id)
    events = database["photo_events"]
    query = {"_id": event_id, "album_id": album_id}
    if await events.find_one(query) is None:
        raise ResourceNotFoundError("Event not found in this album")
    photos = await database["photos"].count_documents({"album_id": album_id, "event_id": event_id}, limit=1)
    if photos:
        raise UnsafeDeleteError("Event has associated photos and cannot be deleted; archive it instead")
    await events.delete_one(query)
