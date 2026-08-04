#!/usr/bin/env python3
"""Migration Audit Report v3 — adds the "Implementation Status" column.

Takes Migration_Audit_Report_v2.xlsx (which carries the client's own
"My Recommendation" column) and appends one final column recording what was
actually built and deployed, so the workbook doubles as the delivery record.

Status vocabulary:
  DONE                  — built, deployed to vietuat and verified
  DONE (real export)    — code is in place; the source column is empty in the
                          redacted sample, so it activates on the real export
  BY DESIGN             — deliberately not migrated (agreed)
  LATER PHASE           — deferred (structured VN address parser)
"""
from copy import copy
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

SRC = "/Users/adity/Documents/GitHub/health19/Migration/Migration_Audit_Report_v2.xlsx"
DST = "/Users/adity/Documents/GitHub/health19/Migration/Migration_Audit_Report_v3.xlsx"

GREEN = PatternFill("solid", fgColor="C6EFCE")
BLUE = PatternFill("solid", fgColor="DDEBF7")
GREY = PatternFill("solid", fgColor="E7E6E6")
AMBER = PatternFill("solid", fgColor="FFE0B2")
WRAP = Alignment(wrap_text=True, vertical="top")

DONE = "DONE"
REAL = "DONE (real export)"
DESIGN = "BY DESIGN"
LATER = "LATER PHASE"


def fill_for(status):
    if status.startswith("DONE (real"):
        return BLUE
    if status.startswith("DONE"):
        return GREEN
    if status.startswith("LATER"):
        return AMBER
    return GREY


