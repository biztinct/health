// MB-05 Nurse app: the finished visit stays Completed with its actual end time. The nurse pressed
// Complete Service in MB-07 (the app asks the close questions straight after it); here the nurse
// app and the office booking screen are reopened to show the finish was kept.
// MB05_OFFICE_ONLY=1 skips the nurse app (practice on an older completed visit).
const a = require('./as_common');
const m = require('./mb_common');
const nurse = m.users.nurse;
const om = m.users.om;
const cl = m.client;

const vnMinOf = (iso) => { const d = new Date(new Date(iso).getTime() + 7 * 3600e3); return d.getUTCHours() * 60 + d.getUTCMinutes(); };
const hasTime = (t, min, tol = 2) => {
  const re = /(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/gi; let x;
  while ((x = re.exec(t))) { let h = Number(x[1]); if (x[3]) h = (h % 12) + (x[3].toUpperCase() === 'PM' ? 12 : 0); if (Math.abs(h * 60 + Number(x[2]) - min) <= tol) return true; }
  return false;
};

module.exports = {
  meta: {
    id: 'MB-05', title: 'Nurse app Finish Service', short: 'Mobile finish service',
    title_vi: 'Ứng dụng điều dưỡng: Hoàn thành dịch vụ',
    criterion: 'After the visit documentation and completion choices are given, the staff member finishes the service. The booking keeps Completed status and its actual end time.',
    data: `Today’s visit ${m.load().bk || '(from MB-02)'} for ${cl.name} (${cl.code}), finished by ${nurse.login} with Complete Service in MB-07; office view as ${om.login}`,
    expected: 'Completed state and actual end time persist.',
    ...nurse,
  },
  proofVi: {
    'Today’s list: the visit is Completed': 'Danh sách hôm nay: lượt khám đã hoàn thành',
    'Opened: Completed, no start or finish buttons left': 'Mở ra: đã hoàn thành, không còn nút bắt đầu hay hoàn thành',
    'After reloading the app: still Completed': 'Sau khi tải lại ứng dụng: vẫn đã hoàn thành',
    'Office view: Completed today': 'Màn hình văn phòng: đã hoàn thành hôm nay',
    'Actual start and end times recorded': 'Đã ghi giờ bắt đầu và kết thúc thực tế',
  },

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.id || !st.completedAt) throw new Error('no completed visit in mb_state.json: run MB-07 first');
    let n = 0;
    const next = () => ++n;
    const day = m.today();
    if (!process.env.MB05_OFFICE_ONLY) {
      await m.asNurse(kit, next());
      await kit.step(next(), `Today’s list: the visit for ${cl.name} (${st.hm})`, `Danh sách hôm nay: lượt khám của ${cl.name} (${st.hm})`);
      await kit.proof(m.card(p, st), 'Today’s list: the visit is Completed', (t) => /completed/i.test(t) && t.includes(cl.name) && t.includes(st.hm));
      await kit.step(next(), 'Open it', 'Mở lượt khám');
      await m.openVisit(kit, st);
      await kit.proof([m.sheet(p).locator('.modal-header').first(), m.sheet(p).locator('.client-name-banner').first()], 'Opened: Completed, no start or finish buttons left',
        async (t) => /completed/i.test(t) && t.includes(cl.name) && (await m.btn(p, /Start Service|Complete Service/).count()) === 0);
      await kit.step(next(), 'Leave it and reload the app', 'Rời lượt khám và tải lại ứng dụng');
      await m.closeVisit(kit);
      await m.reloadApp(kit);
      await kit.proof(m.card(p, st), 'After reloading the app: still Completed', (t) => /completed/i.test(t) && t.includes(cl.name));
    }
    await m.asStaff(kit, next(), om);

    // ------------------------------------------------------------ the office booking screen
    await m.openBooking(kit, next(), st.bk);
    const done = new Date(new Date(st.completedAt).getTime() + 7 * 3600e3);
    const dMon = done.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
    await kit.proof([a.hero(p), p.locator('.o_widget_ws_journey').first()], 'Office view: Completed today',
      (t) => t.includes(st.bk) && /Completed/.test(t) && new RegExp(`Completed\\s*${dMon} ${done.getUTCDate()}`).test(t));
    await kit.step(next(), 'Execution tab: actual start and end', 'Thẻ Thực hiện: giờ bắt đầu và kết thúc thực tế');
    await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Execution\s*$/ }).first(), 2200);
    const startF = p.locator('.o_field_widget[name=actual_start_datetime]').filter({ visible: true }).first();
    const endF = p.locator('.o_field_widget[name=actual_end_datetime]').filter({ visible: true }).first();
    const card = startF.locator('xpath=ancestor::div[contains(@class,"vu-detail-card")][1]');
    await kit.proof(card, 'Actual start and end times recorded', async () => {
      const s = await startF.innerText(), e = await endF.innerText();
      return (!st.startedAt || hasTime(s, vnMinOf(st.startedAt))) && hasTime(e, vnMinOf(st.completedAt)) && e.includes(`${dMon} ${done.getUTCDate()}`);
    });
    await kit.step(next(), 'Reload the booking: it stays Completed', 'Tải lại lịch hẹn: vẫn đã hoàn thành');
    await p.reload();
    await a.hero(p).waitFor({ timeout: 15000 });
    await kit.hold(2500);
    kit._proofVi['After reloading: still Completed with the same end time'] = 'Sau khi tải lại: vẫn đã hoàn thành, cùng giờ kết thúc';
    await kit.proof(a.hero(p), 'After reloading: still Completed with the same end time', async (t) => {
      await p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Execution\s*$/ }).first().click();
      await kit.hold(800);
      return /Completed/.test(t) && hasTime(await endF.innerText(), vnMinOf(st.completedAt));
    });
  },
};
