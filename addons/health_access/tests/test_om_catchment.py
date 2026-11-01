from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from ..hooks import FRESH_ROLE_ABILITIES, scope_operations_managers


@tagged('post_install', '-at_install')
class TestOperationsManagerCatchment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role = cls.env.ref('health_access.role_operations_manager')
        cls.owner_group = cls.env.ref('health_base.group_healthcare_owner')
        cls.areas = cls.env['health.catchment.province'].create([
            {'name': 'OM test A', 'code': 'OMA'},
            {'name': 'OM test B', 'code': 'OMB'},
        ])
        cls.managers = cls.env['res.users'].with_context(no_reset_password=True).create([
            {'name': 'OM scope A', 'login': 'om.scope.a.test',
             'job_role_id': cls.role.id, 'catchment_province_id': cls.areas[0].id},
            {'name': 'OM scope B', 'login': 'om.scope.b.test',
             'job_role_id': cls.role.id, 'catchment_province_id': cls.areas[1].id},
        ])
        cls.patients = cls.env['res.partner'].create([
            {'name': 'OM test patient A', 'is_patient': True,
             'catchment_province_id': cls.areas[0].id},
            {'name': 'OM test patient B', 'is_patient': True,
             'catchment_province_id': cls.areas[1].id},
        ])

    def test_role_never_grants_owner_bypass(self):
        self.assertNotIn('ownership', FRESH_ROLE_ABILITIES['Operations Manager'])
        self.assertNotIn(self.owner_group, self.role.group_ids)
        for manager in self.managers:
            self.assertTrue(manager.catchment_enforced)
            self.assertFalse(manager.has_group('health_base.group_healthcare_owner'))

    def test_both_directions_search_read_and_write(self):
        for index, manager in enumerate(self.managers):
            own, other = self.patients[index], self.patients[1 - index]
            visible = self.patients.with_user(manager).search([
                ('id', 'in', self.patients.ids)])
            self.assertEqual(visible.ids, own.ids)
            own.with_user(manager).read(['name'])
            own.with_user(manager).write({'comment': 'OM scope allowed'})
            with self.assertRaises(AccessError):
                other.with_user(manager).read(['name'])
            with self.assertRaises(AccessError):
                other.with_user(manager).write({'comment': 'must not be written'})
            self.assertEqual(self.areas.with_user(manager).search([
                ('id', 'in', self.areas.ids)]).ids, self.areas[index].ids)

    def test_missing_area_cannot_see_other_areas(self):
        manager = self.managers[0]
        manager.catchment_province_id = False
        self.assertFalse(self.patients.with_user(manager).search([
            ('id', 'in', self.patients.ids)]))
        self.assertFalse(self.areas.with_user(manager).search([]))

    def test_operations_dashboard_roster_obeys_catchment(self):
        employees = self.env['hr.employee'].create([
            {'name': 'OM dashboard A', 'is_healthcare_staff': True,
             'employment_status': 'active', 'staff_catchment_province_id': self.areas[0].id},
            {'name': 'OM dashboard B', 'is_healthcare_staff': True,
             'employment_status': 'active', 'staff_catchment_province_id': self.areas[1].id},
        ])
        for index, manager in enumerate(self.managers):
            dashboard = self.env['health.fieldservice.order'].with_user(manager).get_ops_dashboard_data(
                '2099-01-01', '2099-01-01')
            staff_ids = {row['id'] for row in dashboard['staff']}
            self.assertIn(employees[index].id, staff_ids)
            self.assertNotIn(employees[1 - index].id, staff_ids)

    def test_migration_repairs_legacy_om_and_preserves_owner(self):
        owner = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'OM test genuine owner', 'login': 'om.test.owner',
            'job_role_id': self.env.ref('health_access.role_owner').id,
        })
        ownership = self.env['biz.access.ability'].search([
            ('technical_key', '=', 'ownership')], limit=1)
        self.role.write({'ability_ids': [(4, ownership.id)]})
        self.managers.write({'group_ids': [(4, self.owner_group.id)]})
        before = {u.id: set(u.group_ids.ids) for u in self.managers}
        scope_operations_managers(self.env)
        for manager in self.managers:
            self.assertEqual(set(manager.group_ids.ids), before[manager.id] - {self.owner_group.id})
            self.assertTrue(manager.catchment_enforced)
        self.assertTrue(owner.has_group('health_base.group_healthcare_owner'))
        self.assertFalse(owner.catchment_enforced)
        self.assertEqual(len(self.patients.with_user(owner).search([
            ('id', 'in', self.patients.ids)])), 2)
        self.assertEqual(scope_operations_managers(self.env), 0)
