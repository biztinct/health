// Client test cases TC-10..TC-17 (Ho Chi Minh City): "re-book live + original invoice"
// (owner decision 5 Nov 2026). Each video: the HCMC Operations Manager (om_hcm) books the case's
// client again with the same services, duration and location on the client price list, at the same
// Vietnam time on the date exactly 5 weeks (35 days) after the client's date (same weekday), with
// no staff. The new booking's Quick Booking price, Pricing tab (each line, its rules, the total),
// quote (VAT 0) and "At a glance" (parking apart) are proved against the workbook row; then the
// ORIGINAL 29 Oct booking's invoice proves the lines, total, VAT 0, no parking line, Posted and the
// amount due. The re-booking is cancelled after the final take, off camera (its draft quote stays).
//
// Gotchas (paid for while preparing TC-10..17, 5 Nov 2026):
// - Quick Booking durations are 30 min / 1 / 2 / 3 / 4 hours only: book the nearest, then type the
//   exact minutes into the booking's Overview › Scheduled Duration (Minutes) and Save. The hero
//   holds a hidden read-only copy of that field: target `[name=scheduled_duration] input`.
// - Evening slots run to 20:30; the calendar opens on the current month (`.qb-cal-nav` last = next).
// - Booking "Driving Distance" (Overview › Location Details) is an input for OM/Owner since the
//   5 Nov deploy: typing a value shows "(set by hand)", logs "Distance changed from X to Y km" and
//   re-prices. TC-12 (Bùi Văn Nam, stored 6 km) is set to the workbook's 0 km on camera. Before the
//   deploy the HCMC clinics sat at lat 16.76 (a 932 km "distance" for Ngô Thanh Mai).
// - Line discount (5 Nov deploy): View Quote card `.hfq-disc__input` (%), then the required
//   `.hfq-disc-reason__input`; Save in the dialog footer. The Pricing tab breakdown then has a
//   Discount column (7 cells: subtotal is the LAST cell) and a "Discounts" table
//   (`[name=quote_line_ids]`). The Quick Booking preview shows the price before discount/distance edits.
// - Parking: Overview › "Additional charges" fold (`.ws-fold-tray__title`) › Parking Charge, Save;
//   "At a glance" then shows "Staff parking" apart from "Price".
// - Pricing tab Qty cell reads "2 Hours" (number + unit): parseFloat it.
// - Original invoice: lines `[name=invoice_line_ids] tr.o_data_row`, totals `[name=tax_totals]`,
//   due `[name=amount_residual]` ("Amount Due"), status bar `[name=state]`.
// - Owner's holiday list: Settings › Master Data › segment "Public Holidays" (`button.vu-segment`).
const fs = require('fs');
const path = require('path');
const c = require('./common');
const a = require('./as_common');
const b = require('./bk_common');

// Final runs write tools/uat-video/tchcm_state.json; practice runs point TCHCM_STATE elsewhere.
const STATE = process.env.TCHCM_STATE ? path.resolve(process.env.TCHCM_STATE) : path.join(__dirname, '..', 'tchcm_state.json');
const load = () => (fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {});
const save = (patch) => fs.writeFileSync(STATE, JSON.stringify({ ...load(), ...patch }, null, 1));

const user = (login, role, role_vi) => ({ login, password: c.pw(login), role, role_vi });
const users = {
  om: user('om_hcm', 'Operations Manager, Ho Chi Minh City', 'Quản lý vận hành TP.HCM'),
  owner: user('uat_owner', 'Owner', 'Chủ sở hữu'),
};

const fmt = (n) => Math.round(n).toLocaleString('en-US');
const fmtVi = (n) => Math.round(n).toLocaleString('en-US').replace(/,/g, '.');
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const FACILITY = 'TPHCM_PK_CSTNVU';
const REASON = 'Client discount 10% (client test data)';
const QB_MIN = { 30: '30 minutes', 60: '1 hour', 120: '2 hours', 180: '3 hours', 240: '4 hours' };

const LOC = {
  clinic: { type: 'Clinic Visit', typeVi: 'khám tại phòng khám', location: 'Clinic', en: 'at the clinic', vi: 'tại phòng khám' },
  home: { type: 'Home Visit', typeVi: 'khám tại nhà', location: 'Patient Home', en: 'at the client’s home', vi: 'tại nhà khách hàng' },
};

