import os
import uuid
from pathlib import Path
import anyio

from app.storage.base import StoredContent, StoredObject


class LocalPhotoStorage:
    """Development/test filesystem adapter; keeps paths private to the backend."""

    provider = "local"
    _extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    _mime_types = {extension: mime for mime, extension in _extensions.items()}

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    @staticmethod
    def _write_atomic(root: Path, target: Path, content: bytes) -> None:
        temporary = root / f".{target.name}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _ensure_root(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _delete_path(path: Path) -> None:
        path.unlink(missing_ok=True)

    @staticmethod
    def _file_metadata(path: Path, file_id: str) -> dict | None:
        if not path.is_file():
            return None
        return {"size": path.stat().st_size, "file_id": file_id}

    def _path(self, file_id: str) -> Path:
        if not file_id or Path(file_id).name != file_id or "/" in file_id or "\\" in file_id:
            raise ValueError("Invalid storage identifier")
        path = (self.root / file_id).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid storage identifier")
        return path

    async def upload(
        self, content: bytes, mime_type: str, *, client_upload_id: str | None = None,
        album_slug: str | None = None, event_slug: str | None = None,
    ) -> StoredObject:
        extension = self._extensions.get(mime_type)
        if extension is None:
            raise ValueError("Unsupported image type")
        file_id = f"{uuid.uuid4().hex}{extension}"
        path = self._path(file_id)

        await anyio.to_thread.run_sync(self._ensure_root, self.root)
        await anyio.to_thread.run_sync(self._write_atomic, self.root, path, content)
        return StoredObject(self.provider, file_id, mime_type, len(content))

    async def delete(self, file_id: str) -> None:
        path = self._path(file_id)
        await anyio.to_thread.run_sync(self._delete_path, path)

    async def get_metadata(self, file_id: str) -> dict | None:
        path = self._path(file_id)

        return await anyio.to_thread.run_sync(self._file_metadata, path, file_id)

    async def get_delivery_reference(self, file_id: str) -> str | None:
        # Local files are served only through authorized API routes, not a permanent URL.
        return None

    async def open_read(self, file_id: str) -> StoredContent:
        path = self._path(file_id)
        metadata = await anyio.to_thread.run_sync(self._file_metadata, path, file_id)
        if metadata is None:
            raise FileNotFoundError(file_id)
        mime_type = self._mime_types.get(path.suffix.lower())
        if mime_type is None:
            raise ValueError("Unsupported stored image type")
        size = metadata["size"]
        reader = await anyio.open_file(path, "rb")

        async def chunks():
            try:
                while data := await reader.read(256 * 1024):
                    yield data
            finally:
                await reader.aclose()

        return StoredContent(mime_type=mime_type, size=size, chunks=chunks())
