#!/usr/bin/env python3
"""
Improved PO file translator with better HTML/CSS handling and more Vietnamese terms.
"""

import re

# Extended Vietnamese translation dictionary
TRANSLATIONS = {
    # Additional phrases and terms
    "has expired": "đã hết hạn",
    "please update": "vui lòng cập nhật",
    "coming soon": "sắp ra mắt",
    "will be displayed here": "sẽ được hiển thị ở đây",
    "Please complete all required information": "Vui lòng hoàn thành tất cả thông tin bắt buộc",
    "and verify": "và xác minh",
    "insurance details": "chi tiết bảo hiểm",
    "documentation system integration": "tích hợp hệ thống tài liệu",
    "with appointments, treatments, and key events": "với các cuộc hẹn, điều trị và sự kiện quan trọng",
    "Critical for client safety": "Quan trọng cho sự an toàn của khách hàng",
    "please be thorough": "vui lòng cẩn thận kỹ lưỡng",

    # Core terms (from previous dict)
    "Patient": "Bệnh nhân",
    "Patients": "Bệnh nhân",
    "Client": "Khách hàng",
    "Clients": "Khách hàng",
    "Schedule": "Lịch trình",
    "Insurance": "Bảo hiểm",
    "History": "Lịch sử",
    "Clinical": "Lâm sàng",
    "Timeline": "Dòng thời gian",
    "Appointments": "Các cuộc hẹn",
    "Treatments": "Điều trị",
    "Beds": "Giường bệnh",
    "Capacity": "Sức chứa",
    "Facility Code": "Mã cơ sở",
    "Home Visits": "Khám tại nhà",
    "Location": "Vị trí",
    "Monthly Revenue": "Doanh thu hàng tháng",
    "Type": "Loại",
    "Next Visit": "Lần khám tiếp theo",
    "Lab Results": "Kết quả xét nghiệm",
    "Prescriptions": "Đơn thuốc",
    "ALLERGIES": "Dị ứng",
    "NEW CLIENT": "KHÁCH HÀNG MỚI",
    "Age": "Tuổi",
    "Gender": "Giới tính",
    "Mobile": "Di động",
    "Health": "Y tế",
    "Info": "Thông tin",
    "Complete": "Hoàn thành",
    "All": "Tất cả",
    "Required": "Bắt buộc",
    "Details": "Chi tiết",
    "Information": "Thông tin",
    "Verify": "Xác minh",

    # More comprehensive medical terms
    "Patient ID": "Mã bệnh nhân",
    "First Name": "Tên",
    "Last Name": "Họ",
    "Middle Name": "Tên đệm",
    "Date of Birth": "Ngày sinh",
    "Blood Group": "Nhóm máu",
    "Emergency Contact": "Liên hệ khẩn cấp",
    "Medical History": "Tiền sử bệnh",
    "Primary Facility": "Cơ sở y tế chính",
    "License Number": "Số giấy phép",
    "Registration Date": "Ngày đăng ký",
    "Last Visit": "Lần khám gần nhất",
    "Male": "Nam",
    "Female": "Nữ",
    "Other": "Khác",
    "Cash": "Tiền mặt",
    "Card": "Thẻ",
    "Active": "Đang hoạt động",
    "Inactive": "Không hoạt động",
    "Deceased": "Đã mất",
    "Status": "Trạng thái",

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
    "Update": "Cập nhật",
    "Confirm": "Xác nhận",
    "Close": "Đóng",
    "View": "Xem",
    "Add": "Thêm",
    "Remove": "Gỡ bỏ",
    "Back": "Quay lại",
    "Next": "Tiếp theo",
    "Previous": "Trước",
}


def preserve_html_translate(text):
    """
    Translate text while preserving HTML tags, CSS classes, and special format strings.
    """
    if not text or text.strip() == "":
        return text

    # Save original for comparison
    original = text

    # Don't translate technical class names, IDs, etc.
    # Protect HTML attributes
    protected_patterns = []

    # Store class names and protect them
    class_pattern = r'class="([^"]+)"'
    classes = re.findall(class_pattern, text)
    for i, cls in enumerate(classes):
        placeholder = f"__CLASS_{i}__"
        text = text.replace(f'class="{cls}"', f'class="{placeholder}"', 1)
        protected_patterns.append((placeholder, cls))

    # Store other HTML tags temporarily
    tag_pattern = r'<[^>]+>'
    tags = re.findall(tag_pattern, text)
    for i, tag in enumerate(tags):
        placeholder = f"__TAG_{i}__"
        text = text.replace(tag, placeholder, 1)
        protected_patterns.append((placeholder, tag))

    # Now translate the remaining text
    for eng, vie in sorted(TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True):
        # Case insensitive replacement with word boundaries
        pattern = r'\b' + re.escape(eng) + r'\b'
        text = re.sub(pattern, vie, text, flags=re.IGNORECASE)

    # Restore protected patterns
    for placeholder, original_val in reversed(protected_patterns):
        text = text.replace(placeholder, original_val)

    return text


def translate_po_file(input_file, output_file):
    """Translate PO file with improved handling"""
    print(f"Reading: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into blocks
    blocks = content.split('\n\n')
    translated_blocks = []
    count = 0

    for block in blocks:
        if 'msgid' not in block:
            translated_blocks.append(block)
            continue

        # Extract msgid and msgstr
        msgid_match = re.search(r'msgid "(.*?)"', block, re.DOTALL)
        msgstr_match = re.search(r'msgstr "(.*?)"', block, re.DOTALL)

        if not msgid_match or not msgstr_match:
            # Handle multiline
            msgid_match = re.search(r'msgid\s+"((?:[^"\\]|\\.)*)"', block)
            msgstr_match = re.search(r'msgstr\s+"((?:[^"\\]|\\.)*)"', block)

        if msgid_match and msgstr_match:
            msgid_text = msgid_match.group(1)
            msgstr_text = msgstr_match.group(1)

            # Only translate if msgstr is empty
            if msgstr_text.strip() == "" and msgid_text.strip() != "":
                translated = preserve_html_translate(msgid_text)
                if translated != msgid_text:
                    count += 1
                    if count % 100 == 0:
                        print(f"  Translated {count} entries...")
                    block = block.replace(f'msgstr "{msgstr_text}"', f'msgstr "{translated}"')

        translated_blocks.append(block)

    # Write output
    print(f"Writing: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(translated_blocks))

    print(f"\n✅ Translation complete! Translated {count} entries.")


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 translate_po_improved.py <input.po> <output.po>")
        sys.exit(1)

    translate_po_file(sys.argv[1], sys.argv[2])
