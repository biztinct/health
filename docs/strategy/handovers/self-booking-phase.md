# Handover: Client Self-Booking — `health_self_booking`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; the gotcha ledger has 16 entries — read all). This is Tier 3
continuing after `health_family_link`: a tokenized, no-login,
phone-friendly **rebook page** where an existing client books their own
next visit in two taps — pick a slot, done. It attacks the highest-
frequency ops load (phone-call rebooking) with plumbing that already
exists end-to-end: slot proposal, quick-booking builder, packages,
messaging rails, public token pages. No portal accounts (standing
decision), Zalo-first.

## 0. Scope (one new module `health_self_booking` + one surgical refactor)

1. **`health.selfbook.invite`** — a tokenized invite per patient that
   renders proposed slots for "book your service again" and books on a
   POST accept (offer-accept machinery, rebook context).
2. **One refactor inside `health_workflow_auto`** (allowed, see A1):
   extract the partner-level core of `_propose_first_visit_slots` so
   this module can propose slots WITHOUT a crm.lead.
3. **ZNS purpose `selfbook_invite`** through the shipped rails +
   manual "Send booking link" button on the patient form; optional
   auto-invite after visit completion (config, default OFF).

**No PWA change ⇒ NO PWA bump.** The page is server QWeb like the
offer/family pages, not part of the nurse PWA.

**Non-goals (binding):** new-prospect public lead capture (spam +
no consent anchor — separate phase); full service-catalog browsing
(v1 is REBOOK: the patient re-books what they already buy); payments
on the page; portal accounts; telehealth; any edit to health_pwa,
health_messaging, or health_family_link existing files.

**Synergy to be aware of:** booking confirm on the created FSO fires
`health_family_link`'s post-super hook automatically — opted-in
relations get their family link ZNS with zero code here. State this in
the report after observing it in the live demo.

## 1. Verified plumbing facts (do not re-derive; line refs verified Jul 2026)

- **Slot proposal**: `health_workflow_auto/models/visit_offer.py:110-175`
  `_propose_first_visit_slots(lead, count=3, horizon_days=7)` resolves
  `partner = lead.patient_id or lead.partner_id`, then uses ONLY partner
  fields: requires `partner.primary_facility_id` +
  `partner.catchment_province_id`; queries
  `health.staff.availability.matrix`
  (health_fieldservice/models/health_staff_availability.py) with
  `status='available'`, `remaining_capacity>0`,
  `conflict_detected=False`, province match-or-null, ordered
  `availability_date, start_time`; slot dicts
  `{date, start_time, staff_id, staff_name, confidence}` deduped by
  (date, start_time) keeping highest confidence; confidence from
  `health.ai.assignment.engine._calculate_assignment_confidence`
  (health_ai_assignment_engine.py:419-440) with 0.5 fallback.
- **Accept pipeline precedent**: `visit_offer.py` `accept_slot` —
  `SELECT ... FOR UPDATE` row lock + `invalidate_recordset(['state'])`
  for race safety; then `action_create_from_quick_booking_owl(vals)`
  (health_fieldservice/models/health_fieldservice_order.py:5488-5640)
  with **`patient_id`, NEVER `lead_id`** (ledger §5.16), `draft_only:
  True`, `product_lines`; then
  `action_assign_staff_to_fso(staff_id, assignment_role='lead')`
  (L2489-2513); then `action_confirm_booking()` (L2121-2165) which
  requires `scheduled_datetime` + (quote with lines OR active package
  with remaining services); then
  `health.staff.availability.matrix.book_staff_slot(staff_id,
  datetime_utc, duration_mins, fso_id)`.
- **Packages**: `health.service.package`
  (health_invoicing/models/health_service_package.py) —
  `remaining_services`, `state='active'`, `patient_id`,
  `service_type`; FSO links via `package_ids` m2m; confirm calls
  `_reserve_package_service` (consumes 1), cancel releases. A confirm
  with a valid package needs NO quote line.
- **Preferred nurse**: `res.partner.preferred_staff_id`
  (health_fieldservice/models/res_partner.py:21-26) — already used by
  the internal quick-booking RPC to sort staff.
- **Service products**: `product.product` with `type='service'`,
  `sale_ok=True`; config-param fallback precedent
  `health_workflow_auto.offer_service_product_id`
  (res_config_settings.py:23-27 + `_offer_service_product()`).
- **Public page precedents**:
  `health_workflow_auto/controllers/offer_public.py` (GET page + POST-
  only accept, `gateway.rate.counter.hit('offer:<ip>')` returning
  `(allowed, retry)`, neutral identical page for every failure mode) and
  `health_family_link/controllers/family_public.py` (read-only variant).
  Templates precedent: `offer_templates.xml` / `family_templates.xml` —
  server QWeb, self-contained inline CSS, flat mono, inline currentColor
  SVG, NO emoji, vi-first with en gloss.
