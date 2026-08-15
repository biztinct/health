"""migration.lookup.seeder — make the platform's lookups match the legacy ones.

The client's requirement is *like-for-like*: after the migration the dropdowns
must offer exactly the values the legacy system offered, in Vietnamese for
vi_VN users and English for en_US users. Two mechanisms deliver that:

* **many2one lookups** (cancellation reasons, rejection reasons, facilities,
  units, specialties) — the legacy values are created as records with an
  English ``name`` plus a ``vi_VN`` translation. Values that existed before the
  migration are **archived, never deleted**: records already reference them and
  unlinking would either fail on the foreign key or orphan live bookings.
* **selection fields** — the stored code is workflow-bearing and stays as it
  is; only the label changes. English labels live in the Python source, the
  Vietnamese ones are written straight into ``ir.model.fields.selection`` here
  so they apply immediately without waiting on a .po reload.

Run from odoo shell (idempotent — safe to re-run):

    env['migration.lookup.seeder'].apply_lookup_fidelity()
"""
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- lookup data
# (english, vietnamese, reason_type, sequence)
CANCELLATION_REASONS = [
    ('No doctor available < 2.5 hours', 'Không có bác sĩ <2.5h', 'provider', 10),
    ('No doctor available > 2.5 hours', 'Không có bác sĩ >2.5h', 'provider', 20),
    ('No nurse available < 2.5 hours', 'Không có điều dưỡng <2.5h', 'provider', 30),
    ('No nurse available > 2.5 hours', 'Không có điều dưỡng >2.5h', 'provider', 40),
    ('Preferred nurse not available', 'Y tá được ưu tiên hiện không có', 'provider', 50),
    ('Hospitalized', 'Nhập viện', 'patient', 60),
    ('Deceased', 'Qua đời', 'patient', 70),
    ('Prescription completed/expired', 'Hết đơn thuốc', 'patient', 80),
    ('Other', 'Khác', 'patient', 90),
]

# (english, vietnamese)  — 'Spam' is deliberately absent: it is a contact
# status in this platform, not a rejection reason.
LOST_REASONS = [
    ('No doctor available < 2.5 hours', 'Không có bác sĩ <2.5h'),
    ('No doctor available > 2.5 hours', 'Không có bác sĩ >2.5h'),
    ('No nurse available < 2.5 hours', 'Không có điều dưỡng <2.5h'),
    ('No nurse available > 2.5 hours', 'Không có điều dưỡng >2.5h'),
    ('Price too high', 'Giá quá cao'),
    ('Still considering', 'Vẫn đang cân nhắc'),
    ('No prescription', 'Không có đơn thuốc'),
    ('Consultation only', 'Chỉ cần tư vấn'),
    ('Address too far', 'Địa chỉ quá xa'),
    ('Service not available', 'Không có dịch vụ'),
    ('Wrong hotline number', 'Nhầm số hotline'),
    ('No equipment available', 'Không có máy móc thiết bị'),
    ('No response / Did not say', 'Không nói'),
    ('Other', 'Khác'),
]

# (code, english name, vietnamese name, city key, facility_type)
FACILITIES = [
    ('01_01_00', 'HN_PK_PKGDVU', 'HN_PK_PKGDVU', 'hn', 'main_clinic'),
    ('01_01_01', 'HN_NS_Minh_Khai', 'HN_NS_Minh_Khai', 'hn', 'branch_clinic'),
    ('01_01_02', 'HN_NS_Ha_Dong', 'HN_NS_Hà_Đông', 'hn', 'branch_clinic'),
    ('02_01_00', 'TPHCM_PK_CSTNVU', 'TPHCM_PK_CSTNVU', 'hcm', 'main_clinic'),
    ('02_01_01', 'TPHCM_NS_Thu_Duc', 'TPHCM_NS_Thủ_Đức', 'hcm', 'branch_clinic'),
    ('02_01_02', 'TPHCM_NS_Tan_Thuan', 'TPHCM_NS_Tân_Thuận', 'hcm', 'branch_clinic'),
]
# old generic facility -> official successor (used when re-pointing existing FKs)
FACILITY_SUCCESSOR = {'hn': '01_01_00', 'hcm': '02_01_00'}

