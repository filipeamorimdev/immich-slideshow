const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test, expect } = require('@playwright/test');
const { CARD, open, shown, expectShown, calls, message } = require('./helpers');

const field = (page, name) => page.locator(`#editor label[data-name="${name}"]`);
const select = (page, name) => field(page, name).locator('select');
const input = (page, name) => field(page, name).locator('input');
const fields = (page) => page.locator('#editor label').evaluateAll((labels) => labels.map((l) => l.dataset.name));
const lastConfig = (page) => page.evaluate(() => window.__lastConfig);
// The description's chips, in order, and the ways to change them.
const tags = (page) => field(page, 'description').locator('.chip').evaluateAll((chips) => chips.map((c) => c.dataset.value));
const removeTag = (page, tag) => field(page, 'description').locator(`.chip[data-value="${tag}"]`).click();
const addTag = (page, tag) => select(page, 'description').selectOption(tag);
const albumsListed = (page) => expect(select(page, 'album').locator('option', { hasText: 'Lisbon 2024' })).toHaveCount(1);

test.describe('slideshow editor', () => {
  test("loads Home Assistant's form and fills in the albums", async ({ page }) => {
    await open(page, 'editor=1');
    await albumsListed(page);
    expect(await page.evaluate(() => window.__formLoads)).toBe(1);
    expect(await fields(page)).toEqual(['source', 'album', 'interval', 'shuffle', 'videos', 'fit', 'description', 'title']);
  });

  test('shows the defaults without writing them to the config', async ({ page }) => {
    await open(page, 'editor=1');
    await albumsListed(page);
    await expect(select(page, 'source')).toHaveValue('album');
    await expect(input(page, 'interval')).toHaveValue('10');
    await expect(input(page, 'shuffle')).toBeChecked();
    await expect(select(page, 'fit')).toHaveValue('auto');
    expect(await tags(page)).toEqual(['date', 'place']);
    await select(page, 'album').selectOption('lisbon');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon' });
  });

  test('choosing an album starts the slideshow', async ({ page }) => {
    await open(page, 'editor=1');
    await expect(message(page)).toContainText('Choose an album');
    await albumsListed(page);
    await select(page, 'album').selectOption('lisbon');
    await expect.poll(() => shown(page)).not.toBeNull();
    await expect(message(page)).toBeHidden();
  });

  test('saves changed options and removes them again', async ({ page }) => {
    await open(page, 'album=lisbon&editor=1');
    await albumsListed(page);
    await input(page, 'interval').fill('30');
    await input(page, 'interval').blur();
    await input(page, 'shuffle').uncheck();
    await select(page, 'fit').selectOption('contain');
    await removeTag(page, 'date');
    await removeTag(page, 'place');
    await input(page, 'title').fill('Summer');
    expect(await lastConfig(page)).toEqual({
      album: 'lisbon', interval: 30, shuffle: false, fit: 'contain', description: [], title: 'Summer',
    });
    await expect(page.locator(`${CARD} .title`)).toHaveText('Summer');

    await input(page, 'interval').fill('');
    await input(page, 'interval').blur();
    await input(page, 'shuffle').check();
    await select(page, 'fit').selectOption('auto');
    await addTag(page, 'date');
    await addTag(page, 'place');
    await input(page, 'title').fill('');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon' });
  });

  test('videos are off until asked for, and the album loads again with them', async ({ page }) => {
    await open(page, 'album=clips&editor=1');
    await albumsListed(page);
    await expect(input(page, 'videos')).not.toBeChecked();
    await expect(field(page, 'videos')).toContainText('Videos play to the end, without sound.');
    await input(page, 'videos').check();
    expect(await lastConfig(page)).toEqual({ album: 'clips', videos: true });
    await expect.poll(async () => (await calls(page)).requests.at(-1)).toMatchObject({ album: 'clips', videos: true });
    await input(page, 'videos').uncheck();
    expect(await lastConfig(page)).toEqual({ album: 'clips' });
    await expect.poll(async () => (await calls(page)).requests.at(-1)).toEqual({ type: 'immich_slideshow/photos', source: 'album', album: 'clips' });
  });

  test('removing the date takes it off the tile', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&editor=1');
    await expect(page.locator(`${CARD} .meta`)).toHaveText('January 10, 2024 · Lisbon, Portugal');
    await removeTag(page, 'date');
    await expect(page.locator(`${CARD} .meta`)).toHaveText('Lisbon, Portugal');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon', shuffle: false, description: ['place'] });
  });

  test('the description is built from tags, in the order they are put', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&editor=1');
    await expect(select(page, 'description').locator('option')).toHaveText(['', 'Year', 'Country', 'City', 'People']);
    await expect(field(page, 'description')).toContainText('What to show under each photo');
    await removeTag(page, 'date');
    await removeTag(page, 'place');
    await addTag(page, 'city');
    await addTag(page, 'year');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon', shuffle: false, description: ['city', 'year'] });
    await expect(page.locator(`${CARD} .meta`)).toHaveText('Lisbon · 2024');
    // Dragging a chip gives the same tags in another order.
    await field(page, 'description').locator('.chip[data-value="year"]').click({ modifiers: ['Shift'] });
    expect(await tags(page)).toEqual(['year', 'city']);
    await expect(page.locator(`${CARD} .meta`)).toHaveText('2024 · Lisbon');
  });

  test('adding people asks Immich who is in the photos', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&editor=1');
    await expectShown(page, 'lisbon-0 preview');
    expect((await calls(page)).requests.at(-1).people).toBeUndefined();
    await addTag(page, 'people');
    await expect.poll(async () => (await calls(page)).requests.at(-1)).toMatchObject({ album: 'lisbon', people: true });
    await expect(page.locator(`${CARD} .meta`)).toHaveText('January 10, 2024 · Lisbon, Portugal · Ana');
  });

  test('the date and place switches of earlier versions become a description', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&show_date=0&editor=1');
    expect(await tags(page)).toEqual(['place']);
    await input(page, 'title').fill('Summer');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon', shuffle: false, description: ['place'], title: 'Summer' });
  });

  test('typing is not lost when the album list arrives', async ({ page }) => {
    await open(page, 'album=lisbon&editor=1');
    await input(page, 'title').focus();
    await input(page, 'title').pressSequentially('Sum');
    await albumsListed(page);
    await input(page, 'title').pressSequentially('mer');
    expect((await lastConfig(page)).title).toBe('Summer');
    await expect(input(page, 'title')).toHaveValue('Summer');
  });

  test('offers the three fits, and saves fill the tile', async ({ page }) => {
    await open(page, 'album=lisbon&editor=1');
    await expect(select(page, 'fit').locator('option')).toHaveText(['', 'Automatic', 'Fill the tile', 'Show the whole photo']);
    await expect(field(page, 'fit')).toContainText('Automatic fills the tile');
    await select(page, 'fit').selectOption('cover');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon', fit: 'cover' });
  });

  test('changing options keeps the album and does not reload it', async ({ page }) => {
    await open(page, 'album=lisbon&shuffle=0&interval=3&editor=1');
    await expectShown(page, 'lisbon-0 preview');
    await albumsListed(page);
    const before = (await calls(page)).photos;
    await input(page, 'title').fill('Summer');
    await removeTag(page, 'place');
    // Longer than the harness takes to answer, so a reload would be counted.
    await page.waitForTimeout(200);
    expect((await calls(page)).photos).toBe(before);
    expect(await shown(page)).toBe('lisbon-0 preview');
  });

  test('random photos need no album and are already shuffled', async ({ page }) => {
    await open(page, 'album=lisbon&editor=1');
    await albumsListed(page);
    await select(page, 'source').selectOption('random');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon', source: 'random' });
    await expect.poll(() => fields(page)).toEqual(['source', 'interval', 'videos', 'fit', 'description', 'title']);
    await expect(field(page, 'source')).toContainText('leaves out hidden, locked, archived and deleted photos');
    await expect.poll(() => shown(page)).toMatch(/^random\d-\d preview$/);
    await select(page, 'source').selectOption('album');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon' });
    await expect(select(page, 'album')).toHaveValue('lisbon');
  });

  test('shows an album saved by the standalone card, and saves it as a plain ID', async ({ page }) => {
    await open(page, 'album=lisbon&legacy=1&editor=1');
    await albumsListed(page);
    await expect(select(page, 'album')).toHaveValue('lisbon');
    await select(page, 'fit').selectOption('cover');
    expect(await lastConfig(page)).toEqual({ album: 'lisbon', fit: 'cover' });
  });

  test('keeps an album it can no longer find in the list', async ({ page }) => {
    await open(page, 'album=gone&editor=1');
    await expect(select(page, 'album').locator('option', { hasText: 'Current album' })).toHaveCount(1);
    await expect(select(page, 'album')).toHaveValue('gone');
  });

  test('says when no albums are found', async ({ page }) => {
    await open(page, 'editor=1&nosource=1');
    await expect(field(page, 'album')).toContainText('No albums found');
  });

  test('offers no server choice with one server', async ({ page }) => {
    await open(page, 'album=lisbon&editor=1');
    await albumsListed(page);
    expect(await fields(page)).not.toContain('server');
  });

  test('lets you pick the server when there are several', async ({ page }) => {
    await open(page, 'editor=1&multi=1');
    await expect(select(page, 'server').locator('option')).toHaveText(['', 'immich.local', 'photos.example.com']);
    await expect(select(page, 'server')).toHaveValue('server-1');
    await albumsListed(page);
    await select(page, 'server').selectOption('server-2');
    await expect(select(page, 'album').locator('option', { hasText: 'Other server album' })).toHaveCount(1);
    await select(page, 'album').selectOption('other');
    expect(await lastConfig(page)).toEqual({ server: 'server-2', album: 'other' });
    await expect.poll(async () => (await calls(page)).requests.at(-1)).toMatchObject({ server: 'server-2', album: 'other' });
  });

  test("says so if the form can't be loaded", async ({ page }) => {
    await open(page, 'editor=1&noform=1');
    await expect(page.locator('#editor')).toContainText("Couldn't load the editor");
  });
});

