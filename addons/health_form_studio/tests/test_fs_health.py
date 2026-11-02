# -*- coding: utf-8 -*-
"""FS-H1 overlay tests (handover §5, tests 13–16): the Incident host.

As in the core tests, every test that makes a field rebuilds the touched
models after the transaction is rolled back (the cleanup is registered before
the framework's own, so it runs last).
"""
import os
import re

from lxml import etree

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

MODEL = 'health.incident'


@tagged('post_install', '-at_install')
class TestFsHealth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['fs.studio']
        cls.view = cls.env.ref('health_incident.view_health_incident_form')
        internal = cls.env.ref('base.group_user')
        province = cls.env['health.catchment.province'].search([], limit=1)
        cls.clinic_admin = cls.env['res.users'].create({
            'name': 'FS clinic admin', 'login': 'fs_t14_clinic_admin',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'health_access.group_clinic_admin').id])],
        })
        cls.head_nurse = cls.env['res.users'].create({
            'name': 'FS head nurse', 'login': 'fs_t14_head_nurse',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'health_base.group_healthcare_head_nurse').id])],
        })
        cls.plain = cls.env['res.users'].create({
            'name': 'FS plain login', 'login': 'fs_t15_plain',
            'group_ids': [(6, 0, [internal.id])],
        })

    def setUp(self):
        self.addCleanup(self._fs_rebuild_registry)
        super().setUp()

    def _fs_rebuild_registry(self):
        self.registry._setup_models__(self.cr, [MODEL])

    # T13 --------------------------------------------------------------
    def test_13_parameters_host_and_targets_resolve(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for key in ('biz_form_studio.gate_group', 'biz_form_studio.group_staff',
                    'biz_form_studio.group_admin'):
            xmlid = ICP.get_param(key)
            group = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(group, '%s points at %s, which does not exist'
                            % (key, xmlid))
            self.assertEqual(group._name, 'res.groups')
        self.assertEqual(ICP.get_param('biz_form_studio.gate_group'),
                         'health_access.group_clinic_admin')
        self.assertEqual(ICP.get_param('biz_form_studio.group_staff'),
                         'health_base.group_healthcare_base')
        self.assertTrue(self.env.ref(
            ICP.get_param('biz_form_studio.required_rules_action'),
            raise_if_not_found=False))
        host = self.env['fs.host']._for(MODEL, self.view.id)
        self.assertEqual(host, self.env.ref('health_form_studio.fs_host_incident'))
        self.assertEqual(host._base_view(), self.view)
        self.assertFalse(host.money_ok)
        self.assertFalse(host.sections)
        targets = self.env['fs.link.target'].search([])
        self.assertGreaterEqual(len(targets), 6)
        for target in targets:
            self.assertIn(target.model, self.env,
                          'link target %s is not a model here' % target.model)
        # the incident arch names none of its groups: nothing to declare open
        arch = etree.fromstring(self.view.get_combined_arch())
        self.assertFalse([g for g in arch.iter('group') if g.get('name')
                          and not g.get('name').startswith('fs_')])

    # T14 --------------------------------------------------------------
    def test_14_gate_is_the_clinic_admin(self):
        as_admin = self.Studio.with_user(self.clinic_admin)
        self.assertEqual(as_admin.probe(MODEL, self.view.id),
                         {'host': True, 'can_edit': True})
        data = as_admin.get_studio(MODEL, self.view.id)
        self.assertEqual(data['host']['title'], 'Incident')
        self.assertIn('Counters', [c['title'] for c in data['cards']
                                   if c['kind'] == 'zone'])
        self.assertTrue(data['fields']['state']['locked'])
        name = as_admin.create_field(
            MODEL, {'type': 'char', 'label': 'Gate check'},
            view_id=self.view.id)['name']
        # a database may already carry a published layout of this screen
        before = self.env['fs.layout'].search(
            [('model', '=', MODEL)], limit=1).version
        res = as_admin.publish(MODEL, self.view.id, [{
            'id': 'gate1', 'title': 'Gate', 'anchor': {'kind': 'before_notebook'},
            'fields': [{'name': name, 'order': 0}]}])
        self.assertEqual(res['version'], before + 1)
        layout = self.env['fs.layout'].search([('model', '=', MODEL)])
        # the audit line names the human, not the superuser (sudo keeps uid)
        self.assertEqual(layout.published_by, self.clinic_admin)
        as_nurse = self.Studio.with_user(self.head_nurse)
        self.assertEqual(as_nurse.probe(MODEL, self.view.id),
                         {'host': False, 'can_edit': False})
        with self.assertRaises(AccessError):
            as_nurse.get_studio(MODEL, self.view.id)
        with self.assertRaises(AccessError):
            as_nurse.publish(MODEL, self.view.id, [])

    # T15 --------------------------------------------------------------
    def test_15_end_to_end_on_the_incident(self):
        make = lambda spec: self.Studio.create_field(  # noqa: E731
            MODEL, spec, view_id=self.view.id)['name']
        followup = make({'type': 'selection', 'label': 'Follow-up',
                         'options': ['Phone call', 'Home visit', 'None']})
        informed = make({'type': 'char', 'label': 'Family informed by',
                         'vis': 'staff'})
        duty = make({'type': 'many2one', 'label': 'Nurse on duty',
                     'comodel': 'hr.employee'})
        self.Studio.publish(MODEL, self.view.id, [{
            'id': 'follow', 'title': 'Follow-up',
            'anchor': {'kind': 'before_notebook'},
            'fields': [{'name': n, 'order': i}
                       for i, n in enumerate([followup, informed, duty])]}])
        arch = etree.fromstring(self.view.get_combined_arch())
        group = arch.xpath("//group[@name='fs_follow']")
        self.assertEqual(len(group), 1)
        self.assertEqual([f.get('name') for f in group[0].iter('field')],
                         [followup, informed, duty])
        # it sits above the tabs
        notebook = arch.xpath('//sheet/notebook')[0]
        self.assertIs(group[0].getnext(), notebook)
        employee = self.env['hr.employee'].search([], limit=1)
        option = self.env['ir.model.fields'].search(
            [('model', '=', MODEL), ('name', '=', followup)]
        ).selection_ids.sorted('sequence')[1].value
        incident = self.env[MODEL].create({
            'incident_type': 'other',
            'description': 'Form Studio round trip',
            followup: option,
            informed: 'Daughter, by phone',
            duty: employee.id,
        })
        incident.invalidate_recordset()
        self.assertEqual(incident[followup], option)
        self.assertEqual(incident[informed], 'Daughter, by phone')
        self.assertEqual(incident[duty], employee)
        # "Staff" is the healthcare base group: a login without it never
        # sees the field
        self.assertEqual(self.env[MODEL]._fields[informed].groups,
                         'health_base.group_healthcare_base')
        self.assertNotIn(informed, self.env[MODEL].with_user(
            self.plain).fields_get())
        self.assertIn(informed, self.env[MODEL].with_user(
            self.clinic_admin).fields_get())

    def test_15b_requirement_rule_blocks_deletion(self):
        if 'field.requirement.rule' not in self.env:
            self.skipTest('Field Requirements is not installed')
        name = self.Studio.create_field(
            MODEL, {'type': 'char', 'label': 'Witness phone'},
            view_id=self.view.id)['name']
        field = self.env['ir.model.fields'].search(
            [('model', '=', MODEL), ('name', '=', name)])
        self.env['field.requirement.rule'].create({
            'model_id': field.model_id.id, 'field_id': field.id})
        refs = self.Studio.field_references(MODEL, name)
        self.assertTrue([r for r in refs if r['kind'] == 'requirement'
                         and r['blocker']])

    def test_15c_lock_reasons_read_in_vietnamese(self):
        if not self.env['res.lang']._lang_get('vi_VN'):
            self.skipTest('Vietnamese is not installed')
        host = self.env.ref('health_form_studio.fs_host_incident')
        vi = host.with_context(lang='vi_VN')
        self.assertEqual(vi._fs_text('Drawn by the system.'),
                         'Do hệ thống tạo.')
        self.assertEqual(vi.name, 'Sự cố')

    # T16 --------------------------------------------------------------
    def test_16_sidebar_row_and_catalogues(self):
        item = self.env.ref('health_form_studio.item_admin_form_studio')
        self.assertEqual(item.section_id,
                         self.env.ref('health_cms_sidebar.section_admin'))
        self.assertEqual(set(item.biz_role_ids.ids), {
            self.env.ref('health_access.role_admin').id,
            self.env.ref('health_access.role_owner').id})
        action = self.env.ref(item.action_xmlid)
        self.assertEqual(action.tag, 'biz_form_studio.library')
        self.assertTrue(item.active)
        for module in ('biz_form_studio', 'health_form_studio'):
            path = os.path.join(get_module_path(module), 'i18n', 'vi.po')
            self.assertTrue(os.path.exists(path), '%s has no vi.po' % module)
            text = open(path, encoding='utf-8').read()
            for msgstr in re.findall(r'^msgstr ((?:".*"\n?)+)', text, re.M):
                self.assertNotIn('Odoo', msgstr, module)


@tagged('post_install', '-at_install')
class TestFsHealthOverHttp(HttpCase):
    """T14b — the gate and the dropdown path as a REAL request.

    A test calling the facade `with_user` keeps the superuser as the
    transaction's origin user, which hides one whole class of failure: models
    that refuse sudo commands (`ir.model.fields.selection`) re-run them as
    that origin user. Over HTTP the origin user is the clinic administrator,
    exactly as in the browser — where this was first seen."""

    def setUp(self):
        self.addCleanup(self._fs_rebuild_registry)
        super().setUp()

    def _fs_rebuild_registry(self):
        self.registry._setup_models__(self.cr, [MODEL])

    def test_14b_clinic_admin_makes_a_dropdown_over_http(self):
        internal = self.env.ref('base.group_user')
        province = self.env['health.catchment.province'].search([], limit=1)
        self.env['res.users'].create({
            'name': 'FS http admin', 'login': 'fs_t14b_admin',
            'password': 'fs_t14b_admin_pw',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, [internal.id, self.env.ref(
                'health_access.group_clinic_admin').id])],
        })
        view = self.env.ref('health_incident.view_health_incident_form')
        self.authenticate('fs_t14b_admin', 'fs_t14b_admin_pw')

        def call(method, args, kwargs=None):
            return self.make_jsonrpc_request(
                '/web/dataset/call_kw/fs.studio/%s' % method,
                {'model': 'fs.studio', 'method': method, 'args': args,
                 'kwargs': kwargs or {}})

        res = call('create_field', [MODEL, {
            'type': 'selection', 'label': 'Follow-up',
            'options': ['Phone call', 'Home visit', 'None']}],
            {'view_id': view.id})
        name = res['name']
        field = self.env['ir.model.fields'].search(
            [('model', '=', MODEL), ('name', '=', name)])
        self.assertEqual(len(field.selection_ids), 3)
        opts = [{'value': o.value, 'label': o.name}
                for o in field.selection_ids.sorted('sequence')]
        opts[0]['label'] = 'Phone'
        opts.append({'label': 'Email'})
        call('update_field', [MODEL, name, {'options': opts}])
        field.invalidate_recordset()
        self.assertEqual(sorted(field.selection_ids.mapped('name')),
                         ['Email', 'Home visit', 'None', 'Phone'])
        before = self.env['fs.layout'].search(
            [('model', '=', MODEL)], limit=1).version
        res = call('publish', [MODEL, view.id, [{
            'id': 'http1', 'title': 'Follow-up',
            'anchor': {'kind': 'before_notebook'},
            'fields': [{'name': name, 'order': 0}]}]])
        self.assertEqual(res['version'], before + 1)
        self.assertEqual(call('probe', [MODEL, view.id]),
                         {'host': True, 'can_edit': True})
