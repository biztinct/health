// AR-06 Accounting transaction log: Finance › Receivables › AR Transactions for today's AR
// records of Nguyễn Văn An (AR-01..AR-05): each invoice, payment, credit note and refund with
// its debit and credit accounts, amount, source document, booking, who prepared it and when;
// the cash hand-in row (who handed over, who received, receipt); the log's export.
// View only. AR06_DAY=YYYY-MM-DD and AR06_BK=BK1,BK2 rehearse on another day's records.
const fs = require('fs');
const os = require('os');
const path = require('path');
const r = require('./ar_common');
const fin = r.users.finance;
const cl = r.client;

// What each row must say (event, debit, credit) — the ledger rule for that event.
const RULES = {
  Invoice: { dr: /Account Receivable/, cr: /Product Sales/, vi: 'Hóa đơn' },
  Payment: { dr: /Outstanding Receipts/, cr: /Account Receivable/, vi: 'Thanh toán' },
  'Credit Note': { dr: /Product Sales/, cr: /Account Receivable/, vi: 'Giấy báo có' },
  Refund: { dr: /Account Receivable/, cr: /Outstanding Payments/, vi: 'Hoàn tiền' },
  // the cash hand-in moves cash between staff: no accounts, who → whom and the receipt instead
  Handover: { dr: /^$/, cr: /^$/, vi: 'Nộp tiền', handover: true },
};

