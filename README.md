# Home Assistant Immich Slideshow

A Home Assistant integration with three dashboard cards that show photos from your Immich server:

- **Immich Slideshow:** an album, or random photos from your whole library.
- **Immich Magic:** the photos that match a description, such as "beach sunset" or "snow", found by Immich's smart search.
- **Immich On This Day:** photos taken on this day in earlier years.

It also adds an Immich device with your library's counts, the server's storage and jobs, a check for new Immich releases, and two photo entities. See [Entities](#entities).

![The slideshow tile fading between photos](docs/slideshow.gif)

The integration talks to Immich, and the cards talk only to Home Assistant. The API key stays in Home Assistant and never reaches the browser or your dashboard config.

The images on this page use generated landscapes.

## Requirements

- Home Assistant 2025.6 or later. Tested on 2025.6 and 2026.10. The integration's logo shows from 2026.3.
- Immich 3.2 or later. Tested on 3.3.6.
- An Immich API key with these permissions: `album.read`, `asset.read`, `asset.view` and `memory.read`. Create it in Immich under **Account settings > API keys**. The integration only reads from Immich.
- For the statistics, any of these as well: `server.about`, `server.storage`, `server.statistics`, `server.versionCheck`, `queue.read`, `asset.statistics`, `album.statistics`, `memory.statistics`, `person.read`, `tag.read`, `duplicate.read`, `stack.read`, `user.read` and `sharedLink.read`. Statistics the key can't read are left out. `server.statistics` and `queue.read` also need the key of an Immich admin.

## Install

### HACS

1. In HACS, open the menu and choose **Custom repositories**.
2. Add this repository's URL with the type **Integration**.
3. Install **Immich Slideshow** and restart Home Assistant.

### Manual

1. Copy `custom_components/immich_slideshow` into your Home Assistant `custom_components` folder.
2. Restart Home Assistant.

### Set up

1. Go to **Settings > Devices & services**, choose **Add integration** and pick **Immich Slideshow**.
2. Enter the address you open Immich at, such as `http://192.168.1.10:2283`, and the API key.

The integration adds the cards to your dashboards' resources, and takes them away when you remove its last server. If your dashboards keep their resources in YAML, add `/immich_slideshow/immich-slideshow.js` as a JavaScript module yourself.

### Coming from the standalone card

Earlier versions were a card on its own, read through Home Assistant's built-in Immich integration. The cards no longer need that integration.

- Your Immich Slideshow cards keep their album and options.
- The integration removes the old card's dashboard resource. You can delete `immich-slideshow-card.js` from `/config/www/`.

## The cards

Add a card from the card picker and set it up in the editor. Every card can be resized like any other.

### Immich Slideshow

```yaml
type: custom:immich-slideshow-card
album: 3ca29c70-1351-4eef-a80c-6179975662cb
```

```yaml
type: custom:immich-slideshow-card
source: random
```

| Option | Default | Description |
| --- | --- | --- |
| `source` | `album` | `album`, or `random` for random photos from the whole library. |
| `album` | none | The album to show. The editor fills this in for you. |

Random photos are a new set of 100 every round. They leave out hidden, locked, archived and deleted photos, as Immich's own timeline does.

### Immich Magic

```yaml
type: custom:immich-magic-card
query: beach sunset
```

| Option | Default | Description |
| --- | --- | --- |
| `query` | none | What to show, in your own words. |
| `count` | `50` | How many of the closest matches to show, up to 250. |

Smart search always returns the closest photos it can find, even when few are a good match, so a lower `count` keeps only the closest. How well languages other than English work depends on the search model your Immich server uses.

### Immich On This Day

```yaml
type: custom:immich-on-this-day-card
```

It needs no setup. It shows Immich's "on this day" memories, most recent year first, and switches to the new day's photos at midnight in Home Assistant's time zone. On a day with no photos from earlier years, it says so.

### Options for every card

| Option | Default | Description |
| --- | --- | --- |
| `interval` | `10` | Seconds per photo, at least 3. |
| `shuffle` | `true`, or `false` for On This Day | Show photos in random order. |
| `videos` | `false` | Include videos. See [Behavior](#behavior). |
| `fit` | `auto` | How photos fill the tile. See [Photo fit](#photo-fit). |
| `description` | `[date, place]` | What to show under each photo, in order. See [Description](#description). |
| `title` | none | A caption at the bottom of the tile. |
| `server` | the first one | The Immich server, if you set up more than one. The editor shows this only when there's a choice. |

### Description

Each photo shows when and where it was taken, such as "17 August 2023 · Monchique, Portugal". In the editor, the description is a row of tags: add, remove and drag them to choose what it says. In YAML, it's a list, and an empty list shows nothing:

```yaml
description: [people, city, year]
```

| Tag | Shows |
| --- | --- |
| `date` | The full date, such as "17 August 2023". On This Day says how long ago instead, such as "3 years ago". |
| `year` | The year alone. |
| `place` | The city and country, such as "Monchique, Portugal". The region stands in for a missing city. |
| `country` | The country. |
| `city` | The city. |
| `people` | The named people Immich recognized in the photo, such as "Ana and Rui". Hidden people are left out. |

The date is the one on the camera's clock where the photo was taken. The place comes from what Immich found from the photo's location. A tag is left out for a photo that has nothing to show for it. Opened full screen, a photo always shows its date and place.

`show_date: false` and `show_place: false` from earlier versions still work, and the editor turns them into a description.

### Photo fit

When a photo is shown whole, the space around it is filled with a blurred, darkened copy of the same photo instead of empty bars.

| Option | In the editor | What it does |
| --- | --- | --- |
| `auto` | **Automatic** | Fills the tile, unless that would cut off more than 30% of the photo. Then it shows the whole photo. In a wide tile, landscape photos fill it and vertical photos are shown whole. |
| `cover` | **Fill the tile** | Always fills the tile, cropping whatever doesn't fit. |
| `contain` | **Show the whole photo** | Always shows the whole photo. |

The tile decides again whenever it changes size, so a photo that fills a wide tile can be shown whole in a tall one.

### Full screen

Tap a tile to see the current photo full screen, with its date and place. The slideshow pauses while it's open.

![The current photo shown full screen](docs/fullscreen.png)

| Action | Touch | Mouse and keyboard |
| --- | --- | --- |
| Next or previous | Swipe left or right | Arrow keys, or the on-screen buttons |
| Zoom | Pinch, or double-tap | Scroll wheel, or double-click |
| Move a zoomed photo | Drag | Drag |
| Close | Swipe down, or the close button | Esc, or the close button |

## Entities

Each Immich server gets a device called **Immich**, under **Settings > Devices & services > Immich Slideshow**. Statistics are read every 15 minutes, and only those whose entities are turned on. Duplicates and stacks are read every 6 hours, because Immich sends them as whole lists.

### Your library

These count what the API key's user sees: the timeline and the archive, without hidden, locked or deleted items.

| Entity | What it counts | Permission |
| --- | --- | --- |
| Photos, Videos | Photos and videos in the library | `asset.statistics` |
| Favorites, Archived, In the trash | Items marked as such | `asset.statistics` |
| Added in the last 24 hours | Items uploaded since this time yesterday | `asset.statistics` |
| With a place, With people | Items with a location, or with a recognized face | `asset.statistics` |
| Albums, Shared albums | Albums the user owns, and those shared with them | `album.statistics` |
| Memories | Immich's memories | `memory.statistics` |
| On this day | Photos taken on this day in earlier years, as the On This Day card shows them. It changes at midnight. | `memory.read` |
| People | People Immich has recognized | `person.read` |
| Tags | Tags | `tag.read` |
| Duplicates | Sets of duplicates waiting for review | `duplicate.read` |
| Countries, Cities | Places photos were taken. Countries lists them in an attribute. | `asset.read` |
| Camera makes, Camera models | Cameras the photos came from. Camera makes lists them in an attribute, counting "Samsung" and "SAMSUNG" as one. | `asset.read` |

These start turned off. Turn them on from the device page: Photos and videos, Without a place, In an album, Not in an album, Tagged, Rated, Motion photos, Offline, Hidden people, Photos and videos in duplicates, Stacks, Shared links and Lenses.

### The server

These are on the device page under **Diagnostic**.

| Entity | What it shows | Permission |
| --- | --- | --- |
| Disk size, Disk used, Disk free, Disk usage | The disk Immich keeps its files on | `server.storage` |
| Photos on the server, Videos on the server, Storage used | Every user's library together. Storage used by photos, and by videos, start turned off. | `server.statistics`, admin |
| Jobs running, Jobs waiting, Jobs failed | Immich's background jobs, such as thumbnails and face detection. Paused job queues starts turned off. | `queue.read`, admin |
| Users | Users on the server | `user.read` |
| Server | An update entity that turns on when Immich finds a newer release. Update Immich itself as usual; the entity only reports. | `server.about`, `server.versionCheck` |

### Photos

| Entity | What it shows |
| --- | --- |
| Random photo | A random photo from the timeline, changed every 10 minutes |
| On this day photo | The photos taken on this day in earlier years, one at a time, most recent year first, changed every 10 minutes |

Both have the photo's date and place as attributes, and need only the permissions the cards need. Use them in a picture card on any dashboard, or in a notification.

## Behavior

- **Videos:** left out unless you turn on `videos`. A video shows as a still first, then plays once to the end, without sound, and stays for at least the photo interval. If the browser can't play it, or it stops loading for 15 seconds, the still stays and the slideshow moves on. Home Assistant's log then says why, with the browser it happened in: `format` (the browser can't play that kind of video, such as HEVC), `decode`, `network`, `stalled`, `refused` or `link`. Each reason is a warning once an hour for each browser. Full screen, a video has a button to turn its sound on. Videos are streamed through Home Assistant. The photo entities show photos only.
- **Image size:** the tile loads Immich's `preview` size, so it doesn't pull full-resolution files every few seconds. If a preview can't be loaded, it uses the full image. The blurred background uses the much smaller thumbnail, and only loads for photos shown whole.
- **Broken photos:** a photo that won't load is skipped.
- **Pausing:** the slideshow stops, and stops loading images, while the tile is off screen or the browser tab is hidden.
- **Reduced motion:** if your device asks for reduced motion, the tile shows one photo and stays still, with a play button to start and pause the slideshow.
- **New photos:** albums and searches are checked again about once an hour, and the new photos join from the next round. Cards that show the same photos share one list for five minutes, so a photo you just added can take that long to appear after a reload.
- **Errors:** if Immich can't answer, the card says so and tries again every minute. What Immich answered is in Home Assistant's log, not on the dashboard.
- **Access:** only Home Assistant admins can use the cards. They can see every photo and video the API key can see, and search them, whether or not a card has `videos` turned on. Anyone else sees a message on the card instead of photos. Photo links are signed and expire after five minutes, and still work only for an admin. A video's link lasts five minutes longer than the video. The photo entities and the statistics are Home Assistant entities, which every user can see.
- **A refused key:** if Immich refuses the API key, Home Assistant asks for a new one under **Settings > Devices & services**.

## Languages

The cards are available in English, Portuguese, Spanish, French and German. Anything else falls back to English.

Dates follow your Home Assistant language and region.

## License

MIT
