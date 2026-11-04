// MB-10 E-invoice (red invoice) log for the nurse-app invoice: what really happens on carejiox.
// Each posted invoice is sent automatically to Viettel's TEST e-invoice account (supplier
// 0100109106-507), which returns an e-invoice number; status, number, time, actor and the
// request log are on the invoice and in Finance › Red Invoice Log. Nothing is sent by hand here.
const c = require('./common');
const m = require('./mb_common');
const { searchPatient } = require('./MB-08');
const fin = m.users.finance;
const cl = m.client;

module.exports = {
  meta: {
    id: 'MB-10', title: 'E-invoice status and log for the nurse-app invoice', short: 'Mobile e-invoice log',
    title_vi: 'Trạng thái và nhật ký hóa đơn điện tử của hóa đơn từ ứng dụng điều dưỡng',
    criterion: 'Record the e-invoice signing / tax upload step for the invoice: status, reference, actor and time, and any error. Actual digital signing and tax-department upload are deferred until before go-live.',
    data: `Invoice ${m.load().invoice || '(from MB-08)'} for ${cl.name} (${cl.code}); sent once by Finance (${fin.login}) with Generate Red Invoice to Viettel’s TEST e-invoice account (supplier 0100109106-507), not to the tax department`,
    expected: 'Internal placeholder log exists; actual signing/upload is explicitly deferred until before go-live.',
    ...fin,
  },
  proofVi: {
    'E-invoice: Issued, number K26MTB…, no error': 'Hóa đơn điện tử: Đã phát hành, số K26MTB…, không lỗi',
    'Log: one request to Viettel’s test account, succeeded (200)': 'Nhật ký: một yêu cầu tới tài khoản thử nghiệm Viettel, thành công (200)',
    'Who and when: invoice created by the nurse at completion': 'Ai và khi nào: điều dưỡng tạo hóa đơn khi hoàn thành',
    'Finance › Red Invoice Log: the same request': 'Tài chính › Nhật ký hóa đơn đỏ: cùng yêu cầu',
  },

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.invoice) throw new Error('no invoice in mb_state.json: run MB-08 first');
    const inv = st.invoice;
    const when = new Date(new Date(st.completedAt).getTime() + 7 * 3600e3);
    const dShown = `${when.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })} ${when.getUTCDate()}`;
    const author = st.invoiceBy || m.users.nurse.name;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await kit.step(next(), `Finance › Invoices › open ${inv}`, `Tài chính › Hóa đơn › mở ${inv}`);
    await kit.area('Finance');
    await kit.click(c.sidebar(p, 'Invoices'), 3000);
    await searchPatient(kit, st.searchName || cl.name);   // searchName: practice on another client's invoice
    await kit.click(p.locator('tr.o_data_row', { hasText: inv }).first().locator('td').nth(1), 4500);
    await p.locator('.o_notebook').first().waitFor({ timeout: 15000 });

    await kit.step(next(), 'Red Invoice tab: not sent yet (Pending)', 'Thẻ Hóa đơn đỏ: chưa gửi (Đang chờ)');
    await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Red Invoice\s*$/ }).first(), 2200);
    const pane = p.locator('.o_notebook .tab-pane.active').first();
    if (!st.einvoice) {
      // The invoice was posted from the nurse app before 4 Nov's fix, so it was never sent:
      // Finance sends it once with Generate Red Invoice (owner-approved, Viettel's TEST account).
      kit._proofVi['Before: e-invoice Pending, no number'] = 'Trước: hóa đơn điện tử Đang chờ, chưa có số';
      await kit.proof(pane.locator('.o_group').first(), 'Before: e-invoice Pending, no number', async () => {
        const v = await kit.fieldValues(['red_invoice_state', 'red_invoice_no'], pane);
        return /Pending/i.test(v.red_invoice_state) && !v.red_invoice_no;
      });
      await kit.step(next(), 'Generate Red Invoice (once)', 'Tạo hóa đơn đỏ (một lần)');
      await kit.click(p.locator('button[name=action_redinvoice_generate]').filter({ visible: true }).first(), 6000);
      await p.waitForLoadState('networkidle').catch(() => {});
      await kit.hold(2000);
      const tabAgain = p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Red Invoice\s*$/ }).first();
      await kit.click(tabAgain, 2000);
    }
    await kit.note('Sent to Viettel’s test e-invoice account, not to the tax department; live signing and tax upload are set up before go-live.',
      'Đã gửi tới tài khoản hóa đơn điện tử thử nghiệm của Viettel, không gửi cơ quan thuế; ký số thật và gửi thuế được thiết lập trước khi vận hành chính thức.');
    await kit.hold(2500);
    const page1 = p.locator('.o_notebook .tab-pane.active').first();
    await kit.proof(page1.locator('.o_group').first(), 'E-invoice: Issued, number K26MTB…, no error', async (t) => {
      const v = await kit.fieldValues(['red_invoice_state', 'red_invoice_no', 'red_invoice_last_sync', 'red_invoice_last_error'], page1);
      return /Issued/.test(v.red_invoice_state + t) && /^K26MTB\d+/.test(v.red_invoice_no) && v.red_invoice_last_sync.includes(`${m.today().mon} ${m.today().day}`) && !v.red_invoice_last_error;
    }, 4200);
    const vals = await kit.fieldValues(['red_invoice_no'], page1);
    kit.records['E-invoice number'] = vals.red_invoice_no;
    m.save({ einvoice: vals.red_invoice_no });

    await kit.step(next(), 'Red Invoice Log tab: the request sent', 'Thẻ Nhật ký hóa đơn đỏ: yêu cầu đã gửi');
    await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Red Invoice Log\s*$/ }).first(), 2200);
    const logRows = p.locator('.o_notebook .tab-pane.active tr.o_data_row').filter({ visible: true });
    await kit.proof(logRows.first(), 'Log: one request to Viettel’s test account, succeeded (200)', async (t) =>
      (await logRows.count()) === 1 && /Succeeded/.test(t) && /\b200\b/.test(t) && /0100109106-507/.test(t) && t.includes(dShown), 4200);

    await kit.step(next(), 'Who and when: the invoice history', 'Ai và khi nào: lịch sử hóa đơn');
    const msg = p.locator('.o-mail-Message').filter({ hasText: /Invoice Created/ }).filter({ visible: true }).last();
    await msg.scrollIntoViewIfNeeded().catch(() => {});
    const doneMin = when.getUTCHours() * 60 + when.getUTCMinutes();
    const atDone = (t) => { const re = /(\d{1,2}):(\d{2})\s*(AM|PM)?/gi; let x;
      while ((x = re.exec(t))) { let h = Number(x[1]); if (x[3]) h = (h % 12) + (x[3].toUpperCase() === 'PM' ? 12 : 0); if (Math.abs(h * 60 + Number(x[2]) - doneMin) <= 2) return true; }
      return false; };
    await kit.proof(msg, 'Who and when: invoice created by the nurse at completion', (t) => t.includes(author) && /Invoice Created/.test(t) && atDone(t));

    await kit.step(next(), 'Finance › Red Invoice Log', 'Tài chính › Nhật ký hóa đơn đỏ');
    await kit.click(c.sidebar(p, 'Red Invoice Log'), 3500);
    const lr = p.locator('tr.o_data_row', { hasText: inv }).filter({ visible: true });
    await kit.proof(lr.first(), 'Finance › Red Invoice Log: the same request', async (t) =>
      (await lr.count()) === 1 && /Succeeded/.test(t) && /\b200\b/.test(t) && t.includes(dShown), 4200);
    await kit.note('No signing or tax upload is done by this test; the client deferred them until before go-live.',
      'Bài kiểm tra này không ký số và không gửi thuế; khách hàng đã hoãn các bước đó đến trước khi vận hành chính thức.');
  },
};
