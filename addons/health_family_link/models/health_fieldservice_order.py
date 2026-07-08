import logging

from odoo import models

_logger = logging.getLogger(__name__)


class HealthFieldServiceOrder(models.Model):
    """A7 — family-link triggers on the visit lifecycle.

    Both hooks run post-super and are wrapped: a family-link failure must
    NEVER block the booking/completion workflow (messaging-module precedent).
    Re-confirmation / double completion are safe: the link get-or-create is
    idempotent and the ZNS dedup keys make the sends no-op.
    """
    _inherit = 'health.fieldservice.order'

    def action_confirm_booking(self):
        res = super().action_confirm_booking()
        self._family_link_on_confirm()
        return res

    def action_complete_service(self):
        res = super().action_complete_service()
        self._family_link_on_complete()
        return res

    def _family_link_on_confirm(self):
        """Pre-visit family_visit_link (A2 cond 1+3 — schedule info is not
        medical info, so can_receive_medical_info is not required here)."""
        FamilyLink = self.env['health.family.link']
        for fso in self:
            try:
                relations = FamilyLink._eligible_relations(fso, require_medical=False)
                for relation in relations:
                    if not relation.representative_id:
                        continue
                    link = FamilyLink._get_or_create_link(fso, relation)
                    link._send_zns('family_visit_link')
            except Exception:  # noqa: BLE001 — never block confirmation
                _logger.exception(
                    'Family link confirm hook failed for FSO %s', fso.id)

    def _family_link_on_complete(self):
        """Post-visit family_snapshot (A2 all three conditions). Extends the
        link expiry to actual end + 24h before sending."""
        FamilyLink = self.env['health.family.link']
        for fso in self:
            try:
                relations = FamilyLink._eligible_relations(fso, require_medical=True)
                for relation in relations:
                    if not relation.representative_id:
                        continue
                    link = FamilyLink._get_or_create_link(fso, relation)
                    link.sudo().write(
                        {'expires_at': FamilyLink._completion_expiry(fso)})
                    link._send_zns('family_snapshot')
            except Exception:  # noqa: BLE001 — never block completion
                _logger.exception(
                    'Family link complete hook failed for FSO %s', fso.id)
