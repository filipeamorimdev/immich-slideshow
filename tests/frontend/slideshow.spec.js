const { test, expect } = require('@playwright/test');
const { CARD, open, shown, expectShown, calls, message, advance } = require('./helpers');

test('asks for an album and loads nothing without one', async ({ page }) => {
  await open(page, '');
  await expect(message(page)).toHaveText('Choose an album in the card editor.');
  await expect(page.locator(`${CARD} .message svg`)).toBeVisible();
  const { photos, sign } = await calls(page);
  expect(photos).toBe(0);
  expect(sign).toBe(0);
});

test('shows photos in album order at the chosen interval', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=5');
  await expectShown(page, 'lisbon-0 preview');
  await advance(page, 4000);
  expect(await shown(page)).toBe('lisbon-0 preview');
  await advance(page, 1100);
  await expectShown(page, 'lisbon-1 preview');
  await advance(page, 5000);
  await expectShown(page, 'lisbon-2 preview');
});

test('asks the integration for the album', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0');
  await expectShown(page, 'lisbon-0 preview');
  expect((await calls(page)).requests).toEqual([{ type: 'immich_slideshow/photos', source: 'album', album: 'lisbon' }]);
});

test('reads an album saved by the standalone card', async ({ page }) => {
  await open(page, 'album=lisbon&legacy=1&shuffle=0');
  await expectShown(page, 'lisbon-0 preview');
  expect((await calls(page)).requests[0].album).toBe('lisbon');
});

test('uses the default interval of 10 seconds', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0');
  await expectShown(page, 'lisbon-0 preview');
  await advance(page, 9000);
  expect(await shown(page)).toBe('lisbon-0 preview');
  await advance(page, 1100);
  await expectShown(page, 'lisbon-1 preview');
});

test('never goes faster than the minimum interval', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=1');
  await expectShown(page, 'lisbon-0 preview');
  await advance(page, 2500);
  expect(await shown(page)).toBe('lisbon-0 preview');
  await advance(page, 600);
  await expectShown(page, 'lisbon-1 preview');
});

test('keeps at most the outgoing and incoming photos in the page', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  for (const label of ['lisbon-1 preview', 'lisbon-2 preview', 'lisbon-3 preview']) {
    await advance(page, 3100);
    await expectShown(page, label);
  }
  const slides = page.locator(`${CARD} .slide`);
  expect(await slides.count()).toBeLessThanOrEqual(2);
});

test('shuffle shows every photo once per round without repeating across rounds', async ({ page }) => {
  await open(page, 'album=pair&interval=3');
  await expect.poll(() => shown(page)).not.toBeNull();
  let previous = await shown(page);
  for (let i = 0; i < 6; i += 1) {
    await advance(page, 3100);
    await expect.poll(() => shown(page)).not.toBe(previous);
    previous = await shown(page);
  }
});

test('shuffle covers a whole album in one round', async ({ page }) => {
  await open(page, 'album=lisbon&interval=3');
  await expect.poll(() => shown(page)).not.toBeNull();
  const seen = new Set([await shown(page)]);
  for (let i = 0; i < 11; i += 1) {
    const before = await shown(page);
    await advance(page, 3100);
    await expect.poll(() => shown(page)).not.toBe(before);
    seen.add(await shown(page));
  }
  expect(seen.size).toBe(12);
});

test('asks for the preview size and never the full image', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  await advance(page, 3100);
  await expectShown(page, 'lisbon-1 preview');
  const { signed } = await calls(page);
  expect(signed.length).toBeGreaterThan(0);
  for (const path of signed) expect(path).toMatch(/^\/api\/immich_slideshow\/server-1\/lisbon-\d+\/preview$/);
});

test('falls back to the full image when a preview fails', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3&nopreview=1');
  await expectShown(page, 'lisbon-0 fullsize');
  expect((await calls(page)).signed).toContain('/api/immich_slideshow/server-1/lisbon-0/fullsize');
});

test('skips photos that fail to load', async ({ page }) => {
  await open(page, 'album=flaky&shuffle=0&interval=3');
  await expectShown(page, 'flaky-2 preview');
  await advance(page, 3100);
  await expectShown(page, 'flaky-4 preview');
  await expect(message(page)).toBeHidden();
});

test('says so when no photo loads, and keeps trying', async ({ page }) => {
  await open(page, 'album=allbroken&interval=3');
  await expect(message(page)).toHaveText("Couldn't load the photos");
  const before = (await calls(page)).sign;
  await advance(page, 3100);
  await expect.poll(async () => (await calls(page)).sign).toBeGreaterThan(before);
});

test('stays on the only photo of a one-photo album', async ({ page }) => {
  await open(page, 'album=single&interval=3');
  await expectShown(page, 'single-0 preview');
  const before = (await calls(page)).sign;
  await advance(page, 10000);
  expect((await calls(page)).sign).toBe(before);
});

test('says the album has no photos, and looks again an hour later', async ({ page }) => {
  await open(page, 'album=empty');
  await expect(message(page)).toHaveText('This album has no photos');
  expect((await calls(page)).photos).toBe(1);
  await advance(page, 60 * 60 * 1000 + 100);
  await expect.poll(async () => (await calls(page)).photos).toBe(2);
});

