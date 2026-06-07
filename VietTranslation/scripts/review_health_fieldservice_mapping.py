#!/usr/bin/env python3
"""Apply reviewed Vietnamese terminology for the Odoo 19 field-service module."""

import argparse
import json
import pathlib
import re

import review_health_crm_mapping as base


REPLACEMENTS = [
    ("Buffer Times", "Thời gian đệm"),
    ("Clinical Notes", "Ghi chú lâm sàng"),
    ("Clinical Note", "Ghi chú lâm sàng"),
    ("Home Visit", "Thăm khám tại nhà"),
    ("Clinic Visit", "Thăm khám tại phòng khám"),
    ("Hospital Visit", "Thăm khám tại bệnh viện"),
    ("Lab Visit", "Thăm khám tại phòng xét nghiệm"),
    ("Teleconsultation", "Tư vấn từ xa"),
    ("Operations Manager", "Quản lý vận hành"),
    ("Healthcare Staff", "Nhân viên y tế"),
    ("Assigned Staff", "Nhân viên được phân công"),
    ("Staff Assignment", "Phân công nhân viên"),
    ("Service Requirements", "Yêu cầu dịch vụ"),
    ("Service Timeline", "Tiến trình dịch vụ"),
    ("Service Details", "Chi tiết dịch vụ"),
    ("Service Quality", "Chất lượng dịch vụ"),
    ("Start Service", "Bắt đầu dịch vụ"),
    ("Complete Service", "Hoàn thành dịch vụ"),
    ("Services", "Dịch vụ"),
    ("Service", "Dịch vụ"),
    ("Assignments", "Phân công"),
    ("Assignment", "Phân công"),
    ("Assigning", "Đang phân công"),
    ("Assigned", "Đã phân công"),
    ("Assign", "Phân công"),
    ("Staff", "Nhân viên"),
    ("Patient", "Bệnh nhân"),
    ("Doctors", "Bác sĩ"),
    ("Doctor", "Bác sĩ"),
    ("Nurse", "Y tá"),
    ("Invoices", "Hóa đơn"),
    ("Invoice", "Hóa đơn"),
    ("Quotes", "Báo giá"),
    ("Quote", "Báo giá"),
    ("Payments", "Thanh toán"),
    ("Payment", "Thanh toán"),
    ("Clinical", "Lâm sàng"),
    ("Dashboard", "Bảng điều khiển"),
    ("Timeline", "Dòng thời gian"),
    ("Schedule", "Lịch làm việc"),
    ("Calendar", "Lịch"),
    ("Cancellation", "Hủy lịch hẹn"),
    ("Cancelled", "Đã hủy"),
    ("Confirmed", "Đã xác nhận"),
    ("Completed", "Đã hoàn thành"),
    ("Unassigned", "Chưa phân công"),
    ("Available", "Có sẵn"),
    ("Required", "Bắt buộc"),
    ("Outstanding", "Chưa thanh toán"),
    ("Call", "Gọi"),
]

OVERRIDES = {
    "-- No doctor --": "-- Không có bác sĩ --",
    "-- No lead staff --": "-- Không có nhân viên phụ trách --",
    "-- No package --": "-- Không có gói dịch vụ --",
    "Action Steps Template": "Mẫu các bước hành động",
    "Avatar Hue": "Sắc độ ảnh đại diện",
    "Booking": "Lịch hẹn",
    "Booking moved to In Progress stage. Timer started.": "Lịch hẹn đã chuyển sang giai đoạn Đang thực hiện. Bộ đếm thời gian đã bắt đầu.",
    "Bookings": "Các lịch hẹn",
    "Buffer Times": "Thời gian đệm",
    "Clinic Visit": "Thăm khám tại phòng khám",
    "Clinical Notes": "Ghi chú lâm sàng",
    "Complete Service": "Hoàn thành dịch vụ",
    "Documentation Template": "Mẫu tài liệu",
    "Email": "Thư điện tử",
    "FSO Count": "Số lượng FSO",
    "GPS Longitude": "Kinh độ GPS",
    "Home Visit": "Thăm khám tại nhà",
    "Hospital Visit": "Thăm khám tại bệnh viện",
    "Icon": "Biểu tượng",
    "Invoice": "Hóa đơn",
    "Invoice or Quote is required before completing the service.\n\nPlease create a quote with service items or assign an invoice.": "Cần có hóa đơn hoặc báo giá trước khi hoàn thành dịch vụ.\n\nVui lòng tạo báo giá có các hạng mục dịch vụ hoặc gán một hóa đơn.",
    "Lab Visit": "Thăm khám tại phòng xét nghiệm",
    "Junior": "Sơ cấp",
    "Mark Available": "Đánh dấu là có sẵn",
    "Mark In Use": "Đánh dấu đang sử dụng",
    "Mon": "T2",
    "NEW": "MỚI",
    "No In Progress stage found. Please configure booking stages properly.": "Không tìm thấy giai đoạn Đang thực hiện. Vui lòng cấu hình đúng các giai đoạn lịch hẹn.",
    "No bookings found": "Không tìm thấy lịch hẹn",
    "Online/Telemedicine": "Trực tuyến/Y tế từ xa",
    "Ops Manager Review": "Quản lý vận hành xem xét",
    "Patient": "Bệnh nhân",
    "Payment": "Thanh toán",
    "Quote": "Báo giá",
    "Reference / Transaction ID": "Mã tham chiếu / giao dịch",
    "Sat": "T7",
    "Service": "Dịch vụ",
    "Services": "Dịch vụ",
    "Staff": "Nhân viên",
    "Staff Assignment": "Phân công nhân viên",
    "Start Service": "Bắt đầu dịch vụ",
    "Template": "Mẫu",
    "Teleconsultation": "Tư vấn từ xa",
    "Thu": "T5",
    "Thu off": "Nghỉ Thứ Năm",
    "Tue": "T3",
    "Undo & Delete": "Hoàn tác và xóa",
    "UoM": "Đơn vị tính",
    "Visual Scheduler": "Lịch trực quan",
    "✓ Mark Read": "✓ Đánh dấu đã đọc",
}


def replace_terms(text):
    parts = []
    position = 0
    for match in base.PROTECTED_RE.finditer(text):
        segment = text[position : match.start()]
        for old, new in REPLACEMENTS:
            segment = re.sub(rf"\b{re.escape(old)}\b", new, segment)
        parts.extend((segment, match.group(0)))
        position = match.end()
    segment = text[position:]
    for old, new in REPLACEMENTS:
        segment = re.sub(rf"\b{re.escape(old)}\b", new, segment)
    parts.append(segment)
    return "".join(parts)


def review_translation(text):
    text = base.review_translation(text)
    parts = base.TAG_RE.split(text)
    for index, part in enumerate(parts):
        if not base.TAG_RE.fullmatch(part or ""):
            parts[index] = replace_terms(part)
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()

    mapping = base.load_mapping(args.mapping)
    reviewed = {
        msgid: OVERRIDES.get(
            msgid,
            base.OVERRIDES.get(msgid, review_translation(msgstr)),
        )
        for msgid, msgstr in mapping.items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Reviewed {len(reviewed)} translations in {args.output}")


if __name__ == "__main__":
    main()
