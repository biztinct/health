// MB-03 Nurse app: tapping a visit on the list opens exactly that visit and client, and it
// opens the same again after leaving and reloading the app.
const a = require('./as_common');
const m = require('./mb_common');
const nurse = m.users.nurse;
const cl = m.client;
const T = m.TC;

module.exports = {
  meta: {
    id: 'MB-03', title: 'Nurse app opens the selected visit', short: 'Mobile select visit',
    title_vi: 'Ứng dụng điều dưỡng mở đúng lượt khám được chọn',
    criterion: 'Selecting a booking from the mobile list must open that exact appointment and client, so that start, notes, quote and completion apply to the selected visit.',
    data: `Today’s visit ${m.load().bk || '(from MB-02)'} for ${cl.name} (${cl.code}) at ${m.load().hm || '?'}, booked in MB-02 and accepted by ${nurse.login}`,
    expected: 'Selecting a visit opens that exact record.',
    ...nurse,
  },
  proofVi: {
    'Today’s list: the visit for Đặng Thị Quỳnh': 'Danh sách hôm nay: lượt khám của Đặng Thị Quỳnh',
    'Opened: the same client and ID': 'Đã mở: đúng khách hàng và mã',
    'Opened: the same day and time': 'Đã mở: đúng ngày và giờ',
    'Opened: the booked service and address': 'Đã mở: đúng dịch vụ và địa chỉ',
    'Ready to start: Start Service for this visit': 'Sẵn sàng: Bắt đầu dịch vụ cho lượt khám này',
    'After reloading the app: the same visit opens': 'Sau khi tải lại ứng dụng: mở lại đúng lượt khám',
  },

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.id) throw new Error('no visit in mb_state.json: run MB-02 first');
    const day = m.today();
    let n = 0;
    const next = () => ++n;
    await m.asNurse(kit, next());
    await kit.note('The nurse app on a tablet-size screen (the phone layout)', 'Ứng dụng điều dưỡng trên màn hình cỡ máy tính bảng (bố cục điện thoại)');

    await kit.step(next(), `Today, ${day.mon} ${day.day}: find the visit for ${cl.name} at ${st.hm}`, `Hôm nay ${day.day}/${day.d.getUTCMonth() + 1}: tìm lượt khám của ${cl.name} lúc ${st.hm}`);
    await kit.proof(m.card(p, st), 'Today’s list: the visit for Đặng Thị Quỳnh', (t) => t.includes(cl.name) && t.includes(cl.code) && t.includes(st.hm));

    await kit.step(next(), 'Tap it', 'Chạm vào lượt khám');
    await m.openVisit(kit, st);
    await checkOpened(kit, st, day, true);

    await kit.step(next(), 'Leave the visit and reload the app', 'Rời lượt khám và tải lại ứng dụng');
    await m.closeVisit(kit);
    await m.reloadApp(kit);
    await kit.step(next(), 'Tap the same visit again', 'Chạm lại vào lượt khám đó');
    await m.openVisit(kit, st);
    await kit.proof([m.sheet(p).locator('.client-name-banner').first(), m.section(p, 'Scheduled Visit')], 'After reloading the app: the same visit opens',
      (t) => t.includes(cl.name) && t.includes(cl.code) && (t.includes(st.hm) || t.includes(a.h12(st.hm))) && t.includes(T.product));
    await m.closeVisit(kit);
  },
};

async function checkOpened(kit, st, day) {
  const p = kit.page;
  const s = m.sheet(p);
  await kit.proof(s.locator('.client-name-banner').first(), 'Opened: the same client and ID', (t) => t.includes(cl.name) && t.includes(cl.code));
  const sched = m.section(p, 'Scheduled Visit');
  await kit.proof(sched.locator('.detail-row', { hasText: 'Date & Time' }).first(), 'Opened: the same day and time',
    (t) => t.includes(String(day.day)) && (t.includes(st.hm) || t.includes(a.h12(st.hm))));
  await kit.proof([sched.locator('.detail-row', { hasText: 'Services' }).first(), m.section(p, 'Contact Information').locator('.detail-row', { hasText: 'Address' }).first()],
    'Opened: the booked service and address', (t) => t.includes(T.product) && t.includes(cl.address));
  await kit.proof(s.locator('.modal-footer').first(), 'Ready to start: Start Service for this visit', /Start Service/);
}
