# -*- coding: utf-8 -*-
"""Price list upload (CRM price input workbooks).

One workbook per region, two sheets:

* ``<Region>_Base_Clean…``  — one row per service: item_code, province, the
  four-level taxonomy in English + Vietnamese, unit, base fee, rounding,
  validity and version columns.
* ``<Region>_Adjustments_Clean`` — one row per condition: which item it is
  about, the condition sentence (English + Vietnamese), what it does
  (add / multiply / replace / percentage discount / eligibility / exclude),
  the value and the calculation order.

Sheets are recognised by their HEADERS, not their names or column order, so a
re-arranged or re-named workbook still loads; the layout of the 2025 sheets
(service_type / service_category / service_name) is accepted through aliases.

The condition sentences are read, never guessed: every sentence must be fully
covered by a known phrase (see CONDITION_PHRASES). Whatever is left over is
reported and the rule is imported switched OFF, so an unreadable condition can
never silently change a price.
"""
import base64
import io
import logging
import math
import re
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

try:
    import openpyxl
except ImportError:
    openpyxl = None
    _logger.warning("openpyxl not installed. Excel import will not work.")


class _CheckOnly(Exception):
    """Raised inside a savepoint to throw away a check-only run."""


# Province text in the sheet -> (default_code suffix, rule region). The
# suffix is a contract read in nine places (catalog catchment, pricing region,
# quick booking) — never change it.
REGIONS = {
    'hanoi': ('hanoi', 'Hanoi'), 'ha noi': ('hanoi', 'Hanoi'),
    'hà nội': ('hanoi', 'Hanoi'), 'hn': ('hanoi', 'Hanoi'),
    'tphcm': ('tphcm', 'HCMC'), 'tp hcm': ('tphcm', 'HCMC'),
    'hcmc': ('tphcm', 'HCMC'), 'hcm': ('tphcm', 'HCMC'),
    'ho chi minh': ('tphcm', 'HCMC'), 'ho chi minh city': ('tphcm', 'HCMC'),
    'hồ chí minh': ('tphcm', 'HCMC'), 'tp hồ chí minh': ('tphcm', 'HCMC'),
    'thành phố hồ chí minh': ('tphcm', 'HCMC'), 'saigon': ('tphcm', 'HCMC'),
    'sài gòn': ('tphcm', 'HCMC'),
}

# unit_en code -> (xmlid of a standard unit, or English name of our own unit)
UNIT_MAP = {
    'per_hour': ('uom.product_uom_hour', None),
    'per_km': ('uom.product_uom_km', None),
    'per_service': (None, 'Visit'),
    'per_test': (None, 'Test'),
    'per_injection': (None, 'Injection'),
    'per_wound': (None, 'Wound'),
    'per_bottle': (None, 'Bottle'),
    'per_shift': (None, 'Shift'),
    'per_package': (None, 'Package'),
}

ROUNDING_RULE_MAP = {
    'round up to next 1,000': 'round_1000',
    'round up to next 1000': 'round_1000',
    'round up to next 5 mins': 'round_5min',
    'round up to next 30 mins': 'round_30min',
    'rounded up to next 30 mins': 'round_30min',
    'round up to next half hour': 'round_half_hour',
    'rounded up to next hour': 'round_hour',
    'round up to next hour': 'round_hour',
    'round partial hour up to next 1 hour': 'round_partial_hour',
    'round partial hour up to next 30 minutes': 'round_partial_30min',
    'round up partial time as documented where applicable': 'round_as_documented',
    'round up partial time as documented': 'round_as_documented',
}

# Adjustment_Type (English first, Vietnamese as fallback) -> action_type
ADJUSTMENT_TYPE_MAP = {
    'add': 'add', 'cộng': 'add', 'thêm': 'add',
    'multiply': 'multiply', 'nhân': 'multiply',
    'replace': 'fixed', 'replace with service price': 'fixed',
    'thay thế': 'fixed', 'thay thế bằng giá dịch vụ': 'fixed',
    'percentage discount': 'percentage_discount', 'giảm phần trăm': 'percentage_discount',
    'discount base price': 'discount', 'giảm giá': 'discount',
    'eligibility': 'eligibility', 'điều kiện': 'eligibility',
    'exclude': 'exclude', 'loại trừ': 'exclude',
}

TRIGGER_SOURCE_MAP = {
    'booking/form': 'booking_form', 'booking': 'booking_form',
    'đặt chỗ/biểu mẫu': 'booking_form', 'đặt lịch': 'booking_form',
    'app clock': 'app_clock', 'đồng hồ ứng dụng': 'app_clock',
    'provider after service': 'provider_after_service',
    'nhà cung cấp sau dịch vụ': 'provider_after_service',
    'public holidays table': 'public_holidays_table', 'bảng ngày lễ': 'public_holidays_table',
    'system': 'system', 'hệ thống': 'system',
    'crm': 'crm', 'crm/booking': 'crm_booking', 'crm/đặt lịch': 'crm_booking',
    'cmf + booking form': 'cmf_booking_form',
    'quotation on booking form': 'quotation_booking_form',
    'báo giá trên biểu mẫu đặt chỗ': 'quotation_booking_form',
    'service duration log; booking form;': 'service_duration_log',
    'booking form & provider after service': 'booking_form_provider',
    'booking/form & provider after service': 'booking_form_provider',
    'booking/provider': 'booking_form_provider', 'đặt lịch/nhà cung cấp': 'booking_form_provider',
}

