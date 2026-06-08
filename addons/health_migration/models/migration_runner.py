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

_logger = logging.getLogger(__name__)
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


def _norm(s):
    return (str(s).strip().lower() if s not in (None, False) else '')


# ---------------------------------------------------------------- value maps
GENDER_MAP = {'nữ': 'female', 'nu': 'female', 'nam': 'male',
              'male': 'male', 'female': 'female',
              'không xác định': '', 'khong xac dinh': '', 'khác': '', 'other': 'other'}

PAYMENT_METHOD_MAP = {
    'tiền mặt': 'cash', 'tien mat': 'cash',
    'chuyển khoản': 'bank_transfer', 'chuyen khoan': 'bank_transfer',
    'tiền mặt + chuyển khoản': 'other',
}

CITY_MAP = {
    'hcmc': 'hcm', 'hcm': 'hcm', 'ho chi minh': 'hcm', 'hồ chí minh': 'hcm',
    'tp hcm': 'hcm', 'tphcm': 'hcm',
    'hanoi': 'hn', 'hn': 'hn', 'hà nội': 'hn', 'ha noi': 'hn',
}
CATCHMENT_XMLID = {'hcm': 'health_base.catchment_province_hcm',
                   'hn': 'health_base.catchment_province_hanoi'}

# legacy FSO status -> (state, stage xml-id)
FSO_STATUS_MAP = {
    'đã hoàn thành': ('completed', 'health_fieldservice.stage_completed'),
    'da hoan thanh': ('completed', 'health_fieldservice.stage_completed'),
    'huỷ': ('cancelled', 'health_fieldservice.stage_cancelled'),
    'hủy': ('cancelled', 'health_fieldservice.stage_cancelled'),
    'huy': ('cancelled', 'health_fieldservice.stage_cancelled'),
    'mới': ('confirmed', 'health_fieldservice.stage_booked'),
    'moi': ('confirmed', 'health_fieldservice.stage_booked'),
    'dời lịch': ('confirmed', 'health_fieldservice.stage_booked'),
    'doi lich': ('confirmed', 'health_fieldservice.stage_booked'),
}
FSO_STATUS_FALLBACK = ('draft', 'health_fieldservice.stage_draft')

# legacy contact status -> (contact_status, stage xml-id)
LEAD_STATUS_MAP = {
    'mới': ('lead', 'health_crm.stage_healthcare_contact'),
    'moi': ('lead', 'health_crm.stage_healthcare_contact'),
    'đặt lịch hẹn': ('booking', 'health_crm.stage_healthcare_booking'),
    'dat lich hen': ('booking', 'health_crm.stage_healthcare_booking'),
    'huỷ': ('lost_booking', 'health_crm.stage_healthcare_lost'),
    'hủy': ('lost_booking', 'health_crm.stage_healthcare_lost'),
}
LEAD_STATUS_FALLBACK = ('active', None)

LEAD_SOURCE_MAP = {
    'hotline': 'phone_inquiry', 'zalo': 'zalo_marketing',
    'khách hàng cũ': 'referral_patient',
}

# selection columns to validate up-front: (file, column, map, allow_blank)
SELECTION_COLUMNS = [
    ('booking', 'Contact_gioi_tinh', GENDER_MAP, True),
    ('booking', 'hinh_thuc_thanh_toan', PAYMENT_METHOD_MAP, True),
    ('booking', 'phong_kham_city', CITY_MAP, False),
    ('booking', 'trang_thai', FSO_STATUS_MAP, False),
    ('contact', 'gioi_tinh', GENDER_MAP, True),
    ('contact', 'Status', LEAD_STATUS_MAP, False),
]


