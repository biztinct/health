# Care Command — Phase 1 Implementation Report

**Module:** `addons/health_care_command` (19.0.1.0.0) · **Implemented by:** Opus 4.8
**Handover:** `docs/strategy/handovers/care-command-phase1.md` · **Date:** 2026-07-21
**Status:** SHIPPED to vietuat · installed · `0 failed, 0 error(s) of 17 tests` · `/web/login` HTTP 200

---

## 1. What was built (file list)

```
health_care_command/
  __manifest__.py                       # deps, assets, post_init_hook
  __init__.py                           # models + post_init_hook
  hooks.py                              # post_init backfill (§5.5)
  models/
    care_conversation.py                # the spine + upsert + urgency + bus + all services
    hooks.py                            # additive _inherit ingestion hooks (zalo/lead/mail/fso)
  security/
    ir.model.access.csv                 # CRM user r/w/c, manager +unlink
    care_command_security.xml           # multi-company record rule
  data/cms_sidebar_items_care_command.xml   # CMS sidebar entry (after Dashboard, NOT noupdate)
  views/care_command_actions.xml        # ir.actions.client + /odoo menu item
  static/src/js/care_command.js         # OWL client action
  static/src/xml/care_command.xml       # QWeb template (wall + chat + rail + composer)
  static/src/scss/care_command.scss     # scoped design-system clone of the POC
  static/src/css/care_command_icons.css # mask-icon data-URIs (PLAIN CSS — see gotcha §5.51)
  i18n/vi.po                            # Vietnamese catalog
  tests/test_care_command.py            # T1–T17
```

Deliverables 1–8 (§2) all present: spine + idempotent upsert + ingestion hooks; workspace/detail read
services; claim/release/take-over with race guard + chatter audit; Zalo + Email outbound reply; OWL
`care_command` action + CMS sidebar entry; bus + 60s poll; bounded idempotent backfill; T1–T17 green.

## 2. Test results (verbatim)

```
odoo.tests.result: 0 failed, 0 error(s) of 17 tests when loading database 'vietuat'
EXIT:0 · HTTP:200
```

All of T1–T17 pass. Three tests were adapted to server reality (declared, not silent):
- **T4 / T11** mock `zalo.message.action_send_message` (not `zalo.api.client`) — see deviation D3.
- **T5 / T8** wrap the `action_set_status(junk)` call with a patched `cr.commit` because the reused
  `crm.lead.action_mark_spam()` calls `self.env.cr.commit()`, which Odoo 19 forbids inside a test cursor.
- Every VoIP fixture/assertion is gated on `self.has_voip` (VoIP is not installed — deviation D1).

## 3. Backfill counts per channel on vietuat (data honesty)

Install-time `post_init_hook` log:
```
care_command backfill: created zalo=0 call=0 email=0 lead=167 (total now 167)
```

**The wall's only real data on vietuat today is 167 CRM leads.** The channel silos are empty/absent:

| Source | Rows on vietuat | Backfilled | Why |
|---|---|---|---|
| `zalo.conversation` | **0** | 0 | health_zalo installed but has zero conversations/messages |
| `voip.call.log` | n/a | 0 | health_voip24h **not installed** (see D1) |
| inbound email (`mail.message` type=email on lead/partner, 90d) | **0** | 0 | no fetchmail server configured (see §5b) |
| `crm.lead` (active/lead, phone or email, ≤90d) | 188 qualify | **167** | 21 skipped: no *valid* phone AND no email after `normalize_vn_phone` |

Lead-anchored conversations carry no channel (`channel_primary = NULL`); the UI renders them with a
neutral "Contact" glyph (never a misleading Zalo glyph) and they are excluded from per-channel counts
but included in ALL. Re-running the backfill created 0 new records (idempotent — verified, T12).

## 4. sudo() sites + the group gate protecting each

**Every public service method starts with `self._ensure_access()`** (raises `AccessError` unless the
user `has_group('health_crm.group_health_crm_user')`; manager implies user) **and company-scopes every
search** via `_company_domain()` (`company_id in env.companies.ids`). sudo is used only for
engine-internal maintenance and cross-model reads *after* the gate:

| Site (models/care_conversation.py) | Purpose | Gate in force |
|---|---|---|
| `_find_or_create_for` :257 (`self.sudo()`) | idempotent upsert — called from exception-isolated hooks (webhook/system users) as engine bookkeeping | N/A — invoked by ingestion hooks, not a user RPC |
| `_sync_next_booking` :345 (FSO read) | recompute next booking from patient FSOs | called from the fso hook / after gated services |
| `get_workspace_data` :411,:417 | list + counts over company-scoped conversations | `_ensure_access` at method top |
| `get_conversation_detail` :541 and timeline/context reads :561,:591,:612,:626,:647,:662,:676,:717,:730 | cross-model timeline/context (zalo msgs, calls, emails, relations, bookings) | `_ensure_access` at method top |
| `action_claim` :768,:778 | SQL-guarded single-write claim | `_ensure_access` |
| `action_release`/`take_over`/`set_status` :790,:803,:816,:822 | ownership + status, reuse `lead.action_mark_spam` | `_ensure_access` (+ manager check for take-over/release) |
| `action_send_zalo` :834,:837 | create outgoing `zalo.message` + send | `_ensure_access` + `zalo_conversation_id` guard |
| `action_send_email` :879,:886,:890,:893 | `message_post` threaded reply + ensure recipient partner | `_ensure_access` + recipient-email guard |
| header strip `action_book/open_client/callback/add_note/log/create_lead/escalate` :919,:928,:965,:973,:993,:1008,:1017 | passthroughs to existing crm.lead / ops_quick_booking flows | `_guarded()` = `_ensure_access` + fetch |

No clinical models are imported anywhere (grep `health_emr|health_condition|health_telemonitoring|family_message` = 0 hits in the addon).

## 5. Deviations from the handover (with evidence — not silently adapted)

**D1 — `health_voip24h` made OPTIONAL, not a hard dependency (user-approved).**
The handover §2 lists `health_voip24h` as a dependency, but it is **uninstalled on vietuat and cannot
install on Odoo 19**: `-i` fails at `health_voip24h/security/voip24h_security.xml:12` with
`ValueError: Invalid field 'category_id' in 'res.groups'` (O19 removed `category_id`; it is
`privilege_id` now). I surfaced this; the user chose to make VoIP optional. So: dropped from `depends`;
the `voip.call.log` `_inherit` **ingestion** hook was removed (can't `_inherit` a model absent from the
registry — it would crash load); every voip **read** (timeline, snippet, backfill) is guarded with
`if 'voip.call.log' in self.env`. The Calls dock channel renders but stays inert (0) until VoIP is made
O19-compatible + installed. **Follow-up to re-light live call ingestion:** re-add a
`models.Model(_inherit='voip.call.log')` create-hook (anchors partner/lead/`caller_number_normalized`;
missed→needs_reply+missed_call) — one class; the reads already fire the moment the model exists.

**D2 — Call button ships `tel:` fallback, not click-to-dial.** No trivially-invokable public
click-to-dial seam exists (and VoIP is uninstalled anyway), so the thread Call button uses a `tel:` link
+ toast, per the §7.4 "report which you shipped" instruction.

**D3 — `zalo.message.action_send_message()` is upstream-broken (report item §11.5).** The composer goes
through `action_send_message()` as mandated, but that method does `self.env['zalo.api.client']`, and
**`zalo.api.client` is NOT a registered model** — `ZaloAPIClient` (health_zalo/services/zalo_api.py:12)
is a plain Python class exposed only via `get_api_client(env)`; there is no `_name='zalo.api.client'`
anywhere. So `action_send_message()` **KeyErrors on any text send, independent of this module.**
Consequence: a real outbound Zalo reply cannot succeed on the current codebase (it surfaces the error to
the UI, honestly — no silent success). The one user-approved test send in §10.3 was therefore **not
performed** (it would fail on the upstream bug; there is also zero real Zalo data to send to). Fixing
this belongs in health_zalo (out of scope, §3 "no edits to health_zalo").

**D4 — "Mine" filter = mine + unclaimed (not owner-only).** The POC's Mine/Everyone is a display toggle
that never empties the wall; with nothing owned yet, an owner-only "Mine" would show a blank wall. So
`mine_only` filters to `owner_id = me OR unclaimed`. Everyone shows all with owner chips (`view-all`).

**D5 — Header strip conditional rendering.** Per §3 "do not render buttons with no wired behavior", the
strip renders Book·Callback·Note always; Log+Escalate only when a lead anchor exists; Lead only when
none; Client only when the partner isn't already a client; Junk always. Every rendered button is wired.

## 5b. Email reality check (§10.3b) — report, don't fix

```
fetchmail_servers               = 0     ir_mail_servers = 0
email msgs on lead/partner 90d  = 0     email msgs total 90d = 0
```

