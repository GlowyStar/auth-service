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
