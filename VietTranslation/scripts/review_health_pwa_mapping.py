#!/usr/bin/env python3
"""Review Vietnamese translations for the Odoo 19 health_pwa module."""

import argparse
import json
import pathlib

import review_health_landing_mapping as base


OVERRIDES = {
    ". Please try again.": ". Vui lòng thử lại.",
    "<strong>Note:</strong> DON'T add this page to home screen - it's just a guide!": "<strong>Lưu ý:</strong> ĐỪNG thêm trang này vào màn hình chính - đây chỉ là hướng dẫn!",
    "<strong>Step 1:</strong> Click \"Open Viet Uc\" button below": "<strong>Bước 1:</strong> Nhấn nút \"Mở Viet Uc\" bên dưới",
    "<strong>Step 2:</strong> Once the app opens, follow the instructions below to install": "<strong>Bước 2:</strong> Khi ứng dụng mở, hãy làm theo hướng dẫn bên dưới để cài đặt",
    "Access denied": "Từ chối truy cập",
    "App is already installed! Open from your home screen.": "Ứng dụng đã được cài đặt! Hãy mở từ màn hình chính.",
    "Assignment confirmed successfully": "Đã xác nhận phân công thành công",
    "Assignment declined": "Đã từ chối phân công",
    "Assignment not found": "Không tìm thấy phân công",
    "Auth Key": "Khóa xác thực",
    "Booking Cancelled": "Lịch hẹn đã bị hủy",
    "Booking Reference": "Mã tham chiếu lịch hẹn",
    "Booking Rescheduled": "Đã đổi lịch hẹn",
    "Browser Info": "Thông tin trình duyệt",
    "Cancellation reason is required": "Bắt buộc nhập lý do hủy",
    "Cannot cancel service in %s state": "Không thể hủy dịch vụ ở trạng thái %s",
    "Cannot complete service in %s state": "Không thể hoàn tất dịch vụ ở trạng thái %s",
    "Click install <span class=\"step-icon browser-install-icon\">⬇</span>": "Nhấn cài đặt <span class=\"step-icon browser-install-icon\">⬇</span>",
    "Client reset requested - perform full sync": "Đã yêu cầu đặt lại dữ liệu máy khách - thực hiện đồng bộ toàn bộ",
    "Click the install icon and confirm to install Viet Uc": "Nhấn biểu tượng cài đặt và xác nhận để cài đặt Viet Uc",
    "Clinical note created successfully": "Đã tạo ghi chú lâm sàng thành công",
    "Confirm installation <span class=\"step-icon android-install-icon\">✓</span>": "Xác nhận cài đặt <span class=\"step-icon android-install-icon\">✓</span>",
    "Confirm installation <span class=\"step-icon ios-add-icon\">✓</span>": "Xác nhận cài đặt <span class=\"step-icon ios-add-icon\">✓</span>",
    "Contact email for VAPID claims (mailto: format). Used by push services to contact you.": "Email liên hệ cho khai báo VAPID (định dạng mailto:). Dịch vụ thông báo đẩy sử dụng email này để liên hệ.",
    "Created by": "Được tạo bởi",
    "Created on": "Ngày tạo",
    "Display Name": "Tên hiển thị",
    "Enable Push Notifications": "Bật thông báo đẩy",
    "Enable push notifications for booking assignments and updates": "Bật thông báo đẩy cho phân công và cập nhật lịch hẹn",
    "English": "Tiếng Anh",
    "Find and tap \"Add to Home screen\" or \"Install\" in the menu": "Tìm và nhấn \"Thêm vào Màn hình chính\" hoặc \"Cài đặt\" trong menu",
    "Install app on your phone": "Cài đặt ứng dụng lên điện thoại",
    "Installation Guide": "Hướng dẫn cài đặt",
    "Installation Tutorial": "Hướng dẫn cài đặt ứng dụng",
    "Intake notes saved successfully": "Đã lưu ghi chú tiếp nhận thành công",
    "Invalid FSO or patient mismatch": "FSO không hợp lệ hoặc bệnh nhân không khớp",
    "Invalid action": "Thao tác không hợp lệ",
    "Invalid action. Use accept or decline.": "Thao tác không hợp lệ. Hãy chọn chấp nhận hoặc từ chối.",
    "Invalid cancellation reason": "Lý do hủy không hợp lệ",
    "Invalid date format. Use YYYY-MM-DD": "Định dạng ngày không hợp lệ. Hãy dùng YYYY-MM-DD",
    "Invalid datetime format: %s": "Định dạng ngày giờ không hợp lệ: %s",
    "Invoice verified and saved successfully": "Đã xác minh và lưu hóa đơn thành công",
    "Last Updated by": "Cập nhật lần cuối bởi",
    "Last Updated on": "Ngày cập nhật gần nhất",
    "Launch the app <span class=\"step-icon browser-app-icon\">🚀</span>": "Khởi chạy ứng dụng <span class=\"step-icon browser-app-icon\">🚀</span>",
    "Line ID required": "Bắt buộc có mã dòng",
    "Line not found": "Không tìm thấy dòng",
    "Loading data...": "Đang tải dữ liệu...",
    "Look for the install icon <span class=\"step-icon browser-install-icon\">⊕</span>": "Tìm biểu tượng cài đặt <span class=\"step-icon browser-install-icon\">⊕</span>",
    "Look for the share icon (upward arrow) at the bottom of your Safari browser": "Tìm biểu tượng chia sẻ (mũi tên hướng lên) ở dưới cùng của trình duyệt Safari",
    "Message": "Thông báo",
    "Missing endpoint": "Thiếu endpoint",
    "Missing order ID": "Thiếu mã đơn",
    "Missing patient ID": "Thiếu mã bệnh nhân",
    "Missing required fields: endpoint, keys.p256dh, keys.auth": "Thiếu các trường bắt buộc: endpoint, keys.p256dh, keys.auth",
    "New Date/Time": "Ngày/giờ mới",
    "Next visit scheduled successfully": "Đã lên lịch lượt thăm tiếp theo thành công",
    "No facility found. Please set a facility on the original booking.": "Không tìm thấy cơ sở. Vui lòng đặt cơ sở cho lịch hẹn ban đầu.",
    "No image provided": "Chưa cung cấp hình ảnh",
    "No patient associated with this order": "Không có bệnh nhân liên kết với đơn này",
    "Not your assignment": "Đây không phải phân công của bạn",
    "Not your notification": "Đây không phải thông báo của bạn",
    "Notification not found": "Không tìm thấy thông báo",
    "Old Date/Time": "Ngày/giờ cũ",
    "Order not found": "Không tìm thấy đơn",
    "Order updated successfully": "Đã cập nhật đơn thành công",
    "P256DH Key": "Khóa P256DH",
    "PWA Push Notification Subscription": "Đăng ký thông báo đẩy PWA",
    "PWA Staff Notification": "Thông báo nhân viên PWA",
    "Patient not found": "Không tìm thấy bệnh nhân",
    "Please select a cancellation reason": "Vui lòng chọn lý do hủy",
    "Private key in PEM format for Web Push VAPID authentication. Keep this secret!": "Khóa riêng ở định dạng PEM dùng để xác thực Web Push VAPID. Hãy giữ bí mật khóa này!",
    "Product ID required": "Bắt buộc có mã sản phẩm",
    "Product not found": "Không tìm thấy sản phẩm",
    "Public key for Web Push VAPID authentication. Generate with: vapid --applicationServerKey": "Khóa công khai dùng để xác thực Web Push VAPID. Tạo bằng lệnh: vapid --applicationServerKey",
    "Push Endpoint": "Endpoint thông báo đẩy",
    "Quote updated successfully": "Đã cập nhật báo giá thành công",
    "Read": "Đã đọc",
    "Scan this QR code to install the app": "Quét mã QR này để cài đặt ứng dụng",
    "Scroll down in the share menu and tap \"Add to Home Screen\"": "Cuộn xuống trong menu chia sẻ và nhấn \"Thêm vào Màn hình chính\"",
    "Select \"Add to Home Screen\" <span class=\"step-icon ios-add-icon\">➕</span>": "Chọn \"Thêm vào Màn hình chính\" <span class=\"step-icon ios-add-icon\">➕</span>",
    "Select \"Add to Home screen\" <span class=\"step-icon android-install-icon\">⬇</span>": "Chọn \"Thêm vào Màn hình chính\" <span class=\"step-icon android-install-icon\">⬇</span>",
    "Service completed - %s payment collected": "Dịch vụ đã hoàn tất - Đã thu thanh toán %s",
    "Service completed - %s payment noted": "Dịch vụ đã hoàn tất - Đã ghi nhận thanh toán %s",
    "Service completed - Invoice will be sent for later payment": "Dịch vụ đã hoàn tất - Hóa đơn sẽ được gửi để thanh toán sau",
    "Service completed - No invoice created (zero amount)": "Dịch vụ đã hoàn tất - Không tạo hóa đơn (số tiền bằng 0)",
    "Service completed - No payment required": "Dịch vụ đã hoàn tất - Không yêu cầu thanh toán",
    "Service completed successfully": "Dịch vụ đã hoàn tất thành công",
    "Service completed successfully without invoice": "Dịch vụ đã hoàn tất thành công mà không cần hóa đơn",
    "Service started successfully": "Dịch vụ đã bắt đầu thành công",
    "Staff User": "Người dùng nhân viên",
    "Tap \"Add\" to install Viet Uc on your home screen": "Nhấn \"Thêm\" để cài đặt Viet Uc vào màn hình chính",
    "Tap \"Install\" to add Viet Uc to your home screen": "Nhấn \"Cài đặt\" để thêm Viet Uc vào màn hình chính",
    "Tap the Share button <span class=\"step-icon ios-share-icon\">⬆</span>": "Nhấn nút Chia sẻ <span class=\"step-icon ios-share-icon\">⬆</span>",
    "Tap the button above to add Viet Uc to your home screen": "Nhấn nút bên trên để thêm Viet Uc vào màn hình chính",
    "Tap the menu button <span class=\"step-icon android-menu-icon\">⋮</span>": "Nhấn nút menu <span class=\"step-icon android-menu-icon\">⋮</span>",
    "Unknown error": "Lỗi không xác định",
    "User agent string": "Chuỗi user agent",
    "VAPID Contact Email": "Email liên hệ VAPID",
    "VAPID Private Key": "Khóa riêng VAPID",
    "VAPID Public Key": "Khóa công khai VAPID",
    "Visit cancellation reason recorded successfully": "Đã ghi nhận lý do hủy lượt thăm thành công",
    "Visit cancelled successfully": "Đã hủy lượt thăm thành công",
    "Viet Uc will be available as a standalone desktop application": "Viet Uc sẽ có sẵn dưới dạng ứng dụng máy tính độc lập",
    "You should see an install icon (plus sign or download arrow) in your browser's address bar": "Bạn sẽ thấy biểu tượng cài đặt (dấu cộng hoặc mũi tên tải xuống) trên thanh địa chỉ của trình duyệt",
    "You're viewing the <strong>installation guide</strong>. To install the actual app:": "Bạn đang xem <strong>hướng dẫn cài đặt</strong>. Để cài đặt ứng dụng:",
    "⚠️ IMPORTANT: Open the app before installing!": "⚠️ QUAN TRỌNG: Hãy mở ứng dụng trước khi cài đặt!",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()

    mapping = base.base.base.base.load_mapping(args.mapping)
    reviewed = {
        msgid: OVERRIDES.get(
            msgid,
            base.OVERRIDES.get(
                msgid,
                base.base.OVERRIDES.get(
                    msgid,
                    base.base.base.OVERRIDES.get(
                        msgid,
                        base.base.base.base.OVERRIDES.get(
                            msgid,
                            base.base.review_translation(msgstr),
                        ),
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
