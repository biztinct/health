#!/usr/bin/env python3
"""
Health Module PO File Translator — English → Vietnamese

Comprehensive translator for all health_* Odoo 19 modules.
Handles:
- Empty msgstr entries
- Entries where msgstr == msgid (untranslated)
- Skips code/HTML blocks, proper nouns, Vietnamese text, and technical terms
- Creates backups before modifying
- Generates PO files for modules without them

Usage:
    python3 translate_health_po.py                    # Translate all health_* modules
    python3 translate_health_po.py --dry-run           # Preview without modifying
    python3 translate_health_po.py --stats             # Show stats only
    python3 translate_health_po.py --generate-missing   # Generate PO files for modules without them
"""
import argparse
import os
import re
import shutil
import sys
import glob
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# BASE DIR
# ═══════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════════════════════════════
# COMPREHENSIVE HEALTHCARE TRANSLATION DICTIONARY
# ═══════════════════════════════════════════════════════════════

DICT_HEALTHCARE = {
    # ── Patient / Client Management ──
    "Patient": "Bệnh nhân",
    "Patients": "Bệnh nhân",
    "Patient ID": "Mã bệnh nhân",
    "Patient Name": "Tên bệnh nhân",
    "Patient Details": "Chi tiết bệnh nhân",
    "Patient Management": "Quản lý bệnh nhân",
    "Patient Hub": "Trung tâm bệnh nhân",
    "Patient Location": "Vị trí bệnh nhân",
    "Client": "Khách hàng",
    "Clients": "Khách hàng",
    "Client Info": "Thông tin khách hàng",
    "Client Details": "Chi tiết khách hàng",
    "All Clients": "Tất cả khách hàng",
    "Healthcare": "Chăm sóc sức khỏe",
    "Health": "Sức khỏe",
    "Health Flow": "Luồng y tế",
    "Health Mobile": "Y tế di động",

    # ── Medical Terms ──
    "Diagnosis": "Chẩn đoán",
    "Treatment": "Điều trị",
    "Clinical": "Lâm sàng",
    "Clinical Notes": "Ghi chú lâm sàng",
    "Clinical Observations": "Quan sát lâm sàng",
    "Medical": "Y khoa",
    "Medical History": "Tiền sử bệnh",
    "Medical Record": "Hồ sơ bệnh án",
    "Prescription": "Đơn thuốc",
    "Medication": "Thuốc",
    "Medications": "Thuốc",
    "Symptom": "Triệu chứng",
    "Symptoms": "Triệu chứng",
    "Vitals": "Sinh hiệu",
    "Blood Pressure": "Huyết áp",
    "Heart Rate": "Nhịp tim",
    "Temperature": "Nhiệt độ",
    "Weight": "Cân nặng",
    "Height": "Chiều cao",
    "BMI": "BMI",
    "Allergy": "Dị ứng",
    "Allergies": "Dị ứng",
    "Chronic": "Mãn tính",
    "Acute": "Cấp tính",
    "Surgery": "Phẫu thuật",
    "Therapy": "Trị liệu",
    "Rehabilitation": "Phục hồi chức năng",
    "Palliative": "Chăm sóc giảm nhẹ",
    "Emergency": "Cấp cứu",
    "Referral": "Chuyển viện",
    "Referrals": "Chuyển viện",
    "Referring Doctor": "Bác sĩ giới thiệu",
    "Doctor": "Bác sĩ",
    "Nurse": "Y tá",
    "Therapist": "Kỹ thuật viên trị liệu",
    "Caregiver": "Người chăm sóc",
    "Goal of Care": "Mục tiêu chăm sóc",
    "Nursing": "Điều dưỡng",
    "Nursing Care": "Chăm sóc điều dưỡng",
    "Geriatrics": "Lão khoa",
    "Ambulatory Aid": "Dụng cụ hỗ trợ di chuyển",

    # ── Specific Medical / Symptom Terms ──
    "Chest Pain": "Đau ngực",
    "Cough": "Ho",
    "Fever": "Sốt",
    "Headache": "Đau đầu",
    "Shortness of Breath": "Khó thở",
    "Pain & Discomfort": "Đau và khó chịu",
    "Skin & Dermatological": "Da liễu",
    "Respiratory": "Hô hấp",
    "Neurological": "Thần kinh",
    "Musculoskeletal": "Cơ xương khớp",
    "Digestive": "Tiêu hóa",
    "Cognitive Impairment": "Suy giảm nhận thức",
    "Persistent coughing": "Ho kéo dài",
    "Common Side Effects": "Tác dụng phụ thường gặp",
    "Analgesic": "Thuốc giảm đau",
    "Antibiotic": "Kháng sinh",
    "Antihypertensive": "Thuốc hạ huyết áp",

    # ── Medication Categories ──
    "Monitoring": "Theo dõi",
    "Observance": "Tuân thủ",
    "Scale (1-10)": "Thang điểm (1-10)",
    "Licensing": "Giấy phép hành nghề",
    "Scope": "Phạm vi",
    "Recommended": "Được khuyến nghị",

    # ── Mobility / Assessment ──
    "Gait/Transfer": "Dáng đi/Di chuyển",
    "Impaired (20 points)": "Suy giảm (20 điểm)",
    "Weak (10 points)": "Yếu (10 điểm)",
    "Crutches/Cane/Walker (15 points)": "Nạng/Gậy/Khung tập đi (15 điểm)",
    "Furniture (30 points)": "Bám đồ đạc (30 điểm)",
    "Mobility Issues": "Vấn đề vận động",

    # ── Assessment Ratings ──
    "1 - Poor": "1 - Kém",
    "2 - Fair": "2 - Trung bình",
    "3 - Good": "3 - Tốt",
    "4 - Very Good": "4 - Rất tốt",
    "5 - Excellent": "5 - Xuất sắc",
    "Excellent": "Xuất sắc",
    "Good": "Tốt",
    "Fair": "Trung bình",
    "Poor": "Kém",
    "Major": "Nghiêm trọng",
    "Minor": "Nhẹ",
    "Critical": "Khẩn cấp",

    # ── Field Service / Booking ──
    "Booking": "Đặt lịch",
    "Bookings": "Đặt lịch",
    "Booking Details": "Chi tiết đặt lịch",
    "Booking Calendar": "Lịch đặt hẹn",
    "Confirm Booking": "Xác nhận đặt lịch",
    "Assignment": "Phân công",
    "Assignments": "Phân công",
    "Assignment Dashboard": "Bảng phân công",
    "Staff Assignment": "Phân công nhân viên",
    "Scheduler": "Lịch trình",
    "Visual Scheduler": "Lịch trình trực quan",
    "Staff": "Nhân viên",
    "Staff Availability": "Lịch nhân viên",
    "Workload": "Khối lượng công việc",
    "Staff Workload": "Khối lượng công việc nhân viên",
    "Service Timer": "Bộ đếm thời gian dịch vụ",
    "Field Service": "Dịch vụ hiện trường",
    "Field Orders": "Lệnh dịch vụ",
    "FSO": "Lệnh DVHT",
    "Service": "Dịch vụ",
    "Services": "Dịch vụ",
    "Start Service": "Bắt đầu dịch vụ",
    "Complete Service": "Hoàn tất dịch vụ",
    "Bookings and Assignments": "Đặt lịch và phân công",
    "Search bookings": "Tìm kiếm đặt lịch",
    "Timeline": "Dòng thời gian",
    "Timeline of assignments": "Dòng thời gian phân công",
    "Scheduled Visit": "Lịch thăm khám",
    "Cancel/Refuse Visit": "Hủy/Từ chối lượt thăm",
    "Ready to Start": "Sẵn sàng bắt đầu",
    "Just started": "Vừa bắt đầu",

    # ── FSO Status ──
    "Arrived": "Đã đến",
    "En Route": "Đang trên đường",
    "Deferred": "Hoãn lại",
    "Busy": "Bận",
    "Conflict Detected": "Phát hiện xung đột",
    "Conflicts": "Xung đột",

    # ── FSO Complexity ──
    "Advanced": "Nâng cao",
    "Advanced Complexity": "Độ phức tạp nâng cao",
    "Basic": "Cơ bản",
    "Basic Complexity": "Độ phức tạp cơ bản",
    "Intermediate": "Trung cấp",
    "Intermediate Complexity": "Độ phức tạp trung cấp",
    "Critical Complexity": "Độ phức tạp khẩn cấp",

    # ── FSO Equipment & Transport ──
    "Battery Powered": "Chạy pin",
    "Battery + Mains": "Pin + Điện lưới",
    "Mains Power": "Điện lưới",
    "Calibration": "Hiệu chuẩn",
    "Dimensions": "Kích thước",
    "Manufacturer": "Nhà sản xuất",
    "Diagnostic": "Chẩn đoán",
    "Car": "Ô tô",
    "Bicycle": "Xe đạp",
    "Motorbike": "Xe máy",
    "Physical": "Vật lý",
    "Power": "Nguồn điện",
    "Flexible": "Linh hoạt",

    # ── FSO Staff Roles ──
    "Junior": "Sơ cấp",
    "Expert": "Chuyên gia",
    "Consultant": "Tư vấn viên",
    "Dispatcher": "Điều phối viên",
    "Therapists": "Kỹ thuật viên trị liệu",

    # ── FSO Safety / Precautions ──
    "Airborne Precautions": "Phòng ngừa lây nhiễm qua đường không khí",
    "Enhanced Precautions": "Phòng ngừa tăng cường",
    "Escalation": "Leo thang",
    "Navigation Assistance": "Hỗ trợ dẫn đường",
    "Optimization Insights": "Phân tích tối ưu hóa",
    "AI Predicted Completion": "AI dự đoán hoàn thành",
    "AI Trained": "AI đã huấn luyện",
    "ML Optimization Applied": "Đã áp dụng tối ưu ML",
    "Communications": "Liên lạc",
    "Findings/Issues": "Phát hiện/Vấn đề",

    # ── Schedule / Time Slots ──
    "Break/Lunch": "Nghỉ giải lao/Ăn trưa",
    "Buffer & Travel": "Dự phòng & Di chuyển",
    "Availability": "Khả năng phục vụ",
    "Requires Travel": "Cần di chuyển",
    "Scheduling conflict": "Xung đột lịch trình",

    # ── CRM / Lead Management ──
    "Lead": "Cơ hội",
    "Leads": "Cơ hội",
    "Lead Details": "Chi tiết cơ hội",
    "Opportunity": "Cơ hội kinh doanh",
    "Pipeline": "Quy trình bán hàng",
    "Contact": "Liên hệ",
    "Contacts": "Danh bạ",
    "Contact Details": "Chi tiết liên hệ",
    "Contact Information": "Thông tin liên hệ",
    "All Contacts": "Tất cả liên hệ",
    "Relationship": "Mối quan hệ",
    "Relationships": "Mối quan hệ",
    "Remove Relationship": "Xóa mối quan hệ",
    "No relationships found": "Không tìm thấy mối quan hệ",
    "Representative": "Người đại diện",
    "Payer": "Người thanh toán",
    "Referrer": "Người giới thiệu",
    "Legal Guardian": "Người giám hộ hợp pháp",
    "Family Member": "Thành viên gia đình",
    "Friend": "Bạn bè",
    "Neighbor": "Hàng xóm",
    "Financial Responsibility": "Trách nhiệm tài chính",
    "Financial Responsibility %": "Trách nhiệm tài chính %",
    "Financial Constraints": "Hạn chế tài chính",
    "Financial constraints": "Hạn chế tài chính",
    "Financial": "Tài chính",
    "I am the:": "Tôi là:",
    "Power of Attorney (Giấy ủy quyền)": "Giấy ủy quyền",
    "Inbound Call": "Cuộc gọi đến",
    "Outbound Call": "Cuộc gọi đi",
    "Negotiation": "Đàm phán",
    "Social Media": "Mạng xã hội",
    "Friend/Family": "Bạn bè/Gia đình",
    "Edit Address": "Sửa địa chỉ",
    "Manage leads and activities": "Quản lý cơ hội và hoạt động",

    # ── Communication Channels ──
    "SMS": "Tin nhắn SMS",
    "Email Only": "Chỉ qua Email",

    # ── Invoicing / Financial ──
    "Invoice": "Hóa đơn",
    "Invoices": "Hóa đơn",
    "Invoicing": "Lập hóa đơn",
    "Payment": "Thanh toán",
    "Payments": "Thanh toán",
    "Bank Transfer": "Chuyển khoản ngân hàng",
    "Cash": "Tiền mặt",
    "Card": "Thẻ",
    "AR Reconciled": "Đã đối soát công nợ",
    "Credit Note": "Ghi có",
    "Refund": "Hoàn tiền",
    "Refunded": "Đã hoàn tiền",
    "Outstanding": "Còn nợ",
    "Allocate Automatically": "Phân bổ tự động",
    "Connected": "Đã kết nối",
    "Connecting": "Đang kết nối",
    "Disconnected": "Ngắt kết nối",
    "Consumed": "Đã sử dụng",
    "Consumptions": "Mức tiêu thụ",
    "Exhausted": "Đã hết",
    "Expired": "Hết hạn",
    "Manual": "Thủ công",
    "Offline Submission": "Gửi ngoại tuyến",
    "Submitted": "Đã gửi",
    "Pricing": "Định giá",
    "Pricing Changes": "Thay đổi giá",
    "Pricing Examples": "Ví dụ giá",
    "Travel Expenses": "Chi phí đi lại",
    "Vaccination": "Tiêm chủng",
    "Proof Docs": "Chứng từ",
    "remaining": "còn lại",
    "used": "đã dùng",
    "Verify Invoice": "Xác minh hóa đơn",
    "Save Quote": "Lưu báo giá",
    "Quote": "Báo giá",

    # ── MISA Integration ──
    "MISA Integration": "Tích hợp MISA",
    "MISA API Key": "Khóa API MISA",
    "MISA ID": "Mã MISA",
    "MISA Server URL": "URL máy chủ MISA",

    # ── Landing / Dashboard ──
    "Dashboard": "Bảng điều khiển",
    "Landing": "Trang chủ",
    "Home Page": "Trang chủ",
    "Hub": "Trung tâm",
    "Navigation": "Điều hướng",
    "Favorites": "Yêu thích",
    "Has Quote": "Có báo giá",
    "Not specified": "Chưa xác định",
    "Upcoming": "Sắp tới",
    "- Financials": "- Tài chính",
    "Tip:": "Mẹo:",
    "Expires:": "Hết hạn:",
    "Sessions:": "Buổi:",
    "Patient management and client information": "Quản lý bệnh nhân và thông tin khách hàng",
    "Staff scheduling and workload management": "Quản lý lịch và khối lượng công việc nhân viên",
    "Customer relationship management": "Quản lý quan hệ khách hàng",
    "Field service orders and booking management": "Quản lý đặt lịch và dịch vụ hiện trường",
    "Visual scheduling interface": "Giao diện lịch trình trực quan",
    "Manage staff availability": "Quản lý lịch nhân viên",
    "Manage patient records and information": "Quản lý hồ sơ và thông tin bệnh nhân",

    # ── Landing Dashboard Status Labels ──
    "ASSIGNED": "ĐÃ PHÂN CÔNG",
    "BOOKED": "ĐÃ ĐẶT",
    "COMPLETED": "ĐÃ HOÀN THÀNH",
    "IN PROGRESS": "ĐANG THỰC HIỆN",
    "PRIMARY": "CHÍNH",

    # ── Hub/Spoke Labels ──
    "Relations": "Mối quan hệ",
    "Personal details and contact": "Thông tin cá nhân và liên hệ",
    "Address and location": "Địa chỉ và vị trí",
    "Packages": "Gói dịch vụ",
    "Active service packages": "Gói dịch vụ đang hoạt động",
    "Appointments and visits": "Cuộc hẹn và lượt thăm",
    "Financials": "Tài chính",
    "Invoices and payments": "Hóa đơn và thanh toán",
    "Healthcare quote": "Báo giá y tế",
    "Confirm the booking": "Xác nhận đặt lịch",
    "Equipment": "Thiết bị",
    "Required equipment": "Thiết bị yêu cầu",
    "Required Equipment": "Thiết bị yêu cầu",
    "Main booking hub": "Trung tâm đặt lịch chính",
    "Assign staff to booking": "Phân công nhân viên cho đặt lịch",
    "Lead details and contact": "Chi tiết cơ hội và liên hệ",
    "Source": "Nguồn",
    "Lead acquisition source": "Nguồn tiếp nhận cơ hội",
    "Internal Notes": "Ghi chú nội bộ",
    "Notes and requirements": "Ghi chú và yêu cầu",
    "Initial Contact": "Liên hệ ban đầu",

    # ── Zalo Chat ──
    "Zalo Message": "Tin nhắn Zalo",
    "New Zalo Message": "Tin nhắn Zalo mới",
    "Zalo Chat": "Trò chuyện Zalo",
    "Zalo Lead": "Cơ hội Zalo",
    "Zalo Conversations": "Cuộc trò chuyện Zalo",
    "Send Zalo Notification": "Gửi thông báo Zalo",
    "Notification": "Thông báo",
    "You have a new message": "Bạn có tin nhắn mới",
    "Failed to open related record": "Không thể mở bản ghi liên quan",
    "Failed to load conversation": "Không thể tải cuộc trò chuyện",
    "No conversation loaded": "Chưa tải cuộc trò chuyện",
    "Just now": "Vừa xong",
    "Today": "Hôm nay",
    "Yesterday": "Hôm qua",
    "Close dialog clicked": "Đã nhấn đóng hộp thoại",

    # ── VoIP ──
    "Connection Successful": "Kết nối thành công",
    "Successfully connected to VoIP24h API": "Đã kết nối thành công với API VoIP24h",
    "Connection Failed": "Kết nối thất bại",
    "Click to Dial": "Nhấn để gọi",

    # ── Red Invoice ──
    "Red Invoice": "Hóa đơn đỏ",
    "Red Invoice PDF": "PDF hóa đơn đỏ",
    "No Red Invoice PDF is available for this document.": "Không có PDF hóa đơn đỏ cho hồ sơ này.",

    # ── Common / Shared ──
    "Name": "Tên",
    "Description": "Mô tả",
    "Notes": "Ghi chú",
    "Note": "Ghi chú",
    "Status": "Trạng thái",
    "State": "Trạng thái",
    "Type": "Loại",
    "Date": "Ngày",
    "Amount": "Số tiền",
    "Total": "Tổng cộng",
    "Active": "Đang hoạt động",
    "Company": "Công ty",
    "Search": "Tìm kiếm",
    "Cancel": "Hủy",
    "Confirm": "Xác nhận",
    "Draft": "Nháp",
    "Confirmed": "Đã xác nhận",
    "Assigned": "Đã phân công",
    "In Progress": "Đang thực hiện",
    "Completed": "Đã hoàn thành",
    "Cancelled": "Đã hủy",
    "Unknown": "Không xác định",
    "Close": "Đóng",
    "Loading": "Đang tải",
    "Refresh": "Làm mới",
    "Save": "Lưu",
    "Create": "Tạo mới",
    "Edit": "Chỉnh sửa",
    "Delete": "Xóa",
    "View": "Xem",
    "Call": "Gọi",
    "Print": "In",
    "Install": "Cài đặt",

    # ── Address Fields ──
    "Address": "Địa chỉ",
    "No primary facility assigned": "Chưa phân công cơ sở chính",
    "Facility has no coordinates": "Cơ sở không có tọa độ",
    "Failed to load facility": "Không thể tải cơ sở",
    "No driving route found between locations": "Không tìm thấy tuyến đường giữa các vị trí",
    "Location coordinates not found": "Không tìm thấy tọa độ vị trí",
    "Directions API quota exceeded": "Đã vượt quá giới hạn API chỉ đường",
    "Could not calculate route": "Không thể tính toán tuyến đường",
    "No route found": "Không tìm thấy tuyến đường",
    "Base Travel Fee (VND)": "Phí đi lại cơ bản (VND)",

    # ── Validation messages ──
    "Please enter a valid Vietnamese phone number": "Vui lòng nhập số điện thoại Việt Nam hợp lệ",
    "Please enter a valid email address": "Vui lòng nhập địa chỉ email hợp lệ",
    "Unknown error": "Lỗi không xác định",
    "Dashboard refreshed": "Đã làm mới bảng điều khiển",

    # ── Cancellation Reasons ──
    "Extreme weather making travel unsafe": "Thời tiết cực đoan gây nguy hiểm khi di chuyển",
    "Natural disaster": "Thiên tai",
    "Pandemic/Epidemic restrictions": "Hạn chế do đại dịch/dịch bệnh",
    "Severe weather conditions": "Điều kiện thời tiết khắc nghiệt",
    "Lives Alone": "Sống một mình",
    "Logistics": "Hậu cần",
    "Capabilities": "Năng lực",
    "Maintenance": "Bảo trì",

    # ── Time Ranges ──
    "Last 30 Days": "30 ngày qua",
    "Last 7 Days": "7 ngày qua",
    "Once": "Một lần",
    "Numeric": "Số",

    # ── Vietnamese Address Fields (keep as Vietnamese) ──
    "Khu vực đặt tên": "Khu vực đặt tên",
    "Mã tỉnh/thành phố": "Mã tỉnh/thành phố",
    "Phường/Xã": "Phường/Xã",
    "Số căn hộ": "Số căn hộ",
    "Số ngách": "Số ngách",
    "Số ngõ": "Số ngõ",
    "Số nhà": "Số nhà",
    "Tên tiếng Việt": "Tên tiếng Việt",
    "Tên tòa nhà": "Tên tòa nhà",
    "Dân tộc": "Dân tộc",
    "Ông, Bà, Anh, Chị...": "Ông, Bà, Anh, Chị...",
    "BÁO CÁO TUÂN THỦ BỘ Y TẾ": "BÁO CÁO TUÂN THỦ BỘ Y TẾ",

    # ── FSO Report labels ──
    "Skills & Competencies": "Kỹ năng & Năng lực",
    "Recipients & Response": "Người nhận & Phản hồi",
    "Disc.%": "CK %",
    "Unread": "Chưa đọc",

    # ── Action Buttons / Icons ──
    "↩️ Reply": "↩️ Trả lời",
    "✓ Mark Read": "✓ Đánh dấu đã đọc",
    "⬆️ Escalate": "⬆️ Leo thang",
    "🤖 AI Insights": "🤖 Phân tích AI",
    "🤖 AI Optimization Applied": "🤖 Đã áp dụng tối ưu AI",

    # ── Health Flow Actions ──
    "Home Page": "Trang chủ",
    "Manage leads and activities": "Quản lý cơ hội và hoạt động",
    "All Contacts": "Tất cả liên hệ",
    "Action": "Hành động",
    "Audit Log": "Nhật ký kiểm tra",
    "CRM Search": "Tìm kiếm CRM",
    "Staff Assignment Timeline": "Dòng thời gian phân công nhân viên",
    "AR Dashboard": "Bảng công nợ",
    "Payment Transactions": "Giao dịch thanh toán",
    "Pricing Engines": "Công cụ định giá",
    "Package Products": "Sản phẩm gói",
    "Pricing Rules": "Quy tắc giá",
    "Quick Edit Rules": "Quy tắc chỉnh sửa nhanh",
    "Portable Equipment": "Thiết bị di động",
    "Healthcare Staff": "Nhân viên y tế",
    "Healthcare Facilities": "Cơ sở y tế",
    "Catchment Provinces": "Tỉnh phục vụ",
    "Patient Categories": "Danh mục bệnh nhân",
    "Service Types": "Loại dịch vụ",
    "Referral Sources": "Nguồn giới thiệu",
    "Insurance Providers": "Nhà cung cấp bảo hiểm",
    "Urgency Levels": "Mức độ khẩn cấp",
    "Action Not Found": "Không tìm thấy hành động",
    "Action Error": "Lỗi hành động",
    "New Contact": "Liên hệ mới",
    "Contact Wizard Error": "Lỗi trình tạo liên hệ",
    "Follow-up Activities": "Hoạt động theo dõi",
    "Follow-up Activities Error": "Lỗi hoạt động theo dõi",
    "All Contacts Error": "Lỗi tất cả liên hệ",
    "All Clients Error": "Lỗi tất cả khách hàng",
    "New Lead": "Cơ hội mới",
    "All Leads": "Tất cả cơ hội",
    "Planned Activities": "Hoạt động đã lên kế hoạch",
    "CRM Calendar": "Lịch CRM",
    "Continue Follow-up": "Tiếp tục theo dõi",
    "No leads found for this filter.": "Không tìm thấy cơ hội cho bộ lọc này.",
    "Client Acquired": "Khách hàng đã tiếp nhận",
    "Booking Lost": "Đặt lịch bị mất",
    "CRM": "CRM",
    "CRM Action Error": "Lỗi hành động CRM",
    "Client Action Error": "Lỗi hành động khách hàng",
    "Dashboard Not Found": "Không tìm thấy bảng điều khiển",
    "My Dashboard has not been configured yet.": "Bảng điều khiển của tôi chưa được cấu hình.",
    "Dashboard Error": "Lỗi bảng điều khiển",
    "All Bookings": "Tất cả đặt lịch",
    "Draft Bookings Calendar": "Lịch đặt hẹn nháp",
    "Assigned Bookings Calendar": "Lịch đặt hẹn đã phân công",
    "Scheduled Bookings Calendar": "Lịch đặt hẹn đã lên lịch",
    "In Progress Bookings Calendar": "Lịch đặt hẹn đang thực hiện",
    "Completed Bookings Calendar": "Lịch đặt hẹn đã hoàn thành",
    "Booking Action Error": "Lỗi hành động đặt lịch",
    "Booking not found.": "Không tìm thấy đặt lịch.",
    "Booking Dashboard": "Bảng đặt lịch",
    "Error": "Lỗi",
    "Failed to open booking": "Không thể mở đặt lịch",
    "Client not found.": "Không tìm thấy khách hàng.",
    "Client Dashboard": "Bảng khách hàng",
    "Failed to open client": "Không thể mở khách hàng",
    "Lead Dashboard": "Bảng cơ hội",
    "CRM Contact": "Liên hệ CRM",
    "Failed to open lead": "Không thể mở cơ hội",
    "Health Flow Dashboard": "Bảng điều khiển luồng y tế",
    "Contact Name is required.": "Tên liên hệ là bắt buộc.",
    "New Booking": "Đặt lịch mới",
    "CRM Activities": "Hoạt động CRM",
    "Activity Type": "Loại hoạt động",

    # ── Red Invoice ──
    "The stored Red Invoice attachment (%s) is not a PDF file.": "Tệp đính kèm hóa đơn đỏ đã lưu (%s) không phải tệp PDF.",
    "Missing Red Invoice configuration on company.": "Thiếu cấu hình hóa đơn đỏ trên công ty.",
    "No Red Invoice was issued for this document.": "Chưa phát hành hóa đơn đỏ cho hồ sơ này.",
    "Cancellation requested from Odoo": "Yêu cầu hủy từ Odoo",
    "Cancelled from Odoo": "Đã hủy từ Odoo",
    "Cancellation failed: %s": "Hủy thất bại: %s",
    "Red Invoice template code/series not configured.": "Chưa cấu hình mã mẫu/sê-ri hóa đơn đỏ.",
    "No invoice lines available to send to SInvoice. Please add at least one product/service line.": "Không có dòng hóa đơn để gửi SInvoice. Vui lòng thêm ít nhất một dòng sản phẩm/dịch vụ.",
    "Red Invoice Status": "Trạng thái hóa đơn đỏ",
    "Red Invoice Issued": "Đã phát hành hóa đơn đỏ",
    "Red Invoice Pending": "Hóa đơn đỏ đang chờ",
    "Red Invoice Failed": "Hóa đơn đỏ thất bại",
    "Red Invoice State": "Trạng thái hóa đơn đỏ",
    "Generate Red Invoice": "Tạo hóa đơn đỏ",
    "Download Red Invoice": "Tải hóa đơn đỏ",
    "Download PDF": "Tải PDF",
    "Cancel Red Invoice": "Hủy hóa đơn đỏ",
    "Identifiers": "Định danh",
    "Files": "Tệp tin",
    "Red Invoice Log": "Nhật ký hóa đơn đỏ",
    "Credentials & Defaults": "Thông tin xác thực & Mặc định",
    "Credentials &amp; Defaults": "Thông tin xác thực & Mặc định",
    "Seller Payment / QR78": "Thanh toán người bán / QR78",
    "Automation": "Tự động hóa",
    "Red Invoice Request": "Yêu cầu hóa đơn đỏ",
    "Payload": "Dữ liệu gửi",
    "Response": "Phản hồi",
    "Red Invoices": "Hóa đơn đỏ",
    "API Requests": "Yêu cầu API",

    # ── VoIP24h ──
    "Please configure API credentials first": "Vui lòng cấu hình thông tin API trước",
    "Sync Started": "Đã bắt đầu đồng bộ",


    # -- Health Flow Template --
    "Booking Notifications": "Thông báo lịch hẹn",
    "No new notifications": "Không có thông báo mới",
    "Clients": "Khách hàng",
    "Sales &amp; CRM": "Bán hàng &amp; CRM",
    "Bookings": "Lịch hẹn",
    "Invoicing": "Hóa đơn",
    "Analytics": "Phân tích",
    "Audit": "Kiểm tra",
    "Admin": "Quản trị",
    "CRM Search": "Tìm kiếm CRM",
    "Booking Search": "Tìm kiếm lịch hẹn",
    "Search by name, phone, or email...": "Tìm theo tên, số điện thoại, hoặc email...",
    "Search by client name, phone, or booking code...": "Tìm theo tên khách hàng, số điện thoại, hoặc mã lịch hẹn...",
    "Merge ": "Gộp ",
    " contacts": " liên hệ",
    "Contacts": "Liên hệ",
    "No CRM results found": "Không tìm thấy kết quả CRM",
    "No bookings found": "Không tìm thấy lịch hẹn",

    # -- Wizards --
    "Detailed Reason": "Lý do chi tiết",
    "Their Relationship to Client": "Mối quan hệ với khách hàng",
    "Reported By (us)": "Được báo cáo bởi (chúng tôi)",
    "Cancellation Reason": "Lý do hủy",
    "Recorded At": "Được ghi lại lúc",
    "Reschedule?": "Lên lịch lại?",
    "Client wants to reschedule?": "Khách hàng muốn lên lịch lại?",
    "→ Select": "→ Chọn",
    "Position/Role": "Vị trí/Vai trò",
    "Name (on client side)": "Tên (Phía khách hàng)",
    "Reason Category": "Danh mục lý do",
    "Reschedule Preferences": "Sở thích lên lịch lại",
    "Who Cancelled?": "Người hủy?",
    "Record Cancellation": "Ghi nhận hủy",
    "Create Booking": "Tạo lịch hẹn",
    "Client Details": "Chi tiết khách hàng",
    "This is a New Client": "Đây là khách hàng mới",
    "Select Client": "Chọn khách hàng",
    "New Client Information": "Thông tin khách hàng mới",
    "Full Name": "Họ và tên",
    "Gender": "Giới tính",
    "Date of Birth": "Ngày sinh",
    "Address": "Địa chỉ",
    "Edit Address": "Sửa địa chỉ",
    "Service Requirements": "Yêu cầu dịch vụ",
    "Service Selection": "Chọn dịch vụ",
    "Category": "Danh mục",
    "Sub-Category": "Danh mục phụ",
    "Service Location": "Vị trí dịch vụ",
    "Service Notes": "Ghi chú dịch vụ",
    "Commission Details": "Chi tiết hoa hồng",
    "Commission Due To": "Hoa hồng cho",
    "Commission %": "% Hoa hồng",
    "Service Fee (VND)": "Phí dịch vụ (VNĐ)",
    "Booking Details": "Chi tiết lịch hẹn",
    "Date &amp; Time": "Ngày & Giờ",
    "Date": "Ngày",
    "Time": "Giờ",
    "Duration (Hours)": "Thời lượng (Giờ)",
    "Additional Notes": "Ghi chú bổ sung",
    "Assign Booking (Optional)": "Phân công (Tùy chọn)",
    "Assign To": "Phân công cho",
    "Instructions": "Hướng dẫn",
    "Booking Summary": "Tóm tắt lịch hẹn",
    "Client": "Khách hàng",
    "Service": "Dịch vụ",
    "Back to Contact": "Quay lại liên hệ",
    "Previous": "Trang trước",
    "Next": "Trang sau",
    "Finish &amp; Create Booking": "Hoàn tất & Tạo lịch hẹn",
    "Cancel": "Hủy",
    "House Number": "Số nhà",
    "Street": "Đường",
    "Alley/Lane": "Ngõ/Hẻm",
    "Sub-Alley": "Ngách",
    "Ward/Commune": "Phường/Xã",
    "District": "Quận/Huyện",
    "City/Province": "Tỉnh/Thành phố",
    "Building Name": "Tên tòa nhà",
    "Apartment/Unit": "Căn hộ/Phòng",
    "Save Address": "Lưu địa chỉ",
    "Available Clients": "Khách hàng hiện có",
    "Create New Client": "Tạo khách hàng mới",
    "Select Existing Client": "Chọn khách hàng có sẵn",
    "Select This Client": "Chọn khách hàng này",
    "Associated Client": "Khách hàng liên kết",
    "Associated Leads": "Tiềm năng liên kết",
    "Continue as New Contact": "Tiếp tục tạo mới",
    "Contact ID": "Mã liên hệ",
    "Client ID": "Mã khách hàng",
    "Lead ID": "Mã tiềm năng",
    "Select Contact": "Chọn liên hệ",
    "Select": "Chọn",
    "Additional Information": "Thông tin bổ sung",
    "Confirm Escalation": "Xác nhận chuyển cấp",
    "Consultation from": "Tư vấn từ",
    "Escalate Contact": "Chuyển cấp liên hệ",
    "Escalate To": "Chuyển cấp đến",
    "Escalation Details": "Chi tiết chuyển cấp",
    "Person": "Người",
    "Reason for Escalation": "Lý do chuyển cấp",
    "Reason": "Lý do",
    "Send Consultation Request": "Gửi yêu cầu tư vấn",
    "Specific Person (Optional)": "Người cụ thể (Tùy chọn)",
    "Close": "Đóng",
    "Follow-up Activities": "Hoạt động theo dõi",
    "Add Relationship": "Thêm mối quan hệ",
    "Alternative Telephone": "Số điện thoại thay thế",
    "Home Address": "Địa chỉ nhà",
    "Other Contact Details": "Chi tiết liên hệ khác",
    "Referrer Details": "Chi tiết người giới thiệu",
    "Representative Address": "Địa chỉ người đại diện",
    "Representative Details": "Chi tiết người đại diện",
    "Select Representative": "Chọn người đại diện",
    "Tax Number": "Mã số thuế",

    "Call history synchronization has been initiated": "Đã bắt đầu đồng bộ lịch sử cuộc gọi",
    "Sync failed: %s": "Đồng bộ thất bại: %s",
    "Match to Contact": "Khớp với liên hệ",
    "Please match this call to a contact or lead first": "Vui lòng khớp cuộc gọi này với liên hệ hoặc cơ hội trước",
    "Activity Created": "Đã tạo hoạt động",
    "No recording available for this call": "Không có bản ghi âm cho cuộc gọi này",
    "Download Started": "Đã bắt đầu tải xuống",
    "Recording download initiated": "Đã bắt đầu tải bản ghi âm",
    "Download failed: %s": "Tải xuống thất bại: %s",
    "Recording not available": "Bản ghi âm không khả dụng",
    "VoIP is not configured. Please contact your administrator.": "VoIP chưa được cấu hình. Vui lòng liên hệ quản trị viên.",
    "Call functionality is disabled. Please contact your administrator.": "Chức năng gọi điện đã tắt. Vui lòng liên hệ quản trị viên.",
    "Outgoing calls are disabled. Please contact your administrator.": "Cuộc gọi đi đã tắt. Vui lòng liên hệ quản trị viên.",
    "No phone number available for this lead.": "Không có số điện thoại cho cơ hội này.",
    "Call Initiated": "Đã bắt đầu cuộc gọi",
    "Calling %s...": "Đang gọi %s...",
    'This contact is marked as "Do Not Call".': 'Liên hệ này được đánh dấu "Không gọi".',
    "No phone number available for this contact.": "Không có số điện thoại cho liên hệ này.",
    "Call Logs": "Nhật ký cuộc gọi",
    "Call Log": "Nhật ký cuộc gọi",
    "Match Contact": "Khớp liên hệ",
    "Create Lead": "Tạo cơ hội",
    "Create Activity": "Tạo hoạt động",
    "Play Recording": "Phát bản ghi âm",
    "Call Information": "Thông tin cuộc gọi",
    "Timing": "Thời gian",
    "Phone Numbers": "Số điện thoại",
    "CRM Integration": "Tích hợp CRM",
    "Recording": "Bản ghi âm",
    "Activity": "Hoạt động",
    "Notes & Outcome": "Ghi chú & Kết quả",
    "Notes &amp; Outcome": "Ghi chú & Kết quả",
    "Recordings": "Bản ghi âm",
    "Play": "Phát",
    "Incoming": "Đến",
    "Outgoing": "Đi",
    "Missed": "Nhỡ",
    "Answered": "Đã nghe",
    "Has Recording": "Có bản ghi âm",
    "Group By": "Nhóm theo",
    "Direction": "Hướng",
    "Call Type": "Loại cuộc gọi",
    "VoIP24h Configuration": "Cấu hình VoIP24h",
    "Test Connection": "Kiểm tra kết nối",
    "Sync Now": "Đồng bộ ngay",
    "API Configuration": "Cấu hình API",
    "Credentials": "Thông tin xác thực",
    "API Settings": "Cài đặt API",
    "Call Functionality": "Chức năng gọi điện",
    "Master Control": "Điều khiển chính",
    "Outgoing Calls": "Cuộc gọi đi",
    "Incoming Calls": "Cuộc gọi đến",
    "Webhooks": "Webhook",
    "Sync Settings": "Cài đặt đồng bộ",
    "VoIP24h Configurations": "Cấu hình VoIP24h",
    "Calls": "Cuộc gọi",
    "VoIP": "VoIP",
    "VoIP Settings": "Cài đặt VoIP",
    "Statistics": "Thống kê",
    "VoIP24h": "VoIP24h",
    "All Calls": "Tất cả cuộc gọi",
    "Missed Calls": "Cuộc gọi nhỡ",
    "Extensions": "Máy nhánh",
    "Configuration": "Cấu hình",
    "VoIP Configuration": "Cấu hình VoIP",
    "VoIP Extensions": "Máy nhánh VoIP",
    "Call Recordings": "Bản ghi cuộc gọi",
    "Download": "Tải xuống",
    "No phone number available": "Không có số điện thoại",

    # ── Zalo ──
    "No Zalo Integration": "Chưa tích hợp Zalo",
    "This contact does not have a Zalo User ID configured. Please link their Zalo account first.": "Liên hệ này chưa có ID Zalo. Vui lòng liên kết tài khoản Zalo trước.",
    "This contact does not have a Zalo User ID. Please link their Zalo account first.": "Liên hệ này chưa có ID Zalo. Vui lòng liên kết tài khoản Zalo trước.",
    "Please enter a message to send.": "Vui lòng nhập tin nhắn để gửi.",
    "Message Sent": "Tin nhắn đã gửi",
    "Zalo message sent successfully to %s": "Đã gửi tin nhắn Zalo thành công đến %s",
    "Failed to send Zalo message: %s": "Không thể gửi tin nhắn Zalo: %s",
    "Please enter a name for the new contact.": "Vui lòng nhập tên cho liên hệ mới.",
    "Created new contact and linked to Zalo conversation: %s": "Đã tạo liên hệ mới và liên kết với cuộc trò chuyện Zalo: %s",
    "Please select a contact to link.": "Vui lòng chọn liên hệ để liên kết.",
    "Linked Zalo conversation to contact: %s": "Đã liên kết cuộc trò chuyện Zalo với liên hệ: %s",
    "Success": "Thành công",
    "Only outgoing messages can be sent": "Chỉ có thể gửi tin nhắn đi",
    "Message has already been sent": "Tin nhắn đã được gửi",
    "No image attachment found": "Không tìm thấy hình ảnh đính kèm",
    "Message type %s not yet implemented": "Loại tin nhắn %s chưa được hỗ trợ",
    "Failed to send message: %s": "Không thể gửi tin nhắn: %s",
    "Only failed messages can be retried": "Chỉ tin nhắn thất bại mới có thể gửi lại",
    "This contact does not have a Zalo User ID configured.": "Liên hệ này chưa có ID Zalo.",
    "Link Zalo User": "Liên kết người dùng Zalo",
    "Please configure App ID and App Secret first.": "Vui lòng cấu hình App ID và App Secret trước.",
    "Failed to exchange authorization code for token: %s": "Không thể đổi mã ủy quyền lấy token: %s",
    "No refresh token available. Please reconnect to Zalo.": "Không có refresh token. Vui lòng kết nối lại Zalo.",
    "Access token refreshed successfully": "Đã làm mới access token thành công",
    "Failed to refresh token: %s": "Không thể làm mới token: %s",
    "Zalo account disconnected successfully": "Đã ngắt kết nối tài khoản Zalo thành công",
    "No access token available. Please connect to Zalo first.": "Không có access token. Vui lòng kết nối Zalo trước.",
    "Connected to Zalo OA: %s": "Đã kết nối Zalo OA: %s",
    "Failed to fetch OA profile": "Không thể tải hồ sơ OA",
    "Connection test failed: %s": "Kiểm tra kết nối thất bại: %s",
    "Webhook Enabled": "Đã bật Webhook",
    "Webhook URL: %s": "URL Webhook: %s",
    "Webhook Disabled": "Đã tắt Webhook",
    "Webhook has been disabled": "Webhook đã được tắt",
    "Link to Contact": "Liên kết với liên hệ",
    "No valid access token available. Please connect to Zalo first.": "Không có access token hợp lệ. Vui lòng kết nối Zalo trước.",
    "Zalo API error: %s": "Lỗi API Zalo: %s",
    "Failed to connect to Zalo API: %s": "Không thể kết nối API Zalo: %s",
    "Link Zalo to Contact": "Liên kết Zalo với liên hệ",
    "Zalo User Information": "Thông tin người dùng Zalo",
    "Link to Existing Contact": "Liên kết với liên hệ hiện có",
    "Create New Contact": "Tạo liên hệ mới",
    "Link Contact": "Liên kết liên hệ",
    "Recipient": "Người nhận",
    "Message Type": "Loại tin nhắn",
    "Send Message": "Gửi tin nhắn",
    "Zalo Configuration": "Cấu hình Zalo",
    "Connect to Zalo": "Kết nối với Zalo",
    "Refresh Token": "Làm mới Token",
    "Disconnect": "Ngắt kết nối",
    "Enable Webhook": "Bật Webhook",
    "Disable Webhook": "Tắt Webhook",
    "Basic Information": "Thông tin cơ bản",
    "API Information": "Thông tin API",
    "Zalo Official Account Credentials": "Thông tin xác thực tài khoản Zalo OA",
    "OAuth Status": "Trạng thái OAuth",
    "Webhook Configuration": "Cấu hình Webhook",
    "OAuth Tokens": "Token OAuth",
    "Webhook Settings": "Cài đặt Webhook",
    "Zalo Configurations": "Cấu hình Zalo",
    "Zalo Chats": "Trò chuyện Zalo",
    "Zalo User ID": "ID người dùng Zalo",
    "Zalo Integration": "Tích hợp Zalo",
    "Zalo Connection": "Kết nối Zalo",
    "View Conversations": "Xem cuộc trò chuyện",
    "View All Conversations": "Xem tất cả cuộc trò chuyện",
    "Zalo": "Zalo",
    "Conversations": "Cuộc trò chuyện",
    "Messages": "Tin nhắn",
    "Zalo Settings": "Cài đặt Zalo",
    "Zalo Conversation": "Cuộc trò chuyện Zalo",
    "Open Chat": "Mở trò chuyện",
    "Mark as Read": "Đánh dấu đã đọc",
    "Archive": "Lưu trữ",
    "Unarchive": "Bỏ lưu trữ",
    "Block User": "Chặn người dùng",
    "Zalo User": "Người dùng Zalo",
    "Linked Records": "Bản ghi liên kết",
    "Conversation Info": "Thông tin cuộc trò chuyện",
    "Last Message": "Tin nhắn cuối",
    "Search Conversations": "Tìm kiếm cuộc trò chuyện",
    "Send": "Gửi",
    "Retry": "Thử lại",
    "Message Info": "Thông tin tin nhắn",
    "Sender/Recipient": "Người gửi/Người nhận",
    "Error Info": "Thông tin lỗi",
    "Content": "Nội dung",
    "Attachments": "Tệp đính kèm",
    "Zalo Messages": "Tin nhắn Zalo",
    "Search Messages": "Tìm kiếm tin nhắn",
    "Failed": "Thất bại",
    "Conversation": "Cuộc trò chuyện",
    "Contact Type": "Loại liên hệ",
    "Contact Reason": "Lý do liên hệ",
}

