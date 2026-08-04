#!/usr/bin/env python3
"""Lookup parity report — legacy list vs what CareJioX actually offers.

The client's requirement is that the mapped lookups should offer ONLY the
values the legacy system had. This compares, field by field, the legacy list
(from Lookup.xlsx) against the live system, and states for every difference how
many records rely on it and what removing it would break.

Inputs:
  scratchpad/lookupdump.txt  — live values + usage counts (dump_lookups.py)
Output:
  Migration/Lookup_Parity_Report.xlsx
"""
import json
import os

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = ('/private/tmp/claude-502/-Users-adity-Documents-GitHub-health19/'
        '28f4b4cc-1b87-4ddc-90d3-83b619360cc5/scratchpad/lookupdump.txt')
DST = os.path.join(HERE, 'Lookup_Parity_Report.xlsx')

GREEN = PatternFill('solid', fgColor='C6EFCE')   # matches legacy
AMBER = PatternFill('solid', fgColor='FFE0B2')   # extra, removable
RED = PatternFill('solid', fgColor='FFC7CE')     # extra, unsafe to remove
BLUE = PatternFill('solid', fgColor='DDEBF7')    # legacy value absent
HEAD = PatternFill('solid', fgColor='1F3864')
WRAP = Alignment(wrap_text=True, vertical='top')

