# health_bhyt Phase 1 — BHYT Claim Spine + Coverage Engine — Implementation Report

**Module:** `health_bhyt` 19.0.1.0.0 (NEW) · **Branch:** 19.0 · **Server:** vietuat
**Handover:** `docs/strategy/handovers/bhyt-claims-phase1-spine.md`
**Result:** `0 failed, 0 error(s) of 14 tests` · EXIT:0 · HTTP:200 · live on vietuat

---

## 1. What was built (file list)

New module `health_bhyt` — completed+invoiced visit → structured BHYT claim with a
transparent BHYT-covered vs patient-copay split, a worklist, and an append-only audit.
Reads the posted invoice; **writes no accounting**.

```
health_bhyt/
  __init__.py, __manifest__.py
  models/
    bhyt_coverage.py         VERBATIM §2.2 coverage kernel (pure, no ORM)
    bhyt_config.py           config-param helpers (bhyt.* namespace; clone of twin_config)
    res_partner.py           patient BHYT extension (scheme/rate/beneficiary/facility/bhyt_valid)
    bhyt_claim.py            bhyt.claim + generation (_build_claim_for) + cron + evidence-lock
    bhyt_claim_line.py       bhyt.claim.line + per-line split via the kernel + parent-lock guard
    bhyt_claim_event.py      bhyt.claim.event append-only audit (clone of consent.check.log)
    health_fieldservice_order.py   FSO _inherit: "Generate BHYT Claim" button (no health_fieldservice edit)
  security/
    ir.model.access.csv      finance/admin/owner ACLs (event = read-only)
    bhyt_security.xml         catchment record rules (finance own-catchment; owner all)
  data/
    ir_sequence.xml          BHYT/%(year)s/##### (no_gap)
    bhyt_params.xml          bhyt.generate_enabled=False, generate_batch_cap=500, default_covered=True
    bhyt_provider_data.xml    seed BHYT health.insurance.provider (80% default)
    bhyt_cron.xml            daily config-gated batch generation (OFF by default)
  views/
    bhyt_claim_views.xml     list / form (split + totals footer + audit tab + chatter) / search / action
    res_partner_views.xml    BHYT page on the STANDARD + OPS patient forms (§5.41)
    health_fieldservice_order_views.xml   finance-gated generate button on the FSO header
    bhyt_menus.xml           top-level "BHYT Claims" menu (see deviation D2)
  i18n/vi.po                 Vietnamese catalog (every entry carries `#. module:` per §5.29)
  tests/test_bhyt.py         14 tests (3 kernel + 11 model/flow/security)
```

Sanctioned-edit compliance (§2.8): **only** files inside the new `health_bhyt` module + an
`_inherit` of `health.fieldservice.order` **inside** health_bhyt. No edit to account /
account.move / account.move.line / health_invoicing / health_redinvoice / advanced_pricing /
health_fieldservice / PWA. Confirmed by `git status` (all new files under `addons/health_bhyt/`).

---

## 2. Test results (verbatim)

```
odoo.tests.stats: health_bhyt: 18 tests 7.12s 3799 queries
odoo.tests.result: 0 failed, 0 error(s) of 14 tests when loading database 'vietuat'
EXIT:0   HTTP:200
```
(18 test methods across 2 classes; the result line counts 14 tagged cases. The
`test_bhyt.py line 291 in _side` traceback in the server log is the **intentional** `boom`
exception raised by the never-block savepoint test — logged by the cron's
`_logger.exception`, not a failure.)

Coverage of handover §4: kernel vectors + rounding invariant + claim_totals (1–3);
generate/mirror/snapshot (4); idempotent (5); not-eligible ×3 no-raise (6); uncovered-line
→ all patient + totals recompute (7); evidence-lock as uid 1 + reset unlocks + reset event
(8); append-only event write/unlink raise (9); unlink state-guard (10); cron gate + savepoint
survives a bad order (11); cron batch cap (12); catchment + create-ACL security (13);
bhyt_valid compute (14).

## 3. Kernel proof on live data (report item b)

Seeded a real completed+invoiced BHYT visit (2 invoice lines) and generated a claim:

```
claim BHYT/2026/00001
SPLIT total=450000  bhyt=360000  patient=90000   (covered+copay == total: True)
LINES  Kham va tu van (consult):  elig=300000  bhyt=240000  copay=60000
       Vat tu tieu hao (supplies): elig=150000  bhyt=120000  copay=30000
