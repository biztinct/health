// Shared helpers for the nurse-app cases MB-02..MB-10 (Ho Chi Minh City). All nine videos
// follow ONE visit for Đặng Thị Quỳnh, booked today; the visit is handed from one case to the
// next through mb_state.json (never the shared state.json). MB_STATE=<file> points a practice
// run at another state file.
const fs = require('fs');
const path = require('path');
const c = require('./common');
const a = require('./as_common');

const p2 = (n) => String(n).padStart(2, '0');
const STATE = process.env.MB_STATE ? path.resolve(process.env.MB_STATE) : path.join(__dirname, '..', 'mb_state.json');
const load = () => (fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {});
const save = (patch) => fs.writeFileSync(STATE, JSON.stringify({ ...load(), ...patch }, null, 1));

const user = (login, role, role_vi, extra = {}) => ({ login, password: c.pw(login), role, role_vi, ...extra });
const users = {
  om: user('om_hcm', 'Operations Manager, Ho Chi Minh City', 'Quản lý vận hành TP.HCM'),
  nurse: user('nurse_hcm', 'Nurse, Ho Chi Minh City', 'Điều dưỡng TP.HCM', { name: 'Client UAT nurse_hcm' }),
  finance: user('uat_owner', 'Owner (Finance)', 'Chủ sở hữu (Tài chính)'),
};

// The client and the source case TC-13 (workbook row 19): home visit, injection × 2 = 210,000 ₫.
const client = { name: 'Đặng Thị Quỳnh', code: '02_0000326', id: 37963, address: '34 Võ Văn Tần, Quận 3, TP.HCM', contact: 'Đặng Văn Sơn' };
const TC = {
  type: 'Home Visit', duration: '30 minutes', facility: 'TPHCM_PK_CSTNVU', location: 'Patient Home',
  search: 'Intramuscular', code: 'đd_070_tphcm', qty: 2,
  product: 'Intramuscular, intradermal, subcutaneous injection',
  productVi: 'Tiêm bắp, trong da, dưới da', unit: 105000, total: 210000,
};

// Vietnam today
const today = () => a.vnDay(0);

// A money amount as any screen prints it: 210,000 / 210.000, optional decimals.
const money = (n) => new RegExp(`(^|[^\\d.,])${Math.round(n).toLocaleString('en-US').replace(/,/g, '[.,]')}([.,]00)?(?![\\d])`);

// ---------------------------------------------------------------- screens
const HCM = { latitude: 10.7769, longitude: 106.7009 };
const PHONE = { width: 960, height: 540 };   // below 1024 px the nurse app shows its bell (16:9)
const DESKTOP = { width: 1280, height: 720 };

// The kit moves the caption bar to the top only for targets low on a 720 px screen; on the
// 540 px nurse-app screen use the real height (patched on this recording's kit only).
function fitCaptions(kit) {
  kit._capClear = async function (bottom) {
    const h = (this.page.viewportSize() || { height: 720 }).height;
    const top = bottom > h - 80;
    if (top !== !!(this.state && this.state.capTop)) await this._state({ capTop: top });
  };
}

// Sign in as the nurse in the nurse app, at tablet size, near the client in Ho Chi Minh City.
async function asNurse(kit, n) {
  fitCaptions(kit);
  await kit.page.setViewportSize(PHONE);
  await kit.context.setGeolocation(HCM);
  await kit.switchUser(n, users.nurse, true);
  await kit.page.locator('.booking-card, .empty-state').first().waitFor({ timeout: 20000 }).catch(() => {});
  await kit.hold(800);
}

async function asStaff(kit, n, who) {
  await kit.page.setViewportSize(DESKTOP);
  await kit.switchUser(n, who, false);
}

// The visit's card on the nurse app's day list.
const card = (p, st) => p.locator(`.booking-card[data-fso-id="${st.id}"]`).filter({ visible: true }).first();
const sheet = (p) => p.locator('.booking-detail-modal').filter({ visible: true }).first();
const section = (p, title) => sheet(p).locator('.detail-section', { has: p.locator('.section-title', { hasText: title }) }).first();
const btn = (p, re) => p.locator('button').filter({ hasText: re }).filter({ visible: true }).first();

