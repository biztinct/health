// AS-02 Accepted: the Hanoi nurse accepts the offered visit in the nurse app; the Operations
// Manager reopens the booking and sees the confirmed assignment and the booking Assigned.
const c = require('./common');
const a = require('./as_common');
const om = a.users.omhn;
const nurse = a.users.nurse;
const DAYS = 6;
const STOP = process.env.AS02_STOP || '';

module.exports = {
  meta: {
    id: 'AS-02', title: 'Assignment accepted by the nurse', short: 'Assignment accepted',
    title_vi: 'Điều dưỡng chấp nhận phân công',
    criterion: 'The assigned nurse or doctor can accept the offered visit. Acceptance must persist against the correct booking and employee, and the operations manager must be able to see the confirmed assignment after refreshing the record.',
    data: `New clinic visit for ${a.client.name} (${a.client.code}), HN_PK_PKGDVU, ${a.vnDay(DAYS).mon} ${a.vnDay(DAYS).day}, nurse ${nurse.name} chosen when booking; accepted in the nurse app as ${nurse.login}`,
    expected: 'Staff acceptance persists on the correct assignment.',
    ...om,
  },
  proofVi: {
    'Booking sent to the nurse: waiting for her to accept': 'Lịch hẹn đã gửi cho điều dưỡng: đang chờ chấp nhận',
    'Nurse app: the offer for this booking, date and time': 'Ứng dụng điều dưỡng: lời mời cho lịch hẹn này, ngày và giờ',
    'Accepted: “Assignment confirmed!”': 'Đã chấp nhận: “Đã xác nhận phân công!”',
    'The offer has left her pending list': 'Lời mời đã rời khỏi danh sách chờ',
    'Booking now Assigned, next step Start Service': 'Lịch hẹn nay ở trạng thái Đã phân công, bước tiếp theo Bắt đầu dịch vụ',
    'Assignment: same booking, same nurse, Staff Confirmed': 'Phân công: đúng lịch hẹn, đúng điều dưỡng, Nhân sự đã xác nhận',
    'Assignment history: confirmed by the nurse herself': 'Lịch sử phân công: chính điều dưỡng xác nhận',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ------------------------------------------------------------ OM books with the nurse
    await a.openClient(kit, next());
    const b = await a.quickBook(kit, next, { days: DAYS, times: ['09:00', '09:30', '10:00', '10:30', '11:00', '14:00'], nurse: nurse.name });
    kit.records['Booking'] = `${b.bk} (${b.shown})`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Booking sent to the nurse: waiting for her to accept',
      (t) => t.includes(b.bk) && t.includes(b.shown) && /Waiting for staff to accept/i.test(t) && t.includes(nurse.name));
    if (STOP === 'booking') return;

    // ------------------------------------------------------------ nurse accepts
    await kit.switchUser(next(), nurse, true);
    await kit.step(next(), `Notifications bell: the offer for ${b.bk}`, `Chuông thông báo: lời mời cho ${b.bk}`);
    await a.openBell(kit);
    const card = a.offerCard(p, b.bk);
    await kit.proof(card, 'Nurse app: the offer for this booking, date and time',
      (t) => t.includes(b.bk) && t.includes(a.client.name) && t.includes(`${b.day.dmy} ${b.hm}`));
    await kit.step(next(), 'Accept', 'Chấp nhận');
    await kit.click(card.locator('.notif-btn-accept'), 300);
    const toast = p.getByText('Assignment confirmed!').first();
    await toast.waitFor({ timeout: 8000 }).catch(() => {});
    await kit.proof(toast, 'Accepted: “Assignment confirmed!”', 'Assignment confirmed!', 2200);
    await kit.hold(1500);
    await kit.proof(p.locator('.notif-panel').first(), 'The offer has left her pending list', (t) => !t.includes(b.bk), 2200);
    await kit.click(p.locator('.notif-panel-close').first(), 1000);
    if (STOP === 'nurse') return;

    // ------------------------------------------------------------ OM refreshes
    await kit.switchUser(next(), om, false);
    await a.openBooking(kit, next(), b.bk, `Reopen the booking: Operations › Bookings › ${b.bk}`, `Mở lại lịch hẹn: Vận hành › Lịch hẹn › ${b.bk}`);
    await kit.proof([a.statusChip(p), a.nextCard(p)], 'Booking now Assigned, next step Start Service',
      (t) => /Assigned/.test(t) && /Start Service/.test(t) && !/Waiting for staff/i.test(t));

    await a.viewAssignments(kit, next());
    const row = p.locator('tr.o_data_row', { hasText: nurse.name }).first();
    await kit.proof(row, 'Assignment: same booking, same nurse, Staff Confirmed', async (t) =>
      (await p.locator('tr.o_data_row').count()) === 1 && t.includes(b.bk) && t.includes(b.shown) && /Lead Staff/.test(t) && /Staff Confirmed/.test(t));

    await kit.step(next(), 'Open the assignment: its history', 'Mở phân công: lịch sử');
    await kit.click(row.locator('td').nth(1), 4000);
    const hist = p.locator('.o-mail-Message').filter({ hasText: /Staff Confirmed/ }).first();
    await kit.proof(hist, 'Assignment history: confirmed by the nurse herself',
      (t) => t.includes(nurse.name) && /Assigned/.test(t) && /Staff Confirmed/.test(t));
  },
};