# legacy value (VI, EN) -> platform key, per mapped field.
# Only the mapped fields are in scope; unrelated lookups are out of scope.
LEGACY = {
    'res.partner.gender': ('Giới tính BN', [
        ('Nam', 'Male', 'male'), ('Nữ', 'Female', 'female'),
        ('Khác', 'Other', 'other'),
        ('Không xác định', 'Unspecified', 'prefer_not_to_say')]),
    'crm.lead.gender': ('Giới tính BN', [
        ('Nam', 'Male', 'male'), ('Nữ', 'Female', 'female'),
        ('Khác', 'Other', 'other'),
        ('Không xác định', 'Unspecified', 'prefer_not_to_say')]),
    'crm.lead.service_interest': ('Dịch vụ quan tâm', [
        ('Chăm sóc giảm nhẹ', 'Palliative care', 'palliative'),
        ('Chăm sóc cá nhân', 'Personal care', 'personal_care'),
        ('Chăm sóc vết thương', 'Wound care', 'wound_care'),
        ('Bác sĩ khám', 'Medical Examination', 'consultation'),
        ('Tiêm', 'Injection', 'injection'),
        ('Truyền', 'IV infusion', 'iv_infusion'),
        ('Thụt tháo', 'Enema', 'enema'),
        ('Đặt, rút sonde', 'Catheter insertion/removal', 'catheter'),
        ('Hút đờm, vỗ rung đờm', 'Sputum suction', 'sputum_care'),
        ('Xét nghiệm', 'Laboratory testing', 'lab_test'),
        ('Khác', 'Other', 'other'),
        ('(price list only)', 'Imaging & Procedures', 'imaging_procedures'),
        ('(price list only)', 'Nursing Other', 'nursing_other')]),
    'crm.lead.health_contact_outcome': ('CSKH', [
        ('Chốt dùng dịch vụ', 'Service confirmed', 'service_booked'),
        ('Không nghe máy', 'No answer', 'no_answer'),
        ('Không phản hồi', 'No response', 'no_response'),
        ('Bận gọi lại sau', 'Busy – call back later', 'pending_follow_up'),
        ('Cân nhắc thêm', 'Considering further', 'future_opportunity'),
        ('Tham khảo dịch vụ', 'Service inquiry', 'service_inquiry'),
        ('Từ chối dịch vụ', 'Service declined', 'rejected')]),
    'crm.lead.contact_status': ('Service Status', [
        ('Mới', 'New', 'active'),
        ('Đặt lịch hẹn', 'Appointment scheduled', 'booking'),
        ('Đang suy nghĩ', 'Thinking / considering', 'thinking'),
        ('Liên hệ lại', 'To be contacted again', 'recontact'),
        ('Hủy', 'Cancelled', 'lost_booking'),
        ('Đã sử dụng', 'Service used', 'service_used'),
        ('Cũ', 'Existing', 'existing')]),
    'crm.lead.healthcare_lead_source': ('Nguồn Khách Hàng', [
        ('Form', 'Online form', 'website_form'),
        ('Hotline', 'Hotline / Call-in', 'phone_inquiry'),
        ('Đối tác', 'Partner', 'partner'),
        ('Tự đến PK', 'Walk-in to clinic', 'walk_in'),
        ('Người Giới Thiệu', 'Referrer', 'referral_patient'),
        ('Facebook', 'Facebook', 'facebook_ad'),
        ('Zalo', 'Zalo', 'zalo_marketing'),
        ('TikTok', 'TikTok', 'tiktok'),
        ('Google', 'Google', 'google'),
        ('Khách hàng cũ', 'Former client (sub-source)', 'former_client'),
        ('Bác sĩ/Điều dưỡng', 'Doctor/Nurse referral (sub-source)', 'referral_doctor')]),
    'res.partner.source_type': ('Nguồn Khách Hàng (client side)', [
        ('Facebook', 'Facebook', 'facebook'),
        ('Zalo', 'Zalo', 'zalo'),
        ('Form', 'Online form', 'website'),
        ('Hotline', 'Hotline / Call-in', 'phone'),
        ('Người Giới Thiệu', 'Referrer', 'referral'),
        ('Tự đến PK', 'Walk-in to clinic', 'walk_in'),
        ('Khác', 'Other', 'other')]),
    'res.partner.client_type': ('Loại khách hàng', [
        ('Mới', 'New', 'new'), ('Cũ', 'Repeat', 'repeat')]),
    'health.fieldservice.order.state': ('Trạng thái lịch hẹn', [
        ('Đặt chỗ mới', 'New Booking', 'confirmed'),
        ('Lịch tiếp theo', 'Next appointment', 'confirmed'),
        ('Dời lịch', 'Rescheduled', 'confirmed'),
        ('Đang tiến hành', 'In Progress', 'in_progress'),
        ('Đã hoàn thành', 'Completed', 'completed'),
        ('Hủy', 'Cancelled', 'cancelled')]),
    'health.fieldservice.order.service_location': ('Dịch vụ tại', [
        ('Tại Nhà', 'At home', 'home'),
        ('Tại PK', 'At clinic', 'clinic'),
        ('Telemedicine', 'Telemedicine', 'online')]),
    'health.fieldservice.order.payment_status': ('Thanh toán', [
        ('Chưa thanh toán', 'Unpaid', 'pending'),
        ('Đã thanh toán', 'Paid', 'paid'),
        ('Thanh toán một phần', 'Partial Payment', 'partial')]),
    'health.payment.transaction.payment_method': ('Method of Payment', [
        ('Tiền mặt', 'Cash', 'cash'),
        ('Chuyển khoản ngân hàng', 'Bank Transfer', 'bank_transfer'),
        ('Trả từ TT trước', 'Paid from prepayment balance', 'prepaid'),
        ('Thanh toán trước', 'Prepaid / Pay in advance', 'prepaid')]),
    '(no target field).invoice_print': ('In đơn', [
        ('In đơn lần 1', 'First invoice print', ''),
        ('In đơn cuối cùng', 'Final invoice print', '')]),
    'health.service.type.category': ('Contact_dich_vu_danh_muc', [
        ('DỊCH VỤ ĐIỀU DƯỠNG', 'Nursing services', 'nursing_care'),
        ('DỊCH VỤ BÁC SĨ', 'Doctor services', 'consultation'),
        ('DỊCH VỤ BÁC SĨ/ Người nước ngoài', 'Doctor services – foreigners',
         'foreigner_doctor')]),
}

