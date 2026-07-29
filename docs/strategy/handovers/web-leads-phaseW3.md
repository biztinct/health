# Phase W3 handover — `health_web_leads` Reporting + consent bridge

**Design:** `docs/strategy/website-crm-integration.md` §7.2, §9.3, §10, §15
(W3 row) · **Prior phases:** W1 (capture) + W2 (ops loop) + W2.5 (connector)
all live and reviewed on vietuat at 19.0.3.0.0. **Module:** extend
`health_web_leads` only → `19.0.4.0.0`. **Conventions:** read
`docs/strategy/HANDOVER-CONVENTIONS.md` first — §2, §4, and ledger §5,
especially §5.1, §5.4, §5.15, §5.36, §5.55, §5.69, §5.81, §5.85, and
**§5.88–§5.92** (the W2/W2.5 entries; §5.89 was CORRECTED and §5.92 added in
the W2.5 review — reread both even if you think you know them).

## 1. What this phase is

Four small deliverables that make the pipeline *reportable* and make the
consent checkbox *mean something*:

1. **Consent bridge** — when a web lead becomes a client, the marketing-
   consent claim captured on the form is materialised as a real
   `health.consent` record, so `can_send_marketing()` (which today has ZERO
   production callers and no data) starts answering truthfully.
2. **Unmatched-campaign review** — the raw `utm_campaign` strings the
   find-only policy refused to auto-create, surfaced for marketing to seed,
   plus a back-fill action for after they seed.
3. **Funnel pivots** — leads by city × source × outcome for the ops/marketing
   persona. Data honesty: today this shows 99% hand-keyed "phone" and 350/476
   city-less leads — that *baseline being visible* is the point.
4. **Retention rail** — a raw-payload pruning cron that ships INERT until
   legal sets a horizon (PDPL/Decree 13 review is a W0 item owned by counsel;
   we make no compliance claim and hard-code no number).

## 2. Binding non-goals

- **NO edit to any file in `health_consent`** (or any module outside
  `health_web_leads`). The one model extension this phase needs is done via
  `_inherit = 'health.consent'` *inside* `health_web_leads`.
- **NO ZNS/marketing-send wiring.** Adopting `can_send_marketing()` in
  outbound sends is `health_messaging`'s change, later. W3 only creates the
  data those checks read.
- **NO auto-linking of `partner_id`/patient identity from typed contact
  data** (standing anti-pattern, W1 §2). The bridge fires only AFTER the
  ops-driven conversion has produced the patient, and only materialises a
  consent when the submitter's identity MATCHES that patient (see §5.1
  rail B3).
- **NO superseding an existing active marketing consent.** A checkbox claim
  never overrides a deliberately captured staff record — skip and note.
- **NO new HTTP endpoints, no gateway edits, no GA4/Ads API anything (W4),
  no Lead Ads, no Mode B email.**
- **NO `utm.campaign` seeds and no campaign auto-create anywhere** — the
  find-only policy (record-explosion defence) survives this phase intact.
  The back-fill action LINKS existing campaigns, never creates one.
- **Retention prunes `health.lead.touchpoint.raw_payload` ONLY** — never
  touchpoint rows, never any `crm.lead` field, never consent records.

## 3. Verified plumbing facts (do not re-derive)

1. **Conversion chokepoint**: every lead→client path (7 call sites: the two
   `_process_contact_relationship` arms :1295/:1325, `action_convert_to_
   appointment` :1565, `_resolve_booking_client` :1824, `action_convert_to_
   client` :1832, `booking_wizard.py:429`, `client_selection_wizard.py:85`)
   funnels through **`CrmLead._get_or_create_patient()`**
   (`health_crm/models/crm_lead.py:1343`, creates at :1438, returns a
   `res.partner`). Caveats: it ALSO returns *pre-existing* patients, and the
   auto-trigger `_process_contact_relationship` (:1284) re-fires from BOTH
   `create()` (:921-922) and `write()` (:1100-1101), gated by
   `_should_process_relationship()` (:1338-1341: outcome `service_booked` OR
   `stage_id.is_won`), and early-returns for `type='lead'` (:1289-1290) —
   web leads are `type='opportunity'` (`web_lead_service.py:571`) so they
   qualify. **The bridge hook is an override of `_get_or_create_patient` and
   must therefore be idempotent and re-fire-safe by design.**