// Tap the visit on today's list and wait for its details.
async function openVisit(kit, st) {
  const p = kit.page;
  await card(p, st).waitFor({ timeout: 20000 });
  await dismissBanner(kit);
  // the list may still be refreshing (after Accept / a reload): tap again if nothing opened
  for (let i = 1; ; i++) {
    await kit.click(card(p, st).locator('.booking-patient-name'), 2500);
    try { await sheet(p).locator('.modal-body').first().waitFor({ timeout: 8000 }); break; } catch (e) {
      if (i >= 3) throw new Error('visit details did not open');
      console.log('  visit details did not open, tapping again');
      await dismissBanner(kit);
    }
  }
  await kit.hold(800);
}

// The nurse app's red "Notifications Blocked" banner (a recording browser cannot allow phone
// notifications) comes back after a reload and covers the list: dismiss it on screen.
async function dismissBanner(kit) {
  const p = kit.page;
  const b = p.locator('button').filter({ hasText: /Đóng \/ Dismiss/ }).filter({ visible: true }).first();
  if (await b.isVisible().catch(() => false)) {
    await kit.click(b, 1200).catch(() => {});
    await b.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => {});
  }
}

// Reload the nurse app (as a nurse pulling to refresh) and wait for the day list.
async function reloadApp(kit) {
  const p = kit.page;
  await p.reload();
  await p.locator('.booking-card, .empty-state').first().waitFor({ timeout: 20000 }).catch(() => {});
  await p.locator('button').filter({ hasText: /Đóng \/ Dismiss/ }).filter({ visible: true }).first().waitFor({ timeout: 6000 }).catch(() => {});
  await dismissBanner(kit);
  await kit.hold(1200);
}

// Close the notifications panel (it stays open after Accept).
async function closeBell(kit) {
  const p = kit.page;
  const open = () => p.locator('.notif-panel').filter({ visible: true }).count();
  const x = p.locator('.notif-panel-close').filter({ visible: true }).first();
  await x.waitFor({ timeout: 6000 }).catch(() => {});
  if (await x.isVisible().catch(() => false)) await kit.click(x, 2000);
  // After Accept the × may not close it (seen 4 Nov, nurse app 1.21.4): tap the bell, then reload.
  if (await open()) { console.log('  panel still open after ×: tapping the bell'); await kit.click(p.locator('.notif-bell-btn').filter({ visible: true }).first(), 2000); }
  if (await open()) { console.log('  panel still open: reloading the app'); await reloadApp(kit); }
  await kit.hold(1200);
}

// Close the details sheet (the × in its header).
async function closeVisit(kit) {
  const p = kit.page;
  const x = sheet(p).locator('.btn-modal-close').first();
  if (await x.count()) await kit.click(x, 1500);
}

// Operations › Bookings › open the booking by number (list view).
async function openBooking(kit, n, bk, en, vi) {
  return a.openBooking(kit, n, bk, en, vi);
}

// "Nov 4, 2:00 PM" as the booking screen prints a time today
const shownToday = (hm) => `${today().mon} ${today().day}, ${a.h12(hm)}`;

// A clock time on screen (h:mm or hh:mm, optional AM/PM) within `tol` minutes of now (Vietnam).
function nearNow(text, tol = 6) {
  const now = new Date(Date.now() + 7 * 3600e3);
  const nowMin = now.getUTCHours() * 60 + now.getUTCMinutes();
  const re = /(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/gi;
  let m;
  while ((m = re.exec(text))) {
    let h = Number(m[1]);
    if (m[3]) h = (h % 12) + (m[3].toUpperCase() === 'PM' ? 12 : 0);
    const d = Math.abs(h * 60 + Number(m[2]) - nowMin);
    if (d <= tol || d >= 1440 - tol) return true;
  }
  return false;
}

module.exports = { STATE, load, save, users, client, TC, today, money, HCM, PHONE, DESKTOP, asNurse, asStaff, card, sheet, section, btn,
  openVisit, closeVisit, closeBell, dismissBanner, reloadApp, openBooking, shownToday, nearNow, p2 };
