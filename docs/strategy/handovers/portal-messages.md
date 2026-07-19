# Handover: Portal Messages — patient ↔ care-team messaging in My Care (Phase 4F)

Read `docs/strategy/HANDOVER-CONVENTIONS.md` first (§2 deploy, §3 rails, §5
gotchas — esp. §5.17 append-only, §5.19 encrypted-field domains, §5.50
seeded-fixture asserts). **NEW module `health_portal_messages` ONLY** — §2.1
is the exhaustive sanction list; `health_family_messages`, `health_portal`,
`health_pwa_family`, `health_crm` are READ-ONLY.

## §0 Why / architecture decision (settled — do not re-litigate)

The last portal gap: the patient themselves cannot message their care team
(families can, via the FB-044 rails). The rails are patient-ready — thread +
append-only PHI-encrypted messages + ops inbox + bell/push/activity notify —
except every thread is keyed `(patient_id, relation_id)` with `relation_id`
REQUIRED (a `health.crm` family relation).

**Chosen design: the NULL-relation "patient-self" thread.** The new module
`_inherit`s `health.family.thread`, relaxes `relation_id` to optional, and
treats `relation_id = NULL` as "the patient themselves". REJECTED
alternative (do not build): fabricating a `health.client.relation` row of
type "self" — it pollutes CRM relation data, drags patient-self messaging
through the family consent gate (`receives_visit_updates` + `data_sharing`),
and shows a fake relation in ops CRM views.

Doctrine (clone of portal 4B/4E): a patient messaging their OWN care team is
their right — NOT gated by `data_sharing` consent or
`receives_visit_updates` (those govern FAMILY recipients). The global master
switch `health_family_messages.enabled` DOES apply (one kill switch for the
whole messaging surface).

**Binding non-goals**
- NO edits outside the new module (the field re-definition and method
  overrides all live in the new module via `_inherit`).
- NO new message/thread models — reuse `health.family.message` /
  `health.family.thread` (encryption, append-only, inbox, notify come free).
- NO PWA assets → NO PWA version bump.
- NO ZNS template creation (reuse the reply-ping rails; no template
  configured → row silently not created, the standing posture).
- NO changes to the family (relation-keyed) flow's behavior — every existing
  test in health_family_messages must still pass untouched.

## §1 Verified plumbing facts (do NOT re-derive)

`health_family_messages/models/health_family_thread.py`:
- `relation_id` required=True at `:39-41`; unique `(patient_id,
  relation_id)` index in `init()` `:74-82` (Postgres treats NULLs as
  distinct → the self-thread needs its OWN partial unique index).
- Create dup pre-check `:102-113` only fires when BOTH ids present — a
  self-thread pre-check must be added (else the partial index fires as raw
  IntegrityError, §5.3).
- `_get_or_create(patient, relation)` `:125-136` — clone shape for
  `_get_or_create_self(patient)`.
- `post_family_message(body, fso=None, author_label=None)` `:164-198` —
  state gate, `_sanitize_body`, 10/hour rolling cap `_rate_exceeded`
  `:150-162`, notify legs; `author_label` fallback is
  `self.relation_id.display_name` → PASS an explicit label for self threads.
- `_notify_targets`/`_notify_inbound`/`_schedule_activity` `:200-279` —
  relation-independent, work unchanged for self threads (bell type
  `family_message` reused).
- `_post_team_reply` `:308-345` + `action_send_reply` `:347-361` — ops
  reply core, relation-independent EXCEPT `_send_reply_zns` `:366-426`
  targets `relation_id.representative_id` and `_reply_zns_params`
  `:428-441` links a FAMILY visit token → both must be overridden for self
  threads (target = the patient; link = their portal messages URL).
- `_compute_display_name` `:84-90` uses `relation_id.representative_id` →
  override for self threads.

`health_family_messages/models/health_family_message.py`: dual-field
encryption (stored `body_enc`, computed `body` — never search/order on
`body`, §5.19), `_sanitize_body` (html2plaintext + 2000-char cap, raises
over-cap), append-only `_LOCKED_FIELDS` + unlink guard, `read_by_ops` /
`read_by_family` flags. Reused as-is — zero edits.

`health_family_messages/controllers/family_messages_public.py`: the family
composer precedent — `_msg_rate_limited` `:26-38` (gateway counter,
`fammsg:`/`fammsg-ip:` keys), GET override merging `_messaging_context`
`:52-64`, POST route with PRG redirect `:67-90` (checks
`link._messaging_enabled()` at `:77`).

