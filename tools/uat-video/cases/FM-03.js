// FM-03 Add a new field to a table, shown on the Client form: the Owner opens Form Studio
// from a client, drags a Dropdown into the Overview "Care" card ("Preferred visit time":
// Morning / Afternoon / Evening, with Vietnamese names) and publishes it; the Hanoi
// Operations Manager then fills it on a client, saves, and it is kept after a reload; another
// client has the same (empty) field. Clean-up on camera: the Owner deletes the example field
// with a typed DELETE, so the live Client form is as before (the owner's FM-01 / UM-01 rule:
// test changes are undone).
//
// Learned while scouting (6 Nov 2026):
// - Client record: Operations › Clients › row › top bar "Studio" (button, right of the
//   breadcrumb). Editor URL …/action-biz_form_studio.studio?fs_model=res.partner&fs_view=5026.
// - Editor: palette tiles `.fs-tile` (text "Dropdown"), cards `.fs-card` with an `h3` title;
//   open cards (Personal, Contact, Care, Identity, Commission) end in `.fs-drop`
//   "Drop a field here". A dropped type opens the NEW FIELD form on the right; the field is
//   created only by "Add field" (so a drop alone changes nothing).
// - Publish sheet: "Publish this layout?" › "Publish for everyone"; publishing returns to the
//   record. Delete: select the chip › "Delete this field…" › type DELETE › "Delete field".
// FM03_STOP=form stops before "Add field" (practice without creating anything).
const c = require('./common');
const a = require('./adm_common');
const owner = a.users.owner;
const omhn = a.users.omhn;
const STOP = process.env.FM03_STOP || '';

const CLIENT = { name: 'Nguyễn Văn An', code: '01_0000126' };
const OTHER = { name: 'Trần Thị Bình' };
const F = { label: 'Preferred visit time', vi: 'Khung giờ thăm ưu tiên' };
const OPTS = [['Morning', 'Buổi sáng'], ['Afternoon', 'Buổi chiều'], ['Evening', 'Buổi tối']];
const PICK = 'Afternoon';

