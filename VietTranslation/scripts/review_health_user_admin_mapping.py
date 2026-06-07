#!/usr/bin/env python3
"""Review Vietnamese translations for Odoo 19 health_user_admin."""

import argparse
import json
import pathlib


OVERRIDES = {
    '<span>Reset Password</span>': '<span>Đặt lại mật khẩu</span>',
    '<span>Staff Details</span>': '<span>Chi tiết nhân viên</span>',
    "A user with email '%s' already exists.": "Người dùng có email '%s' đã tồn tại.",
    'Access & Role': 'Truy cập và vai trò',
    'Access Roles': 'Vai trò truy cập',
    "Access role '%s' contains restricted system groups: %s. These groups cannot be assigned through the tenant interface.": "Vai trò truy cập '%s' chứa các nhóm hệ thống bị hạn chế: %s. Không thể gán các nhóm này qua giao diện đơn vị.",
    'Access roles define what permissions a group of users have.\n                Assign roles to users to control their access.': 'Vai trò truy cập xác định quyền của một nhóm người dùng.\n                Gán vai trò cho người dùng để kiểm soát quyền truy cập của họ.',
    'Add users and assign them access roles to control what they can do in the system.': 'Thêm người dùng và gán vai trò truy cập để kiểm soát các thao tác họ có thể thực hiện trong hệ thống.',
    'Archived': 'Đã lưu trữ',
    'Are you sure you want to deactivate this user?': 'Bạn có chắc chắn muốn vô hiệu hóa người dùng này không?',
    'Can create and manage users, assign access roles,\nand manage role permissions — without access to Settings, \nmodule installation, or system administration.': 'Có thể tạo và quản lý người dùng, gán vai trò truy cập\nvà quản lý quyền của vai trò — không có quyền truy cập Cài đặt,\ncài đặt mô-đun hoặc quản trị hệ thống.',
    'Cancel': 'Hủy',
    "Cannot deactivate system administrator '%s'. Contact your system administrator.": "Không thể vô hiệu hóa quản trị viên hệ thống '%s'. Vui lòng liên hệ quản trị viên hệ thống.",
    "Cannot reset password for system administrator '%s'.": "Không thể đặt lại mật khẩu cho quản trị viên hệ thống '%s'.",
    'Casual/Contract': 'Thời vụ/Hợp đồng',
    'Catchment Province': 'Tỉnh phụ trách',
    'Configure role restrictions': 'Cấu hình giới hạn vai trò',
    'Create New User': 'Tạo người dùng mới',
    'Create User': 'Tạo người dùng',
    'Create User and Employee': 'Tạo người dùng và nhân viên',
    'Create your first access role': 'Tạo vai trò truy cập đầu tiên',
    'Create your first user': 'Tạo người dùng đầu tiên',
    'Created by': 'Được tạo bởi',
    'Created on': 'Ngày tạo',
    'Define fine-grained restrictions for each role: hide menus, \n                disable buttons, restrict exports, and control field visibility.': 'Thiết lập giới hạn chi tiết cho từng vai trò: ẩn menu,\n                vô hiệu hóa nút, hạn chế xuất dữ liệu và kiểm soát khả năng hiển thị trường.',
    'Employment Details': 'Thông tin việc làm',
    'Employment Status': 'Trạng thái làm việc',
    'Employment Type': 'Loại hình làm việc',
    'Full-Time Staff': 'Nhân viên toàn thời gian',
    'Healthcare Facility': 'Cơ sở y tế',
    'Healthcare: User Administrator': 'Chăm sóc sức khỏe: Quản trị người dùng',
    'Is Duty Doctor': 'Là bác sĩ trực',
    'Is Head Nurse': 'Là điều dưỡng trưởng',
    'Is Owner Role': 'Là vai trò chủ sở hữu',
    'Last Updated by': 'Cập nhật lần cuối bởi',
    'Last Updated on': 'Ngày cập nhật gần nhất',
    'Location Assignment': 'Phân công địa điểm',
    'No Employee Record': 'Không có hồ sơ nhân viên',
    'No employee record found for this user.': 'Không tìm thấy hồ sơ nhân viên cho người dùng này.',
    'On Leave': 'Đang nghỉ phép',
    'Part-Time Staff': 'Nhân viên bán thời gian',
    'Password': 'Mật khẩu',
    'Regional Settings': 'Cài đặt khu vực',
    'Role Management': 'Quản lý vai trò',
    'Set initial password': 'Đặt mật khẩu ban đầu',
    'Show Duty Doctor': 'Hiển thị bác sĩ trực',
    'Show Head Nurse': 'Hiển thị điều dưỡng trưởng',
    'Staff Details': 'Chi tiết nhân viên',
    'Suspended': 'Tạm đình chỉ',
    'Terminated': 'Đã chấm dứt',
    'User "%s" created successfully.': 'Đã tạo người dùng "%s" thành công.',
    'You do not have permission to manage users. Contact your administrator.': 'Bạn không có quyền quản lý người dùng. Vui lòng liên hệ quản trị viên.',
    'e.g. +84 123 456 789': 'ví dụ: +84 123 456 789',
    'e.g. John Smith': 'ví dụ: Nguyễn Văn An',
    'e.g. john@company.com': 'ví dụ: an@congty.com',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mapping', type=pathlib.Path)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding='utf-8'))
    reviewed = {
        msgid: OVERRIDES.get(msgid, msgstr)
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
