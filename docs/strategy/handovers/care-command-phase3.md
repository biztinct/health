# Care Command — Phase 3 Handover: "Deterministic Assist" (templates + watchlist + ringing/ticker + strip completion)

**For:** Opus implementation session · **Designed/reviewed by:** Fable
**Read first:** `docs/strategy/HANDOVER-CONVENTIONS.md` (§5.45, §5.51–5.58 are from this stream)
**Binding visual spec:** `docs/care-command-center/care-command-combined.html` (template chips, watchlist badges, ringing hero, ticker)
**Prior phases:** phase1 (spine/UI) + phase2 (live channels) handovers in this folder; both live on vietuat, reviewed. Current: health_care_command 19.0.2.0.1, bridge 19.0.1.0.1, health_voip24h 19.0.2.0.1.

## 1. Why this phase

The channels are plumbed; this phase ships the POC's **always-on deterministic assist layer** —
the features that make the composer fast and the wall smart WITHOUT any AI: reply-template
chips, rule-based watchlist phrases, the live ringing hero + now-ticker, and the last missing
header-strip verbs. This is the AI-off baseline the eventual Phase-4 AI layer degrades to.

## 2. Scope (deliverables — all in `health_care_command` unless stated)

1. **Reply templates**: model `care.reply.template` (name, body text, optional channel
   selection matching `channel_primary` + "any", active, company_id, sequence). CRM managers
   manage them (simple list/form view reachable from a gear on the composer or a menuitem
   under the existing action — your call, report which). Chips render above the composer
   (POC style); clicking a chip INSERTS the body into the composer input — never sends.
   Seed 6–8 natural-VN templates as `noupdate="1"` data (greeting, price-list "price card",
   booking-confirm, callback-promise, out-of-area, polite-close). Template body is plain text.
2. **Watchlist phrases**: model `care.watch.phrase` (phrase, active, company_id), manager-
   managed, seeded with a few VN urgent phrases (`khẩn cấp`, `ngã`, `đau ngực`, `khó thở`,
   `nhập viện`, `chảy máu`). At INGEST time (zalo inbound hook + email inbound hook only),
   lowercase-substring match against the message text / email subject+preview; on hit set
   `watch_flag = True` and store the matched phrases in `watch_terms` (Char). Clearing:
   flag+terms reset when status leaves `needs_reply` (same place the missed-call flag clears).
   Urgency: `+15 if watch_flag` (new term in `_compute_urgency_score`, depends updated).
   Wall tile + list row show a small flag badge with the matched phrase (mono flat, no red
   alarm styling — this is triage, not clinical alerting). Matching is deterministic substring
   after `.lower()` — no regex config, no scoring, no NLP.
