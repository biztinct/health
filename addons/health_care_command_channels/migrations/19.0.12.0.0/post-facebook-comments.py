# -*- coding: utf-8 -*-
"""Expose comment readiness on Facebook connections that predate this phase."""
from odoo import api, SUPERUSER_ID


COMMENT_SCOPES = {
    'pages_read_engagement',
    'pages_read_user_content',
    'pages_manage_engagement',
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Check = env['care.channel.readiness.check'].sudo()
    connections = env['care.channel.connection'].sudo().with_context(
        active_test=False).search([('channel', '=', 'fb')])
    for connection in connections:
        scopes = set((connection.granted_scopes or '').split())
        missing = sorted(COMMENT_SCOPES - scopes)
        detail = (
            'Reconnect Facebook and grant: %s' % ', '.join(missing)
            if missing
            else 'permissions granted; reconnect the webhook to enable feed')
        Check.upsert_check(
            connection, 'comments_enabled',
            'fail' if missing else 'pending', detail=detail)
