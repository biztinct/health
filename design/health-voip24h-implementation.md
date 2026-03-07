# Implementation Plan: health_voip24h Module

## Executive Summary

Create a comprehensive VoIP24h integration module for the VAFHS healthcare system that captures call logs, recordings, and metadata via API integration. The module will follow established health module patterns, provide modern UI/UX for call analytics, and seamlessly integrate with CRM and patient management workflows.

**Module Name:** `health_voip24h`
**Type:** External Integration Module (similar to health_zalo)
**Purpose:** Call Detail Record (CDR) tracking, call analytics, and telephony integration

**Key Features:**
- **Call Log Synchronization:** Automatic CDR retrieval every 15 minutes
- **Call Analytics Dashboard:** Professional analytics with KPIs and filters
- **Contact Matching:** Automatic linking of calls to patients/contacts/leads
- **Call Recordings:** Download and playback of call recordings
- **Click-to-Dial:** Initiate outbound calls from contact/lead forms
- **Real-time Popups:** Incoming call notifications with caller identification
- **Call Functionality Control:** ⭐ **NEW** - Master switch to disable calling features (click-to-dial, popups) while maintaining full data collection and analytics capabilities
- **Activity Management:** Auto-create follow-up tasks for missed calls

---

## Research Findings & Key Insights

### VoIP24h API Capabilities

