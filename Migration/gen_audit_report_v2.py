#!/usr/bin/env python3
"""Migration Audit Report v2 — adds gap-resolution + lookup-fidelity columns.

Reads Migration_Audit_Report.xlsx (never modified) and writes
Migration_Audit_Report_v2.xlsx with:
  * Mapping - Booking / Mapping - Contact: cols F-I
      F Proposed Target | G Gap Resolution | H Original Value Kept? | I Recommendation / Decision
  * Lookup - Contact Table / Lookup - Booking Table: cols H-K
      H Field Type | I Bilingual Today? | J To Use Original Value | K Recommendation
  * Summary: appended "v2 additions" block.

Decision locked with the user: DISPLAY FIDELITY — stored values stay technical codes,
but the label users see must equal the original legacy value, VI for Vietnamese-preference
users and EN for English-preference users (both languages are active on vietuat).
All field types / translate flags below were verified live against ir_model_fields.
"""
from copy import copy
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

SRC = "/Users/adity/Documents/GitHub/health19/Migration/Migration_Audit_Report.xlsx"
DST = "/Users/adity/Documents/GitHub/health19/Migration/Migration_Audit_Report_v2.xlsx"

GREEN = PatternFill("solid", fgColor="C6EFCE")   # home exists / already fixed
ORANGE = PatternFill("solid", fgColor="FFE0B2")  # create / extend needed
RED = PatternFill("solid", fgColor="FFC7CE")     # impossible — reason given
GREY = PatternFill("solid", fgColor="E7E6E6")    # leave by design
WRAP = Alignment(wrap_text=True, vertical="top")

# ---------------------------------------------------------------------------
# Mapping-sheet proposals.  key = legacy column (col A), value =
# (Proposed Target, Gap Resolution, Original Value Kept?, Recommendation)
# Gap Resolution drives the row colour: ALREADY*/EXISTS* -> green,
# CREATE* -> orange, BY DESIGN* -> grey.  H coloured on its own:
# YES -> green, PARTLY -> orange, NO -> red.
# ---------------------------------------------------------------------------

