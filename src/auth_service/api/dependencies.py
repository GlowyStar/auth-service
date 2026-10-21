from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_service.service import AuthService
from auth_service.settings import get_settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


async def get_auth_service(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> AuthService:
    state = request.app.state
    return AuthService(session, state.redis, state.email_sender, get_settings())


Service = Annotated[AuthService, Depends(get_auth_service)]
