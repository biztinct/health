# -*- coding: utf-8 -*-
"""Overlay tests: the Incident host (FS-H1, tests 13–16), the Client and
Contact Workspace hosts (FS-H2, tests 23 for the Incident payload, 28–32), and
the Booking host and the four lists (FS-H3, tests 45–48), and health
information reach — exports, analytics, the nurse app, encryption on the
Client record (FS-H4, tests 60–64), and the nurse app's version and
service-worker language (FS-H5, tests 72–73).

As in the core tests, every test that makes a field rebuilds the touched
models after the transaction is rolled back (the cleanup is registered before
the framework's own, so it runs last).
"""
import json
import logging
import os
import re
import time

from lxml import etree

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

_logger = logging.getLogger(__name__)

MODEL = 'health.incident'
CLIENT_VIEW = 'health_fieldservice.view_health_patient_form_ops'
CONTACT_VIEW = 'health_crm.view_crm_contact_form_crm_center'
BOOKING = 'health.fieldservice.order'
BOOKING_VIEW = 'health_fieldservice.view_health_fso_form_ops'
BOOKING_LEGACY_VIEW = 'health_fieldservice.view_health_fieldservice_order_form'
TOUCHED = (MODEL, 'res.partner', 'crm.lead', BOOKING)

#: host xmlid -> (list view xmlid, the column new columns go after)
LISTS = {
    'health_form_studio.fs_host_booking':
        ('health_fieldservice.view_health_fso_list_ops', 'priority'),
    'health_form_studio.fs_host_client':
        ('health_fieldservice.view_health_client_list_ops', 'total_assignments'),
    'health_form_studio.fs_host_contact':
        ('health_crm.view_crm_contact_list_crm_center', 'user_id'),
    'health_form_studio.fs_host_incident':
        ('health_incident.view_health_incident_list', 'open_action_count'),
}

#: the Booking's open cards, in pack order
BOOKING_CARDS = ['visit_card', 'location_details_card', 'care_team_card',
                 'commission_fees_card', 'additional_charges_card']


def _owner_groups(env):
    """The Owner role's permissions (the persona that opens every Workspace
    screen on this product — ledger §5.277)."""
    role = env.ref('health_access.role_owner')
    return (role.group_ids | env.ref('base.group_user')).ids


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
        self.registry._setup_models__(self.cr, list(TOUCHED))

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
        self.registry._setup_models__(self.cr, list(TOUCHED))

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


# =========================================================================
#  FS-H2 — the Client and Contact records (Workspace forms)
# =========================================================================
def _pack_xpath(host):
    return "//page[@name='%s']/div[hasclass('ws-pack')]" % host.pack_page


