# -*- coding: utf-8 -*-
"""Shared fixtures for the CC-A suites (T70–T89).

TransactionCase ONLY — this module ships no HttpCase on purpose: an HttpCase
runs on a separate cursor, and its side effects have poisoned later
TransactionCase suites in the same run before (ledger §5.32). The OAuth
callback is therefore tested through the model method the controller wraps.

Fixture patterns follow health_care_command/tests/test_care_command.py:50-126.
"""
from odoo.tests import TransactionCase

from odoo.addons.health_care_command_channels.models.care_channel_connection import (
    INTERNAL_CTX,
)


class ChannelHubCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Conn = env['care.channel.connection']
        cls.Session = env['care.channel.oauth.session']
        cls.Check = env['care.channel.readiness.check']
        cls.Audit = env['care.channel.audit']
        cls.App = env['channel.platform.app']

        cls.company = env.company
        cls.company2 = env['res.company'].create({'name': 'CHUB Other Co'})
        cls.province = env['health.catchment.province'].search([], limit=1) or \
            env['health.catchment.province'].create({'name': 'CHUB Prov'})

        cls.crm_user = cls._mk_user('chub_user', ['health_crm.group_health_crm_user'])
        cls.crm_mgr = cls._mk_user('chub_mgr', ['health_crm.group_health_crm_manager'])

        # The default test user is the superuser, which is a member of NO group
        # (has_group checks real membership, not su — ledger §5.42) — grant the
        # manager group so the group-gated service methods pass their own gate.
        env.user.sudo().write({
            'group_ids': [(4, env.ref('health_crm.group_health_crm_manager').id),
                          (4, env.ref('base.group_system').id)]})

    @classmethod
    def _mk_user(cls, login, group_xmlids, company=None):
        env = cls.env
        company = company or cls.company
        gids = [env.ref('base.group_user').id]
        for xmlid in group_xmlids:
            gids.append(env.ref(xmlid).id)
        return env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(6, 0, gids)],
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'catchment_province_id': cls.province.id,
        })

    # -- helpers -------------------------------------------------------
    def _conn(self, channel='telegram', company=None, state=None, **extra):
        """Create a connection. `state` (and any other guarded field) is set
        through the internal context — the same door the server paths use.

        The record is re-browsed WITHOUT that context before it is returned:
        an Odoo context propagates through every derived recordset, so a
        fixture that kept it would silently disarm the write guard it is
        supposed to be testing.
        """
        vals = {'channel': channel,
                'company_id': (company or self.company).id}
        vals.update(extra)
        if state:
            vals['state'] = state
        record = self.Conn.with_context(**{INTERNAL_CTX: True}).create(vals)
        return self.Conn.browse(record.id)

    def _seed_checks(self, conn, status='pass', keys=None):
        for key in (keys if keys is not None else conn._required_checks()):
            self.Check.upsert_check(conn, key, status)
        return conn
