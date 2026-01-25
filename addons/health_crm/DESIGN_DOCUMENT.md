# Health CRM Redesign - Design Document
## Contact-First Flow Enhancement

**Document Version:** 1.2  
**Date:** 2026-01-25  
**Status:** ✅ FULLY IMPLEMENTED  

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Data Model Updates | ✅ Complete |
| Phase 2 | Initial Contact Popup | ✅ Complete |
| Phase 3 | Contact Details Form Redesign | ✅ Complete |
| Phase 4 | Follow-up Activities Window | ✅ Complete |
| Phase 5 | Dashboard Integration | ✅ Complete |
| Phase 6 | Menu Updates | ✅ Complete |
| Phase 7 | Business Rules | ✅ Complete |

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [New Data Flow Design](#new-data-flow-design)
4. [New Entity Model](#new-entity-model)
5. [UI/UX Changes](#uiux-changes)
6. [Menu Structure Changes](#menu-structure-changes)
7. [Field Changes](#field-changes)
8. [Logic/Business Rules](#logicbusiness-rules)
9. [Implementation Phases](#implementation-phases)
10. [Risk Mitigation](#risk-mitigation)

---

## 1. Executive Summary

### Client Requirements Summary:
The client wants to shift from a **Lead-First** flow to a **Contact-First** flow where:
- Every incoming call/inquiry is first logged as a **Contact**
- A Contact can then become:
  - **→ Booking** (direct conversion)
  - **→ Lead** (for follow-up) → **Booking** or **Booking Lost**
  - **→ Lost Contact** (junk/spam)

### Key Terminology Changes:
| Old Term | New Term |
|----------|----------|
| CRM | Sales & CRM ✅ (Already Done) |
| Lead (initial) | Contact |
| Opportunity | Lead |
| Primary Facility | Province |
| N/A | Contact Status |

---

## 2. Current State Analysis

### 2.1 Current Models

#### `crm.lead` (health_crm/models/crm_lead.py)
- Currently inherits from Odoo's standard `crm.lead`
- Uses `type` field: 'lead' or 'opportunity' (standard Odoo)
- Has healthcare-specific fields: `service_interest`, `clinical_priority`, `contact_relationship_type`, etc.
- Fields already exist: `contact_datetime`, `contact_outcome`, `contact_type` (new/repeat)
- Has unique `unique_contact_code` generated per city

#### `res.partner` (health_crm/models/res_partner.py)
- Extended for healthcare with `is_patient`, `is_representative`, role flags
- Has `patient_code` for client identification
- Contains relationship management via `health.client.relation`

#### `health.fieldservice.order` (health_fieldservice/models/health_fieldservice_order.py)
- The Booking model - handles appointments, scheduling, staff assignment
- Links to `patient_id` (res.partner), `crm_lead_id`

### 2.2 Current Flow
```
Lead/Opportunity (crm.lead) → Convert to Booking → FSO Order
                           → Convert to Client → res.partner
                           → Booking Lost
```

### 2.3 Current Dashboard (Health Flow)
- **Sales & CRM Panel** (6 tiles): Search, Add Lead, Planned Activities, Calendar, All Leads, Initial Contact, Continue Follow-up, Client Acquired, Booking Lost
- **Booking Panel**: Search, Booking Calendar, All Bookings, Staff Workload, Staff Assignment, Draft, Assigned, Scheduled, In Progress, Completed

---

## 3. New Data Flow Design

### 3.1 New Contact-First Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONTACT ENTRY POINT                            │
│                        (Every call/inquiry starts here)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  INITIAL CONTACT POPUP (Quick Entry)                                       │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Fields: Name, Contact ID (auto), New/Repeat flag, Province,               │
│          Phone, Email, Mode of Contact (Phone/Zalo/Email/Chatbox)          │
│  ─────────────────────────────────────────────────────────────────────────  │
│  System Actions:                                                            │
│  • Check if existing contact (by phone/email/name)                         │
│  • Auto-assign Contact ID if new                                           │
│  • Flag as New or Repeat contact                                           │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Buttons: [NEXT] → Contact Details Form                                    │
│           [HOME] → Mark as Junk/Spam + Return to Dashboard                 │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                                   │
                    │ [NEXT]                            │ [HOME]
                    ▼                                   ▼
┌───────────────────────────────────┐    ┌───────────────────────────────────┐
│  CONTACT DETAILS FORM             │    │  JUNK/SPAM RECORD                 │
│  (Expanded view with actions)     │    │  Contact Status = 'spam'          │
│                                   │    │  Return to Home Page              │
│  Display:                         │    └───────────────────────────────────┘
│  • Initial contact details        │
│  • Address, Tags                  │
│                                   │
│  Collect:                         │
│  • Reason for Contact             │
│  • On behalf of (Self/Other)      │
│  • Client name if on behalf       │
│                                   │
│  Top Menu Bar:                    │
│  ─────────────────────────────────│
│  Home | Booking | Assign | Cancel │
│  Reschedule | Telemedicine |      │
│  Consultation | Escalate |        │
│  Send Message | Log Lead |        │
│  Log Activity | Log Note          │
└───────────────────────────────────┘
            │
            ├─[Home]────────────→ Auto-mark as Junk (no lead logged) → Dashboard
            │
            ├─[Booking]─────────→ BOOKING SUB-WINDOW
            │                    ├─ Client Details
            │                    ├─ Service Requirements (+ Commission fields)
            │                    ├─ Booking Details (Calendar)
            │                    └─ Assign Booking (+ Service Fee VND)
            │
            ├─[Log Lead]────────→ Create Lead record in calendar
            │
            ├─[Log Activity]────→ Schedule activity in calendar
            │
            ├─[Cancellation]────→ Cancellation Form
            │                    ├─ Date/Time stamp
            │                    ├─ Reason for cancellation
            │                    ├─ Who cancelled (client side)
            │                    ├─ Who reported (name/position)
            │                    └─ Last person who visited (if repeat client)
            │
            ├─[Telemedicine]────→ Refer to Duty Doctor (with details)
            │
            ├─[Consultation]────→ Transfer to Duty Doctor/Head Nurse/OM
            │
            └─[Escalate]────────→ Transfer to Head Nurse/OM
```

### 3.2 Follow-up Activities Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FOLLOW-UP ACTIVITIES WINDOW                                                │
│  (Accessed from Home Page or Contact Details)                               │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Top Bar: Search box to select client/contact                               │
│  ─────────────────────────────────────────────────────────────────────────  │
│  Menu Items:                                                                │
│  a. Log as Lead (in calendar)                                              │
│  b. Log Planned Activity (in calendar)                                     │
│  c. Show All Current Leads (sorted by planned follow-up date)              │
│     → Selection shows Lead Follow-up Form                                  │
│       → If follow-up results in booking → New Booking Form                 │
│       → If follow-up results in no booking → Booking Lost Form             │
│  d. Show All Planned Activities (sorted by date)                           │
│     → Selection shows Activity Follow-up Form                              │
│  e. Show Calendar (all leads & activities)                                 │
│     → Selection → Lead or Activity follow-up form                          │
│  f. Recent Client Follow-up (recent clients with selected service)         │
│     → Log lead in calendar or follow-up now → Booking or Rejection         │
│  g. Visit Satisfaction Follow-up (PLACEHOLDER)                             │
│     → Recent clients without follow-up phone calls                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. New Entity Model

### 4.1 Contact Status Field (NEW)

Add to `crm.lead`:

```python
contact_status = fields.Selection([
    ('active', 'Active'),           # In progress, awaiting action
    ('booking', 'Booking'),         # Converted to booking
    ('lead', 'Lead'),               # Converted to lead for follow-up
    ('lost_booking', 'Lost Booking'), # Follow-up resulted in no booking
    ('spam', 'Spam Call'),          # Junk/false contact
], string='Contact Status', default='active', 
   help='Status of this contact in the sales pipeline')
```

### 4.2 Contact ID Lifecycle

**Key Rule:** Contact ID stays the same even if they contact again.

```
Contact ID Logic:
─────────────────
1. On initial contact popup → Check for existing contact by:
   - Phone number (exact match)
   - Email (exact match)
   - Name + Phone combination

2. If EXISTING contact found:
   - Reuse the Contact ID
   - Flag as 'repeat' contact
   - Link to existing res.partner if available

3. If NEW contact:
   - Generate new Contact ID (format: PROVINCE-NNNN)
   - Flag as 'new' contact

4. Contact ID → Client ID Transfer:
   - When contact converts to Client (is_patient=True), 
   - Contact ID becomes the Client ID (patient_code)
   - If contact never becomes client, generate new patient_code when needed
```

### 4.3 Province-Based Organization (Rename)

**Change:** "Primary Facility" → "Province"

```python
# In health.fieldservice.order and crm.lead
# Rename field labels in views:
# - primary_facility_id → province_id (or keep field, change label)

# Province will contain Service Facilities within it
# Staff → Assigned to Province + Service Facility
```

---

## 5. UI/UX Changes

### 5.1 Dashboard Changes (health_flow_action.js + template)

#### Current "Sales & CRM" Panel Items:
```javascript
crm: {
    title: 'Sales & CRM',  // ✅ Already done
    items: [
        { key: 'crm-search', label: 'Search', ... },
        { key: 'crm-add-lead', label: 'Add Lead', ... },
        { key: 'crm-activities', label: 'Planned Activities', ... },
        { key: 'crm-calendar', label: 'Calendar', ... },
        { key: 'crm-all', label: 'All Leads', ... },
        { key: 'crm-initial', label: 'Initial Contact', ... },
        { key: 'crm-continue-followup', label: 'Continue Follow-up', ... },
        { key: 'crm-client-acquired', label: 'Client Acquired', ... },
        { key: 'crm-booking-lost', label: 'Booking Lost', ... },
    ],
}
```

#### NEW "Sales & CRM" Panel Items:
```javascript
crm: {
    title: 'Sales & CRM',
    items: [
        // Only TWO main options now:
        { key: 'crm-contacts', label: 'Contacts', icon: 'fa-phone', 
          desc: 'Log new contact / View contacts', hasCount: true },
        { key: 'crm-followup', label: 'Follow-up Activities', icon: 'fa-calendar-check-o', 
          desc: 'Manage leads and activities', hasCount: true },
    ],
}
```

### 5.2 New Initial Contact Popup

When user clicks "Contacts" from dashboard:

```
┌─────────────────────────────────────────────────────────────────┐
│  NEW CONTACT                                       [×]          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Contact Date: [____________________] (auto-filled)             │
│                                                                 │
│  [Search existing contact ▼]  OR  [+ Create New]                │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  Name: [____________________________] *                         │
│  Contact ID: [AUTO-GENERATED]  New/Repeat: [NEW ▼]             │
│                                                                 │
│  Province: [____________________________] *                     │
│                                                                 │
│  Phone: [____________________________]                          │
│  Email: [____________________________]                          │
│                                                                 │
│  Mode of Contact:                                               │
│  ○ Phone  ○ Zalo  ○ Facebook  ○ Email  ○ Website  ○ Chatbox    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│        [← HOME (Mark as Junk)]        [NEXT →]                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Contact Details Form (Expanded)

After clicking NEXT, open full Contact Details form with TOP MENU BAR:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [Home] [Booking ▼] [Cancellation] [Reschedule] [Telemedicine]              │
│ [Consultation ▼] [Escalate ▼] [Send Message] [Log Lead] [Log Activity]    │
│ [Log Note]                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CONTACT: Nguyen Van A                                    [HCM-0001]       │
│  ═══════════════════════════════════════════════════════════════════════   │
│                                                                             │
│  ┌─ Initial Contact Details ─────────────────────────────────────────────┐ │
│  │ Name: Nguyen Van A          │ Contact Date: 2026-01-25 10:30          │ │
│  │ Phone: 0909 123 456         │ Mode: Phone                             │ │
│  │ Email: nguyen@email.com     │ New/Repeat: New                         │ │
│  │ Province: Ho Chi Minh City  │                                         │ │
│  │ Address: [________________] │ Tags: [________________]                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌─ Contact Details ─────────────────────────────────────────────────────┐ │
│  │ Reason for Contact: [________________________]                        │ │
│  │ Contacting on behalf of: ○ Self  ○ Another Person                    │ │
│  │ Client Name: [________________________] (if on behalf)               │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Contact Status: [ACTIVE ▼]                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Booking Sub-Window Menu Items

When "Booking" is clicked from Contact Details:

```
BOOKING SUB-WINDOW
├── Client Details (auto-filled if Self; enter if representative)
│     - Add (enter services) or Back controls
│
├── Service Requirements
│     - Service and sub-categories
│     - Commission fields: Commission Due To, % Commission, Commission Duration
│     - Back controls
│
├── Booking Details
│     - Date/time selection on calendar
│     - Add Assign Booking or Back controls
│
└── Assign Booking
      - Staff assignment (optional at this stage)
      - Service Fee in VND (negotiated casual provider fee)
      - Finished → Back to booking page
```

### 5.5 Cancellation Form Fields

```
CANCELLATION FORM
├── Date/Time stamp (auto)
├── Reason for cancellation
├── Who cancelled (on client side)
├── Who reported cancellation (name/position)
└── If repeat client: Last person who visited this client
```

---

## 6. Menu Structure Changes

### 6.1 Current Menu (health_crm_menus.xml):
```
Sales & CRM
├── Leads
├── CRM Contacts
├── Customers  
├── Healthcare Relationships
├── Reporting
└── Configuration
```

### 6.2 NEW Menu Structure:
```
Sales & CRM
├── Contacts              → Opens Initial Contact popup
├── Follow-up Activities  → Opens Follow-up Activities window
├── Customers
├── Healthcare Relationships
├── Reporting
└── Configuration
```

### 6.3 Booking Menu Rename:
```
Bookings and Assignments (renamed from "Booking")
```

---

## 7. Field Changes

### 7.1 New Fields to Add

#### In `crm.lead`:

```python
# Contact Status (replaces/extends contact_outcome)
contact_status = fields.Selection([
    ('active', 'Active'),
    ('booking', 'Booking'),
    ('lead', 'Lead'),
    ('lost_booking', 'Lost Booking'),
    ('spam', 'Spam Call'),
], string='Contact Status', default='active')

# On behalf tracking
contacting_on_behalf = fields.Selection([
    ('self', 'Self'),
    ('other', 'Another Person'),
], string='Contacting On Behalf Of', default='self')

# For escalation/transfer
escalated_to = fields.Selection([
    ('head_nurse', 'Head Nurse'),
    ('om', 'Operations Manager'),
    ('duty_doctor', 'Duty Doctor'),
], string='Escalated To')

escalation_datetime = fields.Datetime('Escalation Date/Time')
escalation_notes = fields.Text('Escalation Notes')

# Mode of contact (extend existing vietnamese_channel)
# Already exists as vietnamese_channel - may need to add 'chatbox'
```

#### In `health.fieldservice.order`:

```python
# Service fee for casual providers
service_fee_vnd = fields.Float(
    'Service Fee (VND)',
    help='Negotiated fee for casual healthcare provider'
)

# Commission fields
commission_due_to = fields.Many2one(
    'res.partner', 
    string='Commission Due To',
    help='Person/entity who receives commission'
)
commission_percentage = fields.Float('Commission %')
commission_duration = fields.Char('Commission Duration')

# Cancellation fields
cancellation_datetime = fields.Datetime('Cancellation Date/Time')
cancellation_reason = fields.Text('Cancellation Reason')
cancelled_by = fields.Char('Cancelled By (Client Side)')
cancellation_reported_by = fields.Char('Reported By')
cancellation_reporter_position = fields.Char('Reporter Position')
last_visiting_staff_id = fields.Many2one(
    'hr.employee',
    string='Last Person Who Visited',
    help='For repeat clients - who last visited'
)
```

### 7.2 Field Label Changes

| Model | Field | Old Label | New Label |
|-------|-------|-----------|-----------|
| crm.lead | primary_facility_id / facility_id | Primary Facility / Healthcare Facility | Province |
| health.fieldservice.order | primary_facility_id | Primary Facility | Province |
| Various | - | - | Add Service Facility under Province |

### 7.3 Fields to Make Mandatory

Based on client requirements, update `required` attribute for:
- Contact: Name, Province, Phone or Email (at least one)
- Booking: Client Details completion check
- Cancellation: Reason, Who Cancelled

---

## 8. Logic/Business Rules

### 8.1 Duplicate Contact Detection

```python
def _check_existing_contact(self, name, phone, email):
    """
    Check for existing contacts by phone, email, or name+phone combination.
    Returns: existing contact record or False
    """
    domain = ['|', '|']
    conditions = []
    
    if phone:
        conditions.append(('phone', '=', phone))
    if email:
        conditions.append(('email_from', '=', email))
    if name and phone:
        conditions.append('&', ('name', '=ilike', name), ('phone', '=', phone))
    
    # Search in both crm.lead and res.partner
    existing_lead = self.env['crm.lead'].search(
        conditions, limit=1, order='create_date desc'
    )
    existing_partner = self.env['res.partner'].search([
        '|', ('phone', '=', phone), ('email', '=', email)
    ], limit=1)
    
    return existing_lead or existing_partner
```

### 8.2 Contact ID to Client ID Transfer

```python
def _transfer_contact_id_to_client(self):
    """
    When a contact becomes a client (is_patient=True),
    transfer the Contact ID to become the Client ID (patient_code).
    """
    self.ensure_one()
    if self.patient_id and self.unique_contact_code:
        if not self.patient_id.patient_code:
            self.patient_id.write({
                'patient_code': self.unique_contact_code
            })
```

### 8.3 Spam Caller Tagging

```python
def _mark_as_spam(self):
    """
    Tag the caller as spam. Can be reversed if future contact 
    results in booking, lead, or lost booking.
    """
    self.ensure_one()
    self.write({
        'contact_status': 'spam',
        'contact_outcome': 'not_qualified',
    })
    # Also tag the phone number in a spam list for future detection
```

### 8.4 Invoice Notification for Nurses/Doctors

```python
def _check_invoice_authorization(self):
    """
    Nurses/Doctors cannot raise invoices.
    Send notification to OM when booking made by Nurse/Doctor.
    """
    self.ensure_one()
    user = self.env.user
    
    # Check if user is Nurse or Doctor (by group or employee type)
    is_nurse_or_doctor = user.has_group('health_fieldservice.group_healthcare_staff')
    
    if is_nurse_or_doctor:
        # Create notification for OM
        self._notify_om_invoice_required()
        return False
    return True
```

### 8.5 Province → Service Facility Hierarchy

```python
# Province contains Service Facilities
# Staff assigned to Province + Service Facility combination

# Update hr.employee to have:
# - province_id (Many2one to health.province or res.country.state)
# - service_facility_id (Many2one to health.facility, domain filtered by province)
```

---

## 9. Implementation Phases

### Phase 1: Data Model Updates (Low Risk)
1. Add `contact_status` field to crm.lead
2. Add `contacting_on_behalf`, escalation fields
3. Add commission fields to health.fieldservice.order
4. Add cancellation fields to health.fieldservice.order
5. Rename field labels (Primary Facility → Province)

### Phase 2: Initial Contact Popup (Medium Risk)
1. Create new wizard model `health.contact.initial.wizard`
2. Create popup form view
3. Implement duplicate detection logic
4. Wire up to dashboard "Contacts" button

### Phase 3: Contact Details Form Redesign (Medium Risk)
1. Add top menu bar with action buttons
2. Implement each action:
   - Home (mark as junk)
   - Booking sub-window
   - Log Lead
   - Log Activity
   - Cancellation form
   - Telemedicine/Consultation/Escalate transfers
   - Send Message
   - Log Note

### Phase 4: Follow-up Activities Window (Medium Risk)
1. Create new client action for Follow-up Activities
2. Implement sub-menu items:
   - Log as Lead
   - Log Planned Activity
   - Show All Leads (with sorting)
   - Show All Activities
   - Show Calendar
   - Recent Client Follow-up
   - Visit Satisfaction (placeholder)

### Phase 5: Dashboard Integration (Low Risk)
1. Update health_flow_action.js panel items
2. Update health_flow_templates.xml
3. Test all flows from dashboard

### Phase 6: Menu Updates (Low Risk)
1. Update health_crm_menus.xml
2. Rename Booking menu to "Bookings and Assignments"

### Phase 7: Business Rules (Medium Risk)
1. Implement Contact ID lifecycle
2. Implement spam tagging/untagging
3. Implement invoice authorization check
4. Add province/facility hierarchy

---

## 10. Testing Strategy

Since this application is **not yet in production**, we can implement changes directly without migration concerns.

### 10.1 Testing Approach

1. **Manual Testing:** Test each flow from dashboard
2. **Integration Tests:** Full flow from Contact → Booking
3. **UAT:** Client validation of new UI

### 10.2 Key Test Scenarios

| Scenario | Expected Outcome |
|----------|------------------|
| New Contact → NEXT → Booking | FSO created, Contact Status = 'booking' |
| New Contact → HOME | Contact Status = 'spam', return to dashboard |
| Existing Contact detected | Reuse Contact ID, flag as 'repeat' |
| Contact → Log Lead | Lead created in calendar |
| Lead → Follow-up → Booking | FSO created from lead |
| Lead → Follow-up → No Booking | Contact Status = 'lost_booking' |
| Nurse books service | OM notified for invoice |

---

## Appendix A: File Change Summary

| File | Type of Change |
|------|----------------|
| `health_crm/models/crm_lead.py` | Add fields, methods |
| `health_fieldservice/models/health_fieldservice_order.py` | Add commission/cancellation fields |
| `health_flow/static/src/js/health_flow_action.js` | Update panel items |
| `health_flow/static/src/xml/health_flow_templates.xml` | Update panel display |
| `health_crm/views/crm_lead_views.xml` | Add top menu bar, redesign form |
| `health_crm/views/health_crm_menus.xml` | Update menu items |
| `health_crm/wizard/` (NEW) | Initial contact wizard |
| `health_crm/wizard/` (NEW) | Follow-up activities wizard |
| `health_crm/wizard/` (NEW) | Cancellation wizard |

---

## Appendix B: Visual Flow Diagram

```
                    ┌─────────────────┐
                    │  DASHBOARD      │
                    │  Sales & CRM    │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │   CONTACTS      │           │ FOLLOW-UP       │
    │   (Popup)       │           │ ACTIVITIES      │
    └────────┬────────┘           └────────┬────────┘
             │                             │
      ┌──────┴──────┐                ┌─────┴─────┐
      ▼             ▼                ▼           ▼
   [HOME]       [NEXT]           [All Leads]  [Calendar]
   (Spam)          │                 │
                   ▼                 ▼
           ┌──────────────┐    ┌──────────────┐
           │  CONTACT     │    │  LEAD        │
           │  DETAILS     │    │  FOLLOW-UP   │
           └──────┬───────┘    └──────┬───────┘
                  │                   │
    ┌─────────────┼─────────────┐     │
    ▼             ▼             ▼     ▼
 [Booking]   [Log Lead]   [Cancel]  [Booking] or [Lost]
    │             │           │
    ▼             ▼           ▼
  FSO         Lead in      Cancellation
 Create       Calendar       Record
```

---

**END OF DESIGN DOCUMENT**

*Awaiting approval before implementation begins.*
