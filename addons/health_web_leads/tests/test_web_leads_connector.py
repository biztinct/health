# -*- coding: utf-8 -*-
"""W2.5-T1 … T12 — the self-service Website Connector.

TransactionCase for everything except T8, which needs a real `/oauth/token`
round trip and therefore an `HttpCase` (conventions §2 / ledger §5.75, §5.83:
these only run with BOTH `--workers=0` and no `--no-http`; with either wrong
the class dies in `setUpClass` and the run exits 1 with a FAIL count of zero).

Two standing hazards this file works around:

* **live data.** vietuat already carries the hand-made `svc_web_leads` account
  (id 6103) and the "WordPress pkgdvietuc" OAuth client (id 122), so the
  "creates" and the "adopts" arms are the SAME code path there. Every
  assertion is therefore written against the CONTRACT (one user, one client,
  both scopes, nothing duplicated) rather than against a record count that
  only holds on a fresh database (§5.50).
* **`ir.config_parameter` is not transactional in the ORMCACHE** (§5.32/§5.48).
  Every parameter this suite touches is restored in `setUp`'s cleanup so no
  later suite in the same run inherits an armed heartbeat or a rewritten city
  map.
"""
import json
import os
import re
import uuid
from datetime import timedelta

import psycopg2

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.health_web_leads.models.web_lead_service import (
    CITY_HCM, CITY_HN, HEARTBEAT_SUMMARY, PARAM_FORM_CITY_MAP,
    PARAM_HEARTBEAT_ENABLED, PARAM_HEARTBEAT_USER, PARAM_URL_CITY_MAP)
from odoo.addons.health_web_leads.models.web_leads_connector import (
    READ_SCOPE_CODE, READ_SCOPE_REF, SECRET_PLACEHOLDER, SERVICE_GROUP,
    SERVICE_LOGIN, WRITE_SCOPE_CODE, WRITE_SCOPE_REF)

MODULE = 'health_web_leads'
BOTH_SCOPES = {WRITE_SCOPE_CODE, READ_SCOPE_CODE}
TOUCHED_PARAMS = (PARAM_FORM_CITY_MAP, PARAM_URL_CITY_MAP,
                  PARAM_HEARTBEAT_ENABLED, PARAM_HEARTBEAT_USER)


class ConnectorCaseMixin:
    """Fixtures shared by the TransactionCase and the HttpCase halves."""

    @classmethod
    def _setup_connector_fixtures(cls):
        cls.Connector = cls.env['web.leads.connector']
        cls.Service = cls.env['web.lead.service']
        cls.Touchpoint = cls.env['health.lead.touchpoint']
        cls.Client = cls.env['gateway.oauth.client']
        cls.Param = cls.env['ir.config_parameter'].sudo()
        cls.hn = cls.Service._resolve_catchment(CITY_HN) \
            or cls.env['health.catchment.province'].create(
                {'name': 'Test Hanoi W2.5', 'code': 'HN'})

    def _connector(self):
        """The singleton, get-or-create: a live database may already hold one
        (browser QA creates it), and the partial unique index forbids a
        second for the same company."""
        record = self.Connector.search(
            [('company_id', '=', self.env.company.id)], limit=1)
        return record or self.Connector.create({})

    def _restore_params(self, originals):
        """§5.32 — the parameter ORMCACHE is not rolled back with the
        transaction, so put every value back explicitly."""
        for key, value in originals.items():
            self.Param.set_param(key, value if value else
                                 ('False' if key == PARAM_HEARTBEAT_ENABLED
                                  else '0'))


