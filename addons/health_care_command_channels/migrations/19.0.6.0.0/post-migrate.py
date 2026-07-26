# -*- coding: utf-8 -*-
"""CC-F migration: give every live voip.config a framework connection.

Same placement argument as the CC-D script next door, with one difference
worth stating because it is the fragile part. health_zalo is *guaranteed* to
load first (health_care_command depends on it, and this module depends on
that). health_voip24h has **no dependency edge to this module in either
direction** — deliberately, because adding one risks the unbuildable loop
§5.71 documents. What keeps the ordering right is depth: health_voip24h sits
on base/crm/hr/health_base/health_crm, several levels below this module, and
Odoo's module graph loads by depth. So by the time this runs, ``voip.config``
is in the registry.

That is a reasoned expectation rather than a guarantee, so the guard below
logs a DISTINCT line when it is not met — an absent-voip run and a
zero-config run must not look identical in the log, or a silent no-op would
read as success.

Everything it does is idempotent (T152), nothing is deleted, and an existing
VoIP setup keeps working exactly as it did — in ``state='legacy'``, which
observes traffic without gating it — until a human completes the new setup in
the Channel Center.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'voip.config' not in env:
        _logger.info('CC-F post-migrate: health_voip24h is NOT in the '
                     'registry — no calls migration ran')
        return
    result = env['voip.config']._migrate_legacy_connections()
    _logger.info('CC-F post-migrate: calls facade %s', result)
