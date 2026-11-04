// Shared helpers for the Bookings cases BK-01..BK-05 (no shared state: each case keeps its own).
//
// Gotchas (paid for while recording BK-01..05, 4 Nov 2026):
// - Contact's Book button: `button[data-action=book]`. A `.o_form_view button` "Book" match
//   can be the hidden form button and the click silently misses.
// - Add Services: the first click is `.pcd-add-btn`; it then turns into a −/+ stepper, so
//   further units are `.pcd-qty-btn` (last = +).
// - Quick Booking confirmation: prove on `.qb-modal-header` + `.qb-modal-info-grid` (date as
//   "06 Nov 2026, 10:00", see qbDate). "Create Another" keeps service, duration, facility,
//   location, date and the contact; the services must be added again.
// - View Invoice opens in the Finance area: call openBooking(kit, bk, true) (area switch) next.
// - Many2one fields (e.g. main contact) have no innerText: read them with kit.fieldValues.
// - Lists re-render right after a search: wait for the row before clicking it, or the click
//   hits a detached element ("Element is not attached to the DOM").
// - Re-running a booking case on the same days: archive the previous run's bookings first, or
//   the slot is taken (the next free one is picked) and "each date exactly once" sees doubles.
// - Labels known only at run time (BK number, slot time): add them to kit._proofVi in run().
// - A client created from a contact keeps the contact's number as its client ID (owner's rule).
// - The OM's quote dialog (`.hfq-panel`) shows quantities and totals but no unit names; units
//   (Wound, Visit, Hours, Injection) show on the invoice lines.
const c = require('./common');

const user = (login, role, role_vi, extra = {}) => ({ login, password: c.pw(login), role, role_vi, ...extra });
const users = {
  omhn: c.users.omhn,
  crm: c.users.crm,
  owner: c.users.owner,
  omhcm: user('om_hcm', 'Operations Manager, Ho Chi Minh City', 'Quản lý vận hành TP.HCM'),
  nurse: user('nurse_hn', 'Nurse, Hanoi', 'Điều dưỡng Hà Nội', { name: 'Client UAT nurse_hn' }),
};

// A money amount as any screen prints it: 1,050,000 / 1.050.000, optional decimals.
const money = (n) => {
  const s = Math.round(n).toLocaleString('en-US').replace(/,/g, '[.,]');
  return new RegExp(`(^|[^\\d.,])${s}(\\.00)?(?![\\d])`);
};
const has = (t, n) => money(n).test(t);

// Vietnam date `days` ahead: { day, month (0-based), monShort, d (Date as VN wall clock in UTC fields) }
const vnDay = (days) => {
  const d = new Date(Date.now() + 7 * 3600e3 + days * 86400e3);
  return { d, day: d.getUTCDate(), month: d.getUTCMonth(), monShort: d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }),
    dow: d.toLocaleString('en-US', { weekday: 'short', timeZone: 'UTC' }) };
};

// Operations › Bookings, list view, search a booking number or client, open the first matching row.
async function bookingsList(kit, query, area = true) {
  const p = kit.page;
  if (area) await kit.area('Operations');
  await kit.click(c.sidebar(p, 'Bookings'), 3000);
  const listBtn = p.locator('.o_switch_view.o_list').filter({ visible: true }).first();
  if (await listBtn.count()) await kit.click(listBtn, 2500);
  if (query) {
    await kit.type(p.locator('.o_searchview_input'), query, 900);
    await p.keyboard.press('Enter');
    await kit.hold(2500);
  }
}

async function openBooking(kit, bk, area = true) {
  const p = kit.page;
  await bookingsList(kit, bk, area);
  await kit.click(p.locator('tr.o_data_row', { hasText: bk }).locator('td').nth(1), 4500);
  await p.locator('.ws-hero').first().waitFor({ timeout: 15000 });
}

const tab = async (kit, name) => {
  const p = kit.page;
  await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: new RegExp(`^\\s*${name}\\s*$`) }).first(), 2200);
};

