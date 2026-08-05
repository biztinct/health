# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

MIN_REASON_LEN = 5
PREVIEW_NAMES = 3


class HealthArchiveReasonWizard(models.TransientModel):
    """Mandatory-reason prompt for the record lifecycle actions.
    Launched from the list/form cog menu (see archive_delete_policy.js) with
    active_model/active_ids in context and `default_mode` selecting the tier:
      delete    — USER function: soft flag, record stays visible, out of counts
      archive   — CUSTODIAN function: hidden from views, still counted
      restore   — custodian: clear a Deleted flag
      unarchive — custodian: bring an archived record back
    """
    _name = 'health.archive.reason.wizard'
    _description = 'Record Lifecycle Action'

    mode = fields.Selection([
        ('delete', 'Delete'),
        ('archive', 'Archive'),
        ('restore', 'Restore'),
        ('unarchive', 'Unarchive'),
    ], default='archive', required=True)
    reason_id = fields.Many2one(
        'health.deletion.reason', 'Reason for deletion',
        ondelete='set null',
        help='Every deletion must be explained (client data-governance rule).')
    requires_note = fields.Boolean(related='reason_id.requires_note')
    reason = fields.Text('Details')
    record_count = fields.Integer('Records', compute='_compute_record_preview')
    record_preview = fields.Char('Selection', compute='_compute_record_preview')

    @api.model
    def get_lifecycle_models(self):
        """Concrete models carrying health.lifecycle.mixin. Consumed by the
        web policy layer (archive_delete_policy.js) so the Delete/Archive
        buttons and cog entries follow newly mixed-in models automatically —
        no client-side list to keep in sync."""
        return sorted(
            name
            for name, model in self.env.registry.items()
            if not model._abstract and not model._transient
            and 'deleted' in model._fields
            and hasattr(model, 'action_soft_delete')
        )

    @api.depends('mode')
    @api.depends_context('active_ids', 'active_model')
    def _compute_record_preview(self):
        model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        preview = ''
        if model and active_ids and model in self.env:
            # Deleted/archived rows must resolve too — this dialog also serves
            # restore/unarchive.
            records = self.env[model].with_context(
                deleted_test=False, active_test=False,
            ).browse(active_ids[:PREVIEW_NAMES]).exists()
            names = [r.display_name or str(r.id) for r in records]
            extra = len(active_ids) - len(names)
            preview = ', '.join(names) + (
                _(' and %s more', extra) if extra > 0 else '')
        for wiz in self:
            wiz.record_count = len(active_ids)
            wiz.record_preview = preview

    @api.constrains('mode', 'reason', 'reason_id')
    def _check_reason(self):
        for wiz in self:
            if wiz.mode == 'archive' and (
                    not wiz.reason or len(wiz.reason.strip()) < MIN_REASON_LEN):
                raise ValidationError(_(
                    'Please provide a meaningful reason (at least %s characters).',
                    MIN_REASON_LEN))
            if wiz.mode == 'delete' and not wiz.reason_id:
                raise ValidationError(_(
                    'A deletion reason is required — every deletion must be explained.'))

    def _get_records(self):
        model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if not model or not active_ids or model not in self.env:
            raise UserError(_('No records selected.'))
        return self.env[model].with_context(
            deleted_test=False, active_test=False).browse(active_ids).exists()

    def action_confirm(self):
        self.ensure_one()
        records = self._get_records()
        if not records:
            raise UserError(_('No records selected.'))
        reason = (self.reason or '').strip()
        if self.mode == 'delete':
            if 'deleted' not in records._fields:
                raise UserError(_(
                    'Records of this type do not support Delete requests.'))
            records.action_soft_delete(self.reason_id.id, reason)
        elif self.mode == 'restore':
            if 'deleted' not in records._fields:
                raise UserError(_(
                    'Records of this type do not support Delete requests.'))
            records.action_restore()
        elif self.mode == 'archive':
            records.with_context(
                archive_from_ui=True, archive_reason=reason).action_archive()
        else:
            records.with_context(
                archive_from_ui=True, archive_reason=reason).action_unarchive()
        return {'type': 'ir.actions.act_window_close'}
