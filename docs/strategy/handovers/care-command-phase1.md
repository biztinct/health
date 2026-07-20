# Care Command — Phase 1 Handover: Unified Work Layer (Wall + Thread, Zalo + Calls + Email, Claim)

**For:** Opus 4.8 implementation session · **Designed/reviewed by:** Fable · **Date:** 2026-07-20
**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (the gotcha ledger — §5.32, §5.44, §5.45, §5.50 are directly relevant here).
**Visual spec (binding):** `docs/care-command-center/care-command-combined.html` — the approved POC. Phase 1 implements its **wall state + chat state + channel dock + claim + header action strip + care rail (Care/History tabs)** with REAL data. Open it in a browser before writing any UI code; match its layout, tokens, and interaction model. Its inline CSS tokens/icons are the design system to clone (CSS-mask SVG icons, flat mono colors, navy #1e2a5e family — no gradients, no font-awesome, no emoji in UI chrome).

---

## 1. Context (why)

Sales staff work from a flat `crm.lead` Contacts list with no channel integration, while `health_zalo` (OA conversations/messages/webhooks/bus) and `health_voip24h` (CDR/recordings/matching/popup) already exist as silos. Care Command is the single omnichannel entry point: a **heat wall** for triage that opens into a **messenger thread** per person, with identity/booking context and claim/ownership. The direction was chosen by the user after a 3-option design study; AI is explicitly **out of Phase 1** (the org may be AI-averse; AI arrives later as a config-gated layer — do not build any AI hooks now).

Phase 1 = **unified read + work layer**: canonical conversation spine over existing channel data, the OWL workspace, claim, filters, and Zalo reply. It must not disturb any existing flow — the current Contacts screen stays untouched and fully functional.

## 2. Scope

New addon **`addons/health_care_command`** (depends: `base`, `web`, `mail`, `bus`, `health_base`, `health_crm`, `health_zalo`, `health_voip24h`, `health_fieldservice`, `health_cms_sidebar`; optional-safe reference to `health_messaging` — see §6.4).

Deliverables:
1. `care.conversation` work-item model + idempotent upsert + ingestion hooks (Zalo, VoIP, lead, **email via Odoo's native mail rails**).
2. Read services: workspace payload (wall/list + channel counts) and conversation detail (merged cross-channel timeline + care context).
3. Claim / release / take-over with race guard and audit.
4. Outbound reply from the composer: **Zalo** (existing send path) and **Email** (`message_post` threaded reply).
5. OWL client action `care_command` (wall ↔ chat states per the POC) + CMS sidebar entry directly after the CRM Dashboard.
6. Bus live updates + 60s polling fallback.
7. Backfill init for existing data (bounded).
8. Tests (§9) green; deployed to vietuat (§10).

## 3. Binding NON-goals (do not build)

- **NO AI anything**: no drafts, no intent detection, no summaries, no junk scoring, no provider config, no "AI trace" tab (rail has Care + History tabs only in Phase 1). No placeholder AI pill in the top bar.
- **NO clinical content in the workspace**: never surface clinical notes, EMR, vitals, NEWS2/risk fields, or `health.family.message` bodies. Timeline = channel messages, calls, ZNS delivery events, booking lifecycle only.
- **NO WhatsApp / FB Messenger / Telegram / webchat adapters.** The channel dock renders Zalo, Calls, **Email**, ZNS as active; render the other channels as disabled placeholder buttons (`opacity .4`, tooltip "Coming soon"), counts hidden.
- **NO mailbox provisioning in code.** Email ingestion consumes whatever `mail.message` email rows Odoo's gateway already creates. Configuring `fetchmail.server` / catchall / aliases on vietuat is an ops step: check what exists (§10), document, report honestly — do not create mail servers or aliases from module data.
- **NO live-ringing tile / live call controls** (Phase 2; missed/completed calls DO appear in wall + timeline).
- **NO watchlist/safety phrase engine** (Phase 2). No composer templates picker (Phase 2) — plain text send only.
- **NO edits to `health_zalo` / `health_voip24h` / `health_crm` behavior.** Only additive `_inherit` hooks that call into the new module; if a hook fails it must never break the host module's flow (wrap in try/except with logger, §6.2).
- **NO deletion/migration of any source records.** `care.conversation` references sources; it never owns message content.
- Do not render header-strip buttons that have no wired behavior (drop Price card / Reminder / Consent buttons from the strip until Phase 2; see §7.4 for the Phase-1 button set).

## 4. Verified plumbing facts (do NOT re-derive; cite = file:line)

**Zalo**
- `zalo.conversation`: `zalo_user_id` (models/zalo_conversation.py:29), `zalo_phone_number` (:43), `partner_id` (:49), `unread_count` (:82), `state` active/archived/blocked (:89), `last_message_date` (:101).
- `zalo.message`: `direction` incoming/outgoing (models/zalo_message.py:45), `message_type` (:50), `text` (:61), `sent_date` (:87), `delivered_date` (:93), `read_date` (:96). Outbound send = `zalo.message.action_send_message()` (models/zalo_message.py:152-221) which calls `zalo_api.send_text_message(config, message_data)` (services/zalo_api.py:182). **Composer must go through `action_send_message()` — never call the API service directly.**
- Incoming-message bus: `services/message_handler.py:256` — `self.env['bus.bus']._sendone(channel, 'zalo.message', payload)` on channel `zalo_notification_{company_id}`.

**VoIP24h**
- `voip.call.log` (models/voip_call_log.py:17): `direction` (:46), `call_type` answered/missed/abandoned/… (:52), `caller_number_normalized` (:66, stored compute), auto-matched `partner_id` (:166) and `lead_id` (:172). Webhook → `services/call_handler.py:67` `handle_call_started()` → `process_call_record(...)`. Bus precedent: call_handler.py:202-206 `_sendone('voip_notifications', 'notification', message)`.

**CRM lead actions** (models/crm_lead.py)
- `action_convert_to_booking()` :1701 — opens OWL client action `ops_quick_booking` with `lead_id` (+ optional `patient_id`) in context. **Book button reuses this.**
- `action_log_as_lead()` :1966 — sets `contact_status='lead'`, returns activity-schedule wizard action.
- `action_escalate_contact()` :2137 — escalation wizard, `default_escalation_type='transfer'`.
- `action_mark_spam()` :1933 — `contact_status='spam'`, `is_spam_caller=True`.

**OWL client-action + sidebar precedent (clone exactly)**
- JS: `registry.category("actions").add("crm_dashboard", CrmDashboard)` — health_crm/static/src/js/crm_dashboard.js:518.
- `ir.actions.client` record: health_crm/views/crm_center_menus.xml:6-11 (tag `crm_dashboard`, target `current`).
- Assets: health_crm/__manifest__.py:96-151 under `web.assets_backend`.
- Sidebar item: health_cms_sidebar/data/cms_sidebar_items_crm.xml:4-12 (`item_crm_dashboard`: `section_id` ref `section_crm`, `action_xmlid`, `action_tag`, `icon`, `sequence`). RBAC via `role_ids` M2M → `access.role` (health_cms_sidebar/models/cms_sidebar_item.py:27).

**Identity / partner / phone**
- `res.partner`: `is_patient` (health_base/models/res_partner.py:21), `patient_code` (:30), `primary_facility_id` (:199); `zalo_number` (health_crm/models/res_partner.py:47), `facebook_profile` (:52).
- `health.client.relation` (health_crm/models/health_client_relation.py:16): `client_id` (:22), `representative_id` (:31), `role` caregiver/payer/referrer/emergency_contact/legal_guardian/client_representative (:59), `is_primary` (:86).
- `normalize_vn_phone(value)` — health_base/models/phone_utils.py:7. **Raises ValidationError on garbage — always wrap calls on inbound external data (established gotcha from health_messaging).**

**Bookings**
- `health.fieldservice.order` (health_fieldservice/models/health_fieldservice_order.py:80); `state` draft/confirmed/assigned/in_progress/completed/completed_pending_invoice/cancelled/closed (:45-55); `patient_id` domain `[('is_patient','=',True)]`; `scheduled_datetime` is the booking datetime field.

**Email (Odoo core rails — standard, not repo-specific)**
- Inbound: `fetchmail.server` (IMAP/POP poll) → mail gateway (`mail.thread.message_process`) routes by alias/catchall/references → creates `mail.message` rows with `message_type='email'` on the target record (`crm.lead` inherits `mail.thread`, so lead-bound emails thread onto the lead automatically; replies thread via `References`/`Message-Id`).
- `mail.message` key fields: `message_type`, `model`/`res_id`, `author_id`, `email_from`, `subject`, `body` (html), `date`, `subtype_id`, `partner_ids`.
- Outbound threaded reply: `record.message_post(body=..., message_type='comment', subtype_xmlid='mail.mt_comment', partner_ids=[recipient])` — Odoo emails the recipient partner and keeps the thread (In-Reply-To) intact. Requires a configured outgoing mail server (`ir.mail_server`) — check on vietuat, do not assume.
- Direction rule for timeline/status: `message_type='email'` = inbound (came through the gateway); an outbound reply we post is `message_type='comment'` authored by an internal user with email notification — treat author `user_ids` non-empty as outgoing.

**Groups:** health_crm/security/health_crm_security.xml defines the healthcare CRM groups — reuse them (user + manager); create no new groups.

## 5. Data model

### 5.1 `care.conversation` (`models/care_conversation.py`)
Thin work-item spine. One record per **person-ish anchor**. Never stores message bodies.

```
_name = "care.conversation"; _inherit = ["mail.thread"]; _order = "urgency_score desc, last_event_at desc"
partner_id        M2O res.partner (index)          # client or representative when known
lead_id           M2O crm.lead (index)
zalo_conversation_id  M2O zalo.conversation (index, unique when set)
phone_normalized  Char (index)                     # via normalize_vn_phone, best-effort
email_normalized  Char (index)                     # lower().strip() of the counterparty email, best-effort
display_name_c    Char                             # computed-stored: partner > lead > zalo name > email > phone
channel_primary   Selection [('zalo','Zalo'),('call','Calls'),('email','Email'),('zns','ZNS')]  # last inbound channel
status            Selection [('needs_reply','Needs reply'),('waiting','Waiting'),
                             ('junk_suspect','Junk?'),('closed','Closed')]  default needs_reply, tracking=True
owner_id          M2O res.users (index, tracking=True)
claimed_at        Datetime
unread_count      Integer                          # maintained by hooks (zalo unread + unhandled missed calls)
last_inbound_at   Datetime
last_event_at     Datetime (index)
next_booking_at   Datetime                         # maintained: partner's next non-cancelled FSO scheduled_datetime
urgency_score     Integer, computed-stored (see 5.3)
company_id        M2O res.company, default env.company, required
```
Constraints: SQL partial unique index on `zalo_conversation_id` where set; Python `_check_anchor` — at least one of partner_id / lead_id / zalo_conversation_id / phone_normalized must be set.

### 5.2 Idempotent upsert — `_find_or_create_for(anchor_vals)`
Match precedence (first hit wins): `zalo_conversation_id` → `partner_id` → `lead_id` → `phone_normalized` → `email_normalized`. On match: update `last_event_at`, `last_inbound_at` (if inbound), `channel_primary`, `unread_count`, upgrade anchors (e.g. fill partner_id when a later signal identifies it — **fill only; never overwrite a set partner_id/lead_id**; conflicting signal → log + skip, identity changes are human decisions). On miss: create. Must be safe under webhook retries (same event twice → one record, no duplicate state bump).

### 5.3 `urgency_score` (deterministic, documented in code)
`score = 0; +40 if status=='needs_reply'; +30 if next_booking_at within 24h; +15 if unread_count>0; +10 if a missed call today is unhandled; +min(20, hours_since(last_inbound_at) when needs_reply)`; junk_suspect forces score 0. Wall tile size thresholds (frontend): score≥60 → large (2×2), ≥30 → medium, else small; dim when waiting/junk.

### 5.4 Ingestion hooks (additive `_inherit`, `models/hooks.py`)
- `zalo.message.create()` → after super, for incoming: upsert conversation (anchor zalo_conversation_id; partner from `zalo.conversation.partner_id`; phone from `zalo_phone_number` normalized best-effort), `status='needs_reply'`, bump unread/last_inbound. For outgoing: `status='waiting'`, zero unread.
- `voip.call.log.create()` → upsert (anchors from `partner_id`/`lead_id`/`caller_number_normalized`), `channel_primary='call'`; `call_type='missed'` on incoming → `needs_reply` + unread bump; answered → event-only bump.
- `crm.lead.create()` → upsert when phone or email present (anchor lead_id + phone_normalized + email_normalized from `email_from`).
- `mail.message.create()` → **HOT PATH: exit in the first two lines for anything that isn't `message_type=='email'` with `model in ('crm.lead','res.partner')`** (every chatter note in the whole system passes through here — the guard must be a cheap field check, no searches before it). For qualifying inbound emails: upsert (anchor lead_id/partner_id from model+res_id, email_normalized from `email_from`), `channel_primary='email'`, `status='needs_reply'`, bump unread/last_inbound. Outgoing replies flip status via `action_send_email` (§6.4), not via this hook.
- `health.fieldservice.order` create/write on `scheduled_datetime|state` → recompute `next_booking_at` for the patient's conversation if one exists (cheap targeted search, no cron).
- **Every hook body wrapped**: `try/except Exception: _logger.exception(...)` — a Care Command bug must never block a Zalo webhook, call log, or lead creation. Tests assert this (T13).

### 5.5 Backfill (`post_init_hook`)
Create conversations for: active `zalo.conversation` with `last_message_date` ≥ 30 days ago; `voip.call.log` last 30 days (missed incoming first); inbound `mail.message` emails on `crm.lead`/`res.partner` last 30 days; `crm.lead` with `contact_status in ('active','lead')` and a phone or email, created ≤ 90 days. Idempotent (re-running the hook creates nothing new). Log a one-line count summary per channel.

## 6. Services (model methods on `care.conversation`, called from OWL via `orm.call`)

All service methods: `@api.model`, start with an explicit group gate (`self.env.user.has_group('<health_crm user group xmlid>')` else `AccessError`), and company-scope every search. Where cross-model reads need `sudo()`, keep the sudo scope minimal and comment why (pattern: portal/pwa scoped-sudo precedents in the ledger).

### 6.1 `get_workspace_data(channel=None, mine_only=False)`
Returns dict: `conversations` (open ones, capped 200, ordered per `_order`; each: id, display name, avatar initials, chips [client code / lead status / new / junk], channel_primary, status, owner {id, name, initials}, unread, times, urgency tier, reason line (deterministic: "Booking in Xh", "Missed call — callback due", "New lead · first message", "Waiting on customer"), snippet (last inbound `zalo.message.text` truncated 120 chars — calls: "Missed call · rang Xs")), `channel_counts` {channel: {total, needs}}, `team` (per CRM user: open count, needs count — the dock strip), `me`.

### 6.2 `get_conversation_detail(conv_id)`
Returns `header` (name, chips, relation line via `health.client.relation` when partner is representative or patient — "Daughter of X · verified" style), `timeline`, `context`, `capabilities` {can_reply_zalo: bool, can_reply_email: bool}.
**Timeline merge** (read-time, no storage): zalo.message (both directions; text + dates + delivery state), voip.call.log (event cards: direction, call_type, duration, recording available flag — no audio streaming in Phase 1, "recording available" text only), **email cards** from `mail.message` on the lead/partner (inbound emails + our posted replies per the §4 direction rule; render `subject` bold + plain-text body preview ≤ 300 chars via `html2plaintext` — never raw HTML into the DOM), `health.outbound_message` rows for the partner/fso if module installed (§6.4), FSO lifecycle (created/rescheduled/completed within timeline window) — merged, sorted by timestamp asc, capped last 100 events, day separators computed frontend.
**Context payload**: patient block (patient_code, age if birthdate set, area from catchment/vietnamese_address — best-effort, missing = omit), relations (from health.client.relation), bookings (next 1 + last 3: service_type, scheduled_datetime, state, lifetime count), lead block (contact_status, unique_contact_code) when lead anchor.

### 6.3 Claim / ownership
- `action_claim(conv_id)`: single SQL-guarded write — `search([('id','=',conv_id),('owner_id','=',False)])` then write owner+claimed_at on that recordset; if empty → return current owner name so the UI toasts "Already claimed by X" (no exception). mail.thread tracking gives the audit line for free.
- `action_release(conv_id)`: owner or manager only.
- `action_take_over(conv_id)`: manager group only.
- `action_set_status(conv_id, status)`: junk_suspect/closed/needs_reply; marking junk when `lead_id` set also calls `lead.action_mark_spam()` (reuse, :1933).

### 6.4 Outbound replies
**Zalo — `action_send_zalo(conv_id, text)`**: guard conversation has `zalo_conversation_id` + CRM group. Create `zalo.message` (outgoing, text) on that conversation then call its existing `action_send_message()` (zalo_message.py:152). Return the created message payload for optimistic-render replacement. On send failure propagate the error message to the UI (no silent success — conventions: report honestly).
**Email — `action_send_email(conv_id, text)`**: guard conversation has a lead/partner anchor AND a recipient email (`lead.email_from` or `partner.email`) + CRM group. Target record = lead if set else partner. Ensure a recipient `res.partner` exists (lead without partner: `mail.thread` handles suggested recipients; if needed use `partner_ids` resolved via `find_or_create` on the email — comment the choice). Then `record.message_post(body=Markup escape of text, message_type='comment', subtype_xmlid='mail.mt_comment', partner_ids=[...])`. Set conversation `waiting`. If no outgoing mail server is configured, surface the error to the UI verbatim — do not swallow. Subject: reply threading is automatic; do not invent subjects for replies (only a new-thread email gets `subject='Việt Úc Care'`+context, and new-thread email is NOT in Phase 1 — reply-only).
**Composer channel choice**: the composer sends on `channel_primary` (Zalo if the conversation is Zalo-anchored, else email if capability). Show the active send channel in the composer meta line exactly like the POC. One channel per send; no cascade logic in Phase 1.
`health_messaging` is referenced ONLY read-only in timelines; guard with `if 'health.outbound_message' in self.env` so the module stays installable without it.

### 6.5 Bus
On `care.conversation` create/write of {status, owner_id, unread_count, last_event_at}: `_sendone(f'care_command_{company_id}', 'care.conversation/update', {id, ...small payload})` (clone zalo message_handler.py:256 pattern). Frontend subscribes (clone health_zalo bus service js), patches state in place; plus `setInterval` 60s full `get_workspace_data` refresh as fallback. Debounce bus-triggered refetches (≥2s).

## 7. Frontend (OWL client action `care_command`)

Clone the crm_dashboard registration chain exactly: js `registry.category("actions").add("care_command", CareCommand)` + `ir.actions.client` (tag `care_command`) + manifest `web.assets_backend` entries + `cms.sidebar.item` in module data (section ref `health_cms_sidebar.section_crm`, sequence = Dashboard's +1, `action_tag`/`match` = `care_command`, icon consistent with sidebar's icon set).

Structure (match POC exactly; all styles scoped under a root class `.o_care_command`):
1. **Channel dock**: ALL / Zalo / Calls / Email / ZNS active with counts (red badge when needs>0); WhatsApp/Messenger/Telegram/Web chat rendered disabled ("Coming soon" tooltip). Click = filter (client-side refetch with `channel` arg).
2. **Top bar**: back-to-Wall (chat state), title, Mine/Everyone toggle (Everyone shows owner initials chips on tiles + unclaimed emphasis), New Contact button → existing new-contact action from the Contacts screen (find its action xmlid in crm_center_views/menus and reuse). **No ticker in Phase 1** (needs live event stream depth — Phase 2). **No AI pill.**
3. **Wall state**: grid of tiles per POC (size from urgency tier §5.3; amber dashed + Claim button when unowned; junk tiles dim). Tile click → chat state.
4. **Chat state**: list (sections: Needs reply — mine / Unclaimed / With teammates / Waiting / Junk?) | thread | care rail.
   - Thread header: avatar/name/chips/relation line; right: **Call** button → existing click-to-dial affordance if trivially invokable, else `tel:` link fallback + toast (report which you shipped); **Assign to me / Take over** per §6.3.
5. **Header action strip** (Phase-1 set only): `Book · Callback · Note · Log │ Lead · Client (non-client anchors) │ Escalate · Junk`.
   - Book → `action_convert_to_booking()` when lead_id else open `ops_quick_booking` client action with patient context (mirror :1701's action dict).
   - Callback → `mail.activity` (call type) on the lead (or partner) due today via the standard activity wizard.
   - Note → log note on `care.conversation` chatter (internal, appears in timeline as internal-note event).
   - Log → `action_log_as_lead()` when lead; Lead/Client/Escalate/Junk → §4 actions / §6.3.
6. **Care rail**: tabs **Care** (relation diagram when relation known, snapshot kv rows, bookings NEXT/DONE + lifetime count) and **History** (the same merged timeline, compact). No AI trace tab.
7. **Composer**: enabled when `can_reply_zalo` OR `can_reply_email` (meta line shows which channel the send goes out on, per §6.4); otherwise disabled input with reason ("Replies for this channel arrive in Phase 2 — use Call"). Enter/send → §6.4; optimistic bubble with pending state → replace on ack, error state on failure (email server errors shown verbatim).
8. Empty/loading/error states for every pane (conventions: explicit states, no blank panes).

## 8. Safety rails

- Additive-only inherits; every ingestion hook exception-isolated (§5.4). Zero behavior change tolerated in existing screens — smoke-check Contacts list + Zalo chat hub + VoIP popup after install.
- Service layer: group-gated, company-scoped, minimal-sudo with comments; **no clinical models imported anywhere** in the addon (grep-check `health_emr|health_condition|health_telemonitoring|family_message` = 0 hits).
- `normalize_vn_phone` always try/except (garbage inbound data is normal).
- No new `noupdate=1` records except the sidebar item (ledger §noupdate cutover — keep sidebar item updatable, i.e. NO noupdate flag).
- Frontend: no external assets; icons as CSS-mask data URIs (copy from POC); reduced-motion respected.
- Don't touch `pwa_templates.xml`/PWA (not in scope → no version bump needed).

## 9. Tests (`tests/test_care_command.py`, TransactionCase; no HttpCase → keep `--no-http`; mind ledger §5.32/§5.50 — assert codes/ids, not display strings)

1. **T1 upsert idempotency**: same zalo message hook fired twice → exactly one conversation, one state bump.
2. **T2 anchor precedence**: existing conversation by phone; later zalo message with same phone + zalo_conversation → same record, zalo anchor filled, partner not overwritten.
3. **T3 partner fill-not-overwrite**: conversation with partner A; hook with conflicting partner B signal → partner stays A, warning logged.
4. **T4 status machine**: incoming zalo → needs_reply+unread; outgoing send → waiting+unread 0; missed call → needs_reply.
5. **T5 urgency**: booking in 12h + needs_reply ≥ 60 (large tier); waiting-only < 30; junk_suspect = 0.
6. **T6 claim race**: two users claim same conversation → exactly one owner; second gets "already claimed" payload, no exception.
7. **T7 take-over**: plain user cannot take over an owned conversation (AccessError); manager can.
8. **T8 junk**: `action_set_status(junk_suspect→…)` with lead → lead `contact_status='spam'` + `is_spam_caller` True.
9. **T9 timeline merge**: seed 2 zalo msgs + 1 missed call + 1 FSO → detail timeline sorted asc, all 4 kinds present, no clinical keys in payload (assert on serialized keys).
10. **T10 scoping**: user outside CRM group calling `get_workspace_data` → AccessError; other-company records absent from results.
11. **T11 zalo send path**: `action_send_zalo` creates outgoing zalo.message and calls `action_send_message` (patch/mock the API service; assert conversation flips to waiting).
12. **T12 backfill idempotent**: run post_init logic twice → counts identical.
13. **T13 hook isolation**: monkeypatch upsert to raise → `zalo.message.create` still succeeds.
14. **T14 channel counts**: workspace counts match seeded fixtures per channel and needs flag (include an email fixture).
15. **T15 email ingestion**: create an inbound `mail.message` (`message_type='email'`) on a lead → conversation upserted with `channel_primary='email'`, needs_reply, email_normalized set; same message id processed twice → one conversation (gateway retries happen).
16. **T16 email reply**: `action_send_email` on a lead conversation → `message_post` called with `mail.mt_comment` + recipient partner (assert via posted message), conversation flips to waiting; conversation with no recipient email → clean UserError, no post.
17. **T17 hot-path guard**: creating a plain chatter note (`message_type='comment'`) on an unrelated record creates NO conversation and performs NO care_command searches (assert conversation count unchanged; keep the guard testably cheap — first-line field checks only).

## 10. Deploy / verify (vietuat — per standard workflow)

1. `scp` addon to `/tmp`, `sudo cp -r` into addons path with odoo ownership.
2. **§5.45**: no concurrent odoo-bin during upgrade. `sudo -u odoo odoo-bin -d vietuat -u health_care_command --stop-after-init --no-http` (plus test run with `--test-enable --test-tags /health_care_command`), then restart service.
3. Verify: CMS sidebar shows "Care Command" after Dashboard for CRM users (and NOT for a non-CRM role); wall renders with backfilled real conversations; open a real Zalo conversation → timeline shows history; claim/release round-trip; send a Zalo reply to a **test** conversation only (confirm with the user before any real outbound send — STOP condition); Contacts screen and Zalo chat hub unchanged.
3b. **Email reality check (report, don't fix)**: query `fetchmail.server` and `ir.mail_server` on vietuat, and count `mail.message` rows with `message_type='email'` on leads/partners (last 90 days). If no incoming server exists, the Email dock channel will legitimately show ~0 — state this plainly in the report with the exact counts, and list what ops must configure (IMAP mailbox + catchall/alias) to light the channel up. Email reply testing: only against an internal/test address, never a real customer.
4. Report honestly per conventions: test tallies (0 failed of N), what was NOT verified, data-honesty notes (how many real conversations backfilled per channel).

## 11. Report back to Fable

1. Test results (exact counts) + any skipped/deferred test with reason.
2. Backfill counts per channel on vietuat.
3. The exact sudo() sites introduced (file:line each) + the group gate protecting each.
4. Any deviation from this spec (seam didn't exist as described, renamed field, etc.) — deviation + evidence, don't silently adapt.
5. Anything about `zalo.message.action_send_message` behavior that surprised you (window limits, config requirements, error shapes).
5b. Email reality check results (§10.3b): fetchmail/ir.mail_server presence, inbound email counts, what ops must configure.
6. Screenshots: wall (Mine + Everyone), chat state with a real Zalo thread, channel filter active, claim toast.
7. New gotchas → propose ledger §5.5x entries; do not edit the ledger yourself, list them in the report.

**STOP conditions:** any real outbound message beyond one user-approved test send; any need to modify health_zalo/voip/crm source behavior (not inherit); anything requiring new PHI storage; webhook/credential changes.

---

## Kickoff line (paste into the Opus session)

Implement `docs/strategy/handovers/care-command-phase1.md` (Care Command Phase 1 — unified work layer, channels: Zalo + Calls + Email + ZNS events). Read `docs/strategy/HANDOVER-CONVENTIONS.md` first and open `docs/care-command-center/care-command-combined.html` in a browser as the binding visual spec. Follow the handover exactly: new addon `health_care_command`, additive-only hooks, no AI, no clinical content, tests T1–T17 green, deploy to vietuat per §10 (including the §10.3b email reality check), and report back per §11.
