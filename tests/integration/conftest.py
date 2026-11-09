"""A fake Immich server, and a set-up config entry that talks to it."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from custom_components.immich_slideshow.const import DOMAIN

URL = "http://immich.local:2283"
API_KEY = "test-key-not-real"


def uid(n: int) -> str:
    """A valid Immich ID."""
    return f"00000000-0000-4000-8000-{n:012d}"


def make_asset(
    n: int,
    taken: str = "2020-02-17T17:18:39.000Z",
    *,
    city: str | None = "Puteaux",
    state: str | None = "Île-de-France",
    country: str | None = "France",
    kind: str = "IMAGE",
) -> dict[str, Any]:
    """An asset as Immich returns it, with the fields the integration reads."""
    return {
        "id": uid(n),
        "type": kind,
        "localDateTime": taken,
        "originalFileName": f"IMG_{n:04d}.JPG",
        "originalPath": f"/photos/IMG_{n:04d}.JPG",
        "exifInfo": {"city": city, "state": state, "country": country, "make": "Apple"},
    }


class FakeImmich:
    """Answers the requests the integration makes, and records them."""

    def __init__(self) -> None:
        self.permissions: list[str] = ["all"]
        self.status: dict[str, int] = {}
        self.errors: dict[str, Exception] = {}
        self.albums: list[dict[str, Any]] = []
        self.shared: list[dict[str, Any]] = []
        self.album_assets: dict[str, list[dict[str, Any]]] = {}
        self.random: list[dict[str, Any]] = []
        self.smart: list[dict[str, Any]] = []
        self.memories: list[dict[str, Any]] = []
        self.lookup: dict[str, dict[str, Any]] = {}
        self.image = (b"\xff\xd8 fake jpeg", "image/jpeg")
        self.requests: list[tuple[str, str, dict[str, list[str]], Any]] = []
        # Statistics, by path. Each answer is what Immich 3.3 sends.
        self.stats: dict[str, Any] = {
            "/server/about": {"version": "v3.3.6", "licensed": False},
            "/server/storage": {
                "diskSize": "683.2 GiB",
                "diskSizeRaw": 733_560_700_928,
                "diskUse": "277.2 GiB",
                "diskUseRaw": 297_613_131_776,
                "diskAvailable": "406.0 GiB",
                "diskAvailableRaw": 435_947_569_152,
                "diskUsagePercentage": 40.57,
            },
            "/server/statistics": {
                "photos": 22366,
                "videos": 896,
                "usage": 284_891_981_224,
                "usagePhotos": 58_153_609_977,
                "usageVideos": 226_738_371_247,
                "usageByUser": [{"userId": uid(901)}, {"userId": uid(902)}],
            },
            "/server/version-check": {"checkedAt": "2026-11-08T20:09:01.474Z", "releaseVersion": "v3.4.0"},
            "/queues": [
                {"name": "thumbnailGeneration", "isPaused": False, "statistics": {"active": 1, "completed": 0, "failed": 2, "delayed": 1, "waiting": 5, "paused": 0}},
                {"name": "smartSearch", "isPaused": True, "statistics": {"active": 0, "completed": 0, "failed": 0, "delayed": 0, "waiting": 0, "paused": 3}},
            ],
            "/albums/statistics": {"owned": 43, "shared": 2, "notShared": 41},
            "/memories/statistics": {"total": 13},
            "/people": {"total": 242, "hidden": 4, "people": [], "hasNextPage": True},
            "/tags": [{"id": uid(801)}, {"id": uid(802)}, {"id": uid(803)}],
            "/users": [{"id": uid(901)}, {"id": uid(902)}],
            "/shared-links": [],
            "/duplicates": [{"duplicateId": uid(701), "assets": [{}, {}]}, {"duplicateId": uid(702), "assets": [{}, {}, {}]}],
            "/stacks": [{"id": uid(601)}],
        }
        # /assets/statistics, by its query.
        self.asset_stats: dict[str, dict[str, int]] = {
            "": {"images": 22363, "videos": 895, "total": 23258},
            "isFavorite=true": {"images": 14, "videos": 1, "total": 15},
            "visibility=archive": {"images": 21, "videos": 1, "total": 22},
            "isTrashed=true": {"images": 8, "videos": 21, "total": 29},
        }
        # /search/statistics, by the rule added to the library filter.
        self.counts: dict[str, int] = {
            "country": 17367,
            "hasPeople": 4217,
            "hasAlbums": 6747,
            "hasTags": 7,
            "rating": 9,
            "isMotion": 237,
            "isOffline": 0,
            "createdAt": 25,
        }
        self.suggestions: dict[str, list[str]] = {
            "country": ["France", "Portugal", "Spain"],
            "city": ["Lisbon", "Paris", "Puteaux", "Monchique"],
            "camera-make": ["Apple", "samsung", "Samsung", "SAMSUNG", "MAKER NAME"],
            "camera-model": ["iPhone 12", "SM-G991B"],
            "camera-lens-model": ["iPhone 12 back camera"],
        }

    def add_album(self, n: int, name: str, assets: Iterable[dict[str, Any]], *, order: str = "desc", shared: bool = False) -> str:
        assets = list(assets)
        album = {"id": uid(n), "albumName": name, "assetCount": len(assets), "order": order}
        (self.shared if shared else self.albums).append(album)
        self.album_assets[album["id"]] = assets
        for asset in assets:
            self.lookup[asset["id"]] = asset
        return album["id"]

    def bodies(self, path: str) -> list[Any]:
        return [body for _, p, _, body in self.requests if p == path]

    def _reply(self, method: str, url: Any, status: int = 200, **kwargs: Any) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(method, url, status=status, **kwargs)

    async def handle(self, method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        path = url.path.removeprefix("/api")
        query = parse_qs(url.query_string)
        self.requests.append((method.upper(), path, query, data))
        for prefix, error in self.errors.items():
            if path.startswith(prefix):
                return self._reply(method, url, exc=error)
        for prefix, status in self.status.items():
            if path.startswith(prefix):
                return self._reply(method, url, status, json={"message": "Forced failure"})

        if path == "/api-keys/me":
            return self._reply(method, url, json={"name": "test", "permissions": self.permissions})
        if path in self.stats:
            return self._reply(method, url, json=self.stats[path])
        if path == "/assets/statistics":
            return self._reply(method, url, json=self.asset_stats[url.query_string])
        if path == "/search/statistics":
            return self._reply(method, url, json={"total": self._count(data["filter"])})
        if path == "/search/suggestions":
            return self._reply(method, url, json=self.suggestions[query["type"][0]])
        if path == "/albums":
            return self._reply(method, url, json=self.shared if query.get("shared") == ["true"] else self.albums)
        if path.startswith("/albums/"):
            album = next((a for a in [*self.albums, *self.shared] if a["id"] == path.split("/")[2]), None)
            if album is None:
                return self._reply(method, url, 400, json={"message": "Not found or no album.read access"})
            return self._reply(method, url, json=album)
        if path == "/search/metadata":
            return self._reply(method, url, json=self._metadata(data))
        if path == "/search/random":
            return self._reply(method, url, json=self.random[: data["size"]])
        if path == "/search/smart":
            items = self.smart[: data["size"]]
            return self._reply(method, url, json={"assets": {"items": items, "nextPage": None}})
        if path == "/memories":
            return self._reply(method, url, json=self.memories)
        if path.endswith("/thumbnail"):
            body, content_type = self.image
            return self._reply(method, url, response=body, headers={"Content-Type": content_type})
        raise AssertionError(f"Unexpected request {method} {path}")

    def _count(self, rules: dict[str, Any]) -> int:
        assert rules["visibility"] == {"in": ["timeline", "archive"]}
        assert rules["trashedAt"] == {"eq": None}
        [(name, rule)] = [(k, v) for k, v in rules.items() if k not in ("visibility", "trashedAt")]
        total = self.counts[name]
        # The fake library has 23,236 items: an "eq False" or "eq None" rule counts the rest.
        if rule in ({"eq": False}, {"eq": None}):
            return 23236 - total
        return total

    def _metadata(self, body: dict[str, Any]) -> dict[str, Any]:
        rules = body["filter"]
        if "albumIds" in rules:
            assets = self.album_assets.get(rules["albumIds"]["any"][0], [])
        else:
            ids = [branch["id"]["eq"] for branch in rules.get("or", [])]
            assets = [self.lookup[i] for i in ids if i in self.lookup and self.lookup[i]["type"] == "IMAGE"]
        start = int(body.get("cursor") or 0)
        end = start + body["size"]
        return {
            "assets": {
                "items": assets[start:end],
                "nextCursor": str(end) if end < len(assets) else None,
            }
        }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture
def immich(aioclient_mock: AiohttpClientMocker) -> FakeImmich:
    """A fake Immich server at URL."""
    server = FakeImmich()
    pattern = re.compile(rf"^{re.escape(URL)}/api/")
    for method in ("get", "post"):
        aioclient_mock.request(method, pattern, side_effect=server.handle)
    return server


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry for the fake server."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="immich.local",
        unique_id=URL,
        data={CONF_URL: URL, CONF_API_KEY: API_KEY, CONF_VERIFY_SSL: True},
    )


@pytest.fixture
async def loaded_entry(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> MockConfigEntry:
    """The config entry, set up."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
