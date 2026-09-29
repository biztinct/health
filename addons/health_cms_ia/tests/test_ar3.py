# -*- coding: utf-8 -*-
"""ACCESS AR-3 — the M2 follow-ups and the left menu in Vietnamese.

  G1  the Doctor role carries "See the clinic's patients and visits", a
      doctor can open the bookings list (read only, the visits arranged for
      them), and the Bookings tab is on a doctor's menu
  G2  "Google Ads application" is active, carries no role, and is drawn for
      the platform administrator only — not for an Owner or an Admin; the
      Connections tab it sits in is still there for them
  G3  the app the web client opens on sign-in opens Home, and Home lands a
      nurse on Bookings and an accountant on the Finance dashboard;
      provisioning gives a new administrator Home as their home screen
  E2  every area, tab and screen reads Vietnamese for a Vietnamese reader —
      a Doctor's and an Owner's whole menu carries no English label except
      proper nouns; an upgrade of an updatable seed does not wipe it; the
      shell's own words load; a second run writes nothing
"""
from odoo.tests import TransactionCase, tagged
from odoo.tools.convert import convert_file
from odoo.tools.translate import code_translations

from odoo.addons.health_cms_ia import hooks
from odoo.addons.health_cms_ia.menu_vi import (ITEM_VI, PROPER_NOUNS,
                                               SECTION_VI, apply_names_vi)

BOOKINGS = 'health_fieldservice.action_ops_booking_list_native'
FINANCE = 'health_invoicing.action_fin_dashboard'
GOOGLE_ADS_APP = 'health_google_ads.item_google_ads_platform'


def _labels(data):
    """Every label the menu draws: (area, tab, screen) names, flattened."""
    out = []
    for section in data:
        out.append(('area', section['name']))
        for item in section['items']:
            out.append(('tab', item['name']))
            for child in item['children']:
                out.append(('screen', child['name']))
    return out


def _only_proper_nouns(text):
    rest = text
    for noun in sorted(PROPER_NOUNS, key=len, reverse=True):
        rest = rest.replace(noun, '')
    return not any(ch.isalpha() for ch in rest)