@tagged('post_install', '-at_install')
class TestFsWorkspaceHosts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['fs.studio']
        cls.client_view = cls.env.ref(CLIENT_VIEW)
        cls.contact_view = cls.env.ref(CONTACT_VIEW)
        cls.client_host = cls.env.ref('health_form_studio.fs_host_client')
        cls.contact_host = cls.env.ref('health_form_studio.fs_host_contact')
        internal = cls.env.ref('base.group_user')
        province = cls.env['health.catchment.province'].search([], limit=1)
        cls.province = province
        cls.clinic_admin = cls.env['res.users'].create({
            'name': 'FS2 clinic admin', 'login': 'fs2_clinic_admin',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'health_access.group_clinic_admin').id])],
        })
        # The Admin role reads no contacts at all on this product (crm.lead
        # is Owner / sales only), so Studio on the Contact record is for a
        # clinic administrator who also works contacts — the Owner role's
        # pair, made here from its two groups.
        cls.crm_admin = cls.env['res.users'].create({
            'name': 'FS2 clinic admin with contacts', 'login': 'fs2_crm_admin',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'health_access.group_clinic_admin').id, cls.env.ref(
                'sales_team.group_sale_salesman_all_leads').id])],
        })
        cls.staff = cls.env['res.users'].create({
            'name': 'FS2 staff', 'login': 'fs2_staff',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, [internal.id, cls.env.ref(
                'health_base.group_healthcare_base').id])],
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'FS2 outsider', 'login': 'fs2_outsider',
            'group_ids': [(6, 0, [internal.id])],
        })

    def setUp(self):
        self.addCleanup(self._fs_rebuild_registry)
        super().setUp()

    def _fs_rebuild_registry(self):
        self.registry._setup_models__(self.cr, list(TOUCHED))

    def combined(self, view, lang=None):
        if lang:
            view = view.with_context(lang=lang)
        return etree.fromstring(view.get_combined_arch())

    def layout(self, view):
        return self.env['fs.layout'].search([('base_view_id', '=', view.id)])

    # T23 (the Incident half) ------------------------------------------
    def test_23_incident_payload_keeps_every_field_it_draws(self):
        """T23 — the leaner payload still holds every standard field the
        Incident schematic lists, and nothing it does not."""
        view = self.env.ref('health_incident.view_health_incident_form')
        data = self.Studio.get_studio(MODEL, view.id)
        shown = {n for c in data['cards'] for n in c.get('fields') or []}
        self.assertTrue(shown)
        std = {n for n, f in data['fields'].items() if f['std']}
        self.assertEqual(std, shown)
        self.assertIn('state', data['fields'])
        self.assertTrue(data['fields']['state']['locked'])

    # T28 --------------------------------------------------------------
    def test_28_both_hosts_resolve_against_todays_forms(self):
        from odoo.addons.health_form_studio.models.fs_host import HOST_TEXT
        for host, view in ((self.client_host, self.client_view),
                           (self.contact_host, self.contact_view)):
            self.assertEqual(host._base_view(), view)
            self.assertEqual(self.env['fs.host']._for(host.model, view.id), host)
            self.assertEqual(host.kit, 'ws')
            arch = self.combined(view)
            self.assertEqual(len(arch.xpath(_pack_xpath(host))), 1,
                             '%s: the pack moved' % host.name)
            for card in host.sections:
                self.assertEqual(
                    len(arch.xpath("%s/div[@name='%s']"
                                   % (_pack_xpath(host), card['name']))), 1,
                    '%s: open card %s is not in the pack'
                    % (host.name, card['name']))
            Model = self.env[host.model]
            for name, reason in host.locked_fields.items():
                self.assertIn(name, Model._fields, '%s: locked field %s'
                              % (host.name, name))
                self.assertIn(reason, HOST_TEXT, reason)
            for zone in host.locked_zones:
                self.assertTrue(arch.xpath("//*[@name='%s']" % zone['name']),
                                '%s: zone %s' % (host.name, zone['name']))
                self.assertIn(zone['title'], HOST_TEXT)
                self.assertIn(zone['reason'], HOST_TEXT)
        self.assertEqual(self.client_host.pack_tail, 'ws_client_visits')
        self.assertEqual(len(self.combined(self.client_view).xpath(
            "%s/widget[@name='ws_client_visits']"
            % _pack_xpath(self.client_host))), 1)
        self.assertFalse(self.contact_host.pack_tail)
        self.assertFalse(self.contact_host.pwa_label)
        self.assertEqual(self.client_host.pwa_label, 'Nurse app')
        # the base partner form is NOT a host
        self.assertFalse(self.env['fs.host']._for(
            'res.partner', self.env.ref('base.view_partner_form').id))
        if self.env['res.lang']._lang_get('vi_VN'):
            vi = self.client_host.with_context(lang='vi_VN')
            self.assertEqual(vi._fs_text('Stored encrypted by the system.'),
                             'Hệ thống lưu ở dạng mã hóa.')
            self.assertEqual(vi.name, 'Khách hàng')
            self.assertEqual(self.contact_host.with_context(
                lang='vi_VN')._fs_text('Contact history'), 'Lịch sử liên hệ')

    # T29 --------------------------------------------------------------
    def test_29_end_to_end_on_the_client(self):
        as_admin = self.Studio.with_user(self.clinic_admin)
        view = self.client_view
        self.assertEqual(as_admin.probe('res.partner', view.id),
                         {'host': True, 'can_edit': True})
        note = as_admin.create_field('res.partner', {
            'type': 'char', 'label': 'Gate code', 'vis': 'staff'},
            view_id=view.id)['name']
        slot = as_admin.create_field('res.partner', {
            'type': 'selection', 'label': 'Preferred time slot',
            'options': [{'label': 'Morning', 'label_vi': 'Buổi sáng'},
                        {'label': 'Afternoon'}, {'label': 'Evening'}]},
            view_id=view.id)['name']
        lift = as_admin.create_field('res.partner', {
            'type': 'boolean', 'label': 'Lift access'}, view_id=view.id)['name']
        v1 = [{'id': 'care1', 'title': 'Care preferences',
               'title_vi': 'Ưu tiên chăm sóc', 'anchor': {'kind': 'pack_end'},
               'fields': [{'name': slot, 'order': 0},
                          {'name': note, 'order': 1}]},
              {'id': 'ident1', 'title': '',
               'anchor': {'kind': 'card', 'name': 'identity_card'},
               'fields': [{'name': lift, 'order': 0}]}]
        res = as_admin.publish('res.partner', view.id, v1)
        layout = self.layout(view)
        self.assertEqual(layout.published_by, self.clinic_admin)
        pack = self.combined(view).xpath(_pack_xpath(self.client_host))[0]
        names = [c.get('name') for c in pack]
        # at the end of the pack, before "Recent visits"
        self.assertEqual(names[-2:], ['fs_care1', 'ws_client_visits'])
        card = pack[-2]
        self.assertEqual(card.get('data-fs-fields'), '%s,%s' % (slot, note))
        self.assertEqual(card.get('data-fs-fold'), '1')
        identity = pack.xpath("./div[@name='identity_card']")[0]
        self.assertEqual(identity.get('data-fs-fields'), lift)
        self.assertIn(lift, [f.get('name') for f in identity.iter('field')])
        if self.env['res.lang']._lang_get('vi_VN'):
            vi = self.combined(view, 'vi_VN').xpath(
                "//div[@name='fs_care1']/div[@class='vu-card__title']/div")[-1]
            self.assertEqual(vi.text, 'Ưu tiên chăm sóc')
        # "Staff" is enforced by the server
        field = self.env['res.partner']._fields[note]
        self.assertEqual(field.groups, 'health_base.group_healthcare_base')
        self.env['res.partner'].with_user(self.staff)._check_field_access(
            field, 'read')
        self.assertIn(note, self.env['res.partner'].with_user(
            self.staff).fields_get([note]))
        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(
                self.outsider)._check_field_access(field, 'read')
        self.assertNotIn(note, self.env['res.partner'].with_user(
            self.outsider).fields_get())
        # a second version moves the text field into Identity; going back
        # to version 1 draws version 1 again
        v2 = [dict(v1[0], fields=[{'name': slot, 'order': 0}]),
              dict(v1[1], fields=[{'name': lift, 'order': 0},
                                  {'name': note, 'order': 1}])]
        as_admin.publish('res.partner', view.id, v2)
        back = as_admin.rollback(layout.id, res['version'])
        hist = {h.version: h for h in self.env['fs.layout.history'].search(
            [('layout_id', '=', layout.id)])}
        self.assertEqual(hist[back['version']].arch, hist[res['version']].arch)
        self.assertEqual(layout.view_id.arch_db.strip(),
                         hist[res['version']].arch.strip())
        # the base partner form is untouched
        self.assertFalse(self.combined(self.env.ref(
            'base.view_partner_form')).xpath("//*[@name='fs_care1']"))

    # T30 --------------------------------------------------------------
    def test_30_timing_on_the_client(self):
        """T30 — logged, not asserted: the cost of a field and of a publish
        on the largest record type, in this process (the two-worker numbers
        are measured over HTTP on the rehearsal database)."""
        view = self.client_view
        t0 = time.perf_counter()
        name = self.Studio.create_field('res.partner', {
            'type': 'char', 'label': 'Timing probe'}, view_id=view.id)['name']
        t1 = time.perf_counter()
        self.env['res.partner'].fields_get([name])
        t2 = time.perf_counter()
        self.Studio.publish('res.partner', view.id, [{
            'id': 'time1', 'title': 'Timing', 'anchor': {'kind': 'pack_end'},
            'fields': [{'name': name, 'order': 0}]}])
        t3 = time.perf_counter()
        self.env['res.partner'].fields_get([name])
        self.env['res.partner'].get_views([(view.id, 'form')])
        t4 = time.perf_counter()
        _logger.info(
            "FS-H2 T30 timing res.partner: create_field %.2fs, first "
            "fields_get %.2fs, publish %.2fs, first fields_get+get_views "
            "%.2fs", t1 - t0, t2 - t1, t3 - t2, t4 - t3)

    # T31 --------------------------------------------------------------
    def test_31_end_to_end_on_the_contact(self):
        # a clinic administrator who reads no contacts gets no Studio there
        self.assertEqual(self.Studio.with_user(self.clinic_admin).probe(
            'crm.lead', self.contact_view.id), {'host': False, 'can_edit': False})
        as_admin = self.Studio.with_user(self.crm_admin)
        view = self.contact_view
        self.assertEqual(as_admin.probe('crm.lead', view.id),
                         {'host': True, 'can_edit': True})
        arch = self.combined(view)
        trays = arch.xpath("//widget[@name='ws_fold_tray']")
        self.assertEqual(len(trays), 1)
        self.assertIs(trays[0].getprevious(),
                      arch.xpath(_pack_xpath(self.contact_host))[0])
        channel = as_admin.create_field('crm.lead', {
            'type': 'char', 'label': 'Referral code'}, view_id=view.id)['name']
        budget = as_admin.create_field('crm.lead', {
            'type': 'integer', 'label': 'Visits wanted'}, view_id=view.id)['name']
        as_admin.publish('crm.lead', view.id, [
            {'id': 'reach1', 'title': '',
             'anchor': {'kind': 'card', 'name': 'reached_card'},
             'fields': [{'name': channel, 'order': 0}]},
            {'id': 'plan1', 'title': 'Plan', 'anchor': {'kind': 'pack_end'},
             'fields': [{'name': budget, 'order': 0}]}])
        arch = self.combined(view)
        pack = arch.xpath(_pack_xpath(self.contact_host))[0]
        self.assertEqual([c.get('name') for c in pack],
                         ['contact_card', 'reached_card', 'status_card',
                          'fs_plan1'])
        self.assertEqual(pack[1].get('data-fs-fields'), channel)
        self.assertEqual(len(arch.xpath("//widget[@name='ws_fold_tray']")), 1)
        data = as_admin.get_studio('crm.lead', view.id)
        self.assertEqual(data['host']['kit'], 'ws')
        self.assertEqual(
            [c['name'] for c in data['cards'] if c.get('pack')],
            ['contact_card', 'reached_card', 'status_card'])
        self.assertEqual({z['name'] for z in data['cards']
                          if z['kind'] == 'zone'},
                         {'people_panel', 'contact_history'})
        self.assertEqual(data['host']['pwa_label'], 'Mobile app')

    def test_31b_head_nurse_has_no_studio_on_either_record(self):
        nurse = self.env['res.users'].create({
            'name': 'FS2 head nurse', 'login': 'fs2_head_nurse',
            'catchment_province_id': self.province.id,
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref(
                                      'health_base.group_healthcare_head_nurse'
                                  ).id])],
        })
        Studio = self.Studio.with_user(nurse)
        for model, view in (('res.partner', self.client_view),
                            ('crm.lead', self.contact_view)):
            self.assertEqual(Studio.probe(model, view.id),
                             {'host': False, 'can_edit': False})
            with self.assertRaises(AccessError):
                Studio.get_studio(model, view.id)
        self.assertFalse(Studio.can_use())
        self.assertTrue(self.Studio.with_user(self.clinic_admin).can_use())


