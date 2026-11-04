// MB-01 Mobile app shows only the nurse's own visits: on one day there is a visit assigned to
// the Hanoi nurse, an unassigned Hanoi visit and a Ho Chi Minh City visit; the nurse app lists
// only hers.
const c = require('./common');
const a = require('./as_common');
const om = a.users.omhn;
const omhcm = a.users.omhcm;
const nurse = a.users.nurse;
const DAYS = 7;
const hcmClient = { name: 'Hồ Thị Xuân', code: '02_0000626' };
const STOP = process.env.MB01_STOP || '';

module.exports = {
  meta: {
    id: 'MB-01', title: 'Nurse app lists only the nurse’s own visits', short: 'Mobile assigned visits',
    title_vi: 'Ứng dụng điều dưỡng chỉ liệt kê lượt khám của chính điều dưỡng',
    criterion: 'After signing in as the assigned nurse or doctor, the mobile calendar/list must show the bookings that person is permitted to perform for the selected date. Unassigned or out-of-catchment bookings must not become visible through the list.',
    data: `${a.vnDay(DAYS).mon} ${a.vnDay(DAYS).day}: visit A for ${a.client.name} assigned to ${nurse.name}; visit B for ${a.client.name} with nobody assigned; home visit C in Ho Chi Minh City for ${hcmClient.name} (${hcmClient.code}) booked by ${omhcm.login}; nurse app as ${nurse.login}`,
    expected: 'Only assigned, permitted bookings are listed.',
    ...om,
  },
  proofVi: {
    'Visit A booked for the nurse': 'Đã đặt lượt A cho điều dưỡng',
    'Visit B booked with nobody assigned': 'Đã đặt lượt B, chưa phân công ai',
    'Visit C booked in Ho Chi Minh City': 'Đã đặt lượt C tại TP.HCM',
    [`Nurse app open on ${a.vnDay(DAYS).mon} ${a.vnDay(DAYS).day}`]: `Ứng dụng điều dưỡng mở ngày ${a.vnDay(DAYS).day}/${a.vnDay(DAYS).d.getUTCMonth() + 1}`,
    'That day: one visit, her visit A': 'Ngày đó: một lượt khám, là lượt A của cô ấy',
    'Unassigned visit B is not listed': 'Lượt B chưa phân công không có trong danh sách',
    'Ho Chi Minh City visit C is not listed': 'Lượt C tại TP.HCM không có trong danh sách',
    [`Opening it: visit A, ${a.vnDay(DAYS).mon} ${a.vnDay(DAYS).day} at 09:00`]: `Mở ra: lượt A, ngày ${a.vnDay(DAYS).day}/${a.vnDay(DAYS).d.getUTCMonth() + 1} lúc 09:00`,
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();
    const day = a.vnDay(DAYS);

    // ------------------------------------------------------------ the three visits of the day
    await a.openClient(kit, next());
    const A = await a.quickBook(kit, next, { days: DAYS, times: ['09:00', '09:30', '10:00', '10:30'], nurse: nurse.name, label: 'visit A', labelVi: 'lượt A' });
    kit.records['Visit A'] = `${A.bk} (${A.shown}, ${nurse.name})`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Visit A booked for the nurse', (t) => t.includes(A.bk) && t.includes(A.shown) && t.includes(nurse.name));

    await a.openClient(kit, next());
    const B = await a.quickBook(kit, next, { days: DAYS, times: ['14:00', '14:30', '15:00', '15:30'], label: 'visit B', labelVi: 'lượt B' });
    kit.records['Visit B'] = `${B.bk} (${B.shown}, nobody assigned)`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Visit B booked with nobody assigned', (t) => t.includes(B.bk) && t.includes(B.shown) && /Assign Staff/.test(t));
    if (STOP === 'hn') return;

    await kit.switchUser(next(), omhcm, false);
    await a.openClient(kit, next(), hcmClient);
    const C = await a.quickBook(kit, next, { days: DAYS, times: ['10:00', '10:30', '11:00', '11:30'], facility: 'TPHCM_PK_CSTNVU', svc: a.HOME_HCM, label: 'visit C', labelVi: 'lượt C' });
    kit.records['Visit C'] = `${C.bk} (${C.shown}, Ho Chi Minh City)`;
    await kit.proof([a.hero(p)], 'Visit C booked in Ho Chi Minh City', (t) => t.includes(C.bk) && t.includes(hcmClient.name) && /TPHCM/.test(t));
    if (STOP === 'hcm') return;

    // ------------------------------------------------------------ the nurse app
    await kit.switchUser(next(), nurse, true);
    await kit.step(next(), `Day view: go to ${day.mon} ${day.day}`, `Xem theo ngày: chuyển đến ${day.day}/${day.d.getUTCMonth() + 1}`);
    await a.pwaGoToDay(kit, DAYS);
    const dateHead = p.getByText(new RegExp(`${day.d.toLocaleString('en-US', { month: 'long', timeZone: 'UTC' })} ${day.day}, ${day.d.getUTCFullYear()}`)).filter({ visible: true }).first();
    await kit.proof(dateHead, `Nurse app open on ${day.mon} ${day.day}`, (t) => t.includes(String(day.day)));
    const cards = p.locator('.booking-card').filter({ visible: true });
    const summary = p.locator('*').filter({ hasText: /^\s*\d+\s*visits\s*$/ }).filter({ visible: true }).last();
    const cardA = cards.filter({ hasText: a.client.code }).filter({ hasText: A.hm }).first();
    await kit.proof([summary, cardA], 'That day: one visit, her visit A', async (t) =>
      /\b1\s*visits/.test(t) && (await cards.count()) === 1 && t.includes(a.client.name) && t.includes(A.hm));
    await kit.proof(cardA, 'Unassigned visit B is not listed', async () => {
      const all = (await cards.allInnerTexts()).join(' | ');
      return (await cards.count()) === 1 && !all.includes(B.hm);
    });
    await kit.proof(cardA, 'Ho Chi Minh City visit C is not listed', async () => {
      const all = (await cards.allInnerTexts()).join(' | ');
      return (await cards.count()) === 1 && !all.includes(hcmClient.name) && !all.includes(hcmClient.code);
    });
    await kit.step(next(), 'Open her visit', 'Mở lượt khám của cô ấy');
    await kit.click(cardA.locator('.booking-patient-name'), 3000);
    kit._proofVi[`Opening it: visit A, ${day.mon} ${day.day} at ${A.hm}`] = `Mở ra: lượt A, ngày ${day.day}/${day.d.getUTCMonth() + 1} lúc ${A.hm}`;
    const sheet = p.getByText('Scheduled Visit', { exact: true }).filter({ visible: true }).first().locator('xpath=..');
    await kit.proof(sheet, `Opening it: visit A, ${day.mon} ${day.day} at ${A.hm}`,
      (t) => t.includes(`${day.mon} ${day.day}`) && t.includes(A.hm) && /Internal examination/.test(t));
  },
};
