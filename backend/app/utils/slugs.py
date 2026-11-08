import re
import unicodedata

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_slug(value: str) -> str:
    normalized = re.sub(r"[-_\s]+", "-", value.strip().lower())
    if not SLUG_PATTERN.fullmatch(normalized):
        raise ValueError("Slug may contain lowercase letters, numbers, and single hyphens only")
    if len(normalized) > 120:
        raise ValueError("Slug must be 120 characters or fewer")
    return normalized


def slugify_name(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    if not slug:
        raise ValueError("Provide a URL-friendly slug for this name")
    return normalize_slug(slug)