// New Contact (CT-05 flow): a caller for an existing client, created and opened.
async function newContactForClient(kit, { caller, phone, client, code, interest = 'Clinic Visit' }) {
  const p = kit.page;
  await kit.click(p.getByRole('button', { name: 'New Contact' }), 1500);
  await kit.type(p.getByPlaceholder('Full name'), caller);
  await kit.type(p.getByPlaceholder('Phone number'), phone, 800);
  await kit.click(p.locator('.nc-footer button', { hasText: 'Next' }), 1500);
  await kit.click(p.locator('button').filter({ hasText: /^\s*Client Representative\s*$/ }).first(), 700);
  await kit.type(p.getByPlaceholder('Name of the client'), client, 300);
  await kit.click(p.locator('.nc-search-btn').filter({ visible: true }).last(), 2000);
  await kit.click(p.locator('.nc-search-row', { hasText: code }).first(), 1000);
  const linked = p.locator('.nc-selected-client');
  const input = p.getByPlaceholder('Name of the client');
  await kit.proof([input, linked], 'Contact linked to the existing client', async (t) =>
    /Linked to existing client/i.test(t) && (await input.inputValue()).includes(client), 2400);
  await kit.click(p.locator('button').filter({ hasText: new RegExp(`^\\s*${interest}\\s*$`) }).first(), 700);
  return linked;
}

async function createContact(kit) {
  const p = kit.page;
  await kit.click(p.locator('.nc-footer button', { hasText: 'Create Contact' }), 2500);
  const code = ((await p.locator('.nc-success-code').innerText().catch(() => '')) || '').replace(/[()]/g, '').trim();
  await kit.click(p.locator('button').filter({ hasText: /^\s*Open Record\s*$/ }).first(), 3500);
  return code;
}

// Quick Booking: add services by code and visible name, e.g. [{ q: 'Internal examination', code: 'bs_020' }]
async function qbAddServices(kit, items) {
  const p = kit.page;
  await kit.click(p.locator('.qb-add-services-btn'), 2000);
  for (const it of items) {
    await kit.type(p.locator('.pcd-search-input'), it.q, 1200);
    const card = p.locator('.pcd-card', { hasText: it.code }).filter({ hasText: new RegExp(`^\\s*${it.q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`) }).first();
    await kit.click(card.locator('.pcd-add-btn').first(), 700);
    for (let i = 1; i < (it.qty || 1); i++) await kit.click(card.locator('.pcd-qty-btn').last(), 600);
  }
  await kit.click(p.locator('.pcd-done-btn'), 1500);
}

// The confirmation's date as printed: "06 Nov 2026, 10:00"
const qbDate = (d, hm) => `${String(d.day).padStart(2, '0')} ${d.monShort} ${d.d.getUTCFullYear()}, ${hm}`;

// First free slot among the given times on the chosen day; returns 'HH:MM'.
async function qbSlot(kit, times) {
  return c.qbPickSlot(kit, times);
}

// Create, prove the confirmation, return { bk, text }.
async function qbCreate(kit, label) {
  const p = kit.page;
  await kit.click(p.locator('.qb-btn-create'), 4500);
  const done = p.locator('.qb-modal-card').first();
  await done.waitFor({ timeout: 15000 }).catch(() => {});
  const text = (await done.innerText().catch(() => '')) || '';
  const bk = (text.match(/BK\d{3,}/) || [''])[0];
  const box = [done.locator('.qb-modal-header'), done.locator('.qb-modal-info-grid')];
  return { bk, text, done, box };
}

// The contact's Book button (hero action).
const bookBtn = (p) => p.locator('button[data-action=book]').filter({ visible: true }).first();

module.exports = { bookBtn, qbDate, users, money, has, vnDay, bookingsList, openBooking, tab, newContactForClient, createContact, qbAddServices, qbSlot, qbCreate };
