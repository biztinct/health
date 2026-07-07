# Handover: H0 Ops Quick Wins — `health_workflow_auto`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8, gotcha ledger now has 15 entries — read all).

**Primary spec: `docs/strategy/design-platform-services.md` §E
(lines ~746–985) — implement it as written.** It is implementation-grade:
model/field tables, method bodies, confirmed selection values, verified
line numbers, and per-feature acceptance criteria (turn those acceptance
lists into your tests). This handover is the DELTA SHEET: the spec was
written before several modules shipped, so the amendments below OVERRIDE
the spec wherever they conflict. Everything else: follow §E exactly.

## 0. Scope recap (one new glue module `health_workflow_auto`)

1. **E.2 Exception-only one-tap visit completion** (+ PWA button).
2. **E.3 Nightly Red Invoice batch submission + retry queue.**
3. **E.4 Timecards auto-filled from visit check-in/out + mismatch queue.**
4. **E.5 Instant first-visit offer at lead qualification** (public
   accept page).

Non-goals: §F PWA items other than the one-tap sheet (EVV parts already
shipped in health_evv); §D references (superseded — see A2); glove
mode/sunlight theme (separate phase); SMS/voice channels.

## A. Amendments (override §E where they conflict)

**A1 — Manifest depends.** Replace `health_messaging_auto` with
`health_messaging` (the shipped module). Add `health_api_gateway` (for
A5 rate limiting). Keep the rest as §E.1; verify each is installed on
vietuat before relying on it.

**A2 — E.5 send path (spec references a D.3 engine that was never
built).** The shipped messaging module is `health_messaging` with
`health.outbound.message` (see
`docs/strategy/handovers/messaging-phase.md` §2–3 and the module
itself). Adapt:
- `health.visit.offer.delivery_id` → `outbound_message_id` m2o
  `health.outbound.message`.
- Sending: extend `health.outbound.message.purpose` selection with
  `('visit_offer', 'First-Visit Offer')` (selection_add via inherit in
  this module). Build the ZNS params in health_workflow_auto and log
  through a small helper that mirrors the messaging module's ZNS step:
  respect **`health_messaging.enabled` and `health_messaging.dry_run`
  exactly** (dry_run → state `simulated`, no real send — vietuat holds
  real phones), reuse its zalo client accessor and its
  try/except-normalize_vn_phone pattern (ledger §5.15), dedup_key
  `offer-<offer_id>`.
- Template id config param: `health_workflow_auto.zns_template_visit_offer`
  (empty default → ZNS step skipped, offer still created, lead activity
  “send offer manually” instead — degrade gracefully like the cascade).
- The `link` param uses `web.base.url`.

**A3 — E.2 PWA one-tap UI, without touching health_pwa.** Conventions §4:
this module ships its own `static/src/js/onetap-*.js` (window globals)
injected via QWeb inheritance of `health_pwa.app_shell` — the
incident/consent modules are the copy-paste precedent. The sheet is
**online-only**: on opening a visit in state `in_progress`, when
`navigator.onLine`, call `GET /health_pwa/api/fso/<id>/onetap_eligible`
and show the one-tap button only on `eligible=true`; on `needs_review`
route to the existing quote screen. Do NOT modify
`health_pwa/controllers/sync.py` (spec §F.3's `onetap_eligible` sync key
is CANCELLED — the live GET replaces it). ⇒ **PWA bump required:
1.4.0 → 1.5.0** in all 5 places + manifest `.17 → .18`, deploy
health_pwa alongside (conventions §3).

