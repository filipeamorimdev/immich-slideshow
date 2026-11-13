const { test, expect } = require('@playwright/test');
const { CARD, VIEWER, open, shown, expectShown, calls, advance } = require('./helpers');

const position = (page) => page.locator(`${VIEWER} .position`);
const media = (page) => page.locator(`${VIEWER} .media`);

async function openViewer(page) {
  await open(page, 'album=lisbon&shuffle=0&interval=3');
  await expectShown(page, 'lisbon-0 preview');
  await advance(page, 3100);
  await expectShown(page, 'lisbon-1 preview');
  await page.locator(`${CARD} .stage`).click();
  await expect(position(page)).toHaveText('2 of 12');
}

async function drag(page, from, to) {
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y, { steps: 6 });
  await page.mouse.up();
}

test('tapping the tile opens the current photo full screen', async ({ page }) => {
  await openViewer(page);
  await expect(page.locator(`${VIEWER} .about`)).toHaveText('February 11, 2024 · Puteaux, France');
  await expect(page.locator(`${VIEWER} img.full.ready`)).toBeVisible();
  await expect(page.locator(`${VIEWER} .icon-button[aria-label="Close"]`)).toBeFocused();
});

test('the slideshow pauses while it is open and resumes after', async ({ page }) => {
  await openViewer(page);
  const before = (await calls(page)).sign;
  const current = await shown(page);
  await advance(page, 9000);
  expect(await shown(page)).toBe(current);
  await page.keyboard.press('Escape');
  await expect(page.locator(VIEWER)).toHaveCount(0);
  await expect(page.locator(`${CARD} .stage`)).toBeFocused();
  await advance(page, 3100);
  await expect.poll(() => shown(page)).not.toBe(current);
  expect((await calls(page)).sign).toBeGreaterThan(before);
});

test('shows the photo it loaded ahead, without asking for it again', async ({ page }) => {
  const signed = async (asset) => (await calls(page)).signed.filter((path) => path.endsWith(`/${asset}/fullsize`)).length;
  await openViewer(page);
  // The photos on either side load ahead.
  await expect.poll(() => signed('lisbon-2')).toBe(1);
  await expect.poll(() => signed('lisbon-0')).toBe(1);
  await page.keyboard.press('ArrowRight');
  await expect(position(page)).toHaveText('3 of 12');
  await expect(page.locator(`${VIEWER} img.full.ready`)).toBeVisible();
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  await expect(position(page)).toHaveText('1 of 12');
  await expect(page.locator(`${VIEWER} img.full.ready`)).toBeVisible();
  for (const asset of ['lisbon-0', 'lisbon-1', 'lisbon-2']) expect(await signed(asset)).toBe(1);
});

test('arrow keys move between photos and stop at the ends', async ({ page }) => {
  await openViewer(page);
  await page.keyboard.press('ArrowRight');
  await expect(position(page)).toHaveText('3 of 12');
  await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('ArrowLeft');
  await expect(position(page)).toHaveText('1 of 12');
  await page.keyboard.press('ArrowLeft');
  await expect(position(page)).toHaveText('1 of 12');
  await expect(page.locator(`${VIEWER} .nav.previous`)).toBeHidden();
});

test('swiping moves between photos', async ({ page }) => {
  await openViewer(page);
  await drag(page, { x: 700, y: 350 }, { x: 200, y: 350 });
  await expect(position(page)).toHaveText('3 of 12');
  await drag(page, { x: 200, y: 350 }, { x: 700, y: 350 });
  await expect(position(page)).toHaveText('2 of 12');
});

test('a short drag snaps back', async ({ page }) => {
  await openViewer(page);
  await drag(page, { x: 500, y: 350 }, { x: 485, y: 350 });
  await expect(position(page)).toHaveText('2 of 12');
  // Browsers write a zero translate differently.
  await expect.poll(() => media(page).evaluate((el) => el.style.transform))
    .toMatch(/^translate\(0px(, 0px)?\) scale\(1\)$/);
});

