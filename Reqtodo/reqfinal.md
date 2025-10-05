# Healthcare CRM System - Requirements Documentation

**Project:** HHHPL x IADC Integrated Healthcare Management System
**Period Covered:** August 8 - October 1, 2025
**Source:** 14 Meeting Minutes Documents
**Total Requirements:** 200+ discrete requirements

---

## 1. CRM & Lead Management


### Lead vs Contact Differentiation
- **Lead**: Generated from campaign sources (Google Ads, Facebook) without direct interaction
- **Contact**: Created when lead provides verifiable information (name, phone) or initiates communication
- Leads without sufficient information tagged as "not reliable" or "junk calls"
- Only verifiable campaign-source leads recorded in system
- Contact workflow: check if phone number is known (new vs existing contact) - Ensure Odoo search / filter has filter created for phone number as search 

### Contact Management
- Mandatory fields: phone number, service type, scheduled time
- Contact tagging: new, booked, junk, lead to follow up
- Conversion tracking: contact → booking
- Follow-up prioritization for genuine inquiries with client details
- Automated ID generation with city codes (e.g., HCM00110012)
- All contacts treated as Client Representatives initially
- Junk contacts still recorded for tracking purposes

### Referral Tracking
- Integration with referral platforms: BookingCare, Doc, Die
- Individual referral tracking (person-to-person referrals)
- Partner referral tracking (e.g., FWD, Dai-ichi insurance companies)
- Source of leads renamed to "source of introduction" or "referral"
- Tracking from referral source through to booking completion

---

## 2. Client/Patient Management

### Client Registration & Profiles
- System label: "Client" (not "Patient")
- Client categories: VIP, regular, emergency, senior, pediatric
- Unique client ID auto-generation to avoid errors
- Client ID format with city codes (e.g., HCM00110012)
- Support multiple contact numbers per client
- Shared phone numbers across family members allowed


### Related Persons Management
- **Related Person Master File** linked bidirectionally with Client Master
- Categories: Contact Representative, Caregiver, Payer, Referrer, Emergency Contact, Legal Guardian
- Multiple related persons allowed per category (e.g., multiple caregivers, multiple payers)
- Relationship definitions: spouse, child, parent, sibling, friend, etc.
- Healthcare relationships table for storing relationship types
- Auto-generated unique IDs for all related persons
- Dashboard showing linked clients ↔ related persons

### Client Identification & Data
- Payers can pay for multiple clients
- Caregivers can be primary contacts
- Step-by-step field display based on workflow stage

### Address Management
- Structured address template required for standardization
- Province/district/city dropdown lists
- GPS mapping integration from address
- Coverage area tracking per facility
- Distance-based pricing potential

Address template as follows
Address template:
province_code
Named Area
Apartment Number
Building Name
House Number
Sub-Alley Number (Ngách)
Alley Number (Ngõ)
Street Name
Ward/Commune
City/Province
Postal Code
Country

Address to be concatenated into a single field
---

## 3. Booking & Scheduling

### Booking Workflow
- Workflow stages: Initial inquiry → Tentative booking → Validated/Confirmed (by Operations) → Assigned to staff
- Multiple nurses/doctors can be assigned to single booking (complex cases)
- Future and repeated bookings visible historically and prospectively


### Service Selection
- Service type selection: Doctor, Nurse, Laboratory
- Service category selection (e.g., internal medicine, wound care)


### Staff Assignment

- Head Nurse manages staff replacements
- Operations Manager validates and assigns bookings

### Booking Status Tracking
- Booking statuses: New, Assigned, In Progress, Completed, Cancelled
- Real-time status visibility for all stakeholders
- Visual indicators for booking progress

### Cancellation Management
- Pop-up to capture cancellation details (who, why, when)
- Cancellation reason lookup table
- Cancellation tracking and reporting
- Mandatory cancellation notes

---

## 4. Staff Management & Assignment

