"""A small read-only client for the Immich API.

Only reads: albums, searches, memories, statistics and image files. Requests
carry the API key in a header, and nothing here logs or returns it.
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import REQUIRED_PERMISSIONS

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

TIMEOUT = ClientTimeout(total=30)
IMAGE_TIMEOUT = ClientTimeout(total=60)
# Immich's preview and fullsize images are converted JPEGs or WebPs, far below this.
# The cap keeps one request from holding an unbounded file in memory.
MAX_IMAGE_BYTES = 64 * 1024 * 1024
IMAGE_CHUNK = 64 * 1024
PAGE_SIZE = 1000
MAX_PAGES = 200
# Memories list their photos without places, so they are looked up in batches.
LOOKUP_BATCH = 100

# Photos as Immich's own timeline shows them: no hidden or locked items, nothing archived,
# and nothing in the trash.
TIMELINE_PHOTOS: dict[str, Any] = {
    "type": {"eq": "IMAGE"},
    "visibility": {"eq": "timeline"},
    "trashedAt": {"eq": None},
}
# An album also shows the archived photos someone put in it.
ALBUM_PHOTOS: dict[str, Any] = {
    "type": {"eq": "IMAGE"},
    "visibility": {"notIn": ["hidden", "locked"]},
    "trashedAt": {"eq": None},
}


class ImmichError(Exception):
    """Immich could not answer the request."""


class ImmichConnectionError(ImmichError):
    """Immich could not be reached."""


class ImmichAuthError(ImmichError):
    """Immich refused the API key."""


class ImmichForbiddenError(ImmichAuthError):
    """The key lacks a permission, or the request needs an admin's key."""


class ImmichNotFoundError(ImmichError):
    """The album or photo does not exist, or the key can't see it."""


def photo(asset: dict[str, Any]) -> dict[str, Any]:
    """Return what the cards need about one photo."""
    exif = asset.get("exifInfo") or {}
    return {
        "id": asset["id"],
        # The time on the camera's clock where the photo was taken, written as UTC.
        "taken": asset.get("localDateTime"),
        "city": exif.get("city"),
        "state": exif.get("state"),
        "country": exif.get("country"),
    }


async def _message(response: ClientResponse) -> str:
    try:
        body = await response.json(content_type=None)
    except (ClientError, ValueError):
        return getattr(response, "reason", None) or str(response.status)
    if isinstance(body, dict) and body.get("message"):
        message = body["message"]
        text = ", ".join(message) if isinstance(message, list) else str(message)
        details = [
            error["message"]
            for error in body.get("errors") or []
            if isinstance(error, dict) and error.get("message")
        ]
        return f"{text}: {'; '.join(details)}" if details else text
    return getattr(response, "reason", None) or str(response.status)


