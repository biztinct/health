// CT-06 Prepaid service package: entered, reserved, completed once, cancelled visit released.
// Two people in one recording: the Owner (office) and the Hanoi nurse (nurse app), who
// completes visit 1.
const c = require('./common');
const owner = c.users.owner;
const nurse = { login: 'nurse_hn', password: c.pw('nurse_hn'), role: 'Nurse, Hanoi', role_vi: 'Điều dưỡng Hà Nội', name: 'Client UAT nurse_hn' };
const client = 'Nguyễn Văn An';
const clientCode = '01_0000126';
const clientPhone = '0900000100';
const pkgName = `UAT-VID Three clinic visits ${new Date(Date.now() + 7 * 3600e3).toISOString().slice(11, 16).replace(':', '')}`;
const note = 'Three prepaid clinic visits (UAT video evidence)';
const clinicalNote = 'UAT ONLY - clinic visit 1 of the prepaid package';
const STOP = process.env.CT06_STOP || '';

// The package screen's counters, read from the form.
async function counts(kit) {
  const v = await kit.fieldValues(['total_services', 'consumed_services', 'remaining_services']);
  const n = (x) => Number(String(x).replace(/[^\d]/g, '')) || 0;
  return { total: n(v.total_services), used: n(v.consumed_services), left: n(v.remaining_services) };
}

