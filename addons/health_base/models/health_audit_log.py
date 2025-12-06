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
                    COALESCE(
                        -- Prefer the author_id from mail_message if it's not a system user
                        CASE WHEN mm.author_id != (
                            SELECT id FROM res_users WHERE login = 'Default User Template' LIMIT 1
                        ) THEN mm.author_id
                        -- Otherwise fall back to the message's actual user (create_uid)
                        ELSE mm.create_uid
                        END,
                        mm.author_id
                    ) as user_id,
                    mm.model,
                    COALESCE(im.name->>'en_US', mm.model) as model_name,
                    mm.res_id,
                    COALESCE(mm.subject, '') as record_name,
                    COALESCE(mf.field_description->>'en_US', mf.name) as field_name,
                    mtv.old_value_char as old_value,
                    mtv.new_value_char as new_value
                FROM mail_tracking_value mtv
                JOIN mail_message mm ON mm.id = mtv.mail_message_id
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
                )
                AND mtv.field_id IS NOT NULL
                ORDER BY mm.date DESC
            )
        """ % self._table)