BOOKING = {
    "Sequence": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                 "Row index of the export — no business meaning."),
    "Appointment Date": ("health.fieldservice.order.scheduled_datetime", "ALREADY MIGRATED",
                         "YES — value unchanged (typed datetime, stored UTC; UI shows VN local time)",
                         "No action."),
    "Appointment Time": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                         "Always 00:00 in the export; time_in carries the real time."),
    "CreatedOn": ("health.payment.transaction.transaction_date", "ALREADY MIGRATED",
                  "YES — value unchanged (parsed to typed datetime)",
                  "Optionally CREATE fso.legacy_created_on for audit-trail display — recommend leave."),
    "dich_vu_tai": ("health.fieldservice.order.service_location (Selection: home/clinic/online)",
                    "EXISTS — map only (P1 fix)",
                    "YES — via bilingual label (relabel: 'Tại Nhà'/'At home', 'Tại Phòng khám'/'At clinic', 'Telemedicine')",
                    "Fix the hardcoded 'home' (21 clinic rows wrong today) and relabel the selection to the legacy wording."),
    "CreatedBy": ("CREATE: fso.legacy_created_by (Char) — else LEAVE", "BY DESIGN — leave (CREATE optional)",
                  "YES — value unchanged if the field is created (free text)",
                  "DECISION: legacy operator name, audit-only — recommend LEAVE."),
    "lien_ket_lien_he": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                         "Pancake link column, empty in the export."),
    "Contact_ad_id_tiktok": ("LEAVE — or CREATE one crm.lead.legacy_ad_ids (JSON) bundling all ad ids",
                             "BY DESIGN — leave (CREATE optional)",
                             "YES — value unchanged if bundled into a JSON field",
                             "DECISION: marketing tracking — recommend LEAVE; one JSON field can hold page_id/ad_id/psid/conversation_id if ever needed."),
    "Contact_dich_vu_danh_muc": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                                 "Empty in the export; the contact-level dich_vu_danh_muc is the real source (see Contact sheet)."),
    "Contact_dich_vu_quan_tam": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                                 "Empty in the export; covered by the contact-level dich_vu_quan_tam."),
    "so_cccd": ("res.partner.national_id", "ALREADY MIGRATED", "YES — value unchanged",
                "No action (PHI-encrypted at rest via national_id_enc)."),
    "Name": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
             "Short label ('Bn'); the real name comes from ten_benh_nhan."),
    "so_dien_thoai": ("res.partner.mobile", "ALREADY MIGRATED (placeholder in sample)",
                      "YES — number unchanged; format standardised by normalize_vn_phone",
                      "Redaction-class: real numbers arrive with the unredacted export."),
    "so_dien_thoai_2": ("res.partner.phone (mobile already used for the primary number)",
                        "EXISTS — map only", "YES — value unchanged",
                        "Map the second phone to partner.phone (P1 candidate)."),
    "gui_xe": ("health.fieldservice.order.parking_charge (Monetary)", "ALREADY FIXED (P5.5)",
               "YES — value unchanged",
               "Done — field added, shown on the booking form, importer maps it; populates on the real export."),
    "Contact_nam_sinh": ("res.partner.birth_date", "ALREADY MIGRATED",
                         "YES — date kept; meaningless HH:MM prefix dropped (typed Date field)",
                         "No action."),
    "nghe_nghiep": ("res.partner.profession", "ALREADY MIGRATED", "YES — value unchanged", "No action."),
    "dan_toc": ("res.partner.ethnicity", "ALREADY FIXED (P5.5)",
                "YES — value unchanged (Char field stores the original VI string verbatim)",
                "DECISION: ethnicity is defined twice — Selection in health_base, overridden to Char by health_crm "
                "(live DB = Char). Char keeps the original VI text but cannot show an EN variant. Recommend keeping "
                "Char for fidelity, or consolidating to ONE translatable design if EN display is required."),
    "Contact_gioi_tinh": ("res.partner.gender (Selection)", "ALREADY MIGRATED (partial)",
                          "YES — via bilingual label ('Nam'/'Male', 'Nữ'/'Female', 'Khác'/'Other')",
                          "Map the dropped values: 'Khác'→other, 'Không xác định'→prefer_not_to_say; relabel keys "
                          "to the legacy wording (see Lookup sheet)."),
    "Client ID": ("res.partner.legacy_client_code", "ALREADY MIGRATED",
                  "YES — value unchanged (upsert key)", "No action."),
    "ten_benh_nhan": ("res.partner.name", "ALREADY MIGRATED",
                      "YES — value unchanged (5-char redaction in this sample)",
                      "Redaction-class: real names arrive with the unredacted export."),
    "SourceofClient": ("res.partner.source_type (Selection) + source_details (Char, raw text verbatim)",
                       "EXISTS — map only (P1)",
                       "YES — raw string kept verbatim in source_details; selection label bilingual",
                       "Fix: importer currently drops it and hardcodes booking_source='phone' (841 rows)."),
    "Client_Type": ("Derive from booking history — or CREATE: res.partner.client_type (Selection)",
                    "CREATE field (optional)",
                    "YES — via bilingual label ('Mới'/'New', 'Cũ'/'Repeat') if created",
                    "DECISION: recommend deriving new/repeat from booking count post-load instead of storing a stale flag."),
    "lien_ket_benh_nhan": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                           "Pancake link column, empty in the export."),
    "trang_thai": ("health.fieldservice.order.state + stage_id (Selection — booking workflow)",
                   "ALREADY MIGRATED (P1 widens the map)",
                   "PARTLY — labels relabelable to legacy wording; 'Dời lịch'/'Lịch tiếp theo' have no workflow state",
                   "DECISION: relabel the state labels to legacy wording (note: changes wording app-wide, not only for "
                   "migrated rows). 'Dời lịch' → recommend map to confirmed + keep the original text in a note; adding "
                   "a new state touches every workflow guard."),
    "ly_do_huy": ("fso.cancellation_reason_id → health.booking.cancellation.reason (m2o, name translatable)",
                  "EXISTS — map only + CREATE ~9 reason records (P0/P2)",
                  "YES — original VI + EN stored as the record name and its vi_VN translation",
                  "Create the 9 legacy reasons with VI+EN names and link them on cancelled bookings; free text stays "
                  "in cancellation_notes."),
    "Contact_phong_kham": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                           "City-name variant; phong_kham_city is used instead."),
    "phong_kham_city": ("res.partner.catchment_province_id + primary_facility_id / fso.facility_id (m2o)",
                        "ALREADY MIGRATED",
                        "YES — m2o record names ('Hà Nội', 'TPHCM' — proper nouns, same in both languages)",
                        "health.catchment.province.name is not translatable — irrelevant for proper nouns; no action."),
    "phu_phi": ("health.fieldservice.order.travel_charge (Monetary)", "EXISTS — map only (P3)",
                "YES — value unchanged", "P3 financial recovery: 22 rows / 1.45M VND."),
    "nguoi_thuc_hien": ("LEAVE — bac_si_dieu_duong already carries the staff assignment",
                        "BY DESIGN — leave", "n/a",
                        "Duplicate of the staff column; recommend LEAVE."),
    "khoang_cach": ("fso.travel_distance (Float) — system also recomputes clinic_drive_distance_km by geocoding",
                    "EXISTS — map only (optional)", "YES — value unchanged if mapped",
                    "Recommend keeping the geocoded distance as truth; optionally store the legacy value in fso.travel_distance."),
    "Contact_FullAddress": ("res.partner.street (fallback when Contact_Address is empty)", "ALREADY MIGRATED",
                            "YES — value unchanged (truncated in this sample)",
                            "Redaction-class: resolves with the unredacted export."),
    "country": ("res.partner.country_id (m2o res.country — names translatable in core)",
                "EXISTS — map only (P4)", "YES — standard country record, bilingual display",
                "P4 structured VN address parser."),
    "province": ("res.partner.state_id (m2o res.country.state)", "EXISTS — map only (P4)",
                 "YES — record name (proper noun)", "P4 structured VN address parser."),
    "district": ("res.partner.district_id (m2o health.vietnamese.district)", "EXISTS — map only (P4)",
                 "YES — record name (proper noun)", "P4 structured VN address parser."),
    "commune": ("res.partner.ward_commune (Char)", "EXISTS — map only (P4)",
                "YES — value unchanged (Char stores the original string; proper noun)",
                "P4 structured VN address parser."),
    "Contact_Address": ("res.partner.street", "ALREADY MIGRATED",
                        "YES — value unchanged (truncated in this sample)",
                        "Redaction-class: resolves with the unredacted export."),
    "note": ("health.fieldservice.order.patient_notes (concatenated with mo_ta_tinh_trang)", "ALREADY MIGRATED",
             "YES — text kept verbatim (concatenated)",
             "No action; if the two notes must stay separate, CREATE a second notes field — recommend leave."),
    "Contact_customer_id": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                            "Pancake internal id; legacy_client_code is the migration key."),
    "phong_kham_Owner": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy owner metadata."),
    "loai_kham": ("health.medical.specialty (m2o, name translatable) — empty in this export",
                  "EXISTS — map only (real export)", "YES — record name with VI + EN translation",
                  "Map when the real export populates it; create the missing 'Khám ngoại (Surgery)' specialty."),
    "dich_vu": ("fso.appointment_type_id + sale.order.line + health.service.type / product.product (auto-created)",
                "ALREADY MIGRATED",
                "YES — service names kept verbatim as records (product/service names ARE translatable)",
                "Add vi_VN translations to the auto-created service records if bilingual service names are required."),
    "time_in": ("health.fieldservice.order.scheduled_datetime (time part)", "ALREADY MIGRATED",
                "YES — value unchanged", "No action."),
    "time_out": ("health.fieldservice.order.scheduled_duration", "ALREADY MIGRATED",
                 "YES — recoverable (stored as duration; end = start + duration)", "No action."),
    "TransferMoney": ("health.payment.transaction.amount", "ALREADY MIGRATED (P3 refines)",
                      "PARTLY — summed with Cash today; P3 splits into per-method transactions preserving each amount",
                      "P3: split mixed Cash+Transfer rows into two transactions."),
    "thanh_toan_truoc": ("health.payment.transaction (method 'prepaid') → feeds res.partner remaining_prepaid_value",
                         "EXISTS — map only (P3)", "YES — value unchanged",
                         "P3: model the prepayment as a prepaid transaction."),
    "Cash": ("health.payment.transaction.amount", "ALREADY MIGRATED (P3 refines)",
             "PARTLY — summed with TransferMoney today; P3 splits per method",
             "P3: split mixed rows."),
    "SubTotal": ("sale.order.line.price_unit (distributed) + order totals", "EXISTS — map only (P3)",
                 "YES — booking total preserved exactly (distributed across lines when multiple services)",
                 "P3: 924 rows / 703M VND — revenue is currently invisible at price 0."),
    "Discount": ("sale.order / sale.order.line discount", "EXISTS — map only (P3)",
                 "YES — value unchanged", "P3: 221 rows / 67M VND."),
    "thanh_toan": ("health.fieldservice.order.payment_status (Selection — EXISTS)", "EXISTS — map only",
                   "YES — via bilingual label ('Chưa thanh toán'/'Unpaid', 'Đã thanh toán'/'Paid')",
                   "NEW finding: fso.payment_status exists — map it (the v1 audit reported no target)."),
    "ModifiedBy": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy audit metadata."),
    "thoi_gian_bat_dau": ("Derive from earliest booking — or CREATE: res.partner.first_service_date (Date)",
                          "CREATE field (optional)", "YES — value unchanged if created",
                          "DECISION: recommend deriving from booking history post-load."),
    "bac_si_dieu_duong": ("fso.assigned_staff_ids → hr.employee (auto-stub)", "ALREADY MIGRATED",
                          "YES — staff names kept as employee records (role prefixes stripped by design)",
                          "No action; the 20 GREENLAB/DIAG lab-token rows are correctly left unassigned."),
    "tao_don": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Constant 'Tạo đơn' workflow flag."),
    "so_don_da_tao": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                      "Implicit — exactly one sale order per booking."),
    "dich_vu_don_vi_tinh": ("uom.uom (m2o, name translatable)", "CREATE 2 records (Ca, Chai) — conditional",
                            "YES — original VI + EN via the UoM name translation",
                            "P0: create only if the real export populates the unit column (empty in this sample)."),
    "GrandTotal": ("sale.order.amount_total (computed from lines after P3)", "EXISTS — computed",
                   "YES — reproduced by computation (0 in this export anyway)",
                   "P3 outcome; no direct write needed."),
    "TotalQuantity": ("sale.order.line.product_uom_qty", "EXISTS — map only (P3)",
                      "YES — value unchanged", "P3: today every line qty is hardcoded 1."),
    "hinh_thuc_thanh_toan": ("health.payment.transaction.payment_method (Selection)",
                             "ALREADY MIGRATED (P1 adds prepaid)",
                             "YES — via bilingual label ('Tiền mặt'/'Cash', 'Chuyển khoản ngân hàng'/'Bank Transfer', "
                             "'Trả từ TT trước'/'Paid from prepayment balance')",
                             "P1: map the 74 prepaid rows that fall to 'other'; relabel keys to the legacy wording."),
    "tra": ("health.fieldservice.order.payment_status (folds into it with thanh_toan)", "EXISTS — map only",
            "YES — folded into the payment_status value", "Fold the paid flag into the payment_status mapping."),
    "kanban_order": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy UI ordering."),
    "nguoi_phu_trach": ("LEAVE — or CREATE: fso.legacy_owner (Char)", "BY DESIGN — leave (CREATE optional)",
                        "YES — value unchanged if created",
                        "DECISION: person-in-charge is legacy ops metadata — recommend LEAVE."),
    "ModifiedOn": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy audit metadata."),
    "in_don": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
               "Print-count flag, empty in the export; e-invoicing is handled by the Red Invoice module."),
    "Owner": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy audit metadata."),
    "PancakeCustomer ID": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                           "Pancake internal id; legacy_client_code is the migration key."),
    "page_id": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                "YES — if bundled", "See the ad-ids decision (Contact_ad_id_tiktok row)."),
    "ad_id": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
              "YES — if bundled", "See the ad-ids decision."),
    "TimeEnd": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Duplicate/empty timing column (time_out is used)."),
    "TimeStart": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Duplicate/empty timing column (time_in is used)."),
    "mo_ta_tinh_trang": ("health.fieldservice.order.patient_notes (concatenated with note)", "ALREADY MIGRATED",
                         "YES — text kept verbatim (concatenated)", "No action."),
    "ad_id_fb": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                 "YES — if bundled", "See the ad-ids decision."),
    "conversation_id": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                        "YES — if bundled", "See the ad-ids decision."),
    "Facebook Link": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                      "YES — if bundled", "See the ad-ids decision."),
    "col": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Unknown/unnamed column."),
    "col_1": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Unknown/unnamed column."),
}

