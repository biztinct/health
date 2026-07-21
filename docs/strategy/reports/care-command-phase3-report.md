# Care Command — Phase 3 Report: "Deterministic Assist"

**Implementer:** Opus 4.8 · **Date:** 2026-07-21 · **DB:** vietuat
**Handover:** `docs/strategy/handovers/care-command-phase3.md`
**Result:** `0 failed, 0 error(s) of 32 tests` (2026-07-21 02:28:02 UTC, pid 1940536), EXIT:0, HTTP:200.

---

## 1. What was built (file list)

All in `health_care_command` unless noted. Version → **19.0.3.0.0**; bridge → **19.0.1.1.0**.

### Deliverable 1 — reply templates
- **`models/care_reply_template.py`** (NEW) — `care.reply.template`: `name`, `body`
  (plain Text), `channel` (`any`/zalo/call/email/zns), `active`, `sequence`,
  `company_id`. A plain internal model — NOT a `mail.template` (no render-check,
  no ZNS plumbing, §5.14 avoided entirely).
- **`data/care_reply_templates.xml`** (NEW, `noupdate="1"`) — **8** seeds:
  greeting, price card, booking-confirm, callback, out-of-area, polite-close
  (all `any`) + one `zalo` (ask-phone) + one `email` (formal reply). "Price card"
  ships as a seed, not a feature (per §2.1).
