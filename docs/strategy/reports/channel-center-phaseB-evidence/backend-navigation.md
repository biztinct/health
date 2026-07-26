# CC-B backend evidence — the screenshots the phase could not take

**Captured 2026-07-26 by Fable**, closing the one CC-B DoD item left open
(`channel-center-phaseB-report.md` §4: *"Not in the pack: the backend
dock/composer screenshots. No login credential … is available in this
session"*). The user supplied a login for the existing `crm` account after
the CC-C review; nothing was created, reset or elevated to take these.

**Login:** `crm` — Healthcare CRM Manager + Operations Manager, and
**not** a system administrator (verified: the account holds neither
*Settings* nor *Access Rights*). That is what makes the pack evidence: it
shows a real tenant user reaching the feature, not a superuser.

**Path:** `/web/login` → log in → lands in the `/bizapp` CMS shell (§5.69) →
left sidebar → *CRM → Care Command*. No deep links.
**Console:** zero errors and zero warnings across the whole pass.

---

## 03-backend-dock-8-channels.png — the dock CC-B built

Care Command (`/bizapp/action-1680`) with the full channel rail:

| Rail entry | Rendering | Why |
|---|---|---|
| ALL · 167 | lit | every conversation |
| ZALO, CALLS · 167, EMAIL, ZNS | lit | the base four, live before CC-B |
| **WHATSAPP, FB MSGR, TELEGRAM, WEB CHAT** | **dark** | the four channels CC-B added — rendered, named, and honestly unlit because vietuat has **0 connections** |

This is the data-honesty claim from the CC-B report made visible: the four
new adapters are present in the UI and dark for every real user, exactly as
`_channel_keys()` reports. A lit icon here would have been the bug.

The attention bucket beneath the (empty) wall reads *"Leads · 167 — Not yet
reached on any channel · 167 need reply"* — the P5 surface-truth model
(`has_channel_activity`) telling the truth about a tenant whose 167 leads
have never been touched on a channel.

## 04-backend-composer-lead-no-channel.png — the composer

An unclaimed lead conversation open (*Ron new contact 005 · Calls ·
unclaimed*), showing what CC-B's core touch actually changed:

- the composer footer declares **"Sends via Email"** — `ext_reply_channel`
  derived from `_capabilities()`, so the operator knows which channel a
  reply will actually leave by **before** typing;
- Vietnamese quick replies (*Chào hỏi, Bảng giá dịch vụ, Xác nhận lịch hẹn,
  Hẹn gọi lại, Ngoài khu vực phục vụ, Cảm ơn & kết thúc*) render correctly;
- the CARE panel shows the lead's status and code; the thread is honestly
  empty ("No messages yet") rather than inventing history.

No WhatsApp/Telegram/web-chat send option is offered anywhere, because no
such connection exists — the gating is state-derived, not cosmetic.

---

## Also captured: MED-1 fixed live (CC-C review, commit 6cacb76f)

The CC-C review found that a connection mid-setup could not be turned off:
`testing` only exited forward, so a tenant who registered a webhook for the
wrong bot was stuck with an ingesting connection. T106 covers it, but tests
run in a transaction as a fixture user — so it was re-proven through the
real RPC stack, as `crm`, in the browser:

```
center_begin('webchat')        → authorizing
center_webchat_enable(...)     → testing
center_disconnect(...)         → disabled      ← raised a transition error before the fix
```

`13-post-review-fix-catalogue.png` (in the CC-C pack) shows the Channel
Center loading clean after the fix deploy: all eight cards, only Telegram
and Web chat offering **Connect**, everything else honestly *"Not available
yet"* / *"Available in an upcoming update"*, ZNS rendered as a sub-line of
Zalo. Zero console errors.

**Fixture cleanup (§5.34), verified on a fresh cursor after deletion:**

```
connections | identities | messages | checks | audit_rows
          0 |          0 |        0 |      0 |         25
```

The 25 append-only audit rows are the designed survivors (`connection_id`
is `ondelete='set null'`, so deleting a connection cannot erase its
history); 19 pre-existed this pass, 6 are from the MED-1 proof above. The
catalogue was re-loaded afterwards and shows all eight channels back to
*Not connected*.