CONTACT = {
    "STT": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Row index only."),
    "ID": ("crm.lead.legacy_contact_guid", "ALREADY MIGRATED", "YES — value unchanged (upsert key)", "No action."),
    "ngay_dau_su_dung": ("Derive from history — or CREATE: crm.lead.first_service_date (Date)",
                         "CREATE field (optional)", "YES — value unchanged if created",
                         "DECISION: recommend LEAVE/derive — first-use date on a pre-patient lead is weak data."),
    "Name": ("crm.lead.name", "ALREADY MIGRATED", "YES — value unchanged (redacted in this sample)",
             "Redaction-class: real names arrive with the unredacted export."),
    "gioi_tinh": ("crm.lead.gender (Selection)", "ALREADY FIXED (P5.5)",
                  "YES — via bilingual label ('Nam'/'Male', 'Nữ'/'Female')",
                  "Done — 164 populated on the sample; relabel keys to the legacy wording (see Lookup sheet)."),
    "nam_sinh": ("crm.lead.birth_date (Date)", "ALREADY FIXED (P5.5)",
                 "YES — date kept; HH:MM prefix dropped (typed Date field)",
                 "Done — 119 populated on the sample."),
    "nguon_khach_hang": ("crm.lead.healthcare_lead_source (Selection) + source_id (m2o utm.source)",
                         "ALREADY MIGRATED (partial — P1 widens)",
                         "YES — via bilingual label; sub-sources verbatim as utm.source records "
                         "(utm.source.name NOT translatable — single language unless translate=True is added)",
                         "P1: widen the map (~100 leads empty today); see the Lead Source group on the Lookup sheet."),
    "phong_kham": ("crm.lead.facility_id (m2o health.facility — name translatable)", "EXISTS — map only",
                   "YES — record name with VI + EN translation",
                   "NEW finding: the lead has facility_id — map the clinic (the v1 audit reported no home)."),
    "customer_id": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Pancake internal id."),
    "ly_do_tu_choi": ("crm.lead.lost_reason_id (m2o crm.lost.reason — name translatable) + reason_if_rejected text",
                      "EXISTS — map only + CREATE ~8 reason records (P0/P2)",
                      "YES — original VI + EN stored as the record name and its vi_VN translation",
                      "Create the legacy reject reasons with VI+EN names and link them (134 contacts); "
                      "'Spam' routes to contact_status='spam'."),
    "Phone": ("crm.lead.phone", "ALREADY MIGRATED (placeholder in sample)",
              "YES — number unchanged; format standardised by normalize_vn_phone",
              "Redaction-class: resolves with the unredacted export."),
    "so_dien_thoai_2": ("CREATE: crm.lead.phone2 (Char) — the lead model has no second-phone field",
                        "CREATE field", "YES — value unchanged once created",
                        "DECISION: create a small Char field if the real export carries second numbers."),
    "NextContactAt": ("crm.lead.next_follow_up_date (Datetime — EXISTS)", "EXISTS — map only",
                      "YES — value unchanged",
                      "NEW finding: map it (optionally also create a mail.activity for open follow-ups)."),
    "so_cccd": ("crm.lead.national_id (Char)", "ALREADY FIXED (P5.5)", "YES — value unchanged",
                "Done — empty in the redacted sample; populates on the real export."),
    "ten_benh_nhan": ("crm.lead.contact_name (Char — EXISTS)", "EXISTS — map only",
                      "YES — value unchanged",
                      "NEW finding: core contact_name holds the patient name distinct from the lead name."),
    "khoang_cach": ("crm.lead.distance_from_clinic (Float — EXISTS)", "EXISTS — map only",
                    "YES — value unchanged", "Map it; the system re-computes distance after conversion anyway."),
    "dich_vu_quan_tam": ("crm.lead.service_interest (Selection) + description concat (current behaviour)",
                         "ALREADY MIGRATED (partial — concat only)",
                         "YES — via bilingual label once the selection is extended (8 new keys)",
                         "DECISION: extend the Selection with the 8 missing interests (labels = legacy VI/EN) — "
                         "recommended — or convert the field to a many2one lookup (see Lookup sheet)."),
    "loai_khach_hnagf": ("Derive from history — or CREATE: crm.lead.client_type (Selection)",
                         "CREATE field (optional)",
                         "YES — via bilingual label ('Mới'/'New', 'Cũ'/'Repeat') if created",
                         "DECISION: same as booking Client_Type — recommend derive post-load."),
    "ghi_chu": ("crm.lead.description (concatenated)", "ALREADY MIGRATED", "YES — text kept verbatim", "No action."),
    "Source": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Pancake inbox tag ('INBOX')."),
    "cskh_3": ("crm.lead.health_contact_outcome (Selection)", "EXISTS — map only (P2)",
               "YES — via bilingual label; 2 values need a new key or nearest-map "
               "('Không nghe máy', 'Tham khảo dịch vụ')",
               "P2: map the disposition (13 rows); see the CSKH group on the Lookup sheet."),
    "Untitled": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Unnamed legacy column."),
    "Untitled2": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Unnamed legacy column."),
    "phan_hoi_kh": ("crm.lead.follow_up_notes (Text — EXISTS)", "EXISTS — map only",
                    "YES — text kept verbatim",
                    "NEW finding: customer feedback → follow_up_notes (the v1 audit reported no home)."),
    "PancakeCustomer": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Pancake internal id."),
    "PancakeCustomer ID": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Pancake internal id."),
    "Address": ("crm.lead.street / street_address (EXISTS)", "EXISTS — map only (P4)",
                "YES — value unchanged (truncated in this sample)",
                "P4: the importer never writes a lead address today — wire it."),
    "Status": ("crm.lead.contact_status + stage_id (Selection — lead workflow)", "ALREADY MIGRATED",
               "PARTLY — matched statuses relabelable; 4 legacy statuses have no equivalent code "
               "('Đang suy nghĩ', 'Liên hệ lại', 'Đã sử dụng', 'Cũ')",
               "DECISION: extend contact_status with the 4 missing keys (display fidelity) or accept "
               "nearest-mapping — see the Service Status group on the Lookup sheet."),
    "Owner": ("LEAVE — or map to user_id where names match system users", "BY DESIGN — leave", "n/a",
              "Recommend LEAVE — legacy usernames do not match system users."),
    "pancake_tag": ("LEAVE — or CREATE crm.tag records from the Pancake tags", "BY DESIGN — leave (CREATE optional)",
                    "YES — tag names verbatim if created",
                    "DECISION: recommend LEAVE unless the tags carry business meaning."),
    "lien_ket_lich_hen": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Pancake link column."),
    "FullAddress": ("crm.lead.street (fallback when Address is empty)", "EXISTS — map only (P4)",
                    "YES — value unchanged", "P4: same fallback pattern as the booking side."),
    "Address_1": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Duplicate address column."),
    "country": ("crm.lead.country_id (m2o res.country — names translatable in core)", "EXISTS — map only (P4)",
                "YES — standard country record, bilingual display", "P4 address parser."),
    "province": ("crm.lead.state_id (m2o res.country.state)", "EXISTS — map only (P4)",
                 "YES — record name (proper noun)", "P4 address parser."),
    "district": ("crm.lead.district_id (m2o health.vietnamese.district — EXISTS)", "EXISTS — map only (P4)",
                 "YES — record name (proper noun)", "P4 address parser."),
    "commune": ("crm.lead.ward_commune (Char — EXISTS)", "EXISTS — map only (P4)",
                "YES — value unchanged (proper noun)", "P4 address parser."),
    "kanban_order": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy UI ordering."),
    "dich_vu_don_vi_tinh": ("uom.uom (m2o, name translatable)", "CREATE 2 records (Ca, Chai) — conditional",
                            "YES — original VI + EN via the UoM name translation",
                            "P0: create only if the real export populates the unit column."),
    "dich_vu_danh_muc": ("health.service.type.category (Selection)", "EXISTS — map only",
                         "YES — via bilingual label ('DỊCH VỤ ĐIỀU DƯỠNG'/'Nursing services', "
                         "'DỊCH VỤ BÁC SĨ'/'Doctor services')",
                         "Relabel the category keys to the legacy wording; DECISION on the foreigner sub-category "
                         "(see Lookup sheet)."),
    "CreatedOn": ("LEAVE — or CREATE: crm.lead.legacy_created_on (Datetime)", "BY DESIGN — leave (CREATE optional)",
                  "YES — value unchanged if created",
                  "Recommend LEAVE — system create_date reflects the migration date; legacy date is audit-only."),
    "dich_vu_RetailPrice": ("product.template.list_price — owned by the advanced_pricing importer",
                            "EXISTS — map only (pricing import)",
                            "YES — value unchanged",
                            "Product prices come from pricelistv4.xlsx via the pricing importer; the contact-level "
                            "copy is informational — recommend not double-writing."),
    "dich_vu": ("LEAVE — bookings carry the services", "BY DESIGN — leave", "n/a",
                "The booking-level dich_vu is the service truth; the contact copy is redundant."),
    "SubTotal": ("LEAVE — booking-level SubTotal is the P3 source", "BY DESIGN — leave", "n/a",
                 "Contact-level financials duplicate the booking data."),
    "Discount": ("LEAVE — booking-level Discount is the P3 source", "BY DESIGN — leave", "n/a",
                 "Contact-level financials duplicate the booking data."),
    "GrandTotal": ("LEAVE — booking-level totals are the P3 source", "BY DESIGN — leave", "n/a",
                   "Contact-level financials duplicate the booking data."),
    "CreatedBy": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy audit metadata."),
    "ModifiedOn": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy audit metadata."),
    "psid": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
             "YES — if bundled", "See the ad-ids decision on the Booking sheet."),
    "TotalQuantity": ("LEAVE — booking-level quantity is the P3 source", "BY DESIGN — leave", "n/a",
                      "Contact-level financials duplicate the booking data."),
    "Email": ("crm.lead.email_from (EXISTS)", "EXISTS — map only", "YES — value unchanged",
              "The importer never writes it (all empty in this sample) — wire it for the real export."),
    "ModifiedBy": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy audit metadata."),
    "page_id": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                "YES — if bundled", "See the ad-ids decision."),
    "LastContactUser": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a", "Legacy audit metadata."),
    "ad_id": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
              "YES — if bundled", "See the ad-ids decision."),
    "TransferMoney": ("LEAVE — booking-level payments are the truth", "BY DESIGN — leave", "n/a",
                      "Contact-level financials duplicate the booking data."),
    "Note": ("crm.lead.description (concatenated)", "ALREADY MIGRATED", "YES — text kept verbatim", "No action."),
    "Cash": ("LEAVE — booking-level payments are the truth", "BY DESIGN — leave", "n/a",
             "Contact-level financials duplicate the booking data."),
    "LastContactAt": ("LEAVE (recommended)", "BY DESIGN — leave", "n/a",
                      "Legacy audit metadata; follow-ups live in NextContactAt → next_follow_up_date."),
    "ad_id_tiktok": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                     "YES — if bundled", "See the ad-ids decision."),
    "ad_id_fb": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                 "YES — if bundled", "See the ad-ids decision."),
    "Facebook Link": ("LEAVE — or bundle into crm.lead.legacy_ad_ids (JSON)", "BY DESIGN — leave (CREATE optional)",
                      "YES — if bundled", "See the ad-ids decision."),
}