### Roles & Permissions
- **Admin**: Full system access
- **Doctor**: Service delivery, clinical notes, invoicing
- **Nurse**: Service delivery, clinical notes, invoicing, job assignment acknowledgment
- **Sales Staff**: Contact management, booking creation, follow-ups
- **Accountant**: Invoice verification, payment tracking, financial reports
- **Operations Manager**: Booking validation, staff assignment, oversight
- **Head Nurse**: Staff allocation, replacement management
- **Board/Data Custodian**: Price list and lookup table changes only
- **Marketing Team**: Website-only admin access (no back-office access)

### Staff Assignment & Notification
- Zalo integration for staff assignment notifications
- Nurse acknowledgment of assignment in Zalo updates CRM status
- Push notifications via Zalo 


### Staff Skills & Availability
- Skills tracking per staff member
- Workload management


---

## 5. Invoicing System

### Invoice Types
- **Red Invoice (VAT Invoice)**: Government-compliant tax invoice submitted same day to tax department
- **Retail Invoice**: Internal tracking invoice, always generated for all clients
- Two invoice types required for different scenarios

### Four Invoicing Scenarios
1. **Immediate payment after service**: Red invoice issued upon payment
2. **Prepayment**: Red invoice issued for amount paid; services deducted from balance; retail invoice issued upon service delivery
3. **Service delivered, payment delayed**: Red invoice issued and marked unpaid; submitted same day to avoid fines


### Invoice Workflow
- Workflow stages: Confirm → Issue → Paid (Draft stage removed)
- Nurses generate invoices immediately after service completion
- No draft stage to avoid late submission penalties
- Minor errors tolerated (under/over-charging) to prioritize timely submission
- Confirmation step before finalizing invoice
- Invoice modification with mandatory notes allowed

### Nurse Invoice Generation
- Nurses create invoices at point of service via mobile app
- Pop-up for nurse to record payment status and payment mode
- Start button triggers job timer and opens invoicing details
- Job considered complete upon invoice submission
- Nurses can select items and input additional data (e.g., number of IV bottles, wound size)
- Nurses can override service costs with mandatory note (e.g., discounts)


### Part-Time/Casual Nurse Handling
- Part-time/casual nurses do NOT create invoices
- Operations handles invoicing on their behalf
- So Different workflow for casual vs full-time staff

### Invoice Integration
- Ability to modify invoice before confirmation
- Invoice tracking linked to each client profile for quick lookup
- Invoices linked to specific bookings and assignments

### Payment Processing
- Payment options: Pay Now (cash, transfer, online, credit card, QR code) or Pay Later
- Payment methods: Cash, bank transfer, credit card (rarely used due to fees), QR code (future)
- Cash payment handling: Nurse collects → Operations Manager verifies → Electronic receipt issued
- Screenshot of bank transfer as proof of payment
- Unpaid services marked in Accounts Receivable

### Prepaid Services & Packages
- **Step 1 (Prepayment)**: Client receives VAT invoice for full prepaid amount
- **Step 2 (Service Delivery)**: Retail invoice generated showing service delivered with "prepaid" as payment method
- **Example**: 1 VAT invoice + 5 retail invoices (if 5 services prepaid)
- Prepaid services flagged to prevent duplicate charges
- Retail invoices track status (paid/unpaid, prepayment usage)
- Liability recorded until services rendered
- Refunds handled via MISA and accounted in Accounts Receivable

### Package Management
- Healthcare packages: blood pressure management, physiotherapy, diabetes management, annual monitoring
- Front desk can generate prepaid invoices at client level without existing booking
- Packages cover multiple services (e.g., physiotherapy sessions)
- Package fields: number of services, costs, expiry date
- Countdown mechanism tracks remaining services (e.g., 7 physiotherapy sessions remaining)
- Service usage tracking and flagging when prepaid services exhausted
- Package expiry dates can be extended if clients unavailable
- Unused services can be refunded
- Manual package creation by front desk with notes specifying service details


