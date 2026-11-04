// CT-02 Quality call: details and condition recorded, no booking.
const c = require('./common');
const u = c.users.crm;
const phone = c.phone();
const hhmm = phone.slice(6, 10);
const name = `UAT-VID Quality Enquirer ${hhmm}`;

module.exports = {
  meta: {
    id: 'CT-02', title: 'Quality enquiry recorded without a booking', short: 'Quality enquiry',
    title_vi: 'Ghi nhận cuộc gọi chất lượng, không đặt lịch',
    criterion: 'Record a genuine enquiry with the caller’s details and requested service even when they do not book; it stays available for review and follow-up with no booking created.',
    data: `Fictional caller “${name}”, ${phone}, service interest Medical Examination (general consultation)`,
    expected: 'Contact retains all entered details and condition without a booking.',
    ...u,
  },
  proofVi: {
    'Contact created': 'Đã tạo liên hệ',
    'Name and phone saved': 'Đã lưu tên và số điện thoại',
    'Status: New, no booking yet': 'Trạng thái: Mới, chưa có lịch hẹn',
    'Service interest: Medical Examination': 'Dịch vụ quan tâm: Khám bệnh',
    'Still listed after leaving the record': 'Vẫn có trong danh sách sau khi rời hồ sơ',
    'Reopened: details unchanged, no booking': 'Mở lại: thông tin không đổi, không có lịch hẹn',
  },
  async run(kit) {
    const p = kit.page;
    await kit.login();

    await kit.step(2, 'Open CRM › Contacts', 'Mở CRM › Liên hệ');
    await kit.click(c.sidebar(p, 'CONTACTS'), 2500);

    await kit.step(3, 'A caller asks about a general consultation. Open New Contact', 'Người gọi hỏi về tư vấn tổng quát. Mở Liên hệ mới');
    await kit.click(p.getByRole('button', { name: 'New Contact' }), 1500);
    await kit.type(p.getByPlaceholder('Full name'), name);
    await kit.type(p.getByPlaceholder('Phone number'), phone, 800);
    await kit.click(p.locator('.nc-footer button', { hasText: 'Next' }), 1500);

    await kit.step(4, 'The caller is the client. Service interest: Medical Examination (general consultation)', 'Người gọi là khách hàng. Dịch vụ quan tâm: Khám bệnh (tư vấn tổng quát)');
    await kit.click(p.locator('.nc-radio-btn, button').filter({ hasText: /^\s*Client \(Self\)\s*$/ }).first(), 700);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Medical Examination\s*$/ }).first(), 900);

    await kit.step(5, 'Save the contact. No booking is made', 'Lưu liên hệ. Không đặt lịch');
    await kit.click(p.locator('.nc-footer button', { hasText: 'Create Contact' }), 2500);
    await kit.proof(p.locator('.nc-success-banner'), 'Contact created', name);
    const code = ((await p.locator('.nc-success-code').innerText().catch(() => '')) || '').replace(/[()]/g, '').trim();
    await kit.click(p.locator('button').filter({ hasText: /^\s*Open Record\s*$/ }).first(), 3500);

    await kit.step(6, 'The saved record: name, phone, status and service', 'Hồ sơ đã lưu: tên, số điện thoại, trạng thái và dịch vụ');
    kit.records['Contact'] = code || (await p.locator('.ws-hero .ws-chip--code').first().innerText()).trim();
    c.save({ quality: { name, phone, code: kit.records['Contact'] } });
    await kit.proof(c.hero(p), 'Name and phone saved', (t) => t.includes(name) && t.includes(phone));
    await kit.proof([c.heroChip(p), c.glanceRow(p, 'Last visit'), c.people(p)], 'Status: New, no booking yet',
      (t) => /\bNew\b/.test(t) && /Last visit\s*None/i.test(t) && /Not linked yet/i.test(t));
    await kit.click(p.locator('a.nav-link', { hasText: 'Client Details' }).first(), 1500);
    await kit.proof(c.field(p, 'service_interest_id'), 'Service interest: Medical Examination', async () =>
      /medical examination/i.test((await kit.fieldValues(['service_interest_id'])).service_interest_id));

    await kit.step(7, 'Leave the record, then find it again in the list', 'Rời hồ sơ, rồi tìm lại trong danh sách');
    await kit.click(c.breadcrumbContacts(p), 2500);
    const row = c.listRow(p, phone);
    await kit.proof(row, 'Still listed after leaving the record', (t) => t.includes(name) && t.includes(phone));

    await kit.step(8, 'Reopen it: the details are unchanged and there is no booking', 'Mở lại: thông tin không đổi và không có lịch hẹn');
    await kit.click(row.locator('td').nth(1), 3500);
    await kit.click(p.locator('a.nav-link', { hasText: 'Client Details' }).first(), 1200);
    await kit.proof([c.hero(p), c.field(p, 'service_interest_id')], 'Reopened: details unchanged, no booking', async (t) => {
      const v = await kit.fieldValues(['service_interest_id']);
      const glance = await c.glanceRow(p, 'Last visit').innerText();
      return t.includes(name) && t.includes(phone) && /medical examination/i.test(v.service_interest_id) && /None/i.test(glance);
    });
  },
};
