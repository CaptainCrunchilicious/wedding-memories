from io import BytesIO
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import asyncio
from bson import ObjectId
from fastapi import HTTPException
from PIL import Image

from app.storage.local import LocalPhotoStorage
from test_albums import api_client, make_app


def png_bytes(color=(220, 170, 95)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", (20, 14), color).save(stream, format="PNG")
    return stream.getvalue()


async def seed_photo(app, database, album_id, event_id, *, status="pending", filename="test.png"):
    stored = await app.state.photo_storage.upload(png_bytes(), "image/png")
    now = datetime.now(UTC)
    document = {
        "_id": ObjectId(), "album_id": album_id, "event_id": event_id,
        "storage_provider": "local", "storage_file_id": stored.file_id,
        "original_filename": filename, "mime_type": "image/png", "file_size": stored.size,
        "width": 20, "height": 14, "status": status, "uploaded_at": now, "created_at": now,
    }
    database["photos"].documents.append(document)
    return document


@pytest.mark.asyncio
async def test_admin_photo_auth_listing_preview_approve_and_public_delivery(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        app.state.photo_storage = LocalPhotoStorage(tmp_path)
        album = (await client.post("/api/v1/albums", json={"name": "Gallery Wedding"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Dinner"}, headers=admin_headers)).json()
        pending = await seed_photo(app, database, ObjectId(album["id"]), ObjectId(event["id"]), filename="pending.png")
        response_unauthorized = await client.get("/api/v1/admin/photos")
        listing = await client.get("/api/v1/admin/photos?status=pending", headers=admin_headers)
        admin_image = await client.get(f"/api/v1/admin/photos/{pending['_id']}/image", headers=admin_headers)
        public_before = await client.get(f"/api/v1/public/photos/{pending['_id']}/image")
        approved = await client.patch(f"/api/v1/admin/photos/{pending['_id']}/approve", headers=admin_headers)
        event_gallery = await client.get(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos")
        album_gallery = await client.get(f"/api/v1/public/albums/{album['slug']}/photos")
        public_image = await client.get(event_gallery.json()["items"][0]["image_url"])

    assert response_unauthorized.status_code == 401
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert listing.json()["counts"]["pending"] == 1
    assert listing.json()["items"][0]["album"]["slug"] == album["slug"]
    assert listing.json()["items"][0]["event"]["slug"] == event["slug"]
    assert "storage_file_id" not in listing.text and "D:\\" not in listing.text
    assert admin_image.status_code == 200 and admin_image.headers["content-type"] == "image/png"
    assert admin_image.headers["cache-control"] == "private, no-store"
    assert public_before.status_code == 404
    assert approved.json()["status"] == "approved"
    assert approved.json()["moderated_by"] == "owner@example.com"
    assert event_gallery.json()["total"] == 1 and album_gallery.json()["total"] == 1
    assert public_image.status_code == 200 and public_image.content == png_bytes()
    assert public_image.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_rejected_photo_is_private_restorable_and_deletable(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        app.state.photo_storage = LocalPhotoStorage(tmp_path)
        album = (await client.post("/api/v1/albums", json={"name": "Private Review"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Party"}, headers=admin_headers)).json()
        rejected = await seed_photo(app, database, ObjectId(album["id"]), ObjectId(event["id"]), status="rejected")
        file_path = tmp_path / rejected["storage_file_id"]
        rejected_image = await client.get(f"/api/v1/admin/photos/{rejected['_id']}/image", headers=admin_headers)
        rejected_public = await client.get(f"/api/v1/public/photos/{rejected['_id']}/image")
        rejected_list = await client.get("/api/v1/admin/photos?status=rejected", headers=admin_headers)
        restored = await client.patch(f"/api/v1/admin/photos/{rejected['_id']}/approve", headers=admin_headers)
        existed_before_delete = file_path.exists()
        deleted = await client.delete(f"/api/v1/admin/photos/{rejected['_id']}", headers=admin_headers)

    assert rejected_image.status_code == 200
    assert rejected_public.status_code == 404
    assert rejected_list.json()["total"] == 1
    assert existed_before_delete
    assert restored.json()["status"] == "approved"
    assert deleted.status_code == 204
    assert not file_path.exists()
    assert await database["photos"].find_one({"_id": rejected["_id"]}) is None


@pytest.mark.asyncio
async def test_bulk_approval_reports_missing_items_and_rejects_duplicate_ids(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        app.state.photo_storage = LocalPhotoStorage(tmp_path)
        album = (await client.post("/api/v1/albums", json={"name": "Bulk Review"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Toast"}, headers=admin_headers)).json()
        photo = await seed_photo(app, database, ObjectId(album["id"]), ObjectId(event["id"]))
        missing_id = str(ObjectId())
        result = await client.post("/api/v1/admin/photos/bulk-approve", json={"photo_ids": [str(photo["_id"]), missing_id]}, headers=admin_headers)
        duplicate = await client.post("/api/v1/admin/photos/bulk-approve", json={"photo_ids": [str(photo["_id"]), str(photo["_id"])]}, headers=admin_headers)
        rejected_after_bulk = await client.post("/api/v1/admin/photos/bulk-approve", json={"photo_ids": [str(photo["_id"])]}, headers=admin_headers)

    assert result.status_code == 200 and result.json()["succeeded"] == 1 and result.json()["failed"] == 1
    assert duplicate.status_code == 422
    assert rejected_after_bulk.json()["failed"] == 1


@pytest.mark.asyncio
async def test_storage_delete_failure_preserves_photo_record(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        app.state.photo_storage = LocalPhotoStorage(tmp_path)
        album = (await client.post("/api/v1/albums", json={"name": "Delete Safely"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Tea"}, headers=admin_headers)).json()
        photo = await seed_photo(app, database, ObjectId(album["id"]), ObjectId(event["id"]))
        file_path = tmp_path / photo["storage_file_id"]
        app.state.photo_storage.delete = AsyncMock(side_effect=OSError("test failure"))
        response = await client.delete(f"/api/v1/admin/photos/{photo['_id']}", headers=admin_headers)
        hidden = await client.get(f"/api/v1/public/photos/{photo['_id']}/image")
        retry_queue = await client.get("/api/v1/admin/photos?deletion_state=pending", headers=admin_headers)

    assert response.status_code == 503
    assert file_path.exists()
    retained = await database["photos"].find_one({"_id": photo["_id"]})
    assert retained is not None and retained["deletion_state"] == "pending"
    assert hidden.status_code == 404
    assert retry_queue.json()["total"] == 1


@pytest.mark.asyncio
async def test_metadata_delete_failure_hides_photo_and_retry_finishes(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        storage = LocalPhotoStorage(tmp_path)
        app.state.photo_storage = storage
        album = (await client.post("/api/v1/albums", json={"name": "Deletion Retry"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Ceremony"}, headers=admin_headers)).json()
        photo = await seed_photo(app, database, ObjectId(album["id"]), ObjectId(event["id"]), status="approved")
        file_path = tmp_path / photo["storage_file_id"]
        original_delete_one = database["photos"].delete_one
        database["photos"].delete_one = AsyncMock(side_effect=RuntimeError("simulated database outage"))
        failed = await client.delete(f"/api/v1/admin/photos/{photo['_id']}", headers=admin_headers)
        gallery = await client.get(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos")
        pending_admin = await client.get("/api/v1/admin/photos?deletion_state=pending", headers=admin_headers)
        database["photos"].delete_one = original_delete_one
        retried = await client.delete(f"/api/v1/admin/photos/{photo['_id']}", headers=admin_headers)
        repeated = await client.delete(f"/api/v1/admin/photos/{photo['_id']}", headers=admin_headers)

    assert failed.status_code == 503
    assert not file_path.exists()
    assert gallery.json()["total"] == 0
    assert pending_admin.json()["total"] == 1
    assert pending_admin.json()["counts"]["approved"] == 0
    assert pending_admin.json()["counts"]["deletion_pending"] == 1
    assert retried.status_code == 204
    assert repeated.status_code == 404
    assert await database["photos"].find_one({"_id": photo["_id"]}) is None


@pytest.mark.asyncio
async def test_concurrent_photo_deletion_claim_is_safe(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        storage = LocalPhotoStorage(tmp_path)
        app.state.photo_storage = storage
        album = (await client.post("/api/v1/albums", json={"name": "Concurrent Delete"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Toast"}, headers=admin_headers)).json()
        photo = await seed_photo(app, database, ObjectId(album["id"]), ObjectId(event["id"]))
        delete_started = asyncio.Event()
        continue_delete = asyncio.Event()
        original_delete = storage.delete

        async def held_delete(file_id):
            delete_started.set()
            await continue_delete.wait()
            await original_delete(file_id)

        storage.delete = held_delete
        first_task = asyncio.create_task(client.delete(f"/api/v1/admin/photos/{photo['_id']}", headers=admin_headers))
        await delete_started.wait()
        second = await client.delete(f"/api/v1/admin/photos/{photo['_id']}", headers=admin_headers)
        hidden = await client.get(f"/api/v1/public/photos/{photo['_id']}/image")
        continue_delete.set()
        first = await first_task

    assert second.status_code == 409
    assert hidden.status_code == 404
    assert first.status_code == 204


@pytest.mark.asyncio
async def test_public_galleries_hide_archived_resources_and_invalid_storage_ids(monkeypatch, tmp_path):
    app, database, admin_headers = make_app(monkeypatch)
    async with api_client(app) as client:
        app.state.photo_storage = LocalPhotoStorage(tmp_path)
        album = (await client.post("/api/v1/albums", json={"name": "Archived Gallery"}, headers=admin_headers)).json()
        event = (await client.post(f"/api/v1/albums/{album['id']}/events", json={"name": "Vows"}, headers=admin_headers)).json()
        photo = await seed_photo(app, database, ObjectId(album["id"]), ObjectId(event["id"]), status="approved")
        photo["storage_file_id"] = "..\\outside.png"
        unsafe = await client.get(f"/api/v1/admin/photos/{photo['_id']}/image", headers=admin_headers)
        await client.patch(f"/api/v1/albums/{album['id']}/events/{event['id']}/archive", headers=admin_headers)
        hidden_event_gallery = await client.get(f"/api/v1/public/albums/{album['slug']}/events/{event['slug']}/photos")
        await client.patch(f"/api/v1/albums/{album['id']}/archive", headers=admin_headers)
        hidden_album_gallery = await client.get(f"/api/v1/public/albums/{album['slug']}/photos")
        hidden_image = await client.get(f"/api/v1/public/photos/{photo['_id']}/image")

    assert unsafe.status_code == 404
    assert hidden_event_gallery.status_code == 404
    assert hidden_album_gallery.status_code == 404
    assert hidden_image.status_code == 404
