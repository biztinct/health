# Healthcare CRM System - Requirements Documentation

**Project:** HHHPL x IADC Integrated Healthcare Management System
**Period Covered:** August 8 - October 1, 2025
**Source:** 14 Meeting Minutes Documents
**Total Requirements:** 200+ discrete requirements

---

## 1. CRM & Lead Management

### Lead Capture & Tracking
- Automatic lead capture from multiple channels: Google Ads, Facebook, Zalo, website forms, TikTok
- Each ad/post must have unique campaign ID for tracking
- Lead tracking flow: ad/post → call/chat → lead in CRM
- Integration with Zapier for marketing channel tracking
- Visitor tracking integration (Plausible or Google Analytics)
- Real-time website visitor behavior monitoring
- Lead source attribution (Facebook, Google Ads, Zalo, website, calls, referrals)

### Lead vs Contact Differentiation
- **Lead**: Generated from campaign sources (Google Ads, Facebook) without direct interaction
- **Contact**: Created when lead provides verifiable information (name, phone) or initiates communication
- Leads without sufficient information tagged as "not reliable" or "junk calls"
- Only verifiable campaign-source leads recorded in system
- Contact workflow: check if phone number is known (new vs existing contact)

### Contact Management
- Contact creation from leads or direct interactions (calls, clinic visits, Zalo chat, form submission)
- Mandatory fields: phone number, service type, scheduled time
- Contact tagging: new, booked, junk, lead to follow up
- Conversion tracking: contact → booking (20-45% conversion rate)
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
- Client profiles linked to all service history

### Related Persons Management
- **Related Person Master File** linked bidirectionally with Client Master
- Categories: Contact Representative, Caregiver, Payer, Referrer, Emergency Contact, Legal Guardian
- Single normalized table for all related person types
- Multiple related persons allowed per category (e.g., multiple caregivers, multiple payers)
- Relationship definitions: spouse, child, parent, sibling, friend, etc.
- Healthcare relationships table for storing relationship types
- Auto-generated unique IDs for all related persons
- Dashboard showing linked clients ↔ related persons

### Client Identification & Data
- Clients can be "the client" (receiving service) or representative
- Payers can pay for multiple clients
- Caregivers can be primary contacts
- Compulsory questions (payer details, client information) asked closer to booking completion
- Minimal fields for initial booking to avoid overwhelming interaction
- Step-by-step field display based on workflow stage

### Address Management
- Structured address template required for standardization
- Province/district/city dropdown lists
- GPS mapping integration from address
- Coverage area tracking per facility
- Distance-based pricing potential

---

## 3. Booking & Scheduling

### Booking Workflow
- Workflow stages: Initial inquiry → Tentative booking → Validated/Confirmed (by Operations) → Assigned to staff
- Multiple nurses/doctors can be assigned to single booking (complex cases)
- Each staff assignment produces own invoice
- Future and repeated bookings visible historically and prospectively
- Booking modification capability before confirmation

### Service Selection
- Service type selection: Doctor, Nurse, Laboratory
- Service category selection (e.g., internal medicine, wound care)
- Specific product/service selection from catalog
- Catalog interface with cascading selection (health services → specific products)
- Catalog button to simplify service selection and reduce scrolling

### Scheduling Views
- Timeline view (day/week/month)
- Day view for detailed scheduling
- Week view for overview
- Drag-and-drop booking visualization
- Visual booking assignment interface

### Staff Assignment
- Manual staff assignment by Operations team
- Multiple staff per booking supported
- Staff replacement handling (e.g., nurse sickness)
- Flexible reassignment capability
- Head Nurse manages staff replacements
- Operations Manager validates and assigns bookings

### Booking Status Tracking
- Booking statuses: New, Assigned, In Progress, Completed, Cancelled
- Status updates synchronized across system
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
- Push notifications via Zalo (Easy HR integration not required for Phase 1)
- Staff can view assigned jobs in mobile app
- Real-time sync of assignment status

### Staff Tracking (Future Phase 2)
- Field tracking: nurse location, check-ins
- GPS-based routing
- Job monitoring
- Shift, holiday, attendance functions in main system
- Workload distribution tracking

