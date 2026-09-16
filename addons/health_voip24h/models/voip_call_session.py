# -*- coding: utf-8 -*-
"""One customer interaction, its legs, and the exact provider names for both.

A call is not a row. A single customer interaction can be several PBX legs
(a ring group rings four extensions; a transfer creates another leg; each may
produce its own final CDR), and the provider names it differently in each feed.
So three models:

* ``voip.call.session`` — the interaction a human would describe as "the call".
  It is also the callback work queue: there is deliberately no second callback
  model, because two places to record "we still owe this person a ring back"
  eventually disagree.
* ``voip.call.leg`` — one PBX leg. Legs are evidence, never merged away to
  make a dashboard count look tidy.
* ``voip.call.identity`` — the exact provider identifiers, each in its own
  namespace. ``id``, ``callid``, ``uniqueid`` and ``linkedid`` are four
  different things and the legacy ``call_id`` column could not safely mean all
  four; keeping them apart is what makes cross-feed reconciliation exact
  instead of hopeful.
"""

import logging
import uuid

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VoIPCallSession(models.Model):
    _name = 'voip.call.session'
    _description = 'VoIP Call (interaction)'
    _order = 'started_at desc, id desc'
    _rec_name = 'display_name_c'
    _inherit = ['mail.thread']

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_call_session_uuid_uidx
            ON voip_call_session (session_uuid)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS voip_call_session_callback_idx
            ON voip_call_session (company_id, callback_state, callback_due_at)
            WHERE callback_state = 'due'
        """)

    session_uuid = fields.Char(string='Reference', required=True, index=True,
                               readonly=True, copy=False,
                               default=lambda self: str(uuid.uuid4()))
    voip_config_id = fields.Many2one('voip.config', string='Connection',
                                     required=True, ondelete='cascade',
                                     index=True)
    company_id = fields.Many2one('res.company',
                                 related='voip_config_id.company_id',
                                 store=True, index=True)

    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('internal', 'Internal'),
        ('unknown', 'Not known'),
    ], string='Direction', required=True, default='unknown', index=True)

    external_peer_raw = fields.Char(
        string='Other Party (as dialled)',
        help='Exactly what the phone system reported. Never rewritten.')
    external_peer_key = fields.Char(
        string='Other Party (matching key)', index=True,
        help='The 0xxxxxxxxx form used to match contacts, when the number is '
             'a Vietnamese one.')
    external_peer_e164 = fields.Char(
        string='Other Party (international)', index=True,
        help='The +84… form, filled only when the country could be '
             'established. Used for cross-system matching, never for dialling.')
    is_anonymous = fields.Boolean(
        string='Number Withheld',
        help='The caller withheld their number. This is one session per call, '
             'never a shared “anonymous” contact.')

    did = fields.Char(string='Hotline / DID')
    extension_id = fields.Many2one('voip.extension', string='Extension',
                                   index=True)

    partner_id = fields.Many2one('res.partner', string='Contact/Patient',
                                 index=True, tracking=True)
    lead_id = fields.Many2one('crm.lead', string='Lead', index=True,
                              tracking=True)
    match_state = fields.Selection([
        ('unmatched', 'Not matched'),
        ('auto', 'Matched automatically'),
        ('ambiguous', 'Several possible people'),
        ('manual', 'Matched by a person'),
        ('internal', 'Internal call'),
    ], string='Contact Match', default='unmatched', required=True, index=True)
    match_candidate_count = fields.Integer(string='Possible Matches', default=0)

    live_state = fields.Selection([
        ('unknown', 'Not known'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('ended_pending_cdr', 'Ended, record pending'),
        ('final', 'Complete'),
        ('stale_unconfirmed', 'No ending recorded'),
    ], string='Call State', default='unknown', required=True, index=True,
        tracking=True)
    is_final = fields.Boolean(string='Settled', default=False, index=True)
    finalised_at = fields.Datetime(readonly=True)

    outcome = fields.Selection([
        ('answered', 'Answered'),
        ('no_answer', 'No answer'),
        ('busy', 'Busy'),
        ('failed', 'Failed'),
        ('unknown', 'Not known'),
    ], string='Outcome', default='unknown', required=True, index=True)

    started_at = fields.Datetime(string='Started', index=True)
    answered_at = fields.Datetime(string='Answered')
    ended_at = fields.Datetime(string='Ended')
    talk_seconds = fields.Integer(string='Talk Time (seconds)')
    total_seconds = fields.Integer(string='Total Time (seconds)')
    duration_display = fields.Char(compute='_compute_duration_display')

    leg_ids = fields.One2many('voip.call.leg', 'session_id', string='Legs')
    leg_count = fields.Integer(compute='_compute_counts')
    log_ids = fields.One2many('voip.call.log', 'session_id',
                              string='Final Records')
    log_count = fields.Integer(compute='_compute_counts')
    identity_ids = fields.One2many('voip.call.identity', 'session_id',
                                   string='Provider References')
    event_ids = fields.One2many('voip.call.event', 'session_id',
                                string='Phone System Messages')

    # ------------------------------------------------------------------
    # Callback work queue
    # ------------------------------------------------------------------
    callback_state = fields.Selection([
        ('none', 'Not needed'),
        ('due', 'Call back due'),
        ('resolved', 'Called back'),
        ('cancelled', 'Cancelled'),
    ], string='Call Back', default='none', required=True, index=True,
        tracking=True)
    callback_owner_id = fields.Many2one('res.users', string='Call Back Owner',
                                        index=True, tracking=True)
    callback_due_at = fields.Datetime(string='Call Back By', index=True)
    callback_resolved_at = fields.Datetime(readonly=True)
    callback_resolved_by = fields.Many2one('res.users', readonly=True)
    callback_resolution = fields.Selection([
        ('answered', 'We reached them'),
        ('manual', 'Closed by a person'),
        ('superseded', 'They rang again and we answered'),
    ], string='Resolution')
    callback_attempts = fields.Integer(string='Attempts', default=0)
    callback_resolved_by_session_id = fields.Many2one(
        'voip.call.session', string='Resolved By Call', ondelete='set null')
    activity_id = fields.Many2one('mail.activity', string='Task',
                                  ondelete='set null', readonly=True)

    # ------------------------------------------------------------------
    # Staff work — deliberately separate from the telephony outcome
    # ------------------------------------------------------------------
    notes = fields.Text(string='Call Notes', tracking=True)
    business_outcome = fields.Selection([
        ('service_booked', 'Service booked'),
        ('follow_up_required', 'Follow-up required'),
        ('information_provided', 'Information provided'),
        ('complaint', 'Complaint'),
        ('no_action', 'No action required'),
    ], string='Result', tracking=True)
    wrap_up_state = fields.Selection([
        ('none', 'Nothing to do'),
        ('pending', 'Needs writing up'),
        ('done', 'Written up'),
    ], string='Write-up', default='none', required=True)

    data_quality_state = fields.Selection([
        ('ok', 'Consistent'),
        ('conflict', 'Sources disagree'),
        ('incomplete', 'Missing information'),
    ], string='Data Quality', default='ok', required=True, index=True)
    data_quality_note = fields.Text(string='Data Quality Detail')

    projection_version = fields.Integer(default=0, readonly=True,
                                        help='Bumped on every meaningful '
                                             'change so notifications and the '
                                             'Care Command projection can be '
                                             'made idempotent.')
    care_watermark = fields.Datetime(
        readonly=True,
        help='The event time of the last change already projected into Care '
             'Command. A late, older record cannot reopen newer work.')

    display_name_c = fields.Char(compute='_compute_display_name_c', store=True)

    # ==================================================================

    @api.depends('external_peer_key', 'external_peer_raw', 'partner_id',
                 'lead_id', 'is_anonymous')
    def _compute_display_name_c(self):
        for rec in self:
            if rec.partner_id:
                rec.display_name_c = rec.partner_id.display_name
            elif rec.lead_id:
                rec.display_name_c = rec.lead_id.name
            elif rec.is_anonymous:
                rec.display_name_c = _('Number withheld')
            else:
                rec.display_name_c = (rec.external_peer_key
                                      or rec.external_peer_raw
                                      or _('Unknown caller'))

    @api.depends('total_seconds', 'talk_seconds')
    def _compute_duration_display(self):
        for rec in self:
            seconds = rec.total_seconds or 0
            hours, rest = divmod(seconds, 3600)
            minutes, secs = divmod(rest, 60)
            rec.duration_display = (
                '%02d:%02d:%02d' % (hours, minutes, secs) if hours
                else '%02d:%02d' % (minutes, secs))

    @api.depends('leg_ids', 'log_ids')
    def _compute_counts(self):
        for rec in self:
            rec.leg_count = len(rec.leg_ids)
            rec.log_count = len(rec.log_ids)

    # ==================================================================
    # Identity
    # ==================================================================

    def _add_identity(self, namespace, value):
        """Record one exact provider name for this session. Idempotent."""
        self.ensure_one()
        if not value:
            return self.env['voip.call.identity']
        return self.env['voip.call.identity']._register_reference(
            self.voip_config_id, namespace, value, session=self)

    @api.model
    def _find_by_identity(self, config, namespace, value):
        identity = self.env['voip.call.identity'].sudo().search([
            ('voip_config_id', '=', config.id),
            ('namespace', '=', namespace),
            ('value', '=', value),
        ], limit=1)
        return identity.session_id

    # ==================================================================
    # State reduction
    # ==================================================================

    # Ranked so a late Ring can never reopen a settled call and terminal
    # evidence arriving first is not undone by an intermediate event.
    _STATE_RANK = {
        'unknown': 0,
        'ringing': 1,
        'answered': 2,
        'ended_pending_cdr': 3,
        'stale_unconfirmed': 3,
        'final': 4,
    }

    def _advance_state(self, new_state):
        """Move forward only. Returns True when the state actually changed."""
        self.ensure_one()
        current = self._STATE_RANK.get(self.live_state, 0)
        proposed = self._STATE_RANK.get(new_state, 0)
        if proposed <= current:
            return False
        self.write({'live_state': new_state})
        return True

    def _bump_projection(self):
        self.ensure_one()
        self.sudo().write({'projection_version': (self.projection_version or 0) + 1})
        return self.projection_version

    # ==================================================================
    # Callback obligations
    # ==================================================================

    def _open_callback(self, due_at=None, owner=None):
        """Put this interaction on the call-back queue. Idempotent.

        An interaction already resolved is NOT reopened: a late record about
        an old call must not undo work somebody has already done.
        """
        self.ensure_one()
        if self.callback_state in ('resolved', 'cancelled'):
            return False
        vals = {'callback_state': 'due'}
        if due_at and not self.callback_due_at:
            vals['callback_due_at'] = due_at
        if owner and not self.callback_owner_id:
            vals['callback_owner_id'] = owner.id
        self.write(vals)
        return True

    def _resolve_callback(self, resolution, by_user=None, by_session=None):
        self.ensure_one()
        if self.callback_state != 'due':
            return False
        self.write({
            'callback_state': 'resolved',
            'callback_resolution': resolution,
            'callback_resolved_at': fields.Datetime.now(),
            'callback_resolved_by': (by_user or self.env.user).id,
            'callback_resolved_by_session_id': by_session.id if by_session else False,
        })
        if self.activity_id:
            try:
                self.activity_id.sudo().action_done()
            except Exception:  # noqa: BLE001 — an activity already gone is fine
                _logger.debug('Callback activity %s could not be completed',
                              self.activity_id.id)
        return True

    def action_mark_called_back(self):
        """A person says they have dealt with this. Recorded as such."""
        self.ensure_one()
        self._check_can_work()
        if self.callback_state != 'due':
            raise UserError(_('This call is not on the call-back list.'))
        self._resolve_callback('manual')
        self.message_post(body=_('%s marked this call back as done.')
                          % self.env.user.display_name)
        return True

    @api.model
    def _cron_finalise(self):
        """Settle calls whose legs ended but whose final record never came."""
        from ..services.event_reducer import finalise_stale_sessions
        return finalise_stale_sessions(self.env)

    def action_open_record(self):
        self.ensure_one()
        target = self.partner_id or self.lead_id
        if not target:
            raise UserError(_('This call is not linked to anyone yet.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': target._name,
            'res_id': target.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ==================================================================
    # Guarded staff updates
    # ==================================================================

    def _check_can_work(self):
        """Staff may write notes and outcomes. They may not forge call facts.

        Every field a user can change through this path is a field a human
        owns. Provider evidence — times, durations, dispositions — is written
        only by the reducer, and :meth:`write` refuses it from a normal RPC.
        """
        self.ensure_one()
        if not self.env.user.has_group('health_voip24h.group_voip_user'):
            raise UserError(_('You do not have access to call records.'))
        if self.company_id and self.company_id not in self.env.user.company_ids:
            raise UserError(_('This call belongs to another company.'))

    _PROVIDER_OWNED = frozenset({
        'direction', 'external_peer_raw', 'external_peer_key',
        'external_peer_e164', 'did', 'live_state', 'is_final', 'finalised_at',
        'outcome', 'started_at', 'answered_at', 'ended_at', 'talk_seconds',
        'total_seconds', 'session_uuid', 'voip_config_id',
    })

    def write(self, vals):
        # §5.4 — uid 1 always runs as su, so an ``if not self.env.su`` guard
        # would be dead code for admin and in tests. The guard is therefore on
        # a deliberate context key that only the reducer sets.
        if not self.env.context.get('voip_reducer'):
            forged = self._PROVIDER_OWNED.intersection(vals)
            if forged:
                raise UserError(_(
                    'These call details come from the phone system and cannot '
                    'be edited here: %s') % ', '.join(sorted(forged)))
        return super().write(vals)

    def update_disposition(self, notes=None, business_outcome=None,
                           version=None):
        """The one staff-writable path, version-checked.

        The version check is what stops two agents' write-ups overwriting each
        other silently after a reconnect.
        """
        self.ensure_one()
        self._check_can_work()
        if version is not None and int(version) != self.projection_version:
            raise UserError(_(
                'This call was updated while you were writing. Reopen it and '
                'check before saving again.'))
        vals = {}
        if notes is not None:
            vals['notes'] = notes
        if business_outcome is not None:
            vals['business_outcome'] = business_outcome or False
        if vals:
            vals['wrap_up_state'] = 'done'
            self.write(vals)
            self._bump_projection()
        return {'ok': True, 'version': self.projection_version}


class VoIPCallLeg(models.Model):
    _name = 'voip.call.leg'
    _description = 'VoIP Call Leg'
    _order = 'ringing_at, id'

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_call_leg_uniqueid_uidx
            ON voip_call_leg (voip_config_id, provider_unique_id)
            WHERE provider_unique_id IS NOT NULL
        """)

    session_id = fields.Many2one('voip.call.session', string='Call',
                                 required=True, ondelete='cascade', index=True)
    voip_config_id = fields.Many2one('voip.config', string='Connection',
                                     required=True, ondelete='cascade',
                                     index=True)
    company_id = fields.Many2one('res.company',
                                 related='voip_config_id.company_id',
                                 store=True, index=True)

    provider_unique_id = fields.Char(string='Leg Reference', index=True)
    provider_linked_id = fields.Char(string='Group Reference', index=True)
    channel = fields.Char(string='Channel',
                          help='Diagnostic detail from the phone system.')
    extension_number = fields.Char(string='Extension')
    extension_id = fields.Many2one('voip.extension', string='Extension',
                                   index=True)

    ringing_at = fields.Datetime(string='Started Ringing')
    answered_at = fields.Datetime(string='Answered')
    ended_at = fields.Datetime(string='Ended')

    state = fields.Selection([
        ('unknown', 'Not known'),
        ('ringing', 'Ringing'),
        ('answered', 'Answered'),
        ('ended_pending_cdr', 'Ended, record pending'),
        ('final', 'Complete'),
    ], string='State', default='unknown', required=True, index=True)
    disposition_raw = fields.Char(string='Raw Outcome')
    outcome = fields.Selection([
        ('answered', 'Answered'),
        ('no_answer', 'No answer'),
        ('busy', 'Busy'),
        ('failed', 'Failed'),
        ('unknown', 'Not known'),
    ], string='Outcome', default='unknown', required=True)

    talk_seconds = fields.Integer(string='Talk Time (seconds)')
    total_seconds = fields.Integer(string='Total Time (seconds)')
    source_event_id = fields.Many2one('voip.call.event', string='From Message',
                                      ondelete='set null')

    _STATE_RANK = VoIPCallSession._STATE_RANK

    def _advance_state(self, new_state):
        self.ensure_one()
        if self._STATE_RANK.get(new_state, 0) <= self._STATE_RANK.get(self.state, 0):
            return False
        self.write({'state': new_state})
        return True


