import logging

from odoo import api, fields, models

from odoo.addons.health_catchment_scope.models.catchment_scope import (
    catchment_field_of,
)

_logger = logging.getLogger(__name__)


class CmsSidebarItem(models.Model):
    _name = 'cms.sidebar.item'
    _description = 'CMS Sidebar Menu Item'
    _order = 'section_id, sequence, id'

    name = fields.Char(required=True, translate=True)
    section_id = fields.Many2one(
        'cms.sidebar.section', required=True, ondelete='cascade', string='Section',
    )
    parent_id = fields.Many2one(
        'cms.sidebar.item', string='Parent Item', ondelete='cascade',
        help='When set, this item is a sub-menu shown under its parent.',
    )
    sequence = fields.Integer(default=10)
    icon = fields.Char(string='Icon Class', default='fa fa-circle-o')
    action_xmlid = fields.Char(
        string='Action XML ID',
        help='XML ID of the action to execute on click, e.g. health_crm.action_crm_dashboard',
    )
    action_tag = fields.Char(
        string='Client Action Tag',
        help='Tag for OWL client actions, e.g. crm_dashboard',
    )
    role_ids = fields.Many2many('access.role', string='Allowed Roles')
    active = fields.Boolean(default=True)
    match_action_tags = fields.Char(
        string='Match Action Tags',
        help='Comma-separated client action tags that highlight this item',
    )
    match_action_xmlids = fields.Char(
        string='Match Action XML IDs',
        help='Comma-separated action XML IDs that highlight this item',
    )
    match_models = fields.Char(
        string='Match Models',
        help='Comma-separated model names that highlight this item',
    )

    @api.model
    def get_match_keys(self):
        """Union of every active item's action tags / action xml-ids / models
        (own + match_* hints). The frontend feeds these into the custom-sidebar
        registry so navigating to ANY wired screen keeps the CMS shell — no
        hardcoded allowlist edit needed when a new item is added."""
        def _split(val):
            return [v.strip() for v in (val or '').split(',') if v.strip()]

        tags, xmlids, models = set(), set(), set()
        for item in self.search([('active', '=', True)]):
            if item.action_tag:
                tags.add(item.action_tag)
            if item.action_xmlid:
                xmlids.add(item.action_xmlid)
            tags.update(_split(item.match_action_tags))
            xmlids.update(_split(item.match_action_xmlids))
            models.update(_split(item.match_models))
        return {
            'tags': sorted(tags),
            'xmlids': sorted(xmlids),
            'models': sorted(models),
        }

    @api.model
    def get_catchment_scope(self):
        """What the sidebar's scope pill draws.

        Kept as its own call rather than folded into get_sidebar_data's return
        value, which is a bare list every consumer already unpacks as one.
        """
        return self.env['res.users']._catchment_scope_info()

    def _catchment_scoped_action(self, action_xmlid):
        """The name of the catchment field on this leaf's model, or False.

        Returns the FIELD NAME rather than a boolean because the sidebar builds
        a real domain out of it, and the field is not always called the same
        thing — hr.employee stores its area as staff_catchment_province_id.

        Resolved server-side because the browser has no way to know: it needs
        the action's res_model and then that model's field list. Cached for the
        life of the call — the sidebar resolves ~95 leaves per load and many of
        them point at the same action.
        """
        if not action_xmlid:
            return False
        cache = self.env.context.get('__catchment_action_cache')
        if cache is None:
            cache = {}
        if action_xmlid in cache:
            return cache[action_xmlid]

        result = False
        try:
            # sudo() is required, not convenience: reading ir.actions.act_window
            # is gated to "Role / Administrator" on this deployment, so a nurse
            # resolving their own menu would raise AccessError and every leaf
            # would silently come back unscoped — which is exactly how this was
            # first shipped, and how it was caught. What is read here is pure
            # metadata (which model does this menu open), never a record.
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            res_model = action and getattr(action.sudo(), 'res_model', False)
            if res_model and res_model in self.env:
                result = catchment_field_of(self.env[res_model]) or False
        except Exception:
            _logger.debug('Could not resolve %s for catchment scoping',
                          action_xmlid, exc_info=True)
        cache[action_xmlid] = result
        return result

    @api.model
    def get_sidebar_data(self):
        # One shared dict for the whole call, so the ~95 leaves resolve each
        # distinct action exactly once.
        self = self.with_context(__catchment_action_cache={})
        user = self.env.user
        user_role = user.access_role_id
        # Users with the "Access Role: Administrator" privilege always see the full
        # sidebar, without needing a business access.role assigned. (That privilege
        # is separate from the access.role the items are gated by, and includes the
        # superuser + base admin via the group's user_ids.) Note: base.group_system
        # is intentionally NOT used here — many staff users carry it in this DB, so
        # it would defeat per-role filtering.
        is_admin = user.has_group('access_roles.access_role_group_administrator')

        sections = self.env['cms.sidebar.section'].search(
            [('active', '=', True)], order='sequence, id',
        )
        all_items = self.search(
            [('active', '=', True)], order='section_id, sequence, id',
        )

        if is_admin:
            visible_items = all_items
        elif user_role:
            visible_items = all_items.filtered(
                lambda i: not i.role_ids or user_role in i.role_ids
            )
        else:
            visible_items = all_items.filtered(lambda i: not i.role_ids)

        def _split(val):
            return [v.strip() for v in (val or '').split(',') if v.strip()]

        def _item_dict(item):
            return {
                'id': item.id,
                'name': item.name,
                'icon': item.icon,
                'action_xmlid': item.action_xmlid,
                'action_tag': item.action_tag,
                'match_action_tags': _split(item.match_action_tags),
                'match_action_xmlids': _split(item.match_action_xmlids),
                'match_models': _split(item.match_models),
                # The catchment field to scope this leaf by, or False for the
                # reference-data leaves and the OWL dashboards. The sidebar ANDs
                # a domain built from it into the action.
                'catchment_field': self._catchment_scoped_action(item.action_xmlid),
                'children': [],
            }

        result = []
        for section in sections:
            sec_items = visible_items.filtered(lambda i, s=section: i.section_id == s)
            tops = sec_items.filtered(lambda i: not i.parent_id).sorted(lambda i: (i.sequence, i.id))
            items = []
            for top in tops:
                d = _item_dict(top)
                kids = sec_items.filtered(lambda c, p=top: c.parent_id == p).sorted(
                    lambda c: (c.sequence, c.id))
                d['children'] = [_item_dict(k) for k in kids]
                items.append(d)
            if not items:
                continue
            result.append({
                'id': section.id,
                'name': section.name,
                'key': section.technical_key,
                'icon': section.icon or False,
                'color': section.color or False,
                'items': items,
            })
        return result
