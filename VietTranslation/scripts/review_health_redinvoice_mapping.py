#!/usr/bin/env python3
"""Review Vietnamese translations for Odoo 19 health_redinvoice."""

import argparse
import json
import pathlib

import review_health_invoicing_mapping as base


OVERRIDES = {
    '<p>Dear %s,</p><p>Please find attached your VAT (Red) invoice.</p><p>Best regards,<br/>%s</p>': '<p>Kính gửi %s,</p><p>Vui lòng xem hóa đơn VAT (hóa đơn đỏ) được đính kèm.</p><p>Trân trọng,<br/>%s</p>',
    '<span class="hf-redinv-pdf"/> Red Invoice': '<span class="hf-redinv-pdf"/> Hóa đơn đỏ',
    'A Red Invoice (%s) has already been issued for this document. Cancel the existing Red Invoice before generating a new one — re-issuing would create a duplicate invoice at the tax authority.': 'Hóa đơn đỏ (%s) đã được phát hành cho chứng từ này. Hãy hủy hóa đơn đỏ hiện tại trước khi tạo hóa đơn mới vì phát hành lại sẽ tạo hóa đơn trùng tại cơ quan thuế.',
    'Attachment': 'Tệp đính kèm',
    'Auto-create Red Invoice on Post': 'Tự động tạo hóa đơn đỏ khi ghi sổ',
    'Bank Transfer': 'Chuyển khoản ngân hàng',
    'Bank Transfer (TT78)': 'Chuyển khoản ngân hàng (TT78)',
    'Business License': 'Giấy phép kinh doanh',
    'Buyer Bank Account': 'Tài khoản ngân hàng người mua',
    'Buyer Bank Name': 'Ngân hàng người mua',
    'Buyer Country Code': 'Mã quốc gia người mua',
    'Buyer District': 'Quận/huyện người mua',
    'Buyer Document Type': 'Loại giấy tờ người mua',
    'Buyer Legal Name': 'Tên pháp lý người mua',
    'Buyer Opt-out of Invoice Delivery': 'Người mua không nhận hóa đơn',
    'Buyer Postal Code': 'Mã bưu chính người mua',
    'Cancelled': 'Đã hủy',
    'Cash': 'Tiền mặt',
    'Cash (TT78)': 'Tiền mặt (TT78)',
    'Cash/Bank Transfer': 'Tiền mặt/Chuyển khoản',
    'Cash/Bank Transfer (TT78)': 'Tiền mặt/Chuyển khoản (TT78)',
    'Cloud CA': 'Chữ ký số từ xa',
    'Company': 'Công ty',
    'Created by': 'Được tạo bởi',
    'Created on': 'Ngày tạo',
    'Credentials & Defaults': 'Thông tin xác thực và giá trị mặc định',
    'Credit': 'Ghi nợ',
    'Customer': 'Khách hàng',
    'Date': 'Ngày',
    'Default Exchange User': 'Người dùng chuyển đổi mặc định',
    'Default Invoice Series': 'Ký hiệu hóa đơn mặc định',
    'Default Template Code': 'Mã mẫu mặc định',
    'Download': 'Tải xuống',
    'Download Converted PDF': 'Tải PDF đã chuyển đổi',
    'Email Red Invoice': 'Gửi email hóa đơn đỏ',
    'Email to Client': 'Gửi email cho khách hàng',
    'Enable Red Invoice': 'Bật hóa đơn đỏ',
    'Endpoint': 'Điểm cuối API',
    'Error Message': 'Thông báo lỗi',
    'Failed': 'Thất bại',
    'Filename': 'Tên tệp',
    'HTTP Code': 'Mã HTTP',
    'Hash String': 'Chuỗi băm',
    'ID Card': 'Căn cước công dân',
    'Invoice': 'Hóa đơn',
    'Invoice Type 1 (TT78)': 'Loại hóa đơn 1 (TT78)',
    'Invoice Type 2': 'Loại hóa đơn 2',
    'Invoice Type 3': 'Loại hóa đơn 3',
    'Invoice Type 4': 'Loại hóa đơn 4',
    'Issued': 'Đã phát hành',
    'Issuing': 'Đang phát hành',
    'Last Updated by': 'Cập nhật lần cuối bởi',
    'Last Updated on': 'Ngày cập nhật gần nhất',
    'Lookup URL': 'URL tra cứu',
    'Master toggle — when unchecked, all Red Invoice functionality is disabled (no API calls, no auto-issue, tax tabs hidden on invoices).': 'Công tắc chính — khi tắt, toàn bộ chức năng hóa đơn đỏ bị vô hiệu hóa (không gọi API, không tự động phát hành và ẩn các tab thuế trên hóa đơn).',
    'Master toggle — when unchecked, all Red Invoice functionality is disabled (no API calls, no auto-issue, tax tabs hidden)': 'Công tắc chính — khi tắt, toàn bộ chức năng hóa đơn đỏ bị vô hiệu hóa (không gọi API, không tự động phát hành và ẩn các tab thuế).',
    'Merchant City (QR78)': 'Thành phố người bán (QR78)',
    'Merchant Code (QR78)': 'Mã người bán (QR78)',
    'Merchant Name (QR78)': 'Tên người bán (QR78)',
    'Name': 'Tên',
    'No PDF available.': 'Chưa có tệp PDF.',
    'No Red Invoice file is available yet for this document.': 'Chưa có tệp hóa đơn đỏ cho chứng từ này.',
    'No issued Red Invoice is linked to this booking.': 'Không có hóa đơn đỏ đã phát hành liên kết với lịch hẹn này.',
    'Not Required': 'Không bắt buộc',
    'Number': 'Số',
    'Open Red Invoice': 'Mở hóa đơn đỏ',
    'Open the issued Red Invoice (VAT e-invoice) for this booking': 'Mở hóa đơn đỏ đã phát hành (hóa đơn VAT điện tử) của lịch hẹn này',
    'Other': 'Khác',
    'PDF URL': 'URL PDF',
    'Passport': 'Hộ chiếu',
    'Patient': 'Bệnh nhân',
    'Payload JSON': 'Dữ liệu JSON gửi đi',
    'Payment Method Name': 'Tên phương thức thanh toán',
    'Pending': 'Đang chờ',
    'Print': 'In',
    'Public verification portal base. The reservation code is appended to build each invoice Lookup URL, e.g. "https://portal.example/lookup?code=".': 'Địa chỉ cổng tra cứu công khai. Mã tra cứu được nối vào để tạo URL tra cứu cho từng hóa đơn, ví dụ: "https://portal.example/lookup?code=".',
    'Reason': 'Lý do',
    'Red Invoice %s': 'Hóa đơn đỏ %s',
    'Red Invoice (Viettel SInvoice)': 'Hóa đơn đỏ (Viettel SInvoice)',
    'Red Invoice API Base URL': 'URL cơ sở API hóa đơn đỏ',
    'Red Invoice Error': 'Lỗi hóa đơn đỏ',
    'Red Invoice File': 'Tệp hóa đơn đỏ',
    'Red Invoice Lookup Base URL': 'URL cơ sở tra cứu hóa đơn đỏ',
    'Red Invoice Manager': 'Quản lý hóa đơn đỏ',
    'Red Invoice No': 'Số hóa đơn đỏ',
    'Red Invoice PDF Preview Wizard': 'Trình xem trước PDF hóa đơn đỏ',
    'Red Invoice Password': 'Mật khẩu hóa đơn đỏ',
    'Red Invoice Payment Method': 'Phương thức thanh toán hóa đơn đỏ',
    'Red Invoice Requests': 'Các yêu cầu hóa đơn đỏ',
    'Red Invoice Series': 'Ký hiệu hóa đơn đỏ',
    'Red Invoice Signing Mode': 'Phương thức ký hóa đơn đỏ',
    'Red Invoice Sync Date': 'Ngày đồng bộ hóa đơn đỏ',
    'Red Invoice Tax Code': 'Mã số thuế hóa đơn đỏ',
    'Red Invoice Template': 'Mẫu hóa đơn đỏ',
    'Red Invoice Type': 'Loại hóa đơn đỏ',
    'Red Invoice Username': 'Tên đăng nhập hóa đơn đỏ',
    'Red Invoice — Failed': 'Hóa đơn đỏ — Thất bại',
    'Red Invoice — Issued': 'Hóa đơn đỏ — Đã phát hành',
    'Red Invoice — Pending': 'Hóa đơn đỏ — Đang chờ',
    'Reservation Code': 'Mã tra cứu',
    'Response Body': 'Nội dung phản hồi',
    'Retry / Generate Red Invoice': 'Thử lại / Tạo hóa đơn đỏ',
    'Retry Count': 'Số lần thử lại',
    'Seller Bank Account': 'Tài khoản ngân hàng người bán',
    'Seller Bank Name': 'Ngân hàng người bán',
    'Seller Country Code': 'Mã quốc gia người bán',
    'Seller District': 'Quận/huyện người bán',
    'Sent': 'Đã gửi',
    'Server Signature (HSM)': 'Chữ ký máy chủ (HSM)',
    'State': 'Trạng thái',
    'Succeeded': 'Thành công',
    'Tax Office Code': 'Mã cơ quan thuế',
    'Total': 'Tổng cộng',
    'Transaction ID': 'Mã giao dịch',
    'Transaction UUID': 'UUID giao dịch',
    'USB Token': 'USB Token',
    'Use Secret Code Mode': 'Sử dụng chế độ mã bí mật',
    'https://api-vinvoice.viettel.vn/services/einvoiceapplication/api': 'https://api-vinvoice.viettel.vn/services/einvoiceapplication/api',
    'https://lookup-portal.example/?code=': 'https://lookup-portal.example/?code=',
    'unknown': 'không xác định',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mapping', type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
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
        json.dumps(reviewed, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(f'Reviewed {len(reviewed)} translations in {args.output}')


if __name__ == '__main__':
    main()
