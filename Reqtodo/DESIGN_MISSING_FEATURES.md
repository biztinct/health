# Implementation Design for Missing Requirements

**Project:** HHHPL x IADC Healthcare CRM System
**Document:** Gap Analysis & Design Specifications
**Date:** October 5, 2025
**Purpose:** Identify unimplemented requirements from reqfinal.md and design solutions

---

## Executive Summary

This document analyzes the requirements in `reqfinal.md` against the existing codebase to identify gaps and design implementation solutions. All implementations will **modify existing modules only** - no new modules will be created.

**Existing Modules to Extend:**
- `health_base` - Core healthcare models and lookups
- `health_crm` - CRM and lead management
- `health_fieldservice` - Booking, scheduling, field service orders
- `health_invoicing` - Invoicing, packages, MISA integration
- `health_pwa` - Mobile nurse app
- `advanced_pricing` - Pricing rules engine

---

## 1. CRM & Lead Management

### 1.1 Phone Number Search Filter ✅ IMPLEMENTED
**Requirement:** "Contact workflow: check if phone number is known - Ensure Odoo search/filter has filter created for phone number as search"

**Current Status:** ✅ Already implemented - Phone/Mobile search filter visible in CRM lead search dropdown

**No changes needed.**

---

### 1.2 Contact Tagging System ✅ IMPLEMENTED. (Ash to verify)
**Requirement:** "Contact tagging: new, booked, junk, lead to follow up"

**Current Status:** ✅ Already implemented using CRM stages (Continue Follow-up, Qualified, Booked, Won, Booking Lost)

**No changes needed** - Existing stage system covers the required tagging functionality.

---

### 1.3 Referral Platform Integration ❌ MISSING. (Ash to be done later)
**Requirement:** "Integration with referral platforms: BookingCare, Doc, Die"

**Current Status:** NOT IMPLEMENTED

**Design:**
- **Module:** `health_crm`
- **New Model:** `health.referral.platform` (lookup table)
```python
class HealthReferralPlatform(models.Model):
    _name = 'health.referral.platform'
    _description = 'Referral Platform Integration'

    name = fields.Char('Platform Name', required=True)  # BookingCare, Doc, Die
    platform_type = fields.Selection([
        ('booking_platform', 'Booking Platform'),
        ('insurance_partner', 'Insurance Partner'),
        ('individual', 'Individual Referral'),
    ])
    api_endpoint = fields.Char('API Endpoint')
    api_key = fields.Char('API Key')
    active = fields.Boolean(default=True)
```

- **Extend crm.lead:**
```python
referral_platform_id = fields.Many2one('health.referral.platform', string='Referral Platform')
referral_code = fields.Char('Referral Code', help='Tracking code from platform')
```

**Integration:** Webhook controllers to receive bookings from platforms

**Priority:** P1 (Can be manual entry initially, API later)

---

## 2. Client/Patient Management

### 2.1 Client ID Auto-generation with City Codes ✅ IMPLEMENTED
**Status:** Already exists in res.partner with patient_code field

---

### 2.2 Related Persons Bidirectional Dashboard ⚠️ PARTIAL
**Requirement:** "Dashboard showing linked clients ↔ related persons"

**Current Status:** Related persons exist but no dashboard visualization

**Design:**
- **Module:** `health_base`
- **Add Computed Fields:**
```python
# res.partner (patient)
related_person_count = fields.Integer(compute='_compute_related_person_count')
caregiver_ids = fields.One2many('health.client.relation', 'patient_id',
                                 domain=[('relationship_type', 'in', ['caregiver', 'family_member'])])
payer_ids = fields.One2many('health.client.relation', 'patient_id',
                            domain=[('relationship_type', '=', 'payer')])
```

**Views:**
- Add smart buttons on patient form showing counts
- Kanban view for related persons with relationship badges
- Graph view showing relationship network

**Priority:** P1

---

### 2.3 Address Template Concatenation ❌ MISSING
**Requirement:** Address fields must be concatenated into single field per Vietnamese format

**Current Status:** Odoo has standard address fields

