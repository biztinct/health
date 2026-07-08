# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

MIN_REASON_LEN = 5


class HealthArchiveReasonWizard(models.TransientModel):
    """Mandatory-reason prompt shown before archiving business records.
    Launched from the list/form Archive action (see archive_delete_policy.js)
    with active_model/active_ids in context."""
    _name = 'health.archive.reason.wizard'
    _description = 'Archive Reason'

    reason = fields.Text('Reason for archiving', required=True)
    record_count = fields.Integer('Records', compute='_compute_record_count')

    @api.depends_context('active_ids')
    def _compute_record_count(self):
        active_ids = self.env.context.get('active_ids') or []
        for wiz in self:
            wiz.record_count = len(active_ids)

    @api.constrains('reason')
    def _check_reason(self):
        for wiz in self:
            if not wiz.reason or len(wiz.reason.strip()) < MIN_REASON_LEN:
                raise ValidationError(_(
                    'Please provide a meaningful reason (at least %s characters).',
                    MIN_REASON_LEN))

    def action_confirm(self):
        self.ensure_one()
        model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if not model or not active_ids:
            raise UserError(_('Nothing to archive.'))
        records = self.env[model].browse(active_ids).exists()
        if records:
            records.with_context(
                archive_from_ui=True,
                archive_reason=self.reason.strip(),
            ).action_archive()
        return {'type': 'ir.actions.act_window_close'}
