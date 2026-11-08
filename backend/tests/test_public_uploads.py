from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api.v1.public import _decode_upload_token
from app.services.photo_validation import InvalidPhotoError, validate_and_sanitize
from app.storage.local import LocalPhotoStorage
from test_albums import api_client, make_app


def image_bytes(fmt: str) -> bytes:
    data = BytesIO()
    Image.new("RGB", (8, 6), (120, 80, 40)).save(data, format=fmt)
    return data.getvalue()


@pytest.mark.parametrize(("fmt", "mime"), [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_image_validation_accepts_supported_formats_and_sanitizes(fmt: str, mime: str) -> None:
    cleaned, actual_type, width, height = validate_and_sanitize(image_bytes(fmt), mime)
    assert actual_type == mime
    assert (width, height) == (8, 6)
    assert cleaned


@pytest.mark.parametrize("data,mime", [(b"", "image/jpeg"), (b"not an image", "image/jpeg"), (image_bytes("PNG"), "image/jpeg")])
def test_image_validation_rejects_empty_malformed_and_mime_mismatch(data: bytes, mime: str) -> None:
    with pytest.raises(InvalidPhotoError):
        validate_and_sanitize(data, mime)


@pytest.mark.asyncio
async def test_public_album_event_and_anonymous_multi_upload(monkeypatch, tmp_path) -> None:
    app, db, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        app.state.photo_storage = LocalPhotoStorage(tmp_path)
        album = (await client.post("/api/v1/albums", json={"name": "Public Wedding"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Ceremony"}, headers=admin_headers)).json()
        second_album = (await client.post("/api/v1/albums", json={"name": "Other Wedding"}, headers=admin_headers)).json()
        unrelated_event = (await client.post(f"/api/v1/albums/{second_album['id']}/events", json={"name": "Other Event"}, headers=admin_headers)).json()

        public_album = await client.get(f"/api/v1/public/albums/{album['slug']}")
        public_event = await client.get(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}")
        wrong_parent_event = await client.get(f"/api/v1/public/albums/{album['slug']}/events/{unrelated_event['slug']}")
        session_response = await client.post(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/upload-session")
        wrong_event = await client.post(
            f"/api/v1/public/albums/{album['slug']}/events/another/photos",
            data={"upload_token": session_response.json()["token"], "upload_ids": ["7ca7cb60-d1d3-49ea-b25d-a97789d6077f"]}, files=[("files", ("one.jpg", image_bytes("JPEG"), "image/jpeg"))],
        )
        upload = await client.post(
            f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos",
            data={"upload_token": session_response.json()["token"], "upload_ids": ["7ca7cb60-d1d3-49ea-b25d-a97789d6077f", "a87c8b81-8ce6-4a93-8a7f-fca7e0f1199c"]},
            files=[("files", ("wedding.jpg", image_bytes("JPEG"), "image/jpeg")), ("files", ("memory.png", image_bytes("PNG"), "image/png"))],
        )
        duplicate = await client.post(
            f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos",
            data={"upload_token": session_response.json()["token"], "upload_ids": ["7ca7cb60-d1d3-49ea-b25d-a97789d6077f", "a87c8b81-8ce6-4a93-8a7f-fca7e0f1199c"]},
            files=[("files", ("wedding.jpg", image_bytes("JPEG"), "image/jpeg")), ("files", ("memory.png", image_bytes("PNG"), "image/png"))],
        )
        await client.patch(f"/api/v1/albums/{album['id']}/events/{event['id']}/archive", headers=admin_headers)
        archived_event = await client.get(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}")
        archived = await client.patch(f"/api/v1/albums/{album['id']}/archive", headers=admin_headers)
        inaccessible = await client.get(f"/api/v1/public/albums/{album['slug']}")

    assert public_album.status_code == 200 and public_event.status_code == 200
    assert "_id" not in public_album.json() and "album_id" not in public_event.json()["event"]
    assert "password_hash" not in public_album.text
    assert session_response.status_code == 200
    assert wrong_parent_event.status_code == 404
    assert wrong_event.status_code == 403
    assert upload.status_code == 200, upload.text
    assert upload.json()["succeeded"] == 2
    assert duplicate.status_code == 200 and duplicate.json()["succeeded"] == 2
    assert archived_event.status_code == 404
    assert len(db["photos"].documents) == 2
    assert len(list(tmp_path.iterdir())) == 2
    for photo in db["photos"].documents:
        assert photo["album_id"] == db["photo_albums"].documents[0]["_id"]
        assert photo["event_id"] == db["photo_events"].documents[0]["_id"]
        assert photo["status"] == "pending"
        assert photo["storage_provider"] == "local"
        assert photo["width"] == 8 and photo["height"] == 6
    assert inaccessible.status_code == 404


@pytest.mark.asyncio
async def test_local_upload_file_is_cleaned_when_photo_metadata_insert_fails(monkeypatch, tmp_path) -> None:
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        storage = LocalPhotoStorage(tmp_path)
        app.state.photo_storage = storage
        album = (await client.post("/api/v1/albums", json={"name": "Cleanup Wedding"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Dinner"}, headers=admin_headers)).json()
        database["photos"].insert_one = AsyncMock(side_effect=RuntimeError("simulated metadata insert failure"))
        session = await client.post(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/upload-session")
        response = await client.post(
            f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos",
            data={"upload_token": session.json()["token"], "upload_ids": ["aa48f4b3-3ee8-4e20-b3c5-9e3127aef65b"]},
            files=[("files", ("cleanup.png", image_bytes("PNG"), "image/png"))],
        )

    assert response.status_code == 200
    assert response.json()["succeeded"] == 0 and response.json()["failed"] == 1
    assert not list(tmp_path.iterdir())
    assert database["photos"].documents == []


def test_upload_token_has_separate_purpose_and_rejects_route_mismatch() -> None:
    from datetime import UTC, datetime, timedelta
    from test_albums import settings
    from app.api.v1.public import _upload_key
    import jwt

    config = settings()
    now = datetime.now(UTC)
    claims = {"aud": "photo-upload", "iss": "wedding-memories", "token_use": "upload_session", "scope": ["photo:upload"],
              "album_slug": "another-album", "event_slug": "event", "jti": "mismatch", "iat": now, "exp": now + timedelta(minutes=5)}
    token = jwt.encode(claims, _upload_key(config), algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        _decode_upload_token(token, config, "album", "event")
    assert error.value.status_code == 403


def test_expired_upload_session_is_rejected() -> None:
    from datetime import UTC, datetime, timedelta
    import jwt
    from app.api.v1.public import _upload_key
    from test_albums import settings

    config = settings()
    now = datetime.now(UTC)
    claims = {"aud": "photo-upload", "iss": "wedding-memories", "token_use": "upload_session", "scope": ["photo:upload"],
              "album_slug": "album", "event_slug": "event", "jti": "expired", "iat": now - timedelta(hours=1), "exp": now - timedelta(seconds=1)}
    token = jwt.encode(claims, _upload_key(config), algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        _decode_upload_token(token, config, "album", "event")
    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_local_storage_never_returns_a_public_path(tmp_path) -> None:
    storage = LocalPhotoStorage(tmp_path)
    stored = await storage.upload(image_bytes("JPEG"), "image/jpeg")
    assert stored.provider == "local"
    assert "\\" not in stored.file_id and "/" not in stored.file_id
    assert await storage.get_metadata(stored.file_id)
    assert await storage.get_delivery_reference(stored.file_id) is None
    with pytest.raises(ValueError):
        await storage.delete("../escape.jpg")


@pytest.mark.asyncio
async def test_local_storage_atomic_write_failure_cleans_temporary_file(monkeypatch, tmp_path) -> None:
    import app.storage.local as local_module

    storage = LocalPhotoStorage(tmp_path)

    def fail_replace(source, target):
        raise OSError("simulated interrupted finalization")

    monkeypatch.setattr(local_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        await storage.upload(image_bytes("PNG"), "image/png")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_local_storage_reads_existing_files(tmp_path) -> None:
    storage = LocalPhotoStorage(tmp_path)
    old_file_id = "existing-local-photo.png"
    original = image_bytes("PNG")
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / old_file_id).write_bytes(original)

    content = await storage.open_read(old_file_id)
    chunks = [chunk async for chunk in content.chunks]
    assert content.mime_type == "image/png"
    assert content.size == len(original)
    assert b"".join(chunks) == original
