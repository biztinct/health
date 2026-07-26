# CC-E browser evidence — the honest dark state

Driven 2026-07-26 on `https://care.biztinct.com` as the real **`crm`** login
(Healthcare / CRM Manager + CRM User + Sales Administrator), from the login
page, never from a deep link (ledger §5.69).

## Navigation path — click by click

| # | Action | Result | Screenshot |
|---|---|---|---|
| 1 | Open `https://care.biztinct.com/web/login` | Odoo login page | `01-login.png` |
| 2 | User ID `crm`, password, **Log in** | lands on `/bizapp` — the CMS shell, NOT `/odoo` | `02-bizapp-shell.png` |
| 3 | CMS sidebar → **CRM → Channel Center** | `/bizapp/action-1706`, the Center's catalogue | `03-channel-center-catalogue.png` |
| 4 | (regression) **Telegram → Connect**, then **I have my key** | the CC-C guided-secret stepper, unchanged | `04-telegram-stepper-regression.png` |

The Channel Center is reachable from the sidebar seed CC-C added — it is not a
deep link, and `/odoo` is not where this persona lands.

## What the catalogue says about Meta (the deliverable)

Read out of the live DOM, not from a screenshot:

```
cards (top level)  7   — ZNS renders INSIDE the Zalo card, so 8 channels total
dock order         Zalo, Calls, Email, WhatsApp, Messenger, Telegram, Web chat

Zalo       chip "Not migrated"   "Health19 is completing provider approval for this channel."  0/6  [Not available yet]  disabled
Calls      chip "Not connected"  "Available in an upcoming update."                            —    [Available in an upcoming update] disabled
Email      chip "Not connected"  "Health19 is completing provider approval for this channel."  —    [Not available yet]  disabled
WhatsApp   chip "Not connected"  "Health19 is completing provider approval for this channel."  0/6  [Not available yet]  disabled
Messenger  chip "Not connected"  "Health19 is completing provider approval for this channel."  0/5  [Not available yet]  disabled
Telegram   chip "Not connected"  "Not set up yet"                                              0/4  [Connect]            enabled
Web chat   chip "Not connected"  "Not set up yet"                                              0/2  [Connect]            enabled
```

**This is the phase's honest deliverable.** WhatsApp and Messenger are
software-complete but not offerable: there is no `channel.platform.app` for
provider `meta` on this deployment, so the Center says so and the button is
inert. Clicking the WhatsApp button is a no-op — no modal opens, the URL does
not change, the button stays disabled.

The same refusal holds at the RPC layer, called from this browser session as
this user:

```
center_begin('whatsapp')       -> UserError: This channel is not available yet.
center_begin('fb')             -> UserError: This channel is not available yet.
center_meta_start('whatsapp')  -> UserError: This channel is not set up yet.
center_meta_start('fb')        -> UserError: This channel is not set up yet.
```

## What is NOT proven here

**The Meta steppers themselves are unproven.** With no platform app they
cannot be driven at all: no sign-in popup, no WABA/number picker, no Page
picker, no `subscribed_apps` call, no approval rows. Everything above that
line is proven only against mocks (T127–T136). Driving it for real needs the
operator checklist §12.1–§12.4 finished — a Business-type Meta app, Business
Verification, App Review of five permissions with screencasts, and two
Login-for-Business configurations. **No placeholder platform app was seeded to
make a screenshot possible.**

## Meta's JS SDK is genuinely on demand

```
window.FB                                     false
<script src*="connect.facebook.net">          0 tags
```

The SDK is absent from the loaded Center. It is fetched only when a tenant
presses "Sign in with Meta" inside the WhatsApp stepper — never in the backend
bundle, where every Odoo user would pay for it and a Meta outage would become a
Health19 outage.

## Regression: the CC-C steppers are unaffected

CC-E rewrote the stepper's `oauth_popup` branches to be channel-scoped (Zalo's
copy would otherwise have been served to Messenger, which declares the same
mode). Driving Telegram proves nothing leaked:

```
modal title      Telegram
steps            Create your bot | Paste the key | We set things up | Say hello
step 0 heading   Create your bot
step 0 body      "Open Telegram and message @BotFather. Send /newbot, …"
step 0 link      Open BotFather
step 1 heading   Paste the key
step 1 input     #cc_token, type="password", "Check the key" disabled until typed
Zalo copy in the modal?   false
Meta copy in the modal?   false
```

## Styling compiled (ledger §5.68)

`.o_channel_center` root computed background `rgb(242, 244, 249)` — the SCSS
bundle really compiled. Verified server-side too: the regenerated
`web.assets_web` CSS is **2,190,501 bytes** (not the ~40 KB collapsed state a
libsass failure produces) and carries `.o_channel_center` (128),
`.cc-picker` (4, new in CC-E), `.cc-sub-line.st-pending` (1, new) **and** the
known-good sibling `.o_care_command` (326).

## Vietnamese

The translation bundle **the browser itself loads** for `vi_VN` carries 75
entries for this module (48 after CC-C), including every CC-E string:

```
Sign in with Meta                                 -> Đăng nhập bằng Meta
Sign in with Facebook                             -> Đăng nhập bằng Facebook
Waiting on Meta                                   -> Đang chờ Meta
Use this one                                      -> Dùng cái này
Refresh the list                                  -> Tải lại danh sách
Check again                                       -> Kiểm tra lại
Reading your Meta accounts…                       -> Đang đọc các tài khoản Meta của bạn…
Connected. New messages arrive in Care Command.   -> Đã kết nối. Tin nhắn mới sẽ về Care Command.
Health19 is completing provider approval …        -> Health19 đang hoàn tất phê duyệt với nhà cung cấp cho kênh này.
```

No Vietnamese *screenshot* was taken: rendering the UI in Vietnamese would mean
writing `lang` on the live `crm` account, and the bundle above is the exact
data the client renders from. Server-side, `_center_guide_texts()` under
`lang='vi_VN'` returns the Vietnamese Meta copy directly (185 python + 75 web
translations live).

## Console

One error across the whole session, and it is mine:
`GET /web/webclient/translations/x?lang=vi_VN&… 404` — a probe URL I typed
wrong before finding the right endpoint. No page-generated errors or warnings.

## QA fixture removed, fresh-cursor verified (ledger §5.34)

Clicking **Telegram → Connect** created `care.channel.connection` id 2242
(`telegram`, `authorizing`, no credential, 0 readiness checks). It was deleted
after the pass and the removal confirmed from **psql**, a different process
from the one that made the change:

```
connections           = 1
connections detail    = zalo:legacy      (the CC-D migration row, untouched)
telegram rows         = 0
meta connections      = 0
identities            = 0
channel messages      = 0
oauth sessions        = 0
platform apps         = 0
```

Two `care.channel.audit` rows from that click (`connect_start`,
`health_transition`) survive with `connection_id` NULL. That is by design:
the audit model's `write`/`unlink` raise unconditionally (no `su` escape,
ledger §5.4) and the FK is `ondelete='set null'` precisely so deleting a
connection cannot erase its history (§5.30). They are declared, not hidden.
