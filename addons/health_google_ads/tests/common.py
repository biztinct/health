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
import json
import uuid
from unittest.mock import patch

from odoo.tests import TransactionCase

from odoo.addons.health_web_leads.models.web_lead_service import (
    PARAM_FORM_CITY_MAP,
    PARAM_URL_CITY_MAP,
)

from odoo.addons.health_google_ads.services import google_ads_client as gads

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


# ======================================================================
# GA2 — the reporting sign-in
# ======================================================================
# More of the repdigit block, for the same reason: Google does not issue
# these, so no fixture can collide with a real Viet UC advertising customer.
MANAGER_M = '4444444444'
CHILD_C1 = '5555555555'
CHILD_C2 = '6666666666'      # a manager underneath a manager
CHILD_C3 = '7777777777'      # hidden
CHILD_C4 = '8888888888'      # CANCELED, still listed
DIRECT_D = '9999999999'

# Fixture credentials. Deliberately shaped like nothing Google issues, and
# asserted ABSENT from every payload the suites dump (T01/T02).
FIXTURE_CLIENT_ID = 'ga2-fixture-client-id.apps.googleusercontent.com'
FIXTURE_CLIENT_SECRET = 'ga2-fixture-client-secret-nevershipped'
FIXTURE_DEV_TOKEN = 'ga2-fixture-developer-token-nevershipped'
FIXTURE_ACCESS = 'ga2-fixture-access-token'
FIXTURE_REFRESH = 'ga2-fixture-refresh-token'