# ---------------------------------------------------------------------------
# Lookup-sheet design.  key = exact 'Lookup List' cell text -> group config.
# jmode: how col J is generated per row ('m2o' | 'sel' | 'dual' | 'none')
# ---------------------------------------------------------------------------

LOOKUP = {
    # --- Contact table --------------------------------------------------
    "Giới tính BN (Gender)": dict(
        ftype="Selection on res.partner.gender + crm.lead.gender",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="Keep Selection (4 keys). Relabel each key to the legacy wording (EN + vi_VN). "
            "DECISION for 'Không xác định': relabel prefer_not_to_say as 'Unspecified/Không xác định' "
            "(recommended) or add a 4th key 'unspecified'."),
    "Lý do từ chối (Rejection Reason)": dict(
        ftype="many2one → crm.lost.reason (via crm.lead.lost_reason_id)",
        bilingual="YES — record name translatable (verified live)", bok=True, jmode="m2o",
        rec="Use the many2one as designed: create the 12 legacy reasons as records with EN name + vi_VN "
            "translation — no schema change, full original-value fidelity. 'Spam' routes to "
            "contact_status='spam' instead of a reason record."),
    "Dịch vụ quan tâm (Service of Interest)": dict(
        ftype="Selection on crm.lead.service_interest",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="DECISION: (a) extend the Selection with the 8 missing keys, labels = legacy VI/EN — recommended, "
            "small change — or (b) convert the field to a many2one lookup model (fully data-driven, but a "
            "larger change: field swap + views + importer + any code reading the selection)."),
    "Loại khách hàng (Customer Type)": dict(
        ftype="(no target field today)", bilingual="—", bok=None, jmode="none",
        rec="DECISION: recommend deriving new/repeat from booking history post-load; create "
            "res.partner.client_type (Selection, bilingual labels) only if it must be user-editable."),
    "CSKH / Contact Disposition": dict(
        ftype="Selection on crm.lead.health_contact_outcome",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="Keep Selection. Relabel the 5 matched keys to the legacy wording. DECISION for "
            "'Không nghe máy' + 'Tham khảo dịch vụ': add 2 new keys (recommended for fidelity) or map to nearest."),
    "Service Status (Contact)": dict(
        ftype="Selection on crm.lead.contact_status (+ stage_id) — drives the lead workflow",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="MUST stay Selection (workflow-bearing — display fidelity via labels only). Relabel matched keys. "
            "DECISION for the 4 unmatched legacy statuses ('Đang suy nghĩ', 'Liên hệ lại', 'Đã sử dụng', 'Cũ'): "
            "add keys for display fidelity, or map to nearest and keep the original text in a note."),
    "Đơn vị tính (Unit of Measure)": dict(
        ftype="many2one → uom.uom",
        bilingual="YES — record name translatable (verified live)", bok=True, jmode="m2o",
        rec="Create 'Ca (Shift)' and 'Chai (Bottle)' with EN name + vi_VN translation; add vi_VN translations "
            "to the existing Hours/Units/Km records so both languages display the legacy wording."),
    "Nguồn Khách Hàng (Lead Source)": dict(
        ftype="Selection on crm.lead.healthcare_lead_source + many2one → utm.source (source_id)",
        bilingual="Selection labels YES; utm.source.name NOT translatable (single language)", bok=False, jmode="dual",
        rec="DECISION (recommended): keep the Selection for the broad categories and relabel to legacy wording; "
            "create utm.source records verbatim (VI text as the name) for every sub-source (TikTok, VAFC, partners, "
            "schools, named referrers). If bilingual utm names are required, add translate=True to utm.source.name "
            "(small custom change). Named individual referrers could instead link res.partner referrer records."),
    "Contact_dich_vu_danh_muc (Service Category)": dict(
        ftype="Selection on health.service.type.category",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="Keep Selection; relabel 'nursing_care' → 'DỊCH VỤ ĐIỀU DƯỠNG/Nursing services' and 'consultation' → "
            "'DỊCH VỤ BÁC SĨ/Doctor services'. DECISION: the foreigner sub-category — add a key or model it as a "
            "pricing tier (recommended)."),
    "loai_kham (Visit Type)": dict(
        ftype="many2one → health.medical.specialty",
        bilingual="YES — record name translatable (verified live)", bok=True, jmode="m2o",
        rec="Create the missing 'Khám ngoại (Surgery)' specialty with EN name + vi_VN translation; ensure the "
            "existing Internal Medicine record carries its vi_VN translation."),
    # --- Booking table --------------------------------------------------
    "Trạng thái lịch hẹn (Booking Status)": dict(
        ftype="Selection on health.fieldservice.order.state (+ stage_id m2o) — the booking state machine",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="MUST stay Selection — the state machine drives PWA/EVV/invoicing logic; display fidelity via labels "
            "only. Relabel: confirmed → 'Đặt chỗ mới/New Booking', in_progress → 'Đang tiến hành/In Progress', "
            "completed → 'Đã hoàn thành/Completed', cancelled → 'Hủy/Cancelled'. NOTE: relabelling changes the "
            "wording app-wide, not just for migrated rows. DECISION: 'Dời lịch' and 'Lịch tiếp theo' have no "
            "state — recommend map to confirmed + keep the original value in a note; adding new states touches "
            "every workflow guard."),
    "Dịch vụ tại (Service Location)": dict(
        ftype="Selection on health.fieldservice.order.service_location",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="Keep Selection (3 keys map 1:1). Relabel to the legacy wording; P1 fixes the importer hardcode "
            "(21 clinic rows currently wrong)."),
    "Lý do hủy (Cancellation Reason)": dict(
        ftype="many2one → health.booking.cancellation.reason (via fso.cancellation_reason_id)",
        bilingual="YES — record name translatable (verified live)", bok=True, jmode="m2o",
        rec="Use the many2one as designed: create the 9 legacy reasons as records with EN name + vi_VN "
            "translation and link them on cancelled bookings (P0 + P2). Full original-value fidelity, no schema change."),
    "City": dict(
        ftype="many2one → health.catchment.province",
        bilingual="NO — record name not translatable (proper nouns, so effectively irrelevant)", bok=None, jmode="m2o_noop",
        rec="'Hà Nội' / 'TPHCM' are proper nouns — identical in both languages; no change needed."),
    "Thanh toán (Payment Status)": dict(
        ftype="Selection on health.fieldservice.order.payment_status (also account.move.payment_state)",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="NEW finding: fso.payment_status exists — map thanh_toan/tra onto it and relabel the keys to the "
            "legacy wording ('Chưa thanh toán', 'Đã thanh toán', 'Thanh toán một phần')."),
    "Method of Payment": dict(
        ftype="Selection on health.payment.transaction.payment_method",
        bilingual="YES — selection labels translatable per language", bok=True, jmode="sel",
        rec="Keep Selection (all 4 legacy values have keys — 'prepaid' exists). P1 maps the 74 prepaid rows; "
            "relabel keys to the legacy wording ('Trả từ TT trước' etc.)."),
    "In đơn (Invoice Print)": dict(
        ftype="(no target field today)", bilingual="—", bok=None, jmode="none",
        rec="Recommend LEAVE — print-count has no concept in CareJioX; e-invoicing is handled by the Red "
            "Invoice module."),
    "Facility / Code": dict(
        ftype="many2one → health.facility (fso.facility_id / partner.primary_facility_id)",
        bilingual="YES — record name translatable (verified live)", bok=True, jmode="m2o",
        rec="Create the 6 official facilities (P0) with the legacy codes verbatim ('01_01_00' style) and "
            "names with vi_VN translations."),
}

