# -*- coding: utf-8 -*-
"""Shared fixtures for the GA1 suites.

TransactionCase ONLY — this module ships no HttpCase on purpose (ledger
§5.32: an HttpCase runs on a separate cursor and its side effects have
poisoned later TransactionCase suites in the same run).

Every identity this fixture claims is proven to match NOTHING live before it
is used (the `_free_phones` pattern from health_web_leads): the master
database carries a real lead book, and a fixture phone that happens to belong
to somebody would silently turn a "created" into a "merged".
"""
import uuid

from odoo.tests import TransactionCase

from odoo.addons.health_web_leads.models.web_lead_service import (
    PARAM_FORM_CITY_MAP,
    PARAM_URL_CITY_MAP,
)

# Ten digits, and provably not a real Viet UC advertising customer: they are
# the repdigit block, which Google does not issue.
CUSTOMER_A1 = '1111111111'
CUSTOMER_A2 = '2222222222'
CUSTOMER_B1 = '3333333333'

# A 19-digit campaign id — comfortably past 2**53, which is the whole point
# (rail R3: no `int()` anywhere in the chain).
BIG_CAMPAIGN_ID = '1234567890123456789'
OTHER_CAMPAIGN_ID = '9876543210987654321'


class GoogleAdsCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Account = env['google.ads.account']
        cls.Campaign = env['google.ads.campaign']
        cls.Service = env['web.lead.service']
        cls.Lead = env['crm.lead']
        cls.Touchpoint = env['health.lead.touchpoint']
        cls.Conn = env['care.channel.connection']

        cls.company = env.company
        cls.company2 = env['res.company'].create({'name': 'GADS Other Co'})
        cls.province = env['health.catchment.province'].search([], limit=1) \
            or env['health.catchment.province'].create({'name': 'GADS Prov'})

        # The Channel Center's fixture trap, inherited (ledger §5.95): a
        # human driving the Center on the deployment leaves ACTIVE connection
        # and platform-app rows behind, and the partial unique indexes make
        # every later fixture collide with them. Archived (never deleted)
        # inside the test transaction, so it rolls back with the class.
        env['care.channel.connection'].sudo().with_context(
            active_test=False).search([]).write({'active': False})
        env['channel.platform.app'].sudo().with_context(
            active_test=False).search([]).write({'active': False})

        # The customer-id unique index is DATABASE-WIDE and ignores `active`,
        # so a real account carrying one of the fixture ids would break every
        # create below. Assert the block is free rather than hope.
        clash = cls.Account.sudo().with_context(active_test=False).search(
            [('customer_id', 'in',
              [CUSTOMER_A1, CUSTOMER_A2, CUSTOMER_B1])])
        if clash:
            raise AssertionError(
                'fixture customer ids are in use by %s' % clash.mapped('name'))

        cls.crm_user = cls._mk_user(
            'gads_user', ['health_crm.group_health_crm_user'])
        cls.operator = cls._mk_user(
            'gads_mgr', ['health_crm.group_health_crm_manager'])
        cls.operator2 = cls._mk_user(
            'gads_mgr2', ['health_crm.group_health_crm_manager'],
            company=cls.company2)

        # The runner is the superuser, which is a member of NO group
        # (has_group checks real membership, not su — ledger §5.42), and the
        # Center's own gate calls has_group. Grant what the gates ask for.
        env.user.sudo().write({'group_ids': [
            (4, env.ref('health_crm.group_health_crm_manager').id),
            (4, env.ref('base.group_system').id)]})

        cls.connector = cls._connector_for(cls.company)

        cls.account_a1 = cls.Account.create({
            'name': 'GADS A1', 'company_id': cls.company.id,
            'customer_id': CUSTOMER_A1,
            'website_connector_id': cls.connector.id if cls.connector else False,
        })
        cls.account_a2 = cls.Account.create({
            'name': 'GADS A2', 'company_id': cls.company.id,
            'customer_id': CUSTOMER_A2,
        })
        cls.account_b1 = cls.Account.create({
            'name': 'GADS B1', 'company_id': cls.company2.id,
            'customer_id': CUSTOMER_B1,
        })

        cls.phones = cls._free_phones(10)

        Param = env['ir.config_parameter'].sudo()
        Param.set_param(PARAM_FORM_CITY_MAP, '{"15838": "HN", "15670": "HCM"}')
        Param.set_param(PARAM_URL_CITY_MAP, '{"/lien-he-hanoi/": "HN"}')

    # ------------------------------------------------------------------
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

    @classmethod
    def _connector_for(cls, company):
        """Adopt the deployment's connector when it has one, else make a
        throwaway. Never edits a live row (ledger §5.95)."""
        Connector = cls.env['web.leads.connector'].sudo()
        existing = Connector.search([('company_id', '=', company.id)], limit=1)
        if existing:
            return existing
        return Connector.create({'name': 'GADS test connector',
                                 'company_id': company.id})

    @classmethod
    def _free_phones(cls, count):
        """`count` valid VN mobile numbers that match no lead and no partner."""
        Lead = cls.env['crm.lead']
        Partner = cls.env['res.partner']
        found = []
        for offset in range(0, 4000):
            candidate = '09%08d' % (79000000 + offset)
            if Lead.with_context(active_test=False).search_count(
                    [('phone', '=', candidate)]):
                continue
            if Partner.with_context(active_test=False).search_count(
                    [('phone', 'ilike', candidate[-9:])]):
                continue
            found.append(candidate)
            if len(found) == count:
                return found
        raise AssertionError('no free fixture phone numbers available')

    # ------------------------------------------------------------------
    def _payload(self, index=0, **overrides):
        payload = {
            'submission_id': uuid.uuid4().hex,
            'form_id': '15838',
            'submitted_at': '2026-09-15T09:30:00+07:00',
            'name': 'Nguyễn Văn GA%s' % index,
            'phone': self.phones[index],
            'message': 'Cần tư vấn.',
            'location': 'Hà Nội',
            'page_url': 'https://pkgdvietuc.com/lien-he-hanoi/',
            'anti_spam': {'honeypot_filled': False, 'token_ok': True},
        }
        payload.update(overrides)
        return payload

    def _google_payload(self, index=0, **overrides):
        payload = self._payload(index)
        payload.update({
            'utm': {'source': 'google', 'medium': 'cpc',
                    'campaign': 'gads-test'},
            'click_ids': {'gclid': 'EAIaGA1test'},
            'google_ads': {'customer_id': CUSTOMER_A1,
                           'campaign_id': BIG_CAMPAIGN_ID},
        })
        payload.update(overrides)
        return payload

    def _lead_of(self, result):
        self.assertTrue(result.get('_lead_id'), 'result carries no lead id')
        return self.Lead.browse(result['_lead_id'])

    def _newest_touch(self, lead):
        return self.Touchpoint.search(
            [('lead_id', '=', lead.id)],
            order='occurred_at desc, id desc', limit=1)
