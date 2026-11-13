"""Whether a newer Immich release is out. Immich is updated outside Home Assistant."""

from __future__ import annotations

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ImmichConfigEntry
from .coordinator import ImmichStatsCoordinator
from .entity import device_info

PARALLEL_UPDATES = 0
RELEASES = "https://github.com/immich-app/immich/releases/tag/"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImmichConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the update entity if the key can read the version and the release check."""
    coordinator = entry.runtime_data.coordinator
    if coordinator.supports("about") and coordinator.supports("version_check"):
        async_add_entities([ImmichUpdate(coordinator)])


class ImmichUpdate(CoordinatorEntity[ImmichStatsCoordinator], UpdateEntity):
    """The server's version, and the newest release Immich has found."""

    _attr_has_entity_name = True
    _attr_translation_key = "server"
    _attr_title = "Immich"

    def __init__(self, coordinator: ImmichStatsCoordinator) -> None:
        # The installed version is always read. This asks for the release check too.
        super().__init__(coordinator, context=("version_check", "latest"))
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_update"
        self._attr_device_info = device_info(entry)

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return super().available and "about" in data and "version_check" in data

    @property
    def installed_version(self) -> str | None:
        return (self.coordinator.data or {}).get("about", {}).get("version")

    @property
    def latest_version(self) -> str | None:
        # Immich has no release to report when its version check is turned off.
        latest = (self.coordinator.data or {}).get("version_check", {}).get("latest")
        return latest or self.installed_version

    @property
    def release_url(self) -> str | None:
        latest = self.latest_version
        return f"{RELEASES}{latest}" if latest else None
