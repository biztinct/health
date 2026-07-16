# health_bhyt Phase 1 — BHYT Claim Spine + Coverage Engine (the revenue core)

First phase of the **BHYT (social health insurance) claims** stream. It turns a
completed, invoiced visit into a **structured insurance claim** with a
transparent **BHYT-covered vs patient-copay split**, a claim worklist, and an
append-only audit — the revenue/reconciliation core.

**Binding staging (why the XML is NOT here):** the Decision-4210 (QĐ 4210/QĐ-BYT)
wire XML submitted to Vietnam Social Security (VSS/BHXH) is a precise, revised
government schema. It is a **Phase 2** deliverable that needs the official
current XSD / a real sample XML — do NOT invent it here. Phase 1 builds the
internal claim representation the Phase-2 serializer will read; it must be
XML-agnostic and complete on its own.

Read `HANDOVER-CONVENTIONS.md` first (§4 module structure, §5 ledger — esp.
§4-uid-1-su for the immutability guard, §5.9 raw-SQL fixtures; §2 deploy;
§5.45 no-concurrent-odoo-bin-during-upgrade). All plumbing below is
pre-verified from a live scout — do not re-derive.

**Money path:** the coverage kernel is authored VERBATIM in §2.2 (Fable-owned,
copy as-is like `twin_score.py`) with exhaustive numeric test vectors. Do NOT
alter the kernel math; a transcription slip must be caught by a test.

---

## 0. Scope and binding non-goals

**Build — NEW module `health_bhyt` (depends: health_invoicing, health_base,
health_fieldservice, account, health_consent):**
1. Patient BHYT extension on `res.partner`: coverage rate, beneficiary
   category, registered facility, provider link, a `bhyt_valid` computed.
2. `bhyt_coverage.py` — a PURE coverage-split kernel (verbatim §2.2), VND-safe.
3. `bhyt.claim` (one per completed+invoiced FSO) + `bhyt.claim.line` (mirrors
   the invoice lines with per-line covered/copay split) + totals + a state
   machine (draft → ready) with an evidence-lock once `ready`.
4. Claim GENERATION from a completed+invoiced visit (action + config-gated
   batch), never-block, idempotent (one claim per FSO).
5. Append-only `bhyt.claim.event` audit log (clone `health.consent.check.log`).
6. Catchment security (clone health_invoicing rules) + groups. Worklist + form
   UI + menu. Config params. Tests + vi.po. Module 19.0.1.0.0.

**Binding NON-goals:**
- NO Decision-4210 XML, NO VSS/BHXH submission, NO gateway calls (Phase 2 —
  needs the official schema). The claim state machine STOPS at `ready`;
  `submitted`/`acked`/`rejected` states may be DECLARED in the Selection (so
  Phase 2 adds no migration) but NO transition into them ships here.
- NO tax e-invoice work — that is `health_redinvoice` (Viettel SInvoice → GDT
  tax), a DIFFERENT system/schema/recipient. Do NOT touch it or conflate.
- NO change to how invoices are generated (that is health_invoicing /
  sale.order → account.move; the claim READS the posted invoice, never writes
  accounting). NO write to account.move / account.move.line.
- NO auto-submit, NO messaging/ZNS, NO PWA (backend), NO pip.
- NO hardcoded referral (đúng/trái tuyến) matrix or ceiling law in the kernel —
  Phase 1 models the CORE split (eligible × rate) with rates/eligibility as
  data; the full referral/ceiling refinement is a later phase.

---

## 1. Verified plumbing facts (do not re-derive) — from the live scout

- **Invoice from visit:** `health_invoicing/models/health_fieldservice_order.py`
  — FSO has `invoice_id` M2O `account.move` + `is_invoiced` Boolean; invoice is
  created via `sale_order_id._create_invoices(final=True)` then `action_post()`
  (:256-270). **The claim reads `order.invoice_id` (a posted account.move) —
  never creates/writes it.**
