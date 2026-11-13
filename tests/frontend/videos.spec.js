const { test, expect } = require('@playwright/test');
const { CARD, VIEWER, open, shown, expectShown, calls, advance } = require('./helpers');

// The "clips" album holds a photo, a two-second video and a photo. A video shows as
// its still, so `shown` reports it like a photo.
const CLIP = `${CARD} video.clip`;
const PLAYING = `${CLIP}.on`;
const PLAY = `${CARD} .play`;

// What the video on the tile is doing.
function clip(page) {
  return page.evaluate(() => {
    const video = document.querySelector('#card').shadowRoot.querySelector('.stage > :last-child video.clip');
    return video && { muted: video.muted, paused: video.paused, ended: video.ended, time: video.currentTime };
  });
}

const ended = (page) => expect.poll(async () => (await clip(page))?.ended, { timeout: 10000 }).toBe(true);
const videosSigned = async (page) => (await calls(page)).signed.filter((path) => path.endsWith('/video'));

// Opens the clips album and moves on to its video.
async function showVideo(page, interval = 3) {
  await open(page, `album=clips&videos=1&shuffle=0&interval=${interval}`);
  await expectShown(page, 'clips-0 preview');
  await advance(page, interval * 1000 + 100);
  await expectShown(page, 'clips-1 preview');
}

test('leaves videos out unless they are turned on', async ({ page }) => {
  await open(page, 'album=clips&shuffle=0&interval=3');
  await expectShown(page, 'clips-0 preview');
  expect((await calls(page)).requests).toEqual([{ type: 'immich_slideshow/photos', source: 'album', album: 'clips' }]);
  await advance(page, 3100);
  await expectShown(page, 'clips-2 preview');
  await expect(page.locator(CLIP)).toHaveCount(0);
  expect(await videosSigned(page)).toEqual([]);
});

test('asks the integration for videos when they are turned on', async ({ page }) => {
  await open(page, 'album=clips&videos=1&shuffle=0');
  await expectShown(page, 'clips-0 preview');
  expect((await calls(page)).requests).toEqual([
    { type: 'immich_slideshow/photos', source: 'album', album: 'clips', videos: true },
  ]);
});

for (const [name, query, source] of [
  ['random photos', 'source=random', 'random'],
  ['Magic', 'card=magic&query=snow', 'search'],
  ['On This Day', 'card=on_this_day', 'on_this_day'],
]) {
  test(`${name} can ask for videos too`, async ({ page }) => {
    await open(page, `${query}&videos=1`);
    await expect.poll(async () => (await calls(page)).requests.length).toBeGreaterThan(0);
    expect((await calls(page)).requests[0]).toMatchObject({ source, videos: true });
  });
}

test('plays a video over its still, without sound', async ({ page }) => {
  await open(page, 'album=clips&videos=1&shuffle=0&interval=3');
  await expectShown(page, 'clips-0 preview');
  // The video is next, and so far only its still has loaded.
  await page.evaluate(() => Promise.resolve(document.getElementById('card')._nextSlide).then(() => true));
  expect((await calls(page)).signed).toContain('/api/immich_slideshow/server-1/clips-1/preview');
  expect(await videosSigned(page)).toEqual([]);

  await advance(page, 3100);
  await expectShown(page, 'clips-1 preview');
  await expect(page.locator(PLAYING)).toHaveCount(1);
  expect(await clip(page)).toMatchObject({ muted: true, paused: false });
  expect(await videosSigned(page)).toEqual(['/api/immich_slideshow/server-1/clips-1/video']);
  const fit = await page.locator(PLAYING).evaluate((video) => getComputedStyle(video).objectFit);
  expect(fit).toBe('cover');
});

test('a short video stays for as long as a photo', async ({ page }) => {
  await showVideo(page, 30);
  await ended(page);
  // Two seconds of video, and 28 more of its last frame.
  await advance(page, 20000);
  expect(await shown(page)).toBe('clips-1 preview');
  await expect(page.locator(PLAYING)).toHaveCount(1);
  await advance(page, 10100);
  await expectShown(page, 'clips-2 preview');
});

test('a video longer than the interval plays to its end', async ({ page }) => {
  await showVideo(page);
  await expect(page.locator(PLAYING)).toHaveCount(1);
  // A photo would make way now.
  await advance(page, 3100);
  expect(await shown(page)).toBe('clips-1 preview');
  expect(await clip(page)).toMatchObject({ ended: false });
  await expectShown(page, 'clips-2 preview');
  // The photo after it gets its whole interval.
  await advance(page, 2000);
  expect(await shown(page)).toBe('clips-2 preview');
});