2. **A patient is `res.partner` with `is_patient=True`** — the lead's client
   is **`patient_id`** (`health_crm/models/crm_lead.py:171-176`), NOT
   `partner_id` (secondary; `_booking_client()` :1733-1741 prefers
   `patient_id`). Key everything on the partner `_get_or_create_patient`
   RETURNS.
3. **`health.consent`** (`health_consent/models/health_consent.py`):
   `client_id` required, domain `is_patient=True` (:69-73); `consent_type`
   Selection incl. `'marketing'` (:74-82); `method` required Selection
   verbal/written/digital_signature (:101-106); `state` default `draft`
   (:125-133); **`client_mutation_id` Char with a UNIQUE constraint —
   pre-checked in `create()` (:314-325) — is the designed idempotency key;
   use it.** `_check_one_active` (:224-247): at most one active per
   (client, type). `EVIDENCE_LOCKED_FIELDS` (:49-53) are immutable once out
   of draft with **no superuser escape** (`write()` :333-352); `unlink()` is
   draft-only (:353-368). Constraints are re-run explicitly in `create()`
   (:327-331).
4. **`action_grant()`** (:380-423): `_check_capture_allowed()` (:371-378)
   passes for `env.su` — a sudo'd bridge clears it. The evidence gates are
   **per-method `if` branches** (:389-400), NOT a whitelist — a new method
   key added by `selection_add` passes with no evidence, so the bridge's own
   inherited model must enforce its evidence discipline (§5.2). The grant
   SUPERSEDES any other active same-type consent (:404-421) — which is why
   rail B4 checks-and-skips BEFORE granting, never relying on supersede.
5. **`can_send_marketing()`**: `health_consent/models/res_partner.py:64-70`,
   thin wrapper over `check_consent(partner, 'marketing')`, never raises,
   zero production callers today. `check_consent` (:522-543) writes a check
   log; the log's `source` is free-text set via context key
   `consent_check_source` (:516-518; log model
   `health_consent_check_log.py:36-38`; precedent values `'pwa'`,
   `'fhir_facade'`).
6. **Consent-claim fields already on the lead** (W1):
   `web_consent_marketing` (`health_web_leads/models/crm_lead.py:85`),
   `web_consent_text_version` (:89), `external_submission_id` (:65, partial
   unique index :173-174).
7. **UTM reality**: the five raw strings live on the TOUCHPOINT only
   (`lead_touchpoint.py:78-82`, written at `web_lead_service.py:663-667`);
   the lead carries the `utm.mixin` m2os plus raw `utm_content`/`utm_term`
   only. Find-only campaign logic: `_utm_ids()`
   (`web_lead_service.py:303-329`; campaign arm :323-328 `=ilike`, omitted
   from vals when unmatched). **The merge path (:540-558) never calls
   `_utm_ids`** — a later touch with a newly seeded campaign does NOT
   back-fill `campaign_id`; that is exactly what the W3 back-fill action is
   for. Sanitizer `_sanitize_utm` :153-159. Phone normalizer for identity
   matching: module-level `_safe_phone` (`web_lead_service.py:103`).
8. **Pivot precedents**: core `crm.crm_lead_view_pivot`
   (`addons/crm/views/crm_lead_views.xml:872-890`); in-repo custom precedent
   `health_crm/views/health_client_relation_views.xml:91-100`; action-with-
   view-modes precedent `health_crm/views/crm_lead_views.xml:517-534`. No
   custom pivot/graph on crm.lead exists anywhere yet. biz_bi has a minimal
   "CRM Leads" dataset (`biz_bi_health/hooks.py:212-219`) with no
   city/source/status curation and no CMS reachability — **W3 pivots are
   plain Odoo views per the W1/W2 precedent; do NOT build BI datasets.**
9. **Sidebar**: `section_crm` sequences taken: 12 (Channel Center),
   13 (Website Connector), 21 (Web Touchpoints), plus core items at 4/14/25
   from `cms_sidebar_items_crm.xml` — VERIFY free sequences with a quick
   `SELECT sequence, name FROM cms_sidebar_item` before choosing; 15 and 22
   were free at design time. §5.69 traps restated in
   `health_web_leads/data/cms_sidebar_items_web_leads.xml:1-20`.
   Touchpoint action xmlid: `action_health_lead_touchpoint`
   (`views/lead_touchpoint_views.xml:120`).
