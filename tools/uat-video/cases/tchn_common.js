// Client test cases TC-01..TC-09 (Hanoi): "re-book live + original invoice" (owner decision 5 Nov 2026).
// Each video: the Operations Manager books the case's client again with the same services, duration
// and location, at the same Vietnam time on the date exactly 5 weeks (35 days) after the client's date
// (same weekday, so weekend / after-hours / night conditions are identical), no staff. The new
// booking's quote and Pricing tab prove each line, its rules, discount and the total against the
// workbook; then the ORIGINAL 29 Oct booking's invoice proves the lines, total, VAT 0, no parking and
// the amount due. The re-booking is cancelled at the end (its draft quote stays: it cannot be archived).
//
// Gotchas (paid for while preparing TC-01..09, 5 Nov 2026):
// - Quick Booking durations are only 30 min / 1 / 2 / 3 / 4 hours (no 1.5 h or 2.5 h): book the nearest
//   step, then type the exact minutes in Overview › Visit › Scheduled Duration (Minutes) and Save.
//   Evening slots run to 20:30. The calendar opens on the current month (› for December).
// - Driving Distance (Overview › Location Details) is an input for the OM since the 5 Nov deploy; a
//   hand-set value shows "(set by hand)" and the history logs "Distance changed from X to Y km".
//   Distance only prices home visits.
// - Discounts (5 Nov deploy): View Quote › each card's `.hfq-disc__input` (%), then a required
//   `.hfq-disc-reason__input`; dialog footer Save. Pricing tab breakdown then has a Discount column
//   (7 cells: product, base, rules, final, qty, discount, subtotal) and a "Discounts" list
//   (`[name=quote_line_ids]`) with Discount % and Discount Reason.
// - Glucose test: two products share the name (đd_220_hanoi and đd_030_hanoi): match the code.
// - Parking: Overview › "Additional charges" fold chip (button.ws-fold-tray__chip) › Parking Charge, Save;
//   the At a glance panel then lists "Staff parking" apart from "Price".
// - Pricing tab Qty cell reads "3 Wound" (number + unit).
// - Owner's holiday list: Settings › Master Data › segment "Public Holidays" (button.vu-segment).
const c = require('./common');
const b = require('./bk_common');
const fs = require('fs');
const path = require('path');

const STATE = path.join(__dirname, '..', 'tchn_state.json');
const load = () => (fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {});
const save = (patch) => fs.writeFileSync(STATE, JSON.stringify({ ...load(), ...patch }, null, 1));

const fmt = (n) => Math.round(n).toLocaleString('en-US');
const fmtVi = (n) => Math.round(n).toLocaleString('en-US').replace(/,/g, '.');
const h12 = (hm) => { const [h, m] = hm.split(':').map(Number); return `${((h + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`; };
const REASON = 'Client discount 10% (client test data)';

const LOC = {
  clinic: { type: 'Clinic Visit', typeVi: 'Khám tại phòng khám', location: 'Clinic', chip: 'Clinic Visit', en: 'at the clinic', vi: 'tại phòng khám' },
  home: { type: 'Home Visit', typeVi: 'Khám tại nhà', location: 'Patient Home', chip: 'Home Visit', en: 'at home', vi: 'tại nhà' },
};

