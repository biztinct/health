// CR-01 Cancelled booking shows reason: the Hanoi Operations Manager cancels a booking with a
// reason and a note; reopened, it shows cancelled, the reason, the note, who and when.
const c = require('./common');
const a = require('./as_common');
const om = a.users.omhn;
const DAYS = 5;
const REASON = 'Other';
const NOTE = 'UAT client cancelled - the client called to cancel this visit';

module.exports = {
  meta: {
    id: 'CR-01', title: 'Cancelled booking shows reason, note, who and when', short: 'Cancellation reason',
    title_vi: 'Lịch hẹn đã hủy hiển thị lý do, ghi chú, người hủy và thời điểm',
    criterion: 'Cancel a booking with the selected cancellation reason and explanatory note. The cancelled state, reason, acting user and cancellation time must remain visible after reopening, while any applicable prepaid reservation is released.',
    data: `New clinic visit for ${a.client.name} (${a.client.code}), HN_PK_PKGDVU, ${a.vnDay(DAYS).mon} ${a.vnDay(DAYS).day} (no prepaid package); reason “${REASON}”, note “${NOTE}”`,
    expected: 'Cancellation retains reason and audit information.',
    ...om,
  },
  proofVi: {
    'Booking to cancel: open, next step Assign Staff': 'Lịch hẹn cần hủy: đang mở, bước tiếp theo Phân công nhân sự',
    'Reason and note entered': 'Đã nhập lý do và ghi chú',
    'Booking Cancelled': 'Lịch hẹn đã hủy',
    'Reopened: still Cancelled': 'Mở lại: vẫn Đã hủy',
    'Reason and note kept': 'Lý do và ghi chú được lưu',
    'Cancelled by the Hanoi manager, at the time it was done (Vietnam time)': 'Người hủy là quản lý Hà Nội, đúng thời điểm thực hiện (giờ Việt Nam)',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await a.openClient(kit, next());
    const b = await a.quickBook(kit, next, { days: DAYS, times: ['14:00', '14:30', '15:00', '15:30', '16:00', '16:30'] });
    kit.records['Booking'] = `${b.bk} (${b.shown}), cancelled`;
    await kit.proof([a.hero(p), a.nextCard(p)], 'Booking to cancel: open, next step Assign Staff', (t) => t.includes(b.bk) && t.includes(b.shown) && /Confirmed/.test(t) && /Assign Staff/.test(t));

    await kit.step(next(), 'The client calls to cancel: More › Cancel Booking', 'Khách hàng gọi để hủy: Thêm › Hủy lịch hẹn');
    await kit.click(p.locator('.ws-hero button, .o_form_view button').filter({ hasText: /^\s*More\s*$/ }).filter({ visible: true }).first(), 900);
    await kit.click(p.locator('.dropdown-item, .o-dropdown-item').filter({ hasText: /^\s*Cancel Booking\s*$/ }).filter({ visible: true }).first(), 2000);
    const sure = p.locator('.modal-content', { hasText: 'Are you sure' }).locator('button').filter({ hasText: /^\s*Ok\s*$/ }).first();
    if (await sure.count()) {
      await kit.note('“Are you sure you want to cancel this booking?” Ok', '“Bạn có chắc muốn hủy lịch hẹn này?” Đồng ý');
      await kit.click(sure, 2500);
    }

    await kit.step(next(), `Reason “${REASON}” and the note “${NOTE}”`, `Lý do “${REASON}” và ghi chú “${NOTE}”`);
    const dlg = p.locator('.modal-content').last();
    await kit.type(dlg.locator('.o_field_widget[name=cancellation_reason_id] input'), REASON, 1200);
    await kit.click(p.locator('.o-autocomplete--dropdown-item').filter({ hasText: new RegExp(`^\\s*${REASON}\\s*$`) }).first(), 800);
    await kit.type(dlg.locator('.o_field_widget[name=cancellation_notes] textarea'), NOTE, 500);
    await kit.proof(dlg.locator('.modal-body').first(), 'Reason and note entered', async () => {
      const v = await kit.fieldValues(['cancellation_reason_id', 'cancellation_notes'], dlg);
      return v.cancellation_reason_id === REASON && v.cancellation_notes === NOTE;
    });
    await kit.step(next(), 'Confirm the cancellation', 'Xác nhận hủy');
    const when = new Date(Date.now() + 7 * 3600e3);
    await kit.click(dlg.locator('button[name=action_confirm_cancellation]'), 3500);
    await kit.proof([a.statusChip(p), p.locator('div').filter({ hasText: /^\s*Booking Cancelled\s*See the Cancellation tab/ }).filter({ visible: true }).last()], 'Booking Cancelled', (t) => /Cancelled/.test(t) && /Booking Cancelled/.test(t));

    // reopen from the bookings list
    await openCancelled(kit, next(), b.bk);
    await kit.proof([a.hero(p), p.locator('div').filter({ hasText: /^\s*Booking Cancelled\s*See the Cancellation tab/ }).filter({ visible: true }).last()],
      'Reopened: still Cancelled', async (t) => /Cancelled/.test(t) && (await a.hero(p).innerText()).includes(b.bk));

    await kit.step(next(), 'Open the Cancellation tab', 'Mở thẻ Hủy lịch');
    await kit.click(p.locator('a.nav-link').filter({ hasText: /^\s*Cancellation\s*$/ }).filter({ visible: true }).first(), 2000);
    const f = (name) => c.field(p, name).locator('xpath=ancestor::*[contains(@class,"o_wrap_field") or contains(@class,"o_cell")][1]');
    await kit.proof([c.field(p, 'cancellation_reason_id'), c.field(p, 'cancellation_notes')], 'Reason and note kept', async () => {
      const v = await kit.fieldValues(['cancellation_reason_id', 'cancellation_notes']);
      return v.cancellation_reason_id === REASON && v.cancellation_notes === NOTE;
    });
    await kit.proof([c.field(p, 'cancelled_by'), c.field(p, 'cancellation_date')],
      'Cancelled by the Hanoi manager, at the time it was done (Vietnam time)', async () => {
        const v = await kit.fieldValues(['cancelled_by', 'cancellation_date']);
        const m = v.cancellation_date.match(/([A-Z][a-z]{2}) (\d{1,2}), (\d{1,2}):(\d{2}) (AM|PM)/);
        if (!m || !v.cancelled_by.includes('om_hn')) return false;
        const mon = when.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
        const hh = (Number(m[3]) % 12) + (m[5] === 'PM' ? 12 : 0);
        const diff = Math.abs(hh * 60 + Number(m[4]) - (when.getUTCHours() * 60 + when.getUTCMinutes()));
        return m[1] === mon && Number(m[2]) === when.getUTCDate() && diff <= 3;
      });
    void f;
  },
};

