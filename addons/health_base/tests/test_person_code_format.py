# -*- coding: utf-8 -*-
"""Client / contact identifier numbering — format `PP 0000YY`.

Client spec under test:
  * PP  = 2-digit province code taken from the catchment province.
  * 0000 = per-province, per-year sequence, 4 digits with leading zeros,
    giving 9,999 enrolments per province per year.
  * YY  = 2-digit calendar year (e.g. `02 088126`), NOT the 4-digit year the
    previous format used.
  * Clients and CRM contacts draw from the SAME sequence, so a lead that
    converts to a client keeps its identifier.
  * Codes issued under the old `PP 00000YYYY` format are never rewritten.
"""
import re
from datetime import datetime

from odoo.tests import TransactionCase, tagged

CODE_RE = re.compile(r'^(\d{2}) (\d{4})(\d{2})$')


@tagged('post_install', '-at_install')
class TestPersonCodeFormat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.year = datetime.now().year
        cls.province = cls.env['health.catchment.province'].create({
            'name': 'Code Format Probe Province',
            'code': '77',
        })

    def _seq(self):
        return self.env['ir.sequence'].sudo().search(
            [('code', '=', 'patient.77.%s' % self.year)], limit=1)

    def test_01_shape_is_pp_space_four_digits_two_digit_year(self):
        code = self.env['res.partner']._generate_person_code(self.province)
        match = CODE_RE.match(code)
        self.assertTrue(match, "%r is not PP 0000YY" % code)
        self.assertEqual(match.group(1), '77')
        self.assertEqual(match.group(3), '%02d' % (self.year % 100))

    def test_02_sequence_is_created_with_padding_four(self):
        self.env['res.partner']._generate_person_code(self.province)
        self.assertEqual(self._seq().padding, 4)

    def test_03_pre_existing_five_digit_sequence_is_repadded(self):
        """A sequence left over from the PP 00000YYYY era must narrow to 4."""
        self.env['res.partner']._generate_person_code(self.province)
        seq = self._seq()
        seq.padding = 5
        code = self.env['res.partner']._generate_person_code(self.province)
        self.assertEqual(seq.padding, 4)
        self.assertTrue(CODE_RE.match(code), "%r is not PP 0000YY" % code)

    def test_04_numbers_increment_within_the_province_year(self):
        first = CODE_RE.match(
            self.env['res.partner']._generate_person_code(self.province))
        second = CODE_RE.match(
            self.env['res.partner']._generate_person_code(self.province))
        self.assertEqual(int(second.group(2)), int(first.group(2)) + 1)

    def test_05_unknown_province_falls_back_to_99(self):
        code = self.env['res.partner']._generate_person_code(None)
        self.assertTrue(code.startswith('99 '), code)
        self.assertTrue(CODE_RE.match(code), "%r is not PP 0000YY" % code)

    def test_06_client_created_as_patient_gets_the_new_format(self):
        partner = self.env['res.partner'].with_context(
            skip_auto_geocode=True).create({
                'name': 'Code Format Probe Client',
                'is_patient': True,
                'catchment_province_id': self.province.id,
            })
        self.assertTrue(partner.patient_code, 'no client ID was assigned')
        self.assertTrue(CODE_RE.match(partner.patient_code),
                        "%r is not PP 0000YY" % partner.patient_code)

    def test_07_existing_old_format_codes_are_left_alone(self):
        """Writing a partner must not rewrite a legacy PP 00000YYYY code."""
        partner = self.env['res.partner'].with_context(
            skip_auto_geocode=True).create({
                'name': 'Legacy Code Probe',
                'is_patient': True,
                'catchment_province_id': self.province.id,
            })
        partner.sudo().patient_code = '77 000012019'
        partner.write({'comment': 'touched'})
        self.assertEqual(partner.patient_code, '77 000012019')