// One row per client case. `min` = the workbook duration in minutes; `qb` = the Quick Booking step used.
// `rules` = what the Pricing tab's "Rules Applied" cell must say; `disc` = line discount %;
// `atVisit` = the item the nurse adds during the visit (entered here so the whole price shows).
const CASES = {
  'TC-01': {
    hb: 'HN-B01', client: 'Nguyễn Văn An', code: '01_0000126', loc: 'clinic', min: 60, km: 0,
    orig: { bk: 'BK3832', when: 'Oct 14, 10:00 AM', day: 'Wed 14 Oct', inv: 'INV/2026/00001' },
    when: { mon: 'Nov', day: 18, date: 'Wed 18 Nov', hm: '10:00' },
    conds: ['Clinic Visit'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i, /Distance/i],
    lines: [{ code: 'bs_020', q: 'Internal examination', name: 'Internal examination', qty: 1, total: 500000,
      rules: /No adjustments/, calc: '1 × 500,000, no adjustment (weekday, in hours, at the clinic)', calc_vi: '1 × 500.000, không điều chỉnh (ngày thường, trong giờ, tại phòng khám)' }],
    total: 500000, parking: 0, due: 0,
  },
  'TC-02': {
    hb: 'HN-B02', client: 'Nguyễn Văn An', code: '01_0000126', loc: 'clinic', min: 60, km: 0,
    orig: { bk: 'BK3833', when: 'Oct 21, 2:00 PM', day: 'Wed 21 Oct', inv: 'INV/2026/00003' },
    when: { mon: 'Nov', day: 25, date: 'Wed 25 Nov', hm: '14:00' },
    conds: ['Clinic Visit'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i, /Distance/i],
    lines: [
      { code: 'bs_040', q: 'Ultrasound + reading', name: 'Ultrasound + reading results', qty: 1, disc: 10, total: 270000,
        rules: /No adjustments/, calc: '300,000 − 10% discount on the base 300,000 (at the clinic, so the 200,000 home add does not apply)', calc_vi: '300.000 − giảm 10% trên giá gốc 300.000 (tại phòng khám nên không cộng 200.000 tại nhà)' },
      { code: 'bs_050', q: 'ECG + reading', name: 'ECG + reading results', qty: 1, disc: 10, total: 270000,
        rules: /No adjustments/, calc: '300,000 − 10% discount on the base 300,000 (at the clinic)', calc_vi: '300.000 − giảm 10% trên giá gốc 300.000 (tại phòng khám)' },
    ],
    total: 540000, parking: 0, due: 0,
  },
  'TC-03': {
    hb: 'HN-B03', client: 'Nguyễn Văn An', code: '01_0000126', loc: 'clinic', min: 30, km: 0,
    orig: { bk: 'BK3834', when: 'Oct 28, 11:00 AM', day: 'Wed 28 Oct', inv: 'INV/2026/00002' },
    when: { mon: 'Dec', day: 2, date: 'Wed 2 Dec', hm: '11:00' },
    conds: ['Clinic Visit'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i, /Distance/i],
    lines: [{ code: 'bs_030', q: 'Online internal examination', name: 'Online internal examination', qty: 1, disc: 10, total: 180000,
      rules: /No adjustments/, calc: '200,000 − 10% discount on the base (weekday, in hours)', calc_vi: '200.000 − giảm 10% trên giá gốc (ngày thường, trong giờ)' }],
    total: 180000, parking: 0, due: 180000,
  },
  'TC-04': {
    hb: 'HN-B04', client: 'Trần Thị Bình', code: '01_0000226', loc: 'home', min: 60, km: 6,
    orig: { bk: 'BK3835', when: 'Oct 15, 9:00 AM', day: 'Thu 15 Oct', inv: 'INV/2026/00019' },
    when: { mon: 'Nov', day: 19, date: 'Thu 19 Nov', hm: '09:00' },
    conds: ['Home Visit', 'Distance: 6.0 km'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i],
    lines: [
      { code: 'đd_020', q: 'Change wound dressing', name: 'Change wound dressing < 5cm', qty: 3, total: 350000,
        rules: /Subsequent units[\s\S]*50,000[\s\S]*distance[\s\S]*\+50,000/i,
        calc: '200,000 + 2 × 50,000 (wounds 2–3) + 50,000 (5–8 km, once per visit)', calc_vi: '200.000 + 2 × 50.000 (vết 2–3) + 50.000 (5–8 km, một lần mỗi lượt)' },
      { code: 'đd_220', q: 'Capillary blood glucose', name: 'Capillary blood glucose test', qty: 1, total: 50000, atVisit: true,
        rules: /No adjustments/, calc: 'base 50,000, no adjustment', calc_vi: 'giá gốc 50.000, không điều chỉnh' },
    ],
    total: 400000, parking: 100000, due: 0,
  },
  'TC-05': {
    hb: 'HN-B05', client: 'Trần Thị Bình', code: '01_0000226', loc: 'home', min: 150, qb: 2, km: 0,
    kmWhy: 'this visit is at another address, 0 km per the client\'s data', kmWhy_vi: 'lượt khám này ở địa chỉ khác, 0 km theo dữ liệu của khách',
    orig: { bk: 'BK3836', when: 'Oct 25, 2:00 PM', day: 'Sun 25 Oct', inv: 'INV/2026/00004' },
    when: { mon: 'Nov', day: 29, date: 'Sun 29 Nov', hm: '14:00' },
    conds: ['Home Visit', 'Weekend'], notConds: [/Holiday/i, /Distance/i],
    lines: [
      { code: 'đd_020', q: 'Change wound dressing', name: 'Change wound dressing < 5cm', qty: 1, disc: 10, total: 180000,
        rules: /No adjustments/, calc: '200,000 − 10% of the base (single wound; no weekend rule for this item)', calc_vi: '200.000 − 10% giá gốc (một vết; mục này không có quy tắc cuối tuần)' },
      { code: 'đd_240', q: 'Additional hours', name: 'Nursing fee (Additional hours)', qty: 2, disc: 10, total: 320000, atVisit: true,
        rules: /after hours or weekend[\s\S]*\+50,000/i, calc: '2 × 150,000 + 50,000 (weekend, Sunday) − 10% of the base 300,000', calc_vi: '2 × 150.000 + 50.000 (cuối tuần, Chủ nhật) − 10% của giá gốc 300.000' },
    ],
    total: 500000, parking: 0, due: 0,
  },
  'TC-06': {
    hb: 'HN-B06', client: 'Lê Quang Cường', code: '01_0000326', loc: 'home', min: 60, km: 6,
    orig: { bk: 'BK3837', when: 'Oct 17, 7:00 PM', day: 'Sat 17 Oct', inv: 'INV/2026/00005' },
    when: { mon: 'Nov', day: 21, date: 'Sat 21 Nov', hm: '19:00' },
    conds: ['Home Visit', 'Weekend', 'Distance: 6.0 km'], notConds: [/Holiday/i],
    lines: [{ code: 'bs_020', q: 'Internal examination', name: 'Internal examination', qty: 1, total: 650000,
      rules: /after hours or weekend[\s\S]*\+150,000/i,
      calc: '500,000 + 150,000 (after hours or weekend, Saturday); before 20:00 so no night add; distance 6 km is under this service\'s 10 km rule',
      calc_vi: '500.000 + 150.000 (ngoài giờ hoặc cuối tuần, thứ Bảy); trước 20:00 nên không cộng phí đêm; 6 km dưới mốc 10 km của dịch vụ này' }],
    total: 650000, parking: 100000, due: 650000,
  },
  'TC-07': {
    hb: 'HN-B07', client: 'Phạm Thị Dung', code: '01_0000426', loc: 'home', min: 60, km: 0, holiday: true,
    orig: { bk: 'BK3838', when: 'Oct 19, 8:30 PM', day: 'Mon 19 Oct (test holiday)', inv: 'INV/2026/00006' },
    when: { mon: 'Nov', day: 23, date: 'Mon 23 Nov', hm: '20:30' },
    conds: ['Home Visit', 'After Hours', 'Holiday'], notConds: [/Distance/i],
    lines: [{ code: 'bs_020', q: 'Internal examination', name: 'Internal examination', qty: 1, total: 2700000,
      rules: /\+150,000[\s\S]*\+250,000[\s\S]*(×|x)\s*3/i,
      calc: '(500,000 + 150,000 after hours + 250,000 after 20:00) × 3 public holiday', calc_vi: '(500.000 + 150.000 ngoài giờ + 250.000 sau 20:00) × 3 ngày lễ' }],
    total: 2700000, parking: 0, due: 0,
  },
  'TC-08': {
    hb: 'HN-B08', client: 'Đỗ Minh Giang', code: '01_0000626', loc: 'home', min: 90, qb: 2, km: 0,
    orig: { bk: 'BK3839', when: 'Oct 21, 10:00 AM', day: 'Wed 21 Oct', inv: 'INV/2026/00007' },
    when: { mon: 'Nov', day: 25, date: 'Wed 25 Nov', hm: '10:00' },
    conds: ['Home Visit'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i, /Distance/i],
    lines: [
      { code: 'đd_060', q: 'Intramuscular', name: 'Intramuscular/intradermal/subcutaneous injection', qty: 3, disc: 10, total: 205000,
        rules: /Subsequent units[\s\S]*50,000/i, calc: '150,000 + 2 × 50,000 (injections 2–3) − 10% of the base 450,000', calc_vi: '150.000 + 2 × 50.000 (mũi 2–3) − 10% của giá gốc 450.000' },
      { code: 'bs_040', q: 'Ultrasound + reading', name: 'Ultrasound + reading results', qty: 1, disc: 10, total: 470000,
        rules: /home[\s\S]*\+200,000/i, calc: '300,000 + 200,000 at home − 10% of the base 300,000', calc_vi: '300.000 + 200.000 tại nhà − 10% của giá gốc 300.000' },
    ],
    total: 675000, parking: 100000, due: 0,
  },
  'TC-09': {
    hb: 'HN-B09', client: 'Vũ Thị Khánh', code: '01_0000726', loc: 'home', min: 240, km: 6,
    orig: { bk: 'BK3840', when: 'Oct 22, 8:00 AM', day: 'Thu 22 Oct', inv: 'INV/2026/00008' },
    when: { mon: 'Nov', day: 26, date: 'Thu 26 Nov', hm: '08:00' },
    conds: ['Home Visit', 'Distance: 6.0 km'], notConds: [/After Hours/i, /Weekend/i, /Holiday/i],
    lines: [{ code: 'đd_190', q: 'Daytime personal care', name: 'Daytime personal care (minimum 3 hours)', qty: 4, total: 450000,
      rules: /distance[\s\S]*\+50,000/i,
      calc: '4 × 100,000 + 50,000 (nursing service 5–8 km)', calc_vi: '4 × 100.000 + 50.000 (dịch vụ điều dưỡng 5–8 km)' }],
    total: 450000, parking: 0, due: 450000,
  },
};

