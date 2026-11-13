"""The WebSocket commands the cards use."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from aiohttp import ClientConnectionError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.immich_slideshow import photo_lists
from custom_components.immich_slideshow.api import ImmichClient
from custom_components.immich_slideshow.const import DOMAIN
from custom_components.immich_slideshow.photo_lists import PhotoLists

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


async def test_album_videos_only_when_asked(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    video = make_asset(2, "2020-02-12T10:00:00.000Z", kind="VIDEO")
    album = immich.add_album(1, "Paris", [make_asset(1), video])
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert ids(reply["result"]["photos"]) == [uid(1)]
    assert "video" not in reply["result"]["photos"][0]

    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album, videos=True)
    assert reply["result"]["photos"] == [
        {"id": uid(1), "taken": "2020-02-17T17:18:39.000Z", "city": "Puteaux", "state": "Île-de-France", "country": "France"},
        # Marked as a video, with its length in seconds.
        {"id": uid(2), "taken": "2020-02-12T10:00:00.000Z", "city": "Puteaux", "state": "Île-de-France", "country": "France", "video": True, "duration": 12.345},
    ]
    rules = immich.bodies("/search/metadata")[1]["filter"]
    assert rules["type"] == {"in": ["IMAGE", "VIDEO"]}
    # Still nothing hidden, locked or deleted.
    assert rules["visibility"] == {"notIn": ["hidden", "locked"]}
    assert rules["trashedAt"] == {"eq": None}

    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album, videos=False)
    assert ids(reply["result"]["photos"]) == [uid(1)]


async def test_a_video_of_unknown_length(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    video = make_asset(1, kind="VIDEO")
    video["duration"] = None
    album = immich.add_album(1, "Paris", [video])
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album, videos=True)
    assert reply["result"]["photos"][0]["video"] is True
    assert reply["result"]["photos"][0]["duration"] == 0


@pytest.mark.parametrize("videos", ["yes", 1, None])
async def test_videos_is_on_or_off(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, videos) -> None:
    reply = await ws(type=f"{DOMAIN}/photos", source="random", videos=videos)
    assert reply["error"]["code"] == "invalid_format"


async def test_a_missing_album(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=uid(404))
    assert reply["error"] == {"code": "not_found", "message": "Immich couldn't find the album, or the API key can't read it"}
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


async def test_random_photos_with_videos(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.random = [make_asset(1), make_asset(2, kind="VIDEO")]
    reply = await ws(type=f"{DOMAIN}/photos", source="random", videos=True)
    assert ids(reply["result"]["photos"]) == [uid(1), uid(2)]
    [body] = [b for b in immich.bodies("/search/random") if b["size"] != 1]
    assert body["filter"] == {"type": {"in": ["IMAGE", "VIDEO"]}, "visibility": {"eq": "timeline"}, "trashedAt": {"eq": None}}


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


async def test_search_with_videos(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.smart = [make_asset(1, kind="VIDEO"), make_asset(2)]
    reply = await ws(type=f"{DOMAIN}/photos", source="search", query="snow")
    assert ids(reply["result"]["photos"]) == [uid(2)]
    reply = await ws(type=f"{DOMAIN}/photos", source="search", query="snow", videos=True)
    assert ids(reply["result"]["photos"]) == [uid(1), uid(2)]
    assert reply["result"]["photos"][0]["video"] is True
    assert [body["filter"]["type"] for body in immich.bodies("/search/smart")] == [{"eq": "IMAGE"}, {"in": ["IMAGE", "VIDEO"]}]


async def test_people_only_when_asked(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    faces = ["Ana", ("Hidden", True), "", "Rui", "Ana"]
    album = immich.add_album(1, "Paris", [make_asset(1, people=faces), make_asset(2, "2019-01-01T10:00:00.000Z")])
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert all("people" not in photo for photo in reply["result"]["photos"])
    assert "withPeople" not in immich.bodies("/search/metadata")[0]
    # Asking is another list: the named people who aren't hidden, each once.
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album, people=True)
    assert [photo["people"] for photo in reply["result"]["photos"]] == [["Ana", "Rui"], []]
    assert immich.bodies("/search/metadata")[1]["withPeople"] is True
    # Only the names: nothing else Immich knows about a person.
    assert "1990" not in str(reply)


@pytest.mark.freeze_time("2026-11-08T12:00:00+00:00")
async def test_people_for_every_source(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, freezer) -> None:
    immich.random = [make_asset(1, people=["Ana"])]
    reply = await ws(type=f"{DOMAIN}/photos", source="random", people=True)
    assert reply["result"]["photos"][0]["people"] == ["Ana"]
    assert immich.bodies("/search/random")[0]["withPeople"] is True

    # A smart search can't say who is in a photo, so the photos are read again, in the same order.
    immich.smart = [make_asset(3, people=["Rui"]), make_asset(2, people=["Ana"]), make_asset(4)]
    immich.lookup.update({asset["id"]: asset for asset in immich.smart[:2]})
    reply = await ws(type=f"{DOMAIN}/photos", source="search", query="snow", people=True)
    assert ids(reply["result"]["photos"]) == [uid(3), uid(2), uid(4)]
    assert [photo["people"] for photo in reply["result"]["photos"]] == [["Rui"], ["Ana"], []]
    assert "withPeople" not in immich.bodies("/search/smart")[0]

    day = make_asset(5, "2020-11-08T10:00:00.000Z", people=["Maria"])
    immich.lookup[day["id"]] = day
    immich.memories = [memory(2020, [day])]
    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day", people=True)
    assert reply["result"]["photos"][0]["people"] == ["Maria"]


async def test_a_key_that_cannot_read_people_still_shows_the_photos(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    album = immich.add_album(1, "Paris", [make_asset(1, people=["Ana"])])
    immich.people_forbidden = True
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album, people=True)
    assert ids(reply["result"]["photos"]) == [uid(1)]
    assert "people" not in reply["result"]["photos"][0]
    # The key works, so nobody is asked to enter it again.
    assert not hass.config_entries.flow.async_progress()


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

    # With videos, the video takes its place in the same order.
    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day", videos=True)
    assert ids(reply["result"]["photos"]) == [uid(4), uid(3), uid(2), uid(1)]
    assert reply["result"]["photos"][1]["video"] is True


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
    assert reply["error"] == {"code": "auth_failed", "message": "Immich refused the API key"}
    await hass.async_block_till_done()
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == SOURCE_REAUTH


async def test_immich_down(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.errors["/search"] = ClientConnectionError("refused by 10.0.0.5:2283")
    reply = await ws(type=f"{DOMAIN}/photos", source="random")
    assert reply["error"]["code"] == "unavailable"
    assert reply["error"]["message"] == "Couldn't reach Immich"


@pytest.mark.parametrize(("status", "logged"), [(500, "Immich answered 500: Forced failure"), (302, "Immich's address redirects to another address")])
async def test_what_immich_answered_goes_to_the_log_only(
    hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture, status: int, logged: str
) -> None:
    immich.status["/search"] = status
    reply = await ws(type=f"{DOMAIN}/photos", source="random")
    # Everyone who can see a dashboard sees this message.
    assert reply["error"] == {"code": "unavailable", "message": "Immich gave an unexpected answer. Home Assistant's log has the details."}
    assert logged in caplog.text


async def test_the_same_failure_is_a_warning_once_an_hour(
    hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture, freezer
) -> None:
    def warnings() -> int:
        return sum(r.levelno == logging.WARNING and r.name.endswith(".websocket") for r in caplog.records)

    # A card that can't load asks again every minute.
    immich.status["/search"] = 500
    for _ in range(3):
        await ws(type=f"{DOMAIN}/photos", source="random")
    assert warnings() == 1
    freezer.tick(timedelta(hours=1, seconds=1))
    await ws(type=f"{DOMAIN}/photos", source="random")
    assert warnings() == 2


async def test_a_video_a_browser_could_not_play_goes_to_the_log(
    hass: HomeAssistant, ws, loaded_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    reply = await ws(
        type=f"{DOMAIN}/video_failed", asset=uid(7), reason="format", place="viewer",
        detail="DEMUXER_ERROR_NO_SUPPORTED_STREAMS, loaded 0/4", browser="Mozilla/5.0 (X11; Linux aarch64)",
    )
    assert reply["success"]
    assert (
        f"A browser couldn't play video {uid(7)} in the viewer: format "
        "(DEMUXER_ERROR_NO_SUPPORTED_STREAMS, loaded 0/4). Browser: Mozilla/5.0 (X11; Linux aarch64)"
    ) in caplog.text


async def test_each_reason_is_a_warning_once_an_hour_for_each_browser(
    hass: HomeAssistant, ws, loaded_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture, freezer
) -> None:
    def warnings() -> int:
        return sum(r.levelno == logging.WARNING and r.name.endswith(".websocket") for r in caplog.records)

    # A browser that can't play one video often can't play the next one either.
    for number in (1, 2, 3):
        await ws(type=f"{DOMAIN}/video_failed", asset=uid(number), reason="format", browser="Kiosk")
    assert warnings() == 1
    await ws(type=f"{DOMAIN}/video_failed", asset=uid(1), reason="stalled", browser="Kiosk")
    await ws(type=f"{DOMAIN}/video_failed", asset=uid(1), reason="format", browser="Phone")
    assert warnings() == 3
    freezer.tick(timedelta(hours=1, seconds=1))
    await ws(type=f"{DOMAIN}/video_failed", asset=uid(1), reason="format", browser="Kiosk")
    assert warnings() == 4


async def test_what_a_browser_reports_stays_on_one_line_of_the_log(
    hass: HomeAssistant, ws, loaded_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    await ws(type=f"{DOMAIN}/video_failed", asset=uid(1), reason="unknown", detail="one\nERROR two", browser="Kiosk\r\n")
    assert "unknown (one ERROR two). Browser: Kiosk" in caplog.text


@pytest.mark.parametrize(
    "msg",
    [
        {"asset": "../../etc/passwd", "reason": "format"},
        {"asset": uid(1), "reason": "because"},
        {"asset": uid(1), "reason": "format", "place": "elsewhere"},
        {"asset": uid(1), "reason": "format", "detail": "x" * 301},
        {"asset": uid(1), "reason": "format", "browser": "x" * 301},
        {"reason": "format"},
    ],
)
async def test_rejects_a_report_that_is_not_about_a_video(
    hass: HomeAssistant, ws, loaded_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture, msg: dict[str, Any]
) -> None:
    reply = await ws(type=f"{DOMAIN}/video_failed", **msg)
    assert reply["error"]["code"] == "invalid_format"
    assert "couldn't play" not in caplog.text


async def test_cards_showing_the_same_album_share_one_read(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, freezer) -> None:
    album = immich.add_album(1, "Paris", [make_asset(1, "2020-02-12T10:00:00.000Z")])
    for _ in range(3):
        reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
        assert ids(reply["result"]["photos"]) == [uid(1)]
    assert len(immich.bodies("/search/metadata")) == 1

    # A photo added to the album shows up a few minutes later.
    immich.album_assets[album].append(make_asset(2, "2020-02-13T10:00:00.000Z"))
    freezer.tick(timedelta(minutes=4))
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert ids(reply["result"]["photos"]) == [uid(1)]
    freezer.tick(timedelta(minutes=1, seconds=1))
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert ids(reply["result"]["photos"]) == [uid(2), uid(1)]
    assert len(immich.bodies("/search/metadata")) == 2


async def test_cards_asking_at_the_same_time_share_one_read(
    hass: HomeAssistant, hass_ws_client, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    album = immich.add_album(1, "Paris", [make_asset(1)])
    reads = asked = 0
    answer = asyncio.Event()
    read = ImmichClient.async_album_photos
    get = PhotoLists.async_get

    async def slow_read(self, album_id: str, videos: bool = False, people: bool = False) -> list[dict[str, Any]]:
        nonlocal reads
        reads += 1
        await answer.wait()
        return await read(self, album_id, videos, people)

    async def counted_get(self, key, reader) -> list[dict[str, Any]]:
        nonlocal asked
        asked += 1
        return await get(self, key, reader)

    monkeypatch.setattr(ImmichClient, "async_album_photos", slow_read)
    monkeypatch.setattr(PhotoLists, "async_get", counted_get)
    client = await hass_ws_client(hass)
    for number in (1, 2):
        await client.send_json({"id": number, "type": f"{DOMAIN}/photos", "source": "album", "album": album})
    async with asyncio.timeout(5):
        while asked < 2:
            await asyncio.sleep(0.01)
    answer.set()
    replies = [await client.receive_json(), await client.receive_json()]
    assert sorted(reply["id"] for reply in replies) == [1, 2]
    assert all(ids(reply["result"]["photos"]) == [uid(1)] for reply in replies)
    assert reads == 1


@pytest.mark.freeze_time("2026-11-08T12:00:00+00:00")
async def test_searches_and_on_this_day_are_shared_too(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, freezer) -> None:
    immich.smart = [make_asset(i) for i in range(300)]
    for _ in range(2):
        reply = await ws(type=f"{DOMAIN}/photos", source="search", query="snow", language="pt")
        assert len(reply["result"]["photos"]) == 50
    assert len(immich.bodies("/search/smart")) == 1
    # Another description, number, language or choice of videos is another list.
    for different in ({"query": "beach"}, {"count": 10}, {"language": "es"}, {"videos": True}):
        await ws(type=f"{DOMAIN}/photos", source="search", **{"query": "snow", "language": "pt", **different})
    assert len(immich.bodies("/search/smart")) == 5

    first = make_asset(1, "2020-11-08T10:00:00.000Z")
    second = make_asset(2, "2021-11-08T10:00:00.000Z")
    immich.lookup.update({first["id"]: first, second["id"]: second})
    immich.memories = [memory(2020, [first])]
    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day")
    assert ids(reply["result"]["photos"]) == [uid(1)]
    immich.memories = [memory(2021, [second])]
    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day")
    assert reply["result"]["date"] == "2026-11-08"
    assert ids(reply["result"]["photos"]) == [uid(1)]
    # The next day has its own photos, however recently the last ones were read.
    freezer.move_to("2026-11-09T12:00:00+00:00")
    reply = await ws(type=f"{DOMAIN}/photos", source="on_this_day")
    assert reply["result"]["date"] == "2026-11-09"
    assert ids(reply["result"]["photos"]) == [uid(2)]


async def test_random_photos_are_read_every_time(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.random = [make_asset(i) for i in range(5)]
    for _ in range(2):
        await ws(type=f"{DOMAIN}/photos", source="random")
    assert len([body for body in immich.bodies("/search/random") if body["size"] != 1]) == 2


async def test_a_failed_read_is_not_kept(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    album = immich.add_album(1, "Paris", [make_asset(1)])
    immich.status["/search"] = 500
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert reply["error"]["code"] == "unavailable"
    immich.status.clear()
    reply = await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert ids(reply["result"]["photos"]) == [uid(1)]


async def test_keeps_only_a_few_lists_and_not_for_long(
    hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch, freezer
) -> None:
    monkeypatch.setattr(photo_lists, "MAX_LISTS", 2)
    albums = [immich.add_album(n, f"Album {n}", [make_asset(n)]) for n in (1, 2, 3)]
    for album in albums:
        await ws(type=f"{DOMAIN}/photos", source="album", album=album)
    assert len(immich.bodies("/search/metadata")) == 3
    # The first one made room for the third.
    await ws(type=f"{DOMAIN}/photos", source="album", album=albums[2])
    assert len(immich.bodies("/search/metadata")) == 3
    await ws(type=f"{DOMAIN}/photos", source="album", album=albums[0])
    assert len(immich.bodies("/search/metadata")) == 4

    # Lists nobody asks for again don't stay in memory.
    kept = loaded_entry.runtime_data.photo_lists
    assert len(kept._kept) == 2
    freezer.tick(timedelta(minutes=10, seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert kept._kept == {}


async def test_errors_never_contain_the_key(hass: HomeAssistant, ws, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    for status in (400, 401, 404, 500):
        immich.status = {"/albums": status}
        reply = await ws(type=f"{DOMAIN}/albums")
        assert loaded_entry.data[CONF_API_KEY] not in str(reply)


@pytest.mark.parametrize(
    "msg",
    [
        {"type": f"{DOMAIN}/servers"},
        {"type": f"{DOMAIN}/albums"},
        {"type": f"{DOMAIN}/photos", "source": "random"},
        {"type": f"{DOMAIN}/video_failed", "asset": uid(1), "reason": "format"},
    ],
)
async def test_refuses_a_user_who_is_not_an_admin(hass: HomeAssistant, hass_ws_client, hass_read_only_access_token, immich: FakeImmich, loaded_entry: MockConfigEntry, msg: dict[str, Any]) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass, hass_read_only_access_token)
    before = len(immich.requests)
    await client.send_json({"id": 1, **msg})
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["code"] == "unauthorized"
    assert len(immich.requests) == before