// One entry per client case (workbook "Test Results" rows TC-10..TC-17).
// `rules`: the rule names the Pricing tab's "Rules Applied" cell must show (none = "No adjustments").
const CASES = {
  'TC-10': {
    sg: 'SG-B01', client: 'Ngô Thanh Mai', code: '02_0000126', loc: 'clinic', min: 60, km: 0,
    orig: { bk: 'BK3841', when: 'Oct 14, 10:00 AM', day: 'Wed 14 Oct', dayVi: 'thứ Tư 14/10', inv: 'INV/2026/00009' },
    when: { month: 10, day: 18, date: 'Wed 18 Nov', dateVi: 'thứ Tư 18/11', hm: '10:00' },
    conds: ['Clinic Visit'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i, /Distance/i],
    lines: [{ code: 'bs_010_tphcm', wb: 'bs_010', q: 'Medical Examination', name: 'Medical Examination & Treatment at home', qty: 1, total: 200000,
      rules: [],
      calc: '1 × base 200,000, no adjustment (weekday, in hours, at the clinic)', calc_vi: '1 × giá gốc 200.000, không điều chỉnh (ngày thường, trong giờ, tại phòng khám)' }],
    total: 200000, parking: 0, due: 0,
  },
  'TC-11': {
    sg: 'SG-B02', client: 'Bùi Văn Nam', code: '02_0000226', loc: 'home', min: 90, km: 6,
    orig: { bk: 'BK3842', when: 'Oct 15, 9:00 AM', day: 'Thu 15 Oct', dayVi: 'thứ Năm 15/10', inv: 'INV/2026/00010' },
    when: { month: 10, day: 19, date: 'Thu 19 Nov', dateVi: 'thứ Năm 19/11', hm: '09:00' },
    conds: ['Home Visit', 'Distance: 6.0 km'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i],
    lines: [
      { code: 'bs_015_tphcm', wb: 'bs_015', q: 'in the clinic', name: 'Medical Examination & Treatment in the clinic', qty: 1, total: 600000,
        rules: [],
        calc: '1 × base 600,000, no adjustment (6 km: this service’s distance rule starts at 8 km)', calc_vi: '1 × giá gốc 600.000, không điều chỉnh (6 km: quy tắc khoảng cách của dịch vụ này bắt đầu từ 8 km)' },
      { code: 'đd_290_tphcm', wb: 'đd_290', q: 'Glucose', name: 'Capillary Blood Glucose Test', qty: 1, total: 50000,
        rules: [],
        calc: '1 × base 50,000, no adjustment', calc_vi: '1 × giá gốc 50.000, không điều chỉnh' },
    ],
    total: 650000, parking: 100000, due: 0,
  },
  'TC-12': {
    sg: 'SG-B03', client: 'Bùi Văn Nam', code: '02_0000226', loc: 'home', min: 60, km: 0,
    orig: { bk: 'BK3843', when: 'Oct 24, 10:00 AM', day: 'Sat 24 Oct', dayVi: 'thứ Bảy 24/10', inv: 'INV/2026/00011' },
    when: { month: 10, day: 28, date: 'Sat 28 Nov', dateVi: 'thứ Bảy 28/11', hm: '10:00' },
    conds: ['Home Visit', 'Weekend'], notConds: [/Holiday/i, /Distance/i],
    qbKm: 6, qbConds: ['Home Visit', 'Distance: 6.0 km', 'Weekend'], qbNot: [/Holiday/i],
    lines: [{ code: 'bs_015_tphcm', wb: 'bs_015', q: 'in the clinic', name: 'Medical Examination & Treatment in the clinic', qty: 1, total: 740000, disc: 10, preDisc: 800000,
      rules: [/after hours or weekend[^\n]*\+200,000/i],
      calc: '600,000 + 200,000 Saturday (after hours or weekend) − 10% of the base 600,000', calc_vi: '600.000 + 200.000 thứ Bảy (ngoài giờ hoặc cuối tuần) − 10% của giá gốc 600.000' }],
    total: 740000, preDisc: 800000, parking: 0, due: 0,
  },
  'TC-13': {
    sg: 'SG-B04', client: 'Đặng Thị Quỳnh', code: '02_0000326', loc: 'home', min: 30, km: 0,
    orig: { bk: 'BK3844', when: 'Oct 16, 2:00 PM', day: 'Fri 16 Oct', dayVi: 'thứ Sáu 16/10', inv: 'INV/2026/00012' },
    when: { month: 10, day: 20, date: 'Fri 20 Nov', dateVi: 'thứ Sáu 20/11', hm: '14:00' },
    conds: ['Home Visit'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i, /Distance/i],
    lines: [{ code: 'đd_070_tphcm', wb: 'đd_070', q: 'Intramuscular', name: 'Intramuscular, intradermal, subcutaneous injection', qty: 2, total: 210000,
      rules: [/Is service at home[^\n]*\+70,000/, /Subsequent units[^\n]*50,000/],
      calc: '90,000 + 50,000 (injection 2) + 70,000 at home', calc_vi: '90.000 + 50.000 (mũi 2) + 70.000 tại nhà' }],
    total: 210000, parking: 0, due: 0,
  },
  'TC-14': {
    sg: 'SG-B05', client: 'Đặng Thị Quỳnh', code: '02_0000326', loc: 'home', min: 720, km: 0,
    orig: { bk: 'BK3845', when: 'Oct 27, 7:00 PM', day: 'Tue 27 Oct', dayVi: 'thứ Ba 27/10', inv: 'INV/2026/00013' },
    when: { month: 11, day: 1, date: 'Tue 1 Dec', dateVi: 'thứ Ba 1/12', hm: '19:00' },
    conds: ['Home Visit', 'After Hours'], notConds: [/Weekend/i, /Holiday/i, /Distance/i],
    lines: [{ code: 'đd_270_tphcm', wb: 'đd_270', q: 'Nighttime', name: 'Personal Care 12h Nighttime', qty: 1, total: 1080000, disc: 10, preDisc: 1200000,
      rules: [],
      calc: 'package price 1,200,000, no adjustment − 10% of the base 1,200,000', calc_vi: 'giá gói 1.200.000, không điều chỉnh − 10% của giá gốc 1.200.000' }],
    total: 1080000, preDisc: 1200000, parking: 100000, due: 1080000,
  },
  'TC-15': {
    sg: 'SG-B06', client: 'Lý Minh Tâm', code: '02_0000426', loc: 'home', min: 150, km: 6, holiday: true,
    orig: { bk: 'BK3846', when: 'Oct 19, 10:00 AM', day: 'Mon 19 Oct', dayVi: 'thứ Hai 19/10', inv: 'INV/2026/00014' },
    when: { month: 10, day: 23, date: 'Mon 23 Nov', dateVi: 'thứ Hai 23/11', hm: '10:00' },
    conds: ['Home Visit', 'Distance: 6.0 km', 'Holiday (Public)'], notConds: [/After Hours/i, /Weekend/i],
    lines: [
      { code: 'đd_060_tphcm', wb: 'đd_060', q: 'Infusion over time', name: 'Infusion over time <= 3 hours', qty: 2, total: 2100000,
        rules: [/Is service at home[^\n]*\+50,000/, /Additional IV bottles[^\n]*\+150,000/, /Is public holiday[^\n]*×3/],
        calc: '(2 × 250,000 + 50,000 at home + 150,000 bottle 2) × 3 holiday', calc_vi: '(2 × 250.000 + 50.000 tại nhà + 150.000 chai 2) × 3 ngày lễ' },
      { code: 'đd_120_tphcm', wb: 'đd_120', q: 'Bladder Wash', name: 'Bladder Wash', qty: 1, total: 600000, atVisit: true,
        rules: [/Is service at home[^\n]*\+100,000/, /another service this visit[^\n]*200,000/, /Is public holiday[^\n]*×3/],
        calc: '(250,000 + 200,000 at home with another service) × 3 holiday', calc_vi: '(250.000 + 200.000 tại nhà kèm dịch vụ khác) × 3 ngày lễ' },
    ],
    total: 2700000, parking: 100000, due: 0,
  },
  'TC-16': {
    sg: 'SG-B07', client: 'Trịnh Văn Vinh', code: '02_0000526', loc: 'clinic', min: 30, km: 0,
    orig: { bk: 'BK3847', when: 'Oct 21, 8:30 PM', day: 'Wed 21 Oct', dayVi: 'thứ Tư 21/10', inv: 'INV/2026/00015' },
    when: { month: 10, day: 25, date: 'Wed 25 Nov', dateVi: 'thứ Tư 25/11', hm: '20:30' },
    conds: ['Clinic Visit', 'After Hours'], notConds: [/Weekend/i, /Holiday/i, /Distance/i],
    lines: [{ code: 'bs_020_tphcm', wb: 'bs_020', q: 'Telemedicine', name: 'Telemedicine Consult', qty: 1, total: 500000,
      rules: [/after hours or weekend[^\n]*\+200,000/i, /between 8 pm and 11:59 pm[^\n]*\+100,000/i],
      calc: '200,000 + 200,000 after hours + 100,000 between 8 pm and midnight', calc_vi: '200.000 + 200.000 ngoài giờ + 100.000 từ 20:00 đến 24:00' }],
    total: 500000, parking: 0, due: 0,
  },
  'TC-17': {
    sg: 'SG-B08', client: 'Hồ Thị Xuân', code: '02_0000626', loc: 'home', min: 60, km: 6,
    orig: { bk: 'BK3848', when: 'Oct 29, 3:00 PM', day: 'Thu 29 Oct', dayVi: 'thứ Năm 29/10', inv: 'INV/2026/00016' },
    when: { month: 11, day: 3, date: 'Thu 3 Dec', dateVi: 'thứ Năm 3/12', hm: '15:00' },
    conds: ['Home Visit', 'Distance: 6.0 km'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i],
    lines: [
      { code: 'đd_020_tphcm', wb: 'đd_020', q: 'wound dressing', name: 'Change wound dressing', qty: 2, total: 250000, disc: 10,
        rules: [/Is service at home[^\n]*\+80,000/, /Subsequent units[^\n]*50,000/],
        calc: '150,000 + 50,000 (wound 2) + 80,000 at home − 10% of the base 300,000 (6 km: no rule below 8 km)', calc_vi: '150.000 + 50.000 (vết 2) + 80.000 tại nhà − 10% của giá gốc 300.000 (6 km: không có quy tắc dưới 8 km)' },
      { code: 'đd_290_tphcm', wb: 'đd_290', q: 'Glucose', name: 'Capillary Blood Glucose Test', qty: 1, total: 45000, disc: 10, atVisit: true,
        rules: [],
        calc: 'base 50,000 − 10%', calc_vi: 'giá gốc 50.000 − 10%' },
    ],
    total: 295000, preDisc: 330000, parking: 0, due: 0,
  },
};

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const h12 = (hm) => { const [h, m] = hm.split(':').map(Number); return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`; };
const shown = (k) => `${MON[k.when.month]} ${k.when.day}, ${h12(k.when.hm)}`;                        // hero: "Nov 18, 10:00 AM"
const qbShown = (k) => `${String(k.when.day).padStart(2, '0')} ${MON[k.when.month]} 2026, ${k.when.hm}`; // QB: "18 Nov 2026, 10:00"
const durEn = (m) => (m % 60 ? `${m} minutes` : `${m / 60} hour${m > 60 ? 's' : ''}`);
const durVi = (m) => (m % 60 ? `${m} phút` : `${m / 60} giờ`);

// A proof whose Vietnamese label is registered at run time.
async function P(kit, locs, en, vi, expect, hold = 3000) {
  kit._proofVi[en] = vi;
  return kit.proof(locs, en, expect, hold);
}

const meta = (id, k, extra = {}) => ({
  id, short: 're-price + invoice',
  title: `${k.client} price and invoice match the workbook`,
  title_vi: `${k.client}: giá và hóa đơn khớp bảng tính`,
  criterion: `Client test case ${id} (${k.sg}), ${k.client}, Ho Chi Minh City: with the client price list and the appointment conditions, every service line, the total, VAT 0 and parking (staff reimbursement, outside the client total) match the client workbook on the quotation and on the invoice, and the amount due is right.`,
  data: `Client ${k.client} (${k.code}), price list “Client UAT 20261013 V01.01 (VND)”. Live re-booking: ${k.when.date} 2026 at ${k.when.hm} (the client’s ${k.orig.day} ${k.orig.when.split(', ')[1]}, five weeks later, same weekday and time), ${durEn(k.min)}, ${LOC[k.loc].location}, no staff — price check only, cancelled after the recording. Invoice: original booking ${k.orig.bk} → ${k.orig.inv}. All data fictional.`,
  ...users.om, ...extra,
});

// Re-book the case live, prove the price; returns { bk, id, quote }.
async function rebook(kit, next, id, k) {
  const p = kit.page;
  const L = LOC[k.loc];
  const qbDur = QB_MIN[k.min] || (k.min < 120 ? '1 hour' : k.min < 180 ? '2 hours' : '3 hours');

  await a.openClient(kit, next(), { name: k.client });
  await kit.step(next(), `New booking: ${L.type}, ${FACILITY}, location ${L.location}${QB_MIN[k.min] ? `, ${qbDur}` : ''}`,
    `Đặt lịch mới: ${L.typeVi}, ${FACILITY}, địa điểm ${L.location}${QB_MIN[k.min] ? `, ${durVi(k.min)}` : ''}`);
  await a.clickRetry(kit, () => p.getByRole('button', { name: /^\s*New booking\s*$/ }).filter({ visible: true }).first(), 4000);
  await p.locator('.qb-form-group').first().waitFor({ timeout: 15000 });
  if (!QB_MIN[k.min]) {
    await kit.note(`The booking form offers 30 min to 4 h steps: ${qbDur} now, the exact ${k.min} minutes are set on the booking next`,
      `Biểu mẫu đặt lịch có các mức 30 phút đến 4 giờ: chọn ${durVi(Number(qbDur[0]) * 60)} trước, ${k.min} phút chính xác đặt trên lịch hẹn sau`);
  }
  await c.qbFill(kit, { service: L.type, duration: qbDur, facility: FACILITY, location: L.location });

  const svc = k.lines.map((l) => `${l.code} × ${l.qty}`).join(', ');
  await kit.step(next(), `Services as in the workbook: ${svc}`, `Dịch vụ như bảng tính: ${svc}`);
  if (k.lines.some((l) => l.atVisit)) {
    const l = k.lines.find((x) => x.atVisit);
    await kit.note(`${l.code} is the item the nurse adds at the visit: it is entered here so the whole price is shown (adding at the visit itself is shown in BK-03)`,
      `${l.code} là mục điều dưỡng thêm tại lượt khám: nhập ở đây để thấy toàn bộ giá (việc thêm tại lượt khám được trình bày trong BK-03)`);
  }
  await kit.click(p.locator('.qb-add-services-btn'), 2000);
  for (const l of k.lines) {
    await kit.type(p.locator('.pcd-search-input'), l.q, 1500);
    const card = p.locator('.pcd-card', { hasText: l.code }).first();
    await kit.click(card.locator('.pcd-add-btn').first(), 900);
    for (let i = 1; i < l.qty; i++) await kit.click(card.locator('.pcd-qty-btn').last(), 700);
  }
  await kit.click(p.locator('.pcd-done-btn'), 2000);

  await kit.step(next(), `Date: the client’s ${k.orig.day}, ${k.when.hm} → five weeks later, same weekday and time: ${k.when.date}, ${k.when.hm}`,
    `Ngày: ngày của khách ${k.orig.dayVi}, ${k.when.hm} → năm tuần sau, cùng thứ và giờ: ${k.when.dateVi}, ${k.when.hm}`);
  const now = new Date(Date.now() + 7 * 3600e3);
  for (let m = now.getUTCMonth(); m < k.when.month; m++) await kit.click(p.locator('.qb-cal-nav').last(), 900);
  await kit.click(p.locator('.qb-cal-day:not(.qb-cal-day--disabled):not(.qb-cal-day--empty)')
    .filter({ hasText: new RegExp(`^\\s*${k.when.day}\\s*$`) }).first(), 2200);
  const hr = Number(k.when.hm.slice(0, 2));
  const tod = p.locator('.qb-tod-card', { hasText: hr < 12 ? 'Morning' : hr < 17 ? 'Afternoon' : 'Evening' }).first();
  if (!(await tod.getAttribute('class')).includes('active')) await kit.click(tod, 1500);
  const slot = p.locator('.qb-slot-grid button').filter({ hasText: new RegExp(`^\\s*${k.when.hm}`) }).first();
  if (!(await slot.count()) || !(await slot.isEnabled()) || await slot.locator('.fa-lock, .fa-exclamation-triangle').count()) {
    throw new Error(`slot ${k.when.hm} on ${k.when.date} is not free`);
  }
  await kit.click(slot, 2500);

  const summary = p.locator('.qb-summary-box').first();
  await P(kit, summary, `Booking: ${L.type}, ${qbShown(k)}, ${L.location}, ${FACILITY}`, `Lịch hẹn: ${L.typeVi}, ${qbShown(k)}, ${L.location}, ${FACILITY}`,
    (t) => t.includes(L.type) && t.includes(qbShown(k)) && t.includes(L.location) && t.includes(FACILITY), 2600);
  const preview = p.locator('.qb-pt-footer').first().locator('xpath=..');
  const qbConds = k.qbConds || k.conds, qbNot = k.qbNot || k.notConds, qbTotal = k.preDisc || k.total;
  const before = [k.km !== (k.qbKm ?? k.km) ? `before the distance is set to ${k.km} km` : '', k.preDisc ? 'before the client discount' : ''].filter(Boolean);
  const beforeVi = [k.km !== (k.qbKm ?? k.km) ? `trước khi đặt khoảng cách ${k.km} km` : '', k.preDisc ? 'trước chiết khấu của khách' : ''].filter(Boolean);
  await P(kit, preview, `Price shown while booking: ${fmt(qbTotal)} ₫ (${qbConds.join(', ')})${before.length ? ', ' + before.join(' and ') : ''}`,
    `Giá hiển thị khi đặt lịch: ${fmtVi(qbTotal)} ₫ (${qbConds.join(', ')})${beforeVi.length ? ', ' + beforeVi.join(' và ') : ''}`,
    (t) => b.has(t.match(/Total\s*([\d.,]+)/) ? ' ' + t.match(/Total\s*([\d.,]+)/)[1] : '', qbTotal) && qbConds.every((x) => t.includes(x))
      && qbNot.every((re) => !re.test(t.split('APPLIED CONDITIONS')[1] || '')), 3000);
  await kit.step(next(), 'Create the booking (no staff: this booking only re-runs the price)', 'Tạo lịch hẹn (không có nhân sự: lịch này chỉ để tính lại giá)');
  await kit.click(p.locator('.qb-btn-create'), 4500);
  const done = p.locator('.qb-modal-card').first();
  await done.waitFor({ timeout: 20000 }).catch(() => {});
  const bk = (((await done.innerText().catch(() => '')) || '').match(/BK\d{3,}/) || [''])[0];
  if (!bk) {
    console.log('  after create:', (await p.locator('.qb-validation-popup, .o_notification').allInnerTexts()).join(' | ').slice(0, 300));
    throw new Error('booking not created');
  }
  await P(kit, [done.locator('.qb-modal-header'), done.locator('.qb-modal-info-grid')], `Booking ${bk} created for ${k.client}`, `Đã tạo lịch hẹn ${bk} cho ${k.client}`,
    (t) => t.includes(bk) && t.includes(k.client) && t.includes(qbShown(k)), 2400);
  await kit.click(p.locator('.qb-modal-confirm'), 4500);
  await p.locator('.ws-hero').first().waitFor({ timeout: 20000 });
  const recId = Number((p.url().match(/\/(\d+)(?:\?.*)?$/) || [])[1]) || null;
  save({ [id]: { bk, id: recId, url: p.url(), at: new Date().toISOString() } });

  const dist = p.locator('.o_field_widget[name=travel_distance] input').filter({ visible: true }).first();
  const seeded = Number(await dist.inputValue().catch(() => 'NaN'));
  const setKm = seeded !== k.km;
  if (!QB_MIN[k.min] || k.parking || setKm) {
    const parts = [
      [!QB_MIN[k.min], `duration ${k.min} minutes`, `thời lượng ${k.min} phút`],
      [setKm, `driving distance ${k.km} km (the booking took the client’s stored ${seeded} km)`, `khoảng cách ${k.km} km (lịch hẹn lấy ${seeded} km đã lưu của khách)`],
      [k.parking, `staff parking ${fmt(k.parking)} ₫ (Additional charges)`, `phí gửi xe cho nhân viên ${fmtVi(k.parking)} ₫ (Phụ phí)`],
    ].filter((x) => x[0]);
    await kit.step(next(), `As in the workbook: ${parts.map((x) => x[1]).join('; ')}; Save`, `Như bảng tính: ${parts.map((x) => x[2]).join('; ')}; Lưu`);
    if (!QB_MIN[k.min]) await kit.type(p.locator('.o_field_widget[name=scheduled_duration] input').filter({ visible: true }).first(), String(k.min), 700);
    if (setKm) await kit.type(dist, String(k.km), 700);
    if (k.parking) {
      await kit.click(p.locator('.ws-fold-tray__title', { hasText: 'Additional charges' }).first(), 1500);
      const pk = p.locator('.o_field_widget[name=parking_charge] input').filter({ visible: true }).first();
      await kit.type(pk, String(k.parking), 700);
    }
    await kit.click(c.saveBtn(p), 3500);
  }
  const distWrap = p.locator('.o_field_widget[name=travel_distance]').filter({ visible: true }).first().locator('xpath=..');
  await P(kit, [p.locator('label').filter({ hasText: /^\s*Driving Distance/ }).filter({ visible: true }).first(), distWrap],
    `Driving distance ${k.km} km = workbook${setKm ? ' (set by hand)' : ''}${k.loc === 'clinic' ? ' (clinic visit: not used for the price)' : ''}`,
    `Khoảng cách ${k.km} km = bảng tính${setKm ? ' (nhập tay)' : ''}${k.loc === 'clinic' ? ' (khám tại phòng khám: không dùng để tính giá)' : ''}`,
    async (t) => Number(await dist.inputValue()) === k.km && (!setKm || /set by hand/i.test(t)), 2600);
  const hero = p.locator('.ws-hero').first();
  await P(kit, hero, `${bk}: ${shown(k)}, ${k.min} min, ${L.type}`, `${bk}: ${shown(k)}, ${k.min} phút, ${L.typeVi}`,
    (t) => t.includes(bk) && t.includes(shown(k)) && new RegExp(`\\b${k.min}\\s*min`).test(t) && t.includes(L.type), 2600);

  // ---- the quote: client discounts (if any), VAT 0 and the total
  const disc = k.lines.filter((l) => l.disc);
  if (disc.length) {
    await kit.step(next(), `Quick actions › View Quote: client discount ${disc[0].disc}% on ${disc.map((l) => l.code).join(' and ')} with its reason; Save`,
      `Thao tác nhanh › Xem báo giá: chiết khấu ${disc[0].disc}% cho ${disc.map((l) => l.code).join(' và ')} kèm lý do; Lưu`);
  } else {
    await kit.step(next(), 'Quick actions › View Quote: VAT and total', 'Thao tác nhanh › Xem báo giá: VAT và tổng');
  }
  await p.evaluate(() => window.scrollTo(0, 0));
  await kit.click(p.locator('button, a').filter({ hasText: /^\s*View Quote\s*$/ }).filter({ visible: true }).first(), 4000);
  const panel = p.locator('.hfq-panel').filter({ visible: true }).first();
  await panel.waitFor({ timeout: 15000 });
  const quote = ((await p.locator('.modal-content .o_field_widget[name=name]').first().innerText().catch(() => '')) || '').trim();
  save({ [id]: { ...load()[id], quote } });
  for (const l of disc) {
    const card = panel.locator('.hfq-card', { hasText: l.code }).first();
    await kit.type(card.locator('.hfq-disc__input').first(), String(l.disc), 900);
    await p.keyboard.press('Tab');
    await kit.hold(900);
    await kit.type(card.locator('.hfq-disc-reason__input').first(), REASON, 700);
    await p.keyboard.press('Tab');
    await kit.hold(1200);
    await P(kit, card, `${l.code}: discount ${l.disc}% with reason, line ${fmt(l.total)} ₫ = workbook`, `${l.code}: chiết khấu ${l.disc}% kèm lý do, dòng ${fmtVi(l.total)} ₫ = bảng tính`,
      async (t) => Number(await card.locator('.hfq-disc__input').inputValue()) === l.disc && (await card.locator('.hfq-disc-reason__input').inputValue()) === REASON
        && b.has(' ' + ((await card.locator('.hfq-subtotal').first().innerText().catch(() => '')) || ''), l.total), 2800);
  }
  const totals = panel.locator('.hfq-totals').first();
  await P(kit, totals, `Quote ${quote}: taxes 0 ₫ (VAT 0), total ${fmt(k.total)} ₫`, `Báo giá ${quote}: thuế 0 ₫ (VAT 0), tổng ${fmtVi(k.total)} ₫`, (t) => {
    const g = (re) => ' ' + ((t.match(re) || [])[1] || '');
    return /^\s*0\s*đ?\s*$/.test((t.match(/Taxes\s*([^\n]*?đ)/) || [])[1] || 'x') && b.has(g(/Untaxed\s*([\d.,]+)/), k.total) && b.has(g(/Total\s*([\d.,]+)/), k.total);
  }, 3000);
  if (disc.length) {
    await kit.click(p.locator('.modal-content .modal-footer button, .modal-content footer button').filter({ hasText: /^\s*Save\s*$/ }).filter({ visible: true }).first(), 4000);
    await p.locator('.hfq-panel').filter({ visible: true }).first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  } else {
    await kit.click(p.locator('.modal-content button').filter({ hasText: /^\s*Discard\s*$/ }).filter({ visible: true }).first(), 2000);
  }
  if (await p.locator('.hfq-panel').filter({ visible: true }).count()) await kit.click(p.locator('.modal-header .btn-close').filter({ visible: true }).first(), 1500);

  // ---- Pricing tab: every line, its rules (and discount), then the total
  await kit.step(next(), 'Pricing tab: each line, the rules applied and the total, against the workbook', 'Thẻ Giá: từng dòng, quy tắc áp dụng và tổng, so với bảng tính');
  await b.tab(kit, 'Pricing');
  const wrap = p.locator('.o_field_widget[name=pricing_breakdown_html]').filter({ visible: true }).first();
  const strip = wrap.locator('div[style*="f0f4ff"]').first();
  await strip.waitFor({ timeout: 15000 });
  const condsEn = k.conds.join(', ') + (k.loc === 'clinic' ? ' (nobody travels: no distance charge)' : k.km ? '' : ' (0 km: no distance)');
  const condsVi = k.conds.join(', ') + (k.loc === 'clinic' ? ' (không di chuyển: không tính khoảng cách)' : k.km ? '' : ' (0 km: không có khoảng cách)');
  await P(kit, strip, `Conditions: ${condsEn}`, `Điều kiện: ${condsVi}`,
    (t) => k.conds.every((x) => t.includes(x)) && k.notConds.every((re) => !re.test(t)), 2600);
  const head = await wrap.locator('thead th, tr').first().innerText().catch(() => '');
  for (const l of k.lines) {
    await kit.note(`Workbook ${l.wb} × ${l.qty}: ${l.calc} = ${fmt(l.total)} ₫`, `Bảng tính ${l.wb} × ${l.qty}: ${l.calc_vi} = ${fmtVi(l.total)} ₫`);
    const row = wrap.locator('tbody tr').filter({ hasText: l.code }).first();
    const rulesTxt = (l.rules.length ? 'rules as in the workbook' : 'no adjustments') + (l.disc ? `, discount ${l.disc}%` : '');
    const rulesVi = (l.rules.length ? 'quy tắc như bảng tính' : 'không điều chỉnh') + (l.disc ? `, chiết khấu ${l.disc}%` : '');
    await P(kit, row, `${l.code} × ${l.qty}: ${rulesTxt}, ${fmt(l.total)} ₫ = workbook`, `${l.code} × ${l.qty}: ${rulesVi}, ${fmtVi(l.total)} ₫ = bảng tính`, async () => {
      const cells = await row.locator('td').allInnerTexts();
      const hasDiscCol = cells.length >= 7;
      const sub = cells[cells.length - 1];
      if (cells.length < 6 || !cells[0].includes(l.name) || parseFloat(cells[4]) !== l.qty || !b.has(' ' + sub, l.total)) return false;
      if (l.disc && !(hasDiscCol && parseFloat(cells[5]) === l.disc)) return false;
      if (!l.disc && hasDiscCol && parseFloat(cells[5]) > 0) return false;
      return l.rules.length ? l.rules.every((re) => re.test(cells[2])) : /No adjustments/i.test(cells[2]);
    }, 3400);
  }
  const totalRow = wrap.locator('tr').filter({ hasText: /^\s*Total/ }).last();
  await P(kit, totalRow, `Total ${fmt(k.total)} ₫ = workbook`, `Tổng ${fmtVi(k.total)} ₫ = bảng tính`, (t) => b.has(t, k.total), 2600);
  if (disc.length) {
    const dRows = p.locator('.o_field_widget[name=quote_line_ids] tr.o_data_row').filter({ visible: true });
    await dRows.first().waitFor({ timeout: 10000 });
    const boxes = [];
    for (const l of disc) boxes.push(dRows.filter({ hasText: l.code }).first());
    await P(kit, boxes, `Discounts table: ${disc.map((l) => `${l.code} ${l.disc}%`).join(', ')}, reason “${REASON}”`, `Bảng chiết khấu: ${disc.map((l) => `${l.code} ${l.disc}%`).join(', ')}, lý do “${REASON}”`,
      async () => {
        for (const l of disc) {
          const r = await dRows.filter({ hasText: l.code }).first().innerText();
          if (!new RegExp(`\\b${l.disc}\\.00\\b`).test(r) || !r.includes(REASON) || !b.has(r, l.total)) return false;
        }
        return true;
      }, 3200);
  }

  // ---- parking: a staff charge, outside the client price
  await b.tab(kit, 'Overview');
  await p.evaluate(() => window.scrollTo(0, 0));
  const price = c.glanceRow(p, 'Price').first();
  if (k.parking) {
    await kit.step(next(), `Parking ${fmt(k.parking)} ₫ is the nurse’s reimbursement: shown apart from the client price`, `Phí gửi xe ${fmtVi(k.parking)} ₫ là khoản hoàn cho điều dưỡng: tách riêng khỏi giá của khách`);
    const park = c.glanceRow(p, 'Staff parking').first();
    await P(kit, [price, park], `At a glance: price ${fmt(k.total)} ₫, staff parking ${fmt(k.parking)} ₫ apart`, `Tổng quan: giá ${fmtVi(k.total)} ₫, phí gửi xe ${fmtVi(k.parking)} ₫ tách riêng`,
      async () => b.has(' ' + (await price.innerText()).replace(/Price/, ''), k.total) && b.has(' ' + (await park.innerText()).replace(/Staff parking/, ''), k.parking), 3000);
  } else {
    await P(kit, p.locator('.ws-panel--glance').first(), `At a glance: price ${fmt(k.total)} ₫, no parking (0 ₫)`, `Tổng quan: giá ${fmtVi(k.total)} ₫, không có phí gửi xe (0 ₫)`,
      async (t) => b.has(' ' + (await price.innerText()).replace(/Price/, ''), k.total) && !/parking/i.test(t), 2600);
  }
  const st = load()[id];
  return { bk, id: recId, quote: st.quote };
}

// Original 29 Oct booking → its invoice: lines, VAT 0, total, no parking, Posted, amount due.
async function originalInvoice(kit, next, k) {
  const p = kit.page;
  await kit.step(next(), `The original booking from the client’s test: Operations › Bookings › ${k.orig.bk}`, `Lịch hẹn gốc trong kiểm thử của khách: Vận hành › Lịch hẹn › ${k.orig.bk}`);
  await b.openBooking(kit, k.orig.bk, true);
  await P(kit, p.locator('.ws-hero').first(), `${k.orig.bk}: ${k.orig.when}, ${k.min} min, Completed`, `${k.orig.bk}: ${k.orig.when}, ${k.min} phút, Hoàn thành`,
    (t) => t.includes(k.orig.bk) && t.includes(k.client) && t.includes(k.orig.when) && new RegExp(`\\b${k.min}\\s*min`).test(t) && /Completed/.test(t), 2600);

  await kit.step(next(), `Quick actions › View Invoice › ${k.orig.inv}`, `Thao tác nhanh › Xem hóa đơn › ${k.orig.inv}`);
  await kit.click(p.getByRole('button', { name: /View Invoice/ }).first(), 3500);
  const invRow = p.locator('tr.o_data_row', { hasText: k.orig.inv }).first();
  await invRow.waitFor({ timeout: 15000 });
  await kit.click(invRow.locator('td').nth(1), 4500);
  const lines = p.locator('.o_field_widget[name=invoice_line_ids] tr.o_data_row');
  await lines.first().waitFor({ timeout: 15000 });
  const state = p.locator('.o_field_widget[name=state] .o_arrow_button_current, .o_field_widget[name=state] button[aria-current]').first();
  await P(kit, [p.locator('.o_field_widget[name=name]').filter({ visible: true }).first(), state], `${k.orig.inv}: Posted`, `${k.orig.inv}: đã ghi sổ`,
    async (t) => t.includes(k.orig.inv) && /Posted/i.test(await state.innerText()), 2400);
  const boxes = [];
  for (let i = 0; i < k.lines.length; i++) boxes.push(lines.nth(i));
  await P(kit, boxes, `Invoice lines: ${k.lines.map((l) => `${l.wb} × ${l.qty} = ${fmt(l.total)} ₫`).join('; ')}; no tax, no parking line`,
    `Dòng hóa đơn: ${k.lines.map((l) => `${l.wb} × ${l.qty} = ${fmtVi(l.total)} ₫`).join('; ')}; không thuế, không có phí gửi xe`, async () => {
      const rows = await lines.allInnerTexts();
      const taxes = await lines.locator('td[name=tax_ids]').allInnerTexts();
      return rows.length === k.lines.length
        && k.lines.every((l) => rows.some((r) => r.includes(l.code) && b.has(r, l.total) && new RegExp(`\\b${l.qty}\\.00\\b`).test(r)))
        && taxes.every((x) => !x.trim()) && !/parking/i.test(rows.join(' '));
    }, 3400);
  const totals = p.locator('.o_field_widget[name=tax_totals]').first();
  const due = p.locator('.o_field_widget[name=amount_residual]').filter({ visible: true }).first();
  const dueLabel = p.locator('label').filter({ hasText: /^\s*Amount Due\s*$/ }).filter({ visible: true }).first();
  await P(kit, [totals, dueLabel, due], `Untaxed ${fmt(k.total)} ₫ = total ${fmt(k.total)} ₫ (VAT 0); amount due ${fmt(k.due)} ₫ = workbook final due`,
    `Chưa thuế ${fmtVi(k.total)} ₫ = tổng ${fmtVi(k.total)} ₫ (VAT 0); còn phải thu ${fmtVi(k.due)} ₫ = bảng tính`, async () => {
      const t = await totals.innerText();
      const untaxed = (t.match(/Untaxed Amount:?\s*([\d.,]+)/) || [])[1] || '';
      const total = (t.match(/(?:^|\s)Total:?\s*([\d.,]+)/) || [])[1] || '';
      const d = (await due.innerText()).trim();
      return b.has(' ' + untaxed, k.total) && b.has(' ' + total, k.total) && !/Tax\s*\d|VAT\s*\d/i.test(t.replace(/Untaxed Amount/, ''))
        && Number(d.replace(/[^\d]/g, '')) === k.due;
    }, 3400);
}

async function runCase(kit, id) {
  const k = CASES[id];
  let n = 1;
  const next = () => ++n;
  if (k.holiday) {
    await kit.switchUser(1, users.owner, false);
    n = 1;
    await kit.step(next(), 'Settings › Master Data › Public Holidays: the test holiday used by this case', 'Cài đặt › Dữ liệu gốc › Ngày lễ: ngày lễ thử nghiệm của ca này');
    await showHolidayList(kit);
    await kit.switchUser(next(), users.om, false);
  } else {
    await kit.login();
  }
  const r = await rebook(kit, next, id, k);
  kit.records['Re-booking (price check only, cancelled after this recording)'] = `${r.bk}, quote ${r.quote}, ${k.when.date} ${k.when.hm}`;
  if (process.env.TCHCM_STOP === 'price') return;
  await originalInvoice(kit, next, k);
  kit.records['Original (read only)'] = `${k.orig.bk} → ${k.orig.inv}`;
}

// The holiday list itself (signed in as the Owner).
async function showHolidayList(kit) {
  const p = kit.page;
  await kit.area('Settings');
  await kit.click(c.sidebar(p, 'Master Data'), 3000);
  await kit.click(p.locator('button.vu-segment').filter({ hasText: /^\s*Public Holidays\s*$/ }).first(), 3000);
  await kit.type(p.locator('.o_searchview_input').filter({ visible: true }).first(), 'fictional', 400);
  await p.keyboard.press('Enter');
  const row19 = p.locator('tr.o_data_row', { hasText: '19 Oct 2026' }).first();
  const row23 = p.locator('tr.o_data_row', { hasText: '23 Nov 2026' }).first();
  await row23.waitFor({ timeout: 15000 });
  await kit.hold(1500);
  await P(kit, [row19, row23], 'Test holiday 19 Oct (the client’s date) and its re-run on Mon 23 Nov: price × 3',
    'Ngày lễ thử nghiệm 19/10 (ngày của khách) và bản chạy lại thứ Hai 23/11: giá × 3',
    async () => {
      const r19 = await row19.innerText(), r23 = await row23.innerText();
      return /Oct 19/.test(r19) && /\b3\.00\b/.test(r19) && /Nov 23/.test(r23) && /\b3\.00\b/.test(r23) && /fictional/i.test(r23);
    }, 3600);
  await kit.note('Both are fictional holidays for the client test only (the real calendar has no holiday on these days)',
    'Cả hai là ngày lễ giả định chỉ dùng cho kiểm thử của khách hàng (lịch thật không có ngày lễ vào các ngày này)');
}

const expected = (k) => `${k.lines.map((l) => `${l.wb} × ${l.qty} = ${fmt(l.total)} VND`).join('; ')}. TOTAL ${fmt(k.total)} VND; VAT 0; final due ${fmt(k.due)} VND. Parking ${fmt(k.parking)} VND is staff reimbursement, excluded from client total.`;

module.exports = { CASES, users, meta, runCase, expected, STATE, load, save, fmt, fmtVi };
