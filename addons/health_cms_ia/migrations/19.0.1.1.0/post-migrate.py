# -*- coding: utf-8 -*-
"""ACCESS AR-3 — the M2 follow-ups and the menu in Vietnamese, on upgrade.

The same `consolidate_ia` the install hook calls: every writer compares first,
and the gates are decided once per entry, so everything M2 did is a no-op here.
What is new runs inside it: `apply_followups` (G1 the Bookings tab for doctors,
G2 the Google Ads application for the platform administrator only) and
`apply_names_vi` (E2 — every area, tab and screen named in Vietnamese).
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.health_cms_ia.hooks import consolidate_ia

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    log = consolidate_ia(env)
    _logger.info('health_cms_ia %s: AR-3 follow-ups from %s — %s',
                 '19.0.1.1.0', version,
                 ', '.join('%s %s' % (len(v), k) for k, v in log.items()))
