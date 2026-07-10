# Handover: PWA Family Messaging — `health_pwa_family` (+ sanctioned PWA 1.10.0)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger now 30 entries — read all, §30 is new). This phase
closes the loop FB-044 opened: families can now write to the care team,
but only desk coordinators can answer (backend inbox), and the nurse's
PWA bell shows a **blank, undismissable-looking card** for the new
`family_message` type (documented debt, health_family_messages
QA_LIVE.md "PWA bell" + "Review fixes" sections). This phase delivers:

1. the proper **bell card** for `family_message` (the ONE sanctioned
   `health_pwa` edit, with the **PWA 1.10.0 bump** this time);
2. a **visit-context family-messages panel** in the PWA so the field
   nurse can read and reply to the patient's family thread;
3. **FB-047 one-tap post-visit family update** — nurse composes a short
   human update at visit completion, fanned out to eligible relations.

## 0. Scope & non-goals

**Non-goals (binding):** family portal/login (FB-001); staff↔staff chat;
attachments/photos; websockets (poll/refetch is fine); LLM drafting;
ANY change to the backend ops inbox or the append-only model semantics;
no new master switch (`health_family_messages.enabled` gates everything
here); Zalo Mini App; no full "Messages" tab/router surgery in the PWA —
the panel is visit-context DOM augmentation (daystrip/scribe class).

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Bell internals (health_pwa/static/src/js/app.js)**: badge =
  `state.pendingAssignments.length` (:520); panel v-for `.notif-card`
  with `:class="'notif-card--' + notif.type"` (:541); `<template v-if>`
  branches for `assignment` (:544), `cancelled` (:566), `rescheduled`
  (:584, ends :606) — **no v-else**, so unmatched types render an empty
  card with NO dismiss button. `dismissNotification(id)` POSTs
  `/health_pwa/api/notifications/<id>/dismiss` (api.py:2145, flips
  `is_read`). Pending feed `/health_pwa/api/notifications/pending`
  (api.py:2070) returns ALL unread `health.pwa.staff.notification` rows
  regardless of type — `family_message` rows DO arrive with
  `patient_name`, `fso_id`, `fso_name`, `message` populated
  (health_family_messages/models/health_family_thread.py
  `_notify_inbound`). `navigate` is in template scope (used by other
  cards' handlers).
- **Bell-row lifecycle (already shipped, review fix c2553aa3)**: rows
  carry `family_thread_id`
  (health_family_messages/models/pwa_staff_notification.py) and
  `thread.action_mark_read()` clears them. Your card's dismiss button
  gives the nurse the direct path; both must coexist.
- **PWA version bump = 5 spots in health_pwa/views/pwa_templates.xml**:
  `pwa_asset_version` t-set (:9), `version:` (:246), `PWA_SW_VERSION`
  (:365), SW header comment (:851), `CACHE_VERSION` (:854) — all →
  `1.10.0`. **Co-resident pin tests hard-assert 1.9.0 and WILL fail**:
  health_pwa_daystrip/tests/test_daystrip.py:304-308 and
  health_scribe/tests/test_scribe.py:405-410 — update them to 1.10.0 in
  this phase (they exist to force exactly this conscious step).
- **Child-module PWA pattern (clone daystrip)**: assets injected via
  xpath-inherit of `health_pwa.app_shell`
  (health_pwa_daystrip/views/pwa_shell_inherit.xml — css link + script
  tag with `?v=#{pwa_asset_version}`); logic is a plain-JS IIFE (no
  Vue), data seam = **fetch-wrap** on the API response the target screen
  already loads (daystrip.js:1-30 explains why fetch-wrap beats
  MutationObserver). The visit screen loads
  `GET /health_pwa/api/fso/<int:order_id>` (health_pwa/controllers/
  api.py:394) — wrap that to learn the current order/patient. Child
  modules add routes under `/health_pwa/api/fso/<id>/...`
  (health_scribe/controllers/api.py:49, health_evv/controllers/
  evv_api.py:142+ precedents: `auth='user'`, sudo inside, explicit
  employee-scope checks).
- **Thread/message model (health_family_messages)**: thread
  `_get_or_create(patient, relation)` idempotent sudo;
  `post_family_message` is the INBOUND path (do not touch);
  `action_send_reply` (health_family_thread.py) is the ops OUTBOUND
  path — it now (post-review) checks `messaging_enabled`, creates the
  'out' row, calls `action_mark_read` (which ALSO clears the PWA bell
  rows), then `_send_reply_zns` (purpose `family_message_reply`,
  template param default '' ⇒ silent, dedup `famreply-<t>-<m>`).
  Messages are append-only (§5.17) with the cascade-parent guard (§30) —
  your endpoints only ever CREATE.
- **Eligibility**: `_eligible_relations(fso, require_medical=False)`
  (health_family_link/models/health_family_link.py:115-137) =
  `receives_visit_updates` AND `check_consent(patient,'data_sharing')`.
  FB-047 fans out to exactly this set.
- **Nurses have NO ACL** on thread/message (by v1 design — backend inbox
  stays ops-only). PWA endpoints therefore run sudo with explicit scope
  checks, like every `/health_pwa/api` route (resolve employee via
  `user_id` like api.py:2075; §5.24 sudo employee reads).
- **Master switch**: `health_family_messages.enabled` (default False on
  vietuat). `thread.messaging_enabled` compute reads it. When off, the
  token page composer is hidden and `action_send_reply` raises — your
  endpoints and JS must go equally dark.
- Vietnamese-first labels, mono colors, inline SVG (no emoji, no
  font-awesome); glove/sunlight compat via `--touch-target` +
  `html.vu-glove` / `html.vu-sunlight` rules (daystrip.css precedent).

## 2. Architecture

New module `health_pwa_family`, depends
`['health_family_messages', 'health_pwa']`. Plus TWO sanctioned edits:
`health_pwa` (app.js bell card + 5-spot version bump) and the two pin
tests (daystrip/scribe). Nothing else outside the new module.

### 2.1 Bell card (the app.js edit — keep it ~25 lines)

After the `rescheduled` template (app.js:606) add
`<template v-else-if="notif.type === 'family_message'">`: header = badge
"Tin nhắn gia đình (Family message)" + dismiss ×; body = patient_name
row + `notif.message` (the preview text the server already builds);
actions = OK-dismiss button (clone the cancelled card's, app.js:600-605)
plus, when `notif.fso_id`, a "Xem (View)" button that navigates to the
order detail route (clone how existing handlers call `navigate`).
Do NOT add a generic v-else (an unknown future type should stay a
conscious decision, not silently render). New CSS class
`notif-badge-family` in the new module's css (mono flat color).

### 2.2 Visit-context messages panel (fammsg.js IIFE, new module)

- fetch-wrap `GET /health_pwa/api/fso/<id>` (daystrip seam) to learn the
  current order id/patient; when the response arrives AND messaging is
  enabled (see endpoint below), inject a "Tin nhắn gia đình" collapsible
  section into the order-detail screen (DOM augmentation, own
  `.fammsg-*` classes only).
- `GET /health_pwa/api/fso/<int:order_id>/family_messages` (new,
  `auth='user'`): returns `{enabled, threads: [{thread_id, relation
  label, messages: [{direction, body, author, when}]}]}` for the visit's
  patient. Server-side scope check (BINDING): resolve the caller's
  employee; require an assignment linking that employee to THIS order
  (any state except cancelled) — else 403-style empty. `enabled=False`
  (master switch off / no eligible relations) ⇒ the JS renders nothing.
- `POST /health_pwa/api/fso/<int:order_id>/family_messages/reply`
  (`auth='user'`, params thread_id, body): same scope check + verify the
  thread belongs to this order's patient; then reply **through a
  factored model method** — extract the body of `action_send_reply` into
  `thread._post_team_reply(body, author_user)` (creates 'out' row,
  mark-read + bell-clear, ZNS ping) and make `action_send_reply` a thin
  wrapper (reply_text handling + UserErrors stay in the wrapper).
  Reuse `_sanitize_body` (length cap + HTML strip) — it already raises.
- Reading the panel marks nothing (read_by_family is family-side;
  read_by_ops flips only on reply/mark-read — leave the ops semantics
  alone).

### 2.3 FB-047 one-tap post-visit update

- On the order-detail screen when the visit is completed/completing
  (reuse the state the fetched fso payload exposes), the panel shows
  "Gửi cập nhật cho gia đình (Send family update)": 3 canned VN quick
  phrases (tap to prefill, editable) + free text.
- `POST /health_pwa/api/fso/<int:order_id>/family_messages/update`:
  same scope check; for EACH `_eligible_relations(fso)` relation:
  `_get_or_create` thread → create 'out' message (fso context,
  author = nurse user) via `_post_team_reply`-class path, then optional
  ZNS ping with NEW purpose `family_update` (selection_add), param
  `health_pwa_family.zns_template_update` DEFAULT '' (empty ⇒ no row —
  the standing no-phantom posture), dedup `famupd-<fso>-<relation>`,
  params {patient_name, link=fresh token via `_get_or_create_link`}.
  Zero eligible relations ⇒ friendly "no eligible family recipients"
  response, no rows.
- This is HUMAN-authored and distinct from health_family_link's
  automated post-visit snapshot ZNS — do not touch that flow; a visit
  can legitimately produce both.

### 2.4 Safety rails (binding)

- `health_family_messages.enabled=False` ⇒ GET returns `enabled: False`,
  both POSTs refuse, panel never renders, bell cards still render (rows
  can only exist from when it was on — they must stay dismissable).
- sudo confined to the endpoints AFTER the employee-scope check; no PHI
  in logs (ids only); all new JS text nodes rendered via textContent /
  escaped (family bodies are attacker-adjacent input).
- Nurse endpoints never expose other patients: scope check FIRST, then
  thread-belongs-to-patient check on every id taken from the client.
- PWA bump discipline: 1.10.0 in all 5 spots + both pin tests + your own
  new pin test asserting `fammsg.js?v=1.10.0` served in the shell.
- vi.po per ledger §29 (`#. module:` on every entry).

## 3. Tests (`tests/test_pwa_family.py`)

1. Scope: assigned nurse GET → thread data; unassigned nurse (other
   facility employee) GET → refused/empty; non-employee user → empty.
2. Master switch off → GET `enabled: False`, reply POST refused, no row.
3. Reply POST: creates 'out' row (author_user = nurse), flips
   read_by_ops, **clears the thread's family_message bell rows**, ZNS
   simulated under dry_run when template set / NO outbound row when
   param empty (rails matrix for `family_message_reply` unchanged).
4. Thread-id spoof: reply POST with a thread_id of ANOTHER patient →
   refused, no row.
5. FB-047 update: two relations, one non-consented → exactly one thread
   + one 'out' message; `family_update` outbound row only when template
   param set; dedup on retry; zero-eligible ⇒ no rows, friendly refusal.
6. Sanitization: over-2000 body refused via the shared `_sanitize_body`;
   `<script>` stored plain.
7. `action_send_reply` still green post-refactor (the ops inbox path —
   run /health_family_messages suite in the same deploy).
8. HttpCase shell: app_shell serves `fammsg.js?v=1.10.0` +
   `daystrip.js?v=1.10.0` etc. — and the daystrip/scribe pin tests
   updated and passing.
9. Append-only untouched: no new endpoint can edit or delete (attempt →
   refused at model level as before).

**Browser QA REQUIRED with committed evidence** (phone viewport on
care.biztinct.com, messaging temporarily enabled then re-darkened):
bell shows a real family_message card (text + dismiss working, badge
decrements); visit screen shows the panel with the thread; nurse reply
appears on the family token page; one-tap update reaches the token page
thread; service-worker cache actually refreshed (1.10.0 in the SW —
hard-reload + verify no stale 1.9.0 asset). Clean up QA rows and report
counts.

## 4. Deploy & verify

- `-i health_pwa_family -u health_pwa,health_family_messages,
  health_pwa_daystrip,health_scribe --test-enable --test-tags
  /health_pwa_family,/health_family_messages,/health_pwa_daystrip,
  /health_scribe` (HttpCase ⇒ NO --no-http). Port-wait loop; results
  from the server logfile with YOUR timestamp; login 200.
- After deploy verify and paste: `health_family_messages.enabled=False`
  (still dark), `health_pwa_family.zns_template_update=''`,
  messaging rails untouched; PWA **1.10.0** greps (all 5 spots).
- vi.po; conventions §8; commit+push on 19.0.

## 5. Report-back extras

(a) the app.js diff (paste it — it must stay ~25 lines) and how
"Xem (View)" navigates; (b) the exact nurse-scope domain shipped for the
endpoints; (c) FB-047 fan-out counts from QA (eligible vs skipped);
(d) the 1.10.0 checklist — 5 spots + which pin tests were touched;
(e) live QA evidence incl. the SW-refresh check and cleanup counts;
(f) any new ledger-grade gotcha (explicitly flagged); (g) confirm
everything stays dark with `enabled=False` (panel absent, POSTs refuse)
and that pre-existing bell rows remain dismissable.
