// Optional acceptance runner: use an existing Playwright install, never a production URL.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = 'http://127.0.0.1:8765';
const output = process.env.EVIDENCE_DIR || '/tmp/mock-preview-evidence';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({headless: true, executablePath: process.env.CHROMIUM_PATH || undefined});
try {
  const page = await browser.newPage({viewport: {width: 430, height: 932}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  await page.goto(origin);
  for (const skill of ['reading', 'listening']) {
    await page.getByLabel('Skill', {exact: true}).selectOption(skill);
    await page.getByRole('heading', {name: 'Section 1/' + (skill === 'reading' ? 3 : 4)}).waitFor();
    await page.locator('fieldset input').first().fill('box');
    await page.screenshot({path: output + '/' + skill + '-430.png', fullPage: true});
    for (let n = 1; n <= (skill === 'reading' ? 3 : 4); n++) {
      const widths = await page.evaluate(() => ({viewport: innerWidth, document: document.documentElement.scrollWidth}));
      assert.ok(widths.document <= widths.viewport, JSON.stringify(widths));
      if (n < (skill === 'reading' ? 3 : 4)) await page.getByRole('button', {name: 'Next section'}).click();
    }
    await page.getByRole('button', {name: 'Review submission'}).click();
    await page.getByRole('button', {name: 'Keep editing'}).click();
    await page.getByRole('button', {name: 'Review submission'}).click();
    await page.getByRole('button', {name: 'Submit answers', exact: true}).click();
    await page.getByRole('heading', {name: 'Raw result: 1 / 40', exact: true}).waitFor();
    await page.screenshot({path: output + '/' + skill + '-result-430.png', fullPage: true});
    await page.getByRole('button', {name: 'New attempt'}).click();
    await page.getByRole('heading', {name: 'Section 1/' + (skill === 'reading' ? 3 : 4)}).waitFor();
    assert.equal(await page.locator('fieldset input').first().inputValue(), '');
    assert.equal(await page.getByRole('heading', {name: 'Raw result: 1 / 40'}).count(), 0);
  }
  assert.deepEqual(errors, []);
  console.log('PASS: Reading + Listening, real Python 1/40, cancel/review, new attempt reset, all sections 430px overflow-free, no page errors.');
} finally {
  await browser.close();
}