module.exports = {
  meta: {
    id: 'CT-06', title: 'Prepaid package: entered, used once, cancelled visit released', short: 'Prepaid package',
    title_vi: 'Gói trả trước: nhập gói, dùng một lần, hủy lịch được hoàn lại',
    criterion: 'Enter a prepaid package with its value and number of visits; a reserved visit uses one, completing it does not use a second, and cancelling a reserved visit gives it back.',
    data: `Client ${client} (${clientCode}); package “${pkgName}”: 3 clinic visits, 1,500,000 ₫; nurse ${nurse.login} completes visit 1 in the nurse app`,
    expected: 'Package retains value, correct reservation/completion usage and balance.',
    role: 'Owner', role_vi: 'Chủ sở hữu', login: owner.login, password: owner.password,
  },
  proofVi: {
    'Package saved: 3 visits, 1,500,000 ₫, 3 left': 'Đã lưu gói: 3 lượt, 1.500.000 ₫, còn 3',
    'Visit 1 booked from the package': 'Đã đặt lượt 1 từ gói',
    'Visit 2 booked from the package': 'Đã đặt lượt 2 từ gói',
    'Visit 1 reserved: 2 of 3 left': 'Đã giữ chỗ lượt 1: còn 2/3',
    'Nurse app: visit paid from the package': 'Ứng dụng điều dưỡng: lượt khám trả bằng gói',
    'Visit started': 'Đã bắt đầu lượt khám',
    'Clinical note saved': 'Đã lưu ghi chú lâm sàng',
    'Visit completed': 'Đã hoàn thành lượt khám',
    'After completion: still 2 left (not counted twice)': 'Sau khi hoàn thành: vẫn còn 2 (không trừ hai lần)',
    'Visit 2 reserved: 1 left': 'Giữ chỗ lượt 2: còn 1',
    'Visit 2 cancelled': 'Đã hủy lượt 2',
    'Cancelled visit given back: 2 left': 'Lượt bị hủy được hoàn lại: còn 2',
    'Package history shows each step': 'Lịch sử gói ghi lại từng bước',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ---------------------------------------------------------------- the package
    await kit.step(next(), 'Open Finance › Service Packages and create a new package', 'Mở Tài chính › Gói dịch vụ và tạo gói mới');
    await kit.area('Finance');
    await kit.click(c.sidebar(p, 'Service Packages'), 2500);
    await kit.click(p.locator('.o_list_button_add, button').filter({ hasText: /^\s*New\s*$/ }).first(), 2500);

    await kit.step(next(), `“${pkgName}” for ${client}: Clinic Visit, 3 visits, 1,500,000 ₫`, `“${pkgName}” cho ${client}: Khám tại phòng khám, 3 lượt, 1.500.000 ₫`);
    await kit.type(p.locator('.oe_title [name=name] input'), pkgName, 400);
    await kit.type(c.field(p, 'patient_id').locator('input'), client, 1500);
    await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: client }).first(), 1000);
    await kit.select(c.field(p, 'service_type'), 'Clinic Visit');
    await kit.type(c.field(p, 'total_services').locator('input'), '3');
    await kit.type(c.field(p, 'package_price').locator('input'), '1500000');
    await kit.type(c.field(p, 'package_notes').locator('textarea'), note, 600);

    await kit.step(next(), 'Save the package', 'Lưu gói');
    await kit.click(c.saveBtn(p), 2500);
    kit.records['Package'] = pkgName;
    await kit.proof(p.locator('.o_form_sheet').first(), 'Package saved: 3 visits, 1,500,000 ₫, 3 left', async (t) => {
      const k = await counts(kit);
      const v = await kit.fieldValues(['name', 'package_price']);
      // saved, not just typed: the address carries the new record's number
      return /action-\d+\/\d+$/.test(p.url()) && k.total === 3 && k.left === 3
        && /1,500,000/.test(v.package_price) && v.name === pkgName;
    });
    if (STOP === 'package') return;

    // ---------------------------------------------------------------- visit 1: reserved
    const v1 = await bookFromPackage(kit, next, 'Visit 1', nurse.name);
    kit.records['Visit 1'] = v1.bk;
    await openPackage(kit, next);
    await kit.proof(p.locator('.o_form_sheet').first(), 'Visit 1 reserved: 2 of 3 left', async () => {
      const k = await counts(kit); return k.total === 3 && k.left === 2;
    });
    if (STOP === 'booking') return;

    // ---------------------------------------------------------------- visit 1: the nurse completes it
    await kit.switchUser(next(), nurse, true);
    await kit.step(next(), `Open today’s visit for ${client} (${v1.hm})`, `Mở lượt khám hôm nay của ${client} (${v1.hm})`);
    const card = p.locator('.booking-card', { hasText: clientCode }).filter({ hasText: v1.hm }).first();
    await kit.click(card.locator('.booking-patient-name'), 2500);
    await kit.proof(p.getByText('Scheduled Visit', { exact: true }).locator('xpath=..').first(),
      'Nurse app: visit paid from the package', (t) => t.includes(pkgName));

    await kit.step(next(), 'Start Service', 'Bắt đầu dịch vụ');
    await kit.click(p.locator('button').filter({ hasText: /^\s*Start Service\s*$/ }).filter({ visible: true }).first(), 3500);
    await kit.proof(p.getByText(/^\s*in progress\s*$/i).filter({ visible: true }).first(), 'Visit started', /in progress/i);

    await kit.step(next(), 'Clinical Notes › Add New Clinical Note, then save it', 'Ghi chú lâm sàng › Thêm ghi chú mới, rồi lưu');
    await kit.click(p.locator('button').filter({ hasText: /Clinical Notes/ }).filter({ visible: true }).first(), 2500);
    await kit.click(p.locator('button').filter({ hasText: /Add New Clinical Note/ }).filter({ visible: true }).first(), 2500);
    await kit.type(p.getByPlaceholder('Enter clinical notes...'), clinicalNote, 600);
    await kit.click(p.locator('button').filter({ hasText: /Confirm and Save/ }).filter({ visible: true }).first(), 3500);
    await kit.proof(p.getByText(clinicalNote).first().locator('xpath=..'), 'Clinical note saved', clinicalNote);
    await kit.click(p.locator('button').filter({ hasText: /^\s*close\s*$/ }).filter({ visible: true }).last(), 1500);

    await kit.step(next(), 'Complete Service (no next appointment needed)', 'Hoàn thành dịch vụ (không cần hẹn lần sau)');
    await kit.click(p.locator('button').filter({ hasText: /Complete Service/ }).filter({ visible: true }).first(), 3500);
    const cancelNext = p.locator('button').filter({ hasText: /^\s*Cancel\s*$/ }).filter({ visible: true }).first();
    if (await cancelNext.count()) await kit.click(cancelNext, 2500);
    await kit.proof(p.locator('.booking-card', { hasText: clientCode }).filter({ hasText: v1.hm }).first(), 'Visit completed', /COMPLETED/);

    // ---------------------------------------------------------------- back to the office
    await kit.switchUser(next(), owner, false);
    await openPackage(kit, next);
    await kit.proof(p.locator('.o_form_sheet').first(), 'After completion: still 2 left (not counted twice)', async () => {
      const k = await counts(kit); return k.total === 3 && k.left === 2 && k.used === 1;
    });

    // ---------------------------------------------------------------- visit 2: reserved, then cancelled
    const v2 = await bookFromPackage(kit, next, 'Visit 2', null);
    kit.records['Visit 2'] = v2.bk;
    await openPackage(kit, next);
    await kit.proof(p.locator('.o_form_sheet').first(), 'Visit 2 reserved: 1 left', async () => {
      const k = await counts(kit); return k.left === 1;
    });

    await kit.step(next(), `The client cancels visit 2 (${v2.bk}): More › Cancel Booking`, `Khách hàng hủy lượt 2 (${v2.bk}): Thêm › Hủy lịch hẹn`);
    await p.goto(v2.url);
    await kit.hold(3500);
    await kit.click(p.locator('.ws-hero button, .o_form_view button').filter({ hasText: /^\s*More\s*$/ }).filter({ visible: true }).first(), 900);
    await kit.click(p.locator('.dropdown-item, .o-dropdown-item').filter({ hasText: /^\s*Cancel Booking\s*$/ }).filter({ visible: true }).first(), 2000);
    const sure = p.locator('.modal-content', { hasText: 'Are you sure' }).locator('button').filter({ hasText: /^\s*Ok\s*$/ }).first();
    if (await sure.count()) await kit.click(sure, 2500);
    const dlg = p.locator('.modal-content').last();
    await kit.click(dlg.locator('.o_field_widget[name=cancellation_reason_id] input'), 1200);
    await kit.click(p.locator('.o-autocomplete--dropdown-item').first(), 800);
    await kit.type(dlg.locator('.o_field_widget[name=cancellation_notes] textarea'), 'UAT: client cancelled visit 2 of the prepaid package', 500);
    await kit.click(dlg.locator('button[name=action_confirm_cancellation]'), 3500);
    await kit.proof(p.locator('.ws-hero').first(), 'Visit 2 cancelled', /Cancel/i);

    await openPackage(kit, next);
    await kit.proof(p.locator('.o_form_sheet').first(), 'Cancelled visit given back: 2 left', async () => {
      const k = await counts(kit); return k.total === 3 && k.left === 2;
    });
    await kit.proof(p.locator('.o-mail-Chatter, .o-mail-Thread').first(), 'Package history shows each step',
      (t) => /Service Reserved/i.test(t) && /Released/i.test(t));
  },
};

