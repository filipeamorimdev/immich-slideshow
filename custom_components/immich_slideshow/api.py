"""A small read-only client for the Immich API.

Only reads: albums, searches, memories, statistics, image files and videos. Requests
carry the API key in a header, and nothing here logs or returns it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
import re
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import REQUIRED_PERMISSIONS

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

TIMEOUT = ClientTimeout(total=30)
# A photo is passed on as it arrives, so a slow browser must not run out a total
# time. Immich has this long to connect, and this long between pieces.
IMAGE_TIMEOUT = ClientTimeout(total=None, sock_connect=10, sock_read=30)
# The longest a photo read whole, for an image entity, may take.
IMAGE_SECONDS = 60
# Immich's preview and fullsize images are converted JPEGs or WebPs, far below this.
# The cap keeps one request from passing on an unbounded file.
MAX_IMAGE_BYTES = 64 * 1024 * 1024
IMAGE_CHUNK = 64 * 1024
# What Immich sends for a thumbnail, a preview or a full image. Anything else is
# refused: an SVG, for one, can carry a script.
IMAGE_TYPES = frozenset({"image/jpeg", "image/webp", "image/png", "image/gif", "image/avif"})
# A video is passed on as it arrives, so it has no time limit as a whole.
VIDEO_TIMEOUT = ClientTimeout(total=None, connect=30, sock_read=60)
PAGE_SIZE = 1000
MAX_PAGES = 200
# The only requests that aren't GETs. Each is a search, which Immich takes as a POST
# and which changes nothing. Any other request that isn't a GET is refused before it's sent.
READ_POSTS = frozenset({"/search/metadata", "/search/random", "/search/smart", "/search/statistics"})
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
PHOTOS_AND_VIDEOS: dict[str, Any] = {"type": {"in": ["IMAGE", "VIDEO"]}}


def _rules(rules: dict[str, Any], videos: bool) -> dict[str, Any]:
    """Return a filter for photos, or one that lets videos in too."""
    return {**rules, **PHOTOS_AND_VIDEOS} if videos else rules


class ImmichError(Exception):
    """Immich could not answer the request."""


class ImmichConnectionError(ImmichError):
    """Immich could not be reached."""


class ImmichTimeoutError(ImmichConnectionError):
    """Immich took too long to answer."""


class ImmichRedirectError(ImmichError):
    """The address sends requests on to another one, which the API key must not follow."""


class ImmichAuthError(ImmichError):
    """Immich refused the API key."""


class ImmichForbiddenError(ImmichAuthError):
    """The key lacks a permission, or the request needs an admin's key."""


class ImmichNotFoundError(ImmichError):
    """The album or photo does not exist, or the key can't see it."""


def _names(asset: dict[str, Any]) -> list[str]:
    """The people Immich recognized in a photo, without the hidden and the unnamed."""
    names = [
        person["name"]
        for person in asset.get("people") or []
        if person.get("name") and not person.get("isHidden")
    ]
    return list(dict.fromkeys(names))


def photo(asset: dict[str, Any], people: bool = False) -> dict[str, Any]:
    """Return what the cards need about one photo or video, with who is in it if asked."""
    exif = asset.get("exifInfo") or {}
    item = {
        "id": asset["id"],
        # The time on the camera's clock where the photo was taken, written as UTC.
        "taken": asset.get("localDateTime"),
        "city": exif.get("city"),
        "state": exif.get("state"),
        "country": exif.get("country"),
    }
    if people:
        item["people"] = _names(asset)
    if asset.get("type") == "VIDEO":
        item["video"] = True
        # Immich gives the length in milliseconds. The cards count in seconds.
        item["duration"] = (asset.get("duration") or 0) / 1000
    return item


@dataclass
class ImmichImage:
    """One size of a photo, read from Immich in pieces."""

    content_type: str
    # The size in bytes, when Immich says it up front.
    length: int | None
    chunks: AsyncIterator[bytes]

    async def async_read(self) -> bytes:
        """Read the whole photo."""
        return b"".join([chunk async for chunk in self.chunks])


