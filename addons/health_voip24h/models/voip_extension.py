# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class VoIPExtension(models.Model):
    """
    VoIP Extensions/Lines.

    Manages PBX extensions and staff assignments.
    """
    _name = 'voip.extension'
    _description = 'VoIP Extension/Line'
    _order = 'extension_number'

    name = fields.Char(
        string='Extension Name',
        required=True,
    )
    extension_number = fields.Char(
        string='Extension Number',
        required=True,
        index=True,
    )
    extension_type = fields.Selection([
        ('internal', 'Internal Extension'),
        ('external', 'External Line'),
        ('queue', 'Call Queue'),
        ('ivr', 'IVR'),
    ], string='Type', default='internal', required=True)

    # Staff Assignment
    user_id = fields.Many2one(
        'res.users',
        string='Assigned User',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Assigned Employee',
    )

    # Configuration
    voip_config_id = fields.Many2one(
        'voip.config',
        string='VoIP Configuration',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        'res.company',
        related='voip_config_id.company_id',
        store=True,
    )

    # Settings
    allow_incoming = fields.Boolean(
        string='Allow Incoming Calls',
        default=True,
    )
    allow_outgoing = fields.Boolean(
        string='Allow Outgoing Calls',
        default=True,
    )
    record_calls = fields.Boolean(
        string='Record Calls',
        default=True,
    )

    # Statistics
    total_calls = fields.Integer(
        string='Total Calls',
        compute='_compute_call_stats',
    )
    missed_calls = fields.Integer(
        string='Missed Calls',
        compute='_compute_call_stats',
    )

    active = fields.Boolean(
        default=True,
    )

    def _compute_call_stats(self):
        for ext in self:
            logs = self.env['voip.call.log'].search([
                ('extension_id', '=', ext.id)
            ])
            ext.total_calls = len(logs)
            ext.missed_calls = len(logs.filtered(lambda l: l.call_type == 'missed'))
