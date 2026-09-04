# -*- coding: utf-8 -*-
"""One source of truth for the Vietnamese name of a lookup record.

THE PROBLEM THIS REPLACES
-------------------------
Seven lookup models grew a parallel Vietnamese column next to `name`
(`name_vi`, `name_vietnamese`, `vietnamese_name`). A many2one dropdown renders
`display_name`, which reads `name` — so none of those columns were ever visible
where it mattered: the user picks a service type, a contact reason, a province
from a dropdown and sees English no matter what language they logged in with.
Worse, the Vietnamese text existed in two unrelated places that drifted.

THE FIX
-------
`name` becomes `translate=True` (a jsonb column keyed by language, which Odoo
falls back to en_US for), and the old column becomes a NON-STORED mirror of the
vi_VN translation:

    class Whatever(models.Model):
        _inherit = ['health.vi.alias.mixin']
        _vi_alias_field = 'name_vi'

        name = fields.Char(required=True, translate=True)
        name_vi = fields.Char(
            'Vietnamese Name', compute='_compute_vi_alias',
            inverse='_inverse_vi_alias', store=False)

Reading `rec.name_vi` returns the vi_VN value; writing it sets the vi_VN
translation. Every existing consumer — the eMAR JS, the vitals API, the seed
data files that write `<field name="name_vi">` — keeps working unchanged, but
there is now exactly one place the value lives.

The column left behind in postgres is intentionally NOT dropped: the
per-module post-migrations read it once to seed the translations, and an
orphan varchar costs nothing.
"""
from odoo import api, fields, models

VI_LANG = 'vi_VN'


class HealthViAliasMixin(models.AbstractModel):
    _name = 'health.vi.alias.mixin'
    _description = 'Vietnamese Name Alias (mirrors the vi_VN translation)'

    # Name of the alias field on the concrete model.
    _vi_alias_field = 'name_vi'
    # The translatable field the alias mirrors.
    _vi_alias_source = 'name'

    def _vi_lang_installed(self):
        """Is vi_VN actually a language on THIS database?

        Reading or writing a translated field in a language the database does
        not have raises `KeyError: '<model>.<field>'` out of the ORM's cache —
        it does not fall back to English. That is never the case here (this
        clinic added Vietnamese years ago) and ALWAYS the case on a brand-new
        database, so both halves of this mixin have to ask first. Without it a
        fresh install of any of the seven models dies while loading its own
        seed data, which is exactly what building the golden template found
        (SAAS H3).

        `get_installed()` reads through an ormcache, so this costs nothing per
        record.
        """
        return any(code == VI_LANG
                   for code, _name in self.env['res.lang'].get_installed())

    @api.depends(lambda self: [self._vi_alias_source])
    def _compute_vi_alias(self):
        alias, source = self._vi_alias_field, self._vi_alias_source
        if not self._vi_lang_installed():
            # Not "unknown" — there IS no Vietnamese name on a database with no
            # Vietnamese. Assigning False keeps the field computed rather than
            # leaving it unset, which would raise on read.
            for record in self:
                record[alias] = False
            return
        # One extra read in the vi_VN context for the whole recordset, not one
        # per record: `with_context` on the set keeps this to a single query.
        vi_records = self.with_context(lang=VI_LANG)
        for record, vi_record in zip(self, vi_records):
            record[alias] = vi_record[source] or False

    def _inverse_vi_alias(self):
        alias, source = self._vi_alias_field, self._vi_alias_source
        if not self._vi_lang_installed():
            # Dropping the value rather than raising. The alternative — storing
            # it somewhere until the language arrives — would be a second place
            # the Vietnamese name lives, which is the exact drift this mixin
            # exists to remove. Adding the language later and re-running the
            # module's data load puts the labels in.
            return
        for record in self:
            value = record[alias]
            if not value:
                # Blanking the alias is a no-op rather than a translation
                # delete: the seed data files omit it for English-only rows,
                # and dropping the vi text on every such write would be a
                # silent data loss.
                continue
            record.with_context(lang=VI_LANG)[source] = value
