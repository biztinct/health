// MB-07 Nurse app: the close questions. The nurse checks the quote, chooses how the client pays,
// presses Complete Service, and the app asks whether a next visit is wanted: a blank reason is
// refused, a valid answer (Other + explanation, no follow-up) is accepted and kept.
// MB07_STOP=wizard stops at the payment step (practice: completing posts a real test invoice).
const a = require('./as_common');
const m = require('./mb_common');
const nurse = m.users.nurse;
const om = m.users.om;
const cl = m.client;
const T = m.TC;
const STOP = process.env.MB07_STOP || '';
const CHECKED = 'Checked with the client: 2 injections as booked';
const REASON = 'UAT ONLY - fictional test visit completed; the client will call if she needs another visit';

module.exports = {
  meta: {
    id: 'MB-07', title: 'Nurse app close questions completed', short: 'Mobile close questions',
    title_vi: 'Ứng dụng điều dưỡng: hoàn tất câu hỏi kết thúc',
    criterion: 'Complete the mobile close questions, including the next-visit decision and the required reason when no future visit is wanted. A missing required answer must be rejected; the submitted answers and follow-up choice are kept against the visit and client.',
    data: `Today’s visit ${m.load().bk || '(from MB-02)'} for ${cl.name} (${cl.code}), notes entered in MB-06; quote ${T.code} × ${T.qty} = 210,000 ₫ checked; client pays later; reason “Other: ${REASON}”, Need to Follow up not ticked; nurse ${nurse.login}`,
    expected: 'Required answers are enforced and saved.',
    ...nurse,
  },
  proofVi: {
    'Quote: injection × 2 at 105,000 ₫ = 210,000 ₫': 'Báo giá: tiêm × 2, 105.000 ₫ = 210.000 ₫',
    'Quote total 210,000 ₫, tax 0': 'Tổng báo giá 210.000 ₫, thuế 0',
    'Quote checked and saved': 'Đã kiểm tra và lưu báo giá',
    'Payment timing: Pay Later': 'Thời điểm thanh toán: Trả sau',
    'Create Invoice Now ticked': 'Đã chọn Tạo hóa đơn ngay',
    'Amount 210,000 ₫, payment later': 'Số tiền 210.000 ₫, thanh toán sau',
    'Close question: is a next visit wanted?': 'Câu hỏi kết thúc: có cần lượt khám tiếp theo không?',
    'Blank reason refused: “Please select a reason”': 'Lý do trống bị từ chối: “Vui lòng chọn lý do”',
    'Answer: Other, with the explanation; no follow-up': 'Trả lời: Khác, có giải thích; không cần theo dõi',
    'Answer accepted; the visit is completed': 'Câu trả lời được chấp nhận; lượt khám đã hoàn thành',
    'Booking: Visit close answer, reason, nurse and time': 'Lịch hẹn: câu trả lời kết thúc, lý do, điều dưỡng và thời gian',
    'Client record: no further visits wanted, with the reason': 'Hồ sơ khách hàng: không muốn lượt khám tiếp, có lý do',
  },

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.id) throw new Error('no visit in mb_state.json: run MB-02 first');
    let n = 0;
    const next = () => ++n;
    // Native pop-ups (alert) are not drawn into the recording: note each message and show it as a caption.
    const pops = [];
    p.on('dialog', async (d) => { pops.push(d.message()); console.log('  pop-up:', d.message()); await new Promise((r) => setTimeout(r, 400)); await d.accept().catch(() => {}); });

    await m.asNurse(kit, next());
    await kit.step(next(), `Open the visit in progress for ${cl.name}`, `Mở lượt khám đang thực hiện của ${cl.name}`);
    await m.openVisit(kit, st);

    // ------------------------------------------------------------ quote and payment choices
    await kit.step(next(), 'View service: check the services with the client', 'Xem dịch vụ: kiểm tra dịch vụ cùng khách hàng');
    await kit.click(m.btn(p, /^\s*(receipt\s*)?View service\s*$/), 3000);
    const quote = p.locator('.invoice-modal').filter({ visible: true }).first();
    await quote.waitFor({ timeout: 15000 });
    await kit.proof(quote.locator('.invoice-item-card').first(), 'Quote: injection × 2 at 105,000 ₫ = 210,000 ₫', async (t) => {
      const qty = await quote.locator('.qty-cell input').first().inputValue().catch(() => '');
      return t.includes(T.product) && Number(qty) === T.qty && m.money(T.unit).test(t) && m.money(T.total).test(t);
    });
    await kit.proof(quote.locator('.invoice-totals').first(), 'Quote total 210,000 ₫, tax 0', (t) => /Tax\s*0\b/.test(t) && m.money(T.total).test(t));
    await kit.step(next(), 'Note the check and Save Quote', 'Ghi chú kiểm tra và Lưu báo giá');
    await kit.type(quote.locator('textarea').first(), CHECKED, 500);
    await kit.click(quote.locator('button').filter({ hasText: /Save Quote/ }).first(), 3500);
    await kit.proof(quote.locator('.success-message').first(), 'Quote checked and saved', /verified successfully/i);

    await kit.step(next(), 'Payment: the client will pay later by bank transfer; create the invoice now', 'Thanh toán: khách hàng trả sau bằng chuyển khoản; tạo hóa đơn ngay');
    await kit.click(quote.locator('button').filter({ hasText: /^\s*payment\s*Payment\s*$|^\s*Payment\s*$/ }).first(), 2500);
    const wiz = p.locator('.payment-wizard-modal').filter({ visible: true }).first();
    await wiz.waitFor({ timeout: 15000 });
    await kit.click(wiz.locator('label', { hasText: /^\s*Pay Later\s*$/ }).first(), 900);
    const invoiceNow = wiz.locator('label', { hasText: 'Create Invoice Now' }).locator('input[type=checkbox]').first();
    if (!(await invoiceNow.isChecked())) await kit.click(invoiceNow, 600);
    await kit.proof(wiz.locator('.form-section').first(), 'Payment timing: Pay Later', async () => wiz.locator('input[type=radio][value=pay_later]').isChecked());
    await kit.proof(wiz.locator('label', { hasText: 'Create Invoice Now' }).first(), 'Create Invoice Now ticked', async () => invoiceNow.isChecked(), 2400);
    await kit.proof(wiz.locator('.info-grid').first(), 'Amount 210,000 ₫, payment later', (t) => m.money(T.total).test(t) && /Later/.test(t), 2600);
    if (STOP === 'wizard') { await kit.click(wiz.locator('button', { hasText: /^\s*Cancel\s*$/ }).first(), 1000); return; }

    // ------------------------------------------------------------ finish, then the close questions
    await kit.step(next(), 'Complete Service', 'Hoàn thành dịch vụ');
    await kit.click(wiz.locator('button', { hasText: /Complete Service/ }).last(), 6000);
    const qa = p.locator('.next-visit-modal').filter({ visible: true }).first();
    await qa.waitFor({ timeout: 30000 });
    m.save({ completedAt: new Date().toISOString() });
    await kit.proof(qa, 'Close question: is a next visit wanted?', (t) => /Schedule Next Appointment\?/.test(t) && t.includes(cl.name) && /does not need or want a next visit/.test(t));

    await kit.step(next(), 'The client does not want another visit: choose that answer', 'Khách hàng không muốn lượt khám tiếp theo: chọn câu trả lời đó');
    await kit.click(qa.locator('button', { hasText: /does not need or want a next visit/ }).first(), 1500);
    const sec = qa.locator('.no-future-visit-section').first();
    await kit.step(next(), 'Submit without choosing a reason', 'Gửi mà không chọn lý do');
    const before = pops.length;
    await kit.click(sec.locator('button', { hasText: /^\s*Submit\s*$/ }).first(), 2000);
    const said = pops.slice(before).join(' / ');
    if (said) await kit.note(`The app’s pop-up message: “${said}”`, `Thông báo bật lên của ứng dụng: “${said}”`);
    await kit.proof(sec, 'Blank reason refused: “Please select a reason”', async () =>
      /Please select a reason/.test(said) && (await qa.isVisible()) && (await sec.locator('select').inputValue()) === '');

    await kit.step(next(), 'Reason: Other, with an explanation; Need to Follow up left unticked', 'Lý do: Khác, có giải thích; không đánh dấu Cần theo dõi');
    await kit.select(sec, 'Other');
    await kit.type(sec.locator('textarea').first(), REASON, 600);
    const follow = sec.locator('input[type=checkbox]').first();
    await kit.proof(sec, 'Answer: Other, with the explanation; no follow-up', async () =>
      (await sec.locator('select').inputValue()) === 'other' && (await sec.locator('textarea').first().inputValue()) === REASON && !(await follow.isChecked()));
    await kit.step(next(), 'Submit', 'Gửi');
    const before2 = pops.length;
    await kit.click(sec.locator('button', { hasText: /^\s*Submit\s*$/ }).first(), 3500);
    const said2 = pops.slice(before2).join(' / ');
    if (said2) await kit.note(`The app’s pop-up message: “${said2}”`, `Thông báo bật lên của ứng dụng: “${said2}”`);
    await m.card(p, st).waitFor({ timeout: 15000 }).catch(() => {});
    await kit.proof(m.card(p, st), 'Answer accepted; the visit is completed', async (t) =>
      /Noted/.test(said2) && !(await qa.isVisible().catch(() => false)) && /completed/i.test(t));
    m.save({ closeReason: `Other: ${REASON}` });

    // ------------------------------------------------------------ the saved answer, afterwards
    await m.asStaff(kit, next(), om);
    await m.openBooking(kit, next(), st.bk, `Office: Operations › Bookings › open ${st.bk}`, `Văn phòng: Vận hành › Lịch hẹn › mở ${st.bk}`);
    await kit.step(next(), 'Overview tab: the Visit close card', 'Thẻ Tổng quan: thẻ Kết thúc lượt khám');
    const ov = p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Overview\s*$/ }).first();
    if (await ov.count()) await kit.click(ov, 2000);
    const vc = p.locator('[name=visit_close_card]').filter({ visible: true }).first();
    await vc.waitFor({ timeout: 10000 }).catch(() => {});
    const day = m.today();
    await kit.proof(vc, 'Booking: Visit close answer, reason, nurse and time', async (t) => {
      const v = await kit.fieldValues(['visit_close_answer', 'visit_close_reason', 'visit_close_by_id', 'visit_close_date'], vc);
      const all = Object.values(v).join(' ') + ' ' + t;
      return /No further visits wanted/.test(all) && all.includes(REASON.slice(0, 40)) && all.includes(nurse.name)
        && all.includes(`${day.mon} ${day.day}`);
    });
    await a.openClient(kit, next(), cl);
    const care = p.locator('.o_field_widget[name=visit_close_status]').filter({ visible: true }).first();
    await care.waitFor({ timeout: 10000 }).catch(() => {});
    await kit.proof(care, 'Client record: no further visits wanted, with the reason', async () => {
      const t = await care.innerText();
      return /No further visits wanted/.test(t) && t.includes(REASON.slice(0, 30)) && t.includes(st.bk) && t.includes(nurse.name)
        && t.includes(`${m.p2(day.day)}/${m.p2(day.d.getUTCMonth() + 1)}/${day.d.getUTCFullYear()}`);
    });
  },
};
