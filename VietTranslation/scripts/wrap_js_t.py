#!/usr/bin/env python3
"""
Odoo JS i18n Wrapper — Adds _t() to hardcoded English strings in JS files.

This script:
1. Scans JS files for hardcoded English strings
2. Adds `import { _t } from "@web/core/l10n/translation"` if missing
3. Wraps user-facing strings in _t()
4. Outputs the strings for adding to .po files

Usage:
    python3 wrap_js_t.py                  # Wrap all target JS files
    python3 wrap_js_t.py --dry-run        # Preview without modifying
"""
import argparse
import os
import re
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Map of JS file paths (relative) to strings that should be wrapped in _t()
# Only includes user-visible UI strings, not debug/console/internal strings
JS_TRANSLATIONS = {
    'addons/health_base/static/src/components/relationship_hierarchy/relationship_hierarchy.js': {
        "'Remove Relationship'": "_t('Remove Relationship')",
    },
    'addons/health_crm/static/src/components/relationship_hierarchy/relationship_hierarchy.js': {
        "'Remove Relationship'": "_t('Remove Relationship')",
    },
    'addons/health_care_command_channels/static/src/golive/golive_studio.js': {
        '"Calls (VoIP24h)"': '_t("Calls (VoIP24h)")',
    },
    'addons/health_crm/static/src/js/relationship_graph_widget.js': {
        "'Caregiver'": "_t('Caregiver')",
        "'Payer'": "_t('Payer')",
        "'Referrer'": "_t('Referrer')",
        "'Emergency'": "_t('Emergency')",
        "'Legal Guardian'": "_t('Legal Guardian')",
    },
    'addons/health_crm/static/src/js/crm_new_contact.js': {
        f'"{text}"': f'_t("{text}")' for text in (
            'Phone Call', 'Zalo', 'Facebook', 'Email', 'Website', 'Chatbox',
            'Walk-in', 'Client (Self)', 'Payer', 'Referrer',
            'Emergency Contact', 'Legal Guardian', 'Client Representative',
            'Home Visit', 'Clinic Visit', 'Consultation', 'Follow-up',
            'Emergency', 'Preventive', 'Rehabilitation', 'Palliative',
            'Routine', 'Urgent', 'To-Do', 'Call', 'Meeting', 'Reminder',
            'New Booking', 'Escalate', 'Send Message', 'Log Activity',
            'Add Notes', 'Mark Spam', 'Open Record',
        )
    },
    'addons/health_fieldservice/static/src/js/ops_booking_wizard.js': {
        **{f"'{text}'": f"_t('{text}')" for text in (
            'Home Visit', 'Clinic Visit', 'Consultation', 'Follow-up',
            'Emergency', 'Telemedicine', 'Preventive Care', 'Rehabilitation',
            'Half day (4 hours)', 'Full day (8 hours)', 'Low', 'Normal',
            'High', 'Urgent', 'One Time',
        )},
        "'Staff travels to client\\'s location'":
            '_t("Staff travels to client\'s location")',
        "'Client visits our facility'": "_t('Client visits our facility')",
        "'Video or phone consultation'": "_t('Video or phone consultation')",
        "'Post-visit check-in'": "_t('Post-visit check-in')",
        "'Urgent medical response'": "_t('Urgent medical response')",
        "'Online/remote consultation'": "_t('Online/remote consultation')",
        "'Routine health checkup'": "_t('Routine health checkup')",
        "'Physical therapy sessions'": "_t('Physical therapy sessions')",
    },
    'addons/health_landing/static/src/js/admin_dashboard.js': {
        f'"{text}"': f'_t("{text}")'
        for text in ('Today', 'This Week', 'This Month', 'All Dates', 'Custom')
    },
    'addons/health_pwa/static/src/js/app.js': {
        f"'{text}'": f"_t('{text}')" for text in (
            'Patient died', 'Patient improved/recovered',
            'Patient admitted to hospital', 'Patient declined further visits',
            'Patient moved/relocated', 'Referred to another provider', 'Other',
            'Debug info logged to console. Check browser console.',
            'Failed to get debug info: ',
        )
    },
    'addons/health_theme/static/src/js/vu_side_sheet.js': {
        '"Details"': '_t("Details")',
    },
    'addons/health_theme/static/src/studio/theme_studio_action.js': {
        f'"{text}"': f'_t("{text}")' for text in (
            'Brand', 'Surfaces', 'Text', 'Borders', 'Status colors',
            'Workflow states', 'Navbar & Sidebar', 'Buttons',
            'Status bar & Tabs', 'Publish theme',
        )
    },
    'addons/health_zalo/static/src/js/zalo_bus_service.js': {
        '"Zalo Message"': '_t("Zalo Message")',
    },
    'pb_hr_workforce/static/src/js/overtime_rules.js': {
        '"Weekday"': '_t("Weekday")',
        '"Extra hours on regular work days"': '_t("Extra hours on regular work days")',
        '"Weekend"': '_t("Weekend")',
        '"Holiday"': '_t("Holiday")',
        '"All hours on public holidays"': '_t("All hours on public holidays")',
        '"Night Shift"': '_t("Night Shift")',
        '"Hours within night time window"': '_t("Hours within night time window")',
        '"Extended"': '_t("Extended")',
        '"OT exceeding daily max cap"': '_t("OT exceeding daily max cap")',
        '"Every day"': '_t("Every day")',
        '"No days selected"': '_t("No days selected")',
        '"Please enter a rule name"': '_t("Please enter a rule name")',
        '"Rule updated"': '_t("Rule updated")',
        '"Rule created"': '_t("Rule created")',
        '"Rule deleted"': '_t("Rule deleted")',
    },
    'pb_hr_workforce/static/src/js/shift_planning_grid.js': {
        '"Copy shifts to next week"': '_t("Copy shifts to next week")',
        '"Shift conflict detected"': '_t("Shift conflict detected")',
        '"Failed to load shift grid"': '_t("Failed to load shift grid")',
        '"Employee is on leave this day"': '_t("Employee is on leave this day")',
        '"Shift created"': '_t("Shift created")',
        '"Failed to create shift"': '_t("Failed to create shift")',
        '"Shift deleted"': '_t("Shift deleted")',
        '"Cannot delete this shift"': '_t("Cannot delete this shift")',
        '"Publish failed"': '_t("Publish failed")',
        '"Copy failed"': '_t("Copy failed")',
    },
    'pb_hr_workforce/static/src/js/attendance_live.js': {
        '"Attendance data refreshed"': '_t("Attendance data refreshed")',
    },
    'pb_hr_workforce/static/src/js/attendance_timecard.js': {
        '"With hours only"': '_t("With hours only")',
    },
    'pb_hr_workforce/static/src/js/workforce_dashboard.js': {
        '"Total Hours"': '_t("Total Hours")',
        '"OT Hours"': '_t("OT Hours")',
    },
    'pb_hr_workforce/static/src/js/payroll_report.js': {
        '"Failed to load payroll report"': '_t("Failed to load payroll report")',
    },
    'payroll_analytics_approval/static/src/js/payroll_charts_v19.js': {
        '"Current"': '_t("Current")',
        '"Previous"': '_t("Previous")',
        '"Alert"': '_t("Alert")',
        '"Warning"': '_t("Warning")',
        '"Normal"': '_t("Normal")',
        '"Review all components carefully before approval"': '_t("Review all components carefully before approval")',
        '"No critical issues detected"': '_t("No critical issues detected")',
    },
    'pb_hr_payroll_base/static/src/js/payroll_dashboard_enhanced.js': {
        '"Access Dashboard"': '_t("Access Dashboard")',
        '"Request Access"': '_t("Request Access")',
        '"Total Payroll"': '_t("Total Payroll")',
    },
    'pb_hr_payroll_base/static/src/js/control_panel_home_icon.js': {
        '"Open HR Flow Dashboard"': '_t("Open HR Flow Dashboard")',
    },
    'pb_hr_payroll_formula/static/src/js/cell_editor.js': {
        '"Invalid number"': '_t("Invalid number")',
        '"Unbalanced parentheses"': '_t("Unbalanced parentheses")',
    },
}

