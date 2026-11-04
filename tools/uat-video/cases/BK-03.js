// BK-03 Initial services booked by the office, a service added by the nurse during the visit,
// both kept with the right units and the new total. Source: TC-04 (Test_Data rows 6-7):
// Trần Thị Bình, home visit, 1 hour, đd_020 × 3 wounds initially; đd_220 × 1 added at the visit.
const c = require('./common');
const b = require('./bk_common');
const om = b.users.omhn;
const nurse = b.users.nurse;
const client = 'Trần Thị Bình';
const clientCode = '01_0000226';
const DAY = { k: 1, ...b.vnDay(1) };
const TIMES = ['09:00', '09:30', '10:00', '10:30', '08:00', '08:30', '11:00'];
const note = 'UAT ONLY - three wounds dressed; capillary glucose checked at the visit';
const STOP = process.env.BK03_STOP || '';
const fmt = (n) => Math.round(n).toLocaleString('en-US');
const W = {
  lines: [
    { code: 'đd_020', name: 'Change wound dressing < 5cm', qty: 3, unit: 'Wound', total: 350000 },
    { code: 'đd_220', name: 'Capillary blood glucose test', qty: 1, unit: 'Visit', total: 50000 },
  ],
  total: 400000,
};

module.exports = {
  meta: {
    id: 'BK-03', title: 'Initial services and a service added at the visit, with units', short: 'Services incl. added at visit',
    title_vi: 'Dịch vụ ban đầu và dịch vụ thêm tại lượt khám, đúng đơn vị',
    criterion: 'Record the correct service, clinic-specific item, quantity, unit, location and duration. Services ordered at booking are entered first; the service marked Added at Visit is added by the nurse during the visit; the final saved service list matches the client case.',
    data: `TC-04 (workbook rows 6-7): ${client} (${clientCode}), Home Visit, 1 hour, HN_PK_PKGDVU, ${DAY.monShort} ${DAY.day} 09:00; initial: Change wound dressing < 5cm (đd_020) × 3 wounds; added at the visit by ${nurse.login}: Capillary blood glucose test (đd_220) × 1`,
    expected: 'Correct initial and visit-added services persist with the correct units.',
    ...om,
  },
  proofVi: {
    'Initial service: đd_020 × 3 wounds': 'Dịch vụ ban đầu: đd_020 × 3 vết thương',
    'Booking created with the initial line only': 'Đã tạo lịch hẹn chỉ với dòng ban đầu',
    'Waiting for the nurse to accept': 'Đang chờ điều dưỡng chấp nhận',
    'Nurse accepted the visit': 'Điều dưỡng đã chấp nhận lượt khám',
    'Visit started': 'Đã bắt đầu lượt khám',
    'Clinical note saved': 'Đã lưu ghi chú lâm sàng',
    'Visit now lists both services': 'Lượt khám hiện có cả hai dịch vụ',
    'Nurse sees 3 wounds (350,000 ₫) + 1 glucose test (50,000 ₫)': 'Điều dưỡng thấy 3 vết thương (350.000 ₫) + 1 xét nghiệm đường huyết (50.000 ₫)',
    'Re-priced total 400,000 ₫, tax 0': 'Tổng đã tính lại 400.000 ₫, thuế 0',
    'đd_020 Change wound dressing < 5cm × 3 = 350,000 ₫': 'đd_020 Thay băng vết thương < 5cm × 3 = 350.000 ₫',
    'đd_220 Capillary blood glucose test × 1 = 50,000 ₫': 'đd_220 Kiểm tra đường huyết mao mạch × 1 = 50.000 ₫',
    'New total 400,000 ₫ (was 350,000 ₫)': 'Tổng mới 400.000 ₫ (trước là 350.000 ₫)',
    'Saved quote: 3 × wound dressing + 1 × glucose test, VAT 0, 400,000 ₫': 'Báo giá đã lưu: 3 × thay băng + 1 × đường huyết, VAT 0, 400.000 ₫',
    'History: service added during the visit by the nurse': 'Lịch sử: điều dưỡng thêm dịch vụ trong lượt khám',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await kit.step(next(), `Operations › Clients › ${client} › New booking`, `Vận hành › Khách hàng › ${client} › Đặt lịch mới`);
    await kit.area('Operations');
    await kit.click(c.sidebar(p, 'Clients'), 2500);
    await kit.type(p.locator('.o_searchview_input'), client, 300);
    await p.keyboard.press('Enter');
    await kit.hold(3000);
    const crow = p.locator('tr.o_data_row', { hasText: client }).locator('td[name=name]').first();
    await crow.waitFor({ timeout: 15000 });
    await kit.click(crow, 4000).catch(async () => { await kit.hold(1500); await kit.click(crow, 4000); });
    await kit.click(p.locator('.ws-hero button').filter({ hasText: /^\s*New booking\s*$/ }).filter({ visible: true }).first(), 4500);

    await kit.step(next(), 'TC-04: Home Visit, 1 hour, Hanoi, at the client’s home; only the services ordered at booking', 'TC-04: tại nhà, 1 giờ, Hà Nội; chỉ dịch vụ đặt ban đầu');
    await c.qbFill(kit, { service: 'Home Visit', duration: '1 hour', facility: 'HN_PK_PKGDVU', location: 'Patient Home' });
    await b.qbAddServices(kit, [{ q: 'Change wound dressing < 5cm', code: 'đd_020', qty: 3 }]);
    await kit.proof(p.locator('.qb-pt-footer').first().locator('xpath=..'), 'Initial service: đd_020 × 3 wounds',
      (t) => /Change wound dressing < 5cm/.test(t) && !/glucose/i.test(t), 2400);
    await c.qbPickDay(kit, DAY.k);
    const hm = await b.qbSlot(kit, TIMES);
    await kit.step(next(), `${DAY.monShort} ${DAY.day}, ${hm}; nurse ${nurse.name} assigned and leading`, `${DAY.day}/${DAY.month + 1}, ${hm}; điều dưỡng ${nurse.name} được phân công và phụ trách`);
    await kit.click(p.locator('.qb-staff-chip', { hasText: nurse.name }).first(), 800);
    await kit.select(c.qbGroup(p, 'Lead Staff'), nurse.name);
    const r = await b.qbCreate(kit);
    await kit.proof(r.done.locator('.qb-modal-quote'), 'Booking created with the initial line only',
      (t) => /Change wound dressing/.test(t) && /\b3\b/.test(t) && !/glucose/i.test(t), 2600);
    kit.records['Booking'] = `${r.bk} (${c.shownTime(DAY.d, hm)})`;
    await kit.click(p.locator('.qb-modal-confirm'), 4500);
    await kit.proof([p.locator('.ws-hero').first(), p.locator('.ws-next').first()], 'Waiting for the nurse to accept', (t) => t.includes(r.bk) && /Waiting for staff to accept/i.test(t), 2400);
    if (STOP === 'book') return;

    // ------------------------------------------------------------ nurse app
    await kit.switchUser(next(), nurse, true);
    await kit.step(next(), `Notifications: accept ${r.bk}`, `Thông báo: chấp nhận ${r.bk}`);
    await kit.click(p.locator('.notif-bell-btn').filter({ visible: true }).first(), 1500);
    const card = p.locator('.notif-card', { hasText: r.bk }).first();
    await kit.click(card.locator('.notif-btn-accept'), 3000);
    await kit.proof(p.locator('.notif-panel').first(), 'Nurse accepted the visit', async () => !(await p.locator('.notif-card', { hasText: r.bk }).count()), 1800);
    const close = p.locator('.notif-panel-close').filter({ visible: true }).first();
    if (await close.count()) await kit.click(close, 800);

    await kit.step(next(), `${DAY.monShort} ${DAY.day}: open the visit for ${client} (${hm})`, `${DAY.day}/${DAY.month + 1}: mở lượt khám của ${client} (${hm})`);
    await kit.click(p.locator('button.bk-rnd[title=Next]'), 3000);
    const visit = p.locator('.booking-card', { hasText: clientCode }).filter({ hasText: hm }).first();
    await kit.click(visit.locator('.booking-patient-name'), 2500);
    await kit.step(next(), 'At the visit: Start Service', 'Tại lượt khám: Bắt đầu dịch vụ');
    await kit.click(p.locator('button').filter({ hasText: /^\s*Start Service\s*$/ }).filter({ visible: true }).first(), 3500);
    await kit.proof(p.getByText(/^\s*in progress\s*$/i).filter({ visible: true }).first(), 'Visit started', /in progress/i);

    await kit.step(next(), 'The nurse also checks the blood glucose: Add service › Capillary blood glucose test (đd_220) × 1', 'Điều dưỡng đo thêm đường huyết: Thêm dịch vụ › Kiểm tra đường huyết mao mạch (đd_220) × 1');
    await kit.click(p.locator('button.btn-add-service').filter({ visible: true }).first(), 2000);
    const dlg = p.locator('.add-service-modal').filter({ visible: true }).first();
    await kit.type(dlg.getByPlaceholder('Search services by name or code...'), 'glucose', 2000);
    const row = dlg.locator('.add-service-row').filter({ hasText: 'Capillary blood glucose test' }).filter({ hasText: 'đd_220' }).first();
    await kit.type(row.locator('.add-service-qty'), '1', 500);
    await kit.click(row.locator('button').filter({ hasText: /Add/ }), 3500);
    await kit.proof(p.getByText(/^\s*Services:\s*$/).first().locator('xpath=..'), 'Visit now lists both services',
      (t) => /Change wound dressing < 5cm/.test(t) && /Capillary blood glucose test/.test(t), 2600);

    await kit.step(next(), 'Clinical Notes › Add New Clinical Note, then save it', 'Ghi chú lâm sàng › Thêm ghi chú mới, rồi lưu');
    await kit.click(p.locator('button').filter({ hasText: /Clinical Notes/ }).filter({ visible: true }).first(), 2500);
    await kit.click(p.locator('button').filter({ hasText: /Add New Clinical Note/ }).filter({ visible: true }).first(), 2500);
    await kit.type(p.getByPlaceholder('Enter clinical notes...'), note, 600);
    await kit.click(p.locator('button').filter({ hasText: /Confirm and Save/ }).filter({ visible: true }).first(), 3500);
    await kit.proof(p.getByText(note).first().locator('xpath=..'), 'Clinical note saved', note, 1800);
    await kit.click(p.locator('button').filter({ hasText: /^\s*close\s*$/ }).filter({ visible: true }).last(), 1500);

    await kit.step(next(), 'View service: both lines and the re-priced total', 'Xem dịch vụ: hai dòng và tổng tiền đã tính lại');
    await kit.click(p.locator('button').filter({ hasText: /View service/ }).filter({ visible: true }).first(), 3000);
    const modal = p.locator('.invoice-modal').filter({ visible: true }).first();
    await kit.proof(modal.locator('.invoice-items-container'), 'Nurse sees 3 wounds (350,000 ₫) + 1 glucose test (50,000 ₫)', async () => {
      const cards = await modal.locator('.invoice-item-card').allInnerTexts();
      const qty = await modal.locator('.invoice-item-card input[type=number]').evaluateAll((e) => e.map((x) => x.value));
      return cards.length === 2 && W.lines.every((l, i) => cards[i].includes(l.name) && b.has(cards[i], l.total)) && qty[0] === '3' && qty[2] === '1';
    }, 3000);
    await kit.proof(modal.locator('.invoice-totals'), 'Re-priced total 400,000 ₫, tax 0', (t) => b.has(t, W.total) && /Tax\s*0\b/.test(t), 2600);
    await kit.click(modal.locator('button').filter({ hasText: /^\s*Cancel\s*$/ }), 1200);
    if (STOP === 'nurse') return;

    // ------------------------------------------------------------ OM reopens the booking
    await kit.switchUser(next(), om, false);
    await kit.step(next(), `${r.bk} › Pricing: the initial and the visit-added lines`, `${r.bk} › Giá: dòng ban đầu và dòng thêm tại lượt khám`);
    await b.openBooking(kit, r.bk, true);
    await b.tab(kit, 'Pricing');
    const wrap = p.locator('.o_field_widget[name=pricing_breakdown_html]').filter({ visible: true }).first();
    for (const l of W.lines) {
      const rowP = wrap.locator('tbody tr').filter({ hasText: l.code }).first();
      await kit.proof(rowP, `${l.code} ${l.name} × ${l.qty} = ${fmt(l.total)} ₫`, async () => {
        const cells = await rowP.locator('td').allInnerTexts();
        return cells.length >= 6 && Number(cells[4].trim()) === l.qty && b.has(cells[5], l.total) && cells[0].includes(l.name);
      }, 2600);
    }
    await kit.proof(wrap.locator('tr').filter({ hasText: /^\s*Total/ }).last(), `New total ${fmt(W.total)} ₫ (was ${fmt(W.lines[0].total)} ₫)`, (t) => b.has(t, W.total), 2400);

    await kit.step(next(), 'Quick actions › View Quote: the saved quote', 'Thao tác nhanh › Xem báo giá: báo giá đã lưu');
    await kit.click(p.getByRole('button', { name: /View Quote/ }).first(), 4500);
    const qp = p.locator('.hfq-panel').filter({ visible: true }).first();
    await qp.locator('.hfq-card').first().waitFor({ timeout: 15000 });
    await kit.proof([qp.locator('.hfq-cards'), qp.locator('.hfq-totals')], 'Saved quote: 3 × wound dressing + 1 × glucose test, VAT 0, 400,000 ₫', async () => {
      const cards = await qp.locator('.hfq-card').allInnerTexts();
      const qty = await qp.locator('.hfq-qty__input').evaluateAll((e) => e.map((x) => x.value));
      const tot = await qp.locator('.hfq-totals').innerText();
      return cards.length === 2 && W.lines.every((l, i) => cards[i].includes(l.name) && b.has(cards[i], l.total) && qty[i] === String(l.qty))
        && /Taxes\s*0\b/.test(tot) && b.has((tot.match(/Total\s*([\d.,]+)/) || [])[1] ? ' ' + tot.match(/Total\s*([\d.,]+)/)[1] : '', W.total);
    }, 3200);
    await kit.click(p.locator('.modal-content button').filter({ hasText: /^\s*Discard\s*$/ }).last(), 2500);
    await kit.proof(p.locator('.o-mail-Thread, .o-mail-Chatter').first(), 'History: service added during the visit by the nurse',
      (t) => /Service added during the visit by/i.test(t) && t.includes(nurse.name), 2600);
  },
};
