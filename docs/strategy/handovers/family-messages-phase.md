# Handover: Secure Family Messaging — `health_family_messages`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 28 entries — read all). This phase delivers
roadmap FB-044 ("secure in-app messaging", Horizon 2's top unblocked
item): **two-way, visit-entered, consent-gated messaging between a
patient's family and the care team**, encrypted at rest and auditable.
Today the platform is outbound-only — a family member who wants to say
"please send someone who speaks English" or "Mum had a bad night" has
NO channel except calling the facility.

## 0. Scope

1. **Family side (NO login/portal — the family_link token pattern)**:
   the existing `/family/visit/<token>` page gains a message section —
   read the thread + send a message while the token is valid. No new
   identity system; the token already proves (visit, relation).
2. **Ops side**: a backend "Family Messages" inbox (list + thread form,
   Operations workspace menu) where ops/coordinators read and reply.
3. **Notify**: inbound message → PWA bell notification + VAPID push to
   the visit's lead staff and the facility manager, `mail.activity`
   fallback. Ops reply → ZNS "you have a reply" ping to the family
   (existing rails, new purpose, empty template default = silent).
4. **Storage**: purpose-built thread/message models (NOT mail.message —
   family members have no user account so mail RBAC can't scope them),
   message bodies PHI-encrypted with the clinical-note dual-field
   pattern, messages append-only.

**Non-goals (binding):** family portal/login accounts (FB-001, later);
Zalo Mini App; staff↔staff chat (Discuss exists); attachments/photos;
message editing or deletion by anyone below admin; real-time
websockets (poll on the token page is fine); auto-triage/LLM routing;
PWA UI changes (see §2.4 — if a bump turns out to be required, STOP
and say so in the report instead of bumping).

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Token page pattern** (health_family_link): route
  `/family/visit/<token>` `auth='public'` (controllers/family_public.py:33),
  IP rate-limit via `gateway.rate.counter.hit('family:%s' % ip)` (:20-27),
  token `secrets.token_urlsafe(24)` + real DB unique index
  (models/health_family_link.py:59-61, 92), `expires_at` =
  scheduled_end + 24h, re-extended to actual_end + 24h (:68-70,
  143-156), `state` sent/revoked (:64), neutral page for
  invalid/expired/revoked/consent-withdrawn (`_page_context`, :229-277).
  Templates are STANDALONE HTML (inlined CSS, SVG icons, no backend
  assets, Vietnamese-first) — views/family_templates.xml:4, 51, 77.
- **Eligibility** `_eligible_relations(fso, require_medical=False)`
  (health_family_link.py:115-137): `receives_visit_updates` AND
  `health.consent.check_consent(patient, 'data_sharing')` (audited,
  append-only); `can_receive_medical_info` only gates clinical
  snapshots. Family identity = `health.client.relation`
  (health_crm/models/health_client_relation.py:16) with
  `representative_id` → res.partner (:31). NO family user accounts.
- **Outbound rails** (health_messaging): `health.outbound.message`
  purposes/channels/states (health_outbound_message.py:39-64), dedup
  key + partial unique index (:68, 80), master switches
  `health_messaging.enabled` (default OFF) + `dry_run` (default ON)
  (:122-124), quiet hours (:194-204). family_link's `_send_zns`
  precedent: purpose-specific template param, `_safe_phone` never
  raises, dedup `famlink-<fso>-<relation>` (health_family_link.py:294,
  307). **There is NO inbound model anywhere — you are building the
  first one.**
- **PHI encryption** (health_phi_encryption): AES-256-GCM token
  `enc$1$<b64>` (phi_crypto.py:33), `encrypt/decrypt/is_encrypted`
  (:73-108) — decrypt returns a visible error marker, never raises.
  CLONE the dual-field pattern from health_clinical_note.py:24-65:
  stored `*_enc` Char + computed plaintext field with
  compute/inverse. **Ledger §5.19: the computed plaintext fields are
  NON-STORED — never search/filter/order on them; search on metadata
  (thread, dates, direction) only.**
- **Push infra** (health_pwa): `health.pwa.staff.notification`
  (pwa_staff_notification.py:14-32 — user_id, fso_id,
  notification_type Selection, message, is_read) renders in the PWA
  bell; `health.pwa.push.subscription` + `health.pwa.config
  .get_push_config()` + pywebpush already deployed —
  `_send_staff_assignment_notification` in
  health_fieldservice/models/health_fieldservice_order.py is the
  end-to-end precedent to clone (build payload, loop subscriptions,
  best-effort try/except).
- **Escalation precedent**: `_step_escalate`
  (health_outbound_message.py:301-323) creates a `mail.activity` on
  the FSO for lead_staff/facility-manager — same targets for §2.3.
- **FSO** inherits mail.thread; `lead_staff_id` is NON-STORED (ledger
  §5.22) — resolve the notify target via `primary_nurse_id` /
  assignment lead role, not lead_staff_id in SQL/domains.
- **hr.employee reads as non-HR user trip the public-profile prefetch
  guard** (§5.24) — sudo employee reads inside group-gated methods.
- **PWA version is 1.9.0** — this phase makes NO PWA asset change
  (§2.4 keeps the bell server-side), so NO bump. The version-pin tests
  in co-resident modules will catch an accidental bump.

## 2. Architecture

### 2.1 Models (new module `health_family_messages`)

Depends `['health_family_link', 'health_messaging', 'health_pwa',
'health_phi_encryption']`.

- **`health.family.thread`**: one per (patient_id, relation_id) —
  families think in "my channel about Mum", not per-visit; each
  MESSAGE carries visit context instead. Fields: patient_id,
  relation_id (unique pair — SQL constraint), facility_id (related,
  stored, for inbox filtering), state (active/closed), last_message_at
  (stored, for inbox ordering), unread_ops_count (stored compute or
  plain integer maintained on create/read — keep it cheap).
- **`health.family.message`**: thread_id (required, cascade),
  direction ('in' family→team / 'out' team→family), body_enc +
  computed body (the §1 dual-field clone), fso_id (optional visit
  context — set from the token's visit for 'in'; the reply form's
  current visit for 'out'), author_user_id (for 'out'),
  author_label (denormalized display name — "Con gái (Daughter)" from
  the relation for 'in'), read_by_ops (bool), read_by_family (bool —
  set when the token page renders the thread after the message
  exists). **Append-only: override write to allow ONLY the read_*
  flags and state fields to change; unlink → UserError except for
  system admin** (the EVV append-only precedent, ledger §5.17 — make
  the tests create-then-try-edit).
- Length cap on body (e.g. 2000 chars) enforced server-side at both
  entry points; strip HTML (plain text only, escape at render).

### 2.2 Family entry (extend the token page — health_family_link inherit)

- New controller routes in this module (do NOT edit family_link's
  controller file; add a second controller class on the same paths
  pattern): `GET` stays `/family/visit/<token>` — inherit/extend the
  page context to include the thread (create it lazily on first send,
  not on render); `POST /family/visit/<token>/message` (POST-only —
  state changes never on GET; token+state+expiry+consent re-checked
  inside the POST, same `_page_context`-style neutral refusal; IP
  rate-limit AND per-token rate-limit e.g. 10/hour via
  gateway.rate.counter key `'fammsg:%s' % token`).
- Consent + eligibility for messaging = `receives_visit_updates` AND
  `check_consent(patient, 'data_sharing')` — same as the page itself;
  `can_receive_medical_info` NOT required to WRITE a message.
- The thread section renders previous messages (both directions) only
  while the token is live — the 24h expiry is a privacy feature
  (bounded exposure window), not a bug. Note in the page footer
  (VN-first): "Kênh nhắn tin mở trong 24 giờ quanh mỗi lượt thăm khám".
- Template: extend the standalone-HTML family page (same inlined-CSS
  approach, mono colors, hf-wt-ico-style inline SVG, no emoji).
- If family_link's page template can't be xpath-extended cleanly
  (standalone template, not a website layout), render the messages
  block from a second template injected via a t-call placeholder OR
  re-render the whole page template in this module — report which.

### 2.3 Ops inbox + notify

- Views: list of threads (patient, relation label, facility, last
  message, unread badge), thread form showing the message history
  (newest last) + a reply text box (a simple transient/onchange-free
  server action or a small OWL widget — prefer a plain form with a
  one2many readonly tree + a `reply_text` Char + "Send reply" button
  calling `action_send_reply`; no custom OWL unless the plain form is
  genuinely unusable — report which).
- Menu under the Operations workspace (mirror how Staff Schedule is
  menued in health_fieldservice/views/staff_schedule_views.xml).
- Access: ops ladder (the drag/canvas `_OPS_GROUPS`) read+write on
  both models; nurses/staff NO access in v1 (coordinator-mediated —
  keep the surface small); ir.model.access.csv accordingly + record
  rules by facility_id (clone an existing facility rule — find one in
  health_fieldservice security and cite it in your report).
- On inbound create: (a) `health.pwa.staff.notification` for the
  visit's lead staff user (resolve via primary_nurse_id/assignment
  lead — §1 gotcha) AND the facility manager user, type
  'family_message' (Selection EXTENSION via selection_add — verify
  the PWA bell renders unknown types by message text only; if the PWA
  JS switches on type and would break, fall back to reusing an
  existing type value and SAY SO — do not touch PWA assets); (b)
  VAPID push (clone the assignment-notification loop, best-effort);
  (c) `mail.activity` on the FSO (or patient if no fso) for the
  facility manager — the `_step_escalate` pattern.
