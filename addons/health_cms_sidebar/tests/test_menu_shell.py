# -*- coding: utf-8 -*-
"""MENU M1 — the shell: what the server hands it, and what it may not do.

The shell changes HOW the menu is drawn and nothing about what is in it, so
most of what can go wrong is on the page. These tests pin the parts that live
on the server or in the source:

  * T1  the payload's shape is exactly what it was (ADDITIVE keys only, and
        none were needed);
  * T3  Home and Learn exist where the design put them, Learn between
        ANALYTICS and ADMIN, and the Training screens are in Learn;
  * T8  every memory key the shell writes carries the real user id;
  * T9  no stacking-context property anywhere in the shell's stylesheets
        (ledger §5.96 — they sit beside every form field in the product);
  * the deep-link lookup answers only for an entry the person's menu draws;
  * T4/T5/T6 the browser tours (skipped, never passed, without Chrome).
"""

import os
import re

from odoo.tests import HttpCase, TransactionCase, tagged

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS_DIR = os.path.dirname(MODULE_DIR)

SECTION_KEYS = {'id', 'name', 'key', 'icon', 'color', 'items'}
ITEM_KEYS = {'id', 'name', 'icon', 'action_xmlid', 'action_tag',
             'match_action_tags', 'match_action_xmlids', 'match_models',
             'catchment_field', 'children'}

SHELL_STYLESHEETS = (
    os.path.join(MODULE_DIR, 'static', 'src', 'scss', 'cms_sidebar.scss'),
    os.path.join(ADDONS_DIR, 'health_fieldservice', 'static', 'src', 'scss',
                 'ops_sidebar_global.scss'),
)

#: Every property that makes an element a stacking context or a containing
#: block for a `position: fixed` child — the inline dropdown's two failure
#: modes (§5.96). `z-index` is not here: on its own it changes neither.
FORBIDDEN = re.compile(
    r'(^|[;{\s])(transform|filter|backdrop-filter|perspective|contain|'
    r'container-type|container|will-change|isolation)\s*:', re.MULTILINE)
OPACITY = re.compile(r'(^|[;{\s])opacity\s*:\s*([0-9.]+)', re.MULTILINE)


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(line.split('//', 1)[0] if 'url(' not in line else line
                     for line in text.splitlines())


