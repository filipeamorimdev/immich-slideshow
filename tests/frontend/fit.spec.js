const { test, expect } = require('@playwright/test');
const { CARD, open, expectShown, calls, advance } = require('./helpers');

// The "shapes" album holds, in order: 16:9, 4:3, 3:4, 3:1 and a square photo.
const SHAPES = ['16:9', '4:3', '3:4', '3:1', 'square'];

const current = (page) => page.locator(`${CARD} .stage > :last-child`);

// Shows the photo at `index` of the shapes album, in album order.
async function showShape(page, index, query = '') {
  await open(page, `album=shapes&shuffle=0&interval=3${query}`);
  await expectShown(page, 'shapes-0 preview');
  for (let i = 1; i <= index; i += 1) {
    await advance(page, 3100);
    await expectShown(page, `shapes-${i} preview`);
  }
}

async function fitOf(page) {
  return current(page).evaluate((slide) => {
    const photo = slide.querySelector('.photo');
    const backdrop = slide.querySelector('.backdrop');
    return {
      whole: slide.classList.contains('whole'),
      photoFit: getComputedStyle(photo).objectFit,
      backdrop: backdrop ? getComputedStyle(backdrop).display : null,
      blur: backdrop ? getComputedStyle(backdrop).filter : null,
    };
  });
}

const thumbnailsSigned = async (page) => (await calls(page)).signed.filter((path) => path.endsWith('/thumbnail'));

test.describe('automatic fit in a 16:9 tile', () => {
  for (const [index, expected] of [[0, false], [1, false], [2, true], [3, true], [4, true]]) {
    test(`${expected ? 'shows the whole' : 'fills the tile with a'} ${SHAPES[index]} photo`, async ({ page }) => {
      await showShape(page, index);
      const fit = await fitOf(page);
      expect(fit.whole).toBe(expected);
      expect(fit.photoFit).toBe(expected ? 'contain' : 'cover');
      if (expected) {
        expect(fit.backdrop).toBe('block');
        expect(fit.blur).toContain('blur');
      }
    });
  }

  test('loads a backdrop only for photos that need one', async ({ page }) => {
    // The card prepares the next photo while one is showing, so go round the album once.
    await showShape(page, 4);
    await advance(page, 3100);
    await expectShown(page, 'shapes-0 preview');
    const assets = (await thumbnailsSigned(page)).map((path) => path.split('/')[4]);
    expect([...new Set(assets)].sort()).toEqual(['shapes-2', 'shapes-3', 'shapes-4']);
  });

  test('builds the backdrop from the thumbnail, before the photo fades in', async ({ page }) => {
    await open(page, 'album=shapes&shuffle=0&interval=3');
    await expectShown(page, 'shapes-0 preview');
    await page.evaluate(() => {
      const stage = document.getElementById('card').shadowRoot.querySelector('.stage');
      window.__arrivals = [];
      new MutationObserver((records) => {
        for (const record of records) {
          for (const slide of record.addedNodes) {
            window.__arrivals.push({ whole: slide.classList.contains('whole'), backdrop: Boolean(slide.querySelector('.backdrop')) });
          }
        }
      }).observe(stage, { childList: true });
    });
    await advance(page, 3100);
    await expectShown(page, 'shapes-1 preview');
    await advance(page, 3100);
    await expectShown(page, 'shapes-2 preview');
    const arrivals = await page.evaluate(() => window.__arrivals);
    expect(arrivals).toEqual([{ whole: false, backdrop: false }, { whole: true, backdrop: true }]);
    const src = await current(page).locator('.backdrop').evaluate((img) => decodeURIComponent(img.src));
    expect(src).toContain('shapes-2 thumbnail');
  });

  test('waits for a slow backdrop rather than showing the photo without it', async ({ page }) => {
    // The thumbnail takes longer than the interval, so the photo has to wait for it.
    await showShape(page, 1, '&slowthumb=5000');
    await advance(page, 3100);
    expect(await current(page).evaluate((slide) => slide.querySelector('.photo').src)).toContain('shapes-1');
    await advance(page, 3000);
    await expectShown(page, 'shapes-2 preview');
    const fit = await fitOf(page);
    expect(fit.whole).toBe(true);
    expect(fit.backdrop).toBe('block');
  });

  test('still shows the whole photo if the backdrop fails', async ({ page }) => {
    await showShape(page, 2, '&nothumb=1');
    const fit = await fitOf(page);
    expect(fit.whole).toBe(true);
    expect(fit.backdrop).toBeNull();
  });

  test('decides again when the tile changes shape', async ({ page }) => {
    await showShape(page, 0);
    expect((await fitOf(page)).whole).toBe(false);
    await page.evaluate(() => {
      const box = document.getElementById('box');
      box.className = 'fixed';
      box.style.width = '300px';
      box.style.height = '500px';
    });
    await expect.poll(async () => (await fitOf(page)).whole).toBe(true);
    await expect.poll(async () => (await fitOf(page)).backdrop).toBe('block');
  });
});

test('fill the tile crops every photo and loads no backdrop', async ({ page }) => {
  await showShape(page, 2, '&fit=cover');
  const fit = await fitOf(page);
  expect(fit.whole).toBe(false);
  expect(fit.photoFit).toBe('cover');
  expect(await thumbnailsSigned(page)).toEqual([]);
});

test('show the whole photo uses the blurred backdrop even for a 16:9 photo', async ({ page }) => {
  await showShape(page, 0, '&fit=contain');
  const fit = await fitOf(page);
  expect(fit.whole).toBe(true);
  expect(fit.backdrop).toBe('block');
});

test('changing the fit applies to the photo on screen', async ({ page }) => {
  await showShape(page, 2);
  expect((await fitOf(page)).whole).toBe(true);
  await page.evaluate(() => {
    const card = document.getElementById('card');
    card.setConfig({ ...card._config, fit: 'cover' });
  });
  expect((await fitOf(page)).whole).toBe(false);
  expect(await expectShown(page, 'shapes-2 preview')).toBeUndefined();
});

test('a backdrop never spills outside the tile', async ({ page }) => {
  await showShape(page, 2);
  const tile = await page.locator(`${CARD} ha-card`).boundingBox();
  const clipped = await current(page).evaluate((slide) => getComputedStyle(slide).overflow);
  expect(clipped).toBe('hidden');
  const slide = await current(page).boundingBox();
  expect(Math.round(slide.width)).toBe(Math.round(tile.width));
  expect(Math.round(slide.height)).toBe(Math.round(tile.height));
});