test('a tiny quick movement during a tap does not change the photo', async ({ page }) => {
  await openViewer(page);
  await page.evaluate((viewer) => {
    const stage = document.querySelector(viewer).shadowRoot.querySelector('.stage');
    stage.setPointerCapture = () => {};
    const fire = (type, x) => stage.dispatchEvent(new PointerEvent(type, {
      bubbles: true, composed: true, clientX: x, clientY: 350, pointerId: 1, pointerType: 'touch', button: 0,
    }));
    fire('pointerdown', 500);
    fire('pointermove', 485);
    fire('pointerup', 485);
  }, VIEWER);
  await page.waitForTimeout(300);
  await expect(position(page)).toHaveText('2 of 12');
});

test('a quick flick changes the photo', async ({ page }) => {
  await openViewer(page);
  await page.evaluate((viewer) => {
    const stage = document.querySelector(viewer).shadowRoot.querySelector('.stage');
    stage.setPointerCapture = () => {};
    const fire = (type, x) => stage.dispatchEvent(new PointerEvent(type, {
      bubbles: true, composed: true, clientX: x, clientY: 350, pointerId: 1, pointerType: 'touch', button: 0,
    }));
    fire('pointerdown', 500);
    fire('pointermove', 440);
    fire('pointerup', 440);
  }, VIEWER);
  await expect(position(page)).toHaveText('3 of 12');
});

test('swiping down closes it', async ({ page }) => {
  await openViewer(page);
  await drag(page, { x: 500, y: 150 }, { x: 500, y: 600 });
  await expect(page.locator(VIEWER)).toHaveCount(0);
});

test('double-clicking zooms in and out, and a zoomed photo can be moved', async ({ page }) => {
  await openViewer(page);
  await page.mouse.dblclick(500, 350);
  await expect.poll(() => media(page).evaluate((el) => el.style.transform)).toContain('scale(2.5)');
  const zoomed = await media(page).evaluate((el) => el.style.transform);
  await drag(page, { x: 500, y: 350 }, { x: 400, y: 300 });
  await expect.poll(() => media(page).evaluate((el) => el.style.transform)).not.toBe(zoomed);
  await expect(position(page)).toHaveText('2 of 12');
  await page.waitForTimeout(350);
  await page.mouse.dblclick(500, 350);
  await expect.poll(() => media(page).evaluate((el) => el.style.transform)).toContain('scale(1)');
});

test('the scroll wheel zooms, within limits', async ({ page }) => {
  await openViewer(page);
  await page.mouse.move(500, 350);
  await page.mouse.wheel(0, -2000);
  await expect.poll(() => media(page).evaluate((el) => el.style.transform)).toContain('scale(5)');
  await page.mouse.wheel(0, 4000);
  await expect.poll(() => media(page).evaluate((el) => el.style.transform)).toContain('scale(1)');
});

test('pinching zooms', async ({ page }) => {
  await openViewer(page);
  await page.evaluate((viewer) => {
    const stage = document.querySelector(viewer).shadowRoot.querySelector('.stage');
    const fire = (type, x, y, pointerId) => stage.dispatchEvent(new PointerEvent(type, {
      bubbles: true, composed: true, clientX: x, clientY: y, pointerId, pointerType: 'touch', button: 0,
    }));
    fire('pointerdown', 400, 350, 1);
    fire('pointerdown', 600, 350, 2);
    fire('pointermove', 300, 350, 1);
    fire('pointermove', 700, 350, 2);
  }, VIEWER);
  await expect.poll(() => media(page).evaluate((el) => el.style.transform)).toContain('scale(2)');
});

test('says so when a photo fails to load', async ({ page }) => {
  await open(page, 'album=flaky&shuffle=0&interval=3');
  await expectShown(page, 'flaky-2 preview');
  await page.locator(`${CARD} .stage`).click();
  await expect(position(page)).toHaveText('3 of 6');
  await page.keyboard.press('ArrowLeft');
  await expect(position(page)).toHaveText('2 of 6');
  await expect(page.locator(`${VIEWER} .status`)).toHaveText("Couldn't load this photo");
});

test('Tab stays inside it', async ({ page }) => {
  await openViewer(page);
  for (let i = 0; i < 4; i += 1) await page.keyboard.press('Tab');
  await expect(page.locator(`${VIEWER} button:focus`)).toHaveCount(1);
});
