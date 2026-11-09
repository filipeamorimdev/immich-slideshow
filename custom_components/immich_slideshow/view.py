"""Serves photos to the cards, so the browser never talks to Immich directly."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.http import KEY_HASS

from .api import UUID, ImmichError, ImmichNotFoundError
from .const import DOMAIN, IMAGE_SIZES


class ImmichImageView(HomeAssistantView):
    """One size of one photo. Cards reach it through signed, short-lived paths."""

    url = f"/api/{DOMAIN}/{{server}}/{{asset_id}}/{{size}}"
    name = f"api:{DOMAIN}:image"
    requires_auth = True

    async def get(
        self, request: web.Request, server: str, asset_id: str, size: str
    ) -> web.Response:
        """Fetch the photo from Immich and pass it on."""
        if size not in IMAGE_SIZES or not UUID.match(asset_id):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(server)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        try:
            body, content_type = await entry.runtime_data.client.async_image(asset_id, size)
        except ImmichNotFoundError:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        except ImmichError:
            return web.Response(status=HTTPStatus.BAD_GATEWAY)
        return web.Response(
            body=body,
            content_type=content_type,
            headers={"Cache-Control": "private, max-age=86400"},
        )
