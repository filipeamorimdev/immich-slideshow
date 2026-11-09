"""The image view the cards load photos from."""

from __future__ import annotations

from datetime import timedelta

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant

from custom_components.immich_slideshow import api
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
    assert response.headers["Cache-Control"] == "private, max-age=86400"
    method, asset_path, query, _ = immich.requests[-1]
    assert (method, asset_path, query) == ("GET", f"/assets/{uid(1)}/thumbnail", {"size": [size]})


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
    [(uid(1), "original"), (uid(1), "../../server/about"), ("not-a-uuid", "preview"), ("..", "preview")],
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
        (lambda immich: setattr(immich, "image", (b"<html>", "text/html")), 502),
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
