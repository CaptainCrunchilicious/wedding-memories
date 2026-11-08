from datetime import date, datetime
from enum import Enum
from typing import Self

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.slugs import normalize_slug


class ResourceStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class CoverImageReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: AnyHttpUrl | None = None
    reference: str | None = Field(default=None, max_length=500)
    alt_text: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def require_reference(self) -> Self:
        if self.url is None and not self.reference:
            raise ValueError("Provide a cover image URL or reference")
        return self


class AlbumFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    couple_names: str | None = Field(default=None, max_length=200)
    event_date: date | None = None
    location: str | None = Field(default=None, max_length=200)
    cover_image: CoverImageReference | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str | None) -> str | None:
        return normalize_slug(value) if value is not None else None

    @field_validator("description", "couple_names", "location")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class AlbumCreate(AlbumFields):
    pass


class AlbumPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    couple_names: str | None = Field(default=None, max_length=200)
    event_date: date | None = None
    location: str | None = Field(default=None, max_length=200)
    cover_image: CoverImageReference | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str | None) -> str | None:
        return normalize_slug(value) if value is not None else None

    @field_validator("description", "couple_names", "location")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class EventFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    event_date: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    display_order: int = Field(default=0, ge=0, le=100_000)
    cover_image: CoverImageReference | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str | None) -> str | None:
        return normalize_slug(value) if value is not None else None

    @field_validator("description", "location")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("event_date")
    @classmethod
    def normalize_event_date(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        from datetime import UTC

        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class EventCreate(EventFields):
    pass


class EventPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    event_date: datetime | None = None
    location: str | None = Field(default=None, max_length=200)
    display_order: int | None = Field(default=None, ge=0, le=100_000)
    cover_image: CoverImageReference | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be blank")
        return cleaned

    @field_validator("slug")
    @classmethod
    def clean_slug(cls, value: str | None) -> str | None:
        return normalize_slug(value) if value is not None else None

    @field_validator("description", "location")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("event_date")
    @classmethod
    def normalize_event_date(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        from datetime import UTC

        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AlbumResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    couple_names: str | None
    event_date: date | None
    location: str | None
    cover_image: CoverImageReference | None
    status: ResourceStatus
    event_count: int = 0
    created_at: datetime
    updated_at: datetime


class EventResponse(BaseModel):
    id: str
    album_id: str
    name: str
    slug: str
    description: str | None
    event_date: datetime | None
    location: str | None
    cover_image: CoverImageReference | None
    status: ResourceStatus
    display_order: int
    created_at: datetime
    updated_at: datetime


class AlbumPage(BaseModel):
    items: list[AlbumResponse]
    total: int
    page: int
    page_size: int


class EventPage(BaseModel):
    items: list[EventResponse]
    total: int
    page: int
    page_size: int
