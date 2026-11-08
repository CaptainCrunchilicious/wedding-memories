"""Secure interactive offline password reset for the single owner account."""

import asyncio
from datetime import UTC, datetime
from getpass import getpass

from pymongo.errors import PyMongoError

from app.core.config import get_settings
from app.database.connection import MongoConnection, get_database
from app.utils.create_admin import MINIMUM_PASSWORD_LENGTH
from app.utils.passwords import hash_password


async def reset_admin_password() -> int:
    settings = get_settings()
    if not settings.mongodb_uri.strip():
        print("Password reset failed: MONGODB_URI is not configured in backend/.env.")
        return 1

    connection = MongoConnection(settings)
    try:
        await connection.connect()
        collection = get_database(connection)["administrators"]
        if await collection.count_documents({}, limit=2) != 1:
            print("Password reset refused: expected exactly one administrator account.")
            return 1

        password = getpass("New password (minimum 12 characters): ")
        confirmation = getpass("Confirm new password: ")
        if len(password) < MINIMUM_PASSWORD_LENGTH:
            print("Password reset failed: password must be at least 12 characters.")
            return 1
        if password != confirmation:
            print("Password reset failed: password confirmation did not match.")
            return 1

        admin = await collection.find_one({})
        if admin is None:
            print("Password reset refused: administrator account was not found.")
            return 1
        result = await collection.update_one(
            {"_id": admin["_id"]},
            {
                "$set": {
                    "password_hash": hash_password(password),
                    "updated_at": datetime.now(UTC),
                },
                "$inc": {"token_version": 1},
            },
        )
        if result.modified_count != 1:
            print("Password reset failed: account was not updated.")
            return 1
        print("Administrator password reset successfully; existing tokens were revoked.")
        return 0
    except (PyMongoError, RuntimeError) as exc:
        print(f"Password reset failed: database operation error ({type(exc).__name__}).")
        return 1
    except Exception as exc:
        print(f"Password reset failed ({type(exc).__name__}).")
        return 1
    finally:
        await connection.close()


def main() -> None:
    raise SystemExit(asyncio.run(reset_admin_password()))


if __name__ == "__main__":
    main()
