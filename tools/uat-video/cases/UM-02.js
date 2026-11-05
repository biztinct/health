// UM-02 User roles: the Owner reviews the eight UAT accounts (job and area) in Settings ›
// People; each of the seven accounts we hold a password for signs in and lands on its role's
// screens with its role's menu; Operations Managers are fixed to their own area; the Owner
// can switch areas and opens a Hanoi and a Ho Chi Minh City booking.
// The eighth account ("finance", Accountant) is shown in the list only: no password is held
// for it in this test kit and it is not reset.
const c = require('./common');
const a = require('./adm_common');
const owner = a.users.owner;
const BASE = 'https://carejiox.com';
const STOP = process.env.UM02_STOP || '';

// login → [job on the People list, area on the People list ('' = none)]
const EIGHT = [
  ['uat_crm', 'CRM', 'Hà Nội'], ['doctor_hn', 'Doctor', 'Hà Nội'], ['finance', 'Accountant', ''],
  ['nurse_hcm', 'Nurse', 'TPHCM'], ['nurse_hn', 'Nurse', 'Hà Nội'], ['om_hcm', 'Operations Manager', 'TPHCM'],
  ['om_hn', 'Operations Manager', 'Hà Nội'], ['uat_owner', 'Owner', ''],
];

module.exports = {
  meta: {
    id: 'UM-02', title: 'Each role signs in to its own work', short: 'User roles',
    title_vi: 'Mỗi vai trò đăng nhập vào đúng công việc của mình',
    criterion: 'Assign and verify the Owner, Operations Manager, Nurse, Doctor, Finance and CRM roles. Each role must allow its intended work while denying unauthorised actions. Operations Managers are restricted to their assigned catchment; Owners keep access across catchments.',
    data: 'The eight UAT accounts (fictional people “Client UAT …”); BK3832 (Hà Nội) and BK3841 (Ho Chi Minh City); the Accountant account “finance” is shown in the list only (no password held for it in this test, not reset)',
    expected: 'Each role permits its assigned work. Operations Managers are limited to their assigned catchment; the Owner can access both areas.',
    ...owner,
  },
  proofVi: {
    'The eight UAT accounts with their job and area': 'Tám tài khoản UAT với công việc và khu vực',
    'Accountant account “finance”: listed with its job (not signed in here)': 'Tài khoản Kế toán “finance”: có trong danh sách với công việc (không đăng nhập ở đây)',
    'Owner: every area of the menu, including Settings › People and Master data': 'Chủ sở hữu: mọi khu vực trên menu, gồm Cài đặt › Nhân sự và Dữ liệu gốc',
    'Owner can switch between Hà Nội, TPHCM and All areas': 'Chủ sở hữu có thể chuyển giữa Hà Nội, TP.HCM và Tất cả',
    'CRM user lands on the CRM screens: Contacts, Phone, Channels': 'Nhân viên CRM vào màn hình CRM: Liên hệ, Điện thoại, Kênh',
    'CRM user has no Finance or Clinical area': 'Nhân viên CRM không có khu vực Tài chính hay Lâm sàng',
    'Operations Manager, Hanoi: lands on the Operations dashboard': 'Quản lý vận hành Hà Nội: vào bảng điều khiển Vận hành',
    'Area fixed to Hà Nội': 'Khu vực cố định là Hà Nội',
    'Settings holds only Connections: no People or Master data (Owner settings)': 'Cài đặt chỉ có Kết nối: không có Nhân sự hay Dữ liệu gốc (cài đặt của Chủ sở hữu)',
    'Operations Manager, HCMC: area fixed to TPHCM': 'Quản lý vận hành TP.HCM: khu vực cố định là TP.HCM',
    'Dashboard offers only TPHCM facilities': 'Bảng điều khiển chỉ hiển thị cơ sở TP.HCM',
    'Nurse, Hanoi: Bookings, Clients, Schedule; area Hà Nội': 'Điều dưỡng Hà Nội: Lịch hẹn, Khách hàng, Lịch làm việc; khu vực Hà Nội',
    'Nurse has no CRM, Finance or Settings area': 'Điều dưỡng không có khu vực CRM, Tài chính hay Cài đặt',
    'Doctor, Hanoi: lands on the Clinical screens': 'Bác sĩ Hà Nội: vào màn hình Lâm sàng',
    'Doctor has no CRM, Finance or Settings area': 'Bác sĩ không có khu vực CRM, Tài chính hay Cài đặt',
    'Nurse, HCMC: Bookings, Clients, Schedule; area TPHCM': 'Điều dưỡng TP.HCM: Lịch hẹn, Khách hàng, Lịch làm việc; khu vực TP.HCM',
    'Owner opens BK3832 (Hà Nội)': 'Chủ sở hữu mở được BK3832 (Hà Nội)',
    'Owner opens BK3841 (TPHCM)': 'Chủ sở hữu mở được BK3841 (TP.HCM)',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    const has = (arr, x) => arr.some((v) => v.toLowerCase() === x.toLowerCase());
    const tabs = async () => (await p.locator('button.vu-tab').filter({ visible: true }).allInnerTexts()).map((x) => x.trim());
    const railBox = () => p.locator('.vu-rail-entry').first().locator('xpath=..');
    const tabBox = () => p.locator('button.vu-tab').filter({ visible: true }).first().locator('xpath=..');

    // ------------------------------------------------------------ Owner: the eight accounts
    await kit.login();
    await kit.step(next(), 'Settings › People › Users & Roles: search “Client UAT”', 'Cài đặt › Nhân sự › Người dùng & Vai trò: tìm “Client UAT”');
    await a.area(kit, 'Settings');
    await kit.click(c.sidebar(p, 'People'), 4000);
    await a.listSearch(kit, 'Client UAT');
    const rows = p.locator('tr.o_data_row');
    await rows.first().waitFor({ timeout: 15000 });
    await kit.proof(rows.first().locator('xpath=ancestor::table[1]'), 'The eight UAT accounts with their job and area', async () => {
      const all = await rows.allInnerTexts();
      return all.length === 8 && EIGHT.every(([login, job, ar]) => {
        const r = all.find((t) => t.split('\t').map((x) => x.trim()).includes(login)) || '';
        return r.includes(job) && (!ar || r.includes(ar));
      });
    }, 4500);
    await kit.proof(rows.filter({ hasText: 'finance' }).first(), 'Accountant account “finance”: listed with its job (not signed in here)',
      (t) => t.includes('Client UAT finance') && t.includes('Accountant'));
    await kit.proof([railBox(), tabBox()], 'Owner: every area of the menu, including Settings › People and Master data', async () => {
      const r = await a.railNames(p);
      const t = await tabs();
      return ['CRM', 'Operations', 'Finance', 'Clinical', 'Settings'].every((x) => has(r, x)) && has(t, 'People') && has(t, 'Master Data');
    });
    await kit.proof(a.catchment(p), 'Owner can switch between Hà Nội, TPHCM and All areas', async () => {
      const o = (await a.catchment(p).locator('option').allInnerTexts()).map((x) => x.trim());
      return o.includes('Hà Nội') && o.includes('TPHCM') && o.includes('All areas');
    });
    if (STOP === 'owner') return;

    // ------------------------------------------------------------ CRM
    await kit.switchUser(next(), a.users.crm, false);
    await kit.proof([a.catchment(p), tabBox()], 'CRM user lands on the CRM screens: Contacts, Phone, Channels', async () => {
      const t = await tabs();
      return ['Contacts', 'Phone', 'Channels'].every((x) => has(t, x)) && (await a.catchment(p).innerText()).includes('Hà Nội');
    });
    await kit.proof(railBox(), 'CRM user has no Finance or Clinical area', async () => {
      const r = await a.railNames(p);
      return has(r, 'CRM') && !has(r, 'Finance') && !has(r, 'Clinical');
    });

    // ------------------------------------------------------------ Operations Manager, Hanoi
    await kit.switchUser(next(), a.users.omhn, false);
    await kit.proof([tabBox(), p.getByText('Operations Center').filter({ visible: true }).first()], 'Operations Manager, Hanoi: lands on the Operations dashboard',
      async () => has(await tabs(), 'Bookings') && has(await tabs(), 'Dashboard'));
    await kit.proof(a.catchment(p), 'Area fixed to Hà Nội', async (t) =>
      t.includes('Hà Nội') && !t.includes('TPHCM') && !(await a.catchment(p).locator('select, .dropdown-toggle, button').count()));
    await kit.step(next(), 'Open Settings: what an Operations Manager has there', 'Mở Cài đặt: Quản lý vận hành có gì ở đó');
    await a.area(kit, 'Settings');
    await kit.proof(tabBox(), 'Settings holds only Connections: no People or Master data (Owner settings)', async () => {
      const t = await tabs();
      return t.length === 1 && has(t, 'Connections');
    });

    // ------------------------------------------------------------ Operations Manager, HCMC
    await kit.switchUser(next(), a.users.omhcm, false);
    await kit.proof(a.catchment(p), 'Operations Manager, HCMC: area fixed to TPHCM', async (t) =>
      t.includes('TPHCM') && !t.includes('Hà Nội') && !(await a.catchment(p).locator('select, .dropdown-toggle, button').count()));
    const chips = p.locator('button').filter({ hasText: /^(All Facilities|HN_|TPHCM_)/ }).filter({ visible: true });
    await chips.first().waitFor({ timeout: 15000 });
    await kit.proof(chips.first().locator('xpath=..'), 'Dashboard offers only TPHCM facilities', async () => {
      const names = (await chips.allInnerTexts()).map((x) => x.trim()).filter((x) => x !== 'All Facilities');
      return names.length > 0 && names.every((x) => x.startsWith('TPHCM_'));
    });
    if (STOP === 'om') return;

    // ------------------------------------------------------------ Nurse, Hanoi
    await kit.switchUser(next(), a.users.nursehn, false);
    await kit.proof([a.catchment(p), tabBox()], 'Nurse, Hanoi: Bookings, Clients, Schedule; area Hà Nội', async () => {
      const t = await tabs();
      return ['Bookings', 'Clients', 'Schedule'].every((x) => has(t, x)) && (await a.catchment(p).innerText()).includes('Hà Nội');
    });
    await kit.proof(railBox(), 'Nurse has no CRM, Finance or Settings area', async () => {
      const r = await a.railNames(p);
      return has(r, 'Operations') && !has(r, 'CRM') && !has(r, 'Finance') && !has(r, 'Settings');
    });

    // ------------------------------------------------------------ Doctor, Hanoi
    await kit.switchUser(next(), a.users.doctor, false);
    await kit.proof([a.catchment(p), tabBox()], 'Doctor, Hanoi: lands on the Clinical screens', async () => {
      const t = await tabs();
      return ['Observations', 'Medications', 'Notes'].every((x) => has(t, x)) && (await a.catchment(p).innerText()).includes('Hà Nội');
    });
    await kit.proof(railBox(), 'Doctor has no CRM, Finance or Settings area', async () => {
      const r = await a.railNames(p);
      return has(r, 'Clinical') && !has(r, 'CRM') && !has(r, 'Finance') && !has(r, 'Settings');
    });

    // ------------------------------------------------------------ Nurse, HCMC
    await kit.switchUser(next(), a.users.nursehcm, false);
    await kit.proof([a.catchment(p), tabBox()], 'Nurse, HCMC: Bookings, Clients, Schedule; area TPHCM', async () => {
      const t = await tabs();
      return ['Bookings', 'Clients', 'Schedule'].every((x) => has(t, x)) && (await a.catchment(p).innerText()).includes('TPHCM');
    });
    if (STOP === 'nurse') return;

    // ------------------------------------------------------------ Owner: both areas
    await kit.switchUser(next(), owner, false);
    for (const [bk, id, ar] of [['BK3832', 9666, 'Hà Nội'], ['BK3841', 9675, 'TPHCM']]) {
      await kit.step(next(), `Open ${bk} (${ar}) by its direct link`, `Mở ${bk} (${ar === 'TPHCM' ? 'TP.HCM' : ar}) bằng đường dẫn trực tiếp`);
      await p.goto(`${BASE}/bizapp/action-1433/health.fieldservice.order/${id}`);
      await c.hero(p).waitFor({ timeout: 20000 });
      await kit.hold(1500);
      await kit.proof(c.hero(p), `Owner opens ${bk} (${ar})`, (t) => t.includes(bk) && t.includes(ar));
    }
  },
};
