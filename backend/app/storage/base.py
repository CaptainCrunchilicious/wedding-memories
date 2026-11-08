from dataclasses import dataclass
from collections.abc import AsyncIterator
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    provider: str
    file_id: str
    mime_type: str
    size: int


@dataclass(frozen=True)
class StoredContent:
    mime_type: str
    size: int
    chunks: AsyncIterator[bytes]


class PhotoStorage(Protocol):
    async def upload(
        self, content: bytes, mime_type: str, *, client_upload_id: str | None = None,
        album_slug: str | None = None, event_slug: str | None = None,
    ) -> StoredObject: ...
    async def open_read(self, file_id: str) -> StoredContent: ...
    async def delete(self, file_id: str) -> None: ...
    async def get_metadata(self, file_id: str) -> dict | None: ...
    async def get_delivery_reference(self, file_id: str) -> str | None: ...
