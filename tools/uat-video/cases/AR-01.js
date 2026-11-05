// AR-01 Invoice transaction: completing a visit posts the service invoice and creates the
// matching receivable. The nurse completes v2 (Online internal examination 200,000 ₫ less the
// TC-03 10% discount = 180,000 ₫) with Pay Later; Finance then checks the 180,000 ₫ invoice and
// the 500,000 ₫ invoice of v1 (AR-02): client, VND, source booking and quote, line, VAT 0,
// total, posted, amount due, the Receivables screen and the receivable entries in the AR log.
// AR01_STOP=quote   practice: types the discount, then cancels the quote window (nothing saved).
// AR01_STOP=wizard  practice: stops in the payment window (Cancel).
// AR_PART=office    skip the nurse part (rehearse the office checks on the state file's visits).
const r = require('./ar_common');
const { m, a } = r;
const nurse = r.users.nurse;
const fin = r.users.finance;
const cl = r.client;
const v = r.VISITS.v2;
const v1 = r.VISITS.v1;
const STOP = process.env.AR01_STOP || '';
const PART = process.env.AR_PART || '';
const CHECKED = 'Checked with the client: online internal examination, 10% discount as agreed (TC-03)';
const DREASON = 'TC-03: 10% discount agreed with the client';
const REASON = 'UAT ONLY - fictional test visit; the client will call if he needs another visit';