- **ZNS purpose extension precedent**:
  `health_family_link/models/outbound_message.py` (`selection_add` +
  `ondelete: cascade`); send-path template =
  `health_family_link/models/health_family_link.py::_send_zns`
  (enabled→skipped before dry_run→simulated; empty template param →
  row NOT created; `_safe_phone` try/except per ledger §5.15; dedup
  search-first).

## A. Design

**A1 — Slot refactor (the ONE allowed edit outside the new module).**
In `health_workflow_auto/models/visit_offer.py`, extract the body of
`_propose_first_visit_slots` into
`_propose_slots_for_partner(partner, count=3, horizon_days=7)` (same
model, `@api.model`); the lead-facing method becomes a two-line wrapper
that resolves `lead.patient_id or lead.partner_id` and delegates.
Behavior for the lead path must be byte-identical — prove it by
re-running `/health_workflow_auto` (21 tests) green. Do not change any
other file in that module.

**A2 — `health.selfbook.invite` model.**
| field | notes |
|---|---|
| patient_id | m2o res.partner, required, index |
| token | Char required index, `secrets.token_urlsafe(24)`, unique index in `init()` (ledger §5.1) |
| state | sent / booked / revoked (Selection) |
| expires_at | Datetime = create + `health_self_booking.invite_ttl_days` (config, default 14); render-time check, NO cron (family-link precedent) |
| fso_id | m2o health.fieldservice.order, set on accept |
| service_product_id / package_id | resolved at INVITE time (A3) and snapshotted so the page is stable |
| outbound_message_id | m2o health.outbound.message |
| slots_json | Json — slots snapshotted at invite creation so accept indexes are stable (offer precedent stores slots on the offer; mirror that: a slot child model like health.visit.offer.slot or Json — your call, report it) |
One ACTIVE invite per patient: search-first on
`(patient_id, state='sent', expires_at > now)` before creating.
Re-send on an existing active invite = same token, dedup makes the ZNS
a no-op.

**A3 — What "book again" offers (precedence, resolved at invite time).**
1. Patient's ACTIVE `health.service.package` with
   `remaining_services > 0` → book against the package
   (`package_id` in the builder vals, no product line; confirm
   reserves 1 service). If several, most recent.
2. Else the first service product line of the patient's most recent
   completed FSO's quote (inspect the FSO→sale.order field name in
   health_fieldservice — do not guess it; report what you found).
3. Else config `health_self_booking.fallback_service_product_id`
   (empty → invite creation refuses with a UserError on the manual
   button, and auto-invite silently skips — never create an invite
   that cannot confirm).
`service_type` copied from the same source (package.service_type or
the last FSO's service_type, default 'home_visit').

**A4 — Slots on the page.** `_propose_slots_for_partner(patient,
count=6, horizon_days=10)` (both numbers config params). If the
patient has `preferred_staff_id`, stable-sort the returned slots so
that staff's slots come first WITHIN the same date (do not drop other
staff — preference, not a filter). Zero slots → invite still created;
page renders a "call us" body with the facility phone (no dead end).

**A5 — Public controller (clone offer_public.py conventions).**
- GET `/booking/self/<token>` — rate key `selfbook:<ip>`;
  invalid/expired/revoked/over-limit → identical neutral page;
  `state='sent'` → slot page (patient given name, service name, price
  hidden v1 — pricing rules run at quote level and a wrong public
  price is worse than none; state this in the report); `state='booked'`
  → booked summary (date wall-clock, time window, staff given name,
  facility phone) — keep rendering until expiry.
- POST `/booking/self/<token>/accept/<int:slot_index>` — **POST-only**
  (methods=['POST']; the GET-side effect rule from the offer page).
  Row-lock the invite (offer accept_slot pattern), re-check
  state/expiry under the lock, re-verify the matrix row is still
  available, then run the accept pipeline (§1): builder with
  `patient_id` + `draft_only` (+ `package_id` or `product_lines`),
  assign staff (slot's staff, role 'lead'), `action_confirm_booking()`,
  `book_staff_slot(...)`, write `state='booked'`, `fso_id`. Double-POST
  → second request sees state='booked' under the lock and re-renders
  the booked page (idempotent, no second FSO).
- All datetimes on the page wall-clock via pytz in the FSO/patient
  facility timezone (the +7h bug class — family-link `_wall` helper is
  the template).
- Sudo confined to the routes. Never log the token URL at info level.

**A6 — Triggers.**
- Manual: "Gửi link đặt lịch (Send booking link)" button on the
  patient form (ops/manager groups) → get-or-create invite +
  `selfbook_invite` ZNS to the PATIENT's own phone (mobile-then-phone;
  no relation consent needed — the recipient is the data subject;
  messaging rails still govern). Dedup key `selfbook-<invite_id>`.
  Template param `health_self_booking.zns_template_invite` (empty →
  row not created, family-link precedent).
