// BK-04 Order and invoice totals equal the client workbook, for four typical cases
// (owner's choice): TC-04, TC-07, TC-08 (Hanoi) and TC-15 (Ho Chi Minh City).
// Read-only review of the source bookings made from the client test data: nothing is
// recalculated or overwritten. Each line, the total, VAT 0 and parking outside the
// client total are proved on the booking's Pricing tab and on its invoice.
const c = require('./common');
const b = require('./bk_common');
const STOP = process.env.BK04_STOP || '';

const CASES = [
  {
    tc: 'TC-04', bk: 'BK3835', client: 'Trần Thị Bình', city: 'hn', when: 'Oct 15, 9:00 AM', min: 60, loc: 'Home Visit',
    conds: ['Home Visit', 'Distance: 6.0 km'], conds_vi: 'Tại nhà, khoảng cách 6 km',
    what: 'home visit, 6 km, 3 wounds; glucose test added at the visit', what_vi: 'tại nhà, 6 km, 3 vết thương; xét nghiệm đường huyết thêm tại lượt khám',
    lines: [
      { code: 'đd_020', name: 'Change wound dressing < 5cm', qty: 3, unit: 'Wound', total: 350000,
        calc: '200,000 + 2 × 50,000 (wounds 2–3) + 50,000 (5–8 km)', calc_vi: '200.000 + 2 × 50.000 (vết 2–3) + 50.000 (5–8 km)' },
      { code: 'đd_220', name: 'Capillary blood glucose test', qty: 1, unit: 'Visit', total: 50000, calc: 'base 50,000, no adjustment', calc_vi: 'giá gốc 50.000, không điều chỉnh' },
    ],
    total: 400000, parking: 100000,
  },
  {
    tc: 'TC-07', bk: 'BK3838', client: 'Phạm Thị Dung', city: 'hn', when: 'Oct 19, 8:30 PM', min: 60, loc: 'Home Visit',
    conds: ['Home Visit', 'After Hours', 'Holiday (Public)'], conds_vi: 'Tại nhà, ngoài giờ, ngày lễ',
    what: 'home visit at 20:30 on the test public holiday (19 Oct)', what_vi: 'tại nhà lúc 20:30 vào ngày lễ thử nghiệm (19/10)',
    lines: [
      { code: 'bs_020', name: 'Internal examination', qty: 1, unit: 'Visit', total: 2700000,
        calc: '(500,000 + 150,000 after hours + 250,000 after 20:00) × 3 holiday', calc_vi: '(500.000 + 150.000 ngoài giờ + 250.000 sau 20:00) × 3 ngày lễ' },
    ],
    total: 2700000, parking: 0,
  },
  {
    tc: 'TC-08', bk: 'BK3839', client: 'Đỗ Minh Giang', city: 'hn', when: 'Oct 21, 10:00 AM', min: 90, loc: 'Home Visit',
    conds: ['Home Visit'], conds_vi: 'Tại nhà',
    what: 'home visit, 3 injections and an ultrasound, 10% discount on the base price', what_vi: 'tại nhà, 3 mũi tiêm và siêu âm, giảm 10% trên giá gốc',
    lines: [
      { code: 'đd_060', name: 'Intramuscular/intradermal/subcutaneous injection', qty: 3, unit: 'Injection', total: 205000,
        calc: '150,000 + 2 × 50,000 (injections 2–3) − 10% of base 450,000', calc_vi: '150.000 + 2 × 50.000 (mũi 2–3) − 10% của giá gốc 450.000' },
      { code: 'bs_040', name: 'Ultrasound + reading results', qty: 1, unit: 'Visit', total: 470000,
        calc: '300,000 + 200,000 at home − 10% of base 300,000', calc_vi: '300.000 + 200.000 tại nhà − 10% của giá gốc 300.000' },
    ],
    total: 675000, parking: 100000,
  },
  {
    tc: 'TC-15', bk: 'BK3846', client: 'Lý Minh Tâm', city: 'hcm', when: 'Oct 19, 10:00 AM', min: 150, loc: 'Home Visit',
    conds: ['Home Visit', 'Distance: 6.0 km', 'Holiday (Public)'], conds_vi: 'Tại nhà, 6 km, ngày lễ',
    what: 'Ho Chi Minh City price list, home visit on the test public holiday, 2 bottles; bladder wash added at the visit',
    what_vi: 'bảng giá TP.HCM, tại nhà vào ngày lễ thử nghiệm, 2 chai; rửa bàng quang thêm tại lượt khám',
    lines: [
      { code: 'đd_060', name: 'Infusion over time <= 3 hours', qty: 2, unit: null, total: 2100000,
        calc: '(2 × 250,000 + 50,000 home + 150,000 bottle 2) × 3 holiday', calc_vi: '(2 × 250.000 + 50.000 tại nhà + 150.000 chai 2) × 3 ngày lễ' },
      { code: 'đd_120', name: 'Bladder Wash', qty: 1, unit: null, total: 600000,
        calc: '(250,000 + 200,000 home with another service) × 3 holiday', calc_vi: '(250.000 + 200.000 tại nhà kèm dịch vụ khác) × 3 ngày lễ' },
    ],
    total: 2700000, parking: 100000,
  },
];

