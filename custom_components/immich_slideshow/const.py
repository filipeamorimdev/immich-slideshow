"""Constants for the Immich Slideshow integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "immich_slideshow"

# Keep in step with manifest.json and IS_VERSION in frontend/immich-slideshow.js.
VERSION = "0.6.0"

FRONTEND_PATH = f"/{DOMAIN}"
CARD_URL = f"{FRONTEND_PATH}/immich-slideshow.js"
# The standalone card this integration replaces. Its resource would define the
# same elements, and whichever loads first wins.
LEGACY_CARD_FILE = "immich-slideshow-card.js"

IMAGE_SIZES = ("thumbnail", "preview", "fullsize")

# Everything the cards read. The integration never writes to Immich.
REQUIRED_PERMISSIONS = ("album.read", "asset.read", "asset.view", "memory.read")
# Each group of statistics needs one of these. Without it, those entities are left out.
STATISTICS_PERMISSIONS = (
    "server.about",
    "server.storage",
    "server.statistics",
    "server.versionCheck",
    "queue.read",
    "asset.statistics",
    "album.statistics",
    "memory.statistics",
    "person.read",
    "tag.read",
    "duplicate.read",
    "stack.read",
    "user.read",
    "sharedLink.read",
)

RANDOM_COUNT = 100
SEARCH_COUNT = 50
SEARCH_MAX = 250

STATS_INTERVAL = timedelta(minutes=15)
# Duplicates and stacks come back as whole lists, megabytes on a large library.
SLOW_STATS_INTERVAL = timedelta(hours=6)
PHOTO_INTERVAL = timedelta(minutes=10)