# legacy record names per mapped many2one (English name as created)
LEGACY_M2O = {
    'health.booking.cancellation.reason': ('Lý do hủy', [
        'No doctor available > 2.5 hours', 'No doctor available < 2.5 hours',
        'No nurse available > 2.5 hours', 'No nurse available < 2.5 hours',
        'Preferred nurse not available', 'Hospitalized', 'Deceased',
        'Prescription completed/expired', 'Other']),
    'crm.lost.reason': ('Lý do từ chối', [
        'No doctor available < 2.5 hours', 'No doctor available > 2.5 hours',
        'No nurse available < 2.5 hours', 'No nurse available > 2.5 hours',
        'Price too high', 'Still considering', 'No prescription',
        'Consultation only', 'Address too far', 'Service not available',
        'Wrong hotline number', 'No equipment available',
        'No response / Did not say', 'Other']),
    'health.facility': ('Facility / Code', [
        'HN_PK_PKGDVU', 'HN_NS_Minh_Khai', 'HN_NS_Ha_Dong',
        'TPHCM_PK_CSTNVU', 'TPHCM_NS_Thu_Duc', 'TPHCM_NS_Tan_Thuan']),
    'health.catchment.province': ('City', ['Hà Nội', 'TPHCM']),
    'uom.uom': ('Đơn vị tính', ['Shift', 'Hours', 'Visit', 'km', 'Bottle', 'Units']),
    'health.medical.specialty': ('loai_kham', [
        'Internal Medicine', 'Surgery']),
    'utm.source': ('Nguồn Khách Hàng (sub-sources)', [
        'TikTok', 'Phòng khám Gia đình Việt Úc', 'Chăm sóc tại nhà Việt Úc',
        'FWD', 'Ivie - Bác sĩ ơi', 'Daiichi', 'Trường Quốc Tế Úc ACG',
        'Trường Quốc Tế Châu Âu', 'Bác sĩ/Điều dưỡng', 'Người Giới Thiệu',
        'Facebook', 'Zalo', 'Google', 'Đối tác', 'Khách hàng cũ',
        'Ms. Đặng Thị Thương', 'ĐD Song Phú', 'ĐD Trúc Mai',
        'ĐD Lê Đặng Anh Thương', 'Ms.Thu']),
}

# How deeply the platform itself depends on an extra selection value.
# (files referencing the key in code/views — measured by grep across addons)
CODE_REFS = {
    'draft': 209, 'assigned': 73, 'closed': 73, 'completed_pending_invoice': 34,
    'hospital': 14, 'nursing_home': 9, 'office': 13, 'other': 50,
    'overpaid': 2, 'refunded': 8, 'credit_card': 10, 'qr_code': 15,
    'home_visit': 60, 'clinic_visit': 32, 'follow_up': 28, 'preventive': 18,
    'rehabilitation': 19, 'emergency': 30, 'health_fair': 2,
    'community_outreach': 2, 'lead': 146, 'spam': 15, 'inbox_email': 2,
    'telemedicine': 20, 'physiotherapy': 8, 'laboratory': 12, 'imaging': 10,
    'referral_doctor': 8, 'website': 30, 'phone': 60, 'referral': 40,
}

# master values that live somewhere other than the list they appear under
ELSEWHERE = {
    'Lý do từ chối': "'Spam' is not created as a rejection reason — by your decision it "
                     "is carried as the Spam contact status instead.",
    'Nguồn Khách Hàng (sub-sources)': "'Hanoi' and 'HCMC' are not created as sources — a "
                                      "city is a catchment, and both already land on "
                                      "catchment_province_id.",
    'In đơn': "No target field: CareJioX has no invoice-print-count concept; e-invoicing "
              "is handled by the Red Invoice module.",
}

KEEP_NOTE = {
    'spam': 'Required by your own decision: the legacy reason "Spam" is stored as this status '
            'rather than as a rejection reason.',
    'inbox_email': 'Required by your own decision: the legacy contact column Source = "INBOX" '
                   'maps here.',
    'lead': 'Pipeline status used by the CRM itself, and what the importer assigns to a\n'
            'legacy contact of status "Mới" that has not booked yet.',
}


def load_dump():
    with open(DUMP, encoding='utf-8') as fh:
        return json.loads(fh.read().split('LOOKUPDUMP=', 1)[1])


