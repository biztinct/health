// Shared helpers for the Assignment / Cancellation / Rescheduling / Mobile cases
// (AS-01..03, CR-01..02, MB-01). Kept apart from common.js on purpose: these cases
// keep their own state (no state.json) and book only 5 to 9 days ahead.
const c = require('./common');

const p2 = (n) => String(n).padStart(2, '0');

const users = {
  omhn: c.users.omhn,
  nurse: { login: 'nurse_hn', password: c.pw('nurse_hn'), role: 'Nurse, Hanoi', role_vi: 'Điều dưỡng Hà Nội', name: 'Client UAT nurse_hn' },
  doctor: { login: 'doctor_hn', password: c.pw('doctor_hn'), role: 'Doctor, Hanoi', role_vi: 'Bác sĩ Hà Nội', name: 'Client UAT doctor_hn' },
  omhcm: { login: 'om_hcm', password: c.pw('om_hcm'), role: 'Operations Manager, HCMC', role_vi: 'Quản lý vận hành TP.HCM' },
};

const client = { name: 'Vũ Thị Khánh', code: '01_0000726' };

// Vietnam calendar day `days` from today: { d (UTC fields = VN wall clock), day, mon, dmy, iso }
const vnDay = (days) => {
  const d = new Date(Date.now() + 7 * 3600e3 + days * 86400e3);
  return { d, day: d.getUTCDate(), mon: d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }),
    dmy: `${p2(d.getUTCDate())}/${p2(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`,
    iso: `${d.getUTCFullYear()}-${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())}` };
};
const h12 = (hm) => { const [h, m] = hm.split(':').map(Number); return `${((h + 11) % 12) + 1}:${p2(m)} ${h < 12 ? 'AM' : 'PM'}`; };

// The nurse app is a phone/tablet app: its notification bell (Accept / Decline) is in the
// header that only shows below 1024 px. Record it at a 16:9 tablet size, then go back.
const TABLET = { width: 1008, height: 567 };
const DESKTOP = { width: 1280, height: 720 };

// A click that tolerates a screen still settling (re-renders while the pointer moves).
async function clickRetry(kit, make, after = 900, tries = 2) {
  for (let i = 1; ; i++) {
    try { await make().waitFor({ timeout: 10000 }); await kit.click(make(), after); return; } catch (e) {
      console.log('  retry click:', e.message.split('\n')[0].slice(0, 120));
      if (i >= tries) break;
      await kit.hold(1500);
    }
  }
  // A button that keeps animating (an attention pulse) never counts as "stable" for the
  // scroll-into-view check: move the pointer to it and click where it is.
  const b = await make().boundingBox();
  if (!b) throw new Error('not on screen: ' + make());
  const x = b.x + b.width / 2, y = b.y + Math.min(b.height / 2, 18);
  await kit.page.mouse.move(x, y, { steps: 18 });
  await kit.hold(250);
  await kit.page.mouse.click(x, y);
  await kit.hold(after);
}

// Operations › Clients › open the client (searches by name).
async function openClient(kit, n, who = client) {
  const p = kit.page;
  await kit.step(n, `Operations › Clients › open ${who.name}`, `Vận hành › Khách hàng › mở ${who.name}`);
  await kit.area('Operations');
  await kit.click(c.sidebar(p, 'Clients'), 2500);
  await kit.type(p.locator('.o_searchview_input'), who.name, 300);
  await p.keyboard.press('Enter');
  await kit.hold(2200);
  await kit.click(p.locator('tr.o_data_row', { hasText: who.name }).locator('td[name=name]').first(), 4000);
}

// From the open client record: New booking → Quick Booking, Clinic Visit, 1 hour, clinic,
// Internal examination, on `days` ahead at the first free time in `times`, optionally with a
// nurse (staff chip + lead). Returns { bk, id, hm, day, url }.
const CLINIC = { type: 'Clinic Visit', typeVi: 'khám tại phòng khám', location: 'Clinic', where: 'at the clinic', whereVi: 'tại phòng khám',
  search: 'Internal examination', code: 'bs_020', product: 'Internal examination', productVi: 'Khám nội khoa' };