# Per-row overrides for col J, keyed by (group, VI value prefix).
J_OVERRIDES = {
    ("Giới tính BN (Gender)", "Không xác định"):
        "Map to key prefer_not_to_say + relabel it EN 'Unspecified' / vi_VN 'Không xác định' "
        "(or add a dedicated key 'unspecified')",
    ("Lý do từ chối (Rejection Reason)", "Spam"):
        "Route to contact_status='spam' — a status, not a lost-reason record",
    ("Trạng thái lịch hẹn (Booking Status)", "Dời lịch"):
        "IMPOSSIBLE as a stored state — no reschedule state exists; map to 'confirmed' and keep 'Dời lịch' "
        "in a note (or DECISION: add a new state — high workflow impact)",
    ("Trạng thái lịch hẹn (Booking Status)", "Lịch tiếp theo"):
        "IMPOSSIBLE as a stored state — map to 'confirmed' and keep the original text in a note",
    ("Nguồn Khách Hàng (Lead Source)", "Hanoi / HCMC"):
        "City is a catchment, not a source — DECISION: drop as source (recommended); city already lands in "
        "catchment_province_id",
    ("Loại khách hàng (Customer Type)", "Mới"):
        "Derive post-load from booking count (recommended) or CREATE res.partner.client_type",
    ("Loại khách hàng (Customer Type)", "Cũ"):
        "Derive post-load from booking count (recommended) or CREATE res.partner.client_type",
    ("In đơn (Invoice Print)", "In đơn lần 1"): "LEAVE (recommended) — no print-count concept",
    ("In đơn (Invoice Print)", "In đơn cuối cùng"): "LEAVE (recommended) — no print-count concept",
}