@tagged('post_install', '-at_install')
class TestWebLeadsConnector(ConnectorCaseMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_connector_fixtures()

    def setUp(self):
        super().setUp()
        originals = {key: self.Param.get_param(key)
                     for key in TOUCHED_PARAMS}
        self.addCleanup(self._restore_params, originals)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _service_user(self):
        return self.env['res.users'].sudo().with_context(
            active_test=False).search([('login', '=', SERVICE_LOGIN)])

    def _residue_counts(self):
        """Everything `process_submission` can create. R2 asserts this is
        IDENTICAL before and after a pipeline test."""
        self.env.invalidate_all()
        counts = {
            'leads': self.env['crm.lead'].sudo().with_context(
                active_test=False).search_count([]),
            'touchpoints': self.Touchpoint.sudo().with_context(
                active_test=False).search_count([]),
            'messages': self.env['mail.message'].sudo().search_count(
                [('model', '=', 'crm.lead')]),
        }
        if 'care.conversation' in self.env:
            counts['conversations'] = self.env['care.conversation'].sudo(
            ).with_context(active_test=False).search_count([])
        return counts

    def _heartbeat_activities(self):
        # Ledger §5.89 — model-less activities; the summary constant is the
        # only thing that identifies them.
        return self.env['mail.activity'].sudo().search(
            [('res_model', '=', False), ('summary', '=', HEARTBEAT_SUMMARY)])

    def _mute_wordpress_touchpoints(self):
        """Take every live WordPress row out of the health strip's sight.

        Raw SQL, because `received_at`/`source_system` are ORM-managed and a
        live database has rows this suite did not create (ledger §5.9: flush
        before, invalidate after). A TransactionCase never commits, so the
        real rows are restored on rollback.
        """
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_lead_touchpoint SET source_system = 'manual' "
            "WHERE source_system = 'wordpress'")
        self.env.invalidate_all()

    def _wordpress_touchpoint(self, received_at=None):
        lead = self.env['crm.lead'].create({
            'name': 'W2.5 health fixture', 'type': 'opportunity',
            'contact_status': 'lead', 'contact_name': 'W2.5 Health Fixture',
            'catchment_province_id': self.hn.id})
        return self.Touchpoint.create({
            'lead_id': lead.id,
            'occurred_at': received_at or fields.Datetime.now(),
            'received_at': received_at or fields.Datetime.now(),
            'touchpoint_type_id': self.env['health.lookup.value']._default_for('touchpoint_type', 'form_submit'),
            'source_system': 'wordpress',
            'external_event_id': 'w25-%s' % uuid.uuid4().hex[:16]})

    # ==================================================================
    # T1 — provisioning is idempotent; the second call is a pure rotate
    # ==================================================================
    def test_w25_01_provision_then_rotate(self):
        connector = self._connector()
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        Clients = self.Client.sudo().with_context(active_test=False)

        action = connector.action_provision_credentials()
        self.assertEqual(action.get('tag'), 'display_notification',
                         'provisioning must return the show-once notification')
        self.assertTrue(action['params']['sticky'],
                        'a secret shown in a self-dismissing toast is a '
                        'secret nobody copies')
        # NB the message CONTAINS the plaintext — assert on the framing text,
        # never on secret material (rail R1).
        self.assertIn('not be shown again', action['params']['message'])
        # …and the follow-up that re-reads the record, so the header stops
        # offering "Get credentials" the moment credentials exist. Found by
        # driving Disconnect and watching the buttons not move.
        self.assertEqual(action['params'].get('next', {}).get('res_id'),
                         connector.id,
                         'the notification carries no `next`, so the '
                         'statusbar keeps showing the previous state')

        user = self._service_user()
        self.assertEqual(len(user), 1,
                         'provisioning must leave exactly one %s account'
                         % SERVICE_LOGIN)
        self.assertTrue(user.active)
        self.assertIn(self.env.ref(SERVICE_GROUP), user.group_ids)
        self.assertIn(self.env.ref('base.group_user'), user.group_ids)

        client = connector.oauth_client_id
        self.assertTrue(client, 'no OAuth client was linked')
        self.assertEqual(client.sudo().user_id, user)
        self.assertTrue(
            BOTH_SCOPES <= set(client.sudo().allowed_scope_ids.mapped('code')),
            'the client must carry web_lead.write AND web_lead.read')
        first_hash = client.sudo().client_secret_hash
        self.assertTrue(first_hash)

        users_before = Users.search_count([('login', '=', SERVICE_LOGIN)])
        clients_before = Clients.search_count([('user_id', '=', user.id)])

        # …and again: same client, nothing new, a fresh secret.
        second = connector.action_provision_credentials()
        self.assertEqual(second.get('tag'), 'display_notification')
        self.assertEqual(connector.oauth_client_id, client,
                         'the second call re-pointed the connector')
        self.assertEqual(Users.search_count([('login', '=', SERVICE_LOGIN)]),
                         users_before, 'a second service user was created')
        self.assertEqual(Clients.search_count([('user_id', '=', user.id)]),
                         clients_before, 'a second OAuth client was created')
        self.assertNotEqual(client.sudo().client_secret_hash, first_hash,
                            'the button did not actually rotate the secret')

    # ==================================================================
    # T2 — an existing account + client are ADOPTED, never duplicated
    # ==================================================================
    def test_w25_02_provision_adopts_the_live_credentials(self):
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        Clients = self.Client.sudo().with_context(active_test=False)
        group = self.env.ref(SERVICE_GROUP)

        # Mirror vietuat fact #4: the account exists, hand-made, no xmlid.
        user = self._service_user()[:1]
        if not user:
            user = Users.create({
                'name': 'Pre-existing relay account',
                'login': SERVICE_LOGIN,
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                      group.id])]})

        # The adopt branch is about a connector that has NO client yet, and a
        # live database already has one linked (browser QA creates the
        # singleton). Stage the precondition explicitly rather than assume it
        # — the first run of this test on vietuat passed for the wrong reason
        # and then failed for the right one.
        connector = self._connector()
        connector.oauth_client_id = False

        scopes = self.env.ref(WRITE_SCOPE_REF) | self.env.ref(READ_SCOPE_REF)
        fitting = Clients.search(
            [('user_id', '=', user.id)], order='id asc'
        ).filtered(lambda c: c.active and BOTH_SCOPES <= set(
            c.allowed_scope_ids.mapped('code')))
        if not fitting:
            fitting = self.Client.sudo().create({
                'name': 'W2.5 pre-existing client',
                'user_id': user.id,
                'allowed_scope_ids': [(6, 0, scopes.ids)],
                'token_lifetime': 3600})
        expected = fitting[0]

        users_before = Users.search_count([])
        clients_before = Clients.search_count([])

        connector.action_provision_credentials()

        self.assertEqual(
            connector.oauth_client_id, expected,
            'provisioning created a NEW client instead of adopting the '
            'existing one — on vietuat that orphans client 122')
        self.assertEqual(Users.search_count([]), users_before,
                         'provisioning created a user it should have adopted')
        self.assertEqual(Clients.search_count([]), clients_before,
                         'provisioning created a client it should have '
                         'adopted')

    # ==================================================================
    # T3 — the config block carries no secret material
    # ==================================================================
    def test_w25_03_wp_config_block(self):
        connector = self._connector()
        connector.action_provision_credentials()
        connector.invalidate_recordset()

        block = connector.wp_config_block
        self.assertIn(connector.oauth_client_id.sudo().client_id, block)
        self.assertIn('/oauth/token', block)
        self.assertIn('/api/v1/web/leads', block)
        self.assertIn('/api/v1/web/leads/reconcile', block)
        self.assertIn(SECRET_PLACEHOLDER, block)

        # THE assertion: rotating the secret must not move a single byte of
        # this text. If it ever does, the block is carrying secret material.
        connector.action_provision_credentials()
        connector.invalidate_recordset()
        self.assertEqual(connector.wp_config_block, block,
                         'the config block changed when the secret rotated')

    # ==================================================================
    # T4 — the city maps: write-through, validation, seeds untouched
    # ==================================================================
    def test_w25_04_city_maps(self):
        connector = self._connector()

        connector.write({'form_city_map_text': '{"91234": "HCM"}'})
        self.assertEqual(
            json.loads(self.Param.get_param(PARAM_FORM_CITY_MAP)),
            {'91234': 'HCM'})
        self.assertEqual(self.Service._derive_city({'form_id': '91234'}),
                         (CITY_HCM, 'form_id'))

        connector.write({'url_city_map_text': '{"/w25-hanoi/": "HN"}'})
        self.assertEqual(
            self.Service._derive_city(
                {'form_id': 'no-such-form',
                 'page_url': 'https://pkgdvietuc.com/w25-hanoi/?utm=x'}),
            (CITY_HN, 'page_url'))

        # A value the resolver does not understand is a SILENT dead entry, so
        # the form refuses it and names the offender.
        with self.assertRaises(ValidationError) as caught:
            connector.write({'form_city_map_text': '{"15838": "SGN"}'})
        self.assertIn('SGN', str(caught.exception))

        for bad in ('not json at all', '["HN"]', '{"15838": 42}',
                    '{"": "HN"}'):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    connector.write({'form_city_map_text': bad})

        # …and a refusal changed nothing.
        self.assertEqual(
            json.loads(self.Param.get_param(PARAM_FORM_CITY_MAP)),
            {'91234': 'HCM'})

        # R4 — the connector edits the LIVE parameters; the install seeds stay
        # the noupdate defaults and are not rewritten by this phase.
        for name in ('param_form_city_map', 'param_url_city_map'):
            with self.subTest(seed=name):
                data = self.env['ir.model.data'].sudo().search(
                    [('module', '=', MODULE), ('name', '=', name)], limit=1)
                self.assertTrue(data, '%s seed is missing' % name)
                self.assertTrue(data.noupdate,
                                '%s must stay noupdate=1 or an upgrade '
                                'overwrites the ops edit' % name)
                self.assertEqual(data.model, 'ir.config_parameter')

    # ==================================================================
    # T5 — the pipeline test leaves ZERO residue (rail R2)
    # ==================================================================
    def test_w25_05_test_pipeline_is_residue_free(self):
        connector = self._connector()
        self.Param.set_param(PARAM_FORM_CITY_MAP, '{"15838": "HN"}')
        self.Param.set_param(PARAM_URL_CITY_MAP, '{}')

        before = self._residue_counts()
        action = connector.action_test_pipeline()

        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(action['params']['type'], 'success',
                         action['params']['message'])
        message = action['params']['message']
        self.assertIn('15838', message)
        self.assertIn(self.hn.name, message,
                      'the notification must name the city the maps derived')
        self.assertIn('Nothing was saved', message)
        self.assertIn('cannot check HTTP authentication', message,
                      'the notification must not imply the auth half was '
                      'tested — the CRM never knows the client secret')
        self.assertEqual(self._residue_counts(), before,
                         'the pipeline test left records behind')

        # An empty map is a legitimate (if useless) configuration: it must
        # report, not crash.
        self.Param.set_param(PARAM_FORM_CITY_MAP, '{}')
        action = connector.action_test_pipeline()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertIn('NO city', action['params']['message'])
        self.assertEqual(self._residue_counts(), before)

    def test_w25_05b_test_pipeline_runs_for_a_real_operator(self):
        """Found by DRIVING the screen, not by a test (§5.4 in the flesh).

        Every test above runs as uid 1, which is `su` — so the button passed
        while the persona the screen exists for got
        `You are not allowed to create 'Lead Touchpoint'`: a CRM manager has
        `perm_create = 0` on `health.lead.touchpoint`. The submission now runs
        as the connector's service user (the rights the relay actually has),
        and this test is the one that would have caught it.
        """
        connector = self._connector()
        connector.action_provision_credentials()
        self.Param.set_param(PARAM_FORM_CITY_MAP, '{"15838": "HN"}')

        operator = new_test_user(
            self.env, login='wl_w25_operator',
            password='wl_w25_operator_pw',
            groups='base.group_user,health_crm.group_health_crm_manager')
        self.assertFalse(
            self.env['health.lead.touchpoint'].with_user(
                operator).has_access('create'),
            'the fixture no longer stages the bug — a CRM manager may now '
            'create touchpoints, so running the test as the operator would '
            'pass for the wrong reason')

        before = self._residue_counts()
        action = connector.with_user(operator).action_test_pipeline()
        self.assertEqual(action['params']['type'], 'success',
                         action['params']['message'])
        self.assertIn(self.hn.name, action['params']['message'])
        self.assertEqual(self._residue_counts(), before)

    # ==================================================================
    # T6 — the health strip and the derived state
    # ==================================================================
    def test_w25_06_health_strip_and_state(self):
        connector = self._connector()
        self._mute_wordpress_touchpoints()
        connector.invalidate_recordset()

        self.assertFalse(connector.last_received_at)
        self.assertEqual(connector.received_7d_count, 0)
        self.assertIn('No submission ever received', connector.health_note)

        connector.action_provision_credentials()
        connector.invalidate_recordset()
        self.assertEqual(connector.state, 'credentials_issued')

        touch = self._wordpress_touchpoint()
        connector.invalidate_recordset()
        self.assertEqual(connector.last_received_at, touch.received_at)
        self.assertEqual(connector.received_7d_count, 1)
        self.assertEqual(connector.state, 'live')
        self.assertIn('Last submission', connector.health_note)

        # …and a pipe that has gone quiet says so.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_lead_touchpoint SET received_at = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=48), touch.id))
        self.env.invalidate_all()
        connector.invalidate_recordset()
        self.assertIn('Nothing for over', connector.health_note)
        self.assertEqual(connector.received_7d_count, 1)

    # ==================================================================
    # T7 — heartbeat write-through, watcher handover, archived fallback
    # ==================================================================
    def test_w25_07_heartbeat_write_through(self):
        connector = self._connector()
        ConfigParameter = self.env['ir.config_parameter'].sudo()
        watcher_a = new_test_user(self.env, login='wl_w25_watcher_a',
                                  password='wl_w25_watcher_a_pw')
        watcher_b = new_test_user(self.env, login='wl_w25_watcher_b',
                                  password='wl_w25_watcher_b_pw')
        self._heartbeat_activities().unlink()

        connector.write({'heartbeat_enabled': True,
                         'heartbeat_user_id': watcher_a.id})
        self.assertEqual(self.Param.get_param(PARAM_HEARTBEAT_ENABLED), 'True')
        self.assertEqual(self.Param.get_param(PARAM_HEARTBEAT_USER),
                         str(watcher_a.id))

        connector.write({'heartbeat_enabled': False})
        self.assertEqual(self.Param.get_param(PARAM_HEARTBEAT_ENABLED),
                         'False')
        # Ledger §5.36 — the ROW must survive. `set_param(key, False)` unlinks
        # it, and a get_param-with-default reader then snaps the switch back
        # on: the kill switch would be inert.
        self.assertTrue(
            ConfigParameter.search_count(
                [('key', '=', PARAM_HEARTBEAT_ENABLED)]),
            'switching the heartbeat off UNLINKED the parameter')

        # The open to-do follows the watcher instead of being stranded.
        self.Service._heartbeat_alert(self.Touchpoint.browse())
        alerts = self._heartbeat_activities()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.user_id, watcher_a)

        connector.write({'heartbeat_user_id': watcher_b.id})
        alerts = self._heartbeat_activities()
        self.assertEqual(len(alerts), 1,
                         'the watcher change stranded or duplicated the open '
                         'alert')
        self.assertEqual(alerts.user_id, watcher_b)

        connector.write({'heartbeat_user_id': False})
        self.assertEqual(self.Param.get_param(PARAM_HEARTBEAT_USER), '0',
                         'clearing the watcher must write the string "0", '
                         'never a falsy value that unlinks the parameter')
        self.assertTrue(
            ConfigParameter.search_count([('key', '=', PARAM_HEARTBEAT_USER)]))

    def test_w25_07b_heartbeat_fallback_never_returns_an_archived_admin(self):
        """W2 review LOW — the finding, re-measured on Odoo 19.

        The handover (fact #11, and ledger §5.89's closing caveat) says a
        `user_ids[0]` fallback "does not apply the active filter", because a
        relational read carries `active_test=False`. Measured on vietuat that
        is NOT what `res.groups.user_ids` does: it honours the CALLER's
        `active_test`, so with the relation row present in
        `res_groups_users_rel` and the user archived the field reads back
        EMPTY in an ordinary context and `[ghost]` under
        `active_test=False`. So the un-guarded code was already safe on the
        cron's own path — and would break the moment it was called from any
        environment carrying that context, which is not ours to assume.

        `.filtered('active')` makes the answer the same either way. This test
        drives BOTH contexts, so the guard is exercised where it matters
        rather than asserted where it never fires.
        """
        # '0', not '': an empty value UNLINKS the parameter (§5.36), and the
        # resolver already reads a dangling id as "fall through".
        self.Param.set_param(PARAM_HEARTBEAT_USER, '0')
        group = self.env.ref('health_api_gateway.group_gateway_admin')
        ghost = new_test_user(self.env, login='wl_w25_ghost_admin',
                              password='wl_w25_ghost_admin_pw')
        # Replace the membership rather than archiving the live admins: the
        # point is a group whose ONLY member is inactive.
        group.sudo().write({'user_ids': [(6, 0, ghost.ids)]})
        ghost.sudo().write({'active': False})
        self.env.flush_all()
        self.env.invalidate_all()

        self.env.cr.execute(
            "SELECT uid FROM res_groups_users_rel WHERE gid = %s", (group.id,))
        self.assertEqual({row[0] for row in self.env.cr.fetchall()},
                         set(ghost.ids),
                         'the fixture did not isolate the group membership')
        self.assertEqual(
            group.sudo().with_context(active_test=False).user_ids, ghost,
            'the membership row is there but the field does not see it')

        admin = self.env.ref('base.user_admin')
        for label, service in (
                ('default', self.Service),
                ('active_test=False',
                 self.Service.with_context(active_test=False))):
            with self.subTest(ambient=label):
                resolved = service._heartbeat_user()
                self.assertNotEqual(
                    resolved, ghost,
                    'the fallback handed the alert to an ARCHIVED account')
                self.assertEqual(
                    resolved, admin,
                    'with no ACTIVE gateway admin the documented last resort '
                    'is base.user_admin')

    # ==================================================================
    # T9 — the ACL matrix
    # ==================================================================
    def _live_closure(self, group):
        """Every group reachable from `group` through the LIVE
        `res_groups_implied_rel` table — ledger §5.88: the closure computed
        from the security XML is a claim about the addons, not about this
        database."""
        self.env.flush_all()
        self.env.cr.execute("""
            WITH RECURSIVE closure(gid) AS (
                SELECT %s
                UNION
                SELECT rel.hid FROM res_groups_implied_rel rel
                JOIN closure ON closure.gid = rel.gid
            )
            SELECT gid FROM closure
        """, (group.id,))
        return {row[0] for row in self.env.cr.fetchall()}

    def test_w25_09_acl_matrix(self):
        connector = self._connector()
        granted = self.env.ref('base.group_system') \
            | self.env.ref('health_crm.group_health_crm_manager') \
            | self.env.ref('health_user_admin.group_health_user_admin')

        for suffix, group_xmlid in (
                ('sys', 'base.group_system'),
                ('crm', 'health_crm.group_health_crm_manager'),
                ('uadm', 'health_user_admin.group_health_user_admin')):
            with self.subTest(persona=suffix):
                user = new_test_user(
                    self.env, login='wl_w25_ok_%s' % suffix,
                    password='wl_w25_ok_%s_pw' % suffix,
                    groups='base.group_user,%s' % group_xmlid)
                readable = connector.with_user(user)
                self.assertTrue(readable.name)
                readable.write({'name': readable.name})

        for suffix, group_xmlid in (
                ('recep', 'health_base.group_healthcare_receptionist'),
                ('svc', SERVICE_GROUP)):
            with self.subTest(persona=suffix):
                user = new_test_user(
                    self.env, login='wl_w25_no_%s' % suffix,
                    password='wl_w25_no_%s_pw' % suffix,
                    groups='base.group_user,%s' % group_xmlid)
                # §5.88 first: name the edge before asserting the denial, so a
                # live implication that grants access fails HERE with a
                # readable message instead of as a mystery AccessError miss.
                closure = set()
                for group in user.group_ids:
                    closure |= self._live_closure(group)
                self.assertFalse(
                    closure & set(granted.ids),
                    '%s reaches a connector group through the live '
                    'res_groups_implied_rel table' % suffix)
                with self.assertRaises(AccessError):
                    self.Connector.with_user(user).search([], limit=1)

    # ==================================================================
    # T10 — the catalogue, the sidebar leaf, and the singleton index
    # ==================================================================
    def test_w25_10_catalogue_sidebar_and_singleton(self):
        for xmlid in ('view_web_leads_connector_form',
                      'view_web_leads_connector_list',
                      'action_web_leads_connector',
                      'menu_web_leads_connector',
                      'item_web_leads_connector'):
            self.assertTrue(
                self.env.ref('%s.%s' % (MODULE, xmlid),
                             raise_if_not_found=False),
                '%s did not load' % xmlid)

        # Ledger §5.69 — a sidebar item WITH children stops navigating and
        # breaks its parent; and no `parent_id` may be written at all.
        item = self.env.ref('%s.item_web_leads_connector' % MODULE)
        self.assertFalse(item.parent_id)
        self.assertFalse(self.env['cms.sidebar.item'].search_count(
            [('parent_id', '=', item.id)]))
        self.assertEqual(item.action_xmlid,
                         '%s.action_web_leads_connector' % MODULE)
        # ADMIN, not CRM: the 19.0.1.2.0 menu consolidation moved the
        # configuration tables out of the daily-work sections, and this is a
        # singleton config record. Moving it also resolved the sequence-13
        # collision it had with health_care_command_channels' Unrouted
        # Contacts, where ordering fell through to `id`.
        self.assertEqual(item.section_id,
                         self.env.ref('health_cms_sidebar.section_admin'))
        other = self.env.ref('%s.item_web_touchpoints' % MODULE)
        self.assertNotEqual(item.sequence, other.sequence,
                            'two sidebar leaves must not share a sequence')
        siblings = self.env['cms.sidebar.item'].search(
            [('section_id', '=', item.section_id.id),
             ('sequence', '=', item.sequence), ('id', '!=', item.id)])
        self.assertFalse(siblings,
                         'sequence %s is shared in ADMIN' % item.sequence)

        # The view must RENDER, not merely load: `get_view` runs the
        # field/attribute validator that a raw arch read skips.
        for view_type in ('form', 'list'):
            self.assertTrue(self.Connector.get_view(
                self.env.ref('%s.view_web_leads_connector_%s'
                             % (MODULE, view_type)).id, view_type)['arch'])

        # Ledger §5.1 + §5.55 — the partial unique index is the singleton, and
        # an IntegrityError needs a savepoint or the transaction is poisoned.
        connector = self._connector()
        self.assertTrue(connector)
        with self.assertRaises(psycopg2.IntegrityError):
            with self.env.cr.savepoint():
                self.Connector.create(
                    {'name': 'Second connector',
                     'company_id': self.env.company.id})
                self.env.flush_all()

    # ==================================================================
    # T12 — the catalogue Odoo actually reads (R6 / §5.85, §5.67, §29)
    # ==================================================================
    @staticmethod
    def _po_body():
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'i18n', 'vi.po')
        with open(path, encoding='utf-8') as handle:
            return handle.read()

    def test_w25_12_po_covers_the_new_surfaces(self):
        body = self._po_body()
        for msgid in (
                'Website Connector',
                'Get credentials',
                'Rotate secret',
                'Test pipeline',
                'Disconnect',
                'Reconnect',
                'OAuth Client',
                'Client ID',
                'WordPress Configuration',
                'Form → City Map',
                'Page URL → City Map',
                'Daily Delivery Alert',
                'Alert Watcher',
                'Last Submission',
                'Submissions (7 days)',
                'Delivery Health',
                'Credentials issued',
                'Not connected',
                'Live',
                'Disconnected',
                'No submission ever received — the website side is not live '
                'yet.',
                'Website connector: pipeline OK',
                'Website connector: pipeline test failed',
                'Website disconnected',
                'Website reconnected'):
            self.assertIn('msgid "%s"' % msgid, body,
                          'no vi.po entry for %r' % msgid)

        # §5.85: the entries this phase adds must be shaped for the road they
        # actually travel. The structural sweep over the WHOLE file lives in
        # test_web_leads_w2.test_w2_12; this asserts the W2.5 additions did
        # not break it, and that the labels really reach the database.
        blocks = [block for block in body.split('\n\n')
                  if 'msgid' in block
                  and not re.search(r'^msgid ""$', block, re.M)]
        for block in blocks:
            msgid = re.search(r'^msgid "(.*)"$', block, re.M)
            label = msgid.group(1)[:60] if msgid else block[:60]
            self.assertIn('#. module: %s' % MODULE, block,
                          '%s has no `#. module:` line (§29 CRASHES load)'
                          % label)
            self.assertIn('\n#: ', block,
                          '%s has no `#:` occurrence (§5.67: read by nothing)'
                          % label)

    def test_w25_12b_new_labels_translate_at_runtime(self):
        from odoo.tools.translate import code_translations

        loaded = code_translations.get_python_translations(MODULE, 'vi_VN')
        self.assertTrue(loaded, 'the python catalogue is inert')
        self.assertNotEqual(
            loaded.get('Website connector: pipeline OK'),
            'Website connector: pipeline OK',
            'the pipeline-test notification never reached the catalogue')

        field = self.env.ref(
            '%s.field_web_leads_connector__wp_config_block' % MODULE,
            raise_if_not_found=False)
        self.assertTrue(field, 'the field xmlid does not exist — a guessed '
                               'model reference translates nothing (§5.85)')
        self.assertNotEqual(
            field.with_context(lang='vi_VN').field_description,
            field.with_context(lang='en_US').field_description,
            'the field label never reached the database in Vietnamese')