test('shows the error and recovers from a failed load', async ({ page }) => {
  await open(page, 'album=denied');
  await expect(message(page)).toContainText("Couldn't get the photos from Immich");
  await expect(message(page)).toContainText('Immich answered 500: Internal server error');
  const before = (await calls(page)).photos;
  await page.locator(`${CARD} .action`).click();
  await expect.poll(async () => (await calls(page)).photos).toBe(before + 1);
});

test('retries a failed load on its own', async ({ page }) => {
  await open(page, 'album=denied');
  await expect(message(page)).toContainText("Couldn't get the photos from Immich");
  const before = (await calls(page)).photos;
  await advance(page, 60100);
  await expect.poll(async () => (await calls(page)).photos).toBeGreaterThan(before);
});

test('asks for the integration when it is missing', async ({ page }) => {
  await open(page, 'album=lisbon&nointegration=1');
  await expect(message(page)).toContainText('Set up the Immich Slideshow integration first.');
  await expect(page.locator(`${CARD} .message .detail`)).toHaveCount(0);
});

test('asks for the integration when no server is set up', async ({ page }) => {
  await open(page, 'album=lisbon&nosource=1');
  await expect(message(page)).toContainText('Set up the Immich Slideshow integration first.');
});

test('waits until the tile scrolls into view', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3&spacer=1');
  await expect.poll(async () => (await calls(page)).photos).toBe(1);
  await advance(page, 6000);
  expect((await calls(page)).sign).toBe(0);
  await page.locator(CARD).scrollIntoViewIfNeeded();
  await expectShown(page, 'lisbon-0 preview');
});

test('pauses while the browser tab is hidden', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  // The next photo starts loading as soon as one is shown, while the tab is still visible.
  // Let it finish, so only what happens after hiding is counted.
  await page.evaluate(() => Promise.resolve(document.getElementById('card')._nextSlide).then(() => true));
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  const before = (await calls(page)).sign;
  await advance(page, 9000);
  expect((await calls(page)).sign).toBe(before);
  expect(await shown(page)).toBe('lisbon-0 preview');
  await page.evaluate(() => {
    delete document.hidden;
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expectShown(page, 'lisbon-1 preview');
});

test('ignores Home Assistant state updates', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  const before = await calls(page);
  await page.evaluate(() => {
    const card = document.getElementById('card');
    for (let i = 0; i < 20; i += 1) card.hass = { ...window.__hass };
  });
  // Longer than the harness takes to answer, so a reload would be counted.
  await page.waitForTimeout(200);
  const after = await calls(page);
  expect(after.photos).toBe(before.photos);
  expect(await shown(page)).toBe('lisbon-0 preview');
});

test('checks the album again after an hour', async ({ page }) => {
  await open(page, 'album=pair&shuffle=0&interval=3');
  await expectShown(page, 'pair-0 preview');
  const before = (await calls(page)).photos;
  await page.clock.fastForward('01:01:00');
  for (let i = 0; i < 3; i += 1) await advance(page, 3100);
  await expect.poll(async () => (await calls(page)).photos).toBe(before + 1);
});

test('keeps working after being moved in the page', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  await page.evaluate(() => {
    const card = document.getElementById('card');
    const parent = card.parentElement;
    card.remove();
    parent.appendChild(card);
  });
  await advance(page, 3100);
  await expect.poll(() => shown(page)).not.toBe('lisbon-0 preview');
});

test('switching album replaces the photos', async ({ page }) => {
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  await page.evaluate(() => {
    document.getElementById('card').setConfig({ album: 'pair', shuffle: false });
  });
  await expectShown(page, 'pair-0 preview');
  await expect(page.locator(`${CARD} .slide`)).toHaveCount(1);
});

test('only talks to Home Assistant, with the integration and signed paths', async ({ page }) => {
  const external = [];
  page.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith('data:') && !url.startsWith('http://127.0.0.1:8766/')) external.push(url);
  });
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  await advance(page, 3100);
  await expectShown(page, 'lisbon-1 preview');
  expect(external).toEqual([]);
  const { types } = await calls(page);
  expect(types.sort()).toEqual(['auth/sign_path', 'immich_slideshow/photos']);
});

test.describe('layout', () => {
  test('is 16:9 when the page sets no height', async ({ page }) => {
    await open(page, 'album=lisbon');
    const box = await page.locator(`${CARD} ha-card`).boundingBox();
    expect(box.width / box.height).toBeCloseTo(16 / 9, 1);
  });

  test('fills a fixed dashboard grid cell', async ({ page }) => {
    await open(page, 'album=lisbon&box=1');
    await expect.poll(() => shown(page)).not.toBeNull();
    for (const selector of ['ha-card', '.slide']) {
      const box = await page.locator(`${CARD} ${selector}`).first().boundingBox();
      expect(Math.round(box.width)).toBe(300);
      expect(Math.round(box.height)).toBe(200);
    }
  });

  test('shows a caption only when there is one', async ({ page }) => {
    await open(page, 'album=lisbon');
    await expect(page.locator(`${CARD} .title`)).toBeHidden();
    await open(page, 'album=lisbon&title=Summer');
    await expect(page.locator(`${CARD} .title`)).toHaveText('Summer');
  });

  test('uses the Home Assistant language', async ({ page }) => {
    await open(page, 'lang=pt');
    await expect(message(page)).toHaveText('Escolha um álbum no editor do cartão.');
  });
});