### Staff Skills & Availability
- Skills tracking per staff member
- Workload management
- Staff availability management (manual in Phase 1)
- No automated leave/availability checks in current phase

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
4. **Draft invoice before service**: Operations drafts, nurse delivers service, red invoice issued upon payment (ELIMINATED - nurses now create invoices immediately post-service)

### Invoice Workflow
- Workflow stages: ~~Draft~~ → Confirm → Issue → Paid (Draft stage removed)
- Nurses generate invoices immediately after service completion
- No draft stage to avoid late submission penalties (3-5 million VND per late invoice)
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
- Discretion for overrides may be limited to Operations Managers

### Part-Time/Casual Nurse Handling
- Part-time/casual nurses do NOT create invoices
- Operations handles invoicing on their behalf
- Different workflow for casual vs full-time staff

### Invoice Integration
- Integration with healthcare module to link invoices to patient records
- Ability to modify draft invoice before confirmation
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
- Prepayment bypass quotation; invoice generated directly
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
- Avoid complex automation for now; flexible manual definition

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
- Base prices are fixed; adjustments applied via rules

### Price Adjustment Rules
- **Time-based adjustments**:
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
- Price list filtered by city and service type (Doctor/Nurse)
- Bulk import/export via Excel
- Support updates without overwriting unchanged records
- Audit trail required: user, date, changes, notes column
- Archiving old tables before updates for auditability
- Access restricted to admin/board roles
- Workflow for change requests (staff can request, cannot edit directly)
- Board retains sole authority for price table changes
- Manual approval workflow (to be automated later)

### Translation Requirements
- Service names in Vietnamese and English
- Translation mechanism for multi-language support
- Context-sensitive Vietnamese translations requiring manual review

### Quotation Process
- Quotations created using catalog interface
- Quotations include base price plus adjustments for accurate client estimate
- Itemized display of all adjustments applied
- Service code creation from catalog

---

## 7. Government Compliance & Integrations

### Ministry of Health (MOH) Submissions
- All client visit data must be reported to MOH systems
- MOH requires electronic prescription submission
- MOH field requirements table needed
- Clinical notes with mandatory fields for MOH compliance
- MOH submissions include: client details, prescriptions, clinical data
- Separate from clinical notes (different submission)
- APIs and sandbox access available for testing
- Build and test integrations via sandbox → live submission

### Red Invoice Compliance
- Red invoices mandatory for tax reporting on same day as service completion
- Required even if payment pending
- Late submission penalties: 3-5 million VND per invoice
- Potential for batch processing
- Submitted to Vietnam Tax Department
- Same-day submission critical to avoid severe penalties

### Digital Signatures
- Digital signatures (government-verified) required on Red Invoices
- Submitted to Treasury with e-signature
- E-signature provider: **Viettel** (not MISA) to avoid licensing issues
- Local provider for MOH compliance
- Goal to extend digital signatures to all documents (contracts, government submissions)
- Custom numbering for invoices

### Government System Integration
- Must handle two separate company entities (HCMC & Hanoi)
- Separate red invoice streams per company
- Each company has separate government accounts

### VAT Submission
- VAT invoices submitted via MISA
- XML/JSON data exchange format (to be confirmed with office manager/accountant)
- VAT invoice numbers issued by external authorized company
- VAT invoice format must align with Vietnam government standards
- Invoices sent to MISA for accounting purposes after Viettel e-signature

---

## 8. API Integrations

### Cloud Doctor Integration
- API link for client details
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

### Viettel Integration
- E-prescription submission to MOH
- E-signature provider for Red Invoices
- MOH interface provider
- Government submission integration
- API details to be provided by Viettel contact

### Easy HR Integration
- Minimal integration for Phase 1
- Booking details sent to nurses
- Job timings sent back to CRM
- Attendance and timesheet calculations
- Long-term: shift, holiday, attendance functions in main system

### Zapier Integration
- Marketing channel tracking
- Facebook/Zalo calls and chats integration
- Campaign ID capture from each ad/post
- Ad performance tracking
- Lead source tracking flow

