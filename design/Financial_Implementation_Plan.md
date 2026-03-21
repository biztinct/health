# CRMv2 Financial & Invoicing Requirements — Deep Analysis

## Summary

The CRMv2 document defines **8 key financial requirements** across two sections (i and ii). Below I map each against the existing codebase, identify what's already met, and what changes are needed — **without altering core Odoo accounting/journal processes**.

---

## Section i) — "Finance" Menu (6 Sub-menus)

The document asks to **rename "Invoicing"** to **"Finance"** and expand it from the current 3 tiles to 6 sub-menus:

| # | Required Sub-menu | Current Dashboard Tile | Status |
|---|-------------------|----------------------|--------|
| 1 | **Invoices** — table of all invoices, filter & export | ✅ `invoicing-invoices` → `action_healthcare_invoices` | **Mostly met** — opens `account.move` list with healthcare columns. Filter/export is native Odoo. |
| 2 | **Accounts Receivable** — unpaid invoices with aging | ✅ `invoicing-ar` → `action_healthcare_ar_dashboard` | **Partially met** — opens `account.move.line` AR list. Missing some required fields (see below). |
| 3 | **AR Management** — 3 tabs (Payment, Cash In Transit, Refund/Credit) | ❌ No dedicated tile | **Gap** — must be created (see below). |
| 4 | **Add New Invoice** — manual invoice for prepayments, part-time nurse, ad-hoc services | ❌ No tile; user must go through standard Odoo | **Gap** — needs a tile that opens `account.move` form in create mode. |
| 5 | **VAT Invoices Log** — every VAT invoice detail (interim table for MISA validation) | ❌ No dedicated view | **Gap** — new model or filtered view needed. |
| 6 | **AR Transactions Log** — journal entries for every AR transaction (interim MISA validation) | ❌ No dedicated view | **Gap** — new model or filtered view needed. |

---

### Detailed Analysis Per Sub-menu

### 1. Invoices ✅ Mostly Met

