# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BookingLostWizard(models.TransientModel):
    """Wizard to capture booking lost reason"""
    _name = 'health.crm.booking.lost.wizard'
    _description = 'Booking Lost Reason Wizard'

    lead_id = fields.Many2one('crm.lead', string='Contact', required=True, ondelete='cascade')
    booking_lost_reason = fields.Text(string='Booking Lost Reason', required=True,
                                       help='Please provide the reason why this booking was lost')

    def action_confirm_booking_lost(self):
        """Confirm booking lost and update lead"""
        self.ensure_one()

        if not self.booking_lost_reason or not self.booking_lost_reason.strip():
            raise UserError(_('Please provide a reason for marking this booking as lost.'))

        # Find a lost stage (fold=True) without team_id
        lost_stage = self.env['crm.stage'].search([
            ('fold', '=', True),
            ('team_id', '=', False)
        ], limit=1)

        # If no folded stage without team_id, find "Opportunity Lost" stage
        if not lost_stage:
            lost_stage = self.env['crm.stage'].search([
                ('name', 'ilike', 'lost'),
                '|', ('team_id', '=', False), ('team_id', '=', self.lead_id.team_id.id)
            ], limit=1)

        vals = {
            'contact_outcome': 'booking_lost',
            'health_contact_outcome': 'rejected',
            'booking_lost_reason': self.booking_lost_reason,
        }

        if lost_stage:
            vals['stage_id'] = lost_stage.id

        self.lead_id.write(vals)

        return {'type': 'ir.actions.act_window_close'}
