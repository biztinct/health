Invoicing & Accounts Receivable Management Workflow
General Rules
	•	•	Draft invoices are created when a booking is assigned.
	•	•	Prepayment status is recorded at the time of booking if the client has already paid.
	•	•	Invoice archiving: If a booking is cancelled or rescheduled before service delivery, the draft invoice is archived. If rescheduled, a copy is re-issued for the new date.
	•	•	Integration points:
	•	o	Accounts Receivable App: Tracks sales, payments, outstanding balances.
	•	o	MISA Accounting App: Mirrors sales, AR changes, cash/bank balances.
	•	o	Tax Department Submission: Red invoices must be submitted in real time, except for approved deferred submissions.

Case 1 — Payment on Completion of Service
	•	1.	Service Start
	•	o	Nurse logs start of service (at client home or in clinic).
	•	2.	Service Completion
	•	o	Nurse retrieves the draft invoice.
	•	o	System prompts: “Pay Now” or “Pay Later.”
	•	o	If Pay Now:
	•		Nurse edits the invoice for any adjustments.
	•		On completion:
	•		Pop-up to enter payment method & confirm amount matches invoice.
	•		If bank/card: take photo as proof.
	•		If cash:
	•		Nurse holds cash until next clinic visit.
	•		OM issues electronic receipt to nurse upon receipt of cash.
	•		OM records in Accounts Receivable App → increases clinic cash balance & reduces AR.
	•		MISA updates: cash ↑, AR ↓.
	•		Important: Initial nurse collection is logged as AR ↑, not cash ↑. Cash is only recorded when OM receives it.
	•	3.	Invoice Finalization
	•	o	Pop-up closure triggers:
	•		Submission of Red Invoice to Tax Department.
	•		Service completion log.
	•	o	Successful submission triggers:
	•		Sale + payment + method entry in AR App.
	•		AR App syncs sale/payment data to MISA.
	•	4.	No Internet
	•	o	App logs service completion with “Pending submission” flag.
	•	o	Details stored on device; submission occurs automatically when connection returns.
	•	o	Audit requirement: Store both actual completion time and adjusted submission time.
	•		Adjusted submission time = the time the invoice is submitted to the Tax Department when the system becomes available.
	•		Logic: This is the practical completion time of the job.
	•		Adjusted time is used on the invoice for deferred submissions due to technical delay.
	•		Late nurse-initiated submissions remain marked as late (penalty applies).

Case 2 — Prepaid Services
	•	1.	Prepayment Processing
	•	o	OM or Sales issues final VAT invoice (not draft).
	•	o	Pop-up to enter amount & payment method.
	•	o	On completion:
	•		Submit invoice to Tax Department (or later same day if system down).
	•		AR App updates:
	•		Record sale, service details, amount, method.
	•		Flag prepayment.
	•		Log number of prepaid bookings in CRM (dates set or placeholders).
	•	2.	Service Delivery
	•	o	Nurse logs service start.
	•	o	On completion:
	•		Nurse retrieves invoice (system recognises “prepaid” status).
	•		Retail invoice is prepared automatically.
	•		Payment method auto-set to “Service prepaid.”
	•		Amount = per-service fee from prepayment.
	•		Any balance/refund handled at liquidation stage.
	•	3.	Invoice & AR Updates
	•	o	Invoice submission → Tax Department.
	•	o	AR App records sale & payment method.
	•	o	AR App syncs sale/payment data to MISA → Sale ↑, Cash/Bank ↑, Prepaid liabilities ↑.
	•	o	MISA updates: sale & AR ↓.
	•	4.	Liquidation
	•	o	After all prepaid bookings used:
	•		Refund or new invoice for extra services.
	•		Liquidation date = date of final invoice/refund voucher.
	•		OM updates AR App → triggers Tax submission (if required) + MISA update (sale/refund & cash/bank changes).

Case 3 — Payment After Service Delivery
	•	1.	Service Start
	•	o	Nurse logs start of service.
	•	2.	Service Completion
	•	o	Nurse retrieves draft invoice.
	•	o	System prompts: “Pay Now” or “Pay Later.”
	•	o	If Pay Later:
	•		Nurse edits invoice as required.
	•		Completion triggers:
	•		Red Invoice submission to Tax Department.
	•		Service completion log.
	•	3.	Accounts Receivable
	•	o	Successful Tax submission triggers AR entry:
	•		Sale + positive outstanding balance.
	•	o	MISA updates: sale & AR ↑.
	•	4.	Payment Collection
	•	o	OM records payment in AR App (amount, method).
	•	o	AR App update → MISA update:
	•		Cash/bank ↑, AR ↓.
	•	5.	Collections
	•	o	OM & nurses follow up on unpaid accounts per company policy.
