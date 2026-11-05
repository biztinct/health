// Shared helpers for the Accounts receivable cases AR-01..AR-06 (Hà Nội, 5 Nov 2026).
//
// One story for the six videos, handed from case to case through ar_state.json (never the
// shared state.json; AR_STATE=<file> points a practice run at another state file):
//   setup   om_hn books three clinic visits for Nguyễn Văn An today with nurse_hn; she accepts.
//   AR-02   v1 (Internal examination bs_020, 500,000 ₫): nurse completes, Pay Now, Cash.
//   AR-01   v2 (Online internal examination bs_030, 200,000 ₫ less the TC-03 10% = 180,000 ₫):
//           nurse completes, Pay Later; Finance reviews both invoices and their receivables.
//   AR-03   om_hn confirms the nurse handed in v1's 500,000 ₫ cash (Operations › Collections).
//   AR-04   Finance records 80,000 ₫ cash on the v2 invoice: 100,000 ₫ left.
//   setup   v3 (bs_030, 200,000 ₫) completed with Pay Later: a fresh unpaid charge.
//   AR-05   credit note cancels v3's unpaid charge; refund of v1's cash reopens the amount owing.
//   AR-06   the AR transaction log for all of the above, and its export.
// Money steps are one-shot: each case has a STOP switch (practice stops at the dialog) and a
// REHEARSE switch (the after-steps on old records, view only). The client carries unrelated
// trial invoices (INV/2026/00001-00003, 00017-00018, 00020-00024): every proof names OUR numbers.
const fs = require('fs');
const path = require('path');
const c = require('./common');
const a = require('./as_common');
const m = require('./mb_common');

const STATE = process.env.AR_STATE ? path.resolve(process.env.AR_STATE) : path.join(__dirname, '..', 'ar_state.json');
const load = () => (fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, 'utf8')) : {});
const save = (patch) => fs.writeFileSync(STATE, JSON.stringify({ ...load(), ...patch }, null, 1));

const user = (login, role, role_vi, extra = {}) => ({ login, password: c.pw(login), role, role_vi, ...extra });
const users = {
  om: user('om_hn', 'Operations Manager, Hanoi', 'Quản lý vận hành Hà Nội', { name: 'Client UAT om_hn' }),
  nurse: user('nurse_hn', 'Nurse, Hanoi', 'Điều dưỡng Hà Nội', { name: 'Client UAT nurse_hn' }),
  finance: user('uat_owner', 'Owner (Finance)', 'Chủ sở hữu (Tài chính)', { name: 'Client UAT owner' }),
};

const client = { name: 'Nguyễn Văn An', code: '01_0000126', id: 37955, address: '12 Phố Huế, Hai Bà Trưng, Hà Nội' };

// The three visits (price list "Client UAT 20261013 V01.01 (VND)", the default one).
const VISITS = {
  v1: { tc: 'TC-01', code: 'bs_020', search: 'Internal examination', product: 'Internal examination', productVi: 'Khám nội khoa',
    duration: '1 hour', price: 500000, disc: 0, total: 500000 },
  v2: { tc: 'TC-03', code: 'bs_030', search: 'Online internal', product: 'Online internal examination', productVi: 'Khám nội trực tuyến',
    duration: '30 minutes', price: 200000, disc: 10, total: 180000 },
  v3: { tc: 'AR-05', code: 'bs_030', search: 'Online internal', product: 'Online internal examination', productVi: 'Khám nội trực tuyến',
    duration: '30 minutes', price: 200000, disc: 0, total: 200000 },
};
VISITS.v2b = VISITS.v2;   // AR-01 re-take after the invoice-discount fix (5 Nov)
VISITS.v4 = VISITS.v3;    // AR-05 re-take (6 Nov): the unpaid charge for the credit note
VISITS.v5 = VISITS.v1;    // AR-05 re-take (6 Nov): the cash payment to refund