const fmt = (n) => Math.round(n).toLocaleString('en-US');
const fmtVi = (n) => Math.round(n).toLocaleString('en-US').replace(/,/g, '.');

const proofVi = {};
for (const k of CASES) {
  proofVi[`${k.tc} ${k.bk}: ${k.when}, ${k.min} min, ${k.loc}`] = `${k.tc} ${k.bk}: ${k.when}, ${k.min} phút, tại nhà`;
  for (const l of k.lines) proofVi[`${k.tc} ${l.code} × ${l.qty} = ${fmt(l.total)} ₫ (workbook ${fmt(l.total)})`] = `${k.tc} ${l.code} × ${l.qty} = ${fmtVi(l.total)} ₫ (bảng tính ${fmtVi(l.total)})`;
  proofVi[`${k.tc} total ${fmt(k.total)} ₫ = workbook`] = `${k.tc} tổng ${fmtVi(k.total)} ₫ = bảng tính`;
  if (k.parking) proofVi[`${k.tc} at a glance: price ${fmt(k.total)} ₫, staff parking ${fmt(k.parking)} ₫ apart`] = `${k.tc} tổng quan: giá ${fmtVi(k.total)} ₫, phí gửi xe ${fmtVi(k.parking)} ₫ tách riêng`;
  if (k.parking) proofVi[`${k.tc} parking ${fmt(k.parking)} ₫ recorded as a separate staff charge`] = `${k.tc} phí gửi xe ${fmtVi(k.parking)} ₫ ghi riêng cho nhân viên`;
  proofVi[`${k.tc} invoice: same lines, no parking line, VAT 0, total ${fmt(k.total)} ₫`] = `${k.tc} hóa đơn: cùng dòng, không có phí gửi xe, VAT 0, tổng ${fmtVi(k.total)} ₫`;
}

