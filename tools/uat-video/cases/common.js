// Shared test identities and screen anchors for the contact cases.
const now = new Date();
const vn = new Date(now.getTime() + 7 * 3600e3);          // Vietnam wall clock as UTC fields
const p2 = (n) => String(n).padStart(2, '0');

const fs = require('fs');
const path = require('path');
const STATE = path.join(__dirname, '..', 'state.json');   // hands records from one case to the next
// Test-account passwords live in accounts.local.json (git-ignored): {"<login>": "<password>"}.
const ACCOUNTS = path.join(__dirname, '..', 'accounts.local.json');
const pw = (login) => {
  const a = fs.existsSync(ACCOUNTS) ? JSON.parse(fs.readFileSync(ACCOUNTS, 'utf8')) : {};
  if (!a[login]) throw new Error(`no password for ${login} in accounts.local.json`);
  return a[login];
};

module.exports = {
  pw,
  load: () => (fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {}),
  save: (patch) => fs.writeFileSync(STATE, JSON.stringify({ ...module.exports.load(), ...patch }, null, 1)),
  // Vietnam calendar date `days` from today at hh:mm, as typed into a date-time box (MM/DD/YYYY hh:mm:ss AM)
  // and as the screens print it (Mon D, h:mm AM).
  vnAt: (days, hh, mm = 0) => {
    const d = new Date(Date.now() + 7 * 3600e3 + days * 86400e3);
    const mon = d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
    const h12 = ((hh + 11) % 12) + 1;
    return { typed: `${p2(d.getUTCMonth() + 1)}/${p2(d.getUTCDate())}/${d.getUTCFullYear()} ${p2(h12)}:${p2(mm)}:00 ${hh < 12 ? 'AM' : 'PM'}`,
             shown: `${mon} ${d.getUTCDate()}, ${h12}:${p2(mm)} ${hh < 12 ? 'AM' : 'PM'}` };
  },
  // A unique, valid Vietnamese mobile number per run: 09 + DD HH mm ss (Vietnam time).
  phone: () => { const d = new Date(Date.now() + 7 * 3600e3);
    return `09${p2(d.getUTCDate())}${p2(d.getUTCHours())}${p2(d.getUTCMinutes())}${p2(d.getUTCSeconds())}`; },
  tag: `UAT-VID-${vn.getUTCFullYear()}${p2(vn.getUTCMonth() + 1)}${p2(vn.getUTCDate())}`,
  users: {
    crm: { login: 'uat_crm', password: pw('uat_crm'), role: 'CRM user', role_vi: 'nhân viên CRM' },
    omhn: { login: 'om_hn', password: pw('om_hn'), role: 'Operations Manager, Hanoi', role_vi: 'Quản lý vận hành Hà Nội' },
    owner: { login: 'uat_owner', password: pw('uat_owner'), role: 'Owner', role_vi: 'Chủ sở hữu' },
  },
  // Contacts list / record anchors
  // Sidebar tabs: the label is title case in the DOM, upper case only through CSS.
  sidebar: (page, name) => page.locator('button.vu-tab').filter({
    has: page.locator('.vu-tab-label', { hasText: new RegExp(`^\\s*${name}\\s*$`, 'i') }) }).first(),
  hero: (page) => page.locator('.ws-hero'),
  heroChip: (page) => page.locator('.ws-hero .ws-chip--dot').filter({ visible: true }).first(),
  heroFact: (page, text) => page.locator('.ws-hero .ws-fact', { hasText: text }),
  nextStep: (page) => page.locator('.ws-contact-next'),
  glanceRow: (page, label) => page.locator('.ws-panel--glance .ws-row', { hasText: label }),
  people: (page) => page.locator('.ws-panel--people'),
  statusCard: (page) => page.locator('[name=status_card]'),
  field: (page, name) => page.locator(`.o_field_widget[name="${name}"]`).filter({ visible: true }).first(),
  saveBtn: (page) => page.locator('.o_form_button_save').filter({ visible: true }).first(),
  breadcrumbContacts: (page) => page.locator('a', { hasText: /^\s*Contacts\s*$/ }).filter({ visible: true }).first(),
  listRow: (page, text) => page.locator('tr.o_data_row', { hasText: text }).first(),

  // ---- Quick Booking (shared by the contact, package and booking cases)
  qbGroup: (page, label) => page.locator('.qb-form-group', { has: page.locator('.qb-form-label', { hasText: label }) }).first(),
  async qbFill(kit, { service, duration, facility, location }) {
    const g = (l) => module.exports.qbGroup(kit.page, l);
    if (service) await kit.select(g('Service Type'), service);
    if (duration) await kit.select(g('Duration'), duration);
    if (facility) await kit.select(g('Facility'), facility);
    if (location) await kit.select(g(/^\s*Location/), location);
  },
  async qbPickDay(kit, daysAhead) {
    const p = kit.page;
    const d = new Date(Date.now() + 7 * 3600e3 + daysAhead * 86400e3);
    const now = new Date(Date.now() + 7 * 3600e3);
    if (d.getUTCMonth() !== now.getUTCMonth()) await kit.click(p.locator('.qb-cal-nav').last(), 800);
    await kit.click(p.locator('.qb-cal-day:not(.qb-cal-day--disabled):not(.qb-cal-day--empty)')
      .filter({ hasText: new RegExp(`^\\s*${d.getUTCDate()}\\s*$`) }).first(), 2200);
    return d;
  },
  // First free slot among `times` ('HH:MM'), switching Morning / Afternoon / Evening as needed.
  async qbPickSlot(kit, times) {
    const p = kit.page;
    for (const hm of times) {
      const h = Number(hm.slice(0, 2));
      const tod = h < 12 ? 'Morning' : h < 17 ? 'Afternoon' : 'Evening';
      const card = p.locator('.qb-tod-card', { hasText: tod }).first();
      if (!(await card.getAttribute('class')).includes('active')) await kit.click(card, 1500);
      const b = p.locator('.qb-slot-grid button').filter({ hasText: new RegExp(`^\\s*${hm}`) })
        .filter({ hasNot: p.locator('.fa-lock, .fa-exclamation-triangle') }).first();
      if (await b.count() && await b.isEnabled()) { await kit.click(b, 1000); return hm; }
    }
    throw new Error('no free slot among ' + times.join(','));
  },
  // Half-hour slots from `fromMin` minutes after now (Vietnam time) up to 19:30.
  slotsFromNow: (fromMin) => {
    const t = new Date(Date.now() + 7 * 3600e3 + fromMin * 60e3);
    let m = Math.ceil((t.getUTCHours() * 60 + t.getUTCMinutes()) / 30) * 30;
    const out = [];
    for (; m <= 19 * 60 + 30; m += 30) out.push(`${p2(Math.floor(m / 60))}:${p2(m % 60)}`);
    return out;
  },
  shownTime: (d, hm) => {
    const [h, m] = hm.split(':').map(Number);
    return `${d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })} ${d.getUTCDate()}, ${((h + 11) % 12) + 1}:${p2(m)} ${h < 12 ? 'AM' : 'PM'}`;
  },
};