CATCHMENT_XMLID = {'hcm': 'health_base.catchment_province_hcm',
                   'hn': 'health_base.catchment_province_hanoi'}

# legacy sub-sources / partner referrers that must exist as utm.source records
UTM_SOURCES = [
    'TikTok',
    'Phòng khám Gia đình Việt Úc',
    'Chăm sóc tại nhà Việt Úc',
    'FWD',
    'Ivie - Bác sĩ ơi',
    'Daiichi',
    'Trường Quốc Tế Úc ACG',
    'Trường Quốc Tế Châu Âu',
    'Bác sĩ/Điều dưỡng',
    'Người Giới Thiệu',
]

# (english, vietnamese) units of measure the legacy price list uses
UOM_VALUES = [('Shift', 'Ca'), ('Bottle', 'Chai'), ('Visit', 'Lần')]

MEDICAL_SPECIALTIES = [('Surgery', 'Khám ngoại')]

# Vietnamese labels for every selection value the migration relabels.
# {(model, field): {key: vietnamese label}}
SELECTION_VI_LABELS = {
    ('crm.lead', 'service_interest'): {
        'palliative': 'Chăm sóc giảm nhẹ',
        'personal_care': 'Chăm sóc cá nhân',
        'wound_care': 'Chăm sóc vết thương',
        'consultation': 'Bác sĩ khám',
        'injection': 'Tiêm',
        'iv_infusion': 'Truyền',
        'enema': 'Thụt tháo',
        'catheter': 'Đặt, rút sonde',
        'sputum_care': 'Hút đờm, vỗ rung đờm',
        'lab_test': 'Xét nghiệm',
        'other': 'Khác',
        'home_visit': 'Khám tại nhà',
        'clinic_visit': 'Khám tại phòng khám',
        'follow_up': 'Chăm sóc theo dõi',
        'emergency': 'Cấp cứu',
        'preventive': 'Dự phòng',
        'rehabilitation': 'Phục hồi chức năng',
    },
    ('crm.lead', 'health_contact_outcome'): {
        'service_booked': 'Chốt dùng dịch vụ',
        'pending_follow_up': 'Bận gọi lại sau',
        'rejected': 'Từ chối dịch vụ',
        'no_response': 'Không phản hồi',
        'no_answer': 'Không nghe máy',
        'service_inquiry': 'Tham khảo dịch vụ',
        'future_opportunity': 'Cân nhắc thêm',
    },
    ('crm.lead', 'contact_status'): {
        'active': 'Mới',
        'booking': 'Đặt lịch hẹn',
        'lead': 'Lead',
        'lost_booking': 'Hủy',
        'spam': 'Spam',
        'thinking': 'Đang suy nghĩ',
        'recontact': 'Liên hệ lại',
        'service_used': 'Đã sử dụng',
        'existing': 'Cũ',
    },
    ('crm.lead', 'healthcare_lead_source'): {
        'facebook_ad': 'Facebook',
        'zalo_marketing': 'Zalo',
        'website_form': 'Form',
        'phone_inquiry': 'Hotline',
        'referral_patient': 'Người Giới Thiệu',
        'referral_doctor': 'Bác sĩ/Điều dưỡng',
        'walk_in': 'Tự đến PK',
        'health_fair': 'Hội chợ sức khỏe',
        'community_outreach': 'Cộng đồng',
        'partner': 'Đối tác',
        'tiktok': 'TikTok',
        'google': 'Google',
        'former_client': 'Khách hàng cũ',
        'inbox_email': 'INBOX',
    },
    ('res.partner', 'source_type'): {
        'facebook': 'Facebook', 'zalo': 'Zalo', 'website': 'Website',
        'phone': 'Hotline', 'referral': 'Người Giới Thiệu',
        'walk_in': 'Tự đến PK', 'other': 'Khác',
    },
    ('res.partner', 'client_type'): {'new': 'Mới', 'repeat': 'Cũ'},
    ('health.fieldservice.order', 'state'): {
        'draft': 'Nháp',
        'confirmed': 'Đặt chỗ mới',
        'assigned': 'Đã phân công',
        'in_progress': 'Đang tiến hành',
        'completed': 'Đã hoàn thành',
        'completed_pending_invoice': 'Đã hoàn thành - Chờ xuất hóa đơn',
        'cancelled': 'Hủy',
        'closed': 'Đã đóng',
    },
    ('health.fieldservice.order', 'service_location'): {
        'home': 'Tại Nhà',
        'clinic': 'Tại Phòng khám',
        'hospital': 'Bệnh viện',
        'nursing_home': 'Viện dưỡng lão',
        'office': 'Văn phòng',
        'online': 'Telemedicine',
        'other': 'Khác',
    },
    ('health.fieldservice.order', 'payment_status'): {
        'pending': 'Chưa thanh toán',
        'partial': 'Thanh toán một phần',
        'paid': 'Đã thanh toán',
        'overpaid': 'Thanh toán vượt',
        'refunded': 'Đã hoàn tiền',
    },
    ('health.payment.transaction', 'payment_method'): {
        'cash': 'Tiền mặt',
        'bank_transfer': 'Chuyển khoản ngân hàng',
        'credit_card': 'Thẻ tín dụng',
        'qr_code': 'Thanh toán QR',
        'prepaid': 'Trả từ TT trước',
        'other': 'Khác',
    },
    ('health.service.type', 'category'): {
        'nursing_care': 'DỊCH VỤ ĐIỀU DƯỠNG',
        'consultation': 'DỊCH VỤ BÁC SĨ',
        'foreigner_doctor': 'DỊCH VỤ BÁC SĨ/ Người nước ngoài',
    },
}


