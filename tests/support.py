import re
from dataclasses import dataclass

PASSWORD = "correct horse battery"


@dataclass(frozen=True, slots=True)
class SentEmail:
    to: str
    subject: str
    body: str


class Mailbox:
    def __init__(self) -> None:
        self.sent: list[SentEmail] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append(SentEmail(to, subject, body))

    def last_code(self, to: str) -> str:
        body = next(email.body for email in reversed(self.sent) if email.to == to)
        match = re.search(r"\b\d{6}\b", body)
        assert match is not None
        return match.group()


def bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}