def j_for_row(group, cfg, vi, en, status, match):
    ov = J_OVERRIDES.get((group, vi))
    if ov:
        return ov
    jm = cfg["jmode"]
    if jm == "m2o_noop":
        return "Proper noun — identical in both languages; no action"
    if jm == "none":
        return "No target field — see recommendation"
    if jm == "m2o":
        if status.startswith("EXISTS"):
            return f"Ensure vi_VN translation '{vi}' on the existing record ({match})"
        return f"Create record: name EN '{en}', vi_VN translation '{vi}'"
    if jm == "dual":
        if status.startswith("EXISTS"):
            return (f"Relabel selection key {match}: EN '{en}', vi_VN '{vi}'; ensure a matching utm.source "
                    f"record ('{vi}')")
        return f"Create utm.source record '{vi}' (single-language name); optionally add a selection key"
    # selection
    if status.startswith("EXISTS"):
        return f"Relabel key {match}: EN '{en}', vi_VN '{vi}'"
    if status.startswith("CREATE"):
        return f"Add selection key (labels EN '{en}' / vi_VN '{vi}') OR convert the field to many2one"
    return f"DECISION — map to nearest ({match or 'see note'}) or add a key; labels EN '{en}' / vi_VN '{vi}'"


def fill_for_gap(gap):
    if gap.startswith(("ALREADY", "EXISTS")):
        return GREEN
    if gap.startswith("CREATE"):
        return ORANGE
    return GREY