// Operations › Bookings: find the cancelled booking by its number (cancelled bookings may sit
// outside the default filter: clear it first) and open it.
async function openCancelled(kit, n, bk) {
  const p = kit.page;
  await kit.step(n, `Reopen it: Operations › Bookings › search ${bk}`, `Mở lại: Vận hành › Lịch hẹn › tìm ${bk}`);
  await kit.area('Operations');
  await kit.click(c.sidebar(p, 'Bookings'), 3000);
  const facets = p.locator('.o_searchview_facet .o_facet_remove').filter({ visible: true });
  while (await facets.count()) await kit.click(facets.first(), 1200);
  await kit.type(p.locator('.o_searchview_input').filter({ visible: true }).first(), bk, 300);
  await p.keyboard.press('Enter');
  await kit.hold(2000);
  const listBtn = p.locator('.o_switch_view.o_list').filter({ visible: true }).first();
  if (await listBtn.count()) await kit.click(listBtn, 3000);
  const row = p.locator('tr.o_data_row', { hasText: bk }).first();
  await row.waitFor({ timeout: 10000 }).catch(() => {});
  if (await row.count()) await kit.click(row.locator('td').nth(1), 4500);
  else await kit.click(p.getByText(bk).filter({ visible: true }).first(), 4500);
  await p.locator('.ws-hero').first().waitFor({ timeout: 15000 }).catch(() => {});
}
