from typing import Any

from httpx import AsyncClient, Response

from tests.support import PASSWORD, bearer


async def refresh(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post("/auth/refresh", json={"refresh_token": refresh_token})


async def test_refresh_rotates_the_token_pair(
    client: AsyncClient, tokens: dict[str, Any]
) -> None:
    response = await refresh(client, tokens["refresh_token"])

    assert response.status_code == 200
    rotated = response.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]
    profile = await client.get("/me", headers=bearer(rotated["access_token"]))
    assert profile.status_code == 200


async def test_reused_refresh_token_revokes_the_whole_family(
    client: AsyncClient, tokens: dict[str, Any]
) -> None:
    stolen = tokens["refresh_token"]
    latest = (await refresh(client, stolen)).json()["refresh_token"]

    reuse = await refresh(client, stolen)
    assert reuse.status_code == 401
    assert "already used" in reuse.json()["detail"]

    response = await refresh(client, latest)
    assert response.status_code == 401


async def test_reuse_leaves_other_sessions_alone(
    client: AsyncClient, user: str, tokens: dict[str, Any]
) -> None:
    other = await client.post("/auth/login", json={"email": user, "password": PASSWORD})
    await refresh(client, tokens["refresh_token"])
    await refresh(client, tokens["refresh_token"])

    response = await refresh(client, other.json()["refresh_token"])
    assert response.status_code == 200


async def test_logout_revokes_the_access_and_the_refresh_token(
    client: AsyncClient, tokens: dict[str, Any]
) -> None:
    headers = bearer(tokens["access_token"])

    response = await client.post("/auth/logout", headers=headers)
    assert response.status_code == 204

    profile = await client.get("/me", headers=headers)
    assert profile.status_code == 401
    response = await refresh(client, tokens["refresh_token"])
    assert response.status_code == 401


async def test_logout_ends_only_its_own_session(
    client: AsyncClient, user: str, tokens: dict[str, Any]
) -> None:
    other = await client.post("/auth/login", json={"email": user, "password": PASSWORD})

    await client.post("/auth/logout", headers=bearer(tokens["access_token"]))

    profile = await client.get("/me", headers=bearer(other.json()["access_token"]))
    assert profile.status_code == 200
    response = await refresh(client, other.json()["refresh_token"])
    assert response.status_code == 200


async def test_refresh_rejects_an_unknown_token(client: AsyncClient) -> None:
    response = await refresh(client, "made-up")

    assert response.status_code == 401
