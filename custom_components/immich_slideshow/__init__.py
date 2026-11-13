"""Immich Slideshow: photo cards and statistics from an Immich server."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .api import ImmichAuthError, ImmichClient, ImmichError
from .const import DOMAIN
from .coordinator import ImmichStatsCoordinator
from .entity import async_update_device
from .frontend import async_add_resource, async_register_frontend, async_remove_resource
from .photo_lists import KEEP, PhotoLists
from .view import ImmichImageView
from .websocket import async_register_commands

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.IMAGE, Platform.SENSOR, Platform.UPDATE]


@dataclass
class ImmichRuntime:
    """What one set-up server keeps while it's loaded."""

    client: ImmichClient
    coordinator: ImmichStatsCoordinator
    photo_lists: PhotoLists


type ImmichConfigEntry = ConfigEntry[ImmichRuntime]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the cards, their images and videos, and their WebSocket commands."""
    hass.http.register_view(ImmichImageView())
    async_register_commands(hass)
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ImmichConfigEntry) -> bool:
    """Connect to one Immich server."""
    # Taken away with the last server, so a server added after that brings it back.
    await async_add_resource(hass)
    client = ImmichClient(
        async_get_clientsession(hass, entry.data.get(CONF_VERIFY_SSL, True)),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
    )
    try:
        missing = await client.async_missing_permissions()
    except ImmichAuthError as err:
        raise ConfigEntryAuthFailed(f"Immich refused the API key: {err}") from err
    except ImmichError as err:
        raise ConfigEntryNotReady(str(err)) from err
    if missing:
        raise ConfigEntryAuthFailed(f"The API key is missing permissions: {', '.join(missing)}")

    coordinator = ImmichStatsCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    photo_lists = PhotoLists(hass)
    entry.runtime_data = ImmichRuntime(client, coordinator, photo_lists)
    entry.async_on_unload(
        async_track_time_interval(hass, photo_lists.async_forget_old, KEEP, cancel_on_shutdown=True)
    )

    @callback
    def update_device() -> None:
        async_update_device(hass, entry, (coordinator.data or {}).get("about", {}).get("version"))

    update_device()
    entry.async_on_unload(coordinator.async_add_listener(update_device))

    async def new_day(now: datetime) -> None:
        # Today's On This Day count changes at midnight.
        await coordinator.async_request_refresh()

    entry.async_on_unload(async_track_time_change(hass, new_day, hour=0, minute=0, second=5))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ImmichConfigEntry) -> bool:
    """Disconnect from an Immich server."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ImmichConfigEntry) -> None:
    """Take the cards off the dashboards' resources with the last server."""
    others = [
        other for other in hass.config_entries.async_entries(DOMAIN) if other.entry_id != entry.entry_id
    ]
    if not others:
        await async_remove_resource(hass)
