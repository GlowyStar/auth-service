import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from auth_service.errors import InvalidToken

JWT_ALGORITHM = "HS256"

_password_hash = PasswordHash.recommended()

# Checked when the email is unknown, so a login takes the same time whether the account exists.
DUMMY_PASSWORD_HASH = _password_hash.hash(secrets.token_urlsafe())


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: UUID
    session_id: UUID
    jti: str
    expires_at: datetime


# Argon2 burns tens of milliseconds of CPU, so it runs off the event loop.
async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_password_hash.hash, password)


async def verify_password(password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(_password_hash.verify, password, password_hash)


def create_access_token(user_id: UUID, session_id: UUID, secret: str, ttl: timedelta) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": uuid4().hex,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(claims, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> AccessClaims:
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "sid", "jti"]},
        )
    except jwt.InvalidTokenError as error:
        raise InvalidToken from error

    return AccessClaims(
        user_id=UUID(claims["sub"]),
        session_id=UUID(claims["sid"]),
        jti=claims["jti"],
        expires_at=datetime.fromtimestamp(claims["exp"], UTC),
    )


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
