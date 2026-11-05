// AR-03 Cash handed from the nurse to the Hanoi Operations Manager: Operations › Collections ›
// the 500,000 ₫ collected at visit v1 (AR-02) › Mark Cash Delivered to OM › Confirm Cash Receipt.
// The record keeps the amount, the receiving manager, the time and the receipt number; the
// invoice stays paid by its one payment (no second customer payment).
// AR03_STOP=dialog  practice: fills the dialog, then Cancel (nothing recorded).
// AR03_TXN=PAYxxxxx practice/rehearsal on another pending cash record (default: the state's txn1).
const r = require('./ar_common');
const { m } = r;
const om = r.users.om;
const nurse = r.users.nurse;
const cl = r.client;
const STOP = process.env.AR03_STOP || '';
const NOTES = 'UAT ONLY - fictional cash handed in by the nurse after the clinic visit; counted and matches';

module.exports = {
  meta: {
    id: 'AR-03', title: 'Cash handed from the nurse to the Operations Manager', short: 'Cash hand-in',
    title_vi: 'Điều dưỡng nộp tiền mặt cho Quản lý vận hành',
    criterion: 'Record the transfer of already-collected cash from the nurse to the front desk/operations manager. Retain the amount, receiving staff member, handover time and receipt reference. This custody handover must not create a second customer payment or change the reconciled invoice balance.',
    data: (() => { const s = r.load(); return `Cash record ${s.handin_txn || s.txn1 || '?'}: 500,000 ₫ collected by ${nurse.name} with Pay Now, Cash at today’s clinic visit ${s.handin_bk || (s.v1 || {}).bk || '?'} for ${cl.name} (${cl.code}), invoice ${s.handin_inv || s.inv1 || '?'} already paid;`; })() + ` received by ${om.name} (${om.login}) in Operations › Collections. All data is fictional.`,
    expected: 'Cash handover recorded once with recipient/time/receipt.',
    ...om,
  },
  proofVi: {},

  async run(kit) {
    const p = kit.page;
    const st = r.load();
    const V = kit._proofVi;
    const ref = process.env.AR03_TXN || st.handin_txn || st.txn1;
    if (!ref) throw new Error('no cash record (txn1) in the AR state file: run AR-02 first');
    const rehearse = !!process.env.AR03_TXN;
    let n = 1;
    const next = () => ++n;
    await kit.login();
    if (process.env.AR_PART === 'log') {   // rehearsal of the log part on an existing hand-in (view only)
      const h = st.handover_take1 || st.handover;
      return logPart(kit, next, { amount: 500000, ref: h.ref, receipt: h.receipt, inv: process.env.AR03_INV, rehearse: true, st });
    }

    // ------------------------------------------------------------ the pending cash
    await kit.step(next(), 'Operations › Collections › Pending Delivery', 'Vận hành › Thu tiền › Chờ nộp');
    await kit.area('Operations');
    await kit.click(r.sidebar(p, 'Collections'), 3000);
    await kit.click(p.locator('a, button, .nav-link').filter({ hasText: /^\s*Pending Delivery\s*$/ }).filter({ visible: true }).first(), 3000);
    await p.mouse.move(760, 400, { steps: 12 });
    const row = r.txnRow(p, ref);
    await row.waitFor({ timeout: 15000 });
    const amount = r.num((await row.locator('td[name=amount]').first().innerText().catch(() => '')) || '0') || 500000;
    const L0 = `${ref}: ${r.fmt(amount)} cash for ${cl.name}, waiting to be handed in`;
    V[L0] = `${ref}: ${r.fmtVi(amount)} tiền mặt của ${cl.name}, đang chờ nộp`;
    await kit.proof(row, L0, (t) => t.includes(cl.name) && /Cash Pend/.test(t) && r.money(amount).test(t));

    await kit.step(next(), `Open ${ref}`, `Mở ${ref}`);
    await kit.click(row.locator('td').nth(1), 4000);
    const status = p.locator('.o_form_view .o_statusbar_status').filter({ visible: true }).first();
    await status.waitFor({ timeout: 15000 });
    await kit.hold(1000);

    // the invoice before the hand-in: paid, one payment
    await kit.step(next(), 'Before the hand-in: View Invoice', 'Trước khi nộp: Xem hóa đơn');
    await kit.click(r.smartBtn(p, /Invoice/), 4000);
    const before = await r.invSummary(p);
    const inv = before.inv;
    const payBtn = r.smartBtn(p, /Payments?/);
    const nPay = async () => r.num((await payBtn.innerText().catch(() => '0')).match(/\d+/) || '0');
    const payBefore = await nPay();
    const L1 = `Before: ${inv} total ${r.fmt(before.total || 0)}, amount due ${r.fmt(before.due || 0)}, ${payBefore} payment`;
    V[L1] = `Trước: ${inv} tổng ${r.fmtVi(before.total || 0)}, còn phải thu ${r.fmtVi(before.due || 0)}, ${payBefore} khoản thanh toán`;
    await kit.proof([...before.boxes, payBtn], L1, () => !!inv && (rehearse || (before.due === 0 && payBefore === 1)));
    // back to the cash record: the last link in the breadcrumb
    await kit.click(p.locator('.o_breadcrumb a, .breadcrumb a').filter({ visible: true }).last(), 3500);
    await p.mouse.move(760, 400, { steps: 12 });
    await status.waitFor({ timeout: 15000 });

    // ------------------------------------------------------------ the hand-in
    await kit.step(next(), 'The nurse hands over the cash: Mark Cash Delivered to OM', 'Điều dưỡng giao tiền mặt: Đánh dấu đã nộp cho QLVH');
    await kit.click(p.locator('.o_form_view button').filter({ hasText: /^\s*Mark Cash Delivered to OM\s*$/ }).filter({ visible: true }).first(), 3000);
    const dlg = p.locator('.modal-content').filter({ hasText: 'Confirm Cash Delivery' }).last();
    await dlg.waitFor({ timeout: 15000 });
    await kit.step(next(), `The box already names the receiver: ${om.name} (signed in); count the cash and tick Amount Verified`, `Ô người nhận đã điền sẵn: ${om.name} (đang đăng nhập); đếm tiền và đánh dấu Đã kiểm tra số tiền`);
    const omBox = dlg.locator('.o_field_widget[name=om_employee_id]').first();
    const LO = `Operations Manager already filled in: ${om.name}`;
    V[LO] = `Quản lý vận hành đã điền sẵn: ${om.name}`;
    await kit.proof(omBox, LO, async () => (await kit.fieldValues(['om_employee_id'], dlg)).om_employee_id === om.name, 2400);
    await kit.click(dlg.locator('.o_field_widget[name=amount_verified] input').first(), 800);
    // the receipt number is normally generated; if the box is empty, write the paper receipt's number
    const rc = dlg.locator('.o_field_widget[name=om_receipt_number] input').first();
    if (!(await rc.inputValue().catch(() => ''))) {
      const d = r.today();
      await kit.type(rc, `HN-${d.iso.replace(/-/g, '')}-${(st.v1 || {}).bk || 'CASH'}`, 600);
    }
    await kit.type(dlg.locator('.o_field_widget[name=cash_condition_notes] textarea').first(), NOTES, 500);
    await kit.step(next(), 'As the test steps say: Auto-Reconcile off (the payment is already matched), no bank deposit', 'Theo các bước kiểm thử: tắt Tự động đối soát (khoản thanh toán đã khớp), không tạo nộp ngân hàng');
    const auto = dlg.locator('.o_field_widget[name=auto_reconcile_ar] input').first();
    if (await auto.isChecked()) await kit.click(auto, 800);
    const dep = dlg.locator('.o_field_widget[name=create_bank_deposit] input').first();
    if (await dep.isChecked()) await kit.click(dep, 800);
    const vals = await kit.fieldValues(['om_receipt_number', 'delivery_date', 'om_employee_id'], dlg);
    const receipt = vals.om_receipt_number;
    const L2 = `${r.fmt(amount)} from ${nurse.name} to ${om.name}, now, receipt ${receipt}`;
    V[L2] = `${r.fmtVi(amount)} từ ${nurse.name} cho ${om.name}, bây giờ, biên nhận ${receipt}`;
    await dlg.locator('.modal-body').evaluate((e) => { e.scrollTop = 0; });
    await kit.proof([dlg.locator('.o_field_widget[name=cash_amount]').first(), dlg.locator('.o_field_widget[name=collected_by]').first(),
      dlg.locator('.o_field_widget[name=om_employee_id]').first(), dlg.locator('.o_field_widget[name=delivery_date]').first(),
      dlg.locator('.o_field_widget[name=om_receipt_number]').first()], L2, async (t) =>
      r.money(amount).test(t) && (rehearse || t.includes(nurse.name)) && vals.om_employee_id === om.name && m.nearNow(vals.delivery_date) && !!receipt
      && (await dlg.locator('.o_field_widget[name=amount_verified] input').first().isChecked()), 3600);
    const L3 = 'Auto-Reconcile off, no bank deposit';
    V[L3] = 'Tắt tự động đối soát, không tạo nộp ngân hàng';
    await kit.proof([dlg.locator('.o_field_widget[name=auto_reconcile_ar]').first(), dlg.locator('.o_field_widget[name=create_bank_deposit]').first()], L3,
      async () => !(await auto.isChecked()) && !(await dep.isChecked()));
    if (STOP === 'dialog') { await kit.click(dlg.locator('.modal-footer button').filter({ hasText: /^\s*Cancel\s*$/ }).first(), 1500); return; }

    await kit.step(next(), 'Confirm Cash Receipt', 'Xác nhận đã nhận tiền mặt');
    await kit.click(dlg.locator('.modal-footer button').filter({ hasText: /Confirm Cash Receipt/ }).first(), 4500);
    await p.locator('.modal-content').filter({ hasText: 'Confirm Cash Delivery' }).waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
    r.save({ handover: { ref, receipt, at: new Date().toISOString() } });
    kit.records['Cash hand-in'] = `${ref} receipt ${receipt}`;
    await status.waitFor({ timeout: 15000 });
    await kit.hold(1500);
    const LS = `${ref}: Cash Delivered to OM`;
    V[LS] = `${ref}: Đã nộp tiền mặt cho QLVH`;
    await kit.proof(status, LS, async () => (await status.locator('button.active, .o_arrow_button_current').filter({ hasText: /Cash Delivered to OM/ }).count()) > 0);
    const proc = p.locator('.o_field_widget[name=received_by_om_id]').filter({ visible: true }).first().locator('xpath=ancestor::div[contains(@class,"o_group") or contains(@class,"o_inner_group") or contains(@class,"vu-detail-card")][1]');
    const L4 = `Kept: received by ${om.name}, at ${'the hand-in time'}, receipt ${receipt}`;
    V[L4] = `Đã lưu: người nhận ${om.name}, thời điểm nộp, biên nhận ${receipt}`;
    await kit.proof(proc, L4, async () => {
      const f = await kit.fieldValues(['received_by_om_id', 'cash_delivery_date', 'om_receipt_number', 'collected_by_id']);
      return f.received_by_om_id === om.name && m.nearNow(f.cash_delivery_date, 10) && f.om_receipt_number === receipt && (rehearse || f.collected_by_id === nurse.name);
    });

    // ------------------------------------------------------------ no second customer payment
    await kit.step(next(), 'After the hand-in: View Invoice again', 'Sau khi nộp: Xem lại hóa đơn');
    await kit.click(r.smartBtn(p, /Invoice/), 4000);
    const after = await r.invSummary(p);
    const payAfter = await nPay();
    const L5 = `After: still ${payAfter} payment, amount due ${r.fmt(after.due || 0)} — no second customer payment`;
    V[L5] = `Sau: vẫn ${payAfter} khoản thanh toán, còn phải thu ${r.fmtVi(after.due || 0)} — không có khoản thanh toán thứ hai`;
    await kit.proof([...after.boxes, payBtn], L5, () => payAfter === payBefore && after.due === before.due && after.paid === before.paid);

    await logPart(kit, next, { amount, ref, receipt, inv, rehearse, st });
  },
};

