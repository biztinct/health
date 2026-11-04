// CT-04 Follow-up processed with no booking: closed with a reason (continues CT-03).
const c = require('./common');
const u = c.users.crm;
const q = c.load().quality || {};
const reason = 'UAT declined service';

module.exports = {
  meta: {
    id: 'CT-04', title: 'Follow-up closed with no booking and a reason', short: 'Closed, no booking',
    title_vi: 'Đóng lịch theo dõi, không đặt lịch, có lý do',
    criterion: 'Process an existing follow-up when the client does not proceed: record the no-booking outcome and reason, keep the enquiry history, and create no appointment.',
    data: `Enquiry from CT-02/CT-03: “${q.name}” (${q.code}); reason “${reason}”`,
    expected: 'No-booking follow-up is closed with its reason.',
    ...u,
  },
  proofVi: {
    'Reason box appears for a lost booking': 'Ô lý do hiện ra khi mất lịch hẹn',
    'Listed under Lost': 'Có trong mục Mất',
    'Status: Cancelled, closed without a booking': 'Trạng thái: Đã hủy, đóng mà không đặt lịch',
    'Outcome Booking Lost, reason kept': 'Kết quả Mất lịch hẹn, giữ lý do',
    'Follow-up history kept': 'Lịch sử theo dõi được giữ lại',
    'Follow-up closed, no booking created': 'Đã đóng lịch theo dõi, không tạo lịch hẹn',
  },
  async run(kit) {
    const p = kit.page;
    if (!q.phone) throw new Error('run CT-02 and CT-03 first: no enquiry in state.json');
    await kit.login();

    await kit.step(2, `Open the enquiry “${q.name}” after its follow-up call`, `Mở yêu cầu “${q.name}” sau cuộc gọi theo dõi`);
    await kit.click(c.sidebar(p, 'CONTACTS'), 2500);
    await kit.click(c.listRow(p, q.phone).locator('td').nth(1), 3500);

    await kit.step(3, `The client does not proceed. Outcome: Booking Lost. Reason: “${reason}”`,
      `Khách hàng không tiếp tục. Kết quả: Mất lịch hẹn. Lý do: “${reason}”`);
    await kit.select(c.field(p, 'contact_outcome'), 'Booking Lost');
    await kit.proof(c.field(p, 'booking_lost_reason'), 'Reason box appears for a lost booking', async (_t, l) => l[0].isVisible(), 1800);
    await kit.type(c.field(p, 'booking_lost_reason').locator('textarea'), reason, 600);

    await kit.step(4, 'Save, then find it under the Lost tab', 'Lưu, rồi tìm trong thẻ Mất');
    await kit.click(c.saveBtn(p), 1800);
    await kit.click(c.breadcrumbContacts(p), 2500);
    await kit.click(p.locator('.nav-link, a, button, span').filter({ hasText: /^\s*Lost\s*$/ }).first(), 2500);
    const row = c.listRow(p, q.phone);
    await kit.proof(row, 'Listed under Lost', (t) => t.includes(q.phone) && /Cancelled|Lost/i.test(t));

    await kit.step(5, 'Reopen it: closed, reason kept, history kept, no booking', 'Mở lại: đã đóng, giữ lý do, giữ lịch sử, không có lịch hẹn');
    await kit.click(row.locator('td').nth(1), 3500);
    kit.records['Contact'] = q.code;
    await kit.proof([c.heroChip(p), c.nextStep(p)], 'Status: Cancelled, closed without a booking',
      (t) => /Cancelled/.test(t) && /Closed without a booking/.test(t));
    await kit.proof(c.statusCard(p), 'Outcome Booking Lost, reason kept', async () => {
      const v = await kit.fieldValues(['contact_outcome', 'booking_lost_reason']);
      return v.contact_outcome === 'Booking Lost' && v.booking_lost_reason === reason;
    });
    await kit.proof(c.field(p, 'follow_up_notes'), 'Follow-up history kept', async () =>
      (await kit.fieldValues(['follow_up_notes'])).follow_up_notes === 'UAT call back requested');
    await kit.proof([c.glanceRow(p, 'Follow-up'), c.glanceRow(p, 'Last visit'), c.people(p)], 'Follow-up closed, no booking created',
      (t) => /Follow-up\s*Closed/i.test(t) && /Last visit\s*None/i.test(t) && /Not linked yet/i.test(t));
  },
};