@tagged('post_install', '-at_install')
class TestFsWorkspaceOverHttp(HttpCase):
    """T32 — the probe and the schematic as the clinic administrator's own
    request (the origin user of the transaction is the person, as in the
    browser — ledger §5.265)."""

    def test_32_probe_and_schematic_over_http(self):
        internal = self.env.ref('base.group_user')
        province = self.env['health.catchment.province'].search([], limit=1)
        self.env['res.users'].create({
            'name': 'FS2 http admin', 'login': 'fs2_http_admin',
            'password': 'fs2_http_admin_pw',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, [internal.id, self.env.ref(
                'health_access.group_clinic_admin').id, self.env.ref(
                'sales_team.group_sale_salesman_all_leads').id])],
        })
        client = self.env.ref(CLIENT_VIEW)
        contact = self.env.ref(CONTACT_VIEW)
        base = self.env.ref('base.view_partner_form')
        self.authenticate('fs2_http_admin', 'fs2_http_admin_pw')

        def call(method, args, kwargs=None):
            return self.make_jsonrpc_request(
                '/web/dataset/call_kw/fs.studio/%s' % method,
                {'model': 'fs.studio', 'method': method, 'args': args,
                 'kwargs': kwargs or {}})

        yes = {'host': True, 'can_edit': True}
        self.assertEqual(call('probe', ['res.partner', client.id]), yes)
        self.assertEqual(call('probe', ['crm.lead', contact.id]), yes)
        self.assertEqual(call('probe', ['res.partner', base.id]),
                         {'host': False, 'can_edit': False})
        data = call('get_studio', ['res.partner', client.id])
        self.assertEqual(data['host']['kit'], 'ws')
        markers = [c for c in data['cards'] if c['kind'] == 'pack']
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]['name'], 'profile_overview')
        pack = [c for c in data['cards'] if c.get('pack')]
        self.assertEqual([c['name'] for c in pack],
                         ['personal_card', 'contact_card', 'care_card',
                          'identity_card', 'commission_card'])
        self.assertTrue(all(c['open'] for c in pack))
        self.assertLess(len(data['fields']), 120)
        self.assertTrue(call('can_use', []))


# =========================================================================
#  FS-H3 — the Booking record, and the lists of all four screens
# =========================================================================
def _list_columns(arch):
    return [f.get('name') for f in arch.xpath('/list/field')]


