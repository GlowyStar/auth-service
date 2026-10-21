import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from auth_service.main import app, lifespan
from tests.support import PASSWORD, Mailbox

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://auth:auth@localhost:5432/auth_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-test-secret")


async def create_database_if_missing(url: str) -> None:
    database = make_url(url).database
    server = create_async_engine(
        make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    async with server.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{database}"'))
    await server.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    asyncio.run(create_database_if_missing(os.environ["DATABASE_URL"]))
    command.upgrade(Config(Path(__file__).parents[1] / "alembic.ini"), "head")


@pytest.fixture
def mailbox() -> Mailbox:
    return Mailbox()


@pytest.fixture
async def client(mailbox: Mailbox) -> AsyncIterator[AsyncClient]:
    async with lifespan(app):
        app.state.email_sender = mailbox
        await app.state.redis.flushdb()
        async with app.state.sessionmaker() as session:
            await session.execute(text("TRUNCATE users, refresh_tokens"))
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def user(client: AsyncClient, mailbox: Mailbox) -> str:
    email = "user@example.com"
    await client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    code = mailbox.last_code(email)
    response = await client.post("/auth/confirm", json={"email": email, "code": code})
    assert response.status_code == 204
    return email


@pytest.fixture
async def tokens(client: AsyncClient, user: str) -> dict[str, Any]:
    response = await client.post("/auth/login", json={"email": user, "password": PASSWORD})
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body