# Terms that should NOT be translated
SKIP_TERMS = {
    'CSV', 'Excel', 'API', 'URL', 'JSON', 'XML', 'XLS', 'XLSX',
    'PDF', 'HTML', 'CSS', 'SQL', 'Python', 'JavaScript',
    'ID', 'OK', 'N/A', 'VIP', 'VND', 'GPS:', 'GPS',
    'Email', 'Facebook', 'Google', 'Zalo', 'SMS',
    'Odoo', 'MISA', 'Viet Uc', 'Viet Uc Logo',
    'Vietnam MOH', 'CDC Guidelines', 'Google Maps route data',
    'Google Meet', 'Zoom',
    'AB+', 'AB-', 'es', 'km radius', 'min)',
    'x multiplier):', '× 100,000 =', '_______________________',
    # Vietnamese ethnic groups (already Vietnamese)
    'Ba Na', 'Chăm', 'Cơ Ho', 'Dao', 'Gia Rai', "H'Mông",
    'Hoa (Chinese)', 'Khmer', 'Mường', 'Nùng', 'Sán Chay',
    'Thái', 'Tày', 'Xơ Đăng', 'Ê Đê',
    'Parking Spaces',
}

# Vietnamese diacritical marks
VIETNAMESE_CHARS = set('ăắằẳẵặâấầẩẫậđêếềểễệôốồổỗộơớờởỡợưứừửữựàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵĂẮẰẲẴẶÂẤẦẨẪẬĐÊẾỀỂỄỆÔỐỒỔỖỘƠỚỜỞỠỢƯỨỪỬỮỰÀÁẢÃẠÈÉẺẼẸÌÍỈĨỊÒÓỎÕỌÙÚỦŨỤỲÝỶỸỴ')


