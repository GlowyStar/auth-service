from typing import Any

from httpx import AsyncClient

from tests.support import PASSWORD, Mailbox

NEW_PASSWORD = "a brand new passphrase"


async def test_password_reset_changes_the_password_and_ends_sessions(
    client: AsyncClient, mailbox: Mailbox, user: str, tokens: dict[str, Any]
) -> None:
    response = await client.post("/auth/password/forgot", json={"email": user})
    assert response.status_code == 202

    reset = {"email": user, "code": mailbox.last_code(user), "new_password": NEW_PASSWORD}
    response = await client.post("/auth/password/reset", json=reset)
    assert response.status_code == 204

    old_login = await client.post("/auth/login", json={"email": user, "password": PASSWORD})
    new_login = await client.post(
        "/auth/login", json={"email": user, "password": NEW_PASSWORD}
    )
    assert (old_login.status_code, new_login.status_code) == (401, 200)

    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


async def test_password_reset_rejects_a_wrong_code(
    client: AsyncClient, mailbox: Mailbox, user: str
) -> None:
    await client.post("/auth/password/forgot", json={"email": user})
    code = mailbox.last_code(user)
    wrong_code = "000000" if code != "000000" else "111111"

    reset = {"email": user, "code": wrong_code, "new_password": NEW_PASSWORD}
    response = await client.post("/auth/password/reset", json=reset)

    assert response.status_code == 400


async def test_confirmation_code_does_not_reset_the_password(
    client: AsyncClient, mailbox: Mailbox
) -> None:
    email = "zoe@example.com"
    await client.post("/auth/signup", json={"email": email, "password": PASSWORD})

    reset = {"email": email, "code": mailbox.last_code(email), "new_password": NEW_PASSWORD}
    response = await client.post("/auth/password/reset", json=reset)

    assert response.status_code == 400


async def test_forgot_password_for_an_unknown_email_sends_nothing(
    client: AsyncClient, mailbox: Mailbox
) -> None:
    response = await client.post("/auth/password/forgot", json={"email": "nobody@example.com"})

    assert response.status_code == 202
    assert mailbox.sent == []
