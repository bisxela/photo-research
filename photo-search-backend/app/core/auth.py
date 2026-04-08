import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Optional

from fastapi import Header, HTTPException, status

from app.config import settings
from app.core.database import database

TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
PASSWORD_ITERATIONS = 120_000
def _get_secret_key() -> bytes:
    return hashlib.sha256(settings.AUTH_SECRET.encode("utf-8")).digest()


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"{salt}${derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, stored_hash = password_hash.split("$", 1)
    except ValueError:
        return False

    candidate_hash = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(candidate_hash, stored_hash)


def create_access_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=")
    signature = hmac.new(_get_secret_key(), payload_b64, hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return f"{payload_b64.decode('utf-8')}.{signature_b64.decode('utf-8')}"


def decode_access_token(token: str) -> Dict[str, str]:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    expected_signature = hmac.new(
        _get_secret_key(),
        payload_part.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual_signature = _urlsafe_b64decode(signature_part)

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    payload_bytes = _urlsafe_b64decode(payload_part)
    payload = json.loads(payload_bytes.decode("utf-8"))

    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    return payload


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


async def get_current_user(authorization: str = Header(..., alias="Authorization")) -> Dict[str, str]:
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization[len(prefix):].strip()
    payload = decode_access_token(token)

    user = await database.fetch_one(
        "SELECT id, username, created_at FROM users WHERE id = :id",
        {"id": payload["sub"]},
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return {
        "id": str(user["id"]),
        "username": user["username"],
        "created_at": user["created_at"].isoformat() if user["created_at"] else None,
    }
