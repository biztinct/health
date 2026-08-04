# -*- coding: utf-8 -*-
import logging

from lxml import etree

from odoo import models, _

from .catchment_scope import (
    FILTER_MINE,
    FILTER_PER_AREA,
    catchment_field_of,
)

_logger = logging.getLogger(__name__)


class IrUiView(models.Model):
    """Inject the catchment facet into every search view, per user.

    Why this hook and not `_get_view`: the arch produced by `_get_view` is
    served from `_get_view_cache`, which is shared. `_postprocess_access_rights`
    runs AFTER that cache, once per request, against `self.env.user` — which is
    what lets the facet name the user's own area and lets an owner see filters
    a nurse never receives.

    GOTCHA, paid for in core (base/models/ir_ui_view.py:1357): the super() call
    POPS `model_access_rights` off the tree. Read it first or you get None and
    silently do nothing.
    """
    _inherit = 'ir.ui.view'

    def _postprocess_access_rights(self, tree):
        model_name = tree.get('model_access_rights') if tree.tag == 'search' else None

        tree = super()._postprocess_access_rights(tree)

        if not model_name:
            return tree
        try:
            self._catchment_inject_filters(tree, model_name)
        except Exception:  # never break a view over a filter
            _logger.warning(
                'Could not inject the catchment filter into the %s search view',
                model_name, exc_info=True,
            )
        return tree

    # ------------------------------------------------------------------
    def _catchment_inject_filters(self, tree, model_name):
        model = self.env.get(model_name)
        if model is None:
            return
        field = catchment_field_of(model)
        if not field:
            return
        # Idempotent: an inherited search view that already carries our filter
        # (or a hand-written one of the same name) is left alone.
        if tree.xpath('//filter[@name="%s"]' % FILTER_MINE):
            return

        user = self.env.user
        can_switch = user._catchment_can_switch()
        own = user.catchment_province_id

        nodes = [etree.Element('separator')]

        # A SCOPED user gets no catchment filter at all.
        #
        # The first design gave them a default-on "My Catchment Area: X" facet.
        # It read well and was wrong twice: a facet is removable, and clearing
        # it widened the list on any model whose record rules are permissive
        # (crm.lead lets 296 rows through, because the Sales "All Documents"
        # rule ORs the catchment rule away) or else threw a raw AccessError
        # dialog. It also sat in searchModel.query, which suppressed the
        # Contacts view's own default "Today" filter — the same screen showed
        # different totals depending on whether an area was selected.
        #
        # The scope is now a domain the CMS sidebar ANDs into the action, which
        # cannot be removed and cannot collide with a view's own filters, and
        # the sidebar pill is the visible indication. So there is nothing to
        # inject here for a scoped user except the removal below.
        if can_switch and own:
            nodes.append(self._catchment_filter(
                FILTER_MINE,
                _('My Catchment Area: %s', own.name),
                "[('%s', '=', %d)]" % (field, own.id),
            ))

        if can_switch:
            # Consecutive filters with no separator between them OR together,
            # so an owner can tick two areas and see both. Their own area is
            # already above as `catchment_mine`; listing it twice would be
            # noise.
            others = self.env['health.catchment.province'].sudo().search(
                [('id', '!=', own.id)] if own else [])
            for province in others:
                nodes.append(self._catchment_filter(
                    FILTER_PER_AREA % province.id,
                    province.name,
                    "[('%s', '=', %d)]" % (field, province.id),
                ))
        if len(nodes) > 1:  # more than the bare separator
            tree.extend(nodes)

        if not can_switch:
            # Some search views ship their own <field name="catchment_province_id"/>
            # (health_patient_views, crm_lead_views and others). Left in place it
            # autocompletes over every area for a scoped user — the exact leak
            # this module exists to close. Stripping it here is structural: it
            # also covers views nobody has audited, and views added later.
            for node in tree.xpath('//field[@name="%s"]' % field):
                node.getparent().remove(node)
        elif not tree.xpath('//field[@name="%s"]' % field):
            # The searchable field is owner-only on purpose. Giving it to a
            # scoped user would put every other area's name into their
            # autocomplete, which is the thing this whole module is meant to
            # prevent.
            #
            # It goes FIRST, not last: the search RNG wants every <field>
            # ahead of the filters ("Element search has extra content: field"),
            # and while runtime-injected arch is not RNG-validated, matching
            # the schema keeps the client's own parsing on the happy path.
            node = etree.Element('field')
            node.set('name', field)
            node.set('string', _('Catchment Area'))
            tree.insert(0, node)

    @staticmethod
    def _catchment_filter(name, string, domain):
        node = etree.Element('filter')
        node.set('name', name)
        node.set('string', string)
        node.set('domain', domain)
        return node
