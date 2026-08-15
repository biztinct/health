# -*- coding: utf-8 -*-
"""Vietnamese lookup names live in the vi_VN translation of `name`.

Client spec under test:
  * A lookup's name can hold both an English and a Vietnamese value, chosen by
    the reader's language — that is what makes the value show up correctly in
    the many2one dropdowns on every other form.
  * The legacy `name_vi` / `name_vietnamese` fields still read and write, but
    they are now a mirror of that translation rather than a second column, so
    the two can no longer drift.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestViAliasMixin(TransactionCase):

    # The lookups exercised below belong to health_crm / health_fieldservice /
    # product. They are part of every deployment of this system, but the mixin
    # itself ships in health_base, so skip rather than error if a stripped
    # install runs these.
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        missing = [m for m in ('health.contact.reason', 'health.lead.reason',
                               'health.province') if m not in cls.env]
        if missing:
            raise cls.skipTest(cls, 'health_crm not installed: %s' % missing)


    def test_01_lookup_name_is_translatable(self):
        """Every Master Data lookup must be able to hold a Vietnamese name."""
        should_translate = [
            'health.referral.source', 'health.insurance.provider',
            'health.vietnamese.district', 'health.catchment.province',
            'health.contact.reason', 'health.lead.reason', 'health.province',
            'health.fieldservice.team', 'health.clinical.protocol',
            'product.category',
        ]
        plain = [m for m in should_translate
                 if m in self.env and not self.env[m]._fields['name'].translate]
        self.assertFalse(
            plain, 'these lookups cannot hold a Vietnamese name: %s' % plain)

    def test_02_writing_vi_translation_does_not_touch_english(self):
        reason = self.env['health.contact.reason'].create({
            'name': 'VI Probe Reason',
        })
        reason.with_context(lang='vi_VN').name = 'Lý do thử nghiệm'
        self.assertEqual(reason.with_context(lang='en_US').name, 'VI Probe Reason')
        self.assertEqual(reason.with_context(lang='vi_VN').name, 'Lý do thử nghiệm')

    def test_03_alias_reads_the_vi_translation(self):
        reason = self.env['health.contact.reason'].create({
            'name': 'VI Probe Alias Read',
        })
        reason.with_context(lang='vi_VN').name = 'Đọc bí danh'
        self.assertEqual(reason.name_vietnamese, 'Đọc bí danh')

    def test_04_alias_writes_the_vi_translation(self):
        reason = self.env['health.lead.reason'].create({
            'name': 'VI Probe Alias Write',
            'name_vietnamese': 'Ghi bí danh',
        })
        self.assertEqual(reason.with_context(lang='vi_VN').name, 'Ghi bí danh')
        self.assertEqual(
            reason.with_context(lang='en_US').name, 'VI Probe Alias Write')

    def test_05_alias_falls_back_to_english_when_untranslated(self):
        reason = self.env['health.lead.reason'].create({
            'name': 'VI Probe Untranslated',
        })
        self.assertEqual(reason.name_vietnamese, 'VI Probe Untranslated')

    def test_06_blanking_the_alias_does_not_delete_the_translation(self):
        """Seed files omit the alias for English-only rows; that must not wipe
        a Vietnamese name a user has already typed."""
        reason = self.env['health.lead.reason'].create({
            'name': 'VI Probe Keep',
            'name_vietnamese': 'Giữ lại',
        })
        reason.name_vietnamese = False
        self.assertEqual(reason.with_context(lang='vi_VN').name, 'Giữ lại')

    def test_07_dropdown_label_follows_the_users_language(self):
        """The point of the whole exercise: display_name, which is what a
        many2one renders, must come back in Vietnamese."""
        province = self.env['health.province'].create({
            'name': 'VI Probe Province',
            'code': 'VIP',
            # region became a lookup Many2one in the Tier-1 conversion.
            'region_id': self.env['health.lookup.value']._default_for(
                'vn_region', 'south'),
            'name_vietnamese': 'Tỉnh thử nghiệm',
        })
        vi_label = province.with_context(lang='vi_VN').display_name
        self.assertIn('Tỉnh thử nghiệm', vi_label)
        self.assertNotIn('VI Probe Province',
                         province.with_context(lang='vi_VN').name)