class VoIPCallIdentity(models.Model):
    """Exact provider identifiers, one namespace each.

    Uniqueness is asserted only for namespaces whose uniqueness has actually
    been established. ``cdr`` is the provider's own CDR id and is unique within
    a connection; ``uniqueid`` names one leg. ``callid`` and ``linkedid`` are
    deliberately NOT unique — in the vendor's own sample all three of
    ``uniqueid``, ``linkedid`` and ``callid`` carry the same value, which is
    exactly the sort of coincidence that a unique index would turn into a
    silent data loss.
    """
    _name = 'voip.call.identity'
    _description = 'VoIP Provider Reference'
    _order = 'id'

    UNIQUE_NAMESPACES = ('cdr', 'uniqueid')

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_call_identity_unique_ns_uidx
            ON voip_call_identity (voip_config_id, namespace, value)
            WHERE namespace IN ('cdr', 'uniqueid')
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS voip_call_identity_lookup_idx
            ON voip_call_identity (voip_config_id, namespace, value)
        """)

    voip_config_id = fields.Many2one('voip.config', required=True,
                                     ondelete='cascade', index=True)
    namespace = fields.Selection([
        ('cdr', 'Final record id'),
        ('callid', 'Call id'),
        ('uniqueid', 'Leg id'),
        ('linkedid', 'Group id'),
        ('sip_callid', 'Browser SIP call id'),
    ], string='Kind', required=True, index=True)
    value = fields.Char(required=True, index=True)
    session_id = fields.Many2one('voip.call.session', ondelete='cascade',
                                 index=True)
    leg_id = fields.Many2one('voip.call.leg', ondelete='set null')
    call_log_id = fields.Many2one('voip.call.log', ondelete='set null')

    @api.model
    def _register_reference(self, config, namespace, value, session=None,
                            leg=None, call_log=None):
        """Record one provider name. Idempotent.

        NOT called ``_register``: ``models.Model._register`` is an Odoo
        internal class attribute (it is the boolean that decides whether a
        model class joins the registry), so a method of that name shadows it
        and every call becomes ``True(...)`` — ``TypeError: 'bool' object is
        not callable``, raised nowhere near the definition. Found by the first
        live test run.
        """
        value = (value or '').strip()
        if not value:
            return self.browse()
        existing = self.sudo().search([
            ('voip_config_id', '=', config.id),
            ('namespace', '=', namespace),
            ('value', '=', value),
        ], limit=1)
        if existing:
            vals = {}
            if session and not existing.session_id:
                vals['session_id'] = session.id
            if leg and not existing.leg_id:
                vals['leg_id'] = leg.id
            if call_log and not existing.call_log_id:
                vals['call_log_id'] = call_log.id
            if vals:
                existing.write(vals)
            return existing
        try:
            with self.env.cr.savepoint():
                return self.sudo().create({
                    'voip_config_id': config.id,
                    'namespace': namespace,
                    'value': value,
                    'session_id': session.id if session else False,
                    'leg_id': leg.id if leg else False,
                    'call_log_id': call_log.id if call_log else False,
                })
        except Exception:  # noqa: BLE001 — concurrent registration
            return self.sudo().search([
                ('voip_config_id', '=', config.id),
                ('namespace', '=', namespace),
                ('value', '=', value),
            ], limit=1)