const HOME_HCM = { type: 'Home Visit', typeVi: 'khám tại nhà', location: 'Patient Home', where: 'at home', whereVi: 'tại nhà',
  search: 'Medical Examination', code: 'bs_010_tphcm', product: 'Medical Examination & Treatment at home', productVi: 'Khám và điều trị tại nhà' };

async function quickBook(kit, next, { days, times, facility = 'HN_PK_PKGDVU', nurse = null, doctor = null, label = 'the visit', labelVi = 'lượt khám', svc = CLINIC }) {
  const p = kit.page;
  const day = vnDay(days);
  await kit.step(next(), `New booking: ${svc.type}, 1 hour, ${facility}, ${svc.where}`, `Đặt lịch mới: ${svc.typeVi}, 1 giờ, ${facility}, ${svc.whereVi}`);
  await clickRetry(kit, () => p.getByRole('button', { name: /^\s*New booking\s*$/ }).filter({ visible: true }).first(), 4000);
  await p.locator('.qb-form-group').first().waitFor({ timeout: 15000 }).catch(() => {});
  await c.qbFill(kit, { service: svc.type, duration: '1 hour', facility, location: svc.location });

  await kit.step(next(), `Add the service: ${svc.product} (${svc.code})`, `Thêm dịch vụ: ${svc.productVi} (${svc.code})`);
  await kit.click(p.locator('.qb-add-services-btn'), 2000);
  await kit.type(p.locator('.pcd-search-input'), svc.search, 1200);
  await kit.click(p.locator('.pcd-card', { hasText: svc.code }).filter({ hasText: new RegExp(`^\\s*${svc.product.replace(/[&]/g, '.')}`) }).locator('.pcd-add-btn').first(), 800);
  await kit.click(p.locator('.pcd-done-btn'), 1500);

  await kit.step(next(), `Date and time: ${day.mon} ${day.day}, first free slot from ${times[0]}`, `Ngày giờ: ${day.day}/${day.d.getUTCMonth() + 1}, khung giờ trống đầu tiên từ ${times[0]}`);
  await c.qbPickDay(kit, days);
  const hm = await c.qbPickSlot(kit, times);
  await kit.note(`${label[0].toUpperCase() + label.slice(1)}: ${day.mon} ${day.day} at ${hm} (Vietnam time)`, `${labelVi[0].toUpperCase() + labelVi.slice(1)}: ${day.day}/${day.d.getUTCMonth() + 1} lúc ${hm} (giờ Việt Nam)`);
  if (nurse) {
    await kit.step(next(), `Choose the nurse: ${nurse} (assigned staff and lead)`, `Chọn điều dưỡng: ${nurse} (nhân sự được phân công và phụ trách chính)`);
    await kit.click(p.locator('.qb-staff-chip', { hasText: nurse }).first(), 800);
    await kit.select(c.qbGroup(p, 'Lead Staff'), nurse);
  }
  if (doctor) {
    await kit.step(next(), `Choose the doctor: ${doctor}`, `Chọn bác sĩ: ${doctor}`);
    await kit.select(c.qbGroup(p, 'Doctor'), doctor);
  }
  await kit.step(next(), 'Create the booking', 'Tạo lịch hẹn');
  await kit.click(p.locator('.qb-btn-create'), 4500);
  const done = p.locator('.qb-modal-actions').locator('xpath=..');
  await done.waitFor({ timeout: 15000 }).catch(() => {});
  const bk = (((await done.innerText().catch(() => '')) || '').match(/BK\d{3,}/) || [''])[0];
  if (!bk) {
    console.log('  after create:', (await p.locator('.qb-validation-popup, .o_notification').allInnerTexts()).join(' | ').slice(0, 300));
    throw new Error('booking not created');
  }
  await kit.click(p.locator('.qb-modal-confirm'), 4500);
  await p.locator('.ws-hero').first().waitFor({ timeout: 15000 }).catch(() => {});
  const url = p.url();
  const id = Number((url.match(/\/(\d+)(?:\?.*)?$/) || [])[1]) || null;
  return { bk, id, hm, day, url, shown: `${day.mon} ${day.day}, ${h12(hm)}` };
}

