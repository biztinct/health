// CT-01 Junk call: no client name and no condition.
const c = require('./common');
const u = c.users.crm;
const phone = c.phone();

module.exports = {
  meta: {
    id: 'CT-01', title: 'Junk call with no name and no condition', short: 'Junk call',
    title_vi: 'Cuộc gọi rác không tên, không tình trạng',
    criterion: 'Record a junk enquiry even when the caller gives neither a name nor a condition; mark it junk/spam, keep the contact event and create no booking.',
    data: `New fictional junk call from ${phone}; name and condition left blank`,
    expected: 'Junk contact can be recorded without name or condition.',
    ...u,
  },
  proofVi: {
    'Saved as junk': 'Đã lưu là cuộc gọi rác',
    'Listed under Spam, no client name': 'Có trong mục Rác, không có tên khách hàng',
    'Status: Spam Call': 'Trạng thái: Cuộc gọi rác',
    'Contact time recorded': 'Đã ghi thời điểm liên hệ',
    'No booking, no client created': 'Không tạo lịch hẹn, không tạo khách hàng',
    'Condition / service left blank': 'Tình trạng / dịch vụ để trống',
  },
  async run(kit) {
    const p = kit.page;
    await kit.login();

    await kit.step(2, 'Open CRM › Contacts', 'Mở CRM › Liên hệ');
    await kit.click(c.sidebar(p, 'CONTACTS'), 2500);

    await kit.step(3, `A junk call comes in from ${phone}. Open New Contact`, `Có cuộc gọi rác từ ${phone}. Mở Liên hệ mới`);
    await kit.click(p.getByRole('button', { name: 'New Contact' }), 1500);

    await kit.step(4, 'Enter only the phone number. Name and condition stay blank', 'Chỉ nhập số điện thoại. Để trống tên và tình trạng');
    await kit.type(p.getByPlaceholder('Phone number'), phone, 800);
    await kit.hold(800);

    await kit.step(5, 'Mark it as junk', 'Đánh dấu là cuộc gọi rác');
    await kit.click(p.getByRole('button', { name: 'Mark Junk' }), 600);
    await kit.proof(p.locator('.o_notification').filter({ hasText: 'junk' }).first(), 'Saved as junk', 'marked as junk', 2500);

    await kit.step(6, 'Open the Spam tab and find the call', 'Mở thẻ Rác và tìm cuộc gọi');
    await kit.click(p.locator('.nav-link, a, button, span').filter({ hasText: /^\s*Spam\s*$/ }).first(), 2500);
    const row = c.listRow(p, phone);
    await kit.proof(row, 'Listed under Spam, no client name', (t) => t.includes(phone) && /spam/i.test(t) && /unknown/i.test(t));

    await kit.step(7, 'Reopen the record and check what was saved', 'Mở lại hồ sơ và kiểm tra dữ liệu đã lưu');
    await kit.click(row.locator('td').nth(1), 3000);
    await kit.brandCheck('CT-01 record');
    kit.records['Contact'] = (await p.locator('.ws-hero .ws-chip--code').first().innerText()).trim();
    await kit.proof(c.heroChip(p), 'Status: Spam Call', 'spam');
    await kit.proof(c.heroFact(p, 'First contact'), 'Contact time recorded', /First contact\s*\w{3} \d{1,2}, \d{1,2}:\d{2}/);
    await kit.proof([c.glanceRow(p, 'Last visit'), c.people(p)], 'No booking, no client created',
      (t) => /Last visit\s*None/i.test(t) && /Not linked yet/i.test(t));

    await kit.step(8, 'Client Details: no client name and no condition or service', 'Thông tin khách hàng: không có tên, không có tình trạng hay dịch vụ');
    await kit.click(p.getByRole('tab', { name: 'Client Details' }).or(p.locator('a.nav-link', { hasText: 'Client Details' })).first(), 1500);
    const pane = p.locator('.tab-pane.active');
    await kit.proof(pane, 'Condition / service left blank', async () => {
      const v = await kit.fieldValues(['client_name', 'service_interest_id', 'reason_for_contact_id', 'service_requirements'], pane);
      return Object.values(v).every((x) => !x);
    });
  },
};
