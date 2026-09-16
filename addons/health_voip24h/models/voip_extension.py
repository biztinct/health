# -*- coding: utf-8 -*-

import logging
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# What a dial string may contain once normalised, before it reaches the SDK.
_DIALABLE = re.compile(r'^\+?[0-9]{2,20}$')


class VoIPExtension(models.Model):
    """One PBX extension, its SIP credentials and who may use it.

    The SIP password is the credential that lets a browser register against
    the PBX. With the documented SDK it necessarily becomes readable by the
    owning browser at registration time — ``registerSip(host, number,
    password)`` takes it in clear. This model does not pretend otherwise. What
    it does is keep the password encrypted at rest, hand it out only to the
    one user the extension is assigned to, over an authenticated no-store
    endpoint, and never expose it through a record read, an export or a
    generic RPC (it is stored in an encrypted column with no plaintext field
    to read).
    """
    _name = 'voip.extension'
    _description = 'VoIP Extension/Line'
    _order = 'extension_number'

    def init(self):
        # §5.1 — no _sql_constraints on Odoo 19.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_extension_number_config_uidx
            ON voip_extension (voip_config_id, extension_number)
        """)
        # One browser-enabled extension per user per config: two would mean
        # two SIP registrations racing for the same incoming call.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_extension_user_config_uidx
            ON voip_extension (voip_config_id, user_id)
            WHERE user_id IS NOT NULL AND browser_enabled
        """)

    name = fields.Char(string='Extension Name', required=True)
    extension_number = fields.Char(string='Extension Number', required=True,
                                   index=True)
    extension_type = fields.Selection([
        ('internal', 'Internal Extension'),
        ('external', 'External Line'),
        ('queue', 'Call Queue'),
        ('ivr', 'IVR'),
    ], string='Type', default='internal', required=True)

    user_id = fields.Many2one('res.users', string='Assigned User', index=True)
    employee_id = fields.Many2one('hr.employee', string='Assigned Employee')

    voip_config_id = fields.Many2one(
        'voip.config', string='VoIP Configuration', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', related='voip_config_id.company_id', store=True,
        index=True)

    # ------------------------------------------------------------------
    # SIP registration
    # ------------------------------------------------------------------
    sip_host = fields.Char(
        string='SIP Server',
        help='Left empty, the connection’s default server is used.')
    sip_username = fields.Char(
        string='SIP Username',
        help='Usually the extension number. Ask the supplier if unsure.')
    sip_password_enc = fields.Char(string='SIP Password (encrypted)',
                                   groups='base.group_system', copy=False)
    sip_password_set = fields.Boolean(string='SIP Password Stored',
                                      compute='_compute_sip_password_set',
                                      store=True)
    # Write-only: computed to blank, encrypted by the inverse. A plain stored
    # column would put the plaintext password in the database (and in every
    # backup) for as long as it took the next write to clear it.
    sip_password_input = fields.Char(
        string='SIP Password',
        compute='_compute_sip_password_input',
        inverse='_inverse_sip_password_input',
        store=False,
        groups='base.group_system',
        help='Typed once. It is encrypted immediately and never shown again.')

    browser_enabled = fields.Boolean(
        string='Allow the Browser Phone', default=False,
        help='Lets the assigned user register this extension in their '
             'browser and take calls there.')
    allow_incoming = fields.Boolean(string='Allow Incoming Calls', default=True)
    allow_outgoing = fields.Boolean(string='Allow Outgoing Calls', default=True)
    allow_transfer = fields.Boolean(
        string='Allow Transfer', default=False,
        help='Stays off until transfer has been tested with the supplier — '
             'what their transfer does on failure is not documented.')
    allow_dtmf = fields.Boolean(
        string='Allow Keypad Tones', default=False,
        help='The supplier documents that tones can be sent only once per '
             'call. Until that is clarified the keypad stays hidden.')
    allow_international = fields.Boolean(string='Allow International Calls',
                                         default=False)
    destination_allowlist = fields.Text(
        string='Allowed Destinations',
        help='Optional. One prefix per line, for example 09 or +84. Empty '
             'means any Vietnamese number is allowed.')
    transfer_allowlist = fields.Text(
        string='Allowed Transfer Targets',
        help='One extension or number per line. Empty means transfer targets '
             'are limited to other extensions on this connection.')

    caller_id_did = fields.Char(
        string='Outgoing Number Shown',
        help='The hotline number shown to the person being called. It must be '
             'a number the supplier has approved for this account.')
    hotline_did = fields.Char(string='Hotline / DID',
                              help='Incoming number routed to this extension.')
    team_id = fields.Many2one('crm.team', string='Team')

    record_calls = fields.Boolean(string='Record Calls', default=True)
    active = fields.Boolean(default=True)

    total_calls = fields.Integer(string='Total Calls', compute='_compute_call_stats')
    missed_calls = fields.Integer(string='Missed Calls', compute='_compute_call_stats')
    lease_ids = fields.One2many('voip.client.lease', 'extension_id',
                                string='Browser Sessions')
    live_state = fields.Char(string='Browser State',
                             compute='_compute_live_state')

    # ==================================================================

    @api.depends('sip_password_enc')
    def _compute_sip_password_set(self):
        for ext in self:
            ext.sip_password_set = bool(ext.sudo().sip_password_enc)

    def _compute_call_stats(self):
        Log = self.env['voip.call.log']
        counts = dict(Log._read_group(
            [('extension_id', 'in', self.ids)],
            groupby=['extension_id'], aggregates=['__count']))
        missed = dict(Log._read_group(
            [('extension_id', 'in', self.ids), ('call_type', '=', 'missed')],
            groupby=['extension_id'], aggregates=['__count']))
        for ext in self:
            ext.total_calls = counts.get(ext, 0)
            ext.missed_calls = missed.get(ext, 0)

    def _compute_live_state(self):
        Lease = self.env['voip.client.lease'].sudo()
        now = fields.Datetime.now()
        for ext in self:
            lease = Lease.search([
                ('extension_id', '=', ext.id),
                ('expires_at', '>', now),
                ('released', '=', False),
            ], order='id desc', limit=1)
            if not lease:
                ext.live_state = _('Not signed in')
            else:
                ext.live_state = _('%s (in the browser)') % (
                    lease.user_id.display_name or '')

    # ==================================================================
    # Credential handling
    # ==================================================================

    def _compute_sip_password_input(self):
        # A stored secret is never handed back, not even to an administrator
        # reading the form. Setting it is the only supported direction.
        for ext in self:
            ext.sip_password_input = False

    def _inverse_sip_password_input(self):
        for ext in self:
            if ext.sip_password_input:
                ext._set_sip_password(ext.sip_password_input)

    # The encrypted column is the store, and the cipher is the only way in.
    # A context key marks the one write that is allowed to set it, so the
    # guard cannot be talked past by an RPC that simply names the column.
    _SECRET_WRITE_CTX = 'voip_sip_secret_write'

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get(self._SECRET_WRITE_CTX):
            for vals in vals_list:
                vals.pop('sip_password_enc', None)
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get(self._SECRET_WRITE_CTX):
            vals.pop('sip_password_enc', None)
        return super().write(vals)

    def _set_sip_password(self, password):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise UserError(_('Only an administrator can set a SIP password.'))
        from ..services import voip_crypto
        # Without the context key this write would strip its own value in the
        # override above — the guard was eating the one write it exists to
        # permit. (Found by the first live test run.)
        self.sudo().with_context(**{self._SECRET_WRITE_CTX: True}).write({
            'sip_password_enc': voip_crypto.encrypt(self.env, password) or False,
        })
        self.message_log_sip_change()

    def message_log_sip_change(self):
        """Audit trail without the secret. No chatter on this model, so the
        record goes to the config's chatter, where it is visible to the people
        who administer the connection."""
        for ext in self:
            if ext.voip_config_id:
                ext.voip_config_id.sudo().message_post(body=_(
                    'The SIP password for extension %(ext)s was changed by '
                    '%(user)s.', ext=ext.extension_number,
                    user=self.env.user.display_name))

    def _sip_credentials(self):
        """The bootstrap payload for the OWNING browser. Never logged.

        Returns None when anything is missing, so the caller shows a concrete
        "not set up" state rather than attempting a registration that cannot
        work.
        """
        self.ensure_one()
        from ..services import voip_crypto
        me = self.sudo()
        host = me.sip_host or me.voip_config_id.sip_host_default
        if not (host and me.sip_username and me.sip_password_enc):
            return None
        try:
            password = voip_crypto.decrypt(self.env, me.sip_password_enc)
        except ValueError:
            _logger.error('SIP password unreadable for extension %s', self.id)
            return None
        return {
            'sip_host': host,
            'sip_username': me.sip_username,
            'sip_password': password,
        }

    # ==================================================================
    # Destination policy
    # ==================================================================

    @api.constrains('caller_id_did')
    def _check_caller_id(self):
        for ext in self:
            if ext.caller_id_did and not _DIALABLE.match(
                    re.sub(r'[^\d+]', '', ext.caller_id_did)):
                raise ValidationError(_(
                    'The outgoing number shown must be a plain phone number.'))

    def _destination_allowed(self, dial_string):
        """Application-side destination policy.

        This is a policy check, not a spend control. The PBX is the only place
        that can actually stop a call being placed and billed; the UI must
        never imply otherwise.
        """
        self.ensure_one()
        number = (dial_string or '').strip()
        if not number:
            return False, _('No number to call.')
        if not _DIALABLE.match(number):
            return False, _('That does not look like a phone number.')
        if not self.allow_outgoing:
            return False, _('This extension is not allowed to make calls.')

        allowlist = [line.strip() for line in
                     (self.destination_allowlist or '').splitlines()
                     if line.strip()]
        if allowlist:
            if not any(number.startswith(prefix) for prefix in allowlist):
                return False, _('This extension is not allowed to call that '
                                'number.')
            return True, ''

        # No explicit list: Vietnamese numbers only unless international is on.
        is_international = number.startswith('+') and not number.startswith('+84')
        if is_international and not self.allow_international:
            return False, _('International calls are not enabled for this '
                            'extension.')
        return True, ''

    def _transfer_target_allowed(self, target):
        self.ensure_one()
        if not self.allow_transfer:
            return False, _('Transfer is not enabled for this extension.')
        target = (target or '').strip()
        if not target:
            return False, _('No transfer target given.')
        allowlist = [line.strip() for line in
                     (self.transfer_allowlist or '').splitlines()
                     if line.strip()]
        if allowlist:
            if target not in allowlist:
                return False, _('That transfer target is not allowed.')
            return True, ''
        peer = self.sudo().search([
            ('voip_config_id', '=', self.voip_config_id.id),
            ('extension_number', '=', target),
        ], limit=1)
        if not peer:
            return False, _('Transfer is limited to extensions on this phone '
                            'system until other targets are approved.')
        return True, ''
