// CT-05 Follow-up processed into a booking for the existing client; links both ways.
const c = require('./common');
const u = c.users.crm;
const phone = c.phone();
const caller = `UAT-VID Booking Caller ${phone.slice(6, 10)}`;
const client = 'Nguyễn Văn An';
const clientCode = '01_0000126';
const follow = c.vnAt(1, 10, 0);
const note = 'Client wants a clinic visit; call back to book';

// The appointment: the first weekday at least two days ahead, 10:00 (TC-01: weekday, in hours, at the clinic).
const appt = (() => {
  for (let k = 2; k < 9; k++) {
    const d = new Date(Date.now() + 7 * 3600e3 + k * 86400e3);
    if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) return { days: k, day: d.getUTCDate(), month: d.getUTCMonth(), ...c.vnAt(k, 10, 0) };
  }
})();

module.exports = {
  meta: {
    id: 'CT-05', title: 'Follow-up turned into a booking, linked both ways', short: 'Follow-up to booking',
    title_vi: 'Chuyển lịch theo dõi thành lịch hẹn, liên kết hai chiều',
    criterion: 'Convert a follow-up that results in a booking into the requested appointment for the correct existing client; the contact shows a service was booked and the booking links back to the contact without changing the client.',
    data: `Caller “${caller}” (${phone}) for existing client ${client} (${clientCode}); TC-01 inputs: Clinic Visit, 1 hour, HN_PK_PKGDVU, Internal examination (bs_020), ${appt.shown}`,
    expected: 'Follow-up produces the correct linked booking and closes the follow-up.',
    ...u,
  },
  proofVi: {
    'Linked to the existing client': 'Đã liên kết với khách hàng hiện có',
    'Follow-up pending': 'Đang chờ theo dõi',
    'Booking is for the same existing client': 'Lịch hẹn cho đúng khách hàng hiện có',
    'Internal examination, 500,000 ₫': 'Khám nội khoa, 500.000 ₫',
    'Booking created': 'Đã tạo lịch hẹn',
    'Booking: client, date and time': 'Lịch hẹn: khách hàng, ngày và giờ',
    'Booking opens the contact it came from': 'Lịch hẹn mở lại liên hệ gốc',
    'Contact: Service Booked, follow-up resolved': 'Liên hệ: Đã đặt dịch vụ, lịch theo dõi đã xử lý',
    'Follow-up closed, client linked': 'Đã đóng lịch theo dõi, đã liên kết khách hàng',
    'Contact history shows the booking': 'Lịch sử liên hệ hiển thị lịch hẹn',
  },
  async run(kit) {
    const p = kit.page;
    await kit.login();

    await kit.step(2, `A relative calls for existing client ${client}. Open New Contact`, `Người thân gọi cho khách hàng hiện có ${client}. Mở Liên hệ mới`);
    await kit.click(c.sidebar(p, 'CONTACTS'), 2500);
    await kit.click(p.getByRole('button', { name: 'New Contact' }), 1500);
    await kit.type(p.getByPlaceholder('Full name'), caller);
    await kit.type(p.getByPlaceholder('Phone number'), phone, 800);
    await kit.click(p.locator('.nc-footer button', { hasText: 'Next' }), 1500);

    await kit.step(3, `The caller is the client’s representative. Find and link ${client}`, `Người gọi là đại diện của khách hàng. Tìm và liên kết ${client}`);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Client Representative\s*$/ }).first(), 700);
    await kit.type(p.getByPlaceholder('Name of the client'), client, 300);
    await kit.click(p.locator('.nc-search-btn').filter({ visible: true }).last(), 2000);
    await kit.click(p.locator('.nc-search-row', { hasText: clientCode }).first(), 1000);
    await kit.proof(p.locator('.nc-selected-client'), 'Linked to the existing client', 'Linked to existing client', 2200);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Clinic Visit\s*$/ }).first(), 700);
    await kit.click(p.locator('.nc-footer button', { hasText: 'Create Contact' }), 2500);
    const code = ((await p.locator('.nc-success-code').innerText().catch(() => '')) || '').replace(/[()]/g, '').trim();
    await kit.click(p.locator('button').filter({ hasText: /^\s*Open Record\s*$/ }).first(), 3500);
    kit.records['Contact'] = code;

    await kit.step(4, `Record the follow-up: call back ${follow.shown}`, `Ghi lịch theo dõi: gọi lại ${follow.shown}`);
    await kit.select(c.field(p, 'contact_outcome'), 'Pending Follow-up');
    await kit.datetime(c.field(p, 'next_follow_up_date'), follow.typed);
    await kit.type(c.field(p, 'follow_up_notes').locator('textarea'), note, 600);
    await kit.click(c.saveBtn(p), 2000);
    await kit.proof(c.statusCard(p), 'Follow-up pending', async (t) => {
      const v = await kit.fieldValues(['contact_outcome']);
      return v.contact_outcome === 'Pending Follow-up' && t.includes(follow.shown);
    });

    await kit.step(5, 'On the follow-up call the client books. Press Book', 'Trong cuộc gọi theo dõi, khách hàng đặt lịch. Nhấn Đặt lịch');
    await kit.click(p.locator('.ws-hero button, .o_form_view button').filter({ hasText: /^\s*Book\s*$/ }).first(), 4000);
    await kit.proof(p.locator('.qb-contact-banner, .qb-wizard-header').first(), 'Booking is for the same existing client', client);

    await kit.step(6, 'TC-01 inputs: Clinic Visit, 1 hour, Hanoi clinic, at the clinic', 'Dữ liệu TC-01: Khám tại phòng khám, 1 giờ, phòng khám Hà Nội, tại phòng khám');
    await kit.select(p.locator('.qb-form-group', { has: p.locator('.qb-form-label', { hasText: 'Service Type' }) }), 'Clinic Visit');
    await kit.select(p.locator('.qb-form-group', { has: p.locator('.qb-form-label', { hasText: 'Duration' }) }), '1 hour');
    await kit.select(p.locator('.qb-form-group', { has: p.locator('.qb-form-label', { hasText: 'Facility' }) }), 'HN_PK_PKGDVU');
    await kit.select(p.locator('.qb-form-group', { has: p.locator('.qb-form-label', { hasText: /^\s*Location/ }) }), 'Clinic');

    await kit.step(7, 'Add the service: Internal examination (bs_020)', 'Thêm dịch vụ: Khám nội khoa (bs_020)');
    await kit.click(p.locator('.qb-add-services-btn'), 2000);
    await kit.type(p.locator('.pcd-search-input'), 'Internal examination', 1200);
    await kit.click(p.locator('.pcd-card', { hasText: 'bs_020' }).filter({ hasText: /^\s*Internal examination/ }).locator('.pcd-add-btn').first(), 800);
    await kit.click(p.locator('.pcd-done-btn'), 1500);
    await kit.proof(p.locator('.qb-pt-footer').first().locator('xpath=..'), 'Internal examination, 500,000 ₫',
      (t) => /Internal examination/i.test(t) && /500[.,]000/.test(t));

    const thisMonth = new Date(Date.now() + 7 * 3600e3).getUTCMonth();
    const mon = new Date(Date.UTC(2026, appt.month, 1)).toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
    await kit.step(8, `Choose the date: ${mon} ${appt.day}, morning`, `Chọn ngày: ${appt.day}/${appt.month + 1}, buổi sáng`);
    if (appt.month !== thisMonth) await kit.click(p.locator('.qb-cal-nav').last(), 800);
    await kit.click(p.locator('.qb-cal-day:not(.qb-cal-day--disabled):not(.qb-cal-day--empty)')
      .filter({ hasText: new RegExp(`^\\s*${appt.day}\\s*$`) }).first(), 2200);
    // The client may already have a visit at 10:00 (a locked slot): take the first free one from 10:00.
    let slot = null;
    for (const hm of ['10:00', '10:30', '11:00', '11:30', '09:00', '09:30', '08:00', '08:30']) {
      const b = p.locator('.qb-slot-grid button').filter({ hasText: new RegExp(`^\\s*${hm}`) })
        .filter({ hasNot: p.locator('.fa-lock, .fa-exclamation-triangle') }).first();
      if (await b.count() && await b.isEnabled()) { slot = { b, hm }; break; }
    }
    if (!slot) throw new Error('no free morning slot');
    const [hh, mm] = slot.hm.split(':').map(Number);
    appt.shown = `${mon} ${appt.day}, ${((hh + 11) % 12) + 1}:${String(mm).padStart(2, '0')} ${hh < 12 ? 'AM' : 'PM'}`;
    await kit.note(`Time: ${slot.hm} (first free slot from 10:00)`, `Giờ: ${slot.hm} (khung giờ trống đầu tiên từ 10:00)`);
    await kit.click(slot.b, 1000);

    await kit.step(9, 'Create the booking', 'Tạo lịch hẹn');
    await kit.click(p.locator('.qb-btn-create'), 4000);
    if (!(await p.locator('.qb-modal-actions').count())) {
      await p.screenshot({ path: require('path').join(kit.outDir, 'debug-after-create.png') });
      console.log('  after create:', (await p.locator('.qb-validation-popup, .o_notification').allInnerTexts()).join(' | ').slice(0, 300));
    }
    await kit.proof(p.locator('.qb-modal-actions').locator('xpath=..'), 'Booking created', /BK\d+/);
    const bk = ((await p.locator('body').innerText()).match(/BK\d{3,}/) || [''])[0];
    kit.records['Booking'] = bk;
    await kit.click(p.locator('.qb-modal-confirm'), 4000);

    await kit.step(10, 'The booking: same client, date and time', 'Lịch hẹn: đúng khách hàng, ngày và giờ');
    const hero = p.locator('.ws-hero').first();
    await kit.proof(hero, 'Booking: client, date and time', (t) => t.includes(client) && t.includes(bk) && t.includes(appt.shown));

    await kit.step(11, 'From the booking, open the contact it came from (Quick actions › Lead Dashboard)', 'Từ lịch hẹn, mở liên hệ gốc (Thao tác nhanh › Lead Dashboard)');
    await kit.click(p.locator('button[name=action_open_lead_dashboard]').filter({ visible: true }).first(), 4000);
    await kit.proof(c.hero(p), 'Booking opens the contact it came from', (t) => t.includes(caller));

    await kit.step(12, 'The contact now shows the service was booked; the follow-up is resolved', 'Liên hệ hiển thị đã đặt dịch vụ; lịch theo dõi đã được xử lý');
    await kit.proof([c.heroChip(p), c.statusCard(p)], 'Contact: Service Booked, follow-up resolved', async (t) => {
      const v = await kit.fieldValues(['contact_outcome']);
      return /Appointment Scheduled/i.test(t) && v.contact_outcome === 'Service Booked';
    });
    await kit.proof([c.glanceRow(p, 'Follow-up'), c.people(p)], 'Follow-up closed, client linked',
      (t) => /Follow-up\s*Closed/i.test(t) && t.includes(client));
    await kit.proof(p.locator('.ct-timeline-wrapper'), 'Contact history shows the booking', (t) => t.includes(bk));
    c.save({ booking: { caller, phone, code, bk, client } });
  },
};
