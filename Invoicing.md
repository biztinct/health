Invoicing & Accounts Receivable 
Management Workflow 
General Rules 
∙Final invoices are created when service is completed. (No draft invoice)
∙Prepayment status is recorded at the time of booking if the client has already paid. 
∙Integration points: 
oAccounts Receivable App (Invoicing module): Tracks sales, payments, outstanding balances. 
oMISA Accounting App: Mirrors sales, AR changes, cash/bank balances. 
oTax Department Submission: Red invoices must be submitted in real time, 
except for approved deferred submissions. 

 
Case 1 — Payment on Completion of Service 
1.Service Start 
oNurse logs start of service (at client home or in clinic). 
2.Service Completion 
oNurse generates final invoice
oSystem prompts: “Pay Now” or “Pay Later.” 
oIf Pay Now: 
Nurse edits the invoice for any adjustments if required 
On completion: 
Pop-up to enter payment method & confirm amount matches 
invoice. 
If bank/card: take photo as proof. 
If cash: 
Nurse holds cash until next clinic visit. 
OM (Operations Manager) issues electronic receipt to nurse upon receipt of cash. 
OM records in Accounts Receivable App → increases 
clinic cash balance & reduces AR. 
MISA updates: cash ↑, AR ↓. 
 





Important: Initial nurse collection is logged as AR ↑, not 
cash ↑. Cash is only recorded when OM receives it. 
3.Invoice Finalization 
oPop-up closure triggers: 
Submission of Red Invoice to Tax Department. 
Service completion log. 
oSuccessful submission triggers: 
Sale + payment + method entry in AR App. 
AR App syncs sale/payment data to MISA. 
4.No Internet 
oApp logs service completion with “Pending submission” flag. 
oDetails stored on device; submission occurs automatically when connection 
returns. 
oAudit requirement: Store both actual completion time and adjusted submission 
time. 
Adjusted submission time = the time the invoice is submitted to the Tax 
Department when the system becomes available. 
Logic: This is the practical completion time of the job. 
Adjusted time is used on the invoice for deferred submissions due to 
technical delay. 
Late nurse-initiated submissions remain marked as late (penalty applies). 

 
Case 2 — Prepaid Services 
1.Prepayment Processing 
oOM or Sales issues final VAT invoice (not draft). 
oPop-up to enter amount & payment method. 
oOn completion: 
Submit invoice to Tax Department (or later same day if system down). 
AR App updates: 
Record sale, service details, amount, method. 
Flag prepayment. 
Log number of prepaid bookings in CRM (dates set or 
placeholders). 
2.Service Delivery 



oNurse logs service start. 
oOn completion: 
Nurse retrieves invoice (system recognises “prepaid” status). 
Retail invoice is prepared automatically. 
Payment method auto-set to “Service prepaid.” 
Amount = per-service fee from prepayment. 
Any balance/refund handled at liquidation stage. 
3.Invoice & AR Updates 
oInvoice submission → Tax Department. 
oAR App records sale & payment method. 
oAR App syncs sale/payment data to MISA → Sale ↑, Cash/Bank ↑, Prepaid 
liabilities ↑. 
oMISA updates: sale & AR ↓. 
4.Liquidation 
oAfter all prepaid bookings used: 
Refund or new invoice for extra services. 
Liquidation date = date of final invoice/refund voucher. 
OM updates AR App → triggers Tax submission (if required) + MISA 
update (sale/refund & cash/bank changes). 

 
Case 3 — Payment After Service Delivery 
1.Service Start 
oNurse logs start of service. 
2.Service Completion 
oNurse creates invoice
oSystem prompts: “Pay Now” or “Pay Later.” 
oIf Pay Later: 
Nurse edits invoice as required. 
Completion triggers: 
Red Invoice submission to Tax Department. 
Service completion log. 
3.Accounts Receivable 
oSuccessful Tax submission triggers AR entry: 


Sale + positive outstanding balance. 
oMISA updates: sale & AR ↑. 
4.Payment Collection 
oOM records payment in AR App (amount, method). 
oAR App update → MISA update: 
Cash/bank ↑, AR ↓. 
5.Collections 
oOM & nurses follow up on unpaid accounts per company policy. 
 