const qbLabel = (h) => (h === 0.5 ? '30 minutes' : h === 1 ? '1 hour' : `${h} hours`);
const hrs = (min) => (min % 60 ? `${min / 60}`.replace('.', '.') : `${min / 60}`);

function build(id, row) {
  const k = CASES[id];
  const L = LOC[k.loc];
  k.qb = k.qb || k.min / 60;                               // the Quick Booking step used
  const svcList = k.lines.map((l) => `${l.code} × ${l.qty}${l.disc ? ` (${l.disc}% off)` : ''}`).join(', ');
  const newWhen = `${k.when.mon} ${k.when.day}, ${h12(k.when.hm)}`;
  const vi = {};
  const P = (en, v) => { vi[en] = v; return en; };
  const disc = k.lines.filter((l) => l.disc);
  const labels = {
    client: P(`Client ${k.client} (${k.code}) opened`, `Đã mở khách hàng ${k.client} (${k.code})`),
    services: P(`Services added: ${k.lines.map((l) => `${l.code} × ${l.qty}`).join(', ')}`, `Đã thêm dịch vụ: ${k.lines.map((l) => `${l.code} × ${l.qty}`).join(', ')}`),
    created: P(`New booking created: ${k.when.date} ${k.when.hm}, ${L.type} (${qbLabel(k.qb).replace(' hours', 'h').replace(' hour', 'h').replace('30 minutes', '30 min')})`,
      `Đã tạo lịch hẹn mới: ${k.when.date} ${k.when.hm}, ${L.typeVi}`),
    hero: P(`New booking: ${newWhen}, ${k.min} min, ${L.chip}, nobody assigned`, `Lịch hẹn mới: ${k.when.day}/${k.when.mon === 'Dec' ? 12 : 11} lúc ${k.when.hm}, ${k.min} phút, ${L.typeVi.toLowerCase()}, chưa phân công`),
    km: P(`Driving distance ${k.km} km = workbook`, `Khoảng cách lái xe ${k.km} km = bảng tính`),
    conds: P(`Conditions applied: ${k.conds.join(', ')}`, `Điều kiện áp dụng: ${k.conds.join(', ')}`),
    total: P(`Total ${fmt(k.total)} ₫ = workbook`, `Tổng ${fmtVi(k.total)} ₫ = bảng tính`),
    quote: P(`Quote: taxes 0, total ${fmt(k.total)} ₫`, `Báo giá: thuế 0, tổng ${fmtVi(k.total)} ₫`),
    orig: P(`Original ${k.orig.bk}: ${k.orig.when}, ${k.min} min, ${L.chip}, Completed`, `Lịch hẹn gốc ${k.orig.bk}: ${k.orig.when}, ${k.min} phút, ${L.typeVi.toLowerCase()}, Hoàn thành`),
    invLines: P(`${k.orig.inv}: same lines, VAT 0, no parking line`, `${k.orig.inv}: cùng dòng dịch vụ, VAT 0, không có phí gửi xe`),
    invDue: P(`${k.orig.inv}: total ${fmt(k.total)} ₫, amount due ${fmt(k.due)} ₫ = workbook`, `${k.orig.inv}: tổng ${fmtVi(k.total)} ₫, còn phải thu ${fmtVi(k.due)} ₫ = bảng tính`),
    cancelled: P('Re-booking cancelled: it was for the price check only', 'Đã hủy lịch hẹn đặt lại: chỉ dùng để kiểm tra giá'),
  };
  if (k.min !== k.qb * 60) labels.minutes = P(`Duration ${k.min} minutes (${hrs(k.min)} hours) = workbook`, `Thời lượng ${k.min} phút (${hrs(k.min).replace('.', ',')} giờ) = bảng tính`);
  if (k.parking) {
    labels.parking = P(`Parking ${fmt(k.parking)} ₫ entered as a staff charge`, `Đã nhập phí gửi xe ${fmtVi(k.parking)} ₫ là khoản cho nhân viên`);
    labels.glance = P(`At a glance: price ${fmt(k.total)} ₫, staff parking ${fmt(k.parking)} ₫ apart`, `Tổng quan: giá ${fmtVi(k.total)} ₫, phí gửi xe ${fmtVi(k.parking)} ₫ tách riêng`);
  }
  if (disc.length) labels.discList = P(`Discounts list: ${disc.map((l) => `${l.code} ${l.disc}%`).join(', ')}, with the reason`, `Danh sách giảm giá: ${disc.map((l) => `${l.code} ${l.disc}%`).join(', ')}, có lý do`);
  if (k.holiday) labels.holiday = P('Owner: test holiday 23 Nov 2026, price × 3, applies to pricing', 'Chủ sở hữu: ngày lễ thử nghiệm 23/11/2026, giá × 3, áp dụng tính giá');
  for (const l of k.lines) {
    l.label = P(`${l.code} × ${l.qty}${l.disc ? `, ${l.disc}% off` : ''} = ${fmt(l.total)} ₫ (workbook ${fmt(l.total)})`, `${l.code} × ${l.qty}${l.disc ? `, giảm ${l.disc}%` : ''} = ${fmtVi(l.total)} ₫ (bảng tính ${fmtVi(l.total)})`);
    if (l.disc) l.qlabel = P(`Quote: ${l.code} discount ${l.disc}% with reason, line ${fmt(l.total)} ₫`, `Báo giá: ${l.code} giảm ${l.disc}% có lý do, dòng ${fmtVi(l.total)} ₫`);
  }

  const durTxt = k.min === 30 ? '30 minutes' : `${hrs(k.min)} hour${k.min === 60 ? '' : 's'}`;
  const meta = {
    id, title: `${k.client} - ${row.title}`, short: `${k.hb} re-booked + invoice`,
    title_vi: `${k.client} - ${row.title_vi}`,
    criterion: `Client test case ${id} (${k.hb}): ${k.client}, Hanoi. Book the client's services with the same appointment conditions on the price list "Client UAT 20261013 V01.01 (VND)": each service line, the booking total, VAT 0 and parking outside the client total match the client workbook; the original booking's invoice and amount due match too.`,
    data: `Fictional test client ${k.client} (${k.code}). Client's appointment ${k.orig.day} ${k.when.hm}; re-booked live on ${k.when.date} ${k.when.hm} Vietnam time (5 weeks later, same weekday), ${L.type} ${durTxt} ${L.en}, ${k.km} km, ${svcList}, no staff. Original booking ${k.orig.bk}, invoice ${k.orig.inv}.`,
    expected: row.expected,
    ...b.users.omhn,
  };
  return { k, L, labels, vi, meta, newWhen };
}