@tagged('post_install', '-at_install')
class TestMenuShellData(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Item = self.env['cms.sidebar.item']

    # ------------------------------------------------------------------ T1
    def test_01_payload_shape_is_unchanged(self):
        """Every section and item carries exactly the keys it always did."""
        data = self.Item.get_sidebar_data()
        self.assertTrue(data, 'the menu came back empty for the superuser')
        for section in data:
            self.assertEqual(set(section), SECTION_KEYS, section.get('key'))
            for item in section['items']:
                self.assertEqual(set(item), ITEM_KEYS, item.get('name'))
                for child in item['children']:
                    self.assertEqual(set(child), ITEM_KEYS, child.get('name'))
                    self.assertEqual(child['children'], [],
                                     'the menu has two levels, never three')

    def test_02_the_model_methods_keep_their_marker(self):
        """F46 — `@api.model` is not inherited; the browser calls these by
        name on the model, so losing the marker empties the menu."""
        for name in ('get_sidebar_data', 'home_action', 'item_id_for_xmlid',
                     'get_match_keys', 'get_catchment_scope'):
            method = getattr(type(self.Item), name)
            self.assertTrue(getattr(method, '_api_model', False)
                            or getattr(method, '_api', None) == 'model',
                            '%s has lost its @api.model marker' % name)

    # ------------------------------------------------------------------ T3
    def test_03_home_is_first_and_never_gated(self):
        home = self.env.ref('health_cms_sidebar.section_home')
        self.assertEqual((home.technical_key, home.sequence), ('home', 0))
        first = self.env['cms.sidebar.section'].search([], limit=1)
        self.assertEqual(first, home, 'Home must be the first section')
        item = self.env.ref('health_cms_sidebar.item_home')
        self.assertEqual(item.action_tag, 'cms_home')
        self.assertFalse(item.action_xmlid)
        self.assertFalse(item.match_action_xmlids,
                         'Home must not claim any dashboard: each belongs to '
                         'its own section\'s Dashboard entry')
        self.assertEqual(item.match_action_tags, 'cms_home')
        if 'biz_role_ids' in item._fields:
            self.assertFalse(item.biz_role_ids | home.biz_role_ids,
                             'Home is never gated')
        keys = [s['key'] for s in self.Item.get_sidebar_data()]
        self.assertEqual(keys[0], 'home')

    def test_04_learn_sits_between_analytics_and_admin(self):
        learn = self.env.ref('health_cms_sidebar.section_learn')
        self.assertEqual((learn.technical_key, learn.sequence), ('learn', 38))
        finance = self.env.ref('health_cms_sidebar.section_finance')
        admin = self.env.ref('health_cms_sidebar.section_admin')
        self.assertLess(finance.sequence, learn.sequence)
        self.assertLess(learn.sequence, admin.sequence)
        analytics = self.env['cms.sidebar.section'].search(
            [('technical_key', '=', 'analytics')], limit=1)
        if analytics:
            self.assertLess(analytics.sequence, learn.sequence,
                            'ANALYTICS must still come straight after FINANCE '
                            'and before Learn')

    def test_05_the_training_screens_are_in_learn(self):
        learn = self.env.ref('health_cms_sidebar.section_learn')
        journey = self.env.ref('health_learn.item_learn_journey',
                               raise_if_not_found=False)
        if journey:
            self.assertEqual(journey.section_id, learn)
            self.assertEqual(journey.sequence, 10)
            self.assertFalse(journey.parent_id)
        heading = self.env.ref('health_access.item_admin_training',
                               raise_if_not_found=False)
        if heading:
            heading = heading.with_context(active_test=False)
            self.assertEqual(heading.section_id, learn)
            kids = self.Item.with_context(active_test=False).search(
                [('parent_id', '=', heading.id)])
            self.assertEqual(len(kids), 5)
            self.assertEqual(set(kids.mapped('section_id')), {learn},
                             'a child in another section than its heading is '
                             'never drawn')

    # ------------------------------------------------------------ deep link
    def test_06_the_tab_lookup_answers_only_for_a_drawn_entry(self):
        item = self.env.ref('health_cms_sidebar.item_home')
        self.assertEqual(self.Item.item_id_for_xmlid(
            'health_cms_sidebar.item_home'), item.id)
        self.assertFalse(self.Item.item_id_for_xmlid('nope'))
        self.assertFalse(self.Item.item_id_for_xmlid('base.user_admin'),
                         'a record of another model is not a menu entry')
        self.assertFalse(self.Item.item_id_for_xmlid(None))
        hidden = self.Item.create({
            'name': 'M1 switched off', 'active': False,
            'section_id': self.env.ref('health_cms_sidebar.section_home').id})
        self.env['ir.model.data'].create({
            'module': 'health_cms_sidebar', 'name': 'm1_switched_off',
            'model': 'cms.sidebar.item', 'res_id': hidden.id})
        self.assertFalse(self.Item.item_id_for_xmlid(
            'health_cms_sidebar.m1_switched_off'),
            'an entry the menu does not draw is not answered for')

    # ------------------------------------------------------------------ T8
    def test_07_every_memory_key_carries_the_real_user_id(self):
        with open(os.path.join(MODULE_DIR, 'static', 'src', 'js',
                               'cms_sidebar.js'), encoding='utf-8') as fh:
            source = fh.read()
        self.assertNotIn('session_info?.uid', source,
                         'session_info.uid is undefined in this build — every '
                         'account on a browser would share one key')
        self.assertNotIn('session_info.uid', source)
        self.assertIn('this.uid = user.userId', source)
        for pattern in (r'`vu\.rail\.mode\.\$\{uid', r'`vu\.tab\.\$\{uid',
                        r'`cms_catchment_\$\{user\.userId'):
            self.assertRegex(source, pattern)

    # ------------------------------------------------------------------ T9
    def test_08_no_containment_on_the_shell(self):
        """The rail, the page header and the wrapper sit beside or around
        every form field in the product (§5.96)."""
        offenders = []
        for path in SHELL_STYLESHEETS:
            with open(path, encoding='utf-8') as fh:
                code = _strip_comments(fh.read())
            for lineno, line in enumerate(code.splitlines(), start=1):
                if FORBIDDEN.search(line):
                    offenders.append('%s:%s: %s' % (
                        os.path.basename(path), lineno, line.strip()))
                for match in OPACITY.finditer(line):
                    if float(match.group(2)) < 1:
                        offenders.append('%s:%s: %s' % (
                            os.path.basename(path), lineno, line.strip()))
        self.assertFalse(offenders, 'a stacking-context property in the shell:'
                                    '\n  ' + '\n  '.join(offenders))

    def test_09_the_wrapper_keeps_its_one_xpath(self):
        """health_fieldservice stays the single owner of `//ActionContainer`
        and the action stays the wrapper's direct child."""
        hits = []
        for module in sorted(os.listdir(ADDONS_DIR)):
            static = os.path.join(ADDONS_DIR, module, 'static')
            if not module.startswith(('health_', 'biz_')) or not os.path.isdir(static):
                continue
            for root, _dirs, files in os.walk(static):
                for name in files:
                    if not name.endswith('.xml'):
                        continue
                    path = os.path.join(root, name)
                    with open(path, encoding='utf-8', errors='ignore') as fh:
                        if '//ActionContainer' in fh.read():
                            hits.append(os.path.relpath(path, ADDONS_DIR))
        self.assertEqual(
            hits, ['health_fieldservice/static/src/xml/ops_webclient_patch.xml'])


@tagged('post_install', '-at_install')
class TestMenuShellTour(HttpCase):
    """T4/T5/T6 in a real browser."""

    def setUp(self):
        super().setUp()
        # A screen the shell keeps (its entry exists, switched off, so its
        # action is in the allowlist) but no drawn entry claims — the "unknown
        # action" of test 5.
        self._probe('m1_probe_unclaimed_action', 'M1 unclaimed',
                    'res.partner.category')
        Item = self.env['cms.sidebar.item'].with_context(active_test=False)
        if not Item.search([('action_xmlid', '=',
                             'health_cms_sidebar.m1_probe_unclaimed_action')]):
            Item.create({
                'name': 'M1 unclaimed (off)', 'active': False,
                'section_id': self.env.ref('health_cms_sidebar.section_admin').id,
                'action_xmlid': 'health_cms_sidebar.m1_probe_unclaimed_action'})
        # A screen nothing names yet — test 4 adds its entry from the page.
        self._probe('m1_probe_new_action', 'M1 new', 'res.country')

    def _probe(self, name, label, model):
        """The probe action, reused if a practice copy already has it."""
        found = self.env.ref('health_cms_sidebar.%s' % name,
                             raise_if_not_found=False)
        if found:
            return found
        action = self.env['ir.actions.act_window'].create(
            {'name': label, 'res_model': model, 'view_mode': 'list,form'})
        self.env['ir.model.data'].create({
            'module': 'health_cms_sidebar', 'name': name,
            'model': 'ir.actions.act_window', 'res_id': action.id})
        return action

    def _owner(self):
        role = self.env.ref('health_access.role_owner', raise_if_not_found=False)
        if not role:
            self.skipTest('no Owner role on this database')
        return self.env['res.users'].create({
            'name': 'M1 Owner', 'login': 'm1tour_owner', 'password': 'm1tour_owner',
            'group_ids': [(6, 0, (role.group_ids
                                  | self.env.ref('base.group_user')).ids)]})

    def test_10_the_shell_as_an_owner(self):
        self._owner()
        self.start_tour('/odoo/action-health_crm.action_crm_dashboard',
                        'cms_menu_shell_tour', login='m1tour_owner')

    def test_11_a_new_entry_keeps_the_shell_without_a_reload(self):
        # The platform administrator (writes menu rows, sees every entry). A
        # user of our own rather than `admin`, whose password on a copy of a
        # live database is not "admin".
        self.env['res.users'].create({
            'name': 'M1 Platform', 'login': 'm1tour_sys', 'password': 'm1tour_sys',
            'group_ids': [(6, 0, (self.env.ref('base.group_system')
                                  | self.env.ref('base.group_user')
                                  | self.env.ref('health_cms_sidebar.group_cms_sidebar_admin')).ids)]})
        self.start_tour('/odoo/action-health_landing.action_admin_dashboard',
                        'cms_menu_allowlist_tour', login='m1tour_sys')
