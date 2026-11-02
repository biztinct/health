# -*- coding: utf-8 -*-
"""A screen that supports Form Studio.

A host is DATA, supplied by the product that owns the screen. This module
ships none: it cannot know which forms are safe to extend, which of their
cards may receive a field, or which fields are load-bearing for the product's
own logic. Those are the product's facts, so they arrive here as records.
"""
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .fs_common import ANCHOR_NAME_RE


class FsHost(models.Model):
    _name = 'fs.host'
    _description = 'Screen that supports Form Studio'
    _order = 'model, id'

    name = fields.Char(
        translate=True,
        help="What the screen is called in Studio. Empty: the record type's "
             "own name.")
    model = fields.Char(required=True, index=True)
    base_view_xmlid = fields.Char(
        required=True, help="The form the Studio layout extends.")
    kit = fields.Selection(
        [('vu', 'Standard form'), ('ws', 'Workspace form')],
        default='vu', required=True)
    sections = fields.Json(
        default=list,
        help="Open cards a field may be dropped into: "
             "[{name, title}]. Empty: Studio may only add new sections.")
    locked_fields = fields.Json(
        default=dict, help="{field name: why it cannot be changed}")
    locked_zones = fields.Json(
        default=list, help="[{name, title, reason}] areas shown dimmed.")
    pwa_label = fields.Char(
        translate=True,
        help="What the mobile app switch is called on this screen. "
             "Empty: \"Mobile app\".")
    pack_page = fields.Char(
        help="Workspace forms only: the tab whose card pack receives new "
             "sections.")
    pack_tail = fields.Char(
        help="Workspace forms only: a widget at the end of the pack that new "
             "sections are placed before. Empty: sections go last.")
    list_view_xmlid = fields.Char(
        help="The list this screen's records appear in. Empty: no list "
             "columns.")
    list_anchor = fields.Char(
        help="Name of the last visible column; new columns go after it.")
    list_name = fields.Char(
        translate=True,
        help="What the list is called in Studio (\"the Bookings list\"). "
             "Empty: the list's own title, else the screen's name.")
    money_ok = fields.Boolean(string='Can hold money', compute='_compute_money_ok')
    active = fields.Boolean(default=True)

    @api.constrains('list_view_xmlid', 'list_anchor')
    def _check_list_pair(self):
        """A list and the column new columns follow are declared together.
        Whether they still exist is a question about today's screens, asked
        by `_check_list` and the validator, not when the data loads."""
        for host in self:
            if bool(host.list_view_xmlid) != bool(host.list_anchor):
                raise ValidationError(_(
                    "A list needs the name of the column new columns go "
                    "after, and that column needs its list."))
            if host.list_anchor and not ANCHOR_NAME_RE.match(host.list_anchor):
                raise ValidationError(_(
                    "\"%s\" is not a name Studio can place against.",
                    host.list_anchor))

    @api.constrains('kit', 'pack_page', 'pack_tail')
    def _check_ws(self):
        """A Workspace screen has exactly two places for a field: inside one
        of its open cards, or in a new card at the end of one card pack. The
        pack is named here; a standard form has none."""
        for host in self:
            if host.kit == 'ws' and not host.pack_page:
                raise ValidationError(_(
                    "A Workspace screen needs the tab whose cards receive new "
                    "sections."))
            if host.kit != 'ws' and (host.pack_page or host.pack_tail):
                raise ValidationError(_(
                    "Only a Workspace screen has a card pack."))
            for name in (host.pack_page, host.pack_tail):
                if name and not ANCHOR_NAME_RE.match(name):
                    raise ValidationError(_(
                        "\"%s\" is not a name Studio can place against.", name))

    @api.depends('model')
    def _compute_money_ok(self):
        for host in self:
            model = self.env.get(host.model) if host.model else None
            host.money_ok = model is not None and 'currency_id' in model._fields

    # ------------------------------------------------------------------
    def _base_view(self):
        """The form this host extends, or an empty recordset."""
        self.ensure_one()
        view = self.env.ref(self.base_view_xmlid, raise_if_not_found=False)
        if not view or view._name != 'ir.ui.view':
            return self.env['ir.ui.view']
        return view.sudo()

    def _title(self):
        self.ensure_one()
        if self.name:
            return self.name
        return self.env['ir.model']._get(self.model).name or self.model

    def _list_view(self):
        """The list this host declared, or an empty recordset when it
        declared none or the declaration no longer resolves to a list."""
        self.ensure_one()
        View = self.env['ir.ui.view']
        if not self.list_view_xmlid:
            return View
        view = self.env.ref(self.list_view_xmlid, raise_if_not_found=False)
        if not view or view._name != 'ir.ui.view' or view.type != 'list' \
                or view.model != self.model:
            return View
        return view.sudo()

    def _list_title(self):
        """What the list is called: '' when this screen has no list."""
        self.ensure_one()
        view = self._list_view()
        if not view:
            return ''
        if self.list_name:
            return self.list_name
        try:
            root = etree.fromstring(view.get_combined_arch())
        except Exception:  # noqa: BLE001 — a title never breaks the editor
            root = None
        return (root is not None and root.get('string')) or self._title()

    # ------------------------------------------------------------------
    #  Does the screen still match what this host says about it?
    # ------------------------------------------------------------------
    def _section_problems(self):
        """Open cards that cannot take a field on today's form. A Workspace
        card takes fields into its `<group>`; a card with none (a card that
        holds one field directly, say) can be shown but never opened."""
        self.ensure_one()
        base = self._base_view()
        if not base:
            return [_("The form of the %s screen no longer exists.",
                      self._title())]
        try:
            arch = etree.fromstring(base.get_combined_arch())
        except Exception as exc:  # noqa: BLE001 — reported, not raised
            return [str(exc)]
        out = []
        for card in self.sections or []:
            name = isinstance(card, dict) and card.get('name')
            if not name:
                continue
            if self.kit == 'ws':
                nodes = arch.xpath("//div[@name='%s']" % name)
                if len(nodes) != 1:
                    out.append(_(
                        "The card \"%s\" is not on the screen any more.", name))
                elif not nodes[0].xpath('./group'):
                    out.append(_(
                        "The card \"%s\" cannot take fields: it has no field "
                        "group.", name))
            elif not arch.xpath("//group[@name='%s']" % name):
                out.append(_(
                    "The card \"%s\" is not on the screen any more.", name))
        return out

    def _list_problems(self):
        """Why the declared list cannot take columns today ([] when it can,
        or when no list is declared)."""
        self.ensure_one()
        if not self.list_view_xmlid:
            return []
        view = self.env.ref(self.list_view_xmlid, raise_if_not_found=False)
        if not view or view._name != 'ir.ui.view':
            return [_("The list %s no longer exists.", self.list_view_xmlid)]
        if view.type != 'list' or view.model != self.model:
            return [_("%s is not a list of this screen's records.",
                      self.list_view_xmlid)]
        try:
            arch = etree.fromstring(view.sudo().get_combined_arch())
        except Exception as exc:  # noqa: BLE001 — reported, not raised
            return [str(exc)]
        found = len(arch.xpath("//field[@name='%s']" % self.list_anchor))
        if found != 1:
            return [_("The column \"%(column)s\" is not in the list exactly "
                      "once (found %(count)s).",
                      column=self.list_anchor, count=found)]
        return []

    def _problems(self):
        self.ensure_one()
        return self._section_problems() + self._list_problems()

    def _check_sections(self):
        for host in self:
            problems = host._section_problems()
            if problems:
                raise UserError(problems[0])

    def _check_list(self):
        for host in self:
            problems = host._list_problems()
            if problems:
                raise UserError(problems[0])

    def _fs_text(self, text):
        """Hook: the words of a lock reason or zone title, in the reader's
        language. Core has no catalogue of the product's words; the product's
        overlay overrides this."""
        return text

    @api.model
    def _for(self, model, view_id):
        """The host whose form is `view_id`, or whose form `view_id` is a
        primary copy of (one level is enough: a screen that renders an
        inherited primary view of a host form is still that host)."""
        if not model or not view_id:
            return self.browse()
        hosts = self.sudo().search([('model', '=', model)])
        if not hosts:
            return self.browse()
        view = self.env['ir.ui.view'].sudo().browse(int(view_id)).exists()
        if not view:
            return self.browse()
        candidates = {view.id}
        if view.mode == 'primary' and view.inherit_id:
            candidates.add(view.inherit_id.id)
        for host in hosts:
            base = host._base_view()
            if base and base.id in candidates:
                return host
        return self.browse()
