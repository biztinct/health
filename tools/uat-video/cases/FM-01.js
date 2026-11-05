// FM-01 Compulsory fields: the New Contact form refuses a blank name and a blank phone/email
// and saves nothing; valid details save. Then the Owner sets a representative requirement in
// Settings › Master data › Field Requirements (Email on a contact, for the CRM job only), the
// CRM user's contact form enforces it, and the Owner removes it again (no requirement was
// configured before this test).
const c = require('./common');
const a = require('./adm_common');
const crm = a.users.crm;
const owner = a.users.owner;
const now = a.vnNow();
const phone = c.phone();
const name = `UAT-VID FM01 Caller ${now.hhmm}`;
const email = `uat.fm01.${now.dd}${now.hhmm}@example.com`;
const STOP = process.env.FM01_STOP || '';


module.exports = {
  meta: {
    id: 'FM-01', title: 'Compulsory fields block incomplete saves', short: 'Compulsory fields',
    title_vi: 'Trường bắt buộc chặn việc lưu khi thiếu thông tin',
    criterion: 'Enforce the configured compulsory fields in the relevant forms. Attempt a save or next step with required details blank and verify a clear validation response. Enter valid details and confirm the record can then be saved with those values retained.',
    data: `New Contact form as ${crm.login}: first blank, then fictional caller “${name}”, ${phone}. Field Requirements as ${owner.login}: Email on Contacts for the CRM job (set for this test, removed at the end); fictional email ${email}`,
    expected: 'Required fields block incomplete saves and permit valid entries.',
    ...crm,
  },
  proofVi: {
    'Blank form refused: name and phone or email are required': 'Biểu mẫu trống bị từ chối: bắt buộc nhập tên và số điện thoại hoặc email',
    'Nothing saved: still on step 1, no contact created': 'Không lưu gì: vẫn ở bước 1, không tạo liên hệ',
    'Today’s contacts unchanged: nothing saved': 'Danh sách liên hệ hôm nay không đổi: không lưu gì',
    'Valid details saved: contact created': 'Thông tin hợp lệ được lưu: đã tạo liên hệ',
    'Saved record keeps the name and phone': 'Hồ sơ đã lưu giữ tên và số điện thoại',
    'No requirement configured on Contacts yet': 'Chưa cấu hình trường bắt buộc nào cho Liên hệ',
    'Email required for the CRM job': 'Email bắt buộc với công việc CRM',
    'Email is marked required on the contact': 'Email được đánh dấu bắt buộc trên liên hệ',
    'Save refused: Email must be filled': 'Không cho lưu: phải nhập Email',
    'With the email the contact saves': 'Có email thì liên hệ được lưu',
    'Reopened: email and note kept': 'Mở lại: email và ghi chú vẫn còn',
    'Requirement removed again: Contacts back to none active': 'Đã gỡ yêu cầu: Liên hệ trở lại không có trường bắt buộc',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    // ------------------------------------------------------------ the New Contact form
    await kit.step(next(), 'Open CRM › Contacts', 'Mở CRM › Liên hệ');
    await kit.click(c.sidebar(p, 'CONTACTS'), 3000);
    // The list opens on Today's contacts: count them before and after the blank attempt.
    const listArea = p.locator('.o_list_renderer, .o_view_nocontent').filter({ visible: true }).first();
    const todayRows = async () => {
      await p.locator('.o_searchview_facet', { hasText: 'Today' }).first().waitFor({ timeout: 15000 });
      await listArea.waitFor({ timeout: 15000 });
      await p.waitForTimeout(1500);
      return p.locator('tr.o_data_row').count();
    };
    const before = await todayRows();
    await kit.note(`Today's contacts list holds ${before} ${before === 1 ? 'contact' : 'contacts'}`, `Danh sách liên hệ hôm nay có ${before} liên hệ`);
    await kit.step(next(), 'New Contact, leave everything blank and press Next', 'Liên hệ mới, để trống tất cả và nhấn Tiếp');
    await kit.click(p.getByRole('button', { name: 'New Contact' }), 2000);
    await kit.click(p.locator('.nc-footer button', { hasText: 'Next' }), 1500);
    const dlg = p.locator('.modal-content').filter({ has: p.locator('.rfd-list') }).first();
    await kit.proof(dlg, 'Blank form refused: name and phone or email are required',
      (t) => /Contact Name/.test(t) && /Phone Number or Email Address/.test(t));
    await kit.click(dlg.getByRole('button', { name: 'Got it' }), 1000);
    await kit.proof(p.locator('.nc-stepper'), 'Nothing saved: still on step 1, no contact created', async () =>
      /Contact Info/.test(await p.locator('.nc-step.active').innerText()) && !(await p.locator('.nc-success-banner').count()));

    await kit.step(next(), 'Cancel the empty form: the list is unchanged', 'Hủy biểu mẫu trống: danh sách không đổi');
    await kit.click(p.locator('.nc-footer button', { hasText: 'Cancel' }), 2500);
    const after = await todayRows();
    await kit.proof([p.locator('.o_searchview').filter({ visible: true }).first(), listArea], 'Today’s contacts unchanged: nothing saved', () => after === before);
    await kit.step(next(), `A caller gives a name and phone: ${name}, ${phone}`, `Người gọi cho tên và số điện thoại: ${name}, ${phone}`);
    await kit.click(p.getByRole('button', { name: 'New Contact' }), 2000);
    await kit.type(p.getByPlaceholder('Full name'), name);
    await kit.type(p.getByPlaceholder('Phone number'), phone, 800);
    await kit.click(p.locator('.nc-footer button', { hasText: 'Next' }), 1800);
    await kit.click(p.locator('.nc-radio-btn, button').filter({ hasText: /^\s*Client \(Self\)\s*$/ }).first(), 700);
    await kit.step(next(), 'Create Contact', 'Tạo liên hệ');
    await kit.click(p.locator('.nc-footer button', { hasText: 'Create Contact' }), 2500);
    await kit.proof(p.locator('.nc-success-banner'), 'Valid details saved: contact created', name);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Open Record\s*$/ }).first(), 4000);
    await c.hero(p).waitFor({ timeout: 15000 });
    const code = (await p.locator('.ws-hero .ws-chip--code').first().innerText().catch(() => '')).trim();
    const id = Number((p.url().match(/\/(\d+)(?:\?.*)?$/) || [])[1]) || null;
    kit.records['Contact'] = `${name} (${code}, ${phone})`;
    a.save({ fm01: { name, phone, code, id } });
    await kit.proof(c.hero(p), 'Saved record keeps the name and phone', (t) => t.includes(name) && t.includes(phone));
    if (STOP === 'wizard') return;

    // ------------------------------------------------------------ Owner: a configured requirement
    await kit.switchUser(next(), owner, false);
    await kit.step(next(), 'Settings › Master data › Field Requirements › Sales & CRM › Contacts', 'Cài đặt › Dữ liệu gốc › Trường bắt buộc › Bán hàng & CRM › Liên hệ');
    await a.area(kit, 'Settings');
    await kit.click(c.sidebar(p, 'Master Data'), 3500);
    await kit.click(p.getByText('Field Requirements', { exact: true }).filter({ visible: true }).first(), 3500);
    await kit.click(p.getByText('Sales & CRM', { exact: true }).filter({ visible: true }).first(), 2500);
    await kit.click(p.getByText('Contacts', { exact: true }).filter({ visible: true }).last(), 3500);
    const activeCount = p.getByText(/\d+\s*\/\s*\d+\s*Active/).filter({ visible: true }).first();
    await kit.proof(activeCount, 'No requirement configured on Contacts yet', /^\s*0\s*\//);

    await kit.step(next(), 'Make Email required for the CRM job: find Email, switch it on, untick Global, pick CRM', 'Đặt Email bắt buộc cho công việc CRM: tìm Email, bật, bỏ Toàn cục, chọn CRM');
    await kit.type(p.getByPlaceholder('Search fields...'), 'Email', 1500);
    const row = p.locator('tr').filter({ has: p.locator('.fr-field-name', { hasText: /^email_from$/ }) }).first();
    await kit.click(row.locator('td.fr-col-active label.fr-toggle'), 2000);
    await kit.click(row.locator('td.fr-col-global label.fr-toggle'), 2000);
    await kit.click(row.locator('.fr-role-chip').filter({ hasText: /^\s*CRM\s*$/ }).first(), 2500);
    await kit.proof(row, 'Email required for the CRM job', async (t) =>
      (await row.locator('td.fr-col-active input').isChecked()) && !(await row.locator('td.fr-col-global input').isChecked())
      && (await row.locator('.fr-role-chip.selected').allInnerTexts()).map((x) => x.trim()).join(',') === 'CRM');
    if (STOP === 'rule') return;

    // ------------------------------------------------------------ CRM user: the form enforces it
    await kit.switchUser(next(), crm, false);
    await kit.step(next(), `CRM › Contacts › open ${name}`, `CRM › Liên hệ › mở ${name}`);
    await kit.click(c.sidebar(p, 'CONTACTS'), 3000);
    await a.listSearch(kit, name);
    await kit.click(c.listRow(p, name).locator('td').nth(1), 4000);
    await c.hero(p).waitFor({ timeout: 15000 });
    const emailField = c.field(p, 'email_from');
    const emailLabel = p.locator('.o_form_label, label').filter({ hasText: /^\s*Email\s*\*?\s*$/ }).filter({ visible: true }).first();
    await kit.proof([emailLabel, emailField], 'Email is marked required on the contact', async () =>
      (await emailLabel.evaluate((e) => /required|fr-/.test(e.className) || getComputedStyle(e).color.replace(/\s/g, '') !== getComputedStyle(document.body).color.replace(/\s/g, '')))
      && !(await kit.fieldValues(['email_from'])).email_from);

    await kit.step(next(), 'Add a follow-up note and Save, still without an email', 'Thêm ghi chú theo dõi và Lưu, vẫn chưa có email');
    await kit.type(c.field(p, 'follow_up_notes').locator('textarea, input').first(), 'Caller will send an email address later (fictional UAT).', 800);
    await kit.click(c.saveBtn(p), 2000);
    const missing = p.locator('.modal-content').filter({ has: p.locator('.fr-missing-dialog') }).first();
    await kit.proof(missing, 'Save refused: Email must be filled', (t) => /Email/.test(t) && /must be filled/i.test(t));
    await kit.click(missing.locator('.modal-footer button, footer button').first(), 1200);

    await kit.step(next(), `Enter the email ${email} and Save`, `Nhập email ${email} và Lưu`);
    await kit.type(emailField.locator('input').first(), email, 500);
    await p.keyboard.press('Tab');           // commit the value before saving
    await kit.hold(1200);
    await kit.click(c.saveBtn(p), 3500);
    await c.saveBtn(p).waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
    await kit.proof(emailField, 'With the email the contact saves', async () =>
      (await kit.fieldValues(['email_from'])).email_from === email && !(await c.saveBtn(p).isVisible().catch(() => false))
      && !(await p.locator('.modal-content').filter({ has: p.locator('.fr-missing-dialog') }).count()));

    await kit.step(next(), 'Reload the contact: the values are kept', 'Tải lại liên hệ: dữ liệu vẫn được giữ');
    await p.reload();
    await c.hero(p).waitFor({ timeout: 15000 });
    await kit.hold(1500);
    await kit.proof([c.field(p, 'email_from'), c.field(p, 'follow_up_notes')], 'Reopened: email and note kept', async () => {
      const v = await kit.fieldValues(['email_from', 'follow_up_notes']);
      return v.email_from === email && /send an email address later/.test(v.follow_up_notes);
    });
    kit.records['Contact'] = `${name} (${code}, ${phone}, ${email})`;
    if (STOP === 'enforce') return;

    // ------------------------------------------------------------ Owner removes the test requirement
    await kit.switchUser(next(), owner, false);
    await kit.step(next(), 'Owner removes the test requirement again (Field Requirements › Contacts › Email › bin)', 'Chủ sở hữu gỡ yêu cầu thử nghiệm (Trường bắt buộc › Liên hệ › Email › thùng rác)');
    await a.area(kit, 'Settings');
    await kit.click(c.sidebar(p, 'Master Data'), 3500);
    await kit.click(p.getByText('Field Requirements', { exact: true }).filter({ visible: true }).first(), 3500);
    await kit.click(p.getByText('Sales & CRM', { exact: true }).filter({ visible: true }).first(), 2500);
    await kit.click(p.getByText('Contacts', { exact: true }).filter({ visible: true }).last(), 3500);
    await kit.type(p.getByPlaceholder('Search fields...'), 'Email', 1500);
    await kit.click(row.locator('.fr-delete-btn'), 2500);
    await kit.proof(activeCount, 'Requirement removed again: Contacts back to none active', /^\s*0\s*\//);
  },
};
