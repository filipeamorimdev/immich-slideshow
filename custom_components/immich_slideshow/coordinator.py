"""Reads the server's statistics for the sensors and the update entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection
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
    ImmichRedirectError,
    ImmichTimeoutError,
)
from .const import DOMAIN, SLOW_STATS_INTERVAL, STATS_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Everything in the library that isn't hidden, locked or in the trash. This is
# what Immich's own asset statistics count: the timeline and the archive.
LIBRARY: dict[str, Any] = {
    "visibility": {"in": ["timeline", "archive"]},
    "trashedAt": {"eq": None},
}

# The server's version is shown on the device, whichever entities are turned on.
ALWAYS_READ = ("about",)
# A slow answer leaves out its own statistics. After this many in one update,
# Immich is taken to be down.
MAX_SLOW_ANSWERS = 2

# Called with the client and the day. A selective group is also given the values
# to read, or None for all of them.
type Fetch = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Group:
    """Statistics read together, which need the same permission."""

    fetch: Fetch
    slow: bool = False
    # Each value is a request of its own, so only those an entity shows are read.
    selective: bool = False


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


async def _counts(
    client: ImmichClient, day: date, wanted: Collection[str] | None = None
) -> dict[str, Any]:
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
    return {
        name: await client.async_count({**LIBRARY, **rule})
        for name, rule in rules.items()
        if wanted is None or name in wanted
    }


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


# What each count of places and cameras asks Immich's search suggestions for.
SUGGESTIONS = {
    "countries": "country",
    "cities": "city",
    "camera_makes": "camera-make",
    "camera_models": "camera-model",
    "lenses": "camera-lens-model",
}


async def _places_and_cameras(
    client: ImmichClient, day: date, wanted: Collection[str] | None = None
) -> dict[str, Any]:
    found = {
        value: _distinct(await client.async_get("/search/suggestions", {"type": kind}))
        for value, kind in SUGGESTIONS.items()
        if wanted is None or value in wanted
    }
    stats: dict[str, Any] = {value: len(names) for value, names in found.items()}
    # The sensors for these two list the names in an attribute.
    if "countries" in found:
        stats["country_list"] = found["countries"]
    if "camera_makes" in found:
        stats["camera_make_list"] = found["camera_makes"]
    return stats


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
    "counts": Group(_counts, selective=True),
    "albums": Group(_albums),
    "memories": Group(_memories),
    "on_this_day": Group(_on_this_day),
    "people": Group(_people),
    "tags": Group(_tags),
    "users": Group(_users),
    "shared_links": Group(_shared_links),
    "metadata": Group(_places_and_cameras, selective=True),
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
        self._read_everything = False

    def supports(self, group: str) -> bool:
        """Whether entities for this group can have a value."""
        return group not in self.unsupported

    def _wanted(self) -> dict[str, set[str]] | None:
        """The values the entities that are turned on show, by group.

        None for the first read, which reads everything: what the key can't read
        decides which entities there are.
        """
        if not self._read_everything:
            return None
        wanted: dict[str, set[str]] = {name: set() for name in ALWAYS_READ}
        for group, value in self.async_contexts():
            wanted.setdefault(group, set()).add(value)
        return wanted

    async def _async_update_data(self) -> ImmichStats:
        previous = self.data or {}
        data: ImmichStats = {}
        now = dt_util.utcnow()
        today = dt_util.now().date()
        wanted = self._wanted()
        answered = False
        slow_answers = 0
        for name, group in GROUPS.items():
            if name in self.unsupported:
                continue
            if wanted is not None and name not in wanted:
                continue
            read_at = self._read_at.get(name)
            if group.slow and read_at and now - read_at < SLOW_STATS_INTERVAL:
                if name in previous:
                    data[name] = previous[name]
                continue
            try:
                if group.selective:
                    values = None if wanted is None else wanted[name]
                    data[name] = await group.fetch(self.client, today, values)
                else:
                    data[name] = await group.fetch(self.client, today)
            except (ImmichConnectionError, ImmichRedirectError) as err:
                # Immich answered earlier in this update, so it's up and this one
                # answer is slow. Whole lists can be, on a large library.
                slow = isinstance(err, ImmichTimeoutError) and answered
                if not slow or slow_answers == MAX_SLOW_ANSWERS:
                    raise UpdateFailed(str(err)) from err
                slow_answers += 1
                _LOGGER.warning("Immich took too long to answer for the %s statistics", name)
                # A slow list waits as long as one that was read before it's asked for again.
                self._read_at[name] = now
                continue
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
            answered = True
            self._read_at[name] = now
        self._read_everything = True
        return data
