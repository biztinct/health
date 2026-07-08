# Handover: Family Visit Link + Post-Visit Snapshot — `health_family_link`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger has 16 entries — read all). This is Tier 3a:
FA-066 (post-visit family snapshot via Zalo) + UX-093 in its v1 form
(no-login family visit page). It kills the two biggest family
pain-points — "where is my nurse" calls and the post-visit information
vacuum — through the channel Vietnamese families actually use.

**Primary spec: `docs/strategy/design-platform-services.md` §D.4 +
§D.2.4 + acceptance §D.8 items 6–7.** That spec predates the shipped
messaging/consent stack, so THIS document's amendments override it
wherever they conflict (same delta-sheet contract as the ops-quickwins
phase). §D.2/D.3's `health.message.delivery` engine was NEVER built —
the shipped equivalent is `health_messaging`'s `health.outbound.message`.

## 0. Scope (one new module `health_family_link`)

1. **`health.family.link`** — a tokenized, no-login, phone-friendly
   public page per (visit, family relation) that follows the visit
   lifecycle: upcoming → nurse arrived → completed (with the sanitized
   snapshot). One link covers the whole visit; the completion ZNS
   points at the same URL.
2. **Two family ZNS purposes** through the shipped messaging rails:
   `family_visit_link` (sent at booking confirmation) and
   `family_snapshot` (sent at completion).
3. **Relation opt-in field**: `receives_visit_updates` on
   `health.client.relation` (+ form/list exposure).

**No PWA change ⇒ NO PWA bump this phase.** The snapshot fires
automatically from visit completion (one-tap included — it calls the
same `action_complete_service`).

**Non-goals (binding):** live GPS ETA / position streaming (needs PWA
surgery — day-strip redesign phase); D.2.4's `messaging_consent`
selection on the relation (superseded — the shipped `health_consent`
engine is the consent authority, see A2); SMS/voice; family portal
accounts; any edit to health_pwa or health_messaging's existing files
(the purpose extension is a `selection_add` inherit in THIS module).

## A. Amendments (override §D where they conflict)

**A1 — Send path.** No `health.message.delivery`, no
`health_messaging_auto.*` params. Use `health.outbound.message` with
`purpose` `selection_add` — copy the working one-liner precedent
`health_workflow_auto/models/outbound_message.py` (add BOTH purposes,
`ondelete: cascade`). Sends must respect **`health_messaging.enabled`
and `health_messaging.dry_run` exactly** (dry_run → state `simulated`,
no real send — vietuat holds real phone numbers), reuse the zalo client
accessor + try/except-`normalize_vn_phone` (ledger §5.15) exactly as
`health_workflow_auto/models/visit_offer.py::_send_offer_zns` does —
that method is the copy-paste template. Dedup keys:
`famlink-<fso_id>-<relation_id>` / `famsnap-<fso_id>-<relation_id>`.
Template params (config, empty default → that send silently not
created): `health_family_link.zns_template_family_link` /
`.zns_template_family_snapshot`.

**A2 — Consent gate (three ANDed conditions per recipient).**
1. `relation.receives_visit_updates` (new field, default **False** —
   installing changes nothing until a human opts a relation in);
2. `relation.can_receive_medical_info` (existing Boolean,
   health_crm/models/health_client_relation.py L111) — required for the
   snapshot/summary content; for the pre-visit `family_visit_link` only
   condition 1+3 apply (schedule info is not medical info);
3. `env['health.consent'].check_consent(order.patient_id,
   'data_sharing')` — the shipped spine hook (never raises, logs
   evidence to the append-only check log; 'data_sharing' is a valid
   type, health_consent.py L76).
§D.8.6 stands: zero eligible recipients → zero sends AND zero
`skipped` rows (no phantom PHI trail). The recipient is
`relation.representative_id` (phone precedence mobile, phone).

**A3 — Snapshot content sanitization (§D.4.2 stands, tightened).**
Source = the visit's latest `health.clinical.note`
(health_fieldservice; the FSO-level fields of the same names are
Legacy — do not read them). `summary` = first 200 chars of
`patient_condition_after or treatment_performed or clinical_notes`,
in that precedence; `clinical_notes` is **Html** — strip tags before
truncating. NEVER include: the note's diagnosis field, any
`condition_code_ids` codes, medication names (do not source from any
eMAR model at all). ZNS params: `{patient_name, visit_date (wall-clock
in booking_timezone — pytz, ledger's most-hit bug class), staff_name
(lead staff, given name only), link}` — the full summary lives on the
PAGE, not in ZNS params (ZNS params are length-limited and less
controllable).

**A4 — `health.family.link` model.**
| field | notes |
|---|---|
| fso_id | m2o health.fieldservice.order, required, index, ondelete cascade |
| relation_id | m2o health.client.relation, required, ondelete cascade |
| partner_id | m2o res.partner (recipient snapshot, = relation.representative_id) |
| token | Char required index, `secrets.token_urlsafe(24)`, unique index in `init()` (ledger §5.1) |
| state | sent / revoked (Selection; revoked when consent is withdrawn — see A6) |
| expires_at | Datetime = scheduled_datetime + duration + 24h; re-extended to actual_end + 24h at completion |
| outbound_message_ids | o2m or two m2o's to the log rows — your call, report it |
One link per (fso, relation): search-first before create (idempotent).
No expiry cron — expiry is checked at render time.