const money = m.money;                                   // 180,000 / 180.000, optional decimals
const num = (s) => Number(String(s).replace(/[^\d-]/g, '')) || 0;
const fmt = (n) => `${Math.round(n).toLocaleString('en-US')} ₫`;
const fmtVi = (n) => `${Math.round(n).toLocaleString('vi-VN')} ₫`;
const today = () => a.vnDay(0);
const HANOI = { latitude: 21.0136, longitude: 105.8487 };

// ---------------------------------------------------------------- nurse app
async function asNurse(kit, n) {
  // the 540 px nurse-app screen: flip the caption bar by the real height
  kit._capClear = async function (bottom) {
    const h = (this.page.viewportSize() || { height: 720 }).height;
    const top = bottom > h - 80;
    if (top !== !!(this.state && this.state.capTop)) await this._state({ capTop: top });
  };
  await kit.page.setViewportSize(m.PHONE);
  await kit.context.setGeolocation(HANOI);
  await kit.switchUser(n, users.nurse, true);
  await kit.page.locator('.booking-card, .empty-state').first().waitFor({ timeout: 20000 }).catch(() => {});
  await kit.hold(800);
}
async function asStaff(kit, n, who) {
  await kit.page.setViewportSize(m.DESKTOP);
  await kit.switchUser(n, who, false);
}

// Native pop-ups (alert / confirm) are not drawn into the recording: note them and accept.
function catchPopups(kit) {
  const pops = [];
  kit.page.on('dialog', async (d) => { pops.push(d.message()); console.log('  pop-up:', d.message()); await new Promise((r) => setTimeout(r, 400)); await d.accept().catch(() => {}); });
  return pops;
}

// Open the visit, Start Service if it has not started yet.
async function startIfNeeded(kit, next, st, v) {
  const p = kit.page;
  await m.openVisit(kit, st);
  const start = m.btn(p, /^\s*Start Service\s*$/);
  if (await start.count()) {
    await kit.step(next(), 'Start Service', 'Bắt đầu dịch vụ');
    await kit.click(start, 4000);
    await m.sheet(p).locator('.timer-badge').first().waitFor({ timeout: 15000 }).catch(() => {});
  }
  // View service stays disabled until the visit has a clinical note
  const view = m.btn(p, /^\s*(receipt\s*)?View service\s*$/);
  await view.waitFor({ timeout: 15000 });
  if (await view.isDisabled()) {
    await kit.step(next(), 'Clinical Notes › Add New Clinical Note, then save it', 'Ghi chú lâm sàng › Thêm ghi chú mới, rồi lưu');
    await kit.click(m.btn(p, /Clinical Notes/), 2500);
    await kit.click(m.btn(p, /Add New Clinical Note/), 2500);
    await kit.type(p.getByPlaceholder('Enter clinical notes...'), `UAT ONLY - ${v.product.toLowerCase()} done at the clinic (fictional)`, 600);
    await kit.click(m.btn(p, /Confirm and Save/), 3500);
    await kit.click(p.locator('button').filter({ hasText: /^\s*close\s*$/ }).filter({ visible: true }).last(), 1500);
    await kit.hold(1000);
    if (!(await m.sheet(p).count())) await m.openVisit(kit, st);
  }
}

