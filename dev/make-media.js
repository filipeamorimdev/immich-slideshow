// Generates the README images from the harness and its generated landscapes.
// Needs ffmpeg on the PATH. Run with `npm run media`.
const { execFileSync } = require('node:child_process');
const { mkdirSync, mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const { chromium } = require('@playwright/test');
const { serve } = require('./server');

const PORT = 8767;
const DOCS = join(__dirname, '..', 'docs');
const CARD = '#card';
const PHOTOS = 5;
const HOLD = 2;
const FADE = 0.6;
const FPS = 10;

async function shot(page, query, size, path) {
  await page.setViewportSize(size);
  await page.goto(`http://127.0.0.1:${PORT}/dev/harness.html?${query}`);
  await page.locator(`${CARD} .slide.on`).first().waitFor();
  await page.waitForTimeout(1200);
  if (path) await page.screenshot({ path });
}

function makeGif(stills, output) {
  const inputs = stills.flatMap((file) => ['-loop', '1', '-framerate', String(FPS), '-t', String(HOLD + FADE), '-i', file]);
  const steps = [];
  let previous = '[0]';
  for (let i = 1; i < stills.length; i += 1) {
    steps.push(`${previous}[${i}]xfade=transition=fade:duration=${FADE}:offset=${i * HOLD}[v${i}]`);
    previous = `[v${i}]`;
  }
  // A palette per frame avoids banding in the smooth skies.
  steps.push(`${previous}split[a][b]`, '[a]palettegen=stats_mode=single[p]', '[b][p]paletteuse=new=1:dither=sierra2_4a');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', steps.join(';'), '-loop', '0', output]);
}

async function main() {
  mkdirSync(DOCS, { recursive: true });
  const server = await serve(PORT);
  const browser = await chromium.launch();
  const page = await browser.newPage({ colorScheme: 'dark' });
  const work = mkdtempSync(join(tmpdir(), 'immich-slideshow-media-'));

  try {
    // The tile: one still per photo, faded together in the order the card shows them.
    await shot(page, 'album=demo&shuffle=0&interval=3&title=Summer&lang=en-GB', { width: 672, height: 420 });
    await page.addStyleTag({ content: 'body { padding: 0 !important; } #wrap { max-width: none !important; }' });
    await page.setViewportSize({ width: 640, height: 360 });
    const tile = page.locator(`${CARD} ha-card`);
    await tile.evaluate((card) => { card.style.borderRadius = '0'; });

    // Waits for each photo to arrive and finish fading in, so none is skipped.
    const currentPhoto = () => page.evaluate((card) => document.querySelector(card)
      .shadowRoot.querySelector('.stage > :last-child .photo').src, CARD);
    const stills = [];
    let previous = null;
    for (let i = 0; i < PHOTOS; i += 1) {
      await page.waitForFunction(([card, before]) => {
        const photo = document.querySelector(card).shadowRoot.querySelector('.stage > :last-child .photo');
        return photo && photo.src !== before;
      }, [CARD, previous], { timeout: 15000 });
      previous = await currentPhoto();
      await page.waitForTimeout(1300);
      const file = join(work, `still-${i}.png`);
      await tile.screenshot({ path: file });
      stills.push(file);
    }
    makeGif([...stills, stills[0]], join(DOCS, 'slideshow.gif'));

    // Full screen.
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.locator(`${CARD} .stage`).click();
    await page.locator('immich-slideshow-viewer img.full.ready').waitFor();
    await page.waitForTimeout(500);
    await page.mouse.move(640, 700);
    await page.screenshot({ path: join(DOCS, 'fullscreen.png') });
  } finally {
    await browser.close();
    server.close();
    rmSync(work, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