# --------------------------------------------------------------- booking sheet
BOOKING = {
    "Sequence": (DESIGN, "Row index — no business meaning."),
    "Appointment Date": (DONE, "Already migrated; unchanged."),
    "Appointment Time": (DESIGN, "Always 00:00; time_in carries the real time."),
    "CreatedOn": (DONE, "Payment date; legacy audit trail now also on the booking."),
    "dich_vu_tai": (DONE, "service_location map added — the hard-coded 'home' is gone; "
                          "21 clinic bookings corrected. Labels relabelled Tại Nhà / Tại Phòng khám."),
    "CreatedBy": (DONE, "New field health.fieldservice.order.legacy_created_by, shown in the "
                        "Legacy Record panel."),
    "lien_ket_lien_he": (DONE, "Booking↔contact link implemented via crm_lead_id (Pancake id, "
                               "unambiguous-phone fallback). Column itself is empty."),
    "Contact_ad_id_tiktok": (DONE, "Bundled into res.partner.legacy_ad_ids (JSON)."),
    "Contact_dich_vu_danh_muc": (DESIGN, "Empty; the contact-level column is the real source."),
    "Contact_dich_vu_quan_tam": (DESIGN, "Empty; the contact-level column is the real source."),
    "so_cccd": (DONE, "Already migrated."),
    "Name": (DESIGN, "Short label; ten_benh_nhan carries the real name."),
    "so_dien_thoai": (REAL, "Transform correct; real numbers arrive with the unredacted export."),
    "so_dien_thoai_2": (REAL, "Now written to res.partner.phone; empty in the sample."),
    "gui_xe": (REAL, "parking_charge field + map in place; column empty in the sample."),
    "Contact_nam_sinh": (DONE, "Already migrated."),
    "nghe_nghiep": (DONE, "Already migrated."),
    "dan_toc": (REAL, "ethnicity map in place; column empty in the sample."),
    "Contact_gioi_tinh": (DONE, "'Không xác định' and 'Khác' are no longer dropped; labels "
                                "relabelled (prefer_not_to_say = Unspecified / Không xác định)."),
    "Client ID": (DONE, "Upsert key."),
    "ten_benh_nhan": (REAL, "Transform correct; real names arrive with the unredacted export."),
    "SourceofClient": (DONE, "Now writes source_type + source_details (raw string kept); named "
                             "referrers also land in referral_source and get a utm.source."),
    "Client_Type": (DONE, "New field res.partner.client_type (New/Repeat), shown on the client "
                          "form. Once a client is seen as repeat it stays repeat."),
    "lien_ket_benh_nhan": (DESIGN, "Pancake link column, empty."),
    "trang_thai": (DONE, "Map widened (in-progress, next-appointment, new-booking). 'Dời lịch' "
                         "now raises the new is_rescheduled flag and shows a Rescheduled tag."),
    "ly_do_huy": (DONE, "cancellation_reason_id linked to the 9 legacy reasons; free text kept "
                        "in cancellation_notes."),
    "Contact_phong_kham": (DONE, "Now resolves the branch facility (Hanoi_NS_MinhKhai, "
                                 "HCMC_NS_ThuDuc, …) instead of only the city."),
    "phong_kham_city": (DONE, "Still the fallback when no branch is named."),
    "phu_phi": (DONE, "Mapped to travel_charge (22 rows / 1.45M VND)."),
    "nguoi_thuc_hien": (DESIGN, "Duplicate of the staff column."),
    "khoang_cach": (DESIGN, "Geocoded driving distance is kept as the better source."),
    "Contact_FullAddress": (REAL, "Fallback street; truncated in the sample."),
    "country": (LATER, "Structured VN address parser — later phase."),
    "province": (LATER, "Structured VN address parser — later phase."),
    "district": (LATER, "Structured VN address parser — later phase."),
    "commune": (LATER, "Structured VN address parser — later phase."),
    "Contact_Address": (REAL, "Street; truncated in the sample."),
    "note": (DONE, "Already migrated into patient_notes."),
    "Contact_customer_id": (DONE, "Used as a booking↔contact join key; also in legacy_ad_ids."),
    "phong_kham_Owner": (DONE, "New field legacy_owner. The booking form now also shows the "
                               "facility's Operations Manager."),
    "loai_kham": (REAL, "Specialty 'Surgery / Khám ngoại' created; column empty in the sample."),
    "dich_vu": (DONE, "Already migrated (service types, products, sale lines)."),
    "time_in": (DONE, "Already migrated."),
    "time_out": (DONE, "Already migrated as duration."),
    "TransferMoney": (DONE, "Now its own bank-transfer transaction instead of a summed row."),
    "thanh_toan_truoc": (REAL, "Prepaid transactions supported (a 'Trả từ TT trước' payment is "
                               "recorded whenever a prepaid visit has a non-zero balance to settle); "
                               "only 6 rows carry a value in this export."),
    "Cash": (DONE, "Now its own cash transaction."),
    "SubTotal": (DONE, "Sale lines carry the real price (703.9M VND recovered)."),
    "Discount": (DONE, "Applied as a line discount percentage so the net is exact (67.2M VND)."),
    "thanh_toan": (DONE, "Now drives the settlement method. Note on the 74 'Trả từ TT trước' rows: "
                         "58 of them carry a 100% discount (Discount = SubTotal, net zero) because "
                         "the money was collected earlier when the prepayment package was bought, so "
                         "no further payment or invoice belongs on the visit — the remaining 16 keep "
                         "their real cash/transfer method."),
    "ModifiedBy": (DONE, "New field legacy_modified_by."),
    "thoi_gian_bat_dau": (DESIGN, "Derived from booking history instead of stored."),
    "bac_si_dieu_duong": (DONE, "Already migrated."),
    "tao_don": (DESIGN, "Constant workflow flag."),
    "so_don_da_tao": (DESIGN, "One sale order per booking, implicit."),
    "dich_vu_don_vi_tinh": (REAL, "UoM 'Ca'/'Chai'/'Lần' created; column empty in the sample."),
    "GrandTotal": (DONE, "Computed from the priced lines."),
    "TotalQuantity": (DONE, "Drives the line quantity on single-service bookings."),
    "hinh_thuc_thanh_toan": (DONE, "Labels relabelled to the legacy wording; mixed cash+transfer "
                                   "rows are now split into two transactions."),
    "tra": (DESIGN, "Empty in the export; payment status is derived from thanh_toan."),
    "kanban_order": (DESIGN, "Legacy UI ordering."),
    "nguoi_phu_trach": (DESIGN, "Legacy ops metadata; covered by legacy_owner."),
    "ModifiedOn": (DONE, "New field legacy_modified_on."),
    "in_don": (DESIGN, "No print-count concept; e-invoicing is a separate module."),
    "Owner": (DESIGN, "Legacy audit metadata."),
    "PancakeCustomer ID": (DONE, "Booking↔contact join key; also stored in legacy_ad_ids."),
    "page_id": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "ad_id": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "TimeEnd": (DESIGN, "Duplicate timing column."),
    "TimeStart": (DESIGN, "Duplicate timing column."),
    "mo_ta_tinh_trang": (DONE, "Already migrated into patient_notes."),
    "ad_id_fb": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "conversation_id": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "Facebook Link": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "col": (DESIGN, "Unnamed column."),
    "col_1": (DESIGN, "Unnamed column."),
}