### Discount Handling
- Discounts shown separately (not adjusting package price directly)
- Discount field in invoicing
- Nurses can apply discounts with mandatory notes

### Invoice Status Tracking
- Invoice statuses: Confirmed, Issued, Paid, Unpaid, Partial Payment
- Accounts Receivable integration for outstanding invoices
- Payment status visible in client profile

---

## 6. Pricing Engine

### Price List Structure
- **Separate price lists** for:
  - Services (30 base items, expandable with conditions)
  - Laboratory tests (550 items for Hanoi, 250+ for HCMC)
- Province-based pricing: Hanoi and Ho Chi Minh City
- Price lists can be combined with province filter for easier management
- Service categories: Doctor services, Nurse services, Laboratory services
- Subcategories for filtering

### Base Pricing
- Base prices listed per service
- Example: Internal medicine charged per 20-minute unit at 500,000 VND
- Laboratory prices fixed by province (no adjustment rules except rounding)
- Service prices vary based on rules

### Price Adjustment Rules
- **Time-based adjustments**:
Examples
  - After-hours (post-7 PM): 1.5x or 30% overtime
  - Weekends: 1.5x
  - Public holidays: 3x (TET holiday: triple rate)
- **Service-specific adjustments**:
  - Distance-based pricing
  - Urgency level surcharges
  - Number of injections (additional injections)
  - Wound size (e.g., wounds over 30 cm flagged for hospital referral)
  - Bilingual provider requirements
  - Service location (home, clinic, hospital)
- **Automated triggers** for surcharge application
- **Adjustment sequence** defined to prevent double-counting
- Nurses must provide notes whenever adjustments applied
- Rules-based adjustments included in retail invoices with modification codes

### Rules Engine
- Configurable rules based on multiple conditions: holiday, urgency, distance, service location, province, time, date
- Actions available: add amount, multiply factor, percentage adjustments
- Scheduled date of service determines pricing (not invoice creation date)
- Holiday/weekend date logic integrated
- Recalculation based on booking date and service parameters

### Price List Management
- Automatic city restriction per user
- Bulk import/export via Excel
- Support updates without overwriting unchanged records
- Audit trail required: user, date, changes, notes column
- Access restricted to admin/board roles
- Workflow for change requests (staff can request, cannot edit directly)
- Board retains sole authority for price table changes


### Translation Requirements
- Service names in Vietnamese and English
- Translation mechanism for multi-language support


---

## 7. Government Compliance & Integrations

### Ministry of Health (MOH) Submissions
- All client visit data must be reported to MOH systems
- MOH requires electronic prescription submission
- MOH field requirements table needed
- Clinical notes with mandatory fields for MOH compliance
- MOH submissions include: client details, prescriptions, clinical data
- Separate from clinical notes (different submission)


### Red Invoice Compliance
- Red invoices mandatory for tax reporting on same day as service completion
- Required even if payment pending
- Submitted to Vietnam Tax Department
- Same-day submission critical to avoid severe penalties


### Government System Integration
- Must handle two separate company entities (HCMC & Hanoi)
- Separate red invoice streams per company
- Each company has separate government accounts

### VAT Submission
- VAT invoices submitted via MISA
- XML/JSON data exchange format (to be confirmed with office manager/accountant)
- VAT invoice numbers issued by external authorized company
- VAT invoice format must align with Vietnam government standards
- Invoices sent to MISA for accounting purposes 

---

## 8. API Integrations

### Cloud Doctor Integration
- Clinical reporting submission
- Optional integration for clinical note uploads
- Manual note upload option if Cloud Doctor not used

### MISA Integration (Accounting System - Current)
- Accounting system integration
- VAT invoice submission to government
- Single API to generate and submit VAT invoices directly
- Two company accounts (HCMC & Hanoi), each with separate MISA instances
- Process: Invoice raised in system → XML template generated → sent to MISA → submitted to tax department
- Integration with Accounts Receivable
- MISA API definition required
- Prepayment and refund handling


