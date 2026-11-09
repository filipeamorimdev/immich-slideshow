"""The WebSocket commands the cards use."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.immich_slideshow.const import DOMAIN

from .conftest import FakeImmich, make_asset, uid


@pytest.fixture
async def ws(hass: HomeAssistant, hass_ws_client):
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)
    counter = iter(range(1, 10_000))

    async def call(**msg: Any) -> dict[str, Any]:
        await client.send_json({"id": next(counter), **msg})
        return await client.receive_json()

    return call


def ids(photos: list[dict[str, Any]]) -> list[str]:
    return [photo["id"] for photo in photos]


async def test_lists_servers(hass: HomeAssistant, ws, loaded_entry: MockConfigEntry) -> None:
    reply = await ws(type=f"{DOMAIN}/servers")
    assert reply["result"] == {"servers": [{"id": loaded_entry.entry_id, "name": "immich.local"}]}


async def test_lists_owned_and_shared_albums_by_name(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.add_album(1, "paris", [make_asset(1)])
    immich.add_album(2, "Algarve", [make_asset(2), make_asset(3)])
    immich.add_album(3, "Family", [], shared=True)
    reply = await ws(type=f"{DOMAIN}/albums")
    assert reply["success"]
    assert reply["result"]["server"] == loaded_entry.entry_id
    assert reply["result"]["albums"] == [
        {"id": uid(2), "name": "Algarve", "count": 2},
        {"id": uid(3), "name": "Family", "count": 0},
        {"id": uid(1), "name": "paris", "count": 1},
    ]


async def test_album_photos_with_date_and_place(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    album = immich.add_album(1, "Paris", [make_asset(1, "2020-02-12T10:00:00.000Z"), make_asset(2, "2020-02-17T17:18:39.000Z", city=None, state=None, country=None)])
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert reply["result"]["photos"] == [
        {"id": uid(2), "taken": "2020-02-17T17:18:39.000Z", "city": None, "state": None, "country": None},
        {"id": uid(1), "taken": "2020-02-12T10:00:00.000Z", "city": "Puteaux", "state": "Île-de-France", "country": "France"},
    ]
    # Never the file name, path or camera.
    assert "IMG_" not in str(reply)


async def test_album_photos_follow_the_album_order(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    assets = [make_asset(i, f"2020-02-{10 + i}T10:00:00.000Z") for i in (3, 1, 2)]
    album = immich.add_album(1, "Oldest first", assets, order="asc")
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert ids(reply["result"]["photos"]) == [uid(1), uid(2), uid(3)]


async def test_album_photos_page_through_big_albums(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    assets = [make_asset(i, f"2020-01-01T00:00:{i % 60:02d}.000Z") for i in range(2500)]
    album = immich.add_album(9999, "Big", assets)
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert len(reply["result"]["photos"]) == 2500
    assert len(set(ids(reply["result"]["photos"]))) == 2500
    bodies = immich.bodies("/search/metadata")
    assert [body.get("cursor") for body in bodies] == [None, "1000", "2000"]
    assert "page" not in bodies[0]


async def test_album_photos_leave_out_videos_hidden_locked_and_deleted(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    album = immich.add_album(1, "Paris", [make_asset(1)])
    await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    rules = immich.bodies("/search/metadata")[0]["filter"]
    assert rules["albumIds"] == {"any": [album]}
    assert rules["type"] == {"eq": "IMAGE"}
    assert rules["visibility"] == {"notIn": ["hidden", "locked"]}
    assert rules["trashedAt"] == {"eq": None}


async def test_a_missing_album(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=uid(404))
    assert reply["error"]["code"] == "not_found"
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album="../../users")
    assert reply["error"]["code"] == "not_found"
    reply = await ws(type=f"{DOMAIN}/photos", source="album")
    assert reply["error"]["code"] == "invalid_format"


async def test_random_photos_only_from_the_timeline(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.random = [make_asset(i) for i in range(150)]
    reply = await ws(type=f"{DOMAIN}/photos", source="random")
    assert len(reply["result"]["photos"]) == 100
    # The random photo entity asks for one photo too, before or after the card depending on the version.
    [body] = [b for b in immich.bodies("/search/random") if b["size"] != 1]
    assert body["size"] == 100
    assert body["withExif"] is True
    # Timeline only: no hidden, locked or archived photos, nothing deleted, no videos.
    assert body["filter"] == {"type": {"eq": "IMAGE"}, "visibility": {"eq": "timeline"}, "trashedAt": {"eq": None}}


async def test_search_photos(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.smart = [make_asset(i) for i in range(300)]
    reply = await ws(type=f"{DOMAIN}/photos", source="search", query="  beach sunset ", language="pt")
    assert len(reply["result"]["photos"]) == 50
    body = immich.bodies("/search/smart")[0]
    assert body["query"] == "beach sunset"
    assert body["language"] == "pt"
    assert body["filter"]["visibility"] == {"eq": "timeline"}
    reply = await ws(type=f"{DOMAIN}/photos", source="search", query="snow", count=250)
    assert len(reply["result"]["photos"]) == 250
    assert "language" not in immich.bodies("/search/smart")[1]


@pytest.mark.parametrize("msg", [{"query": ""}, {"query": "   "}, {}])
async def test_search_needs_a_description(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, msg) -> None:
    reply = await ws(type=f"{DOMAIN}/photos", source="search", **msg)
    assert reply["error"]["code"] == "invalid_format"
    assert immich.bodies("/search/smart") == []


@pytest.mark.parametrize("count", [0, 251, "50"])
async def test_search_count_limits(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, count) -> None:
    reply = await ws(type=f"{DOMAIN}/photos", source="search", query="snow", count=count)
    assert reply["error"]["code"] == "invalid_format"


async def test_rejects_unknown_sources(hass: HomeAssistant, ws, loaded_entry: MockConfigEntry) -> None:
    reply = await ws(type=f"{DOMAIN}/photos", source="favorites")
    assert reply["error"]["code"] == "invalid_format"


def memory(year: int, assets: list[dict[str, Any]]) -> dict[str, Any]:
    # Like Immich, memories list their photos without places.
    return {
        "type": "on_this_day",
        "data": {"year": year},
        "memoryAt": f"{year}-11-08T00:00:00.000Z",
        "assets": [{key: value for key, value in asset.items() if key != "exifInfo"} for asset in assets],
    }


@pytest.mark.freeze_time("2026-11-08T23:30:00+00:00")
async def test_on_this_day(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    await hass.config.async_set_time_zone("Europe/Lisbon")
    older = [make_asset(1, "2017-11-08T09:00:00.000Z", city="Lisbon"), make_asset(2, "2017-11-08T08:00:00.000Z", city="Parque das Nações")]
    video = make_asset(3, "2025-11-08T12:00:00.000Z", kind="VIDEO")
    recent = [make_asset(4, "2025-11-08T11:09:50.000Z", city="Mozelos"), video]
    for asset in [*older, *recent]:
        immich.lookup[asset["id"]] = asset
    immich.memories = [memory(2017, older), memory(2025, recent)]

    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day")
    result = reply["result"]
    # Most recent year first, earliest photo first within a year, and no videos.
    assert ids(result["photos"]) == [uid(4), uid(2), uid(1)]
    assert result["photos"][0]["city"] == "Mozelos"
    assert result["date"] == "2026-11-08"
    assert result["refresh_at"] == int(datetime.fromisoformat("2026-11-09T00:00:00+00:00").timestamp() * 1000)
    query = next(q for _, path, q, _ in immich.requests if path == "/memories")
    assert query == {"for": ["2026-11-08"], "type": ["on_this_day"]}


@pytest.mark.freeze_time("2026-11-08T23:30:00+00:00")
async def test_on_this_day_follows_home_assistants_time_zone(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    await hass.config.async_set_time_zone("Pacific/Auckland")
    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day")
    assert reply["result"]["date"] == "2026-11-09"
    assert reply["result"]["photos"] == []


async def test_on_this_day_looks_up_places_in_batches(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    assets = [make_asset(i, f"2020-11-08T10:{i // 60 % 60:02d}:{i % 60:02d}.000Z") for i in range(250)]
    for asset in assets:
        immich.lookup[asset["id"]] = asset
    immich.memories = [memory(2020, assets)]
    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day")
    assert len(reply["result"]["photos"]) == 250
    batches = [len(body["filter"]["or"]) for body in immich.bodies("/search/metadata")]
    assert batches == [100, 100, 50]
    assert all(body["filter"]["visibility"] == {"eq": "timeline"} for body in immich.bodies("/search/metadata"))


async def test_needs_a_server(hass: HomeAssistant, ws, immich: FakeImmich) -> None:
    reply = await ws(type=f"{DOMAIN}/albums")
    assert reply["error"]["code"] == "not_configured"
    reply = await ws(type=f"{DOMAIN}/servers")
    assert reply["result"] == {"servers": []}


async def test_picks_the_named_server(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    reply = await ws(type=f"{DOMAIN}/albums", server=loaded_entry.entry_id)
    assert reply["success"]
    reply = await ws(type=f"{DOMAIN}/albums", server="unknown")
    assert reply["error"]["code"] == "not_configured"


async def test_a_refused_key_asks_for_a_new_one(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.status["/albums"] = 401
    reply = await ws(type=f"{DOMAIN}/albums")
    assert reply["error"]["code"] == "auth_failed"
    await hass.async_block_till_done()
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == SOURCE_REAUTH


async def test_immich_down(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.errors["/search"] = ClientConnectionError("refused by 10.0.0.5:2283")
    reply = await ws(type=f"{DOMAIN}/photos", source="random")
    assert reply["error"]["code"] == "unavailable"
    assert reply["error"]["message"] == "Couldn't reach Immich"
    immich.errors.clear()
    immich.status["/search"] = 500
    reply = await ws(type=f"{DOMAIN}/photos", source="random")
    assert reply["error"]["code"] == "unavailable"
    assert "Forced failure" in reply["error"]["message"]


async def test_errors_never_contain_the_key(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    for status in (400, 401, 404, 500):
        immich.status = {"/albums": status}
        reply = await ws(type=f"{DOMAIN}/albums")
        assert loaded_entry.data[CONF_API_KEY] not in str(reply)