**Design:**
- **Module:** `health_crm/models/res_partner.py`
- **Add Fields:**
```python
province_code = fields.Char('Province Code')
named_area = fields.Char('Named Area')
apartment_number = fields.Char('Apartment Number')
building_name = fields.Char('Building Name')
house_number = fields.Char('House Number')
sub_alley_number = fields.Char('Sub-Alley Number (Ngách)')
alley_number = fields.Char('Alley Number (Ngõ)')
# street_id already exists in Odoo
ward_commune = fields.Char('Ward/Commune')
postal_code = fields.Char('Postal Code')

# Computed concatenated address
vietnamese_address = fields.Text('Vietnamese Address', compute='_compute_vietnamese_address', store=True)

@api.depends('province_code', 'named_area', 'apartment_number', ... 'postal_code')
def _compute_vietnamese_address(self):
    for rec in self:
        parts = [
            rec.apartment_number,
            rec.building_name,
            rec.house_number,
            rec.sub_alley_number,
            rec.alley_number,
            rec.street_id.name if rec.street_id else '',
            rec.ward_commune,
            rec.city,
            rec.state_id.name if rec.state_id else '',
            rec.postal_code,
            rec.country_id.name if rec.country_id else ''
        ]
        rec.vietnamese_address = ', '.join([p for p in parts if p])
```

**Views:** Replace standard address fields with Vietnamese template in patient form

**Priority:** P0 (Critical for GPS and invoicing)

---

## 3. Booking & Scheduling

### 3.1 Cancellation Management ⚠️ PARTIAL
**Requirement:** "Pop-up to capture cancellation details (who, why, when), Cancellation reason lookup table, Mandatory cancellation notes"

**Current Status:** FSO has cancelled state but no structured cancellation data

**Design:**
- **Module:** `health_base/models/health_lookup.py`
- **New Model:**
```python
class BookingCancellationReason(models.Model):
    _name = 'health.booking.cancellation.reason'
    _description = 'Booking Cancellation Reason'
    _order = 'sequence, name'

    name = fields.Char('Reason', required=True, translate=True)
    reason_type = fields.Selection([
        ('patient', 'Patient-initiated'),
        ('provider', 'Provider-initiated'),
        ('system', 'System/Technical'),
        ('emergency', 'Emergency/Force Majeure'),
    ], required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
```

- **Extend health.fieldservice.order:**
```python
cancellation_reason_id = fields.Many2one('health.booking.cancellation.reason', string='Cancellation Reason')
cancelled_by = fields.Many2one('res.users', string='Cancelled By')
cancellation_date = fields.Datetime('Cancellation Date')
cancellation_notes = fields.Text('Cancellation Notes', required_if_cancelled=True)

def action_cancel(self):
    """Override to show cancellation wizard"""
    return {
        'type': 'ir.actions.act_window',
        'name': 'Cancel Booking',
        'res_model': 'health.booking.cancel.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': {'default_booking_id': self.id}
    }
```

- **Wizard:** `health.booking.cancel.wizard` for pop-up capture

**Priority:** P0 (Required for operations workflow)

---

### 3.2 Multiple Staff Assignment ✅ IMPLEMENTED
**Status:** Already supported in health_staff_assignment model

---

## 4. Staff Management & Assignment

### 4.1 Zalo Integration Notifications ❌ MISSING
**Requirement:** "Zalo integration for staff assignment notifications, Nurse acknowledgment in Zalo updates CRM status"

**Current Status:** NOT IMPLEMENTED

**Design:**
- **Module:** `health_fieldservice`
- **New Model:** `health.zalo.config`
```python
class ZaloIntegration(models.Model):
    _name = 'health.zalo.config'
    _description = 'Zalo Integration Configuration'

    name = fields.Char('Config Name', default='Zalo Integration')
    zalo_oa_id = fields.Char('Zalo OA ID', required=True)
    zalo_api_key = fields.Char('Zalo API Key', required=True)
    zalo_secret_key = fields.Char('Zalo Secret Key', required=True)
    webhook_url = fields.Char('Webhook URL', compute='_compute_webhook_url')
    active = fields.Boolean(default=True)
```

- **Extend hr.employee:**
```python
zalo_user_id = fields.Char('Zalo User ID', help='Employee Zalo account ID')
zalo_phone = fields.Char('Zalo Phone Number')
```

