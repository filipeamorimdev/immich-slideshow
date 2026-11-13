"""The diagnostics download for a bug report."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.immich_slideshow.diagnostics import async_get_config_entry_diagnostics

from .conftest import API_KEY, URL, FakeImmich


async def test_leaves_out_the_key_the_address_and_the_names(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    immich.status["/queues"] = 403
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    text = str(diagnostics)
    assert API_KEY not in text
    assert URL not in text
    assert "immich.local" not in text
    # The counts are there. The countries and camera makes themselves are not.
    assert diagnostics["statistics"]["metadata"]["countries"] == 3
    assert "Portugal" not in text
    assert "Apple" not in text

    assert diagnostics["entry"]["verify_ssl"] is True
    assert diagnostics["last_update_success"] is True
    assert diagnostics["left_out"] == ["queues"]
    assert diagnostics["statistics"]["about"] == {"version": "v3.3.6"}
    assert diagnostics["statistics"]["assets"]["photos"] == 22363
