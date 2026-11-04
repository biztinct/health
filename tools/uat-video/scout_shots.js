// Screenshot a list of screens as one user (no recording).
// usage: node scout_shots.js <login> <name>=<path or url> ...   (password from accounts.local.json)
// A step may be "<name>=<path>|click:<css or text=...>" to click something after loading.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [login, ...shots] = process.argv.slice(2);
  const pw = JSON.parse(fs.readFileSync(path.join(__dirname, 'accounts.local.json'), 'utf8'))[login];
  const out = path.join(__dirname, 'scout-out');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 720 }, timezoneId: 'Asia/Ho_Chi_Minh' })).newPage();
  page.on('response', async (r) => {
    if (!r.url().includes('/web/dataset/call_kw')) return;
    try { const j = await r.json(); if (j.error) console.log('RPC ERROR', (j.error.data && j.error.data.message || '').slice(0, 160)); } catch (e) { /* */ }
  });
  await page.goto('https://carejiox.com/web/login');
  await page.fill('#login', login);
  await page.fill('#password', pw);
  await Promise.all([page.waitForURL(/bizapp/), page.click('button.btn-primary:has-text("Log in")')]);
  for (const spec of shots) {
    const [name, rest] = spec.split(/=(.*)/s);
    const [target, ...actions] = rest.split('|');
    if (target) { await page.goto(target.startsWith('http') ? target : 'https://carejiox.com' + target); await page.waitForTimeout(4500); }
    for (const a of actions) {
      const sel = a.replace(/^click:/, '');
      await page.locator(sel).filter({ visible: true }).first().click({ timeout: 8000 }).catch((e) => console.log('click failed', sel, e.message.split('\n')[0]));
      await page.waitForTimeout(2500);
    }
    await page.screenshot({ path: path.join(out, name + '.png') });
    console.log('shot', name, page.url());
  }
  await browser.close();
})();
