#!/usr/bin/env python3
"""Apply reviewed Vietnamese dashboard terminology for Odoo 19 health_landing."""

import argparse
import json
import pathlib

import review_health_invoicing_mapping as base


OVERRIDES = {
    "ACTIVE SERVICE PACKAGES": "CÁC GÓI DỊCH VỤ ĐANG HOẠT ĐỘNG",
    "AR Dashboard": "Bảng điều khiển công nợ",
    "Access Roles": "Vai trò truy cập",
    "Accounts receivable overview": "Tổng quan công nợ phải thu",
    "Admin Center": "Trung tâm quản trị",
    "Admin Dashboard": "Bảng điều khiển quản trị",
    "Admin Settings": "Cài đặt quản trị",
    "Advanced Pricelist": "Bảng giá nâng cao",
    "Assignment Dashboard": "Bảng điều khiển phân công",
    "Assigned Staff": "Nhân viên được phân công",
    "Back to Hub": "Quay lại trung tâm",
    "Billing & Invoicing": "Thanh toán và lập hóa đơn",
    "Booking confirmed": "Lịch hẹn đã được xác nhận",
    "Cash has not been collected from patient yet.": "Chưa thu tiền mặt từ bệnh nhân.",
    "Cash payment not selected": "Chưa chọn thanh toán tiền mặt",
    "Cash received by OM": "Quản lý vận hành đã nhận tiền mặt",
    "Client Dashboard": "Bảng điều khiển khách hàng",
    "Clinical notes submitted": "Đã gửi ghi chú lâm sàng",
    "Collect Cash": "Thu tiền mặt",
    "Collect immediate payment": "Thu tiền ngay",
    "Complete clinical notes first": "Hoàn tất ghi chú lâm sàng trước",
    "Complete service and collect payment": "Hoàn thành dịch vụ và thu tiền",
    "Complete service first": "Hoàn thành dịch vụ trước",
    "Confirm booking first": "Xác nhận lịch hẹn trước",
    "Confirm payment received": "Xác nhận đã nhận thanh toán",
    "Confirm the booking": "Xác nhận lịch hẹn",
    "Create Booking": "Tạo lịch hẹn",
    "Create a healthcare quote": "Tạo báo giá chăm sóc sức khỏe",
    "Create a quote": "Tạo báo giá",
    "Create a quote first": "Tạo báo giá trước",
    "Create invoice": "Tạo hóa đơn",
    "Customer Invoices": "Hóa đơn khách hàng",
    "Defer payment": "Thanh toán sau",
    "Error:": "Lỗi:",
    "FSO Cash Collection Wizard": "Trình hướng dẫn thu tiền mặt FSO",
    "FSO Clinical Notes Wizard": "Trình hướng dẫn ghi chú lâm sàng FSO",
    "FSO Confirm Booking Wizard": "Trình hướng dẫn xác nhận lịch hẹn FSO",
    "FSO Equipment Wizard": "Trình hướng dẫn thiết bị FSO",
    "FSO Invoice Wizard": "Trình hướng dẫn hóa đơn FSO",
    "FSO Payment Received Wizard": "Trình hướng dẫn xác nhận thanh toán FSO",
    "FSO Service Packages Wizard": "Trình hướng dẫn gói dịch vụ FSO",
    "FSO Staff Assignment Wizard": "Trình hướng dẫn phân công nhân viên FSO",
    "FSO Start Service Wizard": "Trình hướng dẫn bắt đầu dịch vụ FSO",
    "Field Service": "Dịch vụ hiện trường",
    "Field Service Orders": "Lệnh dịch vụ hiện trường",
    "Field Service Teams": "Nhóm dịch vụ hiện trường",
    "Fill clinical notes": "Nhập ghi chú lâm sàng",
    "Fill in clinical notes": "Nhập ghi chú lâm sàng",
    "Healthcare Dashboard": "Bảng điều khiển chăm sóc sức khỏe",
    "Healthcare Quote": "Báo giá chăm sóc sức khỏe",
    "Healthcare Quote - %s": "Báo giá chăm sóc sức khỏe - %s",
    "Healthcare quote": "Báo giá chăm sóc sức khỏe",
    "Hub Stage Color": "Màu giai đoạn trung tâm",
    "Invoice created": "Đã tạo hóa đơn",
    "Lost Booking": "Mất lịch hẹn",
    "Main booking hub": "Trung tâm lịch hẹn chính",
    "No invoice or quote found for this booking.": "Không tìm thấy hóa đơn hoặc báo giá cho lịch hẹn này.",
    "Node State Clinical Notes": "Trạng thái nút Ghi chú lâm sàng",
    "Node State Collect Cash": "Trạng thái nút Thu tiền mặt",
    "Node State Complete Service": "Trạng thái nút Hoàn thành dịch vụ",
    "Node State Confirm Booking": "Trạng thái nút Xác nhận lịch hẹn",
    "Node State Equipment": "Trạng thái nút Thiết bị",
    "Node State Invoice": "Trạng thái nút Hóa đơn",
    "Node State Pay Later": "Trạng thái nút Thanh toán sau",
    "Node State Pay Now": "Trạng thái nút Thanh toán ngay",
    "Node State Payment Received": "Trạng thái nút Đã nhận thanh toán",
    "Node State Quote": "Trạng thái nút Báo giá",
    "Node State Service Packages": "Trạng thái nút Gói dịch vụ",
    "Node State Staff Assignment": "Trạng thái nút Phân công nhân viên",
    "Node State Start Service": "Trạng thái nút Bắt đầu dịch vụ",
    "Node Tip Clinical Notes": "Gợi ý nút Ghi chú lâm sàng",
    "Node Tip Collect Cash": "Gợi ý nút Thu tiền mặt",
    "Node Tip Complete Service": "Gợi ý nút Hoàn thành dịch vụ",
    "Node Tip Confirm Booking": "Gợi ý nút Xác nhận lịch hẹn",
    "Node Tip Equipment": "Gợi ý nút Thiết bị",
    "Node Tip Invoice": "Gợi ý nút Hóa đơn",
    "Node Tip Pay Later": "Gợi ý nút Thanh toán sau",
    "Node Tip Pay Now": "Gợi ý nút Thanh toán ngay",
    "Node Tip Payment Received": "Gợi ý nút Đã nhận thanh toán",
    "Node Tip Quote": "Gợi ý nút Báo giá",
    "Node Tip Service Packages": "Gợi ý nút Gói dịch vụ",
    "Node Tip Staff Assignment": "Gợi ý nút Phân công nhân viên",
    "Node Tip Start Service": "Gợi ý nút Bắt đầu dịch vụ",
    "OM collect cash": "Quản lý vận hành thu tiền mặt",
    "OM to collect cash from nurse": "Quản lý vận hành thu tiền mặt từ y tá",
    "Open Client Dashboard": "Mở bảng điều khiển khách hàng",
    "Past Bookings": "Lịch hẹn trước đây",
    "Pay Later": "Thanh toán sau",
    "Pay Later not selected": "Chưa chọn Thanh toán sau",
    "Pay Later selected": "Đã chọn Thanh toán sau",
    "Pay Later was selected": "Đã chọn Thanh toán sau",
    "Pay Now": "Thanh toán ngay",
    "Pay Now was selected": "Đã chọn Thanh toán ngay",
    "Payment Collection": "Thu tiền",
    "Payment received": "Đã nhận thanh toán",
    "Quote": "Báo giá",
    "Quote created": "Đã tạo báo giá",
    "Quote ready for invoicing": "Báo giá đã sẵn sàng lập hóa đơn",
    "Service Booked": "Dịch vụ đã đặt lịch",
    "Service Completed": "Dịch vụ đã hoàn thành",
    "Service completed": "Dịch vụ đã hoàn thành",
    "Service completed successfully!": "Dịch vụ đã hoàn thành!",
    "Service started": "Dịch vụ đã bắt đầu",
    "Show Pay Now Arrow": "Hiển thị mũi tên Thanh toán ngay",
    "Spam Call": "Cuộc gọi rác",
    "Spam Marked": "Đã đánh dấu là thư rác",
    "Start service first": "Bắt đầu dịch vụ trước",
    "Start the service": "Bắt đầu dịch vụ",
    "Start the service delivery": "Bắt đầu cung cấp dịch vụ",
    "Submit clinical notes first": "Gửi ghi chú lâm sàng trước",
    "Track referral sources": "Theo dõi nguồn giới thiệu",
    "Upcoming Bookings": "Lịch hẹn sắp tới",
    "Viet Uc": "Viet Uc",
    "Viet Uc Dashboard": "Bảng điều khiển Viet Uc",
    "Viet Uc Logo": "Logo Viet Uc",
    "View and assign service packages": "Xem và gán gói dịch vụ",
    "View or create quote": "Xem hoặc tạo báo giá",
    "Visual Scheduler": "Lịch trực quan",
    "Waiting for nurse to collect cash": "Đang chờ y tá thu tiền mặt",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()

    mapping = base.base.base.load_mapping(args.mapping)
    reviewed = {
        msgid: OVERRIDES.get(
            msgid,
            base.OVERRIDES.get(
                msgid,
                base.base.OVERRIDES.get(
                    msgid,
                    base.base.base.OVERRIDES.get(
                        msgid,
                        base.review_translation(msgstr),
                    ),
                ),
            ),
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
