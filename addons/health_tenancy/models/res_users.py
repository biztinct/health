# -*- coding: utf-8 -*-
"""The seat limit, on the one record this product sells by.

WHY THE OVERRIDE IS HERE AND NOT IN THE GENERIC MODULE. The platform link
supplies the DECISION — `biz.tenancy.seat_gate()` reads the pushed limit, takes
a fresh count and returns either an empty string or the sentence somebody
should read. What it cannot know is WHICH record this product is sold by: a
payroll counts employees, a shop counts tills, and this product counts people
with a login. So the product names the record by overriding its own `create`,
which is one line of glue and is exactly where somebody looking for "why was I
refused" would go.

⚠ IT REFUSES WITH A SENTENCE, NEVER WITH A NUMBER. "Limit reached" is a wall.
The refusal names the limit, the count, the plan and who to ask — because the
person meeting it is trying to add a colleague on a Monday morning and needs to
know what to do, not what went wrong.

AND IT NEVER APPLIES TO THE WAY BACK IN. The recovery account and an active
support session are exempt inside `seat_gate` — somebody from the platform
going in to fix the very problem must not be stopped by it — and a system that
has never been told a limit has none at all (an ABSENT setting and a limit of
nought are both "no limit", and the platform link keeps them apart for the
person debugging it).
"""
import logging

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """One question, asked once, for however many are being added.

        THE COUNT IS OF PEOPLE WITH A LOGIN, so a portal account is not one:
        `seat_gate` counts the same rows the platform's own "staff with a
        login" meter counts, which is what stops the number on the platform's
        screen and the number this door enforces from ever disagreeing.
        """
        wanted = [v for v in vals_list
                  if not (v or {}).get('share')]
        if wanted:
            try:
                refusal = self.env['biz.tenancy'].sudo().seat_gate(len(wanted))
            except Exception:                                # noqa: BLE001
                # ⚠ FAIL OPEN, AND SAY WHY (the same rule as the paused door).
                # A broken settings row must never stop somebody adding a
                # colleague, and a guard that fails quietly is a guard nobody
                # knows has stopped working.
                _logger.warning(
                    "health_tenancy: the limit on people with a login could "
                    "not be read; the account was allowed. If these lines are "
                    "here, a limit that has been set is not being enforced.",
                    exc_info=True)
                refusal = ''
            if refusal:
                _logger.info("health_tenancy: refused %d new account(s) — the "
                             "plan's limit is reached", len(wanted))
                raise UserError(refusal)
        return super().create(vals_list)
