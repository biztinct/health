// BK-02 The client's personal details, caregiver and referrer match the client workbook;
// repeat visits reuse the same client. Read-only (nothing is created or changed).
// Source: Test_Data rows 6-9 (TC-04, TC-05): Trần Thị Bình, 01_0000226.
const c = require('./common');
const b = require('./bk_common');
const u = b.users.omhn;
const W = {
  name: 'Trần Thị Bình', code: '01_0000226', dob: 'Jul 2, 1941', gender: 'Female',
  phone1: '0900000101', phone2: '0900000212', address: '45 Ngõ 102 Trường Chinh, Đống Đa, Hà Nội',
  caregiver: 'Lê Thu Hà', referrer: 'Bác sĩ Phạm Minh', source: 'Referred',
  first: 'BK3835', repeat: 'BK3836',
};

module.exports = {
  meta: {
    id: 'BK-02', title: 'Client personal details, caregiver and referrer match the workbook', short: 'Correct personal details',
    title_vi: 'Thông tin cá nhân, người chăm sóc và người giới thiệu khớp bảng tính',
    criterion: 'Store and display the supplied client identity, date of birth, gender, phone numbers and address accurately. Keep the designated contact/caregiver and referrer. Repeat visits reuse the correct client; the main contact is not assumed to be the patient.',
    data: `Client workbook Test_Data rows 6-9 (TC-04, TC-05): ${W.name} (${W.code}), born 02/07/1941, Female, phones ${W.phone1} and ${W.phone2}, ${W.address}; contact person ${W.caregiver} (daughter); source ${W.source} by ${W.referrer} (partner GP); bookings ${W.first} (new patient) and ${W.repeat} (repeat)`,
    expected: 'Every supplied personal, caregiver and referrer value matches.',
    ...u,
  },
  proofVi: {
    'Name, client ID, phone 1, address, gender': 'Họ tên, mã khách hàng, số điện thoại 1, địa chỉ, giới tính',
    'Date of birth 02/07/1941, Female': 'Ngày sinh 02/07/1941, Nữ',
    'Both phone numbers 0900000101 and 0900000212': 'Cả hai số điện thoại 0900000101 và 0900000212',
    'Source: referred, by Bác sĩ Phạm Minh': 'Nguồn: được giới thiệu, bởi Bác sĩ Phạm Minh',
    'Designated contact: Lê Thu Hà (not the patient)': 'Người liên hệ chỉ định: Lê Thu Hà (không phải bệnh nhân)',
    'Caregiver Lê Thu Hà and referrer Bác sĩ Phạm Minh': 'Người chăm sóc Lê Thu Hà và người giới thiệu Bác sĩ Phạm Minh',
    'Both visits on this one client record': 'Cả hai lượt khám trên cùng một hồ sơ khách hàng',
    'BK3835 (new patient): same client ID': 'BK3835 (khách mới): cùng mã khách hàng',
    'BK3836 (repeat): same client ID, not a new client': 'BK3836 (lặp lại): cùng mã khách hàng, không tạo khách mới',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await kit.step(next(), `Operations › Clients: search ${W.name}`, `Vận hành › Khách hàng: tìm ${W.name}`);
    await kit.area('Operations');
    await kit.click(c.sidebar(p, 'Clients'), 2500);
    await kit.type(p.locator('.o_searchview_input'), W.name, 300);
    await p.keyboard.press('Enter');
    await kit.hold(2000);
    const rows = p.locator('tr.o_data_row', { hasText: W.name });
    const nRows = await rows.count();
    await kit.click(rows.locator('td[name=name]').first(), 4000);

    await kit.step(next(), 'Identity on the client record, against the workbook', 'Thông tin nhận dạng trên hồ sơ, so với bảng tính');
    await kit.proof(p.locator('.ws-hero').first(), 'Name, client ID, phone 1, address, gender',
      (t) => nRows === 1 && t.includes(W.name) && t.includes(W.code) && t.includes(W.phone1) && t.includes(W.address) && t.includes(W.gender), 3000);
    const f = (name) => c.field(p, name);
    const lab = (txt) => p.locator('label, .o_form_label').filter({ hasText: new RegExp(`^\\s*${txt}\\s*[*?]?\\s*$`) }).filter({ visible: true }).first();
    await kit.proof([lab('Date of Birth'), f('birth_date'), lab('Gender'), p.locator('.o_notebook .o_field_widget[name=gender_id]').filter({ visible: true }).first()],
      'Date of birth 02/07/1941, Female', async () => {
        const v = await kit.fieldValues(['birth_date'], p.locator('.o_notebook'));
        const g = await kit.fieldValues(['gender_id'], p.locator('.o_notebook'));
        return v.birth_date === W.dob && g.gender_id === W.gender;
      }, 3000);

    await kit.step(next(), 'Contact numbers: the workbook gives two phone numbers', 'Số điện thoại: bảng tính có hai số');
    const nb = p.locator('.o_notebook .tab-pane.active').first();
    const fld = (name) => nb.locator(`.o_field_widget[name=${name}]`).filter({ visible: true }).first();
    await kit.proof([fld('phone'), fld('mobile')], 'Both phone numbers 0900000101 and 0900000212', async () => {
      const v = await kit.fieldValues(['phone', 'mobile'], nb);
      return v.phone === W.phone1 && v.mobile === W.phone2;
    }, 3200);
    await kit.proof([fld('source_type'), fld('intake_referring_doctor_id')],
      'Source: referred, by Bác sĩ Phạm Minh', async () => {
        const v = await kit.fieldValues(['source_type', 'intake_referring_doctor_id'], nb);
        return /^referr/i.test(v.source_type) && v.intake_referring_doctor_id === W.referrer;
      }, 3000);

    await kit.step(next(), 'People: the designated contact person; Healthcare Relationships: caregiver and referrer', 'Người liên quan: người liên hệ chỉ định; Quan hệ chăm sóc: người chăm sóc và người giới thiệu');
    await kit.proof(c.people(p), 'Designated contact: Lê Thu Hà (not the patient)', async (t) => {
      const v = await kit.fieldValues(['main_contact_id'], c.people(p));
      return /Main contact/i.test(t) && v.main_contact_id === W.caregiver && v.main_contact_id !== W.name;
    }, 2600);
    await b.tab(kit, 'Healthcare Relationships');
    const net = p.locator('.o_notebook .tab-pane.active').first();
    await kit.proof(net, 'Caregiver Lê Thu Hà and referrer Bác sĩ Phạm Minh', (t) => {
      const cg = t.indexOf('CAREGIVERS'), py = t.indexOf('PAYERS'), rf = t.indexOf('REFERRERS'), em = t.indexOf('EMERGENCY');
      return cg >= 0 && t.slice(cg, py > cg ? py : undefined).includes(W.caregiver) && rf >= 0 && t.slice(rf, em > rf ? em : undefined).includes(W.referrer);
    }, 3200);

    await kit.step(next(), `Bookings tab: the first visit ${W.first} and the repeat visit ${W.repeat}`, `Thẻ Lịch hẹn: lượt đầu ${W.first} và lượt lặp lại ${W.repeat}`);
    await b.tab(kit, 'Bookings');
    await kit.proof(p.locator('.o_notebook .tab-pane.active').first(), 'Both visits on this one client record', (t) => t.includes(W.first) && t.includes(W.repeat), 2800);

    for (const [bk, lbl] of [[W.first, 'BK3835 (new patient): same client ID'], [W.repeat, 'BK3836 (repeat): same client ID, not a new client']]) {
      await kit.step(next(), `Open ${bk}: the booking points to the same client record`, `Mở ${bk}: lịch hẹn trỏ đúng hồ sơ khách hàng`);
      await b.openBooking(kit, bk, true);
      await kit.proof([p.locator('.ws-hero').first(), c.people(p)], lbl, (t) => t.includes(bk) && t.includes(W.name) && t.includes(W.code), 2600);
    }
  },
};