module.exports = {
  meta: {
    id: 'AR-01', title: 'Posted invoices create the matching receivables', short: 'Invoice and receivable',
    title_vi: 'Hóa đơn ghi sổ tạo công nợ phải thu tương ứng',
    criterion: 'Posting a service invoice must create the corresponding receivable for the correct client, currency and source booking. Compare invoice lines, total, tax, posting state and outstanding amount with the client case and ensure the transaction is traceable in the accounting records.',
    data: `TC-03: today’s clinic visit ${(r.load().v2b || r.load().v2 || {}).bk || '(from setup)'} for ${cl.name} (${cl.code}), ${v.product} (${v.code}) 200,000 ₫ less 10% = 180,000 ₫, completed by ${nurse.login} with Pay Later; TC-01: visit ${(r.load().v1 || {}).bk || '(from setup)'}, ${v1.product} (${v1.code}) 500,000 ₫, completed with cash in AR-02 (invoice ${r.load().inv1 || '?'}). Price list “Client UAT 20261013 V01.01 (VND)”. Finance checks as ${fin.login}. All data is fictional.`,
    expected: '500,000 and 180,000 invoices post and create matching receivables.',
    ...nurse,
  },
  proofVi: {
    'Payment timing: Pay Later': 'Thời điểm thanh toán: Trả sau',
    'Create Invoice Now ticked': 'Đã chọn Tạo hóa đơn ngay',
    'Amount 180,000 ₫, payment later': 'Số tiền 180.000 ₫, thanh toán sau',
    'Visit completed in the nurse app': 'Lượt khám đã hoàn thành trên ứng dụng điều dưỡng',
  },

  async run(kit) {
    const p = kit.page;
    const st = r.load();
    const V = kit._proofVi;
    const key = st.v2b ? 'v2b' : 'v2';   // v2b: the re-take visit
    if (!st[key] || !st[key].id) throw new Error('no v2 in the AR state file: run the setup first');
    const visit = st[key];
    let n = 0;
    const next = () => ++n;
    const pops = r.catchPopups(kit);

    if (PART !== 'office') {
      // ---------------------------------------------------------- the nurse completes v2
      await r.asNurse(kit, next());
      await kit.step(next(), `At the clinic: open today’s visit for ${cl.name} (${visit.hm})`, `Tại phòng khám: mở lượt khám hôm nay của ${cl.name} (${visit.hm})`);
      await r.startIfNeeded(kit, next, visit, v);
      const { wiz } = await r.quoteAndWizard(kit, next, v, { checked: CHECKED, discountReason: DREASON, stop: STOP });
      if (STOP === 'quote') return;
      await kit.step(next(), 'Payment: the client will pay later; create the invoice now', 'Thanh toán: khách hàng trả sau; tạo hóa đơn ngay');
      await kit.click(wiz.locator('label', { hasText: /^\s*Pay Later\s*$/ }).first(), 900);
      const invoiceNow = wiz.locator('label', { hasText: 'Create Invoice Now' }).locator('input[type=checkbox]').first();
      if (!(await invoiceNow.isChecked())) await kit.click(invoiceNow, 600);
      // the window is taller than the tablet screen: prove one part at a time
      await kit.proof(wiz.locator('.form-section').first(), 'Payment timing: Pay Later', async () => wiz.locator('input[type=radio][value=pay_later]').isChecked(), 2200);
      await kit.proof(wiz.locator('label', { hasText: 'Create Invoice Now' }).first(), 'Create Invoice Now ticked', async () => invoiceNow.isChecked(), 2200);
      await kit.proof(wiz.locator('.info-grid').first(), 'Amount 180,000 ₫, payment later', (t) => r.money(v.total).test(t) && /Later/.test(t), 3000);
      if (STOP === 'wizard') { await kit.click(wiz.locator('button', { hasText: /^\s*Cancel\s*$/ }).first(), 1000); return; }

      await kit.step(next(), 'Complete Service', 'Hoàn thành dịch vụ');
      const before = pops.length;
      await kit.click(wiz.locator('button', { hasText: /Complete Service/ }).last(), 6000);
      r.save({ [key]: { ...visit, completedAt: new Date().toISOString() } });
      const said = pops.slice(before).join(' / ');
      if (said) await kit.note(`The app’s pop-up message: “${said}”`, `Thông báo bật lên của ứng dụng: “${said}”`);
      await r.closeQuestion(kit, next, pops, REASON);
      await m.card(p, visit).waitFor({ timeout: 15000 }).catch(() => {});
      await kit.proof(m.card(p, visit), 'Visit completed in the nurse app', (t) => /completed/i.test(t) && t.includes(cl.name));
      await r.asStaff(kit, next(), fin);
    } else {
      await kit.page.setViewportSize(m.DESKTOP);
      await kit.switchUser(next(), fin, false);
    }

    // ------------------------------------------------------------ the 180,000 ₫ invoice
    const inv2 = await reviewInvoice(kit, next, visit, v, {
      lineVi: `${v.productVi} × 1 lượt, 200.000 ₫, giảm 10% kèm lý do = 180.000 ₫`,
      lineEn: `${v.product} × 1 visit at 200,000 ₫, Disc. 10% with the reason = 180,000 ₫`,
      lineOk: async (t, row) => {
        const cell = async (n) => ((await row.locator(`td[name=${n}]`).first().innerText().catch(() => '')) || '').trim();
        return /bs_030/.test(t) && /\b1\.00\b/.test(t) && /Visit/.test(t) && Math.round(parseFloat((await cell('price_unit')).replace(/[^\d.]/g, ''))) === v.price
          && /^10(\.0+)?$/.test(await cell('discount')) && (await cell('discount_reason')).startsWith(DREASON.slice(0, 12))
          && r.money(v.total).test(await cell('price_subtotal'));
      },
      due: v.total, paid: 0,
    });
    if (PART !== 'office') r.save({ inv2 });
    kit.records['Invoice (180,000 ₫)'] = inv2;

    await kit.step(next(), `Finance › Receivables: amounts owed by ${cl.name}`, `Tài chính › Phải thu: công nợ của ${cl.name}`);
    await kit.click(r.sidebar(p, 'Receivables'), 3000);
    await r.searchClient(kit);
    const arRow = r.invRow(p, inv2);
    await arRow.waitFor({ timeout: 15000 }).catch(() => {});
    const LR = `Receivable: ${inv2} owes 180,000 ₫, nothing paid, from quote ${visit.so || ''}`.replace(/ ,/, ',').trim();
    V[LR] = `Phải thu: ${inv2} còn nợ 180.000 ₫, chưa trả, từ báo giá ${visit.so || ''}`.trim();
    await kit.proof(arRow, LR, async () => {
      const out = r.num(await arRow.locator('td[name=amount_residual], td[name=outstanding_amount], td[name=amount_residual_signed]').first().innerText().catch(() => '0'));
      const t = await arRow.innerText();
      return out === v.total && t.includes(cl.name) && (!visit.so || t.includes(visit.so));
    });

    // ------------------------------------------------------------ the 500,000 ₫ invoice (AR-02)
    const st2 = r.load();
    if (st2.v1 && st2.v1.bk) {
      const inv1 = await reviewInvoice(kit, next, st2.v1, v1, {
        lineVi: `${v1.productVi} × 1 lượt, 500.000 ₫`,
        lineEn: `${v1.product} × 1 visit at 500,000 ₫`,
        lineOk: (t) => /bs_020/.test(t) && /\b1\.00\b/.test(t) && /Visit/.test(t) && r.money(v1.total).test(t),
        due: 0, paid: v1.total, paidNote: true,
      });
      kit.records['Invoice (500,000 ₫)'] = inv1;

      // ---------------------------------------------------------- both receivables in the log
      await kit.step(next(), 'Finance › Receivables › AR Transactions: the receivable entries', 'Tài chính › Phải thu › Giao dịch AR: các bút toán phải thu');
      await kit.click(r.sidebar(p, 'Receivables'), 3000);
      await kit.click(p.locator('button, a').filter({ hasText: /^\s*AR Transactions\s*$/ }).filter({ visible: true }).first(), 3000);
      await p.mouse.move(760, 400, { steps: 12 });
      await r.searchClient(kit);
      for (const [vis, amt, label] of [[visit, v.total, '180,000'], [st2.v1, v1.total, '500,000']]) {
        const row = p.locator('tr.o_data_row').filter({ hasText: `(${vis.bk})` }).filter({ hasText: /Invoice/ }).filter({ hasText: r.money(amt) }).first();
        await row.waitFor({ timeout: 15000 }).catch(() => {});
        const L = `Invoice ${vis.bk}: debit Account Receivable ${label} ₫, credit sales`;
        V[L] = `Hóa đơn ${vis.bk}: Nợ Phải thu khách hàng ${label.replace(/,/g, '.')} ₫, Có doanh thu`;
        await kit.proof(row, L, (t) => /Account Receivable\s+Product Sales|Account Receivable\s+\S.*Sales/.test(t) && /Posted/.test(t) && r.money(amt).test(t));
      }
    }
  },
};