10. **Funnel fields**: `contact_status` (:312-318, values
    active/booking/lead/lost_booking/spam per :52-59), `contact_outcome`
    (:301-305, :42-50), outcome→status sync in `write()` (:1080-1094),
    `catchment_province_id` (:675-679). Web-lead constant writes:
    `web_lead_service.py:581-586` (`mode_of_contact='website'` etc.).
11. **W2.5 review LOW to fix in passing** (report §9): the comment above
    `_heartbeat_user`'s `.filtered('active')` states the premise §5.89's
    correction refutes — reword it to "defensive against callers carrying
    `active_test=False`" while you are in `web_lead_service.py` anyway.
12. **§5.88 caveat for negative ACL tests on this DB**: live
    `res_groups_implied_rel` makes `base.group_user` imply
    `group_healthcare_base` — clone T9-W2.5's live-closure precheck
    (`tests/test_web_leads_connector.py:535-590`) for any new denial assert.

## 4. Build spec

### 4.1 Consent bridge (`models/health_consent.py` + `models/crm_lead.py`)

**(a) Method key** — new file `models/health_consent.py`:
`_inherit = 'health.consent'`;
`method = fields.Selection(selection_add=[('web_form', 'Web form checkbox')],
ondelete={'web_form': 'set default'})`. Override `action_grant()` to add the
missing evidence gate for our key: `method == 'web_form'` requires BOTH a
non-empty `scope_note` AND a set `client_mutation_id` — raise `UserError`
otherwise (fact #4: the core gates are per-method branches, so without this
our key would grant evidence-free).

**(b) Bridge state on the lead** — one new field on `crm.lead`:
`web_consent_bridged` Selection `created` / `skipped_existing` /
`skipped_identity` / `skipped_declined`, `copy=False`, readonly, tracking.
Set exactly once; the hook exits immediately when it is set (re-fire guard
that also gives reporting visibility). Shown readonly in the Web Attribution
tab on all THREE lead forms (§5.91!) next to `web_consent_marketing`.

**(c) The hook** — in `models/crm_lead.py`, override
`_get_or_create_patient()`: call `super()`, then
`self._web_leads_bridge_consent(patient)`, return the patient unchanged.
`_web_leads_bridge_consent` decision ladder (each step marks
`web_consent_bridged` and stops):

1. Exit unmarked if: no patient, `web_consent_bridged` already set, or
   `external_submission_id` falsy (not a web lead — leave non-web leads
   completely untouched).
2. `web_consent_marketing` False → mark `skipped_declined`. No record, no
   chatter — absence of consent is not an event.
3. **Identity match (rail B3)**: materialise self-granted consent ONLY when
   the submitter is the patient — normalized phone (via `_safe_phone`,
   compare last 9 digits) OR lowercased email of the LEAD equals the
   PATIENT's phone/mobile/email. No match (representative enquiring for a
   relative) → mark `skipped_identity` + ONE chatter note on the lead:
   the claim stays recorded on the lead, staff must capture consent from the
   client themselves. Never guess a `health.client.relation`.
4. Idempotency: `client_mutation_id = 'web-lead-%d-%s' % (lead.id,
   external_submission_id)`; if a consent with that key exists in ANY state
   (`active_test=False` search) → mark `created` and stop.
5. **Skip-don't-supersede (rail B4)**: an ACTIVE `marketing` consent already
   exists for the patient → mark `skipped_existing` + one chatter note.
   Never withdraw or supersede a staff-captured record with an automated
   claim.
6. Create (sudo): `client_id=patient`, `consent_type='marketing'`,
   `method='web_form'`, `self_granted=True`, `effective_date` = the date of
   the original submission (the lead's `form_submit` touchpoint
   `occurred_at`, fallback lead `create_date`), `scope_note` = one line
   naming the consent-text version (`web_consent_text_version` or
   'unversioned'), the `external_submission_id`, and the submission UTC
   timestamp, `client_mutation_id` per step 4. Then `action_grant()` (sudo
   passes the capture gate, fact #4). Chatter both ways: on the lead (with
   the consent reference) and on the consent (created from web lead N).
   Mark `created`.