- **Invoice lines:** standard `account.move.line`. Healthcare extensions on it:
  `healthcare_service_category` (Selection), `staff_member_id`,
  `service_duration_minutes`, and PLACEHOLDER `is_insurance_covered` /
  `insurance_coverage_percentage` (no active compute) at account_move_line.py
  :1386-1400 — you MAY read these as the per-line "BHYT-eligible" hint but the
  claim carries its OWN split fields (do not depend on the placeholders).
- **Billable/complete gate:** a visit is invoiceable only with a quote-with-
  lines or a package, and completes only with `clinical_notes_submitted`
  (health_fieldservice_order.py `action_complete_service` ~:466-521). So a
  claim-eligible visit = state completed/closed AND `is_invoiced` AND the
  patient has BHYT (below).
- **Patient BHYT today (res.partner, health_base/models/res_partner.py):**
  `insurance_number` (:127, the BHYT card no.), `insurance_provider` (:126,
  Char), `insurance_expiry` (:128, Date), `payment_method` Selection incl.
  `'insurance'`/`'government'` (:129-136). **Missing → you add:** coverage rate,
  beneficiary category, registered facility, provider M2O.
- **Insurance provider lookup:** `health.insurance.provider`
  (health_base/models/health_lookup.py:169-200) — has `code`,
  `coverage_percentage` (default), `deductible_amount`, `max_coverage_annual`,
  `currency_id`. Link the patient to one; seed a BHYT provider record.
- **Coverage-split precedent (partial):** `health.service.billing`
  (health_invoicing/models/healthcare_service_billing.py:161-176) computes
  `insurance_covered_amount`/`patient_responsibility_amount` from a % — a
  precedent, NOT the source of truth; the new kernel is authoritative.
- **FHIR BHYT identifier:** `health_fhir_core/serializers/patient.py:99-103`
  emits `insurance_number` as `{'system':'urn:health19:bhyt','value':…}` — keep
  this the canonical BHYT card field (do not introduce a second card field).
- **Append-only precedents (clone the strictest):**
  `health.consent.check.log` (health_consent/models/health_consent_check_log.py
  :12-52) — pure append-only, `write()`/`unlink()` both raise unconditionally
  (§4 uid-1-su: guards must be UNCONDITIONAL). Also `fhir.submission.log`
  (health_fhir_adapter_base/models/fhir_submission_log.py:15-98) — a
  draft→exported→submitted→acked state machine with writable-after-draft guards
  + append-only unlink; the CLAIM state/lock pattern clones THIS.
- **VND rounding:** `currency_id.round(amount)` (VND `rounding=1.0`, integer đồng)
  — EVERY monetary result of the kernel passes through the claim's
  `currency_id.round()` at the model layer (the pure kernel takes a `round_to`
  int, default 1). Precedent: sale_order_line combo rounding.
- **Security template:** `health_invoicing/security/health_invoicing_security.xml`
  :59-96 — the catchment + company + owner ir.rule trio for a client-scoped
  financial model (user/manager read+write+create, no unlink; owner all). Clone
  it; `catchment_province_id` computed from the patient
  (`res.partner._get_health_catchment_province()`,
  health_base/models/res_partner.py:201).
- Groups ladder: `health_base.group_healthcare_{...,finance,manager,owner}`
  (conventions §4). Gate claims to finance/manager+; owner sees all.

---

## 2. Architecture

health_bhyt 19.0.1.0.0. New module. No accounting writes.

### 2.1 Patient BHYT extension (`models/res_partner.py`, `_inherit='res.partner'`)

Add (all optional, no required-field migration risk on existing partners):
- `bhyt_provider_id` M2O `health.insurance.provider` (the BHYT scheme record).
- `bhyt_coverage_rate` Float (0-100; the patient's đồng-chi-trả rate, e.g. 80 /
  95 / 100). Default from `bhyt_provider_id.coverage_percentage` if unset.
