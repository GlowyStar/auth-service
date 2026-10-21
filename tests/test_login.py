from httpx import ASGITransport, AsyncClient

from auth_service.main import app
from tests.support import PASSWORD, bearer


async def test_login_with_json_and_with_the_oauth2_form(
    client: AsyncClient, user: str
) -> None:
    json_login = await client.post("/auth/login", json={"email": user, "password": PASSWORD})
    form_login = await client.post(
        "/auth/token", data={"username": user, "password": PASSWORD}
    )

    for response in (json_login, form_login):
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        profile = await client.get("/me", headers=bearer(response.json()["access_token"]))
        assert profile.json()["email"] == user


async def test_login_rejects_a_wrong_password(client: AsyncClient, user: str) -> None:
    response = await client.post("/auth/login", json={"email": user, "password": "wrong pass"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_failed_logins_are_limited_per_email(client: AsyncClient, user: str) -> None:
    for _ in range(5):
        response = await client.post(
            "/auth/login", json={"email": user, "password": "wrong pass"}
        )
        assert response.status_code == 401

    response = await client.post("/auth/login", json={"email": user, "password": PASSWORD})
    assert response.status_code == 429


async def test_failed_logins_are_limited_per_ip(client: AsyncClient, user: str) -> None:
    for index in range(20):
        credentials = {"email": f"guess{index}@example.com", "password": "wrong pass"}
        response = await client.post("/auth/login", json=credentials)
        assert response.status_code == 401

    response = await client.post("/auth/login", json={"email": user, "password": PASSWORD})
    assert response.status_code == 429

    other_ip = ASGITransport(app=app, client=("203.0.113.7", 40000))
    async with AsyncClient(transport=other_ip, base_url="http://test") as other_client:
        response = await other_client.post(
            "/auth/login", json={"email": user, "password": PASSWORD}
        )
    assert response.status_code == 200