def is_vietnamese_text(text):
    """Check if text contains Vietnamese diacritical characters."""
    return bool(set(text) & VIETNAMESE_CHARS)


def is_code_block(text):
    """Check if the msgid contains code/HTML that shouldn't be translated."""
    code_patterns = [
        r'<[a-z]+[\s>]',       # HTML tags
        r'__custom__\.',        # Python references
        r'class=[\"\'"]',       # CSS classes
        r'def \w+\(',           # Python functions
        r'self\.\w+',           # Python self references
        r'\$\{',               # Template expressions
        r'\bbase\.\w+',        # Odoo XML IDs
        r'^//',                # JS comments
        r'const ',             # JS code
        r'function ',          # JS code
        r'addEventListener',   # JS code
    ]
    for pattern in code_patterns:
        if re.search(pattern, text):
            return True
    return False


def should_skip(msgid):
    """Check if this entry should be skipped."""
    if not msgid or len(msgid.strip()) <= 1:
        return True
    if is_code_block(msgid):
        return True
    stripped = msgid.strip()
    if stripped in SKIP_TERMS:
        return True
    if re.match(r'^[\d\s\.\-\+\/\%\(\)]+$', stripped):
        return True
    return False


def translate_msgid(msgid, dictionary):
    """Try to translate a msgid using the dictionary."""
    stripped = msgid.strip()

    # Exact match (case-sensitive)
    if stripped in dictionary:
        return dictionary[stripped]

    # Exact match (case-insensitive)
    lower = stripped.lower()
    for key, val in dictionary.items():
        if key.lower() == lower:
            return val

    return None


