// Scout helper: sign in, open a URL, screenshot + dump visible text.
// usage: node scout.js <login> <password> <path-or-url> <outName> [waitMs]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [login, pw, target, out, waitMs = '2500'] = process.argv.slice(2);
  const dir = process.env.SCOUT_DIR || path.join(__dirname, 'scout-out');
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5,
    locale: 'en-US', timezoneId: 'Asia/Ho_Chi_Minh',
  });
  const page = await ctx.newPage();
  await page.goto('https://carejiox.com/web/login');
  await page.fill('input[name=login]', login);
  await page.fill('input[name=password]', pw);
  await Promise.all([page.waitForNavigation(), page.click('form.oe_login_form button[type=submit], button.btn-primary:has-text("Log in")')]);
  await page.waitForTimeout(3000);
  if (target !== '-') {
    await page.goto(target.startsWith('http') ? target : 'https://carejiox.com' + target);
    await page.waitForTimeout(+waitMs);
  }
  await page.screenshot({ path: path.join(dir, out + '.png') });
  fs.writeFileSync(path.join(dir, out + '.txt'), page.url() + '\n' + await page.innerText('body'));
  await browser.close();
})();