- **`models/care_conversation.py`** — `_reply_templates()` (active templates for
  the conversation's channel + `any`, company-scoped, ordered) folded into the
  `get_conversation_detail` payload as `templates`, plus a public
  `get_reply_templates(conv_id)` service (group-gated) for the chips.
- **JS/XML** — a `Quick replies` chip row above the composer; clicking a chip
  **inserts** `body` into the composer (`insertTemplate`, appends with a newline)
  — never sends. Manager-only ⚙/⚑ gear buttons open the management views.

### Deliverable 2 — watchlist phrases
- **`models/care_watch_phrase.py`** (NEW) — `care.watch.phrase`: `phrase`,
  `active`, `company_id`.
- **`data/care_watch_phrases.xml`** (NEW, `noupdate="1"`) — **6** seeds: `khẩn
  cấp`, `ngã`, `đau ngực`, `khó thở`, `nhập viện`, `chảy máu`.
- **`models/care_conversation.py`** — `_match_watchlist(*texts)` (lowercase
  substring, plain company-scoped `search_read`, no ormcache → no §5.48 staleness
  surprise); `watch_flag`/`watch_terms` fields; the `+15` urgency term added to
  `_compute_urgency_score` **and** its `@api.depends` (§5.18 full-decorator rule);
  set/merge on hit and cleared alongside `missed_call_unhandled` when status
  leaves `needs_reply`; `_merge_terms` de-dups so a replay never doubles a term.
- **`models/hooks.py`** — watchlist runs at INGEST only, inbound Zalo (`msg.text`)
  and inbound email (`subject` + `html2plaintext(body)[:1000]`), passed through
  `_find_or_create_for` as `watch_hits`. Chatter notes stay excluded (T17 guard).
- **UI** — a mono-flat `watchflag` badge (grey chip, amber `ic-warn`, **no red
  alarm styling** — triage, not clinical alerting) on the wall tile, the chat-list
  row and the thread header.

### Deliverable 3 — live ringing hero + now-ticker (JS-only, no storage)
- **`models/care_conversation.py`** — `resolve_incoming_call(payload)`: gated +
  company-scoped, resolves a `voip_incoming_call` payload to an EXISTING open
  conversation (partner_id → lead_id → normalized caller number). **Never
  creates** (the call.log create-hook upserts the real row).
- **JS** — subscribes to the existing plain `voip_notifications` bus channel
  (§4.1) alongside `care_command_{company}`; on `voip_incoming_call` shows a
  pulsing **ring-hero** at the top of the wall (dedup by `call_id`, auto-dismiss
  after 45s **or** when a matching care bus event lands), opens the resolved
  conversation on click. The **now-ticker** is a client-side ring buffer (last 20
  events: "Ringing …", "Claimed by X", "Conversation updated") fed by both bus
  channels; clicking a tick opens that conversation. No persistence, no history
  fetch.

### Deliverable 4 — bridge signal upgrade (`health_care_command_voip`)
- **`models/hooks.py`** — incoming `busy`/`failed`/`voicemail` now join
  `missed`/`abandoned` as missed-like (`_MISSED_LIKE`) → `needs_reply` +
  `missed_call: True`. `answered`/`internal` stay event-only.

### Deliverable 5 — header strip completion
- **Reminder** — `action_reminder(conv_id, days, note)` schedules a
  `mail.mail_activity_data_todo` on the anchor (lead if present, else partner),
  gated by `_guarded` then `sudo` (§5.24). A small popover in the thread header
  (days + note).
- **Consent** (clients only) — `action_consent(conv_id)` returns an `act_window`
  on `health.consent` scoped to the partner. **SOFT dependency**: no `depends`,
  the button renders only when `'health.consent' in env` AND the conversation has
  a partner (`can_consent` header flag); no consent/clinical field is rendered
  inside Care Command.
- **Take over** — already wired in Phase 1 (thread top-bar, `me.is_manager` on a
  someone-else-owned conversation). No change needed; verified present.

### Cross-cutting
- **`security/ir.model.access.csv`** + **`security/care_command_security.xml`** —
  ACLs (user read-only, manager CRUD) + multi-company `ir.rule` for both new
  models.
- **`views/care_command_admin_views.xml`** (NEW) — list/form + act_window +
  manager-gated menus under CRM Center.
- **`i18n/vi.po`** — all new Python/JS/QWeb strings with the §5.58
  `#. odoo-python` / `#. odoo-javascript` markers.
- **`static/src/scss/care_command.scss`** — ticker, ring-hero (pulse), watch
  badge, template chips, reminder popover; flat mono, `hf-`/`ic-` mask icons.

## 2. Test transcript + T26–T32 mapping

`2026-07-21 02:28:02,988 1940536 INFO vietuat odoo.tests.result: 0 failed, 0 error(s) of 32 tests`

| Test | Suite | Proves | Status |
|------|-------|--------|--------|
| T1–T25 | both | Phase-1/2 suites still green | ✅ |
| **T26** | care_command | template CRUD manager-only (plain user AccessError on create); `get_reply_templates` filters by channel (any+zalo, not email), company-scoped, excludes inactive | ✅ |
| **T27** | care_command | inbound Zalo w/ seeded phrase (mixed case) → `watch_flag` + `watch_terms`; clearing flag drops urgency by exactly **15**; clean msg → no flag; replay → no dup term | ✅ |
| **T28** | care_command | inbound email (subject) match → flag/terms; a chatter NOTE is never scanned (`_match_watchlist` un-called) | ✅ |
| **T29** | care_command | outgoing reply → `waiting` → flag+terms cleared | ✅ |
| **T30** | care_command_voip | incoming `busy`/`voicemail`/`failed` → `needs_reply` + missed-call flag | ✅ |
| **T31** | care_command | `action_reminder` creates a todo activity on the lead (and on the partner when no lead), deadline today+N; plain user AccessError | ✅ |
| **T32** | care_command | `action_consent` returns a `client_id`-scoped act_window; UserError with no partner; skips if consent absent | ✅ |

## 3. Where the template manager UI landed (and why)

**Both** a manager-gated menu **and** composer gears:
- **Menu** — `CRM Center → Care Command Setup → {Reply Templates, Watchlist
  Phrases}` (manager group on every menuitem). A durable admin home that doesn't
  depend on having a conversation open — the right place to curate phrases, which
  aren't conversation-scoped.
- **Composer gears** — two manager-only icon buttons (⚙ templates, ⚑ watchlist)
  in the `Quick replies` chip row, `doAction`-ing the same act_window xmlids.
  Discoverable exactly where the chips are used.

Chips show the template **name** (concise) with the **body** as the tooltip and
the inserted text — a minor deviation from the POC (which shows body text in the
chip); names read better for a curated list of 8.

## 4. Seed rows created (honest)

`care_reply_template` = **8** · `care_watch_phrase` = **6** (SQL-confirmed on
vietuat). Both seeded `noupdate="1"` on the install company.

## 5. Deviations (declared)

1. **(BIG) `health.consent`'s patient field is `client_id`, NOT `partner_id`.**
   The handover §4.2 specified `domain [('partner_id','=',partner_id)]`; the real
   field (verified at `health_consent/models/health_consent.py:69`) is `client_id`
   (`res.partner`, `is_patient` domain). Wired to `client_id` +
   `default_client_id`; T32 asserts the `client_id` tuple. Using the handover's
   literal would have produced a broken act_window domain.
2. **Template manager UI = menu + composer gears** (handover offered "gear or
   menuitem — your call"). Rationale in §3.
3. **Chips show template name, not body** (POC shows body). §3.
4. **No live browser drive** — no `/odoo` credentials this session; the
   ringing/ticker/reminder/consent/chip surfaces are declared for Fable's browser
   pass (§7). This is the handover's own instruction (§5, §8.4).

No other deviation. No AI, no clinical content, no `mail.template`, no new
channel, no webhook/credential/config change, no real outbound message, no edit
to `health_voip24h`/`health_zalo`.

## 6. §6 Data honesty / reality check (report, don't fix)

| Item | Finding |
|------|---------|
| `care_reply_template` | **8** (seeded) |
| `care_watch_phrase` | **6** (seeded) |
| `voip.config` | **0** — VoIP un-provisioned; the ring-hero **cannot fire** on vietuat (no CDR/webhook source). Ships dark until ops wires VoIP24h. |
| `voip.call.log` | **0** — no calls ever ingested; T30's missed-like path is proven by unit tests only. |
| watch-flagged conversations | **0** — watchlist matches only NEW inbound Zalo/email at ingest; no live channel traffic has flowed (167-lead wall unchanged, Zalo OA still `draft`). Any flag will appear the moment a matching message arrives. |

The deterministic assist layer is fully installed and green; on vietuat it is
inert wherever a live channel source is required (VoIP ring, real inbound
matches) — exactly as the handover anticipated. No bus events were simulated
against the live server outside tests.

## 7. Browser QA required (Fable to drive — no creds this session)

1. **Reply chips** — open a Zalo/email conversation; the `Quick replies` row
   shows seeded chips; clicking a chip **inserts** its body into the composer and
   does NOT send; manager sees ⚙/⚑ gears that open the setup lists.
2. **Watchlist badge** — (needs a matching inbound, or set `watch_flag` on a test
   row) grey `ic-warn` badge on tile + list row + thread header, **not** red.
3. **Now-ticker** — inject a `care.conversation/update` bus event (devtools) →
   a tick appears in the top-bar strip; clicking opens the conversation.
4. **Ringing hero** — manually inject a `voip_incoming_call` payload on the
   `voip_notifications` channel in devtools → pulsing hero at the top of the wall;
   `resolve_incoming_call` links it (or shows the number); click opens / dismiss ×
   works; auto-dismiss after 45s.
5. **Reminder** — thread header `Reminder` button → popover (days + note) →
   Schedule → a `mail.activity` todo appears on the lead/partner.
6. **Consent / Take-over visibility** — `Consent` shows only on a client
   conversation (opens backend consent list scoped to the client); `Take over`
   shows only to a manager on a conversation owned by someone else.

## 8. Proposed ledger entry (fresh gotcha)

- **§5.59 — a handover-quoted field name is not ground truth; verify the target
  model's schema before wiring an `act_window` domain.** The phase-3 handover
  named `health.consent.partner_id`; the actual FHIR-modelled field is
  `client_id` (`res.partner`, `is_patient`). A domain on the wrong field is a
  silent runtime break (the view opens empty or errors), invisible to Python
  import and only caught by reading the model. Rule: for any cross-module
  `act_window`/`domain`/`default_*`, grep the target model's field definition,
  don't trust the prose. (Hit in care-command Phase 3 consent action; wired to
  `client_id`, T32 asserts it.)
