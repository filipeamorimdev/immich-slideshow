"""WebSocket commands the cards use to list albums and photos, and to report videos that won't play.

Only Home Assistant admins may use them: they read whatever the API key can see.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .api import (
    UUID,
    ImmichAuthError,
    ImmichClient,
    ImmichConnectionError,
    ImmichError,
    ImmichForbiddenError,
    ImmichNotFoundError,
)
from .const import DOMAIN, RANDOM_COUNT, SEARCH_COUNT, SEARCH_MAX
from .photo_lists import PhotoLists

try:
    import probatio as vol
except ImportError:  # Home Assistant before 2026.9
    import voluptuous as vol  # type: ignore[no-redef]

_LOGGER = logging.getLogger(__name__)
SOURCES = ("album", "random", "search", "on_this_day")
# The same failure is logged as a warning this often, and for debugging in between.
# A card that can't load tries again every minute.
WARN_EVERY = timedelta(hours=1)
WARNED = f"{DOMAIN}_warned"
MAX_WARNED = 32
# Why a browser gave up on a video: it can't play that kind of video, the video is
# damaged or too much for it, it stopped arriving, it showed nothing new for too long,
# the browser wouldn't start it, or its link couldn't be made.
VIDEO_FAILURES = ("format", "decode", "network", "stalled", "refused", "link", "unknown")
VIDEO_PLACES = ("slideshow", "viewer")
MAX_REPORT_TEXT = 300


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
    websocket_api.async_register_command(hass, ws_video_failed)


def _entry(hass: HomeAssistant, server: str | None) -> ConfigEntry:
    """The chosen server, or the first one when the card doesn't name one."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if server:
        entries = [entry for entry in entries if entry.entry_id == server]
    if not entries:
        raise _Failure("not_configured", "No Immich server is set up in Immich Slideshow")
    return entries[0]


@callback
def _warn(hass: HomeAssistant, key: str, message: str, *args: Any) -> None:
    """Log a warning, or for debugging if the same `key` was a warning in the last hour."""
    warned: dict[str, datetime] = hass.data.setdefault(WARNED, {})
    now = dt_util.utcnow()
    last = warned.get(key)
    if last and now - last < WARN_EVERY:
        _LOGGER.debug(message, *args)
        return
    if len(warned) >= MAX_WARNED:
        warned.clear()
    warned[key] = now
    _LOGGER.warning(message, *args)


@callback
def _log(hass: HomeAssistant, command: str, err: ImmichError) -> None:
    """Log what Immich answered. Cards are told only that it failed."""
    _warn(hass, str(err), "Immich couldn't answer %s: %s", command, err)


def _printable(text: str) -> str:
    """What a browser sent, on one line, so it can't pass for other lines of the log."""
    return "".join(char if char.isprintable() else " " for char in text).strip()


async def _run(hass: HomeAssistant, connection: Any, msg: dict[str, Any], work: Any) -> None:
    # Every dashboard user sees these messages, so they never repeat what Immich
    # answered or name its address. The log has that.
    try:
        entry = _entry(hass, msg.get("server"))
        client: ImmichClient = entry.runtime_data.client
        try:
            result = await work(entry, client)
        except ImmichAuthError as err:
            entry.async_start_reauth(hass)
            _log(hass, msg["type"], err)
            raise _Failure("auth_failed", "Immich refused the API key") from err
        except ImmichConnectionError as err:
            _LOGGER.debug("Couldn't reach Immich for %s: %s", msg["type"], err)
            raise _Failure("unavailable", "Couldn't reach Immich") from err
        except ImmichError as err:
            _log(hass, msg["type"], err)
            raise _Failure(
                "unavailable", "Immich gave an unexpected answer. Home Assistant's log has the details."
            ) from err
    except _Failure as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/servers"})
@websocket_api.require_admin
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
@websocket_api.require_admin
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
        vol.Optional("videos"): bool,
        vol.Optional("people"): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_photos(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    """List the photos for one source, with its videos if the card plays them.

    With `people`, each photo also names who is in it.
    """
    source = msg["source"]
    videos = msg.get("videos", False)

    async def work(entry: ConfigEntry, client: ImmichClient) -> dict[str, Any]:
        if not msg.get("people", False):
            return await read(entry, client, False)
        try:
            return await read(entry, client, True)
        except ImmichForbiddenError as err:
            # A key that can't read people still shows the photos, without the names.
            _LOGGER.debug("Immich wouldn't say who is in the photos: %s", err)
            return await read(entry, client, False)

    async def read(entry: ConfigEntry, client: ImmichClient, people: bool) -> dict[str, Any]:
        result: dict[str, Any] = {"server": entry.entry_id}
        # Cards that show the same photos share one read. Random photos are new each time.
        lists: PhotoLists = entry.runtime_data.photo_lists
        if source == "album":
            album = msg.get("album")
            if not album:
                raise _Failure("invalid_format", "Choose an album")
            try:
                result["photos"] = await lists.async_get(
                    ("album", album, videos, people),
                    lambda: client.async_album_photos(album, videos, people),
                )
            except ImmichNotFoundError as err:
                raise _Failure(
                    "not_found", "Immich couldn't find the album, or the API key can't read it"
                ) from err
        elif source == "random":
            result["photos"] = await client.async_random_photos(RANDOM_COUNT, videos, people)
        elif source == "search":
            query = msg.get("query", "").strip()
            if not query:
                raise _Failure("invalid_format", "Describe the photos to show")
            count = msg.get("count", SEARCH_COUNT)
            language = msg.get("language")
            result["photos"] = await lists.async_get(
                ("search", query, count, language, videos, people),
                lambda: client.async_search_photos(query, count, language, videos, people),
            )
        else:
            # Home Assistant's own time zone decides when the day changes.
            today = dt_util.now().date()
            result["photos"] = await lists.async_get(
                ("on_this_day", today, videos, people),
                lambda: client.async_on_this_day(today, videos, people),
            )
            result["date"] = today.isoformat()
            tomorrow = dt_util.start_of_local_day(today + timedelta(days=1))
            result["refresh_at"] = int(tomorrow.timestamp() * 1000)
        return result

    await _run(hass, connection, msg, work)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/video_failed",
        vol.Required("asset"): vol.Match(UUID),
        vol.Required("reason"): vol.In(VIDEO_FAILURES),
        vol.Optional("place"): vol.In(VIDEO_PLACES),
        vol.Optional("detail"): vol.All(str, vol.Length(max=MAX_REPORT_TEXT)),
        vol.Optional("browser"): vol.All(str, vol.Length(max=MAX_REPORT_TEXT)),
    }
)
@websocket_api.require_admin
@callback
def ws_video_failed(hass: HomeAssistant, connection: Any, msg: dict[str, Any]) -> None:
    """Log why a browser couldn't play a video.

    A card keeps the still and moves on, and a wall display has no console to look at,
    so the log is where the reason can be read. A browser that can't play one video
    often can't play many: each reason is a warning once an hour for each browser.
    """
    reason = msg["reason"]
    browser = _printable(msg.get("browser", "")) or "unknown"
    _warn(
        hass,
        f"video {reason} {browser}",
        "A browser couldn't play video %s in the %s: %s (%s). Browser: %s",
        msg["asset"],
        msg.get("place", "slideshow"),
        reason,
        _printable(msg.get("detail", "")) or "no details",
        browser,
    )
    connection.send_result(msg["id"])
