import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import jwt
import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.database.indexes import initialize_indexes
from app.main import create_app
from app.utils.passwords import hash_password

JWT_SECRET = "phase-four-test-secret-that-has-more-than-thirty-two-bytes"


def settings() -> Settings:
    return Settings(
        mongodb_uri="mongodb://mocked.invalid",
        mongodb_database="test_wedding_memories",
        jwt_secret=JWT_SECRET,
        frontend_origins="http://localhost:5173",
        photo_storage_provider="local",
    )


def matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(matches(document, clause) for clause in expected):
                return False
            continue
        actual = document.get(key)
        if isinstance(expected, dict) and "$regex" in expected:
            if re.search(expected["$regex"], actual or "", re.IGNORECASE if expected.get("$options") == "i" else 0) is None:
                return False
        elif isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif isinstance(expected, dict) and "$lte" in expected:
            if actual is None or actual > expected["$lte"]:
                return False
        elif isinstance(expected, dict) and "$gt" in expected:
            if actual is None or actual <= expected["$gt"]:
                return False
        elif isinstance(expected, dict) and "$lt" in expected:
            if actual is None or actual >= expected["$lt"]:
                return False
        elif isinstance(expected, dict) and "$ne" in expected:
            if actual == expected["$ne"]:
                return False
        elif isinstance(expected, dict) and "$exists" in expected:
            if (key in document) != expected["$exists"]:
                return False
        elif actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = list(documents)

    def sort(self, ordering, direction=None):
        keys = [(ordering, direction)] if isinstance(ordering, str) else ordering
        for key, sort_direction in reversed(keys):
            self.documents.sort(
                key=lambda document: (document.get(key) is None, document.get(key)),
                reverse=sort_direction < 0,
            )
        return self

    def skip(self, amount: int):
        self.documents = self.documents[amount:]
        return self

    def limit(self, amount: int):
        self.documents = self.documents[:amount]
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        return self.documents[:length] if length is not None else self.documents


class FakeCollection:
    def __init__(self, name: str, documents: list[dict] | None = None) -> None:
        self.name = name
        self.documents = documents or []

    async def find_one(self, query: dict) -> dict | None:
        return next((document for document in self.documents if matches(document, query)), None)

    def find(self, query: dict) -> FakeCursor:
        return FakeCursor([document for document in self.documents if matches(document, query)])

    async def count_documents(self, query: dict, limit: int = 0) -> int:
        count = sum(matches(document, query) for document in self.documents)
        return min(count, limit) if limit else count

    async def insert_one(self, document: dict) -> SimpleNamespace:
        if self.name == "photo_albums" and any(item.get("slug") == document.get("slug") for item in self.documents):
            raise DuplicateKeyError("duplicate album slug")
        if self.name == "photo_events" and any(
            item.get("album_id") == document.get("album_id") and item.get("slug") == document.get("slug")
            for item in self.documents
        ):
            raise DuplicateKeyError("duplicate event slug in album")
        inserted = {"_id": ObjectId(), **document}
        self.documents.append(inserted)
        return SimpleNamespace(inserted_id=inserted["_id"])

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> SimpleNamespace:
        document = await self.find_one(query)
        if document is None:
            if upsert:
                inserted = dict(query)
                inserted.update(update.get("$setOnInsert", {}))
                inserted.update(update.get("$set", {}))
                inserted["_id"] = ObjectId()
                self.documents.append(inserted)
                return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=inserted["_id"])
            return SimpleNamespace(matched_count=0, modified_count=0)
        for key, value in update.get("$set", {}).items():
            document[key] = value
        for key in update.get("$unset", {}):
            document.pop(key, None)
        return SimpleNamespace(matched_count=1, modified_count=1)

    async def find_one_and_update(self, query: dict, update: dict, return_document=None):
        document = await self.find_one(query)
        if document is None:
            return None
        for key, value in update.get("$set", {}).items():
            document[key] = value
        for key in update.get("$unset", {}):
            document.pop(key, None)
        return document

    async def delete_one(self, query: dict) -> SimpleNamespace:
        document = await self.find_one(query)
        if document is None:
            return SimpleNamespace(deleted_count=0)
        self.documents.remove(document)
        return SimpleNamespace(deleted_count=1)

    async def delete_many(self, query: dict) -> SimpleNamespace:
        matching = [document for document in self.documents if matches(document, query)]
        for document in matching:
            self.documents.remove(document)
        return SimpleNamespace(deleted_count=len(matching))

    async def find_one_and_delete(self, query: dict) -> dict | None:
        document = await self.find_one(query)
        if document is not None:
            self.documents.remove(document)
        return document


