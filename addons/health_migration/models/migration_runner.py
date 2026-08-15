"""migration.runner — the importer.

Run via `odoo shell` (see scripts in ROLLBACK.md / module README):

    r = env['migration.runner']
    report = r.run_migration(booking_path='/tmp/booking_mig.json',
                             contact_path='/tmp/contact_mig.json')
    # dry-run: env.cr.rollback()   |   commit: env.cr.commit()

All FK/dimension resolution goes through migration.xref (idempotent, audited).
Every business entity upserts on its legacy key. Selection/status values use the
closed maps below; unmapped values fall back + are logged (never guessed silently).
"""
import json
import logging
import hashlib
import re
from datetime import datetime, date

import pytz

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.health_base.models.phone_utils import normalize_vn_phone

from .migration_lookup_seeder import CANCELLATION_REASONS, LOST_REASONS

_logger = logging.getLogger(__name__)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


def _norm(s):
    return (str(s).strip().lower() if s not in (None, False) else '')


def _norm_key(s):
    """Normalizer for free-text lookup values (reasons, service interests).

    On top of _norm it collapses runs of whitespace and removes the spaces
    around comparison operators, so 'Không có điều dưỡng > 2.5h' (as it appears
    in the export) matches 'Không có điều dưỡng >2.5h' (as it appears in
    Lookup.xlsx). Trailing punctuation is dropped too — the export carries
    values like 'Bác sĩ khám, siêu âm,..'.
    """
    s = _norm(s)
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'\s*([<>])\s*', r'\1', s)
    return s.strip(' .,;')


# ---------------------------------------------------------------- value maps
# 'Không xác định'/'Khác' now land on real keys instead of being dropped.
GENDER_MAP = {'nữ': 'female', 'nu': 'female', 'nam': 'male',
              'male': 'male', 'female': 'female',
              'không xác định': 'prefer_not_to_say',
              'khong xac dinh': 'prefer_not_to_say',
              'khác': 'other', 'khac': 'other', 'other': 'other'}

PAYMENT_METHOD_MAP = {
    'tiền mặt': 'cash', 'tien mat': 'cash',
    'chuyển khoản': 'bank_transfer', 'chuyen khoan': 'bank_transfer',
    'chuyển khoản ngân hàng': 'bank_transfer',
    'tiền mặt + chuyển khoản': 'other',
    # settled from a prepayment balance (legacy carries these in `thanh_toan`)
    'trả từ tt trước': 'prepaid', 'tra tu tt truoc': 'prepaid',
    'thanh toán trước': 'prepaid', 'thanh toan truoc': 'prepaid',
}

# legacy `thanh_toan` (payment status) -> settlement semantics.
# 'prepaid' means the visit was paid out of a prepayment balance, so no cash or
# transfer is recorded on the row but the service WAS paid for.
PAYMENT_STATUS_MAP = {
    'đã thanh toán': 'paid', 'da thanh toan': 'paid',
    'chưa thanh toán': 'unpaid', 'chua thanh toan': 'unpaid',
    'thanh toán một phần': 'partial', 'thanh toan mot phan': 'partial',
    'trả từ tt trước': 'prepaid', 'tra tu tt truoc': 'prepaid',
    'thanh toán trước': 'prepaid', 'thanh toan truoc': 'prepaid',
}

# legacy `dich_vu_tai` -> health.fieldservice.order.service_location
SERVICE_LOCATION_MAP = {
    'tại nhà': 'home', 'tai nha': 'home',
    'tại pk': 'clinic', 'tai pk': 'clinic',
    'tại phòng khám': 'clinic', 'tai phong kham': 'clinic',
    'telemedicine': 'online',
}
SERVICE_LOCATION_FALLBACK = 'home'

# sale.order.line rejects a discount with no stated reason
LEGACY_DISCOUNT_REASON = 'Migrated from legacy system (Discount)'

# legacy `SourceofClient` / `nguon_khach_hang` -> res.partner.source_type.
# Anything not listed here is a named referrer or partner organisation and is
# handled by _client_source() (kept verbatim in referral_source).
CLIENT_SOURCE_MAP = {
    'hotline': 'phone', 'zalo': 'zalo', 'facebook': 'facebook',
    'form': 'website', 'website': 'website', 'google': 'website',
    'tiktok': 'facebook',
    'tự đến pk': 'walk_in', 'tu den pk': 'walk_in',
    'người giới thiệu': 'referral', 'nguoi gioi thieu': 'referral',
    'khách hàng cũ': 'referral', 'khach hang cu': 'referral',
    'bác sĩ/điều dưỡng': 'referral', 'bac si/dieu duong': 'referral',
    'đối tác': 'referral', 'doi tac': 'referral',
}

# legacy `Client_Type` / `loai_khach_hnagf` -> res.partner.client_type
CLIENT_TYPE_MAP = {'mới': 'new', 'moi': 'new', 'cũ': 'repeat', 'cu': 'repeat'}

# legacy `dich_vu_quan_tam` -> crm.lead.service_interest
SERVICE_INTEREST_MAP = {
    'chăm sóc giảm nhẹ': 'palliative',
    'chăm sóc cá nhân': 'personal_care',
    'chăm sóc vết thương': 'wound_care',
    'bác sĩ khám': 'consultation',
    'bác sĩ khám, siêu âm': 'consultation',
    'tiêm': 'injection',
    'truyền': 'iv_infusion',
    'thụt tháo': 'enema',
    'đặt, rút sonde': 'catheter',
    'hút đờm, vỗ rung đờm': 'sputum_care',
    'xét nghiệm': 'lab_test',
    'khác': 'other',
}

# legacy `cskh_3` (CSKH disposition) -> crm.lead.health_contact_outcome
CONTACT_OUTCOME_MAP = {
    'chốt dùng dịch vụ': 'service_booked',
    'không nghe máy': 'no_answer',
    'không phản hồi': 'no_response',
    'bận gọi lại sau': 'pending_follow_up',
    'cân nhắc thêm': 'future_opportunity',
    'tham khảo dịch vụ': 'service_inquiry',
    'từ chối dịch vụ': 'rejected',
}

# Lookup records are stored under their English name (the Vietnamese wording is
# a translation), but the export speaks Vietnamese — so resolve VI -> EN first.
CANCEL_REASON_VI_TO_EN = {_norm_key(vi): en
                          for en, vi, _t, _s in CANCELLATION_REASONS}
LOST_REASON_VI_TO_EN = {_norm_key(vi): en for en, vi in LOST_REASONS}

# legacy clinic/branch label -> official facility code (see health.facility).
# The export carries branch names on `Contact_phong_kham` (booking) and
# `phong_kham` (contact); `phong_kham_city` only knows the city.
FACILITY_CODE_MAP = {
    'hà nội': '01_01_00', 'ha noi': '01_01_00', 'hanoi': '01_01_00', 'hn': '01_01_00',
    'hồ chí minh': '02_01_00', 'ho chi minh': '02_01_00', 'hcmc': '02_01_00',
    'hcm': '02_01_00', 'tphcm': '02_01_00', 'tp hcm': '02_01_00',
    'hanoi_ns_minhkhai': '01_01_01', 'hn_ns_minh_khai': '01_01_01',
    'hanoi_ns_hadong': '01_01_02', 'hn_ns_hà_đông': '01_01_02',
    'hcmc_ns_thuduc': '02_01_01', 'tphcm_ns_thủ_đức': '02_01_01',
    'hcmc_ns_tanthuan': '02_01_02', 'tphcm_ns_tân_thuận': '02_01_02',
}

CITY_MAP = {
    'hcmc': 'hcm', 'hcm': 'hcm', 'ho chi minh': 'hcm', 'hồ chí minh': 'hcm',
    'tp hcm': 'hcm', 'tphcm': 'hcm',
    'hanoi': 'hn', 'hn': 'hn', 'hà nội': 'hn', 'ha noi': 'hn',
}

# legacy dân tộc (ethnicity) -> res.partner.ethnicity selection key
ETHNICITY_MAP = {
    'kinh': 'kinh', 'tày': 'tay', 'tay': 'tay', 'thái': 'thai', 'thai': 'thai',
    'mường': 'muong', 'muong': 'muong', 'khmer': 'khmer', 'khơ me': 'khmer',
    'hoa': 'hoa', 'nùng': 'nung', 'nung': 'nung', "h'mông": 'hmong', 'hmông': 'hmong',
    'mông': 'hmong', 'dao': 'dao', 'gia rai': 'gia_rai', 'gia-rai': 'gia_rai',
    'ê đê': 'ede', 'ede': 'ede', 'ba na': 'ba_na', 'xơ đăng': 'sedang',
    'cơ ho': 'co_ho', 'chăm': 'cham', 'cham': 'cham', 'sán chay': 'san_chay',
    'khác': 'other', 'other': 'other',
}
CATCHMENT_XMLID = {'hcm': 'health_base.catchment_province_hcm',
                   'hn': 'health_base.catchment_province_hanoi'}

# legacy FSO status -> (state, stage xml-id).
# 'Dời lịch' (rescheduled) has no state of its own — it lands on confirmed and
# raises the is_rescheduled flag instead (see _upsert_booking).
FSO_STATUS_MAP = {
    'đã hoàn thành': ('completed', 'health_fieldservice.stage_completed'),
    'da hoan thanh': ('completed', 'health_fieldservice.stage_completed'),
    'huỷ': ('cancelled', 'health_fieldservice.stage_cancelled'),
    'hủy': ('cancelled', 'health_fieldservice.stage_cancelled'),
    'huy': ('cancelled', 'health_fieldservice.stage_cancelled'),
    'mới': ('confirmed', 'health_fieldservice.stage_booked'),
    'moi': ('confirmed', 'health_fieldservice.stage_booked'),
    'đặt chỗ mới': ('confirmed', 'health_fieldservice.stage_booked'),
    'dat cho moi': ('confirmed', 'health_fieldservice.stage_booked'),
    'dời lịch': ('confirmed', 'health_fieldservice.stage_booked'),
    'doi lich': ('confirmed', 'health_fieldservice.stage_booked'),
    'lịch tiếp theo': ('confirmed', 'health_fieldservice.stage_booked'),
    'lich tiep theo': ('confirmed', 'health_fieldservice.stage_booked'),
    'đang tiến hành': ('in_progress', 'health_fieldservice.stage_en_route'),
    'dang tien hanh': ('in_progress', 'health_fieldservice.stage_en_route'),
}
FSO_STATUS_FALLBACK = ('draft', 'health_fieldservice.stage_draft')

