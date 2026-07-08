# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, models, _
from odoo.exceptions import AccessError, UserError


class HealthSoftDeleteGuard(models.AbstractModel):
    _inherit = 'base'

    _health_owner_delete_exact_models = {
        'account.move',
        'account.move.line',
        'account.payment',
        'crm.lead',
        'crm.stage',
        'hr.employee',
        'product.pricelist',
        'product.product',
        'product.template',
        'res.partner',
        'res.users',
        'sale.order',
        'sale.order.line',
    }
    _health_owner_delete_prefixes = (
        'advanced.pricing.',
        'health.',
        'misa.',
    )

    @api.model
    def _health_owner_only_delete_model(self):
        return (
            self._name in self._health_owner_delete_exact_models
            or self._name.startswith(self._health_owner_delete_prefixes)
        )

    def unlink(self):
        is_transient = getattr(self, 'is_transient', None)
        if callable(is_transient) and is_transient():
            return super().unlink()
        if (
            self._health_owner_only_delete_model()
            and not getattr(self.env, 'su', False)
            and self.env.uid != SUPERUSER_ID
            and not self.env.user.has_group('health_base.group_healthcare_owner')
        ):
            raise AccessError(_(
                "Hard delete is restricted to Healthcare Owner users. "
                "Use Archive instead to deactivate records without deleting history."
            ))
        return super().unlink()

    # ------------------------------------------------------------------
    # Archive-with-reason policy (soft delete)
    # ------------------------------------------------------------------
    # UI archives flow through the health.archive.reason.wizard, which sets
    # `archive_from_ui` + `archive_reason` in the context. Programmatic /
    # internal archives (e.g. cancel-booking archiving its draft invoice) do
    # NOT set the flag and are never blocked. Every archive/unarchive of a
    # business record is logged to health.archive.log (append-only) and, for
    # mail.thread records, to the chatter.

    def action_archive(self):
        ctx = self.env.context
        if (ctx.get('archive_from_ui')
                and self._health_owner_only_delete_model()
                and not (ctx.get('archive_reason') or '').strip()):
            raise UserError(_('A reason is required to archive this record.'))
        res = super().action_archive()
        self._health_log_archive('archive')
        return res

    def action_unarchive(self):
        res = super().action_unarchive()
        self._health_log_archive('unarchive')
        return res

    def _health_log_archive(self, action):
        """Write an append-only archive-log row (+ chatter) for business records."""
        if not self or not self._health_owner_only_delete_model():
            return
        # Never let audit logging break the archive transaction.
        try:
            reason = (self.env.context.get('archive_reason') or '').strip()
            Log = self.env['health.archive.log'].sudo()
            model_label = self.env['ir.model']._get(self._name).name or self._name
            has_chatter = 'message_ids' in self._fields and hasattr(self, 'message_post')
            for rec in self:
                Log.create({
                    'model_technical': rec._name,
                    'model_name': model_label,
                    'res_id': rec.id,
                    'record_name': rec.display_name or str(rec.id),
                    'action': action,
                    'reason': reason or False,
                    'user_id': self.env.uid,
                })
                if has_chatter:
                    if action == 'archive':
                        rec.message_post(body=_(
                            'Archived. Reason: %s', reason or _('(none provided)')))
                    else:
                        rec.message_post(body=_('Unarchived.'))
        except Exception:  # noqa: BLE001 - audit must never block the action
            import logging
            logging.getLogger(__name__).exception(
                'health archive-log failed for %s', self._name)
