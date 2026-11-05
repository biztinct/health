// Shared helpers for the administration cases UM-01..03, FM-01..02, AU-01, NA-01, NA-03.
// Kept apart from common.js on purpose: own state file (adm_state.json, never state.json),
// no bookings, no money. ADM_STATE=<file> points a practice run at another state file.
//
// Learned while scouting (5 Nov 2026):
// - Settings (rail) › People › "Users & Roles" is the users list (name, login, job, area);
//   "Access & roles" › People › "Add a person" is the only screen that takes a first password
//   (the user form has no password field; "Send a password link" needs outgoing mail).
// - Settings › Master data › Field Requirements: tiles › model › one row per field; Active
//   creates a GLOBAL rule at once, Global off + a role chip narrows it; the bin removes it.
// - Settings › Records › Audit Log: When / Changed By / Module / Record / Field / From / To.
// - An Operations Manager's area is a fixed pill (.vu-catchment-pill); the Owner's is a menu.
// - A refused direct link to a booking returns to the Bookings calendar with an access dialog.
const fs = require('fs');
const path = require('path');
const c = require('./common');

const p2 = (n) => String(n).padStart(2, '0');
const STATE = process.env.ADM_STATE ? path.resolve(process.env.ADM_STATE) : path.join(__dirname, '..', 'adm_state.json');
const load = () => (fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {});
const save = (patch) => fs.writeFileSync(STATE, JSON.stringify({ ...load(), ...patch }, null, 1));

const user = (login, role, role_vi, extra = {}) => ({ login, password: c.pw(login), role, role_vi, ...extra });
const users = {
  owner: user('uat_owner', 'Owner', 'Chủ sở hữu', { name: 'Client UAT owner' }),
  crm: user('uat_crm', 'CRM user', 'Nhân viên CRM', { name: 'Client UAT crm' }),
  omhn: user('om_hn', 'Operations Manager, Hanoi', 'Quản lý vận hành Hà Nội', { name: 'Client UAT om_hn' }),
  omhcm: user('om_hcm', 'Operations Manager, HCMC', 'Quản lý vận hành TP.HCM', { name: 'Client UAT om_hcm' }),
  nursehn: user('nurse_hn', 'Nurse, Hanoi', 'Điều dưỡng Hà Nội', { name: 'Client UAT nurse_hn' }),
  nursehcm: user('nurse_hcm', 'Nurse, HCMC', 'Điều dưỡng TP.HCM', { name: 'Client UAT nurse_hcm' }),
  doctor: user('doctor_hn', 'Doctor, Hanoi', 'Bác sĩ Hà Nội', { name: 'Client UAT doctor_hn' }),
};

// Vietnam wall clock now: { hhmm, dd, mm, yyyy }
const vnNow = () => {
  const d = new Date(Date.now() + 7 * 3600e3);
  return { d, hhmm: `${p2(d.getUTCHours())}${p2(d.getUTCMinutes())}`, dd: p2(d.getUTCDate()), mm: p2(d.getUTCMonth() + 1), yyyy: d.getUTCFullYear() };
};

// Left rail area (Home, CRM, Operations, Finance, Settings...).
async function area(kit, name) {
  const p = kit.page;
  const b = p.getByRole('button', { name: new RegExp(`^${name}\\b`) }).first();
  await kit.click(b, 1500);
  await p.mouse.move(760, 400, { steps: 12 });
  await kit.hold(1200);
}
// Sidebar tab by its label (title case in the DOM)
const tab = (p, name) => c.sidebar(p, name);
// The left rail's area names, as the signed-in person sees them.
const railNames = (p) => p.evaluate(() => [...document.querySelectorAll('.vu-rail-entry')]
  .map((e) => (e.getAttribute('aria-label') || e.title || e.innerText || '').replace(/\s*\(Alt\+\d+\)\s*/, '').trim()));
const rail = (p) => p.locator('.vu-rail, nav').filter({ has: p.locator('.vu-rail-entry') }).first();
const sideTabs = (p) => p.locator('button.vu-tab').first().locator('xpath=..');
const catchment = (p) => p.locator('.vu-catchment').filter({ visible: true }).first();

// Operations › Bookings › List view (the menu opens a calendar).
async function bookingsList(kit) {
  const p = kit.page;
  await kit.click(tab(p, 'Bookings'), 3000);
  const listBtn = p.locator('.o_switch_view.o_list').filter({ visible: true }).first();
  await listBtn.waitFor({ timeout: 15000 });
  await kit.click(listBtn, 3000);
  await p.locator('.o_list_renderer').first().waitFor({ timeout: 15000 });
}
// Search the list for `text` (clears earlier facets first).
async function listSearch(kit, text) {
  const p = kit.page;
  while (await p.locator('.o_searchview_facet .o_facet_remove').filter({ visible: true }).count()) {
    await kit.click(p.locator('.o_searchview_facet .o_facet_remove').filter({ visible: true }).first(), 1500);
  }
  const box = p.locator('.o_searchview_input').filter({ visible: true }).first();
  await kit.type(box, text, 300);
  await p.keyboard.press('Enter');
  await kit.hold(2500);
}

module.exports = { users, load, save, vnNow, area, tab, railNames, rail, sideTabs, catchment, bookingsList, listSearch, p2 };
