// Scout the nurse app: sign in, land on Today, screenshot + visible text + buttons.
// usage: node scout_pwa.js login:password [lat,lng]
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const [login, pw] = process.argv[2].split(/:(.*)/s);
  const geo = (process.argv[3] || '21.0136,105.8487').split(',').map(Number);
  fs.mkdirSync(__dirname + '/scout-out', { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5, timezoneId: 'Asia/Ho_Chi_Minh',
    geolocation: { latitude: geo[0], longitude: geo[1] }, permissions: ['geolocation'],
  });
  const page = await ctx.newPage();
  await page.goto('https://carejiox.com/web/login?redirect=%2Fhealth_pwa%3F%23%2Ftoday');
  await page.fill('#login', login);
  await page.fill('#password', pw);
  await Promise.all([page.waitForURL(/health_pwa/, { timeout: 45000 }), page.click('button.btn-primary:has-text("Log in")')]);
  await page.waitForTimeout(6000);
  await page.screenshot({ path: __dirname + '/scout-out/pwa_today.png' });
  const out = { url: page.url(), text: (await page.innerText('body')).slice(0, 2500),
    buttons: (await page.locator('button, a').allInnerTexts()).map((t) => t.trim()).filter(Boolean).slice(0, 60) };
  fs.writeFileSync(__dirname + '/scout-out/pwa_today.json', JSON.stringify(out, null, 1));
  console.log(JSON.stringify(out).slice(0, 2500));
  await browser.close();
})();