class MigrationRunner(models.Model):
    _name = 'migration.runner'
    _description = 'Legacy Migration Runner'

    name = fields.Char(default='runner')

    # ------------------------------------------------------------ utilities
    def _bulk_ctx(self, model):
        return self.env[model].with_context(
            mail_create_nolog=True, tracking_disable=True,
            mail_notrack=True, skip_notification=True, active_test=False,
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
        Fac = self.env['health.facility'].with_context(active_test=False)
        fac = self.env['health.facility']
        if catch:
            fac = Fac.search([('catchment_province_id', '=', catch.id)], limit=1)
        if not fac:
            fac = self._mk('health.facility', {
                'name': 'Home Care - ' + (catch.name if catch else code.upper()),
                'code': ('HC' + code.upper())[:10],
                'facility_type': 'home_care_center',
                'street': '-', 'city': catch.name if catch else code.upper(),
                'consultation_rooms': 1,
                'catchment_province_id': catch.id if catch else False,
            })
            self._xref_store('health.facility', key, fac.id, raw=city_raw,
                             auto=True, notes='home-care facility')
        else:
            self._xref_store('health.facility', key, fac.id, raw=city_raw)
        return fac

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

    def _product(self, name):
        name = (name or '').strip()
        if not name:
            return None
        key = 'product:' + _norm(name)[:120]
        rid = self._xref_lookup('product.product', key)
        if rid:
            return self.env['product.product'].browse(rid)
        prod = self.env['product.product'].with_context(active_test=False).search(
            [('name', '=', name)], limit=1)
        if not prod:
            prod = self._mk('product.product',
                            {'name': name, 'type': 'service', 'list_price': 0.0})
            self._xref_store('product.product', key, prod.id, raw=name, auto=True)
        else:
            self._xref_store('product.product', key, prod.id, raw=name)
        return prod

    def _service_type(self, name):
        name = (name or '').strip()
        if not name:
            return None
        key = 'svctype:' + _norm(name)[:120]
        rid = self._xref_lookup('health.service.type', key)
        if rid:
            return self.env['health.service.type'].browse(rid)
        st = self.env['health.service.type'].search([('name', '=', name)], limit=1)
        if not st:
            code = ('S' + hashlib.md5(_norm(name).encode()).hexdigest()[:8]).upper()[:10]
            st = self._mk('health.service.type', {
                'name': name, 'code': code, 'category': 'home_visit',
                'duration_minutes': 30, 'base_price': 0.0})
            self._xref_store('health.service.type', key, st.id, raw=name, auto=True)
        else:
            self._xref_store('health.service.type', key, st.id, raw=name)
        return st

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
        g = GENDER_MAP.get(_norm(row.get('Contact_gioi_tinh')))
        if g:
            vals['gender'] = g
        dob = self._parse_dob(row.get('Contact_nam_sinh'))
        if dob:
            vals['birth_date'] = dob
        if mobile:
            vals['mobile'] = mobile
        if row.get('so_cccd'):
            vals['national_id'] = str(row['so_cccd']).strip()
        if row.get('nghe_nghiep'):
            vals['profession'] = str(row['nghe_nghiep']).strip()
        addr = str(row.get('Contact_Address') or row.get('Contact_FullAddress') or '').strip()
        if addr:
            vals['street'] = addr
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

    def _upsert_booking(self, row, client, report):
        ref = self._booking_ref(row)
        FSO = self._bulk_ctx('health.fieldservice.order')
        fso = FSO.search([('legacy_booking_ref', '=', ref)], limit=1)
        fac = self._facility(row.get('phong_kham_city'))
        sched = self._combine_local_to_utc(row.get('Appointment Date'), row.get('time_in'))
        state, stage_xmlid = self._fso_status(row.get('trang_thai'), report)
        vals = {
            'patient_id': client.id,
            'facility_id': fac.id if fac else False,
            'service_type': 'home_visit', 'service_location': 'home',
            'scheduled_duration': self._duration(row.get('time_in'), row.get('time_out')),
            'state': state, 'legacy_booking_ref': ref, 'booking_source': 'phone',
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
            vals['cancellation_notes'] = str(row['ly_do_huy'])
        vals = self._only_fields('health.fieldservice.order', vals)
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
            st = self._service_type(names[0])
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
        # sale order + lines (best effort)
        self._make_sale_lines(names, fso, client, report)
        # payment
        self._make_payment(row, fso, client, report)
        return fso

    def _make_sale_lines(self, names, fso, client, report):
        if not names:
            return
        SO = self._bulk_ctx('sale.order')
        if SO.search([('origin', '=', fso.legacy_booking_ref)], limit=1):
            return
        lines = []
        for nm in names:
            prod = self._product(nm)
            if prod:
                lines.append((0, 0, {'product_id': prod.id, 'product_uom_qty': 1,
                                     'price_unit': 0.0, 'name': nm}))
        if not lines:
            return
        vals = {'partner_id': client.id, 'origin': fso.legacy_booking_ref,
                'order_line': lines}
        if 'fso_id' in self.env['sale.order']._fields:
            vals['fso_id'] = fso.id
        try:
            SO.create(self._only_fields('sale.order', vals))
            report['sale_orders'] += 1
            report['sale_lines'] += len(lines)
        except Exception as e:
            report['sale_errors'].append('%s: %s' % (fso.legacy_booking_ref, e))

    def _make_payment(self, row, fso, client, report):
        amount = self._money(row.get('Cash')) + self._money(row.get('TransferMoney'))
        if amount <= 0:
            return
        PT = self._bulk_ctx('health.payment.transaction')
        if PT.search([('fso_id', '=', fso.id)], limit=1):
            return
        method = PAYMENT_METHOD_MAP.get(_norm(row.get('hinh_thuc_thanh_toan')), 'other')
        txn_dt = self._parse_dt(row.get('CreatedOn')) or fso.scheduled_datetime or fields.Datetime.now()
        vals = {'patient_id': client.id, 'fso_id': fso.id, 'amount': amount,
                'payment_method': method, 'transaction_date': txn_dt,
                'transaction_type': 'immediate', 'status': 'collected'}
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
            src = LEAD_SOURCE_MAP.get(_norm(row.get('nguon_khach_hang')))
            if src:
                vals['healthcare_lead_source'] = src
            desc = ' | '.join(filter(None, [str(row.get('ghi_chu') or ''),
                                            str(row.get('Note') or ''),
                                            str(row.get('dich_vu_quan_tam') or '')])).strip()
            if desc:
                vals['description'] = desc
            if row.get('ly_do_tu_choi'):
                vals['reason_if_rejected'] = str(row['ly_do_tu_choi'])
            vals = self._only_fields('crm.lead', vals)
            try:
                if lead:
                    lead.write(vals)
                    report['leads_updated'] += 1
                else:
                    Lead.create(vals)
                    report['leads_created'] += 1
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
        if booking_path:
            rows = json.load(open(booking_path))
            for row in rows:
                client = self._upsert_client(row, report)
                if client:
                    self._upsert_booking(row, client, report)
        if contact_path:
            rows = json.load(open(contact_path))
            self.import_contacts(rows, report)
        if do_archive:
            self.archive_baseline(report, run_tag)
        # make sets printable
        report['unmapped_fso_status'] = sorted(report['unmapped_fso_status'])
        report['unmapped_lead_status'] = sorted(report['unmapped_lead_status'])
        for k in ('bad_phones', 'client_no_catchment'):
            report[k + '_count'] = len(report[k])
            report[k] = report[k][:10]
        return report