@tagged('post_install', '-at_install')
class TestFsBookingAndLists(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['fs.studio']
        cls.booking_view = cls.env.ref(BOOKING_VIEW)
        cls.booking_host = cls.env.ref('health_form_studio.fs_host_booking')
        internal = cls.env.ref('base.group_user')
        province = cls.env['health.catchment.province'].search([], limit=1)
        cls.owner = cls.env['res.users'].create({
            'name': 'FS3 owner', 'login': 'fs3_owner',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, _owner_groups(cls.env))],
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'FS3 outsider', 'login': 'fs3_outsider',
            'group_ids': [(6, 0, [internal.id])],
        })
        # Staff, not an admin, and allowed to open bookings: a nurse (the
        # healthcare base group alone reads no booking)
        nurse = cls.env.ref('health_access.role_nurse')
        cls.staff = cls.env['res.users'].create({
            'name': 'FS3 nurse', 'login': 'fs3_staff',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, (nurse.group_ids | internal).ids)],
        })

    def setUp(self):
        self.addCleanup(self._fs_rebuild_registry)
        super().setUp()

    def _fs_rebuild_registry(self):
        self.registry._setup_models__(self.cr, list(TOUCHED))

    def combined(self, view, lang=None):
        if lang:
            view = view.with_context(lang=lang)
        return etree.fromstring(view.get_combined_arch())

    def list_for(self, model, list_view, user=None, lang=None):
        Model = self.env[model]
        if user:
            Model = Model.with_user(user)
        if lang:
            Model = Model.with_context(lang=lang)
        return Model.get_views([(list_view.id, 'list')])

    # T45 --------------------------------------------------------------
    def test_45_the_booking_host_resolves_against_todays_form(self):
        from odoo.addons.health_form_studio.models.fs_host import HOST_TEXT
        host, view = self.booking_host, self.booking_view
        self.assertEqual(host._base_view(), view)
        self.assertEqual(self.env['fs.host']._for(BOOKING, view.id), host)
        self.assertEqual(host.kit, 'ws')
        self.assertTrue(host.money_ok)
        self.assertFalse(host.pack_tail)
        arch = self.combined(view)
        packs = arch.xpath(_pack_xpath(host))
        self.assertEqual(len(packs), 1, 'the Booking pack moved')
        self.assertEqual([c['name'] for c in host.sections], BOOKING_CARDS)
        for name in BOOKING_CARDS:
            cards = packs[0].xpath("./div[@name='%s']" % name)
            self.assertEqual(len(cards), 1, name)
            self.assertTrue(cards[0].xpath('./group'), '%s has no group' % name)
        # Notes holds its field directly: shown, never open
        self.assertTrue(packs[0].xpath("./div[@name='notes_card']"))
        self.assertFalse(packs[0].xpath("./div[@name='notes_card']/group"))
        self.assertNotIn('notes_card', [c['name'] for c in host.sections])
        host._check_sections()
        Model = self.env[BOOKING]
        for name, reason in host.locked_fields.items():
            self.assertIn(name, Model._fields, 'locked field %s' % name)
            self.assertIn(reason, HOST_TEXT, reason)
        self.assertEqual([z['name'] for z in host.locked_zones], ['button_box'])
        for zone in host.locked_zones:
            self.assertTrue(arch.xpath("//*[@name='%s']" % zone['name']))
            self.assertIn(zone['title'], HOST_TEXT)
            self.assertIn(zone['reason'], HOST_TEXT)
        # the schematic: titles read from the <span>s, five open, Notes shut
        data = self.Studio.get_studio(BOOKING, view.id)
        pack = [c for c in data['cards'] if c.get('pack')]
        by_name = {c['name']: c for c in pack}
        self.assertEqual([c['name'] for c in pack if c['open']], BOOKING_CARDS)
        self.assertEqual(by_name['visit_card']['title'], 'Visit')
        self.assertEqual(by_name['commission_fees_card']['title'], 'Pricing')
        self.assertFalse(by_name['notes_card']['open'])
        self.assertTrue(all(c['title'] for c in pack))
        # every list resolves: the view, its type, the anchor exactly once
        for xmlid, (list_xmlid, anchor) in LISTS.items():
            h = self.env.ref(xmlid)
            self.assertEqual((h.list_view_xmlid, h.list_anchor),
                             (list_xmlid, anchor))
            self.assertEqual(h._list_view(), self.env.ref(list_xmlid))
            self.assertEqual(h._list_problems(), [], h.name)
            self.assertTrue(h._list_title())
            h._check_list()
        if self.env['res.lang']._lang_get('vi_VN'):
            vi = host.with_context(lang='vi_VN')
            self.assertEqual(vi._fs_text('Decides who does the visit.'),
                             'Quyết định ai thực hiện lượt thăm.')
            self.assertEqual(vi.name, 'Lịch hẹn')
            self.assertEqual(vi._list_title(), 'Lịch hẹn')
        res = self.Studio.validate_all()
        self.assertFalse([h for h in res['hosts']
                          if h['model'] in (BOOKING, 'res.partner', 'crm.lead',
                                            MODEL)])

    # T46 --------------------------------------------------------------
    def test_46_end_to_end_on_the_booking(self):
        as_owner = self.Studio.with_user(self.owner)
        view = self.booking_view
        self.assertEqual(as_owner.probe(BOOKING, view.id),
                         {'host': True, 'can_edit': True})
        parking = as_owner.create_field(BOOKING, {
            'type': 'text', 'label': 'Parking instructions', 'vis': 'staff',
            'list_ok': True}, view_id=view.id)['name']
        gender = as_owner.create_field(BOOKING, {
            'type': 'selection', 'label': 'Preferred nurse gender',
            'vis': 'staff', 'list_ok': True,
            'options': [{'label': 'Female', 'label_vi': 'Nữ'},
                        {'label': 'Male', 'label_vi': 'Nam'},
                        {'label': 'No preference'}]}, view_id=view.id)['name']
        # Admins only: everybody who may open a booking at all is Staff, so
        # the visibility of a column is proven between Staff and Admins
        deposit = as_owner.create_field(BOOKING, {
            'type': 'monetary', 'label': 'Key safe deposit', 'vis': 'admin',
            'list_ok': True}, view_id=view.id)['name']
        meta = self.env['fs.field.meta']
        self.assertFalse(meta.search([('name', '=', parking)]).list_ok)
        v1 = [{'id': 'care1', 'title': '',
               'anchor': {'kind': 'card', 'name': 'care_team_card'},
               'fields': [{'name': parking, 'order': 0}]},
              {'id': 'pref1', 'title': 'Visit preferences',
               'title_vi': 'Mong muốn khi thăm',
               'anchor': {'kind': 'pack_end'},
               'fields': [{'name': gender, 'order': 0},
                          {'name': deposit, 'order': 1}]}]
        res = as_owner.publish(BOOKING, view.id, v1)
        layout = self.env['fs.layout'].search([('base_view_id', '=', view.id)])
        self.assertEqual(layout.published_by, self.owner)
        pack = self.combined(view).xpath(_pack_xpath(self.booking_host))[0]
        names = [c.get('name') for c in pack if isinstance(c.tag, str)]
        # last in the pack, after Notes; the cards other modules add stay in
        self.assertEqual(names[-1], 'fs_pref1')
        self.assertLess(names.index('notes_card'), names.index('fs_pref1'))
        for foreign in ('payment_summary_card', 'legacy_audit_card'):
            nodes = self.combined(view).xpath("//div[@name='%s']" % foreign)
            if nodes:
                self.assertTrue(nodes[0].xpath(
                    "ancestor::div[contains(@class,'ws-pack')]"), foreign)
        care = pack.xpath("./div[@name='care_team_card']")[0]
        self.assertEqual(care.get('data-fs-fields'), parking)
        self.assertIn(parking, [f.get('name') for f in care.iter('field')])
        # the list: money and dropdown after Priority, never the long text
        list_view = self.env.ref('health_fieldservice.view_health_fso_list_ops')
        cols = _list_columns(self.combined(list_view))
        at = cols.index('priority')
        self.assertEqual(cols[at + 1:at + 3], [gender, deposit])
        self.assertNotIn(parking, cols)
        node = self.combined(list_view).xpath(
            "/list/field[@name='%s']" % gender)[0]
        self.assertEqual((node.get('widget'), node.get('optional')),
                         ('badge', 'show'))
        self.assertIsNone(self.combined(list_view).xpath(
            "/list/field[@name='%s']" % deposit)[0].get('widget'))
        # Who sees a column is who sees the field, decided by the server: a
        # Staff member gets the Staff dropdown and not the Admins-only money;
        # the Owner gets both; somebody outside Staff cannot open bookings at
        # all, so gets neither the fields nor the columns
        staff = etree.fromstring(self.list_for(
            BOOKING, list_view, self.staff)['views']['list']['arch'])
        self.assertIn(gender, _list_columns(staff))
        self.assertNotIn(deposit, _list_columns(staff))
        owner = etree.fromstring(self.list_for(
            BOOKING, list_view, self.owner)['views']['list']['arch'])
        self.assertIn(gender, _list_columns(owner))
        self.assertIn(deposit, _list_columns(owner))
        staff_form = etree.fromstring(self.env[BOOKING].with_user(
            self.staff).get_views([(view.id, 'form')])['views']['form']['arch'])
        self.assertTrue(staff_form.xpath("//field[@name='%s']" % parking))
        self.assertFalse(staff_form.xpath("//field[@name='%s']" % deposit))
        self.assertNotIn(parking, self.env[BOOKING].with_user(
            self.outsider).fields_get())
        with self.assertRaises(AccessError):
            self.list_for(BOOKING, list_view, self.outsider)
        # the dropdown reads Vietnamese in the list too
        if self.env['res.lang']._lang_get('vi_VN'):
            vi = self.list_for(BOOKING, list_view, lang='vi_VN')
            sel = dict(vi['models'][BOOKING]['fields'][gender]['selection'])
            self.assertIn('Nữ', sel.values())
        # version 2 drops the money column; going back restores both arches
        v2 = [v1[0], dict(v1[1], fields=[{'name': gender, 'order': 0}])]
        as_owner.publish(BOOKING, view.id, v2)
        self.assertNotIn(deposit, _list_columns(self.combined(list_view)))
        back = as_owner.rollback(layout.id, res['version'])
        hist = {h.version: h for h in self.env['fs.layout.history'].search(
            [('layout_id', '=', layout.id)])}
        self.assertEqual(hist[back['version']].arch, hist[res['version']].arch)
        self.assertEqual(hist[back['version']].list_arch,
                         hist[res['version']].list_arch)
        self.assertEqual(layout.list_view_id.arch_db.strip(),
                         hist[res['version']].list_arch.strip())
        self.assertIn(deposit, _list_columns(self.combined(list_view)))

    # T47 --------------------------------------------------------------
    def test_47_a_column_on_each_of_the_other_lists(self):
        made = {}
        for xmlid in ('health_form_studio.fs_host_client',
                      'health_form_studio.fs_host_contact',
                      'health_form_studio.fs_host_incident'):
            host = self.env.ref(xmlid)
            form = host._base_view()
            list_view = host._list_view()
            name = self.Studio.create_field(host.model, {
                'type': 'char', 'label': 'FS3 column', 'list_ok': True},
                view_id=form.id)['name']
            anchor = ({'kind': 'pack_end'} if host.kit == 'ws'
                      else {'kind': 'before_notebook'})
            self.Studio.publish(host.model, form.id, [{
                'id': 'col1', 'title': 'Columns', 'anchor': anchor,
                'fields': [{'name': name, 'order': 0}]}])
            cols = _list_columns(self.combined(list_view))
            self.assertEqual(cols[cols.index(host.list_anchor) + 1], name,
                             host.name)
            # the list draws for the people who open it (the Incident list
            # has no js_class, the Client list is the default partner list)
            res = self.list_for(host.model, list_view)
            self.assertIn(name, _list_columns(etree.fromstring(
                res['views']['list']['arch'])))
            made[host.model] = name
        # the Clients list is the default partner list: a Client column
        # shows wherever a partner list is opened without naming one
        default = self.env['res.partner'].get_views([(False, 'list')])
        if default['views']['list']['id'] == self.env.ref(
                'health_fieldservice.view_health_client_list_ops').id:
            self.assertIn(made['res.partner'], _list_columns(etree.fromstring(
                default['views']['list']['arch'])))


