import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.database.connection import MongoConnection, get_database
from app.services.token_encryption import TokenEncryptionError, decrypt_tokens, encrypt_tokens, needs_key_rotation
from app.storage.base import StoredContent, StoredObject

logger = logging.getLogger(__name__)
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
FOLDER_MIME = "application/vnd.google-apps.folder"
_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class DriveProviderError(RuntimeError):
    """A safe, user-facing Google Drive provider failure."""


class DriveNotConnected(DriveProviderError):
    pass


class DriveFileNotFound(DriveProviderError):
    pass


class DriveConfigurationError(DriveProviderError):
    pass


class GoogleDriveStorage:
    """Private Drive v3 adapter; OAuth tokens are encrypted in photo_settings."""

    provider = "google_drive"

    def __init__(self, settings: Settings, connection: MongoConnection) -> None:
        self.settings = settings
        self.connection = connection

    def _database(self):
        return get_database(self.connection)

    def _assert_oauth_configured(self) -> None:
        if not (self.settings.google_drive_client_id.strip()
                and self.settings.google_drive_client_secret.get_secret_value().strip()
                and self.settings.google_drive_redirect_uri.strip()):
            raise DriveConfigurationError("Google Drive OAuth configuration is incomplete")
        try:
            # Validate the key before any provider state is changed.
            from app.services.token_encryption import validate_encryption_key
            validate_encryption_key(self.settings)
        except TokenEncryptionError as exc:
            raise DriveConfigurationError(str(exc)) from None

    async def _credential_document(self) -> dict | None:
        return await self._database()["photo_settings"].find_one({"key": "google_drive_credentials"})

    async def _load_tokens(self) -> tuple[dict, dict]:
        self._assert_oauth_configured()
        document = await self._credential_document()
        if not document or not document.get("encrypted_tokens"):
            raise DriveNotConnected("Google Drive is not connected")
        try:
            tokens = decrypt_tokens(self.settings, document["encrypted_tokens"])
            if needs_key_rotation(self.settings, document["encrypted_tokens"]):
                await self._database()["photo_settings"].update_one(
                    {"_id": document["_id"]},
                    {"$set": {"encrypted_tokens": encrypt_tokens(self.settings, tokens)}},
                )
        except TokenEncryptionError as exc:
            raise DriveConfigurationError(str(exc)) from None
        return tokens, document

    async def save_tokens(self, tokens: dict, *, account_email: str | None = None) -> None:
        self._assert_oauth_configured()
        current = await self._credential_document()
        if current and current.get("encrypted_tokens"):
            try:
                previous = decrypt_tokens(self.settings, current["encrypted_tokens"])
            except TokenEncryptionError as exc:
                raise DriveConfigurationError(str(exc)) from None
            if not tokens.get("refresh_token") and previous.get("refresh_token"):
                tokens["refresh_token"] = previous["refresh_token"]
            if not tokens.get("folder_id") and previous.get("folder_id"):
                tokens["folder_id"] = previous["folder_id"]
        if not tokens.get("refresh_token"):
            raise DriveConfigurationError("Google did not provide an offline refresh token; reconnect with consent")
        existing = current or {}
        fields = {
            "encrypted_tokens": encrypt_tokens(self.settings, tokens),
            "account_email": account_email or existing.get("account_email"),
            "connected_at": existing.get("connected_at") or datetime.now(UTC),
        }
        await self._database()["photo_settings"].update_one(
            {"key": "google_drive_credentials"},
            {"$set": fields},
            upsert=True,
        )

    async def _refresh(self, tokens: dict) -> dict:
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise DriveNotConnected("Google Drive needs to be reconnected")
        secret = self.settings.google_drive_client_secret.get_secret_value()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(TOKEN_ENDPOINT, data={
                    "client_id": self.settings.google_drive_client_id,
                    "client_secret": secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                })
        except httpx.HTTPError as exc:
            logger.warning("Google token refresh request failed (%s).", type(exc).__name__)
            raise DriveProviderError("Google Drive is temporarily unavailable") from None
        if response.status_code != 200:
            logger.warning("Google token refresh returned HTTP %s.", response.status_code)
            if response.status_code in {400, 401, 403}:
                raise DriveNotConnected("Google Drive needs to be reconnected")
            raise DriveProviderError("Google Drive is temporarily unavailable")
        refreshed = response.json()
        tokens.update(refreshed)
        tokens["refresh_token"] = refreshed.get("refresh_token") or refresh_token
        tokens["expires_at"] = int(time.time()) + int(refreshed.get("expires_in", 3600))
        await self.save_tokens(tokens)
        return tokens

    async def _access_token(self, *, force_refresh: bool = False) -> str:
        tokens, _ = await self._load_tokens()
        if force_refresh or int(tokens.get("expires_at", 0)) <= int(time.time()) + 60:
            tokens = await self._refresh(tokens)
        token = tokens.get("access_token")
        if not token:
            raise DriveNotConnected("Google Drive needs to be reconnected")
        return token

    async def _request(
        self, method: str, url: str, *, retry_safe: bool = False, **kwargs
    ) -> httpx.Response:
        transient_retries = 2 if retry_safe else 0
        refreshed = False
        attempt = 0
        while True:
            token = await self._access_token(force_refresh=refreshed)
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["Authorization"] = f"Bearer {token}"
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.request(method, url, headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                logger.warning("Google Drive request failed (%s).", type(exc).__name__)
                if retry_safe and attempt < transient_retries:
                    attempt += 1
                    continue
                raise DriveProviderError("Google Drive is temporarily unavailable") from None
            if response.status_code == 401 and not refreshed:
                refreshed = True
                continue
            if response.status_code == 401:
                raise DriveNotConnected("Google Drive needs to be reconnected")
            if retry_safe and response.status_code in {429, 500, 502, 503, 504} and attempt < transient_retries:
                attempt += 1
                continue
            if response.status_code == 404:
                raise DriveFileNotFound("The stored Google Drive photo is unavailable")
            if response.is_error:
                logger.warning("Google Drive API returned HTTP %s.", response.status_code)
                raise DriveProviderError("Google Drive could not complete the photo operation")
            return response

    async def _root_folder(self) -> str:
        tokens, _ = await self._load_tokens()
        configured_id = self.settings.google_drive_folder_id.strip()
        folder_id = configured_id or tokens.get("folder_id")
        if folder_id:
            try:
                response = await self._request(
                    "GET", f"{DRIVE_API}/files/{quote(folder_id, safe='')}",
                    params={"fields": "id,mimeType,trashed,capabilities(canAddChildren)"}, retry_safe=True,
                )
            except DriveFileNotFound:
                if configured_id:
                    raise DriveConfigurationError("The configured Google Drive folder is unavailable") from None
                # Recreate a deleted app-managed root. Existing files retain their Drive IDs.
                tokens.pop("folder_id", None)
                folder_id = None
            if folder_id:
                info = response.json()
                if info.get("trashed") or info.get("mimeType") != FOLDER_MIME:
                    if configured_id:
                        raise DriveConfigurationError("The configured Google Drive folder is not accessible")
                    tokens.pop("folder_id", None)
                    folder_id = None
                elif info.get("capabilities", {}).get("canAddChildren") is False:
                    raise DriveConfigurationError("The configured Google Drive folder is not writable")
                if folder_id:
                    if folder_id != tokens.get("folder_id"):
                        tokens["folder_id"] = folder_id
                        await self.save_tokens(tokens)
                    return folder_id

        response = await self._request("POST", f"{DRIVE_API}/files", json={
            "name": "Wedding Memories", "mimeType": FOLDER_MIME,
        }, params={"fields": "id"})
        folder_id = response.json().get("id")
        if not folder_id:
            raise DriveProviderError("Google Drive did not return an application folder")
        tokens["folder_id"] = folder_id
        await self.save_tokens(tokens)
        return folder_id

    async def verify_connection(self) -> dict:
        """Validate credentials and folder access; return non-secret health data."""
        response = await self._request(
            "GET", f"{DRIVE_API}/about", params={"fields": "user(displayName,emailAddress)"}, retry_safe=True,
        )
        user = response.json().get("user") or {}
        await self._root_folder()
        checked_at = datetime.now(UTC)
        await self._database()["photo_settings"].update_one(
            {"key": "google_drive_credentials"},
            {"$set": {"account_email": user.get("emailAddress"), "last_checked_at": checked_at}},
        )
        return {"connected": True, "operational": True, "connected_email": user.get("emailAddress"),
                "folder_status": "ready", "last_successful_check": checked_at.isoformat()}

    async def ensure_ready(self) -> None:
        await self._root_folder()

    async def connection_status(self) -> dict:
        configured = bool(self.settings.google_drive_client_id.strip()
                          and self.settings.google_drive_client_secret.get_secret_value().strip()
                          and self.settings.google_drive_redirect_uri.strip()
                          and self.settings.google_drive_token_encryption_key.get_secret_value().strip())
        if configured:
            try:
                self._assert_oauth_configured()
            except DriveConfigurationError:
                configured = False
        document = await self._credential_document()
        last_check = document.get("last_checked_at") if document else None
        if isinstance(last_check, datetime):
            last_check = (last_check.replace(tzinfo=UTC) if last_check.tzinfo is None else last_check.astimezone(UTC)).isoformat()
        status = {"configured": configured, "connected": bool(document), "operational": False,
                  "connected_email": document.get("account_email") if document else None,
                  "folder_status": "not_connected" if not document else "unknown",
                  "last_successful_check": last_check if isinstance(last_check, str) else None}
        if not configured or not document:
            return status
        try:
            health = await self.verify_connection()
            status.update(health)
        except DriveProviderError:
            status["folder_status"] = "unavailable"
        return status

    async def _find_upload(self, upload_id: str) -> dict | None:
        response = await self._request(
            "GET", f"{DRIVE_API}/files", params={
                "q": f"appProperties has {{ key='weddingUploadId' and value='{upload_id}' }} and trashed=false",
                "spaces": "drive", "pageSize": 1, "fields": "files(id,mimeType,size)",
            }, retry_safe=True,
        )
        files = response.json().get("files", [])
        return files[0] if files else None

    async def upload(
        self, content: bytes, mime_type: str, *, client_upload_id: str | None = None,
        album_slug: str | None = None, event_slug: str | None = None,
    ) -> StoredObject:
        extension = _EXTENSIONS.get(mime_type)
        if extension is None:
            raise DriveConfigurationError("Unsupported image type")
        upload_id = client_upload_id or uuid.uuid4().hex
        existing = await self._find_upload(upload_id)
        if existing:
            return StoredObject(self.provider, existing["id"], mime_type, int(existing.get("size", len(content))))
        parent = await self._root_folder()
        metadata = {"name": f"photo-{upload_id}{extension}", "mimeType": mime_type, "parents": [parent],
                    "appProperties": {"weddingUploadId": upload_id,
                                      "albumSlug": album_slug or "", "eventSlug": event_slug or ""}}
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                token = await self._access_token()
                session = await client.post(
                    f"{DRIVE_UPLOAD_API}/files", params={"uploadType": "resumable", "fields": "id,mimeType,size"},
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                             "X-Upload-Content-Type": mime_type, "X-Upload-Content-Length": str(len(content))},
                    json=metadata,
                )
                if session.status_code == 401:
                    token = await self._access_token(force_refresh=True)
                    session = await client.post(
                        f"{DRIVE_UPLOAD_API}/files", params={"uploadType": "resumable", "fields": "id,mimeType,size"},
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                 "X-Upload-Content-Type": mime_type, "X-Upload-Content-Length": str(len(content))},
                        json=metadata,
                    )
                if session.is_error or not session.headers.get("location"):
                    logger.warning("Google Drive resumable session returned HTTP %s.", session.status_code)
                    raise DriveProviderError("Google Drive could not start the photo upload")
                uploaded = await client.put(session.headers["location"], content=content,
                                            headers={"Content-Type": mime_type}, timeout=90)
        except httpx.HTTPError as exc:
            logger.warning("Google Drive photo upload failed (%s).", type(exc).__name__)
            try:
                recovered = await self._find_upload(upload_id)
            except DriveProviderError as recovery_exc:
                logger.error("Google Drive upload outcome is uncertain (%s); check the application folder.", type(recovery_exc).__name__)
                recovered = None
            if recovered:
                return StoredObject(self.provider, recovered["id"], mime_type,
                                    int(recovered.get("size", len(content))))
            raise DriveProviderError("Google Drive could not complete the photo upload") from None
        if uploaded.is_error:
            logger.warning("Google Drive resumable upload returned HTTP %s.", uploaded.status_code)
            try:
                recovered = await self._find_upload(upload_id)
            except DriveProviderError as recovery_exc:
                logger.error("Google Drive upload outcome is uncertain (%s); check the application folder.", type(recovery_exc).__name__)
                recovered = None
            if recovered:
                return StoredObject(self.provider, recovered["id"], mime_type,
                                    int(recovered.get("size", len(content))))
            raise DriveProviderError("Google Drive could not complete the photo upload")
        result = uploaded.json()
        file_id = result.get("id")
        if not file_id:
            raise DriveProviderError("Google Drive did not return a photo identifier")
        return StoredObject(self.provider, file_id, mime_type, int(result.get("size", len(content))))

    async def open_read(self, file_id: str) -> StoredContent:
        token = await self._access_token()
        client = httpx.AsyncClient(timeout=60)
        refreshed = False
        attempt = 0
        try:
            while True:
                request = client.build_request(
                    "GET", f"{DRIVE_API}/files/{quote(file_id, safe='')}",
                    params={"alt": "media"}, headers={"Authorization": f"Bearer {token}"},
                )
                try:
                    response = await client.send(request, stream=True)
                except httpx.HTTPError as exc:
                    if attempt < 2:
                        attempt += 1
                        continue
                    logger.warning("Google Drive image download failed (%s).", type(exc).__name__)
                    raise DriveProviderError("Google Drive could not retrieve this photo") from None
                if response.status_code == 401 and not refreshed:
                    refreshed = True
                    await response.aclose()
                    token = await self._access_token(force_refresh=True)
                    continue
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    attempt += 1
                    await response.aclose()
                    continue
                if response.status_code == 404:
                    await response.aclose()
                    raise FileNotFoundError(file_id)
                if response.is_error:
                    logger.warning("Google Drive image download returned HTTP %s.", response.status_code)
                    await response.aclose()
                    raise DriveProviderError("Google Drive could not retrieve this photo")
                break
        except (httpx.HTTPError, DriveProviderError, FileNotFoundError):
            await client.aclose()
            raise

        mime_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
        size = int(response.headers.get("content-length", "0"))

        async def chunks() -> AsyncIterator[bytes]:
            try:
                async for data in response.aiter_bytes(256 * 1024):
                    if data:
                        yield data
            finally:
                await response.aclose()
                await client.aclose()

        return StoredContent(mime_type=mime_type, size=size, chunks=chunks())

    async def get_metadata(self, file_id: str) -> dict | None:
        try:
            response = await self._request("GET", f"{DRIVE_API}/files/{quote(file_id, safe='')}",
                                           params={"fields": "id,name,mimeType,size,trashed"}, retry_safe=True)
        except DriveFileNotFound:
            return None
        return response.json()

    async def delete(self, file_id: str) -> None:
        try:
            await self._request("DELETE", f"{DRIVE_API}/files/{quote(file_id, safe='')}", retry_safe=True)
        except DriveFileNotFound:
            # Treat an already-removed file as deleted so its stale DB record can be cleaned up.
            return

    async def get_delivery_reference(self, file_id: str) -> str | None:
        return None
