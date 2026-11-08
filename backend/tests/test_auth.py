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
from app.main import create_app
from app.services.admin_service import (
    AdministratorAlreadyExistsError,
    create_single_administrator,
)
from app.utils.passwords import hash_password

JWT_SECRET = "this-is-a-test-only-secret-with-at-least-32-bytes"
OWNER_PASSWORD = "Correct Horse Battery Staple 42!"


def make_settings(secret: str = JWT_SECRET) -> Settings:
    return Settings(
        mongodb_uri="mongodb://mocked.invalid",
        mongodb_database="test_wedding_memories",
        jwt_secret=secret,
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
        frontend_origins="http://localhost:5173",
    )


def make_admin(*, active: bool = True, token_version: int = 0) -> dict:
    return {
        "_id": ObjectId(),
        "email": "owner@example.com",
        "password_hash": hash_password(OWNER_PASSWORD),
        "account_slot": "owner",
        "is_active": active,
        "token_version": token_version,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "last_login_at": None,
    }


class FakeAdminCollection:
    def __init__(self, documents: list[dict] | None = None) -> None:
        self.documents = documents or []

    async def find_one(self, query: dict) -> dict | None:
        for document in self.documents:
            if all(document.get(key) == value for key, value in query.items()):
                return document
        return None

    async def count_documents(self, query: dict, limit: int = 0) -> int:
        count = sum(all(document.get(key) == value for key, value in query.items()) for document in self.documents)
        return min(count, limit) if limit else count

    async def insert_one(self, document: dict) -> SimpleNamespace:
        if any(
            existing.get("email") == document.get("email")
            or existing.get("account_slot") == document.get("account_slot")
            for existing in self.documents
        ):
            raise DuplicateKeyError("duplicate key")
        inserted = {"_id": ObjectId(), **document}
        self.documents.append(inserted)
        return SimpleNamespace(inserted_id=inserted["_id"])

    async def update_one(self, query: dict, update: dict) -> SimpleNamespace:
        document = await self.find_one(query)
        if document is None:
            return SimpleNamespace(modified_count=0)
        for key, value in update.get("$set", {}).items():
            document[key] = value
        for key, value in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + value
        return SimpleNamespace(modified_count=1)


class FakeDatabase:
    def __init__(self, administrators: FakeAdminCollection) -> None:
        self.administrators = administrators

    def __getitem__(self, name: str) -> FakeAdminCollection:
        assert name == "administrators"
        return self.administrators


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


def build_test_app(monkeypatch: pytest.MonkeyPatch, collection: FakeAdminCollection, secret: str = JWT_SECRET):
    config = make_settings(secret)
    database = FakeDatabase(collection)
    connection = FakeMongoConnection(config, database)
    monkeypatch.setattr("app.main.MongoConnection", Mock(return_value=connection))
    monkeypatch.setattr("app.main.initialize_collections", AsyncMock())
    monkeypatch.setattr("app.main.initialize_indexes", AsyncMock())
    return create_app(settings_provider=lambda: config), connection


@pytest.mark.asyncio
async def test_successful_login_normalizes_email_and_hides_private_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = make_admin()
    collection = FakeAdminCollection([admin])
    app, _ = build_test_app(monkeypatch, collection)

    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": " OWNER@EXAMPLE.COM ", "password": OWNER_PASSWORD},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["admin"] == {"email": "owner@example.com"}
    assert "password_hash" not in response.text
    assert str(admin["_id"]) not in response.text
    assert JWT_SECRET not in response.text
    assert isinstance(admin["last_login_at"], datetime)
    claims = jwt.decode(body["access_token"], JWT_SECRET, algorithms=["HS256"])
    assert claims["sub"] == str(admin["_id"])
    assert claims["token_version"] == 0
    assert claims["jti"]
    assert isinstance(claims["iat"], int) and isinstance(claims["exp"], int)


@pytest.mark.asyncio
async def test_incorrect_password_and_unknown_email_use_same_error(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([make_admin()]))

    async with api_client(app) as client:
        wrong_password = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "not-the-password"},
        )
        unknown_email = await client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "not-the-password"},
        )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Invalid email or password"}


@pytest.mark.asyncio
async def test_inactive_administrator_cannot_log_in(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([make_admin(active=False)]))

    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": OWNER_PASSWORD},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