// Operations › Clients › Book: Clinic Visit from the package, today at the first free
// slot an hour or more from now, optionally with the nurse assigned and leading.
async function bookFromPackage(kit, next, label, staff) {
  const p = kit.page;
  const vi = label === 'Visit 1' ? 'Lượt 1' : 'Lượt 2';
  await kit.step(next(), `${label}: Operations › Clients › ${client} › Book (+)`, `${vi}: Vận hành › Khách hàng › ${client} › Đặt lịch (+)`);
  await kit.area('Operations');
  await kit.click(c.sidebar(p, 'Clients'), 2500);
  await kit.type(p.locator('.o_searchview_input'), client, 300);
  await p.keyboard.press('Enter');
  await kit.hold(2000);
  // the Hanoi client (an HCMC client has the same name); the row's Book button is the "+" icon
  await kit.click(p.locator('tr.o_data_row', { hasText: clientPhone }).locator('button[name=action_create_fso]').first(), 4000);

  await kit.step(next(), 'Clinic Visit at the Hanoi clinic, paid from the prepaid package', 'Khám tại phòng khám Hà Nội, trả bằng gói trả trước');
  await c.qbFill(kit, { service: 'Clinic Visit', duration: '1 hour', facility: 'HN_PK_PKGDVU', location: 'Clinic' });
  const opt = (await c.qbGroup(p, 'Prepaid Package').locator('option').allInnerTexts()).find((t) => t.startsWith(pkgName));
  if (!opt) throw new Error('package not offered in Quick Booking');
  await kit.select(c.qbGroup(p, 'Prepaid Package'), opt.trim());
  const day = await c.qbPickDay(kit, 0);
  const hm = await c.qbPickSlot(kit, c.slotsFromNow(60));
  await kit.note(`Today at ${hm}`, `Hôm nay lúc ${hm}`);
  if (staff) {
    await kit.step(next(), `Assign ${staff} to the visit`, `Phân công ${staff} cho lượt khám`);
    await kit.click(p.locator('.qb-staff-chip', { hasText: staff }).first(), 800);
    await kit.select(c.qbGroup(p, 'Lead Staff'), staff);
  }

  await kit.step(next(), 'Create the booking', 'Tạo lịch hẹn');
  await kit.click(p.locator('.qb-btn-create'), 4000);
  const done = p.locator('.qb-modal-actions').locator('xpath=..');
  await kit.proof(done, `${label} booked from the package`, /BK\d+/);
  const bk = ((await done.innerText()).match(/BK\d{3,}/) || [''])[0];
  await kit.click(p.locator('.qb-modal-confirm'), 4000);
  return { bk, hm, when: c.shownTime(day, hm), url: p.url() };
}

async function openPackage(kit, next) {
  const p = kit.page;
  await kit.step(next(), 'Open the package', 'Mở gói');
  await kit.area('Finance');
  await kit.click(c.sidebar(p, 'Service Packages'), 2500);
  await kit.click(c.listRow(p, pkgName).locator('td').nth(1), 3000);
}
