# -*- coding: utf-8 -*-

import logging
from datetime import datetime, time, timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VoIPSyncWizard(models.TransientModel):
    """Manual CDR sync over an explicit date range."""
    _name = 'voip.sync.wizard'
    _description = 'VoIP24h Manual Sync Wizard'

    voip_config_id = fields.Many2one(
        'voip.config',
        string='VoIP Configuration',
        required=True,
        default=lambda self: self.env['voip.config'].get_active_config(),
    )
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.context_today(self) - timedelta(days=7),
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.context_today,
    )
    download_recordings = fields.Boolean(
        string='Queue Recording Downloads',
        default=True,
        help='Recording downloads are processed by the recordings cron '
             'after the call logs are synced.',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise UserError(_('The start date must be before the end date.'))

    def action_sync(self):
        from ..services.cdr_sync import sync_call_history
        self.ensure_one()

        config = self.voip_config_id
        config._check_credentials()

        result = sync_call_history(
            config.sudo(),
            from_date=datetime.combine(self.date_from, time.min),
            to_date=datetime.combine(self.date_to, time.max),
            create_recordings=self.download_recordings,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Completed'),
                'message': _(
                    '%(created)s new calls, %(updated)s updated, %(errors)s errors.',
                    created=result['created'],
                    updated=result['updated'],
                    errors=result['errors'],
                ),
                'type': 'success' if not result['errors'] else 'warning',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Call Logs'),
                    'res_model': 'voip.call.log',
                    'view_mode': 'list,form',
                    'domain': [('voip_config_id', '=', config.id)],
                },
            }
        }