- **Notification Logic:**
```python
def send_zalo_notification(self, employee, booking):
    """Send Zalo notification for job assignment"""
    zalo_config = self.env['health.zalo.config'].search([('active', '=', True)], limit=1)
    if not zalo_config or not employee.zalo_user_id:
        return False

    message = f"New Assignment: {booking.display_name}\nPatient: {booking.patient_id.name}\nTime: {booking.scheduled_datetime}"
    # Zalo API call here
    return True
```

**Integration:** Webhook controller to receive acknowledgments from Zalo

**Priority:** P1 (Can use manual SMS initially)

---

## 5. Invoicing System

### 5.1 Part-Time Nurse Workflow ❌ MISSING
**Requirement:** "Part-time/casual nurses do NOT create invoices, Operations handles invoicing on their behalf, Different workflow for casual vs full-time staff"

**Current Status:** No distinction between full-time and part-time nurses

**Design:**
- **Module:** `health_fieldservice/models/hr_employee.py`
- **Add Field:**
```python
employment_type = fields.Selection([
    ('full_time', 'Full-Time Staff'),
    ('part_time', 'Part-Time Staff'),
    ('casual', 'Casual/Contract'),
], string='Employment Type', default='full_time', required=True)

can_create_invoices = fields.Boolean('Can Create Invoices', compute='_compute_can_create_invoices', store=True)

@api.depends('employment_type')
def _compute_can_create_invoices(self):
    for emp in self:
        emp.can_create_invoices = emp.employment_type == 'full_time'
```

- **FSO Logic:**
```python
def _check_invoice_creation_permission(self):
    """Check if assigned staff can create invoice"""
    self.ensure_one()
    if not self.primary_staff_id:
        return False
    return self.primary_staff_id.can_create_invoices

def action_complete_job(self):
    """Complete job - different flow for part-time nurses"""
    if self._check_invoice_creation_permission():
        # Full-time: Open invoice wizard
        return self._open_invoice_wizard()
    else:
        # Part-time: Mark for operations invoicing
        self.write({
            'state': 'completed_pending_invoice',
            'completion_notes': 'Completed by part-time staff - requires Operations invoicing'
        })
        # Notify operations manager
        self._notify_operations_for_invoicing()
```

**Views:** Different buttons/workflows in mobile app based on employment type

**Priority:** P0 (Critical workflow requirement)

---

### 5.2 Job Timer & Mandatory Notes/Invoice ❌ MISSING
**Requirement:** "Start job button triggers timer, opens invoicing details; Job cannot be completed until both clinical notes and invoice submitted"

**Current Status:** FSO has start/end dates but no enforced timer or validation

**Design:**
- **Module:** `health_fieldservice/models/health_fieldservice_order.py`
- **Add Fields:**
```python
job_start_time = fields.Datetime('Job Start Time', readonly=True)
job_end_time = fields.Datetime('Job End Time', readonly=True)
job_duration_minutes = fields.Float('Job Duration (Minutes)', compute='_compute_job_duration', store=True)
timer_running = fields.Boolean('Timer Running', default=False)

clinical_notes_submitted = fields.Boolean('Clinical Notes Submitted', compute='_compute_clinical_notes_status')
invoice_submitted = fields.Boolean('Invoice Submitted', compute='_compute_invoice_status')

@api.depends('clinical_notes', 'clinical_note_attachment_ids')
def _compute_clinical_notes_status(self):
    for rec in self:
        rec.clinical_notes_submitted = bool(rec.clinical_notes or rec.clinical_note_attachment_ids)

@api.depends('invoice_ids', 'invoice_ids.state')
def _compute_invoice_status(self):
    for rec in self:
        rec.invoice_submitted = any(inv.state != 'draft' for inv in rec.invoice_ids)
```

- **Methods:**
```python
def action_start_job(self):
    """Start job timer"""
    self.ensure_one()
    if self.job_start_time:
        raise UserError("Job already started!")

    self.write({
        'job_start_time': fields.Datetime.now(),
        'timer_running': True,
        'state': 'in_progress'
    })
    return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
        'message': 'Job timer started',
        'type': 'success'
    }}

def action_complete_job(self):
    """Complete job - validate notes and invoice"""
    self.ensure_one()

    # Validation
    if not self.clinical_notes_submitted:
        raise UserError("Clinical notes are mandatory before completing the job!")

    if not self.invoice_submitted:
        raise UserError("Invoice must be created before completing the job!")

    self.write({
        'job_end_time': fields.Datetime.now(),
        'timer_running': False,
        'state': 'done'
    })
```

