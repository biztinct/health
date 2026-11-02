# -*- coding: utf-8 -*-
"""FS-H1 core tests (handover §5, tests 1–12).

The core is tested on a NEUTRAL model — `res.partner` with a throwaway host on
`base.view_partner_form` — so nothing here depends on a product's screens. The
product's own host (the incident form) is tested by the overlay.

EVERY TEST THAT MAKES A FIELD REBUILDS THE REGISTRY AFTERWARDS. A custom field
is a registry change: rolling the test transaction back removes the row and
the column but not the Python field the registry built from them, and the next
test would then read a column that no longer exists. `_FsCase.setUp` registers
the rebuild BEFORE the framework's own cleanups, so it runs LAST — after the
savepoint has been rolled back — and rebuilds the touched models from what the
database really holds.
"""
import os
import re

from lxml import etree

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

TOUCHED = ('res.partner', 'account.move')


class _FsCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('biz_form_studio.gate_group', 'base.group_system')
        ICP.set_param('biz_form_studio.group_staff', 'base.group_user')
        ICP.set_param('biz_form_studio.group_admin', 'base.group_system')
        cls.Studio = cls.env['fs.studio']
        cls.view = cls.env.ref('base.view_partner_form')
        cls.host = cls.env['fs.host'].create({
            'model': 'res.partner',
            'base_view_xmlid': 'base.view_partner_form',
            'sections': [],
        })
        cls.env['fs.link.target'].create({'model': 'res.country',
                                          'label': 'Country'})

    def setUp(self):
        self.addCleanup(self._fs_rebuild_registry)
        super().setUp()

    def _fs_rebuild_registry(self):
        names = [m for m in TOUCHED if m in self.registry]
        self.registry._setup_models__(self.cr, names)

    # helpers ---------------------------------------------------------
    def make(self, label, ftype='char', **extra):
        spec = dict({'type': ftype, 'label': label}, **extra)
        return self.Studio.create_field('res.partner', spec,
                                        view_id=self.view.id)['name']

    def combined(self):
        return etree.fromstring(self.view.get_combined_arch())

    def section(self, sid, names, title='Extra', anchor=None):
        return {'id': sid, 'title': title,
                'anchor': anchor or {'kind': 'before_notebook'},
                'fields': [{'name': n, 'order': i} for i, n in enumerate(names)]}


