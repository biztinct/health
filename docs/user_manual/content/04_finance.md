# Finance — Invoicing, Payments & Receivables

The Finance section is where you handle everything to do with money: creating bills (invoices), collecting payments, and keeping track of who still owes you (accounts receivable, or "AR"). This chapter walks you through each screen, from the at-a-glance Dashboard down to the detailed receivables ledger.

The Finance menu contains these items:

- **Dashboard** — the Finance Center overview
- **Invoices** — create and manage bills
- **AR Dashboard** — see outstanding receivables and aging
- **AR Management** — Account Payment, Cash In Transit, Refund / Credit
- **Payments** — every payment transaction
- **Overdue Clients** — your collections worklist
- **VAT Log** — VAT / red-invoice tracking
- **AR Transactions** — the detailed receivables ledger

## Dashboard (Finance Center)

### Finance Center

This is your home base for finance. It gives you a single, live overview of revenue, money owed to you, cash collected, and recent activity, so you can spot what needs attention without digging through lists.

![Finance Center dashboard with KPI cards, recent payments and revenue trend](IMG:fin_01_dashboard.png)

**What you see on this screen:**

- **Header** — titled "Finance Center — Billing, Payments & Accounts Receivable", with a **New Invoice** button and a **period filter** to choose the time range you are looking at.
- **KPI cards** (each one is clickable and drills down to the underlying details):
  - **Revenue** — income for this period, from posted invoices.
  - **Outstanding AR** — amounts that are unpaid or only partially paid.
  - **Overdue Amount** — money past its due date.
  - **Cash Collected** — payments you have taken in.
  - **Active Packages** — count of active packages plus their remaining value.
  - **Pending Delivery** — nurse cash that is still in transit to the clinic.
- **Red-Invoice status row** (Vietnamese VAT e-invoices) — may show counts for Red Invoices Issued, Failed, Pending Issue, and Cancelled.
- **Recent Payments** — a list showing avatar, client, reference, method, amount, and a status badge (such as Collected, Pending Delivery, or Reconciled).
- **Revenue Trend** — a bar chart of the last 6 months.
- **Quick Actions** — shortcut buttons: New Invoice, Payments, AR Dashboard, VAT Log.
- **Invoice Status breakdown** — totals by status: Draft, Posted, Paid, Partial, Overdue, Cancelled.

**How to use it:**

1. Use the **period filter** in the header to set the date range. All KPI cards update to match the period you choose.
2. Click any **KPI card** (for example, Outstanding AR) to drill down into the list of records behind that number.
3. Click a row in **Recent Payments** to open that individual payment and view its full details.
4. Click a **Quick Action** button to jump straight to that screen: **New Invoice** starts a new bill, **Payments** opens the payment list, **AR Dashboard** opens receivables, and **VAT Log** opens VAT tracking.
5. Read the **Invoice Status breakdown** to see how many invoices are still Draft, Posted, Overdue, and so on.

**Tip:** The KPI cards are the fastest way to investigate a number that looks off — if Overdue Amount seems high, click it to see exactly which invoices are late.

## Invoices

### Invoices

This is where bills live. Use it to create new invoices, review existing ones, confirm them so they count as revenue, and track whether they have been paid.

![Invoices list with status tabs and date filters](IMG:fin_02_invoices_list.png)

**What you see on this screen:**

- **Status tabs** — to filter invoices by their stage.
- **Date filters** — to narrow the list to a chosen time range.
- A row per invoice, showing the client and key details.

When you open a single invoice, the form looks like this:

![Invoice form showing client, line items, totals and payment status](IMG:fin_02b_invoice_form.png)

- **Client** — who the invoice is billed to.
- **Line items** — the services or products being charged.
- **Totals** — the overall amount due.
- **Payment status** — whether the invoice is Draft, Posted, Paid, and so on.

**How to use it — the invoice-to-payment workflow:**

1. An invoice is created from a completed booking, or by clicking **New Invoice**.
2. The invoice starts as **Draft**. While it is Draft, you can still edit it.
3. Click **Confirm / Post** to post the invoice. Once posted, it counts as revenue and as outstanding AR.
4. Register a **payment** against the invoice (cash or bank transfer).
5. When the invoice is fully paid, its status automatically becomes **Paid**.

**Note:** Vietnamese "red" / VAT invoices can additionally be issued for a posted invoice. When that happens, the invoice appears in the **VAT Log**.

**Invoice statuses at a glance:**

| Status | What it means |
|---|---|
| Draft | Newly created and still editable; not yet counted as revenue. |
| Posted | Confirmed; now counts as revenue and outstanding AR. |
| Partial | Some payment received, but a balance remains. |
| Paid | Fully paid. |
| Overdue | Posted and unpaid past the due date. |
| Cancelled | Voided; no longer owed. |