# Vietnamese translations for the JS strings (for .po file generation)
VI_TRANSLATIONS = {
    "Remove Relationship": "Xóa mối quan hệ",
    "Calls (VoIP24h)": "Cuộc gọi (VoIP24h)",
    "Caregiver": "Người chăm sóc",
    "Payer": "Người thanh toán",
    "Referrer": "Người giới thiệu",
    "Emergency": "Khẩn cấp",
    "Legal Guardian": "Người giám hộ hợp pháp",
    "Phone Call": "Cuộc gọi điện thoại",
    "Zalo": "Zalo",
    "Facebook": "Facebook",
    "Email": "Email",
    "Website": "Trang web",
    "Chatbox": "Hộp trò chuyện",
    "Walk-in": "Khách đến trực tiếp",
    "Client (Self)": "Khách hàng (Bản thân)",
    "Emergency Contact": "Liên hệ khẩn cấp",
    "Client Representative": "Người đại diện khách hàng",
    "Home Visit": "Thăm khám tại nhà",
    "Clinic Visit": "Thăm khám tại phòng khám",
    "Consultation": "Tư vấn",
    "Follow-up": "Theo dõi",
    "Preventive": "Phòng ngừa",
    "Rehabilitation": "Phục hồi chức năng",
    "Palliative": "Chăm sóc giảm nhẹ",
    "Routine": "Thông thường",
    "Urgent": "Khẩn cấp",
    "To-Do": "Việc cần làm",
    "Call": "Gọi điện",
    "Meeting": "Cuộc họp",
    "Reminder": "Nhắc nhở",
    "New Booking": "Đặt lịch mới",
    "Escalate": "Chuyển cấp xử lý",
    "Send Message": "Gửi tin nhắn",
    "Log Activity": "Ghi nhận hoạt động",
    "Add Notes": "Thêm ghi chú",
    "Mark Spam": "Đánh dấu thư rác",
    "Open Record": "Mở bản ghi",
    "Telemedicine": "Khám chữa bệnh từ xa",
    "Preventive Care": "Chăm sóc phòng ngừa",
    "Half day (4 hours)": "Nửa ngày (4 giờ)",
    "Full day (8 hours)": "Cả ngày (8 giờ)",
    "Low": "Thấp",
    "Normal": "Bình thường",
    "High": "Cao",
    "One Time": "Một lần",
    "Staff travels to client's location": "Nhân viên đến địa điểm của khách hàng",
    "Client visits our facility": "Khách hàng đến cơ sở của chúng tôi",
    "Video or phone consultation": "Tư vấn qua video hoặc điện thoại",
    "Post-visit check-in": "Theo dõi sau lượt thăm",
    "Urgent medical response": "Đáp ứng y tế khẩn cấp",
    "Online/remote consultation": "Tư vấn trực tuyến/từ xa",
    "Routine health checkup": "Khám sức khỏe định kỳ",
    "Physical therapy sessions": "Các buổi vật lý trị liệu",
    "Today": "Hôm nay",
    "This Week": "Tuần này",
    "This Month": "Tháng này",
    "All Dates": "Tất cả ngày",
    "Custom": "Tùy chỉnh",
    "Patient died": "Bệnh nhân đã qua đời",
    "Patient improved/recovered": "Bệnh nhân đã cải thiện/hồi phục",
    "Patient admitted to hospital": "Bệnh nhân đã nhập viện",
    "Patient declined further visits": "Bệnh nhân từ chối các lượt thăm tiếp theo",
    "Patient moved/relocated": "Bệnh nhân đã chuyển nơi ở",
    "Referred to another provider": "Đã chuyển đến nhà cung cấp khác",
    "Other": "Khác",
    "Debug info logged to console. Check browser console.":
        "Thông tin gỡ lỗi đã được ghi vào bảng điều khiển trình duyệt.",
    "Failed to get debug info: ": "Không thể lấy thông tin gỡ lỗi: ",
    "The video room is not ready yet.": "Phòng video chưa sẵn sàng.",
    "Could not open the video room.": "Không thể mở phòng video.",
    "Recording needs a connection.": "Cần kết nối mạng để ghi âm.",
    "Recording is not supported on this device.":
        "Thiết bị này không hỗ trợ ghi âm.",
    "Please allow microphone access to record.":
        "Vui lòng cho phép truy cập micro để ghi âm.",
    "Could not start recording.": "Không thể bắt đầu ghi âm.",
    "Glove mode": "Chế độ găng tay",
    "Sunlight mode": "Chế độ ngoài trời",
    "Details": "Chi tiết",
    "Brand": "Thương hiệu",
    "Surfaces": "Bề mặt",
    "Text": "Văn bản",
    "Borders": "Đường viền",
    "Status colors": "Màu trạng thái",
    "Workflow states": "Trạng thái quy trình",
    "Navbar & Sidebar": "Thanh điều hướng và thanh bên",
    "Buttons": "Nút",
    "Status bar & Tabs": "Thanh trạng thái và thẻ",
    "Publish theme": "Xuất bản giao diện",
    "Zalo Message": "Tin nhắn Zalo",
    # pb_hr_workforce - Overtime Rules
    "Weekday": "Ngày thường",
    "Extra hours on regular work days": "Giờ làm thêm vào ngày thường",
    "Weekend": "Cuối tuần",
    "Holiday": "Ngày lễ",
    "All hours on public holidays": "Tất cả giờ vào ngày lễ",
    "Night Shift": "Ca đêm",
    "Hours within night time window": "Giờ trong khung thời gian đêm",
    "Extended": "Kéo dài",
    "OT exceeding daily max cap": "Tăng ca vượt mức tối đa trong ngày",
    "Every day": "Mỗi ngày",
    "No days selected": "Chưa chọn ngày",
    "Please enter a rule name": "Vui lòng nhập tên quy tắc",
    "Rule updated": "Đã cập nhật quy tắc",
    "Rule created": "Đã tạo quy tắc",
    "Rule deleted": "Đã xóa quy tắc",
    # pb_hr_workforce - Shift Planning
    "Copy shifts to next week": "Sao chép ca sang tuần sau",
    "Shift conflict detected": "Phát hiện trùng ca",
    "Failed to load shift grid": "Không thể tải lưới ca",
    "Employee is on leave this day": "Nhân viên nghỉ phép ngày này",
    "Shift created": "Đã tạo ca",
    "Failed to create shift": "Không thể tạo ca",
    "Shift deleted": "Đã xóa ca",
    "Cannot delete this shift": "Không thể xóa ca này",
    "Publish failed": "Xuất bản thất bại",
    "Copy failed": "Sao chép thất bại",
    # pb_hr_workforce - Attendance & Dashboard
    "Attendance data refreshed": "Đã làm mới dữ liệu chấm công",
    "With hours only": "Chỉ hiển thị giờ",
    "Total Hours": "Tổng giờ",
    "OT Hours": "Giờ tăng ca",
    "Failed to load payroll report": "Không thể tải báo cáo lương",
    # payroll_analytics_approval - Charts
    "Current": "Hiện tại",
    "Previous": "Kỳ trước",
    "Alert": "Cảnh báo",
    "Warning": "Cảnh báo",
    "Normal": "Bình thường",
    "Review all components carefully before approval": "Xem xét kỹ tất cả thành phần trước khi phê duyệt",
    "No critical issues detected": "Không phát hiện vấn đề nghiêm trọng",
    # pb_hr_payroll_base - Dashboard
    "Access Dashboard": "Truy cập bảng điều khiển",
    "Request Access": "Yêu cầu quyền truy cập",
    "Total Payroll": "Tổng bảng lương",
    "Open HR Flow Dashboard": "Mở bảng điều khiển HR Flow",
    # pb_hr_payroll_formula - Cell Editor
    "Invalid number": "Số không hợp lệ",
    "Unbalanced parentheses": "Dấu ngoặc không cân bằng",
}

