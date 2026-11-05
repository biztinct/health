// UM-03 Catchment: each Operations Manager sees only their own area (indicator fixed, own
// booking opens, the other area's booking is absent from search and refused by direct link,
// dashboard facilities only from their area); the Owner opens both.
const c = require('./common');
const a = require('./adm_common');
const owner = a.users.owner;
const BASE = 'https://carejiox.com';
const HN = { bk: 'BK3832', id: 9666, client: 'Nguyễn Văn An', facility: 'HN_PK_PKGDVU', area: 'Hà Nội', areaVi: 'Hà Nội', fac: 'HN_' };
const HCM = { bk: 'BK3841', id: 9675, client: '', facility: 'TPHCM_', area: 'TPHCM', areaVi: 'TP.HCM', fac: 'TPHCM_' };
const link = (b) => `${BASE}/bizapp/action-1433/health.fieldservice.order/${b.id}`;
const STOP = process.env.UM03_STOP || '';

module.exports = {
  meta: {
    id: 'UM-03', title: 'Operations Managers see only their own area', short: 'Catchment scope',
    title_vi: 'Quản lý vận hành chỉ thấy khu vực của mình',
    criterion: 'Operations Managers must only access their assigned catchment. They must not see the other catchment in bookings, including direct links and searches. The Owner keeps access across catchments.',
    data: `Hanoi booking ${HN.bk} (id ${HN.id}) and Ho Chi Minh City booking ${HCM.bk} (id ${HCM.id}), both fictional; signed in as om_hn, then om_hcm, then uat_owner`,
    expected: 'Both Operations Managers can access their own catchment only. Searches, direct links and write requests cannot bypass the restriction. Owner cross-catchment access remains available.',
    ...a.users.omhn,
  },
  proofVi: {},

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    const vi = (en, v) => { kit._proofVi[en] = v; return en; };

    // One Operations Manager's pass: own area fixed, own booking opens, other area hidden.
    async function managerPass(own, other, ownVi) {
      await kit.proof(a.catchment(p), vi(`Area indicator: ${own.area} only, no switch`, `Chỉ báo khu vực: chỉ ${own.areaVi}, không có nút chuyển`), async (t) =>
        t.includes(own.area) && !t.includes(other.area) && !(await a.catchment(p).locator('select, .dropdown-toggle, button').count()));

      await kit.step(next(), 'Operations › Bookings › List view, All, All Dates', 'Vận hành › Lịch hẹn › Dạng danh sách, Tất cả, Mọi ngày');
      await a.bookingsList(kit);
      await kit.click(p.locator('a, button, .nav-link').filter({ hasText: /^\s*All\s*$/ }).filter({ visible: true }).first(), 2000);
      await kit.click(p.locator('button, a, span').filter({ hasText: /^\s*All Dates\s*$/ }).filter({ visible: true }).first(), 2500);

      await kit.step(next(), `Search ${own.bk} and open it`, `Tìm ${own.bk} và mở`);
      await a.listSearch(kit, own.bk);
      const row = p.locator('tr.o_data_row', { hasText: own.bk }).first();
      await row.waitFor({ timeout: 15000 });
      await kit.click(row.locator('td').nth(1), 4500);
      await c.hero(p).waitFor({ timeout: 15000 });
      await kit.proof(c.hero(p), vi(`${own.bk} opens with its ${own.area} details`, `${own.bk} mở ra với thông tin ${own.areaVi}`),
        (t) => t.includes(own.bk) && t.includes(own.area) && t.includes(own.fac));

      await kit.step(next(), `Back to the list, clear the search, search ${other.bk} (the other area)`, `Quay lại danh sách, xóa tìm kiếm, tìm ${other.bk} (khu vực khác)`);
      await a.bookingsList(kit);
      await kit.click(p.locator('button, a, span').filter({ hasText: /^\s*All Dates\s*$/ }).filter({ visible: true }).first(), 2500);
      await a.listSearch(kit, other.bk);
      await kit.hold(1500);
      const list = p.locator('.o_list_renderer').filter({ visible: true }).first();
      await kit.proof([p.locator('.o_searchview').filter({ visible: true }).first(), list], vi(`${other.bk} not found: no rows`, `Không tìm thấy ${other.bk}: không có dòng nào`), async (t) =>
        t.includes(other.bk) && (await p.locator('tr.o_data_row').count()) === 0);

      await kit.step(next(), `Paste the direct link to ${other.bk} into the address bar`, `Dán đường dẫn trực tiếp tới ${other.bk} vào thanh địa chỉ`);
      await kit.note(link(other).replace(BASE, 'carejiox.com'), link(other).replace(BASE, 'carejiox.com'));
      await p.goto(link(other));
      const dlg = p.locator('.modal-content').filter({ hasText: /access/i }).filter({ visible: true }).first();
      await dlg.waitFor({ timeout: 20000 }).catch(() => {});
      await kit.hold(1200);
      await kit.proof(dlg, vi(`Direct link refused: ${other.bk} does not open`, `Đường dẫn trực tiếp bị từ chối: ${other.bk} không mở`), async (t) =>
        /You do not have access to this booking/.test(t) && !(await p.locator('.ws-hero').filter({ hasText: other.bk }).count()));
      await kit.click(dlg.locator('.modal-footer button, footer button').filter({ hasText: /^\s*Close\s*$/ }).first(), 1500);

      await kit.step(next(), 'Operations › Dashboard: facilities offered', 'Vận hành › Bảng điều khiển: các cơ sở được hiển thị');
      await kit.click(c.sidebar(p, 'Dashboard'), 4500);
      const chips = p.locator('button').filter({ hasText: /^(All Facilities|HN_|TPHCM_)/ }).filter({ visible: true });
      await chips.first().waitFor({ timeout: 15000 });
      const strip = chips.first().locator('xpath=..');
      await kit.proof([a.catchment(p), strip], vi(`Dashboard: ${own.area} facilities only`, `Bảng điều khiển: chỉ cơ sở ${own.areaVi}`), async () => {
        const names = (await chips.allInnerTexts()).map((x) => x.trim()).filter((x) => x !== 'All Facilities');
        return names.length > 0 && names.every((x) => x.startsWith(own.fac)) && (await a.catchment(p).innerText()).includes(own.area);
      });
    }

    await kit.login();
    await managerPass(HN, HCM);
    if (STOP === 'hn') return;

    await kit.switchUser(next(), a.users.omhcm, false);
    await managerPass(HCM, HN);
    if (STOP === 'hcm') return;

    await kit.switchUser(next(), owner, false);
    await kit.proof(a.catchment(p), vi('Owner: area can be switched between Hà Nội, TPHCM and All areas', 'Chủ sở hữu: có thể chuyển khu vực giữa Hà Nội, TP.HCM và Tất cả'), async (t) => {
      const opts = await a.catchment(p).locator('option').allInnerTexts().catch(() => []);
      return (opts.join('|') + t).includes('Hà Nội') && (opts.join('|') + t).includes('TPHCM');
    });
    for (const b of [HN, HCM]) {
      await kit.step(next(), `Direct link to ${b.bk} (${b.area})`, `Đường dẫn trực tiếp tới ${b.bk} (${b.areaVi})`);
      await p.goto(link(b));
      await c.hero(p).waitFor({ timeout: 20000 });
      await kit.hold(1500);
      await kit.proof(c.hero(p), vi(`Owner opens ${b.bk} (${b.area})`, `Chủ sở hữu mở được ${b.bk} (${b.areaVi})`), (t) => t.includes(b.bk) && t.includes(b.fac));
    }
  },
};
