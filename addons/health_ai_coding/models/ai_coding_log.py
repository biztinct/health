# -*- coding: utf-8 -*-
"""``health.ai.coding.log`` — append-only AI call audit (handover §2.5).

Clones the shape of ``bi.ai.log``: one row per LLM call, storing the EXACT
redacted prompt (system + user) and the raw response, plus timing and the
counts. Two hardening deltas over the bi precedent:

* **Append-only for everyone, admin included.** ``uid 1`` always runs as su
  (conventions §4), so a ``self.env.su`` guard would be dead code — the
  write/unlink blocks here are UNCONDITIONAL. The request text is still
  pseudonymised PHI, so a stray edit must never be possible.
* **``note_id`` is ``ondelete='set null'``, not cascade.** Ledger §17: a
  cascade delete from a note would try to ORM-unlink these rows and hit the
  unconditional ``unlink`` guard, making notes undeletable. A DB-level
  ``SET NULL`` bypasses the ORM guard, so deleting a note just detaches its
  logs.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class HealthAiCodingLog(models.Model):
    _name = 'health.ai.coding.log'
    _description = 'AI Coding Call Log'
    _order = 'id desc'
    _log_access = False

    note_id = fields.Many2one(
        'health.clinical.note', string='Clinical Note',
        ondelete='set null', index=True)
    provider_id = fields.Many2one(
        'bi.ai.provider', string='AI Provider', ondelete='set null')
    request_json = fields.Json(
        string='Request (redacted)',
        help='The exact system + user prompt sent to the model — pseudonymised.')
    response_json = fields.Json(string='Raw Response')
    duration_ms = fields.Integer(string='Duration (ms)')
    suggested_count = fields.Integer(string='Suggestions Created')
    dropped_codes = fields.Integer(
        string='Dropped Codes',
        help='Model-proposed codes not present in the ICD-10 catalog.')
    error = fields.Char(string='Error')
    created_at = fields.Datetime(
        string='Created At', default=fields.Datetime.now, index=True)

    # ------------------------------------------------------------------
    # Append-only — unconditional (conventions §4: uid 1 runs as su).
    # ------------------------------------------------------------------
    def write(self, vals):
        raise UserError(_(
            "AI coding log entries are append-only and cannot be modified."))

    def unlink(self):
        raise UserError(_(
            "AI coding log entries are append-only and cannot be deleted."))
