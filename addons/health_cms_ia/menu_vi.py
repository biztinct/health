# -*- coding: utf-8 -*-
"""The left menu in Vietnamese — every area, tab and screen, from ONE table.

WHY A TABLE HERE AND NOT TWELVE `.po` FILES. The menu's rows are seeded by about
a dozen modules, most of them `noupdate="1"`, and M2 renamed and regrouped them
from this module's hook. A `.po` entry per seeding module would be twelve places
to keep in step with a menu that is decided in ONE place — this module — and a
`model:cms.sidebar.item,name:` occurrence only lands at that module's upgrade.
So the Vietnamese names are data, keyed by the row's fixed name (xml-id), and
written by `apply_names_vi` with `with_context(lang='vi_VN').write` from the
install hook and from the 19.0.1.1.0 migration (AR-3 E2).

WHAT IT NEVER TOUCHES. The English value (M2's), the xml-ids, the keys, the
order. Proper nouns stay as they are: Zalo, VoIP, BHYT, NEWS2, EMR, EVV, VAT,
Google Ads, CRM, Care Command, Viet Uc Care, AI.

TAB LABELS ARE SHORT ON PURPOSE. A root entry is drawn in the 60px tab column in
capitals (M1); the shell shrinks a long label and then cuts it with "…". So a
tab's Vietnamese is the shortest honest word — "Tổng quan", not "Bảng điều
khiển" — and the full meaning is carried by the screen itself. Measured on the
practice copy (AR-3 browser pass).

A ROW NOT ON THIS DATABASE IS SKIPPED, and a row whose Vietnamese already reads
what the table says is not written again — so a second run writes nothing.
"""

import logging

_logger = logging.getLogger(__name__)

LANG = 'vi_VN'

#: The rail — one entry per area.
SECTION_VI = {
    'health_cms_sidebar.section_home': 'Trang chủ',
    'health_cms_sidebar.section_crm': 'CRM',
    'health_cms_sidebar.section_ops': 'Vận hành',
    'health_cms_sidebar.section_finance': 'Tài chính',
    'health_cms_sidebar.section_clinical': 'Lâm sàng',
    'health_cms_sidebar.section_interop': 'Tuân thủ',
    'biz_bi_cms.section_analytics': 'Phân tích',
    'health_cms_sidebar.section_learn': 'Học tập',
    'health_cms_sidebar.section_admin': 'Cài đặt',
}

