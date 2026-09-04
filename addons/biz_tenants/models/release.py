# -*- coding: utf-8 -*-
"""A named release: a photograph of what the master ran at one moment.

WHY A RECORD AND NOT A COMPARISON DONE FRESH EACH TIME. "In step" used to mean
"the same as the master, right now" — a moving target. The master gets a fix at
11:00 and every customer is behind at 11:01, through nobody's decision. A
release freezes the answer: THIS list, at THESE versions, is what everybody is
aiming at, and it changes when somebody cuts a new one.

The photograph includes the parts a customer never gets. The reader is the
platform's owner, and showing them an edited master would make the count on
this screen disagree with the count on their own system.
"""
import json

from odoo import api, fields, models


class BizRelease(models.Model):
    _name = 'biz.release'
    _description = 'A named release of the product'
    _order = 'cut_on desc, id desc'

    name = fields.Char(required=True, index=True,
                       help="Dated name, e.g. 2026.09.04.")
    cut_on = fields.Datetime(default=fields.Datetime.now, required=True)
    notes = fields.Text(
        help="What changed, in plain words. THE CUSTOMERS READ THIS — it is "
             "what appears on their own About screen.")
    #: JSON `{module name: version}` for everything installed on the master when
    #: the release was cut. Text rather than a typed column so the record can
    #: still be read on a database whose framework has moved on.
    module_fingerprint = fields.Text(default='{}')
    module_count = fields.Integer()
    is_current = fields.Boolean(
        index=True,
        help="Exactly one release is current; cutting a new one stands the "
             "previous one down.")
    cut_by = fields.Many2one('res.users', ondelete='set null')
    tenant_ids = fields.One2many('biz.tenant', 'release_id')

    # ⚠ `models.Constraint`, NOT the old `_sql_constraints` list — that form is
    # accepted and never applied on this framework, so the constraint simply
    # would not exist. See the same note on `biz.tenant`.
    _name_unique = models.Constraint(
        'UNIQUE (name)',
        "A release with that name already exists.")

    def fingerprint(self):
        """The photograph, as a plain dict. Never raises on a damaged record."""
        self.ensure_one()
        try:
            data = json.loads(self.module_fingerprint or '{}')
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    @api.model
    def current(self):
        """The release everybody is aiming at, or an empty recordset."""
        return self.sudo().search([('is_current', '=', True)], limit=1)

    def make_current(self):
        """Become the one current release. The only place that field is set."""
        self.ensure_one()
        others = self.sudo().search([('is_current', '=', True),
                                     ('id', '!=', self.id)])
        if others:
            others.write({'is_current': False})
        self.sudo().write({'is_current': True})
        return self
