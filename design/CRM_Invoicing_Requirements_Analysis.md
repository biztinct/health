# CRM & Invoicing System Requirements Analysis

## Extracted from: CRM_Invoicing_TablesFields_20250817.xlsx

## 1. WORKSHEET/TAB OVERVIEW

### Core Data Structure (23 Worksheets)
1. **Contact Management**: Contact, Client Representative, Lead Management
2. **Patient/Client Data**: CMF (Client Master File), Caregiver, Person Paying, Referrer, RelatedParty
3. **Service Delivery**: Job Sheet & Assignment, ServiceEvent, Booking, BookingStatusHistory
4. **Financial**: InvoiceHeader, InvoiceLine, Payment, PrepaymentBatch
5. **Follow-up**: Service Followup, AssignmentNotificationLog
6. **Geographic**: Address, Address input Template, Province
7. **System**: RBAC Notes, Field Catalog

---

## 2. DETAILED TABLE ANALYSIS

### A. CONTACT MANAGEMENT TABLES

#### Contact Table (Core CRM Entry Point)
**Purpose**: Central contact tracking across all channels (Facebook, Zalo, phone, etc.)
**Key Fields**:
- `unique_contact_ID` [Compulsory] - Sequential per city
- `record_status` [Compulsory] - Active/Deleted/Archived
- `Contact Date/Time` [Optional] - Auto-record with override
- `client_representative_id` [Compulsory] - Links to representative
- `channel this contact` [Optional] - Contact method tracking
- `campaign this contact` [Optional] - Lead source tracking
- `province_code` [Compulsory] - Geographic filtering
- `Contact Outcome` [Optional] - Service Booked/Pending/Rejected
- `client_id` [Compulsory] - Auto-generated for new clients
- `Caregiver 1 ID`, `Caregiver 2 ID`, `Payer ID`, `Referrer ID` [Optional]
- `Lead Follow-up Required` [Optional] - Auto-calculated
- `Booking Status` [Compulsory]

**Mapping to Odoo**: 
- **Base Model**: `health_base.res.partner` (enhanced contact)
- **Extension**: `health_crm.health.contact` (inherit from partner)
- **Key Integration**: CRM pipeline stages, lead source tracking

#### Client Representative Table
**Purpose**: Person making contact on behalf of client
**Key Fields**:
- `contact_id` [Compulsory] - Links to contact
- `Representative Name`, `Kinship Title`, `Preferred Name` [Optional]
- `Relationship` [Optional] - Is Client/Relative/Friend/Other
- `Representative Phone No 1/2`, `email`, `Zalo` [Optional]
- `Details Complete` [Optional] - Triggers follow-up if No

**Mapping to Odoo**:
- **Model**: `health_base.health.contact.representative` (new model)
- **Relation**: Many2one to res.partner (contact)

#### Lead Management Table
**Purpose**: Follow-up tracking for potential bookings
**Key Fields**:
- `lead_id` [Compulsory]
- `unique_contact_id` [Compulsory]
- `service_interest` [Optional]
- `Lead Status` [Compulsory] - Booked/Continuing Follow-up/Booking lost
- `next_action_at` [Automated] - Next follow-up date

**Mapping to Odoo**:
- **Base Model**: `crm.lead` (standard Odoo CRM)
- **Extension**: `health_crm.health.lead` (inherit and extend)

### B. PATIENT/CLIENT DATA TABLES

#### CMF (Client Master File) - Core Patient Record
**Purpose**: Complete patient/client information
**Key Fields**:
- `client_id` [Compulsory] - Auto-generated
- `Client Name`, `Kinship title`, `Preferred Name` [Optional]
- `ID Number`, `CCCD number`, `Date of Birth`, `Gender` [Optional]
- `Ethnicity/Dân tộc`, `Occupation` [Optional]
- `Client Phone Number`, `Client Email` [Optional]
- `Date of First Service` [Optional]
- `Caregiver 1/2 ID`, `Payer Id`, `Referrer Id` [Optional]
- `Client Address` [Optional] - Structured address (see Address Template)
- `GPS Coordinates`, `Distance from clinic` [Optional]
- `Client Deceased`, `DoD` [Optional]

