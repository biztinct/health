// Probe: as one user, press Contacts > All Dates and dump the failing RPC (request + error).
// usage: node probe_failing_call.js login:password
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const [login, pw] = process.argv[2].split(/:(.*)/s);
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
  await page.goto('https://carejiox.com/web/login');
  await page.fill('#login', login);
  await page.fill('#password', pw);
  await Promise.all([page.waitForURL(/bizapp|odoo/), page.click('button.btn-primary:has-text("Log in")')]);
  await page.goto('https://carejiox.com/bizapp/action-1438');
  await page.waitForTimeout(3500);
  page.on('response', async (res) => {
    if (!res.url().includes('/web/dataset/call_kw')) return;
    const body = await res.text();
    if (body.includes('"error"')) {
      fs.writeFileSync(__dirname + '/scout-out/failing_call.json',
        JSON.stringify({ url: res.url(), request: JSON.parse(res.request().postData()), error: JSON.parse(body).error.data }, null, 1));
      console.log('captured', res.url());
    }
  });
  await page.click('text="All Dates"');
  await page.waitForTimeout(4000);
  await browser.close();
})();