- `bhyt_beneficiary_code` Char (the beneficiary-group code — kept as free Char
  in Phase 1; the 4210 category enum is Phase 2 with the schema).
- `bhyt_registered_facility` Char (nơi đăng ký KCB ban đầu; Char in Phase 1).
- `bhyt_valid` Boolean compute (NOT stored or stored+depends): `insurance_number
  and insurance_expiry and insurance_expiry >= today`. Used to flag claim
  eligibility + a form warning.
- Reuse `insurance_number` (card) + `insurance_expiry` — do NOT add new card
  fields (§1 FHIR canonical).

### 2.2 Coverage kernel (`models/bhyt_coverage.py` — pure, VERBATIM, copy as-is)

```python
# -*- coding: utf-8 -*-
"""BHYT coverage-split kernel — pure functions, no ORM.

Transparent đồng-chi-trả split: for a BHYT-eligible amount and the patient's
coverage rate, return (bhyt_covered, patient_copay) in whole VND. A service not
on the BHYT list (service_covered=False) is 100% the patient's. Every number is
explainable from the inputs — NO ML, NO hidden rules. Referral (đúng/trái
tuyến) and annual ceilings are a later refinement; Phase 1 is the core split.

Copied verbatim from bhyt-claims-phase1-spine.md §2.2 ('kernel — use as-is').
Money: the caller passes round_to (VND=1) and the kernel rounds each output so
covered + copay == the rounded eligible amount exactly (no lost/created đồng).
"""

# kernel — use as-is
def _round(amount, round_to):
    if round_to <= 0:
        round_to = 1
    # Half-up to the nearest `round_to` (VND đồng). amount is a float VND value.
    return int((amount + round_to / 2.0) // round_to) * round_to


def coverage_split(eligible_amount, coverage_rate, round_to=1,
                   service_covered=True):
    """(eligible_amount VND float, coverage_rate 0..100, round_to int,
    service_covered bool) -> (bhyt_covered int, patient_copay int).

    Invariant: bhyt_covered + patient_copay == _round(eligible_amount) always
    (the copay is the REMAINDER after rounding the covered part — money is
    never created or lost to rounding)."""
    total = _round(max(0.0, eligible_amount), round_to)
    if not service_covered or coverage_rate <= 0:
        return (0, total)
    rate = min(100.0, max(0.0, coverage_rate))
    covered = _round(eligible_amount * rate / 100.0, round_to)
    if covered > total:
        covered = total
    return (covered, total - covered)


def claim_totals(lines):
    """Aggregate a list of per-line dicts
    {'eligible': float, 'rate': float, 'round_to': int, 'covered_service': bool}
    into whole-VND totals. Splits EACH line then sums (never split the sum — a
    per-line rate/eligibility differs). Returns
    {'total': int, 'bhyt': int, 'patient': int}; bhyt + patient == total."""
    tot = bhyt = pat = 0
    for ln in lines:
        c, p = coverage_split(ln['eligible'], ln['rate'],
                              ln.get('round_to', 1),
                              ln.get('covered_service', True))
        tot += c + p
        bhyt += c
        pat += p
    return {'total': tot, 'bhyt': bhyt, 'patient': pat}
```

**Worked vectors (bake into the kernel tests):**
- `coverage_split(100000, 80)` → `(80000, 20000)`.
- `coverage_split(100000, 95)` → `(95000, 5000)`.
- `coverage_split(100000, 100)` → `(100000, 0)`.
- `coverage_split(100000, 80, service_covered=False)` → `(0, 100000)`.
- `coverage_split(12345, 80)` → covered `_round(9876.0)=9876`, copay `2469`
  (sum 12345 ✓).
- `coverage_split(0, 80)` → `(0, 0)`; negative eligible clamps to 0.
- INVARIANT test: for a spread of amounts/rates, `covered + copay ==
  _round(eligible)` ALWAYS.
