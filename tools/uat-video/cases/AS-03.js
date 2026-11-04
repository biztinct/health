// AS-03 Rejected and reassigned: the Hanoi nurse declines the offer in the nurse app; the
// Operations Manager sees the decline, reassigns the visit to the Hanoi doctor, the doctor
// accepts, and only the doctor's assignment is active.
const c = require('./common');
const a = require('./as_common');
const om = a.users.omhn;
const nurse = a.users.nurse;
const doctor = a.users.doctor;
const DAYS = 6;
const STOP = process.env.AS03_STOP || '';

module.exports = {
  meta: {
    id: 'AS-03', title: 'Assignment declined and reassigned', short: 'Declined and reassigned',
    title_vi: 'Phân công bị từ chối và phân công lại',
    criterion: 'The assigned staff member can reject an offer and the operations manager can see that response. Reassign the booking to another eligible person, obtain their acceptance, and ensure that the superseded assignment is no longer the active assignment.',
    data: `New clinic visit for ${a.client.name} (${a.client.code}), HN_PK_PKGDVU, ${a.vnDay(DAYS).mon} ${a.vnDay(DAYS).day}, offered to ${nurse.name} (declines in the nurse app); reassigned to ${doctor.name} (accepts as ${doctor.login})`,
    expected: 'Rejection is visible and replacement assignment reaches confirmed state.',
    ...om,
  },
  proofVi: {
    'Booking sent to the nurse: waiting for her to accept': 'Lịch hẹn đã gửi cho điều dưỡng: đang chờ chấp nhận',
    'Nurse app: the offer for this booking': 'Ứng dụng điều dưỡng: lời mời cho lịch hẹn này',
    'Declined: “Assignment declined.”': 'Đã từ chối: “Đã từ chối phân công.”',
    'The offer has left her list': 'Lời mời đã rời khỏi danh sách của cô ấy',
    'Booking back to Assign Staff: nobody active': 'Lịch hẹn trở lại bước Phân công nhân sự: không còn ai hiệu lực',
    'The nurse’s assignment shows Cancelled': 'Phân công của điều dưỡng hiển thị Đã hủy',
    'History: the nurse herself declined it': 'Lịch sử: chính điều dưỡng đã từ chối',
    'Replacement saved: the doctor, at the visit time': 'Đã lưu người thay thế: bác sĩ, đúng giờ khám',
    'Doctor’s app: the offer for this booking': 'Ứng dụng của bác sĩ: lời mời cho lịch hẹn này',
    'Accepted: “Assignment confirmed!”': 'Đã chấp nhận: “Đã xác nhận phân công!”',
    'Booking now Assigned, next step Start Service': 'Lịch hẹn nay ở trạng thái Đã phân công, bước tiếp theo Bắt đầu dịch vụ',
    'Assignments: nurse Cancelled, doctor Staff Confirmed, only one active': 'Phân công: điều dưỡng Đã hủy, bác sĩ Nhân sự đã xác nhận, chỉ một còn hiệu lực',
    'Care team: the doctor; the nurse who declined is gone': 'Nhóm chăm sóc: bác sĩ; điều dưỡng đã từ chối không còn',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ------------------------------------------------------------ OM books with the nurse
    await a.openClient(kit, next());
    const b = await a.quickBook(kit, next, { days: DAYS, times: ['14:00', '14:30', '15:00', '15:30', '16:00', '16:30'], nurse: nurse.name });
    kit.records['Booking'] = `${b.bk} (${b.shown})`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Booking sent to the nurse: waiting for her to accept',
      (t) => t.includes(b.bk) && t.includes(b.shown) && /Waiting for staff to accept/i.test(t) && t.includes(nurse.name));
    if (STOP === 'booking') return;

    // ------------------------------------------------------------ nurse declines
    await kit.switchUser(next(), nurse, true);
    await kit.step(next(), `Notifications bell: the offer for ${b.bk}`, `Chuông thông báo: lời mời cho ${b.bk}`);
    await a.openBell(kit);
    let card = a.offerCard(p, b.bk);
    await kit.proof(card, 'Nurse app: the offer for this booking', (t) => t.includes(b.bk) && t.includes(`${b.day.dmy} ${b.hm}`));
    await kit.step(next(), 'She cannot take it: Decline', 'Cô ấy không nhận được: Từ chối');
    await kit.click(card.locator('.notif-btn-decline'), 300);
    const toast = p.getByText('Assignment declined.').first();
    await toast.waitFor({ timeout: 8000 }).catch(() => {});
    await kit.proof(toast, 'Declined: “Assignment declined.”', 'Assignment declined.', 2200);
    await kit.hold(1500);
    kit._proofVi[`The offer for ${b.bk} has left her list`] = `Lời mời cho ${b.bk} đã rời khỏi danh sách của cô ấy`;
    await kit.proof(p.locator('.notif-panel').first(), `The offer for ${b.bk} has left her list`, (t) => !t.includes(b.bk), 2200);
    await kit.click(p.locator('.notif-panel-close').first(), 1000);
    if (STOP === 'decline') return;

    // ------------------------------------------------------------ OM sees it, reassigns
    await kit.switchUser(next(), om, false);
    await a.openBooking(kit, next(), b.bk, `Reopen the booking: Operations › Bookings › ${b.bk}`, `Mở lại lịch hẹn: Vận hành › Lịch hẹn › ${b.bk}`);
    await kit.proof([a.statusChip(p), a.nextCard(p)], 'Booking back to Assign Staff: nobody active',
      (t) => /Confirmed/.test(t) && /Assign Staff/.test(t) && !/Waiting for staff/i.test(t));
    const bookingUrl = p.url();
    await a.viewAssignments(kit, next(), 'Quick actions › View Assignments: the nurse’s answer', 'Thao tác nhanh › Xem phân công: phản hồi của điều dưỡng');
    const nRow = p.locator('tr.o_data_row', { hasText: nurse.name }).first();
    await kit.proof(nRow, 'The nurse’s assignment shows Cancelled', (t) => t.includes(b.bk) && /Cancelled/.test(t));
    await kit.step(next(), 'Open it: the history says who declined', 'Mở ra: lịch sử cho biết ai đã từ chối');
    await kit.click(nRow.locator('td').nth(1), 4000);
    await kit.proof(p.locator('.o-mail-Message').filter({ hasText: /Cancelled/ }).first(), 'History: the nurse herself declined it',
      (t) => t.includes(nurse.name) && /Assigned/.test(t) && /Cancelled/.test(t));

    await kit.step(next(), `Back to the booking › Assign Staff › New: ${doctor.name}, role Doctor`, `Quay lại lịch hẹn › Phân công nhân sự › Mới: ${doctor.name}, vai trò Bác sĩ`);
    await p.goto(bookingUrl);
    await p.locator('.ws-hero').first().waitFor({ timeout: 15000 }).catch(() => {});
    await kit.hold(1500);
    await kit.click(a.nextCard(p).locator('button').filter({ hasText: /Assign Staff/ }).first(), 5000);
    await kit.click(p.locator('.o_switch_view.o_list').filter({ visible: true }).first(), 3500);
    await kit.click(p.locator('.o_list_button_add, button').filter({ hasText: /^\s*New\s*$/ }).filter({ visible: true }).first(), 3500);
    await kit.type(c.field(p, 'staff_id').locator('input'), 'Client UAT doctor', 1500);
    await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: doctor.name }).first(), 1000);
    await kit.select(c.field(p, 'assignment_role'), 'Doctor');
    await kit.click(c.saveBtn(p), 3000);
    const panel = (x, y) => p.locator('div').filter({ visible: true }).filter({ has: p.locator(`[name=${x}]`) }).filter({ has: p.locator(`[name=${y}]`) }).last();
    await kit.proof([panel('fso_id', 'assignment_date'), panel('staff_id', 'assignment_role')], 'Replacement saved: the doctor, at the visit time', async (t) => {
      const v = await kit.fieldValues(['staff_id', 'assignment_role']);
      return /health\.staff\.assignment\/\d+$/.test(p.url()) && v.staff_id.includes(doctor.name) && /Doctor/.test(v.assignment_role)
        && t.includes(b.bk) && t.includes(b.shown);
    });
    if (STOP === 'reassign') return;

    // ------------------------------------------------------------ doctor accepts
    await kit.switchUser(next(), doctor, true);
    await kit.note('Offers are answered in the nurse app (the staff web app has no Accept button)', 'Lời mời được trả lời trong ứng dụng điều dưỡng (ứng dụng web nhân viên không có nút Chấp nhận)');
    await kit.step(next(), `Notifications bell: the offer for ${b.bk}`, `Chuông thông báo: lời mời cho ${b.bk}`);
    await a.openBell(kit);
    card = a.offerCard(p, b.bk);
    await kit.proof(card, 'Doctor’s app: the offer for this booking', (t) => t.includes(b.bk) && t.includes(`${b.day.dmy} ${b.hm}`));
    await kit.step(next(), 'Accept', 'Chấp nhận');
    await kit.click(card.locator('.notif-btn-accept'), 300);
    const ok = p.getByText('Assignment confirmed!').first();
    await ok.waitFor({ timeout: 8000 }).catch(() => {});
    await kit.proof(ok, 'Accepted: “Assignment confirmed!”', 'Assignment confirmed!', 2200);
    await kit.click(p.locator('.notif-panel-close').first(), 1000);

    // ------------------------------------------------------------ OM: the result
    await kit.switchUser(next(), om, false);
    await a.openBooking(kit, next(), b.bk, `Reopen the booking: Operations › Bookings › ${b.bk}`, `Mở lại lịch hẹn: Vận hành › Lịch hẹn › ${b.bk}`);
    await kit.proof([a.statusChip(p), a.nextCard(p)], 'Booking now Assigned, next step Start Service',
      (t) => /Assigned/.test(t) && /Start Service/.test(t));
    await kit.step(next(), 'Overview › Care team', 'Tổng quan › Nhóm chăm sóc');
    const fold = p.getByText(/^\s*Care team\s*$/i).filter({ visible: true }).first();
    if (!(await c.field(p, 'assigned_doctor_ids').count()) && await fold.count()) await kit.click(fold, 1200);
    await kit.proof(panel('assigned_staff_ids', 'assigned_doctor_ids'), 'Care team: the doctor; the nurse who declined is gone', async () => {
      const v = await a.fieldTexts(p, ['assigned_staff_ids', 'lead_staff_id', 'assigned_doctor_ids']);
      if (process.env.DEBUG) console.log('  dbg care team', JSON.stringify(v));
      return v.assigned_doctor_ids.includes(doctor.name) && !v.assigned_staff_ids.includes(nurse.name) && !v.lead_staff_id.includes(nurse.name);
    });
    await a.viewAssignments(kit, next());
    const rows = p.locator('tr.o_data_row');
    await kit.proof([rows.nth(0), rows.nth(1)], 'Assignments: nurse Cancelled, doctor Staff Confirmed, only one active', async () => {
      const all = await rows.allInnerTexts();
      const active = all.filter((t) => !/Cancelled/.test(t));
      return all.length === 2 && /Cancelled/.test(all.find((t) => t.includes(nurse.name)) || '')
        && active.length === 1 && active[0].includes(doctor.name) && /Staff Confirmed/.test(active[0]);
    });
  },
};