**What exists:** [action_healthcare_invoices](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/views/health_ar_dashboard_views.xml#L175) opens `account.move` in list view with healthcare-specific columns (booking ref, service type, payment state, tax submission status).

**What's needed:**
- ✅ Filter & export — already native Odoo (list view has export button)
- May want to add a "download to Excel" button for convenience (can use Odoo's built-in list export)

**Changes needed:** Minimal — possibly add more visible export button or column tweaks.

---

### 2. Accounts Receivable ⚠️ Partially Met

**What exists:** [action_healthcare_ar_dashboard](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/views/health_ar_dashboard_views.xml#L97) shows `account.move.line` with receivable account filter, including partner, due date, debit, credit, balance, reconciled status.

**What the document requires — a listing of unpaid invoices with these columns:**

| Required Field | Currently Shown | In Odoo? |
|---|---|---|
| Date | ✅ `date` | Yes |
| Client | ✅ `partner_id` | Yes |
| Name | ✅ `name` (line label) | Yes |
| Phone | ❌ | Available via `partner_id.phone` — add as related field |
| Company ID (VAFHS/CSTNVU) | ❌ | Needs custom field on `res.partner` or use `company_id` |
| Facility ID | ❌ | Available via booking → facility link |
| Original Total of Invoice | ❌ | Available via `move_id.amount_total` |
| Amount Paid to Date | ❌ | Available via `move_id.amount_total - move_id.amount_residual` |
| Balance Outstanding | ✅ `balance` / `amount_residual` | Yes |
| Aging (days) | ❌ | Computable: `today - date_maturity` |
| Outstanding Balance (hide if zero) | ✅ `amount_residual` with filter | Yes |

**Changes needed:**
1. Add related fields: `partner_phone`, `invoice_total`, `amount_paid`, `aging_days` (computed)
2. Update the AR list view to show these additional columns
3. Add filter to hide zero-balance rows (or make it default)

**Impact on core journal process:** None — these are all **read-only computed/related fields** on `account.move.line`.

---

### 3. AR Management ❌ New Feature Needed

**What the document requires:** A popup/wizard with 3 tabs:
- (a) **Account Payment** — record cash or bank transfer payments against invoices
- (b) **Cash In Transit** — track cash transfers from nurse/clinic to Head Office
- (c) **Refund/Credit** — process refunds or credit notes

**What exists:**
- (a) ✅ [health_payment_workflow_wizard.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/wizard/health_payment_workflow_wizard.py) — handles Pay Now/Pay Later flows, creates `account.payment`
- (b) ⚠️ [action_healthcare_cash_management](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/views/health_ar_dashboard_views.xml#L126) — shows cash payments pending delivery to OM. Also: `action_mark_cash_delivered()` in `health_payment_transaction.py`
- (c) ⚠️ `action_create_refund()` in `health_payment_transaction.py` — creates refund transactions

**What's needed:**
- A **combined dashboard tile** "AR Management" that opens a view/wizard with the 3 sections accessible as tabs or sub-tiles
- This could be a new wizard with notebook tabs, or a list view with a sidebar/filter grouping

**Implementation approach (preserves core journal process):**
- Create a new tile `invoicing-ar-management` in the dashboard
- Option 1: Open a wizard with 3 notebook tabs linking to existing actions
- Option 2: Open a list view of `health.payment.transaction` with group-by filter (payment type: payment/cash-transit/refund)

---

### 4. Add New Invoice ❌ New Tile Needed

**What the document requires:** Ability to create manual invoices for:
- Prepayments
- Part-time nurse/doctor payments
- Services without booking/invoice
- Services provided in clinic

**What exists:**
- Standard Odoo `account.move` form can create invoices manually
- [health_prepaid_service.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/models/health_prepaid_service.py) handles prepaid package tracking

**What's needed:**
- Add a tile `invoicing-add-invoice` that opens `account.move` form in create mode with `default_move_type: 'out_invoice'`
- Pre-fill healthcare context (service type, partner defaults)
- This is similar to how we added `client-new` — just a new action entry

**Impact on core process:** None — just a shortcut to create an invoice via standard Odoo form.

---

### 5. VAT Invoices Log ❌ New View Needed

**What the document requires:**
- A table showing every VAT Invoice created
- Used as an **interim table for validating MISA entries**
- This is the "VAT Log" referenced by Dung

**What exists:**
- `account_move.py` has VAT fields: `tax_authority_submission_status`, `tax_submission_reference`, `vietnamese_tax_code`
- `misa_integration.py` has `MISASyncLog` model tracking sync status
- The retail invoice (Hóa Đơn Bán Lẻ) and VAT invoice (Hóa Đơn GTGT) formats are shown in the screenshots

**What's needed — a filtered view of `account.move` showing:**

| Field | Source |
|---|---|
| Invoice Date | `account.move.invoice_date` |
| Serial/Ký hiệu | Needs new field (e.g., `vat_serial_code` — "1C26MVU") |
| Invoice No/Số | Needs new field or use `name` |
| Customer Name | `partner_id.name` |
| Customer Address | `partner_id.contact_address` |
| Customer Tax Code | `partner_id.vat` (already exists as `customer_tax_code`) |
| Item Description | Invoice line descriptions |
| Quantity | Invoice line quantity |
| Unit Price | Invoice line price_unit |
| Discount | Invoice line discount |
| Amount | Invoice line price_subtotal |
| VAT Rate | Tax rate (KCT = exempt) |
| VAT Amount | Tax amount |
| Total | `amount_total` |
| MISA Sync Status | `misa_sync_status` |
| Tax Submission Status | `tax_authority_submission_status` |

**Implementation approach:**
- Create a new list view `view_healthcare_vat_invoice_log` on `account.move` filtered to posted invoices
- Add missing fields for VAT serial/number tracking (Hà Nội vs HCMC have different numbering)
- Make it downloadable (native Odoo export)

**Impact on core journal process:** None — read-only reporting view + 2-3 new tracking fields on `account.move`.

---

### 6. AR Transactions Log ❌ New View/Model Needed

**What the document requires — a transaction log with these fields:**

| Required Field | Odoo Equivalent | Exists? |
|---|---|---|
| Transaction ID (UUID) | None natively — need custom field | ❌ New |
| CRM Event ID | Link to `crm.lead` or booking | ⚠️ Partial — `fieldservice_order_id` exists on invoice |
| Event Type (Payment/Delivery/Refund/Handover) | Closest: `health.payment.transaction.payment_type` | ⚠️ Partial |
| Transaction DateTime | `account.move.line.date` or payment date | ✅ |
| Posting Date | `account.move.date` | ✅ |
| Company/Entity (Hanoi vs HCMC) | `company_id` | ✅ |
| Debit Account | `account.move.line.account_id` (debit side) | ✅ |
| Credit Account | `account.move.line.account_id` (credit side) | ✅ |
| Amount | `account.move.line.debit` or `credit` | ✅ |
| Currency | `currency_id` (VND) | ✅ |
| Amount in Words | None natively | ❌ New |
| Prepared By | `create_uid` | ✅ |
| Posting Path | None — needs custom field | ❌ New |
| Status (Draft/Posted/Reversed) | `parent_state` on `account.move.line` | ✅ |

**Two design approaches (neither changes core journal process):**

#### Approach A: New Read-Only Reporting View on `account.move.line`
- Create a list view of `account.move.line` filtered to AR-related accounts
- Add computed/related fields for the missing columns (Transaction ID, Amount in Words, Posting Path, CRM Event link)
- Pros: Uses real journal data directly, always in sync
- Cons: `account.move.line` is one-sided (each line has either debit OR credit), so the dual-account display requires grouping by `move_id`

#### Approach B: New Transactional Log Model *(Recommended)*
- Create new model `health.ar.transaction.log` that is **auto-populated** by hooks on `account.move.post()` and `account.payment.create()`
- Each log entry captures the double-entry in a single row (Debit Account, Credit Account, Amount)
- Includes all the custom fields (UUID, CRM Event ID, Event Type, Posting Path, Amount in Words)
- Pros: Clean, purpose-built for MISA validation; doesn't touch core journal
- Cons: Requires keeping in sync (but automated via `write`/`create` hooks)

> [!IMPORTANT]
> **Approach B is recommended** because the document specifically defines a flat transaction log format (one row = one double-entry event) which doesn't naturally fit `account.move.line`'s structure (one row = one side of an entry).

---

## Section ii) — Interim Fix for Deferred Items

### Item 1: "Every completed booking has a retail invoice + VAT record"

**What exists:**
- FSO completion flow in [health_fieldservice_order.py](file:///Users/adity/Documents/GitHub/health19/addons/health_invoicing/models/health_fieldservice_order.py) creates invoices
- The payment workflow wizard handles payment recording and creates `account.payment`

**What's needed:**
- Ensure the FSO completion always creates a retail invoice (already does)
- For non-prepaid services: also create a VAT invoice record in the **VAT Invoices Log** (sub-menu 5)
- This is essentially a trigger: on FSO completion → populate VAT Log entry

**Impact on core process:** None — it's an additional logging step, not a change to invoicing.

### Item 2: "Log of correct journal transactions for sales and AR updates"

**What's needed:**
- The **AR Transactions Log** (sub-menu 6) captures this automatically
- Every time an invoice is posted or a payment is recorded, a log entry is created

---

## Item 3: "Show Items 1 and 2 as tables, make available for download"

The user clarifies this **doesn't need to be in Analytics** — it could be tiles under the Invoicing/Finance node.

**Recommended approach:**
- Add two new tiles to the **Invoicing** (→ Finance) panel in the dashboard:
  - `invoicing-vat-log` → VAT Invoices Log (Item 1)
  - `invoicing-ar-log` → AR Transactions Log (Item 2)
- Both open as list views with **native Odoo export** (CSV/Excel download)

---

## Summary of Changes Needed (Preserving Core Journal Process)

| Change | Type | Impact on Core |
|---|---|---|
| Rename "Invoicing" to "Finance" in dashboard | Label change | None |
| Expand panel from 3 to ~8 tiles | JS config change | None |
| Add computed fields to AR view (phone, aging, paid amount) | Related/computed fields | None |
| Add "AR Management" tile (3 sub-tabs) | New wizard or grouped view | None |
| Add "Add New Invoice" tile | New action (form create mode) | None |
| Add VAT serial/number fields to `account.move` | 2-3 new fields | None |
| Create VAT Invoices Log view | New list view on `account.move` | None |
| Create AR Transactions Log model | New model + auto-populate hooks | None (hooks observe, don't modify) |
| Add export/download to both log views | Native Odoo export | None |

---

## Questions

1. **Company ID field (VAFHS / CSTNVU):** Is this a code that maps to the Odoo `company_id`, or is it a separate identifier for the two legal entities (Hanoi vs HCMC)? Do you already have this mapped somewhere?

2. **Facility ID:** Should this come from the booking's assigned facility (`health.facility`), or is it a separate field on the invoice/partner?

3. **VAT Serial Code ("1C26MVU"):** This appears to be a yearly serial prefix. Where does Dung currently manage the serial number sequence? Is it in MISA only, or should Odoo also generate sequential VAT invoice numbers?

4. **Retail Invoice numbering:** The Hóa Đơn Bán Lẻ has number "0039263". Is this auto-generated in Odoo, or is it a manual hand-written number entered by the nurse?

5. **Posting Path field (e.g., "DELIVERY→PREPAID", "DELIVERY→NURSE_CASH"):** Is there a defined list of all possible posting paths, or should it be derived from the payment method + service type combination?

6. **Amount in Words:** Should this be Vietnamese ("ba trăm ngàn đồng") or English, or both? Should it auto-generate from the amount?

7. **AR Management — Cash In Transit:** Is the "Cash In Transit to Head Office" tracking the same as the existing "Cash Collections" view (nurse cash delivery to OM)? Or is there a separate Head Office transfer step after OM receives cash?

8. **Priority:** Of the 6 sub-menus, which are highest priority? I assume **5 (VAT Log)** and **6 (AR Transactions Log)** since those are the "interim fix" items needed for MISA validation — correct?
