// MB-08 Invoice issued from the completed nurse-app visit: one posted invoice, linked to the
// booking, quote and client, with the TC-13 line (injection × 2 at 105,000 ₫), no discount,
// tax 0, total 210,000 ₫. Reviewed by Finance (the Owner account).
const a = require('./as_common');
const m = require('./mb_common');
const fin = m.users.finance;
const cl = m.client;
const T = m.TC;

module.exports = {
  meta: {
    id: 'MB-08', title: 'Invoice issued from the nurse-app visit', short: 'Mobile invoice issued',
    title_vi: 'Hóa đơn được phát hành từ lượt khám trên ứng dụng điều dưỡng',
    criterion: 'The invoice is issued from the completed mobile visit using the verified quote. It links to the correct client and booking, has the expected service lines, discount and tax, and matches the client total without duplicate invoicing.',
    data: `Today’s visit ${m.load().bk || '(from MB-02)'} for ${cl.name} (${cl.code}), completed in the nurse app with “Create Invoice Now” (MB-07); expected TC-13: ${T.code} × ${T.qty} at 105,000 ₫, no discount, tax 0, total 210,000 ₫`,
    expected: 'Mobile completion issues one correct linked invoice.',
    ...fin,
  },
  proofVi: {
    'Booking: invoice created and posted, quote invoiced': 'Lịch hẹn: hóa đơn đã tạo và ghi sổ, báo giá đã lập hóa đơn',
    'Invoice for Đặng Thị Quỳnh, posted': 'Hóa đơn cho Đặng Thị Quỳnh, đã ghi sổ',
    'Line: injection × 2 at 105,000 ₫ = 210,000 ₫, no discount': 'Dòng: tiêm × 2, 105.000 ₫ = 210.000 ₫, không giảm giá',
    'Tax 0, total 210,000 ₫ (the client total)': 'Thuế 0, tổng 210.000 ₫ (tổng của khách hàng)',
    'Linked to the booking and its quote': 'Liên kết với lịch hẹn và báo giá',
    'Only one invoice for this visit': 'Chỉ một hóa đơn cho lượt khám này',
  },

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.id || !st.completedAt) throw new Error('no completed visit in mb_state.json: run MB-07 first');
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ------------------------------------------------------------ from the booking
    await m.openBooking(kit, next(), st.bk, `Operations › Bookings › open the visit ${st.bk}`, `Vận hành › Lịch hẹn › mở lượt khám ${st.bk}`);
    await kit.step(next(), 'Execution tab: Quote & Invoice', 'Thẻ Thực hiện: Báo giá & Hóa đơn');
    await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Execution\s*$/ }).first(), 2200);
    const qi = p.locator('.vu-detail-card[name=quote_invoice_card]').filter({ visible: true }).first();
    const invF = qi.locator('.o_field_widget[name=invoice_id]').first();
    const invText = ((await invF.innerText().catch(() => '')) || '').trim();
    const inv = (invText.match(/INV\/\d{4}\/\d+/) || [''])[0];
    const so = ((await qi.locator('.o_field_widget[name=sale_order_id]').first().innerText().catch(() => '')) || '').trim();
    await kit.proof(qi, 'Booking: invoice created and posted, quote invoiced', (t) => !!inv && /Posted/.test(t) && t.includes(so) && !!so);
    m.save({ invoice: inv, quote: so });
    kit.records['Invoice'] = inv;

    await kit.step(next(), `Open the invoice ${inv}`, `Mở hóa đơn ${inv}`);
    await kit.click(invF.locator('a, .o_form_uri, span').first(), 4000);
    await p.locator('.o_field_widget[name=invoice_line_ids]').first().waitFor({ timeout: 15000 });
    await kit.hold(1200);
    await kit.proof([p.locator('.o_form_view').getByText(inv, { exact: true }).filter({ visible: true }).first(),
      p.locator('.o_field_widget[name=partner_id]').filter({ visible: true }).first(), p.locator('.o_statusbar_status').filter({ visible: true }).first()],
    'Invoice for Đặng Thị Quỳnh, posted', (t) => t.includes(inv) && t.includes(cl.name) && t.includes(cl.address) && /Posted/.test(t));
    const lines = p.locator('.o_field_widget[name=invoice_line_ids] tr.o_data_row').filter({ visible: true });
    await kit.proof(lines.first(), 'Line: injection × 2 at 105,000 ₫ = 210,000 ₫, no discount', async (t) =>
      (await lines.locator('td[name=price_subtotal]').allInnerTexts()).filter((x) => x.trim()).length === 1 && /[dđ]d_070_tphcm/.test(t) && /\b2(\.00)?\b/.test(t) && m.money(T.unit).test(t) && m.money(T.total).test(t));
    await kit.proof(p.locator('.o_field_widget[name=tax_totals]').filter({ visible: true }).first(), 'Tax 0, total 210,000 ₫ (the client total)',
      (t) => m.money(T.total).test(t) && (!/Tax/.test(t) || /Tax[^₫]*?\b0\s*₫/.test(t)));
    const crumbs = p.locator('.o_breadcrumb').filter({ visible: true }).first();
    const soBtn = p.locator('button').filter({ hasText: /Sale Orders/ }).filter({ visible: true }).first();
    await kit.proof([crumbs, soBtn], 'Linked to the booking and its quote', (t) =>
      t.includes(`(${st.bk})`) && t.includes(inv) && t.includes(`(${so})`) && /(\b1\s*Sale Orders|Sale Orders\s*1\b)/.test(t));

    // ------------------------------------------------------------ no duplicate
    await kit.step(next(), `Finance › Invoices: all invoices for ${cl.name}`, `Tài chính › Hóa đơn: mọi hóa đơn của ${cl.name}`);
    await kit.area('Finance');
    await kit.click(require('./common').sidebar(p, 'Invoices'), 3000);
    await searchPatient(kit, cl.name);
    const rows = p.locator('tr.o_data_row').filter({ visible: true });
    const dd = new Date(new Date(st.completedAt).getTime() + 7 * 3600e3);
    const dShown = `${dd.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })} ${dd.getUTCDate()}`;
    await kit.proof(p.locator('.o_list_renderer').filter({ visible: true }).first(), 'Only one invoice for this visit', async () => {
      const all = await rows.allInnerTexts();
      const sameDay = all.filter((r) => new RegExp(`\\b${dShown}\\b`).test(r));
      return sameDay.length === 1 && sameDay[0].includes(inv) && all.filter((r) => r.includes(inv)).length === 1;
    });
  },
};

// Finance › Invoices: search the client by name.
async function searchPatient(kit, name) {
  const p = kit.page;
  await kit.type(p.locator('.o_searchview_input').filter({ visible: true }).first(), name, 1500);
  await p.keyboard.press('Enter');   // the client's name is the first search field
  await kit.hold(3000);
}
module.exports.searchPatient = searchPatient;