### VOIP247 Integration
- Call tracking and logging
- Call forwarding traceability (CRITICAL requirement)
- Incoming/outgoing call recording
- Unanswered call tracking
- SMS notifications for missed calls
- Call duration and outcome logging
- Audio storage for compliance
- Monitor redirected calls during shift changes
- API to track forwarded calls to salesperson mobiles
- Legal compliance for call recording in Vietnam
- Future: AI for quality control
- Ensure calls forwarded to mobiles captured in CRM

### Social Media & Marketing Platform Integration
- Meta/Facebook (ads, posts, campaign tracking)
- Google Ads (campaign tracking, lead capture)
- Zalo (calls, chats, OA account)
- TikTok (future platform)
- YouTube (future consideration)
- Login credentials required for Meta integration
- Ben (marketing contact) to coordinate on campaigns and integrations

### Referral Platform Integration
- BookingCare
- Doc
- Die
- Sales team to provide platform details

### Website Integration
- WordPress website integration via API
- Lead capture forms push to CRM
- Real-time visitor tracking
- Website form, chat, Zalo call, hotline call automation
- Current manual entry in Pancake CRM to be eliminated
- Automated logging from all channels
- Website hosting on Odoo platform for real-time integration (discussed)
- Campaign click tracking → WordPress → API → CRM leads

---

## 9. Mobile Application (Nurse App)

### Platform & Distribution
- Hybrid mobile app (works on iOS & Android)
- Distribution via QR code/URL link
- First login ties app to individual user/device
- One-time authentication per device

### Core Functions
- View assigned bookings/jobs
- Access client details and booking information
- Equipment checklist viewing
- Real-time synchronization with operations

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
- Future: GPS-based route optimization
- Future: Job monitoring via location

### Security
- Biometric login (to be explored)
- Remote user deactivation capability (blocking access)
- Remote app deletion (if feasible)
- Secure authentication per device

### Integration
- Real-time sync with CRM backend
- Zalo notification integration
- Equipment tracking
- Service status updates
- Future: HR/attendance integration
- Future: Field service module integration

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

### Integration
- Optional Cloud Doctor integration for automated note storage
- Manual upload option if Cloud Doctor not used
- Notes linked to specific client visit
- Notes accessible from client profile

### Compliance
- MOH mandatory fields included
- Prescription submission to MOH via Viettel
- Clinical data separate from prescriptions for MOH
- Audit trail for note creation and modifications

---

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

## 12. Reporting & Analytics

### Daily Reports
- Daily activity summary (services completed)
- Daily revenue report
- Services per day/week/month
- Staff performance metrics

### CRM & Conversion Reports
- Conversion rate tracking: Lead → Contact → Booking → Client (20-45% benchmark)
- Lead source performance (Google Ads, Facebook, Zalo, etc.)
- Campaign attribution reports
- Stage count reports (leads, contacts, bookings, clients)
- Follow-up effectiveness tracking

### Financial Reports
- Revenue by service type
- Revenue by location (Hanoi, HCMC)
- Revenue by staff member
- Payment method breakdown
- Outstanding invoice report
- Prepayment balance report
- Accounts receivable aging

### Service Reports
- Service type usage (doctor, nurse, laboratory)
- Customer order history
- Service frequency by client
- Package usage tracking
- Service completion rates

### Statutory Reports
- MOH compliance reports (client data, prescriptions, clinical notes)
- Tax department reports (VAT, Red invoices)
- Submission tracking and confirmation

### Management Reports
- Internal management dashboards
- Visitor tracking reports (website activity, lead behavior)
- Staff workload distribution
- Client satisfaction metrics (future)
- Booking cancellation analysis

### Export & Filtering
- Export to Excel capability
- Filter by date range
- Filter by location (Hanoi, HCMC)
- Filter by service type, staff, client category
- Grouping functionality
- Custom report generation

### Dashboard Features
- Revenue trends
- Activities overview
- Overdue invoices highlighted
- Service usage statistics
- Real-time metrics
- Role-based dashboard views

---

## 13. Website Integration

### Lead Capture
- Web forms for lead capture
- Automated lead creation in CRM from form submission
- No sophisticated client portal required (Phase 1)
- No client-facing calendar system (Phase 1)

### Campaign Tracking
- Campaign click tracking from ads
- Source attribution (Google Ads, Facebook, Zalo)
- UTM parameter capture
- Campaign performance analytics

