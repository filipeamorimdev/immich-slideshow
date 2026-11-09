const { test, expect } = require('@playwright/test');
const { CARD, open, shown, expectShown, calls, advance } = require('./helpers');

const PLAY = `${CARD} .play`;

test.describe('with reduced motion', () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
  });

  test('shows one photo and stays still', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expectShown(page, 'lisbon-0 preview');
    const before = (await calls(page)).sign;
    await advance(page, 12000);
    expect(await shown(page)).toBe('lisbon-0 preview');
    expect((await calls(page)).sign).toBe(before);
  });

  test('plays when asked and pauses again', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expectShown(page, 'lisbon-0 preview');
    await expect(page.locator(PLAY)).toHaveAttribute('aria-label', 'Play slideshow');

    await page.locator(PLAY).click();
    await expect(page.locator(PLAY)).toHaveAttribute('aria-label', 'Pause slideshow');
    await advance(page, 3100);
    await expectShown(page, 'lisbon-1 preview');
    await advance(page, 3100);
    await expectShown(page, 'lisbon-2 preview');

    await page.locator(PLAY).click();
    await expect(page.locator(PLAY)).toHaveAttribute('aria-label', 'Play slideshow');
    await advance(page, 9000);
    expect(await shown(page)).toBe('lisbon-2 preview');
  });

  test('has no play button for a single photo', async ({ page }) => {
    await open(page, 'album=single&interval=3');
    await expectShown(page, 'single-0 preview');
    await expect(page.locator(PLAY)).toBeHidden();
  });

  test('does not fade between photos', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expectShown(page, 'lisbon-0 preview');
    const duration = await page.locator(`${CARD} .slide`).first()
      .evaluate((slide) => getComputedStyle(slide).transitionDuration);
    expect(duration).toBe('0s');
  });
});

test.describe('without reduced motion', () => {
  test('plays on its own with no play button', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expectShown(page, 'lisbon-0 preview');
    await expect(page.locator(PLAY)).toBeHidden();
    await advance(page, 3100);
    await expectShown(page, 'lisbon-1 preview');
  });

  test('stops as soon as the setting turns on', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3');
    await expectShown(page, 'lisbon-0 preview');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(page.locator(PLAY)).toBeVisible();
    await advance(page, 9000);
    expect(await shown(page)).toBe('lisbon-0 preview');
  });
});
