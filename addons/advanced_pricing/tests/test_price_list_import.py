# -*- coding: utf-8 -*-
"""Price list upload (2026-09 CRM price input layout) and the condition
warnings it feeds. The workbook is built in memory with the real headers so
the test fails if the header-driven reader drifts from the client's sheets."""
import base64
import io

import openpyxl

from odoo.tests import common, tagged

from odoo.addons.advanced_pricing.wizards.pricing_import_wizard import (
    CONDITION_PHRASES_EN, CONDITION_PHRASES_VI, read_condition)

BASE_HEADER = [
    'row_order', 'province', 'item_code', 'service_class_vi', 'service_class_en',
    'main_service_vi', 'main_service_en', 'marketing_service_line_vi',
    'marketing_service_line_en', 'item_group_vi', 'item_group_en',
    'item_description_vi', 'item_description_en', 'unit_vi', 'unit_en',
    'base_fee_vnd', 'currency', 'rounding_rule', 'item_active', 'valid_from',
    'valid_to', 'price_version', 'last_updated_by', 'last_updated_on',
    'reason_for_change',
]
ADJ_HEADER = [
    'Region', 'Adjustment Applies to this item_code',
    'Adjustment Applies to this item_name_vi', 'Adjustment Applies to this item_name_en',
    'Trigger Condition vi', 'Trigger Condition en', 'Adjustment_Type_vi',
    'Adjustment_Type_en', 'Adjustment_Value', 'Data_Required_vi', 'Data_Required_en',
    'Calc_Seq', 'Trigger_Source_vi', 'Trigger_Source_en', 'Notes_vi', 'Notes_en',
]


def _svc(code, cls, main, name_vi, name_en, unit_vi, unit_en, fee, rounding='Round up to next 1,000'):
    cls_vi = {'Doctor Service': 'DV Bs', 'Nurse Service': 'DV ĐD', 'Service Fee': 'Phí dịch vụ'}[cls]
    return [1, 'HANOI', code, cls_vi, cls, main + ' VI', main, main + ' VI', main,
            'Nhóm', 'Group', name_vi, name_en, unit_vi, unit_en, fee, 'VND', rounding,
            True, '2026-04-01', None, 'T4.2026', None, None, None]


SERVICES = [
    _svc('bs_020', 'Doctor Service', 'Medical Exam & Treatment', 'Khám tại PK',
         'Doctor examination at clinic', 'Lần', 'per_service', 400000),
    _svc('đd_050', 'Nurse Service', 'Wound Care', 'Thay băng <5cm', 'Wound care <5cm',
         'VT', 'per_wound', 200000),
    _svc('đd_160', 'Nurse Service', 'Injections & IV', 'Truyền ≥2 giờ', 'Infusion ≥2 hours',
         'Giờ', 'per_hour', 130000, 'Round partial hour up to next 30 minutes'),
    _svc('đd_280', 'Nurse Service', 'ADL Care', 'CSCN ban ngày', 'ADL care daytime (minimum 3 hours)',
         'Giờ', 'per_hour', 110000, 'Round partial hour up to next 1 hour'),
    _svc('bs_150', 'Service Fee', 'Service Fee', 'Phụ phí ngoài giờ BS',
         'After-hours consultation surcharge – Doctor', 'Lần', 'per_service', 150000),
    _svc('đd_330', 'Service Fee', 'Service Fee', 'Phụ phí cuối tuần',
         'Weekend medical service surcharge', 'Lần', 'per_service', 100000),
    _svc('đd_350', 'Service Fee', 'Service Fee', 'Phí đi lại >8km',
         'Home medical service travel fee (Over 8 km)', 'Km', 'per_km', 15000),
]


def _adj(code, cond_vi, cond_en, type_vi, type_en, value, seq=10):
    return ['HANOI', code, None, None, cond_vi, cond_en, type_vi, type_en, value,
            None, None, seq, 'Đặt lịch', 'Booking', None, None]


RULES = [
    _adj('đd_050', 'Từ vết thương thứ 2 trở đi', 'From second wound onward', 'cộng', 'add', 50000),
    _adj('đd_280', 'Tối thiểu 3 giờ', 'Minimum 3 hours', 'điều kiện', 'eligibility', 3, 0),
    _adj('bs_150', 'Trước 8h; 12h–13h; sau 17h', 'Before 08:00; 12:00–13:00; after 17:00',
         'điều kiện', 'eligibility', 0, 0),
    _adj('bs_150', 'Không áp dụng: truyền ≥2h, chăm sóc cá nhân',
         'Not applicable: infusion ≥2h, ADL care', 'loại trừ', 'exclude', 0, 1),
    _adj('đd_330', 'Thứ 7/Chủ Nhật và khách hàng mới phát sinh',
         'Saturday/Sunday and newly arising client', 'điều kiện', 'eligibility', 0, 0),
    _adj('đd_350', 'Từ km thứ 8 trở đi, mỗi km phát sinh', 'Beyond 8km, per additional km',
         'điều kiện', 'eligibility', 0, 0),
    _adj('ALL', 'Khách hàng là người nước ngoài', 'Foreign customer', 'nhân', 'multiply', 1.5, 90),
    _adj('ALL_NURSE', 'Từ khách hàng thứ 2, cùng địa điểm/thời gian, cùng điều dưỡng',
         'From second client, same place/time, same nurse', 'giảm phần trăm',
         'percentage discount', 10, 110),
    _adj('bs_020', 'Mỗi thứ Ba', 'Every other Tuesday', 'cộng', 'add', 1000),
]


