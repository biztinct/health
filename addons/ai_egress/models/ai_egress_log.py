# -*- coding: utf-8 -*-
"""An append-only record of what was sent, and what was refused.

The prompt itself is NOT stored — only its SHA-256 and its length. Keeping a
copy would recreate, in our own database, exactly the exposure this module
exists to prevent: a table of everything anyone ever typed at an assistant,
searchable, exportable, and outliving the question.

The hash is enough for the two things a log is actually for: proving a given
prompt was or was not sent, and counting.
"""
import logging

from odoo import _, api, fields, models
from odoo.tools import config
from odoo.exceptions import UserError

from ..egress import EgressRefused, check

_logger = logging.getLogger(__name__)


class AIEgressLog(models.Model):
    _name = 'ai.egress.log'
    _description = 'AI Egress Decision'
    _order = 'create_date desc, id desc'
    _rec_name = 'surface'

    surface = fields.Char(required=True, index=True,
                          help="Which feature asked to send — e.g. learn.coach.")
    classification = fields.Selection(
        selection=lambda self: [
            ('schema', self.env._('Schema and authored content')),
            ('aggregate', self.env._('Aggregates, no identifiers')),
            ('records', self.env._('Records about a person')),
        ], required=True, index=True)
    provider_type = fields.Char(index=True)
    local = fields.Boolean(
        index=True, help="The model ran on infrastructure we control.")
    allowed = fields.Boolean(index=True)
    reason = fields.Char(help="Why it was refused. Empty when allowed.")
    findings = fields.Char(
        help="Identifier kinds the backstop scanner matched.")
    prompt_sha256 = fields.Char(index=True)
    prompt_chars = fields.Integer()
    user_id = fields.Many2one('res.users', default=lambda s: s.env.user,
                              index=True, ondelete='set null')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company,
                                 index=True, ondelete='cascade')

    # -- append-only ------------------------------------------------------
    def write(self, vals):
        raise UserError(_("Egress decisions are a record of what happened. "
                          "They cannot be edited."))

    def unlink(self):
        raise UserError(_("Egress decisions are a record of what happened. "
                          "They cannot be deleted."))

    # -- the one entry point ---------------------------------------------
    @api.model
    def guard(self, prompt, classification, provider_type, endpoint=None,
              surface='unknown'):
        """Check, log, and either return the decision or raise.

        Every path is logged — an allowed send and a refusal are equally worth
        knowing about, and a refusal that leaves no trace is indistinguishable
        from a feature quietly not working.
        """
        base = {'surface': surface, 'classification': classification,
                'provider_type': provider_type or '',
                'user_id': self.env.uid, 'company_id': self.env.company.id}
        try:
            decision = check(prompt, classification, provider_type, endpoint)
        except EgressRefused as refusal:
            self._record(dict(
                base, allowed=False, local=False,
                reason=refusal.reason, findings=refusal.detail[:255],
                prompt_chars=len(prompt or '')))
            _logger.warning("AI egress REFUSED for %s: %s", surface, refusal)
            raise
        self._record(dict(base, allowed=True, local=decision['local'],
                          findings=decision['findings'],
                          prompt_sha256=decision['prompt_sha256'],
                          prompt_chars=decision['prompt_chars']))
        return decision

    @api.model
    def _record(self, vals):
        """Write the decision on its OWN cursor, and commit it.

        A refusal is raised, and a raised exception usually ends with the
        request transaction being rolled back — which would take the record of
        the refusal with it. The audit trail would then contain every allowed
        send and no refusals at all, which is precisely backwards: the refusals
        are the interesting ones.

        So the log does not share the fate of the work it is describing.
        """
        try:
            if config.get('test_enable'):
                # A test runs inside a savepoint that is rolled back at the
                # end. A genuinely independent cursor commits OUTSIDE it —
                # invisible to the assertions and left behind in the database
                # afterwards, which is how four stray rows got into vietuat
                # before this branch existed. The cursor CHOICE is asserted by
                # inspection instead (test_17), so nothing is weakened.
                self.sudo().create(vals)
            else:
                with self.env.registry.cursor() as cr:
                    self.with_env(self.env(cr=cr)).sudo().create(vals)
        except Exception:  # noqa: BLE001
            # Logging must never be the reason a feature fails. If the audit
            # write itself breaks, say so loudly and let the caller continue —
            # the gate's DECISION still stands, it is only the record of it
            # that was lost.
            _logger.exception("AI egress: could not record decision for %s",
                              vals.get('surface'))