def impact(used, refs, key):
    if key in KEEP_NOTE:
        note = KEEP_NOTE[key].replace('\n', ' ')
        if used:
            note += ' %d record(s) currently use it.' % used
        return 'KEEP', note
    parts = []
    if used:
        parts.append('%d record(s) currently use it — they would be left with an empty '
                     'field' % used)
    if refs >= 20:
        parts.append('heavily referenced in application code/views (~%d files) — removing it '
                     'would break workflow logic' % refs)
    elif refs >= 5:
        parts.append('referenced in ~%d code/view files — removing needs those updated' % refs)
    if not parts:
        return 'SAFE', 'Nothing uses it and no code depends on it — can be removed cleanly.'
    verdict = 'UNSAFE' if (used or refs >= 20) else 'REVIEW'
    return verdict, '; '.join(parts) + '.'


def style_header(ws, headers, widths):
    bold = Font(bold=True, color='FFFFFF')
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = bold
        c.fill = HEAD
        c.alignment = WRAP
        ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.freeze_panes = 'A2'


def build():
    dump = load_dump()
    wb = openpyxl.Workbook()

    # ---------------------------------------------------------------- summary
    ws = wb.active
    ws.title = 'Summary'
    style_header(ws, ['Legacy List', 'Type', 'Target Field / Model',
                      'Legacy Values', 'In CareJioX', 'Verdict',
                      'Extra (not in legacy)', 'Missing (in legacy, absent here)'],
                 [30, 12, 42, 13, 13, 26, 46, 40])
    r = 2
    summary_rows = []

    for field, (legacy_name, triples) in LEGACY.items():
        info = dump['selections'].get(field)
        if not info:
            continue
        legacy_keys = []
        for _vi, _en, key in triples:
            if key not in legacy_keys:
                legacy_keys.append(key)
        sys_keys = [v['key'] for v in info['values']]
        extra = [k for k in sys_keys if k not in legacy_keys]
        missing = [k for k in legacy_keys if k not in sys_keys]
        verdict = ('EXACT MATCH' if not extra and not missing
                   else 'EXTRA VALUES PRESENT' if extra and not missing
                   else 'MISSING VALUES' if missing and not extra
                   else 'EXTRA + MISSING')
        summary_rows.append((legacy_name, 'Selection', field, len(legacy_keys),
                             len(sys_keys), verdict, extra, missing, info))

    for model, (legacy_name, names) in LEGACY_M2O.items():
        info = dump['m2o'].get(model)
        if not info:
            continue
        active = [x for x in info['records'] if x['active']]
        sys_names = [x['en'] for x in active]
        norm = lambda s: s.strip().lower()
        legacy_norm = {norm(n) for n in names}
        extra = [n for n in sys_names if norm(n) not in legacy_norm]
        missing = [n for n in names if norm(n) not in {norm(s) for s in sys_names}]
        verdict = ('EXACT MATCH' if not extra and not missing
                   else 'EXTRA VALUES PRESENT' if extra and not missing
                   else 'MISSING VALUES' if missing and not extra
                   else 'EXTRA + MISSING')
        summary_rows.append((legacy_name, 'Many2one', model, len(names),
                             len(active), verdict, extra, missing, info))

    for row in summary_rows:
        legacy_name, typ, target, nleg, nsys, verdict, extra, missing, _info = row
        note = ELSEWHERE.get(legacy_name, '')
        if note:
            verdict = verdict + ' *'
        vals = [legacy_name, typ, target, nleg, nsys, verdict,
                ', '.join(extra) if extra else '—',
                (', '.join(missing) + (' — ' + note if note else '')) if missing
                else (note or '—')]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.alignment = WRAP
        fill = GREEN if verdict == 'EXACT MATCH' else (
            BLUE if verdict == 'MISSING VALUES' else AMBER)
        ws.cell(row=r, column=6).fill = fill
        r += 1

    # ------------------------------------------------------ selection detail
    ws2 = wb.create_sheet('Selection Fields')
    style_header(ws2, ['Target Field', 'Legacy Value (VI)', 'Legacy Value (EN)',
                       'Stored Key', 'Label Shown (EN)', 'Label Shown (VI)',
                       'Status', 'Records Using It', 'If Removed'],
                 [40, 30, 30, 26, 30, 30, 16, 15, 62])
    r = 2
    for field, (legacy_name, triples) in LEGACY.items():
        info = dump['selections'].get(field)
        if not info:
            continue
        by_key = {v['key']: v for v in info['values']}
        seen = set()
        for vi, en, key in triples:
            v = by_key.get(key)
            status = 'LEGACY' if v else 'MISSING'
            vals = [field, vi, en, key,
                    v['en'] if v else '(absent)', v['vi'] if v else '(absent)',
                    status, v['used'] if v else 0,
                    'Required — this is a legacy value.' if v else
                    'This legacy value has no home in the system.']
            for i, val in enumerate(vals, start=1):
                ws2.cell(row=r, column=i, value=val).alignment = WRAP
            ws2.cell(row=r, column=7).fill = GREEN if v else BLUE
            r += 1
            seen.add(key)
        for v in info['values']:
            if v['key'] in seen:
                continue
            refs = CODE_REFS.get(v['key'], 0)
            verdict, note = impact(v['used'], refs, v['key'])
            vals = [field, '— not in legacy list —', '', v['key'], v['en'], v['vi'],
                    'EXTRA', v['used'], note]
            for i, val in enumerate(vals, start=1):
                ws2.cell(row=r, column=i, value=val).alignment = WRAP
            ws2.cell(row=r, column=7).fill = (
                RED if verdict in ('UNSAFE', 'KEEP') else AMBER)
            r += 1

    # ------------------------------------------------------------ m2o detail
    ws3 = wb.create_sheet('Many2one Lookups')
    style_header(ws3, ['Target Model', 'Legacy List', 'Value (EN)', 'Value (VI)',
                       'Status', 'Active', 'Records Using It', 'If Removed'],
                 [38, 30, 40, 34, 16, 10, 15, 60])
    r = 2
    for model, (legacy_name, names) in LEGACY_M2O.items():
        info = dump['m2o'].get(model)
        if not info:
            continue
        norm = lambda s: s.strip().lower()
        legacy_norm = {norm(n) for n in names}
        present = {norm(x['en']) for x in info['records'] if x['active']}
        for x in info['records']:
            if not x['active']:
                continue
            is_legacy = norm(x['en']) in legacy_norm
            if is_legacy:
                status, note = 'LEGACY', 'Required — this is a legacy value.'
                fill = GREEN
            else:
                verdict, note = impact(x['used'], 0, x['en'])
                status = 'EXTRA'
                fill = RED if verdict == 'UNSAFE' else AMBER
            # usage detail is informational on every row — it must never change
            # whether the value is legacy or extra
            if x.get('detail'):
                note += ' Referenced by: %s.' % ', '.join(
                    '%s (%d)' % (k, v) for k, v in list(x['detail'].items())[:4])
            vals = [model, legacy_name, x['en'], x['vi'], status,
                    'Yes' if x['active'] else 'No', x['used'], note]
            for i, val in enumerate(vals, start=1):
                ws3.cell(row=r, column=i, value=val).alignment = WRAP
            ws3.cell(row=r, column=5).fill = fill
            r += 1
        for n in names:
            if norm(n) not in present:
                vals = [model, legacy_name, n, '', 'MISSING', '—', 0,
                        'Legacy value not present in the system.']
                for i, val in enumerate(vals, start=1):
                    ws3.cell(row=r, column=i, value=val).alignment = WRAP
                ws3.cell(row=r, column=5).fill = BLUE
                r += 1
        archived = [x for x in info['records'] if not x['active']]
        if archived:
            vals = [model, legacy_name,
                    '(%d older value(s) archived by the migration)' % len(archived),
                    '', 'ARCHIVED', 'No',
                    sum(x['used'] for x in archived),
                    'Hidden from every dropdown. Kept, not deleted, so existing records '
                    'that already point at them stay valid.']
            for i, val in enumerate(vals, start=1):
                ws3.cell(row=r, column=i, value=val).alignment = WRAP
            ws3.cell(row=r, column=5).fill = GREY_OR_BLUE
            r += 1
    wb.save(DST)
    print('Wrote', DST)


GREY_OR_BLUE = PatternFill('solid', fgColor='E7E6E6')

if __name__ == '__main__':
    build()
