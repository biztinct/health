# CC-C browser evidence — navigation, click by click

**Target:** care.biztinct.com (vietuat) · **Date:** 2026-07-25 ·
**Login:** `crm` (Healthcare CRM Manager — *not* a system administrator)
**Console:** clean on every screen, both tabs, errors + warnings, across all
navigations (`list_console_messages` with preserved messages: none).

Screenshots referenced below are in this directory.

---

## 0. A reachability defect found by this pass (and fixed)

The first attempt could **not** reach the Center as a real user:

1. Log in → the browser lands in the `/bizapp` CMS shell.
2. `https://care.biztinct.com/odoo` → redirects straight back to
   `/bizapp/action-1417`.
3. The shell's app switcher offers exactly two apps: *Viet UC CMS* and
   *Workflow Automations*. No "CRM Center", so no "Care Command Setup", so no
   "Channel Center".

Server-side the menu was correct and visible (`ir.ui.menu` search as the `crm`
user returns it), which is precisely the ledger §5.41 sibling trap: a backend
menu is not the same thing as a surface a CMS-shell user can reach. The
handover specified only the backend menuitem, so **the phase's entire
deliverable was unreachable for the persona it was built for.**

Fixed in `data/cms_sidebar_items_channel_center.xml` — a `cms.sidebar.item`
directly after Care Command in the CRM section. Two traps hit while doing it,
both caught by driving the sidebar rather than reading the model:

- seeding it as a **child** of Care Command turned Care Command itself into a
  non-navigating accordion (`cms_sidebar.js:124` — "items with children act as
  expandable groups; leaves navigate"). It is a sibling instead;
- removing `parent_id` from the XML did **not** unset it — an Odoo data update
  only writes the fields it names, so the item stayed a hidden child through a
  deploy. It now carries `<field name="parent_id" eval="False"/>`.

Everything below is the path **after** that fix.

---

## 1. Real navigation path (no deep link)

`/web/login` → log in as `crm` → lands in the CMS shell → left sidebar,
**CRM → Channel Center** (plug icon, directly under Care Command) →
`/bizapp/action-1706`.

**`12-real-nav-path-sidebar.png`** — the Center rendered inside the CMS shell,
sidebar intact, "Channel Center" highlighted as the active item. Care Command
above it still navigates (verified by clicking it afterwards: it renders
`.o_care_command` and the Channel Center entry stays in the sidebar).

**`01-catalogue.png`** — the catalogue: 8 channels, honest chips.
- Zalo / Email / WhatsApp / Messenger → "Health19 is completing provider
  approval for this channel", primary action disabled (no platform app seeded).
- Calls → "Available in an upcoming update" (needs no platform app, but its
  flow is CC-F).
- ZNS renders as a sub-card **inside** Zalo, never as its own sign-in.
- Telegram and Web chat → the only two "Connect" buttons.

---

## 2. Web chat, end to end

1. **Connect** on the Web chat card → stepper opens at step 1 of 3.
2. Website addresses `https://care.biztinct.com`, first message
   *"Xin chào! Chúng tôi có thể giúp gì?"* → **Turn on web chat**.
   → card behind flips to **ALMOST THERE**, resource line "Website widget",
   checks **1/2**.
3. **`02-webchat-snippet-copied.png`** — step 2 hands back the embed snippet:
   `<script src="https://care.biztinct.com/…/widget.js?v=19.0.3.0.0"
   data-origin="https://care.biztinct.com"></script>` — https (the base-URL fix
   landed) and carrying its `?v=` cache stamp. The **Copy** button reports
   `Copied ✓` (verified in-page: the label changes and resets after 3 s).
4. **`03-demo-page-widget.png`** — the demo page as a visitor. The launcher
   opens, the server mints the session, and the greeting typed in the stepper
   appears in the widget. The embed snippet on that page renders as **text**,
   not as a live `<script>` (§5.64 fix still holding).
5. Visitor sends *"Chào bạn, tôi muốn đặt lịch khám tại nhà"*.
   Network panel for the widget (`list_network_requests`):
   ```
   POST /care_channels/webchat/start    200
   POST /care_channels/webchat/poll     200
   POST /care_channels/webchat/poll     200
   POST /care_channels/webchat/message  200
   POST /care_channels/webchat/poll     200
   ```
   **Every poll is a POST** — the CC-B review touch-up, live: the session id
   never appears in a URL.
6. **`04-webchat-connected.png`** — back on the Center, without a reload: the
   card flipped to **CONNECTED** (2/2, "Received just now") and the stepper's
   step 3 says *"Web chat is working. Messages appear in Care Command."* The
   only thing that moved it there was a real visitor message
   (`inbound_ok`) — readiness derived, never asserted.
7. **`05-dock-webchat-lit.png`** — Care Command: the **WEB CHAT** dock icon is
   lit with a badge of 1 while WhatsApp / FB MSGR / TELEGRAM stay dark. The
   conversation "Web visitor 7738a6fc" is on the wall; the composer footer
   reads "Sends via Web chat".
8. Reply from the composer: *"Chào anh/chị, Việt Úc Care xin nghe…"*
9. **`06-widget-reply-received.png`** — the reply arrives in the visitor's
   widget on the next poll. Round trip closed.

---

## 3. Telegram, end to end against a local stub

**No real bot, and not one packet left the box.** A 40-line stub was run on
`127.0.0.1:8899` answering only `getMe` / `setWebhook` / `sendMessage`, and the
connection's `api_base_override` pointed the adapter at it. Stub stopped and
deleted afterwards; port confirmed closed.

1. **Connect** on Telegram → **`07-telegram-step1-botfather.png`**: 4-step
   indicator, "Create your bot", the BotFather instruction and deep link.
2. "I have my key" → the paste screen. **"Check the key" is disabled until
   something is typed.**
3. **`08-telegram-bad-key-refused.png`** — pasting `not-a-real-bot-key`:
   > That does not look like a bot key. BotFather sends a line like
   > 123456789:AAG… — copy the whole line.

   The field is **zeroed** and the wizard stays on step 2. No network call was
   made (the format check runs first) and nothing was stored.
4. A well-formed key → `getMe` (stub) → the wizard advances and shows
   **"Connected to @vietuc_care_qa_bot"** for confirmation. The token field is
   **gone from the DOM** — it is zeroed on success too.
   Server-side at this point: `provider_secret_enc` starts `chs$1$`, the
   plaintext is absent from the column, state `configuring`.
5. **Connect** → `setWebhook` (stub) → state `testing`,
   `webhook_state='subscribed'`, a 43-character path secret minted once.
   **`09-telegram-step4-waiting.png`** — step 4 "Say hello", card at 3/4,
   *"Waiting for your first message…"*, and **"Send a reply" disabled**.
6. **The real public webhook route**, driven with curl against the live server:
   ```
   wrong X-Telegram-Bot-Api-Secret-Token   → HTTP 403
   unknown path secret                      → HTTP 403
   correct secret + correct header          → HTTP 200, {'ingested': 1}
   ```
7. **This is amendment F1 (§5.66) proven live**: after that inbound the card
   stayed at **"Almost there"** — the connection was *not* demoted to
   `action_required`, so it remained ingestable — and the step line became
   *"We received your message. Send a reply to finish."* with the button
   enabled.
8. **Send a reply** → `center_test` sends the synthetic body
   *"Health19 connection test — please ignore."* (§7.6 — never patient data).
   **`10-telegram-connected.png`** — **CONNECTED**, 4/4,
   `@vietuc_care_qa_bot`, "Sent just now".

### The failure path, evidenced by accident

The first "Send a reply" hit a stub that did not implement `sendMessage`, so
the provider refused. The result is a clean demonstration of §5.65 — the
`UserError` rolled the RPC back, and the evidence survived it on the
independent cursor:

```
STATE testing | last_error  telegram refused: stub: unknown method
MSG outgoing failed 'Health19 connection test — please ignore.'
                    | err: telegram refused: stub: unknown method
AUDIT send_failed   | telegram refused: stub: unknown method
```

`authorization_valid` was **not** flipped and the connection kept its state: a
transient provider error is not a lost grant. Only a 401-class failure costs
readiness.

---

## 4. Manage + disconnect

**`11-manage-and-disconnect-confirm.png`** — the Manage panel on a connected
channel: the readiness checklist in plain words (Sign-in valid / Account chosen
/ Connection set up / Sending works), an expandable "Technical details" (state,
last received, last sent — **no secrets, no webhook URL, no token hint**), and
the disconnect confirmation spelling out the operational impact verbatim from
architecture §9:

> New messages will stop arriving in Care Command. Conversation history stays.
> [Keep it on] [Turn it off]

"Turn it off" → chip **Turned off**, primary action **Turn back on**, and the
resource line `@vietuc_care_qa_bot` is retained — the credential was not wiped,
so reconnecting never re-prompts for the key.

---

## 5. Fixtures cleaned, verified on a fresh cursor (§5.34)

Deleted: 2 connections (telegram + webchat), 2 identities, 5 messages, 2
conversations, all readiness checks. Stub process killed, `/tmp/tg_stub.py`
removed, port 8899 confirmed closed. `api_base_override` died with its
connection row.

Re-counted in a **separate** shell invocation, `active_test=False`:

```
channel.platform.app             0
care.channel.connection          0
care.channel.identity            0
care.channel.message             0
care.channel.readiness.check     0
care.channel.oauth.session       0
care.channel.audit              19      <- append-only, see below
care.conversation._channel_keys() -> ('zalo', 'call', 'email', 'zns')
```

The demo page renders its honest "not enabled on this database yet" panel
again, and the dock is back to the base four rails for every user.

**The 19 audit rows are designed behaviour, not residue.** `care.channel.audit`
is append-only with no `su` escape, and `connection_id` is
`ondelete='set null'` precisely so deleting a connection cannot erase its
history (§5.30). 2 rows pre-date this session (CC-B); 17 are this QA pass —
connect_start, resource_selected, webhook_subscribed, health transitions,
test_ok/send_failed, disconnect. No secret, token fragment or provider payload
appears in any of them.
