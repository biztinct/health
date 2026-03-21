# Financial Gap-Fill Plan — CRMv2 Double-Entry Posting & Hard Rules

## Background

The original [Financial Implementation Plan](file:///Users/adity/Documents/GitHub/health19/design/Financial_Implementation_Plan.md) has been implemented. All 7 Finance tiles work. The AR Transaction Log model has all 14 required fields. This plan addresses the remaining **accounting/journal entry gaps** — the CRMv2 "Double-Entry Posting Table" and "Hard Rules" that govern which accounts get debited/credited in each payment scenario.

---

## Gap 1: Unearned Revenue (UR) Account for Prepayments

### What CRMv2 requires (Scenario A)
> When a customer prepays: **Debit CASH/CIT → Credit UR (Unearned Revenue)**

### What currently happens
- Prepaid package wizard creates an `out_invoice` and an `account.payment`
- Invoice posts: **Debit AR → Credit Income (Service Revenue)**
- Payment posts: **Debit Cash/Bank → Credit AR**
- Net effect: Cash → Income. **Revenue is recognized immediately at prepayment time**

### What's wrong
Revenue should NOT be recognized until the service is delivered. The prepayment should go to a **liability account** (Unearned Revenue) and only move to Service Revenue when each service is consumed.

### Fix required
1. **Create/configure an Unearned Revenue account** (liability_current type) in the Chart of Accounts
2. **Change the prepaid invoice's income account** to use UR instead of SR — either via:
   - A dedicated "Prepaid" product category with income account = UR, or
   - Override the account on the invoice line when `transaction_type == 'prepaid'`
3. This makes prepayment posting: **Debit AR → Credit UR** (invoice) + **Debit Cash → Credit AR** (payment) — net effect: **Debit Cash → Credit UR** ✅

### Files to modify
- [health_prepaid_package_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/wizards/health_prepaid_package_wizard.py) — set income account to UR on prepaid invoice lines
- Chart of Accounts setup (one-time config via XML data or manual DB)

---

## Gap 2: UR → SR Reclassification on Prepaid Service Consumption

### What CRMv2 requires (Scenario B)
> When service is delivered for a prepaid patient: **Debit UR → Credit SR (Service Revenue)**

### What currently happens
- `action_consume_service()` decrements the package counter
- **No journal entry is created** — the accounting is invisible

### What's wrong
Each prepaid service consumption should generate a reclassification journal entry that moves revenue from "Unearned" to "Earned" (Service Revenue). Without this, SR is never credited for delivered prepaid services, and the UR balance never decreases.

### Fix required
1. On prepaid service consumption (FSO completion with prepaid deduction), create a journal entry:
   - **Debit UR** (amount = price_per_service from package)
   - **Credit SR** (same amount)
2. Link this journal entry to the AR Transaction Log with posting path `DELIVERY→PREPAID`

### Files to modify
- [health_nurse_payment_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/wizards/health_nurse_payment_wizard.py) — in `_process_pay_now()` for prepaid path, create reclassification journal entry
- [health_ar_transaction_log.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/models/health_ar_transaction_log.py) — ensure the reclassification entry is logged

---

## Gap 3: Cash in Transit – Nurse (CIT) Account

### What CRMv2 requires (Scenario E)
> When nurse receives cash: **Debit CIT → Credit AR** (not Debit CASH → Credit AR)

### What currently happens
- Nurse collects cash → transaction status = `pending_delivery`
- Cash delivery wizard creates `account.payment` against the **Cash journal**
- Payment posts: **Debit Cash → Credit AR**
- The cash goes directly from AR to the company Cash account

### What's wrong
The nurse is holding the cash in transit — it shouldn't hit the company Cash/Bank account until the OM physically receives it. There should be an intermediate **Cash in Transit – Nurse** account.

### Fix required
1. **Create/configure a CIT account** — the Vietnamese CoA already has "Vietnamese dong in transit" (account id 57, type `asset_cash`). Either reuse this or create a dedicated "Cash in Transit – Nurse" account
2. **When nurse collects cash** (at service completion), create a journal entry:
   - **Debit CIT → Credit AR** (cash is in nurse's hands, AR is settled)
3. **When OM receives cash** (cash delivery wizard), create a second journal entry:
   - **Debit CASH → Credit CIT** (cash moves from nurse to company)

### Current flow vs. proposed flow

| Step | Current | Proposed |
|---|---|---|
| Nurse collects cash | No journal entry (only transaction record) | **Debit CIT → Credit AR** |
| OM receives cash | **Debit Cash → Credit AR** | **Debit Cash → Credit CIT** |

### Files to modify
- [health_nurse_payment_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/wizards/health_nurse_payment_wizard.py) — in `_process_pay_now()` for cash path, create CIT journal entry instead of deferring everything
- [health_cash_delivery_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/wizards/health_cash_delivery_wizard.py) — in `_create_standard_payment()`, change journal entry from Cash→AR to Cash→CIT

---

## Gap 4: Hard Rules Enforcement

### The 8 hard rules from CRMv2

| # | Rule | Currently Enforced? |
|---|---|---|
| 1 | SR = sale of service account | ⚠️ Depends on product config |
| 2 | SR credited only on service completion | ✅ Yes — invoices only created at FSO completion |
| 3 | Cash receipt never credits SR | ✅ Yes — payments go through AR |
| 4 | Allowed debits when crediting SR: UR, AR, CIT | ❌ No validation |
| 5 | Cash/Bank debited only on payment or handover | ✅ Yes — standard Odoo |
| 6 | CIT debited when nurse receives cash | ❌ CIT not used (see Gap 3) |
| 7 | AR credited when client pays | ✅ Yes — standard reconciliation |
| 8 | No journal may debit Cash/Bank and credit SR directly | ❌ No validation on manual entries |

### Fix required
- **Rules 1, 4, 8**: Add a Python constraint on `account.move` that validates:
  - If a line credits an SR account, the debit side must be UR, AR, or CIT
  - If a line debits Cash/Bank, the credit side must NOT be SR
- **Rule 6**: Addressed by Gap 3 (CIT account implementation)
- **Rules 2, 3, 5, 7**: Already enforced by the existing workflow

### Files to modify
- [NEW] `account_move_constraints.py` — add `_check_posting_rules()` constraint on `account.move`

---

## Gap 5: AR View Missing Columns

### What CRMv2 requires for the Accounts Receivable listing

| Required Column | Status |
|---|---|
| Date | ✅ |
| Client | ✅ |
| Name | ✅ |
| Phone | ❌ Not shown — available via `partner_id.phone` |
| Company ID (VAFHS/CSTNVU) | ❌ Not shown — needs entity code |
| Facility ID | ❌ Not shown — available via booking |
| Original Invoice Total | ❌ Not shown — available via `move_id.amount_total` |
| Amount Paid to Date | ❌ Not shown — computable |
| Balance Outstanding | ✅ |
| Aging (days) | ❌ Not computed |

### Fix required
- Add related/computed fields to the AR list view: `partner_phone`, `aging_days`, `invoice_total`, `amount_paid`, `entity_code`, `facility_name`
- These are all **read-only display fields** — no impact on journal entries

### Files to modify
- AR dashboard view XML — add columns
- Possibly `account.move.line` extension for computed fields

---

## Summary — Priority Order

| Priority | Gap | Impact | Effort |
|---|---|---|---|
| 🔴 High | Gap 1: UR account for prepayments | Revenue recognition is incorrect — **revenue is overstated** before service delivery | Medium |
| 🔴 High | Gap 2: UR→SR reclassification | Prepaid revenue never shows as earned | Medium |
| 🟡 Medium | Gap 3: CIT account for nurse cash | Cash balance is overstated while nurse holds cash | Medium |
| 🟢 Low | Gap 4: Hard rules enforcement | Protection against manual entry errors | Low |
| 🟢 Low | Gap 5: AR view columns | Cosmetic — missing info columns | Low |

---

## Deferred Items (confirmed — no action this stage)

From CRMv2 Section a) "Previously Agreed Deliverables Deferred":
1. ~~Link to Viettel digital Signatures for VAT Invoices~~ — Deferred
2. ~~Submission of VAT Invoices to Tax Department~~ — Deferred
3. ~~Updating MISA with Sales and AR Transactions~~ — Deferred
4. ~~MOH Clinical Details~~ — No action
5. ~~MOH Digital Prescriptions~~ — No action

---

## Questions for You

1. **UR Account**: Should I create a new "Unearned Revenue – Healthcare" account, or reuse an existing liability account from the Vietnamese CoA?

2. **CIT Account**: The CoA has "Vietnamese dong in transit" (id 57). Should I reuse that, or create a separate "Cash in Transit – Nurse" account to keep it distinct?

3. **Hard Rules**: Should the constraints be **blocking** (raise error on save) or **warning-only** (allow but flag)? Blocking is safer but may disrupt if someone needs to make a manual correction.

4. **Priority**: Do you want me to implement Gaps 1+2 (UR/prepaid) first since they affect revenue recognition, or Gap 3 (CIT/cash) first since cash is the more common payment method?
