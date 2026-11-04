// MB-02 Nurse app: the visit details match the saved booking and the client data.
// The HCMC Operations Manager books today's home visit for Đặng Thị Quỳnh (source TC-13:
// injection × 2) with nurse_hcm, the nurse accepts it in the nurse app and opens it: client,
// time, address, services and the designated contact are the booked ones.
const c = require('./common');
const a = require('./as_common');
const m = require('./mb_common');
const om = m.users.om;
const nurse = m.users.nurse;
const cl = m.client;
const T = m.TC;
const STOP = process.env.MB02_STOP || '';

module.exports = {
  meta: {
    id: 'MB-02', title: 'Nurse app shows the visit details', short: 'Mobile visit details',
    title_vi: 'Ứng dụng điều dưỡng hiển thị chi tiết lượt khám',
    criterion: 'The mobile visit details must show the correct client, scheduled time, address, services and designated contact person, matching the saved booking and the client test data.',
    data: `TC-13 (workbook row 19): ${cl.name} (${cl.code}), ${cl.address}; designated contact ${cl.contact} (husband); Home Visit, ${T.facility}, today; ${T.product} (${T.code}) × ${T.qty} = 210,000 ₫; nurse ${nurse.login}`,
    expected: 'All source details are visible and correct.',
    ...om,
  },
  proofVi: {
    'TC-13 service: injection × 2, total 210,000 ₫': 'Dịch vụ TC-13: tiêm × 2, tổng 210.000 ₫',
    'Booking created': 'Đã tạo lịch hẹn',
    'Saved booking: client, today’s time, nurse, waiting for her to accept': 'Lịch hẹn đã lưu: khách hàng, giờ hôm nay, điều dưỡng, chờ chấp nhận',
    'The nurse is offered the visit': 'Điều dưỡng nhận được đề nghị lượt khám',
    'Nurse accepted: visit on her list today': 'Điều dưỡng đã chấp nhận: lượt khám có trong danh sách hôm nay',
    'Client: name and ID': 'Khách hàng: tên và mã',
    'Scheduled: today at the booked time': 'Lịch: hôm nay đúng giờ đã đặt',
    'Services: the booked injection': 'Dịch vụ: tiêm như đã đặt',
    'Address: the client’s home address': 'Địa chỉ: nhà của khách hàng',
    'Designated contact: Đặng Văn Sơn': 'Người liên hệ chính: Đặng Văn Sơn',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();
    const day = m.today();

    // ------------------------------------------------------------ OM books today's visit
    await a.openClient(kit, next(), cl);
    await kit.step(next(), `New booking: ${T.type}, 30 minutes, ${T.facility}, at the client’s home`, `Đặt lịch mới: khám tại nhà, 30 phút, ${T.facility}, tại nhà khách hàng`);
    await a.clickRetry(kit, () => p.getByRole('button', { name: /^\s*New booking\s*$/ }).filter({ visible: true }).first(), 4000);
    await p.locator('.qb-form-group').first().waitFor({ timeout: 15000 }).catch(() => {});
    await c.qbFill(kit, { service: T.type, duration: T.duration, facility: T.facility, location: T.location });

    await kit.step(next(), `TC-13 service: ${T.product} (${T.code}) × ${T.qty}`, `Dịch vụ TC-13: ${T.productVi} (${T.code}) × ${T.qty}`);
    await kit.click(p.locator('.qb-add-services-btn'), 2000);
    await kit.type(p.locator('.pcd-search-input'), T.search, 1500);
    const pc = p.locator('.pcd-card', { hasText: T.code }).first();
    await kit.click(pc.locator('.pcd-add-btn').first(), 900);
    for (let i = 1; i < T.qty; i++) await kit.click(pc.locator('.pcd-qty-btn').last(), 700);
    await kit.click(p.locator('.pcd-done-btn'), 2000);
    await kit.proof(p.locator('.qb-pt-footer').first().locator('xpath=..'), 'TC-13 service: injection × 2, total 210,000 ₫',
      (t) => t.includes(T.product) && m.money(T.total).test(t), 2800);

    const times = c.slotsFromNow(20);
    await kit.step(next(), `Today, ${day.mon} ${day.day}: the first free time from ${times[0]}`, `Hôm nay ${day.day}/${day.d.getUTCMonth() + 1}: khung giờ trống đầu tiên từ ${times[0]}`);
    await c.qbPickDay(kit, 0);
    const hm = await c.qbPickSlot(kit, times);
    await kit.note(`The visit: today at ${hm} (Vietnam time)`, `Lượt khám: hôm nay lúc ${hm} (giờ Việt Nam)`);

    await kit.step(next(), `Choose the nurse: ${nurse.name} (assigned and leading)`, `Chọn điều dưỡng: ${nurse.name} (được phân công và phụ trách)`);
    await kit.click(p.locator('.qb-staff-chip', { hasText: nurse.name }).first(), 800);
    await kit.select(c.qbGroup(p, 'Lead Staff'), nurse.name);

    await kit.step(next(), 'Create the booking', 'Tạo lịch hẹn');
    await kit.click(p.locator('.qb-btn-create'), 4500);
    const done = p.locator('.qb-modal-card').first();
    await done.waitFor({ timeout: 15000 }).catch(() => {});
    const bk = (((await done.innerText().catch(() => '')) || '').match(/BK\d{3,}/) || [''])[0];
    if (!bk) {
      console.log('  after create:', (await p.locator('.qb-validation-popup, .o_notification').allInnerTexts()).join(' | ').slice(0, 300));
      throw new Error('booking not created');
    }
    await kit.proof(done, 'Booking created', (t) => t.includes(bk) && t.includes(cl.name), 2600);
    await kit.click(p.locator('.qb-modal-confirm'), 4500);
    await a.hero(p).waitFor({ timeout: 15000 });
    const url = p.url();
    const id = Number((url.match(/\/(\d+)(?:\?.*)?$/) || [])[1]) || null;
    const st = { bk, id, hm, date: day.iso, url, client: cl.name };
    m.save(st);
    kit.records['Booking'] = `${bk} (${m.shownToday(hm)}, ${nurse.name})`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Saved booking: client, today’s time, nurse, waiting for her to accept',
      (t) => t.includes(bk) && t.includes(cl.name) && t.includes(m.shownToday(hm)) && /Waiting for staff to accept/i.test(t));
    if (STOP === 'book') return;

    // ------------------------------------------------------------ the nurse accepts and opens it
    await m.asNurse(kit, next());
    await kit.note('The nurse app on a tablet-size screen (the phone layout), near the client in Ho Chi Minh City',
      'Ứng dụng điều dưỡng trên màn hình cỡ máy tính bảng (bố cục điện thoại), gần nhà khách hàng tại TP.HCM');
    await kit.step(next(), `Notifications: the new visit ${bk}`, `Thông báo: lượt khám mới ${bk}`);
    await a.openBell(kit);
    const offer = a.offerCard(p, bk);
    await kit.proof(offer, 'The nurse is offered the visit', (t) => t.includes(bk) && t.includes(cl.name));
    await kit.step(next(), 'Accept', 'Chấp nhận');
    await kit.click(offer.locator('.notif-btn-accept'), 3500);
    await m.closeBell(kit);
    await m.card(p, st).waitFor({ timeout: 15000 }).catch(() => {});
    await kit.proof(m.card(p, st), 'Nurse accepted: visit on her list today', (t) => t.includes(cl.name) && t.includes(cl.code) && t.includes(hm));

    await kit.step(next(), `Open the visit for ${cl.name} and compare it with the booking`, `Mở lượt khám của ${cl.name} và đối chiếu với lịch hẹn`);
    await m.openVisit(kit, st);
    const s = m.sheet(p);
    await kit.proof(s.locator('.client-name-banner').first(), 'Client: name and ID', (t) => t.includes(cl.name) && t.includes(cl.code));
    const sched = m.section(p, 'Scheduled Visit');
    const dateRow = sched.locator('.detail-row', { hasText: 'Date & Time' }).first();
    await kit.proof(dateRow, 'Scheduled: today at the booked time', (t) => t.includes(String(day.day)) && (t.includes(hm) || t.includes(a.h12(hm))));
    await kit.proof(sched.locator('.detail-row', { hasText: 'Services' }).first(), 'Services: the booked injection', T.product);
    const contact = m.section(p, 'Contact Information');
    await kit.proof(contact.locator('.detail-row', { hasText: 'Address' }).first(), 'Address: the client’s home address', cl.address);
    await kit.proof(contact.locator('.detail-row', { hasText: 'Primary Contact' }).first(), 'Designated contact: Đặng Văn Sơn', cl.contact);
    await m.closeVisit(kit);
    await kit.page.setViewportSize(m.DESKTOP);
  },
};
