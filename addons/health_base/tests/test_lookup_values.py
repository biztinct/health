# -*- coding: utf-8 -*-
"""Tier-1 dropdown vocabularies: the Selection -> Many2one conversion.

Client spec under test:
  * Every one of the twenty-four converted dropdowns is now a table the client
    can add to, rename, translate and reorder — without a developer.
  * Nothing was lost in the conversion: every option that existed as a
    Selection value exists as a lookup row with the SAME code.
  * A value that records still point at cannot be deleted, only archived.
  * One spreadsheet, one sheet per dropdown, round-trips: download, edit,
    re-upload updates instead of duplicating.

The first three tests iterate lookup_registry, so a vocabulary added later is
covered the moment it is declared.
"""
import base64
import io

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_base.lookup_registry import CATEGORIES, CONVERSIONS


@tagged('post_install', '-at_install')
class TestLookupValues(TransactionCase):

    # ------------------------------------------------------------------
    # Conversion completeness
    # ------------------------------------------------------------------
    def test_01_every_vocabulary_is_seeded(self):
        Category = self.env['health.lookup.category'].with_context(active_test=False)
        missing = [code for code in CATEGORIES
                   if not Category.search_count([('code', '=', code)])]
        self.assertFalse(missing, 'vocabularies never seeded: %s' % missing)

    def test_02_every_option_survived_with_its_code(self):
        """No option may be dropped: the codes are the migration's identity."""
        Value = self.env['health.lookup.value'].with_context(active_test=False)
        lost = []
        for category_code, spec in CATEGORIES.items():
            have = set(Value.search(
                [('category_code', '=', category_code)]).mapped('code'))
            for value_code, _en, _vi in spec['values']:
                if value_code not in have:
                    lost.append('%s.%s' % (category_code, value_code))
        self.assertFalse(lost, 'options lost in conversion: %s' % lost)

    def test_03_every_converted_field_is_a_lookup_many2one(self):
        wrong = []
        for model_name, old, new, category_code, _module in CONVERSIONS:
            if model_name not in self.env:
                continue
            field = self.env[model_name]._fields.get(new)
            if not field or field.type != 'many2one' \
                    or field.comodel_name != 'health.lookup.value':
                wrong.append('%s.%s' % (model_name, new))
                continue
            # The old Selection must be gone, or both would show on the form.
            if self.env[model_name]._fields.get(old) is not None:
                wrong.append('%s.%s (old field still declared)' % (model_name, old))
        self.assertFalse(wrong, 'not converted correctly: %s' % wrong)

    def test_04_domain_pins_each_field_to_its_own_vocabulary(self):
        """A dropdown must not offer another dropdown's values."""
        for model_name, _old, new, category_code, _module in CONVERSIONS:
            if model_name not in self.env:
                continue
            domain = self.env[model_name]._fields[new].domain
            self.assertIn(
                "'%s'" % category_code, str(domain),
                '%s.%s is not filtered to the %s vocabulary'
                % (model_name, new, category_code))

    # ------------------------------------------------------------------
    # Client management
    # ------------------------------------------------------------------
    def test_05_client_can_add_a_value_to_a_shipped_vocabulary(self):
        category = self.env['health.lookup.category'].search(
            [('code', '=', 'referral_source_type')], limit=1)
        value = self.env['health.lookup.value'].create({
            'category_id': category.id,
            'code': 'tiktok_probe',
            'name': 'TikTok',
            'name_vi': 'TikTok VN',
        })
        source = self.env['health.referral.source'].create({
            'name': 'Probe Source', 'source_type_id': value.id})
        self.assertEqual(source.source_type_id.code, 'tiktok_probe')
        self.assertEqual(
            value.with_context(lang='vi_VN').name, 'TikTok VN',
            'the Vietnamese label must go into the translation, not a column')

    def test_06_value_in_use_cannot_be_deleted_only_archived(self):
        category = self.env['health.lookup.category'].search(
            [('code', '=', 'referral_source_type')], limit=1)
        value = self.env['health.lookup.value'].create({
            'category_id': category.id, 'code': 'probe_del', 'name': 'Probe Delete'})
        self.env['health.referral.source'].create({
            'name': 'Probe Guard Source', 'source_type_id': value.id})
        self.assertEqual(value.usage_count, 1)
        with self.assertRaises(UserError):
            value.unlink()
        value.active = False
        self.assertFalse(value.active, 'archiving must remain available')

    def test_07_unused_value_can_be_deleted(self):
        category = self.env['health.lookup.category'].search(
            [('code', '=', 'referral_source_type')], limit=1)
        value = self.env['health.lookup.value'].create({
            'category_id': category.id, 'code': 'probe_unused', 'name': 'Unused'})
        self.assertEqual(value.usage_count, 0)
        value.unlink()

    def test_08_code_is_unique_within_a_vocabulary_only(self):
        """Two vocabularies may both have an 'other'; one may not have two."""
        Value = self.env['health.lookup.value']
        first = self.env['health.lookup.category'].search(
            [('code', '=', 'referral_source_type')], limit=1)
        second = self.env['health.lookup.category'].search(
            [('code', '=', 'symptom_category')], limit=1)
        a = Value.create({'category_id': first.id, 'code': 'dup_probe', 'name': 'A'})
        b = Value.create({'category_id': second.id, 'code': 'dup_probe', 'name': 'B'})
        self.assertNotEqual(a.id, b.id)
        with self.assertRaises(Exception):
            with self.cr.savepoint():
                Value.create({'category_id': first.id, 'code': 'dup_probe', 'name': 'C'})

    # ------------------------------------------------------------------
    # Spreadsheet round trip
    # ------------------------------------------------------------------
    def test_09_template_has_one_sheet_per_vocabulary(self):
        openpyxl = self._openpyxl()
        wizard = self.env['health.lookup.import.wizard'].create({})
        wizard.action_download_template()
        book = openpyxl.load_workbook(
            io.BytesIO(base64.b64decode(wizard.template_file)))
        expected = self.env['health.lookup.category'].with_context(
            active_test=False).search_count([])
        self.assertEqual(len(book.sheetnames), expected)
        sheet = book[book.sheetnames[0]]
        header = [c.value for c in next(sheet.iter_rows(min_row=1, max_row=1))]
        self.assertEqual(header[:3], ['code', 'name', 'name_vi'])

    def test_10_reupload_updates_instead_of_duplicating(self):
        """The classic spreadsheet failure — guarded by matching on code."""
        openpyxl = self._openpyxl()
        category = self.env['health.lookup.category'].search(
            [('code', '=', 'referral_source_type')], limit=1)
        Value = self.env['health.lookup.value'].with_context(active_test=False)
        before = Value.search_count([('category_id', '=', category.id)])

        book = openpyxl.Workbook()
        book.remove(book.active)
        sheet = book.create_sheet(title=category.name[:31])
        sheet.append(['code', 'name', 'name_vi', 'sequence', 'active'])
        sheet.append(['facebook', 'Facebook Renamed', 'Facebook VN', 5, 'yes'])
        sheet.append(['brand_new_probe', 'Brand New', 'Hoàn toàn mới', 99, 'yes'])
        stream = io.BytesIO()
        book.save(stream)
        payload = base64.b64encode(stream.getvalue())

        for _pass in range(2):
            wizard = self.env['health.lookup.import.wizard'].create({
                'file': payload, 'filename': 'probe.xlsx'})
            wizard.action_import()

        after = Value.search_count([('category_id', '=', category.id)])
        self.assertEqual(after, before + 1,
                         'importing twice must not create the row twice')
        renamed = Value.search([('category_id', '=', category.id),
                                ('code', '=', 'facebook')])
        self.assertEqual(renamed.with_context(lang='en_US').name, 'Facebook Renamed')
        self.assertEqual(renamed.with_context(lang='vi_VN').name, 'Facebook VN',
                         'name_vi column must land in the vi_VN translation')

    def test_11_unknown_sheet_is_reported_not_silently_dropped(self):
        openpyxl = self._openpyxl()
        book = openpyxl.Workbook()
        book.active.title = 'Not A Vocabulary'
        book.active.append(['code', 'name'])
        book.active.append(['x', 'X'])
        stream = io.BytesIO()
        book.save(stream)
        wizard = self.env['health.lookup.import.wizard'].create({
            'file': base64.b64encode(stream.getvalue()), 'filename': 'p.xlsx'})
        wizard.action_import()
        self.assertIn('SKIPPED', wizard.log)
        self.assertIn('Not A Vocabulary', wizard.log)

    def _openpyxl(self):
        try:
            import openpyxl
        except ImportError:  # pragma: no cover
            self.skipTest('openpyxl not installed')
        return openpyxl


