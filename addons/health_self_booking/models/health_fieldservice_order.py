import logging

from odoo import models

_logger = logging.getLogger(__name__)


class HealthFieldServiceOrder(models.Model):
    """A6 — optional auto-invite after visit completion.

    Post-super, try/except-wrapped: a self-booking failure must NEVER block
    completion (family-link precedent). Gated by
    ``health_self_booking.auto_invite_after_completion`` (default False), so
    installing changes nothing until a human opts in.
    """
    _inherit = 'health.fieldservice.order'

    def action_complete_service(self):
        res = super().action_complete_service()
        self._selfbook_on_complete()
        return res

    def _selfbook_on_complete(self):
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param(
            'health_self_booking.auto_invite_after_completion', 'False') in (
            'True', 'true', '1')
        if not enabled:
            return
        Invite = self.env['health.selfbook.invite']
        for fso in self:
            if not fso.patient_id:
                continue
            try:
                # raise_if_no_source=False: a patient with nothing bookable
                # is silently skipped (never create an invite that cannot
                # confirm — A3).
                Invite.send_invite_for_patient(
                    fso.patient_id, raise_if_no_source=False)
            except Exception:  # noqa: BLE001 — never block completion
                _logger.exception(
                    'Self-booking auto-invite failed for FSO %s', fso.id)