class FakeDatabase:
    def __init__(self) -> None:
        self.collections = {
            "administrators": FakeCollection(
                "administrators",
                [{
                    "_id": ObjectId(),
                    "email": "owner@example.com",
                    "password_hash": hash_password("test admin password"),
                    "is_active": True,
                    "token_version": 0,
                }],
            ),
            "photo_albums": FakeCollection("photo_albums"),
            "photo_events": FakeCollection("photo_events"),
            "photos": FakeCollection("photos"),
            "photo_contributors": FakeCollection("photo_contributors"),
            "photo_settings": FakeCollection("photo_settings"),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


class FakeMongoConnection:
    def __init__(self, config: Settings, database: FakeDatabase) -> None:
        self.config = config
        self.database = database
        self.client = object()
        self.is_connected = True
        self.close = AsyncMock()

    async def connect(self) -> None:
        return None

    async def check_connection(self) -> bool:
        return True


@asynccontextmanager
async def api_client(app):
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def make_app(monkeypatch: pytest.MonkeyPatch):
    config = settings()
    database = FakeDatabase()
    connection = FakeMongoConnection(config, database)
    monkeypatch.setattr("app.main.MongoConnection", Mock(return_value=connection))
    monkeypatch.setattr("app.main.initialize_collections", AsyncMock())
    monkeypatch.setattr("app.main.initialize_indexes", AsyncMock())
    app = create_app(settings_provider=lambda: config)
    admin = database["administrators"].documents[0]
    token = jwt.encode(
        {
            "sub": str(admin["_id"]),
            "exp": datetime.now(UTC) + timedelta(minutes=10),
            "iat": datetime.now(UTC),
            "jti": "albums-test-token",
            "token_version": 0,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return app, database, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_album_create_list_retrieve_update_and_slug_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    app, database, headers = make_app(monkeypatch)
    payload = {
        "name": "  Sharma Wedding 2026  ",
        "couple_names": "Anika & Rohan",
        "description": "Family celebration",
        "event_date": "2026-12-05",
        "location": "Jaipur",
    }

    async with api_client(app) as client:
        created = await client.post("/api/v1/albums", json=payload, headers=headers)
        listed = await client.get("/api/v1/albums?status=active&search=sharma", headers=headers)
        retrieved = await client.get(f"/api/v1/albums/{created.json()['id']}", headers=headers)
        updated = await client.patch(
            f"/api/v1/albums/{created.json()['id']}",
            json={"description": "Updated celebration", "location": "Udaipur"},
            headers=headers,
        )
        duplicate = await client.post(
            "/api/v1/albums", json={"name": "Another", "slug": "sharma-wedding-2026"}, headers=headers
        )

    assert created.status_code == 201
    album = created.json()
    assert album["slug"] == "sharma-wedding-2026"
    assert album["name"] == "Sharma Wedding 2026"
    assert album["event_date"] == "2026-12-05"
    assert album["status"] == "active"
    assert album["event_count"] == 0
    assert "_id" not in album
    assert listed.status_code == 200 and listed.json()["total"] == 1
    assert listed.json()["items"][0]["couple_names"] == "Anika & Rohan"
    assert retrieved.status_code == 200
    assert updated.json()["slug"] == album["slug"]
    assert updated.json()["description"] == "Updated celebration"
    assert duplicate.status_code == 409
    stored = database["photo_albums"].documents[0]
    assert stored["created_at"].tzinfo is not None
    assert stored["updated_at"].tzinfo is not None


@pytest.mark.asyncio
async def test_album_archive_restore_and_delete_safety(monkeypatch: pytest.MonkeyPatch) -> None:
    app, database, headers = make_app(monkeypatch)
    async with api_client(app) as client:
        created = await client.post("/api/v1/albums", json={"name": "Archive This"}, headers=headers)
        album_id = created.json()["id"]
        archived = await client.patch(f"/api/v1/albums/{album_id}/archive", headers=headers)
        filtered = await client.get("/api/v1/albums?status=active", headers=headers)
        restored = await client.patch(f"/api/v1/albums/{album_id}/restore", headers=headers)
        child_event = await client.post(
            f"/api/v1/albums/{album_id}/events", json={"name": "Ceremony"}, headers=headers
        )
        blocked_delete = await client.delete(f"/api/v1/albums/{album_id}", headers=headers)
        no_dependency = await client.post("/api/v1/albums", json={"name": "Empty Album"}, headers=headers)
        deleted = await client.delete(f"/api/v1/albums/{no_dependency.json()['id']}", headers=headers)

    assert archived.json()["status"] == "archived"
    assert filtered.json()["total"] == 0
    assert restored.json()["status"] == "active"
    assert child_event.status_code == 201
    assert blocked_delete.status_code == 409
    assert len(database["photo_events"].documents) == 1
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_album_deletion_is_blocked_by_photos(monkeypatch: pytest.MonkeyPatch) -> None:
    app, database, headers = make_app(monkeypatch)
    async with api_client(app) as client:
        created = await client.post("/api/v1/albums", json={"name": "Album with photos"}, headers=headers)
        album_id = ObjectId(created.json()["id"])
        database["photos"].documents.append({"_id": ObjectId(), "album_id": album_id})
        response = await client.delete(f"/api/v1/albums/{album_id}", headers=headers)

    assert response.status_code == 409
    assert "photos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_event_relationship_slug_scope_and_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    app, database, headers = make_app(monkeypatch)
    async with api_client(app) as client:
        album_a = await client.post("/api/v1/albums", json={"name": "Wedding A"}, headers=headers)
        album_b = await client.post("/api/v1/albums", json={"name": "Wedding B"}, headers=headers)
        album_a_id = album_a.json()["id"]
        album_b_id = album_b.json()["id"]
        event = await client.post(
            f"/api/v1/albums/{album_a_id}/events",
            json={"name": "Mehendi", "event_date": "2026-10-30T18:15:00+05:30", "display_order": 2},
            headers=headers,
        )
        same_album_duplicate = await client.post(
            f"/api/v1/albums/{album_a_id}/events", json={"name": "Duplicate", "slug": "mehendi"}, headers=headers
        )
        other_album_same_slug = await client.post(
            f"/api/v1/albums/{album_b_id}/events", json={"name": "Mehendi"}, headers=headers
        )
        listed = await client.get(f"/api/v1/albums/{album_a_id}/events", headers=headers)
        retrieved = await client.get(f"/api/v1/albums/{album_a_id}/events/{event.json()['id']}", headers=headers)
        updated = await client.patch(
            f"/api/v1/albums/{album_a_id}/events/{event.json()['id']}",
            json={"location": "Jaipur", "display_order": 5},
            headers=headers,
        )
        wrong_album_get = await client.get(f"/api/v1/albums/{album_b_id}/events/{event.json()['id']}", headers=headers)
        wrong_album_patch = await client.patch(
            f"/api/v1/albums/{album_b_id}/events/{event.json()['id']}", json={"name": "Hacked"}, headers=headers
        )
        archived = await client.patch(
            f"/api/v1/albums/{album_a_id}/events/{event.json()['id']}/archive", headers=headers
        )
        restored = await client.patch(
            f"/api/v1/albums/{album_a_id}/events/{event.json()['id']}/restore", headers=headers
        )

    assert event.status_code == 201
    event_doc = event.json()
    assert event_doc["album_id"] == album_a_id
    assert event_doc["slug"] == "mehendi"
    assert event_doc["event_date"].endswith("12:45:00Z")
    assert event_doc["display_order"] == 2
    assert same_album_duplicate.status_code == 409
    assert other_album_same_slug.status_code == 201
    assert other_album_same_slug.json()["slug"] == "mehendi"
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == event_doc["id"]
    assert retrieved.status_code == 200
    assert updated.json()["location"] == "Jaipur"
    assert updated.json()["display_order"] == 5
    assert wrong_album_get.status_code == wrong_album_patch.status_code == 404
    assert archived.json()["status"] == "archived"
    assert restored.json()["status"] == "active"
    assert all(item["album_id"] in {ObjectId(album_a_id), ObjectId(album_b_id)} for item in database["photo_events"].documents)


@pytest.mark.asyncio
async def test_event_parent_missing_archived_restore_and_safe_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    app, database, headers = make_app(monkeypatch)
    missing_album_id = str(ObjectId())
    async with api_client(app) as client:
        missing_parent = await client.post(
            f"/api/v1/albums/{missing_album_id}/events", json={"name": "Orphan"}, headers=headers
        )
        album = await client.post("/api/v1/albums", json={"name": "Events"}, headers=headers)
        album_id = album.json()["id"]
        event = await client.post(f"/api/v1/albums/{album_id}/events", json={"name": "Haldi"}, headers=headers)
        event_id = event.json()["id"]
        album_archive = await client.patch(f"/api/v1/albums/{album_id}/archive", headers=headers)
        forbidden_restore = await client.patch(
            f"/api/v1/albums/{album_id}/events/{event_id}/restore", headers=headers
        )
        album_restore = await client.patch(f"/api/v1/albums/{album_id}/restore", headers=headers)
        database["photos"].documents.append(
            {"_id": ObjectId(), "album_id": ObjectId(album_id), "event_id": ObjectId(event_id)}
        )
        blocked_event_delete = await client.delete(
            f"/api/v1/albums/{album_id}/events/{event_id}", headers=headers
        )
        database["photos"].documents.clear()
        allowed_event_delete = await client.delete(f"/api/v1/albums/{album_id}/events/{event_id}", headers=headers)

    assert missing_parent.status_code == 404
    assert album_archive.json()["status"] == "archived"
    assert forbidden_restore.status_code == 400
    assert album_restore.json()["status"] == "active"
    assert blocked_event_delete.status_code == 409
    assert allowed_event_delete.status_code == 204
    assert not database["photo_events"].documents


@pytest.mark.asyncio
async def test_invalid_ids_and_unauthorized_album_event_access(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _, headers = make_app(monkeypatch)
    async with api_client(app) as client:
        unauthorized_album = await client.get("/api/v1/albums")
        unauthorized_event = await client.get(f"/api/v1/albums/{ObjectId()}/events")
        invalid_album_id = await client.get("/api/v1/albums/not-an-object-id", headers=headers)
        invalid_event_id = await client.get(
            f"/api/v1/albums/{ObjectId()}/events/not-an-object-id", headers=headers
        )
        invalid_slug = await client.post("/api/v1/albums", json={"name": "Test", "slug": "not/a/slug"}, headers=headers)

    assert unauthorized_album.status_code == unauthorized_event.status_code == 401
    assert invalid_album_id.status_code == invalid_event_id.status_code == 400
    assert invalid_slug.status_code == 422


@pytest.mark.asyncio
async def test_management_indexes_keep_slug_uniqueness_scoped_to_parent() -> None:
    class IndexCollection:
        def __init__(self) -> None:
            self.calls: list[tuple[list[tuple[str, int]], dict]] = []

        async def create_index(self, keys, **options):
            self.calls.append((keys, options))

    class IndexDatabase:
        def __init__(self) -> None:
            self.collections = {name: IndexCollection() for name in ("administrators", "photo_albums", "photo_events", "photos", "photo_contributors", "photo_settings")}

        def __getitem__(self, name: str) -> IndexCollection:
            return self.collections[name]

    database = IndexDatabase()
    await initialize_indexes(database)  # type: ignore[arg-type]

    album_indexes = database["photo_albums"].calls
    event_indexes = database["photo_events"].calls
    admin_indexes = database["administrators"].calls
    assert any(keys == [("slug", 1)] and options.get("unique") for keys, options in album_indexes)
    assert any(
        keys == [("album_id", 1), ("slug", 1)]
        and options.get("unique")
        and options.get("name") == "uq_photo_events_album_slug"
        for keys, options in event_indexes
    )
    assert not any(keys == [("slug", 1)] and options.get("unique") for keys, options in event_indexes)
    assert any(keys == [("account_slot", 1)] and options.get("unique") for keys, options in admin_indexes)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        (
            "PATCH",
            "/api/v1/albums/aaaaaaaaaaaaaaaaaaaaaaaa/events/bbbbbbbbbbbbbbbbbbbbbbbb/archive",
        ),
        (
            "DELETE",
            "/api/v1/albums/aaaaaaaaaaaaaaaaaaaaaaaa/events/bbbbbbbbbbbbbbbbbbbbbbbb",
        ),
    ],
)
async def test_album_event_cors_preflight_allows_authenticated_admin_methods(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    app, _, _ = make_app(monkeypatch)
    preflight_headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "authorization,content-type",
    }

    async with api_client(app) as client:
        response = await client.options(path, headers=preflight_headers)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    allowed_methods = {item.strip().upper() for item in response.headers["access-control-allow-methods"].split(",")}
    assert method in allowed_methods
    allowed_headers = {item.strip().lower() for item in response.headers["access-control-allow-headers"].split(",")}
    assert {"authorization", "content-type"}.issubset(allowed_headers)
    assert response.headers["access-control-allow-credentials"] == "true"