module.exports = {
  meta: {
    id: 'AR-06', title: 'Accounting log for invoices, payments, credit note and refund', short: 'AR transaction log',
    title_vi: 'Nhật ký kế toán cho hóa đơn, thanh toán, giấy báo có và hoàn tiền',
    criterion: 'Retain an accounting transaction log for invoicing, payments and relevant cash/refund activity. Each entry must identify the correct accounts, amount, source document, acting user and time. The client identifies upload to MISA as a manual activity, not an automatic integration acceptance requirement.',
    data: (() => { const s = r.load(); return `All AR records of ${cl.name} (${cl.code}) from AR-01..AR-05 on 5 Nov 2026: invoices INV/2026/00026–00032 (bookings BK4066, BK4087, BK4067, BK4068, BK4107, BK4115, BK4116), payments PCSH1/2026/00011–00013 and 00015, cash hand-ins PAY01389 and PAY01388, credit notes RINV/2026/00002 and ${s.cn3b || '?'}, refunds PAY01392 and ${s.refund2 || '?'} (AR-05 take 1 and re-take); viewed by Finance (${fin.login}). No upload to MISA (a manual step for the client). All data is fictional.`; })(),
    expected: 'Every transaction has correct accounts, amount, actor/time and source reference.',
    ...fin,
  },
  proofVi: {},

  async run(kit) {
    const p = kit.page;
    const st = r.load();
    const V = kit._proofVi;
    let n = 1;
    const next = () => ++n;
    await kit.login();
    const day = process.env.AR06_DAY ? (() => { const d = new Date(process.env.AR06_DAY + 'T00:00:00Z'); return { d, day: d.getUTCDate(), mon: d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }) }; })() : r.today();
    const bks = process.env.AR06_BK ? process.env.AR06_BK.split(',') : ['v1old', 'v1', 'v2', 'v2b', 'v3', 'v4', 'v5'].map((k) => (st[k] || {}).bk).filter(Boolean);
    const users = [r.users.nurse.name, fin.name, r.users.om.name];
    const MAP = st.ar06map || {};   // source document (or hand-in receipt) → its booking

    // ------------------------------------------------------------ the log, today, this client
    await kit.step(next(), 'Finance › Receivables › AR Transactions', 'Tài chính › Phải thu › Giao dịch AR');
    await kit.area('Finance');
    await kit.click(r.sidebar(p, 'Receivables'), 3000);
    await kit.click(p.locator('button, a').filter({ hasText: /^\s*AR Transactions\s*$/ }).filter({ visible: true }).first(), 3000);
    await p.mouse.move(760, 400, { steps: 12 });
    await kit.step(next(), `Search the client ${cl.name}; show the oldest first`, `Tìm khách hàng ${cl.name}; hiển thị cũ nhất trước`);
    await r.searchClient(kit);
    // oldest first, so the story reads in order (DateTime column header: one click = ascending)
    await kit.click(p.locator('th[data-name=transaction_datetime]').filter({ visible: true }).first(), 2500);
    const head = await p.locator('th[data-name=transaction_datetime]').first().getAttribute('class');
    if (/o-sort-down/.test(head || '')) await kit.click(p.locator('th[data-name=transaction_datetime]').first(), 2500);
    const mine = p.locator('tr.o_data_row').filter({ hasText: `${day.mon} ${day.day},` });
    await mine.first().waitFor({ timeout: 15000 });
    const rows = [];
    for (let i = 0; i < await mine.count(); i++) {
      const t = (await mine.nth(i).innerText()).replace(/\s+/g, ' ');
      if (bks.some((b) => t.includes(`(${b})`)) || /Credit Note|Refund|Handover/.test(t) || (/Payment/.test(t) && t.includes(fin.name))) rows.push(t);
    }
    console.log('  today’s rows:', rows.length, rows.map((t) => t.slice(0, 160)));
    const L0 = `Today’s log for ${cl.name}: ${rows.length} entries`;
    V[L0] = `Nhật ký hôm nay của ${cl.name}: ${rows.length} dòng`;
    await kit.proof(p.locator('.o_list_renderer').filter({ visible: true }).first(), L0, () => rows.length >= 17);

    // ------------------------------------------------------------ each entry, one by one
    await kit.step(next(), 'Open the first entry, then step through them with the arrow', 'Mở dòng đầu tiên, rồi xem lần lượt bằng mũi tên');
    await kit.click(mine.first().locator('td').nth(2), 3500);
    const seen = [];
    for (let i = 0; i < 25; i++) {
      const sheet = p.locator('.o_form_sheet').filter({ visible: true }).first();
      await sheet.waitFor({ timeout: 15000 });
      await kit.hold(800);
      const f = await kit.fieldValues(['event_type', 'debit_account_id', 'credit_account_id', 'amount', 'move_id', 'payment_id', 'booking_id', 'prepared_by', 'transaction_datetime', 'partner_id', 'status']);
      const t = await sheet.innerText();
      const ev = (f.event_type || (t.match(/Event Type\s*\n?\s*(Invoice|Payment|Credit Note|Refund|Handover|Service Delivery)/) || [])[1] || '').trim();
      const ours = f.partner_id.includes(cl.name) && (f.transaction_datetime.includes(`${day.mon} ${day.day},`))
        && (bks.some((b) => f.booking_id.includes(b)) || /Credit Note|Refund|Handover/.test(ev) || f.prepared_by === fin.name);
      if (ours && RULES[ev]) {
        const amt = r.num(f.amount);
        const bk = (f.booking_id.match(/BK\d+/) || [''])[0];
        if (RULES[ev].handover) {
          const h = await kit.fieldValues(['handed_over_by_id', 'received_by_id', 'receipt_reference', 'cash_record_id', 'invoice_id'], sheet);
          // the Cash Record box shows the record's name ("Nguyễn Văn An - 500,000 VND (Cash)"); the receipt identifies it
          const src = h.receipt_reference;
          const inv = (h.invoice_id.match(/INV\/\d{4}\/\d+/) || [''])[0];
          const L = `Handover ${r.fmt(amt)}: ${h.handed_over_by_id} → ${h.received_by_id}, receipt ${src}, ${inv}${bk ? `, ${bk}` : ''}; ${f.prepared_by}`;
          V[L] = `Nộp tiền ${r.fmtVi(amt)}: ${h.handed_over_by_id} → ${h.received_by_id}, biên nhận ${src}, ${inv}${bk ? `, ${bk}` : ''}; ${f.prepared_by}`;
          await kit.proof(sheet, L, () => amt > 0 && !!src && (!MAP[src] || MAP[src] === bk) && h.cash_record_id.includes(cl.name) && /Cash/.test(h.cash_record_id) && h.received_by_id === r.users.om.name
            && h.handed_over_by_id === r.users.nurse.name && (h.invoice_id || '').includes('INV/') && users.includes(f.prepared_by)
            && /\d{1,2}:\d{2}/.test(f.transaction_datetime), 2800);
          seen.push({ ev, amt, src, bk, by: f.prepared_by });
        } else {
          const src = (f.move_id.match(/(R?INV|P[A-Z]{3}\d)\/\d{4}\/\d+/) || [''])[0];
          const wrong = MAP[src] && MAP[src] !== bk ? ` (booking should be ${MAP[src]})` : '';
          const wrongVi = wrong ? ` (lịch hẹn đúng phải là ${MAP[src]})` : '';
          const L = `${ev} ${r.fmt(amt)}: debit ${f.debit_account_id}, credit ${f.credit_account_id}; ${src}${bk ? `, ${bk}` : ''}${wrong}; ${f.prepared_by}`;
          V[L] = `${RULES[ev].vi} ${r.fmtVi(amt)}: Nợ ${f.debit_account_id}, Có ${f.credit_account_id}; ${src}${bk ? `, ${bk}` : ''}${wrongVi}; ${f.prepared_by}`;
          // the booking on the row must be the source document's own booking
          await kit.proof(sheet, L, () => RULES[ev].dr.test(f.debit_account_id) && RULES[ev].cr.test(f.credit_account_id) && amt > 0 && !!src && (!MAP[src] || MAP[src] === bk)
            && users.includes(f.prepared_by) && /\d{1,2}:\d{2}/.test(f.transaction_datetime) && /Posted/i.test(f.status || t), 2600);
          seen.push({ ev, amt, src, bk, by: f.prepared_by });
        }
      }
      const nextBtn = p.locator('.o_pager_next').filter({ visible: true }).first();
      const pager = await p.locator('.o_pager_value').filter({ visible: true }).first().innerText().catch(() => '');
      const limit = await p.locator('.o_pager_limit').filter({ visible: true }).first().innerText().catch(() => '');
      if (!(await nextBtn.count()) || pager.trim() === limit.trim()) break;
      await kit.click(nextBtn, 2200);
    }
    console.log('  entries proved:', JSON.stringify(seen));
    // 7 visits invoiced (incl. the re-take visits), 4 payments, 2 hand-ins, 2 credit notes and 2 refunds (AR-05 take 1 and re-take)
    const need = { Invoice: 7, Payment: 4, Handover: 2, 'Credit Note': 2, Refund: 2 };
    const got = (e) => seen.filter((s) => s.ev === e).length;
    const LS = 'All 17 entries: 7 invoices, 4 payments, 2 cash hand-ins, 2 credit notes, 2 refunds';
    V[LS] = 'Đủ 17 dòng: 7 hóa đơn, 4 thanh toán, 2 lần nộp tiền mặt, 2 giấy báo có, 2 hoàn tiền';
    await kit.proof(p.locator('.o_form_sheet').filter({ visible: true }).first(), LS, () => Object.entries(need).every(([e, k]) => got(e) >= k));

    // ------------------------------------------------------------ export for the manual MISA upload
    await kit.step(next(), 'Back to AR Transactions: Export All (for the client’s manual MISA upload)', 'Quay lại Giao dịch AR: Xuất tất cả (để khách hàng tự tải lên MISA)');
    await kit.click(r.sidebar(p, 'Receivables'), 3000);
    await kit.click(p.locator('button, a').filter({ hasText: /^\s*AR Transactions\s*$/ }).filter({ visible: true }).first(), 3000);
    await p.mouse.move(760, 400, { steps: 12 });
    await r.searchClient(kit);
    const exp = p.locator('.o_control_panel button').filter({ hasText: /Export All/ }).filter({ visible: true }).first();
    await kit.proof(exp, 'The log offers Export All', /Export All/, 2000);
    const dl = p.waitForEvent('download', { timeout: 30000 }).catch(() => null);
    await kit.click(exp, 3000);
    const d = await dl;
    let name = '';
    let size = 0;
    if (d) {
      name = d.suggestedFilename();
      const to = path.join(process.env.AR06_EXPORT_DIR || os.tmpdir(), `AR-06 ${name}`);
      await d.saveAs(to).catch(() => {});
      size = fs.existsSync(to) ? fs.statSync(to).size : 0;
      console.log('  export saved:', to, size);
    }
    const LE = `Exported: “${name || 'no file'}” downloaded (${Math.round(size / 1024)} KB)`;
    V[LE] = `Đã xuất: tải xuống “${name || 'không có tệp'}” (${Math.round(size / 1024)} KB)`;
    await kit.proof(exp, LE, () => !!name && size > 0, 2400);
    await kit.note('Uploading to MISA is a manual step for the client; nothing is sent to MISA from here',
      'Tải lên MISA là bước thủ công của khách hàng; hệ thống không gửi gì sang MISA');
    await kit.hold(1500);
    kit.records['Log entries shown'] = String(seen.length);
    if (name) kit.records['Export'] = name;
  },
};