### Referral Platform Integration
- BookingCare
- Doc
- Die



## 9. Mobile Application (Nurse App) - health_pwa

### Platform & Distribution
- Distribution via QR code/URL link
- First login ties app to individual user/device
- Only One-time authentication per device

### Core Functions
- View assigned bookings/jobs
- Access client details and booking information
- Equipment checklist viewing


### Job Management
- Start job button (triggers timer, opens invoicing details)
- Complete job button (requires clinical notes and invoice)
- Job cannot be marked "completed" until both clinical notes and invoice submitted
- Real-time sync of job status to Operations
- Job status updates visible to all stakeholders

### Clinical Notes
- Upload handwritten notes as photos
- Direct text entry option
- Mandatory before job closure
- Attach photos/documents (e.g., prescriptions, wound photos)
- Import functionality for scanned documents
- Notes cannot be skipped unless service marked "incomplete"

### Invoice Generation
- Generate invoices at point of service
- Prepaid, paid, or unpaid invoice options
- Payment method selection
- Payment status recording
- Quantity adjustments (e.g., number of injections, wound size)
- Discount application with mandatory notes

### Offline Capability
- Offline data capture
- Data synchronization once internet restored
- Visual indication of online/offline status
- Confirmation of data transmission success
- Critical for field staff with patchy connectivity

### Location & Tracking
- GPS access for location tracking
- Camera access for photo uploads


### Security
- Biometric login (to be explored)
- Remote user deactivation capability (blocking access)
- Remote app deletion (if feasible)
- Secure authentication per device



---

## 10. Clinical Notes & Documentation

### Clinical Note Requirements
- Mandatory clinical notes before job completion
- Job cannot be closed without clinical notes submission
- Clinical notes essential (not optional)
- MOH-compliant field requirements
- Prescription documentation

### Input Methods
- Photo upload of handwritten notes
- Scanned document import
- Direct text entry in mobile app
- Attach supporting documents (prescriptions, lab results)
- Multiple photos per visit allowed



## 11. Accounts Receivable

### Payment Tracking
- Track payment status: Paid, Unpaid, Partial Payment
- Outstanding debt monitoring
- Prepayment balance tracking
- Payment method recording (cash, transfer, credit card, QR code)

### Prepayment Management
- Prepaid service usage tracking
- Countdown of remaining prepaid services
- Flag when prepaid services exhausted
- Liability tracking until services rendered
- Prepayment application to bookings

### Payment Terms
- Immediate payment
- Post-service payment
- Custom payment schedules
- Flexible payment term support

### Refund Handling
- Refund processing for unused prepaid services
- Integration with MISA for refund accounting
- Refund tracking and reporting

### Outstanding Invoice Management
- Overdue invoice tracking
- Payment reminders (future)
- Debt collection support
- Aging report for unpaid invoices

### Integration
- Linked to invoicing system
- MISA accounting integration
- Real-time payment status updates
- Dashboard for outstanding balances

---



#

---

#

---

## 16. Configuration & Master Data

### Lookup Tables & Master Data
- Cancellation reasons
- Customer types (new/existing)
- Client categories (VIP, regular, emergency, senior, pediatric)
- Service types (outpatient/inpatient, doctor/nurse/laboratory)
- Clinic details and facilities
- Contact sources (may be redundant - to be reviewed)
- Source of introduction/referral (standardize naming)
- Insurance providers
- Referral sources
- Payment methods
- Relationship types (spouse, child, parent, sibling, friend)
- Urgency levels
- Equipment types

### Province/District/City Data
- Province list for Vietnam
- District/city dropdown lists
- Structured address templates
- GPS coordinates per location
- Coverage area definitions

### Facility Management
- Multi-location setup (Hanoi, HCMC)
- Facility details and licensing
- Service availability per facility
- Coverage areas per location
- Appointment scheduling per facility

### Holiday Calendar
- Public holiday lookup table
- Holiday pricing rules (3x for TET, etc.)
- Auto-populate holidays from internet (optional)
- Annual calendar update reminder to HR/accounting
- Holiday date logic for pricing calculation

