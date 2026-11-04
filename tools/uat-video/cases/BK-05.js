// BK-05 Every new or repeat booking carries its contact; a repeat enquiry reuses the same
// client; one contact can own several bookings on different dates.
const c = require('./common');
const b = require('./bk_common');
const u = b.users.omhn;
const phoneA = c.phone();
const phoneB = `09${String((Number(phoneA.slice(2)) + 4321) % 1e8).padStart(8, '0')}`;
const newClient = `UAT-VID BK05 New Client ${phoneA.slice(6, 10)}`;
const callerB = `UAT-VID BK05 Caller ${phoneB.slice(6, 10)}`;
const repeat = 'Phạm Thị Dung';
const repeatCode = '01_0000426';
const earlier = { bk: 'BK3838', contact: 'UAT20261021 HN-B07' };
const STOP = process.env.BK05_STOP || '';
const DAYS = [1, 2, 3].map((k) => ({ k, ...b.vnDay(k) }));
const label = (d) => `${d.monShort} ${d.day}`;
const PM = ['14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '13:00', '13:30'];
const svc = [{ q: 'Internal examination', code: 'bs_020' }];

module.exports = {
  meta: {
    id: 'BK-05', title: 'New and repeat enquiries each keep their contact', short: 'Repeat and new contacts',
    title_vi: 'Yêu cầu mới và yêu cầu lặp lại đều giữ liên hệ gốc',
    criterion: 'For each new or repeat enquiry, enter an originating contact and link its booking to that contact. A repeat booking reuses the correct client while recording the new enquiry. One contact can have several bookings, each keeping the same contact link.',
    data: `New enquiry: “${newClient}” (${phoneA}), a new client, ${label(DAYS[0])}. Repeat enquiry: “${callerB}” (${phoneB}) for existing client ${repeat} (${repeatCode}, earlier booking ${earlier.bk} from contact ${earlier.contact}), two bookings ${label(DAYS[1])} and ${label(DAYS[2])}. Clinic Visit, 1 hour, HN_PK_PKGDVU, Internal examination (bs_020).`,
    expected: 'Each new/repeat booking has a contact; one contact can own multiple bookings.',
    ...u,
  },
  proofVi: {
    'New enquiry: a new client will be created at booking': 'Yêu cầu mới: khách hàng mới sẽ được tạo khi đặt lịch',
    'New client’s booking created': 'Đã tạo lịch hẹn cho khách hàng mới',
    'New client’s booking: new client, links to its contact': 'Lịch hẹn của khách mới: đúng khách hàng mới, liên kết liên hệ gốc',
    'Contact linked to the existing client': 'Liên hệ đã liên kết với khách hàng hiện có',
    'Repeat booking 1 created for the same client': 'Đã tạo lịch hẹn lặp lại 1 cho đúng khách hàng',
    'Repeat booking 2 (another date) from the same contact': 'Lịch hẹn lặp lại 2 (ngày khác) từ cùng liên hệ',
    'One contact, two bookings in its history': 'Một liên hệ, hai lịch hẹn trong lịch sử',
    'Repeat booking 1: same client ID': 'Lịch hẹn lặp lại 1: cùng mã khách hàng',
    'Repeat booking 1 opens the new contact': 'Lịch hẹn lặp lại 1 mở liên hệ mới',
    'Repeat booking 2 opens the same contact': 'Lịch hẹn lặp lại 2 mở cùng liên hệ',
    'Earlier booking: same client, its own earlier contact': 'Lịch hẹn trước: cùng khách hàng, liên hệ cũ riêng',
    'One client record holds the earlier and the new bookings': 'Một hồ sơ khách hàng chứa lịch hẹn cũ và mới',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    const openBk = async (bk) => {
      await b.bookingsList(kit, bk, true);
      await kit.click(p.locator('tr.o_data_row', { hasText: bk }).locator('td').nth(1), 4500);
    };
    const leadDash = async () => kit.click(p.locator('button[name=action_open_lead_dashboard]').filter({ visible: true }).first(), 4000);
    await kit.login();

    // ------------------------------------------------------------ new enquiry, new client
    await kit.step(next(), 'A new person calls to book for herself: CRM › Contacts › New Contact (Client, self)', 'Một người mới gọi để tự đặt lịch: CRM › Liên hệ › Liên hệ mới (Khách hàng tự gọi)');
    await kit.area('CRM');
    await kit.click(c.sidebar(p, 'Contacts'), 2500);
    await kit.click(p.getByRole('button', { name: 'New Contact' }), 1500);
    await kit.type(p.getByPlaceholder('Full name'), newClient);
    await kit.type(p.getByPlaceholder('Phone number'), phoneA, 800);
    await kit.click(p.locator('.nc-footer button', { hasText: 'Next' }), 1500);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Client \(Self\)\s*$/ }).first(), 700);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Clinic Visit\s*$/ }).first(), 700);
    const codeA = await b.createContact(kit);
    kit.records['Contact A'] = `${newClient}${codeA ? ' (' + codeA + ')' : ''}`;

    await kit.step(next(), `Book from the contact: Clinic Visit, Hanoi clinic, ${label(DAYS[0])} afternoon`, `Đặt lịch từ liên hệ: khám tại phòng khám Hà Nội, chiều ${DAYS[0].day}/${DAYS[0].month + 1}`);
    await kit.click(b.bookBtn(p), 4500);
    await kit.proof(p.locator('.qb-contact-banner, .qb-wizard-header, .qb-client-section').filter({ hasText: /new client will be created/i }).first(),
      'New enquiry: a new client will be created at booking', (t) => t.includes(newClient), 2600);
    await c.qbFill(kit, { service: 'Clinic Visit', duration: '1 hour', facility: 'HN_PK_PKGDVU', location: 'Clinic' });
    await b.qbAddServices(kit, svc);
    await c.qbPickDay(kit, DAYS[0].k);
    const hmA = await b.qbSlot(kit, PM);
    const rA = await b.qbCreate(kit);
    await kit.proof(rA.box, 'New client’s booking created', (t) => /BK\d+/.test(t) && t.includes(newClient) && t.includes(b.qbDate(DAYS[0], hmA)), 2400);
    kit.records['New client booking'] = `${rA.bk} (${c.shownTime(DAYS[0].d, hmA)})`;
    await kit.click(p.locator('.qb-modal-confirm'), 4500);
    await kit.step(next(), `${rA.bk}: the client is the new person; Quick actions › Lead Dashboard opens the contact`, `${rA.bk}: khách hàng là người mới; Thao tác nhanh › Lead Dashboard mở liên hệ`);
    const heroA = await p.locator('.ws-hero').first().innerText();
    const peopleA = await c.people(p).innerText().catch(() => '');
    const idA = ((peopleA.match(/ID:\s*([^\n]+)/) || [])[1] || "").trim();
    if (idA) kit.records['New client'] = `${newClient} (${idA})`;
    await leadDash();
    await kit.proof([c.hero(p), c.people(p)], 'New client’s booking: new client, links to its contact',
      (t) => heroA.includes(rA.bk) && heroA.includes(newClient) && t.includes(newClient) && t.includes(phoneA.slice(-4)), 2800);
    if (STOP === 'new') return;

    // ------------------------------------------------------------ repeat enquiry, existing client
    await kit.step(next(), `Repeat enquiry: a relative of ${repeat} calls. New Contact, linked to the existing client`, `Yêu cầu lặp lại: người thân của ${repeat} gọi. Liên hệ mới, liên kết khách hàng hiện có`);
    await kit.click(c.sidebar(p, 'Contacts'), 2500);
    await b.newContactForClient(kit, { caller: callerB, phone: phoneB, client: repeat, code: repeatCode, interest: 'Clinic Visit' });
    const codeB = await b.createContact(kit);
    kit.records['Contact B'] = `${callerB}${codeB ? ' (' + codeB + ')' : ''}`;

    await kit.step(next(), `Book two visits from this one contact: ${label(DAYS[1])} and ${label(DAYS[2])}`, `Đặt hai lượt từ cùng một liên hệ: ${DAYS[1].day}/${DAYS[1].month + 1} và ${DAYS[2].day}/${DAYS[2].month + 1}`);
    await kit.click(b.bookBtn(p), 4500);
    await c.qbFill(kit, { service: 'Clinic Visit', duration: '1 hour', facility: 'HN_PK_PKGDVU', location: 'Clinic' });
    await b.qbAddServices(kit, svc);
    await c.qbPickDay(kit, DAYS[1].k);
    const hmB = await b.qbSlot(kit, PM);
    const rB = await b.qbCreate(kit);
    await kit.proof(rB.box, 'Repeat booking 1 created for the same client', (t) => /BK\d+/.test(t) && t.includes(repeat) && t.includes(b.qbDate(DAYS[1], hmB)), 2400);
    kit.records['Repeat booking 1'] = `${rB.bk} (${c.shownTime(DAYS[1].d, hmB)})`;
    await kit.note('Create Another: the same contact, another date', 'Tạo thêm: cùng liên hệ, ngày khác');
    await kit.click(p.locator('.qb-modal-another'), 2500);
    await b.qbAddServices(kit, svc);
    await c.qbPickDay(kit, DAYS[2].k);
    const hmC = await b.qbSlot(kit, PM);
    const rC = await b.qbCreate(kit);
    await kit.proof(rC.box, 'Repeat booking 2 (another date) from the same contact', (t) => /BK\d+/.test(t) && t.includes(repeat) && t.includes(b.qbDate(DAYS[2], hmC)), 2400);
    kit.records['Repeat booking 2'] = `${rC.bk} (${c.shownTime(DAYS[2].d, hmC)})`;
    await kit.click(p.locator('.qb-modal-confirm'), 4500);
    if (STOP === 'repeat') return;

    await kit.step(next(), `${rC.bk} › Lead Dashboard: the contact’s history`, `${rC.bk} › Lead Dashboard: lịch sử của liên hệ`);
    await leadDash();
    await kit.proof([c.hero(p), p.locator('.ct-timeline-wrapper')], 'One contact, two bookings in its history',
      (t) => t.includes(callerB) && t.includes(rB.bk) && t.includes(rC.bk), 3200);

    await kit.step(next(), `Open ${rB.bk}: same client ID ${repeatCode}; its contact is the new enquiry`, `Mở ${rB.bk}: cùng mã khách hàng ${repeatCode}; liên hệ là yêu cầu mới`);
    await openBk(rB.bk);
    await kit.proof([p.locator('.ws-hero').first(), c.people(p)], 'Repeat booking 1: same client ID', (t) => t.includes(rB.bk) && t.includes(repeat) && t.includes(repeatCode), 2600);
    await leadDash();
    await kit.proof(c.hero(p), 'Repeat booking 1 opens the new contact', (t) => t.includes(callerB), 2200);

    await kit.step(next(), `Open ${rC.bk}: the same contact`, `Mở ${rC.bk}: cùng liên hệ`);
    await openBk(rC.bk);
    await leadDash();
    await kit.proof(c.hero(p), 'Repeat booking 2 opens the same contact', (t) => t.includes(callerB), 2200);

    await kit.step(next(), `The earlier booking ${earlier.bk}: same client, but its own earlier contact`, `Lịch hẹn trước ${earlier.bk}: cùng khách hàng, nhưng liên hệ cũ riêng`);
    await openBk(earlier.bk);
    const heroE = await p.locator('.ws-hero').first().innerText();
    const peopleE = await c.people(p).innerText().catch(() => '');
    await leadDash();
    await kit.proof(c.hero(p), 'Earlier booking: same client, its own earlier contact',
      (t) => heroE.includes(repeat) && peopleE.includes(repeatCode) && t.includes(earlier.contact) && !t.includes(callerB), 2600);

    await kit.step(next(), `Operations › Clients › ${repeat} › Bookings: one client record, old and new bookings`, `Vận hành › Khách hàng › ${repeat} › Lịch hẹn: một hồ sơ, lịch hẹn cũ và mới`);
    await kit.area('Operations');
    await kit.click(c.sidebar(p, 'Clients'), 2500);
    await kit.type(p.locator('.o_searchview_input'), repeat, 300);
    await p.keyboard.press('Enter');
    await kit.hold(2000);
    const clientRows = p.locator('tr.o_data_row', { hasText: repeat });
    const nClients = await clientRows.count();
    await kit.click(clientRows.locator('td[name=name]').first(), 4000);
    await b.tab(kit, 'Bookings');
    const table = p.locator('.o_notebook .tab-pane.active').first().locator('table').last();
    await kit.proof([table, p.locator('.ws-hero').first()], 'One client record holds the earlier and the new bookings',
      (t) => nClients === 1 && t.includes(repeatCode) && [earlier.bk, rB.bk, rC.bk].every((x) => t.includes(x)), 3200);
  },
};
