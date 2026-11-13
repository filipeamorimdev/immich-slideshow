"""The Immich client, against real servers on this machine."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re

from aiohttp import ClientSession, web
import pytest

from custom_components.immich_slideshow import api
from custom_components.immich_slideshow.api import READ_POSTS, ImmichClient, ImmichRedirectError

from .conftest import API_KEY, uid


@pytest.mark.parametrize("status", [301, 302, 307, 308])
async def test_the_key_never_follows_a_redirect(socket_enabled, aiohttp_server, status: int) -> None:
    arrived: list[str | None] = []

    async def elsewhere(request: web.Request) -> web.Response:
        arrived.append(request.headers.get("x-api-key"))
        return web.json_response({"permissions": ["all"]})

    other = web.Application()
    other.router.add_route("*", "/{path:.*}", elsewhere)
    other_server = await aiohttp_server(other)

    async def redirect(request: web.Request) -> web.Response:
        return web.Response(status=status, headers={"Location": str(other_server.make_url(request.path))})

    immich = web.Application()
    immich.router.add_route("*", "/{path:.*}", redirect)
    server = await aiohttp_server(immich)

    async with ClientSession() as session:
        client = ImmichClient(session, str(server.make_url("")), API_KEY)
        with pytest.raises(ImmichRedirectError):
            await client.async_missing_permissions()
        with pytest.raises(ImmichRedirectError):
            await client.async_random_photos(1)
        with pytest.raises(ImmichRedirectError):
            async with client.async_open_image(uid(1), "preview"):
                pass
        with pytest.raises(ImmichRedirectError):
            await client.async_image(uid(1), "preview")
        with pytest.raises(ImmichRedirectError):
            await client.async_video(uid(1))
    assert arrived == []


async def test_every_request_carries_the_key_and_only_reads(socket_enabled, aiohttp_server) -> None:
    arrived: list[tuple[str, str, str | None]] = []
    found = {"assets": {"items": [{"id": uid(1), "type": "IMAGE"}], "nextCursor": None}}

    async def answer(request: web.Request) -> web.Response:
        path = request.path.removeprefix("/api")
        arrived.append((request.method, path, request.headers.get("x-api-key")))
        if path.endswith("/thumbnail"):
            return web.Response(body=b"\xff\xd8 fake jpeg", content_type="image/jpeg")
        if path.endswith("/video/playback"):
            return web.Response(body=b"fake video", content_type="video/mp4")
        answers: dict[str, object] = {
            "/api-keys/me": {"permissions": ["all"]},
            "/albums": [],
            "/search/metadata": found,
            "/search/smart": found,
            "/search/random": [],
            "/search/statistics": {"total": 0},
            "/memories": [{"memoryAt": "2020-01-01T00:00:00.000Z", "assets": [{"id": uid(1)}]}],
        }
        return web.json_response(answers.get(path, {}))

    immich = web.Application()
    immich.router.add_route("*", "/{path:.*}", answer)
    server = await aiohttp_server(immich)

    async with ClientSession() as session:
        client = ImmichClient(session, str(server.make_url("")), API_KEY)
        await client.async_missing_permissions()
        await client.async_albums()
        await client.async_album_photos(uid(2), videos=True, people=True)
        await client.async_random_photos(1)
        await client.async_search_photos("snow", 1, people=True)
        await client.async_on_this_day(date(2026, 1, 1))
        await client.async_get("/server/about")
        await client.async_count({})
        await client.async_image(uid(1), "preview")
        (await client.async_video(uid(1), "bytes=0-3")).close()

    assert arrived
    assert {key for _, _, key in arrived} == {API_KEY}
    assert {method for method, _, _ in arrived} == {"GET", "POST"}
    # Every POST is one of the searches, and every search on the list is still used.
    assert {path for method, path, _ in arrived if method == "POST"} == READ_POSTS


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PUT", "/albums/x/assets"),
        ("PATCH", "/albums/x"),
        ("DELETE", "/assets"),
        ("POST", "/albums"),
        ("POST", "/assets"),
        ("post", "/search/random"),
    ],
)
async def test_a_request_that_could_change_immich_is_never_sent(
    socket_enabled, aiohttp_server, method: str, path: str
) -> None:
    arrived: list[str] = []

    async def answer(request: web.Request) -> web.Response:
        arrived.append(request.method)
        return web.json_response({})

    immich = web.Application()
    immich.router.add_route("*", "/{path:.*}", answer)
    server = await aiohttp_server(immich)

    async with ClientSession() as session:
        client = ImmichClient(session, str(server.make_url("")), API_KEY)
        with pytest.raises(RuntimeError):
            await client._request(method, path, json={})
    assert arrived == []


def test_the_client_has_no_other_way_to_reach_immich() -> None:
    # Photos and videos are opened with a GET of their own. Everything else goes through
    # _request, which refuses what isn't a read.
    source = Path(api.__file__).read_text()
    assert sorted(set(re.findall(r"_session\.(\w+)", source))) == ["get", "request"]
