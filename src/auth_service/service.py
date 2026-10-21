import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.errors import (
    EmailAlreadyRegistered,
    EmailNotConfirmed,
    InvalidCode,
    InvalidCredentials,
    InvalidToken,
)
from auth_service.mailer import EmailSender
from auth_service.models import RefreshToken, User
from auth_service.redis_stores import (
    CODE_TTL_SECONDS,
    CodePurpose,
    LoginAttempts,
    OneTimeCodes,
)
from auth_service.repositories import RefreshTokenRepository, UserRepository
from auth_service.security import (
    DUMMY_PASSWORD_HASH,
    AccessClaims,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from auth_service.settings import Settings

CODE_EMAIL_SUBJECTS = {
    CodePurpose.CONFIRM_EMAIL: "Confirm your email",
}


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self, session: AsyncSession, redis: Redis, sender: EmailSender, settings: Settings
    ) -> None:
        secret = settings.secret_key.get_secret_value()
        self._session = session
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)
        self._codes = OneTimeCodes(redis, secret)
        self._login_attempts = LoginAttempts(redis)
        self._sender = sender
        self._secret = secret
        self._access_ttl = timedelta(seconds=settings.access_token_ttl_seconds)
        self._refresh_ttl = timedelta(days=settings.refresh_token_ttl_days)

    async def sign_up(self, email: str, password: str) -> User:
        password_hash = await hash_password(password)
        try:
            user = await self._users.add(email, password_hash)
        except IntegrityError as error:
            raise EmailAlreadyRegistered from error
        await self._session.commit()

        await self._send_code(CodePurpose.CONFIRM_EMAIL, email)
        return user

    async def confirm_email(self, email: str, code: str) -> None:
        await self._codes.consume(CodePurpose.CONFIRM_EMAIL, email, code)
        user = await self._users.get_by_email(email)
        if user is None:
            raise InvalidCode
        user.is_active = True
        await self._session.commit()

    async def resend_confirmation(self, email: str) -> None:
        await self._codes.start_resend_cooldown(CodePurpose.CONFIRM_EMAIL, email)
        user = await self._users.get_by_email(email)

        user_awaits_confirmation = user is not None and not user.is_active
        if user_awaits_confirmation:
            await self._send_code(CodePurpose.CONFIRM_EMAIL, email)

    async def login(self, email: str, password: str, client_ip: str) -> TokenPair:
        await self._login_attempts.ensure_allowed(email, client_ip)
        user = await self._users.get_by_email(email)
        stored_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
        password_matches = await verify_password(password, stored_hash)

        if user is None or not password_matches:
            await self._login_attempts.record_failure(email, client_ip)
            raise InvalidCredentials
        if not user.is_active:
            raise EmailNotConfirmed

        await self._login_attempts.clear(email)
        return await self._issue_tokens(user.id, family_id=uuid4())

    async def authenticate(self, access_token: str) -> AccessClaims:
        return decode_access_token(access_token, self._secret)

    async def get_user(self, user_id: UUID) -> User:
        user = await self._users.get(user_id)
        if user is None:
            raise InvalidToken
        return user

    async def update_profile(self, user: User, full_name: str | None) -> User:
        user.full_name = full_name
        await self._session.commit()
        return user

    async def _issue_tokens(self, user_id: UUID, family_id: UUID) -> TokenPair:
        refresh_token = secrets.token_urlsafe(32)
        self._refresh_tokens.add(
            RefreshToken(
                user_id=user_id,
                family_id=family_id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=datetime.now(UTC) + self._refresh_ttl,
            )
        )
        await self._session.commit()

        access_token = create_access_token(user_id, family_id, self._secret, self._access_ttl)
        return TokenPair(access_token, refresh_token, int(self._access_ttl.total_seconds()))

    async def _send_code(self, purpose: CodePurpose, email: str) -> None:
        code = await self._codes.issue(purpose, email)
        body = f"Your code is {code}. It expires in {CODE_TTL_SECONDS // 60} minutes."
        await self._sender.send(email, CODE_EMAIL_SUBJECTS[purpose], body)
