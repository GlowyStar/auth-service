from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.errors import EmailAlreadyRegistered, InvalidCode
from auth_service.mailer import EmailSender
from auth_service.models import User
from auth_service.redis_stores import CODE_TTL_SECONDS, CodePurpose, OneTimeCodes
from auth_service.repositories import UserRepository
from auth_service.security import hash_password
from auth_service.settings import Settings

CODE_EMAIL_SUBJECTS = {
    CodePurpose.CONFIRM_EMAIL: "Confirm your email",
}


class AuthService:
    def __init__(
        self, session: AsyncSession, redis: Redis, sender: EmailSender, settings: Settings
    ) -> None:
        secret = settings.secret_key.get_secret_value()
        self._session = session
        self._users = UserRepository(session)
        self._codes = OneTimeCodes(redis, secret)
        self._sender = sender

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

    async def _send_code(self, purpose: CodePurpose, email: str) -> None:
        code = await self._codes.issue(purpose, email)
        body = f"Your code is {code}. It expires in {CODE_TTL_SECONDS // 60} minutes."
        await self._sender.send(email, CODE_EMAIL_SUBJECTS[purpose], body)
