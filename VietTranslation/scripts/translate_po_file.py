#!/usr/bin/env python3
"""
Automatic translation of Odoo PO files from English to Vietnamese.
Includes comprehensive medical and healthcare terminology dictionary.
"""

import re
import sys
from pathlib import Path

# Comprehensive English to Vietnamese translation dictionary
# Organized by category for healthcare/medical terminology
TRANSLATION_DICT = {
    # Core Medical Terms
    "Patient": "Bệnh nhân",
    "Patients": "Bệnh nhân",
    "Client": "Khách hàng",
    "Clients": "Khách hàng",
    "Doctor": "Bác sĩ",
    "Nurse": "Y tá",
    "Healthcare": "Y tế",
    "Medical": "Y khoa",
    "Clinical": "Lâm sàng",
    "Facility": "Cơ sở",
    "Facilities": "Các cơ sở",
    "Hospital": "Bệnh viện",
    "Clinic": "Phòng khám",

    # Patient Information
    "First Name": "Tên",
    "Last Name": "Họ",
    "Middle Name": "Tên đệm",
    "Full Name": "Họ và tên",
    "Date of Birth": "Ngày sinh",
    "Birth Date": "Ngày sinh",
    "Age": "Tuổi",
    "Gender": "Giới tính",
    "Male": "Nam",
    "Female": "Nữ",
    "Other": "Khác",
    "Prefer not to say": "Không muốn nói",

    # Medical Information
    "Blood Group": "Nhóm máu",
    "Blood Type": "Nhóm máu",
    "Known Allergies": "Dị ứng đã biết",
    "Allergies": "Dị ứng",
    "Medical History": "Tiền sử bệnh",
    "Medical History Summary": "Tóm tắt tiền sử bệnh",
    "Diagnosis": "Chẩn đoán",
    "Treatment": "Điều trị",
    "Prescription": "Đơn thuốc",
    "Medication": "Thuốc",
    "Symptoms": "Triệu chứng",
    "Condition": "Tình trạng",

    # Contact Information
    "Emergency Contact": "Liên hệ khẩn cấp",
    "Emergency Contact Name": "Tên người liên hệ khẩn cấp",
    "Emergency Contact Phone": "Số điện thoại liên hệ khẩn cấp",
    "Relation to Patient": "Mối quan hệ với bệnh nhân",
    "Phone": "Điện thoại",
    "Mobile": "Di động",
    "Email": "Email",
    "Address": "Địa chỉ",
    "Street": "Đường",
    "City": "Thành phố",
    "State": "Tỉnh/Thành",
    "Country": "Quốc gia",
    "ZIP": "Mã bưu điện",
    "Postal Code": "Mã bưu điện",

    # Healthcare Roles
    "Is Patient": "Là bệnh nhân",
    "Is Healthcare Staff": "Là nhân viên y tế",
    "Is Healthcare Facility": "Là cơ sở y tế",
    "Is Emergency Contact": "Là liên hệ khẩn cấp",
    "Is Caregiver": "Là người chăm sóc",
    "Is Payer": "Là người thanh toán",
    "Is Referrer": "Là người giới thiệu",
    "Caregiver": "Người chăm sóc",
    "Payer": "Người thanh toán",
    "Referrer": "Người giới thiệu",

    # Patient Status
    "Patient Status": "Trạng thái bệnh nhân",
    "Client Status": "Trạng thái khách hàng",
    "New Client": "Khách hàng mới",
    "Active": "Đang hoạt động",
    "Inactive": "Không hoạt động",
    "Deceased": "Đã mất",
    "Status": "Trạng thái",

    # Facility Information
    "Primary Facility": "Cơ sở y tế chính",
    "Healthcare Facility": "Cơ sở y tế",
    "Facility Name": "Tên cơ sở",
    "Facility Code": "Mã cơ sở",
    "Facility Type": "Loại cơ sở",
    "Capacity": "Sức chứa",
    "Beds": "Giường bệnh",
    "Location": "Vị trí",
    "Province": "Tỉnh",
    "Province Code": "Mã tỉnh",

    # Appointments & Visits
    "Appointment": "Cuộc hẹn",
    "Appointments": "Các cuộc hẹn",
    "Visit": "Lần khám",
    "Visits": "Lần khám",
    "Schedule": "Lịch trình",
    "Next Visit": "Lần khám tiếp theo",
    "Last Visit": "Lần khám gần nhất",
    "Next Scheduled Visit": "Lần khám tiếp theo đã lên lịch",
    "Registration Date": "Ngày đăng ký",
    "Home Visit": "Khám tại nhà",
    "Home Visits": "Khám tại nhà",
    "Clinic Visit": "Khám tại phòng khám",

    # Insurance & Payment
    "Insurance": "Bảo hiểm",
    "Insurance Provider": "Nhà cung cấp bảo hiểm",
    "Insurance Number": "Số bảo hiểm",
    "Insurance Expiry": "Ngày hết hạn bảo hiểm",
    "Payment": "Thanh toán",
    "Payment Method": "Phương thức thanh toán",
    "Primary Payment Method": "Phương thức thanh toán chính",
    "Cash": "Tiền mặt",
    "Card": "Thẻ",
    "Corporate": "Công ty",
    "Government": "Chính phủ",
    "Invoice": "Hóa đơn",
    "Receipt": "Biên lai",
    "Amount": "Số tiền",
    "Total": "Tổng cộng",
    "Revenue": "Doanh thu",
    "Monthly Revenue": "Doanh thu hàng tháng",

    # Vietnamese Specific
    "Vietnamese Name": "Tên tiếng Việt",
    "National ID": "Căn cước công dân",
    "CCCD/CMND": "CCCD/CMND",
    "Vietnamese Address": "Địa chỉ Việt Nam",
    "Ward/Commune": "Phường/Xã",
    "District": "Quận/Huyện",
    "Province/City": "Tỉnh/Thành phố",
    "Ethnicity": "Dân tộc",
    "Profession": "Nghề nghiệp",
    "Kinh (Vietnamese)": "Kinh",

    # UI Elements
    "Save": "Lưu",
    "Cancel": "Hủy",
    "Create": "Tạo mới",
    "Edit": "Chỉnh sửa",
    "Delete": "Xóa",
    "Search": "Tìm kiếm",
    "Filter": "Lọc",
    "Export": "Xuất",
    "Import": "Nhập",
    "Print": "In",
    "Confirm": "Xác nhận",
    "Back": "Quay lại",
    "Next": "Tiếp theo",
    "Previous": "Trước",
    "Submit": "Gửi",
    "Close": "Đóng",
    "Open": "Mở",
    "View": "Xem",
    "Update": "Cập nhật",
    "Refresh": "Làm mới",
    "Reset": "Đặt lại",
    "Clear": "Xóa",
    "Apply": "Áp dụng",
    "Download": "Tải xuống",
    "Upload": "Tải lên",
    "Attach": "Đính kèm",
    "Remove": "Gỡ bỏ",
    "Add": "Thêm",
    "New": "Mới",
    "Copy": "Sao chép",
    "Duplicate": "Nhân bản",
    "Archive": "Lưu trữ",
    "Unarchive": "Bỏ lưu trữ",
    "Activate": "Kích hoạt",
    "Deactivate": "Hủy kích hoạt",
    "Send": "Gửi",
    "Receive": "Nhận",
    "Process": "Xử lý",
    "Complete": "Hoàn thành",
    "Draft": "Nháp",
    "Done": "Hoàn tất",
    "Validated": "Đã xác thực",
    "Confirmed": "Đã xác nhận",
    "Pending": "Đang chờ",
    "Cancelled": "Đã hủy",
    "Failed": "Thất bại",
    "Success": "Thành công",
    "Error": "Lỗi",
    "Warning": "Cảnh báo",
    "Info": "Thông tin",
    "Help": "Trợ giúp",
    "Settings": "Cài đặt",
    "Configuration": "Cấu hình",
    "Options": "Tùy chọn",
    "Preferences": "Tùy chỉnh",
    "Actions": "Hành động",

    # Forms and Fields
    "Name": "Tên",
    "Description": "Mô tả",
    "Notes": "Ghi chú",
    "Details": "Chi tiết",
    "Summary": "Tóm tắt",
    "Type": "Loại",
    "Category": "Danh mục",
    "Tags": "Thẻ",
    "Priority": "Ưu tiên",
    "Urgent": "Khẩn cấp",
    "High": "Cao",
    "Medium": "Trung bình",
    "Low": "Thấp",
    "Normal": "Bình thường",
    "Date": "Ngày",
    "Time": "Giờ",
    "Start Date": "Ngày bắt đầu",
    "End Date": "Ngày kết thúc",
    "Duration": "Thời lượng",
    "From": "Từ",
    "To": "Đến",
    "Created": "Đã tạo",
    "Modified": "Đã sửa",
    "Created by": "Tạo bởi",
    "Modified by": "Sửa bởi",
    "Assigned to": "Giao cho",
    "Responsible": "Người phụ trách",
    "Owner": "Chủ sở hữu",
    "User": "Người dùng",
    "Company": "Công ty",
    "Partner": "Đối tác",
    "Contact": "Liên hệ",
    "Reference": "Tham chiếu",
    "Code": "Mã",
    "Number": "Số",
    "Sequence": "Trình tự",
    "Version": "Phiên bản",
    "Language": "Ngôn ngữ",
    "Currency": "Tiền tệ",

    # Navigation
    "Home": "Trang chủ",
    "Dashboard": "Bảng điều khiển",
    "Menu": "Trình đơn",
    "Reporting": "Báo cáo",
    "Reports": "Báo cáo",
    "Analysis": "Phân tích",
    "Statistics": "Thống kê",
    "Charts": "Biểu đồ",
    "Calendar": "Lịch",
    "Timeline": "Dòng thời gian",
    "History": "Lịch sử",
    "Activity": "Hoạt động",
    "Messages": "Tin nhắn",
    "Notifications": "Thông báo",
    "Alerts": "Cảnh báo",

    # Relationships
    "Primary Caregiver": "Người chăm sóc chính",
    "Primary Payer": "Người thanh toán chính",
    "Primary Referrer": "Người giới thiệu chính",
    "Clients I Care For": "Khách hàng tôi chăm sóc",
    "Clients I Pay For": "Khách hàng tôi thanh toán",
    "Clients I Referred": "Khách hàng tôi giới thiệu",
    "Related": "Liên quan",
    "Link": "Liên kết",

    # Medical Specialties
    "Medical Specialties": "Chuyên khoa y tế",
    "Specialty": "Chuyên khoa",
    "General Practice": "Đa khoa",
    "Cardiology": "Tim mạch",
    "Neurology": "Thần kinh",
    "Pediatrics": "Nhi khoa",
    "Surgery": "Phẫu thuật",
    "Emergency": "Khẩn cấp",
    "Preventive": "Phòng ngừa",
    "Rehabilitation": "Phục hồi chức năng",
    "Palliative": "Chăm sóc giảm nhẹ",

    # Clinical Terms
    "Consultation": "Tư vấn",
    "Examination": "Khám bệnh",
    "Follow-up": "Theo dõi",
    "Follow-up Care": "Chăm sóc theo dõi",
    "Emergency Care": "Chăm sóc khẩn cấp",
    "Preventive Care": "Chăm sóc phòng ngừa",
    "Routine": "Thường quy",
    "Laboratory": "Phòng xét nghiệm",
    "Lab Results": "Kết quả xét nghiệm",
    "Test Results": "Kết quả xét nghiệm",
    "Radiology": "X-quang",
    "Imaging": "Chẩn đoán hình ảnh",

    # License and Professional
    "License": "Giấy phép",
    "License Number": "Số giấy phép",
    "License Expiry": "Ngày hết hạn giấy phép",
    "Professional License": "Giấy phép hành nghề",
    "Professional License Number": "Số giấy phép hành nghề",
    "Certification": "Chứng chỉ",
    "Accreditation": "Kiểm định",

    # Geolocation
    "Latitude": "Vĩ độ",
    "Longitude": "Kinh độ",
    "Coordinates": "Tọa độ",
    "GPS Coordinates": "Tọa độ GPS",
    "Geolocation": "Định vị địa lý",
    "Geolocation Date": "Ngày định vị",
    "Map": "Bản đồ",
    "Distance": "Khoảng cách",

    # Audit and Tracking
    "Audit Log": "Nhật ký kiểm toán",
    "Tracking": "Theo dõi",
    "Source": "Nguồn",
    "Client Source": "Nguồn khách hàng",
    "Source Details": "Chi tiết nguồn",
    "Referral Source": "Nguồn giới thiệu",
    "Facebook": "Facebook",
    "Zalo": "Zalo",
    "Website": "Trang web",
    "Phone Call": "Cuộc gọi điện thoại",
    "Referral": "Giới thiệu",
    "Walk-in": "Đến trực tiếp",

    # Messages and Notifications
    "Patient Activated": "Đã kích hoạt bệnh nhân",
    "Patient Deactivated": "Đã hủy kích hoạt bệnh nhân",
    "New Appointment": "Cuộc hẹn mới",
    "Record updated": "Đã cập nhật bản ghi",
    "Record created": "Đã tạo bản ghi",
    "Record deleted": "Đã xóa bản ghi",
    "Please enter": "Vui lòng nhập",
    "Required": "Bắt buộc",
    "Optional": "Tùy chọn",

    # Common Phrases
    "Personal Information": "Thông tin cá nhân",
    "Medical Information": "Thông tin y tế",
    "Contact Details": "Thông tin liên hệ",
    "Address Information": "Thông tin địa chỉ",
    "Insurance Information": "Thông tin bảo hiểm",
    "Professional Details": "Thông tin nghề nghiệp",
    "Additional Information": "Thông tin bổ sung",
    "Basic Information": "Thông tin cơ bản",
    "Clinical Information": "Thông tin lâm sàng",
    "Administrative": "Hành chính",

    # Validation Messages
    "Please enter a valid email address.": "Vui lòng nhập địa chỉ email hợp lệ.",
    "Please enter a valid phone number.": "Vui lòng nhập số điện thoại hợp lệ.",
    "Please enter a valid mobile number.": "Vui lòng nhập số điện thoại di động hợp lệ.",
    "This field is required": "Trường này là bắt buộc",
    "Invalid format": "Định dạng không hợp lệ",

    # System Messages
    "No records found": "Không tìm thấy bản ghi",
    "Loading...": "Đang tải...",
    "Processing...": "Đang xử lý...",
    "Please wait": "Vui lòng đợi",
    "Are you sure?": "Bạn có chắc chắn không?",
    "This action cannot be undone": "Hành động này không thể hoàn tác",
    "Confirmation required": "Yêu cầu xác nhận",

    # Health
    "Health": "Y tế",
    "Patient ID": "Mã bệnh nhân",
    "Patient ID Display": "Hiển thị mã bệnh nhân",
    "Client Category": "Danh mục khách hàng",
    "Patient Category": "Danh mục bệnh nhân",
    "Age Display": "Hiển thị tuổi",
    "years old": "tuổi",
    "Age unknown": "Tuổi không xác định",
    "Not Assigned": "Chưa gán",
    "Not geolocated": "Chưa định vị",
    "Total Visits": "Tổng số lần khám",
    "Patients as Caregiver": "Bệnh nhân với vai trò người chăm sóc",
    "Patients as Payer": "Bệnh nhân với vai trò người thanh toán",
    "Patients as Referrer": "Bệnh nhân với vai trò người giới thiệu",
    "Service Bookings": "Đặt dịch vụ",
    "Facility Record": "Hồ sơ cơ sở",
    "Facility Patients": "Bệnh nhân của cơ sở",

    # More UI
    "Group By": "Nhóm theo",
    "Filters": "Bộ lọc",
    "Search...": "Tìm kiếm...",
    "Select": "Chọn",
    "All": "Tất cả",
    "None": "Không có",
    "Today": "Hôm nay",
    "This Week": "Tuần này",
    "This Month": "Tháng này",
    "This Year": "Năm nay",
    "Yesterday": "Hôm qua",
    "Last Week": "Tuần trước",
    "Last Month": "Tháng trước",
    "Last Year": "Năm trước",
    "Custom": "Tùy chỉnh",
    "Range": "Phạm vi",
    "Show": "Hiển thị",
    "Hide": "Ẩn",
    "Expand": "Mở rộng",
    "Collapse": "Thu gọn",
    "More": "Thêm",
    "Less": "Ít hơn",
    "Full": "Đầy đủ",
    "Empty": "Trống",
    "Yes": "Có",
    "No": "Không",
    "True": "Đúng",
    "False": "Sai",
    "Enabled": "Đã bật",
    "Disabled": "Đã tắt",
    "Public": "Công khai",
    "Private": "Riêng tư",
    "Shared": "Chia sẻ",
    "Internal": "Nội bộ",
    "External": "Bên ngoài",
}


