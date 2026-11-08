from unittest.mock import AsyncMock, Mock

import pytest
import httpx
from pymongo.errors import ServerSelectionTimeoutError

from app.core.config import Settings
from app.database import connection as connection_module
from app.database.collections import COLLECTION_NAMES, initialize_collections
from app.database.connection import MongoConnection
from app.main import create_app


def settings(uri: str = "", name: str = "test_wedding_memories") -> Settings:
    return Settings(mongodb_uri=uri, mongodb_database=name, photo_storage_provider="local")


async def request_health(app):
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    return response


class FakeConnection:
    def __init__(self, config: Settings, error: Exception | None = None) -> None:
        self.config = config
        self.database = Mock(name="database")
        self.error = error
        self.client = object() if config.mongodb_uri and error is None else None
        self.check_connection = AsyncMock(return_value=True)
        self.close = AsyncMock(side_effect=lambda: setattr(self, "client", None))

    async def connect(self) -> None:
        if self.error:
            raise self.error


@pytest.mark.asyncio
async def test_application_starts_and_reports_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.initialize_collections", AsyncMock())
    monkeypatch.setattr("app.main.initialize_indexes", AsyncMock())
    app = create_app(settings_provider=lambda: settings())

    response = await request_health(app)

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "application": "Wedding Memories",
        "database": {"status": "not_configured", "name": "test_wedding_memories"},
    }


@pytest.mark.asyncio
async def test_health_reports_connected_and_initializes_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    config = settings("mongodb://user:private-password@localhost:27017")
    connection = FakeConnection(config)
    connection_class = Mock(return_value=connection)
    collections = AsyncMock()
    indexes = AsyncMock()
    monkeypatch.setattr("app.main.MongoConnection", connection_class)
    monkeypatch.setattr("app.main.initialize_collections", collections)
    monkeypatch.setattr("app.main.initialize_indexes", indexes)

    response = await request_health(create_app(settings_provider=lambda: config))

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "application": "Wedding Memories",
        "database": {"status": "connected", "name": "test_wedding_memories"},
    }
    collections.assert_awaited_once_with(connection.database)
    indexes.assert_awaited_once_with(connection.database)
    connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_reports_disconnected_when_connection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    config = settings("mongodb://user:private-password@unavailable.invalid:27017")
    connection = FakeConnection(config, error=ServerSelectionTimeoutError("connection failed"))
    monkeypatch.setattr("app.main.MongoConnection", Mock(return_value=connection))
    monkeypatch.setattr("app.main.initialize_collections", AsyncMock())
    monkeypatch.setattr("app.main.initialize_indexes", AsyncMock())

    response = await request_health(create_app(settings_provider=lambda: config))

    assert response.status_code == 503
    assert response.json()["database"]["status"] == "disconnected"
    connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_detects_database_becoming_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    config = settings("mongodb://user:private-password@localhost:27017")
    connection = FakeConnection(config)
    connection.check_connection = AsyncMock(return_value=False)
    monkeypatch.setattr("app.main.MongoConnection", Mock(return_value=connection))
    monkeypatch.setattr("app.main.initialize_collections", AsyncMock())
    monkeypatch.setattr("app.main.initialize_indexes", AsyncMock())

    response = await request_health(create_app(settings_provider=lambda: config))

    assert response.status_code == 503
    assert response.json()["database"]["status"] == "disconnected"
    connection.check_connection.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_uri_is_never_returned_by_health(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_uri = "mongodb+srv://private-user:private-password@cluster.example.mongodb.net/db"
    config = settings(secret_uri)
    connection = FakeConnection(config, error=RuntimeError(secret_uri))
    monkeypatch.setattr("app.main.MongoConnection", Mock(return_value=connection))
    monkeypatch.setattr("app.main.initialize_collections", AsyncMock())
    monkeypatch.setattr("app.main.initialize_indexes", AsyncMock())

    response = await request_health(create_app(settings_provider=lambda: config))

    assert secret_uri not in response.text
    assert "private-password" not in response.text


@pytest.mark.asyncio
async def test_mongo_connection_pings_and_selects_configured_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = settings("mongodb://localhost:27017", name="selected_db")
    database = Mock(name="selected_database")
    client = Mock()
    client.admin.command = AsyncMock(return_value={"ok": 1})
    client.get_database.return_value = database
    client.close = AsyncMock()
    client_factory = Mock(return_value=client)
    monkeypatch.setattr(connection_module, "AsyncMongoClient", client_factory)
    manager = MongoConnection(config)

    await manager.connect()

    client_factory.assert_called_once_with(
        config.mongodb_uri,
        serverSelectionTimeoutMS=5_000,
        connectTimeoutMS=5_000,
        socketTimeoutMS=10_000,
    )
    client.admin.command.assert_awaited_once_with("ping")
    client.get_database.assert_called_once_with("selected_db")
    assert manager.is_connected is True
    assert manager.database is database

    await manager.close()
    client.close.assert_awaited_once()
    assert manager.is_connected is False
    assert manager.database is None


@pytest.mark.asyncio
async def test_ping_failure_closes_client_and_does_not_mark_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock()
    client.admin.command = AsyncMock(side_effect=ServerSelectionTimeoutError("unavailable"))
    client.close = AsyncMock()
    monkeypatch.setattr(connection_module, "AsyncMongoClient", Mock(return_value=client))
    manager = MongoConnection(settings("mongodb://localhost:27017"))

    with pytest.raises(ServerSelectionTimeoutError):
        await manager.connect()

    client.close.assert_awaited_once()
    assert manager.is_connected is False
    assert manager.database is None


class FakeCollectionsDatabase:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.created: list[str] = []

    async def list_collection_names(self) -> list[str]:
        return list(self.existing)

    async def create_collection(self, name: str) -> None:
        self.created.append(name)
        self.existing.add(name)


@pytest.mark.asyncio
async def test_collection_initialization_is_idempotent() -> None:
    database = FakeCollectionsDatabase(existing={"photos"})

    await initialize_collections(database)  # type: ignore[arg-type]
    await initialize_collections(database)  # type: ignore[arg-type]

    assert set(database.created) == set(COLLECTION_NAMES) - {"photos"}
    assert len(database.created) == len(COLLECTION_NAMES) - 1