# Header aliases: 2025 layout and loose spellings -> canonical column key.
BASE_ALIASES = {
    'service_type_vi': 'service_class_vi', 'service_type_en': 'service_class_en',
    'service_name_vi': 'main_service_vi', 'service_name_en': 'main_service_en',
    'service_category_vi': 'item_group_vi', 'service_category_en': 'item_group_en',
    'region': 'province', 'base_fee': 'base_fee_vnd', 'price': 'base_fee_vnd',
}

# --- Condition phrases ------------------------------------------------------
# Each phrase is (regex, handler). Handlers receive the match and the vals dict
# to fill. Matched text is removed; anything left that is not a filler word
# means the sentence was NOT understood.
_T = r'(\d{1,2}):(\d{2})'                 # 19:00 (a colon, so '5-8km' is not a time)
_ORD2 = r'(?:the )?(?:second|2nd)'
FILLER_WORDS = {
    'and', 'or', 'night', 'time', 'daytime', 'day', 'onward', 'onwards', 'the',
    'only', 'when', 'using', 'from', 'with',
    # Vietnamese fillers
    'và', 'hoặc', 'ban', 'đêm', 'ngày', 'trở', 'đi', 'chỉ', 'khi', 'dùng', 'từ',
}


def _hhmm(h, m):
    return '%02d:%02d' % (int(h), int(m or 0))


def _add_window(vals, start, end):
    windows = [w for w in (vals.get('time_windows') or '').split('; ') if w]
    windows.append('%s-%s' % (start, end))
    vals['time_windows'] = '; '.join(windows)


def _per_unit(field, minimum_field):
    def handler(m, vals):
        vals['_per_unit_field'] = field
        if minimum_field:
            vals[minimum_field] = 2
    return handler


CONDITION_PHRASES_EN = [
    # Time windows first, so "before/after" do not eat half a range.
    (_T + r'\s*-\s*' + _T,
     lambda m, v: _add_window(v, _hhmm(m[1], m[2]), _hhmm(m[3], m[4]))),
    (r'before ' + _T, lambda m, v: _add_window(v, '00:00', _hhmm(m[1], m[2]))),
    (r'after ' + _T, lambda m, v: _add_window(v, _hhmm(m[1], m[2]), '24:00')),
    (r'from ' + _T + r'(?: onwards?)?', lambda m, v: _add_window(v, _hhmm(m[1], m[2]), '24:00')),
    (r'minimum (\d+(?:\.\d+)?) ?(?:hours?|h)\b', lambda m, v: v.update(min_hours=float(m[1]))),
    (r'saturday ?/ ?sunday|weekends?', lambda m, v: v.update(is_weekend_required=True)),
    (r'(?:newly arising|new) (?:client|customer)s?', lambda m, v: v.update(requires_new_client=True)),
    (r'distance (\d+(?:\.\d+)?) ?(?:km)? ?- ?(\d+(?:\.\d+)?) ?km',
     lambda m, v: v.update(distance_min=float(m[1]), distance_max=float(m[2]))),
    (r'(?:beyond|over|more than) (\d+(?:\.\d+)?) ?km,? per additional km',
     lambda m, v: v.update(per_km_beyond=float(m[1]))),
    (r'(?:beyond|over|more than) (\d+(?:\.\d+)?) ?km',
     lambda m, v: v.update(distance_min=float(m[1]))),
    (r'from ' + _ORD2 + r' wound(?: onwards?)?(?:\s*:\s*(small|large) wound(?:\s*/\s*tm)?)?',
     lambda m, v: (_per_unit('wound_count', 'wound_count_min')(m, v),
                   m[1] and v.update(wound_size=m[1]))),
    (r'complex wounds?', lambda m, v: v.update(requires_complex_wound=True)),
    (r'from ' + _ORD2 + r' injection(?: onwards?)? or additional medicines?',
     _per_unit('injection_or_medication', None)),
    (r'from ' + _ORD2 + r' injection(?: onwards?)?', _per_unit('injection_count', 'injection_count_min')),
    (r'from ' + _ORD2 + r' bottle(?: onwards?)?', _per_unit('iv_fluid_count', 'iv_fluid_count_min')),
    (r'each additional medications?', _per_unit('medication_count', 'medication_count_min')),
    (r'more than one medications?(?: injected)?', lambda m, v: v.update(medication_count_min=2)),
    (r'from ' + _ORD2 + r' client,? same place ?/ ?time,? same (?:doctor ?/ ?nurse|nurse ?/ ?doctor|nurse|doctor)',
     lambda m, v: v.update(requires_multi_client_same_location=True)),
    (r'(?:an)?other service was unsuccessful',
     lambda m, v: v.update(accept_other_service_failed=True)),
    (r'clinic doctor(?:\'s)? (?:indication|order)',
     lambda m, v: v.update(accept_doctor_order=True)),
    (r'(?:combined with|with|using) (?:an)?other services?',
     lambda m, v: v.update(requires_other_service_same_visit=True)),
    (r'foreign (?:customer|client)s?', lambda m, v: v.update(requires_foreign_client=True)),
    (r'(?:tet ?/ ?holiday|holiday ?/ ?tet|public holidays?|holidays?|tet)',
     lambda m, v: v.update(is_holiday_required=True)),
]