**Mapping to Odoo**:
- **Base Model**: `health_base.health.patient` (existing)
- **Enhancement Needed**: Add Vietnamese-specific fields (CCCD, ethnicity, kinship terms)

#### Caregiver, Person Paying, Referrer Tables
**Purpose**: Related parties with specific roles
**Common Pattern**: 
- Links to multiple clients
- Contact information
- Role-specific fields (commission for referrers, tax numbers for payers)

**Mapping to Odoo**:
- **Model**: `health_base.health.related.party` (new base model)
- **Specializations**: Inherit for caregiver, payer, referrer specific fields

### C. SERVICE DELIVERY TABLES

#### Job Sheet & Assignment (Core Workflow)
**Purpose**: Booking assignment and staff notification
**Key Fields**:
- `Booking_id` [Compulsory]
- `contact_id` [Compulsory] - Links to original contact
- `client_id` [Compulsory] - Auto-filled
- `service_type` [Compulsory]
- `Service Items Confirmed` [Optional] - From price list
- `Agreed Price`, `Prepaid flag` [Optional]
- `Confirmed Date/time_start` [Optional]
- `Service Providers Assigned to booking` [Optional]
- `Services Providers Notified/Accepted` [Optional]
- `booking status` [Compulsory] - Triggers calendar updates
- `Draft Invoice saved`, `Clinical Notes Template saved` [Optional]

**Mapping to Odoo**:
- **Base Model**: `health_fieldservice.health.assignment` (existing)
- **Enhancement**: Add staff notification tracking, clinical template integration

#### ServiceEvent (Actual Service Delivery)
**Purpose**: Track actual service start/end times
**Key Fields**:
- `start_time_actual` [Optional] - Opens invoice app, changes status to Started
- `Selection of invoice app` [Optional] - Triggers MOH records, pharmacy prescriptions
- `end_time_actual` [Optional] - Submission of invoice, status to Finished
- `start_time_adjusted`, `end_time_adjusted` [Automated] - Audit trail

**Mapping to Odoo**:
- **Model**: `health_fieldservice.service.event` (new model)
- **Integration**: Links to health.assignment, triggers invoice workflow

#### Booking & BookingStatusHistory
**Purpose**: Core booking management with audit trail
**Key Fields**:
- `booking_id`, `client_id`, `service_type` [Compulsory]
- `planned_start`, `planned_end` [Optional]
- `status`, `stage` [Compulsory]
- Workflow tracking: `submitted_by/at`, `handed_off_by/at`, `received_by_om/at`

**Mapping to Odoo**:
- **Base Model**: `health_calendar.health.appointment` (existing)
- **Enhancement**: Add workflow stages, status history tracking

### D. FINANCIAL TABLES

#### InvoiceHeader & InvoiceLine
**Purpose**: Invoice generation and tax compliance
**Key Features**:
- Links to booking, service event, client
- Prepayment batch support
- Tax submission integration
- Multi-currency support

**Mapping to Odoo**:
- **Base Model**: `account.move` (standard Odoo invoicing)
- **Extension**: `health_invoicing` module for healthcare-specific fields

#### Payment & PrepaymentBatch
**Purpose**: Payment tracking and prepaid service management
**Key Features**:
- Multiple payment methods
- Evidence URI (photos, receipts)
- Cash in transit tracking
- Prepaid service consumption tracking

**Mapping to Odoo**:
- **Base Model**: `account.payment` (standard Odoo)
- **Extension**: Add healthcare-specific tracking fields

### E. INTEGRATION & COMPLIANCE TABLES

#### Address & Address Input Template
**Purpose**: Vietnamese address structure
**Template Fields**:
- `Named Area` (Khu vực đặt tên)
- `Apartment Number` (Số căn hộ)
- `Building Name` (Tên tòa nhà)
- `House Number` (Số nhà)
- `Sub-Alley Number` (Số ngách)
- `Alley Number` (Số ngõ)
- `Street Name` (Tên đường)
- `Ward/Commune` (Phường/Xã)
- `City/Province` (Thành phố/Tỉnh)

