import logging

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings

logger = logging.getLogger(__name__)


class MongoConnection:
    """Owns the application's single asynchronous MongoDB client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.client: AsyncMongoClient | None = None
        self.database: AsyncDatabase | None = None
        self.is_connected = False

    async def connect(self) -> None:
        if not self._settings.mongodb_uri.strip():
            return

        self.client = AsyncMongoClient(
            self._settings.mongodb_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=5_000,
            socketTimeoutMS=10_000,
        )
        try:
            await self.client.admin.command("ping")
        except Exception:
            await self.close()
            raise

        self.database = self.client.get_database(self._settings.mongodb_database)
        self.is_connected = True

    async def check_connection(self) -> bool:
        """Run a lightweight ping for readiness checks and update connection state."""
        if self.client is None:
            self.is_connected = False
            return False
        try:
            await self.client.admin.command("ping")
        except Exception as exc:
            self.is_connected = False
            logger.warning("MongoDB health ping failed (%s).", type(exc).__name__)
            return False
        self.is_connected = True
        return True

    async def close(self) -> None:
        client, self.client = self.client, None
        self.database = None
        self.is_connected = False
        if client is not None:
            await client.close()


def get_database(connection: MongoConnection) -> AsyncDatabase:
    """Return the selected database or raise when the connection is unavailable."""
    if not connection.is_connected or connection.database is None:
        raise RuntimeError("MongoDB database is not connected")
    return connection.database
