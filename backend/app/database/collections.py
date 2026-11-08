from pymongo.asynchronous.database import AsyncDatabase

ADMINISTRATORS = "administrators"
PHOTO_ALBUMS = "photo_albums"
PHOTO_EVENTS = "photo_events"
PHOTOS = "photos"
PHOTO_CONTRIBUTORS = "photo_contributors"
PHOTO_SETTINGS = "photo_settings"

COLLECTION_NAMES = (
    ADMINISTRATORS,
    PHOTO_ALBUMS,
    PHOTO_EVENTS,
    PHOTOS,
    PHOTO_CONTRIBUTORS,
    PHOTO_SETTINGS,
)


async def initialize_collections(database: AsyncDatabase) -> None:
    """Create the known collections if absent; safe to call on every startup."""
    existing = set(await database.list_collection_names())
    for name in COLLECTION_NAMES:
        if name not in existing:
            await database.create_collection(name)
