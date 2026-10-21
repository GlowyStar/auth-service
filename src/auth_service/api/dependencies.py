from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_service.models import User
from auth_service.security import AccessClaims
from auth_service.service import AuthService
from auth_service.settings import get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


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


async def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def get_access_claims(
    service: Service, token: Annotated[str, Depends(oauth2_scheme)]
) -> AccessClaims:
    return await service.authenticate(token)


async def get_current_user(
    service: Service, claims: Annotated[AccessClaims, Depends(get_access_claims)]
) -> User:
    return await service.get_user(claims.user_id)


ClientIp = Annotated[str, Depends(get_client_ip)]
CurrentUser = Annotated[User, Depends(get_current_user)]