def process_po_file(filepath, dictionary, dry_run=False):
    """
    Process a single PO file, translating empty/untranslated entries.
    Uses in-place msgstr replacement to preserve all #: references and formatting.
    """
    if not os.path.isfile(filepath):
        print(f"  ⚠️  File not found: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    translations_to_apply = {}

    translated_count = 0
    skipped_count = 0
    already_done = 0
    untranslatable = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith('msgid "'):
            msgid_match = re.match(r'msgid "(.*)"$', line)
            if not msgid_match:
                i += 1
                continue

            msgid = msgid_match.group(1)
            msgid_start = i
            i += 1

            while i < len(lines) and lines[i].startswith('"'):
                cont_match = re.match(r'"(.*)"$', lines[i])
                if cont_match:
                    msgid += cont_match.group(1)
                i += 1

            if i < len(lines) and lines[i].startswith('msgstr "'):
                msgstr_match = re.match(r'msgstr "(.*)"$', lines[i])
                if not msgstr_match:
                    i += 1
                    continue

                msgstr = msgstr_match.group(1)
                msgstr_line = i
                i += 1

                while i < len(lines) and lines[i].startswith('"'):
                    cont_match = re.match(r'"(.*)"$', lines[i])
                    if cont_match:
                        msgstr += cont_match.group(1)
                    i += 1

                if not msgid:
                    continue

                # Skip if already translated (non-empty AND different from msgid)
                if msgstr and msgstr != msgid:
                    already_done += 1
                    continue

                if should_skip(msgid):
                    skipped_count += 1
                    continue

                # If msgid is already Vietnamese, set msgstr = msgid
                if is_vietnamese_text(msgid):
                    translations_to_apply[msgstr_line] = msgid
                    translated_count += 1
                    continue

                translation = translate_msgid(msgid, dictionary)
                if translation:
                    translations_to_apply[msgstr_line] = translation
                    translated_count += 1
                else:
                    untranslatable.append(msgid)
            else:
                continue
        else:
            i += 1

    # Apply translations in-place
    if not dry_run and translated_count > 0:
        for line_num, translation in translations_to_apply.items():
            escaped = translation.replace('\\', '\\\\').replace('"', '\\"')
            old_line = lines[line_num]
            if re.match(r'^msgstr ""$', old_line):
                lines[line_num] = f'msgstr "{escaped}"'
            elif re.match(r'^msgstr ".*"$', old_line):
                lines[line_num] = f'msgstr "{escaped}"'

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    return {
        'total': already_done + translated_count + skipped_count + len(untranslatable),
        'already_done': already_done,
        'translated': translated_count,
        'skipped': skipped_count,
        'untranslatable': untranslatable,
    }


def generate_po_file(module_name, module_path):
    """
    Generate a vi_VN.po file for a module by scanning its source code.
    Extracts translatable strings from Python _() calls and XML string= attributes.
    """
    entries = []
    seen_msgids = set()

    # Scan Python files for _() calls
    py_files = glob.glob(os.path.join(module_path, '**', '*.py'), recursive=True)
    for pyfile in py_files:
        relpath = os.path.relpath(pyfile, os.path.dirname(module_path))
        with open(pyfile, 'r', encoding='utf-8') as f:
            content = f.read()
        # Pattern: _("...") or _('...')
        for m in re.finditer(r"""_\(\s*(['"])(.*?)\1\s*\)""", content):
            msgid = m.group(2)
            if msgid and msgid not in seen_msgids:
                seen_msgids.add(msgid)
                # Find line number
                line_num = content[:m.start()].count('\n') + 1
                entries.append({
                    'module': module_name,
                    'reference': f'code:addons/{relpath}:{line_num}',
                    'msgid': msgid,
                })

    # Scan XML files for string= attributes
    xml_files = glob.glob(os.path.join(module_path, '**', '*.xml'), recursive=True)
    for xmlfile in xml_files:
        relpath = os.path.relpath(xmlfile, os.path.dirname(module_path))
        with open(xmlfile, 'r', encoding='utf-8') as f:
            content = f.read()
        for m in re.finditer(r'string="([^"]+)"', content):
            msgid = m.group(1)
            if msgid and msgid not in seen_msgids and len(msgid) > 1:
                seen_msgids.add(msgid)
                entries.append({
                    'module': module_name,
                    'reference': f'model_terms:ir.ui.view,arch_db:{module_name}.view',
                    'msgid': msgid,
                })
        # Also get menu names
        for m in re.finditer(r'<menuitem[^>]+name="([^"]+)"', content):
            msgid = m.group(1)
            if msgid and msgid not in seen_msgids:
                seen_msgids.add(msgid)
                entries.append({
                    'module': module_name,
                    'reference': f'model:ir.ui.menu',
                    'msgid': msgid,
                })

    # Scan JS files for _t() calls and user-facing strings
    js_files = glob.glob(os.path.join(module_path, 'static', '**', '*.js'), recursive=True)
    for jsfile in js_files:
        if 'd3.min.js' in jsfile:
            continue
        relpath = os.path.relpath(jsfile, os.path.dirname(module_path))
        with open(jsfile, 'r', encoding='utf-8') as f:
            content = f.read()
        for m in re.finditer(r'_t\(\s*(["\'])(.*?)\1\s*\)', content):
            msgid = m.group(2)
            if msgid and msgid not in seen_msgids:
                seen_msgids.add(msgid)
                line_num = content[:m.start()].count('\n') + 1
                entries.append({
                    'module': module_name,
                    'reference': f'code:addons/{relpath}:{line_num}',
                    'msgid': msgid,
                })

    if not entries:
        return None

    # Build PO file content
    po_lines = [
        '# Translation of Odoo Server.',
        '# This file contains the translation of the following modules:',
        f'# \t* {module_name}',
        '#',
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: Odoo Server 19.0\\n"',
        '"Report-Msgid-Bugs-To: \\n"',
        f'"POT-Creation-Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}+0000\\n"',
        f'"PO-Revision-Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}+0000\\n"',
        '"Last-Translator: \\n"',
        '"Language-Team: \\n"',
        '"Language: vi_VN\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: \\n"',
        '"Plural-Forms: nplurals=1; plural=0;\\n"',
        '',
    ]

    for entry in entries:
        po_lines.append(f'#. module: {entry["module"]}')
        po_lines.append(f'#: {entry["reference"]}')

        # Escape msgid for PO format
        msgid_escaped = entry['msgid'].replace('\\', '\\\\').replace('"', '\\"')
        po_lines.append(f'msgid "{msgid_escaped}"')

        # Try to translate
        translation = translate_msgid(entry['msgid'], DICT_HEALTHCARE)
        if translation:
            trans_escaped = translation.replace('\\', '\\\\').replace('"', '\\"')
            po_lines.append(f'msgstr "{trans_escaped}"')
        else:
            po_lines.append('msgstr ""')

        po_lines.append('')

    return '\n'.join(po_lines)


def main():
    parser = argparse.ArgumentParser(description='Translate health_* Odoo PO files (EN→VI)')
    parser.add_argument('files', nargs='*', help='PO files to translate')
    parser.add_argument('--dry-run', action='store_true', help='Preview without modifying files')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--show-untranslated', action='store_true', help='Show untranslatable entries')
    parser.add_argument('--generate-missing', action='store_true', help='Generate PO files for modules without them')
    parser.add_argument('--base-dir', default=BASE_DIR, help='Base directory of the Odoo project')
    args = parser.parse_args()

    addons_dir = os.path.join(args.base_dir, 'addons')

    print("═" * 60)
    print("  Health Module PO Translator — English → Vietnamese")
    print("═" * 60)
    print(f"  Dictionary: {len(DICT_HEALTHCARE)} terms")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Phase 1: Generate missing PO files
    if args.generate_missing or not args.files:
        health_modules = sorted(glob.glob(os.path.join(addons_dir, 'health_*')))
        for module_path in health_modules:
            module_name = os.path.basename(module_path)
            po_path = os.path.join(module_path, 'i18n', 'vi_VN.po')
            if not os.path.exists(po_path):
                print(f"  📦 Generating PO file for: {module_name}")
                po_content = generate_po_file(module_name, module_path)
                if po_content:
                    if not args.dry_run:
                        os.makedirs(os.path.join(module_path, 'i18n'), exist_ok=True)
                        with open(po_path, 'w', encoding='utf-8') as f:
                            f.write(po_content)
                        print(f"    ✅ Created: {po_path}")
                    else:
                        entries_count = po_content.count('msgid "') - 1  # subtract header
                        print(f"    Would create {entries_count} entries")
                else:
                    print(f"    ⚠️  No translatable strings found in {module_name}")
        print()

    # Phase 2: Translate all PO files
    if not args.files:
        files = sorted(glob.glob(os.path.join(addons_dir, 'health_*', 'i18n', 'vi_VN.po')))
    else:
        files = args.files

    grand_total = 0
    grand_translated = 0
    all_untranslatable = []

    for filepath in files:
        module = os.path.basename(os.path.dirname(os.path.dirname(filepath)))
        print(f"  📝 Processing: {module}")

        result = process_po_file(filepath, DICT_HEALTHCARE, dry_run=args.dry_run or args.stats)
        if isinstance(result, int):
            continue

        grand_total += result['total']
        grand_translated += result['translated']

        print(f"    Total entries:    {result['total']}")
        print(f"    Already done:     {result['already_done']}")
        print(f"    Newly translated: {result['translated']}")
        print(f"    Skipped (code):   {result['skipped']}")
        print(f"    Untranslatable:   {len(result['untranslatable'])}")

        if args.show_untranslated and result['untranslatable']:
            print(f"    --- Untranslatable entries ---")
            for u in result['untranslatable'][:30]:
                print(f"      • {u[:100]}")
            if len(result['untranslatable']) > 30:
                print(f"      ... and {len(result['untranslatable']) - 30} more")

        all_untranslatable.extend([(module, u) for u in result['untranslatable']])
        print()

    print("═" * 60)
    print(f"  TOTAL: {grand_translated} entries translated across {len(files)} files")
    print(f"  Remaining untranslatable: {len(all_untranslatable)}")
    print("═" * 60)


if __name__ == '__main__':
    main()