@tagged('post_install', '-at_install')
class TestFsBookingOverHttp(HttpCase):
    """T48 — the Booking probe and schematic as the Owner's own request."""

    def test_48_probe_and_schematic_over_http(self):
        province = self.env['health.catchment.province'].search([], limit=1)
        self.env['res.users'].create({
            'name': 'FS3 http owner', 'login': 'fs3_http_owner',
            'password': 'fs3_http_owner_pw',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, _owner_groups(self.env))],
        })
        ops = self.env.ref(BOOKING_VIEW)
        legacy = self.env.ref(BOOKING_LEGACY_VIEW)
        self.authenticate('fs3_http_owner', 'fs3_http_owner_pw')

        def call(method, args, kwargs=None):
            return self.make_jsonrpc_request(
                '/web/dataset/call_kw/fs.studio/%s' % method,
                {'model': 'fs.studio', 'method': method, 'args': args,
                 'kwargs': kwargs or {}})

        self.assertEqual(call('probe', [BOOKING, ops.id]),
                         {'host': True, 'can_edit': True})
        self.assertEqual(call('probe', [BOOKING, legacy.id]),
                         {'host': False, 'can_edit': False})
        data = call('get_studio', [BOOKING, ops.id])
        self.assertEqual(data['host']['kit'], 'ws')
        self.assertEqual(data['host']['title'], 'Booking')
        self.assertEqual(data['host']['list_title'], 'Bookings')
        self.assertTrue(data['host']['money_ok'])
        markers = [c for c in data['cards'] if c['kind'] == 'pack']
        self.assertEqual([m['name'] for m in markers], ['overview'])
        self.assertEqual([c['name'] for c in data['cards']
                          if c.get('pack') and c['open']], BOOKING_CARDS)
        self.assertEqual({z['name'] for z in data['cards']
                          if z['kind'] == 'zone'}, {'button_box'})


# =========================================================================
#  FS-H4 — health information reach: exports, analytics, the nurse app,
#  encryption on the Client record (tests 60–64)
# =========================================================================
def _pwa_controller():
    from odoo.addons.health_pwa.controllers.sync import (
        HealthPWASyncController)
    return HealthPWASyncController()


