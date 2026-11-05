// AU-01 Audit trail, representative sample (read-only): the Owner reviews a booking's history
// (BK4032, rescheduled and reassigned in CR-02: who, when, old → new), an invoice's history
// (INV/2026/00025 from MB-08/MB-09: who, when, payment status old → new) and the system's
// Audit Log screen (Settings › Records › Audit Log: when, who, record, field, from → to).
// Nothing is changed by this test.
const c = require('./common');
const a = require('./adm_common');
const owner = a.users.owner;
const BK = { name: 'BK4032', id: 9970, client: 'Vũ Thị Khánh' };
const INV = { name: 'INV/2026/00025', id: 2438 };
const BASE = 'https://carejiox.com';

module.exports = {
  meta: {
    id: 'AU-01', title: 'Audit trail shows when, who and what changed', short: 'Audit trail',
    title_vi: 'Nhật ký kiểm tra cho biết khi nào, ai và thay đổi gì',
    criterion: 'Record transaction activity with the date/time, acting user and changes made. Review representative booking and payment changes and the audit log; confirm source-record linkage and before/after values. This is a representative sample, not every transaction.',
    data: `Booking ${BK.name} (${BK.client}, rescheduled and reassigned on 4 Nov in test CR-02); invoice ${INV.name} (paid on 4 Nov in test MB-09); Settings › Records › Audit Log. Read-only: nothing is changed`,
    expected: 'Every required transaction has timestamp, user and change details.',
    ...owner,
  },
  proofVi: {
    'Booking history: who, when, old → new time and staff': 'Lịch sử lịch hẹn: ai, khi nào, giờ và nhân sự cũ → mới',
    'Booking history: confirmed, with who and when': 'Lịch sử lịch hẹn: đã xác nhận, có ai và khi nào',
    'Invoice history: payment status Not Paid → Paid, by Finance, with time': 'Lịch sử hóa đơn: trạng thái thanh toán Chưa trả → Đã trả, do Tài chính, có thời gian',
    'Invoice history: created by the nurse, with time': 'Lịch sử hóa đơn: điều dưỡng tạo, có thời gian',
    'Audit Log: when, who, record, field, from → to': 'Nhật ký kiểm tra: khi nào, ai, hồ sơ, trường, từ → thành',
    'Open goes to the booking the change belongs to': 'Nút Mở dẫn tới đúng lịch hẹn có thay đổi',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();
    await kit.note('Representative sample, read-only: one booking, one invoice and the Audit Log', 'Mẫu đại diện, chỉ xem: một lịch hẹn, một hóa đơn và Nhật ký kiểm tra');

    await kit.step(next(), `Operations › Bookings › ${BK.name} › Activity`, `Vận hành › Lịch hẹn › ${BK.name} › Hoạt động`);
    await a.area(kit, 'Operations');
    await a.bookingsList(kit);
    await kit.click(p.locator('button, a, span').filter({ hasText: /^\s*All Dates\s*$/ }).filter({ visible: true }).first(), 2500);
    await a.listSearch(kit, BK.name);
    await kit.click(p.locator('tr.o_data_row', { hasText: BK.name }).first().locator('td').nth(1), 4500);
    await c.hero(p).waitFor({ timeout: 15000 });
    const msg = p.locator('.o-mail-Message').filter({ hasText: /Rescheduled from/ }).first();
    await msg.waitFor({ timeout: 15000 });
    await kit.proof(msg, 'Booking history: who, when, old → new time and staff', (t) =>
      t.includes('Client UAT om_hn') && /\d{1,2}:\d{2}\s*(AM|PM)/.test(t) && /Rescheduled from 12\/11\/2026 09:00 to 13\/11\/2026 11:00/.test(t)
      && /Staff added:.*doctor_hn/.test(t) && /Staff removed:.*nurse_hn/.test(t), 4500);
    const confirmed = p.locator('.o-mail-Message').filter({ hasText: /Booking Confirmed/ }).first();
    await kit.proof(confirmed, 'Booking history: confirmed, with who and when', (t) =>
      /Booking Confirmed/.test(t) && t.includes('Client UAT om_hn') && /\d{1,2}:\d{2}\s*(AM|PM)/.test(t));

    await kit.step(next(), `Finance › Invoices › ${INV.name} › history`, `Tài chính › Hóa đơn › ${INV.name} › lịch sử`);
    await a.area(kit, 'Finance');
    await kit.click(c.sidebar(p, 'Invoices'), 3500);
    const box = p.locator('.o_searchview_input').filter({ visible: true }).first();
    await kit.type(box, INV.name, 1200);
    const numOpt = p.locator('.o_searchview_autocomplete li, .o-dropdown-item').filter({ hasText: /Number|Invoice/ }).filter({ visible: true }).first();
    if (await numOpt.count()) await kit.click(numOpt, 2500); else { await p.keyboard.press('Enter'); await kit.hold(2500); }
    const irow = p.locator('tr.o_data_row', { hasText: INV.name }).first();
    if (await irow.count()) await kit.click(irow.locator('td').nth(1), 4500);
    else { await kit.note(`Open ${INV.name}`, `Mở ${INV.name}`); await p.goto(`${BASE}/bizapp/action-1443/${INV.id}`); }
    await p.locator('.o-mail-Message').first().waitFor({ timeout: 15000 });
    const paid = p.locator('.o-mail-Message').filter({ hasText: /Invoice paid/ }).first();
    const inv = p.locator('.o-mail-Message').filter({ hasText: /Invoice Created/ }).first();
    await kit.proof(paid, 'Invoice history: payment status Not Paid → Paid, by Finance, with time', (t) =>
      /Client UAT owner/.test(t) && /Not Paid\s*\S*\s*Paid/.test(t) && /\d{1,2}:\d{2}\s*(AM|PM)/.test(t), 4000);
    await kit.proof(inv, 'Invoice history: created by the nurse, with time', (t) =>
      /Client UAT nurse_hcm/.test(t) && /Invoice Created/.test(t) && /\d{1,2}:\d{2}\s*(AM|PM)/.test(t));

    await kit.step(next(), 'Settings › Records › Audit Log: the system-wide change log', 'Cài đặt › Hồ sơ › Nhật ký kiểm tra: nhật ký thay đổi toàn hệ thống');
    await a.area(kit, 'Settings');
    await kit.click(c.sidebar(p, 'Records'), 4000);
    await kit.step(next(), `Search the Record column for ${BK.name}`, `Tìm theo cột Hồ sơ: ${BK.name}`);
    while (await p.locator('.o_searchview_facet .o_facet_remove').filter({ visible: true }).count()) {
      await kit.click(p.locator('.o_searchview_facet .o_facet_remove').filter({ visible: true }).first(), 1500);
    }
    await kit.type(p.locator('.o_searchview_input').filter({ visible: true }).first(), BK.name, 1500);
    await kit.click(p.locator('.o_searchview_autocomplete li, .o-dropdown-item').filter({ hasText: 'Search Record for' }).filter({ visible: true }).first(), 3500);
    const arow = p.locator('tr.o_data_row').filter({ has: p.locator('td[name=field_name]', { hasText: /^\s*Status\s*$/ }) }).first();
    await arow.waitFor({ timeout: 15000 });
    const head = p.locator('.o_list_renderer thead').filter({ visible: true }).first();
    await kit.proof([head, arow], 'Audit Log: when, who, record, field, from → to', async () => {
      const cell = async (nm) => ((await arow.locator(`td[name=${nm}]`).innerText()) || '').trim();
      return /Nov 4, \d{1,2}:\d{2} (AM|PM)/.test(await cell('date')) && (await cell('user_id')) === 'Client UAT om_hn'
        && (await cell('record_name')) === `${BK.client} (${BK.name})` && (await cell('field_name')) === 'Status'
        && (await cell('old_value')) === 'Draft' && (await cell('new_value')) === 'Confirmed';
    }, 4500);
    await kit.step(next(), 'Open: from the log line to the booking', 'Mở: từ dòng nhật ký tới lịch hẹn');
    await kit.click(arow.locator('button, a').filter({ hasText: /^\s*Open\s*$/ }).first(), 4500);
    await c.hero(p).waitFor({ timeout: 15000 });
    await kit.proof(c.hero(p), 'Open goes to the booking the change belongs to', (t) => t.includes(BK.name) && t.includes(BK.client));
  },
};
