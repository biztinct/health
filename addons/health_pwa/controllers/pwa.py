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
            }
            for k, v in fallback_map.items():
                l10n_map.setdefault(k, v)

            return request.render('health_pwa.app_shell', {
                'user_id': request.env.user.id,
                'user_name': request.env.user.name,
                'company_name': request.env.company.name,
                'db_name': request.db,
                'user_lang': user_lang,
                'health_pwa_l10n': l10n_map,
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
    
    @http.route('/health_pwa/manifest.json', type='http', auth='user')
    def pwa_manifest(self, **kwargs):
        """PWA Manifest for installation"""
        company = request.env.company
        manifest = {
            "name": f"{company.name} - Health Mobile",
            "short_name": "Health Mobile",
            "description": "Healthcare Mobile Application for Field Workers",
            "start_url": "/health_pwa",
            "display": "standalone",
            "orientation": "portrait-primary",
            "theme_color": "#875A7B",
            "background_color": "#FFFFFF",
            "categories": ["health", "medical", "productivity"],
            "lang": "en-US",
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
                    "name": "Patients",
                    "short_name": "Patients",
                    "description": "View patient list",
                    "url": "/health_pwa#/patients",
                    "icons": [{"src": "/health_pwa/static/icons/patients-96.png", "sizes": "96x96"}]
                },
                {
                    "name": "Field Orders",
                    "short_name": "FSO",
                    "description": "Manage field service orders", 
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
        
        return request.render('health_pwa.install_guide', {
            'is_ios': is_ios,
            'is_android': is_android,
            'is_desktop': is_desktop,
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
