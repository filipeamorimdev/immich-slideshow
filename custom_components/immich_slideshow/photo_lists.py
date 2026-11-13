"""Photo lists, kept for a few minutes.

Every card reads its whole list when a dashboard opens, and a large album is
several requests to Immich. Cards that show the same photos share one read.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Hashable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN

KEEP = timedelta(minutes=5)
MAX_LISTS = 16

type Photos = list[dict[str, Any]]


def _retrieve(task: asyncio.Task[Photos]) -> None:
    # A read that failed after every card went away has nobody to tell.
    if not task.cancelled():
        task.exception()


class PhotoLists:
    """The lists one Immich server was asked for in the last few minutes."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._kept: dict[Hashable, tuple[datetime, Photos]] = {}
        self._reading: dict[Hashable, asyncio.Task[Photos]] = {}

    async def async_get(self, key: Hashable, read: Callable[[], Awaitable[Photos]]) -> Photos:
        """Return the list kept under a key, or read it. A failed read isn't kept."""
        kept = self._kept.get(key)
        if kept and dt_util.utcnow() - kept[0] < KEEP:
            return kept[1]
        task = self._reading.get(key)
        if task is None:
            task = self._hass.async_create_background_task(
                self._async_read(key, read), f"{DOMAIN} photo list"
            )
            task.add_done_callback(_retrieve)
            # Home Assistant starts a task at once, so a quick read is already over.
            if not task.done():
                self._reading[key] = task
        # Shielded, so a card that goes away doesn't stop the read for the others.
        return await asyncio.shield(task)

    async def _async_read(self, key: Hashable, read: Callable[[], Awaitable[Photos]]) -> Photos:
        try:
            photos = await read()
        finally:
            self._reading.pop(key, None)
        self.async_forget_old()
        while len(self._kept) >= MAX_LISTS:
            # The one kept longest goes first.
            del self._kept[next(iter(self._kept))]
        self._kept[key] = (dt_util.utcnow(), photos)
        return photos

    @callback
    def async_forget_old(self, _now: datetime | None = None) -> None:
        """Drop the lists that are too old to use. A timer calls this too."""
        now = dt_util.utcnow()
        self._kept = {key: kept for key, kept in self._kept.items() if now - kept[0] < KEEP}
