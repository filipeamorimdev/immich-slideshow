"""The device every entity of one Immich server belongs to."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Point an entity at its server's device."""
    return DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})


@callback
def async_update_device(hass: HomeAssistant, entry: ConfigEntry, version: str | None) -> None:
    """Create or update the server's device, a service with no hardware."""
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Immich",
        manufacturer="Immich",
        model="Immich server",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=entry.data[CONF_URL],
    )
    if version and device.sw_version != version:
        registry.async_update_device(device.id, sw_version=version)
