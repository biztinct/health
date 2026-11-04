// MB-09 Accounts receivable: the nurse-app invoice (client pays later) raises the client's amount
// due by 210,000 ₫; Finance records the client's bank transfer and the amount due drops back.
// MB09_STOP=dialog stops at the payment dialog (practice: Discard, nothing recorded).
const c = require('./common');
const m = require('./mb_common');
const { searchPatient } = require('./MB-08');
const fin = m.users.finance;
const cl = m.client;
const T = m.TC;
const STOP = process.env.MB09_STOP || '';

const num = (s) => Number(String(s).replace(/[^\d]/g, '')) || 0;
const fmt = (n) => `${n.toLocaleString('en-US')} ₫`;

module.exports = {
  meta: {
    id: 'MB-09', title: 'Receivables raised by the invoice and reduced by the payment', short: 'Mobile receivables',
    title_vi: 'Công nợ phải thu tăng theo hóa đơn và giảm theo thanh toán',
    criterion: 'The mobile invoice and payment workflow updates accounts receivable: posting the invoice creates the amount due; collecting payment reduces it by the amount received, consistently and without duplicate allocation.',
    data: `Invoice ${m.load().invoice || '(from MB-08)'} for ${cl.name} (${cl.code}), 210,000 ₫, issued at the nurse-app completion with “Pay Later”; the client pays 210,000 ₫ by bank transfer, recorded by Finance (${fin.login})`,
    expected: 'AR increases for invoice and decreases by payment without duplicate entries.',
    ...fin,
  },
  proofVi: {},

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.invoice) throw new Error('no invoice in mb_state.json: run MB-08 first');
    const inv = st.invoice;
    const amount = st.invoiceTotal || T.total;
    const V = kit._proofVi;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    let others = 0;
    if (process.env.MB09_REHEARSE) {
      // Rehearsal of the after-payment steps on the already-paid invoice (view only).
      await kit.step(next(), 'Rehearsal: open the paid invoice', 'Diễn tập: mở hóa đơn đã thanh toán');
      await kit.area('Finance');
      await arFor(kit);
      others = (await arRows(p)).filter((r) => !r.text.includes(inv)).reduce((s, r) => s + r.out, 0);
      await kit.click(c.sidebar(p, 'Invoices'), 3000);
      await searchPatient(kit, cl.name);
      await kit.click(p.locator('tr.o_data_row', { hasText: inv }).first().locator('td').nth(3), 4000);
      await p.locator('.fin-invoice-header').first().waitFor({ timeout: 15000 }).catch(() => {});
    } else {
      // ------------------------------------------------------------ before the payment
      await kit.step(next(), `Finance › Receivables: amounts due for ${cl.name}`, `Tài chính › Phải thu: công nợ của ${cl.name}`);
      await kit.area('Finance');
      await arFor(kit);
      const before = await arRows(p);
      others = before.filter((r) => !r.text.includes(inv)).reduce((s, r) => s + r.out, 0);
      const L1 = `The invoice adds ${fmt(amount)} due: ${fmt(others + amount)} in total`;
      V[L1] = `Hóa đơn cộng thêm ${amount.toLocaleString('vi-VN')} ₫ phải thu: tổng ${(others + amount).toLocaleString('vi-VN')} ₫`;
      await kit.proof([arRow(p, inv), arFoot(p)], L1, async () => {
        const r = before.find((x) => x.text.includes(inv));
        return !!r && r.out === amount && (await footOut(p)) === others + amount;
      });
      kit.records['Amount due before payment'] = fmt(others + amount);

      // ------------------------------------------------------------ Finance records the bank transfer
      await kit.step(next(), `Finance › Invoices › ${inv} › Receive Payment`, `Tài chính › Hóa đơn › ${inv} › Nhận thanh toán`);
      await kit.click(c.sidebar(p, 'Invoices'), 3000);
      await searchPatient(kit, cl.name);
      const row = p.locator('tr.o_data_row', { hasText: inv }).first();
      await kit.click(row.getByRole('button', { name: /Receive Payment/ }), 3000);
      const dlg = p.locator('.modal-content').filter({ visible: true }).last();
      await dlg.waitFor({ timeout: 15000 });
      await kit.step(next(), `The client paid ${fmt(amount)} by bank transfer today: journal Bank`, `Khách hàng đã chuyển khoản ${amount.toLocaleString('vi-VN')} ₫ hôm nay: sổ Ngân hàng`);
      await kit.type(dlg.locator('.o_field_widget[name=journal_id] input').first(), 'Bank', 1200);
      await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: /^\s*Bank\s*$/ }).first(), 1500);
      const L2 = `Payment: ${fmt(amount)}, bank, today, for ${inv}`;
      V[L2] = `Thanh toán: ${amount.toLocaleString('vi-VN')} ₫, ngân hàng, hôm nay, cho ${inv}`;
      await kit.proof(dlg.locator('.modal-body').first(), L2, async (t) => {
        const v = await kit.fieldValues(['amount', 'payment_date', 'communication'], dlg);
        const day = m.today();
        const j = await kit.fieldValues(['journal_id'], dlg);
        return num(v.amount) === amount && v.payment_date.includes(`${day.mon} ${day.day}`) && v.communication.includes(inv) && j.journal_id === 'Bank';
      });
      if (STOP === 'dialog') { await kit.click(dlg.locator('button', { hasText: /^\s*Discard\s*$/ }).first(), 1500); return; }
      await kit.click(dlg.locator('button', { hasText: /^\s*Receive Payment\s*$/ }).first(), 4000);
      kit.records['Payment'] = `${fmt(amount)} bank transfer for ${inv}`;
      m.save({ paidAt: new Date().toISOString() });
      // The app opens the new payment: paid, bank, the amount, for this invoice only.
      const LP = `Payment recorded: ${fmt(amount)}, Bank, for ${inv} (1 invoice)`;
      V[LP] = `Đã ghi nhận thanh toán: ${amount.toLocaleString('vi-VN')} ₫, Ngân hàng, cho ${inv} (1 hóa đơn)`;
      await p.locator('.o_form_view').first().waitFor({ timeout: 15000 }).catch(() => {});
      await kit.hold(1500);
      const pform = p.locator('.o_form_view').filter({ visible: true }).first();
      await kit.proof(pform, LP, async (t) => {
        const inputs = (await pform.locator('input, textarea').evaluateAll((es) => es.map((e) => e.value))).join(' ');
        const all = t + ' ' + inputs;
        const head = await p.locator('.o_control_panel').filter({ visible: true }).first().innerText().catch(() => '');
        return /PAID/i.test(all) && m.money(amount).test(all) && all.includes(inv) && /Bank/.test(all) && /\b1\s*Invoice/.test(head + ' ' + t);
      });
    }
    await kit.step(next(), `Back to Invoices: ${inv} is paid`, `Quay lại Hóa đơn: ${inv} đã thanh toán`);
    // the payment page has no sidebar: go back with the "Invoices" breadcrumb
    await kit.click(p.locator('.o_breadcrumb a, .breadcrumb a').filter({ hasText: /^\s*Invoices\s*$/ }).filter({ visible: true }).first(), 3500);
    // the breadcrumb sits next to the left rail: park the pointer so the rail's flyout closes
    await p.mouse.move(760, 400, { steps: 12 });
    await kit.hold(1200);
    if (!(await p.locator('tr.o_data_row', { hasText: inv }).count())) await searchPatient(kit, cl.name);
    const L3 = `${inv}: Paid, amount due 0`;
    V[L3] = `${inv}: Đã thanh toán, còn phải thu 0`;
    await p.locator('tr.o_data_row', { hasText: inv }).first().waitFor({ timeout: 10000 }).catch(() => {});
    await kit.proof(p.locator('tr.o_data_row', { hasText: inv }).first(), L3, (t) => /\bPaid\b/.test(t) && /\b0\.00\b/.test(t) && m.money(amount).test(t));

    await kit.step(next(), `Open ${inv}: one payment, nothing left to pay`, `Mở ${inv}: một khoản thanh toán, không còn phải trả`);
    await kit.click(p.locator('tr.o_data_row', { hasText: inv }).first().locator('td').nth(3), 4000);
    await p.locator('.fin-invoice-header').first().waitFor({ timeout: 15000 }).catch(() => {});
    const L4 = `Total ${fmt(amount)}, paid ${fmt(amount)} once, amount due 0`;
    V[L4] = `Tổng ${amount.toLocaleString('vi-VN')} ₫, đã trả ${amount.toLocaleString('vi-VN')} ₫ một lần, còn phải thu 0`;
    const head = p.locator('.fin-invoice-header').first();
    await kit.proof(head, L4, (t) => {
      const mm = t.replace(/\s+/g, ' ').match(/([\d.,]+)\s*TOTAL\s*([\d.,]+)\s*AMOUNT DUE\s*([\d.,]+)\s*PAID/i);
      return /PAID/i.test(t) && !!mm && num(mm[1]) === amount && num(mm[2]) === 0 && num(mm[3]) === amount;
    });

    // ------------------------------------------------------------ after the payment
    await kit.step(next(), `Finance › Receivables again: ${cl.name}`, `Tài chính › Phải thu lần nữa: ${cl.name}`);
    await kit.click(c.sidebar(p, 'Receivables'), 3000);
    await arFor(kit, false);
    const after = await arRows(p);
    const L5 = `After the payment: ${inv} gone, ${fmt(others)} due`;
    V[L5] = `Sau thanh toán: không còn ${inv}, phải thu ${others.toLocaleString('vi-VN')} ₫`;
    await kit.proof(p.locator('.o_list_renderer').filter({ visible: true }).first(), L5, async () =>
      !after.some((r) => r.text.includes(inv)) && after.reduce((s, r) => s + r.out, 0) === others && (after.length === 0 || (await footOut(p)) === others));
    kit.records['Amount due after payment'] = fmt(others);
  },
};

// Receivables › AR Dashboard, searched for the client (Enter searches the client).
async function arFor(kit, step = true) {
  const p = kit.page;
  if (step) await kit.click(c.sidebar(p, 'Receivables'), 3000);
  await kit.type(p.locator('.o_searchview_input').filter({ visible: true }).first(), cl.name, 1200);
  await p.keyboard.press('Enter');
  await kit.hold(3000);
}
const arRow = (p, inv) => p.locator('tr.o_data_row', { hasText: inv }).first();
const arFoot = (p) => p.locator('.o_list_renderer tfoot tr').filter({ visible: true }).first();
async function arRows(p) {
  const rows = p.locator('.o_list_renderer tr.o_data_row').filter({ visible: true });
  const out = [];
  for (let i = 0; i < await rows.count(); i++) {
    const r = rows.nth(i);
    out.push({ text: await r.innerText(), out: num(await r.locator('td[name=amount_residual], td[name=outstanding_amount], td[name=amount_residual_signed]').first().innerText().catch(() => '0')) });
  }
  return out;
}
async function footOut(p) {
  const f = arFoot(p);
  const cells = await f.locator('td').allInnerTexts();
  const vals = cells.map((x) => x.trim()).filter(Boolean).map(num);
  return vals[0] || 0;
}