`health_family_messages/models/health_family_link.py`:
`_messaging_enabled` `:20-35` (global param AND family eligibility — clone
ONLY the global-param half for the portal), `_messaging_context`
`:37-...` (history rows: direction/body/author/when + `mark_read` sets
`read_by_family`) — the render-context clone source.

`health_portal` (READ-ONLY, clone precedents): `_guard` at
`controllers/portal_public.py:40-47`; route shape `:49-56`;
`_record_access` at `models/health_portal_access.py:109-121`; `_VN_OFFSET`
`:25`; `portal_url` compute `:70-75`; access `state`/`_is_expired`.

`health_pwa_family/controllers/pwa_family_api.py:97` reads
`thread.relation_id.display_name or ''` → a NULL relation degrades to an
empty label, NO crash (verified). Self threads will therefore appear in the
nurse PWA panel with an empty relation label — acceptable v1; report how it
renders.

Master-switch state on vietuat: `health_family_messages.enabled` — check at
deploy time and report; if disabled, browser evidence shows the composer
hidden (that IS the correct behavior, not a bug).

## §2 Build (new module `health_portal_messages`)

Depends: `health_portal`, `health_family_messages`. Version 19.0.1.0.0.

### §2.1 Sanctioned files (exhaustive)
`__init__.py`, `__manifest__.py`, `models/__init__.py`,
`models/health_family_thread.py` (the `_inherit` extension),
`models/health_portal_access.py` (`_inherit`: messages render context),
`controllers/__init__.py`, `controllers/portal_messages_public.py`,
`views/portal_messages_templates.xml`, `views/family_messages_views.xml`
(inherited ops-inbox view: optional "Bệnh nhân tự nhắn" filter chip only),
`i18n/vi.po`, `tests/`. Nothing else anywhere.

### §2.2 Thread extension (`_inherit = 'health.family.thread'`)
- Redefine `relation_id` with `required=False` (all other attrs preserved).
- `is_patient_self = fields.Boolean(compute, store=True)` — `not
  relation_id`; used by views/filter and the overrides.
- `init()`: partial unique index
  `health_family_thread_patient_self_uidx ON health_family_thread
  (patient_id) WHERE relation_id IS NULL`.
- `create()` override: pre-check duplicates for vals with `patient_id` and
  NO `relation_id` (search `relation_id = False`) → UserError before the
  index fires (§5.3). Family branch unchanged (super handles it).
- `_get_or_create_self(patient)`: clone of `_get_or_create` with
  `('relation_id', '=', False)`.
- `_compute_display_name` override: self threads → `"%s ↔ Bệnh nhân" %
  patient.name`.
- `_send_reply_zns` override: for self threads target
  `partner = self.patient_id` (phone via the same `_safe_phone`), dedup key
  unchanged shape; params from a new `_self_reply_zns_params`: patient_name
  + link = the patient's ACTIVE `health.portal.access` messages URL
  (`<portal_url>/messages`) if one exists — do NOT auto-create portal
  access here; no access → omit the link param. Family branch: call super.
- `_reply_zns_params` stays family-only (guarded by the super call path).

### §2.3 Portal render context (`_inherit = 'health.portal.access'`)
- `_messages_thread()`: sudo search self thread for `self.patient_id`
  (`relation_id = False`), no create.
- `_messages_ctx(mark_read=True)`: clone `_messaging_context` shape —
  `messaging_enabled` = the GLOBAL param only (no family eligibility),
  history rows (direction/body/author/when, VN wall-clock `%d/%m %H:%M`),
  `mark_read` sets `read_by_family=True` on rendered 'out' messages, plus
  `token`, `patient_name`, `thread_state` (closed → composer hidden,
  history visible).

### §2.4 Controller (`/my/care/<token>/messages`)
- GET: `_guard` → `_record_access('messages')` → render
  `portal_messages` template.
