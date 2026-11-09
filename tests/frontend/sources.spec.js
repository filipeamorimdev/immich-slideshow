const { test, expect } = require('@playwright/test');
const { CARD, open, shown, expectShown, calls, message, meta, advance } = require('./helpers');

test.describe('date and place', () => {
  test('shows when and where each photo was taken', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expectShown(page, 'lisbon-0 preview');
    await expect(meta(page)).toHaveText('January 10, 2024 · Lisbon, Portugal');
    await advance(page, 3100);
    await expectShown(page, 'lisbon-1 preview');
    await expect(meta(page)).toHaveText('February 11, 2024 · Puteaux, France');
  });

  test('uses the region when there is no city, and leaves out a missing place', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expectShown(page, 'lisbon-0 preview');
    for (const label of ['lisbon-1 preview', 'lisbon-2 preview']) {
      await advance(page, 3100);
      await expectShown(page, label);
    }
    await expect(meta(page)).toHaveText('March 12, 2024 · Algarve, Portugal');
    await advance(page, 3100);
    await expectShown(page, 'lisbon-3 preview');
    await expect(meta(page)).toHaveText('April 13, 2024');
  });

  test('can show only the date, only the place, or neither', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&show_date=0');
    await expect(meta(page)).toHaveText('Lisbon, Portugal');
    await open(page, 'album=lisbon&shuffle=0&show_place=0');
    await expect(meta(page)).toHaveText('January 10, 2024');
    await open(page, 'album=lisbon&shuffle=0&show_date=0&show_place=0');
    await expectShown(page, 'lisbon-0 preview');
    await expect(page.locator(`${CARD} .caption`)).toBeHidden();
  });

  test('sits under the caption', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&title=Summer');
    await expect(meta(page)).toHaveText('January 10, 2024 · Lisbon, Portugal');
    const title = await page.locator(`${CARD} .title`).boundingBox();
    const about = await meta(page).boundingBox();
    expect(about.y).toBeGreaterThan(title.y);
  });

  test('follows the Home Assistant language', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&lang=pt');
    await expect(meta(page)).toHaveText('10 de janeiro de 2024 · Lisbon, Portugal');
  });

  test('changes with the photo, without waiting for the next one', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expect(meta(page)).toHaveText('January 10, 2024 · Lisbon, Portugal');
    await advance(page, 3100);
    await expect(meta(page)).toHaveText('February 11, 2024 · Puteaux, France');
    await expect(page.locator(`${CARD} .meta`)).toHaveCount(1);
  });
});

test.describe('date in another time zone', () => {
  // UTC+14: a browser clock this far ahead would move the date if the card read it as local time.
  test.use({ timezoneId: 'Pacific/Kiritimati' });

  test('is the date on the camera, not in the browser', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0');
    await expect(meta(page)).toHaveText('January 10, 2024 · Lisbon, Portugal');
  });
});

test.describe('random photos', () => {
  test('asks for random photos and starts a new set every round', async ({ page }) => {
    await open(page, 'source=random&shuffle=0&interval=3');
    await expectShown(page, 'random1-0 preview');
    expect((await calls(page)).requests[0]).toEqual({ type: 'immich_slideshow/photos', source: 'random' });
    for (const label of ['random1-1 preview', 'random1-2 preview', 'random1-3 preview', 'random2-0 preview', 'random2-1 preview']) {
      await advance(page, 3100);
      await expectShown(page, label);
    }
  });

  test('fetches the next set while the current one plays', async ({ page }) => {
    await open(page, 'source=random&shuffle=0&interval=3');
    await expectShown(page, 'random1-0 preview');
    await expect.poll(async () => (await calls(page)).photos).toBe(2);
    await advance(page, 3100);
    await expectShown(page, 'random1-1 preview');
    expect((await calls(page)).photos).toBe(2);
  });

  test('says so when the library has no photos', async ({ page }) => {
    await open(page, 'source=random&randomsize=0');
    await expect(message(page)).toHaveText('No photos found in the library');
  });
});

test.describe('magic', () => {
  test('asks for a description and searches nothing without one', async ({ page }) => {
    await open(page, 'card=magic');
    await expect(message(page)).toHaveText('Describe the photos to show in the card editor.');
    await expect(page.locator(`${CARD} .message svg`)).toBeVisible();
    expect((await calls(page)).photos).toBe(0);
  });

  test('shows the photos that match', async ({ page }) => {
    await open(page, 'card=magic&query=beach%20sunset&shuffle=0&interval=3');
    await expectShown(page, 'beachsunset-0 preview');
    expect((await calls(page)).requests).toEqual([
      { type: 'immich_slideshow/photos', source: 'search', query: 'beach sunset', count: 50, language: 'en' },
    ]);
    await advance(page, 3100);
    await expectShown(page, 'beachsunset-1 preview');
  });

  test('sends the number of photos, within limits, and the language', async ({ page }) => {
    await open(page, 'card=magic&query=snow&count=300&lang=de');
    await expect.poll(async () => (await calls(page)).requests.length).toBe(1);
    expect((await calls(page)).requests[0]).toMatchObject({ count: 250, language: 'de' });
    await open(page, 'card=magic&query=snow&count=10');
    await expect.poll(async () => (await calls(page)).requests.length).toBe(1);
    expect((await calls(page)).requests[0].count).toBe(10);
  });

  test('says so when nothing matches', async ({ page }) => {
    await open(page, 'card=magic&query=nothing');
    await expect(message(page)).toHaveText('No photos match this description');
  });

  test('waits for a pause in typing before searching again', async ({ page }) => {
    await open(page, 'card=magic&query=snow&shuffle=0&interval=3');
    await expectShown(page, 'snow-0 preview');
    for (const query of ['d', 'do', 'dog', 'dogs']) {
      await page.evaluate((q) => {
        const card = document.getElementById('card');
        card.setConfig({ ...card._config, query: q });
      }, query);
      await advance(page, 200);
    }
    expect((await calls(page)).requests.map((r) => r.query)).toEqual(['snow']);
    await advance(page, 900);
    await expectShown(page, 'dogs-0 preview');
    expect((await calls(page)).requests.map((r) => r.query)).toEqual(['snow', 'dogs']);
  });

  test('changing only the caption keeps the photos', async ({ page }) => {
    await open(page, 'card=magic&query=snow&shuffle=0');
    await expectShown(page, 'snow-0 preview');
    await page.evaluate(() => {
      const card = document.getElementById('card');
      card.setConfig({ ...card._config, title: 'Winter' });
    });
    await page.waitForTimeout(200);
    expect((await calls(page)).photos).toBe(1);
    await expect(page.locator(`${CARD} .title`)).toHaveText('Winter');
  });
});

