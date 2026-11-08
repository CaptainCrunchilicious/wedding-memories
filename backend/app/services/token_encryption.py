from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import Settings


class TokenEncryptionError(RuntimeError):
    """Raised when OAuth tokens cannot be safely encrypted or decrypted."""


def _fernets(settings: Settings) -> MultiFernet:
    key = settings.google_drive_token_encryption_key.get_secret_value().strip()
    if not key:
        raise TokenEncryptionError("Google Drive token encryption is not configured")
    try:
        keys = [Fernet(key.encode("ascii"))]
        previous = settings.google_drive_token_encryption_key_previous.get_secret_value().strip()
        if previous:
            keys.append(Fernet(previous.encode("ascii")))
        return MultiFernet(keys)
    except (ValueError, UnicodeEncodeError):
        raise TokenEncryptionError("Google Drive token encryption key is invalid") from None


def validate_encryption_key(settings: Settings) -> None:
    _fernets(settings)


def encrypt_tokens(settings: Settings, tokens: dict) -> str:
    import json

    # Encrypt with the current key; the previous key is decrypt-only during rotation.
    return _fernets(settings).encrypt(
        json.dumps(tokens, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii")


def decrypt_tokens(settings: Settings, encrypted: str) -> dict:
    import json

    try:
        value = _fernets(settings).decrypt(encrypted.encode("ascii"))
        tokens = json.loads(value)
    except (InvalidToken, ValueError, UnicodeEncodeError, json.JSONDecodeError):
        raise TokenEncryptionError(
            "Stored Google Drive credentials cannot be decrypted; check the encryption key"
        ) from None
    if not isinstance(tokens, dict):
        raise TokenEncryptionError("Stored Google Drive credentials are invalid")
    return tokens


def needs_key_rotation(settings: Settings, encrypted: str) -> bool:
    """Return whether ciphertext was encrypted with the configured previous key."""
    current_key = settings.google_drive_token_encryption_key.get_secret_value().strip()
    try:
        Fernet(current_key.encode("ascii")).decrypt(encrypted.encode("ascii"))
        return False
    except InvalidToken:
        # Verify that a previous key can decrypt it before marking it rotatable.
        if not settings.google_drive_token_encryption_key_previous.get_secret_value().strip():
            raise TokenEncryptionError("Stored Google Drive credentials cannot be decrypted; check the encryption key") from None
        decrypt_tokens(settings, encrypted)
        return True
    except (ValueError, UnicodeEncodeError):
        raise TokenEncryptionError("Google Drive token encryption key is invalid") from None
