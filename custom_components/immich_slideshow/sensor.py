"""Counts and totals from the Immich server."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImmichConfigEntry
from .coordinator import ImmichStatsCoordinator
from .entity import device_info

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ImmichSensorDescription(SensorEntityDescription):
    """A value read from one group of statistics."""

    group: str
    value: str
    attributes: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def count(key: str, group: str, value: str, *, enabled: bool = True, diagnostic: bool = False, **kwargs: Any) -> ImmichSensorDescription:
    """A number of things, such as photos or albums."""
    return ImmichSensorDescription(
        key=key,
        translation_key=key,
        group=group,
        value=value,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
        **kwargs,
    )


def size(key: str, group: str, value: str, *, enabled: bool = True) -> ImmichSensorDescription:
    """An amount of storage, read in bytes and shown in GiB."""
    return ImmichSensorDescription(
        key=key,
        translation_key=key,
        group=group,
        value=value,
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


SENSORS: tuple[ImmichSensorDescription, ...] = (
    # The key owner's library: the timeline and the archive.
    count("photos", "assets", "photos"),
    count("videos", "assets", "videos"),
    count("items", "assets", "total", enabled=False),
    count("favorites", "assets", "favorites"),
    count("archived", "assets", "archived"),
    count("trash", "assets", "trash"),
    count("added_recently", "counts", "added_recently"),
    count("located", "counts", "located"),
    count("unlocated", "counts", "unlocated", enabled=False),
    count("with_people", "counts", "with_people"),
    count("in_albums", "counts", "in_albums", enabled=False),
    count("not_in_albums", "counts", "not_in_albums", enabled=False),
    count("tagged", "counts", "tagged", enabled=False),
    count("rated", "counts", "rated", enabled=False),
    count("motion", "counts", "motion", enabled=False),
    count("offline", "counts", "offline", enabled=False),
    count("albums", "albums", "owned"),
    count("shared_albums", "albums", "shared"),
    count("memories", "memories", "total"),
    count("on_this_day", "on_this_day", "photos"),
    count("people", "people", "total"),
    count("hidden_people", "people", "hidden", enabled=False),
    count("tags", "tags", "total"),
    count("duplicates", "duplicates", "groups"),
    count("duplicate_items", "duplicates", "items", enabled=False),
    count("stacks", "stacks", "total", enabled=False),
    count("shared_links", "shared_links", "total", enabled=False),
    count(
        "countries",
        "metadata",
        "countries",
        attributes=lambda group: {"countries": group["country_list"]},
    ),
    count("cities", "metadata", "cities"),
    count(
        "camera_makes",
        "metadata",
        "camera_makes",
        attributes=lambda group: {"makes": group["camera_make_list"]},
    ),
    count("camera_models", "metadata", "camera_models"),
    count("lenses", "metadata", "lenses", enabled=False),
    # The whole server, every user together. These need an admin's key.
    count("server_photos", "server", "photos", diagnostic=True),
    count("server_videos", "server", "videos", diagnostic=True),
    size("server_usage", "server", "usage"),
    size("server_usage_photos", "server", "usage_photos", enabled=False),
    size("server_usage_videos", "server", "usage_videos", enabled=False),
    count("users", "users", "total", diagnostic=True),
    count("jobs_active", "queues", "active", diagnostic=True),
    count("jobs_waiting", "queues", "waiting", diagnostic=True),
    count("jobs_failed", "queues", "failed", diagnostic=True),
    count("queues_paused", "queues", "paused", diagnostic=True, enabled=False),
    # The disk Immich keeps its files on.
    size("disk_size", "storage", "size"),
    size("disk_used", "storage", "used"),
    size("disk_available", "storage", "available"),
    ImmichSensorDescription(
        key="disk_usage",
        translation_key="disk_usage",
        group="storage",
        value="usage",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a sensor for every statistic the API key can read."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        ImmichSensor(coordinator, description)
        for description in SENSORS
        if coordinator.supports(description.group)
    )


class ImmichSensor(CoordinatorEntity[ImmichStatsCoordinator], SensorEntity):
    """One count or total."""

    _attr_has_entity_name = True
    entity_description: ImmichSensorDescription
    _unrecorded_attributes = frozenset({"countries", "makes"})

    def __init__(self, coordinator: ImmichStatsCoordinator, description: ImmichSensorDescription) -> None:
        # Tells the coordinator which statistic this sensor shows, so it reads it.
        super().__init__(coordinator, context=(description.group, description.value))
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def _group(self) -> dict[str, Any] | None:
        return (self.coordinator.data or {}).get(self.entity_description.group)

    @property
    def available(self) -> bool:
        return super().available and self._group is not None

    @property
    def native_value(self) -> Any:
        group = self._group
        return None if group is None else group.get(self.entity_description.value)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        group = self._group
        if group is None or self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(group)
