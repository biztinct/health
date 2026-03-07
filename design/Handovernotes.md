Developer Handover Checklist: CRM–Invoicing System
1. Documentation Package
✅ Updated workflow document (CRM & Invoicing, single booking structure)✅ Data structure tables (CRM_Invoicing_Template Excel) with fields, compulsory/optional/automated flags📌 Developer Action: Confirm receipt of all files.
2. Scope & Boundaries
• CRM scope covers: Contact → Booking → Assignment → Service Delivery → Completion → Invoicing• Invoicing scope starts at service completion and ends with posting to MISA.• Out of scope (future phases): Lookup codes, advanced reporting, automated compliance forms, role-based security.📌 Developer Action: Confirm scope to avoid scope creep.
3. Data Structures
• Single Booking Table replaces draft/final split.• Related Party Table for client, caregiver, payer.• Address template standardized.• Fields marked as: C = Compulsory, O = Optional, A = Automated📌 Developer Action: Implement as structured tables, validate data entry against flags.
4. Workflow Logic
• CRM → Invoicing link is seamless (completion triggers invoicing).• Status updates are event-driven (contact, booking, assignment, service start, service completion, invoicing).• Failure/exception flows included (e.g., booking deferral/cancellation).📌 Developer Action: Map logic to database triggers & front-end forms.
5. Integration Requirements
• MISA: AR App syncs confirmed sale/payment data.• CloudDoctor: Clinical notes & MOH submissions (manual/automatic options).• Zalo: Push notifications for nurse assignment.
• MOH Clinical Data
• MOH Pharmaceutical Prescriptions
• VAT Invoices
• Digital Signatures📌 Developer Action: Note API touchpoints, design integration hooks but full specs will follow later.
6. Feedback & Iteration
• Map Tables and fields in excel file to existing tables and fields in Odoo              CRM/invoice/accounts receivable applications keep fields but label if possible; Note additional fields for HHH requirements
• Developers to flag:  - Any missing fields or forms  - Any overly complex workflows  - Suggestions for UI simplification⚠️ Reminder: Keep system lightweight. If something looks complex, ask: Can we solve this with fewer clicks or by automating the step?
 
 
Lookup tables/codes will be provided later
 
Note:  not validated by Clinic users so still subject to change.  
