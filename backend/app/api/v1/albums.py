import logging
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pymongo.errors import PyMongoError

from app.core.security import get_current_admin
from app.database.connection import get_database
from app.schemas.album import (
    AlbumCreate,
    AlbumPage,
    AlbumPatch,
    AlbumResponse,
    EventCreate,
    EventPage,
    EventPatch,
    EventResponse,
    ResourceStatus,
)
from app.services import album_service, event_service
from app.services.management_errors import (
    InvalidStateError,
    ResourceNotFoundError,
    SlugConflictError,
    UnsafeDeleteError,
)
from fastapi import Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/albums", tags=["albums"], dependencies=[Depends(get_current_admin)])
AlbumId = Annotated[str, Path(min_length=1, max_length=24)]
EventId = Annotated[str, Path(min_length=1, max_length=24)]


def _object_id(value: str, kind: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail=f"Invalid {kind} ID")
    return ObjectId(value)


def _database(request: Request):
    try:
        return get_database(request.app.state.mongo_connection)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Database service is unavailable") from None


def _handle_management_error(error: Exception) -> None:
    if isinstance(error, ResourceNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from None
    if isinstance(error, (SlugConflictError, UnsafeDeleteError)):
        raise HTTPException(status_code=409, detail=str(error)) from None
    if isinstance(error, InvalidStateError):
        raise HTTPException(status_code=400, detail=str(error)) from None
    raise error


def _handle_database_error(error: PyMongoError) -> None:
    logger.error("Album/event database operation failed (%s).", type(error).__name__)
    raise HTTPException(status_code=503, detail="Database service is unavailable") from None


@router.post("", response_model=AlbumResponse, status_code=status.HTTP_201_CREATED)
async def create_album(payload: AlbumCreate, request: Request) -> AlbumResponse:
    try:
        return await album_service.create_album(_database(request), payload)
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.get("", response_model=AlbumPage)
async def list_albums(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: ResourceStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=120),
) -> AlbumPage:
    try:
        return await album_service.list_albums(
            _database(request),
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            search=search,
        )
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.get("/{album_id}", response_model=AlbumResponse)
async def get_album(album_id: AlbumId, request: Request) -> AlbumResponse:
    try:
        return await album_service.get_album(_database(request), _object_id(album_id, "album"))
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.patch("/{album_id}", response_model=AlbumResponse)
async def update_album(album_id: AlbumId, payload: AlbumPatch, request: Request) -> AlbumResponse:
    try:
        return await album_service.update_album(_database(request), _object_id(album_id, "album"), payload)
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.patch("/{album_id}/archive", response_model=AlbumResponse)
async def archive_album(album_id: AlbumId, request: Request) -> AlbumResponse:
    try:
        return await album_service.set_album_archived(_database(request), _object_id(album_id, "album"), True)
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.patch("/{album_id}/restore", response_model=AlbumResponse)
async def restore_album(album_id: AlbumId, request: Request) -> AlbumResponse:
    try:
        return await album_service.set_album_archived(_database(request), _object_id(album_id, "album"), False)
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.delete("/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_album(album_id: AlbumId, request: Request) -> Response:
    try:
        await album_service.delete_album(_database(request), _object_id(album_id, "album"))
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{album_id}/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(album_id: AlbumId, payload: EventCreate, request: Request) -> EventResponse:
    try:
        return await event_service.create_event(_database(request), _object_id(album_id, "album"), payload)
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.get("/{album_id}/events", response_model=EventPage)
async def list_events(
    album_id: AlbumId,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    status_filter: ResourceStatus | None = Query(default=None, alias="status"),
) -> EventPage:
    try:
        return await event_service.list_events(
            _database(request),
            _object_id(album_id, "album"),
            page=page,
            page_size=page_size,
            status_filter=status_filter,
        )
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.get("/{album_id}/events/{event_id}", response_model=EventResponse)
async def get_event(album_id: AlbumId, event_id: EventId, request: Request) -> EventResponse:
    try:
        return await event_service.get_event(
            _database(request), _object_id(album_id, "album"), _object_id(event_id, "event")
        )
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.patch("/{album_id}/events/{event_id}", response_model=EventResponse)
async def update_event(
    album_id: AlbumId,
    event_id: EventId,
    payload: EventPatch,
    request: Request,
) -> EventResponse:
    try:
        return await event_service.update_event(
            _database(request),
            _object_id(album_id, "album"),
            _object_id(event_id, "event"),
            payload,
        )
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.patch("/{album_id}/events/{event_id}/archive", response_model=EventResponse)
async def archive_event(album_id: AlbumId, event_id: EventId, request: Request) -> EventResponse:
    try:
        return await event_service.set_event_archived(
            _database(request), _object_id(album_id, "album"), _object_id(event_id, "event"), True
        )
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.patch("/{album_id}/events/{event_id}/restore", response_model=EventResponse)
async def restore_event(album_id: AlbumId, event_id: EventId, request: Request) -> EventResponse:
    try:
        return await event_service.set_event_archived(
            _database(request), _object_id(album_id, "album"), _object_id(event_id, "event"), False
        )
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)


@router.delete("/{album_id}/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(album_id: AlbumId, event_id: EventId, request: Request) -> Response:
    try:
        await event_service.delete_event(
            _database(request), _object_id(album_id, "album"), _object_id(event_id, "event")
        )
    except (ResourceNotFoundError, SlugConflictError, UnsafeDeleteError, InvalidStateError) as exc:
        _handle_management_error(exc)
    except PyMongoError as exc:
        _handle_database_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
