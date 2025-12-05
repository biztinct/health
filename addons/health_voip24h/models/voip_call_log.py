# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import re
import logging

_logger = logging.getLogger(__name__)


class VoIPCallLog(models.Model):
    """
    VoIP Call Detail Records (CDR).

    Stores comprehensive call logs with metadata, timing, and CRM integration.
    """
    _name = 'voip.call.log'
    _description = 'VoIP Call Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'call_date desc, id desc'
    _rec_name = 'call_id'

    # Call Identification
    call_id = fields.Char(
        string='Call ID',
        required=True,
        index=True,
        readonly=True,
        help='Unique call identifier from VoIP24h',
    )
    voip_config_id = fields.Many2one(
        'voip.config',
        string='VoIP Configuration',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='voip_config_id.company_id',
        store=True,
        index=True,
    )

    # Call Details
    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('internal', 'Internal'),
    ], string='Direction', required=True, index=True, tracking=True)

    call_type = fields.Selection([
        ('answered', 'Answered'),
        ('missed', 'Missed'),
        ('abandoned', 'Abandoned'),
        ('voicemail', 'Voicemail'),
        ('failed', 'Failed'),
        ('busy', 'Busy'),
    ], string='Call Type', required=True, index=True, tracking=True)

    # Phone Numbers
    caller_number = fields.Char(
        string='Caller Number',
        index=True,
    )
    caller_number_normalized = fields.Char(
        string='Normalized Caller',
        index=True,
        compute='_compute_normalized_numbers',
        store=True,
    )
    called_number = fields.Char(
        string='Called Number',
        index=True,
    )
    called_number_normalized = fields.Char(
        string='Normalized Called',
        index=True,
        compute='_compute_normalized_numbers',
        store=True,
    )

    # Extensions
    extension_id = fields.Many2one(
        'voip.extension',
        string='Extension',
        index=True,
    )
    extension_number = fields.Char(
        string='Extension Number',
    )
    answered_by_extension = fields.Char(
        string='Answered By Extension',
    )

    # Timing
    call_date = fields.Datetime(
        string='Call Date/Time',
        required=True,
        index=True,
    )
    start_time = fields.Datetime(
        string='Start Time',
    )
    answer_time = fields.Datetime(
        string='Answer Time',
    )
    end_time = fields.Datetime(
        string='End Time',
    )

    duration_seconds = fields.Integer(
        string='Total Duration (seconds)',
        default=0,
    )
    talk_duration_seconds = fields.Integer(
        string='Talk Duration (seconds)',
        default=0,
        help='Duration after call was answered',
    )
    wait_duration_seconds = fields.Integer(
        string='Wait Duration (seconds)',
        default=0,
        help='Ring time before answer',
    )

    duration_display = fields.Char(
        string='Duration',
        compute='_compute_duration_display',
    )

    # Quality & Status
    call_status = fields.Selection([
        ('completed', 'Completed'),
        ('no_answer', 'No Answer'),
        ('busy', 'Busy'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='completed')

    hangup_cause = fields.Char(
        string='Hangup Cause',
    )
    call_quality_score = fields.Integer(
        string='Quality Score',
        help='1-5 scale',
    )

    # Recordings
    has_recording = fields.Boolean(
        string='Has Recording',
        default=False,
        index=True,
    )
    recording_ids = fields.One2many(
        'voip.call.recording',
        'call_log_id',
        string='Recordings',
    )
    recording_count = fields.Integer(
        string='Recording Count',
        compute='_compute_recording_count',
    )

    # CRM Integration
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact/Patient',
        index=True,
        tracking=True,
    )
    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead/Opportunity',
        index=True,
        tracking=True,
    )

    # Auto-matching fields
    auto_matched = fields.Boolean(
        string='Auto-matched',
        default=False,
        help='Was contact/lead matched automatically?',
    )
    match_confidence = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Match Confidence')

    # Call Notes & Outcome
    call_notes = fields.Text(
        string='Call Notes',
        tracking=True,
    )
    call_outcome = fields.Selection([
        ('service_booked', 'Service Booked'),
        ('follow_up_required', 'Follow-up Required'),
        ('information_provided', 'Information Provided'),
        ('complaint', 'Complaint'),
        ('no_action', 'No Action Required'),
    ], string='Call Outcome', tracking=True)

    # Activity Creation
    activity_id = fields.Many2one(
        'mail.activity',
        string='Related Activity',
        readonly=True,
    )
    activity_created = fields.Boolean(
        string='Activity Created',
        default=False,
    )

    # Metadata
    raw_data = fields.Text(
        string='Raw API Data',
        groups='base.group_system',
        help='Original JSON data from VoIP24h API',
    )
    synced_date = fields.Datetime(
        string='Synced On',
        default=fields.Datetime.now,
        readonly=True,
    )

    # State
    state = fields.Selection([
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('processed', 'Processed'),
    ], string='State', default='new', tracking=True, required=True)

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
        return re.sub(r'[^\d+]', '', phone)

    @api.depends('duration_seconds', 'talk_duration_seconds')
    def _compute_duration_display(self):
        """Format duration as HH:MM:SS or MM:SS"""
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
        self.ensure_one()
        # TODO: Open wizard to search and link contact
        return {
            'type': 'ir.actions.act_window',
            'name': _('Match to Contact'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [],
            'context': {'default_phone': self.caller_number or self.called_number},
        }

    def action_create_lead(self):
        """Create CRM lead from call log"""
        self.ensure_one()

        lead_vals = {
            'name': f"Call - {self.caller_number or self.called_number}",
            'phone': self.caller_number if self.direction == 'incoming' else self.called_number,
            'description': f"Call on {self.call_date}\nDuration: {self.duration_display}",
            'voip_call_log_ids': [(4, self.id)],
        }

        lead = self.env['crm.lead'].create(lead_vals)
        self.lead_id = lead.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('New Lead'),
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_activity(self):
        """Create follow-up activity for this call"""
        self.ensure_one()

        if not self.partner_id and not self.lead_id:
            raise UserError(_('Please match this call to a contact or lead first'))

        activity_vals = {
            'summary': f"Follow up on call - {self.duration_display}",
            'note': self.call_notes or f"Follow up on {self.call_type} call",
            'res_model_id': self.env['ir.model']._get('res.partner').id if self.partner_id else self.env['ir.model']._get('crm.lead').id,
            'res_id': self.partner_id.id if self.partner_id else self.lead_id.id,
            'user_id': self.env.user.id,
        }

        activity = self.env['mail.activity'].create(activity_vals)
        self.activity_id = activity.id
        self.activity_created = True

        return {
            'type': 'ir.actions.act_window',
            'name': _('Activity Created'),
            'res_model': 'mail.activity',
            'res_id': activity.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_play_recording(self):
        """Play call recording"""
        self.ensure_one()

        if not self.recording_ids:
            raise UserError(_('No recording available for this call'))

        recording = self.recording_ids[0]
        return recording.action_play_recording()

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
                ('mobile', 'ilike', normalized[-9:]),  # Last 9 digits
                ('phone', 'ilike', normalized[-9:]),
            ], limit=1)

        return partner

    @api.model
    def cron_create_missed_call_activities(self):
        """Cron job to create activities for missed calls"""
        missed_calls = self.search([
            ('call_type', '=', 'missed'),
            ('activity_created', '=', False),
            ('state', '=', 'new'),
            ('call_date', '>=', fields.Datetime.subtract(fields.Datetime.now(), days=1)),
        ])

        for call in missed_calls:
            if call.partner_id or call.lead_id:
                try:
                    call.action_create_activity()
                except Exception as e:
                    _logger.error(f'Failed to create activity for call {call.call_id}: {e}')
