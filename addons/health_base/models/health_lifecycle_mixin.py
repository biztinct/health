# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Domain

MIN_NOTE_LEN = 5


class HealthLifecycleMixin(models.AbstractModel):
    """User-facing soft delete — the "Deleted" tier of the record lifecycle.

    Lifecycle states (client spec — delete is a USER function, archive is a
    CUSTODIAN function):
      * Active   — normal record.
      * Deleted  — flagged by any user with a mandatory reason. The record
                   stays VISIBLE in record tables (badge) but is EXCLUDED from
                   every count, report and dropdown via the `deleted_test`
                   context key (mirrors `active_test`, see `_search`).
      * Archived — custodian only, native active=False: hidden from default
                   views but still counted in BI/reports (BI compiles raw SQL
                   and its query engine runs active_test=False on ir.rules).
      * Purged   — physical unlink, Healthcare Owner only, and only AFTER the
                   record was soft-deleted (enforced in soft_delete_guard).
    """
    _name = 'health.lifecycle.mixin'
    _description = 'Record Lifecycle (Soft Delete)'

    deleted = fields.Boolean(
        'Deleted', default=False, copy=False, index=True, tracking=True)
    deleted_date = fields.Datetime('Deleted On', copy=False, readonly=True)
    deleted_by_id = fields.Many2one(
        'res.users', 'Deleted By', copy=False, readonly=True)
    deleted_reason_id = fields.Many2one(
        'health.deletion.reason', 'Deletion Reason',
        copy=False, readonly=True, ondelete='restrict')
    deleted_note = fields.Text('Deletion Note', copy=False, readonly=True)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *,
                active_test=True, bypass_access=False, **kwargs):
        """Exclude soft-deleted records from every search/count/aggregate.

        Opt-outs, mirroring the core `active_test` logic in
        odoo/orm/models.py::_search (verified on the deployed 19 core, where
        _read_group also funnels through _search — so search_count, pivots,
        dashboards and name_search dropdowns are all covered without touching
        any call site):
          * the `active_test` PARAMETER is False — that is how the framework
            marks internal id-constrained queries (fetch() runs
            `_search([('id','in',ids)], active_test=False)` for its rule
            check); filtering there would make deleted records unreadable.
            Business callers that want archived records use the CONTEXT key
            instead, which keeps excluding deleted — exactly the spec;
          * context `deleted_test: False` — set on the record-table actions so
            deleted rows stay visible in every table, per the client spec;
          * the domain already references `deleted` — so a "Deleted" search
            filter works from any view.
        """
        if active_test and self.env.context.get('deleted_test', True):
            domain = Domain(domain)
            if not any(cond.field_expr == 'deleted'
                       for cond in domain.iter_conditions()):
                domain &= Domain('deleted', '=', False)
        return super()._search(
            domain, offset, limit, order,
            active_test=active_test, bypass_access=bypass_access, **kwargs)

    def _lifecycle_check_soft_delete(self):
        """Model-specific gate. Override to raise when a record must not be
        soft-deleted (posted invoices, partners linked to users, ...)."""

    def action_soft_delete(self, reason_id=None, note=None):
        """Mark records Deleted with a mandatory, structured reason."""
        recs = self.filtered(lambda r: not r.deleted)
        if not recs:
            return True
        reason = self.env['health.deletion.reason'].browse(reason_id or [])
        if not reason.exists():
            raise UserError(_(
                'A deletion reason is required — every deletion must be explained.'))
        note = (note or '').strip()
        if reason.requires_note and len(note) < MIN_NOTE_LEN:
            raise UserError(_(
                'Please explain this deletion in the note (at least %s characters).',
                MIN_NOTE_LEN))
        recs._lifecycle_check_soft_delete()
        recs.with_context(health_lifecycle_via_action=True).write({
            'deleted': True,
            'deleted_date': fields.Datetime.now(),
            'deleted_by_id': self.env.uid,
            'deleted_reason_id': reason.id,
            'deleted_note': note or False,
        })
        reason_text = '%s — %s' % (reason.name, note) if note else reason.name
        recs.with_context(archive_reason=reason_text)._health_log_archive('delete')
        return True

    def action_restore(self):
        """Clear the Deleted flag. Custodian function (owner implies it)."""
        if not self.env.user.has_group('health_base.group_healthcare_custodian'):
            raise UserError(_(
                'Only the Record Custodian may restore deleted records.'))
        recs = self.filtered('deleted')
        if not recs:
            return True
        recs.with_context(health_lifecycle_via_action=True).write({
            'deleted': False,
            'deleted_date': False,
            'deleted_by_id': False,
            'deleted_reason_id': False,
            'deleted_note': False,
        })
        recs._health_log_archive('restore')
        return True
