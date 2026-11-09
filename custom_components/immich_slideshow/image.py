"""A random photo, and a photo from this day in earlier years, as image entities."""

from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from . import ImmichConfigEntry
from .api import ImmichClient, ImmichError
from .const import PHOTO_INTERVAL
from .entity import device_info

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add both photo entities. They need only the permissions the cards need."""
    client = entry.runtime_data.client
    async_add_entities(
        [RandomPhoto(hass, entry, client), OnThisDayPhoto(hass, entry, client)]
    )


class ImmichPhoto(ImageEntity):
    """Shows one photo, and moves to the next every few minutes."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_content_type = "image/jpeg"
    _unrecorded_attributes = frozenset({"taken", "city", "state", "country"})
    kind = ""

    def __init__(self, hass: HomeAssistant, entry: ImmichConfigEntry, client: ImmichClient) -> None:
        super().__init__(hass)
        self._client = client
        self._attr_translation_key = self.kind
        self._attr_unique_id = f"{entry.entry_id}_{self.kind}"
        self._attr_device_info = device_info(entry)
        self._photo: dict[str, Any] | None = None
        self._cached: tuple[str, bytes] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_next()
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_next, PHOTO_INTERVAL, cancel_on_shutdown=True
            )
        )

    async def _async_pick(self) -> dict[str, Any] | None:
        raise NotImplementedError

    async def _async_next(self, now: datetime | None = None) -> None:
        try:
            photo = await self._async_pick()
        except ImmichError as err:
            _LOGGER.debug("Couldn't get the next photo for %s: %s", self.entity_id, err)
            self._attr_available = False
        else:
            self._attr_available = True
            if photo is None or self._photo is None or photo["id"] != self._photo["id"]:
                self._photo = photo
                self._attr_image_last_updated = dt_util.utcnow() if photo else None
        if self.hass is not None and self.entity_id:
            self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        photo = self._photo
        if photo is None:
            return None
        if self._cached and self._cached[0] == photo["id"]:
            return self._cached[1]
        try:
            body, content_type = await self._client.async_image(photo["id"], "preview")
        except ImmichError as err:
            _LOGGER.debug("Couldn't load the photo for %s: %s", self.entity_id, err)
            return None
        self._attr_content_type = content_type
        self._cached = (photo["id"], body)
        return body

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._photo is None:
            return None
        return {key: self._photo.get(key) for key in ("taken", "city", "state", "country")}


class RandomPhoto(ImmichPhoto):
    """A random photo from the timeline, as the Random slideshow shows them."""

    kind = "random_photo"

    async def _async_pick(self) -> dict[str, Any] | None:
        photos = await self._client.async_random_photos(1)
        return photos[0] if photos else None


class OnThisDayPhoto(ImmichPhoto):
    """Goes through the photos taken on this day in earlier years, most recent year first."""

    kind = "on_this_day_photo"

    def __init__(self, hass: HomeAssistant, entry: ImmichConfigEntry, client: ImmichClient) -> None:
        super().__init__(hass, entry, client)
        self._day: date | None = None
        self._photos: list[dict[str, Any]] = []
        self._index = -1

    async def _async_pick(self) -> dict[str, Any] | None:
        today = dt_util.now().date()
        if today != self._day:
            self._photos = await self._client.async_on_this_day(today)
            self._day = today
            self._index = -1
        if not self._photos:
            return None
        self._index = (self._index + 1) % len(self._photos)
        return self._photos[self._index]
