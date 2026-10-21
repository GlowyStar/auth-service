import hashlib
import hmac
import secrets
from enum import StrEnum

from redis.asyncio import Redis

from auth_service.errors import CodeResendTooSoon, InvalidCode

CODE_TTL_SECONDS = 5 * 60
CODE_MAX_ATTEMPTS = 5
CODE_RESEND_COOLDOWN_SECONDS = 60


class CodePurpose(StrEnum):
    CONFIRM_EMAIL = "confirm-email"


class OneTimeCodes:
    def __init__(self, redis: Redis, secret: str) -> None:
        self._redis = redis
        self._secret = secret.encode()

    async def issue(self, purpose: CodePurpose, email: str) -> str:
        code = f"{secrets.randbelow(10**6):06d}"
        key = f"code:{purpose}:{email}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hset(key, mapping={"digest": self._digest(key, code), "attempts": 0})
            pipe.expire(key, CODE_TTL_SECONDS)
            pipe.set(f"code-cooldown:{purpose}:{email}", 1, ex=CODE_RESEND_COOLDOWN_SECONDS)
            await pipe.execute()
        return code

    async def start_resend_cooldown(self, purpose: CodePurpose, email: str) -> None:
        cooldown_started = await self._redis.set(
            f"code-cooldown:{purpose}:{email}", 1, ex=CODE_RESEND_COOLDOWN_SECONDS, nx=True
        )
        if not cooldown_started:
            raise CodeResendTooSoon

    async def consume(self, purpose: CodePurpose, email: str, code: str) -> None:
        key = f"code:{purpose}:{email}"
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hget(key, "digest")
            pipe.hincrby(key, "attempts", 1)
            # HINCRBY recreates an expired key without a TTL; give it one so it cannot leak.
            pipe.expire(key, CODE_TTL_SECONDS, nx=True)
            digest, attempts, _ = await pipe.execute()

        code_is_missing = digest is None
        code_is_burned = attempts > CODE_MAX_ATTEMPTS
        if code_is_missing or code_is_burned:
            raise InvalidCode

        if not hmac.compare_digest(digest, self._digest(key, code)):
            if attempts == CODE_MAX_ATTEMPTS:
                await self._redis.delete(key)
            raise InvalidCode

        # Only one of two concurrent requests with the right code gets to delete the key.
        if await self._redis.delete(key) == 0:
            raise InvalidCode

    def _digest(self, key: str, code: str) -> str:
        return hmac.new(self._secret, f"{key}:{code}".encode(), hashlib.sha256).hexdigest()
