const { expect } = require('@playwright/test');

// The card under test is always #card, whichever kind it is.
const CARD = '#card';
const VIEWER = 'immich-slideshow-viewer';

// Opens the harness with a controllable clock, so tests don't wait for real intervals.
async function open(page, query = '') {
  await page.clock.install();
  await page.goto(`/dev/harness.html?${query}`);
}

// The label drawn into the fake image on top of the slideshow, such as "lisbon-3 preview".
function shown(page) {
  return page.evaluate(() => {
    const slide = document.querySelector('#card').shadowRoot.querySelector('.stage > :last-child .photo');
    if (!slide) return null;
    const match = decodeURIComponent(slide.src).match(/>([^<]*(?:preview|fullsize))</);
    return match ? match[1] : slide.src.slice(0, 40);
  });
}

function expectShown(page, label) {
  return expect.poll(() => shown(page)).toBe(label);
}

function calls(page) {
  return page.evaluate(() => JSON.parse(JSON.stringify(window.__calls)));
}

function message(page) {
  return page.locator(`${CARD} .message`);
}

// The date and place under the photo on screen.
function meta(page) {
  return page.locator(`${CARD} .meta`);
}

// Moves the slideshow on by one interval and waits for the promises behind it to settle.
async function advance(page, ms) {
  await page.clock.runFor(ms);
}

module.exports = { CARD, VIEWER, open, shown, expectShown, calls, message, meta, advance };
