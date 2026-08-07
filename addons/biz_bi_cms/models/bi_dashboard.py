# -*- coding: utf-8 -*-
from odoo import api, models


class BiDashboard(models.Model):
    """Which dashboards may this user actually add a report to?

    Until AH-3 the wizard's step-3 target list came from a plain
    ``searchRead("bi.dashboard", [], ["name"])`` — a READ-scoped query — so a
    creator was offered every dashboard they can *see*, discovered only at Save
    time (through a caught ``AccessError``) that most of them are not theirs to
    write, and had to guess again.

    The predicate below is not a second opinion: it is the one
    ``bi_dashboard.get_dashboard_data()`` already publishes as ``can_edit``
    (``biz_bi/models/bi_dashboard.py:213-216``) —
    ``(owner_id == user AND creator) OR modeler`` — expressed as a domain so
    the same answer can be reached in one query instead of per record. The
    record rules still run underneath it: this narrows what a user is OFFERED,
    it never widens what they may do, and the save path keeps its AccessError
    fallback for the race where a dashboard changes hands mid-wizard.
    """
    _inherit = 'bi.dashboard'

    @api.model
    def get_wizard_targets(self):
        """[{id, name}] of dashboards this user may add a chart to."""
        user = self.env.user
        if user.has_group('biz_bi.group_bi_modeler'):
            # The modeler rule is [(1, '=', 1)] for every mode.
            domain = []
        elif user.has_group('biz_bi.group_bi_creator'):
            # The creator rule grants write/create/unlink on own rows only.
            domain = [('owner_id', '=', user.id)]
        else:
            # A viewer may add a report to nothing at all — the wizard then
            # preselects "New dashboard", which they also cannot create, and
            # the save path says so honestly.
            return []
        return self.search_read(domain, ['name'], order='name')