class FakeResponse:
    """Just enough of a requests.Response for `_error_from_response`."""

    def __init__(self, status_code, body=None, text=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.text = text if text is not None else json.dumps(body or {})
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError('no json')
        return self._body


class FakeGoogle:
    """A stand-in for the three module-level HTTP helpers.

    Patched in with `patch.object(gads, '_http_get', fake.get)` — a PLAIN
    FUNCTION (a bound method here), never `autospec`: ledger §5.76, a second
    autospec patch on an already-patched attribute silently stops binding
    `self`, and these flows re-arm their mocks constantly.

    Every call is recorded, headers included, so a test can assert what
    travelled — which is the only way to prove `login-customer-id` was sent on
    the children call and absent on the direct ones.
    """

    def __init__(self):
        self.calls = []
        self.token_queue = []        # dicts or exceptions, consumed in order
        self.accessible = []
        self.customers = {}          # customer id -> customer dict (REST shape)
        self.children = {}           # manager id -> list of customerClient
        self.search_error = None     # exception raised by the NEXT _search
        self.search_pages = None     # explicit page list, overrides the above

    # -- the three patched primitives ---------------------------------
    def post_form(self, url, data=None, headers=None):
        self.calls.append({'kind': 'form', 'url': url, 'data': dict(data or {}),
                           'headers': dict(headers or {})})
        if not self.token_queue:
            return {'access_token': FIXTURE_ACCESS, 'expires_in': 3600,
                    'refresh_token': FIXTURE_REFRESH,
                    'scope': gads.SCOPE}
        answer = self.token_queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get(self, url, headers=None, params=None):
        self.calls.append({'kind': 'get', 'url': url,
                           'headers': dict(headers or {})})
        if self.search_error is not None:
            error, self.search_error = self.search_error, None
            raise error
        return {'resourceNames': ['customers/%s' % cid
                                  for cid in self.accessible]}

    def post_json(self, url, json_body=None, headers=None):
        body = dict(json_body or {})
        self.calls.append({'kind': 'json', 'url': url, 'body': body,
                           'headers': dict(headers or {})})
        if self.search_error is not None:
            error, self.search_error = self.search_error, None
            raise error
        if self.search_pages is not None:
            page = self.search_pages.pop(0)
            return page
        cid = url.split('/customers/')[1].split('/')[0]
        query = body.get('query') or ''
        if 'FROM customer_client' in query:
            return {'results': [{'customerClient': row}
                                for row in self.children.get(cid, [])]}
        raw = self.customers.get(cid)
        return {'results': [{'customer': raw}] if raw else []}

    # -- fixture helpers ----------------------------------------------
    @staticmethod
    def customer(cid, name='Account', currency='VND',
                 time_zone='Asia/Ho_Chi_Minh', manager=False, status='ENABLED',
                 test_account=False, hidden=False, level='1'):
        """One customer row in Google's own REST spelling (lowerCamelCase)."""
        return {'id': cid, 'descriptiveName': name, 'currencyCode': currency,
                'timeZone': time_zone, 'manager': manager, 'status': status,
                'testAccount': test_account, 'hidden': hidden, 'level': level}


class GoogleAdsGa2Case(GoogleAdsCase):
    """GA1's fixtures plus a platform application and a fake Google."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Config = env['google.ads.platform.config']
        cls.Session = env['google.ads.oauth.session']

        # §5.95 — a human who drove this screen on the deployment leaves an
        # ACTIVE row behind and the partial unique index makes every fixture
        # collide with it. Archived (never deleted) inside the transaction.
        cls.Config.sudo().with_context(active_test=False).search([]).write(
            {'active': False})

        clash = cls.Account.sudo().with_context(active_test=False).search(
            [('customer_id', 'in', [MANAGER_M, CHILD_C1, CHILD_C2, CHILD_C3,
                                    CHILD_C4, DIRECT_D])])
        if clash:
            raise AssertionError(
                'GA2 fixture customer ids are in use by %s'
                % clash.mapped('name'))

        cls.config = cls.Config.create({
            'name': 'GA2 fixture application',
            'client_id': FIXTURE_CLIENT_ID,
        })
        cls.config.action_set_client_secret(FIXTURE_CLIENT_SECRET)
        cls.config.action_set_developer_token(FIXTURE_DEV_TOKEN)

        # An account with NO customer id: the one a first sign-in lands on.
        # (`_assert_no_other_draft` allows exactly one per company, and GA1's
        # own fixtures all carry a customer id.)
        cls.draft = cls.Account.create({
            'name': 'GADS draft', 'company_id': cls.company.id,
        })

    # ------------------------------------------------------------------
    def _fake_google(self, **kwargs):
        """Install a FakeGoogle for the length of this test."""
        fake = FakeGoogle()
        for key, value in kwargs.items():
            setattr(fake, key, value)
        for name, func in (('_http_get', fake.get),
                           ('_http_post_json', fake.post_json),
                           ('_http_post_form', fake.post_form)):
            patcher = patch.object(gads, name, func)
            patcher.start()
            self.addCleanup(patcher.stop)
        return fake

    def _grant(self, account, access=FIXTURE_ACCESS, refresh=FIXTURE_REFRESH,
               expires_in=3600, state='connected'):
        """Give `account` a stored reporting grant, the way a callback would."""
        from datetime import timedelta

        from odoo import fields as odoo_fields
        from odoo.addons.health_care_command_channels.services import (
            channel_crypto,
        )
        vals = {
            'access_token_enc': channel_crypto.encrypt(self.env, access)
            if access else False,
            'refresh_token_enc': channel_crypto.encrypt(self.env, refresh)
            if refresh else False,
            'token_expires_at': (odoo_fields.Datetime.now()
                                 + timedelta(seconds=expires_in))
            if expires_in is not None else False,
            'token_scope': gads.SCOPE,
            'reporting_state': state,
        }
        account._internal().write(vals)
        return account

    def _start_oauth(self, account):
        """Press "Connect Google account" and recover the raw state.

        The state leaves the server exactly once, in the URL — which is
        precisely what a test has to read to play the callback back.
        """
        from urllib.parse import parse_qs, urlparse

        action = account.action_start_reporting_oauth()
        query = parse_qs(urlparse(action['url']).query)
        return action, {k: v[0] for k, v in query.items()}