- `claim_totals([{eligible:100000,rate:80,covered_service:True},
  {eligible:50000,rate:80,covered_service:False}])` →
  `{total:150000, bhyt:80000, patient:70000}`.

### 2.3 `bhyt.claim` (models/bhyt_claim.py)

One per FSO (`_sql`/init unique index on `fso_id`, §5.1 — idempotent generation).
- Links: `fso_id` M2O health.fieldservice.order (required, index),
  `invoice_id` M2O account.move (the posted invoice; readonly snapshot),
  `patient_id` M2O res.partner (required, index), `provider_id` M2O
  health.insurance.provider.
- BHYT snapshot AT generation (frozen — don't recompute from live patient
  later): `bhyt_card_no` Char, `bhyt_coverage_rate` Float,
  `bhyt_beneficiary_code` Char, `bhyt_registered_facility` Char,
  `service_date` Date (from FSO scheduled/completed), `currency_id`.
- Lines: `line_ids` O2M bhyt.claim.line.
- Totals (Monetary, computed+stored from lines via the kernel): `total_amount`,
  `bhyt_amount`, `patient_amount`. Compute calls `bhyt_coverage.claim_totals`
  with `round_to = int(currency_id.rounding or 1)`.
- `catchment_province_id` computed+stored from patient (clone, index).
- `company_id` default env.company.
- State: Selection `[('draft','Draft'),('ready','Ready'),('submitted',
  'Submitted'),('acked','Acknowledged'),('rejected','Rejected'),
  ('cancelled','Cancelled')]` default draft — **but only draft⇄ready⇄cancelled
  transitions ship in Phase 1** (submitted/acked/rejected are Phase-2 targets,
  declared now to avoid a later migration; guard `action_mark_ready` /
  `action_reset_draft` / `action_cancel` only).
- `mail.thread` for tracking (state, totals).
- **Evidence-lock once `ready`** (clone fhir_submission_log:write guard, §4
  uid-1-su UNCONDITIONAL): once state in ('ready','submitted','acked'), block
  writes to the snapshot/amount/line fields (a locked claim is the reconciled
  figure); allow only state + a Phase-2 receipt/error field. `unlink()` only in
  draft/cancelled. Reset-to-draft is an explicit action (audited) that unlocks.
- `name`/reference: sequence `data/ir_sequence.xml` noupdate (conventions §4).

### 2.4 `bhyt.claim.line` (models/bhyt_claim_line.py)