@tagged('post_install', '-at_install')
class TestFsHealthReach(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['fs.studio']
        cls.client_view = cls.env.ref(CLIENT_VIEW)
        cls.booking_view = cls.env.ref(BOOKING_VIEW)
        cls.client_host = cls.env.ref('health_form_studio.fs_host_client')
        cls.booking_host = cls.env.ref('health_form_studio.fs_host_booking')
        province = cls.env['health.catchment.province'].search([], limit=1)
        cls.province = province
        cls.owner = cls.env['res.users'].create({
            'name': 'FS4 owner', 'login': 'fs4_owner',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, _owner_groups(cls.env))],
        })
        nurse = cls.env.ref('health_access.role_nurse')
        cls.nurse = cls.env['res.users'].create({
            'name': 'FS4 nurse', 'login': 'fs4_nurse',
            'catchment_province_id': province.id,
            'group_ids': [(6, 0, (nurse.group_ids | cls.env.ref(
                'base.group_user')).ids)],
        })

    def setUp(self):
        self.addCleanup(self._fs_rebuild_registry)
        super().setUp()

    def _fs_rebuild_registry(self):
        self.registry._setup_models__(self.cr, list(TOUCHED))

    def client(self, name='FS4 client'):
        return self.env['res.partner'].create({
            'name': name, 'is_patient': True,
            'catchment_province_id': self.province.id})

    def columns(self, table):
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s", [table])
        return {r[0] for r in self.env.cr.fetchall()}

    # T60 --------------------------------------------------------------
    def test_60_hosts_flags_and_words(self):
        """T60 — the Client stores health information encrypted and is in
        the nurse app; the Booking is in the nurse app, not encrypted; the
        Contact and the Incident are neither. The encryption module is
        installed. Every new sentence has its Vietnamese."""
        from odoo.addons.health_form_studio.models.fs_host import APP_WORDS
        flags = {self.env.ref('health_form_studio.%s' % x).name:
                 (self.env.ref('health_form_studio.%s' % x).encrypt_ok,
                  self.env.ref('health_form_studio.%s' % x).pwa_ok)
                 for x in ('fs_host_client', 'fs_host_booking',
                           'fs_host_contact', 'fs_host_incident')}
        self.assertEqual(flags, {'Client': (True, True),
                                 'Booking': (False, True),
                                 'Contact': (False, False),
                                 'Incident': (False, False)})
        module = self.env['ir.module.module'].search(
            [('name', '=', 'health_phi_encryption')])
        self.assertEqual(module.state, 'installed')
        cipher = self.env['ir.model.fields']._fs_cipher()
        self.assertTrue(cipher)
        token = cipher[0](self.env, 'probe')
        self.assertTrue(token.startswith('enc$1$'))
        self.assertEqual(cipher[1](self.env, token), 'probe')
        self.assertEqual(set(APP_WORDS),
                         set(self.env['fs.host']._app_words()))
        for key in APP_WORDS:
            text = self.client_host._app_text(key)
            self.assertNotIn('mobile app', text)
            self.assertNotIn('Odoo', text)
        if self.env['res.lang']._lang_get('vi_VN'):
            vi = self.client_host.with_context(lang='vi_VN')
            for key in APP_WORDS:
                self.assertNotEqual(vi._app_text(key),
                                    self.client_host._app_text(key), key)

    # T61 --------------------------------------------------------------
    def test_61_end_to_end_on_the_client(self):
        """T61 — as the Owner on the Client: "Allergy notes" (long text,
        health information) is stored encrypted with the client's own token
        format; "Preferred language" (dropdown, nurse app on) reaches the
        app's client record with its Vietnamese option for a Vietnamese
        reader; the health field never does; exports refuse it; analytics
        discovery skips the field and its hidden column."""
        as_owner = self.Studio.with_user(self.owner)
        view = self.client_view
        allergy = as_owner.create_field('res.partner', {
            'type': 'text', 'label': 'Allergy notes', 'phi': True,
            'vis': 'staff', 'pwa': True}, view_id=view.id)
        self.assertTrue(allergy['encrypted'])
        allergy = allergy['name']
        lang = as_owner.create_field('res.partner', {
            'type': 'selection', 'label': 'Preferred language', 'pwa': True,
            'label_vi': 'Ngôn ngữ ưu tiên',
            'options': [{'label': 'Vietnamese', 'label_vi': 'Tiếng Việt'},
                        {'label': 'English', 'label_vi': 'Tiếng Anh'}]},
            view_id=view.id)['name']
        meta = self.env['fs.field.meta']
        self.assertFalse(meta.search([('name', '=', allergy)]).pwa)
        self.assertTrue(meta.search([('name', '=', lang)]).pwa)
        cols = self.columns('res_partner')
        self.assertNotIn(allergy, cols)
        self.assertIn(allergy + '_enc', cols)
        as_owner.publish('res.partner', view.id, [{
            'id': 'pref1', 'title': 'Preferences', 'anchor': {'kind': 'pack_end'},
            'fields': [{'name': lang, 'order': 0},
                       {'name': allergy, 'order': 1}]}])
        partner = self.client()
        en_code = self.env['ir.model.fields'].search(
            [('model', '=', 'res.partner'), ('name', '=', lang)]
        ).selection_ids.filtered(lambda s: s.name == 'English').value
        partner.with_user(self.owner).write(
            {allergy: 'Penicillin\nLatex', lang: en_code})
        self.env.flush_all()
        self.env.cr.execute('SELECT "%s" FROM res_partner WHERE id = %%s'
                            % (allergy + '_enc'), [partner.id])
        raw = self.env.cr.fetchone()[0]
        self.assertTrue(raw.startswith('enc$1$'))
        self.assertNotIn('Penicillin', raw)
        partner.invalidate_recordset()
        self.assertEqual(partner[allergy], 'Penicillin\nLatex')
        # Staff read it on screen (encrypted at rest only)
        self.env.invalidate_all()
        self.assertEqual(partner.with_user(self.nurse).read([allergy])[0][
            allergy], 'Penicillin\nLatex')
        # the nurse app's client record
        ctl = _pwa_controller()
        rec = ctl._patient_record(partner.sudo())
        names = [c['name'] for c in rec['custom_fields']]
        self.assertEqual(names, [lang])
        self.assertEqual(rec['custom_fields'][0]['value'], 'English')
        self.assertEqual(rec['custom_fields'][0]['label'], 'Preferred language')
        if self.env['res.lang']._lang_get('vi_VN'):
            vi = ctl._patient_record(partner.sudo().with_context(lang='vi_VN'))
            self.assertEqual(vi['custom_fields'][0]['value'], 'Tiếng Anh')
            self.assertEqual(vi['custom_fields'][0]['label'], 'Ngôn ngữ ưu tiên')
        self.assertNotIn(allergy, json.dumps(rec, default=str))
        # exports refuse it, by its label
        from odoo.exceptions import UserError
        with self.assertRaisesRegex(UserError, 'Allergy notes'):
            partner.export_data(['name', allergy])
        self.assertIs(self.env['res.partner'].fields_get(
            [allergy], ['exportable'])[allergy]['exportable'], False)
        # analytics discovery skips the field and its hidden column
        if 'bi.source' in self.env:
            source = self.env['bi.source'].create({
                'name': 'FS4 partners', 'type': 'odoo_model',
                'model_id': self.env['ir.model']._get_id('res.partner')})
            found = {c['name'] for c in source._fetch_schema_odoo()}
            self.assertNotIn(allergy, found)
            self.assertNotIn(allergy + '_enc', found)
            self.assertIn(lang, found)

    # T62 --------------------------------------------------------------
    def test_62_end_to_end_on_the_booking(self):
        """T62 — on the Booking: "Key safe code" (text, health information)
        is hidden only (stored plain, not exportable, never in the app);
        "Parking instructions" (long text, Staff, nurse app on) reaches both
        app payloads; an Admins-only field cannot be switched on."""
        as_owner = self.Studio.with_user(self.owner)
        view = self.booking_view
        key = as_owner.create_field(BOOKING, {
            'type': 'char', 'label': 'Key safe code', 'phi': True,
            'pwa': True}, view_id=view.id)
        self.assertFalse(key['encrypted'])
        key = key['name']
        parking = as_owner.create_field(BOOKING, {
            'type': 'text', 'label': 'Parking instructions', 'vis': 'staff',
            'pwa': True}, view_id=view.id)['name']
        internal = as_owner.create_field(BOOKING, {
            'type': 'char', 'label': 'Internal code', 'vis': 'admin',
            'pwa': True}, view_id=view.id)['name']
        meta = self.env['fs.field.meta']
        self.assertFalse(meta.search([('name', '=', key)]).pwa)
        self.assertTrue(meta.search([('name', '=', parking)]).pwa)
        self.assertFalse(meta.search([('name', '=', internal)]).pwa)
        info = as_owner.get_studio(BOOKING, view.id)['fields']
        self.assertEqual(info[internal]['pwa_reason'],
                         'Admins-only fields cannot show in the nurse app.')
        self.assertEqual(info[key]['pwa_reason'],
                         'Health information never reaches the nurse app.')
        row = self.env['ir.model.fields'].search(
            [('model', '=', BOOKING), ('name', '=', key)])
        self.assertTrue(row.store)
        self.assertTrue(row.fs_phi)
        self.assertIn(key, self.columns('health_fieldservice_order'))
        self.assertIs(self.env[BOOKING].fields_get([key], ['exportable'])[
            key]['exportable'], False)
        as_owner.publish(BOOKING, view.id, [{
            'id': 'visit1', 'title': 'Visit access',
            'anchor': {'kind': 'pack_end'},
            'fields': [{'name': parking, 'order': 0},
                       {'name': key, 'order': 1},
                       {'name': internal, 'order': 2}]}])
        order = self.env[BOOKING].search([], limit=1)
        if not order:
            self.skipTest('no booking on this database')
        order.write({parking: 'Use the side gate.\nBlue door.',
                     key: '4455', internal: 'X1'})
        rec = _pwa_controller()._fso_record(order.sudo())
        self.assertEqual([c['name'] for c in rec['custom_fields']], [parking])
        self.assertEqual(rec['custom_fields'][0]['value'],
                         'Use the side gate.\nBlue door.')
        self.assertEqual(rec['custom_fields'][0]['type'], 'text')
        detail = self.env['fs.studio'].app_fields(BOOKING, order.sudo())
        self.assertEqual([c['name'] for c in detail[order.id]], [parking])
        self.assertNotIn('4455', json.dumps(rec, default=str))

    # T64 --------------------------------------------------------------
    def test_64_the_nurse_app_version_and_strings(self):
        """T64 — the app's five version pins read 1.21.6; the new block's
        title has its Vietnamese in both of the app's dictionaries; nothing
        added names the product underneath."""
        pwa = get_module_path('health_pwa')
        with open(os.path.join(pwa, 'views', 'pwa_templates.xml'),
                  encoding='utf-8') as fh:
            tpl = fh.read()
        pins = re.findall(r"(?:pwa_asset_version\">|version: '|PWA_SW_VERSION = '"
                          r"|Service Worker v|CACHE_VERSION = ')(\d+\.\d+\.\d+)",
                          tpl)
        self.assertEqual(pins, ['1.21.6'] * 5)
        with open(os.path.join(pwa, 'static', 'src', 'js', 'app.js'),
                  encoding='utf-8') as fh:
            app = fh.read()
        with open(os.path.join(pwa, 'static', 'src', 'js', 'utils',
                               'pwa-utils.js'), encoding='utf-8') as fh:
            utils = fh.read()
        self.assertIn("'More details': 'Chi tiết thêm'", app)
        self.assertIn("'More details': 'Chi tiết thêm'", utils)
        blocks = re.findall(r'<!-- More details:.*?</div>\s*</div>', app, re.S)
        self.assertEqual(len(blocks), 2)
        for block in blocks:
            self.assertNotIn('Odoo', block)
            self.assertIn('custom_fields', block)