**Mobile App:** Timer UI, validation before completion allowed

**Priority:** P0 (Core workflow)

---

### 5.3 Payment Pop-up (Pay Now/Pay Later) ❌ MISSING
**Requirement:** "Pop-up for nurse to record payment status and payment mode"

**Current Status:** Payment recording exists but no enforced pop-up workflow

**Design:**
- **Module:** `health_pwa/controllers/api.py`
- **Mobile API Endpoint:**
```python
@route('/api/pwa/invoice/payment', type='json', auth='user', methods=['POST'])
def record_payment(self, invoice_id, payment_status, payment_method=None, **kwargs):
    """Record payment from mobile app with mandatory pop-up data"""
    invoice = request.env['account.move'].sudo().browse(invoice_id)

    if payment_status == 'pay_now':
        if not payment_method:
            return {'error': 'Payment method required for Pay Now'}
        # Record payment
        invoice.write({
            'payment_method_id': payment_method,
            'payment_state': 'paid',
            'payment_date': fields.Datetime.now()
        })
    elif payment_status == 'pay_later':
        invoice.write({
            'payment_state': 'not_paid',
            'payment_term_note': 'Payment deferred by nurse at service completion'
        })

    return {'success': True, 'invoice': invoice.read()[0]}
```

**Mobile UI:** Mandatory modal dialog before invoice finalization

**Priority:** P0

---

### 5.4 Discount with Mandatory Notes ⚠️ PARTIAL
**Requirement:** "Discounts shown separately, Nurses can apply discounts with mandatory notes"

**Current Status:** Invoice has discount but no mandatory note enforcement

**Design:**
- **Module:** `health_invoicing/models/account_move.py`
- **Add Constraint:**
```python
discount_reason = fields.Text('Discount Reason')

@api.constrains('invoice_line_ids', 'discount_reason')
def _check_discount_reason(self):
    for invoice in self:
        has_discount = any(line.discount > 0 for line in invoice.invoice_line_ids)
        if has_discount and not invoice.discount_reason:
            raise ValidationError("Discount reason is mandatory when applying discounts!")
```

**Views:** Add discount_reason field to invoice form, make visible when discount applied

**Priority:** P1

---

### 5.5 Package Expiry Extension ✅ IMPLEMENTED
**Status:** Already in health.service.package model with expiry_date field (can be manually updated)

---

## 6. Pricing Engine

### 6.1 Holiday Calendar & Pricing Rules ❌ MISSING
**Requirement:** "Public holiday lookup table, Holiday pricing rules (3x for TET), Holiday date logic for pricing calculation"

**Current Status:** advanced_pricing has rules but no holiday calendar

**Design:**
- **Module:** `health_base/models/health_lookup.py`
- **New Model:**
```python
class PublicHoliday(models.Model):
    _name = 'health.public.holiday'
    _description = 'Public Holiday Calendar'
    _order = 'date desc'

    name = fields.Char('Holiday Name', required=True, translate=True)
    date = fields.Date('Holiday Date', required=True, index=True)
    holiday_type = fields.Selection([
        ('national', 'National Holiday'),
        ('tet', 'TET Holiday'),
        ('regional', 'Regional Holiday'),
        ('observance', 'Observance'),
    ], required=True, default='national')
    price_multiplier = fields.Float('Price Multiplier', default=1.0, help='e.g., 3.0 for TET')
    province_id = fields.Many2one('res.country.state', string='Province', help='Leave blank for national')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('date_unique_per_province', 'unique(date, province_id)', 'Holiday already exists for this date and province!')
    ]
```

- **Extend advanced_pricing:**
```python
# advanced_pricing/models/pricing_rule.py
condition_holiday = fields.Boolean('Apply on Holidays')
holiday_type = fields.Selection([
    ('any', 'Any Holiday'),
    ('tet', 'TET Only'),
    ('national', 'National Holidays'),
], string='Holiday Type')

def _check_holiday_condition(self, date, province=None):
    """Check if date is a holiday"""
    if not self.condition_holiday:
        return True

    domain = [('date', '=', date), ('active', '=', True)]
    if province:
        domain += ['|', ('province_id', '=', False), ('province_id', '=', province.id)]
    if self.holiday_type and self.holiday_type != 'any':
        domain.append(('holiday_type', '=', self.holiday_type))

    return bool(self.env['health.public.holiday'].search(domain, limit=1))
```

