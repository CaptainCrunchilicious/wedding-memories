from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidPhotoError(ValueError):
    pass


MAX_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def validate_and_sanitize(data: bytes, declared_type: str | None) -> tuple[bytes, str, int, int]:
    if not data:
        raise InvalidPhotoError("The selected file is empty.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            fmt = image.format
            if fmt not in {"JPEG", "PNG", "WEBP"}:
                raise InvalidPhotoError("Only JPEG, PNG, and WebP images are accepted.")
            mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[fmt]
            if declared_type and declared_type.lower() not in {mime, "application/octet-stream"}:
                raise InvalidPhotoError("The file content does not match its declared image type.")
            image.verify()
            image = Image.open(BytesIO(data))
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                raise InvalidPhotoError("The image dimensions exceed the allowed limit.")
            if fmt == "JPEG":
                image = image.convert("RGB")
            output = BytesIO()
            image.save(output, format=fmt, quality=90, optimize=True)
            cleaned = output.getvalue()
            # Re-open sanitized output to catch encoder or decoder anomalies.
            Image.open(BytesIO(cleaned)).verify()
            return cleaned, mime, width, height
    except InvalidPhotoError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidPhotoError("The selected file is not a valid supported image.") from exc
