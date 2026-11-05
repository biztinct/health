# -*- coding: utf-8 -*-
"""UAT round 6, item 5: a nurse's Messages › "Search conversations" raised
"no 'read' access to User" — core reads each matching staff user (time-off
badge) as the nurse, and the catchment rule hides staff of another area.

Fixed by offering only people the nurse may already see. Both ways:
the search works and lists a same-area colleague; it does not list, and the
nurse still cannot read, a user from another area.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.mail.tools.discuss import Store


@tagged('post_install', '-at_install')
class TestDiscussSearchScope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Province = cls.env['health.catchment.province']
        cls.area_a = Province.create({'name': 'Chat Scope Area A', 'code': 'CSA'})
        cls.area_b = Province.create({'name': 'Chat Scope Area B', 'code': 'CSB'})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        nurse_group = cls.env.ref('health_base.group_healthcare_nurse')
        om_group = cls.env.ref('health_base.group_healthcare_operations_manager')

        def user(name, login, group, area):
            return Users.create({'name': name, 'login': login,
                                 'group_ids': [(6, 0, group.ids)],
                                 'catchment_province_id': area.id})
        cls.nurse = user('Zqchat Nurse A', 'zqchat_nurse_a', nurse_group, cls.area_a)
        cls.colleague = user('Zqchat Colleague A', 'zqchat_om_a', om_group, cls.area_a)
        cls.stranger = user('Zqchat Stranger B', 'zqchat_om_b', om_group, cls.area_b)
        # A staff member on time off is what makes core read the user record.
        for u in (cls.colleague, cls.stranger):
            cls.env['hr.employee'].create({'name': u.name, 'user_id': u.id})

    def _search(self, user, term='Zqchat'):
        store = Store()
        res = self.env['res.partner'].with_user(user)._search_for_channel_invite(
            store, search_term=term, limit=10)
        return res, store.get_result()

    def test_nurse_search_works_and_lists_only_visible_people(self):
        res, _data = self._search(self.nurse)
        found = self.env['res.partner'].browse(res['partner_ids'])
        self.assertIn(self.colleague.partner_id, found)
        self.assertNotIn(self.stranger.partner_id, found)
        self.assertEqual(res['count'], len(found))

    def test_nurse_still_cannot_read_another_areas_user(self):
        with self.assertRaises(AccessError):
            self.stranger.with_user(self.nurse).read(['login'])

    def test_full_search_route_as_nurse(self):
        from odoo.addons.mail.controllers.discuss.search import SearchController
        store = Store()
        env = self.env(user=self.nurse)
        # Same calls as /discuss/search, minus the HTTP request.
        channels = env['discuss.channel'].search([('name', 'ilike', 'Zqchat')])
        store.add(channels)
        env['res.partner']._search_for_channel_invite(store, search_term='Zqchat', limit=10)
        self.assertTrue(store.get_result() is not None)
        self.assertTrue(hasattr(SearchController, 'get_search_store'))