def translate_text(text, preserve_html=True):
    """
    Translate English text to Vietnamese using the dictionary.
    Preserves HTML tags, format strings, and special characters.
    """
    if not text or text.strip() == "":
        return text

    # Don't translate if it's just HTML/formatting
    if text.strip().startswith('<') and text.strip().endswith('>'):
        # But translate text within HTML
        for eng, vie in sorted(TRANSLATION_DICT.items(), key=lambda x: len(x[0]), reverse=True):
            # Simple text replacement in HTML content
            text = re.sub(r'\b' + re.escape(eng) + r'\b', vie, text, flags=re.IGNORECASE)
        return text

    # Exact match first
    if text in TRANSLATION_DICT:
        return TRANSLATION_DICT[text]

    # Try with stripped whitespace
    stripped = text.strip()
    if stripped in TRANSLATION_DICT:
        # Preserve leading/trailing whitespace
        prefix = text[:len(text) - len(text.lstrip())]
        suffix = text[len(text.rstrip()):]
        return prefix + TRANSLATION_DICT[stripped] + suffix

    # Word-by-word translation for phrases
    result = text
    for eng, vie in sorted(TRANSLATION_DICT.items(), key=lambda x: len(x[0]), reverse=True):
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(eng) + r'\b'
        result = re.sub(pattern, vie, result, flags=re.IGNORECASE)

    return result


