import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from io import BytesIO
from PIL import Image
from bson import ObjectId
from unittest.mock import AsyncMock
from pydantic import ValidationError

from app.core.config import Settings
from app.services.token_encryption import TokenEncryptionError, decrypt_tokens, encrypt_tokens
from app.storage.base import StoredContent, StoredObject
from app.storage.google_drive import (
    DRIVE_API,
    DRIVE_UPLOAD_API,
    FOLDER_MIME,
    DriveFileNotFound,
    DriveNotConnected,
    GoogleDriveStorage,
)
from test_albums import FakeDatabase, FakeMongoConnection, api_client, make_app, settings


def drive_settings(*, current_key: str | None = None, previous_key: str = "", folder_id: str = "root-folder") -> Settings:
    return Settings(
        mongodb_uri="mongodb://mocked.invalid", mongodb_database="test_wedding_memories",
        jwt_secret="phase-four-test-secret-that-has-more-than-thirty-two-bytes",
        frontend_origins="http://localhost:5173", photo_storage_provider="local",
        google_drive_client_id="client-id.apps.googleusercontent.com",
        google_drive_client_secret="test-client-secret",
        google_drive_redirect_uri="http://localhost:8011/api/v1/integrations/google-drive/callback",
        google_drive_token_encryption_key=current_key or Fernet.generate_key().decode(),
        google_drive_token_encryption_key_previous=previous_key,
        google_drive_folder_id=folder_id,
    )


def install_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr("app.storage.google_drive.httpx.AsyncClient", lambda *args, **kwargs: original(*args, transport=transport, **kwargs))
    return transport