# --------------------------------------------------------------- contact sheet
CONTACT = {
    "STT": (DESIGN, "Row index."),
    "ID": (DONE, "Upsert key."),
    "ngay_dau_su_dung": (DONE, "New field crm.lead.first_service_date, shown on the lead form."),
    "Name": (REAL, "Transform correct; real names arrive with the unredacted export."),
    "gioi_tinh": (DONE, "Migrated; 'Không xác định' now maps to Unspecified instead of blank."),
    "nam_sinh": (DONE, "Migrated to birth_date."),
    "nguon_khach_hang": (DONE, "Map widened (partner, TikTok, Google, former client, walk-in, "
                               "referrer, doctor). Unlisted partners/referrers become a "
                               "utm.source and fill 'Referred By'."),
    "phong_kham": (DONE, "Now resolves crm.lead.facility_id, including the branch clinics."),
    "customer_id": (DONE, "Used as a booking↔contact join key."),
    "ly_do_tu_choi": (DONE, "lost_reason_id linked to the 14 legacy reasons; 'Spam' sets the "
                            "spam contact status; free text kept in reason_if_rejected."),
    "Phone": (REAL, "Transform correct; real numbers arrive with the unredacted export."),
    "so_dien_thoai_2": (DONE, "New field crm.lead.phone2, shown on the lead form."),
    "NextContactAt": (DONE, "Mapped to next_follow_up_date."),
    "so_cccd": (REAL, "national_id map in place; empty in the redacted sample."),
    "ten_benh_nhan": (DONE, "Mapped to contact_name (Patient Name on the lead form)."),
    "khoang_cach": (DONE, "Mapped to distance_from_clinic."),
    "dich_vu_quan_tam": (DONE, "Selection extended with the 9 legacy interests and now set "
                               "structurally (free text still appended to the description)."),
    "loai_khach_hnagf": (DESIGN, "New/repeat lives on the client record (res.partner.client_type)."),
    "ghi_chu": (DONE, "Already migrated."),
    "Source": (DONE, "'INBOX' now maps to the new Email Inbox lead source when no other "
                     "source is given."),
    "cskh_3": (DONE, "Mapped to health_contact_outcome; 'Không nghe máy' and 'Tham khảo dịch vụ' "
                     "added as keys, unused 'Not Qualified' removed."),
    "Untitled": (DESIGN, "Unnamed column."),
    "Untitled2": (DESIGN, "Unnamed column."),
    "phan_hoi_kh": (DONE, "Mapped to follow_up_notes."),
    "PancakeCustomer": (DONE, "Booking↔contact join key."),
    "PancakeCustomer ID": (DONE, "Booking↔contact join key."),
    "Address": (DONE, "Lead street now written (was never written before)."),
    "Status": (DONE, "Four legacy statuses added as real keys: Đang suy nghĩ, Liên hệ lại, "
                     "Đã sử dụng, Cũ — each with its own stage."),
    "Owner": (DONE, "Matched to a platform user (salesperson) when the name matches, else kept "
                    "in legacy_owner. Confirmed not a duplicate of the Care Command claim, "
                    "which owns a conversation rather than the lead."),
    "pancake_tag": (DESIGN, "Pancake tags carry no business meaning."),
    "lien_ket_lich_hen": (DESIGN, "Link column."),
    "FullAddress": (DONE, "Fallback street."),
    "Address_1": (DESIGN, "Duplicate address column."),
    "country": (LATER, "Structured VN address parser — later phase."),
    "province": (LATER, "Structured VN address parser — later phase."),
    "district": (LATER, "Structured VN address parser — later phase."),
    "commune": (LATER, "Structured VN address parser — later phase."),
    "kanban_order": (DESIGN, "Legacy UI ordering."),
    "dich_vu_don_vi_tinh": (REAL, "UoM records created; column empty in the sample."),
    "dich_vu_danh_muc": (DONE, "Category relabelled to the legacy wording; the foreigner-doctor "
                               "category added as a key."),
    "CreatedOn": (DESIGN, "Legacy create date is audit-only."),
    "dich_vu_RetailPrice": (DESIGN, "Product prices come from the price-list importer."),
    "dich_vu": (DESIGN, "Bookings carry the services."),
    "SubTotal": (DESIGN, "Booking-level figures are the financial source."),
    "Discount": (DESIGN, "Booking-level figures are the financial source."),
    "GrandTotal": (DESIGN, "Booking-level figures are the financial source."),
    "CreatedBy": (DONE, "New field crm.lead.legacy_created_by."),
    "ModifiedOn": (DESIGN, "Legacy audit metadata."),
    "psid": (DONE, "Bundled into crm.lead.legacy_ad_ids (JSON)."),
    "TotalQuantity": (DESIGN, "Booking-level figures are the financial source."),
    "Email": (REAL, "email_from now written; every value is empty in this export."),
    "ModifiedBy": (DESIGN, "Legacy audit metadata."),
    "page_id": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "LastContactUser": (DONE, "New field crm.lead.legacy_lastcontactuser."),
    "ad_id": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "TransferMoney": (DESIGN, "Booking-level figures are the financial source."),
    "Note": (DONE, "Already migrated."),
    "Cash": (DESIGN, "Booking-level figures are the financial source."),
    "LastContactAt": (DESIGN, "Follow-ups live in NextContactAt."),
    "ad_id_tiktok": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "ad_id_fb": (DONE, "Bundled into legacy_ad_ids (JSON)."),
    "Facebook Link": (DONE, "Bundled into legacy_ad_ids (JSON)."),
}

