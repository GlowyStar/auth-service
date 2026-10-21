from email.message import EmailMessage
from typing import Protocol

import aiosmtplib

from auth_service.settings import Settings


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        print(f"To: {to}\nSubject: {subject}\n\n{body}\n", flush=True)


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        password = self._settings.smtp_password
        await aiosmtplib.send(
            message,
            hostname=self._settings.smtp_host,
            port=self._settings.smtp_port,
            username=self._settings.smtp_username,
            password=password.get_secret_value() if password else None,
        )


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()