// Operations › Bookings › search the booking number › open it (the way a manager reopens one).
async function openBooking(kit, n, bk, en = null, vi = null) {
  const p = kit.page;
  await kit.step(n, en || `Operations › Bookings › open ${bk}`, vi || `Vận hành › Lịch hẹn › mở ${bk}`);
  await kit.area('Operations');
  await kit.click(c.sidebar(p, 'Bookings'), 3000);
  const search = p.locator('.o_searchview_input').filter({ visible: true }).first();
  await kit.type(search, bk, 300);
  await p.keyboard.press('Enter');
  await kit.hold(2000);
  const listBtn = p.locator('.o_switch_view.o_list').filter({ visible: true }).first();
  if (await listBtn.count()) await kit.click(listBtn, 3000);
  const row = p.locator('tr.o_data_row', { hasText: bk }).first();
  await row.waitFor({ timeout: 10000 }).catch(() => {});
  if (await row.count()) {
    await kit.click(row.locator('td').nth(1), 4500);
  } else {
    // a card/kanban queue: click the card that carries the number
    await kit.click(p.getByText(bk, { exact: false }).filter({ visible: true }).first(), 4500);
  }
  await p.locator('.ws-hero').first().waitFor({ timeout: 15000 }).catch(() => {});
}

// Booking screen anchors
const hero = (p) => p.locator('.ws-hero').first();
const statusChip = (p) => p.locator('.ws-hero__state').filter({ visible: true }).first();
const nextCard = (p) => p.locator('.vu-action-card').filter({ visible: true }).first();
const careTeam = (p) => p.locator('.o_form_view').locator('div, section').filter({ has: p.getByText(/^\s*Care team\s*$/i) })
  .filter({ has: p.locator('.o_field_widget[name=lead_staff_id]') }).last();

// Quick actions › View Assignments: the list of this booking's staff assignments.
async function viewAssignments(kit, n, en, vi) {
  const p = kit.page;
  await kit.step(n, en || 'Quick actions › View Assignments', vi || 'Thao tác nhanh › Xem phân công');
  await kit.click(p.locator('button, a, .ws-qa').filter({ hasText: /^\s*View\s*Assignments\s*$/ }).filter({ visible: true }).first(), 4000);
  await p.locator('.o_list_view, .o_list_renderer').first().waitFor({ timeout: 15000 }).catch(() => {});
}

// Nurse app helpers ------------------------------------------------------------------
async function toTablet(kit) { await kit.page.setViewportSize(TABLET); await kit.hold(600); }
async function toDesktop(kit) { await kit.page.setViewportSize(DESKTOP); await kit.hold(600); }

async function openBell(kit) {
  const p = kit.page;
  await kit.click(p.locator('.notif-bell-btn').filter({ visible: true }).first(), 2500);
  await p.locator('.notif-panel').first().waitFor({ timeout: 10000 }).catch(() => {});
}
const offerCard = (p, bk) => p.locator('.notif-card', { hasText: bk }).first();

// Day view: step forward `days` days with the › arrow.
async function pwaGoToDay(kit, days) {
  const p = kit.page;
  const fwd = p.locator('button').filter({ has: p.locator('i.material-icons', { hasText: /^chevron_right$/ }) }).filter({ visible: true }).first();
  for (let i = 0; i < days; i++) await kit.click(fwd, 900);
  await kit.hold(2500);
}

// Visible text of form fields (tags and read-only links have no input value).
async function fieldTexts(p, names) {
  const out = {};
  for (const n of names) out[n] = ((await p.locator(`.o_field_widget[name="${n}"]`).filter({ visible: true }).first().innerText().catch(() => '')) || '').trim();
  return out;
}

module.exports = { CLINIC, HOME_HCM, clickRetry, fieldTexts, users, client, vnDay, h12, openClient, quickBook, openBooking, hero, statusChip, nextCard, careTeam,
  viewAssignments, toTablet, toDesktop, openBell, offerCard, pwaGoToDay, TABLET, DESKTOP };