def _length(response: ClientResponse) -> int | None:
    # A compressed answer is unpacked on the way in, so its length is no longer the photo's.
    if "Content-Encoding" in response.headers:
        return None
    try:
        return int(response.headers["Content-Length"])
    except (KeyError, ValueError):
        return None


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
        if response.status < 300:
            return
        if response.status < 400:
            # Redirects are never followed: only Authorization headers are dropped
            # on the way to another host, and the API key isn't one.
            raise ImmichRedirectError("Immich's address redirects to another address")
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
        if method != "GET" and (method != "POST" or path not in READ_POSTS):
            # A mistake in this integration, not an answer from Immich, so it isn't an ImmichError.
            raise RuntimeError(f"{method} {path} could change something in Immich")
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                headers=self._headers,
                params=params,
                json=json,
                timeout=TIMEOUT,
                allow_redirects=False,
            ) as response:
                await self._check(response)
                return await response.json()
        except TimeoutError as err:
            raise ImmichTimeoutError("Immich took too long to answer") from err
        except ClientError as err:
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

    async def _search(self, body: dict[str, Any], people: bool = False) -> list[dict[str, Any]]:
        # Searches with a filter page by cursor; page numbers are refused.
        assets: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(MAX_PAGES):
            request = {**body, "withExif": True, "size": PAGE_SIZE}
            if people:
                request["withPeople"] = True
            if cursor:
                request["cursor"] = cursor
            result = await self._request("POST", "/search/metadata", json=request)
            assets.extend(result["assets"]["items"])
            cursor = result["assets"].get("nextCursor")
            if not cursor:
                break
        return assets

    async def _lookup(
        self, ids: list[str], videos: bool, people: bool = False
    ) -> dict[str, dict[str, Any]]:
        """Read photos by ID. The ones the filter leaves out are missing from the answer."""
        found: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), LOOKUP_BATCH):
            batch = ids[start : start + LOOKUP_BATCH]
            branches = [{"id": {"eq": asset_id}} for asset_id in batch]
            rules = {**_rules(TIMELINE_PHOTOS, videos), "or": branches}
            for asset in await self._search({"filter": rules}, people):
                found[asset["id"]] = asset
        return found

    async def async_album_photos(
        self, album_id: str, videos: bool = False, people: bool = False
    ) -> list[dict[str, Any]]:
        """Return an album's photos, and its videos if asked, in the album's own order."""
        if not UUID.match(album_id):
            raise ImmichNotFoundError("Not an album ID")
        album = await self._request("GET", f"/albums/{album_id}", params={"withoutAssets": "true"})
        rules = {**_rules(ALBUM_PHOTOS, videos), "albumIds": {"any": [album_id]}}
        assets = await self._search({"filter": rules}, people)
        assets.sort(key=lambda asset: asset.get("localDateTime") or "", reverse=album.get("order") == "desc")
        return [photo(asset, people) for asset in assets]

    async def async_random_photos(
        self, count: int, videos: bool = False, people: bool = False
    ) -> list[dict[str, Any]]:
        """Return random photos, and videos if asked, from the whole library."""
        body: dict[str, Any] = {"size": count, "withExif": True, "filter": _rules(TIMELINE_PHOTOS, videos)}
        if people:
            body["withPeople"] = True
        assets = await self._request("POST", "/search/random", json=body)
        return [photo(asset, people) for asset in assets]

    async def async_search_photos(
        self,
        query: str,
        count: int,
        language: str | None = None,
        videos: bool = False,
        people: bool = False,
    ) -> list[dict[str, Any]]:
        """Return the photos, and videos if asked, that best match a description, best first."""
        body: dict[str, Any] = {
            "query": query,
            "size": count,
            "withExif": True,
            "filter": _rules(TIMELINE_PHOTOS, videos),
        }
        if language:
            body["language"] = language
        result = await self._request("POST", "/search/smart", json=body)
        assets = result["assets"]["items"]
        if people:
            # A smart search can't say who is in a photo, so the photos are read again.
            found = await self._lookup([asset["id"] for asset in assets], videos, people)
            assets = [found.get(asset["id"], asset) for asset in assets]
        return [photo(asset, people) for asset in assets]

    async def async_on_this_day(
        self, day: date, videos: bool = False, people: bool = False
    ) -> list[dict[str, Any]]:
        """Return photos, and videos if asked, from this day in earlier years, most recent year first."""
        memories = await self._request(
            "GET", "/memories", params={"for": day.isoformat(), "type": "on_this_day"}
        )
        memories.sort(key=lambda memory: memory.get("memoryAt") or "", reverse=True)
        order = [asset["id"] for memory in memories for asset in memory.get("assets", [])]
        found = await self._lookup(list(dict.fromkeys(order)), videos, people)
        photos = [found[asset_id] for asset_id in dict.fromkeys(order) if asset_id in found]
        photos.sort(key=lambda asset: (-int((asset.get("localDateTime") or "0")[:4]), asset.get("localDateTime") or ""))
        return [photo(asset, people) for asset in photos]

    async def async_get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Read one of Immich's JSON endpoints, such as /server/storage."""
        return await self._request("GET", path, params=params)

    async def async_count(self, rules: dict[str, Any]) -> int:
        """Count the items that match a search filter."""
        result = await self._request("POST", "/search/statistics", json={"filter": rules})
        return int(result["total"])

    @asynccontextmanager
    async def async_open_image(self, asset_id: str, size: str) -> AsyncIterator[ImmichImage]:
        """Open one size of a photo, to pass it on as it arrives."""
        if not UUID.match(asset_id):
            raise ImmichNotFoundError("Not a photo ID")
        try:
            response = await self._session.get(
                f"{self._base}/assets/{asset_id}/thumbnail",
                headers={**self._headers, "Accept": "image/*", "Accept-Encoding": "identity"},
                params={"size": size},
                timeout=IMAGE_TIMEOUT,
                allow_redirects=False,
            )
        except TimeoutError as err:
            raise ImmichTimeoutError("Immich took too long to answer") from err
        except ClientError as err:
            raise ImmichConnectionError(f"Couldn't reach Immich: {err}") from err
        # Nothing below catches what the caller raises while it holds the photo,
        # so a browser that goes away is never mistaken for Immich failing.
        try:
            await self._check(response)
            content_type = response.content_type
            if content_type not in IMAGE_TYPES:
                raise ImmichError(f"Immich sent {content_type}, not a photo")
            length = _length(response)
            if length is not None and length > MAX_IMAGE_BYTES:
                raise ImmichError("The photo is too large to pass on")
            yield ImmichImage(content_type, length, self._chunks(response))
        finally:
            response.close()

    async def _chunks(self, response: ClientResponse) -> AsyncIterator[bytes]:
        size = 0
        try:
            async for chunk in response.content.iter_chunked(IMAGE_CHUNK):
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise ImmichError("The photo is too large to pass on")
                yield chunk
        except TimeoutError as err:
            raise ImmichTimeoutError("Immich took too long to answer") from err
        except ClientError as err:
            raise ImmichConnectionError(f"Couldn't reach Immich: {err}") from err

    async def async_image(self, asset_id: str, size: str) -> tuple[bytes, str]:
        """Return one size of a photo, and its content type."""
        try:
            async with asyncio.timeout(IMAGE_SECONDS), self.async_open_image(asset_id, size) as image:
                return await image.async_read(), image.content_type
        except TimeoutError as err:
            raise ImmichTimeoutError("Immich took too long to answer") from err

    async def async_video(self, asset_id: str, byte_range: str | None = None) -> ClientResponse:
        """Open a video, or the part of it a Range header asks for.

        The body is left unread, for the caller to pass on and then close.
        """
        if not UUID.match(asset_id):
            raise ImmichNotFoundError("Not a video ID")
        headers = {**self._headers, "Accept": "video/*", "Accept-Encoding": "identity"}
        if byte_range:
            headers["Range"] = byte_range
        try:
            response = await self._session.get(
                f"{self._base}/assets/{asset_id}/video/playback",
                headers=headers,
                timeout=VIDEO_TIMEOUT,
                allow_redirects=False,
            )
        except TimeoutError as err:
            raise ImmichTimeoutError("Immich took too long to answer") from err
        except ClientError as err:
            raise ImmichConnectionError(f"Couldn't reach Immich: {err}") from err
        try:
            await self._check(response)
            if not response.content_type.startswith("video/"):
                raise ImmichError(f"Immich sent {response.content_type}, not a video")
            if "Content-Encoding" in response.headers:
                # It's unpacked on the way in, so its length and ranges would be wrong.
                raise ImmichError("Immich sent the video compressed")
        except BaseException:
            response.close()
            raise
        return response
