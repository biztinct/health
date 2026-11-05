// AR-04 Payment after service with a remaining balance: the client of visit v2 (invoice
// 180,000 ₫, Pay Later in AR-01) pays 80,000 ₫ in cash after the visit. Finance records it on
// that invoice: 100,000 ₫ stays due and the invoice shows the one linked payment.
// AR04_STOP=dialog  practice: fills the payment dialog, then Discard (nothing recorded).
// AR04_INV=INV/...  practice/rehearsal on another invoice (default: the state's inv2).
// AR_PART=after     only the after-payment checks (rehearse on an already part-paid invoice).
const r = require('./ar_common');
const { m } = r;
const fin = r.users.finance;
const cl = r.client;
const STOP = process.env.AR04_STOP || '';
const PART = process.env.AR_PART || '';
const PAID = 80000;
const TOTAL = 180000;

module.exports = {
  meta: {
    id: 'AR-04', title: 'Part payment after the visit leaves 100,000 due', short: 'Part payment after service',
    title_vi: 'Thanh toán một phần sau lượt khám, còn nợ 100.000',
    criterion: 'Receive a payment after service delivery and allocate it to the specified invoice. Show the remaining balance after a partial collection and retain the linked payment record. For the planned example, an invoice of 180,000 VND less 80,000 VND received leaves 100,000 VND due.',
    data: `TC-03: invoice ${r.load().ar04inv || r.load().inv2 || '(from AR-01)'} for ${cl.name} (${cl.code}), 180,000 ₫ (visit ${(r.load().v2 || {}).bk || '?'}, Pay Later); after the visit the client pays 80,000 ₫ in cash, recorded by Finance (${fin.login}) on that invoice. All data is fictional.`,
    expected: 'Partial payment leaves exactly 100,000 due after service.',
    ...fin,
  },
  proofVi: { 'One linked payment': 'Một khoản thanh toán được liên kết' },

  async run(kit) {
    const p = kit.page;
    const st = r.load();
    const V = kit._proofVi;
    const inv = process.env.AR04_INV || st.ar04inv || st.inv2;
    if (!inv) throw new Error('no invoice (inv2) in the AR state file: run AR-01 first');
    let n = 1;
    const next = () => ++n;
    await kit.login();
    const outOf = async (row) => r.num(await row.locator('td[name=amount_residual], td[name=outstanding_amount], td[name=amount_residual_signed]').first().innerText().catch(() => '0'));

    if (PART !== 'after') {
      // ---------------------------------------------------------- before: 180,000 ₫ owed
      await kit.step(next(), `Finance › Receivables: ${cl.name}`, `Tài chính › Phải thu: ${cl.name}`);
      await kit.area('Finance');
      await kit.click(r.sidebar(p, 'Receivables'), 3000);
      await r.searchClient(kit);
      const ar = r.invRow(p, inv);
      await ar.waitFor({ timeout: 15000 });
      const L0 = `Before: ${inv} owes ${r.fmt(TOTAL)}, nothing paid yet`;
      V[L0] = `Trước: ${inv} còn nợ ${r.fmtVi(TOTAL)}, chưa trả`;
      await kit.proof(ar, L0, async () => (await outOf(ar)) === TOTAL || (STOP && (await outOf(ar)) > 0));

      // ---------------------------------------------------------- Finance records the cash
      await kit.step(next(), `Finance › Invoices › ${inv} › Receive Payment`, `Tài chính › Hóa đơn › ${inv} › Nhận thanh toán`);
      await kit.click(r.sidebar(p, 'Invoices'), 3000);
      await r.searchClient(kit);
      const row = r.invRow(p, inv);
      await row.waitFor({ timeout: 15000 });
      await kit.click(row.getByRole('button', { name: /Receive Payment/ }), 3000);
      const dlg = p.locator('.modal-content').filter({ visible: true }).last();
      await dlg.waitFor({ timeout: 15000 });
      await kit.step(next(), `After the visit the client pays ${r.fmt(PAID)} in cash: journal Cash, amount ${r.fmt(PAID)}`, `Sau lượt khám khách hàng trả ${r.fmtVi(PAID)} tiền mặt: sổ Tiền mặt, số tiền ${r.fmtVi(PAID)}`);
      await kit.type(dlg.locator('.o_field_widget[name=journal_id] input').first(), 'Cash', 1200);
      await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: /^\s*Cash\s*$/ }).first(), 1500);
      await kit.type(dlg.locator('.o_field_widget[name=amount] input').first(), String(PAID), 900);
      await dlg.locator('.modal-title, .modal-header').first().click().catch(() => {});   // leave the field so the difference is shown
      await kit.hold(1500);
      const L1 = `Payment: ${r.fmt(PAID)}, Cash, today, for ${inv}`;
      V[L1] = `Thanh toán: ${r.fmtVi(PAID)}, Tiền mặt, hôm nay, cho ${inv}`;
      await kit.proof(dlg.locator('.modal-body').first(), L1, async () => {
        const v = await kit.fieldValues(['amount', 'payment_date', 'communication', 'journal_id'], dlg);
        const day = r.today();
        return r.num(v.amount) === PAID && v.payment_date.includes(`${day.mon} ${day.day}`) && v.communication.includes(inv) && v.journal_id === 'Cash';
      });
      if (STOP === 'dialog') { await kit.click(dlg.locator('button', { hasText: /^\s*Discard\s*$/ }).first(), 1500); return; }

      await kit.step(next(), 'Receive Payment', 'Nhận thanh toán');
      await kit.click(dlg.locator('button', { hasText: /^\s*Receive Payment\s*$/ }).first(), 4000);
      r.save({ ar04: { inv, paidAt: new Date().toISOString() } });
      await p.locator('.o_form_sheet').filter({ hasText: 'Amount' }).filter({ visible: true }).first().waitFor({ timeout: 20000 }).catch(() => {});
      await kit.hold(1500);
      const pform = p.locator('.o_form_view').filter({ visible: true }).first();
      let payName = '';
      const LP = `Payment recorded: ${r.fmt(PAID)}, Cash, for ${inv} (1 invoice)`;
      V[LP] = `Đã ghi nhận thanh toán: ${r.fmtVi(PAID)}, Tiền mặt, cho ${inv} (1 hóa đơn)`;
      await kit.proof(pform, LP, async (t) => {
        const inputs = (await pform.locator('input, textarea').evaluateAll((es) => es.map((e) => e.value))).join(' ');
        const all = t + ' ' + inputs;
        payName = (all.match(/P[A-Z]{3}\d\/\d{4}\/\d+/) || [''])[0];
        const head = await p.locator('.o_control_panel').filter({ visible: true }).first().innerText().catch(() => '');
        return r.money(PAID).test(all) && all.includes(inv) && /Cash/.test(all) && /\b1\s*Invoice/.test(head + ' ' + t);
      });
      if (payName) { kit.records['Payment'] = payName; r.save({ pay2: payName }); }
      await kit.step(next(), `Back to Invoices: ${inv}`, `Quay lại Hóa đơn: ${inv}`);
      await r.crumb(kit, /^\s*Invoices\s*$/);
      if (!(await r.invRow(p, inv).count())) await r.searchClient(kit);
    } else {
      await r.invoicesFor(kit, next(), `Rehearsal: Finance › Invoices: ${cl.name}`, `Diễn tập: Tài chính › Hóa đơn: ${cl.name}`);
    }

    // ------------------------------------------------------------ after: 100,000 ₫ due
    const row = r.invRow(p, inv);
    await row.waitFor({ timeout: 15000 });
    const L3 = `${inv}: Partial, ${r.fmt(TOTAL - PAID)} still due`;
    V[L3] = `${inv}: Trả một phần, còn nợ ${r.fmtVi(TOTAL - PAID)}`;
    await kit.proof(row, L3, (t) => /Partial/.test(t) && /\b100,000\.00\b/.test(t) && /\b180,000\.00\b/.test(t));

    await kit.step(next(), `Open ${inv}`, `Mở ${inv}`);
    await r.openInvoice(kit, inv);
    const L4 = `Total ${r.fmt(TOTAL)} − paid ${r.fmt(PAID)} = ${r.fmt(TOTAL - PAID)} due`;
    V[L4] = `Tổng ${r.fmtVi(TOTAL)} − đã trả ${r.fmtVi(PAID)} = còn nợ ${r.fmtVi(TOTAL - PAID)}`;
    await kit.proof(r.invHead(p), L4, (t) => { const h = r.headNums(t); return t.includes(inv) && /PARTIAL/i.test(t) && !!h && h.total === TOTAL && h.paid === PAID && h.due === TOTAL - PAID; });
    const payBtn = r.smartBtn(p, /Payments?/);
    await kit.proof(payBtn, 'One linked payment', (t) => /\b1\b/.test(t));
    await kit.step(next(), 'Open the linked payment', 'Mở khoản thanh toán được liên kết');
    await kit.click(payBtn, 4000);
    await p.locator('.o_form_sheet').filter({ hasText: 'Amount' }).filter({ visible: true }).first().waitFor({ timeout: 20000 }).catch(() => {});
    await kit.hold(1500);
    const pform = p.locator('.o_form_view').filter({ visible: true }).first();
    const L5 = `The payment: ${r.fmt(PAID)} cash, matched to ${inv}`;
    V[L5] = `Khoản thanh toán: ${r.fmtVi(PAID)} tiền mặt, khớp với ${inv}`;
    await kit.proof(pform, L5, async (t) => {
      const inputs = (await pform.locator('input, textarea').evaluateAll((es) => es.map((e) => e.value))).join(' ');
      const all = t + ' ' + inputs;
      return r.money(PAID).test(all) && all.includes(inv) && /Cash/.test(all);
    });

    await kit.step(next(), `Finance › Receivables again: ${cl.name}`, `Tài chính › Phải thu lần nữa: ${cl.name}`);
    await r.backToRail(kit);
    await kit.area('Finance');
    await kit.click(r.sidebar(p, 'Receivables'), 3000);
    await r.searchClient(kit);
    const ar2 = r.invRow(p, inv);
    await ar2.waitFor({ timeout: 15000 });
    const L6 = `Receivables: ${inv} ${r.fmt(TOTAL - PAID)} outstanding, ${r.fmt(PAID)} paid`;
    V[L6] = `Phải thu: ${inv} còn ${r.fmtVi(TOTAL - PAID)}, đã trả ${r.fmtVi(PAID)}`;
    await kit.proof(ar2, L6, async (t) => (await outOf(ar2)) === TOTAL - PAID && r.money(PAID).test(t));
  },
};