@tagged('post_install', '-at_install')
class TestWebLeadsConnectorHttp(ConnectorCaseMixin, HttpCase):
    """T8 — disconnecting really does stop the token grant.

    An `HttpCase`, because the claim is about `/oauth/token`, not about
    `active` being False on a record. See the module docstring for the two
    flags this needs (§5.75/§5.83).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_connector_fixtures()
        # §5.86 — own the user; never authenticate as admin/admin.
        cls.service_user = new_test_user(
            cls.env, login='svc_w25_disconnect',
            password='svc_w25_disconnect_pw',
            groups='base.group_user,%s' % SERVICE_GROUP)
        cls.secret = 'w25-disconnect-%s' % uuid.uuid4().hex[:8]
        scopes = cls.env.ref(WRITE_SCOPE_REF) | cls.env.ref(READ_SCOPE_REF)
        cls.oauth_client = cls.env['gateway.oauth.client'].create({
            'name': 'W2.5 Disconnect Test Client',
            'user_id': cls.service_user.id,
            'allowed_scope_ids': [(6, 0, scopes.ids)],
            'token_lifetime': 3600})
        cls.oauth_client._set_secret(cls.secret)

        cls.connector = cls.Connector.search(
            [('company_id', '=', cls.env.company.id)], limit=1) \
            or cls.Connector.create({})
        cls.connector.oauth_client_id = cls.oauth_client.id

    def _token(self):
        return self.url_open(
            '/oauth/token',
            data=json.dumps({'grant_type': 'client_credentials',
                             'client_id': self.oauth_client.client_id,
                             'client_secret': self.secret}).encode('utf-8'),
            headers={'Content-Type': 'application/json'})

    def test_w25_08_disconnect_stops_the_token_grant(self):
        granted = self._token()
        self.assertEqual(granted.status_code, 200, granted.text[:300])
        self.assertTrue(granted.json().get('access_token'))

        disconnected = self.connector.action_disconnect()
        self.assertEqual(
            disconnected['params'].get('next', {}).get('res_id'),
            self.connector.id,
            'disconnect must re-read the record or the header keeps offering '
            'Disconnect on an already-disconnected connector')
        self.env.flush_all()
        self.connector.invalidate_recordset()
        self.assertFalse(self.oauth_client.sudo().active,
                         'disconnect must ARCHIVE the client, never delete it')
        self.assertTrue(self.oauth_client.sudo().exists())
        self.assertEqual(self.connector.state, 'disconnected')

        denied = self._token()
        self.assertEqual(denied.status_code, 401, denied.text[:300])
        self.assertEqual(denied.json().get('error'), 'invalid_client')
        self.assertNotIn('access_token', denied.json())

        reconnected = self.connector.action_reconnect()
        self.assertEqual(
            reconnected['params'].get('next', {}).get('res_id'),
            self.connector.id)
        self.env.flush_all()
        self.connector.invalidate_recordset()
        self.assertTrue(self.oauth_client.sudo().active)
        self.assertEqual(self._token().status_code, 200)
