# -*- coding: utf-8 -*-
"""The ONLY clinical-note schema touch: an ``audio_ids`` m2m for scribe
recordings (mirrors the existing ``image_ids`` photo relation) plus a
manager-only "Transcribe now" retry action."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class HealthClinicalNote(models.Model):
    _inherit = 'health.clinical.note'

    audio_ids = fields.Many2many(
        'ir.attachment',
        'health_clinical_note_audio_rel',
        'note_id', 'attachment_id',
        string='Scribe Recordings')
    scribe_job_ids = fields.One2many(
        'health.scribe.job', 'note_id', string='Scribe Jobs')
    scribe_pending_count = fields.Integer(
        string='Pending Recordings', compute='_compute_scribe_pending_count')

    @api.depends('scribe_job_ids.state')
    def _compute_scribe_pending_count(self):
        for note in self:
            note.scribe_pending_count = len(note.scribe_job_ids.filtered(
                lambda j: j.state == 'pending'))

    def action_transcribe_audio(self):
        """Run transcription now for this note's pending recordings
        (manager+ only, server-side guard — retry after fixing the endpoint)."""
        self.ensure_one()
        Job = self.env['health.scribe.job']
        if not any(self.env.user.has_group(g) for g in (
                'health_base.group_healthcare_manager',
                'health_base.group_healthcare_admin',
                'health_base.group_healthcare_owner')):
            raise AccessError(_(
                "Only a manager may run scribe transcription jobs."))
        Job._run_jobs(self.scribe_job_ids.filtered(
            lambda j: j.state == 'pending'))
        return True
