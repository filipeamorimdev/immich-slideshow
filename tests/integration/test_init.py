"""Setting up a server, and serving the cards."""

from __future__ import annotations

from unittest.mock import patch

from aiohttp import ClientConnectionError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.immich_slideshow.const import CARD_URL, DOMAIN, VERSION
from custom_components.immich_slideshow.frontend import is_legacy_resource

from .conftest import FakeImmich


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_loads_and_unloads(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert immich.requests[0][1] == "/api-keys/me"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_asks_for_a_new_key_when_refused(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    immich.status["/api-keys"] = 401
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_asks_for_a_new_key_when_a_permission_is_gone(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    immich.permissions = ["album.read"]
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == SOURCE_REAUTH


async def test_retries_when_immich_is_down(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    immich.errors["/api-keys"] = ClientConnectionError()
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_serves_the_cards(hass: HomeAssistant, hass_client_no_auth, immich: FakeImmich) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client_no_auth()
    response = await client.get(CARD_URL)
    assert response.status == 200
    text = await response.text()
    assert f"const IS_VERSION = '{VERSION}'" in text
    for card in ("immich-slideshow-card", "immich-magic-card", "immich-on-this-day-card"):
        assert f"'{card}'" in text


async def test_loads_the_cards_as_a_dashboard_resource_only(hass: HomeAssistant, immich: FakeImmich) -> None:
    # An extra module can run before the frontend's element registry is in place,
    # and then the dashboard can't find the cards.
    assert await async_setup_component(hass, "lovelace", {})
    assert await async_setup_component(hass, DOMAIN, {})
    assert f"{CARD_URL}?v={VERSION}" not in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_falls_back_to_an_extra_module_for_yaml_dashboards(hass: HomeAssistant, immich: FakeImmich) -> None:
    with patch("custom_components.immich_slideshow.frontend._async_resources", return_value=None):
        assert await async_setup_component(hass, DOMAIN, {})
    assert f"{CARD_URL}?v={VERSION}" in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_registers_the_dashboard_resource_and_replaces_old_ones(hass: HomeAssistant, immich: FakeImmich) -> None:
    assert await async_setup_component(hass, "lovelace", {})
    resources = hass.data["lovelace"].resources
    await resources.async_load()
    resources.loaded = True
    await resources.async_create_item({"res_type": "module", "url": "/local/immich-slideshow-card.js"})
    await resources.async_create_item({"res_type": "module", "url": f"{CARD_URL}?v=0.0.1"})
    await resources.async_create_item({"res_type": "module", "url": "/local/other-card.js"})

    assert await async_setup_component(hass, DOMAIN, {})
    urls = sorted(item["url"] for item in resources.async_items())
    assert urls == sorted([f"{CARD_URL}?v={VERSION}", "/local/other-card.js"])


async def test_adds_the_dashboard_resource_once(hass: HomeAssistant, immich: FakeImmich) -> None:
    assert await async_setup_component(hass, "lovelace", {})
    assert await async_setup_component(hass, DOMAIN, {})
    resources = hass.data["lovelace"].resources
    assert [item["url"] for item in resources.async_items()] == [f"{CARD_URL}?v={VERSION}"]


def test_recognizes_the_standalone_card() -> None:
    assert is_legacy_resource("/local/immich-slideshow-card.js")
    assert is_legacy_resource("/local/immich-slideshow-card.js?v=0.4.0")
    assert is_legacy_resource("/hacsfiles/immich-slideshow-card/immich-slideshow-card.js")
    assert not is_legacy_resource(f"{CARD_URL}?v={VERSION}")
    assert not is_legacy_resource("/local/immich-slideshow-card.js.bak")