# --------------------------------------------------------------- lookup sheets
# Status per lookup LIST; every row of that list gets the same entry.
LOOKUP = {
    "Giới tính BN (Gender)": (
        DONE, "Selection kept; 'prefer_not_to_say' relabelled Unspecified / Không xác định. "
              "The importer no longer drops 'Không xác định' or 'Khác'."),
    "Lý do từ chối (Rejection Reason)": (
        DONE, "All 14 legacy reasons created as crm.lost.reason records with Vietnamese "
              "translations; the 3 generic core reasons archived. Leads now carry a structured "
              "lost reason. 'Spam' sets the spam contact status."),
    "Dịch vụ quan tâm (Service of Interest)": (
        DONE, "Selection extended with the 9 missing interests; 'Consultation' relabelled to "
              "Medical Examination / Bác sĩ khám. Now set structurally on the lead."),
    "Loại khách hàng (Customer Type)": (
        DONE, "New field res.partner.client_type with Mới/Cũ labels, populated by the migration; "
              "the application can derive it from booking history afterwards."),
    "CSKH / Contact Disposition": (
        DONE, "'Không nghe máy' and 'Tham khảo dịch vụ' added as keys; the unused 'Not Qualified' "
              "removed; every label matched to the legacy wording."),
    "Service Status (Contact)": (
        DONE, "Four new keys (Đang suy nghĩ, Liên hệ lại, Đã sử dụng, Cũ) with matching stages; "
              "existing labels relabelled to the legacy wording."),
    "Đơn vị tính (Unit of Measure)": (
        REAL, "'Ca' (Shift), 'Chai' (Bottle) and 'Lần' (Visit) created with Vietnamese names; "
              "the unit column is empty in this export."),
    "Nguồn Khách Hàng (Lead Source)": (
        DONE, "Selection extended (Partner, TikTok, Google, Former Client, Email Inbox) and "
              "relabelled to the legacy wording; every sub-source and named referrer exists as a "
              "utm.source record."),
    "Contact_dich_vu_danh_muc (Service Category)": (
        DONE, "Foreigner-doctor category added as a key; the two existing categories relabelled "
              "to the legacy wording."),
    "loai_kham (Visit Type)": (
        REAL, "'Surgery / Khám ngoại' specialty created; the column is empty in this export."),
    "Trạng thái lịch hẹn (Booking Status)": (
        DONE, "Labels relabelled to the legacy wording; 'Đang tiến hành' and 'Lịch tiếp theo' "
              "now map correctly. 'Dời lịch' raises the new is_rescheduled flag, which shows a "
              "Rescheduled tag on the booking."),
    "Dịch vụ tại (Service Location)": (
        DONE, "Hard-coded 'home' removed — 21 clinic bookings corrected; labels relabelled "
              "Tại Nhà / Tại Phòng khám / Telemedicine."),
    "Lý do hủy (Cancellation Reason)": (
        DONE, "All 9 legacy reasons created with Vietnamese translations and linked on cancelled "
              "bookings; the 16 pre-existing generic reasons archived so only the legacy list "
              "remains selectable."),
    "City": (DONE, "Unchanged — proper nouns identical in both languages."),
    "Thanh toán (Payment Status)": (
        DONE, "fso.payment_status relabelled to the legacy wording; it now follows from the "
              "recovered payments and invoices."),
    "Method of Payment": (
        DONE, "All four legacy methods map 1:1 and the labels now read as they did before. Cash and "
              "transfer are recorded as separate transactions instead of one summed row. "
              "'Trả từ TT trước' is available and used whenever a prepaid visit still has a balance "
              "to settle; in this export those visits are already fully discounted to zero, so they "
              "correctly carry no further payment."),
    "In đơn (Invoice Print)": (
        DESIGN, "No print-count concept in CareJioX; e-invoicing is handled by the Red Invoice "
                "module."),
    "Facility / Code": (
        DONE, "All 6 official facilities created with the legacy codes; every booking, client, "
              "employee and lead re-pointed from the 2 generic city facilities, which are now "
              "archived."),
}


