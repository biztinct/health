# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class HealthPatient(models.Model):
    """
    Extend health.patient to add Zalo integration.

    Links patient records to Zalo conversations for messaging.
    """
    _inherit = 'health.patient'

    # Zalo Integration (via partner)
    zalo_user_id = fields.Char(
        string='Zalo User ID',
        related='partner_id.zalo_user_id',
        readonly=False,
        store=True,
    )

    zalo_conversation_ids = fields.One2many(
        'zalo.conversation',
        'patient_id',
        string='Zalo Conversations',
    )

    zalo_conversation_count = fields.Integer(
        string='Zalo Conversations',
        compute='_compute_zalo_conversation_count',
    )

    has_zalo = fields.Boolean(
        string='Has Zalo',
        related='partner_id.has_zalo',
    )

    @api.depends('zalo_conversation_ids')
    def _compute_zalo_conversation_count(self):
        """Count Zalo conversations"""
        for patient in self:
            patient.zalo_conversation_count = len(patient.zalo_conversation_ids)

    def action_open_zalo_chat(self):
        """Open Zalo chat for patient (delegates to partner)"""
        self.ensure_one()
        return self.partner_id.action_open_zalo_chat()

    def action_call_zalo(self):
        """Call patient via Zalo (delegates to partner)"""
        self.ensure_one()
        return self.partner_id.action_call_zalo()

    def action_view_zalo_conversations(self):
        """View all Zalo conversations for this patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Zalo Conversations'),
            'res_model': 'zalo.conversation',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }

    def action_send_zalo_notification(self):
        """Open wizard to send Zalo notification to patient"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Zalo Notification'),
            'res_model': 'zalo.send.notification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.id,
                'default_partner_id': self.partner_id.id,
            },
        }
