// AR-05 Refund removes amount owing — both meanings, as the owner approved on 5 Nov:
//  Part 1  a credit note cancels an UNPAID charge: invoice of visit v3 (200,000 ₫, Pay Later)
//          › Credit Note › Reverse › Confirm: the amount owing drops to 0, linked both ways.
//  Part 2  a refund returns cash already PAID: the 500,000 ₫ cash of visit v1 (AR-02, handed in
//          in AR-03) › Create Refund: the invoice is owing again (the charge is not cancelled).
// Each reversal is approved ONCE for the final. Create Refund has no "are you sure" step.
// AR05_STOP=cn      practice: fills the Credit Note dialog, then Discard (nothing created).
// AR05_STOP=refund  practice: Part 1 skipped; stops with the pointer on Create Refund (no click).
// AR_PART=after1    rehearsal of Part 1's after-checks on AR05_INV / AR05_CN (old records).
// AR05_INV / AR05_TXN override the state's inv3 / txn1 for practice.
const r = require('./ar_common');
const fin = r.users.finance;
const cl = r.client;
const STOP = process.env.AR05_STOP || '';
const PART = process.env.AR_PART || '';
const CN_REASON = 'UAT ONLY - charge cancelled: this online examination is not to be charged (fictional)';

module.exports = {
  meta: {
    id: 'AR-05', title: 'Credit note cancels a charge and a refund returns paid cash', short: 'Credit note and refund',
    title_vi: 'Giấy báo có hủy khoản phí và hoàn tiền đã trả',
    criterion: 'The client wording is “Refunds removes amount owning”. Demonstrate the agreed refund/credit operation and its receivable result, with source references and accounting entries retained. Returning previously paid cash and cancelling a charge with a credit note have different effects, so the accepted interpretation must be confirmed.',
    data: (() => { const s = r.load(); return `Part 1: unpaid invoice ${s.ar05inv || '?'} of visit ${(s.v4 || {}).bk || '?'} (Online internal examination, 200,000 ₫, completed in the nurse app with Pay Later) for ${cl.name} (${cl.code}), cancelled by a credit note. Part 2: cash record ${s.ar05txn || '?'} — 500,000 ₫ paid in cash at the nurse-app completion of visit ${(s.v5 || {}).bk || '?'} for invoice ${s.ar05inv1 || '?'} — refunded. Finance (${fin.login}). Both approved by the owner (5 and 6 Nov 2026). All data is fictional.`; })(),
    expected: 'Refund/credit follows agreed semantics and reconciles the balance correctly.',
    ...fin,
  },
  proofVi: {},

  async run(kit) {
    const p = kit.page;
    const st = r.load();
    const V = kit._proofVi;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ============================================================ Part 1: credit note
    if (STOP !== 'refund') {
      const inv = process.env.AR05_INV || st.ar05inv || st.inv3;
      if (!inv) throw new Error('no invoice (inv3) in the AR state file: complete visit v3 first');
      await kit.note('Part 1 — a credit note cancels a charge the client has not paid', 'Phần 1 — giấy báo có hủy một khoản phí khách hàng chưa trả');
      await r.invoicesFor(kit, next(), `Finance › Invoices: ${cl.name}`, `Tài chính › Hóa đơn: ${cl.name}`);
      await kit.step(next(), `Open the unpaid invoice ${inv}`, `Mở hóa đơn chưa trả ${inv}`);
      await r.openInvoice(kit, inv);
      const h0 = await r.invSummary(p);
      if (PART !== 'after1') {
        const L0 = `Before: ${inv} owes ${r.fmt(h0.total || 0)}, nothing paid`;
        V[L0] = `Trước: ${inv} còn nợ ${r.fmtVi(h0.total || 0)}, chưa trả`;
        await kit.proof(h0.boxes, L0, () => h0.label === 'NOT PAID' && h0.inv === inv && h0.total > 0 && h0.due === h0.total && !h0.paid);

        await kit.step(next(), 'Credit Note: the reason, then Reverse', 'Giấy báo có: nhập lý do, rồi Đảo bút toán');
        await kit.click(p.locator('.o_form_view button').filter({ hasText: /^\s*Credit Note\s*$/ }).filter({ visible: true }).first(), 3000);
        const dlg = p.locator('.modal-content').filter({ has: p.locator('.o_field_widget[name=reason]') }).last();
        await dlg.waitFor({ timeout: 15000 });
        await kit.type(dlg.locator('.o_field_widget[name=reason] input').first(), CN_REASON, 600);
        const L1 = 'Credit note: reason given, journal Sales, dated today';
        V[L1] = 'Giấy báo có: có lý do, sổ Bán hàng, ngày hôm nay';
        await kit.proof(dlg.locator('.modal-body').first(), L1, async () => {
          const f = await kit.fieldValues(['reason', 'journal_id', 'date'], dlg);
          const day = r.today();
          return f.reason === CN_REASON && /Sales/.test(f.journal_id) && f.date.includes(`${day.mon} ${day.day}`);
        });
        if (STOP === 'cn') { await kit.click(dlg.locator('button').filter({ hasText: /^\s*Discard\s*$/ }).first(), 1500); return; }
        await kit.click(dlg.locator('button').filter({ hasText: /^\s*Reverse\s*$/ }).first(), 5000);
        r.save({ ar05cn: { inv, at: new Date().toISOString() } });

        // the draft credit note opens: confirm it
        const status = p.locator('.o_statusbar_status').filter({ visible: true }).first();
        await status.waitFor({ timeout: 15000 });
        await kit.hold(1500);
        const L2 = `Draft credit note for ${cl.name}: ${r.fmt(h0.total)}, reversal of ${inv}`;
        V[L2] = `Giấy báo có nháp cho ${cl.name}: ${r.fmtVi(h0.total)}, đảo của ${inv}`;
        await kit.proof([p.locator('.o_control_panel').filter({ visible: true }).first(), p.locator('.o_field_widget[name=partner_id]').filter({ visible: true }).first(),
          r.footer(p), status], L2, async (t) => ((await kit.fieldValues(['partner_id'])).partner_id + t).includes(cl.name) && r.money(h0.total).test(t) && t.includes(inv)
          && (await status.locator('button.active, .o_arrow_button_current, [aria-checked=true]').filter({ hasText: /Draft/ }).count()) > 0);
        await kit.step(next(), 'Confirm the credit note', 'Xác nhận giấy báo có');
        await kit.click(p.locator('.o_form_view button[name=action_post], .o_form_view button').filter({ hasText: /^\s*Confirm\s*$/ }).filter({ visible: true }).first(), 5000);
        await status.locator('button.active, .o_arrow_button_current, [aria-checked=true]').filter({ hasText: /Posted/ }).waitFor({ timeout: 20000 }).catch(() => {});
        await kit.hold(1500);
      } else {
        // rehearsal: the credit note is reached from the invoice's Reversed line
        await kit.note('Rehearsal: the credit note already exists', 'Diễn tập: giấy báo có đã có');
        await p.goto(p.url().replace(/\/\d+$/, `/${process.env.AR05_CN_ID}`));
      }
      const hc = await r.invSummary(p);
      const cn = /^RINV/.test(hc.inv) ? hc.inv : '';
      const L3 = `Credit note ${cn} posted: ${r.fmt(hc.total || 0)}, settled against ${inv}`;
      V[L3] = `Giấy báo có ${cn} đã ghi sổ: ${r.fmtVi(hc.total || 0)}, cấn trừ với ${inv}`;
      await kit.proof([...hc.boxes, p.locator('.o_control_panel').filter({ visible: true }).first()], L3,
        (t) => !!cn && hc.total === h0.total && hc.due === 0 && t.includes(`Reversal of: ${inv}`));
      if (PART !== 'after1') { r.save({ cn3b: cn }); kit.records['Credit note'] = cn; }

      await kit.step(next(), `Back to ${inv}`, `Quay lại ${inv}`);
      await r.invoicesFor(kit, null);
      await r.openInvoice(kit, inv);
      const L4 = `${inv}: Reversed, amount owing now 0`;
      V[L4] = `${inv}: Đã đảo, số tiền còn nợ bây giờ là 0`;
      const h4 = await r.invSummary(p);
      await kit.proof(h4.boxes, L4, () => h4.label === 'REVERSED' && h4.inv === inv && h4.total === h0.total && h4.due === 0);
      const pw = p.locator('.o_field_widget[name=invoice_payments_widget]').filter({ visible: true }).first();
      const L5 = `Linked: “Reversed on” the credit note’s date, ${r.fmt(h0.total)}`;
      V[L5] = `Liên kết: “Đã đảo ngày” theo ngày giấy báo có, ${r.fmtVi(h0.total)}`;
      await kit.proof([pw, r.footer(p)], L5,
        (t) => /Reversed on/.test(t) && r.money(h0.total).test(t) && /Amount Due:?\s*0\b/.test(t));
      await kit.step(next(), `Finance › Receivables: ${cl.name}`, `Tài chính › Phải thu: ${cl.name}`);
      await kit.click(r.sidebar(p, 'Receivables'), 3000);
      await r.searchClient(kit);
      const L6 = `Receivables: ${inv} no longer owed`;
      V[L6] = `Phải thu: ${inv} không còn nợ`;
      await kit.proof(p.locator('.o_list_renderer').filter({ visible: true }).first(), L6, async () => !(await r.invRow(p, inv).count()));
    }
    if (PART === 'after1') return;

    // ============================================================ Part 2: refund of paid cash
    const ref = process.env.AR05_TXN || st.ar05txn || st.txn1;
    const inv1 = process.env.AR05_INV1 || st.ar05inv1 || st.inv1;
    if (!ref || !inv1) throw new Error('no cash record (txn1 / inv1) in the AR state file');
    await kit.note('Part 2 — a refund returns cash the client already paid', 'Phần 2 — hoàn lại tiền mặt khách hàng đã trả');
    await r.invoicesFor(kit, next(), `Finance › Invoices: the paid invoice ${inv1}`, `Tài chính › Hóa đơn: hóa đơn đã trả ${inv1}`);
    await r.openInvoice(kit, inv1);
    const b = await r.invSummary(p);
    const L7 = `Before: ${inv1} paid ${r.fmt(b.paid || 0)} in cash, amount due 0`;
    V[L7] = `Trước: ${inv1} đã trả ${r.fmtVi(b.paid || 0)} tiền mặt, còn phải thu 0`;
    await kit.proof(b.boxes, L7, () => b.label === 'PAID' && b.inv === inv1 && b.due === 0 && b.paid === b.total && b.total > 0);

    await kit.step(next(), `Finance › Payments › ${ref}`, `Tài chính › Thanh toán › ${ref}`);
    await kit.click(r.sidebar(p, 'Payments'), 3000);
    await r.searchClient(kit);
    const trow = r.txnRow(p, ref);
    await trow.waitFor({ timeout: 15000 });
    await kit.click(trow.locator('td').nth(1), 4000);
    const status = p.locator('.o_form_view .o_statusbar_status').filter({ visible: true }).first();
    await status.waitFor({ timeout: 15000 });
    await kit.hold(1000);
    const L8 = `${ref}: the ${r.fmt(b.paid)} cash collected at the visit`;
    V[L8] = `${ref}: ${r.fmtVi(b.paid)} tiền mặt đã thu tại lượt khám`;
    await kit.proof([status, p.locator('.o_field_widget[name=amount]').filter({ visible: true }).first()], L8, async (t) =>
      (await status.locator('button.active, .o_arrow_button_current').filter({ hasText: /Cash Pending Delivery|Cash Delivered to OM/ }).count()) > 0 && r.money(b.paid).test(t + ' ' + (await kit.fieldValues(['amount'])).amount));

    await kit.step(next(), 'The client is given the cash back: Create Refund', 'Trả lại tiền mặt cho khách hàng: Tạo hoàn tiền');
    const refundBtn = p.locator('.o_form_view button').filter({ hasText: /^\s*Create Refund\s*$/ }).filter({ visible: true }).first();
    if (STOP === 'refund') { await kit.moveTo(refundBtn); await kit.hold(1500); return; }
    await kit.click(refundBtn, 5000);
    r.save({ ar05refund: { ref, at: new Date().toISOString() } });
    await p.locator('.o_form_view .o_statusbar_status').first().waitFor({ timeout: 15000 });
    await kit.hold(1500);
    const rf = await kit.fieldValues(['name', 'amount', 'transaction_type', 'transaction_notes']);
    const refRef = (rf.name.match(/PAY\d+/) || [''])[0];
    const L9 = `Refund ${refRef}: ${r.fmt(-b.paid)}, for ${ref}`;
    V[L9] = `Hoàn tiền ${refRef}: ${r.fmtVi(-b.paid)}, cho ${ref}`;
    await kit.proof(p.locator('.o_form_sheet').filter({ visible: true }).first(), L9, (t) =>
      !!refRef && refRef !== ref && r.num(rf.amount) === -b.paid && /Refund/i.test(rf.transaction_type + t) && (rf.transaction_notes + t).includes(ref));
    if (refRef) { r.save({ refund2: refRef }); kit.records['Refund'] = refRef; }

    await kit.step(next(), `View Invoice ${inv1}`, `Xem hóa đơn ${inv1}`);
    await kit.click(r.smartBtn(p, /Invoice/), 4000);
    const a10 = await r.invSummary(p);
    const L10 = `${inv1}: owing again — amount due ${r.fmt(b.total)} (the charge itself is not cancelled)`;
    V[L10] = `${inv1}: lại còn nợ — còn phải thu ${r.fmtVi(b.total)} (khoản phí không bị hủy)`;
    await kit.proof(a10.boxes, L10, () => a10.inv === inv1 && a10.total === b.total && a10.due === b.total && a10.label !== 'REVERSED');
    await kit.note('Credit note = the charge is cancelled, nothing owed. Refund = paid cash returned, the charge is owed again.',
      'Giấy báo có = hủy khoản phí, không còn nợ. Hoàn tiền = trả lại tiền đã thu, khoản phí lại còn nợ.');
    await kit.hold(1500);
    await kit.note('The client still has to confirm which meaning “refund removes amount owing” has (this row stays Partial)',
      'Khách hàng vẫn cần xác nhận “hoàn tiền xóa số tiền nợ” theo nghĩa nào (dòng này vẫn ở trạng thái Một phần)');
    await kit.hold(2500);
  },
};
