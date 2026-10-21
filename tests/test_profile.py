from typing import Any

from httpx import AsyncClient

from tests.support import bearer


async def test_profile_requires_a_valid_access_token(client: AsyncClient) -> None:
    missing = await client.get("/me")
    forged = await client.get("/me", headers=bearer("not.a.jwt"))

    assert (missing.status_code, forged.status_code) == (401, 401)


async def test_profile_read_and_update(
    client: AsyncClient, user: str, tokens: dict[str, Any]
) -> None:
    headers = bearer(tokens["access_token"])

    response = await client.patch("/me", json={"full_name": "Ann Lee"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Ann Lee"

    response = await client.get("/me", headers=headers)
    assert response.json()["email"] == user
    assert response.json()["full_name"] == "Ann Lee"
    assert response.json()["is_active"] is True
