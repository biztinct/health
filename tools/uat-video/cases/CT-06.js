// CT-06 Prepaid service package: a template defined in Master Data, bought from the
// client record, a reserved visit completed once by the nurse, a cancelled visit released.
// Three people in one recording: the Owner (template), the Hanoi Operations Manager
// (purchase, bookings, cancellation) and the Hanoi nurse (completes visit 1 in the nurse app).
const c = require('./common');
const owner = c.users.owner;
const om = c.users.omhn;
const nurse = { login: 'nurse_hn', password: c.pw('nurse_hn'), role: 'Nurse, Hanoi', role_vi: 'Điều dưỡng Hà Nội', name: 'Client UAT nurse_hn' };
const client = 'Nguyễn Văn An';
const clientCode = '01_0000126';
const tplName = `UAT-VID Three clinic visits ${new Date(Date.now() + 7 * 3600e3).toISOString().slice(11, 16).replace(':', '')}`;
const terms = 'Three clinic visits, valid 12 weeks (UAT video evidence)';
const clinicalNote = 'UAT ONLY - clinic visit 1 of the prepaid package';
const STOP = process.env.CT06_STOP || '';

module.exports = {
  meta: {
    id: 'CT-06', title: 'Prepaid package: bought for a client, used once, cancelled visit released', short: 'Prepaid package',
    title_vi: 'Gói trả trước: mua cho khách hàng, dùng một lần, hủy lịch được hoàn lại',
    criterion: 'Enter a prepaid package with its value and number of visits; a reserved visit uses one, completing it does not use a second, and cancelling a reserved visit gives it back.',
    data: `Template “${tplName}”: Clinic Visit, 3 visits, 1,500,000 ₫; bought for ${client} (${clientCode}) with invoice and cash payment; nurse ${nurse.login} completes visit 1`,
    expected: 'Package retains value, correct reservation/completion usage and balance.',
    role: 'Owner', role_vi: 'Chủ sở hữu', login: owner.login, password: owner.password,
  },
  proofVi: {
    'Template saved: 3 visits, 1,500,000 ₫, 500,000 ₫ a visit': 'Đã lưu mẫu: 3 lượt, 1.500.000 ₫, 500.000 ₫ mỗi lượt',
    'Checkout: 1,500,000 ₫, invoice and cash payment': 'Thanh toán: 1.500.000 ₫, hóa đơn và tiền mặt',
    'Package bought': 'Đã mua gói',
    'Client’s package: 3 left': 'Gói của khách hàng: còn 3',
    'Visit 1 booked from the package': 'Đã đặt lượt 1 từ gói',
    'Visit 2 booked from the package': 'Đã đặt lượt 2 từ gói',
    'No “price is 0” warning on a package visit': 'Không cảnh báo “giá 0” với lượt trả bằng gói',
    'Visit 1 reserved: 2 left': 'Giữ chỗ lượt 1: còn 2',
    'Nurse app: visit paid from the package': 'Ứng dụng điều dưỡng: lượt khám trả bằng gói',
    'Visit started': 'Đã bắt đầu lượt khám',
    'Clinical note saved, at Vietnam time': 'Đã lưu ghi chú lâm sàng, theo giờ Việt Nam',
    'Visit completed': 'Đã hoàn thành lượt khám',
    'After completion: still 2 left (not counted twice)': 'Sau khi hoàn thành: vẫn còn 2 (không trừ hai lần)',
    'Visit 2 reserved: 1 left': 'Giữ chỗ lượt 2: còn 1',
    'Visit 2 cancelled': 'Đã hủy lượt 2',
    'Cancelled visit given back: 2 left': 'Lượt bị hủy được hoàn lại: còn 2',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ---------------------------------------------------------------- Owner: the template
    await kit.step(next(), 'Settings › Master Data › Package Templates › New', 'Cài đặt › Dữ liệu gốc › Mẫu gói dịch vụ › Mới');
    await kit.area('Settings');
    await kit.click(c.sidebar(p, 'Master Data'), 2500);
    await kit.click(p.getByText('Package Templates', { exact: true }).filter({ visible: true }).first(), 2500);
    await kit.click(p.locator('.o_list_button_add, button').filter({ hasText: /^\s*New\s*$/ }).filter({ visible: true }).first(), 2500);

    await kit.step(next(), `“${tplName}”: Clinic Visit, 3 visits, at the clinic, 1,500,000 ₫`, `“${tplName}”: Khám tại phòng khám, 3 lượt, tại phòng khám, 1.500.000 ₫`);
    await kit.type(p.locator('.oe_title [name=name] input'), tplName, 400);
    await m2o(kit, 'healthcare_package_type_id', 'Clinic', 'Clinic Visit');
    await kit.type(c.field(p, 'healthcare_service_count').locator('input'), '3');
    await m2o(kit, 'healthcare_service_location_id', 'clinic', 'At clinic');
    await kit.type(c.field(p, 'list_price').locator('input'), '1500000');
    await kit.type(c.field(p, 'healthcare_terms').locator('textarea'), terms, 500);

    await kit.step(next(), 'Save the template', 'Lưu mẫu');
    await kit.click(c.saveBtn(p), 2500);
    kit.records['Template'] = tplName;
    await kit.proof(p.locator('.o_form_sheet').first(), 'Template saved: 3 visits, 1,500,000 ₫, 500,000 ₫ a visit', async (t) => {
      const v = await kit.fieldValues(['healthcare_service_count', 'list_price', 'healthcare_price_per_visit']);
      return /action-\d+\/\d+$/.test(p.url()) && v.healthcare_service_count === '3'
        && /1,500,000/.test(v.list_price) && /500,000/.test(v.healthcare_price_per_visit + t);
    });
    if (STOP === 'template') return;

    // ---------------------------------------------------------------- OM: buy it for the client
    await kit.switchUser(next(), om, false);
    await openClient(kit, next);
    await kit.step(next(), 'Quick actions › Buy a package: choose the template', 'Thao tác nhanh › Mua gói: chọn mẫu');
    await kit.click(p.getByRole('button', { name: /Buy a package/ }).first(), 2500);
    await kit.click(p.locator('.pw-card--product', { hasText: tplName }).first(), 900);
    await kit.click(p.locator('.pw-btn--success').filter({ visible: true }).first(), 2500);

    await kit.step(next(), 'Create the invoice and take the cash payment now', 'Tạo hóa đơn và thu tiền mặt ngay');
    await kit.click(p.locator('.pp-option', { hasText: 'Process Payment Now' }).first(), 1200);
    const checkout = p.locator('.pp-dialog').first();
    await kit.proof(checkout, 'Checkout: 1,500,000 ₫, invoice and cash payment', async (t) => {
      const on = await checkout.locator('.pp-toggle--on').count();
      const amount = await checkout.locator('input').last().inputValue().catch(() => '');
      return on === 2 && /1[.,]?500[.,]?000/.test(t + ' ' + amount);
    });
    await kit.click(p.locator('.pw-btn', { hasText: 'Purchase Package' }).first(), 2500);
    await kit.proof(p.locator('.o_notification').filter({ hasText: 'purchased' }).first(), 'Package bought', tplName);
    kit.records['Package'] = `${tplName} (${client})`;

    await packagesTab(kit, next);
    await kit.proof(pkgCard(p), 'Client’s package: 3 left', (t) => /3\s*left/i.test(t) && /0\s*\/\s*3\s*used/i.test(t));
    if (STOP === 'purchase') return;

    // ---------------------------------------------------------------- visit 1: reserved
    const v1 = await bookFromClient(kit, next, 'Visit 1', nurse.name);
    kit.records['Visit 1'] = v1.bk;
    await openClient(kit, next);
    await packagesTab(kit, null);
    await kit.proof(pkgCard(p), 'Visit 1 reserved: 2 left', (t) => /2\s*left/i.test(t));
    if (STOP === 'booking') return;

    // ---------------------------------------------------------------- nurse completes visit 1
    await kit.switchUser(next(), nurse, true);
    await kit.step(next(), `Open today’s visit for ${client} (${v1.hm})`, `Mở lượt khám hôm nay của ${client} (${v1.hm})`);
    const card = p.locator('.booking-card', { hasText: clientCode }).filter({ hasText: v1.hm }).first();
    await kit.click(card.locator('.booking-patient-name'), 2500);
    await kit.proof(p.getByText('Scheduled Visit', { exact: true }).locator('xpath=..').first(),
      'Nurse app: visit paid from the package', (t) => t.includes(tplName));

    await kit.step(next(), 'Start Service', 'Bắt đầu dịch vụ');
    await kit.click(p.locator('button').filter({ hasText: /^\s*Start Service\s*$/ }).filter({ visible: true }).first(), 3500);
    await kit.proof(p.getByText(/^\s*in progress\s*$/i).filter({ visible: true }).first(), 'Visit started', /in progress/i);

    await kit.step(next(), 'Clinical Notes › Add New Clinical Note, then save it', 'Ghi chú lâm sàng › Thêm ghi chú mới, rồi lưu');
    await kit.click(p.locator('button').filter({ hasText: /Clinical Notes/ }).filter({ visible: true }).first(), 2500);
    await kit.click(p.locator('button').filter({ hasText: /Add New Clinical Note/ }).filter({ visible: true }).first(), 2500);
    await kit.type(p.getByPlaceholder('Enter clinical notes...'), clinicalNote, 600);
    await kit.click(p.locator('button').filter({ hasText: /Confirm and Save/ }).filter({ visible: true }).first(), 3500);
    // the note's time must read on the Vietnam clock (it showed UTC before 2026-11-04)
    await kit.proof(p.getByText(clinicalNote).first().locator('xpath=..'), 'Clinical note saved, at Vietnam time', (t) => {
      const now = new Date(Date.now() + 7 * 3600e3);
      const m = t.match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/i);
      if (!t.includes(clinicalNote) || !m) return false;
      let h = Number(m[1]);
      if (m[3]) h = (h % 12) + (m[3].toUpperCase() === 'PM' ? 12 : 0);
      const diff = Math.abs((h * 60 + Number(m[2])) - (now.getUTCHours() * 60 + now.getUTCMinutes()));
      return diff <= 5 || diff >= 1435;
    });
    await kit.click(p.locator('button').filter({ hasText: /^\s*close\s*$/ }).filter({ visible: true }).last(), 1500);

    await kit.step(next(), 'Complete Service (no next appointment needed)', 'Hoàn thành dịch vụ (không cần hẹn lần sau)');
    await kit.click(p.locator('button').filter({ hasText: /Complete Service/ }).filter({ visible: true }).first(), 3500);
    const cancelNext = p.locator('button').filter({ hasText: /^\s*Cancel\s*$/ }).filter({ visible: true }).first();
    if (await cancelNext.count()) await kit.click(cancelNext, 2500);
    await kit.proof(p.locator('.booking-card', { hasText: clientCode }).filter({ hasText: v1.hm }).first(), 'Visit completed', /COMPLETED/);

    // ---------------------------------------------------------------- OM: balance, visit 2, cancel
    await kit.switchUser(next(), om, false);
    await openClient(kit, next);
    await packagesTab(kit, null);
    await kit.proof(pkgCard(p), 'After completion: still 2 left (not counted twice)', (t) => /2\s*left/i.test(t) && /1\s*\/\s*3\s*used/i.test(t));

    const v2 = await bookFromClient(kit, next, 'Visit 2', null);
    kit.records['Visit 2'] = v2.bk;
    const bookingUrl = p.url();
    await openClient(kit, next);
    await packagesTab(kit, null);
    await kit.proof(pkgCard(p), 'Visit 2 reserved: 1 left', (t) => /1\s*left/i.test(t));

    await kit.step(next(), `The client cancels visit 2 (${v2.bk}): More › Cancel Booking`, `Khách hàng hủy lượt 2 (${v2.bk}): Thêm › Hủy lịch hẹn`);
    await p.goto(bookingUrl);
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

    await openClient(kit, next);
    await packagesTab(kit, null);
    await kit.proof(pkgCard(p), 'Cancelled visit given back: 2 left', (t) => /2\s*left/i.test(t) && /1\s*\/\s*3\s*used/i.test(t));
  },
};

