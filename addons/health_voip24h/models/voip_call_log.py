# -*- coding: utf-8 -*-
"""The customer-facing final call record.

This model is deliberately conservative: it keeps every historical row exactly
as it was, and the new columns are additive. What changes is what it is allowed
to say.

* ``call_type`` and ``call_status`` gain an explicit ``unknown``. The old
  parser could not express "the phone system told us something we do not
  recognise", so it defaulted to ``answered``/``completed`` — an invented
  successful call. Unknown is now sayable, and is what gets said.
* The four provider identifiers live in four columns. ``call_id`` could not
  safely mean all of ``id``, ``callid``, ``uniqueid`` and ``linkedid`` at once;
  legacy values stay, and new rows carry a namespaced key (``cdr:…`` /
  ``state:…``) so a provider reference can never be mistaken for our own.
* Provider-owned facts refuse a normal RPC write. A VoIP user can add notes
  and an outcome; they cannot mint a completed call by writing to the model.
"""

import logging
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VoIPCallLog(models.Model):
    _name = 'voip.call.log'
    _description = 'VoIP Call Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'call_date desc, id desc'
    _rec_name = 'call_id'

    def init(self):
        # §5.1 — no _sql_constraints on Odoo 19.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                voip_call_log_callid_config_uidx
            ON voip_call_log (call_id, voip_config_id)
        """)
        # The exact identity of a final record within a connection. Partial,
        # because legacy rows and Feed-B-only rows have no provider CDR id.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                voip_call_log_provider_cdr_uidx
            ON voip_call_log (voip_config_id, provider_cdr_id)
            WHERE provider_cdr_id IS NOT NULL
        """)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    call_id = fields.Char(
        string='Reference', required=True, index=True, readonly=True,
        help='Our own reference. New records are namespaced (cdr:… or '
             'state:…) so they can never be confused with one of the phone '
             'system’s own identifiers.')
    provider_cdr_id = fields.Char(string='Phone System Record Id', index=True,
                                  readonly=True)
    provider_call_id = fields.Char(string='Phone System Call Id', index=True,
                                   readonly=True)
    provider_unique_id = fields.Char(string='Phone System Leg Id', index=True,
                                     readonly=True)
    provider_linked_id = fields.Char(string='Phone System Group Id',
                                     readonly=True)
    source_profile = fields.Selection([
        ('legacy', 'Before this integration'),
        ('feed_a', 'Completed-call call-back'),
        ('feed_b', 'Live-events call-back'),
        ('manual', 'Entered by a person'),
    ], string='Source', default='legacy', required=True, index=True,
        help='Historical rows stay labelled “Before this integration”. They '
             'are not relabelled as newly verified.')
    import_source = fields.Char(string='Import Source', readonly=True)

    session_id = fields.Many2one('voip.call.session', string='Call',
                                 ondelete='set null', index=True)
    voip_config_id = fields.Many2one(
        'voip.config', string='VoIP Configuration', required=True,
        ondelete='restrict', index=True)
    company_id = fields.Many2one(
        'res.company', related='voip_config_id.company_id', store=True,
        index=True)

    # ------------------------------------------------------------------
    # Call facts
    # ------------------------------------------------------------------
    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('internal', 'Internal'),
        ('unknown', 'Not known'),
    ], string='Direction', required=True, index=True, tracking=True,
        default='unknown')

    call_type = fields.Selection([
        ('answered', 'Answered'),
        ('missed', 'Missed'),
        ('abandoned', 'Abandoned'),
        ('voicemail', 'Voicemail'),
        ('failed', 'Failed'),
        ('busy', 'Busy'),
        ('unknown', 'Not known'),
    ], string='Call Type', required=True, index=True, tracking=True,
        default='unknown',
        help='“Not known” means the phone system sent an outcome we do not '
             'recognise. It is never guessed into a successful call.')

    call_status = fields.Selection([
        ('completed', 'Completed'),
        ('no_answer', 'No Answer'),
        ('busy', 'Busy'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('unknown', 'Not known'),
    ], string='Status', default='unknown')

    disposition_raw = fields.Char(string='Raw Outcome', readonly=True,
                                  help='Exactly what the phone system sent.')
    status_raw = fields.Char(string='Raw Status', readonly=True)

    caller_number = fields.Char(string='Caller Number', index=True)
    caller_number_normalized = fields.Char(
        string='Normalized Caller', index=True,
        compute='_compute_normalized_numbers', store=True)
    called_number = fields.Char(string='Called Number', index=True)
    called_number_normalized = fields.Char(
        string='Normalized Called', index=True,
        compute='_compute_normalized_numbers', store=True)
    external_peer_e164 = fields.Char(string='Other Party (international)',
                                     index=True)
    did = fields.Char(string='Hotline / DID', index=True)

    extension_id = fields.Many2one('voip.extension', string='Extension',
                                   index=True)
    extension_number = fields.Char(string='Extension Number')
    answered_by_extension = fields.Char(string='Answered By Extension')

    call_date = fields.Datetime(string='Call Date/Time', required=True,
                                index=True)
    start_time = fields.Datetime(string='Start Time')
    answer_time = fields.Datetime(string='Answer Time')
    end_time = fields.Datetime(string='End Time')
    timestamp_timezone = fields.Char(
        string='Times Read In', readonly=True,
        help='The time zone the phone system’s times were read in. Recorded '
             'so a later correction can tell a wrong zone from a wrong time.')
    synced_date = fields.Datetime(string='Synced On',
                                  default=fields.Datetime.now, readonly=True)

    duration_seconds = fields.Integer(string='Total Duration (seconds)',
                                      default=0)
    talk_duration_seconds = fields.Integer(string='Talk Duration (seconds)',
                                           default=0)
    wait_duration_seconds = fields.Integer(
        string='Wait Duration (seconds)', default=0,
        help='Derived: total minus talk time. Not a measured queue wait.')
    duration_display = fields.Char(string='Duration',
                                   compute='_compute_duration_display')

    hangup_cause = fields.Char(string='Note from the Phone System')
    call_quality_score = fields.Integer(string='Quality Score')

    is_final = fields.Boolean(string='Settled', default=False, index=True)
    finalised_at = fields.Datetime(readonly=True)
    data_quality_state = fields.Selection([
        ('ok', 'Consistent'),
        ('flagged', 'Something looks wrong'),
    ], string='Data Quality', default='ok', required=True, index=True)
    data_quality_note = fields.Text(string='Data Quality Detail')

    # ------------------------------------------------------------------
    # Recordings and CRM
    # ------------------------------------------------------------------
    has_recording = fields.Boolean(string='Has Recording', default=False,
                                   index=True)
    recording_ids = fields.One2many('voip.call.recording', 'call_log_id',
                                    string='Recordings')
    recording_count = fields.Integer(string='Recording Count',
                                     compute='_compute_recording_count')

    partner_id = fields.Many2one('res.partner', string='Contact/Patient',
                                 index=True, tracking=True)
    lead_id = fields.Many2one('crm.lead', string='Lead/Opportunity',
                              index=True, tracking=True)
    auto_matched = fields.Boolean(string='Auto-matched', default=False)
    match_confidence = fields.Selection([
        ('high', 'High'), ('medium', 'Medium'), ('low', 'Low'),
    ], string='Match Confidence')

    call_notes = fields.Text(string='Call Notes', tracking=True)
    call_outcome = fields.Selection([
        ('service_booked', 'Service Booked'),
        ('follow_up_required', 'Follow-up Required'),
        ('information_provided', 'Information Provided'),
        ('complaint', 'Complaint'),
        ('no_action', 'No Action Required'),
    ], string='Call Outcome', tracking=True)

    activity_id = fields.Many2one('mail.activity', string='Related Activity',
                                  readonly=True)
    activity_created = fields.Boolean(string='Activity Created', default=False)

    raw_data = fields.Text(string='Raw API Data', groups='base.group_system')

    # The existing REVIEW workflow. Not a telephony state and never was.
    state = fields.Selection([
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('processed', 'Processed'),
    ], string='Review State', default='new', tracking=True, required=True)

    # ==================================================================

    @api.depends('caller_number', 'called_number')
    def _compute_normalized_numbers(self):
        for log in self:
            log.caller_number_normalized = self._normalize_phone(log.caller_number)
            log.called_number_normalized = self._normalize_phone(log.called_number)

    def _normalize_phone(self, phone):
        if not phone:
            return False
        return re.sub(r'[^\d+]', '', phone)

    @api.depends('duration_seconds', 'talk_duration_seconds')
    def _compute_duration_display(self):
        for log in self:
            seconds = log.duration_seconds or 0
            hours, rest = divmod(seconds, 3600)
            minutes, secs = divmod(rest, 60)
            log.duration_display = ('%02d:%02d:%02d' % (hours, minutes, secs)
                                    if hours else '%02d:%02d' % (minutes, secs))

    @api.depends('recording_ids')
    def _compute_recording_count(self):
        for log in self:
            log.recording_count = len(log.recording_ids)

    # ==================================================================
    # Write protection
    # ==================================================================
    #
    # §5.4 — uid 1 always runs su and tests run as uid 1, so an
    # ``if not self.env.su`` guard would be dead code exactly where it matters.
    # The guard is therefore an explicit context key that only the reducer and
    # the legacy sync set, which is unconditional for everyone else.

    _PROVIDER_OWNED = frozenset({
        'call_id', 'provider_cdr_id', 'provider_call_id', 'provider_unique_id',
        'provider_linked_id', 'source_profile', 'direction', 'call_type',
        'call_status', 'disposition_raw', 'status_raw', 'caller_number',
        'called_number', 'did', 'call_date', 'start_time', 'answer_time',
        'end_time', 'duration_seconds', 'talk_duration_seconds',
        'wait_duration_seconds', 'is_final', 'finalised_at',
        'timestamp_timezone', 'voip_config_id',
    })

    def write(self, vals):
        if not self.env.context.get('voip_reducer'):
            forged = self._PROVIDER_OWNED.intersection(vals)
            if forged:
                raise UserError(_(
                    'These details come from the phone system and cannot be '
                    'edited: %s') % ', '.join(sorted(forged)))
        return super().write(vals)

    # ==================================================================
    # Actions
    # ==================================================================

    def action_match_contact(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Match to Contact'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [],
            'context': {'default_phone': self.caller_number or self.called_number},
        }

    def action_create_lead(self):
        self.ensure_one()
        lead = self.env['crm.lead'].create({
            'name': _('Call — %s') % (self.caller_number or self.called_number
                                      or self.call_id),
            'phone': (self.caller_number if self.direction == 'incoming'
                      else self.called_number),
            'description': _('Call on %(date)s\nDuration: %(duration)s',
                             date=self.call_date, duration=self.duration_display),
            'voip_call_log_ids': [(4, self.id)],
        })
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
        self.ensure_one()
        if not self.partner_id and not self.lead_id:
            raise UserError(_(
                'Match this call to a contact or lead first.'))
        target = self.partner_id or self.lead_id
        activity = target.activity_schedule(
            'mail.mail_activity_data_call',
            date_deadline=fields.Date.context_today(self.env.user),
            summary=_('Follow up on call — %s') % self.duration_display,
            note=self.call_notes or False,
            user_id=self.env.user.id,
        )
        self.write({'activity_id': activity.id, 'activity_created': True})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Activity Created'),
            'res_model': 'mail.activity',
            'res_id': activity.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_play_recording(self):
        self.ensure_one()
        if not self.recording_ids:
            raise UserError(_('No recording is available for this call.'))
        return self.recording_ids[0].action_play_recording()

    def action_open_session(self):
        self.ensure_one()
        if not self.session_id:
            raise UserError(_('This record is not linked to a call yet.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'voip.call.session',
            'res_id': self.session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ==================================================================
    # Matching (kept for legacy callers)
    # ==================================================================

    @api.model
    def auto_match_contact_from_phone(self, phone_number):
        """Legacy helper, now company-scoped and ambiguity-aware.

        Returns a single partner ONLY when exactly one matches. The previous
        version returned the first hit of a ``like`` search on the last nine
        digits, which is how a call gets filed against whichever patient
        happened to be created first.
        """
        if not phone_number:
            return False
        from ..services import phone_ident
        key = phone_ident.matching_key(phone_number)
        if not key:
            return False
        company = self.env.company
        partners = self.env['res.partner'].search([
            '&', '|', ('company_id', '=', False), ('company_id', '=', company.id),
            '|', ('mobile', '=', key), ('phone', '=', key),
        ], limit=2)
        return partners if len(partners) == 1 else False

    @api.model
    def cron_create_missed_call_activities(self):
        """Legacy cron. Now a no-op wherever the session queue owns the work.

        Two independent creators of the same task is how a clinic ends up with
        two call-back activities for one missed call (the bridge created one,
        this created another). The session model is the single owner now; this
        only covers rows that predate it.
        """
        missed = self.search([
            ('call_type', '=', 'missed'),
            ('activity_created', '=', False),
            ('session_id', '=', False),
            ('state', '=', 'new'),
            ('call_date', '>=', fields.Datetime.subtract(
                fields.Datetime.now(), days=1)),
        ], limit=200)
        for call in missed:
            if not (call.partner_id or call.lead_id):
                continue
            try:
                with self.env.cr.savepoint():
                    call.action_create_activity()
            except Exception as exc:  # noqa: BLE001
                _logger.error('Failed to create activity for call %s: %s',
                              call.call_id, exc)
