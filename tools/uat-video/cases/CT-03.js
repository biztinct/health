// CT-03 Follow-up correctly logged (continues the CT-02 enquiry).
const c = require('./common');
const u = c.users.crm;
const q = c.load().quality || {};
const when = c.vnAt(2, 10, 0);
const note = 'UAT call back requested';

module.exports = {
  meta: {
    id: 'CT-03', title: 'Follow-up logged and kept after reopening', short: 'Follow-up logged',
    title_vi: 'Ghi lịch theo dõi và giữ nguyên sau khi mở lại',
    criterion: 'Record the next follow-up date and time, the note and the pending outcome on the right contact; they must survive saving, leaving and reopening so another staff member can continue.',
    data: `Enquiry from CT-02: “${q.name}” (${q.code}); follow-up ${when.shown} Vietnam time; note “${note}”`,
    expected: 'Follow-up date, note and outcome persist.',
    ...u,
  },
  proofVi: {
    'Follow-up entered': 'Đã nhập lịch theo dõi',
    'Listed as a lead after leaving': 'Hiển thị là khách tiềm năng sau khi rời hồ sơ',
    'Reopened: date, time, note and outcome kept': 'Mở lại: ngày, giờ, ghi chú và kết quả được giữ nguyên',
    'Next step shows the follow-up': 'Bước tiếp theo hiển thị lịch theo dõi',
  },
  async run(kit) {
    const p = kit.page;
    if (!q.phone) throw new Error('run CT-02 first: no enquiry in state.json');
    await kit.login();

    await kit.step(2, `Open CRM › Contacts and open the enquiry “${q.name}”`, `Mở CRM › Liên hệ và mở yêu cầu “${q.name}”`);
    await kit.click(c.sidebar(p, 'CONTACTS'), 2500);
    await kit.click(c.listRow(p, q.phone).locator('td').nth(1), 3500);

    await kit.step(3, `Outcome: Pending Follow-up. Next follow-up ${when.shown}. Note: “${note}”`,
      `Kết quả: Chờ theo dõi. Lần theo dõi tiếp theo ${when.shown}. Ghi chú: “${note}”`);
    await kit.select(c.field(p, 'contact_outcome'), 'Pending Follow-up');
    await kit.datetime(c.field(p, 'next_follow_up_date'), when.typed);
    await kit.type(c.field(p, 'follow_up_notes').locator('textarea'), note, 600);
    await kit.proof(c.statusCard(p), 'Follow-up entered', async (t) => {
      const v = await kit.fieldValues(['contact_outcome', 'follow_up_notes']);
      return v.contact_outcome === 'Pending Follow-up' && t.includes(when.shown) && v.follow_up_notes === note;
    });

    await kit.step(4, 'Save, then leave the record', 'Lưu, rồi rời hồ sơ');
    await kit.click(c.saveBtn(p), 1800);
    await kit.click(c.breadcrumbContacts(p), 2500);
    const row = c.listRow(p, q.phone);
    await kit.proof(row, 'Listed as a lead after leaving', (t) => t.includes(q.phone) && /Lead/.test(t));

    await kit.step(5, 'Reopen it and compare with what was entered', 'Mở lại và so sánh với thông tin đã nhập');
    await kit.click(row.locator('td').nth(1), 3500);
    kit.records['Contact'] = q.code;
    await kit.proof(c.statusCard(p), 'Reopened: date, time, note and outcome kept', async (t) => {
      const v = await kit.fieldValues(['contact_outcome', 'next_follow_up_date', 'follow_up_notes']);
      return v.contact_outcome === 'Pending Follow-up' && t.includes(when.shown) && v.follow_up_notes === note;
    });
    await kit.proof(c.nextStep(p), 'Next step shows the follow-up', /follow/i);
  },
};
