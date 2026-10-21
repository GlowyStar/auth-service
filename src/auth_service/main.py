from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from auth_service import errors
from auth_service.api import auth, profile
from auth_service.mailer import build_email_sender
from auth_service.settings import get_settings

ERROR_STATUS_CODES: dict[type[errors.DomainError], int] = {
    errors.EmailAlreadyRegistered: status.HTTP_409_CONFLICT,
    errors.InvalidCode: status.HTTP_400_BAD_REQUEST,
    errors.CodeResendTooSoon: status.HTTP_429_TOO_MANY_REQUESTS,
    errors.InvalidCredentials: status.HTTP_401_UNAUTHORIZED,
    errors.EmailNotConfirmed: status.HTTP_403_FORBIDDEN,
    errors.TooManyLoginAttempts: status.HTTP_429_TOO_MANY_REQUESTS,
    errors.InvalidToken: status.HTTP_401_UNAUTHORIZED,
    errors.RefreshTokenReused: status.HTTP_401_UNAUTHORIZED,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.redis = redis
    app.state.email_sender = build_email_sender(settings)
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


app = FastAPI(title="auth-service", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(profile.router)


@app.exception_handler(errors.DomainError)
async def handle_domain_error(request: Request, error: errors.DomainError) -> JSONResponse:
    status_code = ERROR_STATUS_CODES[type(error)]
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse({"detail": str(error)}, status_code=status_code, headers=headers)