module.exports = {
  meta: {
    id: 'FM-03', title: 'New field added to the Client form and used', short: 'Add a new field',
    title_vi: 'Thêm trường mới vào biểu mẫu Khách hàng và sử dụng',
    criterion: 'An authorized administrator can add an agreed new field to an agreed table, place it on the screen, and staff can enter and keep a value in it.',
    data: `Form Studio on the Client form as ${owner.login}: new dropdown “${F.label}” (${OPTS.map((o) => o[0]).join(' / ')}) in the Care card. Used by ${omhn.login} on ${CLIENT.name} (${CLIENT.code}); also seen on ${OTHER.name}. The example field is deleted again at the end.`,
    expected: 'An admin can add a new field and use it.',
    ...owner,
  },
  proofVi: {
    'Before: the Care card has no “Preferred visit time”': 'Trước: thẻ Chăm sóc chưa có “Khung giờ thăm ưu tiên”',
    'Form Studio is open on the Client form': 'Form Studio đang mở trên biểu mẫu Khách hàng',
    'New dropdown with three options, English and Vietnamese': 'Danh sách chọn mới với ba lựa chọn, tiếng Anh và tiếng Việt',
    'Field added to the Care card (custom)': 'Trường đã được thêm vào thẻ Chăm sóc (tùy chỉnh)',
    'Publish sheet lists the new field': 'Hộp xuất bản liệt kê trường mới',
    'The client form now shows “Preferred visit time”': 'Biểu mẫu khách hàng giờ hiển thị “Khung giờ thăm ưu tiên”',
    'Operations Manager sees the new field, still empty': 'Quản lý vận hành thấy trường mới, còn trống',
    'Afternoon chosen and saved': 'Đã chọn Buổi chiều và lưu',
    'After a reload the value is kept': 'Sau khi tải lại giá trị vẫn được giữ',
    'Another client has the same field, empty': 'Khách hàng khác cũng có trường này, còn trống',
    'Delete check: the field has a value on 1 record': 'Kiểm tra xóa: trường có giá trị trên 1 hồ sơ',
    'Clean-up done: the example field is gone from the form': 'Đã dọn dẹp: trường ví dụ không còn trên biểu mẫu',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    const careCard = () => p.locator('.vu-detail-card, .ws-card').filter({ has: p.locator('text=/^\\s*Care\\s*$/i') }).filter({ visible: true }).first();
    const fsField = () => p.locator('.o_field_widget[name^="x_fs_"]').filter({ visible: true }).first();
    const fsLabel = () => p.locator('label, .o_form_label').filter({ hasText: new RegExp(`^\\s*${F.label}\\s*[*?]?\\s*$`) }).filter({ visible: true }).first();

    const openClient = async (who) => {
      await kit.area('Operations');
      await kit.click(c.sidebar(p, 'Clients'), 3000);
      await a.listSearch(kit, who.name);
      const row = p.locator('tr.o_data_row', { hasText: who.code || who.name }).first();
      await row.waitFor({ timeout: 15000 });
      await kit.click(row.locator('td[name=name]').first(), 4500);
      await c.hero(p).waitFor({ timeout: 20000 });
      await kit.hold(1200);
    };
    const openStudio = async () => {
      await kit.click(p.getByRole('button', { name: /^\s*Studio\s*$/ }).filter({ visible: true }).first(), 5000);
      await p.locator('.fs-studio .fs-card').first().waitFor({ timeout: 20000 });
      await kit.hold(1200);
    };
    const studioCard = (title) => p.locator('.fs-card').filter({ has: p.locator('h3', { hasText: new RegExp(`^\\s*${title}\\s*$`) }) }).first();

    await kit.login();

    // ------------------------------------------------------------ Owner adds the field
    await kit.step(next(), `Operations › Clients › open ${CLIENT.name} (${CLIENT.code})`, `Vận hành › Khách hàng › mở ${CLIENT.name} (${CLIENT.code})`);
    await openClient(CLIENT);
    await kit.proof(careCard(), 'Before: the Care card has no “Preferred visit time”', (t) => /Care/i.test(t) && !t.includes(F.label));

    await kit.step(next(), 'Press Studio (top right) to change the Client form', 'Nhấn Studio (góc trên bên phải) để chỉnh biểu mẫu Khách hàng');
    await openStudio();
    await kit.proof(p.locator('.fs-bar'), 'Form Studio is open on the Client form', (t) => /Form Studio/.test(t) && /Client/.test(t));

    await kit.step(next(), 'Drag “Dropdown” into the Care card', 'Kéo “Danh sách chọn” vào thẻ Chăm sóc');
    const care = studioCard('Care');
    const drop = care.locator('.fs-drop');
    await drop.scrollIntoViewIfNeeded();
    const tile = p.locator('.fs-tile').filter({ hasText: /^\s*Dropdown/ }).first();
    await kit.moveTo(tile);
    await tile.dragTo(drop);
    await kit.hold(1500);
    const props = p.locator('.fs-props');
    await props.locator('.fs-eyebrow', { hasText: 'New field' }).waitFor({ timeout: 10000 });

    await kit.step(next(), `Name it “${F.label}” (Vietnamese “${F.vi}”) with three options`, `Đặt tên “${F.label}” (tiếng Việt “${F.vi}”) với ba lựa chọn`);
    const lab = (t) => props.locator('label.fs-lab').filter({ hasText: new RegExp(`^\\s*${t}`) }).locator('input, textarea').first();
    await kit.type(lab('Label'), F.label, 400);
    await kit.type(lab('Vietnamese label'), F.vi, 400);
    // The form starts with one empty option: fill it, then add the others.
    for (const [i, [en, vi]] of OPTS.entries()) {
      const blocks = props.locator('.fs-optblock');
      if (i >= await blocks.count()) {
        await kit.type(props.getByPlaceholder('Add an option'), en, 200);
        await p.keyboard.press('Enter');
        await kit.hold(400);
      } else {
        await kit.type(blocks.nth(i).locator('.fs-option input').first(), en, 200);
      }
      await kit.type(props.locator('.fs-optblock').nth(i).locator('.fs-input--vi'), vi, 300);
    }
    await props.locator('.bzk-segbtn', { hasText: 'Everyone' }).scrollIntoViewIfNeeded();
    await kit.proof(props.locator('.fs-options'), 'New dropdown with three options, English and Vietnamese', async () => {
      const v = await props.locator('.fs-optblock input').evaluateAll((els) => els.map((e) => e.value));
      return JSON.stringify(v) === JSON.stringify(OPTS.flat());
    });
    if (STOP === 'form') return;

    await kit.step(next(), 'Who sees it: Everyone. Press Add field', 'Ai được xem: Mọi người. Nhấn Thêm trường');
    await kit.click(props.locator('.bzk-segbtn', { hasText: 'Everyone' }), 600);
    await kit.click(props.locator('button', { hasText: 'Add field' }), 4000);
    const chip = care.locator('.fs-chip, [class*=fs-chip]').filter({ hasText: F.label }).first();
    await chip.waitFor({ timeout: 15000 });
    await kit.proof(care, 'Field added to the Care card (custom)', (t) => t.includes(F.label) && /custom/i.test(t));

    await kit.step(next(), 'Publish › Publish for everyone', 'Xuất bản › Xuất bản cho mọi người');
    await kit.click(p.locator('.fs-bar button', { hasText: 'Publish' }), 1800);
    const sheet = p.locator('.fs-sheet').filter({ hasText: 'Publish this layout?' }).first();
    await kit.proof(sheet, 'Publish sheet lists the new field', (t) => t.includes(`Add ${F.label}`));
    await kit.click(sheet.locator('button', { hasText: 'Publish for everyone' }), 6000);
    await c.hero(p).waitFor({ timeout: 20000 });

    await kit.step(next(), 'Back on the client: reload the page', 'Quay lại khách hàng: tải lại trang');
    await p.reload();
    await c.hero(p).waitFor({ timeout: 20000 });
    await kit.hold(2000);
    await kit.proof([fsLabel(), fsField()], 'The client form now shows “Preferred visit time”', async () => (await fsLabel().count()) > 0 && (await fsField().count()) > 0);
    if (STOP === 'published') return;

    // ------------------------------------------------------------ The Operations Manager uses it
    await kit.switchUser(next(), omhn, false);
    await kit.step(next(), `Operations › Clients › ${CLIENT.name}`, `Vận hành › Khách hàng › ${CLIENT.name}`);
    await openClient(CLIENT);
    await fsField().scrollIntoViewIfNeeded();
    await kit.proof([fsLabel(), fsField()], 'Operations Manager sees the new field, still empty', async () => !(await fsField().innerText()).trim() || !(await fsField().locator('input').inputValue().catch(() => '')));

    await kit.step(next(), `Choose “${PICK}” and Save`, `Chọn “Buổi chiều” và Lưu`);
    await kit.select(fsField(), PICK);
    await kit.click(c.saveBtn(p), 3500);
    await c.saveBtn(p).waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
    const shows = async (v) => {
      const txt = (await fsField().innerText()).trim();
      const inp = await fsField().locator('input, select').first().inputValue().catch(() => '');
      return txt.includes(v) || inp.includes(v);
    };
    await kit.proof([fsLabel(), fsField()], 'Afternoon chosen and saved', async () => (await shows(PICK)) && !(await c.saveBtn(p).isVisible().catch(() => false)));

    await kit.step(next(), 'Reload the client: the value is kept', 'Tải lại khách hàng: giá trị vẫn được giữ');
    await p.reload();
    await c.hero(p).waitFor({ timeout: 20000 });
    await kit.hold(2000);
    await fsField().scrollIntoViewIfNeeded();
    await kit.proof([fsLabel(), fsField()], 'After a reload the value is kept', () => shows(PICK));
    kit.records['Value saved'] = `${CLIENT.name} (${CLIENT.code}): ${F.label} = ${PICK}`;

    await kit.step(next(), `Another client, ${OTHER.name}, has the same field`, `Khách hàng khác, ${OTHER.name}, cũng có trường này`);
    await openClient(OTHER);
    await fsField().scrollIntoViewIfNeeded();
    await kit.proof([fsLabel(), fsField()], 'Another client has the same field, empty', async () => !(await shows(PICK)));

    // ------------------------------------------------------------ Clean-up: the Owner deletes the example
    await kit.switchUser(next(), owner, false);
    await kit.step(next(), 'Clean-up: the Owner deletes the example field (Studio › field › Delete)', 'Dọn dẹp: Chủ sở hữu xóa trường ví dụ (Studio › trường › Xóa)');
    await openClient(CLIENT);
    await openStudio();
    const chip2 = studioCard('Care').locator('[class*=fs-chip]').filter({ hasText: F.label }).first();
    await chip2.scrollIntoViewIfNeeded();
    await kit.click(chip2, 1500);
    await kit.click(p.locator('.fs-props button', { hasText: 'Delete this field' }), 2500);
    const del = p.locator('.fs-sheet').filter({ hasText: 'Type DELETE' }).first();
    await del.waitFor({ timeout: 15000 });
    await kit.proof(del.locator('.fs-sheet__lead'), 'Delete check: the field has a value on 1 record', /value on 1 record/);
    await kit.type(del.locator('input'), 'DELETE', 600);
    await kit.click(del.locator('button', { hasText: 'Delete field' }), 4000);
    // The delete republishes the form at once; the editor then offers "1 change" (the now
    // empty Care placement). Publish it too: leaving with Back keeps it as a draft and the
    // record re-reads the deleted field once (practice run, 6 Nov).
    const pubBtn = p.locator('.fs-bar button', { hasText: 'Publish' });
    await pubBtn.waitFor({ state: 'visible' });
    for (let i = 0; i < 20 && !(await pubBtn.isEnabled()); i++) await kit.hold(500);
    if (await pubBtn.isEnabled()) {
      await kit.click(pubBtn, 1800);
      await kit.click(p.locator('.fs-sheet button', { hasText: 'Publish for everyone' }), 6000);
    } else {
      await kit.click(p.locator('.fs-bar button[aria-label="Back to the record"]'), 4000);
    }
    await c.hero(p).waitFor({ timeout: 20000 });
    await p.reload();
    await c.hero(p).waitFor({ timeout: 20000 });
    await kit.hold(2000);
    await kit.proof(careCard(), 'Clean-up done: the example field is gone from the form', async (t) => !t.includes(F.label) && !(await fsField().count()));
    kit.records['New field'] = `${F.label} / ${F.vi} (dropdown: ${OPTS.map((o) => o[0]).join(', ')}), Client form › Care card — deleted again at the end`;
  },
};