test.describe('magic editor', () => {
  test('asks what to show and how many', async ({ page }) => {
    await open(page, 'card=magic&editor=1');
    await expect.poll(() => fields(page)).toEqual(['query', 'count', 'interval', 'shuffle', 'videos', 'fit', 'description', 'title']);
    await expect(input(page, 'count')).toHaveValue('50');
    await expect(field(page, 'query')).toContainText('beach sunset');
  });

  test('saves the description as you type, and searches after a pause', async ({ page }) => {
    await open(page, 'card=magic&editor=1');
    await expect(field(page, 'query')).toBeVisible();
    await input(page, 'query').pressSequentially('snow');
    expect(await lastConfig(page)).toEqual({ query: 'snow' });
    await expect.poll(() => shown(page)).toMatch(/^snow-\d preview$/);
    expect((await calls(page)).requests.map((r) => r.query)).toEqual(['snow']);
  });

  test('saves a different number of photos', async ({ page }) => {
    await open(page, 'card=magic&query=snow&editor=1');
    await expect(field(page, 'count')).toBeVisible();
    await input(page, 'count').fill('100');
    await input(page, 'count').blur();
    expect(await lastConfig(page)).toEqual({ query: 'snow', count: 100 });
  });
});

test.describe('on this day editor', () => {
  test('needs no setup and plays in date order by default', async ({ page }) => {
    await open(page, 'card=on_this_day&editor=1');
    await expect.poll(() => fields(page)).toEqual(['interval', 'shuffle', 'videos', 'fit', 'description', 'title']);
    await expect(input(page, 'shuffle')).not.toBeChecked();
    await input(page, 'shuffle').check();
    expect(await lastConfig(page)).toEqual({ shuffle: true });
    await input(page, 'shuffle').uncheck();
    expect(await lastConfig(page)).toEqual({});
  });
});

