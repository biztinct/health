# -*- coding: utf-8 -*-
"""Extend the family visit link with the messaging page context.

The token page (health_family_link.family_page) gains a message section. We
do NOT edit the family_link controller or its render data assembly — this
method is called by our own public controller to augment the render context.
"""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

_ENABLED_PARAM = 'health_family_messages.enabled'


class HealthFamilyLink(models.Model):
    _inherit = 'health.family.link'

    def _messaging_enabled(self):
        """Global master switch (default False) AND per-recipient eligibility
        (receives_visit_updates + data_sharing consent) — same gate the page
        itself uses; can_receive_medical_info is NOT required to write."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param(_ENABLED_PARAM, 'False') not in ('True', 'true', '1'):
            return False
        relation = self.relation_id
        if not relation or not relation.receives_visit_updates:
            return False
        patient = self.fso_id.patient_id
        if not patient:
            return False
        return bool(self.env['health.consent'].check_consent(
            patient, 'data_sharing'))

    def _messaging_context(self, mark_read=True):
        """Render data for the token-page message section. Returns messaging
        keys to merge into the family page context. The thread is created
        lazily on first send, so a not-yet-started channel renders an empty
        (but composable) section."""
        self.ensure_one()
        if not self._messaging_enabled():
            return {'messaging_enabled': False, 'messages': [], 'msg_token': self.token}
        thread = self.env['health.family.thread'].sudo().search([
            ('patient_id', '=', self.fso_id.patient_id.id),
            ('relation_id', '=', self.relation_id.id),
        ], limit=1)
        rows = []
        if thread:
            msgs = thread.message_ids.sorted('create_date')
            for m in msgs:
                rows.append({
                    'direction': m.direction,
                    'body': m.body or '',
                    'author': m.author_label or '',
                    'when': self._wall(m.create_date).strftime('%d/%m %H:%M')
                    if m.create_date else '',
                })
            if mark_read:
                # Mark the outbound (team → family) messages as seen by family
                # (test 10) — a read-flag flip is the one write the append-only
                # guard allows.
                unseen = msgs.filtered(
                    lambda x: x.direction == 'out' and not x.read_by_family)
                if unseen:
                    unseen.sudo().write({'read_by_family': True})
        return {
            'messaging_enabled': True,
            'messages': rows,
            'msg_token': self.token,
        }