**There is no inbound mail gateway and no outgoing mail server on vietuat**, so the Email dock channel
legitimately shows ~0 and an email *reply* would fail at send (the error is surfaced verbatim, not
swallowed). To light up Email, **ops must configure**: (1) a `fetchmail.server` (IMAP mailbox) plus a
catchall/alias so inbound customer emails thread onto `crm.lead`/`res.partner`; (2) an `ir.mail_server`
(outgoing SMTP) so `action_send_email` can deliver. No mailboxes/aliases were created from module data
(§3 non-goal respected). Email reply was **not** tested against any real address.

## 6. Screenshots (browser evidence pack)

`docs/strategy/reports/care-command-phase1-evidence/`
- `01-wall-mine.png` — wall (Mine), 167 real lead conversations, channel dock (ALL 167, Zalo/Calls/Email/ZNS active, others "Coming soon"), tiles with avatar/chip/Claim/neutral Contact glyph.
- `02-chat-thread.png` — chat state: list ("UNCLAIMED · 167"), claim banner, thread header (Call / Assign to me), full Phase-1 action strip, honest "No messages yet." timeline, read-only composer ("Replies for this channel arrive in Phase 2 — use Call"), Care rail.
- `03-claim-toast.png` — after Assign-to-me: conversation moved to "NEEDS REPLY — MINE · 1", unclaimed dropped to 166, header now "owned by Mitchell Admin" + Release button. Claim round-trip proven end-to-end.

Navigation path is the real one: CMS sidebar → **Care Command** (renders directly after Dashboard for a
CRM user). QA claim was reverted via Release; fresh-cursor DB check: `owned_conversations = 0`.
Sidebar placement + client action confirmed; **no SCSS/JS console errors after the icon fix** (§5.51).

## 7. Proposed new gotcha-ledger entries (do not edit the ledger — for Fable)

- **§5.51 — Odoo's libsass mangles data-URI `url()` mask icons in `.scss`; keep them in a plain
  `.css` file.** A `.scss` full of `--m:url("data:image/svg+xml,...http://www.w3.org/2000/svg...")`
  compiles fine under dart-sass but Odoo's libsass returns a "Style compilation failed" and the whole
  page renders unstyled (old-style fallback). The repo already dodges this (advanced_pricing ships mask
  icons in `static/src/css/*.css`). Fix: put `.o_care_command .ic-*{--m:url(...)}` in a plain `.css`
  loaded before the `.scss`; keep only nesting/tokens in scss. (Hit live; care_command shipped unstyled
  until the split.)
- **§5.52 — a full-screen OWL client action must NOT use `position:absolute; inset:0` for its root.**
  Under the /bizapp CMS shell the action host isn't a positioned ancestor, so `inset:0` escapes to the
  **viewport** and the left ~215px (channel dock + first tile column) hides behind the CMS sidebar. Use
  `display:flex; width:100%; height:100%` and let it flow in the content area (crm_dashboard does).
- **§5.53 — `crm.lead.action_mark_spam()` (and `action_log_as_lead`) call `self.env.cr.commit()`**,
  which Odoo 19's test cursor forbids (`AssertionError: Cannot commit ... inside a test`). Any test that
  reuses these CRM actions must wrap the call in `with patch.object(self.env.cr, 'commit'):`.
- **§5.54 — `zalo.message.action_send_message()` is broken: it references the unregistered model
  `self.env['zalo.api.client']`** (only the plain `ZaloAPIClient` class + `get_api_client(env)` exist).
  Any text send KeyErrors. Consumers must mock `action_send_message` itself, and outbound Zalo won't
  work in production until health_zalo is fixed.

## 8. STOP-condition notes

No real outbound message was sent (Zalo send is upstream-broken per D3; email has no server per §5b; and
there is no real channel data to send to). No health_zalo/voip/crm source behaviour was modified (only
additive `_inherit` hooks + reuse of existing action methods). No PHI storage added. No
webhook/credential changes. The VoIP-optional decision and the two blocking discoveries were raised with
the user before proceeding.

## 9. Not verified / open

- Live Zalo/Email/Call data flows end-to-end (no such data/servers on vietuat — backend logic is
  test-covered, but not exercised against real channel traffic).
- Existing screens (Contacts list, Zalo chat hub) beyond "module installs cleanly + server 200": the
  additive hooks are exception-isolated (T13/T17) and the install ran the backfill over 167 real leads
  without error, but a full click-through of the legacy Contacts screen was not re-driven.
