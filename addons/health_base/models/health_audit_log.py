# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
import logging

_logger = logging.getLogger(__name__)


class HealthAuditLogView(models.Model):
    _name = 'health.audit.log.view'
    _description = 'Consolidated Healthcare Audit Log'
    _auto = False  # SQL view, not regular table
    _order = 'date desc'
    _rec_name = 'field_name'

    # Display fields
    date = fields.Datetime('Date', readonly=True)
    user_id = fields.Many2one('res.users', 'User', readonly=True)
    model = fields.Char('Model', readonly=True)
    model_name = fields.Char('Model Name', readonly=True)
    res_id = fields.Integer('Record ID', readonly=True)
    # The changed record's own name (BK3832, INV/2026/00025, the client's
    # name…), computed — the message subject the view used to read is empty
    # for tracking messages, so the column was always blank (UAT round 6,
    # item 7). Searchable; never stored, so existing rows show it too.
    record_name = fields.Char('Record', compute='_compute_record_name',
                              search='_search_record_name')
    field_name = fields.Char('Field Changed', readonly=True)
    old_value = fields.Char('Old Value', readonly=True)
    new_value = fields.Char('New Value', readonly=True)

    def _compute_record_name(self):
        by_model = {}
        for row in self:
            by_model.setdefault(row.model, set()).add(row.res_id)
        names = {}
        for model, ids in by_model.items():
            if not model or model not in self.env:
                continue
            records = self.env[model].browse(list(ids)).exists()
            # Names only of records the viewer may read; others show
            # "<kind> #<id>" (the audit itself is still listed).
            try:
                readable = records._filtered_access('read')
            except Exception:  # noqa: BLE001
                readable = records.browse()
            for rec in readable:
                try:
                    names[(model, rec.id)] = rec.display_name
                except AccessError:
                    pass
        for row in self:
            row.record_name = names.get((row.model, row.res_id)) or (
                '%s #%s' % (row.model_name or row.model or '', row.res_id) if row.res_id else '')

    def _search_record_name(self, operator, value):
        if operator not in ('ilike', 'like', '=', '=like', '=ilike', 'in'):
            return NotImplemented
        domains = []
        self.env.cr.execute('SELECT DISTINCT model FROM %s' % self._table)
        for (model,) in self.env.cr.fetchall():
            if not model or model not in self.env:
                continue
            ids = self.env[model].with_context(active_test=False)._search(
                [('display_name', operator, value)])
            domains.append(Domain('model', '=', model) & Domain('res_id', 'in', ids))
        return Domain.OR(domains) if domains else Domain.FALSE

    def action_open_record(self):
        """Open the changed record, when the viewer may read it."""
        self.ensure_one()
        if not self.model or self.model not in self.env or not self.res_id:
            raise UserError(_('This record can no longer be opened.'))
        record = self.env[self.model].browse(self.res_id).exists()
        if not record:
            raise UserError(_('This record no longer exists.'))
        try:
            record.check_access('read')
        except AccessError:
            raise UserError(_('You do not have access to this record.'))
        action = record.get_formview_action()
        action['target'] = 'current'
        return action

    def init(self):
        """Create SQL view for consolidated audit log across healthcare models"""
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    mtv.id,
                    mm.date,
                    COALESCE(actor.id, mm.create_uid) as user_id,
                    mm.model,
                    COALESCE(im.name->>'en_US', mm.model) as model_name,
                    mm.res_id,
                    COALESCE(mf.field_description->>'en_US', mf.name) as field_name,
                    CASE
                        WHEN mf.ttype IN ('float', 'monetary') THEN mtv.old_value_float::text
                        WHEN mf.ttype IN ('integer', 'boolean') THEN mtv.old_value_integer::text
                        WHEN mf.ttype IN ('date', 'datetime') THEN mtv.old_value_datetime::text
                        WHEN mf.ttype IN ('text', 'html') THEN mtv.old_value_text
                        ELSE mtv.old_value_char END as old_value,
                    CASE
                        WHEN mf.ttype IN ('float', 'monetary') THEN mtv.new_value_float::text
                        WHEN mf.ttype IN ('integer', 'boolean') THEN mtv.new_value_integer::text
                        WHEN mf.ttype IN ('date', 'datetime') THEN mtv.new_value_datetime::text
                        WHEN mf.ttype IN ('text', 'html') THEN mtv.new_value_text
                        ELSE mtv.new_value_char END as new_value
                FROM mail_tracking_value mtv
                JOIN mail_message mm ON mm.id = mtv.mail_message_id
                LEFT JOIN LATERAL (
                    SELECT id FROM res_users WHERE partner_id = mm.author_id ORDER BY id LIMIT 1
                ) actor ON true
                JOIN ir_model im ON im.model = mm.model
                LEFT JOIN ir_model_fields mf ON mf.id = mtv.field_id
                WHERE mm.model IN (
                    'advanced.pricing.engine',
                    'advanced.pricing.rule',
                    'product.pricelist',
                    'health.fieldservice.order',
                    'account.move',
                    'res.partner',
                    'health.facility',
                    'resource.calendar.leaves'
                    , 'crm.lead', 'health.clinical.note', 'account.payment',
                    'health.payment.transaction', 'health.staff.assignment',
                    'res.users', 'biz.access.role'
                )
                AND mtv.field_id IS NOT NULL
                ORDER BY mm.date DESC
            )
        """ % self._table)
