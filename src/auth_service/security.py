import asyncio

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


# Argon2 burns tens of milliseconds of CPU, so it runs off the event loop.
async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_password_hash.hash, password)
