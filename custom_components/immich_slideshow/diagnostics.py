"""What Home Assistant's "Download diagnostics" gives for a bug report.

It leaves out the API key and the server's address, and the names of places and
cameras, which say where the photos were taken.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from . import ImmichConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ImmichConfigEntry
) -> dict[str, Any]:
    """Return the connection's settings and the statistics read last."""
    coordinator = entry.runtime_data.coordinator
    statistics = {
        name: {key: value for key, value in group.items() if not isinstance(value, list)}
        for name, group in (coordinator.data or {}).items()
    }
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        # Statistics the API key may not read, or this Immich version doesn't have.
        "left_out": sorted(coordinator.unsupported),
        "statistics": statistics,
    }
