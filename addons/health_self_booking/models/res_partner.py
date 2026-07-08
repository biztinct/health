from odoo import models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """A6 — manual "Send booking link" button on the patient form."""
    _inherit = 'res.partner'

    def action_send_selfbook_link(self):
        """Get-or-create the patient's active rebook invite and send its ZNS.

        Raises a friendly UserError when nothing is bookable (no active
        package, no previous booked service, no fallback product configured)
        so the operator gets feedback instead of a silent no-op.
        """
        self.ensure_one()
        if not self.is_patient:
            raise UserError(_('Booking links can only be sent to patients.'))
        invite = self.env['health.selfbook.invite'].send_invite_for_patient(
            self, raise_if_no_source=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Booking link ready'),
                'message': _('A self-booking link has been prepared for %s.',
                             self.name),
                'sticky': False,
            },
        }