test("a video's link lasts as long as the video", async ({ page }) => {
  await showVideo(page);
  await expect(page.locator(PLAYING)).toHaveCount(1);
  const { expires } = await calls(page);
  expect(expires['/api/immich_slideshow/server-1/clips-0/preview']).toBe(300);
  expect(expires['/api/immich_slideshow/server-1/clips-1/preview']).toBe(300);
  expect(expires['/api/immich_slideshow/server-1/clips-1/video']).toBe(302);
});

test("keeps the still when the video can't be played, and moves on", async ({ page }) => {
  await open(page, 'album=badclip&videos=1&shuffle=0&interval=3');
  await expectShown(page, 'badclip-0 preview');
  await expect.poll(() => videosSigned(page)).toHaveLength(1);
  await expect(page.locator(PLAYING)).toHaveCount(0);
  await expect(page.locator(`${CARD} .message`)).toBeHidden();
  await advance(page, 3100);
  await expectShown(page, 'badclip-1 preview');
});

test('gives up on a video that stops loading', async ({ page }) => {
  // The video never arrives.
  await page.route('**/dev/clip.webm*', () => {});
  await showVideo(page);
  await expect.poll(() => videosSigned(page)).toHaveLength(1);
  await advance(page, 9000);
  expect(await shown(page)).toBe('clips-1 preview');
  await advance(page, 6100);
  await expectShown(page, 'clips-2 preview');
});

test("tells Home Assistant why a video couldn't be played", async ({ page }) => {
  await open(page, 'album=badclip&videos=1&shuffle=0&interval=3');
  await expectShown(page, 'badclip-0 preview');
  await expect.poll(async () => (await calls(page)).videoFailures).toHaveLength(1);
  const [failure] = (await calls(page)).videoFailures;
  expect(failure).toMatchObject({ type: 'immich_slideshow/video_failed', asset: 'badclip-0', reason: 'format', place: 'slideshow' });
  expect(failure.browser).toBe(await page.evaluate(() => navigator.userAgent));
  expect(failure.detail).toContain('loaded 0/4');
});

test('tells Home Assistant when a video stopped loading', async ({ page }) => {
  await page.route('**/dev/clip.webm*', () => {});
  await showVideo(page);
  await advance(page, 15100);
  await expect.poll(async () => (await calls(page)).videoFailures).toHaveLength(1);
  expect((await calls(page)).videoFailures[0]).toMatchObject({ asset: 'clips-1', reason: 'stalled', place: 'slideshow' });
});

test('says nothing to Home Assistant about a video that played', async ({ page }) => {
  await showVideo(page, 30);
  await ended(page);
  expect((await calls(page)).videoFailures).toEqual([]);
});

test('pauses the video while the browser tab is hidden, and carries on after', async ({ page }) => {
  await showVideo(page);
  await expect(page.locator(PLAYING)).toHaveCount(1);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  const paused = await clip(page);
  expect(paused).toMatchObject({ paused: true, ended: false });
  await advance(page, 9000);
  expect(await clip(page)).toMatchObject({ paused: true, time: paused.time });
  expect(await shown(page)).toBe('clips-1 preview');

  await page.evaluate(() => {
    delete document.hidden;
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect.poll(async () => (await clip(page)).time).toBeGreaterThan(paused.time);
  await expectShown(page, 'clips-2 preview');
});

test('an only video plays again and again', async ({ page }) => {
  await open(page, 'album=clip&videos=1&interval=3');
  await expectShown(page, 'clip-0 preview');
  await expect(page.locator(PLAYING)).toHaveCount(1);
  await ended(page);
  await page.evaluate(() => { window.__first = document.querySelector('#card').shadowRoot.querySelector('video.clip'); });
  await advance(page, 3100);
  // A new video element plays, from the link the first one had.
  await expect.poll(() => page.evaluate(() => {
    const video = document.querySelector('#card').shadowRoot.querySelector('.stage > :last-child video.clip');
    return Boolean(video && video !== window.__first && !video.paused);
  })).toBe(true);
  expect(await videosSigned(page)).toHaveLength(1);
});

test('lets go of a video once its slide is gone', async ({ page }) => {
  // A long interval, so the video is still on screen when it has ended.
  await showVideo(page, 30);
  await expect(page.locator(PLAYING)).toHaveCount(1);
  await page.evaluate(() => { window.__first = document.querySelector('#card').shadowRoot.querySelector('video.clip'); });
  await ended(page);
  expect(await page.evaluate(() => window.__first.getAttribute('src'))).toContain('clip.webm');
  await advance(page, 30100);
  await expectShown(page, 'clips-2 preview');
  // The old slide leaves after the fade.
  await advance(page, 1200);
  await expect.poll(() => page.evaluate(() => ({ onPage: window.__first.isConnected, src: window.__first.getAttribute('src') }))).toEqual({ onPage: false, src: null });
});

test('asks for a new link after a video failed', async ({ page }) => {
  await open(page, 'album=badclip&videos=1&shuffle=0&interval=3');
  await expectShown(page, 'badclip-0 preview');
  await expect.poll(() => videosSigned(page)).toHaveLength(1);
  await advance(page, 3100);
  await expectShown(page, 'badclip-1 preview');
  await advance(page, 3100);
  await expectShown(page, 'badclip-0 preview');
  await expect.poll(() => videosSigned(page)).toHaveLength(2);
});

test.describe('with reduced motion', () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
  });

  test('a video waits for the play button', async ({ page }) => {
    await open(page, 'album=clip&videos=1&interval=3');
    await expectShown(page, 'clip-0 preview');
    await expect(page.locator(PLAY)).toHaveAttribute('aria-label', 'Play slideshow');
    await advance(page, 9000);
    await expect(page.locator(CLIP)).toHaveCount(0);
    expect(await videosSigned(page)).toEqual([]);

    await page.locator(PLAY).click();
    await expect(page.locator(PLAYING)).toHaveCount(1);
    await page.locator(PLAY).click();
    await expect(page.locator(PLAY)).toHaveAttribute('aria-label', 'Play slideshow');
    expect(await clip(page)).toMatchObject({ paused: true });
  });
});

