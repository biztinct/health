// UM-01 Enter a new user: the Owner adds a fictional nurse (job, area, base, Vietnam time zone,
// first password) from Settings › People › Access & roles › Add a person; the new person signs
// in with that login and password and sees their own name and their job's screens; the Owner
// then switches the account off again (owner decision: the test login does not stay usable).
// The password is generated here, written only to accounts.local.json, never shown or captioned.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const c = require('./common');
const a = require('./adm_common');
const owner = a.users.owner;
const now = a.vnNow();
const login = `uat_video_${now.hhmm}`;
const fullName = `UAT Video User 0511-${now.hhmm}`;
const STOP = process.env.UM01_STOP || '';

// A fresh first password per run, stored only in the git-ignored accounts file.
function newPassword() {
  const pw = `Uv-${crypto.randomBytes(9).toString('base64').replace(/[^A-Za-z0-9]/g, 'x')}-${now.hhmm}`;
  const file = path.join(__dirname, '..', 'accounts.local.json');
  const acc = JSON.parse(fs.readFileSync(file, 'utf8'));
  acc[login] = pw;
  fs.writeFileSync(file, JSON.stringify(acc, null, 1));
  return pw;
}

module.exports = {
  meta: {
    id: 'UM-01', title: 'New user added and signs in', short: 'New user',
    title_vi: 'Thêm người dùng mới và đăng nhập',
    criterion: 'An authorised administrator can enter a new user with the intended identity, role and catchment. The account must authenticate using its login/password and keep the correct staff record and time zone.',
    data: `Fictional nurse “${fullName}”, login ${login}, job Nurse, area Hà Nội, based at HN_PK_PKGDVU, time zone Asia/Ho_Chi_Minh, a temporary first password; switched off by the Owner at the end`,
    expected: 'New account can authenticate with intended identity.',
    ...owner,
  },
  proofVi: {
    'Owner opens Add a person': 'Chủ sở hữu mở Thêm người',
    'Details entered: name, login, temporary password, Vietnam time, Nurse, Hà Nội': 'Đã nhập: tên, tên đăng nhập, mật khẩu tạm, giờ Việt Nam, Điều dưỡng, Hà Nội',
    'Added: can sign in and holds Nurse': 'Đã thêm: có thể đăng nhập và giữ vai trò Điều dưỡng',
    'People list: job Nurse, area Hà Nội': 'Danh sách nhân sự: công việc Điều dưỡng, khu vực Hà Nội',
    'User record: Vietnam time zone, linked staff record': 'Hồ sơ người dùng: múi giờ Việt Nam, có hồ sơ nhân viên liên kết',
    'Signed in as the new user: nurse screens, area Hà Nội': 'Đã đăng nhập bằng người dùng mới: màn hình điều dưỡng, khu vực Hà Nội',
    'My Preferences: the new user’s own name': 'Tùy chọn của tôi: đúng tên của người dùng mới',
    'My Preferences: Vietnam time zone': 'Tùy chọn của tôi: múi giờ Việt Nam',
    'Switched off: can no longer sign in': 'Đã tắt: không thể đăng nhập nữa',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    const password = newPassword();
    const newUser = { login, password, role: 'New user (Nurse, Hanoi)', role_vi: 'Người dùng mới (Điều dưỡng Hà Nội)' };
    kit.records['New user'] = `${fullName} (login ${login})`;
    a.save({ um01: { login, name: fullName } });
    await kit.login();

    await kit.step(next(), 'Settings › People › Access & roles › People › Add a person', 'Cài đặt › Nhân sự › Truy cập & vai trò › Nhân sự › Thêm người');
    await a.area(kit, 'Settings');
    await kit.click(c.sidebar(p, 'People'), 3500);
    await kit.click(p.locator('button, a').filter({ hasText: /^\s*Access & roles\s*$/ }).filter({ visible: true }).first(), 4500);
    await kit.click(p.locator('button, a, [role=tab], .nav-link, span').filter({ hasText: /^\s*People\s*$/ }).filter({ visible: true }).last(), 3000);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Add a person\s*$/ }).filter({ visible: true }).first(), 3500);
    const dlg = p.locator('.modal-content').filter({ has: p.locator('.o_field_widget[name=role_id]') }).first();
    await kit.proof(dlg, 'Owner opens Add a person', /HOW THEY SIGN IN/i);

    await kit.step(next(), `Name ${fullName}, login ${login}, a temporary first password`, `Tên ${fullName}, tên đăng nhập ${login}, một mật khẩu tạm`);
    await kit.type(dlg.locator('.o_field_widget[name=name] input'), fullName, 400);
    await kit.type(dlg.locator('.o_field_widget[name=login] input'), login, 400);
    await kit.type(dlg.locator('.o_field_widget[name=password] input'), password, 400);

    await kit.step(next(), 'Language English, time zone Asia/Ho_Chi_Minh (Vietnam)', 'Ngôn ngữ tiếng Anh, múi giờ Asia/Ho_Chi_Minh (Việt Nam)');
    const tz = dlg.locator('.o_field_widget[name=tz]');
    if (!(await tz.locator('select').inputValue().catch(() => '')).includes('Ho_Chi_Minh')) await kit.select(tz, 'Asia/Ho_Chi_Minh');
    await kit.moveTo(tz);
    await kit.hold(800);

    await kit.step(next(), 'Job: Nurse. Area: Hà Nội. Based at HN_PK_PKGDVU', 'Công việc: Điều dưỡng. Khu vực: Hà Nội. Làm việc tại HN_PK_PKGDVU');
    const m2o = async (fname, text) => {
      const inp = dlg.locator(`.o_field_widget[name=${fname}] input`).first();
      await kit.type(inp, text, 1200);
      await kit.click(p.locator('.o-autocomplete--dropdown-menu .dropdown-item, .o-autocomplete--dropdown-item').filter({ hasText: new RegExp(`^\\s*${text}\\s*$`) }).filter({ visible: true }).first(), 1200);
    };
    await m2o('role_id', 'Nurse');
    await m2o('catchment_province_id', 'Hà Nội');
    await m2o('healthcare_facility_id', 'HN_PK_PKGDVU');
    await kit.proof(dlg, 'Details entered: name, login, temporary password, Vietnam time, Nurse, Hà Nội', async () => {
      const v = await kit.fieldValues(['name', 'login', 'password', 'tz', 'role_id', 'catchment_province_id', 'healthcare_facility_id'], dlg);
      const pwType = await dlg.locator('.o_field_widget[name=password] input').getAttribute('type');
      return v.name === fullName && v.login === login && v.password.length > 0 && pwType === 'password'
        && /Ho_Chi_Minh/.test(v.tz) && v.role_id === 'Nurse' && v.catchment_province_id === 'Hà Nội' && v.healthcare_facility_id === 'HN_PK_PKGDVU';
    });

    await kit.step(next(), 'Add them', 'Thêm');
    await kit.click(dlg.locator('button').filter({ hasText: /^\s*Add them\s*$/ }), 1500);
    const toast = p.locator('.o_notification').filter({ hasText: login }).first();
    await kit.proof(toast, 'Added: can sign in and holds Nurse', (t) => t.includes(fullName) && t.includes(login) && /Nurse/.test(t));
    if (STOP === 'add') return;

    await kit.step(next(), `Users & Roles: find ${fullName}`, `Người dùng & Vai trò: tìm ${fullName}`);
    await kit.click(c.sidebar(p, 'People'), 3500);
    await a.listSearch(kit, fullName);
    const row = p.locator('tr.o_data_row', { hasText: login }).first();
    await row.waitFor({ timeout: 15000 });
    await kit.proof(row, 'People list: job Nurse, area Hà Nội', (t) => t.includes(fullName) && t.includes('Nurse') && t.includes('Hà Nội'));
    await kit.click(row.locator('td').nth(1), 3500);
    const form = p.locator('.o_form_view').first();
    await kit.proof([c.field(p, 'tz'), p.locator('button, a').filter({ hasText: /^\s*Staff record\s*$/ }).filter({ visible: true }).first()],
      'User record: Vietnam time zone, linked staff record', async () => /Ho_Chi_Minh/.test((await kit.fieldValues(['tz'])).tz)
        && (await form.innerText()).includes(fullName));
    const userId = Number((p.url().match(/\/(\d+)(?:\?.*)?$/) || [])[1]) || null;
    a.save({ um01: { login, name: fullName, id: userId } });

    // ------------------------------------------------------------ the new person signs in
    await kit.switchUser(next(), newUser, false);
    await kit.proof([a.catchment(p), p.locator('button.vu-tab').first().locator('xpath=..')], 'Signed in as the new user: nurse screens, area Hà Nội', async () => {
      const t = (await p.locator('button.vu-tab').filter({ visible: true }).allInnerTexts()).map((x) => x.trim().toLowerCase());
      return ['bookings', 'clients', 'schedule'].every((x) => t.includes(x)) && (await a.catchment(p).innerText()).includes('Hà Nội');
    });
    await kit.step(next(), 'User menu › My Preferences: who is signed in', 'Menu người dùng › Tùy chọn của tôi: ai đang đăng nhập');
    await kit.click(p.locator('.o_user_menu').first(), 1200);
    await kit.click(p.locator('.dropdown-item').filter({ hasText: 'My Preferences' }).first(), 3000);
    const pref = p.locator('.modal-content').filter({ visible: true }).first();
    await kit.proof(pref.locator('.o_field_widget[name=name]').first(), 'My Preferences: the new user’s own name', async () =>
      (await kit.fieldValues(['name'], pref)).name === fullName);
    await kit.click(pref.locator('a.nav-link', { hasText: 'Calendar' }).first(), 1500);
    // Asia/Saigon is the older name of the same zone (UTC+7); the first sign-in may store it.
    await kit.proof(pref.locator('.o_field_widget[name=tz]').first(), 'My Preferences: Vietnam time zone', async () =>
      /Asia\/(Ho_Chi_Minh|Saigon)/.test((await kit.fieldValues(['tz'], pref)).tz));
    await kit.click(pref.locator('button').filter({ hasText: /^\s*Discard\s*$/ }).first(), 1200);
    if (STOP === 'signin') return;

    // ------------------------------------------------------------ Owner switches the test login off
    await kit.switchUser(next(), owner, false);
    await kit.step(next(), `Owner switches the test login off: Users & Roles › ${login} › Switch off`, `Chủ sở hữu tắt tài khoản thử nghiệm: Người dùng & Vai trò › ${login} › Tắt`);
    await a.area(kit, 'Settings');
    await kit.click(c.sidebar(p, 'People'), 3500);
    await a.listSearch(kit, fullName);
    await kit.click(p.locator('tr.o_data_row', { hasText: login }).first().locator('td').nth(1), 3500);
    await kit.click(p.locator('button').filter({ hasText: /^\s*Switch off\s*$/ }).filter({ visible: true }).first(), 1500);
    await kit.click(p.locator('.modal-footer button.btn-primary').filter({ visible: true }).first(), 3000);
    await p.locator('button').filter({ hasText: /^\s*Switch back on\s*$/ }).filter({ visible: true }).first().waitFor({ timeout: 15000 }).catch(() => {});
    await kit.proof([p.locator('button').filter({ hasText: /^\s*Switch back on\s*$/ }).filter({ visible: true }).first(), c.field(p, 'active')],
      'Switched off: can no longer sign in', async () => !(await c.field(p, 'active').locator('input').isChecked().catch(() => true)));
    kit.records['New user'] = `${fullName} (login ${login}), switched off at the end`;
  },
};