#: Tabs (root entries) and the screens inside them. Switched-off rows are
#: included, so a row somebody switches back on reads Vietnamese at once.
ITEM_VI = {
    # --------------------------------------------------------------- Home
    'health_cms_sidebar.item_home': 'Trang chủ',
    # ---------------------------------------------------------------- CRM
    'health_cms_sidebar.item_crm_dashboard': 'Tổng quan',
    'health_care_command.item_care_command': 'Care Command',
    'health_web_leads.item_campaign_review': 'Rà soát chiến dịch',
    'health_cms_ia.parent_crm_channels': 'Kênh',
    'health_care_command_channels.item_channel_center': 'Trung tâm kênh',
    'health_care_command_channels.item_contact_capture': 'Liên hệ chưa phân luồng',
    'health_access.item_crm_channel_audit': 'Nhật ký kênh',
    'health_access.item_crm_channel_messages': 'Tin nhắn kênh',
    'health_access.item_crm_watch_phrases': 'Cụm từ cần theo dõi',
    'health_care_command_voip.item_phone': 'Điện thoại',
    'health_care_command_voip.item_phone_calls': 'Cuộc gọi',
    'health_care_command_voip.item_phone_callbacks': 'Gọi lại',
    'health_care_command_voip.item_phone_recordings': 'Bản ghi âm',
    'health_care_command_voip.item_phone_records': 'Dữ liệu từ tổng đài',
    'health_cms_ia.parent_crm_contacts': 'Liên hệ',
    'health_cms_sidebar.item_crm_contacts': 'Tất cả liên hệ',
    'health_cms_coverage.item_crm_relationships': 'Mối quan hệ',
    'health_cms_sidebar.item_crm_activities': 'Hoạt động',
    'health_cms_coverage.item_crm_followup_calendar': 'Lịch theo dõi',
    'health_cms_ia.parent_crm_web': 'Web & quảng cáo',
    'health_web_leads.item_web_touchpoints': 'Điểm chạm web',
    'health_web_leads.item_lead_analysis': 'Phân tích khách tiềm năng',
    'health_google_ads.item_google_ads': 'Google Ads',
    'health_access.item_crm_zalo': 'Zalo',
    'health_access.item_crm_zalo_conversations': 'Hội thoại',
    'health_access.item_crm_zalo_messages': 'Tin nhắn',
    'health_access.item_crm_zalo_settings': 'Cài đặt Zalo',
    # --------------------------------------------------------- Operations
    'health_cms_sidebar.item_ops_dashboard': 'Tổng quan',
    'health_cms_sidebar.item_ops_bookings': 'Lịch hẹn',
    'health_cms_sidebar.item_ops_clients': 'Khách hàng',
    'health_cms_ia.parent_ops_schedule': 'Lịch làm việc',
    'health_cms_sidebar.item_ops_roster': 'Lịch nhân sự',
    'health_cms_sidebar.item_ops_staff_timeoff': 'Nghỉ phép',
    'health_cms_sidebar.item_ops_workload': 'Khối lượng công việc',
    'health_cms_sidebar.item_ops_staff': 'Nhân viên',
    'health_cms_sidebar.item_ops_staff_roster': 'Lịch phân ca',
    'health_cms_sidebar.item_ops_staff_schedules': 'Lịch làm việc',
    'health_cms_sidebar.item_ops_collections': 'Thu tiền',
    'health_cms_coverage.item_ops_family_messages': 'Hộp thư người nhà',
    'health_cms_coverage.item_ops_route_feasibility': 'Tuyến đường',
    'health_cms_ia.parent_ops_exceptions': 'Ngoại lệ',
    'health_access.item_ops_visit_offers': 'Ưu đãi lượt đầu',
    'health_access.item_ops_timecard_mismatches': 'Chấm công không khớp',
    'health_cms_coverage.item_ops_telehealth': 'Khám từ xa',
    'health_cms_coverage.item_ops_selfbooking': 'Lời mời tự đặt lịch',
    'health_cms_coverage.item_ops_family_links': 'Liên kết người nhà',
    'health_cms_ia.parent_ops_development': 'Phát triển',
    'health_access.item_ops_employee_development': 'Phát triển nhân viên',
    'health_access.item_ops_coaching': 'Huấn luyện',
    'health_access.item_ops_voice': 'Thoại',
    'health_access.item_ops_voice_calls': 'Tất cả cuộc gọi',
    'health_access.item_ops_voice_missed': 'Cuộc gọi nhỡ',
    'health_access.item_ops_voice_recordings': 'Bản ghi âm',
    'health_access.item_ops_voice_extensions': 'Máy nhánh',
    'health_access.item_ops_voice_sync': 'Đồng bộ lịch sử cuộc gọi',
    'health_access.item_ops_voice_config': 'Cài đặt thoại',
    # ------------------------------------------------------------ Finance
    'health_cms_sidebar.item_fin_dashboard': 'Tổng quan',
    'health_cms_sidebar.item_fin_invoices': 'Hóa đơn',
    'health_cms_ia.parent_fin_receivables': 'Phải thu',
    'health_cms_sidebar.item_fin_ar_dashboard': 'Tổng quan phải thu',
    'health_cms_sidebar.item_fin_ar_transactions': 'Giao dịch phải thu',
    'health_cms_sidebar.item_fin_overdue': 'Khách hàng quá hạn',
    'health_cms_sidebar.item_fin_ar_management': 'Quản lý công nợ phải thu',
    'health_cms_ia.parent_fin_payments': 'Thanh toán',
    'health_cms_sidebar.item_fin_payments': 'Tất cả thanh toán',
    'health_cms_sidebar.item_fin_ar_account_payment': 'Thanh toán tài khoản',
    'health_cms_sidebar.item_fin_ar_cash_transit': 'Tiền đang chuyển',
    'health_cms_sidebar.item_fin_ar_refund': 'Hoàn tiền / Ghi có',
    'health_cms_sidebar.item_fin_vat_log': 'Nhật ký VAT',
    'health_cms_coverage.item_fin_bhyt_claims': 'Hồ sơ BHYT',
    'health_cms_coverage.item_fin_service_packages': 'Gói dịch vụ',
    'health_cms_coverage.item_fin_red_invoice_log': 'Nhật ký hóa đơn đỏ',
    # ----------------------------------------------------------- Clinical
    'health_cms_sidebar.item_clin_vitals': 'Sinh hiệu & quan sát',
    'health_cms_sidebar.item_clin_vitals_thresholds': 'Ngưỡng',
    'health_cms_sidebar.item_clin_vitals_obs': 'Quan sát',
    'health_cms_clinical.item_clin_care_intel': 'Theo dõi sát',
    'health_cms_clinical.item_clin_worklist': 'Danh sách cần theo dõi',
    'health_cms_clinical.item_clin_alerts': 'Cảnh báo',
    'health_cms_clinical.item_clin_news2': 'NEWS2',
    'health_cms_sidebar.item_clin_careplan': 'Kế hoạch chăm sóc',
    'health_cms_sidebar.item_clin_emar': 'Thuốc',
    'health_cms_sidebar.item_clin_emar_orders': 'Y lệnh thuốc',
    'health_cms_sidebar.item_clin_emar_admin': 'Sổ thực hiện thuốc',
    'health_cms_sidebar.item_clin_forms': 'Biểu mẫu lâm sàng',
    'health_cms_sidebar.item_clin_forms_instances': 'Đánh giá',
    'health_cms_sidebar.item_clin_incidents': 'Sự cố',
    'health_cms_sidebar.item_clin_incidents_register': 'Sổ sự cố',
    'health_cms_sidebar.item_clin_incidents_actions': 'Hành động khắc phục',
    'health_cms_sidebar.item_clin_incidents_analysis': 'Phân tích',
    'health_cms_sidebar.item_clin_consents_expiring': 'Đồng thuận',
    'health_cms_sidebar.item_clin_consents': 'Đồng thuận',
    'health_cms_sidebar.item_clin_consents_all': 'Tất cả đồng thuận',
    'health_cms_coverage.item_clin_diagnoses': 'Chẩn đoán',
    'health_cms_ia.parent_clin_notes': 'Ghi chép',
    'health_cms_coverage.item_clin_unsigned_notes': 'Ghi chép chưa ký',
    'health_cms_coverage.item_clin_voice_notes': 'Ghi chép bằng giọng nói',
    'health_cms_coverage.item_clin_coding_review': 'Duyệt mã bệnh',
    'health_cms_coverage.item_clin_visit_tasks': 'Công việc theo lượt thăm',
    'health_cms_coverage.item_clin_patient_portal': 'Cổng bệnh nhân',
    # --------------------------------------------------------- Compliance
    'health_cms_sidebar.item_int_terminology': 'Thuật ngữ',
    'health_cms_sidebar.item_int_term_codes': 'Mã y tế',
    'health_cms_sidebar.item_int_term_systems': 'Hệ thống mã',
    'health_cms_sidebar.item_int_term_import': 'Nhập mã',
    'health_cms_ia.parent_int_emr': 'EMR (VN)',
    'health_cms_sidebar.item_int_emr_export': 'Xuất dữ liệu',
    'health_cms_sidebar.item_int_emr_readiness': 'Mức sẵn sàng',
    'health_cms_sidebar.item_int_messaging': 'Tin nhắn lượt thăm',
    'health_cms_sidebar.item_int_evv': 'Sự kiện EVV',
    # ---------------------------------------------------------- Analytics
    'biz_bi_cms.item_analytics_hub': 'Phân tích',
    'biz_bi_cms.item_analytics_explore': 'Khám phá',
    'biz_bi_cms.item_analytics_dashboards': 'Bảng số liệu',
    'biz_bi_cms.item_analytics_data': 'Dữ liệu',
    'biz_bi_cms.item_analytics_sources': 'Nguồn dữ liệu',
    'biz_bi_cms.item_analytics_datasets': 'Bộ dữ liệu',
    'biz_bi_cms.item_analytics_refresh': 'Lịch làm mới',
    'biz_bi_cms.item_analytics_pipelines': 'Luồng dữ liệu',
    'biz_bi_cms.item_analytics_model': 'Mô hình ngữ nghĩa',
    'biz_bi_cms.item_analytics_glossary': 'Bảng thuật ngữ',
    'biz_bi_cms.item_analytics_import': 'Nhập dữ liệu',
    'biz_bi_cms.item_analytics_settings': 'Cài đặt báo cáo',
    'biz_bi_cms.item_analytics_access_rules': 'Ai xem số liệu nào',
    'biz_bi_cms.item_analytics_ai': 'Nhà cung cấp AI',
    # -------------------------------------------------------------- Learn
    'health_learn.item_learn_journey': 'Đào tạo',
    'health_access.item_admin_training': 'Quản lý đào tạo',
    'health_access.item_admin_training_lessons': 'Bài học',
    'health_access.item_admin_training_stations': 'Trạm học',
    'health_access.item_admin_training_progress': 'Tiến độ học viên',
    'health_access.item_admin_training_events': 'Sự kiện học tập',
    'health_access.item_admin_training_wording': 'Từ ngữ đào tạo',
    # ----------------------------------------------------------- Settings
    'health_cms_sidebar.item_admin_dashboard': 'Tổng quan',
    'health_cms_ia.parent_admin_people': 'Nhân sự',
    'health_cms_sidebar.item_admin_users': 'Người dùng & vai trò',
    'health_access.item_admin_access': 'Quyền truy cập & vai trò',
    'health_cms_sidebar.item_admin_staff': 'Nhân viên y tế',
    'health_cms_ia.parent_admin_master': 'Danh mục',
    'health_cms_sidebar.item_admin_master_data': 'Cơ sở',
    'health_cms_sidebar.item_admin_pricing': 'Bảng giá',
    'health_cms_sidebar.item_admin_equipment': 'Thiết bị',
    'health_cms_sidebar.item_admin_holidays': 'Ngày nghỉ lễ',
    'health_cms_sidebar.item_clin_vitals_types': 'Loại quan sát',
    'health_cms_sidebar.item_clin_emar_catalog': 'Danh mục thuốc',
    'health_cms_sidebar.item_clin_forms_templates': 'Mẫu biểu',
    'health_cms_clinical.item_clin_devices': 'Thiết bị theo dõi',
    'health_cms_sidebar.item_admin_field_req': 'Trường bắt buộc',
    'health_cms_ia.parent_admin_connections': 'Kết nối',
    'health_cms_coverage.item_crm_channels_setup': 'Thiết lập kênh',
    'health_cms_coverage.item_crm_reply_templates': 'Mẫu trả lời',
    'health_care_command_channels.item_golive_studio': 'Đưa kênh vào hoạt động',
    'health_web_leads.item_web_leads_connector': 'Kết nối website',
    'health_google_ads.item_google_ads_platform': 'Ứng dụng Google Ads',
    'health_care_command_voip.item_phone_settings': 'Tổng đài điện thoại',
    'health_care_command_voip.item_phone_extensions': 'Máy nhánh',
    'health_cms_ia.parent_admin_records': 'Hồ sơ',
    'health_cms_sidebar.item_admin_audit': 'Nhật ký kiểm tra',
    'health_cms_sidebar.item_admin_data_lifecycle': 'Vòng đời dữ liệu',
    'health_cms_coverage.item_clin_consent_log': 'Nhật ký kiểm tra đồng thuận',
    'health_cms_sidebar.item_admin_cms_sidebar': 'Menu',
    'health_cms_sidebar.item_admin_settings': 'Cài đặt',
    'health_tenancy.item_admin_about': 'Giới thiệu',
    'health_tenancy.item_admin_customers': 'Khách hàng nền tảng',
    'health_tenancy.item_feature_off_shell': 'Chưa bật',
}

