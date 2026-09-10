# -*- coding: utf-8 -*-
"""Remove abandoned Zalo setup rows and invalidate stale inbound proof."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Connection = env['care.channel.connection'].sudo().with_context(
        active_test=False)

    # These are the rows the old Add another account flow left visible after
    # a duplicate OA was selected.  Archiving mirrors the new Remove action;
    # no credential, audit row or conversation is deleted.
    abandoned = Connection.search([
        ('channel', '=', 'zalo'),
        ('active', '=', True),
        ('state', '=', 'disabled'),
        ('resource_external_id', '=', False),
        ('last_inbound_at', '=', False),
        ('last_outbound_at', '=', False),
    ])
    if abandoned:
        abandoned._internal().write({'active': False})

    Check = env['care.channel.readiness.check'].sudo()
    Audit = env['care.channel.audit'].sudo()
    for connection in Connection.search([
            ('channel', '=', 'zalo'), ('active', '=', True)]):
        latest_login = Audit.search([
            ('connection_id', '=', connection.id),
            ('event', '=', 'callback_ok'),
        ], order='ts desc, id desc', limit=1)
        if not latest_login:
            continue
        # A message seen before the latest authorization does not prove the
        # path the operator is configuring now.  This is the exact stale green
        # state that required the live data correction on 10 September.
        if not connection.last_webhook_at or (
                latest_login.ts and latest_login.ts > connection.last_webhook_at):
            Check.upsert_check(
                connection, 'webhook_verified', 'pending',
                detail='Awaiting a signed event after the latest Zalo sign-in')
            Check.upsert_check(
                connection, 'inbound_ok', 'pending',
                detail='Awaiting a message after the latest Zalo sign-in')