_TV = r'(\d{1,2})[h:](\d{2})?'            # 19h / 19h30 / 19:30
CONDITION_PHRASES_VI = [
    (_TV + r'\s*-\s*' + _TV, lambda m, v: _add_window(v, _hhmm(m[1], m[2]), _hhmm(m[3], m[4]))),
    (r'trước ' + _TV, lambda m, v: _add_window(v, '00:00', _hhmm(m[1], m[2]))),
    (r'sau ' + _TV, lambda m, v: _add_window(v, _hhmm(m[1], m[2]), '24:00')),
    (r'từ ' + _TV + r'(?: trở đi)?', lambda m, v: _add_window(v, _hhmm(m[1], m[2]), '24:00')),
    (r'tối thiểu (\d+(?:\.\d+)?) ?giờ', lambda m, v: v.update(min_hours=float(m[1]))),
    (r'thứ 7 ?/ ?chủ nhật|cuối tuần', lambda m, v: v.update(is_weekend_required=True)),
    (r'khách hàng mới(?: phát sinh)?', lambda m, v: v.update(requires_new_client=True)),
    (r'khoảng cách (\d+(?:\.\d+)?) ?- ?(\d+(?:\.\d+)?) ?km',
     lambda m, v: v.update(distance_min=float(m[1]), distance_max=float(m[2]))),
    (r'từ km thứ (\d+) trở đi,? mỗi km phát sinh', lambda m, v: v.update(per_km_beyond=float(m[1]))),
    (r'(?:từ )?vết thương thứ 2(?: trở đi)?(?:\s*:\s*vết thương (nhỏ|lớn)(?:\s*/\s*tm)?)?',
     lambda m, v: (_per_unit('wound_count', 'wound_count_min')(m, v),
                   m[1] and v.update(wound_size='small' if m[1] == 'nhỏ' else 'large'))),
    (r'vết thương phức tạp', lambda m, v: v.update(requires_complex_wound=True)),
    (r'(?:từ )?mũi thứ 2 hoặc thêm thuốc khác', _per_unit('injection_or_medication', None)),
    (r'(?:từ )?mũi thứ 2(?: trở đi)?', _per_unit('injection_count', 'injection_count_min')),
    (r'(?:từ )?chai thứ 2(?: trở đi)?', _per_unit('iv_fluid_count', 'iv_fluid_count_min')),
    (r'mỗi loại thuốc thêm', _per_unit('medication_count', 'medication_count_min')),
    (r'tiêm nhiều hơn 1 loại thuốc', lambda m, v: v.update(medication_count_min=2)),
    (r'(?:từ )?khách hàng thứ 2,? cùng địa điểm ?/ ?thời gian,? cùng (?:bs ?/ ?đd|điều dưỡng|bác sĩ)',
     lambda m, v: v.update(requires_multi_client_same_location=True)),
    (r'dịch vụ khác không thành công', lambda m, v: v.update(accept_other_service_failed=True)),
    (r'có chỉ định bs pk', lambda m, v: v.update(accept_doctor_order=True)),
    (r'(?:đi kèm|đi cùng|dùng) dịch vụ khác', lambda m, v: v.update(requires_other_service_same_visit=True)),
    (r'(?:khách hàng là người|khách) nước ngoài', lambda m, v: v.update(requires_foreign_client=True)),
    (r'ngày lễ ?/ ?tết|lễ ?/ ?tết|tết', lambda m, v: v.update(is_holiday_required=True)),
]


def _normalise_sentence(text):
    text = (text or '').lower()
    for dash in ('–', '—', '−', '‐'):
        text = text.replace(dash, '-')
    text = text.replace('≥', '>=').replace('≤', '<=')
    return ' '.join(text.split())


def read_condition(sentence, phrases):
    """Read a condition sentence into rule fields.

    Returns ``(vals, leftover)``; ``leftover`` is the unread part (empty when
    the whole sentence was understood). Nothing is inferred beyond the listed
    phrases.
    """
    text = _normalise_sentence(sentence)
    vals = {}
    for pattern, handler in phrases:
        while True:
            m = re.search(pattern, text)
            if not m:
                break
            handler(m, vals)
            text = text[:m.start()] + ' ' + text[m.end():]
    if vals.get('time_windows'):
        vals['time_windows'] = '; '.join(sorted(vals['time_windows'].split('; ')))
    words = [w for w in re.split(r'[\s,;:.()/]+', text) if w]
    leftover = [w for w in words if w not in FILLER_WORDS]
    return vals, ' '.join(leftover)


