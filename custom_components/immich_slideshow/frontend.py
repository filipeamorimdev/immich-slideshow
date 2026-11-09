"""Serves the cards and registers them with the dashboard."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import CARD_URL, DOMAIN, FRONTEND_PATH, LEGACY_CARD_FILE, VERSION

_LOGGER = logging.getLogger(__name__)
FRONTEND_DIR = Path(__file__).parent / "frontend"
REGISTERED = f"{DOMAIN}_frontend"


def resource_path(url: str) -> str:
    """Return a resource URL's path, without the version query."""
    return urlsplit(url).path


def is_legacy_resource(url: str) -> bool:
    """Whether a resource loads the standalone card this integration replaces."""
    return resource_path(url).rsplit("/", 1)[-1] == LEGACY_CARD_FILE


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card file and make sure dashboards load it."""
    if hass.data.get(REGISTERED):
        return
    hass.data[REGISTERED] = True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_PATH, str(FRONTEND_DIR), False)]
    )
    versioned = f"{CARD_URL}?v={VERSION}"
    # Dashboards load their resources once the frontend is ready. An extra JS URL
    # can run before that, and from Home Assistant 2026.10 the frontend then swaps
    # in its own element registry, which no longer knows the cards. So the extra
    # URL is only a fallback for dashboards whose resources are kept in YAML.
    if not await _async_update_resources(hass, versioned):
        frontend.add_extra_js_url(hass, versioned)
        _LOGGER.info("Add %s to your dashboard resources as a JavaScript module", versioned)


async def _async_resources(hass: HomeAssistant) -> Any:
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    # Dashboards in YAML mode list their resources in YAML, which can't be changed here.
    if resources is None or not hasattr(resources, "async_create_item"):
        return None
    if not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True
    return resources


async def _async_update_resources(hass: HomeAssistant, versioned: str) -> bool:
    """Add or update the cards' dashboard resource. False if it couldn't be."""
    resources = await _async_resources(hass)
    if resources is None:
        return False
    try:
        ours = None
        for item in list(resources.async_items()):
            url = item.get("url", "")
            if resource_path(url) == CARD_URL:
                ours = item
            elif is_legacy_resource(url):
                await resources.async_delete_item(item["id"])
                _LOGGER.info("Removed the standalone card's resource %s", url)
        if ours is None:
            await resources.async_create_item({"res_type": "module", "url": versioned})
        elif ours.get("url") != versioned:
            await resources.async_update_item(ours["id"], {"res_type": "module", "url": versioned})
    except Exception:  # noqa: BLE001 - the extra JS URL is the fallback.
        _LOGGER.debug("Couldn't update dashboard resources", exc_info=True)
        return False
    return True
