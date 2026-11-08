from datetime import UTC, datetime
from typing import Any

from pymongo.errors import DuplicateKeyError
from pymongo.asynchronous.collection import AsyncCollection

OWNER_ACCOUNT_SLOT = "owner"


class AdministratorAlreadyExistsError(Exception):
    """Raised when the one allowed administrator already exists."""


async def create_single_administrator(
    collection: AsyncCollection,
    *,
    email: str,
    password_hash: str,
) -> dict[str, Any]:
    """Create the owner record, with a unique slot index protecting races."""
    if await collection.count_documents({}, limit=1):
        raise AdministratorAlreadyExistsError

    now = datetime.now(UTC)
    document = {
        "email": email.strip().lower(),
        "password_hash": password_hash,
        "account_slot": OWNER_ACCOUNT_SLOT,
        "is_active": True,
        "token_version": 0,
        "created_at": now,
        "updated_at": now,
        "last_login_at": None,
    }
    try:
        await collection.insert_one(document)
    except DuplicateKeyError as exc:
        raise AdministratorAlreadyExistsError from exc
    return document