### Service Catalogs
- Service category hierarchy
- Service subcategories
- Laboratory test catalogs (550 Hanoi, 250+ HCMC)
- Doctor service catalog (30 base items)
- Nurse service catalog
- Cascading service selection

### Code Management & Data Custodian
- Data Custodian role for master data management
- Board of Directors controls code changes
- Formal board approval required for code updates
- Staff can request changes but cannot edit directly
- Audit trail for all code changes (user, date, changes, notes)
- Lookup code cleanup to eliminate duplicates
- Avoid inconsistent codes

### Translation & Multi-Language
- Configuration table for multi-language support
- User language preference determines display
- Vietnamese and English initially
- Context-sensitive Vietnamese translation requiring manual review
- Future: Additional language support

### Audit Trail Requirements
- All configuration changes logged
- User, date/time, old value, new value, notes
- Change request workflow
- Approval tracking
- Archive old configurations before updates

---



## 18. UI/UX Requirements

### User Interface Simplification
- Minimize number of clicks/screens
- Simplified navigation
- Reduce complexity for end users
- Single-screen workflows where possible
- Intuitive design for non-technical users

### Language & Localization
- Primary language: Vietnamese
- English as secondary language
- All staff informed system will be in Vietnamese
- User language preference selection
- Context-sensitive translations

### Visual Design & Branding
- Apply official Việt Úc Clinic branding
- Logos and color scheme integration
- Professional healthcare aesthetic
- Modern and clean design
- Branding guide to be provided by client

### Workflow Interface
- Step-by-step field display based on workflow stage
- Progressive disclosure of information
- Minimal initial fields, expand as workflow progresses
- Context-aware form fields

### Catalog Interface
- Cascading service selection (health services → categories → specific products)
- Catalog button for easy browsing
- Reduce need to scroll through long lists
- Visual product/service selection

### Pop-ups & Notifications
- Mandatory note pop-ups for changes (cancellations, invoice edits, discounts)
- Payment status pop-up for nurses (Pay Now or Pay Later)
- Cancellation reason pop-up
- Confirmation pop-ups before critical actions

### Dashboards
- Role-based dashboard views
- Admin dashboard
- Nurse dashboard
- Sales dashboard
- Accountant dashboard
- Operations dashboard
- Customizable widgets
- Real-time data display

### Visual Indicators
- Online/offline status indicators
- Data transmission confirmation
- Job status visual indicators
- Booking status color coding
- Alert notifications for overdue items


### Mobile App UI

- Minimal text entry required
- Camera integration for photos
- GPS integration
- Offline mode indicators

---

## 19. Security & Access Control

### Authentication
- User authentication once per device (mobile app)
- Username/password login
- Session management
- Login tracking and audit

### Biometric Security
- Biometric login exploration for mobile app
- Fingerprint/Face ID support
- Enhanced security for field staff

### Role-Based Access Control (RBAC)
- Granular permissions per role
- Admin: Full system access
- Board: Price list and lookup table changes only
- Operations Manager: Booking validation, staff assignment
- Sales: Contact and booking creation, no financial access
- Nurse: Service delivery, notes, invoicing (assigned jobs only)
- Accountant: Financial data, invoice verification
- Marketing: Website-only access, no back-office
- Data Custodian: Master data with board approval

### User Management
- Remote user deactivation capability
- Block access for terminated staff
- Disable user accounts immediately
- Remote app deletion (if feasible)
- User activity monitoring

### Audit Logging
- All changes logged (who, what, when, why)
- Lookup table changes tracked
- Price list modifications logged
- Invoice changes with mandatory notes
- Configuration change history
- Call activity audit log (sales staff off-hours monitoring)

### Data Access Restrictions
- Row-level security (users see only their data)
- City-based data restriction (auto-filter by user location)
- Automatic city restriction per user
- Client data privacy
- Financial data access control


---