**Warning:** Only edit an invoice while it is in **Draft**. Once you post it, it counts toward revenue and receivables, so changes should be made carefully.

## Accounts Receivable

### AR Dashboard

The AR Dashboard shows everything still owed to you (your outstanding receivables). Use it to answer "who owes us, how much, and how late is it?" — including aging.

![AR Dashboard showing outstanding receivables as list, pivot and graph](IMG:fin_03_ar_dashboard.png)

**What you see on this screen:**

- Outstanding receivables presented as a **list**, a **pivot**, and a **graph**.

**How to use it:**

1. Use the **list** view to scan individual outstanding amounts by client.
2. Switch to the **pivot** view to summarize and group the receivables (for example, by client or period).
3. Switch to the **graph** view to see the totals and aging visually.

**Tip:** Use this screen to understand aging — how long invoices have been outstanding — so you know which clients to follow up with first.

### AR Management

AR Management is a sub-menu with three tools for working with receivables: recording payments, tracking nurse cash, and issuing credits.

![Accounts receivable transactions ledger](IMG:fin_08_ar_transactions.png)

**What you see in this sub-menu:**

- **Account Payment** — opens a payment-collection wizard so you can record a payment against a client or invoice.
- **Cash In Transit** — nurse cash that is pending delivery to the clinic (this is the same as **Pending Delivery** on the Dashboard).
- **Refund / Credit** — customer credit notes.

**How to use it:**

1. Choose **Account Payment** when a client pays you. The payment-collection wizard opens; record the payment against the relevant client or invoice.
2. Choose **Cash In Transit** to see cash a nurse has collected that has not yet been delivered and reconciled at the clinic.
3. Choose **Refund / Credit** to issue a customer credit note.

**Note:** "Cash In Transit" and the Dashboard's "Pending Delivery" KPI refer to the same thing — nurse cash that has not yet reached the clinic.

## Payments & Collections

### Payments

This screen lists every payment transaction. Use it to confirm a specific payment, check its method and amount, or see whether the money has been reconciled.

![Payments list with method, amount, date and status](IMG:fin_05_payments.png)

**What you see on this screen:**

- One row per payment, showing the **method**, **amount**, **date**, and **status**.

**Payment statuses:**

| Status | What it means |
|---|---|
| Collected | The payment has been taken. |
| Pending Delivery | Nurse cash that has not yet been delivered to the clinic. |
| Delivered | The cash has been delivered. |
| Reconciled | The payment has been matched and confirmed in the books. |

**How to use it:**

1. Scan the list to find the payment you need by client, date, or amount.
2. Click a payment row to open it and view its full details.
3. Check the **status** column to know where each payment is in its lifecycle, from Collected through to Reconciled.

### Overdue Clients

This is your collections worklist: posted invoices that are unpaid and past their due date. Use it to know exactly who to chase for payment.

![Overdue clients list of posted, unpaid, past-due invoices](IMG:fin_06_overdue.png)

**What you see on this screen:**

- A list of **posted, unpaid invoices that are past their due date**.

**How to use it:**

1. Open this screen to get your list of overdue accounts.
2. Work through the clients, following up with each one to collect payment.
3. As payments come in and invoices are settled, they drop off this list.

**Tip:** Check Overdue Clients regularly — it is the most direct way to keep receivables under control.

## Tax & Ledger

### VAT Log

The VAT Log tracks posted customer invoices for VAT and red-invoice purposes. Use it when you need to review or follow up on Vietnamese VAT e-invoices.

![VAT Log of posted customer invoices for VAT and red-invoice tracking](IMG:fin_07_vat_log.png)

**What you see on this screen:**

- A list of **posted customer invoices** tracked for VAT / red-invoice purposes.

**How to use it:**

1. Open the VAT Log to review the posted invoices relevant to VAT.
2. Cross-check against the Dashboard's Red-Invoice status row (Issued, Failed, Pending Issue, Cancelled) to confirm which red invoices still need attention.

**Note:** A Vietnamese "red" / VAT invoice can be issued for a posted invoice; once issued, it is tracked here.

### AR Transactions

AR Transactions is the detailed receivables ledger. Use it when you need the full, line-by-line history of receivables rather than a summary.

![AR Transactions detailed receivables ledger](IMG:fin_08_ar_transactions.png)

**What you see on this screen:**

- The detailed **receivables ledger** — every receivable transaction in full detail.

**How to use it:**

1. Open AR Transactions when you need to trace a receivable in depth.
2. Review the individual entries to reconcile balances or investigate a specific client's account.

**Tip:** Use the AR Dashboard for the big picture and aging, then come to AR Transactions when you need the detailed, transaction-level record.