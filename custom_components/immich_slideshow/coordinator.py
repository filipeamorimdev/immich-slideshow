"""Reads the server's statistics for the sensors and the update entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    ImmichAuthError,
    ImmichClient,
    ImmichConnectionError,
    ImmichError,
    ImmichForbiddenError,
    ImmichNotFoundError,
)
from .const import DOMAIN, SLOW_STATS_INTERVAL, STATS_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Everything in the library that isn't hidden, locked or in the trash. This is
# what Immich's own asset statistics count: the timeline and the archive.
LIBRARY: dict[str, Any] = {
    "visibility": {"in": ["timeline", "archive"]},
    "trashedAt": {"eq": None},
}

type Fetch = Callable[[ImmichClient, date], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Group:
    """Statistics read together, which need the same permission."""

    fetch: Fetch
    slow: bool = False


def _distinct(values: list[str]) -> list[str]:
    # Camera makes come back as "samsung", "Samsung" and "SAMSUNG".
    seen: dict[str, str] = {}
    for value in values:
        if value and value.strip():
            seen.setdefault(value.strip().casefold(), value.strip())
    return sorted(seen.values(), key=str.casefold)


async def _about(client: ImmichClient, day: date) -> dict[str, Any]:
    about = await client.async_get("/server/about")
    return {"version": about.get("version")}


async def _storage(client: ImmichClient, day: date) -> dict[str, Any]:
    storage = await client.async_get("/server/storage")
    return {
        "size": storage["diskSizeRaw"],
        "used": storage["diskUseRaw"],
        "available": storage["diskAvailableRaw"],
        "usage": storage["diskUsagePercentage"],
    }


async def _server(client: ImmichClient, day: date) -> dict[str, Any]:
    # Every user's library together. Only an admin's key can read this.
    stats = await client.async_get("/server/statistics")
    return {
        "photos": stats["photos"],
        "videos": stats["videos"],
        "usage": stats["usage"],
        "usage_photos": stats["usagePhotos"],
        "usage_videos": stats["usageVideos"],
        "users": len(stats.get("usageByUser") or []),
    }


async def _version_check(client: ImmichClient, day: date) -> dict[str, Any]:
    check = await client.async_get("/server/version-check")
    return {"latest": check.get("releaseVersion"), "checked_at": check.get("checkedAt")}


async def _queues(client: ImmichClient, day: date) -> dict[str, Any]:
    queues = await client.async_get("/queues")
    totals = {"active": 0, "waiting": 0, "failed": 0, "paused": 0}
    for queue in queues:
        stats = queue.get("statistics") or {}
        totals["active"] += stats.get("active", 0)
        totals["waiting"] += stats.get("waiting", 0) + stats.get("delayed", 0) + stats.get("paused", 0)
        totals["failed"] += stats.get("failed", 0)
        totals["paused"] += bool(queue.get("isPaused"))
    return totals


async def _assets(client: ImmichClient, day: date) -> dict[str, Any]:
    everything = await client.async_get("/assets/statistics")
    favorites = await client.async_get("/assets/statistics", {"isFavorite": "true"})
    archived = await client.async_get("/assets/statistics", {"visibility": "archive"})
    trash = await client.async_get("/assets/statistics", {"isTrashed": "true"})
    return {
        "photos": everything["images"],
        "videos": everything["videos"],
        "total": everything["total"],
        "favorites": favorites["total"],
        "archived": archived["total"],
        "trash": trash["total"],
    }


async def _counts(client: ImmichClient, day: date) -> dict[str, Any]:
    since = (dt_util.utcnow() - timedelta(days=1)).isoformat()
    rules: dict[str, dict[str, Any]] = {
        "located": {"country": {"ne": None}},
        "unlocated": {"country": {"eq": None}},
        "with_people": {"hasPeople": {"eq": True}},
        "in_albums": {"hasAlbums": {"eq": True}},
        "not_in_albums": {"hasAlbums": {"eq": False}},
        "tagged": {"hasTags": {"eq": True}},
        "rated": {"rating": {"gte": 1}},
        "motion": {"isMotion": {"eq": True}},
        "offline": {"isOffline": {"eq": True}},
        "added_recently": {"createdAt": {"gte": since}},
    }
    return {name: await client.async_count({**LIBRARY, **rule}) for name, rule in rules.items()}


async def _albums(client: ImmichClient, day: date) -> dict[str, Any]:
    stats = await client.async_get("/albums/statistics")
    return {"owned": stats["owned"], "shared": stats["shared"]}


async def _memories(client: ImmichClient, day: date) -> dict[str, Any]:
    stats = await client.async_get("/memories/statistics")
    return {"total": stats["total"]}


async def _on_this_day(client: ImmichClient, day: date) -> dict[str, Any]:
    # Counted the way the On This Day card shows them: photos on the timeline.
    memories = await client.async_get("/memories", {"for": day.isoformat(), "type": "on_this_day"})
    photos = {
        asset["id"]
        for memory in memories
        for asset in memory.get("assets") or []
        if asset.get("type") == "IMAGE"
        and not asset.get("isTrashed")
        and asset.get("visibility", "timeline") == "timeline"
    }
    years = {memory.get("data", {}).get("year") for memory in memories if memory.get("assets")}
    return {"photos": len(photos), "years": len(years - {None})}


async def _people(client: ImmichClient, day: date) -> dict[str, Any]:
    people = await client.async_get("/people", {"size": "1", "withHidden": "true"})
    return {"total": people["total"], "hidden": people["hidden"]}


async def _tags(client: ImmichClient, day: date) -> dict[str, Any]:
    return {"total": len(await client.async_get("/tags"))}


async def _users(client: ImmichClient, day: date) -> dict[str, Any]:
    return {"total": len(await client.async_get("/users"))}


async def _shared_links(client: ImmichClient, day: date) -> dict[str, Any]:
    return {"total": len(await client.async_get("/shared-links"))}


async def _places_and_cameras(client: ImmichClient, day: date) -> dict[str, Any]:
    async def suggestions(kind: str) -> list[str]:
        return _distinct(await client.async_get("/search/suggestions", {"type": kind}))

    countries = await suggestions("country")
    makes = await suggestions("camera-make")
    return {
        "countries": len(countries),
        "country_list": countries,
        "cities": len(await suggestions("city")),
        "camera_makes": len(makes),
        "camera_make_list": makes,
        "camera_models": len(await suggestions("camera-model")),
        "lenses": len(await suggestions("camera-lens-model")),
    }


async def _duplicates(client: ImmichClient, day: date) -> dict[str, Any]:
    groups = await client.async_get("/duplicates")
    return {"groups": len(groups), "items": sum(len(group.get("assets") or []) for group in groups)}


async def _stacks(client: ImmichClient, day: date) -> dict[str, Any]:
    return {"total": len(await client.async_get("/stacks"))}


GROUPS: dict[str, Group] = {
    "about": Group(_about),
    "storage": Group(_storage),
    "server": Group(_server),
    "version_check": Group(_version_check),
    "queues": Group(_queues),
    "assets": Group(_assets),
    "counts": Group(_counts),
    "albums": Group(_albums),
    "memories": Group(_memories),
    "on_this_day": Group(_on_this_day),
    "people": Group(_people),
    "tags": Group(_tags),
    "users": Group(_users),
    "shared_links": Group(_shared_links),
    "metadata": Group(_places_and_cameras),
    "duplicates": Group(_duplicates, slow=True),
    "stacks": Group(_stacks, slow=True),
}

type ImmichStats = dict[str, dict[str, Any]]


class ImmichStatsCoordinator(DataUpdateCoordinator[ImmichStats]):
    """Reads every group of statistics the API key is allowed to."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: ImmichClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=STATS_INTERVAL,
        )
        self.client = client
        # Groups the key may not read, or this Immich version doesn't have.
        self.unsupported: set[str] = set()
        self._read_at: dict[str, datetime] = {}

    def supports(self, group: str) -> bool:
        """Whether entities for this group can have a value."""
        return group not in self.unsupported

    async def _async_update_data(self) -> ImmichStats:
        previous = self.data or {}
        data: ImmichStats = {}
        now = dt_util.utcnow()
        today = dt_util.now().date()
        for name, group in GROUPS.items():
            if name in self.unsupported:
                continue
            read_at = self._read_at.get(name)
            if group.slow and name in previous and read_at and now - read_at < SLOW_STATS_INTERVAL:
                data[name] = previous[name]
                continue
            try:
                data[name] = await group.fetch(self.client, today)
            except ImmichConnectionError as err:
                raise UpdateFailed(str(err)) from err
            except (ImmichForbiddenError, ImmichNotFoundError) as err:
                # A key without this permission, or an Immich without this endpoint.
                self.unsupported.add(name)
                _LOGGER.debug("Leaving out the %s statistics: %s", name, err)
                continue
            except ImmichAuthError as err:
                raise ConfigEntryAuthFailed(f"Immich refused the API key: {err}") from err
            except (ImmichError, KeyError, TypeError, ValueError) as err:
                _LOGGER.warning("Couldn't read the %s statistics from Immich: %s", name, err)
                continue
            self._read_at[name] = now
        return data