**Rail B1 (CRITICAL): the bridge NEVER breaks conversion.** The entire
ladder runs inside `try/except Exception` → `_logger.warning(exc_info=True)`
and return; a consent failure must never cost the ops user their booking
flow. No savepoint needed around the ladder's reads; wrap ONLY the
create+grant in `self.env.cr.savepoint()` (§5.55) so a constraint refusal
rolls back cleanly inside the wider transaction.

**Rail B2**: the bridge runs sudo for consent create/grant but derives every
value from the lead record — never from context, never from `request`.

### 4.2 Unmatched-campaign review + back-fill (`views/lead_touchpoint_views.xml` + service)

- Search-view filter "Unmatched campaign" on the touchpoint:
  `[('utm_campaign','!=',False),('lead_id.campaign_id','=',False)]`.
- New act_window `action_campaign_review` on `health.lead.touchpoint` with
  that domain + `context={'group_by':'utm_campaign'}`, list view reusing the
  existing one. Sidebar leaf (§5.69: childless, no `parent_id` field, no
  noupdate, distinct free sequence per fact #9) named "Campaign Review",
  icon `fa fa-bullhorn`.
- Server action / list-header button **"Link seeded campaigns"** on the
  touchpoint model (group-gated to the W2.5 operator trio +
  `sales_team.group_sale_manager` if it exists — check, else the trio):
  for each distinct raw `utm_campaign` among selected (or filtered) rows
  whose lead lacks `campaign_id`, `search([('name','=ilike',raw)], limit=1)`
  on `utm.campaign`; if found, write the lead's `campaign_id`. Find-only —
  NEVER create. Chatter on each touched lead ("campaign linked
  retroactively from touchpoint N"). Report count via
  `display_notification`.

### 4.3 Funnel pivots (`views/crm_lead_views.xml` extension)

- New pivot view on `crm.lead`: rows `catchment_province_id`, cols
  `mode_of_contact`, measure count (clone the core arch, fact #8). New graph
  view (bar, stacked) same dimensions. New act_window "Lead Funnel" —
  `view_mode` list,pivot,graph with explicit `view_ids`, domain `[]` (ALL
  leads — the funnel compares channels; web leads are the new column, the
  hand-keyed phone mass is the honest baseline), context group-bys
  `contact_status`. Sidebar leaf "Lead Analysis" (same §5.69 rules, free
  sequence per fact #9).
- Do NOT try to compute conversion joins (lead→booking→client revenue) in
  this phase — count-by-dimension only. Deeper funnel math is a biz_bi
  question for later, per fact #8's precedent verdict.

### 4.4 UTM vocabulary seeds (`data/utm_seeds.xml`)

`noupdate="1"`. Seed ONLY names absent from core utm data (check
`addons/utm/data/utm_data.xml` and live rows first; core already ships
several mediums): mediums `cpc`, `organic`, `social`, `referral`,
`messaging`; sources `google`, `facebook`, `zalo`, `tiktok`. Lowercase
names exactly as the naming standard (§7.2 of the design doc) prescribes so
`_utm_ids` find-or-create matches them instead of creating case-variants.
No campaigns (non-goal).

### 4.5 Retention rail (`data/web_leads_params.xml` + `data/web_leads_cron.xml` + service)

- New param `web_leads.raw_payload_retention_days`, seeded as the STRING
  `'0'` (noupdate; §5.36). `'0'` = keep forever — the legal default until
  counsel decides (no compliance claim anywhere in code or docs).
- New nightly cron (active=True, inert via the param gate — the §5.81
  pattern the heartbeat already uses) calling
  `web.lead.service._cron_prune_raw_payloads()`: parse the param via the
  existing falsy/int discipline; if days ≤ 0 return; else
  `search([('received_at','<', now - days),('raw_payload','!=',False)],
  limit=500)` and write `raw_payload=False`; `_logger.info` the count.
  Batched (limit 500/night is plenty at current volumes); prunes the payload
  FIELD only (non-goal rail).
- While in `web_lead_service.py`: apply fact #11 (the §5.89 comment reword).

### 4.6 vi.po

Every new field label/help/selection value/button/filter/notification/chatter
string; 0 inert entries; §5.85/§5.90 discipline; extend the W2.5 named-msgid
test pattern (`test_w25_12`) rather than duplicating its structural sweep.

## 5. Tests (new class `TestWebLeadsW3`, extend `tests/`)

Run persona-real (§5.4): conversion-driving tests must run as a REAL ops user
(e.g. a receptionist or CRM manager via `with_user`), not uid 1 — W2.5's D3
exists because uid-1 tests hid exactly this class of bug.

- T1 happy path: web lead (claim True, version set) converts via
  `action_convert_to_client` as a CRM manager → exactly one consent:
  marketing/web_form/active/self_granted, mutation key correct, scope_note
  carries submission id + version, `effective_date` = submission date,
  `patient.can_send_marketing()` is True, lead marked `created`, chatter both
  sides.
- T2 re-fire safe: convert again + a `write()` that re-triggers
  `_process_contact_relationship` → still exactly ONE consent, marker
  unchanged.
- T3 declined: claim False → no record, marker `skipped_declined`,
  `can_send_marketing()` False, zero chatter added by the bridge.
- T4 skip-don't-supersede: pre-existing ACTIVE marketing consent (staff-
  captured, different mutation key) → it remains THE active one untouched,
  marker `skipped_existing`, one note.
- T5 identity mismatch: lead phone/email differ from the patient's (the
  representative case) → no record, marker `skipped_identity`, exactly one
  note even after a second re-fire.
- T6 bridge never breaks conversion: force the create to fail (e.g. patch
  `health.consent.create` to raise, or stage a colliding active consent
  concurrently) → `_get_or_create_patient` still returns the patient and the
  lead converts; a warning is logged.
- T7 audit shape: the created consent's `scope_note` write raises `UserError`
  (evidence lock, fact #3) and our `action_grant` override refuses a
  `web_form` draft missing scope_note/mutation key.
- T8 campaign review + back-fill: unmatched raw campaign filters correctly;
  after seeding a matching `utm.campaign`, the action links the lead
  (`=ilike` case-insensitive), the filtered list empties, and NO
  `utm.campaign` row was created by the action.
- T9 catalogue: all new xmlids load; `get_view` renders pivot/graph/list;
  sidebar leaves childless with distinct sequences (§5.69); negative-ACL
  asserts (the back-fill button gate) use the live-closure precheck
  (fact #12).
- T10 retention: param `'0'` → cron a no-op; param `'30'` + a 31-day-old
  touchpoint → `raw_payload` cleared, every other field and the row intact,
  a 5-day-old row untouched; param row still exists after runs (§5.36).
- T11 UTM seeds: present, noupdate, and `_utm_ids` with `medium='CPC'`
  matches the seeded `cpc` instead of creating a duplicate.
- T12 vi.po per §4.6.

Expected executed-method count after this phase: 52 + the new methods —
STATE the number in the report and prove it per §5.90 **with the §5.92
discipline: the result line and counts come from
`/var/log/odoo/odoo-server.log` scoped to the run's PID, never from stdout.**

## 6. Deploy + report-back

Standard workflow (§7 of the W2.5 handover; stop `odoo-server`, upgrade with
tests, restart, §5.45, §5.92). Browser-verify per the standing rule as the
ops persona: the two new sidebar leaves, the pivot rendering with real
grouped counts, the Campaign Review list, and the Web Attribution tab showing
`web_consent_bridged` — screenshots to
`docs/strategy/reports/web-leads-phaseW3-evidence/`. **Do NOT drive a real
conversion or create consent/patient rows in live data during QA — the
bridge is proven by the test transcript only; say so in the report.**

Report back: (1) test transcript + §5.90/§5.92-proven executed count;
(2) the live-DB free-sequence check you ran for fact #9 and the sequences
chosen; (3) pivot + Campaign Review screenshots; (4) proof the retention
cron is inert (param value + a no-op log line); (5) confirmation zero
consent/patient/lead rows were created in live data by QA; (6) any deviation
with the file:line premise that forced it.

## Kickoff line

Implement Phase W3 of the website lead integration exactly per
`docs/strategy/handovers/web-leads-phaseW3.md`. Read
`docs/strategy/HANDOVER-CONVENTIONS.md` first (§2, §4, ledger §5 —
especially §5.1, §5.4, §5.36, §5.55, §5.69, §5.81, §5.85, §5.88–§5.92).
Extend only the `health_web_leads` module. Run tests T1–T12, deploy to
vietuat per §6, and report back the six items in §6.