@pytest.mark.asyncio
async def test_oauth_state_is_bound_single_use_and_expires(monkeypatch):
    app, database, admin_headers = make_app(monkeypatch)
    config = drive_settings()
    async with api_client(app) as client:
        app.state.settings = config
        app.state.google_drive_storage = GoogleDriveStorage(config, app.state.mongo_connection)
        unauthorized = await client.post("/api/v1/integrations/google-drive/connect")
        response = await client.post("/api/v1/integrations/google-drive/connect", headers=admin_headers)
        authorization_url = response.json()["authorization_url"]
        query = parse_qs(urlparse(authorization_url).query)
        state = query["state"][0]
        transaction = database["photo_settings"].documents[0]
        transaction["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
        expired = await client.get(f"/api/v1/integrations/google-drive/callback?state={state}&error=access_denied")
        replay = await client.get(f"/api/v1/integrations/google-drive/callback?state={state}&error=access_denied")

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert query["scope"] == ["https://www.googleapis.com/auth/drive.file"]
    assert query["access_type"] == ["offline"]
    assert len(state) >= 32 and state not in json.dumps(transaction, default=str)
    assert transaction["administrator_id"] == database["administrators"].documents[0]["_id"]
    assert expired.status_code == 303 and "drive=invalid_state" in expired.headers["location"]
    assert replay.status_code == 303 and "drive=invalid_state" in replay.headers["location"]
    assert not database["photo_settings"].documents


@pytest.mark.asyncio
async def test_oauth_callback_consumes_valid_state_and_rejects_replay(monkeypatch):
    app, database, admin_headers = make_app(monkeypatch)
    config = drive_settings()
    async with api_client(app) as client:
        app.state.settings = config
        app.state.google_drive_storage = GoogleDriveStorage(config, app.state.mongo_connection)
        response = await client.post("/api/v1/integrations/google-drive/connect", headers=admin_headers)
        state = parse_qs(urlparse(response.json()["authorization_url"]).query)["state"][0]
        transaction = database["photo_settings"].documents[0]
        transaction["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
        callback = await client.get(f"/api/v1/integrations/google-drive/callback?state={state}&code=fake")
        assert callback.status_code == 303
        assert "drive=invalid_state" in callback.headers["location"]
        assert await database["photo_settings"].find_one({"key": transaction["key"]}) is None


@pytest.mark.asyncio
async def test_oauth_callback_exchanges_code_saves_encrypted_tokens_and_does_not_replay(monkeypatch):
    app, database, admin_headers = make_app(monkeypatch)
    config = drive_settings()
    async with api_client(app) as client:
        app.state.settings = config
        app.state.google_drive_storage = GoogleDriveStorage(config, app.state.mongo_connection)

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "oauth2.googleapis.com":
                return httpx.Response(200, json={"access_token": "secret-access-token", "refresh_token": "secret-refresh-token", "expires_in": 3600}, request=request)
            if request.url.path == "/drive/v3/about":
                return httpx.Response(200, json={"user": {"emailAddress": "owner@gmail.com"}}, request=request)
            if request.url.path == "/drive/v3/files/root-folder":
                return httpx.Response(200, json={"id": "root-folder", "mimeType": FOLDER_MIME, "trashed": False, "capabilities": {"canAddChildren": True}}, request=request)
            return httpx.Response(404, request=request)

        install_transport(monkeypatch, handler)
        connect = await client.post("/api/v1/integrations/google-drive/connect", headers=admin_headers)
        state = parse_qs(urlparse(connect.json()["authorization_url"]).query)["state"][0]
        callback = await client.get(f"/api/v1/integrations/google-drive/callback?state={state}&code=authorization-code")
        replay = await client.get(f"/api/v1/integrations/google-drive/callback?state={state}&code=authorization-code")
        status = await client.get("/api/v1/admin/storage/status", headers=admin_headers)

    saved = await database["photo_settings"].find_one({"key": "google_drive_credentials"})
    decrypted = decrypt_tokens(config, saved["encrypted_tokens"])
    assert callback.status_code == 303 and "drive=connected" in callback.headers["location"]
    assert replay.status_code == 303 and "drive=invalid_state" in replay.headers["location"]
    assert decrypted["refresh_token"] == "secret-refresh-token"
    assert "secret-access-token" not in saved["encrypted_tokens"]
    assert "secret-refresh-token" not in saved["encrypted_tokens"]
    assert status.status_code == 200 and status.json()["google_drive"]["connected_email"] == "owner@gmail.com"
    assert "secret-access-token" not in status.text and "secret-refresh-token" not in status.text


def test_token_encryption_rejects_missing_and_wrong_keys_and_supports_rotation():
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    old_settings = drive_settings(current_key=old_key)
    ciphertext = encrypt_tokens(old_settings, {"access_token": "access-secret", "refresh_token": "refresh-secret"})
    rotated_settings = drive_settings(current_key=new_key, previous_key=old_key)
    assert decrypt_tokens(rotated_settings, ciphertext)["refresh_token"] == "refresh-secret"
    with pytest.raises(TokenEncryptionError):
        decrypt_tokens(drive_settings(current_key=new_key), ciphertext)
    with pytest.raises(TokenEncryptionError):
        encrypt_tokens(Settings(google_drive_token_encryption_key=""), {"access_token": "x"})


def test_google_oauth_redirect_requires_https_except_for_loopback():
    with pytest.raises(ValidationError):
        Settings(google_drive_redirect_uri="http://example.com/api/v1/integrations/google-drive/callback")
    assert Settings(google_drive_redirect_uri="http://localhost:8011/api/v1/integrations/google-drive/callback")


@pytest.mark.asyncio
async def test_refresh_token_is_preserved_and_previous_encryption_key_is_rotated():
    database = FakeDatabase()
    connection = FakeMongoConnection(settings(), database)
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    old_settings = drive_settings(current_key=old_key)
    old_storage = GoogleDriveStorage(old_settings, connection)
    await old_storage.save_tokens({"access_token": "old-access", "refresh_token": "stable-refresh", "expires_at": int(time.time()) + 3600})
    document = await database["photo_settings"].find_one({"key": "google_drive_credentials"})
    original_ciphertext = document["encrypted_tokens"]

    rotated = GoogleDriveStorage(drive_settings(current_key=new_key, previous_key=old_key), connection)
    tokens, _ = await rotated._load_tokens()
    await rotated.save_tokens({"access_token": "new-access", "expires_at": int(time.time()) + 3600})
    final = await database["photo_settings"].find_one({"key": "google_drive_credentials"})

    assert tokens["refresh_token"] == "stable-refresh"
    assert final["encrypted_tokens"] != original_ciphertext
    assert decrypt_tokens(rotated.settings, final["encrypted_tokens"])["refresh_token"] == "stable-refresh"


@pytest.mark.asyncio
async def test_drive_upload_is_resumable_idempotent_private_streamable_and_deletable(monkeypatch):
    database = FakeDatabase()
    config = drive_settings()
    storage = GoogleDriveStorage(config, FakeMongoConnection(settings(), database))
    await storage.save_tokens({"access_token": "private-access", "refresh_token": "private-refresh", "expires_at": int(time.time()) + 3600})
    file_payload = b"sanitized-test-image-bytes"
    remote: dict[str, dict] = {}
    starts: list[dict] = []
    deletes: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/drive/v3/files" and request.method == "GET":
            matches = [value for value in remote.values() if value["upload_id"] in request.url.params.get("q", "")]
            return httpx.Response(200, json={"files": [{"id": value["id"], "mimeType": value["mimeType"], "size": str(value["size"])} for value in matches[:1]]}, request=request)
        if path == "/drive/v3/files/root-folder" and request.method == "GET":
            return httpx.Response(200, json={"id": "root-folder", "mimeType": FOLDER_MIME, "trashed": False, "capabilities": {"canAddChildren": True}}, request=request)
        if path == "/upload/drive/v3/files" and request.method == "POST":
            metadata = json.loads(request.content)
            starts.append(metadata)
            return httpx.Response(200, headers={"location": "https://upload.test/session"}, request=request)
        if path == "/session" and request.method == "PUT":
            metadata = starts[-1]
            upload_id = metadata["appProperties"]["weddingUploadId"]
            uploaded = {"id": "drive-photo-1", "mimeType": metadata["mimeType"], "size": len(request.content), "upload_id": upload_id}
            remote[upload_id] = uploaded
            return httpx.Response(200, json={key: value for key, value in uploaded.items() if key != "upload_id"}, request=request)
        if path == "/drive/v3/files/drive-photo-1" and request.method == "GET" and request.url.params.get("alt") == "media":
            return httpx.Response(200, content=file_payload, headers={"content-type": "image/png", "content-length": str(len(file_payload))}, request=request)
        if path == "/drive/v3/files/drive-photo-1" and request.method == "GET":
            return httpx.Response(200, json={"id": "drive-photo-1", "name": "private-photo.png", "mimeType": "image/png", "size": str(len(file_payload))}, request=request)
        if path == "/drive/v3/files/drive-photo-1" and request.method == "DELETE":
            deletes.append("drive-photo-1")
            return httpx.Response(204, request=request)
        return httpx.Response(404, request=request)

    install_transport(monkeypatch, handler)
    first = await storage.upload(file_payload, "image/png", client_upload_id="e9074a93-316b-40cc-860d-b6968f8fe087", album_slug="album", event_slug="event")
    second = await storage.upload(file_payload, "image/png", client_upload_id="e9074a93-316b-40cc-860d-b6968f8fe087", album_slug="album", event_slug="event")
    content = await storage.open_read(first.file_id)
    downloaded = b"".join([chunk async for chunk in content.chunks])
    metadata = await storage.get_metadata(first.file_id)
    await storage.delete(first.file_id)

    assert first.provider == "google_drive" and first.file_id == "drive-photo-1"
    assert second.file_id == first.file_id
    assert len(starts) == 1
    assert starts[0]["parents"] == ["root-folder"]
    assert starts[0]["appProperties"]["eventSlug"] == "event"
    assert "permissions" not in starts[0]
    assert downloaded == file_payload and content.mime_type == "image/png"
    assert metadata["id"] == first.file_id
    assert deletes == [first.file_id]


@pytest.mark.asyncio
async def test_drive_missing_file_and_bounded_get_retry(monkeypatch):
    database = FakeDatabase()
    storage = GoogleDriveStorage(drive_settings(), FakeMongoConnection(settings(), database))
    await storage.save_tokens({"access_token": "access", "refresh_token": "refresh", "expires_at": int(time.time()) + 3600})
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.path.endswith("/retry"):
            calls += 1
            return httpx.Response(503 if calls == 1 else 200, json={"id": "retry"}, request=request)
        if request.url.path.endswith("/missing"):
            return httpx.Response(404, request=request)
        return httpx.Response(404, request=request)

    install_transport(monkeypatch, handler)
    retried = await storage.get_metadata("retry")
    missing = await storage.get_metadata("missing")
    await storage.delete("missing")
    with pytest.raises(FileNotFoundError):
        await storage.open_read("missing")

    assert calls == 2 and retried["id"] == "retry"
    assert missing is None


@pytest.mark.asyncio
async def test_drive_refresh_uses_preserved_refresh_token(monkeypatch):
    database = FakeDatabase()
    storage = GoogleDriveStorage(drive_settings(), FakeMongoConnection(settings(), database))
    await storage.save_tokens({"access_token": "expired-access", "refresh_token": "stable-refresh", "expires_at": 0})
    seen_refresh_tokens: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            seen_refresh_tokens.append(request.content.decode())
            return httpx.Response(200, json={"access_token": "fresh-access", "expires_in": 3600, "token_type": "Bearer"}, request=request)
        return httpx.Response(200, json={"id": "ok"}, request=request)

    install_transport(monkeypatch, handler)
    metadata = await storage.get_metadata("ok")
    saved = await database["photo_settings"].find_one({"key": "google_drive_credentials"})
    tokens = decrypt_tokens(storage.settings, saved["encrypted_tokens"])

    assert metadata["id"] == "ok"
    assert "stable-refresh" in seen_refresh_tokens[0]
    assert tokens["access_token"] == "fresh-access"
    assert tokens["refresh_token"] == "stable-refresh"


@pytest.mark.asyncio
async def test_invalid_drive_refresh_token_requires_reconnection_without_logging_tokens(monkeypatch, caplog):
    database = FakeDatabase()
    storage = GoogleDriveStorage(drive_settings(), FakeMongoConnection(settings(), database))
    await storage.save_tokens({"access_token": "expired-access", "refresh_token": "sensitive-refresh", "expires_at": 0})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"}, request=request)

    install_transport(monkeypatch, handler)
    with pytest.raises(DriveNotConnected):
        await storage.get_metadata("photo-id")
    stored = await database["photo_settings"].find_one({"key": "google_drive_credentials"})
    assert decrypt_tokens(storage.settings, stored["encrypted_tokens"])["refresh_token"] == "sensitive-refresh"
    assert "sensitive-refresh" not in caplog.text
    assert "expired-access" not in caplog.text


@pytest.mark.asyncio
async def test_admin_disconnect_clears_drive_credentials_and_selects_local(monkeypatch):
    app, database, admin_headers = make_app(monkeypatch)
    database["photo_settings"].documents.extend([
        {"_id": __import__("bson").ObjectId(), "key": "google_drive_credentials", "encrypted_tokens": "ciphertext"},
        {"_id": __import__("bson").ObjectId(), "key": "storage_provider", "value": "google_drive"},
        {"_id": __import__("bson").ObjectId(), "purpose": "google_drive_oauth_state"},
    ])
    async with api_client(app) as client:
        unauthorized = await client.post("/api/v1/integrations/google-drive/disconnect")
        result = await client.post("/api/v1/integrations/google-drive/disconnect", headers=admin_headers)

    assert unauthorized.status_code == 401
    assert result.status_code == 200 and result.json() == {"disconnected": True, "provider": "local"}
    assert await database["photo_settings"].find_one({"key": "google_drive_credentials"}) is None
    assert await database["photo_settings"].find_one({"purpose": "google_drive_oauth_state"}) is None
    selected = await database["photo_settings"].find_one({"key": "storage_provider"})
    assert selected["value"] == "local"


@pytest.mark.asyncio
async def test_selected_drive_provider_fails_without_fallback_to_local(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    config = drive_settings()
    async with api_client(app) as client:
        app.state.settings = config
        app.state.local_photo_storage.root = tmp_path
        app.state.google_drive_storage = GoogleDriveStorage(config, app.state.mongo_connection)
        album = (await client.post("/api/v1/albums", json={"name": "Drive Failure Test"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Ceremony"}, headers=admin_headers)).json()
        database["photo_settings"].documents.append({"_id": "provider-setting", "key": "storage_provider", "value": "google_drive"})
        session = await client.post(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/upload-session")
        from io import BytesIO
        from PIL import Image
        image = BytesIO()
        Image.new("RGB", (6, 4)).save(image, "PNG")
        import uuid
        upload = await client.post(
            f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos",
            data={"upload_token": session.json()["token"], "upload_ids": [str(uuid.uuid4())]},
            files=[("files", ("guest.png", image.getvalue(), "image/png"))],
        )

    assert upload.status_code == 503
    assert upload.json()["detail"] == "Google Drive storage is unavailable"
    assert not list(tmp_path.iterdir())
    assert not database["photos"].documents


def _valid_png() -> bytes:
    data = BytesIO()
    Image.new("RGB", (8, 5), (120, 85, 45)).save(data, "PNG")
    return data.getvalue()


@pytest.mark.asyncio
async def test_new_guest_upload_uses_drive_and_saves_provider_metadata(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    config = drive_settings()

    class FakeDrive:
        provider = "google_drive"
        async def ensure_ready(self): pass
        async def upload(self, content, mime_type, **kwargs):
            return StoredObject("google_drive", "private-drive-id", mime_type, len(content))
        async def delete(self, file_id): raise AssertionError("successful upload must not clean up")

    async with api_client(app) as client:
        app.state.settings = config
        app.state.google_drive_storage = FakeDrive()
        app.state.local_photo_storage.root = tmp_path
        album = (await client.post("/api/v1/albums", json={"name": "New Drive Upload"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Welcome"}, headers=admin_headers)).json()
        database["photo_settings"].documents.append({"_id": ObjectId(), "key": "storage_provider", "value": "google_drive"})
        session = await client.post(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/upload-session")
        upload = await client.post(
            f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos",
            data={"upload_token": session.json()["token"], "upload_ids": ["85eb201c-cc0f-4e16-8b1e-33f6f2bb8640"]},
            files=[("files", ("new.png", _valid_png(), "image/png"))],
        )

    assert upload.status_code == 200 and upload.json()["succeeded"] == 1
    assert database["photos"].documents[0]["storage_provider"] == "google_drive"
    assert database["photos"].documents[0]["storage_file_id"] == "private-drive-id"
    assert database["photos"].documents[0]["status"] == "pending"
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_drive_upload_is_cleaned_if_photo_metadata_insert_fails(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    config = drive_settings()

    class FakeDrive:
        provider = "google_drive"
        deleted: list[str] = []
        async def ensure_ready(self): pass
        async def upload(self, content, mime_type, **kwargs):
            return StoredObject("google_drive", "orphan-candidate-id", mime_type, len(content))
        async def delete(self, file_id): self.deleted.append(file_id)

    async with api_client(app) as client:
        app.state.settings = config
        drive = FakeDrive()
        app.state.google_drive_storage = drive
        app.state.local_photo_storage.root = tmp_path
        album = (await client.post("/api/v1/albums", json={"name": "Drive Cleanup"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Dinner"}, headers=admin_headers)).json()
        database["photo_settings"].documents.append({"_id": ObjectId(), "key": "storage_provider", "value": "google_drive"})
        database["photos"].insert_one = AsyncMock(side_effect=RuntimeError("simulated database insert failure"))
        session = await client.post(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/upload-session")
        upload = await client.post(
            f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos",
            data={"upload_token": session.json()["token"], "upload_ids": ["635c4309-54df-467e-9f26-6bd5f1e38d58"]},
            files=[("files", ("new.png", _valid_png(), "image/png"))],
        )

    assert upload.status_code == 200 and upload.json()["failed"] == 1
    assert drive.deleted == ["orphan-candidate-id"]
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_admin_storage_routes_authorize_and_provider_selection_is_persisted(monkeypatch):
    from unittest.mock import AsyncMock

    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        unauthorized_status = await client.get("/api/v1/admin/storage/status")
        unauthorized_connect = await client.post("/api/v1/integrations/google-drive/connect")
        app.state.google_drive_storage.verify_connection = AsyncMock(return_value={"operational": True})
        selected = await client.patch("/api/v1/admin/storage/provider", json={"provider": "google_drive"}, headers=admin_headers)
        stored_drive = await database["photo_settings"].find_one({"key": "storage_provider"})
        stored_drive_value = stored_drive["value"]
        local = await client.patch("/api/v1/admin/storage/provider", json={"provider": "local"}, headers=admin_headers)
        stored_local = await database["photo_settings"].find_one({"key": "storage_provider"})

    assert unauthorized_status.status_code == 401
    assert unauthorized_connect.status_code == 401
    assert selected.status_code == 200 and selected.json()["provider"] == "google_drive"
    assert stored_drive_value == "google_drive"
    assert local.status_code == 200 and stored_local["value"] == "local"


@pytest.mark.asyncio
async def test_mixed_local_and_drive_photos_stream_and_drive_delete_uses_record_provider(monkeypatch, tmp_path):
    from app.storage.local import LocalPhotoStorage
    from app.storage.base import StoredObject
    from io import BytesIO
    from PIL import Image

    app, database, admin_headers = make_app(monkeypatch)
    image_stream = BytesIO()
    Image.new("RGB", (7, 5), (201, 165, 99)).save(image_stream, "PNG")
    image_bytes = image_stream.getvalue()

    class FakeDrive:
        provider = "google_drive"

        def __init__(self):
            self.deleted = []

        async def open_read(self, file_id):
            async def chunks():
                yield image_bytes
            return StoredContent("image/png", len(image_bytes), chunks())

        async def delete(self, file_id):
            self.deleted.append(file_id)

    async with api_client(app) as client:
        app.state.photo_storage = LocalPhotoStorage(tmp_path)
        drive = FakeDrive()
        app.state.google_drive_storage = drive
        album = (await client.post("/api/v1/albums", json={"name": "Mixed Providers"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Reception"}, headers=admin_headers)).json()
        album_id, event_id = __import__("bson").ObjectId(album["id"]), __import__("bson").ObjectId(event["id"])
        local_stored = await app.state.photo_storage.upload(image_bytes, "image/png")
        local_doc = {"_id": __import__("bson").ObjectId(), "album_id": album_id, "event_id": event_id,
                     "storage_provider": "local", "storage_file_id": local_stored.file_id,
                     "original_filename": "local.png", "mime_type": "image/png", "file_size": len(image_bytes),
                     "width": 7, "height": 5, "status": "approved", "uploaded_at": datetime.now(UTC)}
        drive_doc = {"_id": __import__("bson").ObjectId(), "album_id": album_id, "event_id": event_id,
                     "storage_provider": "google_drive", "storage_file_id": "private-drive-file-id",
                     "original_filename": "drive.png", "mime_type": "image/png", "file_size": len(image_bytes),
                     "width": 7, "height": 5, "status": "approved", "uploaded_at": datetime.now(UTC)}
        database["photos"].documents.extend([local_doc, drive_doc])
        gallery = await client.get(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos")
        album_gallery = await client.get(f"/api/v1/public/albums/{album['slug']}/photos")
        local_image = await client.get(f"/api/v1/public/photos/{local_doc['_id']}/image")
        drive_image = await client.get(f"/api/v1/public/photos/{drive_doc['_id']}/image")
        local_download = await client.get(f"/api/v1/public/photos/{local_doc['_id']}/image?download=true")
        drive_download = await client.get(f"/api/v1/public/photos/{drive_doc['_id']}/image?download=true")
        admin_drive_image = await client.get(f"/api/v1/admin/photos/{drive_doc['_id']}/image", headers=admin_headers)
        listing = await client.get("/api/v1/admin/photos", headers=admin_headers)
        deleted = await client.delete(f"/api/v1/admin/photos/{drive_doc['_id']}", headers=admin_headers)

    assert local_image.status_code == drive_image.status_code == admin_drive_image.status_code == 200
    assert local_image.content == drive_image.content == admin_drive_image.content == image_bytes
    assert gallery.json()["total"] == album_gallery.json()["total"] == 2
    gallery_image_ids = {item["id"] for item in gallery.json()["items"]}
    assert gallery_image_ids == {str(local_doc["_id"]), str(drive_doc["_id"])}
    assert local_download.status_code == drive_download.status_code == 200
    assert local_download.content == drive_download.content == image_bytes
    assert "attachment" in local_download.headers["content-disposition"]
    assert "attachment" in drive_download.headers["content-disposition"]
    assert {item["storage_provider"] for item in listing.json()["items"]} == {"local", "google_drive"}
    assert deleted.status_code == 204 and drive.deleted == ["private-drive-file-id"]
    assert await database["photos"].find_one({"_id": drive_doc["_id"]}) is None
    assert await database["photos"].find_one({"_id": local_doc["_id"]}) is not None
