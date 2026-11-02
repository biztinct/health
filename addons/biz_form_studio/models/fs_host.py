# -*- coding: utf-8 -*-
"""A screen that supports Form Studio.

A host is DATA, supplied by the product that owns the screen. This module
ships none: it cannot know which forms are safe to extend, which of their
cards may receive a field, or which fields are load-bearing for the product's
own logic. Those are the product's facts, so they arrive here as records.
"""
from odoo import api, fields, models


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
    money_ok = fields.Boolean(string='Can hold money', compute='_compute_money_ok')
    active = fields.Boolean(default=True)

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