@tagged('post_install', '-at_install')
class TestFsFields(_FsCase):

    def test_01_create_char_field(self):
        """T1 — a real manual field, a real column, a meta row; Vietnamese
        label slugged to ASCII."""
        name = self.make('Khung giờ ưu tiên')
        self.assertEqual(name, 'x_fs_khung_gio_uu_tien')
        row = self.env['ir.model.fields'].search(
            [('model', '=', 'res.partner'), ('name', '=', name)])
        self.assertEqual(row.state, 'manual')
        self.assertEqual(row.ttype, 'char')
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'res_partner' AND column_name = %s", [name])
        self.assertTrue(self.env.cr.fetchone(), 'the column was not created')
        self.assertIn(name, self.env['res.partner'].fields_get([name]))
        meta = self.env['fs.field.meta'].search([('field_id', '=', row.id)])
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta.vis, 'all')

    def test_02_slug_collision_length_and_characters(self):
        """T2 — `_2` on collision; a 60-character label stays within 63; odd
        characters are stripped."""
        first = self.make('Preferred window')
        second = self.make('Preferred window')
        self.assertEqual(first, 'x_fs_preferred_window')
        self.assertEqual(second, 'x_fs_preferred_window_2')
        long_name = self.make('A' * 60)
        self.assertLessEqual(len(long_name), 63)
        self.assertRegex(long_name, r'^x_fs_[a-z0-9_]+$')
        odd = self.make('  Đơn vị / (kg) #1!! ')
        self.assertEqual(odd, 'x_fs_don_vi_kg_1')

    def test_03_selection_options_add_rename_refuse_removal(self):
        """T3 — three options; add a fourth and rename one; removing one that
        records use is refused with the count."""
        name = self.make('Contact way', 'selection',
                         options=['Phone call', 'Home visit', 'None'])
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'res.partner'), ('name', '=', name)])
        self.assertEqual(len(field.selection_ids), 3)
        opts = [{'value': s.value, 'label': s.name}
                for s in field.selection_ids.sorted('sequence')]
        opts[0]['label'] = 'Phone'
        opts.append({'label': 'Email'})
        self.Studio.update_field('res.partner', name, {'options': opts})
        field.invalidate_recordset()
        labels = field.selection_ids.sorted('sequence').mapped('name')
        self.assertEqual(len(labels), 4)
        self.assertIn('Phone', labels)
        self.assertIn('Email', labels)
        partners = self.env['res.partner'].search([], limit=2)
        partners.write({name: opts[1]['value']})
        keep = [o for o in opts if o.get('value') != opts[1]['value']]
        with self.assertRaisesRegex(UserError, r'used on 2 records'):
            self.Studio.update_field('res.partner', name, {'options': keep})

    def test_04_link_targets(self):
        """T4 — only a listed record type may be linked; a required link is
        created `restrict`."""
        with self.assertRaises(UserError):
            self.make('Bank', 'many2one', comodel='res.bank')
        name = self.make('Home country', 'many2one', comodel='res.country')
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'res.partner'), ('name', '=', name)])
        self.assertEqual(field.relation, 'res.country')
        self.assertEqual(field.on_delete, 'set null')
        req = self.make('Birth country', 'many2one', comodel='res.country',
                        required=True)
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'res.partner'), ('name', '=', req)])
        self.assertEqual(field.on_delete, 'restrict')
        meta = self.env['fs.field.meta'].search([('field_id', '=', field.id)])
        self.assertTrue(meta.required)
        # required is a rule of the screen, never of the database column
        self.assertFalse(field.required)

    def test_05_money_needs_a_currency(self):
        """T5 — Money is refused on a screen without `currency_id`, and works
        on one that has it."""
        partner_has = 'currency_id' in self.env['res.partner']._fields
        self.assertEqual(self.host.money_ok, partner_has)
        if not partner_has:
            with self.assertRaises(UserError):
                self.make('Budget', 'monetary')
        if 'account.move' not in self.env or not self.env.ref(
                'account.view_move_form', raise_if_not_found=False):
            self.skipTest('no second screen with a currency installed')
        self.env['fs.host'].create({
            'model': 'account.move',
            'base_view_xmlid': 'account.view_move_form'})
        res = self.Studio.create_field(
            'account.move', {'type': 'monetary', 'label': 'Agreed fee'})
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'account.move'), ('name', '=', res['name'])])
        self.assertEqual(field.ttype, 'monetary')
        self.assertEqual(field.currency_field, 'currency_id')

    def test_06_visibility_is_enforced_by_the_orm(self):
        """T6 — Admins: a plain internal user neither sees nor reads it.
        Everyone: they do."""
        admin_only = self.make('Internal note', vis='admin')
        everyone = self.make('Nickname')
        field = self.env['res.partner']._fields[admin_only]
        self.assertEqual(field.groups, 'base.group_system')
        self.assertFalse(self.env['res.partner']._fields[everyone].groups)
        user = self.env['res.users'].create({
            'name': 'FS plain user', 'login': 'fs_plain_user_t6',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        Partner = self.env['res.partner'].with_user(user)
        fields_ = Partner.fields_get()
        self.assertNotIn(admin_only, fields_)
        self.assertIn(everyone, fields_)
        partner = Partner.search([], limit=1)
        self.assertTrue(partner)
        with self.assertRaises(AccessError):
            partner.read([admin_only])
        partner.read([everyone])
        # a change of who sees it is a change of the field the ORM builds
        self.Studio.update_field('res.partner', admin_only, {'vis': 'all'})
        self.assertFalse(self.env['res.partner']._fields[admin_only].groups)
        self.assertIn(admin_only, self.env['res.partner'].with_user(user)
                      .fields_get())

    def test_06b_required_is_a_rule_of_the_screen(self):
        name = self.make('Visit code', required=True)
        self.assertFalse(self.env['res.partner']._fields[name].required)
        self.Studio.publish('res.partner', self.view.id, [{
            'id': 'req1', 'title': 'Codes', 'anchor': {'kind': 'before_notebook'},
            'fields': [{'name': name, 'order': 0}]}])
        node = self.combined().xpath("//field[@name='%s']" % name)[0]
        self.assertEqual(node.get('required'), '1')
        # a record made elsewhere is not refused
        self.env['res.partner'].create({'name': 'FS made elsewhere'})
        # switching it off draws the screen again, without the rule
        self.Studio.update_field('res.partner', name, {'required': False})
        node = self.combined().xpath("//field[@name='%s']" % name)[0]
        self.assertFalse(node.get('required'))

    def test_06c_health_information_is_never_a_list_column(self):
        name = self.make('Allergy note', 'text', phi=True, list_ok=True)
        meta = self.env['fs.field.meta'].search([('name', '=', name)])
        self.assertTrue(meta.phi)
        self.assertFalse(meta.list_ok)
        with self.assertRaises(ValidationError):
            meta.sudo().write({'list_ok': True})

    def test_07_rename_reaches_the_label_cache(self):
        """T7 — a rename shows at once in the cached field labels."""
        name = self.make('Old label')
        self.env['ir.model.fields'].get_field_string('res.partner')
        self.Studio.update_field('res.partner', name, {'label': 'New label'})
        strings = self.env['ir.model.fields'].get_field_string('res.partner')
        self.assertEqual(strings.get(name), 'New label')
        self.assertEqual(self.env['res.partner']._fields[name].string,
                         'New label')

    def test_07b_type_cannot_change(self):
        name = self.make('Count of visits', 'integer')
        with self.assertRaisesRegex(UserError, 'type cannot be changed'):
            self.Studio.update_field('res.partner', name, {'type': 'char'})


@tagged('post_install', '-at_install')
class TestFsLayouts(_FsCase):

    def _layout(self):
        return self.env['fs.layout'].search(
            [('model', '=', 'res.partner'),
             ('base_view_id', '=', self.view.id)])

    def test_08_publish_one_section(self):
        """T8 — one section of two fields: an extension view at priority 200,
        the group in the combined arch, version 1, history, chatter, no
        draft."""
        a, b = self.make('Alpha'), self.make('Beta')
        sections = [self.section('sec1', [a, b], 'Follow-up')]
        self.Studio.save_draft('res.partner', self.view.id, sections)
        res = self.Studio.publish('res.partner', self.view.id, sections,
                                  base_version=0)
        layout = self._layout()
        self.assertEqual(res['version'], 1)
        self.assertEqual(layout.version, 1)
        view = layout.view_id
        self.assertEqual(view.mode, 'extension')
        self.assertEqual(view.inherit_id, self.view)
        self.assertEqual(view.priority, 200)
        group = self.combined().xpath("//group[@name='fs_sec1']")
        self.assertEqual(len(group), 1)
        self.assertEqual([f.get('name') for f in group[0].iter('field')],
                         [a, b])
        self.assertEqual(group[0].get('string'), 'Follow-up')
        hist = self.env['fs.layout.history'].search(
            [('layout_id', '=', layout.id)])
        self.assertEqual(hist.mapped('version'), [1])
        self.assertTrue(any('Published version 1' in (m.body or '')
                            for m in layout.message_ids))
        self.assertFalse(self.env['fs.layout.draft'].search(
            [('layout_id', '=', layout.id)]))

    def test_08b_stale_version_is_refused(self):
        a = self.make('Alpha')
        sections = [self.section('sec1', [a])]
        self.Studio.publish('res.partner', self.view.id, sections)
        with self.assertRaisesRegex(UserError, 'newer version'):
            self.Studio.publish('res.partner', self.view.id, sections,
                                base_version=0)

    def test_08c_writer_refuses_a_field_that_does_not_exist(self):
        with self.assertRaises(UserError):
            self.Studio.publish('res.partner', self.view.id,
                                [self.section('sec1', ['x_fs_ghost'])])
        self.assertFalse(self._layout().view_id)

    def test_09_move_then_go_back(self):
        """T9 — a move makes version 2; going back to 1 republishes version
        1's arch exactly."""
        a, b = self.make('Alpha'), self.make('Beta')
        self.Studio.publish('res.partner', self.view.id,
                            [self.section('sec1', [a, b])])
        self.Studio.publish('res.partner', self.view.id,
                            [self.section('sec1', [b, a])])
        layout = self._layout()
        self.assertEqual(layout.version, 2)
        res = self.Studio.rollback(layout.id, 1)
        self.assertEqual(res['version'], 3)
        hist = {h.version: h for h in self.env['fs.layout.history'].search(
            [('layout_id', '=', layout.id)])}
        self.assertEqual(hist[3].arch, hist[1].arch)
        self.assertEqual(layout.view_id.arch_db.strip(), hist[1].arch.strip())

    def test_10_validator_switches_a_broken_layout_off(self):
        """T10 — an anchor that no longer exists: the layout switches its own
        view off, the screen still draws, the reason is kept."""
        a = self.make('Alpha')
        self.Studio.publish('res.partner', self.view.id,
                            [self.section('sec1', [a])])
        layout = self._layout()
        layout.sudo().write({'sections': [self.section(
            'sec1', [a], anchor={'kind': 'card', 'name': 'nope'})]})
        res = self.Studio.validate_all()
        self.assertGreaterEqual(res['checked'], 1)
        self.assertIn(layout.id, [b['layout_id'] for b in res['broken']])
        self.assertEqual(layout.state, 'broken')
        self.assertTrue(layout.broken_reason)
        self.assertFalse(layout.view_id.active)
        arch = self.combined()
        self.assertFalse(arch.xpath("//group[@name='fs_sec1']"))
        self.assertTrue(arch.xpath('//sheet'))

    def test_11_delete_field(self):
        """T11 — typed DELETE; a blocker is named; then the layout is
        republished without the field BEFORE the field goes; the count shown
        first is the real one."""
        a, b = self.make('Alpha'), self.make('Beta')
        self.Studio.publish('res.partner', self.view.id,
                            [self.section('sec1', [a, b])])
        partners = self.env['res.partner'].search([], limit=3)
        partners.write({a: 'kept'})
        expected = self.env['res.partner'].with_context(
            active_test=False).search_count([(a, '!=', False)])
        with self.assertRaisesRegex(UserError, 'DELETE'):
            self.Studio.delete_field('res.partner', a, confirm='delete')
        export = self.env['ir.exports'].create({
            'name': 'Partner sheet', 'resource': 'res.partner',
            'export_fields': [(0, 0, {'name': a})]})
        refs = self.Studio.field_references('res.partner', a)
        values = [r for r in refs if r['kind'] == 'values'][0]
        self.assertEqual(values['count'], expected)
        with self.assertRaisesRegex(UserError, 'Partner sheet'):
            self.Studio.delete_field('res.partner', a, confirm='DELETE')
        export.unlink()
        res = self.Studio.delete_field('res.partner', a, confirm='DELETE')
        self.assertEqual(res['count'], expected)
        arch = self.combined()
        self.assertFalse(arch.xpath("//field[@name='%s']" % a))
        self.assertTrue(arch.xpath("//field[@name='%s']" % b))
        self.assertNotIn(a, self.env['res.partner'].fields_get())
        self.assertEqual(self._layout().version, 2)

    def test_11b_history_is_append_only(self):
        a = self.make('Alpha')
        self.Studio.publish('res.partner', self.view.id,
                            [self.section('sec1', [a])])
        hist = self.env['fs.layout.history'].search(
            [('layout_id', '=', self._layout().id)])
        with self.assertRaises(UserError):
            hist.unlink()
        with self.assertRaises(UserError):
            hist.write({'version': 9})


@tagged('post_install', '-at_install')
class TestFsGate(_FsCase):

    def test_gate_and_probe(self):
        user = self.env['res.users'].create({
            'name': 'FS gate user', 'login': 'fs_gate_user',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        Studio = self.Studio.with_user(user)
        self.assertEqual(Studio.probe('res.partner', self.view.id),
                         {'host': False, 'can_edit': False})
        with self.assertRaises(AccessError):
            Studio.get_studio('res.partner', self.view.id)
        with self.assertRaises(AccessError):
            Studio.create_field('res.partner', {'type': 'char',
                                                'label': 'Nope'})
        # never raises, whatever it is asked
        self.assertFalse(self.Studio.probe('no.such.model', 1)['host'])
        self.assertFalse(self.Studio.probe('res.partner', False)['host'])
        self.assertTrue(self.Studio.probe('res.partner',
                                          self.view.id)['can_edit'])

    def test_get_studio_shape(self):
        data = self.Studio.get_studio('res.partner', self.view.id)
        for key in ('host', 'layout', 'draft', 'cards', 'fields',
                    'link_targets', 'types', 'history', 'can_publish'):
            self.assertIn(key, data)
        self.assertEqual(len(data['types']), 11)
        self.assertTrue(data['host']['has_notebook'])
        self.assertTrue(any(c['kind'] == 'notebook' for c in data['cards']))
        # FS-H2: the payload carries only the standard fields the schematic
        # draws (the partner form's title row is not a card, so `name` is not
        # among them any more), plus every Studio field
        std = {n for n, f in data['fields'].items() if f['std']}
        shown = {n for c in data['cards'] for n in c.get('fields') or []}
        self.assertTrue(std)
        self.assertEqual(std, shown)


# =========================================================================
#  T17–T26 — the Workspace kit (FS-H2)
# =========================================================================
#: A form shaped like a Workspace screen, on a neutral model: a header, one
#: tab holding a pack of two named cards and a trailing widget, a second tab.
WS_ARCH = """
<form>
  <sheet>
    <div class="ws-page">
      <div class="ws-main">
        <div class="ws-hero"><h1><field name="name"/></h1></div>
        <notebook>
          <page string="Overview" name="fsx_ov">
            <div class="ws-pack">
              <div class="vu-detail-card ws-card" name="first_card">
                <div class="vu-card__title">
                  <div class="vu-section__icon" data-icon="phone"/>
                  <div>First</div>
                </div>
                <group><field name="email"/></group>
              </div>
              <div class="vu-detail-card ws-card" name="second_card">
                <div class="vu-card__title">
                  <div class="vu-section__icon" data-icon="tag"/>
                  <div>Second</div>
                </div>
                <group><field name="phone"/></group>
              </div>
              <widget name="fsx_tail"/>
            </div>
          </page>
          <page string="More" name="fsx_more">
            <group><field name="ref"/></group>
          </page>
        </notebook>
      </div>
      <div class="fsx-rail" name="fsx_zone"/>
    </div>
  </sheet>
</form>
"""


class _FsWsCase(_FsCase):
    """A Workspace host on its own primary form of the neutral model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ws_view = cls.env['ir.ui.view'].create({
            'name': 'fsx workspace form', 'model': 'res.partner',
            'type': 'form', 'priority': 99, 'arch': WS_ARCH})
        cls.env['ir.model.data'].create({
            'module': 'biz_form_studio_test', 'name': 'fsx_ws_form',
            'model': 'ir.ui.view', 'res_id': cls.ws_view.id})
        cls.ws_host = cls.env['fs.host'].create({
            'name': 'Workspace test',
            'model': 'res.partner',
            'base_view_xmlid': 'biz_form_studio_test.fsx_ws_form',
            'kit': 'ws',
            'pack_page': 'fsx_ov',
            'sections': [{'name': 'first_card', 'title': 'First'}],
            'locked_zones': [{'name': 'fsx_zone', 'title': 'Rail',
                              'reason': 'Drawn by the system.'}],
        })

    def ws_combined(self, lang=None):
        view = self.ws_view.with_context(lang=lang) if lang else self.ws_view
        return etree.fromstring(view.get_combined_arch())

    def ws_publish(self, sections):
        return self.Studio.publish('res.partner', self.ws_view.id, sections)

    def ws_layout(self):
        return self.env['fs.layout'].search(
            [('model', '=', 'res.partner'),
             ('base_view_id', '=', self.ws_view.id)])

    def pack(self, arch):
        return arch.xpath("//page[@name='fsx_ov']/div[hasclass('ws-pack')]")[0]


@tagged('post_install', '-at_install')
class TestFsWorkspace(_FsWsCase):

    def test_17_pack_end_draws_a_workspace_card(self):
        """T17 — a `pack_end` section is a card like the pack's own, with the
        two tray attributes, placed INSIDE the pack when there is no tail."""
        a = self.make('Preferred slot')
        b = self.make('Lift code', required=True)
        self.ws_publish([self.section('p1', [a, b], 'Care preferences',
                                      anchor={'kind': 'pack_end'})])
        pack = self.pack(self.ws_combined())
        card = pack[-1]
        self.assertEqual(card.tag, 'div')
        self.assertEqual(card.get('name'), 'fs_p1')
        self.assertEqual(card.get('class'), 'vu-detail-card ws-card fs-card')
        self.assertEqual(card.get('data-fs-fold'), '1')
        self.assertEqual(card.get('data-fs-fields'), '%s,%s' % (a, b))
        title = card.xpath("./div[@class='vu-card__title']")[0]
        icon = title.xpath("./div[@class='vu-section__icon']")[0]
        self.assertEqual(icon.get('data-icon'), 'clipboard-list')
        self.assertEqual(title.xpath('./div')[-1].text, 'Care preferences')
        fields_ = card.xpath('./group/field')
        self.assertEqual([f.get('name') for f in fields_], [a, b])
        self.assertFalse(fields_[0].get('required'))
        self.assertEqual(fields_[1].get('required'), '1')
        self.assertEqual(fields_[0].get('placeholder'), '—')
        # the generated view anchors on the pack, inside
        arch = etree.fromstring(self.ws_layout().view_id.arch_db)
        xp = arch.xpath('//xpath')[0]
        self.assertEqual(xp.get('expr'),
                         "//page[@name='fsx_ov']/div[hasclass('ws-pack')]")
        self.assertEqual(xp.get('position'), 'inside')

    def test_18_with_a_tail_cards_go_before_it_in_order(self):
        """T18 — with `pack_tail`, every section is placed before the tail
        widget, in section order."""
        self.ws_host.pack_tail = 'fsx_tail'
        a, b = self.make('Alpha'), self.make('Beta')
        self.ws_publish([
            self.section('p1', [a], 'One', anchor={'kind': 'pack_end'}),
            self.section('p2', [b], 'Two', anchor={'kind': 'pack_end'})])
        pack = self.pack(self.ws_combined())
        names = [c.get('name') for c in pack]
        self.assertEqual(names, ['first_card', 'second_card', 'fs_p1', 'fs_p2',
                                 'fsx_tail'])
        arch = etree.fromstring(self.ws_layout().view_id.arch_db)
        for xp in arch.xpath('//xpath'):
            self.assertEqual(
                xp.get('expr'),
                "//page[@name='fsx_ov']/div[hasclass('ws-pack')]"
                "/widget[@name='fsx_tail']")
            self.assertEqual(xp.get('position'), 'before')

    def test_19_places_that_do_not_exist_on_the_kit_are_refused(self):
        """T19 — a Workspace screen has no "above the tabs" or "bottom"; a
        standard form has no pack; a Workspace host needs its pack tab."""
        a = self.make('Alpha')
        for kind in ('before_notebook', 'sheet_end'):
            with self.assertRaisesRegex(UserError, 'could not be read'):
                self.ws_publish([self.section('p1', [a],
                                              anchor={'kind': kind})])
        with self.assertRaisesRegex(UserError, 'could not be read'):
            self.Studio.publish('res.partner', self.view.id, [
                self.section('p1', [a], anchor={'kind': 'pack_end'})])
        with self.assertRaises(ValidationError):
            self.env['fs.host'].create({
                'model': 'res.partner',
                'base_view_xmlid': 'biz_form_studio_test.fsx_ws_form',
                'kit': 'ws'})
        with self.assertRaises(ValidationError):
            self.host.pack_page = 'fsx_ov'

    def test_20_a_field_in_an_open_card_marks_the_card(self):
        """T20 — dropping into an open card writes the field into its group
        AND lists it on the card for the tray."""
        a = self.make('Alpha')
        self.ws_publish([self.section(
            'c1', [a], anchor={'kind': 'card', 'name': 'first_card'})])
        arch = etree.fromstring(self.ws_layout().view_id.arch_db)
        self.assertEqual(
            [(x.get('expr'), x.get('position')) for x in arch.xpath('//xpath')],
            [("//div[@name='first_card']/group", 'inside'),
             ("//div[@name='first_card']", 'attributes')])
        combined = self.ws_combined()
        card = combined.xpath("//div[@name='first_card']")[0]
        self.assertEqual(card.get('data-fs-fields'), a)
        self.assertEqual([f.get('name') for f in card.xpath('./group/field')],
                         ['email', a])
        self.assertIsNone(card.get('data-fs-fold'))
        # a card the host did not open refuses
        with self.assertRaisesRegex(UserError, 'no longer accepts'):
            self.ws_publish([self.section(
                'c1', [a], anchor={'kind': 'card', 'name': 'second_card'})])

    def test_21_vietnamese_card_title_reaches_the_form(self):
        """T21 — the card title is a TEXT node; its Vietnamese wording is the
        view's translation of it, and the English source is untouched."""
        lang = self.env['res.lang']._lang_get('vi_VN')
        if not lang or not lang.active:
            self.skipTest('Vietnamese is not active')
        a = self.make('Alpha')
        sec = self.section('p1', [a], 'Care preferences',
                           anchor={'kind': 'pack_end'})
        sec['title_vi'] = 'Ưu tiên chăm sóc'
        self.ws_publish([sec])
        title = "//div[@name='fs_p1']/div[@class='vu-card__title']/div[last()]"
        self.assertEqual(self.ws_combined('vi_VN').xpath(title)[0].text,
                         'Ưu tiên chăm sóc')
        self.assertEqual(self.ws_combined('en_US').xpath(title)[0].text,
                         'Care preferences')
        en = etree.fromstring(self.ws_layout().view_id.with_context(
            lang='en_US').arch_db)
        self.assertIn('Care preferences', etree.tostring(en, encoding='unicode'))

    def test_22_the_schematic_reads_the_pack(self):
        """T22 — header card, pack marker, one card per named card of the pack
        (title text, open flag), Studio's own card skipped, end marker, the
        other tab as a tab card, the locked zone."""
        a = self.make('Alpha')
        self.ws_publish([self.section('p1', [a], 'Mine',
                                      anchor={'kind': 'pack_end'})])
        cards = self.Studio.get_studio('res.partner', self.ws_view.id)['cards']
        kinds = [c['kind'] for c in cards]
        self.assertEqual(kinds, ['std', 'notebook', 'pack', 'std', 'std',
                                 'pack_end', 'std', 'zone'])
        header, _nb, marker, first, second, _end, more, zone = cards
        self.assertEqual(header['fields'], ['name'])
        self.assertFalse(header['open'])
        self.assertEqual((marker['name'], marker['title']),
                         ('fsx_ov', 'Overview'))
        self.assertEqual((first['name'], first['title'], first['open'],
                          first['fields']),
                         ('first_card', 'First', True, ['email']))
        self.assertEqual((second['name'], second['title'], second['open']),
                         ('second_card', 'Second', False))
        self.assertTrue(more['tab'])
        self.assertEqual(more['name'], 'fsx_more')
        self.assertEqual(zone['name'], 'fsx_zone')
        self.assertNotIn('fs_p1', [c.get('name') for c in cards])
        data = self.Studio.get_studio('res.partner', self.ws_view.id)
        self.assertEqual(data['host']['kit'], 'ws')
        self.assertEqual(data['host']['pack_page'], 'fsx_ov')
        self.assertFalse(data['host']['has_notebook'])

    def test_23_the_fields_payload_holds_only_what_is_drawn(self):
        """T23 — standard fields: exactly those the schematic's cards list;
        plus every field made in Studio, placed or not."""
        a, b = self.make('Alpha'), self.make('Beta')
        self.ws_publish([self.section('p1', [a], 'Mine',
                                      anchor={'kind': 'pack_end'})])
        for view in (self.ws_view, self.view):
            data = self.Studio.get_studio('res.partner', view.id)
            shown = {n for c in data['cards'] for n in c.get('fields') or []}
            std = {n for n, f in data['fields'].items() if f['std']}
            self.assertEqual(std, shown)
            self.assertIn(a, data['fields'])
            self.assertIn(b, data['fields'])
            self.assertLess(len(data['fields']),
                            len(self.env['res.partner']._fields))

    def test_24_a_broken_pack_switches_the_layout_off(self):
        """T24 — the pack's tab is renamed underneath (as an upgrade would):
        the validator switches the layout off with a reason and the form
        still draws."""
        a = self.make('Alpha')
        self.ws_publish([self.section('p1', [a], 'Mine',
                                      anchor={'kind': 'pack_end'})])
        layout = self.ws_layout()
        renamed = WS_ARCH.replace('name="fsx_ov"', 'name="fsx_renamed"')
        # straight into the table: writing the form through the ORM would
        # re-check the layout's view against it and refuse
        self.env.cr.execute(
            "UPDATE ir_ui_view SET arch_db = jsonb_build_object('en_US', %s) "
            "WHERE id = %s", [renamed, self.ws_view.id])
        self.env.invalidate_all()
        res = self.Studio.validate_all()
        self.assertIn(layout.id, [b['layout_id'] for b in res['broken']])
        self.assertEqual(layout.state, 'broken')
        self.assertTrue(layout.broken_reason)
        self.assertFalse(layout.view_id.active)
        arch = self.ws_combined()
        self.assertTrue(arch.xpath("//page[@name='fsx_renamed']"))
        self.assertFalse(arch.xpath("//div[@name='fs_p1']"))

    def test_25_a_section_named_like_a_field_is_refused(self):
        """T25 — a Studio card is found on the page by `name="fs_<id>"`; an
        id whose card name is a field of the record type is refused."""
        Layout = self.env['fs.layout']
        self.assertIn('fs_vis', self.env['ir.model.fields']._fields)
        with self.assertRaisesRegex(UserError, 'already taken'):
            Layout._clean_sections([{'id': 'vis', 'title': 'T',
                                     'anchor': {'kind': 'before_notebook'},
                                     'fields': []}], 'ir.model.fields')
        self.assertTrue(Layout._clean_sections(
            [{'id': 'vix', 'title': 'T', 'anchor': {'kind': 'before_notebook'},
              'fields': []}], 'ir.model.fields'))

    def test_26_dropdown_options_in_vietnamese(self):
        """T26 — options carry a Vietnamese name as their own translation:
        English under en_US, Vietnamese under vi_VN, the English where none
        was given; changed later through `update_field`."""
        lang = self.env['res.lang']._lang_get('vi_VN')
        if not lang or not lang.active:
            self.skipTest('Vietnamese is not active')
        name = self.make('Preferred time slot', 'selection', options=[
            {'label': 'Morning', 'label_vi': 'Buổi sáng'},
            {'label': 'Afternoon', 'label_vi': 'Buổi chiều'},
            {'label': 'Evening'}])
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'res.partner'), ('name', '=', name)])
        rows = field.selection_ids.sorted('sequence')
        self.assertEqual(rows.with_context(lang='en_US').mapped('name'),
                         ['Morning', 'Afternoon', 'Evening'])
        self.assertEqual(rows.with_context(lang='vi_VN').mapped('name'),
                         ['Buổi sáng', 'Buổi chiều', 'Evening'])
        vi = dict(self.env['res.partner'].with_context(lang='vi_VN').fields_get(
            [name], ['selection'])[name]['selection'])
        self.assertEqual(vi[rows[0].value], 'Buổi sáng')
        self.assertEqual(vi[rows[2].value], 'Evening')
        en = dict(self.env['res.partner'].with_context(lang='en_US').fields_get(
            [name], ['selection'])[name]['selection'])
        self.assertEqual(en[rows[0].value], 'Morning')
        info = self.Studio.get_studio('res.partner', self.view.id)['fields'][name]
        self.assertEqual([o['label_vi'] for o in info['options']],
                         ['Buổi sáng', 'Buổi chiều', ''])
        # later: give Evening its Vietnamese, clear Afternoon's, add Night
        opts = [dict(o) for o in info['options']]
        opts[1]['label_vi'] = ''
        opts[2]['label_vi'] = 'Buổi tối'
        opts.append({'label': 'Night', 'label_vi': 'Ban đêm'})
        self.Studio.update_field('res.partner', name, {'options': opts})
        field.invalidate_recordset()
        rows = field.selection_ids.sorted('sequence')
        self.assertEqual(rows.with_context(lang='vi_VN').mapped('name'),
                         ['Buổi sáng', 'Afternoon', 'Buổi tối', 'Ban đêm'])
        self.assertEqual(rows.with_context(lang='en_US').mapped('name'),
                         ['Morning', 'Afternoon', 'Evening', 'Night'])
        vi = dict(self.env['res.partner'].with_context(lang='vi_VN').fields_get(
            [name], ['selection'])[name]['selection'])
        self.assertEqual(vi[rows[3].value], 'Ban đêm')


# =========================================================================
#  T12 — the source gates
# =========================================================================
_ROOT = get_module_path('biz_form_studio')


def _src(*parts):
    with open(os.path.join(_ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _all_sources():
    out = []
    for base, _dirs, files in os.walk(_ROOT):
        if '/tests' in base[len(_ROOT):] or '__pycache__' in base:
            continue
        for fn in files:
            if fn.endswith(('.py', '.js', '.xml', '.scss', '.csv')):
                out.append(os.path.join(base, fn))
    return out


@tagged('post_install', '-at_install')
class TestFsSourceGates(TransactionCase):
    """A generic core names no product, no industry, and draws no broken
    picture — read from the files, because a running test renders none."""

    BANNED = ('Payobook', 'payobook', 'Viet Uc', 'Việt Úc', 'health_',
              'Odoo', 'odoo.com', 'Carejiox', 'carejiox', 'clinic', 'Clinic',
              'nurse', 'Nurse', 'patient', 'Patient')
    ALLOWED = ('from odoo', 'import odoo', 'odoo.addons', 'odoo.exceptions',
               'odoo.tests', 'odoo.tools', 'odoo.modules', 'odoo.fields',
               'odoo-bin', '@odoo-module', '@odoo/owl', '/odoo/', '<odoo>',
               '</odoo>')

    def test_12a_no_product_or_industry_word_anywhere(self):
        """Comments included: a generic module whose comments name a product
        sends the next reader to files that do not exist."""
        for path in _all_sources() + [os.path.join(_ROOT, 'i18n', 'vi.po')]:
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            for allowed in self.ALLOWED:
                text = text.replace(allowed, '')
            for word in self.BANNED:
                self.assertNotIn(word, text, '%s contains "%s"'
                                 % (os.path.relpath(path, _ROOT), word))

    def test_12b_every_icon_is_in_the_shared_registry(self):
        path = get_module_path('biz_kit')
        with open(path + '/static/src/js/kit_icons.js', encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('wandSparkles', known)
        used = set()
        for path in _all_sources():
            text = open(path, encoding='utf-8').read()
            used |= set(re.findall(r"""ic\(['"]([A-Za-z0-9_]+)['"]""", text))
            used |= set(re.findall(r"""icon:\s*['"]([A-Za-z0-9_]+)['"]""", text))
        from odoo.addons.biz_form_studio.models.fs_studio import (
            OTHER_TYPE_INFO, TYPE_INFO)
        used |= {info[2] for info in TYPE_INFO.values()}
        used |= {info[1] for info in OTHER_TYPE_INFO.values()}
        self.assertTrue(used)
        for name in sorted(used):
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry" % name)

    def test_12c_no_fire_and_forget_promise_in_onwillstart(self):
        """§5.127(c): a `.then(` with no `.catch(` in `onWillStart` turns an
        access error into a modal on a screen that works."""
        for path in _all_sources():
            if not path.endswith('.js'):
                continue
            text = open(path, encoding='utf-8').read()
            for match in re.finditer(r'onWillStart\(', text):
                body = text[match.end():match.end() + 600]
                body = body.split('\n    });', 1)[0]
                if '.then(' in body:
                    self.assertIn('.catch(', body, '%s: onWillStart has a '
                                  '.then( with no .catch(' % path)

    def test_12d_no_font_family_and_no_clamped_calc(self):
        scss = _src('static', 'src', 'scss', 'studio.scss')
        code = re.sub(r'//[^\n]*', '', scss)
        self.assertNotIn('font-family', code)
        self.assertFalse(re.search(r'(min|max)\([^;]*calc\(', code),
                         'min()/max() around calc() breaks the bundle (§5.148)')
        self.assertNotIn('gradient', code)

    def test_12e_no_adjacent_strings_and_no_reserved_loop_names(self):
        rx = re.compile(r"""["']\s*\n\s*["']""")
        reserved = {'lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'}
        for path in _all_sources():
            text = open(path, encoding='utf-8').read()
            if path.endswith('.js'):
                self.assertFalse(rx.search(text), '%s: two adjacent string '
                                 'literals across a newline' % path)
            if path.endswith('.xml'):
                for name in re.findall(r't-as="(\w+)"', text):
                    self.assertNotIn(name, reserved, path)

    def test_12f_studio_button_anchors_on_the_cog(self):
        xml = _src('static', 'src', 'xml', 'studio_button.xml')
        self.assertIn('web.FormView', xml)
        self.assertIn("control-panel-additional-actions']/CogMenu", xml)
        self.assertIn('o_fs_studio_btn', xml)
        self.assertNotIn('StatusBarButtons', xml)

    def test_27_one_button_template_for_every_header(self):
        """T27 — the button's markup is ONE named template, called from the
        cog slot and callable from a product's own top bar; the gates above
        run over every FS-H2 file too."""
        xml = etree.fromstring(_src('static', 'src', 'xml',
                                    'studio_button.xml').encode())
        named = xml.xpath("//t[@t-name='biz_form_studio.StudioButton']")
        self.assertEqual(len(named), 1)
        self.assertEqual(len(named[0].xpath(".//button[contains(@class, "
                                            "'o_fs_studio_btn')]")), 1)
        calls = xml.xpath("//t[@t-inherit='web.FormView']"
                          "//t[@t-call='biz_form_studio.StudioButton']")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(xml.xpath('//button')), 1)
        sources = {os.path.relpath(p, _ROOT) for p in _all_sources()}
        for rel in ('models/fs_layout.py', 'models/fs_studio.py',
                    'models/fs_host.py', 'static/src/js/studio/studio_editor.js',
                    'static/src/xml/studio/studio_editor.xml'):
            self.assertIn(rel, sources)