// A many2one: type, then pick the option.
async function m2o(kit, name, typed, option) {
  const p = kit.page;
  await kit.type(c.field(p, name).locator('input'), typed, 1200);
  await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: option }).first(), 800);
}

const pkgCard = (p) => p.locator('.ap-card', { hasText: tplName }).first();

// Operations › Clients › open the Hanoi client.
async function openClient(kit, next) {
  const p = kit.page;
  await kit.step(next(), `Operations › Clients › open ${client}`, `Vận hành › Khách hàng › mở ${client}`);
  await kit.area('Operations');
  await kit.click(c.sidebar(p, 'Clients'), 2500);
  await kit.type(p.locator('.o_searchview_input'), client, 300);
  await p.keyboard.press('Enter');
  await kit.hold(2000);
  await kit.click(p.locator('tr.o_data_row', { hasText: client }).locator('td[name=name]').first(), 4000);
}

// Quick actions › Packages: the client's Active Packages tab.
async function packagesTab(kit, next) {
  const p = kit.page;
  if (next) await kit.step(next(), 'Quick actions › Packages', 'Thao tác nhanh › Gói dịch vụ');
  await kit.click(p.getByRole('button', { name: /^\s*Packages\s*$/ }).first(), 2500);
  await pkgCard(p).waitFor({ timeout: 10000 }).catch(() => {});
}