### Visitor Tracking
- Real-time visitor behavior monitoring
- Visitor activity tracking (similar to Zoho)
- Lead behavior analysis
- Integration with Plausible or Google Analytics
- Balance performance and functionality

### Website Platform
- New website under development by marketing agency
- Current domain and channels to be utilized
- Discussion on hosting on Odoo platform for real-time integration
- WordPress integration via API
- Website-only admin role for marketing team (no back-office access)

### Channel Integration
- Website forms
- Live chat
- Zalo integration
- Hotline integration
- Current channels: Facebook, Zalo, Google Ads, website
- Automated logging from all channels (eliminate manual entry)

---

## 14. VOIP & Call Management

### Call Recording & Logging
- All incoming calls recorded
- All outgoing calls recorded
- Call duration tracking
- Answer time tracking
- Call outcome logging
- Audio storage for compliance

### Call Forwarding Traceability (CRITICAL)
- Track calls forwarded to salesperson mobiles
- Monitor redirected calls during shift changes
- Capture call details after forwarding
- Lost tracking issue after forwarding to be resolved
- VOIP247 API review for forwarding traceability
- Legal compliance for recording forwarded calls in Vietnam

### Unanswered Call Management
- Track unanswered calls
- SMS notifications for missed calls
- Visibility of diverted calls
- Follow-up workflow for missed calls

### CRM Integration
- Automatic lead/contact creation from calls
- Call log linked to contact record
- Call pickup, duration, and handling tracking
- Diverted call tracking

### Call Analytics
- Call volume by time period
- Answer rate metrics
- Call duration analysis
- Staff activity tracking during off-hours (weekends/nights)
- Audit log for call receipt, pickup, duration, handling

### VOIP Provider
- Current VOIP system in use (VOIP247)
- Potential replacement with better alternative
- Sandbox environment evaluation for new system
- Comparison with current setup
- Solution exists despite provider claiming technical limitations

### Future Enhancements
- AI-assisted call logging
- Call quality control via AI
- Automated call conversion tracking
- Headset integration for sales staff

---

## 15. Data Migration

### Source System
- Current CRM: Pancake
- Excel sheets represent Pancake CRM tables
- Legacy CRM data to be migrated

### Migration Planning
- Field mapping from Pancake to Odoo
- Master & child tables identification
- Lookup code mapping
- Transaction stage mapping: Lead → Contact → Booking → Client conversion
- Standardized code cleanup before migration

### Data Structure
- Normalize related person tables (merge caregiver/payer/referral into one)
- Avoid field/table duplication
- Lookup fields/tables finalization
- Client ID standardization and auto-generation

### Migration Process
- Export data from Pancake in Excel format
- Ensure standardized codes and client IDs
- Data cleanup before migration (remove duplicates, inconsistencies)
- Import into Odoo in batches (due to volume constraints)
- Validation of migrated data

### Data Preparation
- Spreadsheet of data structure for migration planning
- Two companies (HCMC & Hanoi) data handling
- Separate red invoice streams
- Master data scrubbing and validation

### Final Data Migration
- Timing: Week 6 of project plan
- Final data migration from legacy CRM
- Post-migration validation

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

## 17. Performance & Technical Requirements

### Response Time Targets
- Dashboard/form screen load: < 2-3 seconds
- Report generation: < 5 seconds
- Fast server-side performance
- Data transfer optimized via caching
- Minimal payload transfer

### System Uptime & Availability
- System uptime: 99.5%
- Hosting: AWS or local hosting
- High availability architecture
- Redundancy and failover

### Concurrent Users
- Support 50-100 concurrent users
- Scalable to larger volumes
- Load balancing capability

### Database Performance
- Capacity: up to 1 million records manageable
- Primary/foreign key indexing for performance
- Database growth projections required from client
- Capacity planning based on volume estimates

### Network & Connectivity
- Performance measured server-side
- Dependency on internet speed acknowledged
- Normal latency/connection assumed
- Patchy Wi-Fi/5G ignored in baseline testing
- Screen refresh/latency targets to be defined in performance testing

### Offline Capability
- Offline data capture for mobile app
- Data synchronization when internet restored
- Visual indication of online/offline status
- Confirmation of data transmission success
- Critical for nurses with unreliable field connectivity