T_IMPORT_LINE = 'import { _t } from "@web/core/l10n/translation";'


def process_js_file(filepath, replacements, dry_run=False, backup=True):
    """Process a single JS file: add _t import and wrap strings."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    modified_count = 0

    # Apply string replacements
    for old, new in replacements.items():
        if old in content:
            # Be careful not to replace already-wrapped strings
            # Check if the string is already inside _t()
            pattern = re.escape(old)
            # Only replace if NOT preceded by _t(
            occurrences = [(m.start(), m.end()) for m in re.finditer(pattern, content)]
            for start, end in reversed(occurrences):
                before = content[max(0, start-3):start]
                if '_t(' not in before:
                    content = content[:start] + new + content[end:]
                    modified_count += 1

    # Add _t import if we modified anything and it's not already imported
    if modified_count > 0 and '_t' not in original:
        if '/** @odoo-module **/' in content:
            content = content.replace(
                '/** @odoo-module **/',
                f'/** @odoo-module **/\n{T_IMPORT_LINE}',
                1
            )
        else:
            content = T_IMPORT_LINE + '\n' + content

    if content != original and not dry_run:
        if backup:
            shutil.copy2(filepath, filepath + '.bak')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return modified_count


def generate_po_entries(translations):
    """Generate PO-format entries for new JS strings."""
    lines = []
    lines.append("")
    lines.append("# === JavaScript UI Strings ===")
    for en, vi in sorted(translations.items()):
        lines.append(f'')
        lines.append(f'#. JS Dashboard/UI String')
        lines.append(f'msgid "{en}"')
        lines.append(f'msgstr "{vi}"')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Wrap JS strings in _t()')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--no-backup', action='store_true')
    parser.add_argument('--generate-po', action='store_true',
                        help='Generate PO entries for new strings')
    args = parser.parse_args()

    print("=" * 60)
    print("  Odoo JS i18n Wrapper")
    print("=" * 60)

    total = 0
    for rel_path, replacements in JS_TRANSLATIONS.items():
        filepath = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(filepath):
            print(f"  ⚠️  Not found: {rel_path}")
            continue

        count = process_js_file(
            filepath,
            replacements,
            dry_run=args.dry_run,
            backup=not args.no_backup,
        )
        if count > 0:
            print(f"  ✅ {rel_path}: {count} strings wrapped")
        else:
            print(f"  ⏭️  {rel_path}: no changes needed")
        total += count

    print()
    print(f"  Total: {total} strings wrapped in _t()")
    if args.dry_run:
        print("  (DRY RUN — no files modified)")
    print("=" * 60)

    if args.generate_po:
        print()
        print("PO entries to add to vi_VN.po files:")
        print(generate_po_entries(VI_TRANSLATIONS))


if __name__ == '__main__':
    main()