**Data:** Seed Vietnamese holidays for 2025-2026

**Priority:** P0 (Required for pricing accuracy)

---

### 6.2 Audit Trail for Price Changes ⚠️ PARTIAL
**Requirement:** "Audit trail: user, date, changes, notes; Archive old configurations"

**Current Status:** Odoo has tracking=True but no dedicated audit log UI

**Design:**
- **Module:** `advanced_pricing`
- **Enhance existing with:**
```python
# Enable mail.tracking on pricing models
_inherit = ['mail.thread', 'mail.activity.mixin']

# All price fields
tracking=True

# Add approval workflow
approval_status = fields.Selection([
    ('draft', 'Draft'),
    ('pending', 'Pending Board Approval'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
], default='draft', tracking=True)

approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
approval_date = fields.Datetime('Approval Date', readonly=True)
approval_notes = fields.Text('Approval Notes')
```

**Views:** Add Chatter to price list forms, create approval workflow wizard

**Priority:** P1

---

## 7. Government Compliance & Integrations

### 7.1 MOH Electronic Submission ❌ MISSING
**Requirement:** "All client visit data reported to MOH, Electronic prescription submission, MOH field requirements"

**Current Status:** MISA integration exists, MOH stub only

**Design:**
- **Module:** `health_invoicing`
- **New Model:** `health.moh.submission`
```python
class MOHSubmission(models.Model):
    _name = 'health.moh.submission'
    _description = 'Ministry of Health Submission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc'

    name = fields.Char('Submission Reference', required=True, readonly=True, default='New')
    submission_date = fields.Datetime('Submission Date', readonly=True)
    fso_id = fields.Many2one('health.fieldservice.order', string='Service Order', required=True)
    patient_id = fields.Many2one('res.partner', related='fso_id.patient_id', store=True)

    # MOH Required Fields
    client_national_id = fields.Char('National ID', related='patient_id.vat')
    service_date = fields.Datetime('Service Date', related='fso_id.scheduled_datetime')
    diagnosis_code = fields.Char('Diagnosis Code (ICD-10)')
    prescription_data = fields.Text('Prescription JSON')
    clinical_notes = fields.Text('Clinical Notes', related='fso_id.clinical_notes')

    # Submission Status
    submission_status = fields.Selection([
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted'),
        ('acknowledged', 'Acknowledged by MOH'),
        ('rejected', 'Rejected'),
        ('error', 'Submission Error'),
    ], default='pending', tracking=True)

    moh_response = fields.Text('MOH Response')
    error_message = fields.Text('Error Message')

    def action_submit_to_moh(self):
        """Submit to MOH via API"""
        # API integration logic here
        pass
```

- **Auto-submission:** Triggered when FSO state = 'done'

**Priority:** P1 (Can be manual initially, then automated)

---

### 7.2 Viettel E-signature Integration ❌ MISSING
**Requirement:** "Digital signatures via Viettel for Red Invoices"

**Current Status:** NOT IMPLEMENTED

**Design:**
- **Module:** `health_invoicing`
- **New Model:** `viettel.esignature.config`
```python
class ViettelESignature(models.Model):
    _name = 'viettel.esignature.config'
    _description = 'Viettel E-Signature Configuration'

    name = fields.Char('Config Name', default='Viettel E-Signature')
    viettel_api_url = fields.Char('Viettel API URL', required=True)
    viettel_client_id = fields.Char('Client ID', required=True)
    viettel_client_secret = fields.Char('Client Secret', required=True)
    certificate_path = fields.Char('Certificate Path')
    active = fields.Boolean(default=True)
```

- **Extend account.move (VAT Invoice):**
```python
esignature_status = fields.Selection([
    ('not_signed', 'Not Signed'),
    ('signing', 'Signing in Progress'),
    ('signed', 'E-Signed'),
    ('failed', 'Signature Failed'),
], default='not_signed', string='E-Signature Status')

esignature_reference = fields.Char('E-Signature Reference')
esignature_date = fields.Datetime('E-Signature Date')

def action_sign_with_viettel(self):
    """Sign invoice with Viettel e-signature"""
    # Viettel API integration
    pass
```

