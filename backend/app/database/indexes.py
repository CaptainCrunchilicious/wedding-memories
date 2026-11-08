from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.database.collections import (
    ADMINISTRATORS,
    PHOTO_ALBUMS,
    PHOTO_CONTRIBUTORS,
    PHOTO_EVENTS,
    PHOTOS,
    PHOTO_SETTINGS,
)


async def initialize_indexes(database: AsyncDatabase) -> None:
    """Create only the first query-supporting indexes; names make setup repeatable."""
    indexes = {
        ADMINISTRATORS: [
            ([('email', ASCENDING)], {"unique": True, "name": "uq_administrators_email"}),
            ([('account_slot', ASCENDING)], {"unique": True, "name": "uq_administrators_account_slot"}),
        ],
        PHOTO_ALBUMS: [
            ([('slug', ASCENDING)], {"unique": True, "name": "uq_photo_albums_slug"}),
            ([('created_at', DESCENDING)], {"name": "ix_photo_albums_created_at_desc"}),
        ],
        PHOTO_EVENTS: [
            ([('album_id', ASCENDING)], {"name": "ix_photo_events_album_id"}),
            ([('album_id', ASCENDING), ('slug', ASCENDING)], {"unique": True, "name": "uq_photo_events_album_slug"}),
            ([('created_at', DESCENDING)], {"name": "ix_photo_events_created_at_desc"}),
        ],
        PHOTOS: [
            ([('client_upload_id', ASCENDING)], {"unique": True, "sparse": True, "name": "uq_photos_client_upload_id"}),
            ([('album_id', ASCENDING)], {"name": "ix_photos_album_id"}),
            ([('event_id', ASCENDING)], {"name": "ix_photos_event_id"}),
            ([('status', ASCENDING)], {"name": "ix_photos_status"}),
            ([('uploaded_at', DESCENDING)], {"name": "ix_photos_uploaded_at_desc"}),
            ([('album_id', ASCENDING), ('status', ASCENDING)], {"name": "ix_photos_album_status"}),
            ([('event_id', ASCENDING), ('status', ASCENDING)], {"name": "ix_photos_event_status"}),
            ([('status', ASCENDING), ('uploaded_at', DESCENDING)], {"name": "ix_photos_status_uploaded_at"}),
            ([('album_id', ASCENDING), ('status', ASCENDING), ('uploaded_at', DESCENDING)], {"name": "ix_photos_album_status_uploaded_at"}),
            ([('event_id', ASCENDING), ('status', ASCENDING), ('uploaded_at', DESCENDING)], {"name": "ix_photos_event_status_uploaded_at"}),
        ],
        PHOTO_CONTRIBUTORS: [
            ([('album_id', ASCENDING)], {"name": "ix_photo_contributors_album_id"}),
            ([('created_at', DESCENDING)], {"name": "ix_photo_contributors_created_at_desc"}),
        ],
        PHOTO_SETTINGS: [
            ([('key', ASCENDING)], {"unique": True, "name": "uq_photo_settings_key"}),
        ],
    }

    for collection_name, definitions in indexes.items():
        collection = database[collection_name]
        for keys, options in definitions:
            await collection.create_index(keys, **options)
