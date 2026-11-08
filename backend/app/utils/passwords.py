import anyio
import secrets
from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


async def verify_password(password: str, stored_hash: str | None) -> bool:
    hash_to_verify = stored_hash or DUMMY_PASSWORD_HASH
    try:
        password_matches = await anyio.to_thread.run_sync(password_hasher.verify, password, hash_to_verify)
        return bool(stored_hash) and password_matches
    except Exception:
        return False