**A4 — E.2 endpoint tail.** The spec offers a choice ("factor the tail
into a helper ... if touching health_pwa is approved; otherwise
duplicate"). Ruling: do NOT touch health_pwa — duplicate the
invoice/payment tail from `health_pwa/controllers/api.py` (~L823-885)
into this module's controller with a comment naming the source lines
(established duplication convention).

**A5 — E.5 rate limiting.** "gateway counter (B.8)" = the shipped
`health_api_gateway` rate-counter model (it has an `init()` unique index
and an ON CONFLICT upsert — inspect `gateway_rate_counter.py` and call
its public increment/check method). 10 req/min/IP on both public offer
routes; over-limit → the friendly expired/unavailable page (no
OperationOutcome — these are human-facing pages).

**A6 — E.4 verification order.** `action_complete_service` sets
`actual_end_datetime` (spec cites L2795/2825) — call
`_attendance_close()` AFTER super() so the value exists; if
`actual_end_datetime` is falsy (defensive), use `fields.Datetime.now()`.
The E.5 acceptance item 1 wording "flagged stage" is stale — the trigger
is `action_convert_to_client()` per the spec body (+ the manual button).

**A7 — Timezones.** Offer page + ZNS slot params render wall-clock in
the client's facility/booking timezone (pytz pattern from
health_messaging — ledger's most-repeated bug class). Slot storage
follows the availability matrix's own conventions — inspect how
`health.staff.availability.matrix` stores date/time before formatting.

**A8 — Public page style.** Server-rendered QWeb, self-contained inline
CSS, flat mono colors, hf-wt-ico CSS-mask icons, NO emoji, vi-first
labels with en fallback (`lang` from partner). It renders on a phone.

## B. Safety rails (binding)

- All four features ship BEHIND config params (settings block
  `health_workflow_auto.*`): `onetap_enabled` (default **True** — it
  only adds a button), `redinvoice_batch_enabled` (default **False** —
  it talks to Viettel production), `timecard_sync_enabled` (default
  **False** — it writes payroll-adjacent hr.attendance), offers ride
  `health_messaging.enabled`/`dry_run` (per A2). Live verify on vietuat
  accordingly: one-tap on a demo FSO is fine; leave redinvoice batch +
  timecard sync OFF after testing via unit tests only; offer flow in
  dry_run with a demo lead. State the final switch positions in your
  report.
- Public offer controller: sudo() is confined to the two routes; token
  `secrets.token_urlsafe(24)`; row-lock (`FOR UPDATE`) on accept;
  expired/invalid tokens all render the same neutral page (no
  existence oracle).
- Crons: per-record savepoints, one failure never aborts the batch
  (§E already specifies this — it is also ledger discipline).

## C. Tests

Implement each §E acceptance list (E.2 items 1–5, E.3 items 1–5, E.4
items 1–5, E.5 items 1–6) as tests wherever it does not require real
network — mock the Viettel submit at `_redinvoice_issue`'s HTTP boundary
and the ZNS client exactly as health_messaging's tests do (inspect
them). Conventions §6 fixtures apply (patients need
catchment_province_id; FSO needs facility+patient+scheduled_datetime;
staff assignment before action_start_service; the current user needs an
hr.employee). E.5 tests: create availability-matrix fixture rows —
inspect that model's required fields first. Public-controller logic:
factor accept/validate into model methods and test those directly
(established pattern), plus one HttpCase smoke test of the GET page if
straightforward.

## D. Deploy & verify

- `-i health_workflow_auto -u health_pwa --test-tags
  /health_workflow_auto` + re-run `/health_messaging` (you extend its
  selection — prove no regression).
- PWA bump per A3; verify served shell shows 1.5.0 and the one-tap
  globals exist (`window.healthOnetap*`).
- Live verify (per B): demo FSO one-tap end-to-end; offer created for a
  demo lead in dry_run (`simulated` row + working public page — open the
  token URL and screenshot-describe it); redinvoice/timecard verified by
  tests only, switches left OFF.
- vi.po, conventions §8, commit+push.

## E. Report-back extras

(a) final positions of all four feature switches on vietuat;
(b) the duplicated invoice-tail source line range and any drift you
found in it; (c) availability-matrix required fixture fields;
(d) the demo lead/FSO ids used; (e) any new ledger-grade gotcha
(explicitly flagged).