test.describe('full screen', () => {
  const position = (page) => page.locator(`${VIEWER} .position`);
  const sound = (page, label) => page.locator(`${VIEWER} .icon-button[aria-label="${label}"]`);

  test('plays the video, with a button for its sound', async ({ page }) => {
    await showVideo(page);
    await expect(page.locator(PLAYING)).toHaveCount(1);
    await page.locator(`${CARD} .stage`).click();
    await expect(position(page)).toHaveText('2 of 3');
    const video = page.locator(`${VIEWER} video.full.ready`);
    await expect(video).toBeVisible();
    expect(await video.evaluate((el) => el.muted)).toBe(true);
    expect((await calls(page)).signed).not.toContain('/api/immich_slideshow/server-1/clips-1/fullsize');
    // The tile's own video waits meanwhile.
    expect(await clip(page)).toMatchObject({ paused: true });

    await sound(page, 'Turn sound on').click();
    await expect(sound(page, 'Turn sound off')).toBeVisible();
    expect(await video.evaluate((el) => el.muted)).toBe(false);
    await sound(page, 'Turn sound off').click();
    await expect(sound(page, 'Turn sound on')).toBeVisible();
    expect(await video.evaluate((el) => el.muted)).toBe(true);
  });

  test('has no sound button for a photo, and stops the video on leaving it', async ({ page }) => {
    await showVideo(page);
    await page.locator(`${CARD} .stage`).click();
    await expect(page.locator(`${VIEWER} video.full.ready`)).toBeVisible();
    await page.keyboard.press('ArrowRight');
    await expect(position(page)).toHaveText('3 of 3');
    await expect(page.locator(`${VIEWER} img.full.ready`)).toBeVisible();
    await expect(page.locator(`${VIEWER} video`)).toHaveCount(0);
    await expect(sound(page, 'Turn sound on')).toBeHidden();
    await page.keyboard.press('ArrowLeft');
    await expect(sound(page, 'Turn sound on')).toBeVisible();
    await expect(page.locator(`${VIEWER} video.full.ready`)).toBeVisible();
  });

  test('Tab reaches the sound button and stays inside', async ({ page }) => {
    await showVideo(page);
    await page.locator(`${CARD} .stage`).click();
    await expect(sound(page, 'Turn sound on')).toBeVisible();
    const focused = [];
    for (let i = 0; i < 4; i += 1) {
      await page.keyboard.press('Tab');
      focused.push(await page.locator(`${VIEWER} button:focus`).getAttribute('aria-label'));
    }
    expect(focused).toContain('Turn sound on');
    expect(focused).toContain('Close');
  });

  test("says so when a video can't be played", async ({ page }) => {
    await open(page, 'album=badclip&videos=1&shuffle=0&interval=3');
    await expectShown(page, 'badclip-0 preview');
    await page.locator(`${CARD} .stage`).click();
    await expect(position(page)).toHaveText('1 of 2');
    await expect(page.locator(`${VIEWER} .status`)).toHaveText("Couldn't play this video");
    await expect.poll(async () => (await calls(page)).videoFailures.filter((failure) => failure.place === 'viewer')).toHaveLength(1);
  });
});