test.describe('on this day', () => {
  test('starts without setup, most recent year first, with how long ago', async ({ page }) => {
    await open(page, 'card=on_this_day&interval=3');
    await expectShown(page, 'day20251108-0 preview');
    expect((await calls(page)).requests).toEqual([{ type: 'immich_slideshow/photos', source: 'on_this_day' }]);
    await expect(meta(page)).toHaveText('Last year · Lisbon, Portugal');
    await advance(page, 3100);
    await expectShown(page, 'day20251108-1 preview');
    await advance(page, 3100);
    await expectShown(page, 'day20241108-0 preview');
    await expect(meta(page)).toHaveText('2 years ago · Algarve, Portugal');
    for (let i = 0; i < 2; i += 1) await advance(page, 3100);
    await expectShown(page, 'day20171108-0 preview');
    await expect(meta(page)).toHaveText('9 years ago · Lisbon, Portugal');
  });

  test('says how long ago in the Home Assistant language', async ({ page }) => {
    await open(page, 'card=on_this_day&interval=3&lang=pt');
    await expectShown(page, 'day20251108-0 preview');
    await expect(meta(page)).toHaveText('Ano passado · Lisbon, Portugal');
    for (let i = 0; i < 2; i += 1) await advance(page, 3100);
    await expect(meta(page)).toHaveText('Há 2 anos · Algarve, Portugal');
  });

  test('the full screen view shows the date', async ({ page }) => {
    await open(page, 'card=on_this_day&show_date=0');
    await expect(meta(page)).toHaveText('Lisbon, Portugal');
    await page.locator(`${CARD} .stage`).click();
    await expect(page.locator('immich-slideshow-viewer .about')).toHaveText('Last year · Lisbon, Portugal');
  });

  test('says so on a day with no photos, and looks again when the day changes', async ({ page }) => {
    await page.addInitScript(() => { window.__noMemories = true; });
    await open(page, 'card=on_this_day&refreshin=5000');
    await expect(message(page)).toHaveText('No photos from this day in earlier years');
    await page.evaluate(() => { window.__noMemories = false; window.__day = '2026-11-09'; });
    await advance(page, 5100);
    await expectShown(page, 'day20251109-0 preview');
    await expect(message(page)).toBeHidden();
  });

  test('switches to the new day at midnight', async ({ page }) => {
    await open(page, 'card=on_this_day&interval=3&refreshin=7000');
    await expectShown(page, 'day20251108-0 preview');
    await page.evaluate(() => { window.__day = '2026-11-09'; });
    await advance(page, 3100);
    await expectShown(page, 'day20251108-1 preview');
    await advance(page, 4000);
    await advance(page, 3100);
    await expectShown(page, 'day20251109-0 preview');
  });

  test('empties when the new day has no photos', async ({ page }) => {
    await open(page, 'card=on_this_day&interval=3&refreshin=4000');
    await expectShown(page, 'day20251108-0 preview');
    await page.evaluate(() => { window.__noMemories = true; });
    for (let i = 0; i < 3; i += 1) await advance(page, 3100);
    await expect(message(page)).toHaveText('No photos from this day in earlier years');
    await expect(page.locator(`${CARD} .slide`)).toHaveCount(0);
    await expect(page.locator(`${CARD} .caption`)).toBeHidden();
  });
});

test('registers all three cards in the card picker', async ({ page }) => {
  await open(page, '');
  const cards = await page.evaluate(() => window.customCards.map(({ type, name, preview }) => ({ type, name, preview })));
  expect(cards).toEqual([
    { type: 'immich-slideshow-card', name: 'Immich Slideshow', preview: true },
    { type: 'immich-magic-card', name: 'Immich Magic', preview: true },
    { type: 'immich-on-this-day-card', name: 'Immich On This Day', preview: true },
  ]);
  for (const tag of ['immich-slideshow-card', 'immich-magic-card', 'immich-on-this-day-card']) {
    const stub = await page.evaluate((t) => customElements.get(t).getStubConfig(), tag);
    expect(stub).toEqual({});
  }
});