Mirrors each invoice line that is BHYT-relevant:
- `claim_id` M2O (required, ondelete cascade), `sequence`.
- `name` Char (service description), `product_id` M2O product.product (from the
  invoice line), `quantity` Float, `unit_price` Monetary,
  `eligible_amount` Monetary (the BHYT-eligible base = line subtotal unless a
  service is out-of-list), `covered_service` Boolean (is it on the BHYT list —
  default True; a manual/data toggle in Phase 1),
  `bhyt_amount`/`patient_amount` Monetary (computed via `coverage_split` with
  the claim's rate + rounding).
- Currency from claim.

### 2.5 Generation (models/bhyt_claim.py + FSO action)

- `_build_claim_for(order)` (@api.model, sudo engine): guard — order completed/
  closed AND `is_invoiced` AND `invoice_id` posted AND patient `bhyt_valid`.
  Idempotent: if a claim exists for the FSO, return it (unique index also
  guards). Snapshot the patient BHYT fields; build one line per invoice line
  (map product/qty/price/subtotal → eligible_amount; covered_service default
  True); totals compute via the kernel. Create in `draft`.
- `action_generate_bhyt_claim()` on health.fieldservice.order (button on a
  completed+invoiced BHYT visit) → `_build_claim_for(self)` + open it.
- `cron_bhyt_generate()` (@api.model, config-gated `bhyt.generate_enabled`,
  default OFF/opt-in): batch over completed+invoiced+bhyt_valid FSOs without a
  claim, per-order savepoint (never-block, clone the twin sweep), batch cap
  (config, default 500), logged. Does NOT auto-mark-ready (human review).
- **Never-block + no double count:** wrap per-order in `cr.savepoint()`; the
  unique `fso_id` index makes a racing double-generate raise → caught → skip.

### 2.6 Append-only audit (models/bhyt_claim_event.py)

`bhyt.claim.event` — clone `health.consent.check.log` (pure append-only,
write/unlink raise UNCONDITIONALLY): `claim_id` M2O (cascade), `event`
Selection `[('generated','Generated'),('marked_ready','Marked ready'),
('reset','Reset to draft'),('cancelled','Cancelled')]`, `user_id`,
`amount_snapshot` Monetary, `note` Char. Written (sudo) on each claim
transition. This is the reconciliation/audit trail (Phase 2 adds
exported/submitted/acked events).

### 2.7 UI (views) + config

- Worklist list of `bhyt.claim`: reference, patient, service_date, provider,
  total/bhyt/patient amounts, state badge, catchment; default filter state in
  (draft, ready); group by state / provider / catchment; search by patient/card.
- Form: readonly snapshot + the line table (service / eligible / covered /
  copay) + a totals footer + the split breakdown; state buttons (Mark Ready /
  Reset to Draft / Cancel) gated by group + state; chatter at bottom.
- Menu "BHYT Claims" under the Billing/Finance menu (find the health_invoicing
  finance menu parent; if none obvious, `health_base.menu_healthcare_clinical`
  is the fallback — verify at build).
- Config params (`data/bhyt_params.xml`, noupdate): `bhyt.generate_enabled`
  (False — opt-in), `bhyt.generate_batch_cap` (500), `bhyt.default_covered`
  (True). §5.36 set_values only if you expose a Boolean in settings (optional).

### 2.8 Sanctioned edits (exhaustive)

| Module | File | What may change |
|---|---|---|
| health_bhyt (NEW) | models/ (res_partner.py inherit BHYT fields, bhyt_coverage.py VERBATIM, bhyt_claim.py, bhyt_claim_line.py, bhyt_claim_event.py, __init__.py), security/ (ir.model.access.csv + bhyt_security.xml groups+rules), data/ (ir_sequence.xml, bhyt_params.xml, seed a BHYT health.insurance.provider record), views/ (claim list/form/search, res_partner BHYT fields on the ops+standard patient form — reuse §5.41 ops-view precedent if surfacing on /bizapp, menus), i18n/vi.po, __manifest__.py, tests | as listed |
| health_fieldservice | — | READ-ONLY. The generate button is added via an `_inherit` of health.fieldservice.order INSIDE health_bhyt (never edit health_fieldservice), same pattern as twin's hooks. |

NO edits to account / account.move / account.move.line / health_invoicing /
health_redinvoice / advanced_pricing. NO PWA.

---

## 3. Safety rails (binding)

- **Reads accounting, never writes it.** The claim snapshots the POSTED invoice;
  it must NOT create/modify/post any account.move or account.move.line, or touch
  sale.order. A claim is a downstream record.
- **One kernel, one source of truth.** All money splits go through
  `bhyt_coverage` + `currency_id.round()`. NO ad-hoc split math in the models or
  views. The invariant (covered+copay==total) is enforced by the kernel and
  asserted in tests — money is never created or lost to rounding.
- **Immutable once ready.** The evidence-lock is UNCONDITIONAL (no su escape,
  §4 uid-1-su) so a reconciled/submitted claim can't be silently altered; only
  an audited reset-to-draft unlocks it. Append-only `bhyt.claim.event`.
- **Never-block generation** (per-order savepoint; idempotent via unique
  fso_id). A bad order can't abort the batch.
- **Eligibility gate** honest: only completed/closed + invoiced + `bhyt_valid`
  patients yield a claim; an expired/absent card → no claim (logged, not
  errored). NO auto-submit (Phase 1 stops at `ready`).
- Catchment security (clone), finance/manager-gated, owner-all. Flat-mono UI
  (§4), chatter bottom. QA fixtures cleaned + fresh-cursor verified (§5.34).
  NO 4210 XML / VSS call / pip.

## 4. Tests (~14, TransactionCase)

**Kernel (pure, fast — the §2.2 vectors):**
1. `coverage_split` 80/95/100 → exact covered/copay; not-covered → all patient;
   0 and negative → (0,0).
2. Rounding invariant: for many (amount, rate) pairs, `covered+copay ==
   _round(eligible)` — no đồng lost/created.
3. `claim_totals` mixed covered/uncovered lines → correct per-line-then-sum.

**Model / flow:**
4. Generate from a completed+invoiced BHYT visit → one draft claim, lines mirror
   the invoice, totals match the kernel; patient BHYT snapshot frozen.
5. Idempotent: generate twice → the SAME claim (unique fso_id; no second row).
6. Not eligible: no invoice / expired card / non-BHYT patient → NO claim
   (generation returns empty, logged, no raise).
7. Totals recompute from lines; a `covered_service=False` line → its full amount
   in patient_amount, 0 in bhyt_amount.
8. Evidence-lock: mark a claim `ready` → writing an amount/line/snapshot field
   raises UNCONDITIONALLY (test as uid 1 too — §4); state + reset still allowed;
   reset-to-draft unlocks + writes a `reset` event.
9. Append-only: `bhyt.claim.event` write()/unlink() raise (even su).
10. Cron: gate OFF → no-op; ON → generates for eligible FSOs only, per-order
    savepoint survives one bad order (force one to raise), batch cap honoured.
11. Security: a finance user sees only own-catchment claims; owner sees all; a
    non-finance user can't create; unlink only in draft.
12. `bhyt_valid` compute: expired vs valid card.

Fixture notes (§6 conventions + §5.9): patient needs `catchment_province_id`;
FSO needs facility+patient+scheduled_datetime and a posted invoice (build a
minimal account.move + a completed FSO via raw-SQL state, §5.9). Create claims
sudo where a create-only group is used.

## 5. Deploy / verify (conventions §2)

- `-i health_bhyt --test-enable --test-tags /health_bhyt --stop-after-init
  --no-http --workers 0` (no HttpCase → --no-http OK). Result line; restart;
  `/web/login` 200. **Confirm by the `odoo.tests.result` line + EXIT:0, not
  just HTTP:200 (§5.45).**
- **Browser evidence pack (§8.1)** to `docs/strategy/reports/bhyt-phase1-evidence/`:
  the BHYT Claims worklist + a generated claim form showing the transparent
  BHYT/patient split on the lines + totals; the patient BHYT fields on the
  profile. Console clean. Seed a QA BHYT patient + a completed+invoiced QA
  visit (safe test data — NOT a real patient), generate a claim, screenshot,
  then delete the fixture (patient/FSO/invoice/claim/events) + fresh-cursor
  verify (§5.34). **Do all QA cleanup BEFORE/AFTER the deploy run, never during
  (§5.45).**

## 6. Report back

Standard §8 (report → `docs/strategy/reports/bhyt-phase1-report.md`), plus:
(a) evidence pack (worklist + split form + patient fields); (b) the kernel test
vectors' actual output on a real generated claim (prove covered+copay==total on
live data); (c) confirmation NO account.move/line was written (grep your diff);
(d) the eligibility counts on vietuat (how many completed+invoiced+bhyt_valid
visits exist — sizes the real claim population, read-only); (e) QA cleanup
fresh-cursor confirmation; (f) any new gotcha; (g) an explicit note on what the
Phase-2 4210 serializer will need from the claim model (so we can spec it the
moment the official XSD/sample arrives).

Kickoff line: `Implement the phase specified in docs/strategy/handovers/bhyt-claims-phase1-spine.md.`