3. **Live ringing hero + now-ticker (JS-only, no new storage):** the OWL action additionally
   subscribes to the EXISTING `voip_notifications` bus channel; on a `voip_incoming_call`
   payload (keys verified §4.1) show a RINGING hero tile at the top of the wall (pulse style
   per POC) that resolves to the matching conversation (by partner_id → lead_id → normalized
   caller number via a small gated service) and opens it on click; auto-dismiss after 45s or
   when a matching `voip.call.log`-driven care_command bus event lands. The ticker is a thin
   one-line strip above the wall streaming the last ~20 LIVE events this session (client-side
   ring buffer fed by the two bus channels: "ringing 09xx…", "conversation updated", "claimed
   by X") — clicking a ticker item opens that conversation. No persistence, no history fetch.
4. **Bridge signal upgrade (`health_care_command_voip`)**: incoming `busy`/`failed`/
   `voicemail` now count as missed-like (→ `needs_reply` + `missed_call: True`) — the customer
   tried to reach us and didn't. Keep `answered` event-only.
5. **Header strip completion**: **Reminder** — service `action_reminder(conv_id, days, note)`
   schedules a `mail.activity` (todo) on the anchor record (lead if present, else partner),
   small popover in the thread header for days/note; **Consent** (clients only) — opens the
   existing backend consent records for the partner via `act_window` on `health.consent`
   domain `[('partner_id','=',partner_id)]` — SOFT dependency: render the button only when
   `'health.consent' in self.env` AND the conversation has a partner; no hard `depends`, no
   consent content rendered inside Care Command (the backend view enforces its own ACLs).
   **Take over** — the existing manager-gated `action_take_over` service gets its thread-header
   button (visible to managers on conversations owned by someone else). "Price card" ships as
   a seeded template, not a feature.
6. Tests T26–T32; deploy per §7.

## 3. Binding NON-goals

- **STILL NO AI.** No drafts, no summaries, no intent detection, no junk scores. The watchlist
  is a literal substring rule the manager typed — nothing more.
- **NO clinical content**: the Consent button only *navigates* to the existing backend view;
  never render consent/clinical fields in Care Command; no hard dependency on health_consent
  or any clinical module (grep rail stays: 0 imports of health_emr/condition/telemonitoring/
  family_message).
- **NO mail.template / ZNS template involvement** — `care.reply.template` is a plain internal
  model (avoids the health_messaging install-render gotcha entirely). Template chips insert
  text; the ONLY send path remains the existing composer send.
- **NO new channels, NO webhook/credential/config changes, NO real outbound messages.**
- **NO edits to health_voip24h / health_zalo** this phase (the ringing feature consumes the
  existing bus event as-is).
- **NO watchlist scanning of historical/backfilled data** — ingest-time only, hot-path cheap
  (one cached search of active phrases per ingest; use `ormcache` or a simple
  `search_read` — but remember §5.48: config-param-style ormcache is per-worker).

## 4. Verified plumbing (do not re-derive)

### 4.1 VoIP ringing bus (consume as-is)
`health_voip24h/services/call_handler.py:197-213` — `_sendone('voip_notifications',
'voip_incoming_call', payload)` with payload keys: `call_id`, `call_log_id`, `caller_number`,
`partner_id`, `partner_name`, `lead_id`, `lead_name`. Note the channel is the plain string
`'voip_notifications'` (not company-scoped) — subscribe alongside the existing
`care_command_{company_id}` subscription in the OWL action.

### 4.2 Seams you extend (all in `health_care_command`)
- Ingest hooks: `models/hooks.py` — `_care_ingest_zalo` (msg.text available) and
  `_care_ingest_email` (msg.subject/body available; preview via `html2plaintext`). Watchlist
  match runs INSIDE the existing savepoint-guarded ingest, passed through
  `_find_or_create_for` as new signal keys (`watch_hits: [...]`) — keep upsert semantics: set
  flag/terms on hit, never clear on a non-hit inbound.
- Flag clearing precedent: `_find_or_create_for` waiting/closed branch (clears
  `missed_call_unhandled`) — clear `watch_flag`/`watch_terms` in the same place.
- Urgency: `_compute_urgency_score` + its `@api.depends` (`models/care_conversation.py:160-187`).
- Composer + thread header: `static/src/js/care_command.js`, `static/src/xml/care_command.xml`
  (Phase-2 versions; search input pattern shows the debounce/service style to clone).
- Manager gate precedent: `action_take_over` (manager check) in `models/care_conversation.py`.
- `mail.activity` scheduling: both `crm.lead` and `res.partner` are mail.thread models —
  use `record.activity_schedule('mail.mail_activity_data_todo', date_deadline=..., summary=...,
  note=...)` with sudo AFTER `_ensure_access` + company-scoped fetch (clone `_guarded`).
- Consent model: `health.consent` (`addons/health_consent/models/health_consent.py:57`),
  installed on vietuat; guard with `'health.consent' in self.env`.
- Seed data rule: user-editable seeds ship `noupdate="1"` (templates/phrases WILL be edited by
  managers; an upgrade must not clobber them — and remember the flip side, the noupdate seed
  cutover gotcha: later XML edits to these records won't apply on upgrade).

### 4.3 vi.po
Every new string needs the §5.58 markers (`#. odoo-python` / `#. odoo-javascript`) or it
silently won't translate. Extend `i18n/vi.po` accordingly (natural Vietnamese).

## 5. Tests (T26–T32, continue the numbering)

- **T26** templates: model CRUD manager-only (user gets AccessError on create); service
  returns active templates filtered by conversation channel (+ "any"), company-scoped.
- **T27** watchlist zalo: inbound zalo message containing a seeded phrase (case-insensitive)
  → `watch_flag`, `watch_terms` contains the phrase, urgency includes +15; clean message → no
  flag; replaying the same event doesn't duplicate terms.
- **T28** watchlist email: same via the mail.message email ingest path; plain chatter note
  still ignored (T17 guard untouched).
- **T29** watchlist clears: flagged conversation → outgoing reply (status waiting) → flag and
  terms cleared (mirror missed-call clearing).
- **T30** bridge: incoming `busy` and `voicemail` → needs_reply + missed_call flag (extend
  T21's suite in the bridge module).
- **T31** reminder: `action_reminder` creates a mail.activity on the lead anchor (and on the
  partner when no lead), gated (plain user AccessError), company-scoped fetch.
- **T32** consent action: returns an act_window scoped to the partner for a client
  conversation; raises UserError when no partner; (skipTest if `health.consent` not in env —
  keeps the soft dependency honest).

Rules: §5.50 codes-not-display-text; §5.53 cr.commit patch if any CRM action is reused;
§5.56 `_flush_tracking` if you assert tracking; no HttpCase. Ringing/ticker are JS-only —
declare "browser QA required" in your report; Fable will drive it (you have no /odoo creds).

## 6. Data honesty

Templates/phrases seed real rows (report counts). The ringing hero cannot fire on vietuat
(0 voip.config — no webhook source); it ships dark until ops wires VOIP24h. Say so in the
report; do NOT simulate bus events against the live server outside tests.

## 7. Deploy (vietuat — §5.45)

1. Standard scp/chown flow; modules: `health_care_command`, `health_care_command_voip`.
2. One run: `-u health_care_command,health_care_command_voip --test-enable
   --test-tags /health_care_command,/health_care_command_voip --stop-after-init --no-http`.
3. Verify: fresh TODAY-UTC test-result line (grep by your run's pid; never trust a stale
   line), 5 procs, /web/login 200, seed counts (`select count(*) from care_reply_template;`
   etc.).
4. Bump `health_care_command` → 19.0.3.0.0, bridge → 19.0.1.1.0.

## 8. Report back

1. Test transcript (timestamped, pid) + T26–T32 mapping.
2. Where the template manager UI landed (gear vs menuitem) and why.
3. Seed rows created (templates + phrases counts, honest).
4. Screenshots you CAN take are none (no creds) — list exactly what Fable must browser-verify
   (chips insert, watch badge, ticker, ringing hero via manual bus injection in devtools,
   Reminder popover, Consent/Take-over visibility rules).
5. Any deviation declared with evidence; proposed ledger entries if fresh gotchas.

**Kickoff line for the Opus session:**
Implement `docs/strategy/handovers/care-command-phase3.md` (Care Command Phase 3 —
Deterministic Assist: reply-template chips + watchlist phrases + ringing hero/ticker + strip
completion). Read `docs/strategy/HANDOVER-CONVENTIONS.md` first (§5.51–5.58 especially) and
open `docs/care-command-center/care-command-combined.html` as the binding visual spec. Follow
the handover exactly: still NO AI, no clinical content, soft consent dependency, plain-model
templates (no mail.template), ingest-time watchlist only, tests T26–T32 green, deploy to
vietuat per §7, report back per §8. No real outbound messages, no config/credential changes.
