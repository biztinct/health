// AS-01 Correct assignment: the Hanoi Operations Manager books a visit, assigns the Hanoi
// nurse as lead and the Hanoi doctor as doctor from Assign Staff; the booking's care team,
// the staff assignments and the nurse app all agree.
const c = require('./common');
const a = require('./as_common');
const om = a.users.omhn;
const nurse = a.users.nurse;
const doctor = a.users.doctor;
const DAYS = 5;
const STOP = process.env.AS01_STOP || '';

module.exports = {
  meta: {
    id: 'AS-01', title: 'Correct assignment - nurse lead and doctor', short: 'Correct assignment',
    title_vi: 'Phân công đúng - điều dưỡng phụ trách chính và bác sĩ',
    criterion: 'Assign the appropriate eligible nurse or doctor to the correct booking, with the intended lead/support role and appointment time. The staff assignment, booking care team and mobile visibility must agree so the assigned person can accept and perform the visit.',
    data: `New clinic visit for ${a.client.name} (${a.client.code}), HN_PK_PKGDVU, ${a.vnDay(DAYS).mon} ${a.vnDay(DAYS).day}; lead nurse ${nurse.name}, doctor ${doctor.name}; nurse app as ${nurse.login}`,
    expected: 'Assignment and booking care-team fields stay consistent.',
    ...om,
  },
  proofVi: {
    'Booking created, nobody assigned yet: next step Assign Staff': 'Đã tạo lịch hẹn (Hà Nội), chưa phân công ai: bước tiếp theo Phân công nhân sự',
    'New assignment opens for this booking at the visit time': 'Phân công mới mở cho đúng lịch hẹn, đúng giờ khám',
    'Nurse assignment saved: lead role, visit time': 'Đã lưu phân công điều dưỡng: phụ trách chính, đúng giờ khám',
    'Doctor assignment saved: doctor role, visit time': 'Đã lưu phân công bác sĩ: vai trò bác sĩ, đúng giờ khám',
    'Booking: waiting for the staff to accept': 'Lịch hẹn: đang chờ nhân sự chấp nhận',
    'Care team: nurse is assigned staff and lead, doctor is assigned doctor': 'Nhóm chăm sóc: điều dưỡng được phân công và phụ trách chính, bác sĩ được phân công',
    'Assignments: both on this booking, at the visit time': 'Phân công: cả hai trên lịch hẹn này, đúng giờ khám',
    'Nurse app: the offer for this booking, same date and time': 'Ứng dụng điều dưỡng: lời mời cho lịch hẹn này, cùng ngày giờ',
    'Nurse app: the visit is in her list for that day': 'Ứng dụng điều dưỡng: lượt khám có trong danh sách ngày đó',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ------------------------------------------------------------ OM: the booking
    await a.openClient(kit, next());
    const b = await a.quickBook(kit, next, { days: DAYS, times: ['09:00', '09:30', '10:00', '10:30', '11:00', '14:00', '14:30', '15:00'] });
    kit.records['Booking'] = `${b.bk} (${b.shown})`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Booking created, nobody assigned yet: next step Assign Staff',
      (t) => t.includes(b.bk) && t.includes(b.shown) && t.includes('Hà Nội') && /Assign Staff/.test(t) && !/Waiting for staff/i.test(t));
    if (STOP === 'booking') return;

    // ------------------------------------------------------------ OM: Assign Staff
    await kit.step(next(), 'Next step › Assign Staff: the staff schedule opens for this booking', 'Bước tiếp theo › Phân công nhân sự: lịch nhân sự mở cho lịch hẹn này');
    await kit.click(a.nextCard(p).locator('button').filter({ hasText: /Assign Staff/ }).first(), 5000);
    await kit.step(next(), 'Switch to the list and press New to add an assignment', 'Chuyển sang danh sách và nhấn Mới để thêm phân công');
    await kit.click(p.locator('.o_switch_view.o_list').filter({ visible: true }).first(), 3500);
    await kit.click(p.locator('.o_list_button_add, button').filter({ hasText: /^\s*New\s*$/ }).filter({ visible: true }).first(), 3500);
    await kit.proof(infoBox(p),
      'New assignment opens for this booking at the visit time', (t) => t.includes(b.bk) && t.includes(b.shown));

    await assign(kit, next, nurse.name, 'Client UAT nurse', 'Lead Staff', 'Nurse');
    await kit.proof([infoBox(p), staffBox(p)], 'Nurse assignment saved: lead role, visit time', async (t) => {
      const v = await kit.fieldValues(['staff_id', 'assignment_role']);
      if (process.env.DEBUG) console.log('  dbg', p.url(), JSON.stringify(v));
      return /health\.staff\.assignment\/\d+$/.test(p.url()) && v.staff_id.includes(nurse.name) && /Lead Staff/.test(v.assignment_role)
        && (await infoBox(p).innerText()).includes(b.shown);
    });
    kit.records['Nurse assignment'] = await refOf(p);

    await kit.step(next(), 'Add the doctor too: New', 'Thêm cả bác sĩ: Mới');
    await kit.click(p.locator('.o_form_button_create, button').filter({ hasText: /^\s*New\s*$/ }).filter({ visible: true }).first(), 3500);
    await assign(kit, next, doctor.name, 'Client UAT doctor', 'Doctor', 'Doctor');
    await kit.proof([infoBox(p), staffBox(p)], 'Doctor assignment saved: doctor role, visit time', async (t) => {
      const v = await kit.fieldValues(['staff_id', 'assignment_role', 'fso_id']);
      return /health\.staff\.assignment\/\d+$/.test(p.url()) && v.staff_id.includes(doctor.name) && /Doctor/.test(v.assignment_role)
        && (await infoBox(p).innerText()).includes(b.shown) && (await infoBox(p).innerText()).includes(b.bk);
    });
    kit.records['Doctor assignment'] = await refOf(p);
    if (STOP === 'assign') return;

    // ------------------------------------------------------------ OM: booking agrees
    await a.openBooking(kit, next(), b.bk, `Reopen the booking: Operations › Bookings › ${b.bk}`, `Mở lại lịch hẹn: Vận hành › Lịch hẹn › ${b.bk}`);
    await kit.proof(a.nextCard(p), 'Booking: waiting for the staff to accept',
      (t) => /Waiting for staff to accept/i.test(t) && t.includes(nurse.name) && /Change Staff/.test(t));
    await kit.step(next(), 'Overview › Care team', 'Tổng quan › Nhóm chăm sóc');
    const team = p.locator('.o_field_widget[name=assigned_staff_ids]').filter({ visible: true }).first();
    if (!(await team.count())) {
      const fold = p.getByText(/^\s*Care team\s*$/i).filter({ visible: true }).first();
      if (await fold.count()) await kit.click(fold, 1200);
    }
    const teamBox = p.locator('.o_field_widget[name=assigned_doctor_ids]').filter({ visible: true }).first()
      .locator('xpath=ancestor::*[.//*[@name="assigned_staff_ids"] and .//*[@name="lead_staff_id"]][1]');
    await kit.proof(teamBox, 'Care team: nurse is assigned staff and lead, doctor is assigned doctor', async () => {
      const v = await a.fieldTexts(p, ['assigned_staff_ids', 'lead_staff_id', 'assigned_doctor_ids']);
      return v.assigned_staff_ids.includes(nurse.name) && v.lead_staff_id.includes(nurse.name)
        && v.assigned_doctor_ids.includes(doctor.name) && !v.assigned_staff_ids.includes(doctor.name);
    });

    await a.viewAssignments(kit, next());
    const rows = p.locator('tr.o_data_row');
    await kit.proof([rows.nth(0), rows.nth(1)], 'Assignments: both on this booking, at the visit time', async () => {
      const all = await rows.allInnerTexts();
      const nr = all.find((t) => t.includes(nurse.name)) || '';
      const dr = all.find((t) => t.includes(doctor.name)) || '';
      return all.length === 2 && [nr, dr].every((t) => t.includes(b.bk) && t.includes(b.shown) && /Assigned/.test(t))
        && /Lead Staff/.test(nr) && /Doctor/.test(dr);
    });
    if (STOP === 'om') return;

    // ------------------------------------------------------------ nurse app: same offer
    await kit.switchUser(next(), nurse, true);
    await kit.step(next(), 'Open the notifications bell: the new offer', 'Mở chuông thông báo: lời mời mới');
    await a.openBell(kit);
    const card = a.offerCard(p, b.bk);
    await card.scrollIntoViewIfNeeded().catch(() => {});
    await kit.proof(card, 'Nurse app: the offer for this booking, same date and time',
      (t) => t.includes(b.bk) && t.includes(a.client.name) && t.includes(`${b.day.dmy} ${b.hm}`) && /Accept/.test(t) && /Decline/.test(t));
    await kit.click(p.locator('.notif-panel-close').first(), 1200);

    await kit.step(next(), `Day view: go to ${b.day.mon} ${b.day.day}`, `Xem theo ngày: chuyển đến ${b.day.day}/${b.day.d.getUTCMonth() + 1}`);
    await a.pwaGoToDay(kit, DAYS);
    const visit = p.locator('.booking-card', { hasText: a.client.code }).filter({ hasText: b.hm }).first();
    await kit.proof(visit, 'Nurse app: the visit is in her list for that day',
      (t) => t.includes(a.client.name) && t.includes(b.hm));
  },
};