def fill_for_kept(kept):
    if kept.startswith("YES"):
        return GREEN
    if kept.startswith("PARTLY"):
        return ORANGE
    if kept.startswith("NO"):
        return RED
    return GREY


def style_header(ws, col, text, ref_col):
    c = ws.cell(row=1, column=col, value=text)
    c._style = copy(ws.cell(row=1, column=ref_col)._style)


def do_mapping_sheet(ws, proposals):
    headers = ["Proposed Target", "Gap Resolution", "Original Value Kept?", "Recommendation / Decision"]
    for i, h in enumerate(headers):
        style_header(ws, 6 + i, h, 5)
    missing = []
    for r in range(2, ws.max_row + 1):
        key = ws.cell(row=r, column=1).value
        if key is None or str(key).strip() == "":
            continue
        key = str(key).strip()
        if key not in proposals:
            missing.append(key)
            continue
        target, gap, kept, rec = proposals[key]
        vals = [target, gap, kept, rec]
        gap_fill = fill_for_gap(gap)
        for i, v in enumerate(vals):
            c = ws.cell(row=r, column=6 + i, value=v)
            c.alignment = WRAP
            c.fill = fill_for_kept(kept) if i == 2 else gap_fill
    if missing:
        raise SystemExit(f"{ws.title}: no proposal for {missing}")
    for col, w in zip("FGHI", (46, 30, 46, 60)):
        ws.column_dimensions[col].width = w
    if ws.auto_filter.ref:
        ws.auto_filter.ref = f"A1:I{ws.max_row}"


