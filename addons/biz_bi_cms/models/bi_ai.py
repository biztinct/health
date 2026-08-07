# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import AccessError


class BiAi(models.AbstractModel):
    """Make the AI availability probe answer "no" instead of raising.

    Found by DRIVING the phase's own CTA (browser evidence 07): a user holding
    only ``biz_bi.group_bi_creator`` who opens Explore is met by a modal
    reading *"You are not allowed to access 'BI AI Provider' (bi.ai.provider)
    records."* — because ``bi.ai.is_available()`` searches ``bi.ai.provider``,
    whose ACL starts at ``group_bi_modeler``, and
    ``explore_action.js`` fires that RPC in ``onWillStart`` without a
    ``.catch``, so the rejection reaches the global error handler.

    The defect is pre-existing in biz_bi and had never fired, because before
    this module only two accounts on this deployment held ANY BI group and
    both were BI administrators. Granting ten business users
    ``group_bi_creator`` is what makes it reachable, so it belongs to this
    phase to neutralise.

    "Is a feature available to me?" is a question that has an answer for every
    user — the answer for someone who cannot even read the provider table is
    simply **no**. Only ``AccessError`` is caught (§5.47): a misconfigured
    provider, a broken key, any other failure still propagates.

    This is additive and read-only: no ACL is widened, no group is granted,
    and modelers/administrators keep the exact behaviour they had.
    """
    _inherit = 'bi.ai'

    @api.model
    def is_available(self):
        try:
            return super().is_available()
        except AccessError:
            return False