@tagged('post_install', '-at_install')
class TestFsNurseAppOverHttp(HttpCase):
    """T63 — as a nurse, over the app's real routes: the client in the
    nurse's sync and the booking detail carry the allowed Studio field only;
    health information never."""

    def setUp(self):
        self.addCleanup(self._fs_rebuild_registry)
        super().setUp()

    def _fs_rebuild_registry(self):
        self.registry._setup_models__(self.cr, list(TOUCHED))

    def test_63_the_nurse_app_over_http(self):
        import uuid
        from datetime import timedelta
        from odoo import fields as ofields
        from odoo.tests import new_test_user
        env = self.env
        Province = env['health.catchment.province']
        province = Province.create({'name': 'FS4 X %s' % uuid.uuid4().hex[:5],
                                    'code': 'F4%s' % uuid.uuid4().hex[:3]})
        facility = env['health.facility'].create({
            'name': 'FS4 Facility', 'code': 'F4F%s' % uuid.uuid4().hex[:3],
            'street': '1 X St', 'city': 'X City',
            'catchment_province_id': province.id})
        patient = env['res.partner'].create({
            'name': 'FS4 Patient', 'is_patient': True,
            'catchment_province_id': province.id,
            'primary_facility_id': facility.id,
            'mobile': '09%08d' % (uuid.uuid4().int % 10 ** 8)})
        nurse = new_test_user(
            env, login='fs4_nurse_%s' % uuid.uuid4().hex[:6],
            groups='base.group_user,health_base.group_healthcare_nurse',
            password='fs4nursepw')
        nurse.write({'catchment_province_id': False})
        staff = env['hr.employee'].create({'name': 'FS4 Nurse Emp',
                                           'user_id': nurse.id})
        order = env[BOOKING].create({
            'patient_id': patient.id, 'facility_id': facility.id,
            'scheduled_datetime': ofields.Datetime.now() + timedelta(days=1),
            'scheduled_duration': 120, 'service_type': 'home_visit'})
        order.action_assign_staff_to_fso(staff.id, assignment_role='lead')
        # Studio fields (as the superuser: the gate is not what is tested)
        Studio = env['fs.studio']
        client_view = env.ref(CLIENT_VIEW)
        booking_view = env.ref(BOOKING_VIEW)
        lang = Studio.create_field('res.partner', {
            'type': 'char', 'label': 'Preferred language', 'pwa': True},
            view_id=client_view.id)['name']
        allergy = Studio.create_field('res.partner', {
            'type': 'text', 'label': 'Allergy notes', 'phi': True},
            view_id=client_view.id)['name']
        parking = Studio.create_field(BOOKING, {
            'type': 'text', 'label': 'Parking instructions', 'vis': 'staff',
            'pwa': True}, view_id=booking_view.id)['name']
        keycode = Studio.create_field(BOOKING, {
            'type': 'char', 'label': 'Key safe code', 'phi': True},
            view_id=booking_view.id)['name']
        Studio.publish('res.partner', client_view.id, [{
            'id': 'pref1', 'title': 'Preferences', 'anchor': {'kind': 'pack_end'},
            'fields': [{'name': lang, 'order': 0},
                       {'name': allergy, 'order': 1}]}])
        Studio.publish(BOOKING, booking_view.id, [{
            'id': 'acc1', 'title': 'Access', 'anchor': {'kind': 'pack_end'},
            'fields': [{'name': parking, 'order': 0},
                       {'name': keycode, 'order': 1}]}])
        patient.write({lang: 'Vietnamese', allergy: 'Penicillin'})
        order.write({parking: 'Side gate', keycode: '4455'})
        self.authenticate(nurse.login, 'fs4nursepw')
        resp = self.url_open('/health_pwa/sync/changes?force_full=true').json()
        resp = resp.get('data', resp)
        patients = {r['id']: r for r in resp['changes']['patients']['records']
                    if not r.get('is_deleted')}
        self.assertIn(patient.id, patients)
        custom = patients[patient.id]['custom_fields']
        self.assertEqual([(c['name'], c['value']) for c in custom],
                         [(lang, 'Vietnamese')])
        orders = {r['id']: r for r in
                  resp['changes']['field_service_orders']['records']
                  if not r.get('is_deleted')}
        self.assertIn(order.id, orders)
        self.assertEqual([c['name'] for c in orders[order.id]['custom_fields']],
                         [parking])
        detail = self.url_open('/health_pwa/api/fso/%s' % order.id).json()
        data = detail.get('data', detail)
        self.assertEqual([(c['name'], c['value'])
                          for c in data['custom_fields']],
                         [(parking, 'Side gate')])
        body = json.dumps(resp) + json.dumps(detail)
        self.assertNotIn('Penicillin', body)
        self.assertNotIn('4455', body)
        self.assertNotIn(allergy, body)
        self.assertNotIn(keycode, body)