# legacy statuses that mean "the appointment was moved"
FSO_RESCHEDULED_STATUSES = ('dời lịch', 'doi lich')

# legacy contact status -> (contact_status, stage xml-id)
LEAD_STATUS_MAP = {
    'mới': ('lead', 'health_crm.stage_healthcare_contact'),
    'moi': ('lead', 'health_crm.stage_healthcare_contact'),
    'đặt lịch hẹn': ('booking', 'health_crm.stage_healthcare_booking'),
    'dat lich hen': ('booking', 'health_crm.stage_healthcare_booking'),
    'huỷ': ('lost_booking', 'health_crm.stage_healthcare_lost'),
    'hủy': ('lost_booking', 'health_crm.stage_healthcare_lost'),
    'đang suy nghĩ': ('thinking', 'health_crm.stage_healthcare_qualification'),
    'dang suy nghi': ('thinking', 'health_crm.stage_healthcare_qualification'),
    'liên hệ lại': ('recontact', 'health_crm.stage_healthcare_contact'),
    'lien he lai': ('recontact', 'health_crm.stage_healthcare_contact'),
    'đã sử dụng': ('service_used', 'health_crm.stage_healthcare_won'),
    'da su dung': ('service_used', 'health_crm.stage_healthcare_won'),
    'cũ': ('existing', 'health_crm.stage_healthcare_won'),
    'cu': ('existing', 'health_crm.stage_healthcare_won'),
}
LEAD_STATUS_FALLBACK = ('active', None)

# legacy `nguon_khach_hang` -> crm.lead.healthcare_lead_source.
# Partner/school/named-referrer values are not listed: they resolve to the
# generic 'partner'/'referral_patient' keys in _lead_source(), with the raw
# string preserved on the linked utm.source.
LEAD_SOURCE_MAP = {
    'hotline': 'phone_inquiry',
    'zalo': 'zalo_marketing',
    'facebook': 'facebook_ad',
    'form': 'website_form',
    'website': 'website_form',
    'google': 'google',
    'tiktok': 'tiktok',
    'khách hàng cũ': 'former_client', 'khach hang cu': 'former_client',
    'tự đến pk': 'walk_in', 'tu den pk': 'walk_in',
    'người giới thiệu': 'referral_patient', 'nguoi gioi thieu': 'referral_patient',
    'bác sĩ/điều dưỡng': 'referral_doctor', 'bac si/dieu duong': 'referral_doctor',
    'đối tác': 'partner', 'doi tac': 'partner',
    'inbox': 'inbox_email',
}

# selection columns to validate up-front: (file, column, map, allow_blank)
SELECTION_COLUMNS = [
    ('booking', 'Contact_gioi_tinh', GENDER_MAP, True),
    ('booking', 'hinh_thuc_thanh_toan', PAYMENT_METHOD_MAP, True),
    ('booking', 'thanh_toan', PAYMENT_STATUS_MAP, True),
    ('booking', 'phong_kham_city', CITY_MAP, False),
    ('booking', 'trang_thai', FSO_STATUS_MAP, False),
    ('booking', 'dich_vu_tai', SERVICE_LOCATION_MAP, True),
    ('booking', 'Client_Type', CLIENT_TYPE_MAP, True),
    ('contact', 'gioi_tinh', GENDER_MAP, True),
    ('contact', 'Status', LEAD_STATUS_MAP, False),
    ('contact', 'cskh_3', CONTACT_OUTCOME_MAP, True),
    ('contact', 'loai_khach_hnagf', CLIENT_TYPE_MAP, True),
]