@tagged('post_install', '-at_install')
class TestAr3(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Item = cls.env['cms.sidebar.item']
        if not cls.env['res.lang'].search_count(
                [('code', '=', 'vi_VN'), ('active', '=', True)]):
            cls.env['res.lang']._activate_lang('vi_VN')
        # The install hook / migration's own writers, so this runs the same
        # on a fresh test database and on a copy of the live one.
        hooks.apply_followups(cls.env, {k: [] for k in (
            'gates', 'narrowed', 'names_vi')})
        apply_names_vi(cls.env)

    def _person(self, login, *role_xmlids, lang='en_US', extra=()):
        groups = self.env.ref('base.group_user')
        for xmlid in role_xmlids:
            role = self.env.ref(xmlid, raise_if_not_found=False)
            if not role:
                self.skipTest('%s is not on this database' % xmlid)
            groups |= role.group_ids
        for xmlid in extra:
            groups |= self.env.ref(xmlid)
        return self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': login, 'login': '%s@ar3.example.test' % login,
                'lang': lang, 'group_ids': [(6, 0, groups.ids)]})

    def _menu(self, user, lang=None):
        return self.Item.with_user(user).with_context(
            lang=lang or user.lang).sudo().get_sidebar_data()

    @staticmethod
    def _screens(data):
        return {n.get('action_xmlid') for s in data for i in s['items']
                for n in [i] + list(i['children'])}

    # ------------------------------------------------------------------ G1
    def test_g1_a_doctor_opens_bookings(self):
        from odoo.addons.health_access.hooks import role_can_read
        doctor_role = self.env.ref(hooks.DOCTOR)
        keys = doctor_role.ability_ids.mapped('technical_key')
        self.assertIn('care-base', keys)
        self.assertTrue(role_can_read(self.env, doctor_role,
                                      'health.fieldservice.order'))
        bookings = self.env.ref('health_cms_sidebar.item_ops_bookings')
        self.assertIn(doctor_role, bookings.biz_role_ids)
        doctor = self._person('ar3doc', hooks.DOCTOR)
        data = self._menu(doctor)
        self.assertIn(BOOKINGS, self._screens(data))
        ops = [s for s in data if s['key'] == 'ops']
        self.assertTrue(ops)
        self.assertIn('Bookings', [i['name'] for i in ops[0]['items']])
        # Read only: a doctor who is not also a nurse cannot change a booking.
        Order = self.env['health.fieldservice.order'].with_user(doctor)
        self.assertTrue(Order.has_access('read'))
        self.assertFalse(Order.has_access('write'))
        self.assertFalse(Order.has_access('create'))
        # Home is unchanged for a doctor: Observations.
        self.assertEqual(self.Item.with_user(doctor).home_action(),
                         'health_vitals.action_health_observation')

    # ------------------------------------------------------------------ G2
    def test_g2_google_ads_application_is_the_platforms_alone(self):
        item = self.env.ref(GOOGLE_ADS_APP, raise_if_not_found=False)
        if not item:
            self.skipTest('the advertising module is not on this database')
        self.assertTrue(item.active)
        self.assertFalse(item.biz_role_ids)
        self.assertIn(item.id, self.Item._platform_only_ids())
        owner = self._person('ar3own', hooks.OWNER)
        admin = self._person('ar3adm', hooks.ADMIN)
        system = self._person('ar3sys', extra=('base.group_system',))
        action = item.action_xmlid
        for who in (owner, admin):
            data = self._menu(who)
            self.assertNotIn(action, self._screens(data),
                             '%s sees the Google Ads application' % who.login)
        self.assertIn(action, self._screens(self._menu(system)))
        # The Connections tab is still there for the Owner.
        owner_tabs = {i['name'] for s in self._menu(owner) for i in s['items']}
        self.assertIn('Connections', owner_tabs)
        # And the Screens lens says the same thing the menu does.
        from odoo.addons.health_access.models.cms_sidebar import HealthCmsRail
        vis = HealthCmsRail().visibility_for(self.env, owner)
        self.assertEqual(vis['items'].get(item.id), 'hidden')

    # ------------------------------------------------------------------ G3
    def test_g3_sign_in_lands_on_home(self):
        root = self.env.ref('health_cms_sidebar.menu_cms_root')
        home = self.env.ref('health_cms_sidebar.action_cms_home')
        self.assertEqual(root.action, home)
        self.assertEqual(home.tag, 'cms_home')
        nurse = self._person('ar3nurse', hooks.NURSE)
        accountant = self._person('ar3acct', hooks.ACCOUNTANT)
        self.assertEqual(self.Item.with_user(nurse).home_action(), BOOKINGS)
        self.assertEqual(self.Item.with_user(accountant).home_action(),
                         FINANCE)
        try:
            from odoo.addons.biz_tenants.models import tenants_common
        except ImportError:
            return
        self.assertEqual(tenants_common.home_action(),
                         'health_cms_sidebar.action_cms_home')

    # ------------------------------------------------------------------ E2
    def test_e2_every_table_row_reads_vietnamese(self):
        wrong = []
        for table, model in ((SECTION_VI, 'cms.sidebar.section'),
                             (ITEM_VI, 'cms.sidebar.item')):
            for xmlid, name in table.items():
                rec = self.env.ref(xmlid, raise_if_not_found=False)
                if not rec:
                    continue
                got = rec.with_context(lang='vi_VN', active_test=False).name
                if got != name:
                    wrong.append('%s: %r' % (xmlid, got))
        self.assertFalse(wrong, 'not in Vietnamese:\n  ' + '\n  '.join(wrong))

    def test_e2b_every_menu_row_is_in_the_table(self):
        """A row on the menu that the table does not name would stay English
        for a Vietnamese reader."""
        missing = []
        for model, table in (('cms.sidebar.item', ITEM_VI),
                             ('cms.sidebar.section', SECTION_VI)):
            for rec in self.env[model].sudo().with_context(
                    active_test=False).search([]):
                xmlid = rec.get_external_id().get(rec.id)
                if xmlid and xmlid not in table and not xmlid.startswith(
                        '__'):
                    missing.append(xmlid)
        self.assertFalse(missing, 'menu rows with no Vietnamese name: %s'
                         % missing)

    def test_e2c_a_vietnamese_menu_has_no_english_label(self):
        for login, roles in (('ar3docvi', (hooks.DOCTOR,)),
                             ('ar3ownvi', (hooks.OWNER,)),
                             ('ar3nursevi', (hooks.NURSE,))):
            user = self._person(login, *roles, lang='vi_VN')
            en = _labels(self._menu(user, lang='en_US'))
            vi = _labels(self._menu(user, lang='vi_VN'))
            self.assertEqual(len(en), len(vi))
            english = [e for (kind, e), (_k, v) in zip(en, vi)
                       if e == v and not _only_proper_nouns(v)]
            self.assertFalse(english, '%s still reads English: %s'
                             % (login, english))

    def test_e2d_an_upgrade_of_a_seed_keeps_the_vietnamese(self):
        """The phone rows are an UPDATABLE seed: re-loading it (a real
        upgrade, in this transaction) must not wipe the Vietnamese."""
        if not self.env['ir.module.module'].search_count(
                [('name', '=', 'health_care_command_voip'),
                 ('state', '=', 'installed')]):
            self.skipTest('the phone bridge is not on this database')
        xmlid = 'health_care_command_voip.item_phone_calls'
        before = self.env.ref(xmlid).with_context(lang='vi_VN').name
        convert_file(self.env, 'health_care_command_voip',
                     'data/cms_sidebar_items_phone.xml', {}, mode='update',
                     noupdate=False)
        self.env.invalidate_all()
        self.assertEqual(self.env.ref(xmlid).with_context(lang='vi_VN').name,
                         before)
        self.assertEqual(before, ITEM_VI[xmlid])

    def test_e2e_a_second_run_writes_nothing(self):
        self.assertEqual(apply_names_vi(self.env), 0)
        log = hooks.consolidate_ia(self.env)
        for key in ('names_vi', 'gates', 'doctor_roles', 'doctor_people'):
            self.assertFalse(log.get(key), '%s on a second run: %s'
                             % (key, log.get(key)))

    def test_e2f_the_shell_words_load(self):
        web = code_translations.get_web_translations('health_cms_sidebar',
                                                     'vi_VN')
        strings = {m['id']: m['string'] for m in web['messages']}
        for source in ('Keep the menu open', 'Show icons only',
                       'My area (%s)', 'Home', 'Catchment Area',
                       'You are here', 'All areas'):
            self.assertIn(source, strings, source)
            self.assertNotEqual(strings[source], source, source)
