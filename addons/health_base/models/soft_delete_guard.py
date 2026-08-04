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
        if self._health_owner_only_delete_model():
            bypass = (
                getattr(self.env, 'su', False)
                or self.env.uid == SUPERUSER_ID
            )
            if not bypass and not self.env.user.has_group(
                    'health_base.group_healthcare_owner'):
                raise AccessError(_(
                    "Hard delete is restricted to Healthcare Owner users. "
                    "Use Archive instead to deactivate records without deleting history."
                ))
            # Lifecycle records (health.lifecycle.mixin): even the Owner may
            # only purge records that went through a Delete request first —
            # the client rule "the custodian can physically delete records
            # when the purpose for deletion has been verified".
            if not bypass and 'deleted' in self._fields:
                not_deleted = self.filtered(lambda r: not r.deleted)
                if not_deleted:
                    raise UserError(_(
                        'Physical deletion requires a verified Delete request: '
                        'mark the record as Deleted (with a reason) first. '
                        'Not marked: %s',
                        ', '.join(not_deleted.mapped('display_name')[:5])))
            # Log user-driven purges; scripted/su cleanups stay quiet.
            if not bypass:
                self._health_log_archive('purge')
        return super().unlink()

    # ------------------------------------------------------------------
    # Record lifecycle policy
    # ------------------------------------------------------------------
    # Two user-facing tiers on business records (client data-governance spec):
    #   * Delete  (any user, mandatory reason)  -> health.lifecycle.mixin:
    #     record stays visible with a DELETED badge, excluded from counts.
    #   * Archive (Record Custodian, mandatory reason) -> active=False:
    #     record hidden from views, still counted in BI/reports.
    # UI flows go through health.archive.reason.wizard, which sets
    # `archive_from_ui` + `archive_reason` in the context. Programmatic /
    # internal archives (e.g. cancel-booking archiving its draft invoice) do
    # NOT set the flag and are never blocked. Every lifecycle action on a
    # business record is logged to health.archive.log (append-only) and, for
    # mail.thread records, to the chatter.

    def action_archive(self):
        ctx = self.env.context
        if ctx.get('archive_from_ui') and self._health_owner_only_delete_model():
            if not self.env.user.has_group('health_base.group_healthcare_custodian'):
                raise AccessError(_(
                    'Archiving is a custodian function — ask a Record Custodian.'))
            if not (ctx.get('archive_reason') or '').strip():
                raise UserError(_('A reason is required to archive this record.'))
        recs = self.with_context(health_archive_via_action=True)
        res = super(HealthSoftDeleteGuard, recs).action_archive()
        recs._health_log_archive('archive')
        return res

    def action_unarchive(self):
        ctx = self.env.context
        if ctx.get('archive_from_ui') and self._health_owner_only_delete_model():
            if not self.env.user.has_group('health_base.group_healthcare_custodian'):
                raise AccessError(_(
                    'Unarchiving is a custodian function — ask a Record Custodian.'))
        recs = self.with_context(health_archive_via_action=True)
        res = super(HealthSoftDeleteGuard, recs).action_unarchive()
        recs._health_log_archive('unarchive')
        return res

    def write(self, vals):
        # Plain writes on the lifecycle fields — boolean_toggle widgets,
        # imports, code paths that skip the actions — must still reach the
        # lifecycle log, or the log is not trustworthy as a compliance record.
        # The context flags prevent double-logging when the write comes from
        # action_archive/unarchive or action_soft_delete/restore (which call
        # write internally).
        log_after = []
        if self._health_owner_only_delete_model():
            ctx = self.env.context
            if (
                'active' in vals
                and 'active' in self._fields
                and not ctx.get('health_archive_via_action')
            ):
                target = bool(vals['active'])
                log_after.append((
                    'unarchive' if target else 'archive',
                    self.filtered(lambda r: bool(r.active) != target)))
            if (
                'deleted' in vals
                and 'deleted' in self._fields
                and not ctx.get('health_lifecycle_via_action')
            ):
                target = bool(vals['deleted'])
                log_after.append((
                    'delete' if target else 'restore',
                    self.filtered(lambda r: bool(r.deleted) != target)))
        res = super().write(vals)
        for action, changed in log_after:
            changed._health_log_archive(action)
        return res

    def _health_log_archive(self, action):
        """Write an append-only lifecycle-log row (+ chatter) for business records."""
        if not self or not self._health_owner_only_delete_model():
            return
        # Never let audit logging break the transaction.
        try:
            ctx_reason = (self.env.context.get('archive_reason') or '').strip()
            Log = self.env['health.archive.log'].sudo()
            model_label = self.env['ir.model']._get(self._name).name or self._name
            has_chatter = 'message_ids' in self._fields and hasattr(self, 'message_post')
            has_lifecycle = 'deleted' in self._fields
            for rec in self:
                reason = ctx_reason
                if not reason and action == 'purge' and has_lifecycle:
                    # Carry the original Delete-request justification onto the
                    # purge row so the trail stays self-explanatory.
                    parts = [p for p in (rec.deleted_reason_id.name,
                                         rec.deleted_note) if p]
                    reason = ' — '.join(parts)
                Log.create({
                    'model_technical': rec._name,
                    'model_name': model_label,
                    'res_id': rec.id,
                    'record_name': rec.display_name or str(rec.id),
                    'action': action,
                    'reason': reason or False,
                    'user_id': self.env.uid,
                })
                # No chatter on purge: the record (and its thread) is going away.
                if has_chatter and action != 'purge':
                    if action == 'archive':
                        body = _('Archived. Reason: %s',
                                 reason or _('(none provided)'))
                    elif action == 'unarchive':
                        body = _('Unarchived.')
                    elif action == 'delete':
                        body = _('Marked as Deleted. Reason: %s',
                                 reason or _('(none provided)'))
                    else:
                        body = _('Restored — the Deleted flag was removed.')
                    rec.message_post(body=body)
        except Exception:  # noqa: BLE001 - audit must never block the action
            import logging
            logging.getLogger(__name__).exception(
                'health archive-log failed for %s', self._name)
