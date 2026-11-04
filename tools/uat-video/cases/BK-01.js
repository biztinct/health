// BK-01 One single visit plus a group of further dates, booked in Quick Booking from the
// caller's contact; every date is recorded exactly once, at the right Vietnam time, duration
// and clinic, and every booking links back to the contact.
const c = require('./common');
const b = require('./bk_common');
const u = b.users.omhn;
const phone = c.phone();
const caller = `UAT-VID BK01 Caller ${phone.slice(6, 10)}`;
const client = 'Lê Quang Cường';
const clientCode = '01_0000326';
const STOP = process.env.BK01_STOP || '';
// Single visit: tomorrow. Date group: the two days after (all inside days 1-3).
const DAYS = [1, 2, 3].map((k) => ({ k, ...b.vnDay(k) }));
const label = (d) => `${d.monShort} ${d.day}`;
const TIMES = ['10:00', '10:30', '11:00', '11:30', '09:00', '09:30', '08:00', '08:30'];

module.exports = {
  meta: {
    id: 'BK-01', title: 'Single visit and a group of dates, each recorded once', short: 'Single and multiple dates',
    title_vi: 'Một lượt khám và một nhóm ngày, mỗi ngày ghi nhận đúng một lần',
    criterion: 'Record both a single appointment and all dates requested for a multi-date booking. Keep the date, Vietnam start time, duration and clinic for each appointment. Every requested date is represented once, with no missing or duplicate booking, and each booking links to its contact.',
    data: `Caller “${caller}” (${phone}) for existing client ${client} (${clientCode}); Clinic Visit, 1 hour, HN_PK_PKGDVU, at the clinic, Internal examination (bs_020) as in the client workbook; single visit ${label(DAYS[0])}, date group ${label(DAYS[1])} and ${label(DAYS[2])}, 10:00 Vietnam time`,
    expected: 'All requested appointments and date groups are recorded without loss/duplicates.',
    ...u,
  },
  proofVi: {
    'Contact linked to the existing client': 'Liên hệ đã liên kết với khách hàng hiện có',
    'Quick Booking is for the same client': 'Đặt lịch nhanh cho đúng khách hàng',
    'Internal examination added': 'Đã thêm Khám nội khoa',
    'Single visit booked': 'Đã đặt lượt khám đơn',
    'Date group: first date booked': 'Nhóm ngày: đã đặt ngày thứ nhất',
    'Date group: second date booked': 'Nhóm ngày: đã đặt ngày thứ hai',
    'Each requested date appears exactly once': 'Mỗi ngày yêu cầu xuất hiện đúng một lần',
    ...Object.fromEntries([0, 1, 2].flatMap((i) => [
      [`Booking ${i + 1} opens its contact`, `Lịch hẹn ${i + 1} mở lại liên hệ gốc`],
    ])),
    'Contact history lists all three bookings': 'Lịch sử liên hệ liệt kê cả ba lịch hẹn',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await kit.step(next(), `A relative calls for existing client ${client}: CRM › Contacts › New Contact`, `Người thân gọi cho khách hàng hiện có ${client}: CRM › Liên hệ › Liên hệ mới`);
    await kit.area('CRM');
    await kit.click(c.sidebar(p, 'Contacts'), 2500);
    await b.newContactForClient(kit, { caller, phone, client, code: clientCode, interest: 'Clinic Visit' });
    const contactCode = await b.createContact(kit);
    kit.records['Contact'] = `${caller}${contactCode ? ' (' + contactCode + ')' : ''}`;

    await kit.step(next(), `The caller wants one visit on ${label(DAYS[0])}, and also ${label(DAYS[1])} and ${label(DAYS[2])}. Press Book`, `Người gọi muốn một lượt ngày ${DAYS[0].day}/${DAYS[0].month + 1}, và thêm ngày ${DAYS[1].day}/${DAYS[1].month + 1}, ${DAYS[2].day}/${DAYS[2].month + 1}. Nhấn Đặt lịch`);
    await kit.click(b.bookBtn(p), 4500);
    await kit.proof(p.locator('.qb-contact-banner, .qb-wizard-header').first(), 'Quick Booking is for the same client', client, 2200);

    await kit.step(next(), 'Clinic Visit, 1 hour, Hanoi clinic, at the clinic; service Internal examination (bs_020)', 'Khám tại phòng khám, 1 giờ, phòng khám Hà Nội; dịch vụ Khám nội khoa (bs_020)');
    await c.qbFill(kit, { service: 'Clinic Visit', duration: '1 hour', facility: 'HN_PK_PKGDVU', location: 'Clinic' });
    const svc = [{ q: 'Internal examination', code: 'bs_020' }];
    await b.qbAddServices(kit, svc);
    await kit.proof(p.locator('.qb-pt-footer').first().locator('xpath=..'), 'Internal examination added', (t) => /Internal examination/i.test(t), 2000);

    const made = [];
    const names = ['Single visit booked', 'Date group: first date booked', 'Date group: second date booked'];
    for (let i = 0; i < 3; i++) {
      const d = DAYS[i];
      if (i === 0) await kit.step(next(), `Single visit: ${label(d)}, 10:00 (first free slot from 10:00). Create`, `Lượt khám đơn: ${d.day}/${d.month + 1}, 10:00 (khung trống đầu tiên từ 10:00). Tạo`);
      else {
        await kit.step(next(), `Date group, date ${i}: Create Another — same service, clinic and duration; ${label(d)}, 10:00`, `Nhóm ngày, ngày ${i}: Tạo thêm — cùng dịch vụ, phòng khám, thời lượng; ${d.day}/${d.month + 1}, 10:00`);
        await kit.click(p.locator('.qb-modal-another'), 2500);
        await b.qbAddServices(kit, svc);
      }
      await c.qbPickDay(kit, d.k);
      const hm = await b.qbSlot(kit, TIMES);
      const r = await b.qbCreate(kit);
      const shown = c.shownTime(d.d, hm);
      await kit.proof(r.box, names[i], (t) => /BK\d+/.test(t) && t.includes(client) && t.includes('HN_PK_PKGDVU')
        && t.includes(b.qbDate(d, hm)) && /Clinic Visit \(1h\)/.test(t), 2600);
      made.push({ bk: r.bk, hm, shown, d });
      kit.records[`Booking ${i + 1}`] = `${r.bk} (${shown})`;
    }
    if (STOP === 'book') return;
    await kit.click(p.locator('.qb-modal-confirm'), 4000);

    await kit.step(next(), `Operations › Bookings, list view, search the client ${client}`, `Vận hành › Lịch hẹn, dạng danh sách, tìm khách hàng ${client}`);
    await b.bookingsList(kit, client, true);
    const rows = p.locator('tr.o_data_row');
    const ours = made.map((m) => rows.filter({ hasText: m.bk }).first());
    await kit.proof(ours, 'Each requested date appears exactly once', async () => {
      const all = await rows.allInnerTexts();
      return made.every((m) => {
        const day = all.filter((r) => r.includes(`${label(m.d)},`) && !/Cancelled/i.test(r));
        return day.length === 1 && day[0].includes(m.bk) && day[0].includes(m.shown.split(', ')[1]) && day[0].includes(client);
      });
    }, 3600);

    for (let i = 0; i < 3; i++) {
      const m = made[i];
      await kit.step(next(), `Open ${m.bk}: date, time, duration and clinic; then its contact (Quick actions › Lead Dashboard)`, `Mở ${m.bk}: ngày, giờ, thời lượng, phòng khám; rồi liên hệ gốc (Thao tác nhanh › Lead Dashboard)`);
      if (i > 0) await b.bookingsList(kit, client, true);
      await kit.click(p.locator('tr.o_data_row', { hasText: m.bk }).locator('td').nth(1), 4500);
      const lbl = `${m.bk}: ${m.shown}, 60 min, HN_PK_PKGDVU`;
      kit._proofVi[lbl] = `${m.bk}: ${m.d.day}/${m.d.month + 1} lúc ${m.hm}, 60 phút, HN_PK_PKGDVU`;
      await kit.proof(p.locator('.ws-hero').first(), lbl,
        (t) => t.includes(m.bk) && t.includes(m.shown) && /\b60\s*min/.test(t) && t.includes('HN_PK_PKGDVU') && t.includes(client), 2600);
      await kit.click(p.locator('button[name=action_open_lead_dashboard]').filter({ visible: true }).first(), 4000);
      await kit.proof(c.hero(p), `Booking ${i + 1} opens its contact`, (t) => t.includes(caller), 2200);
    }
    await kit.proof(p.locator('.ct-timeline-wrapper'), 'Contact history lists all three bookings', (t) => made.every((m) => t.includes(m.bk)), 3200);
  },
};