#: The words a Vietnamese label may keep in English — proper nouns and the
#: product's own names. `test_ar3` asserts a vi_VN user's menu carries nothing
#: English outside these.
PROPER_NOUNS = ('Zalo', 'VoIP', 'BHYT', 'NEWS2', 'EMR', 'EVV', 'VAT',
                'Google Ads', 'CRM', 'Care Command', 'Viet Uc Care', 'AI',
                'Menu', 'Web', '(VN)')


def _lang_active(env):
    return bool(env['res.lang'].sudo().search_count(
        [('code', '=', LANG), ('active', '=', True)]))


def apply_names_vi(env, log=None):
    """Write every Vietnamese name in the tables above. Idempotent.

    Returns the number of rows written. Nothing is written when Vietnamese is
    not active on this database — the name would be unreachable, and
    `res.lang` activation is a decision for whoever runs the database.
    """
    log = log if log is not None else {}
    rows = log.setdefault('names_vi', [])
    if not _lang_active(env):
        _logger.info('health_cms_ia: %s is not active here; the menu keeps '
                     'its English names only', LANG)
        return 0
    written = 0
    for table, model in ((SECTION_VI, 'cms.sidebar.section'),
                         (ITEM_VI, 'cms.sidebar.item')):
        for xmlid, name in table.items():
            record = env.ref(xmlid, raise_if_not_found=False)
            if not record or record._name != model:
                continue
            record = record.sudo().with_context(lang=LANG, active_test=False)
            if record.name == name:
                continue
            record.write({'name': name})
            rows.append('%s: %s' % (xmlid, name))
            written += 1
    _logger.info('health_cms_ia: %s menu name(s) written in Vietnamese', written)
    return written
