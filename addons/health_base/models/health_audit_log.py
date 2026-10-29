# -*- coding: utf-8 -*-
from odoo import models, fields, tools, api
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
    record_name = fields.Char('Record', readonly=True)
    field_name = fields.Char('Field Changed', readonly=True)
    old_value = fields.Char('Old Value', readonly=True)
    new_value = fields.Char('New Value', readonly=True)

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
                    COALESCE(mm.subject, '') as record_name,
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
