# -*- coding: utf-8 -*-

import json
from odoo import http
from odoo.http import request


class HealthPWAController(http.Controller):
    """Main PWA Controller for Health Mobile Application"""
    
    @http.route('/health_pwa/debug', type='http', auth='user')
    def pwa_debug(self, **kwargs):
        """Debug endpoint to check if controller is working"""
        return request.make_response("Health PWA Controller is working!")
    
    @http.route('/health_pwa/test', type='http', auth='user', website=True)
    def pwa_test(self, **kwargs):
        """Debug template to test PWA components"""
        return request.render('health_pwa.debug_shell', {
            'user_id': request.env.user.id,
            'user_name': request.env.user.name,
            'company_name': request.env.company.name,
            'db_name': request.db,
        })
    
    @http.route('/health_pwa', type='http', auth='user', website=True)
    def pwa_app(self, **kwargs):
        """Main PWA application entry point"""
        try:
            # Check if user has access to health modules
            if not self._check_health_access():
                return request.render('health_pwa.access_denied')
            
            user_lang = request.env.user.lang or request.lang or 'en_US'
            # Preload translations for this module to avoid frontend fetch issues
            l10n_map = {}
            try:
                translations = request.env['ir.translation'].sudo().search([
                    ('lang', '=', user_lang),
                    ('module', '=', 'health_pwa'),
                    ('src', '!=', False),
                    ('value', '!=', False),
                ])
                l10n_map = {t.src: t.value for t in translations}
            except Exception:
                # If translation model not available yet, continue without preload
                l10n_map = {}

            # Minimal hardcoded fallback for key UI strings if DB preload failed
            fallback_map = {
                'Day': 'Ngày',
                'Week': 'Tuần',
                'Month': 'Tháng',
                'Today': 'Hôm nay',
                'Select date': 'Chọn ngày',
                'Loading bookings...': 'Đang tải lịch hẹn...',
                'Loading details...': 'Đang tải chi tiết...',
                'Close': 'Đóng',
                'Booking Details': 'Chi tiết đặt lịch',
                'Scheduled Visit': 'Lịch thăm khám',
                'Date & Time:': 'Ngày & Giờ:',
                'Services:': 'Dịch vụ:',
                'Package:': 'Gói:',
                'Contact Information': 'Thông tin liên hệ',
                'Address:': 'Địa chỉ:',
                'Primary Contact:': 'Liên hệ chính:',
                'Call': 'Gọi',
                'View Intake Summary': 'Xem tóm tắt tiếp nhận',
                'Cancel/Refuse Visit': 'Hủy/Từ chối lượt thăm',
                'Start Service': 'Bắt đầu dịch vụ',
                'Clinical Notes': 'Ghi chú lâm sàng',
                'Diagnosis': 'Chẩn đoán',
                'Type here...': 'Nhập tại đây...',
                'Referring Doctor': 'Bác sĩ giới thiệu',
                'Goal of Care': 'Mục tiêu chăm sóc',
                'Required Equipment': 'Thiết bị yêu cầu',
                'Intake Notes': 'Ghi chú tiếp nhận',
                'Verification Notes': 'Ghi chú xác minh',
                'Required: Explain the changes made to Qty or Discount...': 'Bắt buộc: Giải thích các thay đổi về Số lượng hoặc Chiết khấu...',
                'Add any general comments about this invoice...': 'Thêm bất kỳ ghi chú chung nào về hóa đơn này...',
                'Invoice verified successfully!': 'Xác minh hóa đơn thành công!',
                'Cancel': 'Hủy',
                'Save Quote': 'Lưu báo giá',
                'Payment': 'Thanh toán',
                'Complete Service - Payment Collection': 'Hoàn tất dịch vụ - Thu tiền',
                'Payment Timing': 'Thời điểm thanh toán',
                'Pay Now': 'Trả ngay',
                'Pay Later': 'Trả sau',
                'Payment Method': 'Phương thức thanh toán',
                'Cash': 'Tiền mặt',
                'Card': 'Thẻ',
                'Bank Transfer': 'Chuyển khoản',
                'Service Notes': 'Ghi chú dịch vụ',
                'Enter any additional service or payment notes...': 'Nhập thêm ghi chú dịch vụ hoặc thanh toán...',
                'Create Invoice Now': 'Tạo hóa đơn ngay',
                'Amount': 'Số tiền',
                'Now': 'Ngay',
                'Complete Payment': 'Hoàn tất thanh toán',
                'Not set': 'Chưa thiết lập',
                'Draft': 'Nháp',
                'Confirmed': 'Đã xác nhận',
                'Assigned': 'Đã phân công',
                'In Progress': 'Đang thực hiện',
                'Completed': 'Đã hoàn thành',
                'Cancelled': 'Đã hủy',
                'Unknown': 'Không xác định',
                'Staff': 'Nhân viên',
                'Health Mobile': 'Health Mobile',
                'Loading healthcare data...': 'Đang tải dữ liệu y tế...',
                'Page Not Found': 'Không tìm thấy trang',
                'The requested page could not be found.': 'Không tìm thấy trang được yêu cầu.',
                'Go to Today': 'Đi đến hôm nay',
                'Patient Details': 'Chi tiết bệnh nhân',
                'Unnamed Patient': 'Bệnh nhân chưa đặt tên',
                'Unknown Status': 'Trạng thái không xác định',
                'Basic Information': 'Thông tin cơ bản',
                'Full Name': 'Họ và tên',
                'Date of Birth': 'Ngày sinh',
                'Age': 'Tuổi',
                'years old': 'tuổi',
                'Gender': 'Giới tính',
                'Blood Group': 'Nhóm máu',
                'Mobile': 'Di động',
                'Email': 'Email',
                'Address': 'Địa chỉ',
                'Not specified': 'Chưa xác định',
                'Emergency Contact': 'Liên hệ khẩn cấp',
                'Name': 'Tên',
                'Medical Information': 'Thông tin y tế',
                'Known Allergies': 'Dị ứng đã biết',
                'Medical History': 'Tiền sử bệnh',
                'Recent Orders': 'Đơn gần đây',
                'Service Order': 'Đơn dịch vụ',
                'Visit History': 'Lịch sử thăm khám',
                'Last Visit': 'Lần thăm khám gần nhất',
                'Next Visit': 'Lần thăm khám tiếp theo',
                'Patient Not Found': 'Không tìm thấy bệnh nhân',
                'The requested patient could not be found.': 'Không tìm thấy bệnh nhân được yêu cầu.',
                'Back to Patients': 'Quay lại danh sách bệnh nhân',
                'Never': 'Chưa từng',
                'Yesterday': 'Hôm qua',
                'days ago': 'ngày trước',
                'Week of': 'Tuần của',
                'No phone number available': 'Không có số điện thoại',
                'Location not available': 'Không có vị trí',
                'Phone': 'Điện thoại',
                'Retry': 'Thử lại',
                'Loading patients...': 'Đang tải bệnh nhân...',
                'No Patients Found': 'Không tìm thấy bệnh nhân',
                'No patients match your search criteria.': 'Không có bệnh nhân nào khớp với tiêu chí tìm kiếm.',
                'No patients have been synced yet.': 'Chưa đồng bộ bệnh nhân nào.',
                'No address provided': 'Chưa có địa chỉ',
                'Loading patient details...': 'Đang tải chi tiết bệnh nhân...',
                'Error Loading Patient': 'Lỗi khi tải bệnh nhân',
                'Phone Number': 'Số điện thoại',
                'Call Now': 'Gọi ngay',
                'Copy Number': 'Sao chép số',
                'Clinic phone number not available': 'Không có số điện thoại phòng khám',
                'Phone number copied to clipboard!': 'Đã sao chép số điện thoại vào clipboard!',
                'Contact Clinic': 'Liên hệ phòng khám',
                'Loading clinic information...': 'Đang tải thông tin phòng khám...',
                'Tap "Call Now" to initiate a call to the clinic directly from your phone.': 'Nhấn "Gọi ngay" để gọi trực tiếp đến phòng khám từ điện thoại của bạn.',
                'Patient Code': 'Mã bệnh nhân',
                'Patient Information': 'Thông tin bệnh nhân',
                'Age / Gender': 'Tuổi / Giới tính',
                'Allergies': 'Dị ứng',
                'Service Information': 'Thông tin dịch vụ',
                'Scheduled Time': 'Thời gian đã lên lịch',
                'Estimated Duration': 'Thời lượng dự kiến',
                'Team': 'Đội',
                'Priority': 'Mức ưu tiên',
                'No bookings scheduled for this day': 'Không có lịch hẹn nào trong ngày này',
                'No bookings scheduled for this week': 'Không có lịch hẹn nào trong tuần này',
                'No bookings scheduled for this month': 'Không có lịch hẹn nào trong tháng này',
                'Call patient': 'Gọi bệnh nhân',
                'Open map': 'Mở bản đồ',
                'View Quote': 'Xem báo giá',
                'No quote associated with this booking': 'Không có báo giá liên kết với lịch hẹn này',
                'Proceed to payment collection': 'Tiếp tục thu tiền',
                'Complete Service': 'Hoàn tất dịch vụ',
                'hours': 'giờ',
                'High': 'Cao',
                'Medium': 'Trung bình',
                'Low': 'Thấp',
                'Description': 'Mô tả',
                'Service Status': 'Trạng thái dịch vụ',
                'Started At': 'Bắt đầu lúc',
                'Completed At': 'Hoàn tất lúc',
                'Duration': 'Thời lượng',
                'Elapsed Time': 'Thời gian đã trôi qua',
                'Clinical Observations': 'Quan sát lâm sàng',
                'Enter clinical observations and notes...': 'Nhập quan sát và ghi chú lâm sàng...',
                'Enter diagnosis...': 'Nhập chẩn đoán...',
                'Treatment Performed': 'Điều trị đã thực hiện',
                'Describe treatment provided...': 'Mô tả điều trị đã cung cấp...',
                'Medications Prescribed': 'Thuốc đã kê',
                'List medications...': 'Liệt kê thuốc...',
                'Vital Signs': 'Dấu hiệu sinh tồn',
                'Blood pressure, temperature, heart rate...': 'Huyết áp, nhiệt độ, nhịp tim...',
                'Service Procedures': 'Thủ thuật dịch vụ',
                'Injections': 'Tiêm',
                'Medications': 'Thuốc',
                'Wounds': 'Vết thương',
                'IV Fluid Bags': 'Túi dịch truyền',
                'Clinical Images': 'Hình ảnh lâm sàng',
                'Capture Image': 'Chụp ảnh',
                'Offline': 'Ngoại tuyến',
                'Syncing': 'Đang đồng bộ',
                'Online': 'Trực tuyến',
                'Dismiss': 'Bỏ qua',
                'Welcome back': 'Chào mừng trở lại',
                'User': 'Người dùng',
                'Working offline': 'Đang làm việc ngoại tuyến',
                'Manage patient records': 'Quản lý hồ sơ bệnh nhân',
                'Field Orders': 'Đơn công việc',
                'View service orders': 'Xem đơn dịch vụ',
                'Teams': 'Đội nhóm',
                'Team management': 'Quản lý đội nhóm',
                'Sync Data': 'Đồng bộ dữ liệu',
                'Force full sync of all data': 'Buộc đồng bộ toàn bộ dữ liệu',
                'Force Full Sync': 'Buộc đồng bộ đầy đủ',
                'Check server data availability': 'Kiểm tra dữ liệu có sẵn trên máy chủ',
                'Debug Info': 'Thông tin gỡ lỗi',
                'No quote available': 'Không có báo giá',
                'Please fill in the clinical notes or take image of the notes to view Quote': 'Vui lòng điền ghi chú lâm sàng hoặc chụp ảnh ghi chú để xem báo giá',
                'Please fill in the clinical notes or take image of the notes to Complete this service': 'Vui lòng điền ghi chú lâm sàng hoặc chụp ảnh ghi chú để hoàn tất dịch vụ này',
                'Cancellation Reason': 'Lý do hủy',
                'Select a reason...': 'Chọn lý do...',
                'Patient-initiated': 'Do bệnh nhân yêu cầu',
                'Provider-initiated': 'Do nhà cung cấp yêu cầu',
                'System/Technical': 'Hệ thống/Kỹ thuật',
                'Emergency': 'Khẩn cấp',
                'Cancellation Notes': 'Ghi chú hủy',
                'Additional details about the cancellation...': 'Thông tin bổ sung về việc hủy...',
                'Cancellation details will be logged for record-keeping.': 'Chi tiết hủy sẽ được ghi lại để lưu hồ sơ.',
                'Go Back': 'Quay lại',
                'Cancelling...': 'Đang hủy...',
                'Confirm Cancellation': 'Xác nhận hủy',
            }
            for k, v in fallback_map.items():
                l10n_map.setdefault(k, v)

            # Check if install overlay should be shown
            show_install_overlay = kwargs.get('install') == '1'

            # Get company phone number for call functionality
            company_phone = request.env.company.phone or ''

            return request.render('health_pwa.app_shell', {
                'user_id': request.env.user.id,
                'user_name': request.env.user.name,
                'company_name': request.env.company.name,
                'company_phone': company_phone,
                'db_name': request.db,
                'user_lang': user_lang,
                'health_pwa_l10n': l10n_map,
                'show_install_overlay': show_install_overlay,
            })
        except Exception as e:
            # Return simple HTML for debugging
            return request.make_response(f"""
                <html>
                <head><title>Health PWA Debug</title></head>
                <body>
                    <h1>Health PWA Debug Info</h1>
                    <p><strong>Error:</strong> {str(e)}</p>
                    <p><strong>User:</strong> {request.env.user.name if request.env.user else 'No user'}</p>
                    <p><strong>Database:</strong> {request.db}</p>
                    <p><a href="/health_pwa/debug">Test Controller</a></p>
                </body>
                </html>
            """)
    
    @http.route('/health_pwa/manifest.json', type='http', auth='public')
    def pwa_manifest(self, **kwargs):
        """PWA Manifest for installation"""
        manifest = {
            "name": "Viet Uc - Ứng dụng Y tế Di động",
            "short_name": "Viet Uc",
            "description": "Ứng dụng di động cho nhân viên y tế làm việc tại gia với khả năng offline",
            "start_url": "/health_pwa/?utm_source=pwa_installed&utm_medium=homescreen",
            "display": "standalone",
            "orientation": "portrait-primary",
            "theme_color": "#875A7B",
            "background_color": "#FFFFFF",
            "color_scheme": "light",
            "categories": ["health", "medical", "productivity"],
            "lang": "vi",
            "scope": "/health_pwa/",
            "icons": [
                {
                    "src": "/health_pwa/static/icons/icon-72.png",
                    "sizes": "72x72",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/health_pwa/static/icons/icon-96.png",
                    "sizes": "96x96",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/health_pwa/static/icons/icon-128.png",
                    "sizes": "128x128",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/health_pwa/static/icons/icon-144.png",
                    "sizes": "144x144",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/health_pwa/static/icons/icon-152.png",
                    "sizes": "152x152",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/health_pwa/static/icons/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/health_pwa/static/icons/icon-384.png",
                    "sizes": "384x384",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "/health_pwa/static/icons/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable"
                }
            ],
            "screenshots": [
                {
                    "src": "/health_pwa/static/screenshots/mobile-1.png",
                    "sizes": "390x844",
                    "type": "image/png",
                    "form_factor": "narrow"
                },
                {
                    "src": "/health_pwa/static/screenshots/tablet-1.png",
                    "sizes": "1024x768",
                    "type": "image/png",
                    "form_factor": "wide"
                }
            ],
            "shortcuts": [
                {
                    "name": "Bệnh nhân",
                    "short_name": "Bệnh nhân",
                    "description": "Xem danh sách bệnh nhân",
                    "url": "/health_pwa#/patients",
                    "icons": [{"src": "/health_pwa/static/icons/patients-96.png", "sizes": "96x96"}]
                },
                {
                    "name": "Đơn hàng",
                    "short_name": "Đơn hàng",
                    "description": "Quản lý đơn dịch vụ tại nhà",
                    "url": "/health_pwa#/orders",
                    "icons": [{"src": "/health_pwa/static/icons/orders-96.png", "sizes": "96x96"}]
                }
            ]
        }
        
        response = request.make_response(
            json.dumps(manifest, indent=2),
            headers=[
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'public, max-age=3600'),
            ]
        )
        return response
    
    @http.route('/health_pwa/service-worker.js', type='http', auth='user')
    def service_worker(self, **kwargs):
        """Service Worker for offline functionality"""
        response = request.make_response(
            request.env['ir.ui.view']._render_template('health_pwa.service_worker_js'),
            headers=[
                ('Content-Type', 'application/javascript'),
                ('Cache-Control', 'no-cache'),
                ('Service-Worker-Allowed', '/health_pwa/'),
            ]
        )
        return response
    
    @http.route('/health_pwa/offline', type='http', auth='user', website=True)
    def offline_page(self, **kwargs):
        """Offline fallback page"""
        return request.render('health_pwa.offline_page')
    
    @http.route('/health_pwa/install', type='http', auth='user', website=True)
    def install_guide(self, **kwargs):
        """Installation guide for different platforms"""
        user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')

        # Detect platform
        is_ios = 'iPhone' in user_agent or 'iPad' in user_agent
        is_android = 'Android' in user_agent
        is_desktop = not (is_ios or is_android)

        # Get user language preference
        user_lang = request.env.user.lang or request.lang or 'en_US'

        return request.render('health_pwa.install_guide', {
            'is_ios': is_ios,
            'is_android': is_android,
            'is_desktop': is_desktop,
            'user_lang': user_lang,
        })
    
    def _check_health_access(self):
        """Check if user has access to health modules"""
        try:
            # Check if user can access health models
            request.env['res.partner'].check_access_rights('read')
            return True
        except:
            return False


# HealthPWAHome class removed to fix backend routing conflicts
# PWA promotion will be handled through other means without overriding /web route