def _workbook(services=SERVICES, rules=RULES):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Hanoi_Base_Clean_v3'
    ws.append(BASE_HEADER)
    for row in services:
        ws.append(row)
    ws.append([None] * len(BASE_HEADER))          # trailing blank row
    ws2 = wb.create_sheet('Hanoi_Adjustments_Clean')
    ws2.append(ADJ_HEADER)
    for row in rules:
        ws2.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue())


@tagged('post_install', '-at_install')
class TestPriceListImport(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('health_base.group_healthcare_owner')
        cls.engine = cls.env['advanced.pricing.engine'].create({'name': 'Test Engine'})

    def _import(self, data=None, check_only=False, **kw):
        wiz = self.env['advanced.pricing.import.wizard'].create(dict({
            'file': data or _workbook(), 'filename': 'Hanoi.xlsx',
            'engine_id': self.engine.id, 'approve_rules': True}, **kw))
        (wiz.action_check if check_only else wiz.import_rules)()
        return wiz

    def _svc(self, code):
        return self.env['product.template'].with_context(active_test=False).search(
            [('default_code', '=', code + '_hanoi')])

    def _rules(self, code):
        return self.engine.with_context(active_test=False).rule_ids.filtered(
            lambda r: r.item_code == code)

    # -- reading sentences -------------------------------------------------
    def test_reader_understands_and_refuses(self):
        vals, left = read_condition('Night time 19:00–07:00', CONDITION_PHRASES_EN)
        self.assertEqual((vals, left), ({'time_windows': '19:00-07:00'}, ''))
        vals, left = read_condition('Distance 5–8km', CONDITION_PHRASES_EN)
        self.assertEqual(vals, {'distance_min': 5.0, 'distance_max': 8.0})
        self.assertFalse(left, "a distance range must not be read as a time")
        vals, left = read_condition('Ban đêm 19h–7h', CONDITION_PHRASES_VI)
        self.assertEqual((vals, left), ({'time_windows': '19:00-07:00'}, ''))
        vals, left = read_condition('Every other Tuesday', CONDITION_PHRASES_EN)
        self.assertTrue(left)

    # -- services ----------------------------------------------------------
    def test_services_categories_units_translations(self):
        self._import()
        adl = self._svc('đd_280')
        self.assertEqual(adl.list_price, 110000)
        self.assertEqual(adl.price_item_code, 'đd_280')
        self.assertEqual(adl.uom_id, self.env.ref('uom.product_uom_hour'))
        self.assertEqual(adl.rounding_rule, 'round_partial_hour')
        self.assertEqual(adl.with_context(lang='en_US').categ_id.complete_name,
                         'Nurse Service / ADL Care')
        self.assertEqual(adl.categ_id.parent_id.with_context(lang='vi_VN').name, 'DV ĐD')
        self.assertEqual(adl.price_version, 'T4.2026')
        if self.env['res.lang']._lang_get('vi_VN'):
            self.assertEqual(adl.with_context(lang='vi_VN').name, 'CSCN ban ngày')
        self.assertEqual(adl.with_context(lang='en_US').name, 'ADL care daytime (minimum 3 hours)')
        wound = self._svc('đd_050')
        self.assertEqual(wound.uom_id.with_context(lang='en_US').name, 'Wound')
        self.assertTrue(self._svc('bs_150').price_is_fee)
        self.assertFalse(wound.price_is_fee)
        self.assertEqual(self._svc('bs_020').product_variant_id.catalog_catchment_area, 'hanoi')

    def test_rules_read_and_unreadable_switched_off(self):
        self._import()
        wound = self._rules('đd_050')
        self.assertEqual((wound.action_type, wound.per_unit_field, wound.wound_count_min),
                         ('per_unit', 'wound_count', 2))
        self.assertEqual(wound.approval_status, 'approved')
        self.assertEqual(self._rules('đd_280').min_hours, 3)
        windows = self._rules('bs_150').filtered(lambda r: r.action_type == 'eligibility')
        self.assertEqual(windows.time_windows, '00:00-08:00; 12:00-13:00; 17:00-24:00')
        self.assertIn('&lt;', self._rules('đd_050').rule_summary_html or '',
                      "service names are escaped in the summary")
        exclude = self._rules('bs_150').filtered(lambda r: r.action_type == 'exclude')
        self.assertEqual(set(exclude.conflict_product_tmpl_ids.mapped('default_code')),
                         {'đd_160_hanoi', 'đd_280_hanoi'})
        nurse = self._rules('ALL_NURSE')
        self.assertEqual((nurse.action_type, nurse.action_value), ('percentage', -10))
        self.assertEqual(nurse.applied_on, '2_product_category')
        odd = self._rules('bs_020')
        self.assertEqual(odd.parse_status, 'not_understood')
        self.assertFalse(odd.active, "an unreadable condition must never change a price")
        if self.env['res.lang']._lang_get('vi_VN'):
            self.assertEqual(self._rules('đd_280').with_context(lang='vi_VN').condition_text,
                             'Tối thiểu 3 giờ')

    # -- prices and warnings -----------------------------------------------
    def _ctx(self, product, qty=1, **kw):
        Engine = self.env['advanced.pricing.engine']
        tmpls = kw.pop('tmpls', product.product_tmpl_id)
        facts = {'booking_product_tmpl_ids': tmpls.ids,
                 'booking_fee_tmpl_ids': tmpls.filtered('price_is_fee').ids,
                 'is_new_client': True, 'is_foreign_client': False}
        facts.update(kw)
        return Engine._line_pricing_context(product, qty, facts)

    def test_extra_wounds_priced_per_wound(self):
        self._import()
        wound = self._svc('đd_050').product_variant_id
        price = self.engine.calculate_price(wound.id, 1, False, self._ctx(wound, wound_count=3))
        self.assertEqual(price, 200000 + 2 * 50000)

    def test_condition_warnings(self):
        self._import()
        adl = self._svc('đd_280').product_variant_id
        self.assertTrue(self.engine.booking_warnings(adl, 2, self._ctx(adl, 2)))
        self.assertFalse(self.engine.booking_warnings(adl, 3, self._ctx(adl, 3)))

        after = self._svc('bs_150').product_variant_id
        self.assertTrue(self.engine.booking_warnings(after, 1, self._ctx(after, appointment_time=10.0)))
        self.assertFalse(self.engine.booking_warnings(after, 1, self._ctx(after, appointment_time=18.5)))
        # "Not applicable" with ADL care on the same booking
        both = after.product_tmpl_id | adl.product_tmpl_id
        msgs = self.engine.booking_warnings(after, 1, self._ctx(after, appointment_time=18.5, tmpls=both))
        self.assertEqual(len(msgs), 1)

        weekend = self._svc('đd_330').product_variant_id
        self.assertFalse(self.engine.booking_warnings(
            weekend, 1, self._ctx(weekend, is_weekend=True, is_new_client=True)))
        self.assertTrue(self.engine.booking_warnings(
            weekend, 1, self._ctx(weekend, is_weekend=True, is_new_client=False)))

        km = self._svc('đd_350').product_variant_id
        self.assertTrue(self.engine.booking_warnings(km, 1, self._ctx(km, 1, distance=6.0)))
        self.assertTrue(self.engine.booking_warnings(km, 1, self._ctx(km, 1, distance=11.2)))
        self.assertFalse(self.engine.booking_warnings(km, 4, self._ctx(km, 4, distance=11.2)))

    def test_foreign_and_second_client(self):
        self._import()
        adl = self._svc('đd_280').product_variant_id
        base = self.engine.calculate_price(adl.id, 3, False, self._ctx(adl, 3))
        self.assertEqual(base, 110000)
        self.assertEqual(self.engine.calculate_price(
            adl.id, 3, False, self._ctx(adl, 3, is_foreign_client=True)), 165000)
        self.assertEqual(self.engine.calculate_price(
            adl.id, 3, False, self._ctx(adl, 3, is_multi_client_same_location=True)), 99000)
        doctor = self._svc('bs_020').product_variant_id
        self.assertEqual(self.engine.calculate_price(
            doctor.id, 1, False, self._ctx(doctor, is_multi_client_same_location=True)), 400000,
            "the second-client discount is for nurse services only")

    # -- replace / check-only ----------------------------------------------
    def test_check_only_saves_nothing(self):
        probe = _svc('zz_901', 'Doctor Service', 'Medical Exam & Treatment', 'Thử', 'Probe',
                     'Lần', 'per_service', 1000)
        wiz = self._import(_workbook(services=SERVICES + [probe]), check_only=True)
        self.assertFalse(self._svc('zz_901'))
        self.assertIn('CHECK ONLY', wiz.import_log)
        self.assertIn('Services created', wiz.import_log)

    def test_reimport_replaces(self):
        self._import()
        first_rules = self.engine.rule_ids.filtered('active')
        self._import(_workbook(services=SERVICES[:-1]))
        self.assertFalse(self._svc('đd_350').active, "a service missing from the new file is switched off")
        self.assertEqual(len(self._svc('bs_020')), 1, "re-import updates, never duplicates")
        self.assertFalse(first_rules.filtered('active'), "old rules are switched off, not stacked")
