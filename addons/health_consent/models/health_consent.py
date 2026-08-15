# -*- coding: utf-8 -*-
"""Client consent record (clinical spec §6.2.1).

FHIR Consent: status draft→draft, active→active, withdrawn/expired→
inactive. Consent types use the local CodeSystem `health19-consent-types`
verbatim (spec §6.9) — do not rename selection values.

The model is also the cross-cutting service API (spec §6.4 + DESIGN §7.1):
sharing features call `check_consent()` / `check_consents()` /
`require_consent()`. Every check writes an append-only
`health.consent.check.log` row as compliance evidence. Enforcement is
log-only-friendly: `check_consent` NEVER raises; `require_consent`
raises AccessError only when the `health_consent.enforce` config
parameter is truthy (default falsy = log-only).
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import str2bool

_logger = logging.getLogger(__name__)

# Consent capture / withdrawal is a front-line task (spec §6.3:
# receptionist, nurse+, manager+ — the operations desk included).
CAPTURE_GROUPS = (
    'health_base.group_healthcare_receptionist',
    'health_base.group_healthcare_nurse',
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_doctor',
    'health_base.group_healthcare_operations_manager',
    'health_base.group_healthcare_manager',
    'health_base.group_healthcare_admin',
    'health_base.group_healthcare_owner',
)

# Kinship grantor validation (health.client.relation Booleans):
# - service / emergency_treatment: the grantor decides on treatment →
#   can_make_medical_decisions required.
# - data_sharing: sharing medical information → can_make_medical_decisions
#   OR can_receive_medical_info.
# - photography / marketing: any active relation of the client.
MEDICAL_DECISION_TYPES = ('service', 'emergency_treatment')
MEDICAL_INFO_TYPES = ('data_sharing',)

# Evidence fields become immutable once the record leaves draft
# (active/withdrawn/expired consents are audit records — spec §6.3).
EVIDENCE_LOCKED_FIELDS = (
    'client_id', 'consent_type_id', 'scope_note', 'self_granted',
    'granted_by_relation_id', 'method', 'signature',
    'evidence_attachment_ids', 'verbal_witness_id', 'effective_date',
)


class HealthConsent(models.Model):
    _name = 'health.consent'
    _description = 'Client Consent'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Reference', readonly=True, copy=False,
        default=lambda self: _('New'),
        help='Consent reference (sequence health.consent, prefix CNS).')
    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        domain=[('is_patient', '=', True)], ondelete='restrict',
        index=True, tracking=True,
        help='FHIR Consent.patient')
    consent_type_id = fields.Many2one(
        'health.lookup.value',
        string='Consent Type',
        domain="[('category_code', '=', 'consent_type'), ('active', '=', True)]",
        ondelete='restrict',
        required=True,
        tracking=True,
        index=True,
        help='FHIR Consent.scope + category ')
    # Companion for view expressions and domains: an Odoo view attribute
    # (invisible=, decoration-, domain=) cannot traverse a many2one, and
    # this keeps every existing comparison a one-word change.
    consent_type_code = fields.Char(
        related='consent_type_id.code', string='Consent Type Code', readonly=True)
    scope_note = fields.Char(
        string='Scope / Limitations',
        help='Free-text narrowing, e.g. "photos for clinical record '
             'only, no social media". FHIR provision narrative.')
    self_granted = fields.Boolean(
        string='Granted by Client', default=True,
        help='The client consented personally.')
    granted_by_relation_id = fields.Many2one(
        'health.client.relation', string='Granted By (Relation)',
        domain="[('client_id', '=', client_id)]",
        help='Kinship grantor when the client did not consent '
             'personally. FHIR performer + relationship.')
    granted_by_partner_id = fields.Many2one(
        related='granted_by_relation_id.representative_id',
        string='Grantor', store=True, readonly=True)
    granted_by_role = fields.Selection(
        related='granted_by_relation_id.role',
        string='Grantor Role', store=True, readonly=True)
    method = fields.Selection([
        ('verbal', 'Verbal'),
        ('written', 'Written (paper)'),
        ('digital_signature', 'Digital Signature'),
    ], required=True, tracking=True, default='verbal',
        help='Evidence class.')
    signature = fields.Binary(
        attachment=True, copy=False,
        help='Digital signature PNG (required for digital_signature '
             'on grant). FHIR sourceAttachment.')
    evidence_attachment_ids = fields.Many2many(
        'ir.attachment', 'health_consent_attachment_rel',
        'consent_id', 'attachment_id', string='Evidence', copy=False,
        help='Scanned form / photo (required for written on grant).')
    verbal_witness_id = fields.Many2one(
        'res.users', string='Verbal Witness', copy=False,
        help='Staff who heard the verbal consent '
             '(defaults to the current user for verbal method).')
    effective_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True,
        help='FHIR provision.period.start')
    expiry_date = fields.Date(
        tracking=True,
        help='FHIR provision.period.end (empty = indefinite).')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
    ], default='draft', required=True, tracking=True, index=True,
        copy=False,
        help='FHIR Consent.status: active→active, withdrawn→inactive '
             '(+ deny provision), expired→inactive, draft→draft.')
    withdrawal_date = fields.Date(readonly=True, copy=False)
    withdrawal_reason = fields.Char(copy=False)
    withdrawn_by_id = fields.Many2one(
        'res.users', readonly=True, copy=False)
    notes = fields.Text()
    client_mutation_id = fields.Char(
        readonly=True, copy=False, index=True,
        help='PWA offline idempotency key — the server no-ops on '
             'replay (interop §6.7 append-only discipline).')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    # Kept for documentation parity with the spec — Odoo 19 no longer
    # materializes _sql_constraints; the check is enforced by
    # _check_expiry below (also called from create()).
    _sql_constraints = [
        ('expiry_check',
         'CHECK (expiry_date IS NULL OR expiry_date >= effective_date)',
         'Expiry must be after effective date.'),
    ]

    def init(self):
        # Odoo 19 does not materialize _sql_constraints — a partial
        # unique index backs the unique-if-set client_mutation_id
        # idempotency contract (health_forms client_uuid pattern).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_consent_client_mutation_uidx
            ON health_consent (client_mutation_id)
            WHERE client_mutation_id IS NOT NULL
              AND client_mutation_id != ''
        """)

    # ------------------------------------------------------------------
    # Computes / onchange
    # ------------------------------------------------------------------
    @api.depends('client_id.name', 'consent_type_id', 'name')
    def _compute_display_name(self):
        for consent in self:
            if consent.client_id and consent.consent_type_id:
                consent.display_name = '%s — %s' % (
                    consent.client_id.name,
                    consent.consent_type_id.name or '')
            else:
                consent.display_name = consent.name or _('New')

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    @api.onchange('client_id')
    def _onchange_client_id(self):
        # Grantor picker only offers relations of the selected client.
        if (self.granted_by_relation_id
                and self.granted_by_relation_id.client_id
                != self.client_id):
            self.granted_by_relation_id = False

    @api.onchange('method')
    def _onchange_method(self):
        if self.method == 'verbal' and not self.verbal_witness_id:
            self.verbal_witness_id = self.env.user

    # ------------------------------------------------------------------
    # Constraints (also enforced from create() — Odoo 19 gotcha:
    # @api.constrains does not fire on create when none of the
    # constrained fields are in vals).
    # ------------------------------------------------------------------
    @api.constrains('effective_date', 'expiry_date')
    def _check_expiry(self):
        for consent in self:
            if (consent.expiry_date and consent.effective_date
                    and consent.expiry_date < consent.effective_date):
                raise ValidationError(
                    _('Expiry must be after effective date.'))

    @api.constrains('state', 'client_id', 'consent_type_id')
    def _check_one_active(self):
        """At most one active consent per (client, type) — granting a
        new one supersedes the previous inside action_grant()."""
        for consent in self:
            if consent.state != 'active':
                continue
            duplicate = self.search([
                ('id', '!=', consent.id),
                ('client_id', '=', consent.client_id.id),
                ('consent_type_id', '=', consent.consent_type_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Client %(client)s already has an active '
                    '%(type)s consent (%(name)s). Grant supersedes it '
                    'automatically — withdraw it first when editing '
                    'manually.',
                    client=consent.client_id.name,
                    type=consent.consent_type_id.name or '',
                    name=duplicate.name))

    @api.constrains('self_granted', 'granted_by_relation_id',
                    'client_id', 'consent_type_id')
    def _check_grantor(self):
        """Grantor is the client (self_granted) or a kinship relation
        whose health.client.relation permissions allow it (spec §6.4 +
        health_crm kinship Booleans)."""
        for consent in self:
            if consent.self_granted:
                continue
            relation = consent.granted_by_relation_id
            if not relation:
                raise ValidationError(_(
                    'A consent not granted by the client personally '
                    'requires a grantor relation.'))
            if relation.client_id != consent.client_id:
                raise ValidationError(_(
                    'The grantor relation must belong to the consent '
                    'client.'))
            if not relation.active:
                raise ValidationError(_(
                    'The grantor relation is archived — only active '
                    'relations may grant consent.'))
            if (consent.consent_type_code in MEDICAL_DECISION_TYPES
                    and not relation.can_make_medical_decisions):
                raise ValidationError(_(
                    '%(rep)s cannot grant %(type)s consent: the '
                    'relation lacks "Can Make Medical Decisions".',
                    rep=relation.representative_id.name,
                    type=consent.consent_type_id.name or ''))
            if (consent.consent_type_code in MEDICAL_INFO_TYPES
                    and not (relation.can_make_medical_decisions
                             or relation.can_receive_medical_info)):
                raise ValidationError(_(
                    '%(rep)s cannot grant %(type)s consent: the '
                    'relation may neither make medical decisions nor '
                    'receive medical information.',
                    rep=relation.representative_id.name,
                    type=consent.consent_type_id.name or ''))

    @api.constrains('client_mutation_id')
    def _check_client_mutation_id(self):
        for consent in self:
            if not consent.client_mutation_id:
                continue
            duplicates = self.search_count([
                ('client_mutation_id', '=', consent.client_mutation_id),
                ('id', '!=', consent.id),
            ])
            if duplicates:
                raise ValidationError(_(
                    'A consent with this client mutation id already '
                    'exists (idempotency key must be unique).'))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seen_mutation_ids = set()
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'health.consent') or _('New')
            if (vals.get('method') == 'verbal'
                    and not vals.get('verbal_witness_id')):
                vals['verbal_witness_id'] = self.env.uid
            # Pre-check the idempotency key BEFORE the INSERT: the
            # partial unique index would otherwise raise a raw
            # IntegrityError and poison the transaction.
            mutation_id = vals.get('client_mutation_id')
            if mutation_id:
                if (mutation_id in seen_mutation_ids
                        or self.sudo().search_count([
                            ('client_mutation_id', '=', mutation_id)])):
                    raise ValidationError(_(
                        'A consent with this client mutation id '
                        'already exists (idempotency key must be '
                        'unique).'))
                seen_mutation_ids.add(mutation_id)
        consents = super().create(vals_list)
        # Constraints re-run explicitly (Odoo 19 create gotcha).
        consents._check_expiry()
        consents._check_one_active()
        consents._check_grantor()
        consents._check_client_mutation_id()
        return consents

    def write(self, vals):
        # Active/withdrawn/expired consents are immutable audit
        # records: evidence fields are locked after grant (spec §6.3,
        # acceptance #7). State-machine fields (state, withdrawal_*)
        # remain writable through the action methods.
        # No superuser escape: uid 1 always runs as su (Odoo forces
        # su=True for SUPERUSER_ID), so a su bypass would void the
        # evidence lock entirely (EVV append-only precedent).
        locked = [field for field in EVIDENCE_LOCKED_FIELDS
                  if field in vals]
        if locked:
            frozen = self.filtered(lambda c: c.state != 'draft')
            if frozen:
                raise UserError(_(
                    'Evidence fields (%(fields)s) are locked once a '
                    'consent leaves draft (%(names)s).',
                    fields=', '.join(locked),
                    names=', '.join(frozen.mapped('name'))))
        return super().write(vals)

    def unlink(self):
        # Draft records may be deleted; active/withdrawn/expired are
        # immutable audit records — draft-only unlink for everyone,
        # superuser included (spec §6.3/§6.6, acceptance #8; the ACL
        # additionally restricts unlink to the owner group).
        # Data-retention scripts archive (active=False) instead.
        frozen = self.filtered(lambda c: c.state != 'draft')
        if frozen:
            raise UserError(_(
                'Only draft consents can be deleted — '
                'active/withdrawn/expired consents are audit '
                'records (%s).') % ', '.join(frozen.mapped('name')))
        return super().unlink()

    # ------------------------------------------------------------------
    # State machine (spec §6.3) — defense in depth: buttons carry
    # groups=..., methods additionally check.
    # ------------------------------------------------------------------
    def _check_capture_allowed(self):
        user = self.env.user
        if self.env.su or user._is_admin():
            return
        if not any(user.has_group(group) for group in CAPTURE_GROUPS):
            raise AccessError(_(
                'Only front-line healthcare staff may capture or '
                'withdraw consents.'))

    def action_grant(self):
        """draft → active. Method-specific evidence + grantor guards,
        then supersede: the previous active consent of the same
        (client, type) is withdrawn with reason "Superseded", logged
        in both chatters (spec §6.2.1/§6.3)."""
        self.ensure_one()
        self._check_capture_allowed()
        if self.state != 'draft':
            raise UserError(_('Only a draft consent can be granted.'))
        if self.method == 'verbal' and not self.verbal_witness_id:
            raise UserError(_(
                'Verbal consent requires a witness (staff who heard '
                'the consent).'))
        if self.method == 'written' and not self.evidence_attachment_ids:
            raise UserError(_(
                'Written consent requires at least one evidence '
                'attachment (scanned form or photo).'))
        if self.method == 'digital_signature' and not self.signature:
            raise UserError(_(
                'Digital signature consent requires a signature '
                'image.'))
        # Grantor guard (also a constraint — re-checked here so the
        # grant fails loudly even on legacy rows).
        self._check_grantor()
        previous = self.search([
            ('id', '!=', self.id),
            ('client_id', '=', self.client_id.id),
            ('consent_type_code', '=', self.consent_type_code),
            ('state', '=', 'active'),
        ])
        today = fields.Date.context_today(self)
        for old in previous:
            old.write({
                'state': 'withdrawn',
                'withdrawal_date': today,
                'withdrawal_reason': _('Superseded'),
                'withdrawn_by_id': self.env.uid,
            })
            old.message_post(body=_(
                'Superseded by %s.') % (self.name or _('a new consent')))
            self.message_post(body=_(
                'Supersedes %s.') % old.name)
        self.write({'state': 'active'})
        return True

    def action_withdraw(self):
        """active → withdrawn. Requires withdrawal_reason (wizard-free
        — spec §6.3)."""
        self.ensure_one()
        self._check_capture_allowed()
        if self.state != 'active':
            raise UserError(_(
                'Only an active consent can be withdrawn.'))
        reason = self.withdrawal_reason or self.env.context.get(
            'withdrawal_reason')
        if not reason:
            raise UserError(_(
                'Provide a withdrawal reason before withdrawing the '
                'consent.'))
        self.write({
            'state': 'withdrawn',
            'withdrawal_reason': reason,
            'withdrawal_date': fields.Date.context_today(self),
            'withdrawn_by_id': self.env.uid,
        })
        return True

    # ------------------------------------------------------------------
    # Service API (spec §6.4 + DESIGN §7.1) — the cross-cutting
    # enforcement points other modules call. Deny-by-default: callers
    # MUST treat False as deny. check_consent NEVER raises;
    # require_consent raises AccessError only when the
    # `health_consent.enforce` config parameter is truthy (default
    # falsy = log-only mode, failures logged as compliance evidence).
    # ------------------------------------------------------------------
    @api.model
    def _partner_id(self, partner):
        """Accept a res.partner record or a plain id."""
        if isinstance(partner, models.BaseModel):
            partner.ensure_one()
            return partner.id
        return int(partner)

    @api.model
    def _enforce_enabled(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'health_consent.enforce')
        try:
            return str2bool(param or 'False')
        except ValueError:
            return False

    @api.model
    def _covers_scope(self, consent, scope):
        """A consent covers `scope` when it carries no narrowing
        scope_note (blanket) or the note mentions the scope. scope_note
        is free text — this is a best-effort match; the note itself is
        always surfaced to callers via get_consent()."""
        if not scope or not consent.scope_note:
            return True
        return scope.strip().lower() in consent.scope_note.lower()

    @api.model
    def _find_active_consent(self, partner_id, consent_type,
                             scope=None, at_date=None):
        at_date = at_date or fields.Date.context_today(self)
        # sudo: the check is a platform service callable from any
        # module/user context; record rules must not silently turn a
        # granted consent into a deny for a nurse outside catchment.
        consents = self.sudo().search([
            ('client_id', '=', partner_id),
            # `consent_type` stays a CODE in this public interface — every
            # caller across the clinical spine passes a string.
            ('consent_type_code', '=', consent_type),
            ('state', '=', 'active'),
            ('effective_date', '<=', at_date),
            '|', ('expiry_date', '=', False),
            ('expiry_date', '>=', at_date),
        ], order='effective_date desc')
        for consent in consents:
            if self._covers_scope(consent, scope):
                return consent
        return self.sudo().browse()

    @api.model
    def _log_check(self, partner_id, consent_type, result, consent,
                   scope=None, at_date=None):
        """Append-only compliance evidence — one lightweight row per
        check. Never lets logging break the caller."""
        try:
            self.env['health.consent.check.log'].sudo().create({
                'client_id': partner_id,
                'consent_type': consent_type,
                'scope': scope or False,
                'at_date': at_date or fields.Date.context_today(self),
                'result': result,
                'consent_id': consent.id if consent else False,
                'user_id': self.env.uid,
                'source': self.env.context.get(
                    'consent_check_source') or False,
            })
        except Exception:  # noqa: BLE001 — evidence must not break checks
            _logger.exception('Consent check logging failed')

    @api.model
    def check_consent(self, partner, consent_type, scope=None,
                      at_date=None):
        """Return True iff `partner` (res.partner record or id) has an
        ACTIVE consent of `consent_type` covering `scope`/`at_date`
        (default today). Cheap: single search on (client_id,
        consent_type, state='active') + date-window check. NEVER
        raises — callers MUST treat False as deny-by-default. Every
        call writes a health.consent.check.log row."""
        try:
            partner_id = self._partner_id(partner)
        except (TypeError, ValueError):
            return False
        consent = self._find_active_consent(
            partner_id, consent_type, scope=scope, at_date=at_date)
        result = bool(consent)
        self._log_check(partner_id, consent_type, result, consent,
                        scope=scope, at_date=at_date)
        if not result:
            _logger.info(
                'Consent check DENY (log-only=%s): partner=%s type=%s '
                'scope=%s', not self._enforce_enabled(), partner_id,
                consent_type, scope)
        return result

    @api.model
    def require_consent(self, partner, consent_type, scope=None,
                        at_date=None):
        """check_consent variant for enforcement points: when the
        `health_consent.enforce` config parameter is truthy a missing
        consent raises AccessError; otherwise (default) the failure is
        only logged and False is returned."""
        result = self.check_consent(partner, consent_type, scope=scope,
                                    at_date=at_date)
        if not result and self._enforce_enabled():
            raise AccessError(_(
                'No active %(type)s consent on file for this client '
                '(consent enforcement is enabled).',
                type=consent_type))
        return result

    @api.model
    def get_consent(self, partner, consent_type):
        """Return the active consent record (or empty recordset) for
        display/logging."""
        try:
            partner_id = self._partner_id(partner)
        except (TypeError, ValueError):
            return self.browse()
        return self._find_active_consent(partner_id, consent_type)

    @api.model
    def check_consents(self, partner, consent_types):
        """Batch variant → dict {consent_type: bool} in one search.
        Used by the FSO/PWA payloads. Logs one row per type."""
        try:
            partner_id = self._partner_id(partner)
        except (TypeError, ValueError):
            return {consent_type: False for consent_type in consent_types}
        today = fields.Date.context_today(self)
        consents = self.sudo().search([
            ('client_id', '=', partner_id),
            ('consent_type_code', 'in', list(consent_types)),
            ('state', '=', 'active'),
            ('effective_date', '<=', today),
            '|', ('expiry_date', '=', False),
            ('expiry_date', '>=', today),
        ])
        by_type = {}
        for consent in consents:
            by_type.setdefault(consent.consent_type_code, consent)
        result = {}
        for consent_type in consent_types:
            consent = by_type.get(consent_type, self.sudo().browse())
            result[consent_type] = bool(consent)
            self._log_check(partner_id, consent_type,
                            bool(consent), consent, at_date=today)
        return result

    # ------------------------------------------------------------------
    # Cron (spec §6.4, daily 01:00)
    # ------------------------------------------------------------------
    @api.model
    def _cron_expire_consents(self):
        """(1) active + expiry_date < today → expired (+ chatter).
        (2) Renewal warning at expiry == today + 14 days → to-do
        activity for the client's facility manager."""
        today = fields.Date.context_today(self)
        expired = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '!=', False),
            ('expiry_date', '<', today),
        ])
        for consent in expired:
            consent.write({'state': 'expired'})
            consent.message_post(body=_(
                'Consent expired automatically (expiry %s).')
                % consent.expiry_date)
        expiring = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '=', today + timedelta(days=14)),
        ])
        for consent in expiring:
            consent._schedule_renewal_activity()
        return True

    def _schedule_renewal_activity(self):
        self.ensure_one()
        manager = self.client_id.primary_facility_id.facility_manager_id
        user = manager.user_id if manager else False
        if not user:
            _logger.info(
                'Consent %s expiring but no facility manager user to '
                'notify for client %s.', self.name, self.client_id.name)
            return
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning('Todo activity type not found')
            return
        try:
            self.activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('Consent expiring: %(client)s — %(type)s',
                          client=self.client_id.name,
                          type=self.consent_type_id.name or ''),
                date_deadline=self.expiry_date,
                user_id=user.id,
            )
        except Exception as exc:  # noqa: BLE001 — alerting must never
            # break the cron loop for the remaining consents.
            _logger.error(
                'Consent renewal activity failed for %s: %s',
                self.id, exc)
