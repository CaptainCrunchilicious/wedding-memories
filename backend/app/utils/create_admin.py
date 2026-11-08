"""Secure interactive CLI for creating the one Wedding Memories administrator."""

import asyncio
from getpass import getpass
from pydantic import EmailStr, TypeAdapter, ValidationError
from pymongo.errors import PyMongoError

from app.core.config import get_settings
from app.database.collections import initialize_collections
from app.database.connection import MongoConnection, get_database
from app.database.indexes import initialize_indexes
from app.services.admin_service import (
    AdministratorAlreadyExistsError,
    create_single_administrator,
)
from app.utils.passwords import hash_password

MINIMUM_PASSWORD_LENGTH = 12


async def create_admin_interactive() -> int:
    settings = get_settings()
    if not settings.mongodb_uri.strip():
        print("Administrator creation failed: MONGODB_URI is not configured in backend/.env.")
        return 1

    connection = MongoConnection(settings)
    try:
        await connection.connect()
        database = get_database(connection)
        await initialize_collections(database)
        await initialize_indexes(database)
        collection = database["administrators"]

        if await collection.count_documents({}, limit=1):
            print("Administrator creation refused: the single administrator already exists.")
            return 1

        try:
            email = str(TypeAdapter(EmailStr).validate_python(input("Administrator email: "))).strip().lower()
        except ValidationError:
            print("Administrator creation failed: enter a valid email address.")
            return 1

        password = getpass("Password (minimum 12 characters): ")
        confirmation = getpass("Confirm password: ")
        if len(password) < MINIMUM_PASSWORD_LENGTH:
            print("Administrator creation failed: password must be at least 12 characters.")
            return 1
        if password != confirmation:
            print("Administrator creation failed: password confirmation did not match.")
            return 1

        password_hash = hash_password(password)
        await create_single_administrator(collection, email=email, password_hash=password_hash)
        print("Administrator created successfully.")
        return 0
    except AdministratorAlreadyExistsError:
        print("Administrator creation refused: the single administrator already exists.")
        return 1
    except (PyMongoError, RuntimeError) as exc:
        print(f"Administrator creation failed: database operation error ({type(exc).__name__}).")
        return 1
    except Exception as exc:
        print(f"Administrator creation failed ({type(exc).__name__}).")
        return 1
    finally:
        await connection.close()


def main() -> None:
    raise SystemExit(asyncio.run(create_admin_interactive()))


if __name__ == "__main__":
    main()