class MigrationRunner(models.Model):
    _name = 'migration.runner'
    _description = 'Legacy Migration Runner'

    name = fields.Char(default='runner')

    # process-level cache of the reviewed service mapping (see _service_mapping)
    _svc_map_cache = None
    _svc_map_groups = {}

    # ------------------------------------------------------------ utilities
    def _bulk_ctx(self, model):
        # skip_auto_geocode + skip_distance_recompute keep the import from making a
        # synchronous geocode API call per client (which stalls when outbound
        # requests are blocked). Coordinates + driving distance are backfilled
        # separately afterwards via backfill_geo() (see the real-export runbook).
        return self.env[model].with_context(
            mail_create_nolog=True, tracking_disable=True,
            mail_notrack=True, skip_notification=True, active_test=False,
            skip_auto_geocode=True, skip_distance_recompute=True,
        )

    def _only_fields(self, model, vals):
        flds = self.env[model]._fields
        return {k: v for k, v in vals.items() if k in flds}

    def _mk(self, model, vals):
        return self._bulk_ctx(model).create(self._only_fields(model, vals))

    # ---- transformers
    def _phone(self, raw):
        if not raw:
            return None, None
        try:
            return normalize_vn_phone(str(raw)), None
        except ValidationError:
            return None, str(raw)

    def _money(self, v):
        if v in (None, '', False):
            return 0.0
        try:
            return float(str(v).replace(',', '').strip() or 0)
        except Exception:
            return 0.0

    def _parse_date_any(self, v):
        """Accept ISO date/datetime string, or 'dd/mm/yyyy' (optionally with a
        leading 'HH:MM ' time prefix as in '19:00 02/10/1991')."""
        if not v:
            return None
        s = str(v).strip()
        # ISO from the local converter
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            pass
        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return date(y, mo, d)
            except ValueError:
                return None
        return None

    def _parse_dob(self, v):
        return self._parse_date_any(v)

    def _gender_id(self, raw):
        """GENDER_MAP code -> health.lookup.value id, or False.

        Gender stopped being a Selection when it joined the client-editable
        dropdown vocabularies, so the migration resolves the code it already
        derives into the `gender` vocabulary rather than writing a varchar.
        Cached per run: this is called once per imported row.
        """
        code = GENDER_MAP.get(_norm(raw))
        if not code:
            return False
        cache = getattr(self, '_gender_id_cache', None)
        if cache is None:
            cache = {
                v.code: v.id
                for v in self.env['health.lookup.value']
                .with_context(active_test=False)
                .search([('category_code', '=', 'gender')])
            }
            type(self)._gender_id_cache = cache
        return cache.get(code, False)

    def _parse_dt(self, v):
        """'dd/mm/yyyy HH:MM' -> naive datetime (treated as local, stored UTC)."""
        if not v:
            return None
        s = str(v).strip()
        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})', s)
        if m:
            d, mo, y, h, mi = (int(m.group(i)) for i in range(1, 6))
            try:
                naive = datetime(y, mo, d, h, mi)
                return VN_TZ.localize(naive).astimezone(pytz.utc).replace(tzinfo=None)
            except ValueError:
                return None
        dd = self._parse_date_any(s)
        return datetime(dd.year, dd.month, dd.day) if dd else None

    def _parse_time(self, v):
        if not v:
            return None
        m = re.match(r'\s*(\d{1,2}):(\d{2})', str(v))
        if m:
            return int(m.group(1)), int(m.group(2))
        return None

    def _combine_local_to_utc(self, date_v, time_v):
        d = self._parse_date_any(date_v)
        t = self._parse_time(time_v)
        if not d:
            return None
        h, mi = t if t else (0, 0)
        naive = datetime(d.year, d.month, d.day, h, mi)
        return VN_TZ.localize(naive).astimezone(pytz.utc).replace(tzinfo=None)

    def _duration(self, time_in, time_out):
        a, b = self._parse_time(time_in), self._parse_time(time_out)
        if a and b:
            mins = (b[0] * 60 + b[1]) - (a[0] * 60 + a[1])
            if mins > 0:
                return mins
        return 60

    def _booking_ref(self, row):
        basis = '|'.join(str(row.get(k) or '') for k in
                         ('Client ID', 'Appointment Date', 'time_in', 'dich_vu', 'CreatedOn'))
        return 'BKG-' + hashlib.md5(basis.encode('utf-8')).hexdigest()[:16]

    # ---- xref
    def _xref_lookup(self, model, key):
        rec = self.env['migration.xref'].search(
            [('target_model', '=', model), ('legacy_key', '=', key)], limit=1)
        return rec.res_id if rec else None

    def _xref_store(self, model, key, res_id, raw=None, auto=False, notes=None):
        if self._xref_lookup(model, key):
            return
        self.env['migration.xref'].create({
            'source': 'legacy_mig', 'target_model': model, 'legacy_key': key,
            'res_id': res_id, 'raw_value': (raw or '')[:255],
            'auto_created': auto, 'notes': notes,
        })

    # ---- resolvers
    def _catchment(self, city_raw):
        code = CITY_MAP.get(_norm(city_raw))
        if not code:
            return None
        rec = self.env.ref(CATCHMENT_XMLID[code], raise_if_not_found=False)
        if not rec:
            rec = self.env['health.catchment.province'].search(
                [('code', '=', code.upper())], limit=1)
        return rec or None

    def _facility(self, city_raw):
        code = CITY_MAP.get(_norm(city_raw))
        if not code:
            return None
        key = 'facility:' + code
        rid = self._xref_lookup('health.facility', key)
        if rid:
            return self.env['health.facility'].browse(rid)
        catch = self._catchment(city_raw)
        # Facilities are master data (the six official codes). Match only —
        # never invent one from the export.
        Fac = self.env['health.facility'].with_context(active_test=False)
        fac = self.env['health.facility']
        if catch:
            fac = Fac.search([('catchment_province_id', '=', catch.id),
                              ('active', '=', True)], limit=1)
        if fac:
            self._xref_store('health.facility', key, fac.id, raw=city_raw)
            return fac
        return None

    def _facility_by_branch(self, *labels):
        """Resolve the official facility from a legacy clinic/branch label.

        The export names the branch on `Contact_phong_kham` / `phong_kham`
        (e.g. 'Hanoi_NS_MinhKhai') and only the city on `phong_kham_city`.
        Each label is tried in order; the first that maps to an official code
        wins, so callers pass branch first and city last. Returns None when
        nothing matches (e.g. the literal 'Khác'), letting the caller fall back
        to the city-level resolver.
        """
        Fac = self.env['health.facility'].with_context(active_test=False)
        for label in labels:
            for seg in str(label or '').split(';'):
                code = FACILITY_CODE_MAP.get(_norm_key(seg))
                if not code:
                    continue
                key = 'facility:code:' + code
                rid = self._xref_lookup('health.facility', key)
                if rid:
                    fac = Fac.browse(rid)
                    if fac.exists():
                        return fac
                fac = Fac.search([('code', '=', code)], limit=1)
                if fac:
                    self._xref_store('health.facility', key, fac.id, raw=str(seg))
                    return fac
        return None

    def _reason_record(self, model, prefix, vi_to_en, raw):
        """Resolve a Vietnamese legacy reason string to its lookup record.

        The records are created with an English ``name`` plus a Vietnamese
        translation, so a legacy value is translated to English first. Falling
        back to a direct name match keeps values that were entered manually (or
        already in English) working.
        """
        name = str(raw or '').strip()
        if not name:
            return None
        target = _norm_key(name)
        key = prefix + target[:120]
        Reason = self.env[model].with_context(active_test=False)
        rid = self._xref_lookup(model, key)
        if rid:
            rec = Reason.browse(rid)
            if rec.exists():
                return rec
        english = vi_to_en.get(target)
        rec = Reason.search([('name', '=', english)], limit=1) if english else None
        if not rec:
            rec = Reason.search([('name', '=ilike', name)], limit=1)
        if not rec:
            rec = Reason.search([]).filtered(
                lambda r: _norm_key(r.name) == target)[:1]
        if rec:
            self._xref_store(model, key, rec.id, raw=name)
            return rec
        return None

    def _cancel_reason(self, raw):
        return self._reason_record('health.booking.cancellation.reason',
                                   'cancelreason:', CANCEL_REASON_VI_TO_EN, raw)

    def _lost_reason(self, raw):
        return self._reason_record('crm.lost.reason', 'lostreason:',
                                   LOST_REASON_VI_TO_EN, raw)

    def _utm_source(self, raw, report=None):
        """Match a legacy source to a utm.source seeded from Lookup.xlsx.

        Never creates one: the source list is master data. A source present in
        the export but absent from the lookup master is reported instead, so it
        can be added to the master deliberately rather than by import.
        """
        name = str(raw or '').strip()
        if not name:
            return None
        key = 'utmsource:' + _norm_key(name)[:120]
        Src = self.env['utm.source'].with_context(active_test=False)
        rid = self._xref_lookup('utm.source', key)
        if rid:
            rec = Src.browse(rid)
            if rec.exists():
                return rec
        rec = Src.search([('name', '=ilike', name)], limit=1)
        if rec:
            self._xref_store('utm.source', key, rec.id, raw=name)
            return rec
        if report is not None:
            report['unmatched_sources'].add(name[:120])
        return None

    def _lead_for_booking(self, row):
        """Find the contact (crm.lead) a booking originated from.

        Primary key is the Pancake customer id, which import_contacts stores in
        migration.xref. That column is empty in the redacted sample but present
        in the real export. The phone fallback only accepts an unambiguous
        single match, so a shared family number never links the wrong contact.
        """
        Lead = self.env['crm.lead'].with_context(active_test=False)
        for col in ('PancakeCustomer ID', 'Contact_customer_id', 'customer_id'):
            v = str(row.get(col) or '').strip()
            if not v:
                continue
            rid = self._xref_lookup('crm.lead', 'pancakecust:' + _norm(v))
            if rid:
                lead = Lead.browse(rid)
                if lead.exists():
                    return lead
        phone, _bad = self._phone(row.get('so_dien_thoai'))
        if phone:
            leads = Lead.search([('phone', '=', phone),
                                 ('legacy_contact_guid', '!=', False)], limit=2)
            if len(leads) == 1:
                return leads
        return None

    def _service_interest(self, raw):
        """Map a legacy 'dịch vụ quan tâm' string to the selection key."""
        v = _norm_key(raw)
        if not v:
            return None
        if v in SERVICE_INTEREST_MAP:
            return SERVICE_INTEREST_MAP[v]
        # the export appends free text ('Bác sĩ khám, siêu âm,..') — take the
        # longest listed value that the string starts with
        for legacy in sorted(SERVICE_INTEREST_MAP, key=len, reverse=True):
            if v.startswith(legacy):
                return SERVICE_INTEREST_MAP[legacy]
        return None

    # Tokens that are NOT real staff (lab/diagnostic markers) -> skipped.
    _NON_STAFF = ('diag', 'greenlab', 'lab', 'diagnostic')

    def _normalize_nurse_name(self, seg):
        """Turn ONE legacy nurse segment into (clean_name, is_doctor).

        Handles: city prefix (HCM/HN, hyphen or en-dash), role tokens
        (ĐD/DD/DT/ĐDT/DDT/ĐDPT/DDPT/BS/BSCKI/Dr), 'Partime' marker and a
        trailing 'Oncall' shift marker. Example:
        'HN – DD NGUYỄN THỊ HẰNG ONCALL' -> ('NGUYỄN THỊ HẰNG', False)
        'HCM - BS TRẦN THANH TÂM'        -> ('TRẦN THANH TÂM', True)
        """
        s = (seg or '').strip().replace('–', '-').replace('—', '-')
        s = re.sub(r'\s+', ' ', s)
        # drop leading city prefix
        s = re.sub(r'^(HCMC|HCM|HANOI|HN)\s*-\s*', '', s, flags=re.I)
        is_doctor = bool(re.match(r'^\s*(BS|Dr)\b', s, flags=re.I))
        # drop leading role token + its separator (space, dot or underscore)
        s = re.sub(r'^(ĐDPT|DDPT|ĐDT|DDT|ĐD|DD|DT|BSCK[I0-9]*|BS|Dr)[\s._]+',
                   '', s, flags=re.I)
        # drop 'Partime' marker
        s = re.sub(r'^part[\s_-]?time\s+', '', s, flags=re.I)
        # drop trailing on-call marker
        s = re.sub(r'[\s_-]*oncall\s*$', '', s, flags=re.I)
        return s.strip(' _-'), is_doctor

    def _staff_segment(self, seg):
        """Resolve ONE nurse/doctor segment to an hr.employee (get-or-create)."""
        name, is_doctor = self._normalize_nurse_name(seg)
        if not name or _norm(name) in self._NON_STAFF:
            return None
        key = 'staff:' + _norm(name)
        rid = self._xref_lookup('hr.employee', key)
        if rid:
            emp = self.env['hr.employee'].with_context(active_test=False).browse(rid)
            if emp.exists():
                return emp
        Emp = self.env['hr.employee'].with_context(active_test=False)
        emp = Emp.search([('name', '=ilike', name)], limit=1)
        if not emp:
            emp = self._mk('hr.employee', {
                'name': name, 'is_healthcare_staff': True,
                'healthcare_role': 'doctor' if is_doctor else 'nurse',
                'employment_status': 'active',
            })
            self._xref_store('hr.employee', key, emp.id, raw=seg, auto=True,
                             notes='staff stub ' + ('doctor' if is_doctor else 'nurse'))
        else:
            self._xref_store('hr.employee', key, emp.id, raw=seg)
        return emp

    def _staff_list(self, raw):
        """Split a (possibly multi-nurse, ';'-separated) legacy string into a
        deduped recordset of hr.employee (creating individuals as needed)."""
        emps = self.env['hr.employee']
        if not raw:
            return emps
        seen = set()
        for seg in str(raw).replace('–', '-').split(';'):
            seg = seg.strip()
            if not seg:
                continue
            emp = self._staff_segment(seg)
            if emp and emp.id not in seen:
                seen.add(emp.id)
                emps |= emp
        return emps

    def _staff(self, raw):
        """Backward-compatible single resolver (first individual nurse)."""
        return self._staff_list(raw)[:1] or None

    def _product(self, name, report=None, province_hint=None):
        """Match a legacy service string to a master product.

        The price list is the source of truth: the migration matches against it
        and NEVER creates a product from booking free text. Anything that does
        not match falls back to the single explicit 'unmapped legacy service'
        product so the invoice line (and therefore the revenue) still exists,
        with the original wording preserved on the line itself. Every such
        string is reported for a human decision.
        """
        name = (name or '').strip()
        if not name:
            return None
        key = 'product:' + _norm(name)[:120]
        rid = self._xref_lookup('product.product', key)
        if rid:
            prod = self.env['product.product'].browse(rid)
            if prod.exists() and prod.active:
                return prod
        # the ops-reviewed mapping is the bridge from legacy wording to a
        # price-list item; without it a free-text name matches almost nothing
        seg = self._service_mapping().get(_norm_key(name))
        if seg:
            if seg.get('kind') == 'ADJUSTMENT':
                return self._surcharge_product() or self._unmapped_product()
            prod = self._pricelist_product(seg.get('item_code'), province_hint)
            if prod:
                self._xref_store('product.product', key, prod.id, raw=name)
                return prod
        Product = self.env['product.product'].with_context(active_test=False)
        prod = Product.search([('name', '=', name), ('active', '=', True)], limit=1)
        if prod:
            self._xref_store('product.product', key, prod.id, raw=name)
            return prod
        if report is not None:
            report['unmatched_services'].add(name[:120])
        return self._unmapped_product()

    def _service_mapping(self):
        """The ops-reviewed legacy-text -> price-list mapping, keyed by _norm_key.

        Path comes from the `health_migration.service_mapping_path` parameter so
        the reviewed file can be refreshed without a code change.
        """
        if getattr(self, '_svc_map_cache', None) is not None:
            return self._svc_map_cache
        path = self.env['ir.config_parameter'].sudo().get_param(
            'health_migration.service_mapping_path', '/tmp/service_mapping.json')
        data = {}
        try:
            with open(path, encoding='utf-8') as fh:
                payload = json.load(fh)
            for s in payload.get('segments', []):
                data[s['norm']] = s
            self._svc_map_groups = {g['vi']: g for g in payload.get('groups', [])}
        except Exception as e:  # noqa: BLE001
            _logger.warning('service mapping not loaded from %s: %s', path, e)
            self._svc_map_groups = {}
        type(self)._svc_map_cache = data
        return data

    def _surcharge_product(self):
        tmpl = self.env.ref('health_migration.product_legacy_surcharge',
                            raise_if_not_found=False)
        return tmpl.product_variant_id if tmpl else None

    def _unmapped_product(self):
        """The one deliberate placeholder for services absent from the price list."""
        tmpl = self.env.ref('health_migration.product_legacy_unmapped',
                            raise_if_not_found=False)
        if not tmpl:
            return None
        # the xmlid points at the template; sale lines need the variant
        return tmpl.product_variant_id or None

    def _service_type(self, name, report=None):
        """Match a legacy service string to a master service type.

        Never creates one: the service catalogue belongs to the price list. When
        nothing matches, the booking simply gets no appointment type rather than
        a catalogue entry invented from free text.
        """
        name = (name or '').strip()
        if not name:
            return None
        key = 'svctype:' + _norm(name)[:120]
        rid = self._xref_lookup('health.service.type', key)
        if rid:
            st = self.env['health.service.type'].browse(rid)
            if st.exists():
                return st
        ST = self.env['health.service.type'].with_context(active_test=False)
        seg = self._service_mapping().get(_norm_key(name))
        group = (seg or {}).get('group_vi')
        if group:
            code = ('PL' + hashlib.md5(group.encode()).hexdigest()[:6]).upper()[:10]
            st = ST.search([('code', '=', code), ('active', '=', True)], limit=1)
            if st:
                self._xref_store('health.service.type', key, st.id, raw=name)
                return st
        st = ST.search([('name', '=', name), ('active', '=', True)], limit=1)
        if st:
            self._xref_store('health.service.type', key, st.id, raw=name)
            return st
        if report is not None:
            report['unmatched_service_types'].add(name[:120])
        return None

    # ---- status resolvers
    def _fso_status(self, raw, report):
        v = FSO_STATUS_MAP.get(_norm(raw))
        if not v:
            report['unmapped_fso_status'].add(str(raw))
            return FSO_STATUS_FALLBACK
        return v

    def _lead_status(self, raw, report):
        v = LEAD_STATUS_MAP.get(_norm(raw))
        if not v:
            report['unmapped_lead_status'].add(str(raw))
            return LEAD_STATUS_FALLBACK
        return v

    # ------------------------------------------------------------- report
    def _new_report(self):
        return {
            'clients_created': 0, 'clients_updated': 0, 'client_skipped': 0,
            'bookings_created': 0, 'bookings_updated': 0,
            'assignments': 0, 'payments': 0, 'sale_orders': 0, 'sale_lines': 0,
            'leads_created': 0, 'leads_updated': 0, 'lead_skipped': 0,
            'bad_phones': [], 'client_no_catchment': [], 'booking_errors': [],
            'assignment_errors': [], 'payment_errors': [], 'sale_errors': [],
            'lead_errors': [], 'unmapped_fso_status': set(),
            'unmapped_lead_status': set(), 'archived': {},
            'unmapped_cancel_reason': set(), 'unmapped_lost_reason': set(),
            'unmatched_services': set(), 'unmatched_service_types': set(),
            'unmatched_sources': set(), 'unmatched_facilities': set(),
            'client_named_referrers': set(), 'bookings_linked_to_lead': 0,
            'cancel_reasons_linked': 0, 'lost_reasons_linked': 0,
            'sale_revenue': 0.0, 'sale_discount': 0.0,
        }

    # ------------------------------------------------------------- imports
    def _upsert_client(self, row, report):
        code = str(row.get('Client ID') or '').strip()
        if not code:
            report['client_skipped'] += 1
            return None
        catch = self._catchment(row.get('phong_kham_city'))
        if not catch:
            report['client_no_catchment'].append(code)
            return None
        # branch-level facility first (the export names the branch on
        # Contact_phong_kham); fall back to the city-level resolver
        fac = self._facility_by_branch(row.get('Contact_phong_kham'),
                                       row.get('phong_kham_city'))
        if not fac:
            fac = self._facility(row.get('phong_kham_city'))
        Partner = self._bulk_ctx('res.partner')
        p = Partner.search([('legacy_client_code', '=', code)], limit=1)
        name = str(row.get('ten_benh_nhan') or '').strip() or ('BN ' + code)
        mobile, bad = self._phone(row.get('so_dien_thoai'))
        if bad:
            report['bad_phones'].append(code)
        vals = {
            'name': name, 'is_patient': True, 'customer_rank': 1,
            'company_type': 'person', 'legacy_client_code': code,
            'catchment_province_id': catch.id,
            'primary_facility_id': fac.id if fac else False,
        }
        g = self._gender_id(row.get('Contact_gioi_tinh'))
        if g:
            vals['gender_id'] = g
        dob = self._parse_dob(row.get('Contact_nam_sinh'))
        if dob:
            vals['birth_date'] = dob
        if mobile:
            vals['mobile'] = mobile
        if row.get('so_cccd'):
            vals['national_id'] = str(row['so_cccd']).strip()
        if row.get('nghe_nghiep'):
            vals['profession'] = str(row['nghe_nghiep']).strip()
        eth = ETHNICITY_MAP.get(_norm(row.get('dan_toc')))
        if eth:
            vals['ethnicity'] = eth
        addr = str(row.get('Contact_Address') or row.get('Contact_FullAddress') or '').strip()
        if addr:
            vals['street'] = addr
        # second phone (mobile already holds the primary number)
        phone2, _bad2 = self._phone(row.get('so_dien_thoai_2'))
        if phone2:
            vals['phone'] = phone2
        # acquisition source — the raw legacy string is always preserved
        raw_src = str(row.get('SourceofClient') or '').strip()
        if raw_src:
            vals['source_details'] = raw_src[:255]
            mapped = CLIENT_SOURCE_MAP.get(_norm_key(raw_src))
            vals['source_type'] = mapped or 'referral'
            if not mapped:
                # a named referrer or partner organisation: keep it verbatim and
                # give it a utm.source so acquisition reporting can group on it
                vals['referral_source'] = raw_src[:255]
                self._utm_source(raw_src, report)
                report['client_named_referrers'].add(raw_src)
        # new/repeat: once a client is seen as 'repeat' it stays repeat
        ctype = CLIENT_TYPE_MAP.get(_norm(row.get('Client_Type')))
        if ctype == 'repeat' or (ctype and not (p and p.client_type)):
            vals['client_type'] = ctype
        ad_ids = self._legacy_ad_ids(row, prefix_variants=('Contact_',))
        if ad_ids:
            vals['legacy_ad_ids'] = ad_ids
        vals = self._only_fields('res.partner', vals)
        try:
            if p:
                p.write(vals)
                report['clients_updated'] += 1
            else:
                p = Partner.create(vals)
                report['clients_created'] += 1
            return p
        except Exception as e:
            report['booking_errors'].append('client %s: %s' % (code, e))
            return None

    _AD_COLUMNS = ('page_id', 'ad_id', 'ad_id_fb', 'ad_id_tiktok',
                   'conversation_id', 'psid', 'Facebook Link',
                   'PancakeCustomer ID', 'PancakeCustomer', 'customer_id')

    def _legacy_ad_ids(self, row, prefix_variants=()):
        """Bundle the legacy marketing/channel identifiers into one dict.

        These have no CRM home individually (they are Pancake/Facebook tracking
        ids); keeping them together preserves the data without adding a column
        per tracker. Returns None when the row carries none of them.
        """
        out = {}
        for col in self._AD_COLUMNS:
            for prefix in ('',) + tuple(prefix_variants):
                v = row.get(prefix + col)
                if v in (None, '', False):
                    continue
                out[col.lower().replace(' ', '_')] = str(v).strip()
                break
        return out or None

    def _upsert_booking(self, row, client, report):
        ref = self._booking_ref(row)
        FSO = self._bulk_ctx('health.fieldservice.order')
        fso = FSO.search([('legacy_booking_ref', '=', ref)], limit=1)
        fac = self._facility_by_branch(row.get('Contact_phong_kham'),
                                       row.get('phong_kham_city'))
        if not fac:
            fac = self._facility(row.get('phong_kham_city'))
        sched = self._combine_local_to_utc(row.get('Appointment Date'), row.get('time_in'))
        state, stage_xmlid = self._fso_status(row.get('trang_thai'), report)
        # service_location is written unconditionally: the first migration pass
        # hard-coded 'home', so a conditional write would leave clinic bookings
        # wrong forever.
        location = SERVICE_LOCATION_MAP.get(_norm_key(row.get('dich_vu_tai')),
                                            SERVICE_LOCATION_FALLBACK)
        vals = {
            'patient_id': client.id,
            'facility_id': fac.id if fac else False,
            'service_type': 'home_visit', 'service_location': location,
            'scheduled_duration': self._duration(row.get('time_in'), row.get('time_out')),
            'state': state, 'legacy_booking_ref': ref, 'booking_source': 'phone',
            'is_rescheduled': _norm(row.get('trang_thai')) in FSO_RESCHEDULED_STATUSES,
        }
        if sched:
            vals['scheduled_datetime'] = sched
        if stage_xmlid:
            st = self.env.ref(stage_xmlid, raise_if_not_found=False)
            if st:
                vals['stage_id'] = st.id
        note = ' '.join(filter(None, [str(row.get('note') or ''),
                                      str(row.get('mo_ta_tinh_trang') or '')])).strip()
        if note:
            vals['patient_notes'] = note
        if _norm(row.get('trang_thai')) in ('huỷ', 'hủy', 'huy') and row.get('ly_do_huy'):
            # keep the free text AND link the structured reason record
            vals['cancellation_notes'] = str(row['ly_do_huy'])
            reason = self._cancel_reason(row['ly_do_huy'])
            if reason:
                vals['cancellation_reason_id'] = reason.id
            else:
                report['unmapped_cancel_reason'].add(str(row['ly_do_huy']))
        parking = self._money(row.get('gui_xe'))
        if parking > 0:
            vals['parking_charge'] = parking
        surcharge = self._money(row.get('phu_phi'))
        if surcharge > 0:
            vals['travel_charge'] = surcharge
        # legacy audit trail
        for col, field in (('CreatedBy', 'legacy_created_by'),
                           ('ModifiedBy', 'legacy_modified_by'),
                           ('phong_kham_Owner', 'legacy_owner')):
            v = str(row.get(col) or '').strip()
            if v:
                vals[field] = v[:255]
        mod_on = self._parse_dt(row.get('ModifiedOn'))
        if mod_on:
            vals['legacy_modified_on'] = mod_on
        lead = self._lead_for_booking(row)
        if lead:
            vals['crm_lead_id'] = lead.id
        vals = self._only_fields('health.fieldservice.order', vals)
        if fso:
            # Re-writing an unchanged stage still runs the stage-transition
            # guard, which rejects e.g. a Completed booking that has no staff
            # (the lab-token rows). Dropping the no-op keys lets the rest of the
            # correction land on those bookings instead of failing the whole row.
            if vals.get('stage_id') == fso.stage_id.id:
                vals.pop('stage_id', None)
            if vals.get('state') == fso.state:
                vals.pop('state', None)
        try:
            if fso:
                fso.write(vals)
                report['bookings_updated'] += 1
            else:
                fso = FSO.create(vals)
                report['bookings_created'] += 1
        except Exception as e:
            report['booking_errors'].append('%s: %s' % (ref, e))
            return None

        # primary service type
        names = [s.strip() for s in str(row.get('dich_vu') or '').split(';') if s.strip()]
        if names and 'appointment_type_id' in fso._fields:
            st = self._service_type(names[0], report)
            if st:
                try:
                    fso.write({'appointment_type_id': st.id})
                except Exception:
                    pass
        # staff assignment — split multi-nurse ";" strings into individuals
        if 'assigned_staff_ids' in fso._fields:
            emps = self._staff_list(row.get('bac_si_dieu_duong'))
            if emps:
                try:
                    fso.write({'assigned_staff_ids': [(6, 0, emps.ids)]})
                    report['assignments'] += len(emps)
                except Exception as e:
                    report['assignment_errors'].append('%s: %s' % (ref, e))
        if fso.crm_lead_id:
            report['bookings_linked_to_lead'] += 1
        if fso.cancellation_reason_id:
            report['cancel_reasons_linked'] += 1
        # sale order + lines (best effort)
        self._make_sale_lines(names, fso, client, report, row)
        # payment
        self._make_payment(row, fso, client, report)
        return fso

    # ------------------------------------------------------------- money
    def _line_prices(self, row, n_lines):
        """Split the booking-level SubTotal across n_lines sale lines.

        The legacy export prices a booking, not a service line, so the total is
        distributed evenly and any rounding remainder is added to the first
        line — the order total then matches SubTotal to the dong. Discount is
        an absolute amount legacy-side; it is carried as a percentage so the
        net stays exact regardless of how the lines are split.

        Returns (list_of_unit_prices, discount_percent, quantity_for_single_line).
        """
        subtotal = self._money(row.get('SubTotal'))
        discount = self._money(row.get('Discount'))
        qty = self._money(row.get('TotalQuantity'))
        if subtotal <= 0 or n_lines <= 0:
            return [0.0] * n_lines, 0.0, 1.0
        pct = round(discount / subtotal * 100.0, 4) if discount > 0 else 0.0
        if n_lines == 1:
            # a single service: keep the real quantity and derive the unit price
            q = qty if qty > 0 else 1.0
            return [round(subtotal / q, 2)], pct, q
        share = round(subtotal / n_lines, 2)
        prices = [share] * n_lines
        prices[0] = round(subtotal - share * (n_lines - 1), 2)
        return prices, pct, 1.0

    def _make_sale_lines(self, names, fso, client, report, row=None):
        if not names:
            return
        SO = self._bulk_ctx('sale.order')
        existing = SO.search([('origin', '=', fso.legacy_booking_ref)], limit=1)
        if existing:
            # already imported: only correct the pricing (the first pass wrote 0)
            if row is not None:
                self._reprice_order(existing, row, report)
            return
        prices, pct, qty = self._line_prices(row or {}, len(names))
        province = ('hcmc' if (fso.facility_id.code or '').startswith('02')
                    else 'hanoi')
        lines = []
        for i, nm in enumerate(names):
            prod = self._product(nm, report, province)
            if prod:
                line = {'product_id': prod.id,
                        'product_uom_qty': qty if len(names) == 1 else 1,
                        'price_unit': prices[i] if i < len(prices) else 0.0,
                        'name': nm}
                if pct:
                    line['discount'] = pct
                    line['discount_reason'] = LEGACY_DISCOUNT_REASON
                lines.append((0, 0, line))
        if not lines:
            return
        vals = {'partner_id': client.id, 'origin': fso.legacy_booking_ref,
                'order_line': lines}
        if 'fso_id' in self.env['sale.order']._fields:
            vals['fso_id'] = fso.id
        try:
            so = SO.create(self._only_fields('sale.order', vals))
            report['sale_orders'] += 1
            report['sale_lines'] += len(lines)
            report['sale_revenue'] += self._money(row.get('SubTotal')) if row else 0.0
            report['sale_discount'] += self._money(row.get('Discount')) if row else 0.0
            return so
        except Exception as e:
            report['sale_errors'].append('%s: %s' % (fso.legacy_booking_ref, e))

    def _reprice_order(self, order, row, report):
        """Write the real prices onto an order imported at price 0."""
        lines = order.order_line.filtered(lambda l: not l.display_type)
        if not lines:
            return
        prices, pct, qty = self._line_prices(row, len(lines))
        if not any(prices):
            return
        changed = False
        for i, line in enumerate(lines):
            vals = {}
            new_price = prices[i] if i < len(prices) else 0.0
            if float(line.price_unit or 0.0) != new_price:
                vals['price_unit'] = new_price
            if len(lines) == 1 and float(line.product_uom_qty or 0.0) != qty:
                vals['product_uom_qty'] = qty
            if pct and float(line.discount or 0.0) != pct:
                vals['discount'] = pct
                # a discount without a reason is rejected by sale.order.line
                if not line.discount_reason:
                    vals['discount_reason'] = LEGACY_DISCOUNT_REASON
            if vals:
                try:
                    line.write(vals)
                    changed = True
                except Exception as e:
                    report['sale_errors'].append(
                        '%s reprice: %s' % (order.origin, str(e)[:80]))
        if changed:
            report['sale_repriced'] = report.get('sale_repriced', 0) + 1
            report['sale_revenue'] += self._money(row.get('SubTotal'))
            report['sale_discount'] += self._money(row.get('Discount'))

    def _payment_splits(self, row):
        """Return [(amount, method)] for a legacy booking row.

        Cash and transfer are kept as separate transactions so the method stays
        accurate when a visit was settled with both. A visit paid out of a
        prepayment balance carries no cash/transfer at all — it is recorded as
        a 'prepaid' transaction for the net amount so the booking still reads
        as paid.
        """
        cash = self._money(row.get('Cash'))
        transfer = self._money(row.get('TransferMoney'))
        splits = []
        if cash > 0:
            splits.append((cash, 'cash'))
        if transfer > 0:
            splits.append((transfer, 'bank_transfer'))
        # Cash/transfer amounts are real collections and keep their own method.
        # Only when nothing was collected does a 'prepaid' status mean the visit
        # was settled out of the client's balance.
        if not splits and PAYMENT_STATUS_MAP.get(_norm(row.get('thanh_toan'))) == 'prepaid':
            net = self._money(row.get('SubTotal')) - self._money(row.get('Discount'))
            if net > 0:
                splits.append((net, 'prepaid'))
        return splits

    def _make_payment(self, row, fso, client, report):
        splits = self._payment_splits(row)
        if not splits:
            return
        PT = self._bulk_ctx('health.payment.transaction')
        if PT.search([('fso_id', '=', fso.id)], limit=1):
            return
        txn_dt = self._parse_dt(row.get('CreatedOn')) or fso.scheduled_datetime or fields.Datetime.now()
        for amount, method in splits:
            vals = {'patient_id': client.id, 'fso_id': fso.id, 'amount': amount,
                    'payment_method': method, 'transaction_date': txn_dt,
                    'transaction_type': 'prepaid' if method == 'prepaid' else 'immediate',
                    'status': 'collected'}
            try:
                PT.create(self._only_fields('health.payment.transaction', vals))
                report['payments'] += 1
            except Exception as e:
                report['payment_errors'].append('%s: %s' % (fso.legacy_booking_ref, e))

    def import_contacts(self, rows, report):
        Lead = self._bulk_ctx('crm.lead')
        for row in rows:
            guid = str(row.get('ID') or '').strip()
            if not guid:
                report['lead_skipped'] += 1
                continue
            lead = Lead.search([('legacy_contact_guid', '=', guid)], limit=1)
            name = str(row.get('Name') or '').strip() or ('Contact ' + guid[:8])
            status, stage_xmlid = self._lead_status(row.get('Status'), report)
            mobile, _bad = self._phone(row.get('Phone'))
            vals = {'name': name, 'legacy_contact_guid': guid, 'type': 'lead'}
            if status:
                vals['contact_status'] = status
            if stage_xmlid:
                st = self.env.ref(stage_xmlid, raise_if_not_found=False)
                if st:
                    vals['stage_id'] = st.id
            if mobile:
                vals['phone'] = mobile
            phone2, _bad2 = self._phone(row.get('so_dien_thoai_2'))
            if phone2:
                vals['phone2'] = phone2
            raw_src = str(row.get('nguon_khach_hang') or '').strip()
            src = LEAD_SOURCE_MAP.get(_norm_key(raw_src))
            if not src and raw_src:
                # a partner organisation or named referrer — record it as a
                # partner-sourced lead and keep the name on a utm.source
                src = 'partner'
                utm = self._utm_source(raw_src, report)
                if utm:
                    vals['source_id'] = utm.id
                vals['referred'] = raw_src[:255]
            elif not raw_src and _norm(row.get('Source')) == 'inbox':
                # the Pancake inbox tag is the only acquisition signal left
                src = 'inbox_email'
            if src:
                vals['healthcare_lead_source'] = src
            desc = ' | '.join(filter(None, [str(row.get('ghi_chu') or ''),
                                            str(row.get('Note') or ''),
                                            str(row.get('dich_vu_quan_tam') or '')])).strip()
            if desc:
                vals['description'] = desc
            interest = self._service_interest(row.get('dich_vu_quan_tam'))
            if interest:
                vals['service_interest'] = interest
            if row.get('ly_do_tu_choi'):
                raw_reason = str(row['ly_do_tu_choi']).strip()
                vals['reason_if_rejected'] = raw_reason
                if _norm(raw_reason) == 'spam':
                    # spam is a contact status in this platform, not a reason
                    vals['contact_status'] = 'spam'
                else:
                    reason = self._lost_reason(raw_reason)
                    if reason:
                        vals['lost_reason_id'] = reason.id
                        report['lost_reasons_linked'] += 1
                    else:
                        report['unmapped_lost_reason'].add(raw_reason)
            outcome = CONTACT_OUTCOME_MAP.get(_norm_key(row.get('cskh_3')))
            if outcome:
                vals['health_contact_outcome'] = outcome
            g = self._gender_id(row.get('gioi_tinh'))
            if g:
                vals['gender_id'] = g
            dob = self._parse_dob(row.get('nam_sinh'))
            if dob:
                vals['birth_date'] = dob
            if row.get('so_cccd'):
                vals['national_id'] = str(row['so_cccd']).strip()
            if row.get('ten_benh_nhan'):
                vals['contact_name'] = str(row['ten_benh_nhan']).strip()
            if row.get('Email'):
                vals['email_from'] = str(row['Email']).strip()
            fac = self._facility_by_branch(row.get('phong_kham'))
            if fac:
                vals['facility_id'] = fac.id
            nxt = self._parse_dt(row.get('NextContactAt'))
            if nxt:
                vals['next_follow_up_date'] = nxt
            if row.get('phan_hoi_kh'):
                vals['follow_up_notes'] = str(row['phan_hoi_kh']).strip()
            dist = self._money(row.get('khoang_cach'))
            if dist > 0:
                vals['distance_from_clinic'] = dist
            first_use = self._parse_date_any(row.get('ngay_dau_su_dung'))
            if first_use:
                vals['first_service_date'] = first_use
            addr = str(row.get('Address') or row.get('FullAddress') or '').strip()
            if addr:
                vals['street'] = addr
            # legacy audit trail — Owner becomes the salesperson when the name
            # matches a platform user, otherwise it is kept as raw text
            for col, field in (('CreatedBy', 'legacy_created_by'),
                               ('LastContactUser', 'legacy_lastcontactuser')):
                v = str(row.get(col) or '').strip()
                if v:
                    vals[field] = v[:255]
            owner = str(row.get('Owner') or '').strip()
            if owner:
                user = self.env['res.users'].search(
                    [('name', '=ilike', owner), ('active', '=', True)], limit=1)
                if user:
                    vals['user_id'] = user.id
                else:
                    vals['legacy_owner'] = owner[:255]
            ad_ids = self._legacy_ad_ids(row)
            if ad_ids:
                vals['legacy_ad_ids'] = ad_ids
            vals = self._only_fields('crm.lead', vals)
            try:
                if lead:
                    lead.write(vals)
                    report['leads_updated'] += 1
                else:
                    lead = Lead.create(vals)
                    report['leads_created'] += 1
                # index the Pancake customer id so bookings can find this
                # contact (see _lead_for_booking)
                for col in ('PancakeCustomer ID', 'PancakeCustomer', 'customer_id'):
                    v = str(row.get(col) or '').strip()
                    if v:
                        self._xref_store('crm.lead', 'pancakecust:' + _norm(v),
                                         lead.id, raw=v)
                        break
            except Exception as e:
                report['lead_errors'].append('%s: %s' % (guid, e))

    # ------------------------------------------------------------- archive
    def archive_baseline(self, report, run_tag='legacy_mig'):
        Baseline = self.env['migration.baseline']
        now = fields.Datetime.now()
        scopes = [
            ('res.partner', [('is_patient', '=', True),
                             ('legacy_client_code', 'in', [False, ''])]),
            ('crm.lead', [('legacy_contact_guid', 'in', [False, ''])]),
            ('health.fieldservice.order', [('legacy_booking_ref', 'in', [False, ''])]),
        ]
        for model, dom in scopes:
            recs = self.env[model].search(dom)  # active_test default -> only active
            for r in recs:
                Baseline.create({'run': run_tag, 'target_model': model,
                                 'res_id': r.id, 'archived_at': now})
            if recs:
                recs.write({'active': False})
            report['archived'][model] = len(recs)

        # staff: healthcare staff not created by migration and not a login user
        xref_emp = self.env['migration.xref'].search(
            [('target_model', '=', 'hr.employee')]).mapped('res_id')
        emps = self.env['hr.employee'].search(
            [('is_healthcare_staff', '=', True), ('id', 'not in', xref_emp)])
        emps = emps.filtered(lambda e: not e.user_id)
        for e in emps:
            Baseline.create({'run': run_tag, 'target_model': 'hr.employee',
                             'res_id': e.id, 'archived_at': now})
        if emps:
            emps.write({'active': False})
        report['archived']['hr.employee'] = len(emps)

        # cascade: assignments/payments of archived (non-migrated) bookings
        for model in ('health.staff.assignment', 'health.payment.transaction'):
            fk = 'fso_id'
            if fk not in self.env[model]._fields:
                continue
            recs = self.env[model].search(
                [(fk + '.legacy_booking_ref', 'in', [False, ''])])
            for r in recs:
                Baseline.create({'run': run_tag, 'target_model': model,
                                 'res_id': r.id, 'archived_at': now})
            if recs:
                recs.write({'active': False})
            report['archived'][model] = len(recs)
        return report

    def remediate_staff(self, booking_path):
        """Re-resolve and re-assign staff for already-migrated bookings using the
        fixed multi-nurse (';') splitter. Replaces each booking's assigned_staff
        with the correct individual nurses (creating any missing). Run after a
        commit; follow with cleanup_orphan_staff()."""
        rows = json.load(open(booking_path))
        report = {'bookings_fixed': 0, 'multi_nurse_bookings': 0,
                  'total_assignments': 0, 'no_fso': 0, 'no_nurse': 0, 'errors': []}
        FSO = self._bulk_ctx('health.fieldservice.order')
        for row in rows:
            raw = row.get('bac_si_dieu_duong')
            if not raw:
                report['no_nurse'] += 1
                continue
            ref = self._booking_ref(row)
            fso = FSO.search([('legacy_booking_ref', '=', ref)], limit=1)
            if not fso:
                report['no_fso'] += 1
                continue
            emps = self._staff_list(raw)
            if not emps:
                continue
            try:
                fso.write({'assigned_staff_ids': [(6, 0, emps.ids)]})
                report['bookings_fixed'] += 1
                report['total_assignments'] += len(emps)
                if ';' in str(raw):
                    report['multi_nurse_bookings'] += 1
            except Exception as e:
                report['errors'].append('%s: %s' % (ref, str(e)[:100]))
        return report

    def cleanup_orphan_staff(self):
        """Delete migration-created staff stubs that are no longer assigned to any
        booking (e.g. the old garbled/concatenated names). Archives instead of
        deleting if the record can't be removed."""
        report = {'deleted': 0, 'archived': 0, 'kept': 0}
        Assign = self.env['health.staff.assignment'].with_context(active_test=False)
        xrefs = self.env['migration.xref'].search(
            [('target_model', '=', 'hr.employee'), ('auto_created', '=', True)])
        for x in xrefs:
            emp = self.env['hr.employee'].with_context(active_test=False).browse(x.res_id)
            if not emp.exists():
                x.unlink()
                continue
            if Assign.search_count([('staff_id', '=', emp.id)]) == 0 and not emp.user_id:
                try:
                    emp.unlink()
                    x.unlink()
                    report['deleted'] += 1
                except Exception:
                    emp.write({'active': False})
                    report['archived'] += 1
            else:
                report['kept'] += 1
        return report

    def backfill_geo(self):
        """One-time backfill: geocode facilities + clients, then compute the
        one-way driving distance for clients (clinic_drive_*) and bookings
        (travel_distance). Idempotent + throttled. Run via odoo shell + commit."""
        import time
        report = {'facilities_geocoded': 0, 'clients_geocoded': 0,
                  'clients_distance': 0, 'bookings_distance': 0,
                  'methods': {}, 'errors': []}

        def _tally(rec_field_obj):
            m = rec_field_obj or 'none'
            report['methods'][m] = report['methods'].get(m, 0) + 1

        # 1) Facilities lacking coordinates -> Photon (city-level ok)
        for f in self.env['health.facility'].with_context(active_test=False).search([]):
            if not (f.latitude and f.longitude):
                try:
                    f._geocode_facility_address()
                    if f.latitude and f.longitude:
                        report['facilities_geocoded'] += 1
                except Exception as e:  # noqa: BLE001
                    report['errors'].append('fac %s: %s' % (f.id, str(e)[:60]))
                time.sleep(0.3)

        Partner = self.env['res.partner'].with_context(active_test=False)
        clients = Partner.search([('is_patient', '=', True)])

        # 2) Clients lacking coordinates -> geocode (skip the auto distance hook;
        #    distance is computed in step 3 in one consistent pass)
        for p in clients:
            if not (p.partner_latitude and p.partner_longitude):
                try:
                    coords = p._get_geocode_coordinates_sync()
                    if coords:
                        p.with_context(skip_distance_recompute=True).write({
                            'partner_latitude': coords['latitude'],
                            'partner_longitude': coords['longitude'],
                            'date_localization': fields.Date.today(),
                        })
                        report['clients_geocoded'] += 1
                except Exception as e:  # noqa: BLE001
                    report['errors'].append('cli %s: %s' % (p.id, str(e)[:60]))
                time.sleep(0.3)

        # 3) Client one-way driving distance from primary facility
        for p in clients:
            p._update_clinic_distance()
            if p.clinic_drive_distance_km:
                report['clients_distance'] += 1
                _tally(p.clinic_distance_method)
            time.sleep(0.12)

        # 4) Booking one-way driving distance (facility -> client). Reuses the
        #    client's distance for same-facility bookings (no API call) and skips
        #    per-quote recompute for historical bookings.
        for fso in self.env['health.fieldservice.order'].with_context(
                active_test=False, skip_quote_recalc=True).search(
                    [('legacy_booking_ref', '!=', False)]):
            fso._update_travel_distance()
            if fso.travel_distance:
                report['bookings_distance'] += 1

        return report

    def reassign_facility_by_location(self):
        """For every geocoded client, set primary_facility_id (and matching
        catchment_province_id) to the NEAREST facility by straight-line distance,
        then recompute the one-way driving distance. Fixes clients sitting on the
        far-city facility (the cause of very long distances)."""
        from odoo.addons.health_base.models import geo_utils
        facs = [f for f in self.env['health.facility'].with_context(
                active_test=False).search([]) if f.latitude and f.longitude]
        if not facs:
            return {'error': 'no geocoded facilities'}
        report = {'reassigned': 0, 'unchanged': 0, 'no_coords': 0, 'by_facility': {}}
        Partner = self.env['res.partner'].with_context(active_test=False)
        for p in Partner.search([('is_patient', '=', True)]):
            if not (p.partner_latitude and p.partner_longitude):
                report['no_coords'] += 1
                continue
            nearest = min(facs, key=lambda f: geo_utils.haversine_km(
                p.partner_latitude, p.partner_longitude, f.latitude, f.longitude))
            vals = {}
            if p.primary_facility_id.id != nearest.id:
                vals['primary_facility_id'] = nearest.id
            if nearest.catchment_province_id and \
                    p.catchment_province_id.id != nearest.catchment_province_id.id:
                vals['catchment_province_id'] = nearest.catchment_province_id.id
            if vals:
                p.write(vals)  # write hook recomputes the driving distance
                report['reassigned'] += 1
                report['by_facility'][nearest.name] = \
                    report['by_facility'].get(nearest.name, 0) + 1
            else:
                report['unchanged'] += 1
        return report

    def set_placeholder_phones(self, overwrite_all=True):
        """Put VALID random Vietnamese mobile numbers on clients + contacts so the
        phone constraint stops blocking saves (legacy phones are truncated to 4
        digits). overwrite_all=False only fixes empty/invalid numbers."""
        import random
        rnd = random.Random(20260608)
        prefixes = ['3', '5', '7', '8', '9']

        def gen():
            return '0' + rnd.choice(prefixes) + ''.join(
                rnd.choice('0123456789') for _ in range(8))

        def is_valid(v):
            if not v:
                return False
            try:
                normalize_vn_phone(v)
                return True
            except ValidationError:
                return False

        report = {'clients': 0, 'leads': 0}
        Partner = self.env['res.partner'].with_context(
            active_test=False, skip_distance_recompute=True,
            mail_create_nolog=True, tracking_disable=True)
        for p in Partner.search([('is_patient', '=', True)]):
            vals = {}
            if overwrite_all or not is_valid(p.mobile):
                vals['mobile'] = gen()
            if overwrite_all or not is_valid(p.phone):
                vals['phone'] = gen()
            # The phone constraint re-validates emergency_contact_phone on any
            # phone/mobile write, so a junk emergency number would block the save.
            if p.emergency_contact_phone and not is_valid(p.emergency_contact_phone):
                vals['emergency_contact_phone'] = gen()
            if vals:
                p.write(vals)
                report['clients'] += 1
        Lead = self.env['crm.lead'].with_context(
            active_test=False, mail_create_nolog=True, tracking_disable=True)
        for l in Lead.search([]):
            vals = {}
            if overwrite_all or not is_valid(l.phone):
                vals['phone'] = gen()
            if 'mobile' in l._fields and (overwrite_all or not is_valid(l.mobile)):
                vals['mobile'] = gen()
            if vals:
                l.write(vals)
                report['leads'] += 1
        return report

    def restore_baseline(self, run_tag='legacy_mig'):
        n = 0
        for b in self.env['migration.baseline'].search([('run', '=', run_tag)]):
            try:
                rec = self.env[b.target_model].with_context(active_test=False).browse(b.res_id)
                if rec.exists():
                    rec.write({'active': True})
                    n += 1
            except Exception:
                pass
        return {'restored': n}

    def purge_migrated(self, delete=False):
        """Rollback the migrated data itself. delete=False archives (default),
        delete=True removes. Reference dimensions in migration.xref are left in
        place unless delete=True (then auto_created ones are removed too)."""
        out = {}
        targets = [
            ('health.payment.transaction', [('fso_id.legacy_booking_ref', '!=', False)]),
            ('sale.order', [('origin', 'like', 'BKG-%')]),
            ('health.fieldservice.order', [('legacy_booking_ref', '!=', False)]),
            ('res.partner', [('legacy_client_code', '!=', False)]),
            ('crm.lead', [('legacy_contact_guid', '!=', False)]),
        ]
        for model, dom in targets:
            recs = self.env[model].with_context(active_test=False).search(dom)
            out[model] = len(recs)
            if not recs:
                continue
            if delete:
                try:
                    recs.unlink()
                except Exception as e:
                    out[model] = 'archived(unlink failed: %s)' % e
                    recs.write({'active': False})
            else:
                recs.write({'active': False})
        if delete:
            auto = self.env['migration.xref'].search([('auto_created', '=', True)])
            for x in auto:
                rec = self.env[x.target_model].with_context(active_test=False).browse(x.res_id)
                if rec.exists():
                    try:
                        rec.unlink()
                    except Exception:
                        pass
            self.env['migration.xref'].search([]).unlink()
            self.env['migration.baseline'].search([]).unlink()
        return out

    # ------------------------------------------------------------- preflight
    def preflight(self, booking_path=None, contact_path=None):
        data = {'booking': json.load(open(booking_path)) if booking_path else [],
                'contact': json.load(open(contact_path)) if contact_path else []}
        missing = {}
        for fl, col, mp, allow_blank in SELECTION_COLUMNS:
            seen = set()
            for row in data[fl]:
                raw = row.get(col)
                if raw in (None, '') and allow_blank:
                    continue
                if _norm(raw) not in mp and raw not in (None, ''):
                    seen.add(str(raw))
            if seen:
                missing['%s.%s' % (fl, col)] = sorted(seen)
        return missing

    # ------------------------------------------------------------- driver
    @api.model
    def run_migration(self, booking_path=None, contact_path=None,
                      do_archive=False, run_tag='legacy_mig'):
        report = self._new_report()
        # Contacts first: bookings link back to them (crm_lead_id), so the leads
        # and their Pancake-id crosswalk must exist before the bookings run.
        if contact_path:
            rows = json.load(open(contact_path))
            self.import_contacts(rows, report)
        if booking_path:
            rows = json.load(open(booking_path))
            for row in rows:
                client = self._upsert_client(row, report)
                if client:
                    self._upsert_booking(row, client, report)
        if do_archive:
            self.archive_baseline(report, run_tag)
        # Give the freshly-imported nurses/doctors their access role + login.
        # The importer only sets `healthcare_role` on the staff stubs; this turns
        # that tag into a Nurse/Doctor access.role (creating an internal, no-invite
        # user when needed) and clears the tag. Idempotent — only touches staff
        # that don't already hold a role, so it's safe on every run.
        if booking_path:
            report['staff_roles'] = self.env['health.staff.assignment'] \
                .migrate_booking_staff_roles()
        # make sets printable
        for k in ('unmapped_fso_status', 'unmapped_lead_status',
                  'unmapped_cancel_reason', 'unmapped_lost_reason',
                  'client_named_referrers', 'unmatched_services',
                  'unmatched_service_types', 'unmatched_sources',
                  'unmatched_facilities'):
            report[k] = sorted(report[k])
        for k in ('bad_phones', 'client_no_catchment'):
            report[k + '_count'] = len(report[k])
            report[k] = report[k][:10]
        return report

    # ------------------------------------------------- price-list alignment
    def _group_service_types(self, groups):
        """Create/refresh the service catalogue from the price-list groups.

        These come from the price list (master), not from booking text, so
        creating them here is loading master data — not inventing it.
        Returns {group_vi: health.service.type}.
        """
        ST = self._bulk_ctx('health.service.type')
        out = {}
        for g in groups:
            code = ('PL' + hashlib.md5(g['vi'].encode()).hexdigest()[:6]).upper()[:10]
            rec = ST.search([('code', '=', code)], limit=1)
            vals = {'name': g['en'] or g['vi'], 'code': code,
                    'category': g['category'], 'active': True}
            if rec:
                rec.write(self._only_fields('health.service.type', vals))
            else:
                vals.update({'duration_minutes': 30, 'base_price': 0.0})
                rec = ST.create(self._only_fields('health.service.type', vals))
            # the Vietnamese price-list wording is the vi label
            try:
                rec.with_context(lang='vi_VN').write({'name': g['vi']})
            except Exception:  # noqa: BLE001
                pass
            out[g['vi']] = rec
        return out

    def _pricelist_product(self, item_code, province_hint):
        """Find the master product for a price-list item code.

        The pricing import names them '<item_code>_<province>', so the same
        clinical item exists once per region; prefer the booking's own region.
        """
        if not item_code:
            return None
        Product = self.env['product.product'].with_context(active_test=False)
        for suffix in ([province_hint] if province_hint else []) + ['hanoi', 'hcmc', '']:
            code = '%s_%s' % (item_code, suffix) if suffix else item_code
            prod = Product.search([('default_code', '=ilike', code)], limit=1)
            if prod:
                return prod
        prod = Product.search([('default_code', '=ilike', item_code + '%')], limit=1)
        return prod or None

    def apply_service_mapping(self, mapping_path, commit=False):
        """Re-point migrated invoice lines onto the real price list.

        Uses the ops-reviewed mapping (Migration/service_mapping.json). Lines
        whose service exists in the price list move onto that product; the rest
        move onto an explicit placeholder — surcharges to one, services with no
        price-list item (including individual lab analytes) to the other. The
        original wording is left on the line either way, so nothing is lost and
        the migrated revenue is untouched.

        Also sets each booking's appointment type from the price-list group, so
        the service category stops being a guess, and archives the products and
        service types the earlier import invented from booking text.
        """
        with open(mapping_path, encoding='utf-8') as fh:
            payload = json.load(fh)
        by_text = {s['norm']: s for s in payload['segments']}
        groups = self._group_service_types(payload['groups'])
        unmapped = self._unmapped_product()
        surcharge = self.env.ref('health_migration.product_legacy_surcharge',
                                 raise_if_not_found=False)
        surcharge = surcharge.product_variant_id if surcharge else unmapped
        report = {'lines_to_pricelist': 0, 'lines_to_placeholder': 0,
                  'lines_to_surcharge': 0, 'lines_unchanged': 0,
                  'lines_locked_by_invoice': 0,
                  'bookings_typed': 0, 'archived_products': 0,
                  'archived_service_types': 0, 'no_mapping': set(), 'errors': []}

        SOL = self.env['sale.order.line'].with_context(
            active_test=False, tracking_disable=True)
        lines = SOL.search([('order_id.origin', 'like', 'BKG-%')])
        # Any line touched here is re-validated on flush, and a discounted line
        # without a stated reason is rejected. Backfill before touching anything.
        report_fixed = self._ensure_discount_reason(lines)
        for line in lines:
            seg = by_text.get(_norm_key(line.name or ''))
            if not seg:
                report['no_mapping'].add((line.name or '')[:80])
                continue
            province = 'hanoi'
            fso = self.env['health.fieldservice.order'].with_context(
                active_test=False).search(
                    [('legacy_booking_ref', '=', line.order_id.origin)], limit=1)
            if fso and fso.facility_id and (fso.facility_id.code or '').startswith('02'):
                province = 'hcmc'
            target = None
            if seg['kind'] == 'ADJUSTMENT':
                target, bucket = surcharge, 'lines_to_surcharge'
            else:
                target = self._pricelist_product(seg.get('item_code'), province)
                bucket = 'lines_to_pricelist' if target else 'lines_to_placeholder'
                if not target:
                    target = unmapped
            if not target or line.product_id.id == target.id:
                report['lines_unchanged'] += 1
                continue
            if line.qty_invoiced:
                # Odoo refuses to change the product of an invoiced line, and
                # rightly so — the invoice already names it. These are corrected
                # by the clean purge+reload of the real export, where the line is
                # created against the price-list product in the first place.
                report['lines_locked_by_invoice'] += 1
                continue
            try:
                # keep the legacy wording; only the product changes
                original = line.name
                line.write({'product_id': target.id, 'name': original})
                report[bucket] += 1
            except Exception as e:  # noqa: BLE001
                report['errors'].append('%s: %s' % (line.order_id.origin, str(e)[:80]))
        if commit:
            self.env.cr.commit()

        # booking appointment type = the group of its primary service
        FSO = self._bulk_ctx('health.fieldservice.order')
        for fso in FSO.search([('legacy_booking_ref', '!=', False)]):
            so = self.env['sale.order'].with_context(active_test=False).search(
                [('origin', '=', fso.legacy_booking_ref)], limit=1)
            if not so or not so.order_line:
                continue
            seg = by_text.get(_norm_key(so.order_line[0].name or ''))
            if not seg or not seg.get('group_vi'):
                continue
            st = groups.get(seg['group_vi'])
            if st and fso.appointment_type_id.id != st.id:
                try:
                    fso.write({'appointment_type_id': st.id})
                    report['bookings_typed'] += 1
                except Exception as e:  # noqa: BLE001
                    report['errors'].append('%s type: %s' % (fso.legacy_booking_ref,
                                                             str(e)[:70]))
        if commit:
            self.env.cr.commit()

        report['archived_products'] = self._archive_invented('product.product')
        report['archived_service_types'] = self._archive_invented('health.service.type')
        report['discount_reasons_backfilled'] = report_fixed
        report['no_mapping'] = sorted(report['no_mapping'])[:20]
        report['errors'] = report['errors'][:20]
        if commit:
            self.env.cr.commit()
        return report

    def _archive_invented(self, model):
        """Archive the records the earlier import created from booking text.

        Kept (not deleted) so any record still pointing at one stays valid.
        """
        xrefs = self.env['migration.xref'].search(
            [('target_model', '=', model), ('auto_created', '=', True)])
        Model = self.env[model].with_context(active_test=False)
        n = 0
        for x in xrefs:
            rec = Model.browse(x.res_id)
            if not rec.exists() or not rec.active:
                continue
            try:
                rec.write({'active': False})
                n += 1
            except Exception:  # noqa: BLE001
                pass
        return n

    def link_bookings_to_leads(self, booking_path):
        """Back-fill health.fieldservice.order.crm_lead_id on bookings that were
        imported before the contact link was available. Idempotent: only fills
        bookings that have no lead yet."""
        rows = json.load(open(booking_path))
        report = {'linked': 0, 'already': 0, 'no_lead': 0, 'no_fso': 0}
        FSO = self._bulk_ctx('health.fieldservice.order')
        for row in rows:
            fso = FSO.search([('legacy_booking_ref', '=', self._booking_ref(row))],
                             limit=1)
            if not fso:
                report['no_fso'] += 1
                continue
            if fso.crm_lead_id:
                report['already'] += 1
                continue
            lead = self._lead_for_booking(row)
            if not lead:
                report['no_lead'] += 1
                continue
            fso.write({'crm_lead_id': lead.id})
            report['linked'] += 1
        return report

    def recover_financials(self, booking_path, create_invoices=True,
                           batch_size=50, commit=False):
        """Post-import money pass for data already loaded at price 0.

        1. Reprice every migrated sale order from the legacy SubTotal/Discount.
        2. Replace a single summed payment with method-accurate transactions
           (the only place the migration deletes anything — a summed cash+
           transfer row cannot be split in place).
        3. Optionally raise and post the invoice for completed, priced bookings
           and reconcile it against those transactions.

        Idempotent: repricing is a no-op when the prices already match, payments
        are only rebuilt when the split disagrees with what is stored, and an
        invoice is only created when the booking has none.

        Invoicing runs in batches of `batch_size` bookings, confirming, invoicing
        and posting each batch as a recordset rather than one order at a time —
        one-at-a-time takes hours for a full export. With `commit=True` each
        batch is committed, so the job is resumable and never holds a long
        transaction open on a live database.
        """
        rows = json.load(open(booking_path))
        report = {'repriced': 0, 'payments_rebuilt': 0, 'payments_created': 0,
                  'invoices_created': 0, 'invoices_posted': 0, 'skipped': 0,
                  'revenue': 0.0, 'errors': [], 'processed': 0}
        FSO = self._bulk_ctx('health.fieldservice.order')
        SO = self._bulk_ctx('sale.order')
        PT = self._bulk_ctx('health.payment.transaction')
        sub_report = {'sale_errors': [], 'sale_revenue': 0.0,
                      'sale_discount': 0.0, 'payment_errors': [], 'payments': 0}
        batch = []
        for row in rows:
            ref = self._booking_ref(row)
            fso = FSO.search([('legacy_booking_ref', '=', ref)], limit=1)
            if not fso:
                report['skipped'] += 1
                continue
            report['processed'] += 1
            # --- 1. prices
            order = SO.search([('origin', '=', ref)], limit=1)
            if order and order.state in ('draft', 'sent', 'sale'):
                before = order.amount_total
                self._reprice_order(order, row, sub_report)
                if order.amount_total != before:
                    report['repriced'] += 1
                    report['revenue'] += order.amount_total
            # --- 2. payments
            splits = self._payment_splits(row)
            existing = PT.search([('fso_id', '=', fso.id)])
            want = sorted((round(a, 2), m) for a, m in splits)
            have = sorted((round(t.amount, 2), t.payment_method) for t in existing)
            if splits and want != have:
                try:
                    if existing:
                        existing.unlink()
                        report['payments_rebuilt'] += 1
                    self._make_payment(row, fso, fso.patient_id, sub_report)
                    report['payments_created'] += len(splits)
                except Exception as e:
                    report['errors'].append('%s payments: %s' % (ref, str(e)[:90]))
            # --- 3. invoice (batched — see _invoice_batch)
            if create_invoices and order:
                batch.append((fso, order, row))
                if len(batch) >= batch_size:
                    self._flush_invoice_batch(batch, report, commit)
                    batch = []
        if batch:
            self._flush_invoice_batch(batch, report, commit)
        if commit:
            self.env.cr.commit()
        report['errors'].extend(sub_report['sale_errors'][:20])
        report['errors'].extend(sub_report['payment_errors'][:20])
        report['errors'] = report['errors'][:40]
        return report

    def _flush_invoice_batch(self, batch, report, commit):
        # Persist the repricing and payment work first: if the invoice step of
        # this batch fails, its rollback must not undo them too.
        if commit:
            self.env.cr.commit()
        try:
            self._invoice_batch(batch, report)
            if commit:
                self.env.cr.commit()
        except Exception as e:
            # one bad batch must not lose the whole run
            self.env.cr.rollback()
            report['errors'].append('invoice batch %s..: %s' % (
                batch[0][0].legacy_booking_ref, str(e)[:120]))
        _logger.info('recover_financials: %s bookings, %s invoices created',
                     report['processed'], report['invoices_created'])

    def _invoice_batch(self, items, report):
        """Invoice a batch of (fso, order, row) triples in bulk.

        Only completed bookings with a real amount are invoiced, and only
        settled ones are posted, so no historical accounting entry is created
        speculatively. Each invoice is linked back to its booking and payment
        transactions but deliberately NOT reconciled — reconciliation creates
        bank/cash entries that move real balances and needs finance sign-off
        rather than a migration script.
        """
        SO = self.env['sale.order']
        todo, already = [], []
        for fso, order, row in items:
            if fso.state != 'completed' or order.amount_total <= 0:
                continue
            if order.invoice_ids:
                already.append((fso, order.invoice_ids[0]))
                continue
            todo.append((fso, order, row))
        for fso, invoice in already:
            self._link_invoice(fso, invoice)
        if not todo:
            return
        orders = SO.browse([o.id for _f, o, _r in todo])
        unconfirmed = orders.filtered(lambda o: o.state not in ('sale', 'done'))
        if unconfirmed:
            unconfirmed.action_confirm()
        # Confirming re-applies the pricelist, which can add a discount of its
        # own. Any discount without a stated reason is rejected on both the
        # order line and the invoice line, so backfill it before invoicing.
        self._ensure_discount_reason(orders.order_line)
        # grouped=True keeps one invoice per order; the default would merge every
        # order of the same customer into a single invoice
        invoices = orders._create_invoices(grouped=True)
        if not invoices:
            return
        report['invoices_created'] += len(invoices)
        by_order = {}
        for inv in invoices:
            for oid in inv.line_ids.sale_line_ids.order_id.ids:
                by_order.setdefault(oid, inv)
        to_post = self.env['account.move']
        for fso, order, row in todo:
            inv = by_order.get(order.id)
            if not inv:
                continue
            inv.invoice_date = (fso.scheduled_datetime.date()
                                if fso.scheduled_datetime else fields.Date.today())
            self._link_invoice(fso, inv)
            if self._payment_splits(row):
                to_post |= inv
        if to_post:
            # skip_redinvoice: these are historical visits being reconstructed.
            # Posting must NOT file an e-invoice with the tax authority — that
            # is only ever valid for a genuine live sale.
            to_post.with_context(skip_redinvoice=True).action_post()
            report['invoices_posted'] += len(to_post)

    def _ensure_discount_reason(self, lines):
        """Give every discounted line a reason (the platform requires one)."""
        missing = lines.filtered(
            lambda l: not l.display_type and l.discount and not l.discount_reason)
        if missing:
            missing.write({'discount_reason': LEGACY_DISCOUNT_REASON})
        return len(missing)

    def _link_invoice(self, fso, invoice):
        """Point the booking and its payment transactions at the invoice."""
        if 'invoice_id' in fso._fields and fso.invoice_id.id != invoice.id:
            fso.write({'invoice_id': invoice.id})
        txns = self.env['health.payment.transaction'].with_context(
            active_test=False).search([('fso_id', '=', fso.id),
                                       ('invoice_id', '=', False)])
        if txns:
            txns.write({'invoice_id': invoice.id})