```
Per-line-then-sum through the single kernel; the invariant holds exactly (no đồng lost/created).

## 4. Browser evidence pack

`docs/strategy/reports/bhyt-phase1-evidence/` (owner login; console clean on every screen):
1. `1-claims-worklist.png` — BHYT Claims worklist, split columns + "Draft or Ready" default filter + column sums.
2. `2-claim-form-split.png` — claim form: frozen BHYT snapshot + per-line transparent split + totals footer (450k = 360k + 90k) + chatter at bottom.
3. `3-audit-trail.png` — append-only "Generated" event (450,000₫ snapshot).
4. `4-patient-bhyt-fields.png` — the **BHYT tab on the OPS profile** (the real user surface, §5.41): scheme / rate 80.00 / beneficiary DN / facility / valid ✓ / card DN4790012345678 / expiry.

## 5. No accounting writes (report item c)

`grep` of the module diff for `.write(/.create(/action_post/_create_invoices` on any
`move|invoice|sale|account` model → **NONE**. The claim only *reads* `order.invoice_id`,
`invoice.invoice_line_ids`, `iline.price_subtotal/price_unit/quantity/product_id` and snapshots
them. No sale.order / account.move(.line) mutation anywhere.

## 6. Eligibility population on vietuat (report item d, read-only)

```
completed+invoiced = 1   +posted-invoice = 1   +bhyt_valid = 1   (that 1 is the QA fixture)
```
The **real** pre-existing BHYT-eligible population is effectively **0**: almost no live visit
carries both a *posted* invoice and a patient with a non-expired BHYT card
(`insurance_number` + `insurance_expiry ≥ today`). Data-honesty note: the claim population
will only grow once BHYT card data is captured on patients AND their completed visits are
invoiced-and-posted. The generation gate is honest — it silently yields nothing today rather
than fabricating claims.

## 7. QA cleanup + fresh-cursor verify (report item e, §5.34/§5.45)

All seeding/cleanup done **after** the deploy run fully returned (never during — §5.45; one
odoo process on the DB at a time). Cleanup deleted claim+events (id 14), FSO, invoice
(draft+unlink), and patient. **Fresh-cursor** re-check in a separate shell:
```
claims_remaining=0  qa_patient_exists=False  qa_fso_exists=False  qa_invoice_exists=False
events_remaining=0  provider_seed_intact=True
```
(The BHYT provider data-seed is intentionally kept — it is module data, not QA.)

---

## 8. Deviations from the handover design (with reasoning)

- **D1 — Kernel negative-input vector corrected in the TEST, not the kernel.** The §2.2
  worked-vector line states `coverage_split(-500, 80) → (0, 0)` ("negative eligible clamps to
  0"). The **verbatim kernel does not do that**: it clamps only `total` via `max(0, ·)`, but
  computes `covered` from the *raw* (negative) eligible, so `coverage_split(-500, 80)` actually
  returns `(-400, 400)`. The money **invariant still holds** (`covered + copay == clamped
  total == 0`). Per the binding instruction "copy the kernel VERBATIM; do not alter the kernel
  math", I copied it unchanged and made the test assert the *faithful* behavior
  (`sum(cs(-500,80)) == 0` and `== (-400, 400)`) with an explanatory comment. **This is a real
  discrepancy in the handover for Fable to reconcile** (see §10 gotcha). It never fires in
  production: `eligible_amount` is always an invoice `price_subtotal ≥ 0`.

- **D2 — Dedicated top-level "BHYT Claims" menu instead of nesting under Finance Center.** The
  handover suggested the health_invoicing finance menu parent. That parent
  (`health_invoicing.menu_fin_center_root`) is gated to `group_health_invoicing_user`, and the
  claim's own audience `group_healthcare_finance` (and manager/owner) does **not** imply that
  group (verified: the implications run invoicing-manager → invoicing-user, never from the
  healthcare ladder). Nesting there would hide the worklist from its own audience *and* from
  the owner QA user. I created a top-level menu gated to `group_healthcare_finance`. Verified
  reachable in the evidence pack.

- **D3 — Accepted the FSO completed-state set `('completed','completed_pending_invoice','closed')`**
  (the real FSO selection) as the generation gate, layered with the hard `is_invoiced` +
  posted-invoice + `bhyt_valid` gates. `completed_pending_invoice` in practice fails the
  invoiced gate, so this is permissive-but-safe and matches the twin sweep's completed set.

No other deviations. Flat-mono UI, chatter-at-bottom, `#. module:` on every vi.po entry,
unconditional evidence/append-only guards (uid-1-su safe), unique `fso_id` index in `init()`,
per-order savepoint generation — all per conventions.

## 9. Deferred (unchanged from handover non-goals)

Decision-4210 (QĐ 4210) wire XML + VSS/BHXH submission = **Phase 2** (needs the official
current XSD / a real sample XML; the claim state machine ships stopping at `ready`, with
`submitted/acked/rejected` declared in the Selection but no transition into them). No tax
e-invoice (that is `health_redinvoice`). No referral (đúng/trái tuyến) matrix or annual ceiling
(later refinement — rates/eligibility are data in Phase 1). No auto-submit, no ZNS, no PWA.

## 10. New gotcha discovered (for conventions §5)

**§5.46 — the BHYT §2.2 coverage kernel does NOT clamp `covered` for a negative eligible
amount, only `total`.** `coverage_split(eligible, rate)` computes
`total = _round(max(0, eligible))` but `covered = _round(eligible * rate/100)` from the *raw*
eligible, so a negative eligible yields a negative `covered` and a compensating positive
`copay` (e.g. `(-500, 80) → (-400, 400)`). The money invariant `covered + copay == total`
still holds (both sum to the clamped 0), so downstream totals never leak đồng — but the split
is nonsensical for a negative input. Harmless in Phase 1 because `eligible_amount` is always an
invoice `price_subtotal ≥ 0`. If a future phase ever feeds a negative (e.g. a credit-note line
or a discount adjustment), add `max(0.0, eligible_amount)` to the `covered` line too. The
handover's own worked-vector (`(-500,80)→(0,0)`) is therefore aspirational, not what the
verbatim code does; the test asserts the true behavior so a real transcription slip is still
caught.

## 11. What the Phase-2 4210 serializer will need from the claim model (report item g)

The Phase-1 claim model is XML-agnostic and complete on its own. When the official QĐ 4210
XSD / sample arrives, the serializer will read (all already present, frozen at generation):

- **Claim header:** `name` (claim ref), `service_date`, `patient_id` (name/DOB/gender/national-id
  on res.partner), `bhyt_card_no`, `bhyt_coverage_rate`, `bhyt_beneficiary_code`,
  `bhyt_registered_facility`, `provider_id`, `invoice_id` (the posted invoice ref for
  cross-reference), `currency_id`, `total_amount` / `bhyt_amount` / `patient_amount`,
  `catchment_province_id`, `company_id`.
- **Per-line detail (`line_ids`):** `name`, `product_id`, `quantity`, `unit_price`,
  `eligible_amount`, `covered_service`, `bhyt_amount`, `patient_amount`.
- **State + audit:** `state` (the Selection already declares `submitted/acked/rejected`, so
  Phase 2 adds transitions with **no migration**), the Phase-2 placeholder fields
  `submission_ref` + `error_text` (already writable-while-locked in the evidence-lock allowlist),
  and `event_ids` (append-only; Phase 2 appends `exported/submitted/acked` events).

Phase-2 **gaps to spec once the schema lands** (not blockers now): (a) the 4210 **beneficiary
category enum** (Phase-1 `bhyt_beneficiary_code` is free Char — map to the enum); (b) the
**referral/đúng-trái-tuyến** flag + the 95/100% category rates + annual ceiling (currently the
core split with rate-as-data); (c) facility/KCB **codes** (Phase-1 `bhyt_registered_facility`
is Char); (d) the VSS endpoint/auth + the readonly-cursor-safe write path (ledger §5.38 — do
NOT front the submission POST with the gateway `@api_route` decorator).

---

### Kickoff line (Phase 2, once the official 4210 XSD / sample XML is provided)
`Implement the phase specified in docs/strategy/handovers/bhyt-claims-phase2-4210.md.`
(Phase 2 remains BLOCKED on the user providing the official current QĐ 4210 XSD or a real
sample XML — we will not invent a government schema.)