// ------------------------------------------------------------------------- the story
async function run(kit, id, B) {
  const { k, L, labels } = B;
  const p = kit.page;
  let n = 1;
  const next = () => ++n;
  const STOP = process.env.TCHN_STOP || '';
  const disc = k.lines.filter((l) => l.disc);

  if (k.holiday) {
    await kit.login();   // meta is the owner for this case: show the test holiday first
    await kit.step(next(), 'The client\'s date 19 Oct was a test public holiday. Settings › Master Data › Public Holidays: the same test holiday on Mon 23 Nov',
      'Ngày 19/10 của khách là ngày lễ thử nghiệm. Cài đặt › Dữ liệu gốc › Ngày lễ: cùng ngày lễ thử nghiệm vào thứ Hai 23/11');
    await kit.area('Settings');
    await kit.click(c.sidebar(p, 'Master Data'), 3000);
    await kit.click(p.locator('button.vu-segment', { hasText: 'Public Holidays' }).first(), 3000);
    await kit.type(p.locator('.o_searchview_input'), 'CLIENT UAT ONLY', 600);
    await p.keyboard.press('Enter');
    const hrow = p.locator('tr.o_data_row', { hasText: '23 Nov 2026' }).first();
    await hrow.waitFor({ timeout: 15000 });
    await kit.proof(hrow, labels.holiday, async (t) => /Nov 23, 12:00 AM/.test(t) && /Nov 23, 11:59 PM/.test(t) && /\b3\.00\b/.test(t)
      && (await hrow.locator('input[type=checkbox]').last().isChecked().catch(() => false)), 3400);
    await kit.switchUser(next(), b.users.omhn, false);
  } else {
    await kit.login();
  }

  // ---- 1. book again, same conditions, 5 weeks later
  await kit.step(next(), `Operations › Clients › ${k.client}`, `Vận hành › Khách hàng › ${k.client}`);
  await kit.area('Operations');
  await kit.click(c.sidebar(p, 'Clients'), 2500);
  await kit.type(p.locator('.o_searchview_input'), k.client, 300);
  await p.keyboard.press('Enter');
  await p.locator('tr.o_data_row', { hasText: k.client }).first().waitFor({ timeout: 15000 });
  await kit.hold(1200);
  await kit.click(p.locator('tr.o_data_row', { hasText: k.client }).locator('td[name=name]').first(), 4000);
  await kit.proof(c.hero(p), labels.client, (t) => t.includes(k.client) && t.includes(k.code), 2200);

  const exact = k.min !== k.qb * 60;
  await kit.step(next(), `New booking: ${L.type}, ${qbLabel(k.qb)}${exact ? ` (the nearest step; set to ${k.min} minutes after booking)` : ''}, HN_PK_PKGDVU, ${L.en} (as on ${k.orig.day})`,
    `Đặt lịch mới: ${L.typeVi.toLowerCase()}, ${k.qb} giờ${exact ? ` (mức gần nhất; chỉnh thành ${k.min} phút sau khi đặt)` : ''}, HN_PK_PKGDVU, ${L.vi} (như ngày ${k.orig.day})`);
  const nb = () => p.getByRole('button', { name: /^\s*New booking\s*$/ }).filter({ visible: true }).first();
  await nb().waitFor({ timeout: 15000 });
  const box = await nb().boundingBox();
  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 15 });
  await kit.hold(300);
  await p.mouse.click(box.x + box.width / 2, box.y + box.height / 2);   // the button pulses: never "stable"
  await p.locator('.qb-form-group').first().waitFor({ timeout: 15000 });
  await kit.hold(1500);
  await c.qbFill(kit, { service: L.type, duration: qbLabel(k.qb), facility: 'HN_PK_PKGDVU', location: L.location });

  const atVisit = k.lines.filter((l) => l.atVisit);
  await kit.step(next(), `Add the services: ${k.lines.map((l) => `${l.name} (${l.code}) × ${l.qty}`).join('; ')}`,
    `Thêm dịch vụ: ${k.lines.map((l) => `${l.code} × ${l.qty}`).join('; ')}`);
  if (atVisit.length) {
    await kit.note(`${atVisit.map((l) => l.name).join(', ')} is the item the nurse adds at the visit: it is entered here so the whole price is shown (adding at the visit itself is shown in BK-03)`,
      `${atVisit.map((l) => l.code).join(', ')} là dịch vụ điều dưỡng thêm tại lượt khám: nhập ở đây để thấy toàn bộ giá (việc thêm tại lượt khám được trình bày ở BK-03)`);
  }
  await kit.click(p.locator('.qb-add-services-btn'), 2000);
  for (const l of k.lines) {
    await kit.type(p.locator('.pcd-search-input'), l.q, 1400);
    const card = p.locator('.pcd-card', { hasText: `${l.code}_hanoi` }).first();
    await kit.click(card.locator('.pcd-add-btn').first(), 700);
    for (let i = 1; i < l.qty; i++) await kit.click(card.locator('.pcd-qty-btn').last(), 600);
  }
  await kit.click(p.locator('.pcd-done-btn'), 1800);
  const qbQuote = p.locator('.qb-pt-footer').first().locator('xpath=..');
  await kit.proof(qbQuote, labels.services, async (t) => k.lines.every((l) => t.includes(l.name)), 2000);

  await kit.step(next(), `Date: ${k.when.date}, ${k.when.hm} — the client's ${k.orig.day} ${k.when.hm} five weeks later (same weekday and time). No staff`,
    `Ngày: ${k.when.date}, ${k.when.hm} — ngày ${k.orig.day} ${k.when.hm} của khách cộng 5 tuần (cùng thứ, cùng giờ). Không phân công nhân sự`);
  if (k.when.mon === 'Dec') await kit.click(p.locator('.qb-cal-nav').last(), 1200);
  await kit.click(p.locator('.qb-cal-day:not(.qb-cal-day--disabled):not(.qb-cal-day--empty)')
    .filter({ hasText: new RegExp(`^\\s*${k.when.day}\\s*$`) }).first(), 2400);
  const hh = Number(k.when.hm.slice(0, 2));
  const tod = hh < 12 ? 'Morning' : hh < 17 ? 'Afternoon' : 'Evening';
  const todCard = p.locator('.qb-tod-card', { hasText: tod }).first();
  if (!(await todCard.getAttribute('class')).includes('active')) await kit.click(todCard, 1500);
  const slot = p.locator('.qb-slot-grid button').filter({ hasText: new RegExp(`^\\s*${k.when.hm}`) }).first();
  if (!(await slot.count()) || !(await slot.isEnabled()) || await slot.locator('.fa-lock, .fa-exclamation-triangle').count()) {
    throw new Error(`slot ${k.when.hm} on ${k.when.date} is not free`);
  }
  await kit.click(slot, 1800);

  await kit.step(next(), 'Create the booking', 'Tạo lịch hẹn');
  const r = await b.qbCreate(kit);
  if (!r.bk) throw new Error('booking not created: ' + r.text.slice(0, 200));
  const qbd = `${String(k.when.day).padStart(2, '0')} ${k.when.mon} 2026, ${k.when.hm}`;
  const qbDur = k.qb >= 1 ? `${k.qb}h` : '30 min';
  await kit.proof(r.box, labels.created, (t) => t.includes(r.bk) && t.includes(k.client) && t.includes(qbd)
    && t.includes(L.type) && (!qbDur || t.includes(`(${qbDur})`)) && t.includes('HN_PK_PKGDVU'), 2600);
  kit.records['New booking (re-pricing, cancelled at the end)'] = r.bk;
  await kit.click(p.locator('.qb-modal-confirm'), 4500);
  await p.locator('.ws-hero').first().waitFor({ timeout: 20000 });
  const newId = Number((p.url().match(/\/(\d+)(?:\?.*)?$/) || [])[1]) || null;
  save({ [id]: { bk: r.bk, id: newId, at: new Date().toISOString(), out: process.argv.includes('--out') ? 'practice' : 'final' } });

  // exact duration and distance (Overview › Visit / Location Details), when they differ from the workbook
  const durF = p.locator('.o_field_widget[name=scheduled_duration]').filter({ has: p.locator('input') }).filter({ visible: true }).first();
  const dist = p.locator('.o_field_widget[name=travel_distance]').filter({ visible: true }).first();
  const locCard = p.locator('[name=location_details_card]').filter({ visible: true }).first();
  const kmNow = async () => parseFloat(((await dist.locator('input').inputValue().catch(() => '')) || (await dist.innerText())).replace(/[^\d.]/g, '')) || 0;
  let dirty = false;
  if (exact) {
    await kit.step(next(), `Quick Booking offers whole hours only: type the exact duration, ${k.min} minutes (${hrs(k.min)} hours), in Visit › Scheduled Duration (Minutes)`,
      `Đặt lịch nhanh chỉ có giờ tròn: nhập thời lượng chính xác ${k.min} phút (${hrs(k.min).replace('.', ',')} giờ) ở Lượt khám › Thời lượng dự kiến (phút)`);
    await kit.type(durF.locator('input'), String(k.min), 600);
    await p.keyboard.press('Tab');
    dirty = true;
  }
  const before = await kmNow();
  if (Math.abs(before - k.km) >= 0.005) {
    await kit.step(next(), `Location Details › Driving Distance shows ${before} km; set ${k.km} km: ${k.kmWhy || `the client's data says ${k.km} km for this visit`}`,
      `Chi tiết địa điểm › Khoảng cách lái xe đang là ${before} km; đặt ${k.km} km: ${k.kmWhy_vi || `dữ liệu của khách ghi ${k.km} km cho lượt này`}`);
    await kit.type(dist.locator('input'), String(k.km), 600);
    await p.keyboard.press('Tab');
    dirty = true;
  }
  if (dirty) {
    await kit.hold(600);
    await kit.click(c.saveBtn(p), 3500);
  }
  await kit.proof([p.locator('.ws-hero').first(), p.locator('.ws-panel--glance').first()], labels.hero,
    (t) => t.includes(r.bk) && t.includes(B.newWhen) && new RegExp(`\\b${k.min}\\s*min`).test(t) && t.includes(L.chip) && /Nobody yet/.test(t), 2600);
  if (labels.minutes) await kit.proof(durF, labels.minutes, async () => Number((await durF.locator('input').inputValue()).replace(/[^\d]/g, '')) === k.min, 2200);
  if (Math.abs(before - k.km) < 0.005) await kit.step(next(), `Location Details: driving distance ${k.km} km as in the workbook`, `Chi tiết địa điểm: khoảng cách lái xe ${k.km} km như bảng tính`);
  await kit.proof(locCard, labels.km, async () => Math.abs((await kmNow()) - k.km) < 0.005 && !(await c.saveBtn(p).isVisible().catch(() => false)), 2600);
  if (STOP === 'book') return;

  // parking: staff reimbursement, outside the client total
  if (k.parking) {
    await kit.step(next(), `Parking ${fmt(k.parking)} ₫ (staff reimbursement): Additional charges › Parking Charge, Save`,
      `Phí gửi xe ${fmtVi(k.parking)} ₫ (hoàn cho nhân viên): Phụ phí › Phí gửi xe, Lưu`);
    const chip = p.locator('button.ws-fold-tray__chip').filter({ hasText: /Additional charges/ }).first();
    if (await chip.count()) await kit.click(chip, 1500);
    const f = p.locator('.o_field_widget[name=parking_charge]').filter({ visible: true }).first();
    await kit.type(f.locator('input'), String(k.parking), 600);
    await p.keyboard.press('Tab');
    await kit.hold(800);
    await kit.click(c.saveBtn(p), 3000);
    await kit.proof(f.locator('xpath=ancestor::div[contains(@class,"ws-card")][1]'), labels.parking, async () =>
      Number((await f.locator('input').inputValue()).replace(/[^\d]/g, '')) === k.parking && !(await c.saveBtn(p).isVisible().catch(() => false)), 2400);
  }

  // ---- 2. the quote: discounts (if any), taxes and total
  await kit.step(next(), disc.length ? `Quick actions › View Quote: enter the ${disc[0].disc}% client discount on ${disc.map((l) => l.code).join(' and ')} with its reason` : 'Quick actions › View Quote: taxes and total',
    disc.length ? `Thao tác nhanh › Xem báo giá: nhập giảm giá ${disc[0].disc}% cho ${disc.map((l) => l.code).join(' và ')} kèm lý do` : 'Thao tác nhanh › Xem báo giá: thuế và tổng');
  await kit.click(p.locator('button, a').filter({ hasText: /^\s*View Quote\s*$/ }).filter({ visible: true }).first(), 4000);
  const dlg = p.locator('.modal-content').filter({ has: p.locator('.hfq-panel') }).last();
  await dlg.waitFor({ timeout: 15000 });
  const quoteNo = (((await dlg.innerText()).match(/S0\d{4,}/)) || [''])[0];
  if (quoteNo) { kit.records['Its quote (stays as a draft)'] = quoteNo; save({ [id]: { ...(load()[id] || {}), quote: quoteNo } }); }
  for (const l of disc) {
    const card = dlg.locator('.hfq-card', { hasText: `${l.code}_hanoi` }).first();
    await kit.type(card.locator('.hfq-disc__input'), String(l.disc), 600);
    await p.keyboard.press('Tab');
    await kit.hold(1200);
    await kit.type(card.locator('.hfq-disc-reason__input'), REASON, 600);
    await p.keyboard.press('Tab');
    await kit.hold(1200);
    await kit.proof(card, l.qlabel, async () => Number(await card.locator('.hfq-disc__input').inputValue()) === l.disc
      && (await card.locator('.hfq-disc-reason__input').inputValue()) === REASON && b.has(' ' + (await card.locator('.hfq-subtotal').innerText()), l.total), 2600);
  }
  const sums = dlg.locator('.hfq-totals').first();
  await kit.proof(sums, labels.quote, (t) => /Taxes\s*0\s*đ/.test(t) && b.has(' ' + ((t.match(/Total\s*([\d.,]+)/) || [])[1] || ''), k.total)
    && b.has(' ' + ((t.match(/Untaxed\s*([\d.,]+)/) || [])[1] || ''), k.total), 3000);
  if (disc.length) {
    await kit.note('Save the quote', 'Lưu báo giá');
    await kit.click(dlg.locator('.modal-footer button').filter({ hasText: /^\s*Save\s*$/ }).first(), 3500);
  } else {
    await kit.click(dlg.locator('.modal-footer button').filter({ hasText: /^\s*Discard\s*$/ }).first(), 2000);
  }
  if (await dlg.isVisible().catch(() => false)) await kit.click(dlg.locator('.btn-close').first(), 1500);
  await dlg.waitFor({ state: 'detached', timeout: 10000 }).catch(() => {});

  if (k.parking) {
    const g = (lab) => c.glanceRow(p, lab).first();
    await kit.proof([g('Price'), g('Staff parking')], labels.glance, async () => {
      const pr = await g('Price').innerText(); const pk = await g('Staff parking').innerText();
      return b.has(' ' + pr, k.total) && b.has(' ' + pk, k.parking);
    }, 2800);
  }

  // ---- 3. pricing tab: each line, its rules, discount and the total
  await kit.step(next(), 'Pricing tab: each line, the rules applied and the total against the workbook', 'Thẻ Giá: từng dòng, quy tắc áp dụng và tổng so với bảng tính');
  await b.tab(kit, 'Pricing');
  const wrap = p.locator('.o_field_widget[name=pricing_breakdown_html]').filter({ visible: true }).first();
  const strip = wrap.locator('div[style*="f0f4ff"]').first();
  await kit.proof(strip, labels.conds, (t) => k.conds.every((x) => t.includes(x)) && k.notConds.every((re) => !re.test(t)), 2600);
  for (const l of k.lines) {
    await kit.note(`${l.code} × ${l.qty}: ${l.calc} = ${fmt(l.total)} ₫`, `${l.code} × ${l.qty}: ${l.calc_vi} = ${fmtVi(l.total)} ₫`);
    const row = wrap.locator('tbody tr').filter({ hasText: `${l.code}_hanoi` }).first();
    await kit.proof(row, l.label, async () => {
      const cells = await row.locator('td').allInnerTexts();
      const dcell = cells.length >= 7 ? cells[5] : '';
      const dOk = l.disc ? new RegExp(`^\\s*${l.disc}\\s*%`).test(dcell) : !/[1-9]/.test(dcell);
      return cells.length >= 6 && cells[0].includes(l.name) && parseFloat(cells[4]) === l.qty && l.rules.test(cells[2]) && dOk
        && b.has(' ' + cells[cells.length - 1], l.total);
    }, 3200);
  }
  const totalRow = wrap.locator('tr').filter({ hasText: /^\s*Total/ }).last();
  await kit.proof(totalRow, labels.total, (t) => b.has(t, k.total), 2600);
  if (disc.length) {
    const list = p.locator('.o_field_widget[name=quote_line_ids]').filter({ visible: true }).first();
    const rows = list.locator('tr.o_data_row');
    await kit.proof(list, labels.discList, async () => {
      const all = await rows.allInnerTexts();
      return disc.every((l) => all.some((t) => t.includes(`${l.code}_hanoi`) && new RegExp(`\\b${l.disc}\\.00\\b`).test(t) && t.includes(REASON) && b.has(t, l.total)));
    }, 3000);
  }
  if (STOP === 'pricing') return;

  // ---- 4. the original booking and its invoice
  await kit.step(next(), `The original booking ${k.orig.bk} (${k.orig.day} ${k.when.hm}, completed): Operations › Bookings`, `Lịch hẹn gốc ${k.orig.bk} (${k.orig.day} ${k.when.hm}, đã hoàn thành): Vận hành › Lịch hẹn`);
  await b.openBooking(kit, k.orig.bk, true);
  await kit.proof(p.locator('.ws-hero').first(), labels.orig, (t) => t.includes(k.orig.bk) && t.includes(k.client) && t.includes(k.orig.when)
    && new RegExp(`\\b${k.min}\\s*min`).test(t) && t.includes(L.chip) && /Completed/.test(t), 2600);

  await kit.step(next(), `Quick actions › View Invoice › ${k.orig.inv}`, `Thao tác nhanh › Xem hóa đơn › ${k.orig.inv}`);
  await kit.click(p.getByRole('button', { name: /View Invoice/ }).first(), 3500);
  await kit.click(p.locator('tr.o_data_row', { hasText: k.orig.inv }).first().locator('td').nth(1), 4500);
  const lines = p.locator('.o_field_widget[name=invoice_line_ids] tr.o_data_row');
  const totals = p.locator('.o_field_widget[name=tax_totals]').first();
  const due = p.locator('.o_field_widget[name=amount_residual]').filter({ visible: true }).first();
  await lines.first().waitFor({ timeout: 15000 });
  const boxes = []; for (let i = 0; i < k.lines.length; i++) boxes.push(lines.nth(i));
  await kit.proof(boxes, labels.invLines, async () => {
    const rows = await lines.allInnerTexts();
    const taxes = await lines.locator('td[name=tax_ids]').allInnerTexts();
    return rows.length === k.lines.length
      && k.lines.every((l) => rows.some((r) => r.includes(`${l.code}_hanoi`) && b.has(r, l.total) && new RegExp(`\\b${l.qty}\\.00\\b`).test(r)))
      && taxes.every((x) => !x.trim()) && !/parking/i.test(rows.join(' '));
  }, 3400);
  const head = p.locator('.o_form_sheet').first();
  await kit.proof([totals, due], labels.invDue, async () => {
    const tt = await totals.innerText();
    const untaxed = (tt.match(/Untaxed Amount\s*([\d.,]+)/) || [])[1] || '';
    const total = (tt.match(/(?:^|\n)\s*Total\s*([\d.,]+)/) || [])[1] || '';
    const sheet = await head.innerText();
    return b.has(' ' + untaxed, k.total) && b.has(' ' + total, k.total) && b.has(' ' + (await due.innerText()), k.due)
      && sheet.includes(k.orig.inv) && /POSTED/i.test(sheet);
  }, 3400);
  if (STOP === 'invoice') return;

  // ---- 5. tidy up: the re-booking was for the price check only
  await kit.step(next(), `Close: cancel the re-booking ${r.bk} (More › Cancel Booking), it was for the price check only`, `Kết thúc: hủy lịch hẹn đặt lại ${r.bk} (Thêm › Hủy lịch hẹn), chỉ dùng để kiểm tra giá`);
  await b.openBooking(kit, r.bk, true);
  await kit.click(p.locator('.ws-hero button, .o_form_view button').filter({ hasText: /^\s*More\s*$/ }).filter({ visible: true }).first(), 900);
  await kit.click(p.locator('.dropdown-item, .o-dropdown-item').filter({ hasText: /^\s*Cancel Booking\s*$/ }).filter({ visible: true }).first(), 2000);
  const sure = p.locator('.modal-content', { hasText: 'Are you sure' }).locator('button').filter({ hasText: /^\s*Ok\s*$/ }).first();
  if (await sure.count()) await kit.click(sure, 2500);
  const cd = p.locator('.modal-content').last();
  await kit.type(cd.locator('.o_field_widget[name=cancellation_reason_id] input'), 'Other', 1200);
  await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: /^\s*Other\s*$/ }).first(), 800);
  await kit.type(cd.locator('.o_field_widget[name=cancellation_notes] textarea'), `UAT video re-pricing only (${id})`, 500);
  await kit.click(cd.locator('button[name=action_confirm_cancellation]'), 3500);
  await kit.proof(p.locator('.ws-hero').first(), labels.cancelled, (t) => t.includes(r.bk) && /Cancelled/.test(t), 2400);
  save({ [id]: { ...(load()[id] || {}), cancelled: true } });
}

// A case file: module.exports = make('TC-01', { title, title_vi, expected })
function make(id, row) {
  const B = build(id, row);
  if (B.k.holiday) Object.assign(B.meta, { ...b.users.owner, role: 'Owner, then Operations Manager, Hanoi', role_vi: 'Chủ sở hữu, sau đó Quản lý vận hành Hà Nội' });
  return { meta: B.meta, proofVi: B.vi, run: (kit) => run(kit, id, B) };
}

module.exports = { CASES, make, load, save };
