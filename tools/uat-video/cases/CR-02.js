// CR-02 Rescheduling: the Hanoi Operations Manager moves a booking to a new day and time and
// gives it to a different person on the Reschedule screen (the nurse is not free on the new
// day). The replacement defaults to the Hanoi doctor; CR02_TO="<name>" picks another person.
const c = require('./common');
const a = require('./as_common');
const om = a.users.omhn;
const nurse = a.users.nurse;
const doctor = a.users.doctor;
const FROM_DAYS = 8;
const TO_DAYS = 9;
const TO_HM = '11:00';
const STOP = process.env.CR02_STOP || '';
const REPL = process.env.CR02_TO || doctor.name;

module.exports = {
  meta: {
    id: 'CR-02', title: 'Rescheduled to a new date and time and reassigned', short: 'Reschedule and reassign',
    title_vi: 'Dời lịch sang ngày giờ mới và phân công lại',
    criterion: 'Reschedule a booking to a different date/time and reassign it when required. The new Vietnam appointment time and intended staff must persist. Superseded assignments must no longer be active, with the reschedule retained in the booking history.',
    data: `New clinic visit for ${a.client.name} (${a.client.code}), HN_PK_PKGDVU, ${a.vnDay(FROM_DAYS).mon} ${a.vnDay(FROM_DAYS).day} with nurse ${nurse.name}; moved to ${a.vnDay(TO_DAYS).mon} ${a.vnDay(TO_DAYS).day} ${a.h12(TO_HM)} (Vietnam time) and given to ${REPL}`,
    expected: 'Both appointment date and staff update without duplicate active slots.',
    ...om,
  },
  proofVi: {
    'Booking with the nurse, at the original time': 'Lịch hẹn với điều dưỡng, vào giờ ban đầu',
    'Summary: new date, 11:00 AM, the new person': 'Tóm tắt: ngày mới, 11:00 sáng, người mới',
    'Booking Rescheduled: new date and time': 'Đã dời lịch: ngày và giờ mới',
    'Booking shows the new Vietnam time, marked Rescheduled': 'Lịch hẹn hiển thị giờ Việt Nam mới, có nhãn Đã dời lịch',
    'Care team: the new person only, the nurse is gone': 'Nhóm chăm sóc: chỉ người mới, điều dưỡng không còn',
    'Assignments: nurse Cancelled, the new person is the only active one, at the new time': 'Phân công: điều dưỡng Đã hủy, người mới là phân công duy nhất còn hiệu lực, vào giờ mới',
    'One booking in the list, at the new time only': 'Chỉ một lịch hẹn trong danh sách, chỉ ở giờ mới',
    'History keeps the reschedule: old and new time, staff changed': 'Lịch sử lưu việc dời lịch: giờ cũ, giờ mới và thay đổi nhân sự',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await a.openClient(kit, next());
    const b = await a.quickBook(kit, next, { days: FROM_DAYS, times: ['09:00', '09:30', '10:00', '10:30', '14:00', '14:30'], nurse: nurse.name });
    const to = a.vnDay(TO_DAYS);
    const newShown = `${to.mon} ${to.day}, ${a.h12(TO_HM)}`;
    kit.records['Booking'] = `${b.bk} (${b.shown} → ${newShown})`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Booking with the nurse, at the original time',
      (t) => t.includes(b.bk) && t.includes(b.shown) && t.includes(nurse.name));
    if (STOP === 'booking') return;

    await kit.step(next(), `The client asks to move the visit: press Reschedule`, `Khách hàng xin dời lượt khám: nhấn Dời lịch`);
    await kit.click(p.locator('.ws-hero button').filter({ hasText: /^\s*Reschedule\s*$/ }).filter({ visible: true }).first(), 5000);
    await p.locator('.rsb-cal-day').first().waitFor({ timeout: 15000 }).catch(() => {});

    await kit.step(next(), `New date ${to.mon} ${to.day}, ${a.h12(TO_HM)} (Vietnam time)`, `Ngày mới ${to.day}/${to.d.getUTCMonth() + 1}, ${TO_HM} (giờ Việt Nam)`);
    const thisMonth = new Date(Date.now() + 7 * 3600e3).getUTCMonth();
    if (to.d.getUTCMonth() !== thisMonth) await kit.click(p.locator('.rsb-cal-nav').last(), 900);
    await kit.click(p.locator('.rsb-cal-day:not(.rsb-cal-day--disabled):not(.rsb-cal-day--empty)').filter({ hasText: new RegExp(`^\\s*${to.day}\\s*$`) }).first(), 2500);
    await kit.click(p.locator('.rsb-tod-card').filter({ hasText: 'Morning' }).first(), 2000);
    await kit.click(p.locator('.rsb-slot-grid button').filter({ hasText: new RegExp(`^\\s*${TO_HM}`) }).first(), 1500);

    await kit.step(next(), `The nurse is not free that day: give the visit to ${REPL}`, `Điều dưỡng bận ngày đó: giao lượt khám cho ${REPL}`);
    const replChip = p.locator('.rsb-staff-chip', { hasText: REPL }).first();
    if (!(await replChip.count())) throw new Error(`${REPL} is not offered on the Reschedule screen (staff chips: ${(await p.locator('.rsb-staff-chip').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ').trim()).join(', ')})`);
    await kit.click(replChip, 1200);
    await kit.click(p.locator('.rsb-staff-chip', { hasText: nurse.name }).first(), 1500);
    await kit.proof(p.locator('.rsb-summary').first(), 'Summary: new date, 11:00 AM, the new person',
      (t) => t.includes(to.iso) && t.includes(a.h12(TO_HM)) && t.includes(REPL) && !t.includes(nurse.name));

    await kit.step(next(), 'Confirm Reschedule', 'Xác nhận dời lịch');
    await kit.click(p.locator('.rsb-btn--primary').filter({ hasText: /Confirm Reschedule/ }).first(), 4000);
    await kit.proof(p.locator('.rsb-confirm-card').first(), 'Booking Rescheduled: new date and time',
      (t) => t.includes(b.bk) && t.includes(to.dmy) && t.includes(TO_HM));
    if (STOP === 'wizard') return;

    await a.openBooking(kit, next(), b.bk, `Reopen it: Operations › Bookings › ${b.bk}`, `Mở lại: Vận hành › Lịch hẹn › ${b.bk}`);
    await kit.proof(a.hero(p), 'Booking shows the new Vietnam time, marked Rescheduled',
      (t) => t.includes(b.bk) && t.includes(newShown) && !t.includes(b.shown) && /Rescheduled/i.test(t));

    await kit.step(next(), 'Overview › Care team', 'Tổng quan › Nhóm chăm sóc');
    const fold = p.getByText(/^\s*Care team\s*$/i).filter({ visible: true }).first();
    if (!(await c.field(p, 'assigned_staff_ids').count()) && await fold.count()) await kit.click(fold, 1200);
    const teamBox = p.locator('div').filter({ visible: true }).filter({ has: p.locator('[name=assigned_staff_ids]') })
      .filter({ has: p.locator('[name=assigned_doctor_ids]') }).last();
    await kit.proof(teamBox, 'Care team: the new person only, the nurse is gone', async () => {
      const v = await a.fieldTexts(p, ['assigned_staff_ids', 'lead_staff_id', 'assigned_doctor_ids']);
      return (v.assigned_staff_ids + v.assigned_doctor_ids).includes(REPL) && !(v.assigned_staff_ids + v.lead_staff_id).includes(nurse.name);
    });

    await kit.step(next(), 'Activity: the change is in the booking history', 'Hoạt động: thay đổi nằm trong lịch sử lịch hẹn');
    const oldLbl = `${b.day.dmy} ${b.hm}`;
    const newLbl = `${to.dmy} ${TO_HM}`;
    const msg = p.locator('.o-mail-Message').filter({ hasText: /Rescheduled from/ }).first();
    await kit.proof(msg, 'History keeps the reschedule: old and new time, staff changed',
      (t) => t.includes(`Rescheduled from ${oldLbl} to ${newLbl}`) && /Staff added:/.test(t) && t.includes(REPL)
        && /Staff removed:/.test(t) && t.includes(nurse.name) && t.includes(om.login));

    await a.viewAssignments(kit, next());
    const rows = p.locator('tr.o_data_row');
    await kit.proof([rows.nth(0), rows.nth(1)], 'Assignments: nurse Cancelled, the new person is the only active one, at the new time', async () => {
      const all = await rows.allInnerTexts();
      const active = all.filter((t) => !/Cancelled/.test(t));
      const old = all.find((t) => t.includes(nurse.name)) || '';
      return /Cancelled/.test(old) && active.length === 1 && active[0].includes(REPL) && active[0].includes(newShown);
    });
  },
};
