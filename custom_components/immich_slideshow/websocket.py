"""WebSocket commands the cards use to list albums and photos."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .api import (
    ImmichAuthError,
    ImmichClient,
    ImmichConnectionError,
    ImmichError,
    ImmichNotFoundError,
)
from .const import DOMAIN, RANDOM_COUNT, SEARCH_COUNT, SEARCH_MAX

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.9
    import voluptuous as vol  # type: ignore[no-redef]

_LOGGER = logging.getLogger(__name__)
SOURCES = ("album", "random", "search", "on_this_day")


class _Failure(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the commands once."""
    websocket_api.async_register_command(hass, ws_servers)
    websocket_api.async_register_command(hass, ws_albums)
    websocket_api.async_register_command(hass, ws_photos)


def _entry(hass: HomeAssistant, server: str | None) -> ConfigEntry:
    """The chosen server, or the first one when the card doesn't name one."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if server:
        entries = [entry for entry in entries if entry.entry_id == server]
    if not entries:
        raise _Failure("not_configured", "No Immich server is set up in Immich Slideshow")
    return entries[0]


async def _run(hass: HomeAssistant, connection: Any, msg: dict[str, Any], work: Any) -> None:
    try:
        entry = _entry(hass, msg.get("server"))
        client: ImmichClient = entry.runtime_data.client
        try:
            result = await work(entry, client)
        except ImmichAuthError as err:
            entry.async_start_reauth(hass)
            raise _Failure("auth_failed", f"Immich refused the API key: {err}") from err
        except ImmichNotFoundError as err:
            raise _Failure("not_found", str(err)) from err
        except ImmichConnectionError as err:
            # The detail names Immich's address, which every dashboard user would see.
            _LOGGER.debug("Couldn't reach Immich for %s: %s", msg["type"], err)
            raise _Failure("unavailable", "Couldn't reach Immich") from err
        except ImmichError as err:
            raise _Failure("unavailable", str(err)) from err
    except _Failure as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/servers"})
@callback
def ws_servers(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    """List the Immich servers that are set up."""
    connection.send_result(
        msg["id"],
        {
            "servers": [
                {"id": entry.entry_id, "name": entry.title}
                for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            ]
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/albums", vol.Optional("server"): str}
)
@websocket_api.async_response
async def ws_albums(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    """List a server's albums."""

    async def work(entry: ConfigEntry, client: ImmichClient) -> dict[str, Any]:
        return {"server": entry.entry_id, "albums": await client.async_albums()}

    await _run(hass, connection, msg, work)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/photos",
        vol.Required("source"): vol.In(SOURCES),
        vol.Optional("server"): str,
        vol.Optional("album"): str,
        vol.Optional("query"): str,
        vol.Optional("count"): vol.All(int, vol.Range(min=1, max=SEARCH_MAX)),
        vol.Optional("language"): str,
    }
)
@websocket_api.async_response
async def ws_photos(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    """List the photos for one source."""
    source = msg["source"]

    async def work(entry: ConfigEntry, client: ImmichClient) -> dict[str, Any]:
        result: dict[str, Any] = {"server": entry.entry_id}
        if source == "album":
            if not msg.get("album"):
                raise _Failure("invalid_format", "Choose an album")
            result["photos"] = await client.async_album_photos(msg["album"])
        elif source == "random":
            result["photos"] = await client.async_random_photos(RANDOM_COUNT)
        elif source == "search":
            query = msg.get("query", "").strip()
            if not query:
                raise _Failure("invalid_format", "Describe the photos to show")
            result["photos"] = await client.async_search_photos(
                query, msg.get("count", SEARCH_COUNT), msg.get("language")
            )
        else:
            # Home Assistant's own time zone decides when the day changes.
            today = dt_util.now().date()
            result["photos"] = await client.async_on_this_day(today)
            result["date"] = today.isoformat()
            tomorrow = dt_util.start_of_local_day(today + timedelta(days=1))
            result["refresh_at"] = int(tomorrow.timestamp() * 1000)
        return result

    await _run(hass, connection, msg, work)
