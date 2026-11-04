// MB-06 Nurse app: the nurse enters the clinical note for the visit (procedure count included);
// it reopens against the same visit after reloading, and the office sees it on the booking.
const a = require('./as_common');
const m = require('./mb_common');
const nurse = m.users.nurse;
const om = m.users.om;
const cl = m.client;
const NOTE = 'UAT ONLY - TC-13: 2 intramuscular injections given (left and right deltoid); no reaction after 15 minutes';
const NOTE_START = 'UAT ONLY - TC-13: 2 intramuscular injections';

module.exports = {
  meta: {
    id: 'MB-06', title: 'Nurse app clinical notes entered', short: 'Mobile clinical notes',
    title_vi: 'Ứng dụng điều dưỡng: nhập ghi chú lâm sàng',
    criterion: 'An authorised nurse can enter clinical notes for the assigned visit. Saved notes reopen against the correct booking and the procedure count is kept.',
    data: `Today’s visit ${m.load().bk || '(from MB-02)'} for ${cl.name} (${cl.code}), in progress since MB-04; note “${NOTE}”; nurse ${nurse.login}; office view as ${om.login}`,
    expected: 'Authorized nurse can save/reopen notes or upload clinical notes.',
    ...nurse,
  },
  proofVi: {
    'Visit in progress: notes can be added': 'Lượt khám đang thực hiện: có thể thêm ghi chú',
    'Note saved for this visit, at Vietnam time': 'Đã lưu ghi chú cho lượt khám này, theo giờ Việt Nam',
    'Reopened: the same note, 2 injections, on the same visit': 'Mở lại: đúng ghi chú, 2 mũi tiêm, đúng lượt khám',
    'Office: the note is on the booking': 'Văn phòng: ghi chú có trên lịch hẹn',
  },

  async run(kit) {
    const p = kit.page;
    const st = m.load();
    if (!st.id) throw new Error('no visit in mb_state.json: run MB-02 first');
    let n = 0;
    const next = () => ++n;
    await m.asNurse(kit, next());

    await kit.step(next(), `Open the visit in progress for ${cl.name}`, `Mở lượt khám đang thực hiện của ${cl.name}`);
    await m.openVisit(kit, st);
    await kit.proof([m.sheet(p).locator('.modal-header').first(), m.sheet(p).locator('.client-name-banner').first()], 'Visit in progress: notes can be added',
      async (t) => /in progress/i.test(t) && t.includes(cl.name) && (await m.btn(p, /Clinical Notes/).count()) > 0);

    await kit.step(next(), 'Clinical Notes › Add New Clinical Note', 'Ghi chú lâm sàng › Thêm ghi chú mới');
    await kit.click(m.btn(p, /Clinical Notes/), 2500);
    await kit.click(m.btn(p, /Add New Clinical Note/), 2500);
    await kit.step(next(), 'Write what was done: 2 injections, no reaction; Confirm and Save', 'Ghi việc đã làm: 2 mũi tiêm, không phản ứng; Xác nhận và lưu');
    await kit.type(p.getByPlaceholder('Enter clinical notes...'), NOTE, 600);
    await kit.click(m.btn(p, /Confirm and Save/), 3500);
    const noteBox = () => p.getByText(NOTE_START).filter({ visible: true }).first().locator('xpath=..');
    await kit.proof(noteBox(), 'Note saved for this visit, at Vietnam time', (t) => t.includes(NOTE_START) && m.nearNow(t, 5));

    await kit.step(next(), 'Close the notes, leave the visit and reload the app', 'Đóng ghi chú, rời lượt khám và tải lại ứng dụng');
    await kit.click(p.locator('button').filter({ hasText: /^\s*close\s*$/ }).filter({ visible: true }).last(), 1500);
    await m.closeVisit(kit);
    await m.reloadApp(kit);
    await kit.step(next(), 'Open the visit again › Clinical Notes', 'Mở lại lượt khám › Ghi chú lâm sàng');
    await m.openVisit(kit, st);
    await kit.click(m.btn(p, /Clinical Notes/), 2500);
    await kit.proof(noteBox(), 'Reopened: the same note, 2 injections, on the same visit',
      async (t) => t.includes('2 intramuscular injections') && (await p.locator('.client-name-banner').filter({ visible: true }).first().innerText()).includes(cl.name));
    await kit.click(p.locator('button').filter({ hasText: /^\s*close\s*$/ }).filter({ visible: true }).last(), 1500);
    await m.closeVisit(kit);

    // ------------------------------------------------------------ the office sees it on the booking
    await m.asStaff(kit, next(), om);
    await m.openBooking(kit, next(), st.bk);
    await kit.step(next(), 'Clinical tab', 'Thẻ Lâm sàng');
    await kit.click(p.locator('.o_notebook .nav-link').filter({ hasText: /^\s*Clinical\s*$/ }).first(), 2500);
    const office = p.getByText(NOTE_START).filter({ visible: true }).first();
    await office.waitFor({ timeout: 8000 }).catch(() => {});
    await kit.proof([p.getByText(/Clinical Notes Submitted/).filter({ visible: true }).first(),
      office.locator('xpath=ancestor::*[self::tr or contains(@class,"o_kanban_record") or contains(@class,"card")][1]')], 'Office: the note is on the booking',
      async (t) => t.includes(NOTE_START) && (await a.hero(p).innerText()).includes(st.bk));
  },
};
