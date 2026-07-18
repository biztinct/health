# -*- coding: utf-8 -*-
"""Coded-diagnosis → problem-list sync hook (condition-spine handover §2.2).

Every write of the ICD-10 coded sidecar (``condition_code_ids``) converges into
``health.condition`` records here — the SOLE production writer is
``health.ai.code.suggestion.action_approve`` (a sudo note.write), and manual
tags come through the many2many_tags widget on the note form; BOTH are
``write()`` on the note, so ONE hook catches all paths.

ADDITIVE-ONLY: the sync creates, links evidence and reactivates; it NEVER
deletes, resolves or inactivates, and it NEVER writes the note, the sidecar or
any clinical/accounting model (safety rails §3). Removing a code from a note
does NOT touch the condition — corrections are a human act on the condition
form.
"""

from odoo import _, api, fields, models


class HealthClinicalNote(models.Model):
    _inherit = 'health.clinical.note'

    @api.model_create_multi
    def create(self, vals_list):
        notes = super().create(vals_list)
        # @api.constrains-style: create does not carry the m2m in a way a
        # write hook would see, so sync the notes that got codes at create.
        coded = notes.filtered(lambda note: note.condition_code_ids)
        if coded:
            coded._sync_health_conditions()
        return notes

    def write(self, vals):
        result = super().write(vals)
        if 'condition_code_ids' in vals:
            self._sync_health_conditions()
        return result

    def _sync_health_conditions(self):
        """Additive, idempotent, sudo — creates/links/reactivates problem-list
        records for every ICD-10 code currently on each note's sidecar."""
        Condition = self.env['health.condition'].sudo()
        for note in self:
            patient = note.order_id.patient_id
            if not patient:
                continue
            asserted = (note.create_date or fields.Datetime.now()).date()
            for code in note.condition_code_ids:
                cond = Condition.with_context(active_test=False).search([
                    ('patient_id', '=', patient.id),
                    ('code_id', '=', code.id),
                ], limit=1)
                if not cond:
                    # First assertion — recorded_date / recorder_id are the
                    # provenance of THIS note and never move afterwards.
                    Condition.create({
                        'patient_id': patient.id,
                        'code_id': code.id,
                        'recorded_date': asserted,
                        'last_asserted_date': asserted,
                        'recorder_id': note.author_id.id,
                        'note_ids': [(4, note.id)],
                    })
                    continue
                new_vals = {}
                if note not in cond.note_ids:
                    new_vals['note_ids'] = [(4, note.id)]
                if not cond.last_asserted_date or asserted > cond.last_asserted_date:
                    new_vals['last_asserted_date'] = asserted
                reactivated = not cond.active or cond.clinical_status != 'active'
                if reactivated:
                    # A fresh clinical assertion re-opens a resolved/archived
                    # problem (still additive — never resolves).
                    new_vals['active'] = True
                    new_vals['clinical_status'] = 'active'
                if new_vals:
                    cond.write(new_vals)
                if reactivated:
                    cond.message_post(body=_(
                        'Reactivated by a fresh assertion on note %s.',
                        note.display_name or note.id))
