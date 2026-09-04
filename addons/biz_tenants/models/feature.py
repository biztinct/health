# -*- coding: utf-8 -*-
"""Which parts of the product a customer has, and which are switched off.

TWO TABLES AND ONE IDEA. `biz.feature` is the catalogue — the parts of the
product that can be sold separately, in the product's own words. `biz.tenant.
feature` is one customer's answer for one of them. A customer with no row for a
feature has it ON: a switch nobody has ever touched must not take half a
product away, and the absence of a decision is not a decision.

⚠ SWITCHING A FEATURE OFF UNINSTALLS NOTHING. The parts of the product stay
exactly where they are; the doors to them close. Uninstalling a module from a
live system takes its data with it, and no sales decision should ever be able
to do that — the day somebody switches Telehealth back on, every session that
was ever held is still there.

WHERE THE ANSWER LIVES. On the customer's own system, as ONE setting written
through the single door the platform already has (`push_settings`). So the
customer's system decides for itself, out of a value it holds, with no call
back to the platform: if this machine vanished tomorrow every clinic would go
on working exactly as it was last told.

⚠ AND THE UNIQUENESS IS `models.Constraint`, NOT `_sql_constraints` (ledger
H63). The list form is INERT on this build and fails silently — no error, no
warning, and two rows for one customer and one feature, which is two answers to
a yes/no question.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import tenants_common as common

_logger = logging.getLogger(__name__)


class BizFeature(models.Model):
    _name = 'biz.feature'
    _description = 'A part of the product that can be switched off'
    _order = 'sequence, id'

    key = fields.Char(
        required=True, index=True,
        help="The name this part is known by on a customer's system. It is "
             "written into their settings, so it never changes.")
    name = fields.Char(required=True, help="What it is called on screen.")
    blurb = fields.Text(
        help="What a customer LOSES when this is off, in their own words. It "
             "is shown on the switched-off page they reach, so it is written "
             "for them and not for us.")
    sequence = fields.Integer(default=10)
    default_on = fields.Boolean(
        default=True,
        help="Whether a brand new customer has it. Everything is on by "
             "default; a switch is a decision somebody takes, not one they "
             "inherit.")
    active = fields.Boolean(default=True)

    _key_unique = models.Constraint(
        'UNIQUE (key)',
        "Two parts of the product cannot share one name.")

    # =====================================================================
    #  SEEDING
    # =====================================================================
    @api.model
    def ensure_seeded(self):
        """Put the product's catalogue in the table, and keep it in step.

        ⚠ `@api.model` IS LOAD-BEARING HERE AND NOT DECORATION (ledger F45).
        A `<function>` in a data file with no arguments reads the FIRST
        argument as the records to call the method on; without the marker the
        upgrade dies on "not enough values to unpack" and the traceback names
        the XML line rather than the method it could not reach.

        IDEMPOTENT, AND IT NEVER OVERWRITES A NAME. The wording of a switch is
        something an operator is invited to improve; only a NEW key is written,
        and a key that has disappeared from the product is archived rather than
        deleted, because a customer may still carry a decision about it.
        """
        specs = common.features()
        if not specs:
            _logger.debug("biz_tenants: no product has said which parts of "
                          "itself can be switched off.")
            return self.browse()
        existing = {f.key: f for f in self.with_context(active_test=False)
                    .sudo().search([])}
        made = self.browse()
        for spec in specs:
            row = existing.get(spec['key'])
            if row:
                # Only the ORDER is kept in step: it is the one field with no
                # human opinion in it.
                if row.sequence != spec['sequence'] or not row.active:
                    row.sudo().write({'sequence': spec['sequence'],
                                      'active': True})
                continue
            made |= self.sudo().create({
                'key': spec['key'], 'name': spec['name'],
                'blurb': spec['blurb'], 'sequence': spec['sequence'],
                'default_on': spec['default_on'],
            })
        gone = set(existing) - {s['key'] for s in specs}
        for key in sorted(gone):
            if existing[key].active:
                existing[key].sudo().write({'active': False})
                _logger.info("biz_tenants: the product no longer has a part "
                             "called \"%s\"; it was put away rather than "
                             "deleted, because customers may still carry a "
                             "decision about it.", key)
        if made:
            _logger.info("biz_tenants: %d parts of the product can be "
                         "switched off (%s new).", len(specs), len(made))
        return made

    @api.model
    def catalogue(self):
        """The switches, seeded on first read.

        SEEDED LAZILY AS WELL AS FROM THE DATA FILE, on purpose. The data file
        runs when this module is installed or upgraded; the product's overlay
        may be installed AFTER it, and then the table would sit empty until
        somebody happened to upgrade the cockpit again.
        """
        rows = self.sudo().search([])
        # Seeded when a registered switch is MISSING, not when the counts
        # differ: a switch a product has retired is archived rather than
        # deleted, so the two numbers legitimately disagree for ever and a
        # count test would re-seed on every read.
        if {f['key'] for f in common.features()} - set(rows.mapped('key')):
            self.ensure_seeded()
            rows = self.sudo().search([])
        return rows


class BizTenantFeature(models.Model):
    _name = 'biz.tenant.feature'
    _description = "One customer's answer about one part of the product"
    _order = 'tenant_id, feature_id'

    tenant_id = fields.Many2one('biz.tenant', required=True, index=True,
                                ondelete='cascade')
    feature_id = fields.Many2one('biz.feature', required=True, index=True,
                                 ondelete='cascade')
    enabled = fields.Boolean(default=True)
    reason = fields.Char(
        help="Why it is off, in a sentence somebody reading this in six "
             "months can act on.")
    changed_at = fields.Datetime(default=fields.Datetime.now)
    changed_by = fields.Many2one('res.users', ondelete='set null')

    _one_answer_per_feature = models.Constraint(
        'UNIQUE (tenant_id, feature_id)',
        "A customer has one answer per part of the product, not two.")

    @api.constrains('enabled', 'reason')
    def _check_reason(self):
        """A switch turned off with no reason is a decision nobody can review.

        Not required — an owner in a hurry must not be stopped — but the
        absence is recorded as such, so the screen can say "no reason given"
        rather than showing an empty cell that reads like a bug.
        """
        for row in self:
            if not row.enabled and row.reason and len(row.reason) > 300:
                raise UserError(self.env._(
                    "Keep the reason under 300 characters — it is a line on a "
                    "screen, not a file note."))