Based on research from [VoIP24h API documentation](https://voip24h.vn/api-tong-dai-voip/) and [technical docs](https://docs-sdk.voip24h.vn/):

**Available Features:**
- Click-to-dial functionality (initiate calls from CRM)
- Pop-up call notifications (display caller info automatically)
- Missed call event tracking
- Call history retrieval with timestamps, duration, status
- Call recording file access
- Caller identification and customer matching
- Real-time webhook notifications

**Integration Patterns:**
- RESTful API with authentication tokens
- Webhook callbacks for real-time events
- Call metadata includes: phone number, time, duration, status, recording URL
- Support for multi-extension PBX systems

**Similar Implementations:**
- [Salework CRM VoIP24h integration](https://docs.salework.net/salework-tai-lieu/salework-crm/thiet-lap-he-thong/cau-hinh-tu-dong/call-center-voip24h) demonstrates CRM popup and call logging
- Odoo has native [VoIP capabilities](https://www.odoo.com/documentation/18.0/applications/productivity/voip.html) with activity logging
- Third-party integrations ([Nuacom](https://nuacom.com/integrations/odoo-crm/), [CloudTalk](https://www.cloudtalk.io/odoo/)) show CDR and analytics patterns

### Architectural Patterns from Existing Modules

**From health_zalo (Reference Pattern):**
- Service layer for API client (decoupled from Odoo)
- OAuth/token management model
- Webhook controller with async processing
- Real-time bus notifications
- Integration with res.partner and crm.lead
- Message/conversation threading model

**From health_fieldservice (UI Patterns):**
- Timeline view with drag-and-drop
- Dashboard with analytics (pivot, graph, list views)
- Kanban boards with color-coded status
- Smart buttons and stat buttons
- Activity logging and escalation

**From health_base (Foundation):**
- Always inherit, never duplicate
- Security groups with RBAC hierarchy
- Configuration models as singletons
- Sequence generation for unique IDs
- Multi-company support

---

## Module Architecture Design

### 1. Module Structure

```
health_voip24h/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── voip_config.py              # VoIP24h configuration & auth
│   ├── voip_call_log.py            # Call Detail Records (CDR)
│   ├── voip_call_recording.py     # Call recordings & attachments
│   ├── voip_extension.py           # PBX extensions/lines
│   ├── voip_call_queue.py          # Call queue statistics
│   ├── res_partner.py              # Add VoIP fields to contacts
│   ├── crm_lead.py                 # Add VoIP fields to leads
│   └── mail_activity.py            # VoIP call activity type
├── services/
│   ├── __init__.py
│   ├── voip24h_api.py             # API client wrapper
│   ├── token_manager.py            # Authentication & token refresh
│   ├── call_handler.py             # Call event processing service
│   └── cdr_sync.py                 # Periodic CDR synchronization
├── controllers/
│   ├── __init__.py
│   ├── webhook.py                  # Webhook receiver for real-time events
│   └── api.py                      # Internal API for click-to-dial
├── wizard/
│   ├── __init__.py
│   ├── voip_sync_wizard.py        # Manual sync wizard
│   └── voip_sync_wizard_views.xml
├── security/
│   ├── voip24h_security.xml       # Security groups
│   └── ir.model.access.csv        # Access control matrix
├── data/
│   ├── voip24h_data.xml           # Sequences, call types
│   ├── voip24h_activity_types.xml # Phone call activity types
│   └── voip24h_cron.xml           # Scheduled actions
├── views/
│   ├── voip_config_views.xml      # Configuration form
│   ├── voip_call_log_views.xml    # Call log list/form/kanban
│   ├── voip_dashboard_views.xml   # Analytics dashboard
│   ├── voip_timeline_views.xml    # Call timeline view
│   ├── res_partner_views.xml      # Partner extensions
│   ├── crm_lead_views.xml         # Lead extensions
│   └── voip_menus.xml             # Menu structure
├── static/
│   ├── src/
│   │   ├── js/
│   │   │   ├── call_log_widget.js      # Call log widget
│   │   │   ├── click_to_dial_widget.js # Click-to-dial functionality
│   │   │   ├── call_popup_service.js   # Real-time call popups
│   │   │   └── voip_dashboard.js       # Dashboard component
│   │   ├── xml/
│   │   │   ├── call_log_widget.xml
│   │   │   ├── click_to_dial_widget.xml
│   │   │   └── call_popup.xml
│   │   ├── scss/
│   │   │   ├── voip_dashboard.scss
│   │   │   └── call_popup.scss
│   │   └── css/
│   └── description/
│       └── icon.png
└── demo/
    └── demo_data.xml
```

---

## 2. Data Models

### A. voip.config (Configuration & Authentication)

**Purpose:** VoIP24h account configuration and API credentials management

```python
class VoIP24hConfig(models.Model):
    _name = 'voip.config'
    _description = 'VoIP24h Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    # Basic Info
    name = fields.Char(string='Configuration Name', required=True, default='VoIP24h Integration')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True)
    active = fields.Boolean(default=True)

    # API Credentials
    api_key = fields.Char(string='API Key', required=True, groups='base.group_system')
    api_secret = fields.Char(string='API Secret', required=True, groups='base.group_system')
    account_id = fields.Char(string='Account ID', required=True)
    domain = fields.Char(string='VoIP24h Domain', default='voip24h.vn')
    api_base_url = fields.Char(string='API Base URL',
                               default='https://api.voip24h.vn/v1',
                               required=True)

    # Authentication Token
    access_token = fields.Char(string='Access Token', groups='base.group_system', readonly=True)
    token_expires_at = fields.Datetime(string='Token Expires At', readonly=True)
    token_type = fields.Char(string='Token Type', readonly=True)

    # Webhook Configuration
    webhook_enabled = fields.Boolean(string='Webhook Enabled', default=False)
    webhook_url = fields.Char(string='Webhook URL', compute='_compute_webhook_url', readonly=True)
    webhook_secret = fields.Char(string='Webhook Secret', groups='base.group_system')

    # Call Functionality Control
    enable_call_functionality = fields.Boolean(
        string='Enable Call Functionality',
        default=False,
        help='Enable click-to-dial and incoming call popups. '
             'When disabled, only call logs, recordings, and analytics are available.'
    )
    enable_outgoing_calls = fields.Boolean(
        string='Enable Outgoing Calls',
        default=True,
        help='Allow users to initiate calls via click-to-dial. '
             'Requires "Enable Call Functionality" to be enabled.'
    )
    enable_incoming_call_popups = fields.Boolean(
        string='Enable Incoming Call Popups',
        default=True,
        help='Show real-time popups for incoming calls. '
             'Requires "Enable Call Functionality" to be enabled.'
    )

    # Sync Settings
    auto_sync_enabled = fields.Boolean(string='Auto Sync CDR', default=True)
    sync_interval_minutes = fields.Integer(string='Sync Interval (Minutes)', default=15)
    sync_history_days = fields.Integer(string='Sync History (Days)', default=30,
                                      help='Number of days to sync call history on first setup')
    last_sync_date = fields.Datetime(string='Last Sync Date', readonly=True)

    # Statistics
    total_calls_synced = fields.Integer(string='Total Calls Synced', readonly=True, default=0)
    total_recordings_synced = fields.Integer(string='Total Recordings Synced', readonly=True, default=0)

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('error', 'Connection Error'),
    ], string='Status', default='draft', tracking=True)

    error_message = fields.Text(string='Error Message', readonly=True)

    @api.depends('company_id')
    def _compute_webhook_url(self):
        """Compute webhook URL for VoIP24h to call"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for config in self:
            config.webhook_url = f"{base_url}/voip24h/webhook"

    def action_test_connection(self):
        """Test VoIP24h API connection"""
        # Implementation
        pass

    def action_sync_call_history(self):
        """Manually trigger call history sync"""
        # Implementation
        pass

    @api.model
    def get_active_config(self):
        """Get active VoIP24h configuration (singleton pattern)"""
        return self.search([('active', '=', True), ('company_id', '=', self.env.company.id)], limit=1)
```

### B. voip.call.log (Call Detail Records)

**Purpose:** Store comprehensive call logs with metadata

```python
class VoIPCallLog(models.Model):
    _name = 'voip.call.log'
    _description = 'VoIP Call Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'call_date desc, id desc'
    _rec_name = 'call_id'

    # Call Identification
    call_id = fields.Char(string='Call ID', required=True, index=True, readonly=True,
                         help='Unique call identifier from VoIP24h')
    voip_config_id = fields.Many2one('voip.config', string='VoIP Configuration',
                                     required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', related='voip_config_id.company_id',
                                store=True, index=True)

    # Call Details
    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('internal', 'Internal'),
    ], string='Direction', required=True, index=True)

    call_type = fields.Selection([
        ('answered', 'Answered'),
        ('missed', 'Missed'),
        ('abandoned', 'Abandoned'),
        ('voicemail', 'Voicemail'),
        ('failed', 'Failed'),
        ('busy', 'Busy'),
    ], string='Call Type', required=True, index=True)

    # Phone Numbers
    caller_number = fields.Char(string='Caller Number', index=True)
    caller_number_normalized = fields.Char(string='Normalized Caller', index=True,
                                          compute='_compute_normalized_numbers', store=True)
    called_number = fields.Char(string='Called Number', index=True)
    called_number_normalized = fields.Char(string='Normalized Called', index=True,
                                          compute='_compute_normalized_numbers', store=True)

    # Extensions
    extension_id = fields.Many2one('voip.extension', string='Extension', index=True)
    extension_number = fields.Char(string='Extension Number')
    answered_by_extension = fields.Char(string='Answered By Extension')

    # Timing
    call_date = fields.Datetime(string='Call Date/Time', required=True, index=True)
    start_time = fields.Datetime(string='Start Time')
    answer_time = fields.Datetime(string='Answer Time')
    end_time = fields.Datetime(string='End Time')

    duration_seconds = fields.Integer(string='Total Duration (seconds)', default=0)
    talk_duration_seconds = fields.Integer(string='Talk Duration (seconds)', default=0,
                                          help='Duration after call was answered')
    wait_duration_seconds = fields.Integer(string='Wait Duration (seconds)', default=0,
                                          help='Ring time before answer')

    duration_display = fields.Char(string='Duration', compute='_compute_duration_display')

    # Quality & Status
    call_status = fields.Selection([
        ('completed', 'Completed'),
        ('no_answer', 'No Answer'),
        ('busy', 'Busy'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='completed')

    hangup_cause = fields.Char(string='Hangup Cause')
    call_quality_score = fields.Integer(string='Quality Score', help='1-5 scale')

    # Recordings
    has_recording = fields.Boolean(string='Has Recording', default=False, index=True)
    recording_ids = fields.One2many('voip.call.recording', 'call_log_id', string='Recordings')
    recording_count = fields.Integer(string='Recording Count', compute='_compute_recording_count')

    # CRM Integration
    partner_id = fields.Many2one('res.partner', string='Contact/Patient', index=True)
    lead_id = fields.Many2one('crm.lead', string='Lead/Opportunity', index=True)

    # Auto-matching fields
    auto_matched = fields.Boolean(string='Auto-matched', default=False,
                                  help='Was contact/lead matched automatically?')
    match_confidence = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Match Confidence')

    # Call Notes & Outcome
    call_notes = fields.Text(string='Call Notes')
    call_outcome = fields.Selection([
        ('service_booked', 'Service Booked'),
        ('follow_up_required', 'Follow-up Required'),
        ('information_provided', 'Information Provided'),
        ('complaint', 'Complaint'),
        ('no_action', 'No Action Required'),
    ], string='Call Outcome')

    # Activity Creation
    activity_id = fields.Many2one('mail.activity', string='Related Activity', readonly=True)
    activity_created = fields.Boolean(string='Activity Created', default=False)

    # Metadata
    raw_data = fields.Text(string='Raw API Data', groups='base.group_system',
                          help='Original JSON data from VoIP24h API')
    synced_date = fields.Datetime(string='Synced On', default=fields.Datetime.now, readonly=True)

    # State
    state = fields.Selection([
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('processed', 'Processed'),
    ], string='State', default='new', tracking=True)

    @api.depends('caller_number', 'called_number')
    def _compute_normalized_numbers(self):
        """Normalize phone numbers for matching"""
        for log in self:
            log.caller_number_normalized = self._normalize_phone(log.caller_number)
            log.called_number_normalized = self._normalize_phone(log.called_number)

    def _normalize_phone(self, phone):
        """Remove spaces, dashes, parentheses from phone number"""
        if not phone:
            return False
        import re
        return re.sub(r'[^\d+]', '', phone)

    @api.depends('duration_seconds', 'talk_duration_seconds')
    def _compute_duration_display(self):
        """Format duration as HH:MM:SS"""
        for log in self:
            if log.duration_seconds:
                hours = log.duration_seconds // 3600
                minutes = (log.duration_seconds % 3600) // 60
                seconds = log.duration_seconds % 60
                if hours > 0:
                    log.duration_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    log.duration_display = f"{minutes:02d}:{seconds:02d}"
            else:
                log.duration_display = "00:00"

    @api.depends('recording_ids')
    def _compute_recording_count(self):
        for log in self:
            log.recording_count = len(log.recording_ids)

    def action_match_contact(self):
        """Manually match call to contact/patient"""
        # Open wizard to search and link contact
        pass

    def action_create_lead(self):
        """Create CRM lead from call log"""
        # Create lead with pre-filled data
        pass

    def action_create_activity(self):
        """Create follow-up activity for this call"""
        # Create phonecall activity
        pass

    def action_play_recording(self):
        """Play call recording"""
        # Open recording player
        pass

    @api.model
    def auto_match_contact_from_phone(self, phone_number):
        """Auto-match contact based on phone number"""
        if not phone_number:
            return False

        normalized = self._normalize_phone(phone_number)

        # Search res.partner by mobile or phone
        partner = self.env['res.partner'].search([
            '|',
            ('mobile', '=', phone_number),
            ('phone', '=', phone_number),
        ], limit=1)

        if not partner and normalized:
            # Try normalized search
            partner = self.env['res.partner'].search([
                '|',
                ('mobile', 'ilike', normalized),
                ('phone', 'ilike', normalized),
            ], limit=1)

        return partner
```

### C. voip.call.recording (Call Recordings)

**Purpose:** Store call recording files and metadata

```python
class VoIPCallRecording(models.Model):
    _name = 'voip.call.recording'
    _description = 'VoIP Call Recording'
    _order = 'create_date desc'

    name = fields.Char(string='Recording Name', compute='_compute_name', store=True)
    call_log_id = fields.Many2one('voip.call.log', string='Call Log',
                                  required=True, ondelete='cascade', index=True)

    # Recording Details
    recording_id = fields.Char(string='Recording ID', index=True,
                              help='Unique recording identifier from VoIP24h')
    recording_url = fields.Char(string='Recording URL', required=True)
    recording_file = fields.Binary(string='Recording File', attachment=True)
    recording_filename = fields.Char(string='Filename')

    # Metadata
    duration_seconds = fields.Integer(string='Duration (seconds)')
    file_size_bytes = fields.Integer(string='File Size (bytes)')
    file_format = fields.Char(string='Format', default='mp3')
    mimetype = fields.Char(string='MIME Type', default='audio/mpeg')

    # Download Status
    is_downloaded = fields.Boolean(string='Downloaded', default=False)
    downloaded_date = fields.Datetime(string='Downloaded On')
    download_error = fields.Text(string='Download Error')

    # State
    state = fields.Selection([
        ('pending', 'Pending Download'),
        ('downloading', 'Downloading'),
        ('available', 'Available'),
        ('error', 'Download Error'),
    ], string='State', default='pending')

    @api.depends('call_log_id.call_id', 'recording_id')
    def _compute_name(self):
        for rec in self:
            rec.name = f"Recording - {rec.call_log_id.call_id or 'Unknown'}"

    def action_download_recording(self):
        """Download recording file from VoIP24h"""
        # Implementation to fetch and store recording
        pass

    def action_play_recording(self):
        """Play recording in browser"""
        # Open audio player
        pass
```

### D. voip.extension (PBX Extensions)

**Purpose:** Manage VoIP extensions/lines and staff assignments

```python
class VoIPExtension(models.Model):
    _name = 'voip.extension'
    _description = 'VoIP Extension/Line'
    _order = 'extension_number'

    name = fields.Char(string='Extension Name', required=True)
    extension_number = fields.Char(string='Extension Number', required=True, index=True)
    extension_type = fields.Selection([
        ('internal', 'Internal Extension'),
        ('external', 'External Line'),
        ('queue', 'Call Queue'),
        ('ivr', 'IVR'),
    ], string='Type', default='internal', required=True)

    # Staff Assignment
    user_id = fields.Many2one('res.users', string='Assigned User')
    employee_id = fields.Many2one('hr.employee', string='Assigned Employee')

    # Configuration
    voip_config_id = fields.Many2one('voip.config', string='VoIP Configuration',
                                     required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='voip_config_id.company_id', store=True)

    # Settings
    allow_incoming = fields.Boolean(string='Allow Incoming Calls', default=True)
    allow_outgoing = fields.Boolean(string='Allow Outgoing Calls', default=True)
    record_calls = fields.Boolean(string='Record Calls', default=True)

    # Statistics
    total_calls = fields.Integer(string='Total Calls', compute='_compute_call_stats')
    missed_calls = fields.Integer(string='Missed Calls', compute='_compute_call_stats')

    active = fields.Boolean(default=True)

    def _compute_call_stats(self):
        for ext in self:
            logs = self.env['voip.call.log'].search([
                ('extension_id', '=', ext.id)
            ])
            ext.total_calls = len(logs)
            ext.missed_calls = len(logs.filtered(lambda l: l.call_type == 'missed'))
```

### E. res.partner Extension

**Purpose:** Add VoIP fields to contacts

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    # VoIP Integration
    voip_call_log_ids = fields.One2many('voip.call.log', 'partner_id', string='Call Logs')
    voip_call_count = fields.Integer(string='Call Count', compute='_compute_voip_stats')
    voip_last_call_date = fields.Datetime(string='Last Call Date', compute='_compute_voip_stats', store=True)
    voip_total_talk_time = fields.Integer(string='Total Talk Time (minutes)',
                                         compute='_compute_voip_stats')

    # Preferred Contact Method
    voip_preferred_number = fields.Char(string='Preferred Call Number',
                                       help='Preferred number for outgoing calls')
    voip_do_not_call = fields.Boolean(string='Do Not Call', default=False,
                                      help='Flag to prevent outgoing calls')

    @api.depends('voip_call_log_ids')
    def _compute_voip_stats(self):
        for partner in self:
            logs = partner.voip_call_log_ids
            partner.voip_call_count = len(logs)
            if logs:
                partner.voip_last_call_date = max(logs.mapped('call_date'))
                partner.voip_total_talk_time = sum(logs.mapped('talk_duration_seconds')) // 60
            else:
                partner.voip_last_call_date = False
                partner.voip_total_talk_time = 0

    def action_view_call_logs(self):
        """View all call logs for this contact"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Call Logs - {self.name}',
            'res_model': 'voip.call.log',
            'view_mode': 'list,form,kanban',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id}
        }

    def action_call_voip(self):
        """Initiate VoIP call (click-to-dial)"""
        self.ensure_one()

        # Get VoIP configuration
        config = self.env['voip.config'].get_active_config()
        if not config:
            raise UserError(_('VoIP is not configured. Please contact your administrator.'))

        # Check if call functionality is enabled
        if not config.enable_call_functionality:
            raise UserError(_('Call functionality is disabled. Please contact your administrator.'))

        if not config.enable_outgoing_calls:
            raise UserError(_('Outgoing calls are disabled. Please contact your administrator.'))

        # Check do not call flag
        if self.voip_do_not_call:
            raise UserError(_('This contact is marked as "Do Not Call".'))

        # Determine phone number to call
        phone_to_call = self.voip_preferred_number or self.mobile or self.phone
        if not phone_to_call:
            raise UserError(_('No phone number available for this contact.'))

        # Implementation for click-to-dial
        # Call VoIP24h API to initiate call
        pass
```

### F. crm.lead Extension

**Purpose:** Add VoIP call tracking to leads

```python
class CRMLead(models.Model):
    _inherit = 'crm.lead'

    voip_call_log_ids = fields.One2many('voip.call.log', 'lead_id', string='Call Logs')
    voip_call_count = fields.Integer(string='Call Count', compute='_compute_voip_call_count')
    voip_last_call_date = fields.Datetime(string='Last Call', compute='_compute_voip_call_count', store=True)

    @api.depends('voip_call_log_ids')
    def _compute_voip_call_count(self):
        for lead in self:
            lead.voip_call_count = len(lead.voip_call_log_ids)
            lead.voip_last_call_date = max(lead.voip_call_log_ids.mapped('call_date')) if lead.voip_call_log_ids else False

    def action_call_lead(self):
        """Call the lead via VoIP"""
        self.ensure_one()

        # Get VoIP configuration
        config = self.env['voip.config'].get_active_config()
        if not config:
            raise UserError(_('VoIP is not configured. Please contact your administrator.'))

        # Check if call functionality is enabled
        if not config.enable_call_functionality:
            raise UserError(_('Call functionality is disabled. Please contact your administrator.'))

        if not config.enable_outgoing_calls:
            raise UserError(_('Outgoing calls are disabled. Please contact your administrator.'))

        # Determine phone number to call
        phone_to_call = self.mobile or self.phone
        if not phone_to_call:
            raise UserError(_('No phone number available for this lead.'))

        # Click-to-dial implementation
        # Call VoIP24h API to initiate call
        pass
```

---

## 3. Service Layer (API Integration)

### A. VoIP24h API Client

**File:** `services/voip24h_api.py`

**Key Methods:**
- `authenticate()` - Get access token
- `get_call_history(from_date, to_date, limit, offset)` - Fetch CDR
- `get_call_details(call_id)` - Get single call details
- `get_recording_url(call_id)` - Get recording download URL
- `download_recording(url)` - Download recording file
- `initiate_call(from_extension, to_number)` - Click-to-dial
- `get_extensions()` - List all extensions
- `get_call_queue_stats()` - Queue statistics

**Pattern:** Follow health_zalo/services/zalo_api.py structure
- Automatic token refresh on 401
- Retry logic with exponential backoff
- Error handling and logging
- Rate limiting compliance

### B. Call Handler Service

**File:** `services/call_handler.py`

**Purpose:** Process incoming webhook events and create/update records

**Key Methods:**
- `process_call_event(event_data)` - Main webhook handler
- `create_or_update_call_log(call_data)` - Upsert call log
- `auto_match_contact(phone_number)` - Match to res.partner
- `create_activity_for_missed_call(call_log)` - Auto-create follow-up
- `download_recording_async(call_log)` - Queue recording download

### C. CDR Sync Service

**File:** `services/cdr_sync.py`

**Purpose:** Periodic synchronization of call history

**Key Methods:**
- `sync_call_history(config, from_date, to_date)` - Bulk sync
- `sync_recordings(call_logs)` - Download all recordings
- `process_sync_batch(call_data_list)` - Batch processing

---

## 4. Controllers (Webhooks & API)

### A. Webhook Controller

**File:** `controllers/webhook.py`

**Endpoint:** `/voip24h/webhook`

**Pattern:** Follow health_zalo webhook pattern
- Fast response (<2 seconds)
- Async processing with `.with_delay()`
- Signature validation
- Always return HTTP 200

**Events to Handle:**
- `call.started` - Call initiated
- `call.answered` - Call connected
- `call.ended` - Call completed
- `call.missed` - Missed call
- `recording.available` - Recording ready

### B. Internal API Controller

**File:** `controllers/api.py`

**Endpoints:**
- `/voip24h/click_to_dial` - Initiate outbound call
- `/voip24h/call_logs` - Get call logs (for widgets)
- `/voip24h/call_stats` - Get call statistics

---

## 5. Modern UI/UX Design

### A. VoIP Configuration Form

**File:** `views/voip_config_views.xml`

**Purpose:** Central configuration interface for VoIP24h integration settings

**Form Structure:**
```xml
<form>
    <sheet>
        <div class="oe_button_box" name="button_box">
            <button name="action_test_connection" type="object" class="oe_stat_button" icon="fa-plug">
                <div class="o_field_widget o_stat_info">
                    <span class="o_stat_text">Test Connection</span>
                </div>
            </button>
            <button name="action_sync_call_history" type="object" class="oe_stat_button" icon="fa-refresh">
                <div class="o_field_widget o_stat_info">
                    <span class="o_stat_value"><field name="total_calls_synced"/></span>
                    <span class="o_stat_text">Calls Synced</span>
                </div>
            </button>
        </div>

        <group>
            <field name="name"/>
            <field name="company_id"/>
            <field name="state"/>
        </group>

        <notebook>
            <!-- API Configuration Tab -->
            <page string="API Configuration">
                <group>
                    <group string="Credentials">
                        <field name="api_key" password="True"/>
                        <field name="api_secret" password="True"/>
                        <field name="account_id"/>
                    </group>
                    <group string="API Settings">
                        <field name="api_base_url"/>
                        <field name="domain"/>
                        <field name="access_token" readonly="1"/>
                        <field name="token_expires_at" readonly="1"/>
                    </group>
                </group>
            </page>

            <!-- Call Functionality Tab (NEW) -->
            <page string="Call Functionality">
                <div class="alert alert-info mb-3" role="alert">
                    <h5><i class="fa fa-info-circle"/> Call Functionality Control</h5>
                    <p>Toggle these settings to control whether users can make or receive calls through the system.
                       <strong>Data collection (call logs, recordings, analytics) continues regardless of these settings.</strong></p>
                </div>

                <group>
                    <group string="Master Control">
                        <field name="enable_call_functionality"/>
                    </group>
                    <group/>
                </group>

                <group invisible="not enable_call_functionality">
                    <group string="Outgoing Calls">
                        <field name="enable_outgoing_calls"/>
                        <p class="text-muted" invisible="not enable_outgoing_calls">
                            Users can initiate calls via click-to-dial buttons on contact/lead forms.
                        </p>
                        <p class="text-danger" invisible="enable_outgoing_calls">
                            Click-to-dial buttons will be hidden from all forms.
                        </p>
                    </group>
                    <group string="Incoming Calls">
                        <field name="enable_incoming_call_popups"/>
                        <p class="text-muted" invisible="not enable_incoming_call_popups">
                            Real-time popups will display caller information when calls arrive.
                        </p>
                        <p class="text-danger" invisible="enable_incoming_call_popups">
                            Incoming call popups will not be shown to users.
                        </p>
                    </group>
                </group>

                <div class="alert alert-warning mt-3" role="alert" invisible="enable_call_functionality">
                    <h5><i class="fa fa-warning"/> ⚠️ Call Functionality Disabled</h5>
                    <p><strong>What's disabled:</strong></p>
                    <ul class="mb-2">
                        <li>Users cannot initiate outgoing calls (click-to-dial)</li>
                        <li>Incoming call popups will not appear</li>
                        <li>Real-time call status updates disabled</li>
                    </ul>
                    <p><strong>What remains active:</strong></p>
                    <ul class="mb-0">
                        <li>Call log synchronization (every 15 minutes)</li>
                        <li>Call recordings download and playback</li>
                        <li>Analytics dashboard and reports</li>
                        <li>Contact/lead matching</li>
                        <li>Activity creation for missed calls</li>
                    </ul>
                </div>
            </page>

            <!-- Webhook Configuration Tab -->
            <page string="Webhooks">
                <group>
                    <group>
                        <field name="webhook_enabled"/>
                        <field name="webhook_url" readonly="1"/>
                        <field name="webhook_secret" password="True"/>
                    </group>
                    <group>
                        <!-- Webhook configuration help text -->
                    </group>
                </group>
            </page>

            <!-- Sync Settings Tab -->
            <page string="Sync Settings">
                <group>
                    <group>
                        <field name="auto_sync_enabled"/>
                        <field name="sync_interval_minutes"/>
                        <field name="sync_history_days"/>
                    </group>
                    <group>
                        <field name="last_sync_date" readonly="1"/>
                        <field name="total_calls_synced" readonly="1"/>
                        <field name="total_recordings_synced" readonly="1"/>
                    </group>
                </group>
            </page>
        </notebook>
    </sheet>
    <chatter reload_on_follower="True"/>
</form>
```

**Key Features:**
- **Call Functionality Tab:** NEW - Dedicated tab for enabling/disabling calling features
- **Master switch:** `enable_call_functionality` controls all calling features
- **Granular control:** Separate toggles for outgoing calls and incoming popups
- **Visual feedback:** Alert boxes explain what's enabled/disabled
- **Help text:** Clear descriptions of each setting's impact

---

### B. VoIP Dashboard (Main View)

**Inspired by:** health_invoicing AR dashboard + health_fieldservice assignment dashboard

**Features:**
- **Multi-view support:** List, Kanban, Pivot, Graph
- **KPI Cards at top:**
  - Total Calls Today
  - Missed Calls (red alert if > 5)
  - Average Call Duration
  - Total Talk Time
- **Interactive filters:**
  - Date ranges (Today, This Week, This Month, Custom)
  - Call direction (Incoming, Outgoing, Internal)
  - Call type (Answered, Missed, Abandoned)
  - Extension/User filter
  - Contact/Lead filter
- **Color-coded rows:**
  - Green: Answered calls
  - Red: Missed calls
  - Yellow: Abandoned calls
  - Gray: Voicemail
- **Quick actions:**
  - Play recording (if available)
  - Match to contact
  - Create lead
  - Create follow-up activity

**File:** `views/voip_dashboard_views.xml`

### B. Call Timeline View (OWL Component)

**Inspired by:** health_fieldservice assignment_timeline_view

**Features:**
- **Timeline visualization** showing calls chronologically
- **Extension/User rows** with call blocks
- **Color-coded call blocks:**
  - Incoming: Blue
  - Outgoing: Green
  - Missed: Red
- **Hover details:**
  - Caller/Called number
  - Duration
  - Status
  - Recording icon if available
- **Filters:**
  - Date range selector
  - Extension filter
  - Call type filter

**Files:**
- `static/src/xml/call_timeline.xml`
- `static/src/js/call_timeline.js`
- `static/src/scss/call_timeline.scss`

### C. Call Log Kanban

**Features:**
- **Group by:** Status, User, Call Type, Date
- **Card design:**
  - Large phone icon (incoming/outgoing)
  - Contact name (if matched)
  - Phone number
  - Call duration with icon
  - Recording badge (if available)
  - Status badge (color-coded)
  - Quick action buttons:
    - Match contact
    - Create lead
    - Play recording
- **Drag-and-drop:** Change status (New → Reviewed → Processed)

**File:** `views/voip_call_log_views.xml`

### D. Click-to-Dial Widget (Phone Icon)

**Inspired by:** Odoo native VoIP widget

**Features:**
- **Phone icon button** next to phone/mobile fields in forms
- **Click triggers:**
  - API call to VoIP24h to initiate call
  - Show dialing notification
  - Create call log entry
- **Real-time status updates:**
  - Dialing...
  - Ringing...
  - Connected
  - Ended
- **Post-call actions:**
  - Add notes
  - Schedule follow-up
  - Update lead stage

**Files:**
- `static/src/js/click_to_dial_widget.js`
- `static/src/xml/click_to_dial_widget.xml`

### E. Call Popup (Real-time)

**Inspired by:** VoIPstudio Odoo integration popup

**Features:**
- **Popup on incoming call:**
  - Caller identification (if matched)
  - Phone number
  - Call history count
  - Recent interactions
  - Quick actions:
    - Open contact/lead
    - Create new lead
    - Add note
- **Persistent during call**
- **Post-call form:**
  - Call outcome
  - Notes
  - Follow-up required?

**Files:**
- `static/src/js/call_popup_service.js`
- `static/src/xml/call_popup.xml`
- `static/src/scss/call_popup.scss`

### F. Smart Buttons on Forms

**Add to res.partner form:**
```xml
<button name="action_view_call_logs"
        type="object"
        class="oe_stat_button"
        icon="fa-phone"
        invisible="voip_call_count == 0">
    <field name="voip_call_count" widget="statinfo" string="Calls"/>
</button>

<button name="action_call_voip"
        type="object"
        string="📞 Call"
        class="btn-primary"/>
```

**Add to crm.lead form:**
```xml
<button name="action_view_call_logs"
        type="object"
        class="oe_stat_button"
        icon="fa-phone"
        invisible="voip_call_count == 0">
    <field name="voip_call_count" widget="statinfo" string="Calls"/>
</button>
```

---

## 6. Security & Access Control

### A. Security Groups

```xml
<!-- Base access for all healthcare staff -->
<record id="group_voip_user" model="res.groups">
    <field name="name">VoIP: User</field>
    <field name="category_id" ref="module_category_voip24h"/>
    <field name="implied_ids" eval="[(4, ref('health_base.group_healthcare_base'))]"/>
</record>

<!-- Manager access for configuration -->
<record id="group_voip_manager" model="res.groups">
    <field name="name">VoIP: Manager</field>
    <field name="category_id" ref="module_category_voip24h"/>
    <field name="implied_ids" eval="[(4, ref('group_voip_user'))]"/>
</record>
```

### B. Record Rules

- Users can see their own call logs
- Managers can see all call logs
- System admins have full access
- Patients can't see call logs (no portal access)

### C. Field-Level Security

- API credentials: `base.group_system` only
- Raw API data: `base.group_system` only
- Call recordings: All VoIP users

---

## 7. Scheduled Actions (Cron Jobs)

```xml
<!-- Sync call history every 15 minutes -->
<record id="cron_sync_call_history" model="ir.cron">
    <field name="name">VoIP24h: Sync Call History</field>
    <field name="model_id" ref="model_voip_config"/>
    <field name="state">code</field>
    <field name="code">model.cron_sync_call_history()</field>
    <field name="interval_number">15</field>
    <field name="interval_type">minutes</field>
    <field name="numbercall">-1</field>
    <field name="active" eval="True"/>
</record>

<!-- Download pending recordings every 5 minutes -->
<record id="cron_download_recordings" model="ir.cron">
    <field name="name">VoIP24h: Download Pending Recordings</field>
    <field name="model_id" ref="model_voip_call_recording"/>
    <field name="state">code</field>
    <field name="code">model.cron_download_pending_recordings()</field>
    <field name="interval_number">5</field>
    <field name="interval_type">minutes</field>
    <field name="numbercall">-1</field>
    <field name="active" eval="True"/>
</record>

<!-- Auto-create activities for missed calls -->
<record id="cron_create_missed_call_activities" model="ir.cron">
    <field name="name">VoIP24h: Create Missed Call Activities</field>
    <field name="model_id" ref="model_voip_call_log"/>
    <field name="state">code</field>
    <field name="code">model.cron_create_missed_call_activities()</field>
    <field name="interval_number">10</field>
    <field name="interval_type">minutes</field>
    <field name="numbercall">-1</field>
    <field name="active" eval="True"/>
</record>
```

---

## 8. Menu Structure

```
Healthcare (root)
└── VoIP24h
    ├── Dashboard (action: voip_dashboard)
    ├── Call Logs
    │   ├── All Calls
    │   ├── Missed Calls
    │   ├── Today's Calls
    │   └── My Calls
    ├── Call Timeline (OWL view)
    ├── Recordings
    ├── Extensions
    └── Configuration
        ├── VoIP Configuration
        ├── Sync Call History (wizard)
        └── Settings
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1)
- Create module structure
- Implement data models (voip.config, voip.call.log, voip.call.recording, voip.extension)
- Basic security groups and access rules
- Configuration form view

### Phase 2: API Integration (Week 1-2)
- Implement VoIP24h API client service
- Token management and authentication
- CDR sync service
- Webhook controller
- Test API connectivity

### Phase 3: Core Features (Week 2-3)
- Call log list/form/kanban views
- Auto-matching logic (phone → contact/lead)
- Recording download functionality
- res.partner and crm.lead extensions
- Smart buttons

### Phase 4: Advanced UI (Week 3-4)
- VoIP Dashboard with analytics
- Call Timeline OWL component
- Click-to-dial widget
- Real-time call popup
- Call log kanban with drag-drop

### Phase 5: Automation (Week 4)
- Scheduled actions (cron jobs)
- Auto-create activities for missed calls
- Webhook real-time processing
- Bus notifications

### Phase 6: Testing & Polish (Week 5)
- End-to-end testing
- UI/UX refinements
- Performance optimization
- Documentation

---

## 10. Dependencies & Requirements

### Module Dependencies
```python
'depends': [
    'base',
    'web',
    'mail',
    'contacts',
    'crm',
    'hr',
    'health_base',
    'health_crm',
    'bus',
]
```

### External Python Libraries
```python
'external_dependencies': {
    'python': ['requests', 'python-dateutil'],
}
```

### Odoo 18 Requirements
- OWL (Odoo Web Library) for custom components
- Bus service for real-time notifications
- Proper XML structure (no `<data>` tags, use `<odoo>`)
- Use `list` not `tree` for list views
- Chatter pattern: `<chatter reload_on_follower="True"/>` outside `</sheet>`

---

## 11. Key Technical Decisions

### A. Why Service Layer Pattern?
Following health_zalo architecture for:
- Decoupling from Odoo ORM
- Easier testing
- Reusable API client
- Better error handling

### B. Why Webhook + Polling Hybrid?
- **Webhooks:** Real-time call notifications
- **Polling (Cron):** Backup for missed webhooks, historical sync

### C. Phone Number Normalization
Store both original and normalized formats:
- Original: Display to users
- Normalized: Matching and searching

### D. Recording Storage Strategy
- Store URL always
- Download file on-demand or async
- Use ir.attachment for file storage
- Configurable retention policy

### E. Auto-Matching Confidence Levels
- **High:** Exact match on mobile/phone
- **Medium:** Partial match (normalized)
- **Low:** Multiple matches found

### F. Call Functionality Control (Master Switch)

**Purpose:** Allow administrators to disable calling features while maintaining all data collection and analytics capabilities.

**Use Cases:**
- **Initial Setup:** Collect and analyze historical call data before enabling live calling
- **Training Period:** Learn from existing call logs without allowing staff to make calls
- **Compliance/Testing:** Monitor integration without affecting live operations
- **Data-Only Mode:** Use VoIP24h purely for analytics without phone system integration

**Configuration Hierarchy:**
```
enable_call_functionality (Master Switch)
├── enable_outgoing_calls (Click-to-dial)
└── enable_incoming_call_popups (Real-time popups)
```

**Behavior When Disabled:**
- ✅ **ENABLED (Not Affected):**
  - Call log synchronization (cron jobs)
  - CDR data retrieval via API
  - Call recordings download and playback
  - Analytics dashboard and reports
  - Call timeline view
  - Contact/lead matching
  - Call history viewing
  - Activity creation for missed calls
  - All views (list, kanban, form, pivot, graph)
  - Smart buttons showing call counts

- ❌ **DISABLED (Hidden/Blocked):**
  - Click-to-dial buttons on forms
  - Incoming call popup notifications
  - `action_call_voip()` method execution
  - `action_call_lead()` method execution
  - API endpoint `/voip24h/click_to_dial`
  - Real-time call status updates

**Implementation Pattern:**
```python
# In res.partner extension
def action_call_voip(self):
    """Initiate VoIP call (click-to-dial)"""
    config = self.env['voip.config'].get_active_config()

    # Check if call functionality is enabled
    if not config or not config.enable_call_functionality or not config.enable_outgoing_calls:
        raise UserError(_('Outgoing calls are disabled. Please contact your administrator.'))

    # Proceed with click-to-dial
    # ...
```

```xml
<!-- In res.partner form view -->
<button name="action_call_voip"
        type="object"
        string="📞 Call"
        class="btn-primary"
        invisible="not voip_config.enable_call_functionality or not voip_config.enable_outgoing_calls"/>
```

```javascript
// In call_popup_service.js
setup() {
    // Subscribe to bus notifications only if popups are enabled
    this.busService = useService('bus_service');

    const config = await this.rpc('/voip24h/get_config');
    if (config.enable_call_functionality && config.enable_incoming_call_popups) {
        this.busService.addEventListener('notification', this.onNotification.bind(this));
    }
}
```

**Configuration UI:**
- Place in separate "Call Functionality" tab in configuration form
- Show warning when disabling: "Users will not be able to make or receive calls. Data collection will continue."
- Add info box explaining what remains active when disabled

---

## 12. Testing Scenarios

### Unit Tests
- Phone number normalization
- Auto-matching logic
- Duration calculations
- Token refresh

### Integration Tests
- API authentication
- CDR sync
- Webhook processing
- Recording download

### UI Tests
- Dashboard filters
- Click-to-dial
- Call popup display
- Timeline view rendering

### Call Functionality Control Tests
- **Scenario 1: Master Switch Disabled**
  - Verify click-to-dial buttons are hidden on contact/lead forms
  - Verify incoming call popups do not appear
  - Verify call log sync continues normally
  - Verify dashboard and analytics remain accessible
  - Verify recordings can still be played

- **Scenario 2: Master Switch Enabled, Outgoing Disabled**
  - Verify click-to-dial buttons are hidden
  - Verify incoming call popups still work
  - Verify call log sync continues

- **Scenario 3: Master Switch Enabled, Incoming Disabled**
  - Verify click-to-dial buttons work
  - Verify incoming call popups do not appear
  - Verify call logs for incoming calls are still created

- **Scenario 4: All Features Enabled**
  - Verify full functionality
  - Verify configuration UI shows correct status

---

## 13. Documentation Requirements

### User Documentation
- Setup guide (API credentials, webhook config)
- Dashboard usage
- Click-to-dial instructions
- Call log management

### Technical Documentation
- API integration guide
- Webhook event reference
- Data model documentation
- Customization guide

---

## 14. Future Enhancements (Phase 2)

- **AI-powered call analytics:** Sentiment analysis, keyword detection
- **Call queue management:** Real-time queue stats, agent assignment
- **IVR integration:** Track IVR paths and outcomes
- **SMS integration:** If VoIP24h supports SMS
- **Mobile app:** React Native SDK integration
- **Predictive dialing:** AI-suggested next calls
- **Call scripts:** Pop-up call scripts for agents
- **Multi-language:** Vietnamese and English support

---

## Success Criteria

✅ **API Integration:** Successfully authenticate and fetch call logs from VoIP24h
✅ **Data Sync:** Automatic CDR synchronization every 15 minutes
✅ **Real-time:** Webhook notifications working with <2 second response
✅ **Contact Matching:** Auto-match 80%+ of calls to existing contacts
✅ **Recording Access:** Download and play call recordings
✅ **Dashboard:** Professional analytics dashboard with filters and KPIs
✅ **Click-to-Dial:** Initiate calls from contact/lead forms
✅ **Activity Creation:** Auto-create follow-up activities for missed calls
✅ **Call Functionality Control:** Master switch to enable/disable calling features while maintaining data collection
✅ **Granular Controls:** Separate toggles for outgoing calls and incoming popups
✅ **UI/UX:** Modern, responsive interface matching health module design standards
✅ **Performance:** Handle 1000+ calls per day without performance degradation

---

## Sources & References

- [VoIP24h API Integration Guide](https://voip24h.vn/api-tong-dai-voip/)
- [VoIP24h Technical Documentation](https://docs-sdk.voip24h.vn/)
- [Odoo VoIP Documentation](https://www.odoo.com/documentation/18.0/applications/productivity/voip.html)
- [Nuacom Odoo Integration](https://nuacom.com/integrations/odoo-crm/)
- [CloudTalk Odoo Integration](https://www.cloudtalk.io/odoo/)
- [VoIPstudio API Documentation](https://voipstudio.com/docs/api/introduction/)

---

**End of Implementation Plan**

This plan provides a comprehensive blueprint for implementing the health_voip24h module following established patterns from health_zalo, health_fieldservice, and health_base modules while delivering modern UI/UX and robust VoIP24h API integration.