@tagged('post_install', '-at_install')
class TestTier2Conversions(TransactionCase):
    """Tier 2: fields whose VALUES python compared.

    The distinguishing risk here is not the dropdown, it is the code that used
    to branch on the string. Each converted model gained a `<field>_code`
    related field and every comparison now reads that — these tests pin the
    contract so a later refactor cannot quietly break it.
    """

    TIER2 = [
        ('health.client.relation', 'relationship_type_id', 'relationship_type'),
        ('crm.lead', 'mode_of_contact_id', 'mode_of_contact'),
        ('hr.employee', 'employment_type_id', 'employment_type'),
        ('hr.employee', 'availability_status_id', 'availability_status'),
        ('health.clinical.protocol', 'complexity_level_id', 'complexity_level'),
        ('health.clinical.protocol', 'infection_control_level_id', 'infection_control_level'),
        ('health.medication.order', 'route_id', 'route'),
        ('advanced.pricing.rule', 'holiday_type_id', 'holiday_type'),
        ('advanced.pricing.rule', 'service_location_id', 'service_location'),
        ('resource.calendar.leaves', 'holiday_type_id', 'holiday_type'),
        ('care.contact.capture', 'reason_id', 'reason'),
        ('health.lead.touchpoint', 'touchpoint_type_id', 'touchpoint_type'),
        ('health.consent', 'consent_type_id', 'consent_type'),
    ]

    def test_01_every_tier2_field_has_a_code_companion(self):
        """Without it, view expressions and domains cannot see the value."""
        missing = []
        for model, new, old in self.TIER2:
            if model not in self.env:
                continue
            code_field = self.env[model]._fields.get('%s_code' % old)
            if not code_field or code_field.type != 'char':
                missing.append('%s.%s_code' % (model, old))
        self.assertFalse(missing, 'no code companion on: %s' % missing)

    def test_02_code_companion_reads_through_to_the_value(self):
        consent_type = self.env['health.lookup.value'].search(
            [('category_code', '=', 'consent_type'), ('code', '=', 'service')], limit=1)
        self.assertTrue(consent_type, 'the consent_type vocabulary was not seeded')
        patient = self.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'T2 Probe Client', 'is_patient': True,
            # The client's own rule: a patient needs a catchment province
            # before an ID can be generated.
            'catchment_province_id': self.env['health.catchment.province'].search(
                [], limit=1).id})
        consent = self.env['health.consent'].create({
            'client_id': patient.id, 'consent_type_id': consent_type.id})
        self.assertEqual(consent.consent_type_code, 'service',
                         'python comparisons read the _code companion')

    def test_03_code_companion_is_searchable(self):
        """Domains like [('consent_type_code','=','service')] must still work.

        This is load-bearing: `health.consent.check_consent()` — the interface
        the whole clinical spine calls — searches on exactly this. If a
        non-stored related field were not searchable it would silently match
        nothing and deny every consent check.
        """
        consent_type = self.env['health.lookup.value'].search(
            [('category_code', '=', 'consent_type'), ('code', '=', 'service')], limit=1)
        patient = self.env['res.partner'].with_context(skip_auto_geocode=True).create({
            'name': 'T2 Search Probe', 'is_patient': True,
            'catchment_province_id': self.env['health.catchment.province'].search(
                [], limit=1).id})
        made = self.env['health.consent'].create({
            'client_id': patient.id, 'consent_type_id': consent_type.id})
        found = self.env['health.consent'].search(
            [('consent_type_code', '=', 'service'), ('id', '=', made.id)])
        self.assertEqual(found, made,
                         'the code companion is not searchable — check_consent '
                         'would deny everything')

    def test_04_symptom_urgency_points_at_the_urgency_model(self):
        """Not a parallel vocabulary — urgency already had its own model."""
        field = self.env['health.symptom']._fields.get('urgency_level_id')
        self.assertTrue(field, 'health.symptom.urgency_level_id is missing')
        self.assertEqual(field.comodel_name, 'health.urgency.level')

    def test_05_shared_vocabularies_are_actually_shared(self):
        """holiday_type backs two models; service_location backs two more."""
        for category, models in (
                ('holiday_type', ('advanced.pricing.rule', 'resource.calendar.leaves')),
                ('service_location', ('advanced.pricing.rule', 'product.template'))):
            for model in models:
                if model not in self.env:
                    continue
                field = next((f for f in self.env[model]._fields.values()
                              if f.comodel_name == 'health.lookup.value'
                              and category in str(f.domain)), None)
                self.assertTrue(
                    field, '%s does not draw from the %s vocabulary' % (model, category))