// View service → (optional discount) → Save Quote → Payment wizard. Returns { quote, wiz }.
// stop: 'quote' cancels the quote window without saving (practice of the discount step).
async function quoteAndWizard(kit, next, v, { checked, discountReason, stop = '' }) {
  const p = kit.page;
  const V = kit._proofVi;
  await kit.step(next(), 'View service: check the service and price with the client', 'Xem dịch vụ: kiểm tra dịch vụ và giá cùng khách hàng');
  await kit.click(m.btn(p, /^\s*(receipt\s*)?View service\s*$/), 3000);
  const quote = p.locator('.invoice-modal').filter({ visible: true }).first();
  await quote.waitFor({ timeout: 15000 });
  const card = quote.locator('.invoice-item-card').filter({ hasText: v.product }).first();
  const L1 = `Quote: ${v.product} (${v.code}) × 1 at ${fmt(v.price)}`;
  V[L1] = `Báo giá: ${v.productVi} (${v.code}) × 1, ${fmtVi(v.price)}`;
  await kit.proof(card, L1, async (t) => {
    const qty = await card.locator('.qty-cell input').first().inputValue().catch(() => '');
    return (await quote.locator('.invoice-item-card').count()) === 1 && Number(qty) === 1 && money(v.price).test(t);
  });
  if (v.disc) {
    await kit.step(next(), `${v.tc} discount agreed with the client: ${v.disc}% with the reason`, `Giảm giá ${v.tc} đã thỏa thuận với khách hàng: ${v.disc}% kèm lý do`);
    await kit.type(card.locator('.disc-cell input').first(), String(v.disc), 600);
    await kit.type(card.locator('.discount-reason-input-full').first(), discountReason, 500);
    const L2 = `Discount ${v.disc}% with the reason`;
    V[L2] = `Giảm ${v.disc}% kèm lý do`;
    await kit.proof(card, L2, async () => Number(await card.locator('.disc-cell input').first().inputValue()) === v.disc
      && (await card.locator('.discount-reason-input-full').first().inputValue()) === discountReason);
    if (stop === 'quote') { await kit.click(quote.locator('.modal-footer button').filter({ hasText: /^\s*Cancel\s*$/ }).first(), 1500); return {}; }
  }
  await kit.step(next(), 'Note the check and Save Quote', 'Ghi chú kiểm tra và Lưu báo giá');
  await kit.type(quote.locator('textarea').first(), checked, 500);
  await kit.click(quote.locator('button').filter({ hasText: /Save Quote/ }).first(), 4000);
  await quote.locator('.success-message').first().waitFor({ timeout: 15000 }).catch(() => {});
  const L3 = `Quote saved: total ${fmt(v.total)}, tax 0`;
  V[L3] = `Đã lưu báo giá: tổng ${fmtVi(v.total)}, thuế 0`;
  await kit.proof(quote.locator('.invoice-totals').first(), L3, (t) => /Tax\s*0\b/.test(t) && money(v.total).test(t));
  // the window is taller than the tablet screen: the saved message sits below the totals
  V['Quote checked and saved'] = 'Đã kiểm tra và lưu báo giá';
  await kit.proof(quote.locator('.success-message').first(), 'Quote checked and saved', /verified successfully/i, 2400);
  await kit.click(quote.locator('button').filter({ hasText: /^\s*payment\s*Payment\s*$|^\s*Payment\s*$/ }).first(), 2500);
  const wiz = p.locator('.payment-wizard-modal').filter({ visible: true }).first();
  await wiz.waitFor({ timeout: 15000 });
  return { quote, wiz };
}

// After Complete Service the app asks about the next visit. With no later visit booked it asks
// "Schedule Next Appointment?" (answer: no next visit, reason Other + explanation). When the client
// already has a later visit, it shows that "Next Appointment Details" instead: keep it (Cancel).
async function closeQuestion(kit, next, pops, reason) {
  const p = kit.page;
  const anyQ = p.locator('.next-visit-modal').filter({ visible: true }).first();
  await anyQ.waitFor({ timeout: 30000 });
  await kit.hold(1200);
  const qa = p.locator('.next-visit-modal').filter({ hasText: /Schedule Next Appointment\?/ }).filter({ visible: true }).first();
  if (await qa.count()) {
    await kit.step(next(), 'Close question: no next visit wanted, reason Other with an explanation; Submit', 'Câu hỏi kết thúc: không cần lượt khám tiếp, lý do Khác kèm giải thích; Gửi');
    await kit.click(qa.locator('button', { hasText: /does not need or want a next visit/ }).first(), 1500);
    const sec = qa.locator('.no-future-visit-section').first();
    await kit.select(sec, 'Other');
    await kit.type(sec.locator('textarea').first(), reason, 600);
    const before = pops.length;
    await kit.click(sec.locator('button', { hasText: /^\s*Submit\s*$/ }).first(), 3500);
    const said = pops.slice(before).join(' / ');
    if (said) await kit.note(`The app’s pop-up message: “${said}”`, `Thông báo bật lên của ứng dụng: “${said}”`);
    await qa.waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
    return;
  }
  await kit.step(next(), 'The client already has a later visit booked: the app shows it; keep it (Cancel)', 'Khách hàng đã có lượt khám sau: ứng dụng hiển thị lượt đó; giữ nguyên (Hủy)');
  await kit.click(anyQ.locator('.modal-footer button, button').filter({ hasText: /^\s*Cancel\s*$/ }).filter({ visible: true }).last(), 2500);
  await anyQ.waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
}

