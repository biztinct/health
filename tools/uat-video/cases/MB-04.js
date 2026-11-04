// MB-04 Nurse app: Start Service on the accepted visit. The visit moves to In Progress with the
// actual start time recorded; reloading keeps it, and the office sees the same start time.
const a = require('./as_common');
const m = require('./mb_common');
const nurse = m.users.nurse;
const om = m.users.om;
const cl = m.client;

// minutes since midnight, Vietnam time
const vnMin = () => { const d = new Date(Date.now() + 7 * 3600e3); return d.getUTCHours() * 60 + d.getUTCMinutes(); };
// any h:mm (AM/PM) in the text within `tol` minutes of `min`
const hasTime = (t, min, tol = 2) => {
  const re = /(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/gi; let x;
  while ((x = re.exec(t))) { let h = Number(x[1]); if (x[3]) h = (h % 12) + (x[3].toUpperCase() === 'PM' ? 12 : 0); if (Math.abs(h * 60 + Number(x[2]) - min) <= tol) return true; }
  return false;
};

module.exports = {
  meta: {
    id: 'MB-04', title: 'Nurse app Start Service', short: 'Mobile start service',
    title_vi: 'Ứng dụng điều dưỡng: Bắt đầu dịch vụ',
    criterion: 'An authorised staff member with an accepted assignment can start the service. The visit moves to In Progress and records the actual start time; refreshing or reopening keeps that state without an access error.',
    data: `Today’s visit ${m.load().bk || '(from MB-02)'} for ${cl.name} (${cl.code}) at ${m.load().hm || '?'}, accepted by ${nurse.login}; the office view as ${om.login}`,
    expected: 'Visit enters In Progress with a timestamp.',
    ...nurse,
  },
  proofVi: {
    'Accepted visit, not started yet': 'Lượt khám đã chấp nhận, chưa bắt đầu',
    'In Progress, the visit timer is running': 'Đang thực hiện, đồng hồ lượt khám đang chạy',
    'After reloading: still In Progress, timer still running': 'Sau khi tải lại: vẫn Đang thực hiện, đồng hồ vẫn chạy',
    'List card: In Progress': 'Thẻ trong danh sách: Đang thực hiện',
    'Office view: In Progress today, visit timer running': 'Màn hình văn phòng: Đang thực hiện hôm nay, đồng hồ đang chạy',
    'Actual start time recorded': 'Đã ghi giờ bắt đầu thực tế',
  },

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.id) throw new Error('no visit in mb_state.json: run MB-02 first');
    let n = 0;
    const next = () => ++n;
    await m.asNurse(kit, next());

    await kit.step(next(), `At the client’s home: open today’s visit for ${cl.name} (${st.hm})`, `Tại nhà khách hàng: mở lượt khám hôm nay của ${cl.name} (${st.hm})`);
    await m.openVisit(kit, st);
    const head = m.sheet(p).locator('.modal-header').first();
    await kit.proof(head, 'Accepted visit, not started yet', async (t) => /assigned/i.test(t) && !/in progress/i.test(t)
      && (await m.btn(p, /^\s*Start Service\s*$/).count()) > 0);

    await kit.step(next(), 'Start Service', 'Bắt đầu dịch vụ');
    const started = vnMin();
    await kit.click(m.btn(p, /^\s*Start Service\s*$/), 4000);
    await m.sheet(p).locator('.timer-badge').first().waitFor({ timeout: 15000 }).catch(() => {});
    await kit.proof(head, 'In Progress, the visit timer is running', async (t) => /in progress/i.test(t) && /\d{2}:\d{2}:\d{2}/.test(t));
    m.save({ startedMin: started, startedAt: new Date().toISOString() });

    await kit.step(next(), 'Leave the visit and reload the app', 'Rời lượt khám và tải lại ứng dụng');
    await m.closeVisit(kit);
    await m.reloadApp(kit);
    await kit.proof(m.card(p, st), 'List card: In Progress', (t) => /in progress/i.test(t) && t.includes(cl.name));
    await kit.step(next(), 'Open the visit again', 'Mở lại lượt khám');
    await m.openVisit(kit, st);
    await kit.hold(1500);
    await kit.proof([head, m.sheet(p).locator('.modal-footer').first()], 'After reloading: still In Progress, timer still running',
      (t) => /in progress/i.test(t) && /\d{2}:\d{2}:\d{2}/.test(t) && /Clinical Notes/.test(t) && !/Start Service/.test(t));
    await m.closeVisit(kit);

    // ------------------------------------------------------------ the office sees the start time
    await m.asStaff(kit, next(), om);
    await m.openBooking(kit, next(), st.bk);
    const day = m.today();
    await kit.proof([a.hero(p), p.locator('.ws-journey, [name=ws_journey], .o_widget_ws_journey').first()], 'Office view: In Progress today, visit timer running',
      (t) => t.includes(st.bk) && /In Progress/.test(t) && /\d{2}\s*:\s*\d{2}\s*:\s*\d{2}/.test(t) && new RegExp(`In progress\\s*${day.mon} ${day.day}`).test(t));
    await kit.step(next(), 'Execution tab: actual start', 'Thẻ Thực hiện: giờ bắt đầu thực tế');
    await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Execution\s*$/ }).first(), 2200);
    const startF = p.locator('.o_field_widget[name=actual_start_datetime]').filter({ visible: true }).first();
    await kit.proof(startF.locator('xpath=ancestor::div[contains(@class,"o_wrap_field") or contains(@class,"o_cell")][1]'), 'Actual start time recorded',
      async (t) => hasTime(t + ' ' + (await startF.innerText().catch(() => '')), started) && t.includes(String(m.today().day)));
  },
};