@pytest.mark.asyncio
async def test_missing_invalid_and_expired_bearer_tokens_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = make_admin()
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([admin]))
    expired = jwt.encode(
        {
            "sub": str(admin["_id"]),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
            "iat": datetime.now(UTC) - timedelta(minutes=2),
            "jti": "expired-token",
            "token_version": 0,
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    async with api_client(app) as client:
        missing = await client.get("/api/v1/auth/me")
        invalid = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        expired_response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert [missing.status_code, invalid.status_code, expired_response.status_code] == [401, 401, 401]
    assert missing.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_valid_me_returns_only_public_administrator_information(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = make_admin()
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([admin]))
    token = jwt.encode(
        {
            "sub": str(admin["_id"]),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "jti": "valid-token",
            "token_version": 0,
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    async with api_client(app) as client:
        response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "admin": {"email": "owner@example.com"}}
    assert "password_hash" not in response.text
    assert str(admin["_id"]) not in response.text


@pytest.mark.asyncio
async def test_logout_increments_token_version_and_revokes_current_token(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = make_admin()
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([admin]))
    token = jwt.encode(
        {
            "sub": str(admin["_id"]),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "jti": "logout-token",
            "token_version": 0,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with api_client(app) as client:
        logout = await client.post("/api/v1/auth/logout", headers=headers)
        current = await client.get("/api/v1/auth/me", headers=headers)

    assert logout.status_code == 200
    assert admin["token_version"] == 1
    assert current.status_code == 401


@pytest.mark.asyncio
async def test_outdated_token_version_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = make_admin(token_version=2)
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([admin]))
    old_token = jwt.encode(
        {
            "sub": str(admin["_id"]),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "jti": "revoked-token",
            "token_version": 1,
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    async with api_client(app) as client:
        response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_inactive_administrator_token_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = make_admin(active=False)
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([admin]))
    token = jwt.encode(
        {
            "sub": str(admin["_id"]),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
            "jti": "inactive-token",
            "token_version": 0,
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    async with api_client(app) as client:
        response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_authentication_fails_closed_without_strong_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = build_test_app(monkeypatch, FakeAdminCollection([make_admin()]), secret="short")

    async with api_client(app) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": OWNER_PASSWORD},
        )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is not configured"}


@pytest.mark.asyncio
async def test_public_registration_endpoint_does_not_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _ = build_test_app(monkeypatch, FakeAdminCollection())

    async with api_client(app) as client:
        response = await client.post("/api/v1/auth/register", json={})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_creation_service_refuses_existing_administrator() -> None:
    collection = FakeAdminCollection([make_admin()])

    with pytest.raises(AdministratorAlreadyExistsError):
        await create_single_administrator(collection, email="another@example.com", password_hash="argon-hash")


@pytest.mark.asyncio
async def test_creation_service_handles_racing_duplicate_insert() -> None:
    class DuplicateOnInsert(FakeAdminCollection):
        async def count_documents(self, query: dict, limit: int = 0) -> int:
            return 0

    collection = DuplicateOnInsert([{"email": "race@example.com", "account_slot": "owner"}])

    with pytest.raises(AdministratorAlreadyExistsError):
        await create_single_administrator(collection, email="owner@example.com", password_hash="argon-hash")


@pytest.mark.asyncio
async def test_cli_refuses_a_second_administrator_before_prompting(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from app.utils import create_admin

    admin = make_admin()
    collection = FakeAdminCollection([admin])
    database = FakeDatabase(collection)
    connection = FakeMongoConnection(make_settings(), database)
    monkeypatch.setattr(create_admin, "get_settings", make_settings)
    monkeypatch.setattr(create_admin, "MongoConnection", Mock(return_value=connection))
    monkeypatch.setattr(create_admin, "get_database", lambda _: database)
    monkeypatch.setattr(create_admin, "initialize_collections", AsyncMock())
    monkeypatch.setattr(create_admin, "initialize_indexes", AsyncMock())
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("CLI must refuse before prompting"))
    monkeypatch.setattr(create_admin, "getpass", lambda *_: pytest.fail("CLI must refuse before prompting"))

    result = await create_admin.create_admin_interactive()

    assert result == 1
    assert "single administrator already exists" in capsys.readouterr().out
    connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cli_creates_one_argon2_hashed_administrator(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    from app.utils import create_admin

    collection = FakeAdminCollection()
    database = FakeDatabase(collection)
    connection = FakeMongoConnection(make_settings(), database)
    monkeypatch.setattr(create_admin, "get_settings", make_settings)
    monkeypatch.setattr(create_admin, "MongoConnection", Mock(return_value=connection))
    monkeypatch.setattr(create_admin, "get_database", lambda _: database)
    monkeypatch.setattr(create_admin, "initialize_collections", AsyncMock())
    monkeypatch.setattr(create_admin, "initialize_indexes", AsyncMock())
    monkeypatch.setattr("builtins.input", lambda *_: "OWNER@EXAMPLE.COM")
    prompts = iter([OWNER_PASSWORD, OWNER_PASSWORD])
    monkeypatch.setattr(create_admin, "getpass", lambda *_: next(prompts))

    result = await create_admin.create_admin_interactive()

    assert result == 0
    assert len(collection.documents) == 1
    created = collection.documents[0]
    assert created["email"] == "owner@example.com"
    assert created["account_slot"] == "owner"
    assert created["is_active"] is True
    assert created["token_version"] == 0
    assert created["last_login_at"] is None
    assert created["password_hash"] != OWNER_PASSWORD
    assert created["password_hash"].startswith("$argon2id$")
    assert created["created_at"].tzinfo is not None
    assert OWNER_PASSWORD not in capsys.readouterr().out
    connection.close.assert_awaited_once()