**Priority:** P1 (Required for compliance but can use manual process temporarily)

---

## 8. API Integrations

### 8.1 Cloud Doctor Integration ❌ MISSING
**Requirement:** "Clinical reporting submission, Optional clinical note uploads"

**Current Status:** Stub only

**Design:**
- **Module:** `health_invoicing`
- **New Model:** `clouddoctor.integration`
- Similar pattern to MISA integration
- Webhook to sync clinical notes

**Priority:** P2 (Optional integration)

---

## 9. Mobile Application (health_pwa)

### 9.1 Biometric Login ❌ MISSING
**Requirement:** "Biometric login (fingerprint/Face ID), One-time authentication per device"

**Current Status:** Standard login only

**Design:**
- **Module:** `health_pwa`
- **Device Registration:**
```python
class PWADeviceRegistration(models.Model):
    _name = 'pwa.device.registration'
    _description = 'PWA Device Registration for Biometric Auth'

    user_id = fields.Many2one('res.users', required=True)
    device_id = fields.Char('Device ID', required=True, index=True)  # UUID from mobile
    device_name = fields.Char('Device Name')
    biometric_public_key = fields.Text('Biometric Public Key')  # For challenge-response
    registered_date = fields.Datetime('Registered Date', default=fields.Datetime.now)
    last_login = fields.Datetime('Last Login')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('device_unique', 'unique(device_id)', 'Device already registered!')
    ]
```

- **API Endpoints:**
```python
@route('/api/pwa/register_device', type='json', auth='user')
def register_device(self, device_id, device_name, public_key):
    """Register device for biometric auth"""
    # Store device registration

@route('/api/pwa/biometric_challenge', type='json', auth='none')
def biometric_challenge(self, device_id):
    """Get challenge for biometric authentication"""
    # Return challenge string

@route('/api/pwa/biometric_verify', type='json', auth='none')
def biometric_verify(self, device_id, signed_challenge):
    """Verify biometric signature and login"""
    # Verify signature, create session
```

**Mobile App:** Use WebAuthn API for fingerprint/Face ID

**Priority:** P2 (Security enhancement, not blocking)

---

### 9.2 GPS Location Tracking ⚠️ PARTIAL
**Requirement:** "GPS access for location tracking, Camera access for photos"

**Current Status:** Camera exists, GPS needs implementation

**Design:**
- **Module:** `health_pwa`
- **Add to FSO:**
```python
job_start_location = fields.Char('Job Start GPS', help='Lat,Long')
job_end_location = fields.Char('Job End GPS')
location_accuracy = fields.Float('GPS Accuracy (meters)')
```

- **Mobile API:**
```python
@route('/api/pwa/record_location', type='json', auth='user')
def record_location(self, booking_id, location_type, latitude, longitude, accuracy):
    """Record GPS location for job start/end"""
    booking = request.env['health.fieldservice.order'].browse(booking_id)
    location_str = f"{latitude},{longitude}"

    if location_type == 'start':
        booking.write({
            'job_start_location': location_str,
            'location_accuracy': accuracy
        })
    elif location_type == 'end':
        booking.write({'job_end_location': location_str})
```

**Priority:** P1 (Useful for compliance and tracking)

---

## 10. Configuration & Master Data

### 10.1 Multi-Language Support ⚠️ PARTIAL
**Requirement:** "Vietnamese and English, User language preference, Context-sensitive translations"

**Current Status:** Odoo supports translations but not fully implemented

**Design:**
- **Module:** `health_base`
- **Enable translate=True on all user-facing fields**
- **Add language switcher:**
```python
# res.users
preferred_language = fields.Selection([
    ('vi_VN', 'Tiếng Việt'),
    ('en_US', 'English'),
], string='Preferred Language', default='vi_VN')
```

- **Data:** Create Vietnamese translation files for all modules
- **Views:** Language switcher in user preferences, auto-set on login

**Priority:** P0 (Critical for Vietnamese users)

---

### 10.2 Data Custodian Role & Approval Workflow ❌ MISSING
**Requirement:** "Board/Data Custodian controls code changes, Staff can request but not edit, Formal approval required"

**Current Status:** No approval workflow

