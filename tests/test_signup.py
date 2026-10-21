from httpx import AsyncClient

from tests.support import PASSWORD, Mailbox


async def test_sign_up_and_confirm_activates_the_account(
    client: AsyncClient, mailbox: Mailbox
) -> None:
    response = await client.post(
        "/auth/signup", json={"email": "Ann@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "ann@example.com"
    assert response.json()["is_active"] is False

    credentials = {"email": "ann@example.com", "password": PASSWORD}
    response = await client.post("/auth/login", json=credentials)
    assert response.status_code == 403

    code = mailbox.last_code("ann@example.com")
    response = await client.post(
        "/auth/confirm", json={"email": "ann@example.com", "code": code}
    )
    assert response.status_code == 204

    response = await client.post("/auth/login", json=credentials)
    assert response.status_code == 200


async def test_sign_up_rejects_a_registered_email(client: AsyncClient, user: str) -> None:
    response = await client.post("/auth/signup", json={"email": user, "password": PASSWORD})

    assert response.status_code == 409


async def test_wrong_codes_burn_the_code_after_five_attempts(
    client: AsyncClient, mailbox: Mailbox
) -> None:
    email = "bob@example.com"
    await client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    code = mailbox.last_code(email)
    wrong_code = "000000" if code != "000000" else "111111"

    for _ in range(5):
        response = await client.post(
            "/auth/confirm", json={"email": email, "code": wrong_code}
        )
        assert response.status_code == 400

    response = await client.post("/auth/confirm", json={"email": email, "code": code})
    assert response.status_code == 400


async def test_code_is_single_use(client: AsyncClient, mailbox: Mailbox) -> None:
    email = "eve@example.com"
    await client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    payload = {"email": email, "code": mailbox.last_code(email)}

    first = await client.post("/auth/confirm", json=payload)
    second = await client.post("/auth/confirm", json=payload)

    assert (first.status_code, second.status_code) == (204, 400)


async def test_resend_waits_for_the_cooldown(client: AsyncClient, mailbox: Mailbox) -> None:
    email = "kim@example.com"
    await client.post("/auth/signup", json={"email": email, "password": PASSWORD})

    response = await client.post("/auth/confirm/resend", json={"email": email})

    assert response.status_code == 429
    assert len(mailbox.sent) == 1


async def test_resend_to_an_unknown_email_sends_nothing(
    client: AsyncClient, mailbox: Mailbox
) -> None:
    response = await client.post("/auth/confirm/resend", json={"email": "nobody@example.com"})

    assert response.status_code == 202
    assert mailbox.sent == []
