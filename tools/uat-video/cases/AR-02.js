// AR-02 Cash paid at completion: the nurse completes visit v1 (Internal examination, 500,000 ₫)
// in the nurse app with Pay Now, Cash. The invoice is posted and paid in full (amount due 0) by
// exactly one payment; the cash itself is recorded as held by the nurse until she hands it in.
// AR02_STOP=wizard  practice: stops in the payment window (Cancel), nothing is completed.
// AR_PART=office    skip the nurse part (rehearse the office checks on the state file's v1).
const r = require('./ar_common');
const { m, a } = r;
const nurse = r.users.nurse;
const fin = r.users.finance;
const cl = r.client;
const v = r.VISITS.v1;
const STOP = process.env.AR02_STOP || '';
const PART = process.env.AR_PART || '';
const CHECKED = 'Checked with the client: internal examination at the clinic as booked (TC-01)';
const REASON = 'UAT ONLY - fictional test visit; the client will call if he needs another visit';

module.exports = {
  meta: {
    id: 'AR-02', title: 'Cash paid at completion leaves nothing due', short: 'Cash at completion',
    title_vi: 'Thanh toán tiền mặt khi hoàn thành, không còn nợ',
    criterion: 'Record the cash received at service completion against the correct invoice. The payment must post and reconcile the customer balance, with the expected cash custody record. Full payment leaves zero due and repeated processing must not collect or allocate the same payment twice.',
    data: `TC-01: today’s clinic visit ${(r.load().v1 || {}).bk || '(from setup)'} for ${cl.name} (${cl.code}), ${v.product} (${v.code}) 500,000 ₫, price list “Client UAT 20261013 V01.01 (VND)”; nurse ${nurse.login} completes it with Pay Now, Cash; Finance checks as ${fin.login}. All data is fictional.`,
    expected: 'Cash payment posts, reconciles and leaves zero due.',
    ...nurse,
  },
  proofVi: {
    'Payment timing: Pay Now': 'Thời điểm thanh toán: Trả ngay',
    'Payment method: Cash': 'Phương thức thanh toán: Tiền mặt',
    'Create Invoice Now ticked': 'Đã chọn Tạo hóa đơn ngay',
    'Amount 500,000 ₫, paid now': 'Số tiền 500.000 ₫, trả ngay',
    'Visit completed in the nurse app': 'Lượt khám đã hoàn thành trên ứng dụng điều dưỡng',
    'Exactly one payment on the invoice': 'Đúng một khoản thanh toán trên hóa đơn',
  },

  async run(kit) {
    const p = kit.page;
    const st = r.load();
    const V = kit._proofVi;
    if (!st.v1 || !st.v1.id) throw new Error('no v1 in the AR state file: run the setup first');
    const visit = st.v1;
    let n = 0;
    const next = () => ++n;
    const pops = r.catchPopups(kit);

    if (PART !== 'office') {
      // ---------------------------------------------------------- the nurse completes the visit
      await r.asNurse(kit, next());
      await kit.step(next(), `At the clinic: open today’s visit for ${cl.name} (${visit.hm})`, `Tại phòng khám: mở lượt khám hôm nay của ${cl.name} (${visit.hm})`);
      await r.startIfNeeded(kit, next, visit, v);
      const { wiz } = await r.quoteAndWizard(kit, next, v, { checked: CHECKED });
      await kit.step(next(), 'Payment: the client pays now, in cash (500,000 ₫); create the invoice now', 'Thanh toán: khách hàng trả ngay bằng tiền mặt (500.000 ₫); tạo hóa đơn ngay');
      await kit.click(wiz.locator('label', { hasText: /^\s*Pay Now\s*$/ }).first(), 900);
      await kit.click(wiz.locator('label', { hasText: /^\s*Cash\s*$/ }).first(), 900);
      const invoiceNow = wiz.locator('label', { hasText: 'Create Invoice Now' }).locator('input[type=checkbox]').first();
      if (!(await invoiceNow.isChecked())) await kit.click(invoiceNow, 600);
      // the window is taller than the tablet screen: prove one part at a time
      await kit.proof(wiz.locator('.form-section').nth(0), 'Payment timing: Pay Now', async () => wiz.locator('input[type=radio][value=pay_now]').isChecked(), 2200);
      await kit.proof(wiz.locator('.form-section').nth(1), 'Payment method: Cash', async () => wiz.locator('input[type=radio][value=cash]').isChecked(), 2200);
      await kit.proof(wiz.locator('label', { hasText: 'Create Invoice Now' }).first(), 'Create Invoice Now ticked', async () => invoiceNow.isChecked(), 2200);
      await kit.proof(wiz.locator('.info-grid').first(), 'Amount 500,000 ₫, paid now', (t) => r.money(v.total).test(t) && /\bNow\b/.test(t), 3000);
      if (STOP === 'wizard') { await kit.click(wiz.locator('button', { hasText: /^\s*Cancel\s*$/ }).first(), 1000); return; }

      await kit.step(next(), 'Complete Service', 'Hoàn thành dịch vụ');
      const before = pops.length;
      await kit.click(wiz.locator('button', { hasText: /Complete Service/ }).last(), 6000);
      r.save({ v1: { ...visit, completedAt: new Date().toISOString() } });
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

    // ------------------------------------------------------------ Finance: the booking's invoice
    await a.openBooking(kit, next(), visit.bk, `Operations › Bookings › open ${visit.bk}`, `Vận hành › Lịch hẹn › mở ${visit.bk}`);
    await kit.step(next(), 'Execution tab: Quote & Invoice', 'Thẻ Thực hiện: Báo giá & Hóa đơn');
    await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Execution\s*$/ }).first(), 2200);
    const qi = p.locator('.vu-detail-card[name=quote_invoice_card]').filter({ visible: true }).first();
    await qi.waitFor({ timeout: 15000 });
    const invF = qi.locator('.o_field_widget[name=invoice_id]').first();
    const inv = (((await invF.innerText().catch(() => '')) || '').match(/INV\/\d{4}\/\d+/) || [''])[0];
    const LB = `Booking ${visit.bk}: invoice ${inv} posted`;
    V[LB] = `Lịch hẹn ${visit.bk}: hóa đơn ${inv} đã ghi sổ`;
    await kit.proof(qi, LB, (t) => !!inv && /Posted/.test(t));
    if (PART !== 'office') r.save({ inv1: inv });
    kit.records['Invoice'] = inv;

    await kit.step(next(), `Open the invoice ${inv}`, `Mở hóa đơn ${inv}`);
    await kit.click(invF.locator('a, .o_form_uri, span').first(), 4000);
    await p.locator('.o_field_widget[name=invoice_line_ids]').first().waitFor({ timeout: 15000 });
    await kit.hold(1200);
    const L0 = `${inv} for ${cl.name}: posted, marked PAID`;
    V[L0] = `${inv} cho ${cl.name}: đã ghi sổ, đánh dấu ĐÃ THANH TOÁN`;
    const status = p.locator('.o_statusbar_status').filter({ visible: true }).first();
    await kit.proof([p.locator('.o_breadcrumb').filter({ visible: true }).first(),
      p.locator('.o_field_widget[name=partner_id]').filter({ visible: true }).first(), status], L0, async (t) => {
      const ribbon = await p.locator('.ribbon, .o_widget_web_ribbon').filter({ visible: true }).allInnerTexts();
      return t.includes(inv) && t.includes(cl.name) && /Posted/.test(t) && ribbon.join(' ').includes('PAID')
        && (await status.locator('button.active, .o_arrow_button_current, [aria-checked=true]').filter({ hasText: /Posted/ }).count()) > 0;
    });
    const L1 = `Total ${r.fmt(v.total)}, paid today ${r.fmt(v.total)}, amount due 0`;
    V[L1] = `Tổng ${r.fmtVi(v.total)}, đã trả hôm nay ${r.fmtVi(v.total)}, còn phải thu 0`;
    await kit.proof(r.footer(p), L1, (t) => { const f = r.footNums(t); const day = r.today();
      return f.total === v.total && f.due === 0 && f.paid.length === 1 && f.paid[0] === v.total && t.includes(`${r.m.p2(day.d.getUTCMonth() + 1)}/${r.m.p2(day.day)}/${day.d.getUTCFullYear()}`); });
    const pay = r.smartBtn(p, /Payments?/);
    await kit.proof(pay, 'Exactly one payment on the invoice', (t) => /\b1\b/.test(t) && /Payment/.test(t));

    await kit.step(next(), 'Open that payment', 'Mở khoản thanh toán đó');
    await kit.click(pay, 4000);
    const psheet = p.locator('.o_form_sheet').filter({ hasText: 'Amount' }).filter({ visible: true }).first();
    await psheet.waitFor({ timeout: 20000 });
    await kit.hold(1500);
    const pform = p.locator('.o_form_view').filter({ visible: true }).first();
    let payName = '';
    const L2 = `One cash payment of ${r.fmt(v.total)} today, posted and matched to ${inv}`;
    V[L2] = `Một khoản tiền mặt ${r.fmtVi(v.total)} hôm nay, đã ghi sổ và khớp với ${inv}`;
    await kit.proof([psheet, r.smartBtn(p, /Invoice/), p.locator('.o_breadcrumb').filter({ visible: true }).first()], L2, async (t) => {
      const inputs = (await pform.locator('input, textarea').evaluateAll((es) => es.map((e) => e.value))).join(' ');
      const all = t + ' ' + inputs;
      if (!/\b1\s*Invoice/.test(all)) return false;
      payName = (all.match(/P[A-Z]{3}\d\/\d{4}\/\d+/) || [''])[0];
      const day = r.today();
      return r.money(v.total).test(all) && /Cash/.test(all) && all.includes(inv) && (all.includes(`${day.mon} ${day.day}`) || all.includes(day.dmy))
        && (/\bPAID\b/i.test(all) || /In Process/i.test(all));
    });
    if (payName) kit.records['Payment'] = payName;
    if (PART !== 'office' && payName) r.save({ pay1: payName });

    // ------------------------------------------------------------ no second collection possible
    await r.backToRail(kit);
    await r.invoicesFor(kit, next(), `Finance › Invoices: ${cl.name}`, `Tài chính › Hóa đơn: ${cl.name}`);
    const row = r.invRow(p, inv);
    await row.waitFor({ timeout: 15000 });
    const L3 = `${inv}: Paid, 0.00 due, nothing left to collect (no Receive Payment)`;
    V[L3] = `${inv}: Đã thanh toán, còn 0, không còn gì để thu (không có nút Nhận thanh toán)`;
    await kit.proof(row, L3, (t) => /\bPaid\b/.test(t) && /\b0\.00\b/.test(t) && r.money(v.total).test(t) && !/Receive Payment/.test(t));

    // ------------------------------------------------------------ the cash custody record
    await kit.step(next(), 'Finance › Payments: the cash collected at this visit', 'Tài chính › Thanh toán: tiền mặt thu tại lượt khám này');
    await kit.click(r.sidebar(p, 'Payments'), 3000);
    await r.searchClient(kit);
    const day = r.today();
    const trow = st.txn1 ? r.txnRow(p, st.txn1)   // rehearsal on an old record
      : p.locator('tr.o_data_row').filter({ hasText: `${day.mon} ${day.day},` }).filter({ hasText: r.money(v.total) }).filter({ hasText: /Pay Now/ }).first();
    await trow.waitFor({ timeout: 15000 });
    const ref = ((await trow.innerText()).match(/PAY\d+/) || [''])[0];
    const L4 = `${ref}: 500,000 ₫ cash, Pay Now, collected by the nurse, pending hand-in`;
    V[L4] = `${ref}: 500.000 ₫ tiền mặt, trả ngay, điều dưỡng đã thu, chờ nộp`;
    await kit.proof(trow, L4, (t) => !!ref && /Cash/.test(t) && /Cash Pend/.test(t) && /nurse_hn/.test(t));
    if (PART !== 'office' && ref) r.save({ txn1: ref });
    kit.records['Cash record'] = ref;
    await kit.step(next(), `Open ${ref}`, `Mở ${ref}`);
    await kit.click(trow.locator('td').nth(1), 4000);
    await p.locator('.o_form_view .o_statusbar_status').first().waitFor({ timeout: 15000 }).catch(() => {});
    await kit.hold(1200);
    const L5 = `Cash custody: held by ${nurse.name} until hand-in (Cash Pending Delivery)`;
    V[L5] = `Giữ tiền mặt: ${nurse.name} giữ đến khi nộp (Chờ nộp tiền mặt)`;
    await kit.proof([p.locator('.o_form_view .o_statusbar_status').filter({ visible: true }).first(),
      p.locator('.o_field_widget[name=collected_by_id]').filter({ visible: true }).first()], L5, async (t) => {
      const vals = await kit.fieldValues(['collected_by_id']);
      return /Cash Pending Delivery/.test(t) && (vals.collected_by_id + t).includes(nurse.name)
        && (await p.locator('.o_statusbar_status button.active, .o_statusbar_status .o_arrow_button_current').filter({ hasText: /Cash Pending Delivery/ }).count()) > 0;
    });
    const L6 = `Linked to ${inv}`;
    V[L6] = `Liên kết với ${inv}`;
    await kit.proof(p.locator('.o_field_widget[name=invoice_id]').filter({ visible: true }).first(), L6, async () => {
      const vals = await kit.fieldValues(['invoice_id']);
      return vals.invoice_id.includes(inv);
    });
    await kit.note('The invoice is paid at completion; the cash stays with the nurse until she hands it in under Collections (AR-03)',
      'Hóa đơn được thanh toán khi hoàn thành; tiền mặt do điều dưỡng giữ đến khi nộp tại mục Thu tiền (AR-03)');
    await kit.hold(1500);
  },
};
