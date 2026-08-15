# -*- coding: utf-8 -*-
"""W3-T1 … T12 — the consent bridge, campaign review, funnel and retention.

`TransactionCase` throughout: nothing in W3 is an HTTP surface.

**Every conversion in this file runs as a REAL ops user** (ledger §5.4 /
handover §5). W2.5's D3 exists because uid-1 tests hid an ACL failure that
the button surfaced the moment a human pressed it — uid 1 always runs as su
(§5.4), so a conversion driven by uid 1 proves nothing about the ops desk.
The persona is modelled on the live one (vietuat uid 40 `crm`): CRM Manager
+ Operations Manager + the stock sales administrator, with a catchment
province, because `crm.lead` / `res.partner` are catchment-scoped by record
rule (`health_crm/security/health_crm_security.xml:30-62`).
"""
import logging
import os
import re
import uuid
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.health_web_leads.models.health_consent import WEB_FORM_METHOD
from odoo.addons.health_web_leads.models.lead_touchpoint import (
    UNMATCHED_CAMPAIGN_DOMAIN)
from odoo.addons.health_web_leads.models.web_lead_service import (
    CITY_HN, PARAM_RAW_RETENTION_DAYS)

MODULE = 'health_web_leads'


@tagged('post_install', '-at_install')
class TestWebLeadsW3(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Service = cls.env['web.lead.service']
        cls.Lead = cls.env['crm.lead']
        cls.Touchpoint = cls.env['health.lead.touchpoint']
        cls.Consent = cls.env['health.consent']
        cls.Partner = cls.env['res.partner']

        cls.province = cls.Service._resolve_catchment(CITY_HN) \
            or cls.env['health.catchment.province'].create(
                {'name': 'Test Hanoi W3', 'code': 'HN'})

        # The ops persona. `catchment_province_id` is not decoration: without
        # it every catchment record rule denies, and the conversion fails for
        # a reason that has nothing to do with this phase.
        cls.ops = new_test_user(
            cls.env, login='wl_w3_ops', password='wl_w3_ops_pw',
            groups='base.group_user,sales_team.group_sale_manager,'
                   'health_crm.group_health_crm_manager,'
                   'health_base.group_healthcare_operations_manager',
            catchment_province_id=cls.province.id)

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------
    @staticmethod
    def _sid(tag):
        return 'w3-%s-%s' % (tag, uuid.uuid4().hex[:16])

    @classmethod
    def _free_phone(cls):
        """A valid VN mobile that matches NO live lead and NO live partner.

        vietuat carries 476 leads and a full client book; a fixture number
        that happens to belong to one of them would silently re-route the
        conversion onto somebody real (ledger §5.17's live-data lesson).
        """
        Lead = cls.env['crm.lead']
        Partner = cls.env['res.partner']
        for offset in range(0, 4000):
            candidate = '09%08d' % (76000000 + offset)
            if Lead.search_count([('phone', '=', candidate)]):
                continue
            if Partner.with_context(active_test=False).search_count(
                    [('phone', 'ilike', candidate[-9:])]):
                continue
            return candidate
        raise AssertionError('no free fixture phone number available')

    def _web_lead(self, consent=True, name=None, phone=None, email=None,
                  version='v1.2-2026-07', **vals):
        """A lead exactly as the capture endpoint leaves it."""
        submission_id = self._sid('sub')
        base = {
            'name': name or 'Web: W3 %s' % uuid.uuid4().hex[:8],
            'type': 'opportunity',
            'contact_relationship_type': 'client',
            'contact_status': 'active',
            'contact_name': 'W3 Fixture Person',
            'phone': phone or self._free_phone(),
            'email_from': email or ('%s@webleads.invalid'
                                    % uuid.uuid4().hex[:12]),
            'catchment_province_id': self.province.id,
            'mode_of_contact_id': self.env['health.lookup.value']._default_for('mode_of_contact', 'website'),
            'external_submission_id': submission_id,
            'web_consent_marketing': consent,
            'web_consent_text_version': version,
        }
        base.update(vals)
        lead = self.Lead.create(base)
        occurred_at = fields.Datetime.now() - timedelta(days=3)
        self.Touchpoint.create({
            'lead_id': lead.id,
            'occurred_at': occurred_at,
            'received_at': fields.Datetime.now() - timedelta(days=2),
            'touchpoint_type_id': self.env['health.lookup.value']._default_for('touchpoint_type', 'form_submit'),
            'source_system': 'wordpress',
            'external_event_id': submission_id,
            'utm_campaign': False,
            'raw_payload': '{"submission_id": "%s"}' % submission_id,
        })
        return lead, submission_id, occurred_at

    def _convert(self, lead):
        """Drive the real conversion as the ops persona."""
        lead.with_user(self.ops).action_convert_to_client()
        lead.invalidate_recordset()
        return lead.patient_id

    def _marketing_consents(self, patient):
        return self.Consent.sudo().with_context(active_test=False).search(
            [('client_id', '=', patient.id),
             ('consent_type_code', '=', 'marketing')])

    @staticmethod
    def _bodies(record):
        return ' '.join(str(message.body or '')
                        for message in record.sudo().message_ids)

    def _flush_tracking(self):
        """Ledger §5.56 — tracking messages post at PRECOMMIT, and a
        TransactionCase never commits. Without this a tracked write looks
        silent, which would make T3's "the bridge posted nothing" pass for
        the wrong reason."""
        self.env.flush_all()
        self.env.cr.precommit.run()

    # ==================================================================
    # T1 — the happy path, end to end, as a real ops user
    # ==================================================================
    def test_w3_01_bridge_creates_a_real_consent(self):
        lead, submission_id, occurred_at = self._web_lead()
        patient = self._convert(lead)

        self.assertTrue(patient, 'the conversion produced no client')
        self.assertEqual(lead.web_consent_bridged, 'created')

        consents = self._marketing_consents(patient)
        self.assertEqual(len(consents), 1,
                         'exactly one marketing consent must exist')
        consent = consents
        self.assertEqual(consent.method, WEB_FORM_METHOD)
        self.assertEqual(consent.state, 'active')
        self.assertTrue(consent.self_granted)
        self.assertEqual(consent.client_mutation_id,
                         'web-lead-%d-%s' % (lead.id, submission_id))
        self.assertIn(submission_id, consent.scope_note)
        self.assertIn('v1.2-2026-07', consent.scope_note)
        self.assertEqual(consent.effective_date,
                         fields.Date.to_date(occurred_at),
                         'the consent is effective from the SUBMISSION, not '
                         'from the day ops happened to convert')

        # The whole point of the phase: the rail now answers truthfully.
        self.assertTrue(patient.sudo().can_send_marketing())

        # Chatter both ways — the audit trail has to be readable from either
        # end (from the lead: "what became of the box?"; from the consent:
        # "where did this come from?").
        self.assertIn(consent.name, self._bodies(lead))
        self.assertIn(submission_id, self._bodies(consent))

    # ==================================================================
    # T2 — re-fire safe: the chokepoint fires from create(), write() and
    #      every convert action
    # ==================================================================
    def test_w3_02_refire_never_creates_a_second_consent(self):
        lead, _submission_id, _occurred = self._web_lead()
        patient = self._convert(lead)
        self.assertEqual(len(self._marketing_consents(patient)), 1)

        # (a) the same button again
        self._convert(lead)
        # (b) a write that re-triggers `_process_contact_relationship`
        #     (`health_crm/models/crm_lead.py:1100-1101`)
        lead.with_user(self.ops).write({'contact_outcome': 'service_booked'})
        # (c) the chokepoint called directly, as a wizard would
        lead.with_user(self.ops)._get_or_create_patient()
        lead.invalidate_recordset()

        self.assertEqual(len(self._marketing_consents(patient)), 1,
                         'the bridge re-fired and created a second consent')
        self.assertEqual(lead.web_consent_bridged, 'created',
                         'the marker must be written exactly once')

    # ==================================================================
    # T3 — declined: no record, no note, and the rail says no
    # ==================================================================
    def test_w3_03_declined_claim_creates_nothing(self):
        lead, _submission_id, _occurred = self._web_lead(consent=False)
        before = set(lead.sudo().message_ids.ids)

        patient = self._convert(lead)
        self._flush_tracking()
        lead.invalidate_recordset()

        self.assertEqual(lead.web_consent_bridged, 'skipped_declined')
        self.assertFalse(self._marketing_consents(patient))
        self.assertFalse(patient.sudo().can_send_marketing())

        # The ABSENCE of consent is not an event: no note. A tracking-only
        # message (the field is tracked) carries an empty body, so asserting
        # on bodies stays true in production as well as in the test cursor.
        added = lead.sudo().message_ids.filtered(
            lambda m: m.id not in before and (m.body or '').strip())
        for message in added:
            self.assertNotIn('consent', str(message.body).lower(),
                             'the bridge posted a note about a consent that '
                             'was never given')

    # ==================================================================
    # T4 — rail B4: skip, never supersede a staff-captured consent
    # ==================================================================
    def test_w3_04_existing_active_consent_is_never_superseded(self):
        phone = self._free_phone()
        email = '%s@webleads.invalid' % uuid.uuid4().hex[:12]
        name = 'Web: W3 Existing %s' % uuid.uuid4().hex[:8]
        # The client already exists and the submitter IS them, so identity
        # cannot be what makes this test pass.
        patient = self.Partner.create({
            'name': name, 'is_patient': True, 'is_company': False,
            'phone': phone, 'email': email,
            'catchment_province_id': self.province.id})
        staff_consent = self.Consent.create({
            'client_id': patient.id, 'consent_type_id': self.env['health.lookup.value']._default_for('consent_type', 'marketing'),
            'method': 'verbal', 'self_granted': True,
            'verbal_witness_id': self.env.uid,
            'scope_note': 'Captured at the desk by a human'})
        staff_consent.action_grant()
        self.assertEqual(staff_consent.state, 'active')

        lead, _submission_id, _occurred = self._web_lead(
            name=name, phone=phone, email=email)
        converted = self._convert(lead)
        self.assertEqual(converted, patient,
                         'the fixture did not reuse the existing client')

        self.assertEqual(lead.web_consent_bridged, 'skipped_existing')
        staff_consent.invalidate_recordset()
        self.assertEqual(staff_consent.state, 'active',
                         'the staff-captured consent was superseded')
        self.assertFalse(staff_consent.withdrawal_date)
        self.assertEqual(self._marketing_consents(patient), staff_consent,
                         'a second marketing consent was created')

        notes = [m for m in lead.sudo().message_ids
                 if 'already holds an active marketing consent'
                 in str(m.body or '')]
        self.assertEqual(len(notes), 1, 'expected exactly one skip note')

    # ==================================================================
    # T5 — rail B3: the representative case never self-grants for someone
    # ==================================================================
    def test_w3_05_identity_mismatch_records_the_reason_once(self):
        name = 'Web: W3 Relative %s' % uuid.uuid4().hex[:8]
        patient = self.Partner.create({
            'name': name, 'is_patient': True, 'is_company': False,
            'phone': self._free_phone(),
            'email': '%s@webleads.invalid' % uuid.uuid4().hex[:12],
            'catchment_province_id': self.province.id})

        # Same NAME (so the conversion resolves to this client), different
        # phone AND email — the person enquiring is not the person cared for.
        lead, _submission_id, _occurred = self._web_lead(name=name)
        converted = self._convert(lead)
        self.assertEqual(converted, patient)

        self.assertEqual(lead.web_consent_bridged, 'skipped_identity')
        self.assertFalse(self._marketing_consents(patient))
        self.assertFalse(patient.sudo().can_send_marketing())
        # The claim is not lost — it is still on the lead for a human.
        self.assertTrue(lead.web_consent_marketing)

        # Re-fire: still exactly one note, not one per conversion attempt.
        self._convert(lead)
        lead.with_user(self.ops).write({'contact_outcome': 'service_booked'})
        notes = [m for m in lead.sudo().message_ids
                 if 'do not match the client' in str(m.body or '')]
        self.assertEqual(len(notes), 1)
        self.assertFalse(self._marketing_consents(patient))

    # ==================================================================
    # T6 — rail B1: the bridge can NEVER cost an ops user their conversion
    # ==================================================================
    def test_w3_06_a_broken_bridge_does_not_break_conversion(self):
        lead, _submission_id, _occurred = self._web_lead()
        ConsentCls = type(self.env['health.consent'])
        original = ConsentCls.create

        def exploding_create(self_, vals_list):
            raise ValueError('staged consent failure')

        with self.assertLogs('odoo.addons.health_web_leads.models.crm_lead',
                             level=logging.WARNING) as captured:
            with patch.object(ConsentCls, 'create', exploding_create):
                patient = self._convert(lead)

        self.assertTrue(patient.exists(),
                        'the conversion did not produce a client')
        self.assertEqual(lead.patient_id, patient)
        self.assertIs(ConsentCls.create, original, 'the patch leaked')
        self.assertTrue(
            any('consent bridge failed' in line for line in captured.output),
            'the failure was swallowed without a warning')

        # Unmarked, so the next conversion retries rather than recording a
        # decision that was never taken.
        lead.invalidate_recordset()
        self.assertFalse(lead.web_consent_bridged)

        # …and the transaction is still usable: the savepoint is what makes
        # that true (§5.55).
        self.assertTrue(self.Lead.search_count([('id', '=', lead.id)]))

        # Now let it run for real — the retry works.
        self._convert(lead)
        self.assertEqual(lead.web_consent_bridged, 'created')

    # ==================================================================
    # T7 — the audit shape: locked after grant, refused without evidence
    # ==================================================================
    def test_w3_07_evidence_lock_and_the_web_form_grant_gate(self):
        lead, _submission_id, _occurred = self._web_lead()
        patient = self._convert(lead)
        consent = self._marketing_consents(patient)
        self.assertEqual(consent.state, 'active')

        # (a) the evidence lock, with NO superuser escape — the scope_note is
        #     the only record of which wording the visitor agreed to.
        with self.assertRaises(UserError):
            consent.write({'scope_note': 'rewritten after the fact'})

        # (b) our own gate. The core `action_grant` checks evidence with
        #     per-method `if` branches (health_consent.py:389-400), so a key
        #     added by `selection_add` would otherwise grant evidence-free.
        other = self.Partner.create({
            'name': 'W3 Gate Client %s' % uuid.uuid4().hex[:8],
            'is_patient': True, 'is_company': False,
            'catchment_province_id': self.province.id})
        draft = self.Consent.create({
            'client_id': other.id, 'consent_type_id': self.env['health.lookup.value']._default_for('consent_type', 'marketing'),
            'method': WEB_FORM_METHOD, 'self_granted': True})
        with self.assertRaises(UserError):
            draft.action_grant()
        self.assertEqual(draft.state, 'draft')

        draft.write({'scope_note': 'Website marketing consent checkbox'})
        with self.assertRaises(UserError):
            draft.action_grant()
        self.assertEqual(draft.state, 'draft')

        draft.write({'client_mutation_id': 'w3-gate-%s' % uuid.uuid4().hex[:8]})
        draft.action_grant()
        self.assertEqual(draft.state, 'active',
                         'with both evidence values the grant must succeed')

    # ==================================================================
    # T8 — campaign review + the find-only back-fill
    # ==================================================================
    def test_w3_08_campaign_review_and_backfill(self):
        raw = 'hn_w3backfill_leads_%s' % uuid.uuid4().hex[:8]
        lead, _submission_id, _occurred = self._web_lead()
        touch = self.Touchpoint.search(
            [('lead_id', '=', lead.id)], limit=1)
        touch.utm_campaign = raw
        self.assertFalse(lead.campaign_id)

        # (a) the review queue sees it…
        self.assertIn(touch, self.Touchpoint.search(
            UNMATCHED_CAMPAIGN_DOMAIN + [('id', '=', touch.id)]))
        Campaign = self.env['utm.campaign']
        self.assertFalse(Campaign.search([('name', '=ilike', raw)]),
                         'the fixture campaign must not exist yet')

        # (b) …and pressing the button now links nothing, because find-only
        #     means find-only.
        result = touch.with_user(self.ops).action_link_seeded_campaigns()
        self.assertEqual(result['params']['type'], 'warning')
        lead.invalidate_recordset()
        self.assertFalse(lead.campaign_id)
        self.assertFalse(Campaign.search([('name', '=ilike', raw)]),
                         'the back-fill CREATED a campaign — it must never')

        # (c) marketing seeds it, in a different case (the capture path
        #     matches `=ilike`, so the back-fill must too).
        before = Campaign.search_count([])
        campaign = Campaign.create({'name': raw.upper()})

        result = touch.with_user(self.ops).action_link_seeded_campaigns()
        self.assertEqual(result['params']['type'], 'success')
        lead.invalidate_recordset()
        self.assertEqual(lead.campaign_id, campaign)
        self.assertEqual(Campaign.search_count([]), before + 1,
                         'the action created a utm.campaign row')
        self.assertFalse(self.Touchpoint.search(
            UNMATCHED_CAMPAIGN_DOMAIN + [('id', '=', touch.id)]),
            'the row is still in the review queue after being linked')
        self.assertIn('linked retroactively', self._bodies(lead))

        # (d) `=ilike` is a SQL PATTERN. A raw value of '%' must not match
        #     every campaign in the register and mislabel a lead.
        wild_lead, _sub, _occ = self._web_lead()
        wild_touch = self.Touchpoint.search(
            [('lead_id', '=', wild_lead.id)], limit=1)
        wild_touch.utm_campaign = '%'
        wild_touch.with_user(self.ops).action_link_seeded_campaigns()
        wild_lead.invalidate_recordset()
        self.assertFalse(wild_lead.campaign_id,
                         'a wildcard raw campaign matched a real campaign')

    # ==================================================================
    # T9 — the catalogue, the sidebar leaves, and the button's gate
    # ==================================================================
    def _live_closure(self, group):
        """Ledger §5.88 — the closure that GOVERNS access lives in
        `res_groups_implied_rel`, not in the security XML, and on this
        database they disagree."""
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

    def test_w3_09_catalogue_sidebar_and_acl(self):
        for xmlid in ('action_campaign_review',
                      'menu_campaign_review',
                      'item_campaign_review',
                      'view_crm_lead_web_funnel_pivot',
                      'view_crm_lead_web_funnel_graph',
                      'action_web_leads_funnel',
                      'menu_web_leads_funnel',
                      'item_lead_analysis',
                      'ir_cron_web_leads_prune_raw_payloads',
                      'param_raw_payload_retention_days'):
            self.assertTrue(
                self.env.ref('%s.%s' % (MODULE, xmlid),
                             raise_if_not_found=False),
                '%s did not load' % xmlid)

        # The views must RENDER, not merely load: `get_view` runs the
        # field/attribute validator that a raw arch read skips.
        for view_type in ('pivot', 'graph'):
            arch = self.env['crm.lead'].get_view(
                self.env.ref('%s.view_crm_lead_web_funnel_%s'
                             % (MODULE, view_type)).id, view_type)['arch']
            self.assertIn('name="catchment_province_id"', arch)
            self.assertIn('name="mode_of_contact"', arch)
        # The outcome dimension is the pivot's SECOND row, not a
        # `search_default_` group-by: measured in the browser, a search-panel
        # group-by REPLACES a pivot's arch rows and the city axis disappears.
        pivot_arch = self.env.ref(
            '%s.view_crm_lead_web_funnel_pivot' % MODULE).arch
        self.assertIn('name="contact_status" type="row"', pivot_arch)
        funnel = self.env.ref('%s.action_web_leads_funnel' % MODULE)
        self.assertNotIn('search_default_groupby', funnel.context or '',
                         'a search-panel default would clobber the pivot '
                         'rows this action exists to show')
        list_arch = self.env['health.lead.touchpoint'].get_view(
            self.env.ref('%s.view_health_lead_touchpoint_list'
                         % MODULE).id, 'list')['arch']
        self.assertIn('action_link_seeded_campaigns', list_arch)
        search_arch = self.env.ref(
            '%s.view_health_lead_touchpoint_search' % MODULE
        ).get_combined_arch()
        self.assertIn('name="filter_unmatched_campaign"', search_arch)

        # Ledger §5.91 — `crm.lead` has THREE standalone primary form views on
        # this database, and the bridge marker has to reach ALL of them or the
        # persona who opens the third one never sees why a consent was (not)
        # created. §5.42: assert with `get_combined_arch`, which applies the
        # inheritance without the group node-removal `get_view` performs.
        for form_xmlid in ('health_crm.view_healthcare_opportunity_form',
                           'health_crm.view_crm_contact_form_crm_center',
                           'health_landing.view_lead_source_modal'):
            with self.subTest(form=form_xmlid):
                self.assertIn(
                    'name="web_consent_bridged"',
                    self.env.ref(form_xmlid).get_combined_arch(),
                    '%s does not show the consent-bridge outcome'
                    % form_xmlid)

        # Ledger §5.69 — a sidebar item WITH children stops navigating and
        # breaks its parent, and two leaves must not share a sequence.
        #
        # `item_campaign_review` no longer belongs here: the 19.0.1.2.0 menu
        # consolidation retired it, because it was the same
        # health.lead.touchpoint model as Web Touchpoints with only a different
        # domain — it is now the "Unmatched Campaigns" chip on that list
        # (health_web_leads/static/src/js/touchpoint_list_view.js). It is
        # asserted separately below, since a retired leaf is invisible to the
        # active_test search that the sequence-uniqueness check runs.
        section = self.env.ref('health_cms_sidebar.section_crm')
        siblings = self.env['cms.sidebar.item'].search(
            [('section_id', '=', section.id)])
        for item in [self.env.ref('%s.item_lead_analysis' % MODULE)]:
            self.assertFalse(item.parent_id, 'the leaf must be a sibling')
            self.assertFalse(self.env['cms.sidebar.item'].search_count(
                [('parent_id', '=', item.id)]))
            self.assertEqual(item.section_id, section)
            self.assertEqual(
                len(siblings.filtered(lambda s, i=item:
                                      s.sequence == i.sequence)), 1,
                'sequence %s is shared with another sidebar leaf'
                % item.sequence)
            # `match_models` would land in a LAST-WINS index and steal the
            # highlight from Contacts / Web Touchpoints (cms_sidebar.js:65).
            self.assertFalse(item.match_models)

        # Campaign Review: retired, not deleted — and its action must still be
        # in the shell allowlist via the Web Touchpoints leaf, or the chip that
        # replaced it would open outside the CMS chrome.
        review = self.env.ref('%s.item_campaign_review' % MODULE)
        self.assertFalse(review.active,
                         'Campaign Review is retired into the Web Touchpoints '
                         'chip bar')
        self.assertIn(
            '%s.action_campaign_review' % MODULE,
            self.env['cms.sidebar.item'].get_match_keys()['xmlids'],
            'the Campaign Review action must stay in the shell allowlist')

        # The back-fill gate, negatively. §5.88 first: name the edge before
        # asserting the denial, so a live implication that grants access
        # fails HERE with a readable message instead of as a mystery miss.
        granted = self.env['res.groups'].browse()
        for xmlid in ('base.group_system',
                      'health_user_admin.group_health_user_admin',
                      'health_crm.group_health_crm_manager',
                      'sales_team.group_sale_manager'):
            granted |= self.env.ref(xmlid)
        denied_user = new_test_user(
            self.env, login='wl_w3_recep', password='wl_w3_recep_pw',
            groups='base.group_user,'
                   'health_base.group_healthcare_receptionist')
        closure = set()
        for group in denied_user.group_ids:
            closure |= self._live_closure(group)
        self.assertFalse(
            closure & set(granted.ids),
            'the receptionist reaches a back-fill group through the live '
            'res_groups_implied_rel table')

        gate_lead, _sub, _occ = self._web_lead()
        touch = self.Touchpoint.search([('lead_id', '=', gate_lead.id)],
                                       limit=1)
        with self.assertRaises(AccessError):
            touch.with_user(denied_user).action_link_seeded_campaigns()

    # ==================================================================
    # T10 — retention: inert by default, surgical when switched on
    # ==================================================================
    def test_w3_10_retention_prunes_only_the_payload(self):
        Param = self.env['ir.config_parameter'].sudo()
        self.addCleanup(Param.set_param, PARAM_RAW_RETENTION_DAYS, '0')

        lead, _submission_id, _occurred = self._web_lead()
        old = self.Touchpoint.create({
            'lead_id': lead.id,
            'occurred_at': fields.Datetime.now() - timedelta(days=31),
            'received_at': fields.Datetime.now() - timedelta(days=31),
            'touchpoint_type_id': self.env['health.lookup.value']._default_for('touchpoint_type', 'form_submit'),
            'source_system': 'wordpress',
            'external_event_id': self._sid('old'),
            'utm_campaign': 'hn_w3_retention_202606',
            'raw_payload': '{"kept": "for now"}'})
        recent = self.Touchpoint.create({
            'lead_id': lead.id,
            'occurred_at': fields.Datetime.now() - timedelta(days=5),
            'received_at': fields.Datetime.now() - timedelta(days=5),
            'touchpoint_type_id': self.env['health.lookup.value']._default_for('touchpoint_type', 'form_submit'),
            'source_system': 'wordpress',
            'external_event_id': self._sid('recent'),
            'raw_payload': '{"kept": "definitely"}'})

        # (a) the shipped value: a no-op.
        Param.set_param(PARAM_RAW_RETENTION_DAYS, '0')
        self.assertEqual(self.Service._cron_prune_raw_payloads(), 0)
        old.invalidate_recordset()
        self.assertTrue(old.raw_payload, 'an inert cron pruned a payload')
        # Ledger §5.36 — `'0'` is a STRING precisely so the row survives:
        # a falsy value handed to `set_param` UNLINKS it, and a missing
        # parameter is indistinguishable from one nobody ever configured.
        self.assertTrue(Param.search_count(
            [('key', '=', PARAM_RAW_RETENTION_DAYS)]),
            'the shipped value did not keep the parameter row')

        # …and so is anything that is not a positive number.
        for junk in ('', 'false', 'off', 'none', 'not-a-number', '-5'):
            with self.subTest(param=junk):
                Param.set_param(PARAM_RAW_RETENTION_DAYS, junk)
                self.assertEqual(self.Service._cron_prune_raw_payloads(), 0)
        old.invalidate_recordset()
        self.assertTrue(old.raw_payload)

        # (b) switched on.
        Param.set_param(PARAM_RAW_RETENTION_DAYS, '30')
        pruned = self.Service._cron_prune_raw_payloads()
        self.assertGreaterEqual(pruned, 1)
        old.invalidate_recordset()
        recent.invalidate_recordset()
        self.assertFalse(old.raw_payload)
        self.assertTrue(recent.raw_payload,
                        'a row inside the horizon was pruned')

        # The ROW and every other field survive — this prunes a payload, not
        # evidence that the touch happened (binding non-goal).
        self.assertTrue(old.exists())
        self.assertEqual(old.lead_id, lead)
        self.assertEqual(old.touchpoint_type_code, 'form_submit')
        self.assertEqual(old.utm_campaign, 'hn_w3_retention_202606')
        self.assertTrue(old.external_event_id)
        self.assertTrue(old.occurred_at)

        # A second run is idempotent (nothing left inside the horizon).
        self.assertEqual(self.Service._cron_prune_raw_payloads(), 0)

    # ==================================================================
    # T11 — the UTM vocabulary
    # ==================================================================
    def test_w3_11_utm_seeds_are_matched_not_duplicated(self):
        seeds = {'utm_medium_organic': ('utm.medium', 'organic'),
                 'utm_medium_social': ('utm.medium', 'social'),
                 'utm_medium_messaging': ('utm.medium', 'messaging'),
                 'utm_source_tiktok': ('utm.source', 'tiktok')}
        data = self.env['ir.model.data'].sudo()
        for xmlid, (model, name) in seeds.items():
            with self.subTest(seed=xmlid):
                record = self.env.ref('%s.%s' % (MODULE, xmlid),
                                      raise_if_not_found=False)
                self.assertTrue(record, '%s did not load' % xmlid)
                self.assertEqual(record._name, model)
                # Case-INSENSITIVE (ledger §5.50). The seed file's own header
                # says "once these rows exist, marketing owns their names",
                # and `noupdate="1"` two lines below enforces exactly that —
                # so asserting the literal seeded spelling contradicts the
                # contract this same test asserts on the next line. Measured
                # 2026-08-03: `utm_source_tiktok` reads 'TikTok' on vietuat
                # (renamed 03:24:19 by uid 1, outside any phase's code), and
                # the equality was red against a perfectly correct seed.
                # `_utm_ids` matches with `=ilike`, so case is exactly what
                # the production matcher already ignores; what this assertion
                # is really for is catching an xmlid bound to the WRONG
                # channel row, and that still holds.
                self.assertEqual(
                    (record.name or '').lower(), name,
                    '%s resolves to %r, which is not the %r channel'
                    % (xmlid, record.name, name))
                row = data.search([('module', '=', MODULE),
                                   ('name', '=', xmlid)], limit=1)
                self.assertTrue(row.noupdate,
                                '%s must be noupdate — marketing owns the '
                                'name once it exists' % xmlid)

        Medium = self.env['utm.medium']
        Source = self.env['utm.source']

        # The seeded name is MATCHED, case-insensitively, not duplicated.
        organic = self.env.ref('%s.utm_medium_organic' % MODULE)
        before = Medium.search_count([])
        vals = self.Service._utm_ids({'medium': 'Organic'})
        self.assertEqual(vals.get('medium_id'), organic.id)
        self.assertEqual(Medium.search_count([]), before,
                         'a case variant of a seeded medium was created')

        tiktok = self.env.ref('%s.utm_source_tiktok' % MODULE)
        self.assertEqual(
            self.Service._utm_ids({'source': 'TikTok'}).get('source_id'),
            tiktok.id)

        # `cpc` is NOT seeded by this module — it already exists on this
        # database (id 105) and on any database the first `cpc` submission
        # creates it. Either way the invariant that matters is the same: the
        # vocabulary must never end up holding two spellings of one channel,
        # because the funnel would then split it across two columns.
        self.Service._utm_ids({'medium': 'CPC'})
        self.assertEqual(Medium.search_count([('name', '=ilike', 'cpc')]), 1,
                         'the vocabulary now holds two rows for `cpc`')
        # `zalo` is likewise not seeded here (it exists as `Zalo`); assert
        # only that no second spelling appeared, so this holds on a fresh
        # database too (ledger §5.50 — never assert a live row into being).
        self.assertLessEqual(
            Source.search_count([('name', '=ilike', 'zalo')]), 1)

        # Campaigns stay find-only — the seed file must not have smuggled a
        # `utm.campaign` in through the back door (binding non-goal).
        self.assertFalse(
            data.search([('module', '=', MODULE),
                         ('model', '=', 'utm.campaign')]),
            'this module owns a utm.campaign record — find-only means the '
            'register is marketing\'s, not ours')

    # ==================================================================
    # T12 — the catalogue Odoo actually reads (§5.85 / §5.67 / §29)
    # ==================================================================
    @staticmethod
    def _po_body():
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'i18n', 'vi.po')
        with open(path, encoding='utf-8') as handle:
            return handle.read()

    def test_w3_12_po_covers_the_new_surfaces(self):
        """Extends the W2.5 named-msgid pattern. The STRUCTURAL sweep over
        the whole file lives once, in `test_w2_12` — duplicating it here
        would only make the same failure fire twice."""
        body = self._po_body()
        for msgid in (
                'Consent Bridge',
                'Consent record created',
                'Skipped — consent already on file',
                'Skipped — submitter is not the client',
                'Skipped — consent not given',
                'Web form checkbox',
                'Campaign Review',
                'Lead Analysis',
                'Lead Funnel',
                'Unmatched campaign',
                'Link seeded campaigns',
                'Campaigns linked',
                'Nothing to link',
                'unversioned',
                'Only CRM managers and administrators may link campaigns '
                'retroactively.'):
            self.assertIn('msgid "%s"' % msgid, body,
                          'no vi.po entry for %r' % msgid)

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

    def test_w3_12b_new_labels_translate_at_runtime(self):
        from odoo.tools.translate import code_translations

        loaded = code_translations.get_python_translations(MODULE, 'vi_VN')
        self.assertTrue(loaded, 'the python catalogue is inert')
        self.assertNotEqual(
            loaded.get('Campaigns linked'), 'Campaigns linked',
            'the back-fill notification never reached the catalogue')

        field = self.env.ref(
            '%s.field_crm_lead__web_consent_bridged' % MODULE,
            raise_if_not_found=False)
        self.assertTrue(field, 'the field xmlid does not exist — a guessed '
                               'model reference translates nothing (§5.85)')
        self.assertNotEqual(
            field.with_context(lang='vi_VN').field_description,
            field.with_context(lang='en_US').field_description,
            'the field label never reached the database in Vietnamese')