class MigrationLookupSeeder(models.Model):
    _name = 'migration.lookup.seeder'
    _description = 'Legacy Lookup Fidelity Seeder'

    name = fields.Char(default='lookup-seeder')

    # ------------------------------------------------------------- helpers
    def _bulk(self, model):
        return self.env[model].with_context(
            mail_create_nolog=True, tracking_disable=True, mail_notrack=True,
            active_test=False, skip_auto_geocode=True,
            skip_distance_recompute=True)

    def _lookup(self, category_code, value_code):
        """Resolve a Tier-1 vocabulary CODE to its health.lookup.value id.

        The legacy tables in this module are keyed by the old Selection codes;
        those codes survived the lookup conversion unchanged, which is exactly
        what makes this a one-line translation rather than a re-mapping.
        """
        if not value_code:
            return False
        return self.env['health.lookup.value']._default_for(
            category_code, value_code)

    def _set_vi(self, record, field, vietnamese):
        """Write the vi_VN translation of a translatable field."""
        try:
            record.with_context(lang='vi_VN').write({field: vietnamese})
        except Exception as e:  # noqa: BLE001
            _logger.warning('vi translation failed for %s.%s: %s',
                            record._name, field, e)

    # --------------------------------------------------------------- steps
    def seed_cancellation_reasons(self):
        """Create the 9 legacy reasons; archive every pre-existing one."""
        Reason = self._bulk('health.booking.cancellation.reason')
        out = {'created': 0, 'updated': 0, 'archived': 0}
        keep = self.env['health.booking.cancellation.reason']
        for en, vi, rtype, seq in CANCELLATION_REASONS:
            rec = Reason.search([('name', '=', en)], limit=1)
            if not rec:
                rec = Reason.create({'name': en,
                                     'reason_type_id': self._lookup(
                                         'cancellation_reason_type', rtype),
                                     'sequence': seq, 'active': True})
                out['created'] += 1
            else:
                rec.write({'reason_type_id': self._lookup(
                    'cancellation_reason_type', rtype),
                    'sequence': seq, 'active': True})
                out['updated'] += 1
            self._set_vi(rec, 'name', vi)
            keep |= rec
        stale = Reason.search([('id', 'not in', keep.ids), ('active', '=', True)])
        if stale:
            # archived, not deleted: migrated bookings already point at them
            stale.write({'active': False})
            out['archived'] = len(stale)
        return out

    def seed_lost_reasons(self):
        Reason = self._bulk('crm.lost.reason')
        out = {'created': 0, 'updated': 0, 'archived': 0}
        keep = self.env['crm.lost.reason']
        for en, vi in LOST_REASONS:
            rec = Reason.search([('name', '=', en)], limit=1)
            if not rec:
                rec = Reason.create({'name': en, 'active': True})
                out['created'] += 1
            else:
                rec.write({'active': True})
                out['updated'] += 1
            self._set_vi(rec, 'name', vi)
            keep |= rec
        stale = Reason.search([('id', 'not in', keep.ids), ('active', '=', True)])
        if stale:
            stale.write({'active': False})
            out['archived'] = len(stale)
        return out

    def seed_facilities(self):
        """Create the 6 official facilities and move every reference off the two
        generic city facilities before archiving them."""
        Fac = self._bulk('health.facility')
        out = {'created': 0, 'updated': 0, 'repointed': {}, 'archived': 0}
        by_code = {}
        for code, en, vi, city, ftype in FACILITIES:
            rec = Fac.search([('code', '=', code)], limit=1)
            catch = self.env.ref(CATCHMENT_XMLID[city], raise_if_not_found=False)
            vals = {
                'name': en, 'code': code,
                'facility_type_id': self._lookup('facility_type', ftype),
                'facility_status': 'operational', 'active': True,
                'catchment_province_id': catch.id if catch else False,
            }
            if not rec:
                vals.setdefault('street', '-')
                vals['city'] = 'Hà Nội' if city == 'hn' else 'Hồ Chí Minh'
                rec = Fac.create(self._only(Fac, vals))
                out['created'] += 1
            else:
                rec.write(self._only(Fac, vals))
                out['updated'] += 1
            self._set_vi(rec, 'name', vi)
            by_code[code] = rec

        # copy coordinates from the outgoing city facility to its successor so
        # distance calculations keep working without a fresh geocode
        old = Fac.search([('code', 'in', ['HAN', 'HCM'])])
        for o in old:
            city = 'hn' if o.code == 'HAN' else 'hcm'
            successor = by_code.get(FACILITY_SUCCESSOR[city])
            if successor and o.latitude and o.longitude and not successor.latitude:
                successor.write({'latitude': o.latitude, 'longitude': o.longitude})
            if successor:
                for col, n in self._repoint_facility(o.id, successor.id).items():
                    # accumulate: both old city facilities feed the same columns
                    out['repointed'][col] = out['repointed'].get(col, 0) + n
        if old:
            old.write({'active': False})
            out['archived'] = len(old)
        return out

    def _only(self, model, vals):
        return {k: v for k, v in vals.items() if k in model._fields}

    def _repoint_facility(self, old_id, new_id):
        """Move every FK pointing at old_id to new_id.

        Discovered from the catalog rather than hard-coded, so a column added by
        another module is not silently left behind.
        """
        self.env.cr.execute("""
            SELECT c.conrelid::regclass::text AS tbl, a.attname AS col
              FROM pg_constraint c
              JOIN pg_attribute a
                ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f'
               AND c.confrelid = 'health_facility'::regclass
               AND array_length(c.conkey, 1) = 1
        """)
        moved = {}
        for tbl, col in self.env.cr.fetchall():
            self.env.cr.execute(
                'UPDATE "%s" SET "%s" = %%s WHERE "%s" = %%s' % (tbl, col, col),
                (new_id, old_id))
            if self.env.cr.rowcount:
                moved['%s.%s' % (tbl, col)] = self.env.cr.rowcount
        if moved:
            self.env.invalidate_all()
        return moved

    def seed_utm_sources(self):
        Src = self._bulk('utm.source')
        out = {'created': 0, 'renamed': 0}
        for name in UTM_SOURCES:
            if Src.search_count([('name', '=', name)]):
                continue
            # normalise a lower-case variant instead of creating a duplicate
            variant = Src.search([('name', '=ilike', name)], limit=1)
            if variant:
                variant.write({'name': name})
                out['renamed'] += 1
                continue
            Src.create({'name': name})
            out['created'] += 1
        return out

    def seed_uom(self):
        Uom = self._bulk('uom.uom')
        out = {'created': 0, 'updated': 0}
        if 'uom.uom' not in self.env:
            return out
        unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        for en, vi in UOM_VALUES:
            rec = Uom.search([('name', '=', en)], limit=1)
            if not rec:
                vals = {'name': en}
                if unit and 'relative_factor' in Uom._fields:
                    vals['relative_uom_id'] = unit.id
                    vals['relative_factor'] = 1.0
                elif unit and 'category_id' in Uom._fields:
                    vals['category_id'] = unit.category_id.id
                    vals['factor'] = 1.0
                    vals['uom_type'] = 'bigger'
                try:
                    rec = Uom.create(self._only(Uom, vals))
                    out['created'] += 1
                except Exception as e:  # noqa: BLE001
                    _logger.warning('uom %s not created: %s', en, e)
                    continue
            else:
                out['updated'] += 1
            self._set_vi(rec, 'name', vi)
        return out

    def seed_specialties(self):
        Spec = self._bulk('health.medical.specialty')
        out = {'created': 0, 'updated': 0}
        for en, vi in MEDICAL_SPECIALTIES:
            rec = Spec.search([('name', '=ilike', en)], limit=1)
            if not rec:
                vals = {'name': en}
                if 'code' in Spec._fields:
                    vals['code'] = en[:10].upper()
                rec = Spec.create(self._only(Spec, vals))
                out['created'] += 1
            else:
                out['updated'] += 1
            self._set_vi(rec, 'name', vi)
        return out

    def apply_selection_labels(self):
        """Write the Vietnamese label of every relabelled selection value.

        Goes straight at ir.model.fields.selection so the labels are live
        immediately; the English side comes from the Python source.
        """
        Sel = self.env['ir.model.fields.selection']
        out = {'updated': 0, 'via_po': [], 'missing': []}
        for (model, field), labels in SELECTION_VI_LABELS.items():
            fld = self.env['ir.model.fields'].search(
                [('model', '=', model), ('name', '=', field)], limit=1)
            if not fld:
                out['missing'].append('%s.%s' % (model, field))
                continue
            rows = Sel.search([('field_id', '=', fld.id)])
            if not rows:
                # A selection built by a Python function has no rows here — its
                # labels are gettext strings, so the Vietnamese wording ships in
                # the module's i18n/vi_VN.po instead. Nothing to do.
                out['via_po'].append('%s.%s' % (model, field))
                continue
            by_value = {r.value: r for r in rows}
            for key, vi in labels.items():
                sel = by_value.get(key)
                if not sel:
                    out['missing'].append('%s.%s:%s' % (model, field, key))
                    continue
                sel.with_context(lang='vi_VN').write({'name': vi})
                out['updated'] += 1
        # ir.model.fields.get_field_selection() is ormcached, so the new labels
        # stay invisible until the cache is dropped.
        self.env.registry.clear_cache('stable')
        self.env.registry.clear_cache()
        return out

    # ---------------------------------------------------------------- driver
    @api.model
    def apply_lookup_fidelity(self):
        """Run every step. Idempotent — safe to re-run after a failed pass."""
        report = {
            'cancellation_reasons': self.seed_cancellation_reasons(),
            'lost_reasons': self.seed_lost_reasons(),
            'facilities': self.seed_facilities(),
            'utm_sources': self.seed_utm_sources(),
            'uom': self.seed_uom(),
            'specialties': self.seed_specialties(),
            'selection_labels': self.apply_selection_labels(),
        }
        _logger.info('lookup fidelity applied: %s', report)
        return report