class ImmichClient:
    """Reads from one Immich server with one API key."""

    def __init__(self, session: ClientSession, url: str, api_key: str) -> None:
        self._session = session
        self._base = f"{url.rstrip('/')}/api"
        self._headers = {"x-api-key": api_key, "Accept": "application/json"}

    async def _check(self, response: ClientResponse) -> None:
        if response.status < 400:
            return
        message = await _message(response)
        if response.status == 403:
            raise ImmichForbiddenError(message)
        if response.status == 401:
            raise ImmichAuthError(message)
        # Immich answers a missing album or photo with 400 "Not found or no ... access".
        if response.status == 404 or (response.status == 400 and message.startswith("Not found")):
            raise ImmichNotFoundError(message)
        raise ImmichError(f"Immich answered {response.status}: {message}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                headers=self._headers,
                params=params,
                json=json,
                timeout=TIMEOUT,
            ) as response:
                await self._check(response)
                return await response.json()
        except (ClientError, TimeoutError) as err:
            raise ImmichConnectionError(f"Couldn't reach Immich: {err}") from err

    async def async_missing_permissions(self) -> list[str]:
        """Check the key works, and return the permissions it lacks."""
        key = await self._request("GET", "/api-keys/me")
        granted = set(key.get("permissions") or [])
        if "all" in granted:
            return []
        return [name for name in REQUIRED_PERMISSIONS if name not in granted]

    async def async_albums(self) -> list[dict[str, Any]]:
        """Return the albums the key's user owns, and those shared with them."""
        owned = await self._request("GET", "/albums")
        shared = await self._request("GET", "/albums", params={"shared": "true"})
        albums = {album["id"]: album for album in [*owned, *shared]}
        return sorted(
            (
                {"id": album["id"], "name": album["albumName"], "count": album.get("assetCount", 0)}
                for album in albums.values()
            ),
            key=lambda album: album["name"].casefold(),
        )

    async def _search(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        # Searches with a filter page by cursor; page numbers are refused.
        assets: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            request = {**body, "withExif": True, "size": PAGE_SIZE}
            if cursor:
                request["cursor"] = cursor
            result = await self._request("POST", "/search/metadata", json=request)
            assets.extend(result["assets"]["items"])
            cursor = result["assets"].get("nextCursor")
            if not cursor:
                break
        return assets

    async def async_album_photos(self, album_id: str) -> list[dict[str, Any]]:
        """Return an album's photos in the album's own order."""
        if not UUID.match(album_id):
            raise ImmichNotFoundError("Not an album ID")
        album = await self._request("GET", f"/albums/{album_id}", params={"withoutAssets": "true"})
        assets = await self._search({"filter": {**ALBUM_PHOTOS, "albumIds": {"any": [album_id]}}})
        assets.sort(key=lambda asset: asset.get("localDateTime") or "", reverse=album.get("order") == "desc")
        return [photo(asset) for asset in assets]

    async def async_random_photos(self, count: int) -> list[dict[str, Any]]:
        """Return random photos from the whole library."""
        assets = await self._request(
            "POST",
            "/search/random",
            json={"size": count, "withExif": True, "filter": TIMELINE_PHOTOS},
        )
        return [photo(asset) for asset in assets]

    async def async_search_photos(
        self, query: str, count: int, language: str | None = None
    ) -> list[dict[str, Any]]:
        """Return the photos that best match a description, best first."""
        body: dict[str, Any] = {
            "query": query,
            "size": count,
            "withExif": True,
            "filter": TIMELINE_PHOTOS,
        }
        if language:
            body["language"] = language
        result = await self._request("POST", "/search/smart", json=body)
        return [photo(asset) for asset in result["assets"]["items"]]

    async def async_on_this_day(self, day: date) -> list[dict[str, Any]]:
        """Return photos taken on this day in earlier years, most recent year first."""
        memories = await self._request(
            "GET", "/memories", params={"for": day.isoformat(), "type": "on_this_day"}
        )
        memories.sort(key=lambda memory: memory.get("memoryAt") or "", reverse=True)
        order = [asset["id"] for memory in memories for asset in memory.get("assets", [])]
        found: dict[str, dict[str, Any]] = {}
        for start in range(0, len(order), LOOKUP_BATCH):
            batch = order[start : start + LOOKUP_BATCH]
            branches = [{"id": {"eq": asset_id}} for asset_id in batch]
            for asset in await self._search({"filter": {**TIMELINE_PHOTOS, "or": branches}}):
                found[asset["id"]] = asset
        photos = [found[asset_id] for asset_id in dict.fromkeys(order) if asset_id in found]
        photos.sort(key=lambda asset: (-int((asset.get("localDateTime") or "0")[:4]), asset.get("localDateTime") or ""))
        return [photo(asset) for asset in photos]

    async def async_get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Read one of Immich's JSON endpoints, such as /server/storage."""
        return await self._request("GET", path, params=params)

    async def async_count(self, rules: dict[str, Any]) -> int:
        """Count the items that match a search filter."""
        result = await self._request("POST", "/search/statistics", json={"filter": rules})
        return int(result["total"])

    async def async_image(self, asset_id: str, size: str) -> tuple[bytes, str]:
        """Return one size of a photo, and its content type."""
        if not UUID.match(asset_id):
            raise ImmichNotFoundError("Not a photo ID")
        try:
            async with self._session.get(
                f"{self._base}/assets/{asset_id}/thumbnail",
                headers={**self._headers, "Accept": "image/*"},
                params={"size": size},
                timeout=IMAGE_TIMEOUT,
            ) as response:
                await self._check(response)
                content_type = response.content_type
                if not content_type.startswith("image/"):
                    raise ImmichError(f"Immich sent {content_type}, not an image")
                body = bytearray()
                async for chunk in response.content.iter_chunked(IMAGE_CHUNK):
                    body.extend(chunk)
                    if len(body) > MAX_IMAGE_BYTES:
                        raise ImmichError("The photo is too large to pass on")
                return bytes(body), content_type
        except (ClientError, TimeoutError) as err:
            raise ImmichConnectionError(f"Couldn't reach Immich: {err}") from err