**Design:**
- **Module:** `health_base`
- **New Group:** `Data Custodian` (res.groups)
- **New Model:** `health.config.change.request`
```python
class ConfigChangeRequest(models.Model):
    _name = 'health.config.change.request'
    _description = 'Configuration Change Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Request Title', required=True)
    requested_by = fields.Many2one('res.users', default=lambda self: self.env.user)
    request_date = fields.Datetime(default=fields.Datetime.now)

    change_type = fields.Selection([
        ('price_list', 'Price List Change'),
        ('lookup_table', 'Lookup Table Change'),
        ('service_catalog', 'Service Catalog Change'),
    ], required=True)

    target_model = fields.Char('Target Model')
    target_record_id = fields.Integer('Target Record ID')
    proposed_changes = fields.Text('Proposed Changes (JSON)')
    justification = fields.Text('Justification', required=True)

    approval_status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True)

    approved_by = fields.Many2one('res.users', string='Approved By')
    approval_date = fields.Datetime('Approval Date')
    approval_notes = fields.Text('Approval Notes')

    def action_submit_for_approval(self):
        """Submit request to Data Custodian"""
        self.write({'approval_status': 'submitted'})
        # Notify custodians

    def action_approve(self):
        """Approve and apply changes"""
        if not self.env.user.has_group('health_base.group_data_custodian'):
            raise UserError("Only Data Custodians can approve changes")
        # Apply changes from proposed_changes JSON
        self.write({
            'approval_status': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
```

**Views:** Approval dashboard for custodians, request form for staff

**Priority:** P1 (Governance requirement)

---

## 11. UI/UX Requirements

### 11.1 Role-Based Dashboards ⚠️ PARTIAL
**Requirement:** "Nurse dashboard, Sales dashboard, Accountant dashboard, Operations dashboard"

**Current Status:** Generic dashboards only

**Design:**
- **Module:** `health_base`
- **Create Custom Dashboards:**

```python
# Nurse Dashboard
<record id="action_nurse_dashboard" model="ir.actions.act_window">
    <field name="name">My Jobs</field>
    <field name="res_model">health.fieldservice.order</field>
    <field name="view_mode">kanban,calendar,list,form</field>
    <field name="domain">[('primary_staff_id.user_id', '=', uid), ('state', 'in', ['assigned', 'in_progress'])]</field>
    <field name="context">{'search_default_today': 1}</field>
</record>

# Sales Dashboard
<record id="action_sales_dashboard" model="ir.actions.act_window">
    <field name="name">My Leads & Bookings</field>
    <field name="res_model">crm.lead</field>
    <field name="view_mode">kanban,list,form,graph,pivot</field>
    <field name="domain">[('user_id', '=', uid)]</field>
</record>

# Accountant Dashboard
<record id="action_accountant_dashboard" model="ir.actions.act_window">
    <field name="name">Outstanding Invoices</field>
    <field name="res_model">account.move</field>
    <field name="view_mode">list,form,pivot,graph</field>
    <field name="domain">[('payment_state', '!=', 'paid'), ('move_type', '=', 'out_invoice')]</field>
</record>
```

**Menu Items:** Add to respective role menus

**Priority:** P1 (Improves UX significantly)

---

### 11.2 Visual Status Indicators ❌ MISSING
**Requirement:** "Online/offline status, Job status visual indicators, Booking status color coding"

**Current Status:** Basic status fields only

**Design:**
- **Module:** `health_base`
- **Add Status Badge Widget:**

```xml
<!-- Custom status badge -->
<field name="state" widget="statusbar" statusbar_visible="draft,confirmed,in_progress,done"/>

<!-- Color-coded badges -->
<field name="urgency_level" widget="badge" decoration-danger="urgency_level=='emergency'" decoration-warning="urgency_level=='urgent'"/>
```

- **Add Online Status:**
```python
# res.users
is_online = fields.Boolean('Online Status', compute='_compute_online_status')
last_activity = fields.Datetime('Last Activity')

@api.depends('last_activity')
def _compute_online_status(self):
    for user in self:
        if user.last_activity:
            diff = fields.Datetime.now() - user.last_activity
            user.is_online = diff.total_seconds() < 300  # 5 minutes
        else:
            user.is_online = False
```

**Views:** Green/red online indicators in staff lists