const panel = (p, a, b) => p.locator('div').filter({ visible: true }).filter({ has: p.locator(`[name=${a}]`) }).filter({ has: p.locator(`[name=${b}]`) }).last();
const infoBox = (p) => panel(p, 'fso_id', 'assignment_date');
const staffBox = (p) => panel(p, 'staff_id', 'assignment_role');
async function refOf(p) {
  const t = await p.locator('.o_form_view').filter({ visible: true }).first().innerText().catch(() => '');
  const m = t.match(/SA\d{4,}/);
  return m ? m[0] : (p.url().match(/\/(\d+)$/) || [, '?'])[1];
}

// On the new assignment form: staff, role, save.
async function assign(kit, next, name, typed, role, who) {
  const p = kit.page;
  const roleVi = role === 'Doctor' ? 'Bác sĩ' : 'Phụ trách chính';
  await kit.step(next(), `${who}: ${name}, role ${role}; save`, `${who === 'Doctor' ? 'Bác sĩ' : 'Điều dưỡng'}: ${name}, vai trò ${roleVi}; lưu`);
  await kit.type(c.field(p, 'staff_id').locator('input'), typed, 1500);
  await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: name }).first(), 1000);
  await kit.select(c.field(p, 'assignment_role'), role);
  await kit.click(c.saveBtn(p), 3000);
}
