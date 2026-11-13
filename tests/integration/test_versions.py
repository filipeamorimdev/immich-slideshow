"""The version is written in several files, which a release changes together."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib

from custom_components.immich_slideshow.const import VERSION

ROOT = Path(__file__).parents[2]
COMPONENT = ROOT / "custom_components" / "immich_slideshow"


def test_every_file_names_the_same_version() -> None:
    card = re.search(
        r"^const IS_VERSION = '([^']+)';$",
        (COMPONENT / "frontend" / "immich-slideshow.js").read_text(),
        re.MULTILINE,
    )
    assert card, "immich-slideshow.js has no IS_VERSION"
    lock = json.loads((ROOT / "package-lock.json").read_text())
    versions = {
        "manifest.json": json.loads((COMPONENT / "manifest.json").read_text())["version"],
        "immich-slideshow.js": card[1],
        "pyproject.toml": tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"],
        "package.json": json.loads((ROOT / "package.json").read_text())["version"],
        "package-lock.json": lock["version"],
        "package-lock.json, the package itself": lock["packages"][""]["version"],
    }
    assert versions == dict.fromkeys(versions, VERSION)
