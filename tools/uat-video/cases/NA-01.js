// NA-01 Medical report for the Ministry of Health (row stays Partial: the official MOH layout
// and mandatory fields still await the client's approval). The Owner opens the fictional
// visit BK3832, finds MOH Report under Print, and checks the report preview on screen:
// company and clinic, booking, visit date, doctor, patient, service and notes.
// Nothing is sent to the Ministry.
const c = require('./common');
const a = require('./adm_common');
const owner = a.users.owner;
const BK = { name: 'BK3832', id: 9666, client: 'Nguyễn Văn An', clinic: 'HN_PK_PKGDVU', doctor: 'Client UAT doctor_hn' };
const PREVIEW = `https://carejiox.com/report/html/health_fieldservice.report_moh_document/${BK.id}`;

module.exports = {
  meta: {
    id: 'NA-01', title: 'Ministry of Health report for a visit', short: 'MOH report',
    title_vi: 'Báo cáo Bộ Y tế cho một lượt khám',
    criterion: 'Generate the medical report for the Ministry of Health from the test visit and check the patient, visit, staff, service and clinical information. The official MOH layout and mandatory fields still have to be approved by the client: rendering alone does not establish format acceptance.',
    data: `Fictional visit ${BK.name} for ${BK.client} at ${BK.clinic}, doctor ${BK.doctor}. Report preview only; nothing is sent to the Ministry`,
    expected: 'Report renders with correct information and agreed MOH format (format awaiting client approval).',
    ...owner,
  },
  proofVi: {
    'The visit: BK3832, Nguyễn Văn An, HN_PK_PKGDVU, Client UAT doctor_hn': 'Lượt khám: BK3832, Nguyễn Văn An, HN_PK_PKGDVU, Client UAT doctor_hn',
    'Print offers MOH Report': 'Mục In có Báo cáo Bộ Y tế',
    'Report header: company and clinic HN_PK_PKGDVU': 'Đầu báo cáo: công ty và phòng khám HN_PK_PKGDVU',
    'Report: booking BK3832, visit 14/10/2026 10:00, Clinic Visit, doctor': 'Báo cáo: lịch hẹn BK3832, ngày khám 14/10/2026 10:00, khám tại phòng khám, bác sĩ',
    'Report: patient Nguyễn Văn An, 58, male, address': 'Báo cáo: bệnh nhân Nguyễn Văn An, 58 tuổi, nam, địa chỉ',
    'Report: service given and visit notes': 'Báo cáo: dịch vụ đã thực hiện và ghi chú lượt khám',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await kit.step(next(), `Operations › Bookings › ${BK.name}`, `Vận hành › Lịch hẹn › ${BK.name}`);
    await a.area(kit, 'Operations');
    await a.bookingsList(kit);
    await kit.click(p.locator('button, a, span').filter({ hasText: /^\s*All Dates\s*$/ }).filter({ visible: true }).first(), 2500);
    await a.listSearch(kit, BK.name);
    const row = p.locator('tr.o_data_row', { hasText: BK.name }).first();
    await kit.click(row.locator('td').nth(1), 4500);
    await c.hero(p).waitFor({ timeout: 15000 });
    await kit.proof([c.hero(p), p.locator('.ws-panel--glance, .ws-panel').filter({ hasText: 'Staff' }).first()],
      'The visit: BK3832, Nguyễn Văn An, HN_PK_PKGDVU, Client UAT doctor_hn', (t) =>
        t.includes(BK.name) && t.includes(BK.client) && t.includes(BK.clinic) && t.includes(BK.doctor));

    await kit.step(next(), 'Back to the list, tick the booking, open Print', 'Quay lại danh sách, chọn lịch hẹn, mở In');
    await a.bookingsList(kit);
    await kit.click(p.locator('button, a, span').filter({ hasText: /^\s*All Dates\s*$/ }).filter({ visible: true }).first(), 2500);
    await a.listSearch(kit, BK.name);
    await kit.click(row.locator('td.o_list_record_selector').first(), 1500);
    await kit.click(p.locator('.o_control_panel button').filter({ hasText: /^\s*Print\s*$/ }).first(), 1500);
    const menu = p.locator('.dropdown-menu, .o-dropdown--menu').filter({ visible: true }).first();
    await kit.proof(menu, 'Print offers MOH Report', /MOH Report/);
    await p.keyboard.press('Escape');

    await kit.step(next(), 'Open the MOH Report preview on screen', 'Mở bản xem trước Báo cáo Bộ Y tế trên màn hình');
    await p.goto(PREVIEW);
    await p.locator('.page').first().waitFor({ timeout: 30000 });
    await kit._state({});
    await kit.hold(1500);
    await kit.brandCheck('MOH preview');
    const head = p.locator('.page table').first();
    await kit.proof(head, 'Report header: company and clinic HN_PK_PKGDVU', (t) => /VIET UC/.test(t) && t.includes(`Clinic / Phòng khám: ${BK.clinic}`));
    const rows = p.locator('.page .row').filter({ has: p.locator('strong') });
    const ref = [rows.filter({ hasText: 'Booking Reference' }).first(), rows.filter({ hasText: 'Service Type' }).first()];
    await kit.proof(ref, 'Report: booking BK3832, visit 14/10/2026 10:00, Clinic Visit, doctor', (t) =>
      t.includes(BK.name) && t.includes('14/10/2026 10:00') && t.includes('Clinic Visit') && t.includes(BK.doctor));
    await kit.proof(p.locator('tr', { hasText: BK.client }).first(), 'Report: patient Nguyễn Văn An, 58, male, address', (t) =>
      t.includes(BK.client) && /\b58\b/.test(t) && /Male/.test(t) && /Hà Nội/.test(t));
    await kit.proof(p.locator('tr', { hasText: 'Fictional test service' }).first(), 'Report: service given and visit notes', (t) =>
      t.includes('Fictional test service') && /UAT ONLY - simulated care/.test(t));
    await kit.note('The official MOH layout and mandatory fields still await the client’s approval. Nothing is sent to the Ministry.',
      'Mẫu báo cáo chính thức của Bộ Y tế và các trường bắt buộc vẫn đang chờ khách hàng phê duyệt. Không gửi gì tới Bộ.');
    await kit.hold(3000);
  },
};
