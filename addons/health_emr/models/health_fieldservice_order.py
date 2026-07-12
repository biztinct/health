# -*- coding: utf-8 -*-
"""Protect finalized medical records from cascade deletion.

`health.clinical.note.order_id` is `ondelete='cascade'`, so deleting an FSO
would delete its notes at the DB level — bypassing the note's own Python
`unlink()` guard (§5.30 cascade caveat). A finalized note is a permanent
medical record (Circular 13/2025 retention), so block deletion of any order
that owns one. No superuser escape (uid 1 forces su=True)."""
from odoo import _, models
from odoo.exceptions import UserError


class HealthFieldserviceOrder(models.Model):
    _inherit = 'health.fieldservice.order'

    def unlink(self):
        final_notes = self.env['health.clinical.note'].sudo().search([
            ('order_id', 'in', self.ids),
            ('emr_state', '=', 'final'),
        ])
        if final_notes:
            blocked = final_notes.mapped('order_id')
            raise UserError(_(
                'These service orders have finalized (signed) clinical notes '
                'that are permanent medical records and cannot be deleted '
                '(%(names)s). Archive or cancel the order instead.',
                names=', '.join(blocked.mapped('display_name'))))
        return super().unlink()