// ---------------------------------------------------------------- office screens
const sidebar = c.sidebar;

// Finance › Invoices, searched by the client's name (Enter searches the client).
async function invoicesFor(kit, n, en, vi) {
  const p = kit.page;
  if (n) await kit.step(n, en || `Finance › Invoices: ${client.name}`, vi || `Tài chính › Hóa đơn: ${client.name}`);
  await kit.area('Finance');
  await kit.click(sidebar(p, 'Invoices'), 3000);
  await searchClient(kit);
}
async function searchClient(kit, name = client.name) {
  const p = kit.page;
  await kit.type(p.locator('.o_searchview_input').filter({ visible: true }).first(), name, 1200);
  // pick "Search Client for: …" where the first search field is something else (Payments, AR log)
  const opt = p.locator('.o_searchview_autocomplete li, .o_searchview_autocomplete .o-dropdown-item')
    .filter({ hasText: /Search\s+(Client|Patient|Customer|Partner)\s+for:/ }).filter({ visible: true }).first();
  if (await opt.count()) await kit.click(opt, 300); else await p.keyboard.press('Enter');
  await kit.hold(2500);
}
// the number cell reads "INV/2026/00027" (Invoices) or "INV/2026/00027 (S04521)" (Receivables)
const invRow = (p, inv) => p.locator('tr.o_data_row').filter({ has: p.locator('td', { hasText: new RegExp(`^\\s*${inv.replace(/\//g, '\\/')}(\\s*\\([^)]*\\))?\\s*$`) }) }).first();