// From the client screen: New booking → Clinic Visit paid from the package, today at the
// first free slot an hour or more from now; optionally the nurse assigned and leading.
async function bookFromClient(kit, next, label, staff) {
  const p = kit.page;
  const vi = label === 'Visit 1' ? 'Lượt 1' : 'Lượt 2';
  if (label === 'Visit 2') await openClient(kit, next);
  await kit.step(next(), `${label}: New booking — Clinic Visit at the Hanoi clinic, paid from the package`, `${vi}: Đặt lịch mới — khám tại phòng khám Hà Nội, trả bằng gói`);
  await kit.click(p.locator('.ws-hero button, .o_form_view button').filter({ hasText: /^\s*New booking\s*$/ }).filter({ visible: true }).first(), 4000);
  await c.qbFill(kit, { service: 'Clinic Visit', duration: '1 hour', facility: 'HN_PK_PKGDVU', location: 'Clinic' });
  const opt = (await c.qbGroup(p, 'Prepaid Package').locator('option').allInnerTexts()).find((t) => t.startsWith(tplName));
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
  await kit.click(p.locator('.qb-modal-confirm'), 4500);
  if (label === 'Visit 1') {
    await kit.proof(p.locator('.ws-hero').first(), 'No “price is 0” warning on a package visit',
      async (t) => t.includes(bk) && !/price is 0/i.test(await p.locator('body').innerText()));
  }
  return { bk, hm, when: c.shownTime(day, hm), url: p.url() };
}
