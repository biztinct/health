# -*- coding: utf-8 -*-
"""``bhyt.claim.line`` — one line per BHYT-relevant invoice line.

Mirrors the posted invoice line and carries the per-line BHYT/patient split
computed through the ONE coverage kernel (handover §2.4). Locked whenever the
parent claim is locked — a line can't be edited/added/removed on a reconciled
claim (the parent evidence-lock reaches its children).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import bhyt_coverage

_LOCKED_STATES = frozenset({'ready', 'submitted', 'acked'})


class BhytClaimLine(models.Model):
    _name = 'bhyt.claim.line'
    _description = 'BHYT Claim Line'
    _order = 'claim_id, sequence, id'

    claim_id = fields.Many2one(
        'bhyt.claim', string='Claim', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Service')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', default=1.0)
    unit_price = fields.Monetary(
        string='Unit Price', currency_field='currency_id')
    eligible_amount = fields.Monetary(
        string='Eligible Amount', currency_field='currency_id',
        help='BHYT-eligible base (the invoice line subtotal unless the '
             'service is out-of-list).')
    covered_service = fields.Boolean(
        string='On BHYT List', default=True,
        help='When off, the whole line is the patient responsibility.')
    bhyt_amount = fields.Monetary(
        string='BHYT Covered', compute='_compute_split', store=True,
        currency_field='currency_id')
    patient_amount = fields.Monetary(
        string='Patient Copay', compute='_compute_split', store=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        related='claim_id.currency_id', string='Currency', store=True,
        readonly=True)

    @api.depends('eligible_amount', 'covered_service',
                 'claim_id.bhyt_coverage_rate', 'currency_id')
    def _compute_split(self):
        for line in self:
            round_to = int((line.currency_id.rounding or 1.0) or 1)
            covered, copay = bhyt_coverage.coverage_split(
                line.eligible_amount, line.claim_id.bhyt_coverage_rate,
                round_to, line.covered_service)
            line.bhyt_amount = covered
            line.patient_amount = copay

    def _check_parent_unlocked(self, action):
        frozen = self.filtered(lambda l: l.claim_id.state in _LOCKED_STATES)
        if frozen:
            raise UserError(_(
                'Cannot %(action)s a line on a locked BHYT claim (%(claims)s) '
                '— reset it to draft first.',
                action=action,
                claims=', '.join(frozen.mapped('claim_id.name'))))

    def write(self, vals):
        self._check_parent_unlocked(_('modify'))
        return super().write(vals)

    def unlink(self):
        self._check_parent_unlocked(_('delete'))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        claim_ids = [v['claim_id'] for v in vals_list if v.get('claim_id')]
        if claim_ids:
            locked = self.env['bhyt.claim'].browse(claim_ids).filtered(
                lambda c: c.state in _LOCKED_STATES)
            if locked:
                raise UserError(_(
                    'Cannot add a line to a locked BHYT claim (%s) — reset it '
                    'to draft first.') % ', '.join(locked.mapped('name')))
        return super().create(vals_list)
