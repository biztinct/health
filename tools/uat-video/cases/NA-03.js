// NA-03 Private chat space: the existing private group "UAT20261021 Private acceptance chat"
// (created 21 Oct, as the workbook row says) has exactly two members, the Owner and nurse_hn;
// nurse_hn finds and opens it; nurse_hcm (not a member) neither has it in her list nor finds
// it with Search conversations. No message is sent.
const a = require('./adm_common');
const owner = a.users.owner;
const CHAT = 'UAT20261021 Private acceptance chat';

module.exports = {
  meta: {
    id: 'NA-03', title: 'Private chat space only for its members', short: 'Private chat',
    title_vi: 'Không gian trò chuyện riêng chỉ dành cho thành viên',
    criterion: 'Create or use a private chat space with the intended test members only. Members must be able to find and open the space and non-members must not. No messages need to be sent.',
    data: `Existing private group “${CHAT}” (members Client UAT owner and Client UAT nurse_hn); non-member nurse_hcm. No message is sent`,
    expected: 'Private space is accessible to intended members and hidden from others.',
    ...owner,
  },
  proofVi: {
    'Owner: the private space is in Messages': 'Chủ sở hữu: không gian riêng có trong Tin nhắn',
    'Members: Client UAT owner and Client UAT nurse_hn only': 'Thành viên: chỉ Client UAT owner và Client UAT nurse_hn',
    'nurse_hn: the space is in her Messages': 'nurse_hn: không gian có trong Tin nhắn của cô ấy',
    'nurse_hn: opens it, same two members': 'nurse_hn: mở được, cùng hai thành viên',
    'nurse_hcm: the space is not in her Messages': 'nurse_hcm: không gian không có trong Tin nhắn của cô ấy',
    'nurse_hcm: Search conversations finds nothing': 'nurse_hcm: Tìm cuộc trò chuyện không thấy gì',
  },

  async run(kit) {
    const p = kit.page;
    let n = 1;
    const next = () => ++n;
    const menuBtn = () => p.locator('.o_menu_systray .o-mail-MessagingMenu-counter, .o_menu_systray .fa-comments').first()
      .locator('xpath=ancestor::*[contains(@class,"dropdown-toggle") or self::button][1]');
    const menu = () => p.locator('.o-mail-MessagingMenu').filter({ visible: true }).first();
    const openMenu = async () => {
      await kit.click(menuBtn(), 2000);
      await menu().waitFor({ timeout: 10000 });
      await kit.hold(1200);
    };
    const item = (name) => menu().locator('.o-mail-NotificationItem').filter({ hasText: name }).first();
    // From the messaging menu: open a conversation, then the full Messages page.
    const openFull = async (name) => {
      await kit.click(item(name), 2500);
      const win = p.locator('.o-mail-ChatWindow').filter({ hasText: name }).first();
      await win.waitFor({ timeout: 10000 });
      await kit.click(win.locator('button[title="Open Actions Menu"]').first(), 1200);
      await kit.click(p.locator('.dropdown-item, .o-dropdown-item').filter({ hasText: /^\s*Open in Discuss\s*$/ }).filter({ visible: true }).first(), 3500);
      await p.locator('.o-mail-DiscussSidebar').first().waitFor({ timeout: 15000 });
    };
    const members = () => p.locator('.o-discuss-ChannelMemberList').filter({ visible: true }).first();
    const showMembers = async () => {
      if (!(await members().count())) await kit.click(p.locator('.o-mail-DiscussContent-header button[title="Members"], button[title="Members"]').first(), 2000);
      if (!(await members().count())) await kit.click(p.locator('button[title="Members"]').first(), 2000);
      await members().waitFor({ timeout: 10000 });
    };
    const chatName = async () => (await p.locator('input.o-mail-DiscussContent-threadName').first().inputValue().catch(() => ''))
      || (await p.locator('.o-mail-DiscussContent-header').first().innerText().catch(() => ''));
    const memberNames = async () => (await members().locator('.o-discuss-ChannelMember, [class*=ChannelMember-]').allInnerTexts())
      .map((x) => x.trim()).filter(Boolean);

    // ------------------------------------------------------------ Owner
    await kit.login();
    await kit.step(next(), 'Messages (chat icon, top right)', 'Tin nhắn (biểu tượng trò chuyện, góc trên phải)');
    await openMenu();
    await kit.proof(item(CHAT), 'Owner: the private space is in Messages', CHAT);
    await kit.step(next(), 'Open it, then Actions › Open in Discuss › Members', 'Mở ra, rồi Thao tác › Mở trong Thảo luận › Thành viên');
    await openFull(CHAT);
    await showMembers();
    await kit.proof([p.locator('.o-mail-DiscussContent-header').first(), members()], 'Members: Client UAT owner and Client UAT nurse_hn only', async (t) =>
      (await chatName()).includes(CHAT) && /Client UAT owner/.test(t) && /Client UAT nurse_hn/.test(t)
      && ((await members().innerText()).match(/Client UAT \w+/g) || []).length === 2, 4000);

    // ------------------------------------------------------------ nurse_hn (member)
    await kit.switchUser(next(), a.users.nursehn, false);
    await kit.step(next(), 'Messages', 'Tin nhắn');
    await openMenu();
    await kit.proof(item(CHAT), 'nurse_hn: the space is in her Messages', CHAT);
    await kit.step(next(), 'Open it in Discuss and show the members', 'Mở trong Thảo luận và xem thành viên');
    await openFull(CHAT);
    await showMembers();
    await kit.proof([p.locator('.o-mail-DiscussContent-header').first(), members()], 'nurse_hn: opens it, same two members', async (t) =>
      (await chatName()).includes(CHAT) && /Client UAT owner/.test(t) && /Client UAT nurse_hn/.test(t)
      && ((await members().innerText()).match(/Client UAT \w+/g) || []).length === 2);

    // ------------------------------------------------------------ nurse_hcm (not a member)
    await kit.switchUser(next(), a.users.nursehcm, false);
    await kit.step(next(), 'Messages: her conversations', 'Tin nhắn: các cuộc trò chuyện của cô ấy');
    await openMenu();
    await kit.proof(menu(), 'nurse_hcm: the space is not in her Messages', (t) => !t.includes('Private acceptance'));
    await kit.step(next(), 'Open Discuss and use Search conversations: “Private acceptance”', 'Mở Thảo luận và dùng Tìm cuộc trò chuyện: “Private acceptance”');
    await openFull('Viet Uc Care');
    await kit.click(p.locator('.o-mail-DiscussSearch-inputClickable').first(), 2000);
    const pal = p.locator('.o_command_palette, .modal-content').filter({ visible: true }).first();
    await pal.waitFor({ timeout: 10000 });
    await p.keyboard.type('Private acceptance', { delay: 55 });
    await kit.hold(3000);
    await kit.proof(pal, 'nurse_hcm: Search conversations finds nothing', (t) =>
      !t.includes(CHAT) && !/access/i.test(t), 4000);
    await p.keyboard.press('Escape');
  },
};