**Mapping to Odoo**:
- **Enhancement**: Extend `res.partner` address fields for Vietnamese structure

#### Province Table
**Purpose**: Geographic filtering and permissions
**Fields**: `province_code`, `province_name`, `is_active`

**Mapping to Odoo**:
- **Model**: `res.country.state` (standard Odoo states/provinces)

---

## 3. WORKFLOW MAPPING TO EXISTING MODULES

### Current Odoo Health Modules:
1. **health_base**: Core models (patient, facility, service types)
2. **health_calendar**: Appointment booking
3. **health_fieldservice**: Staff assignment and service delivery

### Required Module Enhancements:

#### A. health_base Extensions
```python
# res.partner (contact) extensions
- channel_type: Contact channel tracking
- campaign_source: Lead source
- vietnamese_address_fields: Structured address
- relationship_ids: One2many to related parties

# health.patient extensions  
- cccd_number: Vietnamese ID
- ethnicity: Dân tộc
- kinship_title: Vietnamese honorifics
- preferred_name: Preferred calling name
- caregiver_ids: One2many to caregivers
- payer_ids: One2many to payers
- referrer_ids: One2many to referrers
```

#### B. health_calendar Extensions
```python
# health.appointment extensions
- contact_id: Link to original contact
- booking_status_history_ids: Status audit trail
- workflow fields: submitted_by/at, handed_off_by/at
- clinical_template_saved: MOH compliance flag
```

#### C. health_fieldservice Extensions
```python
# health.assignment extensions
- notification_log_ids: Staff notification tracking
- service_event_ids: Actual delivery tracking
- invoice_draft_saved: Invoice preparation flag
```

#### D. New Modules Required
```python
# health_crm (new)
- CRM pipeline integration
- Lead source tracking
- Follow-up management

# health_invoicing (new)
- Healthcare-specific invoicing
- Prepayment batch management
- Tax authority integration (MISA)
- MOH compliance records

# health_compliance (new)
- Ministry of Health submissions
- Clinical record formatting (JSON/XML)
- Prescription submissions
- Regulatory audit trails
```

---

## 4. CRITICAL INTEGRATION REQUIREMENTS

### A. Lead Source Tracking (Facebook, Zalo, Website, Calls, Referrals)
**Implementation**: 
- Extend `utm.source`, `utm.campaign` in Odoo CRM
- Custom fields for Vietnamese channels (Zalo integration)

### B. Real-time Tax Authority Submission
**Implementation**:
- API integration with Vietnamese Tax Authorities
- Real-time invoice submission workflow
- Compliance validation before submission

### C. Ministry of Health (MOH) Submissions
**Implementation**:
- Clinical record API (JSON/XML format)
- Prescription submission system
- Patient data privacy compliance

### D. Mobile-First Design
**Implementation**:
- Progressive Web Application (PWA)
- Offline functionality for field staff
- Real-time data synchronization

### E. Multilingual Support (Vietnamese & English)
**Implementation**:
- Translation infrastructure
- Vietnamese-specific UI elements
- Cultural adaptation (kinship terms, address formats)

---

## 5. DEVELOPMENT PRIORITY RECOMMENDATIONS

### Phase 1: Core Foundation (Weeks 1-2)
1. Enhance health_base with Vietnamese-specific fields
2. Extend health_calendar for workflow tracking
3. Create basic health_crm module

### Phase 2: Service Delivery (Weeks 3-4)
1. Enhance health_fieldservice with notification tracking
2. Implement ServiceEvent model
3. Create booking status history

### Phase 3: Financial Integration (Weeks 5-6)
1. Create health_invoicing module
2. Implement prepayment batch system
3. Basic tax authority integration

### Phase 4: Compliance & Mobile (Weeks 7-8)
1. MOH integration development
2. Mobile PWA optimization
3. Real-time synchronization testing

This analysis provides a comprehensive mapping of the Excel requirements to our existing Odoo health module architecture, identifying specific enhancements needed while maintaining the inheritance-based design pattern established in the project guidelines.