# Measured on the live system after the migration re-run and the financial
# pass. Filled in from Migration/verified_counts.json when that file exists so
# the workbook always quotes real numbers rather than hand-typed ones.
VERIFIED_FALLBACK = {}


def load_verified():
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'verified_counts.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    return VERIFIED_FALLBACK


VERIFIED_ROWS = [
    ('bookings_total', 'Bookings migrated'),
    ('clients_total', 'Clients migrated'),
    ('leads_total', 'Contacts migrated'),
    ('revenue_vnd', 'Revenue on quote lines (VND)'),
    ('discount_lines', 'Lines carrying a legacy discount'),
    ('txn_total', 'Payment transactions'),
    ('txn_cash', '  · cash'),
    ('txn_bank', '  · bank transfer'),
    ('txn_prepaid', '  · paid from prepayment balance'),
    ('invoices_posted', 'Posted invoices (incl. 127 pre-existing)'),
    ('fso_with_invoice', 'Bookings linked to their invoice'),
    ('active_cancel_reasons', 'Cancellation reasons selectable (legacy list)'),
    ('active_lost_reasons', 'Rejection reasons selectable (legacy list)'),
    ('active_facilities', 'Facilities selectable (official codes)'),
    ('fso_facility_official', 'Bookings on an official facility'),
    ('service_location_clinic', 'Clinic bookings corrected (were all "home")'),
    ('is_rescheduled', 'Bookings flagged rescheduled'),
    ('cancel_linked', 'Cancelled bookings with a structured reason'),
    ('lost_linked', 'Contacts with a structured rejection reason'),
    ('lead_spam', 'Contacts routed to the Spam status'),
    ('lead_source', 'Contacts with a lead source'),
    ('lead_interest', 'Contacts with a service interest'),
    ('lead_outcome', 'Contacts with a contact outcome'),
    ('partner_client_type', 'Clients with New/Repeat type'),
    ('partner_source', 'Clients with an acquisition source'),
    ('fso_legacy_audit', 'Bookings carrying the legacy audit trail'),
    ('utm_sources', 'Marketing sources (incl. legacy sub-sources)'),
]


def style_header(ws, col, text, ref_col):
    c = ws.cell(row=1, column=col, value=text)
    c._style = copy(ws.cell(row=1, column=ref_col)._style)


def do_mapping_sheet(ws, statuses, col_idx):
    style_header(ws, col_idx, "Implementation Status", col_idx - 1)
    missing = []
    for r in range(2, ws.max_row + 1):
        key = ws.cell(row=r, column=1).value
        if key is None or str(key).strip() == "":
            continue
        key = str(key).strip()
        if key not in statuses:
            missing.append(key)
            continue
        status, note = statuses[key]
        c = ws.cell(row=r, column=col_idx, value="%s — %s" % (status, note))
        c.alignment = WRAP
        c.fill = fill_for(status)
    if missing:
        raise SystemExit("%s: no status for %s" % (ws.title, missing))
    ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 62


