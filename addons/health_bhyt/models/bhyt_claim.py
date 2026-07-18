# -*- coding: utf-8 -*-
"""``bhyt.claim`` — one BHYT insurance claim per completed+invoiced visit.

Turns a completed, invoiced FSO into a structured claim with a transparent
BHYT-covered vs patient-copay split (the money core). It READS the posted
invoice and NEVER writes accounting (handover §3). One claim per FSO
(idempotent, unique index). Evidence-locked once ``ready`` — a reconciled
claim can't be silently altered (UNCONDITIONAL guard, conventions §5.4). The
state machine STOPS at ``ready`` this phase; submitted/acked/rejected are
declared for Phase 2 (the Decision-4210 serializer) but no transition into
them ships here.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import bhyt_config
from . import bhyt_coverage

_logger = logging.getLogger(__name__)

# Completed-visit states a claim may be generated from (verified FSO selection,
# health_fieldservice_order.py:45-55). The is_invoiced + posted-invoice + valid
# card gates below make the population honest.
_COMPLETED_STATES = ('completed', 'completed_pending_invoice', 'closed')

# Once a claim leaves draft for a reconciled/submitted state, ONLY these fields
# (plus mail/activity machinery) stay writable — the rest is frozen evidence.
_LOCKED_STATES = frozenset({'ready', 'submitted', 'acked'})
_WRITABLE_WHEN_LOCKED = {'state', 'submission_ref', 'error_text'}


class BhytClaim(models.Model):
    _name = 'bhyt.claim'
    _description = 'BHYT Insurance Claim'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)

    # Links
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', required=True,
        index=True, ondelete='restrict', readonly=True)
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', readonly=True, ondelete='restrict',
        help='The posted customer invoice this claim was generated from '
             '(read-only snapshot — the claim never writes accounting).')
    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='restrict', readonly=True, tracking=True)
    provider_id = fields.Many2one(
        'health.insurance.provider', string='BHYT Scheme', readonly=True)

    # BHYT snapshot AT generation (frozen — never recomputed from live patient)
    bhyt_card_no = fields.Char(string='BHYT Card No.', readonly=True)
    bhyt_coverage_rate = fields.Float(
        string='Coverage Rate (%)', readonly=True)
    bhyt_beneficiary_code = fields.Char(
        string='Beneficiary Code', readonly=True)
    bhyt_registered_facility = fields.Char(
        string='Registered Facility', readonly=True)
    service_date = fields.Date(string='Service Date', readonly=True)

    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True,
        default=lambda self: self.env.company.currency_id)

    line_ids = fields.One2many(
        'bhyt.claim.line', 'claim_id', string='Claim Lines')

    # Totals (computed+stored from the lines via the coverage kernel)
    total_amount = fields.Monetary(
        string='Total', compute='_compute_totals', store=True,
        currency_field='currency_id', tracking=True)
    bhyt_amount = fields.Monetary(
        string='BHYT Covered', compute='_compute_totals', store=True,
        currency_field='currency_id', tracking=True)
    patient_amount = fields.Monetary(
        string='Patient Copay', compute='_compute_totals', store=True,
        currency_field='currency_id', tracking=True)

    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('submitted', 'Submitted'),
        ('acked', 'Acknowledged'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True,
        index=True)

    # Phase-2 placeholders (declared now so no migration later; NOT transitioned
    # into this phase). They stay writable while the claim is locked.
    submission_ref = fields.Char(string='Submission Reference', readonly=True)
    error_text = fields.Text(string='Submission Error', readonly=True)

    event_ids = fields.One2many(
        'bhyt.claim.event', 'claim_id', string='Audit Trail')

    def init(self):
        # §5.1: _sql_constraints are not materialized — one claim per FSO is an
        # idempotency contract, so create the unique index explicitly.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS bhyt_claim_fso_id_uniq
            ON bhyt_claim (fso_id)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('line_ids.eligible_amount', 'line_ids.covered_service',
                 'bhyt_coverage_rate', 'currency_id')
    def _compute_totals(self):
        for claim in self:
            round_to = int((claim.currency_id.rounding or 1.0) or 1)
            dicts = [{
                'eligible': line.eligible_amount,
                'rate': claim.bhyt_coverage_rate,
                'round_to': round_to,
                'covered_service': line.covered_service,
            } for line in claim.line_ids]
            totals = bhyt_coverage.claim_totals(dicts)
            claim.total_amount = totals['total']
            claim.bhyt_amount = totals['bhyt']
            claim.patient_amount = totals['patient']

    @api.depends('patient_id')
    def _compute_catchment_province_id(self):
        for claim in self:
            claim.catchment_province_id = (
                claim.patient_id._get_health_catchment_province()
                if claim.patient_id else False)

    # ------------------------------------------------------------------
    # ORM overrides — sequence, evidence-lock, delete guard
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'bhyt.claim') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        # Evidence-lock: once ready/submitted/acked the reconciled figure is
        # frozen — only state and the Phase-2 receipt/error fields (and mail
        # machinery) may change. UNCONDITIONAL: uid 1 runs as su, so any su
        # escape would void the lock (conventions §5.4).
        protected = {
            key for key in vals
            if key not in _WRITABLE_WHEN_LOCKED
            and not key.startswith('message_')
            and not key.startswith('activity_')
        }
        if protected:
            frozen = self.filtered(lambda c: c.state in _LOCKED_STATES)
            if frozen:
                raise UserError(_(
                    'BHYT claim %(names)s is locked reconciliation evidence — '
                    'reset it to draft to change it (locked fields: '
                    '%(fields)s).',
                    names=', '.join(frozen.mapped('name')),
                    fields=', '.join(sorted(protected))))
        return super().write(vals)

    def unlink(self):
        frozen = self.filtered(lambda c: c.state not in ('draft', 'cancelled'))
        if frozen:
            raise UserError(_(
                'Only draft or cancelled BHYT claims can be deleted — a '
                'ready/submitted claim is reconciliation evidence (%s).')
                % ', '.join(frozen.mapped('name')))
        return super().unlink()

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def _log_event(self, event, note=None):
        """Append one immutable audit row per transition (sudo — the log is
        append-only and users have no create right on it)."""
        self.ensure_one()
        self.env['bhyt.claim.event'].sudo().create({
            'claim_id': self.id,
            'event': event,
            'user_id': self.env.uid,
            'amount_snapshot': self.total_amount,
            'note': note or False,
        })

    # ------------------------------------------------------------------
    # State machine (Phase 1: draft ⇄ ready ⇄ cancelled only)
    # ------------------------------------------------------------------
    def action_mark_ready(self):
        for claim in self:
            if claim.state != 'draft':
                raise UserError(_(
                    'Only a draft claim can be marked ready (%s).')
                    % claim.name)
            if not claim.line_ids:
                raise UserError(_(
                    'Claim %s has no lines to reconcile.') % claim.name)
            claim.write({'state': 'ready'})
            claim._log_event('marked_ready')
        return True

    def action_reset_draft(self):
        for claim in self:
            if claim.state not in ('ready', 'cancelled'):
                raise UserError(_(
                    'Only a ready or cancelled claim can be reset to draft '
                    '(%s).') % claim.name)
            claim.write({'state': 'draft'})
            claim._log_event('reset')
        return True

    def action_cancel(self):
        for claim in self:
            if claim.state not in ('draft', 'ready'):
                raise UserError(_(
                    'Only a draft or ready claim can be cancelled (%s).')
                    % claim.name)
            claim.write({'state': 'cancelled'})
            claim._log_event('cancelled')
        return True

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    @api.model
    def _build_claim_for(self, order):
        """Build (or return the existing) claim for one FSO. Never raises on an
        ineligible order — returns an empty recordset and logs (handover §2.5,
        §3). Idempotent: the unique fso_id index is the hard guard, a search
        the soft one."""
        order = order.sudo()
        Claim = self.sudo()

        existing = Claim.search([('fso_id', '=', order.id)], limit=1)
        if existing:
            return existing

        # Eligibility gate — honest: completed/closed + invoiced + posted
        # invoice + a valid BHYT card. Anything else → no claim (logged).
        patient = order.patient_id
        invoice = order.invoice_id
        if (order.state not in _COMPLETED_STATES or not order.is_invoiced
                or not invoice or invoice.state != 'posted'
                or not patient or not patient.bhyt_valid):
            _logger.info(
                'BHYT: FSO %s not claim-eligible (state=%s invoiced=%s '
                'invoice_posted=%s bhyt_valid=%s) — skipped.',
                order.id, order.state, order.is_invoiced,
                bool(invoice) and invoice.state == 'posted',
                bool(patient) and patient.bhyt_valid)
            return Claim.browse()

        default_covered = bhyt_config.get_bool(
            self.env, 'default_covered', True)
        rate = patient.bhyt_coverage_rate
        if not rate and patient.bhyt_provider_id:
            rate = patient.bhyt_provider_id.coverage_percentage

        lines = []
        for iline in invoice.invoice_line_ids:
            if iline.display_type != 'product':
                continue
            lines.append((0, 0, {
                'name': iline.name or (
                    iline.product_id.display_name if iline.product_id else ''),
                'product_id': iline.product_id.id or False,
                'quantity': iline.quantity,
                'unit_price': iline.price_unit,
                'eligible_amount': iline.price_subtotal,
                'covered_service': default_covered,
            }))

        claim = Claim.create({
            'fso_id': order.id,
            'invoice_id': invoice.id,
            'patient_id': patient.id,
            'provider_id': patient.bhyt_provider_id.id or False,
            'bhyt_card_no': patient.insurance_number,
            'bhyt_coverage_rate': rate,
            'bhyt_beneficiary_code': patient.bhyt_beneficiary_code or False,
            'bhyt_registered_facility':
                patient.bhyt_registered_facility or False,
            'service_date': (order.scheduled_datetime.date()
                             if order.scheduled_datetime else False),
            'currency_id': (invoice.currency_id.id
                            or self.env.company.currency_id.id),
            'line_ids': lines,
        })
        claim._log_event('generated')
        return claim

    @api.model
    def cron_bhyt_generate(self):
        """Config-gated batch generation over eligible FSOs without a claim.
        OFF by default (opt-in). Per-order savepoint so one bad order can never
        abort the batch; the unique fso_id index makes a racing double-generate
        raise → caught → skipped. Does NOT mark ready (human review)."""
        env = self.env
        if not bhyt_config.get_bool(env, 'generate_enabled', False):
            _logger.info('BHYT generate cron: disabled (config off).')
            return True
        cap = bhyt_config.get_int(env, 'generate_batch_cap', 500)

        FSO = env['health.fieldservice.order'].sudo()
        Claim = self.sudo()
        claimed = set(Claim.search([]).mapped('fso_id').ids)
        candidates = FSO.search([
            ('state', 'in', _COMPLETED_STATES),
            ('is_invoiced', '=', True),
        ], order='id')
        # Filter to eligible + not-already-claimed, cap the batch.
        todo = candidates.filtered(
            lambda o: o.id not in claimed
            and o.invoice_id and o.invoice_id.state == 'posted'
            and o.patient_id and o.patient_id.bhyt_valid)
        total = len(todo)
        if total > cap:
            _logger.info('BHYT generate cron: %s eligible, capping at %s '
                         '(deferred %s).', total, cap, total - cap)
            todo = todo[:cap]

        made = 0
        for order in todo:
            try:
                with env.cr.savepoint():
                    claim = Claim._build_claim_for(order)
                    if claim:
                        made += 1
            except Exception:  # never-block: one bad order can't abort batch
                _logger.exception(
                    'BHYT generate cron: FSO %s failed — skipped.', order.id)
        _logger.info('BHYT generate cron: generated=%s (of %s eligible).',
                     made, total)
        return True