// The hand-in's row in Finance › Receivables › AR Transactions › Cash Hand-ins, and its cash record.
async function logPart(kit, next, { amount, ref, receipt, inv, rehearse, st }) {
  const p = kit.page;
  const V = kit._proofVi;
  // ------------------------------------------------------------ the hand-in in the accounting log
  await kit.step(next(), 'Finance › Receivables › AR Transactions › Cash Hand-ins', 'Tài chính › Phải thu › Giao dịch AR › Nộp tiền mặt');
  await r.backToRail(kit);
  await kit.area('Finance');
  await kit.click(r.sidebar(p, 'Receivables'), 3000);
  await kit.click(p.locator('button, a').filter({ hasText: /^\s*AR Transactions\s*$/ }).filter({ visible: true }).first(), 3000);
  await p.mouse.move(760, 400, { steps: 12 });
  await kit.click(p.locator('.o_searchview_dropdown_toggler').filter({ visible: true }).first(), 1500);
  await kit.click(p.locator('.o_filter_menu .o_menu_item, .o-dropdown-item, .dropdown-item').filter({ hasText: /^\s*Cash Hand-ins\s*$/ }).filter({ visible: true }).first(), 2500);
  await p.keyboard.press('Escape');
  await p.mouse.move(760, 400, { steps: 12 });
  await kit.hold(1500);
  const bk = st.handin_bk || (r.load().v1 || {}).bk || '';
  const hrows = p.locator('tr.o_data_row').filter({ hasText: /Handover/ }).filter({ hasText: r.money(amount) });
  const hrow = (rehearse || !bk ? hrows : hrows.filter({ hasText: `(${bk})` })).first();
  await hrow.waitFor({ timeout: 15000 });
  const L6 = `One Handover entry: ${r.fmt(amount)}${bk && !rehearse ? `, booking ${bk}` : ''}`;
  V[L6] = `Một dòng Nộp tiền: ${r.fmtVi(amount)}${bk && !rehearse ? `, lịch hẹn ${bk}` : ''}`;
  await kit.proof(hrow, L6, async () => rehearse || (await (bk ? hrows.filter({ hasText: `(${bk})` }) : hrows).count()) === 1);
  await kit.step(next(), 'Open the Handover entry', 'Mở dòng Nộp tiền');
  await kit.click(hrow.locator('td').nth(2), 3500);
  const sheet = p.locator('.o_form_sheet').filter({ visible: true }).first();
  await sheet.waitFor({ timeout: 15000 });
  await kit.hold(1200);
  const fw = (nm) => sheet.locator(`.o_field_widget[name=${nm}]`).first();
  const f = await kit.fieldValues(['event_type', 'amount', 'transaction_datetime', 'handed_over_by_id', 'received_by_id', 'receipt_reference', 'cash_record_id', 'invoice_id'], sheet);
  console.log('  handover row:', JSON.stringify(f));
  const L7 = `Handover ${r.fmt(amount)}, at the hand-in time`;
  V[L7] = `Nộp tiền ${r.fmtVi(amount)}, đúng thời điểm nộp`;
  await kit.proof(['event_type', 'transaction_datetime', 'amount'].map(fw), L7, () =>
    /Handover/.test(f.event_type) && r.num(f.amount) === amount && (rehearse || m.nearNow(f.transaction_datetime, 15)));
  // the Cash Record box shows the record by its name ("Nguyễn Văn An - 500,000 VND (Cash)"), not PAY…
  const L8 = `From ${nurse.name} to ${om.name}, receipt ${receipt}, the ${r.fmt(amount)} cash record, invoice ${inv}`;
  V[L8] = `Từ ${nurse.name} cho ${om.name}, biên nhận ${receipt}, bản ghi tiền mặt ${r.fmtVi(amount)}, hóa đơn ${inv}`;
  await kit.proof(['handed_over_by_id', 'received_by_id', 'receipt_reference', 'cash_record_id', 'invoice_id'].map(fw), L8, () =>
    (rehearse || f.handed_over_by_id === nurse.name) && f.received_by_id === om.name && f.receipt_reference === receipt
    && f.cash_record_id.includes(cl.name) && r.money(amount).test(f.cash_record_id) && /Cash/.test(f.cash_record_id) && f.invoice_id.includes(inv));
  // the Cash Record box is a link: it opens the cash record, whose reference is ref
  await kit.step(next(), 'Open the Cash Record from the Handover entry', 'Mở Bản ghi tiền mặt từ dòng Nộp tiền');
  await kit.click(fw('cash_record_id').locator('a, .o_form_uri').first(), 4000);
  const st2 = p.locator('.o_form_view .o_statusbar_status').filter({ visible: true }).first();
  await st2.waitFor({ timeout: 15000 });
  await kit.hold(1200);
  const L9 = `It is ${ref}: Cash Delivered to OM, receipt ${receipt}`;
  V[L9] = `Đó là ${ref}: Đã nộp tiền mặt cho QLVH, biên nhận ${receipt}`;
  await kit.proof([p.locator('.o_field_widget[name=name]').filter({ visible: true }).first(), st2,
    p.locator('.o_field_widget[name=om_receipt_number]').filter({ visible: true }).first()], L9, async () => {
    const g = await kit.fieldValues(['name', 'om_receipt_number']);
    return g.name === ref && g.om_receipt_number === receipt
      && (await st2.locator('button.active, .o_arrow_button_current').filter({ hasText: /Cash Delivered to OM/ }).count()) > 0;
  });
  kit.records['Log entry'] = 'Handover (AR Transactions)';
}