test.describe('translations', () => {
  const source = readFileSync(join(__dirname, '..', '..', 'custom_components', 'immich_slideshow', 'frontend', 'immich-slideshow.js'), 'utf8');
  const literal = source.match(/const IS_TRANSLATIONS = (\{[\s\S]*?\n\});/)[1];
  // eslint-disable-next-line no-new-func
  const translations = new Function(`return ${literal}`)();
  const keys = Object.keys(translations.en);

  for (const lang of Object.keys(translations)) {
    test(`${lang} has every string`, () => {
      expect(Object.keys(translations[lang]).sort()).toEqual([...keys].sort());
    });
  }

  test('every string the code asks for exists', () => {
    const code = source.slice(source.indexOf('const IS_ICONS'));
    const used = [...code.matchAll(/\b(?:_t|t|isT)\((?:[^,()]+, )?'([a-z_]+)'\)/g)].map((match) => match[1]);
    expect(used.length).toBeGreaterThan(5);
    for (const key of used) expect(keys).toContain(key);
    const kinds = [...code.matchAll(/(?:placeholder|empty): (?:\(\w*\) => )?(?:\([^)]*\) ?\? ?)?'([a-z_]+)'/g)].map((match) => match[1]);
    for (const key of kinds) expect(keys).toContain(key);
  });

  test('every editor field has a label', () => {
    const names = [...source.matchAll(/name: '([a-z_]+)'/g)].map((match) => match[1]);
    for (const name of new Set([...names, 'server', 'source', 'album', 'fit'])) expect(keys).toContain(`editor_${name}`);
  });
});
