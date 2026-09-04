# -*- coding: utf-8 -*-
"""The platform's message rides in with the page, not after it.

WHY NOT JUST ASK THE SERVER FROM THE BROWSER. Because then the top of every
page would be empty for the length of a round trip and the bar would drop in a
beat late — on every navigation, for every person, for ever. A warning that
arrives after somebody has started typing is a worse warning than none. So the
state travels in `session_info`, which the page already carries, and the bar is
drawn on the first paint with no request of its own.

The 60-second poll (`/biz_tenancy/state`) exists for the OTHER case: a tab that
has been open for an hour when the platform sends something.
"""
import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        # Nothing for a visitor who is not signed in: there is no page with our
        # chrome on it to put a bar at the top of.
        if not (request and request.session.uid):
            return info
        try:
            info['biz_tenancy'] = self.env['biz.tenancy'].state()
        except Exception:                                    # noqa: BLE001
            # A damaged settings row must never stop somebody signing in. The
            # browser reads a missing key as "no message, no release".
            _logger.warning("biz_tenancy: could not read the platform state "
                            "for this session", exc_info=True)
        return info
