# -*- coding: utf-8 -*-
"""Client-maintained dropdown vocabularies.

WHY ONE MODEL AND NOT TWENTY-THREE
----------------------------------
Twenty-four Selection fields across the CMS were plain hardcoded lists — the
client could not add "one more referral source" or "one more service interest"
without a developer. Each could have become its own small model, but that is
twenty-three model files, list views, forms, actions, ACL blocks and navigator
tabs for what is, in every case, the same four columns: a code, a label, an
order and an on/off switch. None of them carries extra attributes; anything
that does (urgency levels have response times, referral SOURCES have
cost-per-lead) already IS its own model and is untouched here.

So: one `health.lookup.value` table discriminated by `category_id`, and each
converted field is a Many2one into it filtered on the category. Adding a
twenty-fifth vocabulary later is a row in lookup_registry.py, not a module.

WHAT THE CLIENT SEES
--------------------
Never the merge. Master Data > Value Categories lists the vocabularies; each
one drills into its own filtered, inline-editable screen that carries
`default_category_id`, so importing there needs no category column at all.

CODES
-----
`code` is the identity: it is what a re-import matches on, and what a future
Tier-2 conversion will compare against in python (`rec.field_id.code == 'x'`).
It is set once and then read-only — renaming one would silently break both.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import ormcache

_logger = logging.getLogger(__name__)


class HealthLookupCategory(models.Model):
    _name = 'health.lookup.category'
    _description = 'Dropdown Value Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True, copy=False,
        help='Technical key this vocabulary is addressed by. Never change it.')
    description = fields.Char(translate=True)
    used_by = fields.Char(
        string='Used By', readonly=True,
        help='The model fields that draw their options from this vocabulary.')
    value_ids = fields.One2many(
        'health.lookup.value', 'category_id', string='Values')
    value_count = fields.Integer(compute='_compute_value_count')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'A vocabulary with this code already exists.'),
    ]

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints, so the declaration
        # above is documentation only — the index has to be created by hand or
        # duplicate codes slip through and break code-based lookups.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_lookup_category_code_uidx
                ON health_lookup_category (code)
        """)

    @api.depends('value_ids')
    def _compute_value_count(self):
        counts = dict(self.env['health.lookup.value']._read_group(
            [('category_id', 'in', self.ids)], ['category_id'], ['__count']))
        for category in self:
            category.value_count = counts.get(category, 0)

    def action_open_values(self):
        """Drill into one vocabulary.

        This is the per-vocabulary screen the client imports from: the context
        carries `default_category_id`, so a spreadsheet of just code/name/
        name_vi loads correctly without a category column, and the domain keeps
        the merge invisible.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'health.lookup.value',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {
                'default_category_id': self.id,
                'search_default_category_id': self.id,
                'active_test': False,
            },
            'views': [
                (self.env.ref('health_base.view_health_lookup_value_list').id, 'list'),
                (False, 'form'),
            ],
        }


class HealthLookupValue(models.Model):
    _name = 'health.lookup.value'
    _description = 'Dropdown Value'
    _inherit = ['health.vi.alias.mixin']
    _vi_alias_field = 'name_vi'
    _order = 'category_id, sequence, name'

    name = fields.Char(required=True, translate=True)
    # One row carries BOTH languages, which is what lets a single import sheet
    # do the same — see health.vi.alias.mixin.
    name_vi = fields.Char(
        string='Vietnamese Name', compute='_compute_vi_alias',
        inverse='_inverse_vi_alias', store=False)
    code = fields.Char(
        required=True, index=True, copy=False,
        help='Stable technical key. Used to match rows on re-import — changing '
             'it makes the next import create a duplicate instead of updating.')
    category_id = fields.Many2one(
        'health.lookup.category', required=True, ondelete='cascade',
        index=True, string='Category')
    # Stored so every converted field can filter with a plain, indexable
    # domain: [('category_code', '=', 'facility_type')].
    category_code = fields.Char(
        related='category_id.code', store=True, index=True, readonly=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    usage_count = fields.Integer(
        compute='_compute_usage_count', search='_search_usage_count',
        string='In Use',
        help='How many records currently point at this value.')

    _sql_constraints = [
        ('code_unique_per_category', 'unique(category_id, code)',
         'That code is already used in this vocabulary.'),
    ]

    def init(self):
        # Same Odoo 19 gotcha. This one matters more: `code` is what a
        # re-import matches on, so a duplicate would make an import update an
        # arbitrary one of the two rows.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_lookup_value_code_uidx
                ON health_lookup_value (category_id, code)
        """)

    @api.model
    def _seed_from_registry(self):
        """Seed the vocabularies on demand, from a data file.

        post_init_hook already does this, but it runs AFTER the data and demo
        files — so anything in those files that resolves a value by code (the
        demo patients' gender, for one) would find an empty table. Calling this
        first from the file itself fixes the ordering. Idempotent.
        """
        from ..lookup_migration import seed_lookup_values
        seed_lookup_values(self.env)

    @api.model
    def _default_for(self, category_code, value_code):
        """Default helper for converted fields that had a Selection default.

        Used as `default=lambda self: self.env['health.lookup.value']
        ._default_for('vn_region', 'south')`. Returns False rather than raising
        if the value is missing, so a half-seeded database still opens the form.

        The table check is load-bearing, not defensive clutter: Odoo evaluates
        column defaults while it is CREATING those columns, and a module that
        owns a converted field can reach this during its own `_auto_init` —
        before health_base has created health_lookup_value in a fresh or
        partially-upgraded database. Without the guard the whole registry fails
        with 'relation "health_lookup_value" does not exist'. The back-fill
        migration sets the real value afterwards either way.
        """
        if not value_code:
            return False
        self.env.cr.execute("SELECT to_regclass('health_lookup_value')")
        if not self.env.cr.fetchone()[0]:
            return False
        return self.with_context(active_test=False).search([
            ('category_code', '=', category_code),
            ('code', '=', value_code),
        ], limit=1).id or False

    @api.model
    @ormcache()
    def _referencing_fields(self):
        """Every (model, field) in the registry that points here.

        Derived from the ORM rather than bookkept on the category, because a
        vocabulary can back more than one field — "Vietnam Region" is shared by
        health.province and health.vietnamese.district — and because a field
        added later is then picked up with no extra step. Cached: it only
        changes when the registry does.
        """
        out = []
        for model_name, model in self.env.registry.items():
            for fname, field in model._fields.items():
                if (field.comodel_name == 'health.lookup.value'
                        and field.store and field.type == 'many2one'):
                    out.append((model_name, fname))
        return tuple(out)

    def _compute_usage_count(self):
        totals = self._usage_totals()
        for record in self:
            record.usage_count = totals.get(record.id, 0)

    def _usage_totals(self):
        """value id -> number of records pointing at it, across every field."""
        totals = {}
        for model_name, fname in self._referencing_fields():
            Model = self.env.get(model_name)
            if Model is None or not Model._auto:
                continue
            try:
                groups = Model.with_context(active_test=False)._read_group(
                    [(fname, '!=', False)], [fname], ['__count'])
            except Exception:  # a model the current user cannot read
                continue
            for value, count in groups:
                if value:
                    totals[value.id] = totals.get(value.id, 0) + count
        return totals

    def _search_usage_count(self, operator, value):
        """Makes the "Unused" filter work — which is what tells the client
        which values are safe to delete rather than archive."""
        import operator as operator_module
        compare = {
            '=': operator_module.eq, '!=': operator_module.ne,
            '<': operator_module.lt, '<=': operator_module.le,
            '>': operator_module.gt, '>=': operator_module.ge,
        }.get(operator)
        if compare is None or not isinstance(value, int):
            raise NotImplementedError(
                'Unsupported search on usage_count: %s %r' % (operator, value))
        totals = self._usage_totals()
        all_ids = self.with_context(active_test=False).search([]).ids
        matching = [rid for rid in all_ids if compare(totals.get(rid, 0), value)]
        return [('id', 'in', matching)]

    def unlink(self):
        """Archive, don't delete, anything still in use.

        Deleting a value that live records point at either raises a FK error or
        (with ondelete='set null') silently blanks a field on a clinical
        record. Neither is an acceptable outcome for a mis-click on a
        reference-data screen, so in-use values must be archived instead.
        """
        in_use = self.filtered(lambda v: v.usage_count)
        if in_use:
            raise UserError(_(
                'These values are still used by existing records, so they '
                'cannot be deleted:\n\n%s\n\nUncheck "Active" instead — the '
                'value stops being offered in new records and the existing '
                'ones keep their history.',
                '\n'.join('  • %s (%s): %s record(s)' % (
                    v.display_name, v.category_id.name, v.usage_count)
                    for v in in_use)))
        return super().unlink()