- On ops reply: create 'out' message, then ZNS ping through the
  health_messaging rails: new purpose `family_message_reply`
  (selection_add on health.outbound.message), template param
  `health_family_messages.zns_template_reply` DEFAULT '' (empty = no
  send — the standing safety posture), dedup
  `famreply-<thread>-<message_id>`, params {patient_name, link} where
  link is a FRESH family token for the thread's most recent
  live-or-upcoming visit if one exists, else no link param. Rails
  master switches (enabled/dry_run) apply unchanged.

### 2.4 Safety & compliance rails (binding)

- `health_family_messages.enabled` ir.config_parameter, DEFAULT
  False: when off, the token page shows NO message section and the
  POST route returns the neutral page; inbox stays installed but
  banner "Messaging is disabled". Go-live is a manual param flip.
- All family-supplied text: escape on every render (backend form AND
  token page), length-capped, plain text only.
- No PHI in logs — log message IDs and thread IDs, never bodies.
- sudo confined to the public controller + the notification/ZNS
  senders (guard-by-group-then-sudo inside backend methods, §5.24).
- Messages are patient-record material: keep them out of
  ir.logging/exception paths (try/except the notify+ZNS legs like
  every rails caller).

## 3. Tests (`tests/test_family_messages.py`)

1. Thread uniqueness: second (patient, relation) thread refused.
2. Dual-field crypto: write body → DB column `body_enc` starts
   `enc$1$`; read returns plaintext; search on body is never used
   (grep-level assertion not needed — just don't).
3. Append-only: editing body after create raises; unlink as ops
   raises; read_by_ops flip allowed.
4. POST send: valid token + consent → message row (direction 'in',
   fso context set, author_label from relation); expired token →
   neutral, NO row; revoked → neutral; consent withdrawn (mock
   check_consent False) → neutral, NO row; enabled=False → neutral,
   NO row. (HttpCase — REMEMBER: no --no-http on the deploy test run,
   reference_httpcase_no_http.)
5. Rate limit: 11th send in the window → refused politely, 10 rows.
6. Length cap + HTML strip: 3000-char body refused; `<script>` body
   stored escaped/plain.
7. Notify on inbound: pwa notification rows for lead staff + facility
   manager users; mail.activity created; all best-effort (mock a push
   failure → message still created).
8. Reply flow: `action_send_reply` as ops user creates 'out' row +
   outbound message row with purpose `family_message_reply`; empty
   template → NO outbound row (the no-phantom rule); dedup on retry.
9. Non-ops user: read/write on thread/message models raises
   AccessError; other-facility ops user sees nothing (record rule).
10. Token page GET renders thread messages when live; marks
    read_by_family on the 'out' messages it displayed.
11. Rails matrix for the new purpose (clone health_family_link's
    rails tests): enabled off → skipped; dry_run → simulated.

**Browser QA REQUIRED with committed evidence**: real token page on
care.biztinct.com — send a message from a phone-width viewport, see it
in the backend inbox, reply, see the reply appear on the token page
(dry_run keeps ZNS simulated); neutral page on an expired token; PWA
bell shows the notification for the lead staff user.

## 4. Deploy & verify

- `-i health_family_messages --test-enable --test-tags
  /health_family_messages,/health_family_link,/health_messaging`
  (HttpCase ⇒ NO --no-http). Port-wait loop; results from the server
  logfile with YOUR timestamp; login 200.
- Params after deploy: `health_family_messages.enabled=False`,
  `zns_template_reply=''`; health_messaging.enabled/dry_run untouched
  (verify and paste values).
- PWA stays 1.9.0 (verify, paste grep).
- vi.po; conventions §8; commit+push on 19.0.

## 5. Report-back extras

(a) how the family page template was extended (xpath vs re-render)
and what the section looks like (screenshot); (b) the inbox UI choice
(plain form vs OWL) and why; (c) whether the PWA bell rendered the
new notification type without JS changes (and what you did if not);
(d) the facility record-rule you cloned (cite it); (e) exact live
counts: threads/messages created during QA and their cleanup; (f) any
new ledger-grade gotcha (explicitly flagged); (g) confirm messaging
stays fully dark with enabled=False (live token page shows no
composer).
