# Contributing

Bug reports and pull requests are welcome. For a bug, **Download diagnostics** on the integration's page gives a file to attach. It leaves out the API key and the server's address.

## Development

There is no build step. The cards are the single file `custom_components/immich_slideshow/frontend/immich-slideshow.js`.

The integration's tests use Home Assistant's own test tools:

```bash
uv venv .venv --python 3.14
```

```bash
uv pip install --python .venv pytest-homeassistant-custom-component home-assistant-frontend
```

```bash
.venv/bin/python -m pytest
```

The cards' tests run in Chromium and WebKit against `dev/harness.html`, which fakes Home Assistant and the integration with generated images:

```bash
npm install
```

```bash
npx playwright install chromium webkit
```

```bash
npm test
```

The harness also stands in for Home Assistant's `ha-form` component, so check changes to the editors on a real Home Assistant too.

To open the harness yourself, run `node dev/server.js` and go to the address it prints. It takes these address options:

| Option | Effect |
| --- | --- |
| `card=magic` | Shows a card other than the slideshow: `magic` or `on_this_day`. |
| `album=lisbon` | Sets the album: `lisbon`, `demo`, `shapes`, `pair`, `single`, `flaky`, `allbroken`, `empty`, `big` or `denied`. Add `legacy=1` to save it the way the standalone card did. |
| `source=random` | Shows random photos. `randomsize=0` makes the library empty. |
| `query=snow` | Sets the Magic card's description. `nothing` finds no photos. |
| `count=10` | Sets the Magic card's number of photos. |
| `interval=3` | Sets the seconds per photo. |
| `shuffle=0` | Turns shuffle off, or on with `1`. |
| `fit=contain` | Sets the photo fit. |
| `description=year,city` | Sets the description's tags: `date`, `year`, `place`, `country`, `city` or `people`. `show_date=0` and `show_place=0` are the switches of earlier versions. |
| `title=Summer` | Sets the caption. |
| `day=2026-11-09` | Sets the On This Day date. `refreshin=5000` makes the card look for the next day's photos after this many milliseconds, and `nomemories=1` gives a day with no photos. |
| `nopreview=1` | Makes preview images fail, to test the fallback. |
| `nothumb=1` | Makes thumbnails fail, so there's no blurred background. |
| `slowthumb=5000` | Delays thumbnails by this many milliseconds. |
| `box=1` | Puts the card in a fixed-size box, like a dashboard grid cell. |
| `spacer=1` | Starts the card off screen. |
| `multi=1` | Simulates two Immich servers. |
| `nosource=1` | Simulates the integration with no server set up. |
| `nointegration=1` | Simulates the integration not being installed. |
| `notadmin=1` | Simulates a Home Assistant user who isn't an admin. |
| `noform=1` | Makes Home Assistant's form fail to load. |
| `lang=pt` | Sets the language. |
| `editor=1` | Shows the card editor. |

To regenerate the images in `docs/`, run `npm run media`. This needs `ffmpeg`.

## Releasing

The version is written in `manifest.json`, `const.py`, `immich-slideshow.js`, `pyproject.toml`, `package.json` and `package-lock.json`. Change them together: a test fails when they differ.
