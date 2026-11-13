"""Serves photos and videos to the cards, so the browser never talks to Immich directly."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import ClientError, hdrs, web

from homeassistant.components.http import KEY_HASS_USER, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.http import KEY_HASS

from .api import UUID, ImmichClient, ImmichError, ImmichNotFoundError
from .const import DOMAIN, IMAGE_SIZES, VIDEO

CACHE = {hdrs.CACHE_CONTROL: "private, max-age=86400"}
VIDEO_CHUNK = 64 * 1024
# What the browser needs to play a video and to ask for parts of it.
VIDEO_HEADERS = (hdrs.CONTENT_TYPE, hdrs.CONTENT_LENGTH, hdrs.CONTENT_RANGE, hdrs.ACCEPT_RANGES)


class ImmichImageView(HomeAssistantView):
    """One size of one photo, or one video, for Home Assistant admins only.

    Cards reach it through signed, short-lived paths, which carry the user who signed them.
    """

    url = f"/api/{DOMAIN}/{{server}}/{{asset_id}}/{{size}}"
    name = f"api:{DOMAIN}:image"
    requires_auth = True

    async def get(
        self, request: web.Request, server: str, asset_id: str, size: str
    ) -> web.StreamResponse:
        """Fetch the photo or video from Immich and pass it on."""
        if not request[KEY_HASS_USER].is_admin:
            return web.Response(status=HTTPStatus.FORBIDDEN)
        if size not in (*IMAGE_SIZES, VIDEO) or not UUID.match(asset_id):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        hass = request.app[KEY_HASS]
        entry = hass.config_entries.async_get_entry(server)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        client: ImmichClient = entry.runtime_data.client
        try:
            if size == VIDEO:
                return await self._video(request, client, asset_id)
            return await self._image(request, client, asset_id, size)
        except ImmichNotFoundError:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        except ImmichError:
            return web.Response(status=HTTPStatus.BAD_GATEWAY)

    async def _image(
        self, request: web.Request, client: ImmichClient, asset_id: str, size: str
    ) -> web.StreamResponse:
        """Pass a photo on as it arrives, when Immich says how long it is."""
        async with client.async_open_image(asset_id, size) as image:
            if image.length is None:
                # Read whole first, so a photo that turns out too large or cut off
                # is refused and not passed on in part.
                body = await image.async_read()
                return web.Response(body=body, content_type=image.content_type, headers=CACHE)
            response = web.StreamResponse(headers=CACHE)
            response.content_type = image.content_type
            response.content_length = image.length
            try:
                await response.prepare(request)
                async for chunk in image.chunks:
                    await response.write(chunk)
            except (ImmichError, ConnectionResetError):
                # Immich stopped sending, or the browser stopped listening. With the
                # length sent ahead, a cut-off photo can't pass for a whole one.
                response.force_close()
            return response

    async def _video(
        self, request: web.Request, client: ImmichClient, asset_id: str
    ) -> web.StreamResponse:
        """Pass a video on as it arrives. Browsers ask for it in parts, with a Range header."""
        upstream = await client.async_video(asset_id, request.headers.get(hdrs.RANGE))
        try:
            headers = {name: upstream.headers[name] for name in VIDEO_HEADERS if name in upstream.headers}
            response = web.StreamResponse(status=upstream.status, headers={**headers, **CACHE})
            try:
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(VIDEO_CHUNK):
                    await response.write(chunk)
            except (ClientError, TimeoutError, ConnectionResetError):
                # The browser stopped listening, as it does when it skips ahead, or Immich
                # stopped sending. Closing the connection keeps a cut-off video from
                # passing for a whole one.
                response.force_close()
            return response
        finally:
            upstream.close()