def translate_po_file(input_file, output_file=None):
    """
    Translate a PO file from English to Vietnamese.
    """
    if output_file is None:
        output_file = input_file

    print(f"Reading: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    translated_lines = []
    in_msgid = False
    in_msgstr = False
    current_msgid = ""
    msgid_lines = []

    translated_count = 0
    total_count = 0

    for i, line in enumerate(lines):
        # Detect msgid
        if line.startswith('msgid '):
            in_msgid = True
            in_msgstr = False
            msgid_text = line[6:].strip().strip('"')
            msgid_lines = [msgid_text]
            translated_lines.append(line)
            continue

        # Detect msgstr
        if line.startswith('msgstr '):
            in_msgid = False
            in_msgstr = True

            # Combine multi-line msgid
            current_msgid = ''.join(msgid_lines)

            # Check if msgstr is empty
            msgstr_content = line[7:].strip().strip('"')

            if msgstr_content == "" and current_msgid != "":
                # Translate!
                translated = translate_text(current_msgid)
                if translated != current_msgid:  # Only count if actually translated
                    translated_count += 1
                total_count += 1
                translated_lines.append(f'msgstr "{translated}"\n')

                if translated_count % 50 == 0:
                    print(f"  Translated {translated_count}/{total_count} strings...")
            else:
                # Keep existing msgstr
                translated_lines.append(line)

            msgid_lines = []
            continue

        # Handle multi-line strings
        if in_msgid and line.strip().startswith('"'):
            msgid_text = line.strip().strip('"')
            msgid_lines.append(msgid_text)
            translated_lines.append(line)
            continue

        # All other lines (comments, blank lines, etc.)
        translated_lines.append(line)

    # Write output
    print(f"\nWriting: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(translated_lines)

    print(f"\n✅ Translation complete!")
    print(f"   Translated: {translated_count} strings")
    print(f"   Total: {total_count} translatable strings")
    print(f"   Coverage: {translated_count/total_count*100:.1f}%")

    return translated_count, total_count


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 translate_po_file.py <po_file>")
        print("Example: python3 translate_po_file.py addons/health_base/i18n/base.po")
        sys.exit(1)

    input_file = sys.argv[1]

    if not Path(input_file).exists():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    # Create backup
    backup_file = str(input_file) + ".backup"
    print(f"Creating backup: {backup_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)

    # Translate
    translate_po_file(input_file)


if __name__ == '__main__':
    main()