**A5 — Public controller `/family/visit/<token>`** — clone the
conventions of `health_workflow_auto/controllers/offer_public.py`:
`auth='public'`, sudo confined to the route, `gateway.rate.counter`
reuse (key prefix `family:<ip>`), invalid/expired/revoked all render
the SAME neutral page (no existence oracle). The page is READ-ONLY —
GET only, no actions, no form (the POST-only rule that bit the offer
page doesn't arise; do not add any state-changing route). Page states,
driven server-side at render:
- FSO in confirmed/assigned → upcoming: date + time window (wall-clock,
  booking_timezone), staff given name + role word ("y tá"), facility
  phone for changes;
- in_progress → "nurse arrived at HH:MM" from `actual_start_datetime`;
- completed/completed_pending_invoice/closed → the sanitized summary
  (A3) + visit date/staff;
- cancelled → neutral "contact us" body.
Style per the offer pages (`offer_templates.xml` precedent): server
QWeb, self-contained inline CSS, flat mono, inline currentColor SVG,
NO emoji, vi-first with en gloss. Renders on a phone.

**A6 — Consent withdrawal.** `health.consent` withdrawal must not keep
live pages: simplest is at render — re-run the A2 check on every page
view for the summary section (upcoming/arrived schedule info can stay);
if `check_consent(patient,'data_sharing')` is False at view time,
render the neutral page for completed-state links. No write hooks into
health_consent needed. State this behavior in the module description.

**A7 — Triggers (FSO inherit, both wrapped try/except — a family-link
failure must NEVER block the booking/completion workflow; messaging
module precedent).**
- `action_confirm_booking` post-super → for each eligible relation
  (A2 cond 1+3): get-or-create link, send `family_visit_link` ZNS.
- `action_complete_service` post-super → for each eligible relation
  (A2 all three): extend link expiry, send `family_snapshot` ZNS.
- Re-confirmation / double completion: dedup keys make the sends
  no-op; link get-or-create makes the rows stable.

## B. Safety rails (binding)

- Rides `health_messaging.enabled` (False on vietuat) + `dry_run`
  (True): live verification = `simulated` rows only. Do NOT enable
  live mode; state final switch positions in the report.
- `receives_visit_updates` defaults False — zero behavior change at
  install until a relation is opted in.
- Public page: no PHI beyond the A3-sanitized summary; no patient
  address, no diagnosis, no codes; token URLs are capability URLs —
  never log the full URL at info level.
- ACL: internal read nurse+, create/write via system flows
  (sudo), no unlink below manager. Catchment rule pair on
  health.family.link (template:
  health_consent/security/health_consent_security.xml).

## C. Tests (`tests/test_family_link.py`)

Fixtures per conventions §6 (patient partner needs
catchment_province_id; relation needs a DISTINCT representative
partner — the model CHECK-constrains client != representative; FSO
needs facility+patient+scheduled_datetime; completing needs the stage
prerequisites — inspect health_workflow_auto's tests, they already
walk an FSO to completed). Mock ZNS at the same boundary
health_messaging's tests do. Cases:

1. Consent matrix: opted-in relation + service consent recorded via
   the real health.consent flow → confirm creates link + simulated
   `family_visit_link` row; flag off OR check_consent False → zero
   rows (assert search_count == 0, the no-phantom rule).
2. `can_receive_medical_info=False` → gets the visit-link send but NO
   snapshot send.
3. Snapshot params/page contain no diagnosis text (seed a note with a
   diagnosis field set; assert absence), summary truncates at 200 and
   strips HTML tags.
4. Double confirm / double complete → exactly one row per purpose per
   relation (dedup), one link per (fso, relation).
5. Public page: valid token renders each lifecycle state (upcoming
   wall-clock string correct for `Asia/Ho_Chi_Minh`, arrived shows
   HH:MM, completed shows summary); bogus + expired + revoked tokens
   render the identical neutral page.
6. Consent withdrawn after completion → completed-state page renders
   neutral (A6).
7. Hook resilience: patch the send helper to raise → confirm/complete
   still succeed.
8. Timezone: 02:00 UTC scheduled + Asia/Ho_Chi_Minh → page/params say
   09:00 (the +7 class of bug).

Public-page tests: factor render-data assembly into a model method
(`_page_context()`) and test it directly + one HttpCase GET smoke
(established pattern).

## D. Deploy & verify

- `-i health_family_link --test-tags /health_family_link` + re-run
  `/health_messaging` (you extend its selection — prove no regression).
  No PWA bump.
- Live verify on vietuat (safe under dry_run): opt in a relation on a
  demo client (861–864), record a service+data_sharing consent, confirm
  + complete a demo FSO, show the `simulated` rows, open the token URL
  through the lifecycle and describe each render. Leave
  `health_messaging.enabled` OFF.
- vi.po, conventions §8, commit+push.

## E. Report-back extras

(a) final `health_messaging.enabled`/`dry_run` positions; (b) the
demo client/relation/FSO ids used + the token URL page text at each
state; (c) exact summary-source precedence hit in your live demo;
(d) how you modeled outbound_message linkage (A4); (e) any new
ledger-grade gotcha (explicitly flagged).