// Open an invoice from the list (the number cell).
async function openInvoice(kit, inv) {
  const p = kit.page;
  const row = invRow(p, inv);
  await row.waitFor({ timeout: 15000 });
  await kit.click(row.locator('td').nth(3), 4000);
  await p.locator('.fin-invoice-header').first().waitFor({ timeout: 15000 }).catch(() => {});
  await kit.hold(1000);
}
const invHead = (p) => p.locator('.fin-invoice-header').filter({ visible: true }).first();
// "180,000 TOTAL 100,000 AMOUNT DUE 80,000 PAID" → { total, due, paid, status }
function headNums(t) {
  const s = t.replace(/\s+/g, ' ');
  const mm = s.match(/([\d.,]+)\s*TOTAL\s*([\d.,]+)\s*AMOUNT DUE\s*([\d.,]+)\s*PAID/i);
  return mm ? { total: num(mm[1]), due: num(mm[2]), paid: num(mm[3]) } : null;
}
// The invoice opened from a booking uses the full invoice form: its totals block reads
// "Untaxed Amount 180,000 ₫ Total 180,000 ₫ [Paid on 11/05/2026 80,000 ₫] Amount Due 100,000 ₫".
const footer = (p) => p.locator('.oe_subtotal_footer').filter({ visible: true }).first();
function footNums(t) {
  const s = t.replace(/\s+/g, ' ');
  const g = (re) => { const x = s.match(re); return x ? num(x[1]) : null; };
  const paid = [...s.matchAll(/(?:Paid|Reversed) on [\d/]+\s*([\d.,]+)/g)].map((x) => num(x[1]));
  return { untaxed: g(/Untaxed Amount:?\s*([\d.,]+)/), total: g(/(?:^|[^d] )Total:?\s*([\d.,]+)/), due: g(/Amount Due:?\s*([\d.,]+)/),
    tax: g(/(?:^| )(?:Tax|VAT)[^:\d]*:?\s*([\d.,]+)/), paid };
}
// The invoice on screen, whichever form shows it: Finance › Invoices opens the finance form
// (header boxes TOTAL / AMOUNT DUE / PAID); a booking or a payment record opens the full form
// (breadcrumb + ribbon + totals block). → { inv, total, due, paid, label, boxes }
async function invSummary(p) {
  await p.locator('.fin-invoice-header, .oe_subtotal_footer').filter({ visible: true }).first().waitFor({ timeout: 15000 });
  await p.waitForTimeout(800);
  const head = invHead(p);
  if (await head.count()) {
    const t = await head.innerText();
    const h = headNums(t) || {};
    const label = (t.match(/\b(NOT PAID|PARTIAL|PAID|REVERSED|IN PAYMENT)\b/i) || [''])[0].toUpperCase();
    return { inv: (t.match(/R?INV\/\d{4}\/\d+/) || [''])[0], total: h.total, due: h.due, paid: h.paid, label, boxes: [head] };
  }
  const crumbs = p.locator('.o_breadcrumb').filter({ visible: true }).first();
  const ct = await crumbs.innerText().catch(() => '');
  const f = footNums(await footer(p).innerText());
  const ribbon = p.locator('.ribbon, .o_widget_web_ribbon').filter({ visible: true }).first();
  const label = (((await ribbon.count()) && (await ribbon.innerText().catch(() => ''))) || 'NOT PAID').trim().toUpperCase();
  // the open record is the last breadcrumb item ("… / RINV/2026/00002 (Reversal of: INV/…)"):
  // its own number is the first one in that item
  const items = await crumbs.locator('li, .breadcrumb-item, a, span').allInnerTexts().catch(() => []);
  const lastItem = (ct.split(/\n|\s\/\s/).map((x) => x.trim()).filter(Boolean).pop()) || items.pop() || '';
  const inv = (lastItem.match(/R?INV\/\d{4}\/\d+/) || ct.match(/R?INV\/\d{4}\/\d+/g) || [''])[0];
  return { inv, total: f.total, due: f.due, paid: f.paid.reduce((s, x) => s + x, 0), label, boxes: [crumbs, footer(p)] };
}
const smartBtn = (p, re) => p.locator('.o_form_view .oe_button_box button, .o_control_panel button, .o_form_view button.oe_stat_button')
  .filter({ hasText: re }).filter({ visible: true }).first();

// Back to a list through the breadcrumb, then park the pointer off the left rail.
async function crumb(kit, re) {
  const p = kit.page;
  await kit.click(p.locator('.o_breadcrumb a, .breadcrumb a').filter({ hasText: re }).filter({ visible: true }).first(), 3500);
  await p.mouse.move(760, 400, { steps: 12 });
  await kit.hold(1000);
}

// A payment page opened from an invoice has no left rail: go back through the first
// breadcrumb link (the booking or the list) until the rail is there.
async function backToRail(kit) {
  const p = kit.page;
  const rail = p.getByRole('button', { name: /^Finance\b/ }).first();
  for (let i = 0; i < 3 && !(await rail.isVisible().catch(() => false)); i++) {
    await kit.click(p.locator('.o_breadcrumb a, .breadcrumb a').filter({ visible: true }).first(), 3500);
    await p.mouse.move(760, 400, { steps: 12 });
  }
}

// Payments (Finance) or Collections (Operations): the transaction for an invoice.
const txnRow = (p, ref) => p.locator('tr.o_data_row', { hasText: ref }).first();

module.exports = { STATE, load, save, users, client, VISITS, money, num, fmt, fmtVi, today, HANOI, asNurse, asStaff, catchPopups,
  startIfNeeded, quoteAndWizard, closeQuestion, sidebar, invoicesFor, searchClient, invRow, openInvoice, invHead, headNums, footer, footNums, invSummary, smartBtn,
  crumb, backToRail, txnRow, m, a, c };