def do_lookup_sheet(ws, col_idx):
    style_header(ws, col_idx, "Implementation Status", col_idx - 1)
    group = None
    unknown = set()
    for r in range(2, ws.max_row + 1):
        a = ws.cell(row=r, column=1).value
        if a and str(a).strip():
            group = str(a).strip()
        if not str(ws.cell(row=r, column=2).value or "").strip():
            continue
        if group not in LOOKUP:
            unknown.add(group)
            continue
        status, note = LOOKUP[group]
        c = ws.cell(row=r, column=col_idx, value="%s — %s" % (status, note))
        c.alignment = WRAP
        c.fill = fill_for(status)
    if unknown:
        raise SystemExit("%s: no status for groups %s" % (ws.title, sorted(unknown)))
    ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 62


def do_summary(ws):
    def tally(d):
        out = {}
        for status, _ in d.values():
            out[status] = out.get(status, 0) + 1
        return out
    b, c = tally(BOOKING), tally(CONTACT)
    total = {k: b.get(k, 0) + c.get(k, 0) for k in set(b) | set(c)}
    r = ws.max_row + 2
    lines = [
        ("v3 — IMPLEMENTATION COMPLETE (deployed to vietuat)", True),
        ("Every decision recorded in the 'My Recommendation' column has been built and deployed. "
         "The final column on each sheet records what was done, field by field.", False),
        ("Legacy column outcomes across both mapping sheets: "
         + " · ".join("%s = %d" % (k, v) for k, v in sorted(total.items())), False),
        ("Lookups are now like-for-like: 9 cancellation reasons and 14 rejection reasons created "
         "with Vietnamese translations (the 16 + 3 pre-existing generic values archived, not "
         "deleted, so existing records keep valid references); all 6 official facilities created "
         "and every booking/client/employee/lead re-pointed onto them.", False),
        ("Bilingual display: static selections carry Vietnamese labels in the database; "
         "code-based selections (booking status, service location, contact status, contact "
         "outcome, payment method) carry them in each module's vi_VN translation file. A user "
         "set to Tiếng Việt sees the original legacy wording; an English user sees the English.", False),
        ("Financial recovery: quote lines now carry the real prices (703,951,000 VND gross; "
         "636,795,700 net of the 67,155,300 in legacy discounts, applied as an exact percentage so "
         "the net is preserved to the dong). Cash and transfer are separate transactions rather than "
         "one summed row, and completed visits that were actually settled have a posted invoice "
         "linked to the booking and its payments.", False),
        ("Historical invoices are posted WITHOUT filing an e-invoice with the tax authority. Posting "
         "normally triggers the Viettel Red Invoice integration; a migration must never do that, so "
         "the importer posts with a skip_redinvoice guard enforced in code rather than relying on a "
         "settings toggle. Invoices are also deliberately left unreconciled — reconciliation moves "
         "real cash/bank balances and is a finance decision, not a migration step.", False),
        ("Still pending by agreement: the structured Vietnamese address parser (province / "
         "district / ward), and everything marked DONE (real export), where the code is in place "
         "but the source column is blank in this redacted sample.", False),
    ]
    bold = Font(bold=True)
    for text, is_bold in lines:
        cell = ws.cell(row=r, column=1, value=text)
        cell.alignment = WRAP
        if is_bold:
            cell.font = bold
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        ws.row_dimensions[r].height = max(15, 14 * (len(text) // 95 + 1))
        r += 1

    verified = load_verified()
    if verified:
        r += 1
        head = ws.cell(row=r, column=1, value='VERIFIED ON THE LIVE SYSTEM')
        head.font = bold
        r += 1
        for key, label in VERIFIED_ROWS:
            if key not in verified:
                continue
            ws.cell(row=r, column=1, value=label).alignment = WRAP
            v = ws.cell(row=r, column=2, value=verified[key])
            v.font = bold
            v.fill = GREEN
            r += 1


def main():
    wb = openpyxl.load_workbook(SRC)
    do_mapping_sheet(wb["Mapping - Booking"], BOOKING, 11)
    do_mapping_sheet(wb["Mapping - Contact"], CONTACT, 11)
    do_lookup_sheet(wb["Lookup - Contact Table"], 13)
    do_lookup_sheet(wb["Lookup - Booking Table"], 13)
    do_summary(wb["Summary"])
    wb.save(DST)
    print("Wrote", DST)


if __name__ == "__main__":
    main()
