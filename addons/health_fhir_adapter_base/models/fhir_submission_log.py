# -*- coding: utf-8 -*-
"""Audit trail of every EMR export / submission (interop §3).

Rows are audit evidence: append-only past draft. Only state, receipt_ref
and error_text stay writable once exported/submitted (evidence-lock list
pattern from health_consent); unlink is draft-only. Guards are
unconditional — uid 1 runs as su, so a su escape would void the lock
(conventions §5.4)."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Once a row leaves draft, only these fields remain writable (the rest is
# frozen audit evidence). mail/activity technical writes are always allowed.
WRITABLE_AFTER_DRAFT = {'state', 'receipt_ref', 'error_text'}


class FhirSubmissionLog(models.Model):
    _name = 'fhir.submission.log'
    _description = 'FHIR Submission Log'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    adapter_code = fields.Char(required=True, index=True, tracking=True)
    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='restrict', tracking=True)
    bundle_sha256 = fields.Char(string='Bundle SHA-256', readonly=True)
    entry_count = fields.Integer(string='Entry Count', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('exported', 'Exported'),
        ('submitted', 'Submitted'),
        ('acked', 'Acknowledged'),
        ('error', 'Error'),
    ], default='draft', required=True, tracking=True, index=True)
    receipt_ref = fields.Char(string='Receipt Reference', tracking=True)
    issue_text = fields.Text(string='Profile Validation Issues', readonly=True)
    error_text = fields.Text(string='Error')
    attachment_id = fields.Many2one(
        'ir.attachment', string='Bundle Attachment', ondelete='set null',
        readonly=True)
    exported_by_id = fields.Many2one('res.users', string='Exported By',
                                     readonly=True)
    exported_at = fields.Datetime(string='Exported At', readonly=True)
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True,
        help='Catchment area used for filtering and access control')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    @api.depends('patient_id')
    def _compute_catchment_province_id(self):
        for log in self:
            log.catchment_province_id = (
                log.patient_id._get_health_catchment_province()
                if log.patient_id else False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'fhir.submission.log') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        # Audit evidence: past draft, only state/receipt_ref/error_text
        # (and mail machinery) may change. Unconditional — no su escape.
        protected = {
            key for key in vals
            if key not in WRITABLE_AFTER_DRAFT
            and not key.startswith('message_')
            and not key.startswith('activity_')
        }
        if protected:
            frozen = self.filtered(lambda log: log.state != 'draft')
            if frozen:
                raise UserError(_(
                    'Submission log %(names)s is exported audit evidence — '
                    'only state, receipt reference and error may change '
                    '(locked fields: %(fields)s).',
                    names=', '.join(frozen.mapped('name')),
                    fields=', '.join(sorted(protected))))
        return super().write(vals)

    def unlink(self):
        frozen = self.filtered(lambda log: log.state != 'draft')
        if frozen:
            raise UserError(_(
                'Only draft submission logs can be deleted — exported logs '
                'are audit evidence (%s).') % ', '.join(frozen.mapped('name')))
        return super().unlink()
