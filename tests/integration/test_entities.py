"""The server's device, its statistics sensors, the update entity and the photo entities."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.immich_slideshow.const import DOMAIN, PHOTO_INTERVAL, STATS_INTERVAL

from .conftest import URL, FakeImmich, make_asset, uid


def server_device(hass: HomeAssistant, entry: MockConfigEntry) -> dr.DeviceEntry | None:
    # Looked up through the entry, which works on every supported Home Assistant version.
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    return next((d for d in devices if (DOMAIN, entry.entry_id) in d.identifiers), None)


def entity_id(hass: HomeAssistant, entry: MockConfigEntry, key: str, platform: str = "sensor") -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")


def value(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    eid = entity_id(hass, entry, key)
    assert eid, f"no sensor for {key}"
    state = hass.states.get(eid)
    assert state, f"{eid} has no state"
    return state.state


def memory(year: int, assets: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "on_this_day", "data": {"year": year}, "memoryAt": f"{year}-11-08T00:00:00.000Z", "assets": assets}


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_one_service_device_per_server(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    device = server_device(hass, loaded_entry)
    assert device is not None
    assert device.name == "Immich"
    assert device.manufacturer == "Immich"
    assert device.sw_version == "v3.3.6"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.configuration_url == URL
    entities = er.async_entries_for_config_entry(er.async_get(hass), loaded_entry.entry_id)
    assert entities
    assert {entity.device_id for entity in entities} == {device.id}


async def test_library_counts(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    expected = {
        "photos": "22363",
        "videos": "895",
        "favorites": "15",
        "archived": "22",
        "trash": "29",
        "added_recently": "25",
        "located": "17367",
        "with_people": "4217",
        "albums": "43",
        "shared_albums": "2",
        "memories": "13",
        "people": "242",
        "tags": "3",
        "duplicates": "2",
        "cities": "4",
        "camera_models": "2",
    }
    assert {key: value(hass, loaded_entry, key) for key in expected} == expected


async def test_places_and_cameras(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    countries = hass.states.get(entity_id(hass, loaded_entry, "countries"))
    assert countries.state == "3"
    assert countries.attributes["countries"] == ["France", "Portugal", "Spain"]
    # "samsung", "Samsung" and "SAMSUNG" are one make.
    makes = hass.states.get(entity_id(hass, loaded_entry, "camera_makes"))
    assert makes.state == "3"
    assert makes.attributes["makes"] == ["Apple", "MAKER NAME", "samsung"]


async def test_counts_only_the_library(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    # Hidden, locked and trashed items are never counted; FakeImmich checks each filter.
    filters = [body["filter"] for body in immich.bodies("/search/statistics")]
    assert len(filters) == 10
    since = next(f["createdAt"]["gte"] for f in filters if "createdAt" in f)
    assert since.endswith("+00:00")


async def test_server_and_disk(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    assert value(hass, loaded_entry, "server_photos") == "22366"
    assert value(hass, loaded_entry, "server_videos") == "896"
    assert value(hass, loaded_entry, "users") == "2"
    # Waiting counts delayed and paused jobs too.
    assert value(hass, loaded_entry, "jobs_active") == "1"
    assert value(hass, loaded_entry, "jobs_waiting") == "9"
    assert value(hass, loaded_entry, "jobs_failed") == "2"
    usage = hass.states.get(entity_id(hass, loaded_entry, "server_usage"))
    assert usage.attributes["unit_of_measurement"] == "GiB"
    assert float(usage.state) == pytest.approx(284_891_981_224 / 2**30)
    assert float(value(hass, loaded_entry, "disk_available")) == pytest.approx(435_947_569_152 / 2**30)
    assert value(hass, loaded_entry, "disk_usage") == "40.57"


async def test_some_sensors_start_disabled(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    registry = er.async_get(hass)
    for key in ("lenses", "stacks", "motion", "server_usage_photos", "queues_paused"):
        entry = registry.async_get(entity_id(hass, loaded_entry, key))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION, key
    assert registry.async_get(entity_id(hass, loaded_entry, "photos")).disabled_by is None


async def test_leaves_out_what_the_key_cant_read(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    # A key that isn't an admin's, and lacks asset.statistics.
    immich.status["/server/statistics"] = 403
    immich.status["/queues"] = 403
    immich.status["/assets/statistics"] = 403
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()
    for key in ("server_photos", "server_usage", "jobs_waiting", "photos", "favorites"):
        assert entity_id(hass, config_entry, key) is None, key
    assert value(hass, config_entry, "albums") == "43"
    # It doesn't ask again.
    immich.requests.clear()
    await refresh(hass, config_entry)
    assert not [path for _, path, _, _ in immich.requests if path in ("/server/statistics", "/queues", "/assets/statistics")]


async def test_leaves_out_what_an_older_immich_doesnt_have(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    immich.status["/queues"] = 404
    await setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert entity_id(hass, config_entry, "jobs_active") is None
    assert value(hass, config_entry, "photos") == "22363"


async def test_one_failing_statistic_doesnt_stop_the_rest(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.status["/people"] = 500
    await refresh(hass, loaded_entry)
    assert value(hass, loaded_entry, "people") == STATE_UNAVAILABLE
    assert value(hass, loaded_entry, "photos") == "22363"
    del immich.status["/people"]
    await refresh(hass, loaded_entry)
    assert value(hass, loaded_entry, "people") == "242"


async def test_unreachable_server(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.errors["/server"] = ClientConnectionError()
    await refresh(hass, loaded_entry)
    assert value(hass, loaded_entry, "photos") == STATE_UNAVAILABLE
    del immich.errors["/server"]
    await refresh(hass, loaded_entry)
    assert value(hass, loaded_entry, "photos") == "22363"


async def test_refused_key_asks_for_a_new_one(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.status["/server/about"] = 401
    await refresh(hass, loaded_entry)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_updates_every_15_minutes(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    immich.asset_stats[""] = {"images": 23000, "videos": 900, "total": 23900}
    freezer.tick(STATS_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert value(hass, loaded_entry, "photos") == "23000"


async def test_reads_duplicates_and_stacks_every_6_hours(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    def reads() -> int:
        return len([p for _, p, _, _ in immich.requests if p == "/duplicates"])

    assert reads() == 1
    immich.stats["/duplicates"] = []
    await refresh(hass, loaded_entry)
    assert reads() == 1
    assert value(hass, loaded_entry, "duplicates") == "2"
    freezer.tick(timedelta(hours=6))
    await refresh(hass, loaded_entry)
    assert reads() == 2
    assert value(hass, loaded_entry, "duplicates") == "0"


@pytest.mark.freeze_time("2026-11-08T12:00:00+00:00")
async def test_on_this_day_count(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    trashed = {**make_asset(3, "2020-11-08T10:00:00.000Z"), "isTrashed": True}
    archived = {**make_asset(4, "2020-11-08T10:00:00.000Z"), "visibility": "archive"}
    video = make_asset(5, "2020-11-08T10:00:00.000Z", kind="VIDEO")
    immich.memories = [
        memory(2025, [make_asset(1, "2025-11-08T10:00:00.000Z")]),
        memory(2020, [make_asset(2, "2020-11-08T10:00:00.000Z"), trashed, archived, video]),
    ]
    await hass.config.async_set_time_zone("UTC")
    await setup(hass, config_entry)
    assert value(hass, config_entry, "on_this_day") == "2"

    # It changes at midnight, without waiting for the next update.
    immich.memories = []
    freezer.move_to("2026-11-09T00:00:06+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert value(hass, config_entry, "on_this_day") == "0"
    days = [q["for"][0] for _, p, q, _ in immich.requests if p == "/memories"]
    assert days[-1] == "2026-11-09"


async def test_update_entity(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    eid = entity_id(hass, loaded_entry, "update", "update")
    state = hass.states.get(eid)
    assert state.state == STATE_ON
    assert state.attributes["installed_version"] == "v3.3.6"
    assert state.attributes["latest_version"] == "v3.4.0"
    assert state.attributes["release_url"] == "https://github.com/immich-app/immich/releases/tag/v3.4.0"
    assert state.attributes["supported_features"] == 0

    # Up to date, or Immich's own version check turned off.
    immich.stats["/server/version-check"] = {"checkedAt": None, "releaseVersion": None}
    await refresh(hass, loaded_entry)
    assert hass.states.get(eid).state == STATE_OFF


async def test_device_follows_the_server_version(hass: HomeAssistant, immich: FakeImmich, loaded_entry: MockConfigEntry) -> None:
    immich.stats["/server/about"] = {"version": "v3.4.0"}
    await refresh(hass, loaded_entry)
    device = server_device(hass, loaded_entry)
    assert device.sw_version == "v3.4.0"


async def test_no_update_entity_without_the_version_check(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    immich.status["/server/version-check"] = 403
    await setup(hass, config_entry)
    assert entity_id(hass, config_entry, "update", "update") is None


async def test_random_photo(hass: HomeAssistant, hass_client, immich: FakeImmich, config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    immich.random = [make_asset(1, "2020-02-17T17:18:39.000Z")]
    await setup(hass, config_entry)
    eid = entity_id(hass, config_entry, "random_photo", "image")
    state = hass.states.get(eid)
    assert state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
    assert state.attributes["taken"] == "2020-02-17T17:18:39.000Z"
    assert state.attributes["city"] == "Puteaux"
    assert state.attributes["country"] == "France"
    assert next(body for body in immich.bodies("/search/random"))["size"] == 1

    client = await hass_client()
    for _ in range(2):
        response = await client.get(state.attributes["entity_picture"])
        assert response.status == 200
        assert await response.read() == immich.image[0]
    thumbnails = [(p, q) for _, p, q, _ in immich.requests if p.endswith("/thumbnail")]
    # Loaded once, at the preview size.
    assert thumbnails == [(f"/assets/{uid(1)}/thumbnail", {"size": ["preview"]})]

    immich.random = [make_asset(2, city="Lisbon", country="Portugal")]
    freezer.tick(PHOTO_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    changed = hass.states.get(eid)
    assert changed.state != state.state
    assert changed.attributes["city"] == "Lisbon"


async def test_random_photo_survives_a_failure(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    immich.random = [make_asset(1)]
    await setup(hass, config_entry)
    eid = entity_id(hass, config_entry, "random_photo", "image")
    immich.status["/search/random"] = 500
    freezer.tick(PHOTO_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == STATE_UNAVAILABLE
    del immich.status["/search/random"]
    freezer.tick(PHOTO_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(eid).state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)


@pytest.mark.freeze_time("2026-11-08T12:00:00+00:00")
async def test_on_this_day_photo(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory) -> None:
    older = make_asset(1, "2017-11-08T09:00:00.000Z", city="Lisbon")
    recent = make_asset(2, "2025-11-08T11:00:00.000Z", city="Mozelos")
    for asset in (older, recent):
        immich.lookup[asset["id"]] = asset
    immich.memories = [memory(2017, [older]), memory(2025, [recent])]
    await setup(hass, config_entry)
    eid = entity_id(hass, config_entry, "on_this_day_photo", "image")

    cities = []
    for _ in range(3):
        cities.append(hass.states.get(eid).attributes["city"])
        freezer.tick(PHOTO_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    # Most recent year first, then around again.
    assert cities == ["Mozelos", "Lisbon", "Mozelos"]


async def test_on_this_day_photo_on_a_day_without_any(hass: HomeAssistant, immich: FakeImmich, config_entry: MockConfigEntry) -> None:
    await setup(hass, config_entry)
    state = hass.states.get(entity_id(hass, config_entry, "on_this_day_photo", "image"))
    assert state.state == STATE_UNKNOWN
    assert "city" not in state.attributes


async def test_unload_removes_the_entities_state(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    eid = entity_id(hass, loaded_entry, "photos")
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == STATE_UNAVAILABLE