// Bookings › the visit › Execution › Quote & Invoice › open the invoice; prove posting, client,
// VND, source booking and quote, the line, tax 0 and total, and the amounts due / paid.
async function reviewInvoice(kit, next, visit, v, o) {
  const p = kit.page;
  const V = kit._proofVi;
  await r.a.openBooking(kit, next(), visit.bk, `Operations › Bookings › open ${visit.bk}`, `Vận hành › Lịch hẹn › mở ${visit.bk}`);
  await kit.step(next(), 'Execution tab: Quote & Invoice', 'Thẻ Thực hiện: Báo giá & Hóa đơn');
  await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Execution\s*$/ }).first(), 2200);
  const qi = p.locator('.vu-detail-card[name=quote_invoice_card]').filter({ visible: true }).first();
  await qi.waitFor({ timeout: 15000 });
  const invF = qi.locator('.o_field_widget[name=invoice_id]').first();
  const inv = (((await invF.innerText().catch(() => '')) || '').match(/INV\/\d{4}\/\d+/) || [''])[0];
  const so = (((await qi.locator('.o_field_widget[name=sale_order_id]').first().innerText().catch(() => '')) || '').match(/S\d{4,}/) || [''])[0];
  visit.so = so;
  const LB = `Booking ${visit.bk}: quote ${so} invoiced as ${inv}, posted`;
  V[LB] = `Lịch hẹn ${visit.bk}: báo giá ${so} đã lập hóa đơn ${inv}, đã ghi sổ`;
  await kit.proof(qi, LB, (t) => !!inv && !!so && /Posted/.test(t));

  await kit.step(next(), `Open the invoice ${inv}`, `Mở hóa đơn ${inv}`);
  await kit.click(invF.locator('a, .o_form_uri, span').first(), 4000);
  await p.locator('.o_field_widget[name=invoice_line_ids]').first().waitFor({ timeout: 15000 });
  await kit.hold(1200);
  const status = p.locator('.o_statusbar_status').filter({ visible: true }).first();
  const cur = p.locator('.o_field_widget[name=currency_id]').filter({ visible: true }).first();
  const LP = `${inv} for ${r.client.name}: posted, currency VND`;
  V[LP] = `${inv} cho ${r.client.name}: đã ghi sổ, tiền tệ VND`;
  await kit.proof([p.locator('.o_field_widget[name=partner_id]').filter({ visible: true }).first(), cur, status], LP, async (t) =>
    t.includes(r.client.name) && /VND/.test(t) && (await status.locator('button.active, .o_arrow_button_current, [aria-checked=true]').filter({ hasText: /Posted/ }).count()) > 0);
  if (v.disc) {
    // the Disc.% column is optional on the invoice lines: show it
    await kit.step(next(), 'Invoice lines: show the Disc.% column', 'Dòng hóa đơn: hiển thị cột Giảm %');
    const il = p.locator('.o_field_widget[name=invoice_line_ids]').filter({ visible: true }).first();
    await kit.click(il.locator('.o_optional_columns_dropdown_toggle, .o_optional_columns_dropdown button').first(), 1200);
    const item = p.locator('.o-dropdown--menu .dropdown-item, .o_optional_columns_dropdown .dropdown-item').filter({ hasText: /^\s*Disc\.%\s*$/ }).filter({ visible: true }).first();
    const box = item.locator('input[type=checkbox]').first();
    if (!((await box.count()) && (await box.isChecked()))) await kit.click(item, 1500);
    await p.keyboard.press('Escape');
    await p.mouse.move(760, 400, { steps: 12 });
    await kit.hold(1000);
  }
  const lines = p.locator('.o_field_widget[name=invoice_line_ids] tr.o_data_row').filter({ visible: true });
  V[o.lineEn] = o.lineVi;
  await kit.proof(lines.first(), o.lineEn, async (t) => (await lines.count()) === 1 && (await o.lineOk(t, lines.first()))
    && !((await lines.first().locator('td[name=tax_ids]').innerText().catch(() => '')).trim()));
  // no tax line (or a 0 one): the amount before tax equals the total
  const LT = o.due
    ? `VAT 0, total ${r.fmt(v.total)}, amount due ${r.fmt(o.due)}`
    : `VAT 0, total ${r.fmt(v.total)}, paid in full at the visit (AR-02), amount due 0`;
  V[LT] = o.due
    ? `Thuế GTGT 0, tổng ${r.fmtVi(v.total)}, còn phải thu ${r.fmtVi(o.due)}`
    : `Thuế GTGT 0, tổng ${r.fmtVi(v.total)}, đã trả đủ tại lượt khám (AR-02), còn phải thu 0`;
  await kit.proof(r.footer(p), LT, (t) => {
    const f = r.footNums(t);
    const paid = f.paid.reduce((s, x) => s + x, 0);
    return f.untaxed === v.total && f.total === v.total && (f.tax === null || f.tax === 0) && f.due === o.due && paid === o.paid;
  });
  const crumbs = p.locator('.o_breadcrumb').filter({ visible: true }).first();
  const soBtn = r.smartBtn(p, /Sale Orders?/);
  const LS = `Source: booking ${visit.bk} and quote ${so}`;
  V[LS] = `Nguồn: lịch hẹn ${visit.bk} và báo giá ${so}`;
  await kit.proof([crumbs, soBtn], LS, (t) => t.includes(`(${visit.bk})`) && t.includes(inv) && t.includes(so) && /(\b1\s*Sale Orders?|Sale Orders?\s*1\b)/.test(t));
  return inv;
}
