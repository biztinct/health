// Probe: sign in as each role, open CRM > Contacts, press "All Dates", report any error dialog.
// usage: node check_contacts_all.js login:password [login:password ...]
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  for (const cred of process.argv.slice(2)) {
    const [login, pw] = cred.split(/:(.*)/s);
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, timezoneId: 'Asia/Ho_Chi_Minh' });
    const page = await ctx.newPage();
    await page.goto('https://carejiox.com/web/login');
    await page.fill('#login', login);
    await page.fill('#password', pw);
    await Promise.all([page.waitForURL(/bizapp|odoo/), page.click('button.btn-primary:has-text("Log in")')]);
    await page.goto('https://carejiox.com/bizapp/action-1438');
    await page.waitForTimeout(3500);
    await page.click('text="All Dates"');
    await page.waitForTimeout(3500);
    const dialog = await page.locator('.modal-body').allInnerTexts();
    const rows = await page.locator('tr.o_data_row').count();
    console.log(login, '| rows:', rows, '| dialog:', dialog.join(' ').replace(/\s+/g, ' ').slice(0, 160) || 'none');
    await ctx.close();
  }
  await browser.close();
})();