def do_lookup_sheet(ws):
    headers = ["Field Type", "Bilingual Today?", "To Use Original Value", "Recommendation"]
    for i, h in enumerate(headers):
        style_header(ws, 8 + i, h, 7)
    group = None
    unknown = set()
    for r in range(2, ws.max_row + 1):
        a = ws.cell(row=r, column=1).value
        if a and str(a).strip():
            group = str(a).strip()
        vi = str(ws.cell(row=r, column=2).value or "").strip()
        if not vi:
            continue
        cfg = LOOKUP.get(group)
        if cfg is None:
            unknown.add(group)
            continue
        en = str(ws.cell(row=r, column=3).value or "").strip()
        status = str(ws.cell(row=r, column=5).value or "").strip()
        match = str(ws.cell(row=r, column=6).value or "").strip()
        for junk in (" EXISTS", " (used", " (approx"):
            if junk in match:
                match = match.split(junk)[0].strip()
        j = j_for_row(group, cfg, vi, en, status, match)
        if cfg["bok"] is True:
            i_fill = GREEN
        elif cfg["bok"] is False:
            i_fill = RED
        else:
            i_fill = GREY
        if j.startswith("IMPOSSIBLE"):
            j_fill = RED
        elif status.startswith("EXISTS"):
            j_fill = GREEN
        elif status.startswith("CREATE"):
            j_fill = ORANGE
        else:
            j_fill = GREY
        for col, val, f in ((8, cfg["ftype"], None), (9, cfg["bilingual"], i_fill),
                            (10, j, j_fill), (11, cfg["rec"], None)):
            c = ws.cell(row=r, column=col, value=val)
            c.alignment = WRAP
            if f is not None:
                c.fill = f
    if unknown:
        raise SystemExit(f"{ws.title}: no design for groups {sorted(unknown)}")
    for col, w in zip("HIJK", (44, 34, 56, 70)):
        ws.column_dimensions[col].width = w
    if ws.auto_filter.ref:
        ws.auto_filter.ref = f"A1:K{ws.max_row}"


def do_summary(ws):
    def count(d, pred):
        return sum(1 for v in d.values() if pred(v[1]))
    n_exists = count(BOOKING, lambda g: g.startswith("EXISTS")) + count(CONTACT, lambda g: g.startswith("EXISTS"))
    n_already = count(BOOKING, lambda g: g.startswith("ALREADY")) + count(CONTACT, lambda g: g.startswith("ALREADY"))
    n_create = count(BOOKING, lambda g: g.startswith("CREATE")) + count(CONTACT, lambda g: g.startswith("CREATE"))
    n_leave = count(BOOKING, lambda g: g.startswith("BY DESIGN")) + count(CONTACT, lambda g: g.startswith("BY DESIGN"))
    n_dec = sum(1 for d in (BOOKING, CONTACT) for v in d.values() if "DECISION" in v[3])
    r = ws.max_row + 2
    bold = Font(bold=True)
    lines = [
        ("v2 ADDITIONS — gap resolution & lookup fidelity (generated by gen_audit_report_v2.py)", True),
        ("Decision locked: DISPLAY FIDELITY — stored values stay technical codes; the label a user sees equals the "
         "original legacy value, Vietnamese for vi-preference users, English for en-preference users. "
         "Both languages (en_US, vi_VN) are active in CareJioX.", False),
        ("New columns — Mapping sheets: F Proposed Target | G Gap Resolution | H Original Value Kept? | "
         "I Recommendation/Decision.  Lookup sheets: H Field Type | I Bilingual Today? | J To Use Original Value | "
         "K Recommendation.", False),
        ("Colour code: GREEN = home exists / already handled · ORANGE = create/extend needed · "
         "RED = impossible (reason given) · GREY = leave by design.", False),
        (f"Field mapping totals across both sheets: {n_already} already migrated/fixed · {n_exists} have an existing "
         f"home (map only) · {n_create} need a new field/record (mostly optional) · {n_leave} recommended leave "
         f"by design · {n_dec} rows carry an explicit DECISION for you.", False),
        ("Lookup design: many2one lookups (lost reason, cancellation reason, facility, service type, specialty, UoM, "
         "products) all have TRANSLATABLE names — original VI+EN values migrate as record name + vi_VN translation "
         "with no schema change. Selection fields keep their codes; labels are relabelled/extended to the legacy "
         "wording per language. Workflow-bearing selections (booking state, contact status) MUST stay selections.", False),
        ("Exceptions flagged: utm.source.name and health.catchment.province.name are NOT translatable "
         "(single-language names; translate=True would be a small custom change). res.partner.ethnicity is defined "
         "twice (Selection in health_base overridden to Char by health_crm — live DB is Char).", False),
        ("NOTE: relabelling a selection changes that wording app-wide (all records, not only migrated ones).", False),
    ]
    for text, is_bold in lines:
        c = ws.cell(row=r, column=1, value=text)
        c.alignment = WRAP
        if is_bold:
            c.font = bold
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        ws.row_dimensions[r].height = max(15, 14 * (len(text) // 95 + 1))
        r += 1


def main():
    wb = openpyxl.load_workbook(SRC)
    do_mapping_sheet(wb["Mapping - Booking"], BOOKING)
    do_mapping_sheet(wb["Mapping - Contact"], CONTACT)
    do_lookup_sheet(wb["Lookup - Contact Table"])
    do_lookup_sheet(wb["Lookup - Booking Table"])
    do_summary(wb["Summary"])
    wb.save(DST)
    print(f"Wrote {DST}")
    print(f"Booking proposals: {len(BOOKING)}  Contact proposals: {len(CONTACT)}  Lookup groups: {len(LOOKUP)}")


if __name__ == "__main__":
    main()
