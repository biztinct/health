// FM-02 New lookup value: the Owner adds a Contact Reason in Settings › Master data › Contact
// Reasons; the CRM user picks it on a new contact; it is kept after reopening and the old
// reasons are still offered.
const c = require('./common');
const a = require('./adm_common');
const owner = a.users.owner;
const crm = a.users.crm;
const now = a.vnNow();
const reason = `UAT 0511 Acceptance enquiry ${now.hhmm}`;
const rcode = `UAT${now.hhmm}`;
const phone = c.phone();
const name = `UAT-VID FM02 Caller ${now.hhmm}`;
const OLD = ['General Healthcare Inquiry', 'Home Visit Request', 'Clinic Appointment Request', 'Service Pricing Inquiry'];
const STOP = process.env.FM02_STOP || '';

module.exports = {
  meta: {
    id: 'FM-02', title: 'New contact reason added, chosen and kept', short: 'New lookup value',
    title_vi: 'Thêm lý do liên hệ mới, chọn và được lưu giữ',
    criterion: 'An authorised user can add a new lookup value to a supported selected table, then choose that value in the relevant business form. The new choice must remain available and be retained on the saved record without replacing existing lookup values.',
    data: `New Contact Reason “${reason}” (code ${rcode}) added by ${owner.login}; fictional contact “${name}”, ${phone}, created by ${crm.login}`,
    expected: 'Lookup can be created, selected and retained.',
    ...owner,
  },
  proofVi: {
    'Contact Reasons before: the existing list': 'Lý do liên hệ trước đó: danh sách hiện có',
    'New reason saved, the old reasons still listed': 'Đã lưu lý do mới, các lý do cũ vẫn còn',
    'New reason chosen; the old reasons are still offered': 'Đã chọn lý do mới; các lý do cũ vẫn có trong danh sách',
    'Contact created with the new reason': 'Đã tạo liên hệ với lý do mới',
    'Saved contact shows the new reason': 'Liên hệ đã lưu hiển thị lý do mới',
    'Reloaded: the reason is kept': 'Tải lại: lý do vẫn được giữ',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    await kit.login();

    await kit.step(next(), 'Settings › Master data › Contact Reasons', 'Cài đặt › Dữ liệu gốc › Lý do liên hệ');
    await a.area(kit, 'Settings');
    await kit.click(c.sidebar(p, 'Master Data'), 3500);
    await kit.click(p.getByText('Contact Reasons', { exact: true }).filter({ visible: true }).first(), 3500);
    const rows = p.locator('tr.o_data_row');
    await rows.first().waitFor({ timeout: 15000 });
    const before = await rows.count();
    const table = rows.first().locator('xpath=ancestor::table[1]');
    await kit.proof(rows.filter({ hasText: OLD[0] }).first(), 'Contact Reasons before: the existing list', async () => {
      const t = (await rows.allInnerTexts()).join(' | ');
      return OLD.every((x) => t.includes(x)) && !t.includes(reason);
    });

    await kit.step(next(), `New: code ${rcode}, name “${reason}”, then Save`, `Mới: mã ${rcode}, tên “${reason}”, rồi Lưu`);
    await kit.click(p.locator('button').filter({ hasText: /^\s*New\s*$/ }).filter({ visible: true }).first(), 2500);
    const edit = p.locator('tr.o_data_row.o_selected_row').first();
    await edit.waitFor({ timeout: 10000 });
    await kit.type(edit.locator('td[name=code] input').first(), rcode, 400);
    await kit.type(edit.locator('td[name=name] input').first(), reason, 600);
    await kit.click(p.locator('.o_list_button_save').filter({ visible: true }).first(), 3000);
    await p.locator('.o_selected_row').first().waitFor({ state: 'detached', timeout: 10000 }).catch(() => {});
    const newRow = rows.filter({ hasText: reason }).first();
    await newRow.waitFor({ timeout: 10000 });
    kit.records['Contact Reason'] = `${reason} (${rcode})`;
    a.save({ fm02: { reason, rcode } });
    const pager = p.locator('.o_pager_counter, .o_pager').filter({ visible: true }).first();
    await kit.proof([newRow, pager], 'New reason saved, the old reasons still listed', async () =>
      (await rows.count()) === before + 1 && (await Promise.all(OLD.map((x) => rows.filter({ hasText: x }).count()))).every((k) => k === 1)
      && !(await p.locator('.o_list_button_save').filter({ visible: true }).count()));
    if (STOP === 'lookup') return;

    // ------------------------------------------------------------ CRM user picks it on a contact
    await kit.switchUser(next(), crm, false);
    await kit.step(next(), `CRM › Contacts › New Contact: ${name}, ${phone}`, `CRM › Liên hệ › Liên hệ mới: ${name}, ${phone}`);
    await kit.click(c.sidebar(p, 'CONTACTS'), 3000);
    await kit.click(p.getByRole('button', { name: 'New Contact' }), 2000);
    await kit.type(p.getByPlaceholder('Full name'), name);
    await kit.type(p.getByPlaceholder('Phone number'), phone, 800);
    await kit.click(p.locator('.nc-footer button', { hasText: 'Next' }), 1800);
    await kit.click(p.locator('.nc-radio-btn, button').filter({ hasText: /^\s*Client \(Self\)\s*$/ }).first(), 700);

    await kit.step(next(), `Contact Reason: choose “${reason}”`, `Lý do liên hệ: chọn “${reason}”`);
    const sel = p.locator('.nc-field').filter({ has: p.locator('.nc-label', { hasText: /Contact Reason/i }) }).locator('select').first();
    await sel.scrollIntoViewIfNeeded();
    await kit.moveTo(sel);
    await p.mouse.down(); await p.mouse.up();
    await sel.selectOption({ label: reason });
    await kit.hold(1200);
    await kit.proof(sel, 'New reason chosen; the old reasons are still offered', async () => {
      const o = (await sel.locator('option').allInnerTexts()).map((x) => x.trim());
      const chosen = (await sel.locator('option:checked').innerText()).trim();
      return chosen === reason && OLD.every((x) => o.includes(x));
    });

    await kit.step(next(), 'Create Contact and open it', 'Tạo liên hệ và mở ra');
    await kit.click(p.locator('.nc-footer button', { hasText: 'Create Contact' }), 2500);
    await kit.proof(p.locator('.nc-success-banner'), 'Contact created with the new reason', name);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Open Record\s*$/ }).first(), 4000);
    await c.hero(p).waitFor({ timeout: 15000 });
    const code = (await p.locator('.ws-hero .ws-chip--code').first().innerText().catch(() => '')).trim();
    kit.records['Contact'] = `${name} (${code}, ${phone})`;
    await kit.click(p.locator('a.nav-link', { hasText: 'Client Details' }).first(), 1800);
    await kit.proof(c.field(p, 'reason_for_contact_id'), 'Saved contact shows the new reason', async () =>
      (await kit.fieldValues(['reason_for_contact_id'])).reason_for_contact_id === reason);

    await kit.step(next(), 'Reload the contact', 'Tải lại liên hệ');
    await p.reload();
    await c.hero(p).waitFor({ timeout: 15000 });
    await kit.click(p.locator('a.nav-link', { hasText: 'Client Details' }).first(), 1800);
    await kit.proof(c.field(p, 'reason_for_contact_id'), 'Reloaded: the reason is kept', async () =>
      (await c.hero(p).innerText()).includes(name) && (await kit.fieldValues(['reason_for_contact_id'])).reason_for_contact_id === reason);
  },
};