class PricingImportWizard(models.TransientModel):
    _name = 'advanced.pricing.import.wizard'
    _description = 'Import Pricing Rules from Excel'

    def _default_engine(self):
        return self.env['advanced.pricing.config'].get_config().default_engine_id

    file = fields.Binary('Excel File', required=True)
    filename = fields.Char('Filename')
    engine_id = fields.Many2one('advanced.pricing.engine', 'Target Engine',
                                required=True, default=_default_engine)

    import_type = fields.Selection([
        ('base', 'Base Price List (Services)'),
        ('adjustments', 'Adjustments (Price Rules and Conditions)'),
        ('both', 'Both (Services + Rules)'),
    ], string='Import Type', default='both', required=True,
       help='What to import from the Excel file')
    replace_existing = fields.Boolean(
        'Replace the Current Price List', default=True,
        help="For each region in the file: services of that region that are not in "
             "the file are switched off, and the region's current price rules are "
             "switched off and replaced by the file's rules. Nothing is deleted, so "
             "older bookings keep their lines.")
    approve_rules = fields.Boolean(
        'Approve the Rules Now',
        help='Owners only. Imported rules start working straight away instead of '
             'waiting for approval.')

    import_log = fields.Text('Import Log', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('checked', 'Checked'), ('done', 'Done'),
    ], default='draft')

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_check(self):
        """Run the whole import and throw it away: shows exactly what an
        import would do, including every sentence it could not read."""
        self.ensure_one()
        log = []
        try:
            with self.env.cr.savepoint():
                self._run_import(log)
                raise _CheckOnly()
        except _CheckOnly:
            pass
        self.env.invalidate_all()
        log.insert(0, _("CHECK ONLY: nothing was saved. Press Import to load the file."))
        self.write({'import_log': '\n'.join(log), 'state': 'checked'})
        return self._reopen()

    def import_rules(self):
        """Import services and/or rules from the workbook."""
        self.ensure_one()
        log = []
        self._run_import(log)
        self.write({'import_log': '\n'.join(log), 'state': 'done'})
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def _run_import(self, log):
        if not openpyxl:
            raise UserError(_("The openpyxl library is required for Excel import. "
                              "Please install it: pip install openpyxl"))
        user = self.env.user
        if not (user.has_group('health_base.group_healthcare_owner')
                or user.has_group('base.group_system')
                or self.env['product.template'].has_access('create')):
            # Replacing the price list changes every future booking's price.
            raise AccessError(_('Only owners, or staff allowed to create services, '
                                'can upload a price list.'))
        if self.approve_rules and not user.has_group('health_base.group_healthcare_owner'):
            raise AccessError(_('Only owners can approve price rules.'))
        try:
            wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(self.file)), data_only=True)
        except Exception as e:
            raise UserError(_("Could not read the Excel file: %s", e))

        base_sheets, adj_sheets = [], []
        for ws in wb.worksheets:
            kind, header = self._sheet_kind(ws)
            if kind == 'base':
                base_sheets.append((ws, header))
            elif kind == 'adjustments':
                adj_sheets.append((ws, header))
        if self.import_type in ('base', 'both') and not base_sheets:
            raise UserError(_(
                "No price list sheet found. It needs at least the columns "
                "item_code, province, item_description_en and base_fee_vnd."))
        if self.import_type in ('adjustments', 'both') and not adj_sheets and self.import_type == 'adjustments':
            raise UserError(_(
                "No adjustments sheet found. It needs at least the columns "
                "Adjustment Applies to this item_code, Trigger Condition en and "
                "Adjustment_Type_en."))

        # A new clinic's copy has no default engine, and without one no
        # booking screen reads any rule: make the engine loaded here the default.
        config = self.env['advanced.pricing.config'].sudo().get_config()
        if not config.default_engine_id:
            config.default_engine_id = self.engine_id

        stats = {'created': 0, 'updated': 0, 'archived': 0, 'rules': 0,
                 'rules_off': 0, 'rules_replaced': 0, 'errors': 0}
        attention, detail = [], []
        category_cache = {}

        if self.import_type in ('base', 'both'):
            for ws, header in base_sheets:
                detail.append(_("--- Services sheet: %s ---", ws.title))
                self._import_base_sheet(ws, header, category_cache, stats, attention, detail)
        if self.import_type in ('adjustments', 'both'):
            for ws, header in adj_sheets:
                detail.append(_("--- Rules sheet: %s ---", ws.title))
                self._import_adjustments_sheet(ws, header, stats, attention, detail)

        log.append(_("=== %s ===", self.filename or _('Price list')))
        log.append(_("Services created: %(c)s, updated: %(u)s, switched off (not in file): %(a)s",
                     c=stats['created'], u=stats['updated'], a=stats['archived']))
        log.append(_("Rules loaded: %(n)s (of which switched off because not understood: %(off)s); "
                     "old rules replaced: %(old)s",
                     n=stats['rules'], off=stats['rules_off'], old=stats['rules_replaced']))
        if stats['rules'] and not self.approve_rules:
            log.append(_("The rules are waiting for approval and do not change prices "
                         "until an owner approves them."))
        log.append(_("Rows with errors: %s", stats['errors']))
        if attention:
            log.append('')
            log.append(_("NEEDS ATTENTION:"))
            log.extend('  • ' + a for a in attention)
        log.append('')
        log.extend(detail)

    # ------------------------------------------------------------------
    # Sheet reading
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_header(value):
        text = str(value or '').strip().lower()
        text = re.sub(r'[^0-9a-zà-ỹđ]+', '_', text).strip('_')
        if 'item_code' in text:
            return 'item_code'
        for key in ('item_name_vi', 'item_name_en'):
            if text.endswith(key):
                return key
        return text

    def _sheet_kind(self, ws):
        rows = ws.iter_rows(min_row=1, max_row=1, values_only=True)
        raw = [self._norm_header(h) for h in next(rows, ())]
        base = [BASE_ALIASES.get(h, h) for h in raw]
        if {'item_code', 'base_fee_vnd'} <= set(base):
            return 'base', base
        if 'item_code' in raw and ({'trigger_condition_en', 'trigger_condition_vi'} & set(raw)):
            return 'adjustments', raw
        return None, raw

    @staticmethod
    def _clean(value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    def _rows(self, ws, header):
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            rec = {k: self._clean(v) for k, v in zip(header, row) if k}
            if rec.get('item_code') is None:
                continue  # blank / trailing rows
            yield row_idx, rec

    @staticmethod
    def _parse_numeric(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        cleaned = str(val).replace(',', '').replace(' ', '').strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_date(val):
        if not val:
            return False
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
            try:
                return datetime.strptime(str(val).strip(), fmt).date()
            except ValueError:
                continue
        return False

    @staticmethod
    def _parse_bool(val, default=True):
        if val is None or val == '':
            return default
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in ('true', '1', 'yes', 'y', 'x', 'có')

    @staticmethod
    def _region(text):
        key = ' '.join(str(text or '').lower().replace('.', ' ').split())
        return REGIONS.get(key) or REGIONS.get(key.replace(' ', ''))

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------
    def _import_base_sheet(self, ws, header, category_cache, stats, attention, detail):
        Product = self.env['product.template'].with_context(lang='en_US', active_test=False)
        seen_by_suffix = {}
        seen_codes = set()
        for row_idx, rec in self._rows(ws, header):
            code = str(rec['item_code']).strip()
            region = self._region(rec.get('province'))
            if not region:
                stats['errors'] += 1
                attention.append(_("Row %(row)s (%(code)s): unknown province '%(prov)s'.",
                                   row=row_idx, code=code, prov=rec.get('province') or ''))
                continue
            suffix = region[0]
            internal_ref = '%s_%s' % (code, suffix)
            if internal_ref in seen_codes:
                stats['errors'] += 1
                attention.append(_("Row %(row)s: %(code)s appears twice for this region; "
                                   "the second row was skipped.", row=row_idx, code=code))
                continue
            fee = self._parse_numeric(rec.get('base_fee_vnd'))
            if fee is None:
                stats['errors'] += 1
                attention.append(_("Row %(row)s (%(code)s): the base fee '%(fee)s' is not a number.",
                                   row=row_idx, code=code, fee=rec.get('base_fee_vnd') or ''))
                continue
            name_en = rec.get('item_description_en') or rec.get('item_description_vi') or code
            name_vi = rec.get('item_description_vi')
            try:
                with self.env.cr.savepoint():
                    categ = self._category(rec, category_cache, detail)
                    unit, unit_note = self._unit(rec.get('unit_en'), rec.get('unit_vi'))
                    if unit_note:
                        attention.append(_("Row %(row)s (%(code)s): %(note)s",
                                           row=row_idx, code=code, note=unit_note))
                    main_en = (rec.get('main_service_en') or '').lower()
                    class_en = (rec.get('service_class_en') or '').lower()
                    vals = {
                        'name': name_en,
                        'default_code': internal_ref,
                        'price_item_code': code,
                        'list_price': fee,
                        'type': 'service',
                        'sale_ok': True,
                        'purchase_ok': False,
                        'active': self._parse_bool(rec.get('item_active')),
                        'categ_id': categ.id,
                        'marketing_service_line': rec.get('marketing_service_line_en')
                                                  or rec.get('marketing_service_line_vi') or False,
                        'item_group': rec.get('item_group_en') or rec.get('item_group_vi') or False,
                        'price_is_fee': 'fee' in main_en or 'fee' in class_en,
                        'price_valid_from': self._parse_date(rec.get('valid_from')),
                        'price_valid_to': self._parse_date(rec.get('valid_to')),
                        'price_version': rec.get('price_version') and str(rec['price_version']) or False,
                        'price_updated_by': rec.get('last_updated_by') or False,
                        'price_updated_on': self._parse_date(rec.get('last_updated_on')),
                        'price_change_reason': rec.get('reason_for_change') or False,
                    }
                    rounding = ROUNDING_RULE_MAP.get((rec.get('rounding_rule') or '').lower())
                    if rounding:
                        vals['rounding_rule'] = rounding
                    elif rec.get('rounding_rule'):
                        attention.append(_("Row %(row)s (%(code)s): rounding rule '%(r)s' is not known; left empty.",
                                           row=row_idx, code=code, r=rec['rounding_rule']))
                    product = Product.search([('default_code', '=', internal_ref)], limit=1)
                    if product:
                        if unit and product.uom_id != unit:
                            try:
                                with self.env.cr.savepoint():
                                    product.write({'uom_id': unit.id})
                            except Exception:
                                attention.append(_(
                                    "%(code)s: the unit could not be changed because the service "
                                    "is already used; the rest was updated.", code=internal_ref))
                        product.write(vals)
                        stats['updated'] += 1
                        detail.append(_("  Updated %(code)s: %(name)s (%(fee)s VND)",
                                        code=internal_ref, name=name_en, fee='{:,.0f}'.format(fee)))
                    else:
                        if unit:
                            vals['uom_id'] = unit.id
                        product = Product.create(vals)
                        stats['created'] += 1
                        detail.append(_("  Created %(code)s: %(name)s (%(fee)s VND)",
                                        code=internal_ref, name=name_en, fee='{:,.0f}'.format(fee)))
                    vi_vals = {}
                    if name_vi:
                        vi_vals['name'] = name_vi
                    if rec.get('marketing_service_line_vi'):
                        vi_vals['marketing_service_line'] = rec['marketing_service_line_vi']
                    if rec.get('item_group_vi'):
                        vi_vals['item_group'] = rec['item_group_vi']
                    if vi_vals:
                        product.with_context(lang='vi_VN').write(vi_vals)
            except Exception as e:
                stats['errors'] += 1
                attention.append(_("Row %(row)s (%(code)s): %(err)s", row=row_idx, code=code, err=e))
                _logger.exception("Price list row %s failed", row_idx)
                # The savepoint rolled back anything this row created (a new
                # category, a new unit); forget it so later rows re-create it.
                category_cache.clear()
                self.env.invalidate_all()
                continue
            seen_codes.add(internal_ref)
            seen_by_suffix.setdefault(suffix, set()).add(internal_ref)

        if self.replace_existing:
            for suffix, codes in seen_by_suffix.items():
                stale = self.env['product.template'].search([
                    ('type', '=', 'service'),
                    ('default_code', '=like', '%\\_' + suffix),
                    ('default_code', 'not in', list(codes)),
                ])
                if stale:
                    stale.write({'active': False})
                    stats['archived'] += len(stale)
                    detail.append(_("  Switched off %(n)s %(region)s services not in the file: %(codes)s",
                                    n=len(stale), region=suffix,
                                    codes=', '.join(stale.mapped('default_code'))))

    def _category(self, rec, cache, detail):
        """Two-level category: service class → main service, each holding its
        English name (source) and Vietnamese translation."""
        key = (rec.get('service_class_en'), rec.get('service_class_vi'),
               rec.get('main_service_en'), rec.get('main_service_vi'))
        if key not in cache:
            parent = self._find_or_create_category(key[0], key[1], False, detail)
            child = self._find_or_create_category(key[2], key[3], parent, detail) if parent else False
            cache[key] = child or parent or self.env.ref('product.product_category_all')
        return cache[key]

    def _find_or_create_category(self, name_en, name_vi, parent, detail):
        # Categories and units are shared master data the price list owns;
        # an owner may lack the stock "create product category/unit" rights.
        Categ = self.env['product.category'].sudo()
        primary = name_en or name_vi
        if not primary:
            return parent
        domain = [('parent_id', '=', parent.id if parent else False)]
        categ = Categ.with_context(lang='en_US').search(domain + [('name', '=', primary)], limit=1)
        if not categ and name_vi:
            categ = Categ.with_context(lang='vi_VN').search(domain + [('name', '=', name_vi)], limit=1)
        if not categ:
            categ = Categ.with_context(lang='en_US').create(
                dict({'name': primary}, **({'parent_id': parent.id} if parent else {})))
            detail.append(_("  Created category: %s", categ.with_context(lang='en_US').complete_name))
        else:
            categ.with_context(lang='en_US').name = primary
        if name_vi:
            categ.with_context(lang='vi_VN').name = name_vi
        return categ

    def _unit(self, unit_en, unit_vi):
        """Return (uom, note). Standard units come from their xmlid; the price
        list's own units (Visit, Wound, Shift…) are created once, 1:1 with
        Units, with the Vietnamese name from the sheet."""
        code = (unit_en or 'per_service').strip().lower()
        Uom = self.env['uom.uom'].sudo().with_context(lang='en_US')
        units = self.env.ref('uom.product_uom_unit')
        if code not in UNIT_MAP:
            return units, _("unit '%s' is not known; Units was used.", unit_en)
        xmlid, name = UNIT_MAP[code]
        if xmlid:
            return self.env.ref(xmlid), None
        uom = Uom.search([('name', '=', name)], limit=1)
        if not uom:
            uom = Uom.create({'name': name, 'relative_factor': 1.0, 'relative_uom_id': units.id})
        if unit_vi and uom.with_context(lang='vi_VN').name != unit_vi:
            uom.with_context(lang='vi_VN').name = unit_vi
        return uom, None

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def _import_adjustments_sheet(self, ws, header, stats, attention, detail):
        Rule = self.env['advanced.pricing.rule'].with_context(lang='en_US')
        is_owner = self.env.user.has_group('health_base.group_healthcare_owner')
        rows = list(self._rows(ws, header))

        if self.replace_existing:
            regions = {r[1] for r in (self._region(rec.get('region')) for _i, rec in rows) if r}
            old = Rule.search([('engine_id', '=', self.engine_id.id), ('active', '=', True)])
            old = old.filtered(lambda r: (self._region(r.region) or (None, None))[1] in regions)
            if old:
                old.write({'active': False})
                stats['rules_replaced'] += len(old)
                detail.append(_("  Switched off %(n)s old rules of %(regions)s.",
                                n=len(old), regions=', '.join(sorted(regions))))

        for row_idx, rec in rows:
            code = str(rec.get('item_code') or '').strip()
            region = self._region(rec.get('region'))
            if not region:
                stats['errors'] += 1
                attention.append(_("Rules row %(row)s (%(code)s): unknown region '%(reg)s'.",
                                   row=row_idx, code=code, reg=rec.get('region') or ''))
                continue
            try:
                with self.env.cr.savepoint():
                    vals, problems = self._rule_vals(rec, region)
                    understood = not problems
                    vals.update({
                        'engine_id': self.engine_id.id,
                        'parse_status': 'understood' if understood else 'not_understood',
                        'parse_leftover': '; '.join(problems) or False,
                        'active': understood,
                    })
                    rule = Rule.create(vals)
                    vi = {}
                    if rec.get('trigger_condition_vi'):
                        vi['condition_text'] = rec['trigger_condition_vi']
                    if rec.get('notes_vi'):
                        vi['rule_note'] = rec['notes_vi']
                    if vi:
                        rule.with_context(lang='vi_VN').write(vi)
                    # Approve LAST: any content write to an approved rule
                    # resets it to draft (see advanced.pricing.rule.write).
                    if understood and self.approve_rules and is_owner:
                        rule.write({'approval_status': 'approved',
                                    'approved_by': self.env.uid,
                                    'approval_date': fields.Datetime.now(),
                                    'approval_notes': _('Approved on import of %s', self.filename or '')})
                    stats['rules'] += 1
                    if understood:
                        detail.append(_("  Rule %(code)s: %(cond)s → %(reading)s",
                                        code=code, cond=rec.get('trigger_condition_en') or '',
                                        reading=self._plain_reading(rule)))
                    else:
                        stats['rules_off'] += 1
                        attention.append(_(
                            "Rules row %(row)s (%(code)s, '%(cond)s'): not understood (%(why)s). "
                            "Loaded switched off.", row=row_idx, code=code,
                            cond=rec.get('trigger_condition_en') or rec.get('trigger_condition_vi') or '',
                            why='; '.join(problems)))
            except Exception as e:
                stats['errors'] += 1
                attention.append(_("Rules row %(row)s (%(code)s): %(err)s", row=row_idx, code=code, err=e))
                _logger.exception("Price rule row %s failed", row_idx)

    @staticmethod
    def _plain_reading(rule):
        import html
        text = html.unescape(re.sub(r'<[^>]+>', ' ', rule.rule_summary_html or ''))
        return ' '.join(text.replace('→', '→ ').split())

    def _rule_vals(self, rec, region):
        """Rule values for one adjustments row, plus the list of problems
        (empty when the row was fully understood)."""
        suffix, region_name = region
        code = str(rec.get('item_code') or '').strip()
        cond_en = rec.get('trigger_condition_en')
        cond_vi = rec.get('trigger_condition_vi')
        type_key = (rec.get('adjustment_type_en') or '').strip().lower()
        action = ADJUSTMENT_TYPE_MAP.get(type_key) or ADJUSTMENT_TYPE_MAP.get(
            (rec.get('adjustment_type_vi') or '').strip().lower())
        value_raw = rec.get('adjustment_value')
        value = self._parse_numeric(value_raw)
        calc_seq = int(self._parse_numeric(rec.get('calc_seq')) or 10)
        problems = []

        vals = {
            'name': ('%s - %s %s - %s' % (region_name, code, rec.get('item_name_en') or '',
                                          cond_en or cond_vi or '')).replace('  ', ' ')[:200],
            'sequence': calc_seq * 10,
            'level': '1' if calc_seq <= 2 else '2',
            'rule_type': 'condition',
            'approval_status': 'draft',
            'region': region_name,
            'item_code': code,
            'condition_text': cond_en or cond_vi or False,
            'rule_note': rec.get('notes_en') or rec.get('notes_vi') or False,
            'data_required': rec.get('data_required_en') or rec.get('data_required_vi') or False,
            'trigger_source': TRIGGER_SOURCE_MAP.get((rec.get('trigger_source_en') or '').strip().lower())
                              or TRIGGER_SOURCE_MAP.get((rec.get('trigger_source_vi') or '').strip().lower())
                              or False,
            'notes': rec.get('notes_en') or rec.get('notes_vi') or False,
        }

        # Which service(s) the row is about
        targeting, target_problem = self._rule_target(code, suffix)
        vals.update(targeting)
        if target_problem:
            problems.append(target_problem)

        if not action:
            problems.append(_("adjustment type '%s' is not known",
                              rec.get('adjustment_type_en') or rec.get('adjustment_type_vi') or ''))
            action = 'eligibility'

        # The condition sentence
        if action == 'exclude':
            conflicts, missing = self._conflict_services(cond_en or '', suffix)
            vals['conflict_product_tmpl_ids'] = [(6, 0, conflicts.ids)]
            if missing:
                problems.append(_("no service found for: %s", ', '.join(missing)))
            if not conflicts and not missing:
                problems.append(_("no services listed after 'Not applicable:'"))
        else:
            if cond_en:
                cond_vals, leftover = read_condition(cond_en, CONDITION_PHRASES_EN)
            else:
                cond_vals, leftover = read_condition(cond_vi, CONDITION_PHRASES_VI)
            if leftover:
                problems.append(_("did not understand '%s'", leftover))
            if not cond_vals:
                problems.append(_("no condition found"))
            per_unit_field = cond_vals.pop('_per_unit_field', False)
            vals.update(cond_vals)
            if per_unit_field and action == 'add':
                action = 'per_unit'
                vals['per_unit_field'] = per_unit_field

        # What it does
        if action == 'percentage_discount':
            if value is None:
                problems.append(_("the discount '%s' is not a number", value_raw))
            else:
                pct = value * 100 if 0 < value <= 1 else value
                vals.update(action_type='percentage', action_value=-abs(pct))
        elif action in ('eligibility', 'exclude'):
            vals.update(action_type=action, action_value=value or 0.0)
        else:
            if value is None:
                problems.append(_("the value '%s' is not a number", value_raw))
            vals.update(action_type=action, action_value=value or 0.0)
        return vals, problems

    def _rule_target(self, code, suffix):
        """(targeting vals, problem). 'ALL' = every service of the region;
        'ALL_<CLASS>' = every service of that service class (e.g. ALL_NURSE);
        anything else is an item code of that region."""
        upper = code.upper()
        if upper in ('ALL', 'ANY', 'ANY SERVICE'):
            return {'applied_on': '3_global'}, None
        if upper.startswith('ALL_'):
            word = upper[4:].replace('_', ' ').lower()
            categ = self.env['product.category'].with_context(lang='en_US').search(
                [('parent_id', '=', False), ('name', '=ilike', word + '%')], limit=1)
            if categ:
                return {'applied_on': '2_product_category', 'categ_id': categ.id}, None
            return {'applied_on': '3_global'}, _("no service class matching '%s'", code)
        product = self.env['product.template'].with_context(active_test=False).search(
            [('default_code', '=', '%s_%s' % (code, suffix))], limit=1)
        if product:
            return {'applied_on': '1_product', 'product_tmpl_id': product.id}, None
        return {'applied_on': '3_global'}, _("service %(code)s not found for this region",
                                              code=code)

    def _conflict_services(self, sentence, suffix):
        """'Not applicable: infusion ≥2h, ADL care, palliative care' → the
        services of this region each term names (by main service or by the
        service's own name)."""
        text = _normalise_sentence(sentence)
        text = re.sub(r'^.*?not applicable\s*:?', '', text)
        terms = [t.strip() for t in re.split(r',|;| and ', text) if t.strip()]
        Product = self.env['product.template'].with_context(lang='en_US')
        region_products = Product.search([('type', '=', 'service'),
                                          ('default_code', '=like', '%\\_' + suffix)])
        found, missing = Product.browse(), []
        for term in terms:
            # "≥2h" is written "≥2 hours" in the service names
            norm = re.sub(r'(\d)\s*h\b', r'\1 hours', term)
            hits = region_products.filtered(
                lambda p: norm in _normalise_sentence(p.name)
                or norm == _normalise_sentence(p.categ_id.name))
            if hits:
                found |= hits
            else:
                missing.append(term)
        return found, missing