- Auto: `health_self_booking.auto_invite_after_completion` (config,
  default **False**) → `action_complete_service` post-super,
  try/except-wrapped (a self-booking failure must never block
  completion — A7 family-link precedent), creates invite + ZNS.

**A7 — ACL/security.** Internal read nurse+, create/write via system
flows (sudo) + manager, no unlink below manager; catchment rule pair
on the invite model (family-link security files are the template).

## B. Safety rails (binding)

- Rides `health_messaging.enabled` (False on vietuat) + `dry_run`
  (True): live verification = `simulated` rows only. Leave both as-is;
  state final positions in the report.
- `auto_invite_after_completion` defaults False — installing changes
  nothing until a human opts in or presses the button.
- Booked slot must be re-verified under the lock at accept time — an
  invite link can be opened days after the slots were proposed; a
  stale slot renders "slot no longer available, here are fresh ones"
  (re-propose) rather than double-booking staff.
- Page shows no address, no diagnosis, no price (v1), no package
  balance beyond "gói của bạn (your package)" wording.
- Do NOT commit `__pycache__`/*.pyc (now repo-gitignored; the family
  phase accidentally committed them).

## C. Tests (`tests/test_self_booking.py`)

Fixtures per conventions §6 (patient needs catchment_province_id +
primary_facility_id; matrix rows seeded for slots; walking an FSO to
completed — copy health_workflow_auto/health_family_link test helpers).
Mock ZNS at the same boundary health_messaging's tests do. Cases:

1. Invite idempotency: two sends → one active invite, one outbound row
   (dedup), same token.
2. A3 precedence: patient with active package → invite snapshots
   package; without → last-FSO product; neither + empty fallback →
   UserError on button / silent skip on auto.
3. Accept books: FSO confirmed, staff assigned (slot's staff, lead),
   matrix slot booked, invite state='booked' + fso_id; with package →
   `consumed_services` +1 and no quote line; without → quote line with
   the product present.
4. Double-POST race → exactly one FSO (threaded or sequential
   re-entry, offer test precedent).
5. Accept route rejects GET (405) — the POST-only pin.
6. Bogus + expired + revoked tokens → identical neutral page
   (HttpCase through the render path — assert the response body, not
   just flags; this was the family-phase test gap, close it here).
7. Booked invite GET → booked summary with wall-clock time (02:00 UTC
   + Asia/Ho_Chi_Minh → page says 09:00).
8. Rails: dry_run → `simulated`; empty template param → zero rows;
   enabled=False → `skipped`.
9. Auto-invite: config off (default) → completing an FSO creates
   nothing; on → invite + row; patched `_send_invite_zns` raising →
   completion still succeeds.
10. Preferred staff: slots for the preferred nurse sort first within
    the same date.
11. Zero feasible slots → invite created, page renders the call-us
    body (no crash, no dead end).
12. `/health_workflow_auto` still green after the A1 refactor (run the
    whole tag, don't cherry-pick).

Factor page data into `_page_context()` tested directly + HttpCase
smokes (established pattern). HttpCase present ⇒ do NOT pass
`--no-http` in the deploy test command.

## D. Deploy & verify

- `-i health_self_booking -u health_workflow_auto --test-tags
  /health_self_booking,/health_workflow_auto,/health_messaging`.
  No PWA bump.
- Live verify on vietuat (safe under dry_run): demo client 861–864
  with a seeded matrix row, press the button, show the `simulated`
  row + token URL; open the page, accept a slot, show the confirmed
  FSO + booked page render; observe the family-link hook firing on
  the same confirm (if relation 60's opt-in is still set from the
  family demo). State final switch positions.
- vi.po, conventions §8, commit+push on 19.0.

## E. Report-back extras

(a) final `health_messaging.*` + `health_self_booking.*` param
positions; (b) demo ids + the page text at sent/booked/neutral states;
(c) which A3 precedence branch your demo hit and the FSO→quote field
name you found; (d) how you modeled the slot snapshot (Json vs child
model); (e) the `visit_offer.py` refactor diff (prove the lead path is
delegation-only); (f) any new ledger-grade gotcha (explicitly flagged).