#: the files whose literal nurse-app version pins move with every bump
PIN_FILES = (
    ('health_pwa_daystrip', 'tests/test_daystrip.py'),
    ('health_scribe', 'tests/test_scribe.py'),
    ('health_pwa_ergo', 'tests/test_pwa_ergo.py'),
    ('health_pwa_family', 'tests/test_pwa_family.py'),
    ('health_form_studio', 'tests/test_fs_health.py'),
)
APP_VERSION = '1.21.6'


@tagged('post_install', '-at_install')
class TestFsNurseAppVersion(TransactionCase):

    def test_73_the_nurse_app_version_pins(self):
        """T73 (FS-H5) — the five pins read 1.21.6; the five co-resident
        test files pin 1.21.6 and no older version of the 1.21 line; the
        service-worker script is kept out of the translatable terms."""
        pwa = get_module_path('health_pwa')
        with open(os.path.join(pwa, 'views', 'pwa_templates.xml'),
                  encoding='utf-8') as fh:
            tpl = fh.read()
        pins = re.findall(r"(?:pwa_asset_version\">|version: '|PWA_SW_VERSION = '"
                          r"|Service Worker v|CACHE_VERSION = ')(\d+\.\d+\.\d+)",
                          tpl)
        self.assertEqual(pins, [APP_VERSION] * 5)
        arch = etree.fromstring(tpl.encode())
        worker = arch.xpath("//template[@id='service_worker_js']")
        self.assertEqual(len(worker), 1)
        self.assertEqual([c.get('t-translation') for c in worker[0]], ['off'])
        self.assertFalse((worker[0].text or '').strip())
        for module, rel in PIN_FILES:
            path = os.path.join(get_module_path(module), rel)
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            self.assertIn(APP_VERSION, text, path)
            self.assertNotIn('1.21.' + '0', text, path)
        with open(os.path.join(pwa, 'i18n', 'vi_VN.po'),
                  encoding='utf-8') as fh:
            self.assertNotIn('arch_db:health_pwa.service_worker_js', fh.read())


@tagged('post_install', '-at_install')
class TestFsWorkerLanguage(HttpCase):
    """T72 (FS-H5) — a Vietnamese-language user and an English one are
    served the same service-worker script, at the current version; a stale
    Vietnamese copy planted in the view goes with the module's migration;
    the app's own Vietnamese copy is untouched."""

    def _users(self):
        from odoo.tests import new_test_user
        env = self.env
        env['res.lang']._activate_lang('vi_VN')
        groups = 'base.group_user,health_base.group_healthcare_nurse'
        vi = new_test_user(env, login='fs5_sw_vi', groups=groups,
                           password='fs5_sw_vi_pw', lang='vi_VN')
        en = new_test_user(env, login='fs5_sw_en', groups=groups,
                           password='fs5_sw_en_pw', lang='en_US')
        return vi, en

    def _worker(self, login, password):
        self.authenticate(login, password)
        res = self.url_open('/health_pwa/service-worker.js')
        self.assertEqual(res.status_code, 200)
        return res.content

    def test_72_the_worker_script_is_the_same_in_every_language(self):
        import importlib.util
        vi, en = self._users()
        view = self.env.ref('health_pwa.service_worker_js')
        self.env.flush_all()
        cr = self.env.cr
        # plant what every database carried: a Vietnamese copy of an old
        # version of the script
        cr.execute("SELECT arch_db->>'en_US' FROM ir_ui_view WHERE id = %s",
                   (view.id,))
        source = cr.fetchone()[0]
        self.assertIn("CACHE_VERSION = '%s'" % APP_VERSION, source)
        stale = source.replace(APP_VERSION, '1.0.95')
        cr.execute("UPDATE ir_ui_view SET arch_db = arch_db || "
                   "jsonb_build_object('vi_VN', %s::text) WHERE id = %s",
                   (stale, view.id))
        self.env.invalidate_all()
        self.env.registry.clear_cache('templates')
        planted = self._worker('fs5_sw_vi', 'fs5_sw_vi_pw')
        self.assertIn(b"CACHE_VERSION = '1.0.95'", planted)
        # the migration removes it, for this view only
        path = os.path.join(get_module_path('health_pwa'), 'migrations',
                            '19.0.1.1.1', 'end-drop-stale-worker-copy.py')
        spec = importlib.util.spec_from_file_location('fs5_pwa_end', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cr.execute("SELECT count(*) FROM ir_ui_view WHERE arch_db ? 'vi_VN'")
        others = cr.fetchone()[0] - 1
        module.migrate(cr, '19.0.1.1.0')
        cr.execute("SELECT arch_db ? 'vi_VN' FROM ir_ui_view WHERE id = %s",
                   (view.id,))
        self.assertFalse(cr.fetchone()[0])
        cr.execute("SELECT count(*) FROM ir_ui_view WHERE arch_db ? 'vi_VN'")
        self.assertEqual(cr.fetchone()[0], others)
        self.env.invalidate_all()
        self.env.registry.clear_cache('templates')
        body_vi = self._worker('fs5_sw_vi', 'fs5_sw_vi_pw')
        body_en = self._worker('fs5_sw_en', 'fs5_sw_en_pw')
        self.assertEqual(body_vi, body_en)
        self.assertIn(b"CACHE_VERSION = '%s'" % APP_VERSION.encode(), body_vi)
        self.assertNotIn(b'<t', body_vi)
        # the shell itself is still Vietnamese for the Vietnamese user
        self.authenticate('fs5_sw_vi', 'fs5_sw_vi_pw')
        shell = self.url_open('/health_pwa')
        self.assertEqual(shell.status_code, 200)
        self.assertIn('Việt Úc Care v', shell.text)
        self.assertIn('?v=%s' % APP_VERSION, shell.text)
        self.authenticate('fs5_sw_en', 'fs5_sw_en_pw')
        self.assertIn('Viet Uc Care v', self.url_open('/health_pwa').text)