### Device Compatibility
- Modern mobile devices expected (smartphones)
- Potential shift to tablets in future
- Desktop browser compatibility
- Responsive design for various screen sizes

### Data Volume & Scalability
- Database growth monitoring
- Scalability for increasing transaction volumes
- Batch processing for large imports
- Performance optimization for growing datasets

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

### Drag-and-Drop Features
- Drag-and-drop booking visualization
- Nurse assignment via drag-and-drop
- Intuitive scheduling interface

### Mobile App UI
- Touch-optimized interface
- Large buttons for field use
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

### Compliance & Data Protection
- Call recording compliance (Vietnamese regulations)
- Patient data confidentiality
- Government submission security
- E-signature security (Viettel)
- Secure API communications

---

## 20. Future Enhancements (Phase 2 & Beyond)

### HR Module Automation
- Automated attendance/scheduling modules
- Shift management
- Holiday tracking and management
- Leave management
- Staff availability integration into booking system
- Timesheet automation

### Finance & Accounting
- Full accounting module tailored to international best practices
- Feeding into MISA for compliance
- Advanced financial reporting
- Budget management
- Cost center tracking

### AI Integration
- AI as systems analyst for holistic review
- Legislation monitoring
- Staff interaction and satisfaction monitoring
- Workflow optimization suggestions
- Business improvement feedback
- AI-assisted call logging and conversion
- Call quality control via AI
- AI knowledge base (30-40% of global knowledge)
- Daily AI exploration for capabilities

### Field Service Enhancements
- GPS-based routing and optimization
- Real-time nurse location tracking
- Check-in/check-out tracking
- Route planning and optimization
- Distance calculation for billing
- Map integration for coverage areas

### Advanced Client Portal
- Client-facing portal for booking
- Client self-service features
- Appointment scheduling by clients
- Payment portal
- Document access (invoices, prescriptions)

### Payment Enhancements
- QR code payment integration
- Advanced credit card processing
- Online payment gateway
- Recurring payment automation
- Payment plan automation

### Advanced Analytics
- Predictive analytics for demand forecasting
- Client satisfaction tracking and analytics
- Staff performance analytics
- Advanced business intelligence dashboards
- Trend analysis and forecasting

### Marketing Automation
- Automated lead nurturing campaigns
- Email/SMS marketing integration
- Client segmentation
- Personalized communications
- Campaign performance optimization

### Website & Digital Presence
- Sophisticated client portal
- Client-facing calendar system
- Online booking system
- Telemedicine integration (future)
- Mobile app for clients (in addition to staff app)

### Collaboration System
- Internal collaboration tools
- Document sharing
- Team communication
- Task management
- Workflow automation

### Additional Platforms
- YouTube integration
- Additional social media platforms
- Emerging digital channels
- Regional platform expansion

### System Evolution
- Framework for continuous adaptation
- Processes that evolve with business growth
- Customization at every level
- Scalability for international expansion (other countries)
- Currency and internationalization support

---

## Implementation Priority Notes

### Phase 1 (Weeks 1-8) - CURRENT SCOPE:
- CRM (contacts, leads, bookings)
- Invoicing (Red & Retail)
- API integrations (Cloud Doctor, MISA, Viettel, Easy HR, Zapier, VOIP247)
- Manual scheduling and job assignments
- Basic reporting
- Mobile app for nurses
- Red invoice compliance
- MOH submissions
- Accounts Receivable

### Phase 2 (Future):
- HR automation
- Advanced field service features
- AI layer integration
- Client portal
- Advanced analytics
- Payment automation
- Marketing automation

---

**END OF REQUIREMENTS DOCUMENT**

**Total Functional Areas:** 20
**Total Requirements:** 200+ discrete requirements
**Source Documents:** 14 meeting minutes (Aug 8 - Oct 1, 2025)
**Last Updated:** Based on meetings through October 1, 2025

**Notes:**
- Action items from meetings have been excluded as requested
- Requirements organized by functionality/screen for implementation tracking
- Each requirement can be checked off as implemented
- Requirements reflect client discussions and decisions, not interpretations
- Some requirements marked as "Phase 2" or "Future" based on meeting context