**Priority:** P2 (UX enhancement)

---

## 12. Security & Access Control

### 12.1 Audit Logging Enhancement ⚠️ PARTIAL
**Requirement:** "All changes logged (who, what, when, why), Call activity audit"

**Current Status:** Odoo has audit log but not comprehensive

**Design:**
- **Module:** `health_base`
- **Enable Advanced Audit:**
```python
# Add to all critical models
_inherit = ['mail.thread', 'mail.activity.mixin']

# All sensitive fields
tracking=True

# Create audit log view
class AuditLogView(models.Model):
    _name = 'health.audit.log.view'
    _description = 'Consolidated Audit Log'
    _auto = False

    @api.model
    def _get_sql(self):
        return """
        SELECT
            ml.id,
            ml.date,
            ml.author_id,
            ml.model,
            ml.res_id,
            ml.body,
            ml.tracking_value_ids
        FROM mail_message ml
        WHERE ml.message_type = 'notification'
        AND ml.tracking_value_ids IS NOT NULL
        ORDER BY ml.date DESC
        """
```

**Views:** Audit log dashboard accessible to Admin/Board only

**Priority:** P1 (Compliance requirement)

---

## Summary of Priorities

### P0 - Critical for Go-Live (Must implement immediately)
1. Phone number search filter (health_crm)
2. Contact tagging system (health_crm)
3. Address template concatenation (health_crm)
4. Cancellation management pop-up (health_fieldservice)
5. Part-time nurse workflow (health_fieldservice)
6. Job timer with mandatory notes/invoice (health_fieldservice)
7. Payment pop-up (pay now/later) (health_pwa)
8. Holiday calendar & pricing (health_base + advanced_pricing)
9. Multi-language support (all modules)

### P1 - Important (Implement soon after go-live)
1. Referral platform integration (health_crm)
2. Related persons dashboard (health_base)
3. Zalo notification integration (health_fieldservice)
4. Discount mandatory notes (health_invoicing)
5. Audit trail enhancement (advanced_pricing)
6. MOH submission (health_invoicing)
7. Viettel e-signature (health_invoicing)
8. GPS location tracking (health_pwa)
9. Data custodian approval workflow (health_base)
10. Role-based dashboards (health_base)
11. Comprehensive audit logging (health_base)

### P2 - Nice to Have (Future enhancements)
1. Cloud Doctor integration (health_invoicing)
2. Biometric login (health_pwa)
3. Visual status indicators (health_base)

---

## Implementation Approach

### Phase 1 - Core Workflows (Week 1-2)
- P0 items 1-5: CRM and booking workflows
- Database schema updates
- Basic UI changes

### Phase 2 - Invoicing & Compliance (Week 3-4)
- P0 items 6-9: Invoicing workflows, pricing, language
- MISA integration refinement
- Mobile app enhancements

### Phase 3 - Integration & Enhancement (Week 5-6)
- P1 items 1-6: External integrations
- Advanced features
- Admin tools

### Phase 4 - Polish & Optimization (Week 7-8)
- P1 items 7-11: Dashboards, reporting, audit
- Testing and refinement
- P2 items if time permits

---

## Technical Notes

### Module Modification Strategy
- **DO NOT create new modules** - extend existing ones only
- Use `_inherit` pattern for all model extensions
- Add new models only when absolutely necessary (lookup tables, configs)
- Leverage Odoo's existing infrastructure (mail.thread, portal.mixin, etc.)

### Database Considerations
- All new fields are additive - no breaking changes
- Use computed/related fields to minimize data duplication
- Index frequently searched fields (phone, patient_code, etc.)
- Use SQL constraints for data integrity

### Integration Patterns
- All external APIs: Create config model + integration model + webhook controller
- Use JSON fields for flexible API response storage
- Implement retry logic and error handling
- Log all integration attempts for debugging

### Mobile App (PWA) Strategy
- Keep API endpoints RESTful and versioned
- Implement offline-first data sync
- Use optimistic UI updates with background sync
- Validate all data server-side regardless of client validation

---

**END OF DESIGN DOCUMENT**

**Next Steps:**
1. Review and approve this design with client
2. Create detailed user stories for each feature
3. Estimate development effort
4. Implement in priority order (P0 → P1 → P2)
5. Test thoroughly before deployment
