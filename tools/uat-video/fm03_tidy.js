// After an FM-03 run: open Studio on the client; if an unpublished draft is waiting,
// continue it and publish it, so the next Studio session starts clean. No field is created.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const pw = JSON.parse(fs.readFileSync(path.join(__dirname, 'accounts.local.json'), 'utf8'));
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1600, height: 900 } })).newPage();
  await page.goto('https://carejiox.com/web/login');
  await page.fill('#login', 'uat_owner'); await page.fill('#password', pw.uat_owner);
  await Promise.all([page.waitForURL(/bizapp/), page.click('button.btn-primary:has-text("Log in")')]);
  await page.goto('https://carejiox.com/bizapp/action-1430/res.partner/37955'); await page.waitForTimeout(6000);
  await page.getByRole('button', { name: /^\s*Studio\s*$/ }).filter({ visible: true }).first().click();
  await page.waitForTimeout(6000);
  const draft = page.locator('.fs-sheet', { hasText: 'not published' });
  if (await draft.count()) { console.log('draft found'); await draft.locator('button', { hasText: 'Start from the published layout' }).click(); await page.waitForTimeout(3000); }
  console.log('bar:', (await page.locator('.fs-bar').innerText()).replace(/\s+/g, ' '));
  const pub = page.locator('.fs-bar button', { hasText: 'Publish' });
  if (await pub.isEnabled()) {
    await pub.click(); await page.waitForTimeout(1500);
    console.log('sheet:', (await page.locator('.fs-sheet').innerText()).replace(/\s+/g, ' '));
    await page.locator('.fs-sheet button', { hasText: 'Publish for everyone' }).click(); await page.waitForTimeout(6000);
    console.log('published');
  } else {
    await page.locator('.fs-bar button[aria-label="Back to the record"]').click(); await page.waitForTimeout(3000);
  }
  await browser.close();
})().catch((e) => { console.log('ERR', e.message); process.exit(1); });
