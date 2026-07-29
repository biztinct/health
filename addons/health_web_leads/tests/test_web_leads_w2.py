# -*- coding: utf-8 -*-
"""W2-T1, T2, T4, T5, T6, T8, T10, T11, T12 — the ops loop and the hardening.

TransactionCase throughout; the three cases that need a real HTTP request
(T3 reconcile auth, T7 the narrowed-ACL round trip, T9 the audit rows) live
in test_web_leads_endpoint.py because `_write_audit_row` uses a FRESH cursor
and a TransactionCase can never see it (ledger §5.63).
"""
import os
import re
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import psycopg2

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.health_api_gateway.controllers.gateway import ApiError
from odoo.addons.health_web_leads.models.web_lead_service import (
    CITY_HN, HEARTBEAT_SUMMARY, PARAM_FORM_CITY_MAP, PARAM_HEARTBEAT_ENABLED,
    PARAM_HEARTBEAT_USER, RECONCILE_MAX_IDS)

MODULE = 'health_web_leads'


@tagged('post_install', '-at_install')
class TestWebLeadsW2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Service = cls.env['web.lead.service']
        cls.Lead = cls.env['crm.lead']
        cls.Touchpoint = cls.env['health.lead.touchpoint']
        cls.hn = cls.Service._resolve_catchment(CITY_HN) \
            or cls.env['health.catchment.province'].create(
                {'name': 'Test Hanoi W2', 'code': 'HN'})
        cls.env['ir.config_parameter'].sudo().set_param(
            PARAM_FORM_CITY_MAP, '{"15838": "HN", "15670": "HCM"}')

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    def _lead(self, submission_id=None, **vals):
        base = {'name': 'W2 fixture lead', 'type': 'opportunity',
                'contact_status': 'lead', 'contact_name': 'W2 Fixture',
                'catchment_province_id': self.hn.id}
        if submission_id:
            base['external_submission_id'] = submission_id
        base.update(vals)
        return self.Lead.create(base)

    def _touchpoint(self, lead, event_id, received_at=None):
        return self.Touchpoint.create({
            'lead_id': lead.id,
            'occurred_at': received_at or fields.Datetime.now(),
            'received_at': received_at or fields.Datetime.now(),
            'touchpoint_type': 'form_submit',
            'source_system': 'wordpress',
            'external_event_id': event_id,
        })

    @staticmethod
    def _sid(tag):
        return 'w2-%s-%s' % (tag, uuid.uuid4().hex[:16])

    # ==================================================================
    # W2-T1 — known / missing across all three ways an id can be known
    # ==================================================================
    def test_w2_01_reconcile_splits_known_and_missing(self):
        by_lead = self._sid('lead')
        by_touch = self._sid('touch')
        absent_a = self._sid('gone-a')
        absent_b = self._sid('gone-b')

        self._lead(submission_id=by_lead)
        # The merged case: the touchpoint carries the id, the lead does not.
        host = self._lead(submission_id=self._sid('host'))
        self._touchpoint(host, by_touch)

        result = self.Service.reconcile({
            'submission_ids': [absent_a, by_lead, by_touch, absent_b]})

        self.assertEqual(result['known'], [by_lead, by_touch],
                         'a merged submission is KNOWN — its evidence is the '
                         'touchpoint, not the lead')
        self.assertEqual(result['missing'], [absent_a, absent_b])
        self.assertNotIn('counts', result,
                         'counts are computed only when a date is supplied')

        # Duplicates in the request collapse, order is the caller's.
        collapsed = self.Service.reconcile(
            {'submission_ids': [absent_a, by_lead, absent_a, by_lead]})
        self.assertEqual(collapsed['known'], [by_lead])
        self.assertEqual(collapsed['missing'], [absent_a])

        # A touchpoint of another TYPE carrying the same external id is not a
        # form submission and must not answer for one.
        other_kind = self._sid('cdr')
        self.Touchpoint.create({
            'lead_id': host.id, 'occurred_at': fields.Datetime.now(),
            'touchpoint_type': 'call_cdr', 'source_system': 'manual',
            'external_event_id': other_kind})
        self.assertEqual(
            self.Service.reconcile({'submission_ids': [other_kind]})['missing'],
            [other_kind])

    # ==================================================================
    # W2-T2 — the per-day counts, and the two 422s
    # ==================================================================
    def test_w2_02_reconcile_counts_and_input_gates(self):
        # A day far enough in the past that no live row shares it, so the
        # counts are exactly the three rows this test creates.
        day = datetime(2019, 1, 15, 8, 30, 0)
        self.assertFalse(
            self.Touchpoint.search_count(
                [('received_at', '>=', day.replace(hour=0, minute=0, second=0)),
                 ('received_at', '<', day.replace(hour=0, minute=0, second=0)
                  + timedelta(days=1))]),
            'the fixture day is not empty — pick another')

        for index in range(2):
            sid = self._sid('created-%s' % index)
            lead = self._lead(submission_id=sid)
            self._touchpoint(lead, sid, received_at=day)
        merged_host = self._lead(submission_id=self._sid('host'))
        self._touchpoint(merged_host, self._sid('merged'), received_at=day)

        result = self.Service.reconcile(
            {'submission_ids': [self._sid('probe')], 'date': '2019-01-15'})
        self.assertEqual(result['counts'], {'created': 2, 'merged': 1})

        # A neighbouring day sees none of it — the window is one UTC day.
        self.assertEqual(
            self.Service.reconcile({'submission_ids': [self._sid('probe')],
                                    'date': '2019-01-16'})['counts'],
            {'created': 0, 'merged': 0})

        # -- the input gates ------------------------------------------
        with self.assertRaises(ApiError) as caught:
            self.Service.reconcile(
                {'submission_ids': ['x-%s' % i
                                    for i in range(RECONCILE_MAX_IDS + 1)]})
        self.assertEqual(caught.exception.status_code, 422)

        for bad in ({}, {'submission_ids': []}, {'submission_ids': 'abc'},
                    {'submission_ids': None}):
            with self.subTest(payload=bad):
                with self.assertRaises(ApiError) as caught:
                    self.Service.reconcile(bad)
                self.assertEqual(caught.exception.status_code, 422)

        with self.assertRaises(ApiError) as caught:
            self.Service.reconcile({'submission_ids': [self._sid('p')],
                                    'date': '15/01/2019'})
        self.assertEqual(caught.exception.status_code, 422)

        # Exactly the cap is accepted (the gate is `>`, not `>=`).
        at_cap = self.Service.reconcile(
            {'submission_ids': ['cap-%s' % i for i in range(RECONCILE_MAX_IDS)]})
        self.assertEqual(len(at_cap['missing']), RECONCILE_MAX_IDS)

    # ==================================================================
    # W2-T4 — the heartbeat: off, stale, twice, fresh
    # ==================================================================
    def _quiet_the_pipe(self, hours):
        """Backdate every WordPress touchpoint. Raw SQL because `received_at`
        is set on create (ledger §5.9: flush before, invalidate after) — and
        a TransactionCase never commits, so live rows are restored on
        rollback."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE health_lead_touchpoint SET received_at = %s "
            "WHERE source_system = 'wordpress'",
            (fields.Datetime.now() - timedelta(hours=hours),))
        self.env.invalidate_all()

    def _heartbeat_activities(self, user):
        return self.env['mail.activity'].sudo().search(
            [('res_model', '=', False), ('user_id', '=', user.id),
             ('summary', '=', HEARTBEAT_SUMMARY)])

    def test_w2_04_heartbeat(self):
        watcher = new_test_user(self.env, login='wl_w2_heartbeat_watcher',
                                password='wl_w2_heartbeat_watcher_pw')
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param(PARAM_HEARTBEAT_USER, str(watcher.id))
        # Ledger §5.32 — pin the switch OFF again whatever happens, so no
        # later suite in this run inherits an armed canary through the
        # non-transactional ormcache.
        self.addCleanup(Param.set_param, PARAM_HEARTBEAT_ENABLED, 'False')
        self.addCleanup(Param.set_param, PARAM_HEARTBEAT_USER, '')

        self._quiet_the_pipe(48)

        # (a) disabled — silence, even though the pipe is provably dead.
        Param.set_param(PARAM_HEARTBEAT_ENABLED, 'False')
        self.assertFalse(self.Service._cron_heartbeat())
        self.assertFalse(self._heartbeat_activities(watcher))

        # (b) enabled + stale -> exactly one activity.
        Param.set_param(PARAM_HEARTBEAT_ENABLED, 'True')
        self.assertTrue(self.Service._cron_heartbeat())
        self.assertEqual(len(self._heartbeat_activities(watcher)), 1)

        # (c) run again -> still one (search-first dedupe, fact #3).
        self.assertFalse(self.Service._cron_heartbeat())
        self.assertEqual(len(self._heartbeat_activities(watcher)), 1)

        # (d) the pipe recovers -> no new activity is raised.
        self._heartbeat_activities(watcher).unlink()
        lead = self._lead(submission_id=self._sid('fresh'))
        self._touchpoint(lead, self._sid('fresh-touch'))
        self.assertFalse(self.Service._cron_heartbeat())
        self.assertFalse(self._heartbeat_activities(watcher))

    def test_w2_04b_heartbeat_user_resolution(self):
        """§5.16 regression: `res.groups` has `.user_ids`, never `.users` —
        the precedent this clones gets that wrong inside a blanket except,
        which silently degrades every alert to the admin account."""
        Param = self.env['ir.config_parameter'].sudo()
        self.addCleanup(Param.set_param, PARAM_HEARTBEAT_USER, '')

        watcher = new_test_user(self.env, login='wl_w2_heartbeat_named',
                                password='wl_w2_heartbeat_named_pw')
        Param.set_param(PARAM_HEARTBEAT_USER, str(watcher.id))
        self.assertEqual(self.Service._heartbeat_user(), watcher)

        # Garbage and dangling ids fall through instead of raising.
        for bad in ('not-an-id', '0', '99999999'):
            with self.subTest(param=bad):
                Param.set_param(PARAM_HEARTBEAT_USER, bad)
                self.assertNotEqual(self.Service._heartbeat_user(), watcher)

        Param.set_param(PARAM_HEARTBEAT_USER, '')
        self.assertTrue(self.Service._heartbeat_user(),
                        'with no configured watcher the fallback chain must '
                        'still resolve somebody')

    # ==================================================================
    # W2-T5 / W2-T6 — the inbound-email duplicate guard
    # ==================================================================
    def _msg(self, **overrides):
        msg = {'subject': 'New submission from the website',
               'from': 'wordpress@pkgdvietuc.com',
               'email_from': 'wordpress@pkgdvietuc.com',
               'body': '<p>Name: Nguyen Van A</p>',
               'message_id': '<%s@pkgdvietuc.com>' % uuid.uuid4().hex,
               'message_type': 'email'}
        msg.update(overrides)
        return msg

    def test_w2_05_message_new_with_known_marker_returns_the_lead(self):
        for variant in ('header', 'body', 'subject'):
            with self.subTest(marker=variant):
                sid = self._sid('mail-%s' % variant)
                lead = self._lead(submission_id=sid)
                marker = '[web-lead:%s]' % sid
                if variant == 'header':
                    msg = self._msg(**{'X-Web-Lead-Submission': sid})
                elif variant == 'body':
                    msg = self._msg(
                        body='<p>Name: Nguyen Van A</p><p>%s</p>' % marker)
                else:
                    msg = self._msg(subject='Website enquiry %s' % marker)

                before = self.Lead.search_count([])
                notes_before = len(lead.message_ids)

                returned = self.Lead.message_new(msg)

                self.assertEqual(returned, lead,
                                 'a marked notification email must file onto '
                                 'the lead its webhook already created')
                self.assertEqual(self.Lead.search_count([]), before,
                                 'message_new created a second lead')
                lead.invalidate_recordset()
                self.assertGreater(len(lead.message_ids), notes_before,
                                   'no log note was posted on the lead')
                self.assertIn(sid,
                              ' '.join(lead.message_ids.mapped('body')))

    def test_w2_06_message_new_without_a_known_marker_creates(self):
        cases = {
            'no marker at all': self._msg(),
            'unknown marker': self._msg(
                body='<p>[web-lead:%s]</p>' % self._sid('never-seen')),
            'malformed marker': self._msg(body='<p>[web-lead:short]</p>'),
            'header with junk': self._msg(
                **{'X-Web-Lead-Submission': 'nope!! not a uuid'}),
        }
        for label, msg in cases.items():
            with self.subTest(case=label):
                before = self.Lead.search_count([])
                created = self.Lead.message_new(msg)
                self.assertEqual(self.Lead.search_count([]), before + 1,
                                 'the normal create path did not run')
                self.assertTrue(created.exists())
                self.assertFalse(created.external_submission_id)

    def test_w2_06b_marker_parser_never_raises(self):
        """A parser that can raise would break the mail gateway for every
        model sharing this create path — not just for web leads."""
        for payload in (None, 'a string', 42, {'body': None},
                        {'body': object()}, {'subject': b'bytes'},
                        {None: 'x'}, {'X-Web-Lead-Submission': None}):
            with self.subTest(payload=payload):
                self.assertFalse(self.Lead._web_lead_marker(payload))

    # ==================================================================
    # W2-T8 — the narrowed service account, negatively
    # ==================================================================
    def _group_closure(self, group):
        """Every group reachable from `group` through implied_ids."""
        seen, todo = set(), [group]
        while todo:
            current = todo.pop()
            if current.id in seen:
                continue
            seen.add(current.id)
            todo.extend(current.implied_ids)
        return self.env['res.groups'].browse(sorted(seen))

    def test_w2_08_acl_negative(self):
        group = self.env.ref('health_web_leads.group_web_leads_service')

        # (a) the group implies NOTHING any more (M3). This is the assertion
        #     that fails the day someone re-adds a convenience group.
        closure = self._group_closure(group)
        self.assertEqual(closure, group,
                         'group_web_leads_service must imply no other group: '
                         'reached %s' % closure.mapped('name'))

        reachable = set(self.env['ir.model.access'].sudo().search(
            [('group_id', 'in', closure.ids)]).mapped('model_id.model'))
        self.assertEqual(reachable, {
            'crm.lead', 'crm.stage', 'crm.team', 'health.catchment.province',
            'health.lead.touchpoint', 'utm.campaign', 'utm.medium',
            'utm.source'})
        for forbidden in ('res.partner', 'account.move', 'account.move.line',
                          'health.ews.score'):
            self.assertNotIn(forbidden, reachable)

        # (b) the live probes, as the service user actually runs.
        service_user = new_test_user(
            self.env, login='wl_w2_acl_probe', password='wl_w2_acl_probe_pw',
            groups='base.group_user,health_web_leads.group_web_leads_service')

        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(service_user).create(
                {'name': 'W2 ACL probe partner'})
        with self.assertRaises(AccessError):
            self.env['account.move'].with_user(service_user).search([], limit=1)

        # …and the capture path's own models still work. W2.5 T11: the old
        # `assertIsNotNone` on a recordset was a TAUTOLOGY — `search()` returns
        # an empty recordset, never None, so it passed even for a model the
        # user cannot read (the AccessError would have been the real signal).
        # Assert the type instead, which only holds if the read went through.
        for model_name in ('crm.lead', 'health.lead.touchpoint'):
            with self.subTest(model=model_name):
                rows = self.env[model_name].with_user(service_user).search(
                    [], limit=1)
                self.assertEqual(rows._name, model_name,
                                 'the service user cannot read %s'
                                 % model_name)

    def test_w2_08b_ews_read_survives_and_it_is_not_ours_to_close(self):
        """HONEST NEGATIVE. The W1 review listed `health.ews.score` read as
        part of the salesman closure to be taken back. It is not: on this
        database `base.group_user` ITSELF implies
        `health_base.group_healthcare_base` (res_groups_implied_rel 1 -> 346,
        a live data edge — the module XML declares the arrow the other way),
        and that group carries the `health.ews.score base` ACL. The service
        user must keep `base.group_user` (mail.message, ir.sequence,
        res.partner read all hang off it), so every internal user on vietuat
        can read EWS scores and narrowing this group cannot change that.

        The test asserts the mechanism rather than the wish, so that the day
        somebody fixes the implication the failure points here.
        """
        base_user = self.env.ref('base.group_user')
        healthcare_base = self.env.ref('health_base.group_healthcare_base')
        if healthcare_base not in self._group_closure(base_user):
            self.skipTest('base.group_user no longer implies healthcare base '
                          '— re-check whether EWS read is still universal')
        service_user = new_test_user(
            self.env, login='wl_w2_ews_probe', password='wl_w2_ews_probe_pw',
            groups='base.group_user,health_web_leads.group_web_leads_service')
        # No raise: this is a property of base.group_user, not of our group.
        self.env['health.ews.score'].with_user(service_user).search([], limit=1)

    # ==================================================================
    # W2-T10 — the two IntegrityError race branches
    # ==================================================================
    def _payload(self, **overrides):
        payload = {
            'submission_id': self._sid('race'),
            'form_id': '15838',
            'submitted_at': '2026-07-28T09:30:00+07:00',
            'name': 'W2 Race Fixture',
            'email': '%s@webleads.invalid' % uuid.uuid4().hex[:12],
            'phone': self._free_phone(),
            'location': 'Hà Nội',
            'anti_spam': {'honeypot_filled': False, 'token_ok': True},
        }
        payload.update(overrides)
        return payload

    def _free_phone(self):
        for offset in range(0, 3000):
            candidate = '09%08d' % (78000000 + offset)
            if self.Lead.search_count([('phone', '=', candidate)]):
                continue
            if self.env['res.partner'].with_context(
                    active_test=False).search_count(
                    [('phone', 'ilike', candidate[-9:])]):
                continue
            return candidate
        raise AssertionError('no free fixture phone number available')

    def test_w2_10_create_race_answers_duplicate(self):
        """Single-threaded, this branch is unreachable — the search-first
        check would have found the winner. Mock the index firing instead;
        patch NARROWLY (one model's create) and leave the savepoint alone,
        because the savepoint is what keeps the transaction usable (§5.55)."""
        payload = self._payload()
        LeadCls = type(self.env['crm.lead'])
        original = LeadCls.create

        def exploding_create(self_, vals_list):
            raise psycopg2.IntegrityError(
                'duplicate key value violates unique constraint '
                '"crm_lead_external_submission_uidx"')

        with patch.object(LeadCls, 'create', exploding_create):
            result = self.Service.process_submission(payload)

        self.assertEqual(result['status'], 'duplicate')
        self.assertEqual(result['submission_id'], payload['submission_id'])
        self.assertIs(LeadCls.create, original, 'the patch leaked')

    def test_w2_10b_merge_race_answers_duplicate_with_the_candidate(self):
        phone = self._free_phone()
        candidate = self._lead(name='W2 Race Fixture',
                               contact_name='W2 Race Fixture', phone=phone)
        payload = self._payload(phone=phone, name='W2 Race Fixture')

        TouchpointCls = type(self.env['health.lead.touchpoint'])

        def exploding_create(self_, vals_list):
            raise psycopg2.IntegrityError(
                'duplicate key value violates unique constraint '
                '"health_lead_touchpoint_ext_uidx"')

        with patch.object(TouchpointCls, 'create', exploding_create):
            result = self.Service.process_submission(payload)

        self.assertEqual(result['status'], 'duplicate')
        self.assertEqual(result['lead_ref'], candidate.unique_contact_code,
                         'the merge race must answer against the known merge '
                         'target, not with an empty ref')

    # ==================================================================
    # W2-T11 — the view catalogue
    # ==================================================================
    def test_w2_11_views_and_menu(self):
        for xmlid in ('view_health_lead_touchpoint_list',
                      'view_health_lead_touchpoint_form',
                      'view_health_lead_touchpoint_search',
                      'action_health_lead_touchpoint',
                      'menu_health_lead_touchpoint',
                      'view_healthcare_opportunity_form_web_attribution',
                      'view_crm_contact_form_crm_center_web_attribution',
                      'view_lead_source_modal_web_attribution',
                      'view_crm_case_opportunities_filter_web_leads',
                      'view_crm_contact_search_crm_center_web_leads',
                      'item_web_touchpoints'):
            self.assertTrue(
                self.env.ref('%s.%s' % (MODULE, xmlid),
                             raise_if_not_found=False),
                '%s did not load' % xmlid)

        # Ledger §5.69 — the CMS-shell persona never sees a backend menuitem,
        # and a sidebar item WITH children stops navigating (and breaks its
        # parent). Assert both properties, not just existence.
        item = self.env.ref('%s.item_web_touchpoints' % MODULE)
        self.assertFalse(item.parent_id, 'the sidebar item must be a leaf '
                                         'sibling, never a child')
        self.assertFalse(
            self.env['cms.sidebar.item'].search_count(
                [('parent_id', '=', item.id)]),
            'a sidebar item with children becomes a non-navigating group')
        self.assertEqual(item.action_xmlid,
                         '%s.action_health_lead_touchpoint' % MODULE)

        # A model with no `name` renders as `health.lead.touchpoint,97` in
        # every breadcrumb and m2o label until it computes a display name.
        touch = self._touchpoint(self._lead(), self._sid('naming'))
        self.assertNotIn('health.lead.touchpoint', touch.display_name)
        self.assertIn('Website Form Submission', touch.display_name)

        # Ledger §5.42 — `get_view()` STRIPS group-gated nodes for a caller
        # who is not a member, and in a TransactionCase the caller is
        # SUPERUSER, a member of nothing. `get_combined_arch()` applies the
        # inheritance without the group node-removal, so it is the honest
        # assertion for "did my xpath merge".
        full_form = self.env.ref('health_crm.view_healthcare_opportunity_form')
        arch = full_form.get_combined_arch()
        self.assertIn('name="web_attribution"', arch)
        for field_name in ('city_source', 'city_conflict', 'web_needs_review',
                           'web_form_id', 'external_submission_id',
                           'web_landing_url', 'web_submit_page_url',
                           'web_referrer_url', 'utm_content', 'utm_term',
                           'gclid', 'fbclid', 'fbc', 'fbp', 'ga_client_id',
                           'web_consent_marketing', 'web_consent_text_version',
                           'web_touchpoint_ids'):
            self.assertIn('name="%s"' % field_name, arch,
                          '%s is missing from the Web Attribution tab'
                          % field_name)

        # §5.41 — the CMS sidebar's "Contacts" entry opens a DIFFERENT
        # primary form (`view_crm_contact_form_crm_center`, priority 50). The
        # triage tab has to merge into that one too or the ops persona never
        # sees it; this assertion is what stops a future edit dropping it.
        cms_form = self.env.ref('health_crm.view_crm_contact_form_crm_center')
        cms_arch = cms_form.get_combined_arch()
        self.assertIn('name="web_attribution"', cms_arch)
        for field_name in ('web_needs_review', 'city_conflict', 'city_source',
                           'external_submission_id', 'web_touchpoint_ids'):
            self.assertIn('name="%s"' % field_name, cms_arch)
        cms_search_arch = self.env.ref(
            'health_crm.view_crm_contact_search_crm_center').get_combined_arch()
        self.assertIn('name="filter_web_needs_review"', cms_search_arch)

        modal = self.env.ref('health_landing.view_lead_source_modal')
        modal_arch = modal.get_combined_arch()
        for field_name in ('city_source', 'web_form_id', 'web_needs_review',
                           'city_conflict'):
            self.assertIn('name="%s"' % field_name, modal_arch)

        search_arch = self.env.ref(
            'crm.view_crm_case_opportunities_filter').get_combined_arch()
        for filter_name in ('filter_web_needs_review',
                            'filter_web_city_conflict', 'filter_web_leads'):
            self.assertIn('name="%s"' % filter_name, search_arch)

        # The views must also actually RENDER: `get_combined_arch` only
        # applies the xpaths, while `get_view` runs the field/attribute
        # validator that rejects a typo'd field name. (`get_view` is a MODEL
        # method — `view.get_view()` would return the form of `ir.ui.view`.)
        self.assertTrue(
            self.env['crm.lead'].get_view(full_form.id, 'form')['arch'])
        self.assertTrue(
            self.env['crm.lead'].get_view(modal.id, 'form')['arch'])
        self.assertTrue(
            self.env['crm.lead'].get_view(cms_form.id, 'form')['arch'])
        for search_xmlid in ('crm.view_crm_case_opportunities_filter',
                             'health_crm.view_crm_contact_search_crm_center'):
            self.assertTrue(self.env['crm.lead'].get_view(
                self.env.ref(search_xmlid).id, 'search')['arch'])
        for view_type in ('list', 'form', 'search'):
            self.assertTrue(self.env['health.lead.touchpoint'].get_view(
                self.env.ref('%s.view_health_lead_touchpoint_%s'
                             % (MODULE, view_type)).id, view_type)['arch'])

    # ==================================================================
    # W2-T12 — the catalogue is shaped so that Odoo actually reads it
    # ==================================================================
    @staticmethod
    def _po_blocks():
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'i18n', 'vi.po')
        with open(path, encoding='utf-8') as handle:
            body = handle.read()
        # Drop the header block (the one whose msgid is empty).
        return [block for block in body.split('\n\n')
                if 'msgid' in block and not re.search(r'^msgid ""$', block,
                                                      re.M)], body

    def test_w2_12_po_every_entry_is_readable(self):
        blocks, body = self._po_blocks()
        self.assertTrue(blocks, 'the catalogue is empty')

        inert = []
        for block in blocks:
            msgid = re.search(r'^msgid "(.*)"$', block, re.M)
            label = msgid.group(1)[:60] if msgid else block[:60]
            if '#. module: %s' % MODULE not in block:
                inert.append('%s — no `#. module:` line (§29 CRASHES load)'
                             % label)
                continue
            if '\n#: ' not in block:
                inert.append('%s — no `#:` occurrence (§5.67: read by nothing)'
                             % label)
                continue
            has_code_marker = ('#. odoo-python' in block
                               or '#. odoo-javascript' in block)
            has_code_occurrence = '#: code:addons/%s/' % MODULE in block
            has_model_occurrence = '#: model' in block
            if has_code_marker and not has_code_occurrence:
                inert.append('%s — code marker with no `#: code:` occurrence'
                             % label)
            if has_code_occurrence and not has_code_marker:
                inert.append('%s — `#: code:` occurrence with no `#. odoo-*` '
                             'marker (§5.58: silently inert)' % label)
            if not has_code_marker and not has_model_occurrence:
                inert.append('%s — neither a code nor a model occurrence'
                             % label)
        # NB §5.85 allows an entry to carry BOTH kinds when the same string
        # really lives in code and in a model term; what it forbids is a
        # LABEL whose only occurrence is a `code:` one. Structure cannot tell
        # those apart — test_w2_12b proves the labels by reading them back
        # out of the database in Vietnamese.
        self.assertFalse(inert, 'inert vi.po entries:\n  ' + '\n  '.join(inert))

        # Every W2 string the user or the ops team can see. NOT in this list:
        # `HEARTBEAT_SUMMARY`, deliberately — it is the dedupe KEY the cron
        # searches on, so it is stored verbatim in English and translating it
        # would only add an inert entry (the note body beside it IS
        # translated, and that is the sentence a human reads).
        for msgid in (
                'Web Leads Service',
                'submission_ids is required and must be a non-empty list',
                'submission_ids accepts at most %s ids per call',
                'date must be formatted YYYY-MM-DD',
                'Web Attribution',
                'Web Touchpoints',
                'Needs review (web)',
                'City conflict',
                'Web leads'):
            self.assertIn('msgid "%s"' % msgid, body,
                          'no vi.po entry for %r' % msgid)
        self.assertNotIn('msgid "%s"' % HEARTBEAT_SUMMARY, body,
                         'the heartbeat dedupe key must not be translated — '
                         'the cron searches on the English literal')

    def test_w2_12b_po_new_surfaces_translate_at_runtime(self):
        """§5.67's lesson: shape is necessary, not sufficient — spot-check a
        RUNTIME translation and a MODEL TERM that W2 added."""
        from odoo.tools.translate import code_translations

        loaded = code_translations.get_python_translations(MODULE, 'vi_VN')
        self.assertTrue(loaded, 'the python catalogue is inert')
        self.assertEqual(loaded.get('date must be formatted YYYY-MM-DD'),
                         'Ngày phải theo định dạng YYYY-MM-DD')

        group = self.env.ref('health_web_leads.group_web_leads_service')
        self.assertNotEqual(
            group.with_context(lang='vi_VN').name, 'Web Leads Service',
            'the res.groups name never reached the database in Vietnamese')

        scope = self.env.ref('health_web_leads.scope_web_lead_read')
        self.assertNotEqual(
            scope.with_context(lang='vi_VN').name, 'Web Leads Read',
            'the api.key.scope name never reached the database in Vietnamese')

        field = self.env.ref(
            'health_web_leads.field_crm_lead__web_needs_review')
        self.assertNotEqual(
            field.with_context(lang='vi_VN').help,
            field.with_context(lang='en_US').help,
            'the field help never reached the database in Vietnamese')
