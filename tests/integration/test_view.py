"""The view the cards load photos and videos from."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from aiohttp import ClientConnectionError, ClientPayloadError
from multidict import CIMultiDict
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant

from custom_components.immich_slideshow import api
from custom_components.immich_slideshow.api import ImmichClient, ImmichConnectionError, ImmichImage
from custom_components.immich_slideshow.const import DOMAIN

from .conftest import FakeImmich, uid


def path(entry: MockConfigEntry, asset: str = uid(1), size: str = "preview") -> str:
    return f"/api/{DOMAIN}/{entry.entry_id}/{asset}/{size}"


@pytest.mark.parametrize("size", ["thumbnail", "preview", "fullsize"])
async def test_serves_each_size(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, size: str) -> None:
    client = await hass_client()
    response = await client.get(path(loaded_entry, size=size))
    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert await response.read() == immich.image[0]
    assert response.headers["Content-Length"] == str(len(immich.image[0]))
    assert response.headers["Cache-Control"] == "private, max-age=86400"
    method, asset_path, query, _ = immich.requests[-1]
    assert (method, asset_path, query) == ("GET", f"/assets/{uid(1)}/thumbnail", {"size": [size]})


async def test_a_compressed_photo_is_read_whole(hass: HomeAssistant, hass_client, aioclient_mock, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch) -> None:
    # A proxy in front of Immich may compress anyway. The length it gives is then
    # the compressed one, which must not be passed on as the photo's.
    reply = immich._reply

    def compressed(method: str, url, status: int = 200, **kwargs):
        if "headers" in kwargs and url.path.endswith("/thumbnail"):
            kwargs["headers"] = {**kwargs["headers"], "Content-Encoding": "gzip", "Content-Length": "5"}
        return reply(method, url, status, **kwargs)

    monkeypatch.setattr(immich, "_reply", compressed)
    client = await hass_client()
    response = await client.get(path(loaded_entry))
    assert response.status == 200
    assert await response.read() == immich.image[0]
    # Immich is asked not to compress in the first place.
    assert aioclient_mock.mock_calls[-1][3]["Accept-Encoding"] == "identity"


async def test_serves_a_photo_of_unknown_length(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.image_length = False
    client = await hass_client()
    response = await client.get(path(loaded_entry))
    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert await response.read() == immich.image[0]
    assert response.headers["Cache-Control"] == "private, max-age=86400"


async def test_needs_a_login(hass: HomeAssistant, hass_client_no_auth, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    client = await hass_client_no_auth()
    response = await client.get(path(loaded_entry))
    assert response.status == 401
    assert all(p != f"/assets/{uid(1)}/thumbnail" for _, p, _, _ in immich.requests)


async def test_works_through_a_signed_path(hass: HomeAssistant, hass_client_no_auth, hass_admin_user, hass_access_token, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    refresh = hass.auth.async_validate_access_token(hass_access_token)
    signed = async_sign_path(hass, path(loaded_entry), timedelta(seconds=300), refresh_token_id=refresh.id)
    client = await hass_client_no_auth()
    response = await client.get(signed)
    assert response.status == 200


@pytest.mark.parametrize(
    ("asset", "size"),
    [(uid(1), "original"), (uid(1), "../../server/about"), ("not-a-uuid", "preview"), ("..", "preview"), ("not-a-uuid", "video")],
)
async def test_refuses_anything_else(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, asset: str, size: str) -> None:
    client = await hass_client()
    before = len(immich.requests)
    response = await client.get(f"/api/{DOMAIN}/{loaded_entry.entry_id}/{asset}/{size}")
    assert response.status == 404
    assert immich.requests[before:] == []


async def test_unknown_server(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    client = await hass_client()
    response = await client.get(f"/api/{DOMAIN}/someone-else/{uid(1)}/preview")
    assert response.status == 404


async def test_unloaded_server(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    await hass.config_entries.async_unload(loaded_entry.entry_id)
    client = await hass_client()
    assert (await client.get(path(loaded_entry))).status == 404


@pytest.mark.parametrize(
    ("setup", "status"),
    [
        (lambda immich: immich.status.update({"/assets": 400}), 502),
        (lambda immich: immich.status.update({"/assets": 404}), 404),
        (lambda immich: immich.status.update({"/assets": 500}), 502),
        (lambda immich: immich.errors.update({"/assets": ClientConnectionError()}), 502),
        (lambda immich: immich.errors.update({"/assets": TimeoutError()}), 502),
        # An address that redirects is never followed.
        (lambda immich: immich.status.update({"/assets": 302}), 502),
        # Only a photo is passed on, never a page or a drawing that could carry a script.
        (lambda immich: setattr(immich, "image", (b"<html>", "text/html")), 502),
        (lambda immich: setattr(immich, "image", (b"<svg/>", "image/svg+xml")), 502),
    ],
)
async def test_passes_on_failures(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, setup, status: int) -> None:
    setup(immich)
    client = await hass_client()
    response = await client.get(path(loaded_entry))
    assert response.status == status


async def test_refuses_an_oversized_photo(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_IMAGE_BYTES", 1024)
    monkeypatch.setattr(api, "IMAGE_CHUNK", 256)
    immich.image = (b"x" * 2048, "image/jpeg")
    client = await hass_client()
    response = await client.get(path(loaded_entry))
    assert response.status == 502
    immich.image = (b"x" * 1024, "image/jpeg")
    response = await client.get(path(loaded_entry))
    assert response.status == 200
    assert len(await response.read()) == 1024


async def test_refuses_an_oversized_photo_of_unknown_length(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "MAX_IMAGE_BYTES", 1024)
    monkeypatch.setattr(api, "IMAGE_CHUNK", 256)
    immich.image_length = False
    immich.image = (b"x" * 2048, "image/jpeg")
    client = await hass_client()
    response = await client.get(path(loaded_entry))
    assert response.status == 502
    assert await response.read() == b""


async def test_a_photo_cut_off_by_immich_does_not_pass_for_whole(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"x" * 1024
        raise ImmichConnectionError("Immich hung up")

    closed = []

    @asynccontextmanager
    async def open_image(self, asset_id: str, size: str) -> AsyncIterator[ImmichImage]:
        try:
            yield ImmichImage("image/jpeg", 4096, chunks())
        finally:
            closed.append(True)

    monkeypatch.setattr(ImmichClient, "async_open_image", open_image)
    client = await hass_client()
    response = await client.get(path(loaded_entry))
    assert response.status == 200
    with pytest.raises(ClientPayloadError):
        await response.read()
    assert closed == [True]


async def test_serves_a_whole_video(hass: HomeAssistant, hass_client, aioclient_mock, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    client = await hass_client()
    response = await client.get(path(loaded_entry, size="video"))
    assert response.status == 200
    assert response.content_type == "video/mp4"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Length"] == "1024"
    assert response.headers["Cache-Control"] == "private, max-age=86400"
    assert await response.read() == immich.video[0]
    method, asset_path, query, _ = immich.requests[-1]
    assert (method, asset_path, query) == ("GET", f"/assets/{uid(1)}/video/playback", {})
    assert "Range" not in aioclient_mock.mock_calls[-1][3]


@pytest.mark.parametrize(
    ("asked", "sent", "content_range"),
    [("bytes=0-1", (0, 2), "bytes 0-1/1024"), ("bytes=100-299", (100, 300), "bytes 100-299/1024"), ("bytes=1000-", (1000, 1024), "bytes 1000-1023/1024")],
)
async def test_serves_the_part_of_a_video_the_browser_asks_for(
    hass: HomeAssistant, hass_client, aioclient_mock, immich: FakeImmich, loaded_entry: MockConfigEntry, asked: str, sent: tuple[int, int], content_range: str
) -> None:
    client = await hass_client()
    response = await client.get(path(loaded_entry, size="video"), headers={"Range": asked})
    assert response.status == 206
    assert response.headers["Content-Range"] == content_range
    assert response.headers["Content-Length"] == str(sent[1] - sent[0])
    assert await response.read() == immich.video[0][slice(*sent)]
    # Immich was asked for that part only.
    assert aioclient_mock.mock_calls[-1][3]["Range"] == asked


async def test_a_video_needs_a_login(hass: HomeAssistant, hass_client_no_auth, hass_admin_user, hass_access_token, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    client = await hass_client_no_auth()
    response = await client.get(path(loaded_entry, size="video"))
    assert response.status == 401
    assert all(not p.endswith("/video/playback") for _, p, _, _ in immich.requests)
    refresh = hass.auth.async_validate_access_token(hass_access_token)
    signed = async_sign_path(hass, path(loaded_entry, size="video"), timedelta(seconds=300), refresh_token_id=refresh.id)
    response = await client.get(signed, headers={"Range": "bytes=0-9"})
    assert response.status == 206
    assert len(await response.read()) == 10


@pytest.mark.parametrize(
    ("setup", "status"),
    [
        (lambda immich: immich.status.update({"/assets": 400}), 502),
        (lambda immich: immich.status.update({"/assets": 404}), 404),
        (lambda immich: immich.status.update({"/assets": 500}), 502),
        (lambda immich: immich.errors.update({"/assets": ClientConnectionError()}), 502),
        (lambda immich: immich.status.update({"/assets": 302}), 502),
        # Only a video is passed on, never a page that would run in Home Assistant's name.
        (lambda immich: setattr(immich, "video", (b"<html>", "text/html")), 502),
    ],
)
async def test_passes_on_video_failures(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, setup, status: int) -> None:
    setup(immich)
    client = await hass_client()
    response = await client.get(path(loaded_entry, size="video"))
    assert response.status == status


async def test_refuses_a_compressed_video(hass: HomeAssistant, hass_client, aioclient_mock, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch) -> None:
    client = await hass_client()
    assert (await client.get(path(loaded_entry, size="video"))).status == 200
    # Immich is asked not to compress, as the browser is told the length Immich gives.
    assert aioclient_mock.mock_calls[-1][3]["Accept-Encoding"] == "identity"
    reply = immich._reply

    def compressed(method: str, url, status: int = 200, **kwargs):
        if "headers" in kwargs:
            kwargs["headers"] = {**kwargs["headers"], "Content-Encoding": "gzip"}
        return reply(method, url, status, **kwargs)

    monkeypatch.setattr(immich, "_reply", compressed)
    assert (await client.get(path(loaded_entry, size="video"))).status == 502


async def test_a_video_cut_off_by_immich_does_not_pass_for_whole(hass: HomeAssistant, hass_client, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch) -> None:
    class Content:
        async def iter_chunked(self, size: int):
            yield b"x" * 1024
            raise ClientPayloadError("Immich hung up")

    class CutOff:
        status = 200
        headers = CIMultiDict({"Content-Type": "video/mp4", "Content-Length": "4096"})
        content = Content()
        closed = False

        def close(self) -> None:
            self.closed = True

    upstream = CutOff()

    async def video(self, asset_id: str, byte_range: str | None = None) -> CutOff:
        return upstream

    monkeypatch.setattr(ImmichClient, "async_video", video)
    client = await hass_client()
    response = await client.get(path(loaded_entry, size="video"))
    assert response.status == 200
    with pytest.raises(ClientPayloadError):
        await response.read()
    assert upstream.closed


@pytest.mark.parametrize("size", ["preview", "video"])
async def test_refuses_a_user_who_is_not_an_admin(hass: HomeAssistant, hass_client, hass_client_no_auth, hass_read_only_access_token, immich: FakeImmich, loaded_entry: MockConfigEntry, size: str) -> None:
    before = len(immich.requests)
    client = await hass_client(hass_read_only_access_token)
    assert (await client.get(path(loaded_entry, size=size))).status == 403
    # A link the user signed carries the user, so it's refused too.
    refresh = hass.auth.async_validate_access_token(hass_read_only_access_token)
    signed = async_sign_path(hass, path(loaded_entry, size=size), timedelta(seconds=300), refresh_token_id=refresh.id)
    assert (await (await hass_client_no_auth()).get(signed)).status == 403
    assert len(immich.requests) == before
