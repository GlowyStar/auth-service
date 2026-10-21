class DomainError(Exception):
    detail = "request rejected"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)


class EmailAlreadyRegistered(DomainError):
    detail = "email is already registered"


class InvalidCode(DomainError):
    detail = "code is invalid or expired"


class CodeResendTooSoon(DomainError):
    detail = "a code was sent recently, try again in a minute"


class InvalidCredentials(DomainError):
    detail = "email or password is wrong"


class EmailNotConfirmed(DomainError):
    detail = "email is not confirmed yet"


class TooManyLoginAttempts(DomainError):
    detail = "too many failed logins, try again later"


class InvalidToken(DomainError):
    detail = "token is invalid or expired"


class RefreshTokenReused(DomainError):
    detail = "refresh token was already used, the session is revoked"