module.exports = {
  meta: {
    id: 'BK-04', title: 'Order and invoice totals match the client workbook', short: 'Order and invoice totals',
    title_vi: 'Tổng đơn hàng và hóa đơn khớp bảng tính của khách hàng',
    criterion: 'Produce the order or invoice from the client test data with the right price list and appointment conditions; every service line and booking total matches, including quantity, extra-unit rules, home/clinic fees, distance, after-hours or holiday adjustments and base-only discounts; parking stays outside the client invoice.',
    data: 'Four typical cases chosen by the owner, from the client workbook (Test_Data): TC-04 BK3835 Trần Thị Bình; TC-07 BK3838 Phạm Thị Dung (test holiday 19 Oct); TC-08 BK3839 Đỗ Minh Giang; TC-15 BK3846 Lý Minh Tâm (Ho Chi Minh City). Read-only: nothing is recalculated or overwritten.',
    expected: 'All 17 order totals and 24 line totals equal the client formula outputs. (This recording: the 4 owner-chosen cases, 7 lines.)',
    ...b.users.omhn,
  },
  proofVi,

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();
    let first = true;
    for (const k of CASES) {
      if (STOP && !STOP.split(',').includes(k.tc)) continue;
      if (k.city === 'hcm') {
        await kit.switchUser(next(), b.users.omhcm, false);
        first = true;
      }
      await kit.step(next(), `${k.tc} (${k.client}): ${k.what}. Open ${k.bk}`, `${k.tc} (${k.client}): ${k.what_vi}. Mở ${k.bk}`);
      await b.openBooking(kit, k.bk, true);
      first = false;
      await kit.proof(p.locator('.ws-hero').first(), `${k.tc} ${k.bk}: ${k.when}, ${k.min} min, ${k.loc}`,
        (t) => t.includes(k.bk) && t.includes(k.when) && new RegExp(`\\b${k.min}\\s*min`).test(t) && t.includes(k.loc), 2600);

      await kit.step(next(), `${k.tc}: Pricing tab — each line against the workbook`, `${k.tc}: thẻ Giá — từng dòng so với bảng tính`);
      await b.tab(kit, 'Pricing');
      const wrap = p.locator('.o_field_widget[name=pricing_breakdown_html]').filter({ visible: true }).first();
      const strip = wrap.locator('div[style*="f0f4ff"]').first();
      for (const l of k.lines) {
        await kit.note(`${l.code} × ${l.qty}: ${l.calc} = ${fmt(l.total)} ₫`, `${l.code} × ${l.qty}: ${l.calc_vi} = ${fmtVi(l.total)} ₫`);
        const row = wrap.locator('tbody tr').filter({ hasText: l.code }).first();
        await kit.proof([strip, row], `${k.tc} ${l.code} × ${l.qty} = ${fmt(l.total)} ₫ (workbook ${fmt(l.total)})`, async (t) => {
          const cells = await row.locator('td').allInnerTexts();
          const st = await strip.innerText();
          return k.conds.every((x) => st.includes(x)) && cells.length >= 6 && Number(cells[4].trim()) === l.qty
            && b.has(cells[5], l.total) && cells[0].includes(l.name);
        }, 3000);
      }
      const totalRow = wrap.locator('tr').filter({ hasText: /^\s*Total/ }).last();
      await kit.proof(totalRow, `${k.tc} total ${fmt(k.total)} ₫ = workbook`, (t) => b.has(t, k.total), 2600);
      if (STOP === 'pricing') continue;

      if (k.parking) {
        await kit.step(next(), `${k.tc}: parking (staff reimbursement) is a separate charge`, `${k.tc}: phí gửi xe (hoàn cho nhân viên) là khoản riêng`);
        await b.tab(kit, 'Overview');
        const f = p.locator('.o_field_widget[name=parking_charge]').filter({ visible: true }).first();
        const lab = p.locator('label').filter({ hasText: /^\s*Parking Charge/ }).filter({ visible: true }).first();
        await kit.proof([lab, f], `${k.tc} parking ${fmt(k.parking)} ₫ recorded as a separate staff charge`, async () => {
          const v = await f.locator('input').inputValue();
          return Number(v.replace(/[^\d]/g, '')) === k.parking;
        }, 2600);
        await kit.proof([c.glanceRow(p, 'Price').first(), c.glanceRow(p, 'Staff parking').first()], `${k.tc} at a glance: price ${fmt(k.total)} ₫, staff parking ${fmt(k.parking)} ₫ apart`,
          (t) => /Price\s*([\d.,]+)/.test(t) && b.has(' ' + t.match(/Price\s*([\d.,]+)/)[1], k.total) && b.has(' ' + (t.match(/Staff parking\s*([\d.,]+)/) || [])[1], k.parking), 2600);
      }

      await kit.step(next(), `${k.tc}: Quick actions › View Invoice`, `${k.tc}: Thao tác nhanh › Xem hóa đơn`);
      await kit.click(p.getByRole('button', { name: /View Invoice/ }).first(), 3500);
      await kit.click(p.locator('tr.o_data_row').first().locator('td').nth(1), 4500);
      const lines = p.locator('.o_field_widget[name=invoice_line_ids] tr.o_data_row');
      const totals = p.locator('.o_field_widget[name=tax_totals]').first();
      await lines.first().waitFor({ timeout: 15000 });
      const boxes = [totals]; for (let i = 0; i < k.lines.length; i++) boxes.push(lines.nth(i));
      await kit.proof(boxes, `${k.tc} invoice: same lines, no parking line, VAT 0, total ${fmt(k.total)} ₫`, async () => {
        const rows = await lines.allInnerTexts();
        const taxes = await lines.locator('td[name=tax_ids]').allInnerTexts();
        const tt = await totals.innerText();
        const untaxed = (tt.match(/Untaxed Amount\s*([\d.,]+)/) || [])[1] || '';
        const total = (tt.match(/(?:^|\n)\s*Total\s*([\d.,]+)/) || [])[1] || '';
        return rows.length === k.lines.length
          && k.lines.every((l) => rows.some((r) => r.includes(l.code) && b.has(r, l.total) && new RegExp(`\\b${l.qty}\\.00\\b`).test(r)))
          && taxes.every((x) => !x.trim())
          && b.has(' ' + untaxed, k.total) && b.has(' ' + total, k.total) && !/parking/i.test(rows.join(' '));
      }, 3400);
    }
  },
};