- POST `/my/care/<token>/messages/send`: `_guard`, then a message-specific
  gateway throttle (clone `_msg_rate_limited` with `portalmsg:`/
  `portalmsg-ip:` keys), refuse when the global switch is off, then
  `thread = _get_or_create_self(patient)` (lazy, first send creates) →
  `thread.post_family_message(body, fso=None, author_label='Bệnh nhân %s' %
  given_name)` (reuse the portal `_given_name`) → PRG redirect back to GET.
  Empty/over-cap body and rate-refusal: redirect (PRG) without a 500 —
  over-cap `_sanitize_body` RAISES ValidationError, so catch it and re-render
  with a friendly error line (don't let a public route 500, 4C precedent).
- Hub nav link "Tin nhắn với đội chăm sóc →" in `portal_hub` via template
  inheritance (xpath after the health link) — NOT by editing health_portal.

### §2.5 Ops inbox
Self threads appear automatically (same model). Add one inherited search
filter `is_patient_self` ("Bệnh nhân tự nhắn"). Reply flow
(`action_send_reply`) works unchanged; its ZNS leg now pings the patient
via the §2.2 override.

## §3 Safety rails (binding)
- Every read/write sudo but scoped to `self.patient_id` in-domain (portal
  doctrine); the POST route takes ONLY the token + body field.
- Never widen the family flow: `relation_id=False` semantics must be
  unreachable from the family token page (it always passes a relation).
- Append-only and encryption come from the reused message model — do NOT
  add any code path that writes `body`/`body_enc` post-create.
- No consent gate for self threads (doctrine above) — but the GLOBAL
  `health_family_messages.enabled` switch must gate composer render AND the
  POST (enforce server-side, not just template).
- Never log the token or message bodies (`_logger` lines carry ids only).
- All template output `t-esc`; bodies are plain text (sanitizer).

## §4 Tests (numbered; new module's own suite)
1. `_get_or_create_self` idempotent; partial index exists; duplicate
   self-create raises UserError (not IntegrityError).
2. Family flow untouched: `_get_or_create(patient, relation)` still works
   and the two threads coexist for the same patient.
3. Patient send: creates 'in' message (encrypted at rest — assert
   `body_enc` set and `body` round-trips), bumps `unread_ops_count`,
   `last_message_at`; author_label = "Bệnh nhân <given>".
4. Global switch off → POST refused, composer flag False; switch on →
   flows.
5. Hourly cap: 11th inbound within the hour refused (empty recordset).
6. Ops reply on a self thread: 'out' message, `action_mark_read` clears
   unread + bell rows; `_send_reply_zns` targets the PATIENT partner (no
   template param → no outbound row, assert none created — no-phantom).
7. Self-thread display_name and `is_patient_self`; PWA panel read
   (`relation_id.display_name or ''`) returns '' without error.
8. Scope: another patient's self thread never renders in `_messages_ctx`.
9. `mark_read` sets `read_by_family` on rendered 'out' rows.
10. Closed self thread: history renders, POST refused (state gate).
11. HttpCase: GET renders (valid token) incl. a seeded message body;
    unknown token → neutral byte-identical to hub; POST send → redirect →
    GET shows the message.
12. Hub nav link present via the inherited template.

## §5 Deploy + verify (conventions §2; §5.45)
- `-i health_portal_messages --test-enable --test-tags
  /health_portal_messages,/health_family_messages,/health_portal
  --stop-after-init --workers 0` — NO `--no-http` (HttpCase). The
  family_messages + portal suites re-run green proves the READ-ONLY
  contract behaviorally.
- Report the `health_family_messages.enabled` live value; do NOT flip it
  without noting it in the report (if you enable for browser QA, restore
  the prior value and state so — §5.48: restart before probing a param
  change).
- Browser evidence (real drive, Demo Patient 861): hub link, messages page
  (composer or disabled state — honest either way), a sent message
  round-trip IF the switch is/was on, ops inbox showing the self thread
  with the filter. Commit under
  `docs/strategy/reports/portal-messages-evidence/`.
- QA residue: any QA self-thread/messages on REAL patients must be removed
  post-QA (messages are append-only below system-admin — prefer a QA
  patient; 861 is a demo patient, acceptable, but say what was left).

## §6 Report back
`docs/strategy/reports/portal-messages-report.md`: what shipped, declared
deviations, verbatim test tally, evidence pack, live switch state, how the
nurse PWA panel renders a self thread, proposed ledger gotchas.

---
Kickoff (paste into the Opus session):

Implement the phase specified in docs/strategy/handovers/portal-messages.md.
Read docs/strategy/HANDOVER-CONVENTIONS.md first. Build the NEW module
health_portal_messages ONLY — §2.1 is the exhaustive sanction list;
health_family_messages, health_portal, health_pwa_family and health_crm are
READ-ONLY. The NULL-relation patient-self thread design in §0 is settled —
do not fabricate a 'self' relation. The §3 rails are binding (global switch
enforced server-side, no consent gate for self, append-only untouched).
Full self-verification per §5 including the cross-suite re-run and browser
evidence pack, then commit the report per §6 and report back.
