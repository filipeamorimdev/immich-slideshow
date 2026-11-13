"""Setting up, reauthenticating and reconfiguring the connection."""

from __future__ import annotations

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.immich_slideshow.config_flow import normalize_url
from custom_components.immich_slideshow.const import DOMAIN

from .conftest import API_KEY, URL, FakeImmich

INPUT = {CONF_URL: f"{URL}/api/", CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True}


async def start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://10.0.0.10:2283", "http://10.0.0.10:2283"),
        (" http://10.0.0.10:2283/ ", "http://10.0.0.10:2283"),
        ("https://photos.example.com/api", "https://photos.example.com"),
        ("https://photos.example.com/immich/api/", "https://photos.example.com/immich"),
        ("10.0.0.10:2283", None),
        ("ftp://10.0.0.10", None),
        ("http://", None),
    ],
)
def test_normalize_url(url: str, expected: str | None) -> None:
    assert normalize_url(url) == expected


async def test_creates_an_entry(hass: HomeAssistant, immich: FakeImmich) -> None:
    flow_id = await start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "immich.local"
    assert result["data"] == {CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True}
    assert result["result"].unique_id == URL


async def test_accepts_a_key_with_exactly_the_needed_permissions(hass: HomeAssistant, immich: FakeImmich) -> None:
    immich.permissions = ["album.read", "asset.read", "asset.view", "memory.read"]
    result = await hass.config_entries.flow.async_configure(await start(hass), INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        (lambda immich: immich.status.update({"/api-keys": 401}), "invalid_auth"),
        (lambda immich: immich.errors.update({"/api-keys": ClientConnectionError()}), "cannot_connect"),
        (lambda immich: immich.errors.update({"/api-keys": TimeoutError()}), "cannot_connect"),
        (lambda immich: immich.status.update({"/api-keys": 500}), "unknown"),
        (lambda immich: immich.status.update({"/api-keys": 302}), "redirected"),
    ],
)
async def test_reports_errors_and_recovers(hass: HomeAssistant, immich: FakeImmich, setup, error: str) -> None:
    flow_id = await start(hass)
    setup(immich)
    result = await hass.config_entries.flow.async_configure(flow_id, INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    immich.status.clear()
    immich.errors.clear()
    result = await hass.config_entries.flow.async_configure(flow_id, INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_names_the_missing_permissions(hass: HomeAssistant, immich: FakeImmich) -> None:
    immich.permissions = ["album.read", "asset.read"]
    result = await hass.config_entries.flow.async_configure(await start(hass), INPUT)
    assert result["errors"] == {"base": "missing_permissions"}
    assert result["description_placeholders"]["missing"] == "asset.view, memory.read"


async def test_rejects_an_address_without_a_scheme(hass: HomeAssistant, immich: FakeImmich) -> None:
    result = await hass.config_entries.flow.async_configure(
        await start(hass), {**INPUT, CONF_URL: "10.0.0.10:2283"}
    )
    assert result["errors"] == {CONF_URL: "invalid_url"}
    assert immich.requests == []


async def test_never_puts_the_key_back_in_the_form(hass: HomeAssistant, immich: FakeImmich) -> None:
    immich.status["/api-keys"] = 401
    result = await hass.config_entries.flow.async_configure(await start(hass), INPUT)
    for field in result["data_schema"].schema:
        assert (field.description or {}).get("suggested_value") != API_KEY
    assert API_KEY not in str(result)


async def test_refuses_the_same_server_twice(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(await start(hass), INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_stores_the_new_key(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    immich.status["/api-keys"] = 401
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}
    immich.status.clear()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_KEY: "new-key"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert config_entry.data[CONF_API_KEY] == "new-key"
    assert config_entry.data[CONF_URL] == URL


async def test_reconfigure_changes_the_address(hass: HomeAssistant, immich: FakeImmich, aioclient_mock, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    import re

    aioclient_mock.request("get", re.compile(r"^https://photos\.example\.com/api/"), side_effect=immich.handle)
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "https://photos.example.com/", CONF_API_KEY: "other", CONF_VERIFY_SSL: False}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert config_entry.unique_id == "https://photos.example.com"
    assert config_entry.title == "photos.example.com"
    assert config_entry.data == {CONF_URL: "https://photos.example.com", CONF_API_KEY: "other", CONF_VERIFY_SSL: False}


async def test_reconfigure_keeps_the_same_address(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**INPUT, CONF_API_KEY: "rotated"})
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert config_entry.data[CONF_API_KEY] == "rotated"


async def test_reconfigure_refuses_another_entrys_server(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    other = MockConfigEntry(domain=DOMAIN, unique_id="http://other:2283", data={**INPUT, CONF_URL: "http://other:2283"})
    other.add_to_hass(hass)
    result = await other.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
