// Health PWA - Utility Functions for PWA Features

window.PWAUtils = {

  // Localization - Vietnamese and English translations
  i18n: {
    vi: {
      // UI Labels
      'Day': 'Ngày',
      'Week': 'Tuần',
      'Month': 'Tháng',
      'Today': 'Hôm nay',
      'Select date': 'Chọn ngày',
      'Loading bookings...': 'Đang tải lịch hẹn...',
      'Loading details...': 'Đang tải chi tiết...',
      'Close': 'Đóng',
      'Booking Details': 'Chi tiết đặt lịch',
      'Booking': 'Lịch hẹn',
      'Patients': 'Bệnh nhân',
      'Profile': 'Hồ sơ',
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
      'Booked': 'Đã đặt lịch',
      'Running Late': 'Trễ lịch',
      'Pending Invoice': 'Chờ hóa đơn',
      'Closed': 'Đã đóng',
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
      'Search patients...': 'Tìm kiếm bệnh nhân...',
      'Loading patients...': 'Đang tải bệnh nhân...',
      'Failed to load patients': 'Không thể tải bệnh nhân',
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
      'No email': 'Không có email',
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

      // Camera messages
      'camera.not_supported': 'Camera không được hỗ trợ trên thiết bị này',
      'camera.permission_denied': 'Quyền truy cập camera bị từ chối',
      'camera.access_failed': 'Không thể truy cập camera',
      'camera.no_file_selected': 'Chưa chọn tệp',

      // Location messages
      'location.not_supported': 'Định vị không được hỗ trợ',
      'location.permission_denied': 'Quyền truy cập vị trí bị từ chối',
      'location.unavailable': 'Vị trí không khả dụng',
      'location.timeout': 'Yêu cầu vị trí hết thời gian',
      'location.failed': 'Không thể lấy vị trí',
      'location.watch_failed': 'Không thể theo dõi vị trí',

      // Notification messages
      'notification.not_supported': 'Thông báo đẩy không được hỗ trợ',
      'notification.permission_not_granted': 'Quyền thông báo chưa được cấp',
      'notification.new_booking': 'Lịch hẹn mới',
      'notification.booking_reminder': 'Nhắc nhở lịch hẹn',
      'notification.booking_cancelled': 'Lịch hẹn đã hủy',
      'notification.status_update': 'Cập nhật trạng thái',
      'notification.view': 'Xem',

      // Installation messages
      'install.cannot_install': 'Không thể cài đặt ứng dụng lúc này',
      'install.use_safari': 'Vui lòng sử dụng Safari để cài đặt trên iOS',
      'install.use_chrome': 'Vui lòng sử dụng Chrome để cài đặt trên Android',
      'install.ios_step1': 'Nhấn nút Chia sẻ',
      'install.ios_step2': 'Chọn "Thêm vào Màn hình chính"',
      'install.ios_step3': 'Nhấn "Thêm"',
      'install.android_step1': 'Nhấn nút menu',
      'install.android_step2': 'Chọn "Thêm vào Màn hình chính"',
      'install.android_step3': 'Nhấn "Cài đặt"',
      'install.desktop_step1': 'Tìm biểu tượng cài đặt',
      'install.desktop_step2': 'Nhấn cài đặt',
      'install.desktop_step3': 'Khởi chạy ứng dụng',

      // Network messages
      'network.offline': 'Bạn đang ngoại tuyến',
      'network.online': 'Đã kết nối lại',
      'network.slow_connection': 'Kết nối chậm được phát hiện',

      // Storage messages
      'storage.quota_exceeded': 'Dung lượng lưu trữ đã đầy',
      'storage.low_space': 'Dung lượng lưu trữ sắp hết'
    },
    en: {
      // UI Labels
      'Day': 'Day',
      'Week': 'Week',
      'Month': 'Month',
      'Today': 'Today',
      'Select date': 'Select date',
      'Loading bookings...': 'Loading bookings...',
      'Loading details...': 'Loading details...',
      'Close': 'Close',
      'Booking Details': 'Booking Details',
      'Booking': 'Booking',
      'Patients': 'Patients',
      'Profile': 'Profile',
      'Scheduled Visit': 'Scheduled Visit',
      'Date & Time:': 'Date & Time:',
      'Services:': 'Services:',
      'Package:': 'Package:',
      'Contact Information': 'Contact Information',
      'Address:': 'Address:',
      'Primary Contact:': 'Primary Contact:',
      'Call': 'Call',
      'View Intake Summary': 'View Intake Summary',
      'Cancel/Refuse Visit': 'Cancel/Refuse Visit',
      'Start Service': 'Start Service',
      'Clinical Notes': 'Clinical Notes',
      'Diagnosis': 'Diagnosis',
      'Type here...': 'Type here...',
      'Referring Doctor': 'Referring Doctor',
      'Goal of Care': 'Goal of Care',
      'Required Equipment': 'Required Equipment',
      'Intake Notes': 'Intake Notes',
      'Verification Notes': 'Verification Notes',
      'Required: Explain the changes made to Qty or Discount...': 'Required: Explain the changes made to Qty or Discount...',
      'Add any general comments about this invoice...': 'Add any general comments about this invoice...',
      'Invoice verified successfully!': 'Invoice verified successfully!',
      'Cancel': 'Cancel',
      'Save Quote': 'Save Quote',
      'Payment': 'Payment',
      'Complete Service - Payment Collection': 'Complete Service - Payment Collection',
      'Payment Timing': 'Payment Timing',
      'Pay Now': 'Pay Now',
      'Pay Later': 'Pay Later',
      'Payment Method': 'Payment Method',
      'Cash': 'Cash',
      'Card': 'Card',
      'Bank Transfer': 'Bank Transfer',
      'Service Notes': 'Service Notes',
      'Enter any additional service or payment notes...': 'Enter any additional service or payment notes...',
      'Create Invoice Now': 'Create Invoice Now',
      'Amount': 'Amount',
      'Now': 'Now',
      'Complete Payment': 'Complete Payment',
      'Not set': 'Not set',
      'Draft': 'Draft',
      'Confirmed': 'Confirmed',
      'Assigned': 'Assigned',
      'In Progress': 'In Progress',
      'Completed': 'Completed',
      'Cancelled': 'Cancelled',
      'Booked': 'Booked',
      'Running Late': 'Running Late',
      'Pending Invoice': 'Pending Invoice',
      'Closed': 'Closed',
      'Unknown': 'Unknown',
      'Staff': 'Staff',
      'Health Mobile': 'Health Mobile',
      'Loading healthcare data...': 'Loading healthcare data...',
      'Page Not Found': 'Page Not Found',
      'The requested page could not be found.': 'The requested page could not be found.',
      'Go to Today': 'Go to Today',
      'Patient Details': 'Patient Details',
      'Unnamed Patient': 'Unnamed Patient',
      'Unknown Status': 'Unknown Status',
      'Basic Information': 'Basic Information',
      'Full Name': 'Full Name',
      'Date of Birth': 'Date of Birth',
      'Age': 'Age',
      'years old': 'years old',
      'Gender': 'Gender',
      'Blood Group': 'Blood Group',
      'Mobile': 'Mobile',
      'Email': 'Email',
      'Address': 'Address',
      'Not specified': 'Not specified',
      'Emergency Contact': 'Emergency Contact',
      'Name': 'Name',
      'Medical Information': 'Medical Information',
      'Known Allergies': 'Known Allergies',
      'Medical History': 'Medical History',
      'Recent Orders': 'Recent Orders',
      'Service Order': 'Service Order',
      'Visit History': 'Visit History',
      'Last Visit': 'Last Visit',
      'Next Visit': 'Next Visit',
      'Patient Not Found': 'Patient Not Found',
      'The requested patient could not be found.': 'The requested patient could not be found.',
      'Back to Patients': 'Back to Patients',
      'Never': 'Never',
      'Yesterday': 'Yesterday',
      'days ago': 'days ago',
      'Week of': 'Week of',
      'No phone number available': 'No phone number available',
      'Location not available': 'Location not available',
      'Phone': 'Phone',
      'Retry': 'Retry',
      'Search patients...': 'Search patients...',
      'Loading patients...': 'Loading patients...',
      'Failed to load patients': 'Failed to load patients',
      'No Patients Found': 'No Patients Found',
      'No patients match your search criteria.': 'No patients match your search criteria.',
      'No patients have been synced yet.': 'No patients have been synced yet.',
      'No address provided': 'No address provided',
      'Loading patient details...': 'Loading patient details...',
      'Error Loading Patient': 'Error Loading Patient',
      'Phone Number': 'Phone Number',
      'Call Now': 'Call Now',
      'Copy Number': 'Copy Number',
      'Clinic phone number not available': 'Clinic phone number not available',
      'Phone number copied to clipboard!': 'Phone number copied to clipboard!',
      'Contact Clinic': 'Contact Clinic',
      'Loading clinic information...': 'Loading clinic information...',
      'Tap "Call Now" to initiate a call to the clinic directly from your phone.': 'Tap "Call Now" to initiate a call to the clinic directly from your phone.',
      'Patient Code': 'Patient Code',
      'Patient Information': 'Patient Information',
      'Age / Gender': 'Age / Gender',
      'Allergies': 'Allergies',
      'Service Information': 'Service Information',
      'Scheduled Time': 'Scheduled Time',
      'Estimated Duration': 'Estimated Duration',
      'Team': 'Team',
      'Priority': 'Priority',
      'No bookings scheduled for this day': 'No bookings scheduled for this day',
      'No bookings scheduled for this week': 'No bookings scheduled for this week',
      'No bookings scheduled for this month': 'No bookings scheduled for this month',
      'Call patient': 'Call patient',
      'Open map': 'Open map',
      'View Quote': 'View Quote',
      'No quote associated with this booking': 'No quote associated with this booking',
      'Proceed to payment collection': 'Proceed to payment collection',
      'Complete Service': 'Complete Service',
      'hours': 'hours',
      'High': 'High',
      'Medium': 'Medium',
      'Low': 'Low',
      'Description': 'Description',
      'Service Status': 'Service Status',
      'Started At': 'Started At',
      'Completed At': 'Completed At',
      'Duration': 'Duration',
      'Elapsed Time': 'Elapsed Time',
      'Clinical Observations': 'Clinical Observations',
      'Enter clinical observations and notes...': 'Enter clinical observations and notes...',
      'Enter diagnosis...': 'Enter diagnosis...',
      'Treatment Performed': 'Treatment Performed',
      'Describe treatment provided...': 'Describe treatment provided...',
      'Medications Prescribed': 'Medications Prescribed',
      'List medications...': 'List medications...',
      'Vital Signs': 'Vital Signs',
      'Blood pressure, temperature, heart rate...': 'Blood pressure, temperature, heart rate...',
      'Service Procedures': 'Service Procedures',
      'Injections': 'Injections',
      'Medications': 'Medications',
      'Wounds': 'Wounds',
      'IV Fluid Bags': 'IV Fluid Bags',
      'Clinical Images': 'Clinical Images',
      'Capture Image': 'Capture Image',
      'Offline': 'Offline',
      'Syncing': 'Syncing',
      'Online': 'Online',
      'Dismiss': 'Dismiss',
      'Welcome back': 'Welcome back',
      'User': 'User',
      'No email': 'No email',
      'Working offline': 'Working offline',
      'Manage patient records': 'Manage patient records',
      'Field Orders': 'Field Orders',
      'View service orders': 'View service orders',
      'Teams': 'Teams',
      'Team management': 'Team management',
      'Sync Data': 'Sync Data',
      'Force full sync of all data': 'Force full sync of all data',
      'Force Full Sync': 'Force Full Sync',
      'Check server data availability': 'Check server data availability',
      'Debug Info': 'Debug Info',
      'No quote available': 'No quote available',
      'Please fill in the clinical notes or take image of the notes to view Quote': 'Please fill in the clinical notes or take image of the notes to view Quote',
      'Please fill in the clinical notes or take image of the notes to Complete this service': 'Please fill in the clinical notes or take image of the notes to Complete this service',
      'Cancellation Reason': 'Cancellation Reason',
      'Select a reason...': 'Select a reason...',
      'Patient-initiated': 'Patient-initiated',
      'Provider-initiated': 'Provider-initiated',
      'System/Technical': 'System/Technical',
      'Emergency': 'Emergency',
      'Cancellation Notes': 'Cancellation Notes',
      'Additional details about the cancellation...': 'Additional details about the cancellation...',
      'Cancellation details will be logged for record-keeping.': 'Cancellation details will be logged for record-keeping.',
      'Go Back': 'Go Back',
      'Cancelling...': 'Cancelling...',
      'Confirm Cancellation': 'Confirm Cancellation',

      // Camera messages
      'camera.not_supported': 'Camera not supported on this device',
      'camera.permission_denied': 'Camera permission denied',
      'camera.access_failed': 'Failed to access camera',
      'camera.no_file_selected': 'No file selected',

      // Location messages
      'location.not_supported': 'Geolocation not supported',
      'location.permission_denied': 'Location permission denied',
      'location.unavailable': 'Location unavailable',
      'location.timeout': 'Location request timeout',
      'location.failed': 'Failed to get location',
      'location.watch_failed': 'Failed to watch location',

      // Notification messages
      'notification.not_supported': 'Push notifications not supported',
      'notification.permission_not_granted': 'Notification permission not granted',
      'notification.new_booking': 'New Booking',
      'notification.booking_reminder': 'Booking Reminder',
      'notification.booking_cancelled': 'Booking Cancelled',
      'notification.status_update': 'Status Update',
      'notification.view': 'View',

      // Installation messages
      'install.cannot_install': 'App cannot be installed at this time',
      'install.use_safari': 'Please use Safari to install on iOS',
      'install.use_chrome': 'Please use Chrome to install on Android',
      'install.ios_step1': 'Tap the Share button',
      'install.ios_step2': 'Select "Add to Home Screen"',
      'install.ios_step3': 'Tap "Add"',
      'install.android_step1': 'Tap the menu button',
      'install.android_step2': 'Select "Add to Home screen"',
      'install.android_step3': 'Tap "Install"',
      'install.desktop_step1': 'Look for the install icon',
      'install.desktop_step2': 'Click install',
      'install.desktop_step3': 'Launch the app',

      // Network messages
      'network.offline': 'You are offline',
      'network.online': 'Back online',
      'network.slow_connection': 'Slow connection detected',

      // Storage messages
      'storage.quota_exceeded': 'Storage quota exceeded',
      'storage.low_space': 'Low storage space'
    },

    t: function(key) {
      const lang = window.healthPWAConfig?.user_lang?.startsWith('vi') ? 'vi' : 'en';
      if (lang === 'vi' && window.healthPWA?.l10n?.[key]) {
        return window.healthPWA.l10n[key];
      }
      return this[lang][key] || this.en[key] || key;
    }
  },

  // Device and platform detection
  device: {
    isIOS: function() {
      return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    },

    isAndroid: function() {
      return /Android/.test(navigator.userAgent);
    },

    isMobile: function() {
      return this.isIOS() || this.isAndroid() || /Mobi|Android/i.test(navigator.userAgent);
    },

    isStandalone: function() {
      return window.matchMedia('(display-mode: standalone)').matches ||
             window.navigator.standalone === true ||
             document.referrer.includes('android-app://');
    },

    getDeviceType: function() {
      if (this.isIOS()) return 'ios';
      if (this.isAndroid()) return 'android';
      return 'desktop';
    },

    // Get iOS version
    getIOSVersion: function() {
      if (!this.isIOS()) return null;

      const match = navigator.userAgent.match(/OS (\d+)_(\d+)_?(\d+)?/);
      if (match) {
        return {
          major: parseInt(match[1], 10),
          minor: parseInt(match[2], 10),
          patch: parseInt(match[3] || 0, 10),
          version: `${match[1]}.${match[2]}${match[3] ? '.' + match[3] : ''}`
        };
      }
      return null;
    },

    // Check if iOS version supports PWA features
    supportsPWA: function() {
      if (this.isIOS()) {
        const version = this.getIOSVersion();
        // PWA support started in iOS 11.3
        if (version) {
          return version.major > 11 || (version.major === 11 && version.minor >= 3);
        }
        return false;
      }
      return true; // Android and desktop generally support PWAs
    },

    // Get browser name
    getBrowser: function() {
      const ua = navigator.userAgent;

      if (ua.includes('Safari') && !ua.includes('Chrome') && !ua.includes('CriOS')) {
        return 'safari';
      }
      if (ua.includes('Chrome') || ua.includes('CriOS')) {
        return 'chrome';
      }
      if (ua.includes('Firefox') || ua.includes('FxiOS')) {
        return 'firefox';
      }
      if (ua.includes('Edge')) {
        return 'edge';
      }
      return 'unknown';
    },

    // Check if using correct browser for PWA installation
    isCorrectBrowser: function() {
      const browser = this.getBrowser();

      if (this.isIOS()) {
        return browser === 'safari';
      }
      if (this.isAndroid()) {
        return browser === 'chrome';
      }
      return true; // Desktop - most browsers support PWA
    },

    supportsCamera: function() {
      return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    },

    supportsGeolocation: function() {
      return !!navigator.geolocation;
    },

    supportsPushNotifications: function() {
      return 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
    }
  },
  
  // Camera utilities
  camera: {
    async requestPermission() {
      if (!PWAUtils.device.supportsCamera()) {
        throw new Error(PWAUtils.i18n.t('camera.not_supported'));
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'environment', // Use back camera
            width: { ideal: 1280 },
            height: { ideal: 720 }
          }
        });

        // Stop the stream immediately as we just wanted to check permission
        stream.getTracks().forEach(track => track.stop());
        return true;

      } catch (error) {
        console.error('Camera permission denied:', error);
        throw new Error(PWAUtils.i18n.t('camera.permission_denied'));
      }
    },
    
    async capturePhoto(options = {}) {
      const {
        facingMode = 'environment',
        width = 1280,
        height = 720,
        quality = 0.8
      } = options;
      
      return new Promise(async (resolve, reject) => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: facingMode,
              width: { ideal: width },
              height: { ideal: height }
            }
          });
          
          // Create video element to display camera feed
          const video = document.createElement('video');
          video.srcObject = stream;
          video.autoplay = true;
          video.playsInline = true; // Important for iOS
          
          // Create canvas for capturing
          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d');
          
          // Wait for video to be ready
          video.addEventListener('loadedmetadata', () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
          });
          
          // Return capture function and cleanup
          resolve({
            video: video,
            capture: () => {
              context.drawImage(video, 0, 0);
              const dataUrl = canvas.toDataURL('image/jpeg', quality);
              
              // Stop camera
              stream.getTracks().forEach(track => track.stop());
              
              return {
                dataUrl: dataUrl,
                blob: PWAUtils.helpers.dataURLtoBlob(dataUrl)
              };
            },
            cleanup: () => {
              stream.getTracks().forEach(track => track.stop());
            }
          });
          
        } catch (error) {
          console.error('Failed to access camera:', error);
          reject(new Error(PWAUtils.i18n.t('camera.access_failed')));
        }
      });
    },

    // Fallback for iOS - use file input
    createFileInput(accept = 'image/*') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = accept;
      input.capture = 'environment'; // Hint for camera

      return new Promise((resolve, reject) => {
        input.addEventListener('change', (event) => {
          const file = event.target.files[0];
          if (file) {
            resolve(file);
          } else {
            reject(new Error(PWAUtils.i18n.t('camera.no_file_selected')));
          }
        });

        input.click();
      });
    }
  },
  
  // Geolocation utilities
  location: {
    async getCurrentPosition(options = {}) {
      if (!PWAUtils.device.supportsGeolocation()) {
        throw new Error(PWAUtils.i18n.t('location.not_supported'));
      }

      const defaultOptions = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000 // 5 minutes
      };

      const geoOptions = { ...defaultOptions, ...options };

      return new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            resolve({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              accuracy: position.coords.accuracy,
              timestamp: position.timestamp
            });
          },
          (error) => {
            let messageKey = 'location.failed';
            switch (error.code) {
              case error.PERMISSION_DENIED:
                messageKey = 'location.permission_denied';
                break;
              case error.POSITION_UNAVAILABLE:
                messageKey = 'location.unavailable';
                break;
              case error.TIMEOUT:
                messageKey = 'location.timeout';
                break;
            }
            reject(new Error(PWAUtils.i18n.t(messageKey)));
          },
          geoOptions
        );
      });
    },

    watchPosition(callback, errorCallback, options = {}) {
      if (!PWAUtils.device.supportsGeolocation()) {
        throw new Error(PWAUtils.i18n.t('location.not_supported'));
      }

      const defaultOptions = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000 // 1 minute
      };

      const geoOptions = { ...defaultOptions, ...options };

      return navigator.geolocation.watchPosition(
        (position) => {
          callback({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: position.timestamp
          });
        },
        (error) => {
          let messageKey = 'location.watch_failed';
          switch (error.code) {
            case error.PERMISSION_DENIED:
              messageKey = 'location.permission_denied';
              break;
            case error.POSITION_UNAVAILABLE:
              messageKey = 'location.unavailable';
              break;
            case error.TIMEOUT:
              messageKey = 'location.timeout';
              break;
          }
          errorCallback(new Error(PWAUtils.i18n.t(messageKey)));
        },
        geoOptions
      );
    },
    
    calculateDistance(lat1, lon1, lat2, lon2) {
      // Haversine formula
      const R = 6371; // Earth's radius in kilometers
      const dLat = PWAUtils.helpers.toRad(lat2 - lat1);
      const dLon = PWAUtils.helpers.toRad(lon2 - lon1);
      
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(PWAUtils.helpers.toRad(lat1)) * Math.cos(PWAUtils.helpers.toRad(lat2)) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c; // Distance in kilometers
    }
  },
  
  // Push notification utilities
  notifications: {
    async requestPermission() {
      if (!PWAUtils.device.supportsPushNotifications()) {
        throw new Error(PWAUtils.i18n.t('notification.not_supported'));
      }

      const permission = await Notification.requestPermission();
      return permission === 'granted';
    },

    async showNotification(title, options = {}) {
      if (Notification.permission !== 'granted') {
        console.warn(PWAUtils.i18n.t('notification.permission_not_granted'));
        return;
      }

      const defaultOptions = {
        icon: '/health_pwa/static/icons/icon-192.png',
        badge: '/health_pwa/static/icons/icon-96.png',
        vibrate: [200, 100, 200],
        tag: 'health-pwa'
      };

      const notificationOptions = { ...defaultOptions, ...options };

      if ('serviceWorker' in navigator) {
        const registration = await navigator.serviceWorker.ready;
        return registration.showNotification(title, notificationOptions);
      } else {
        return new Notification(title, notificationOptions);
      }
    },

    // Helper to show booking notifications with Vietnamese translations
    async showBookingNotification(type, booking) {
      const titleKey = `notification.${type}`;
      const title = PWAUtils.i18n.t(titleKey);

      const body = booking.patient_name || booking.name || '';
      const data = {
        type: type,
        booking_id: booking.id,
        url: `/health_pwa#/bookings/${booking.id}`
      };

      return this.showNotification(title, {
        body: body,
        data: data,
        actions: [
          {
            action: 'view',
            title: PWAUtils.i18n.t('notification.view') || 'View',
            icon: '/health_pwa/static/icons/icon-96.png'
          }
        ]
      });
    }
  },
  
  // Storage utilities
  storage: {
    // Check available storage quota
    async getStorageQuota() {
      if ('storage' in navigator && 'estimate' in navigator.storage) {
        const estimate = await navigator.storage.estimate();
        return {
          quota: estimate.quota,
          usage: estimate.usage,
          available: estimate.quota - estimate.usage,
          usagePercentage: Math.round((estimate.usage / estimate.quota) * 100)
        };
      }
      return null;
    },
    
    // Check if storage is persistent
    async isPersistent() {
      if ('storage' in navigator && 'persist' in navigator.storage) {
        return await navigator.storage.persisted();
      }
      return false;
    },
    
    // Request persistent storage
    async requestPersistent() {
      if ('storage' in navigator && 'persist' in navigator.storage) {
        return await navigator.storage.persist();
      }
      return false;
    }
  },
  
  // Network utilities
  network: {
    isOnline: function() {
      return navigator.onLine;
    },
    
    getConnectionInfo: function() {
      if ('connection' in navigator) {
        const connection = navigator.connection;
        return {
          effectiveType: connection.effectiveType,
          downlink: connection.downlink,
          rtt: connection.rtt,
          saveData: connection.saveData
        };
      }
      return null;
    },
    
    isSlowConnection: function() {
      const info = this.getConnectionInfo();
      if (info) {
        return info.effectiveType === 'slow-2g' || info.effectiveType === '2g';
      }
      return false;
    }
  },
  
  // App installation utilities
  installation: {
    canInstall: function() {
      return window.deferredPrompt !== null;
    },

    async promptInstall() {
      // Check if using correct browser
      if (!PWAUtils.device.isCorrectBrowser()) {
        const device = PWAUtils.device.getDeviceType();
        if (device === 'ios') {
          throw new Error(PWAUtils.i18n.t('install.use_safari'));
        } else if (device === 'android') {
          throw new Error(PWAUtils.i18n.t('install.use_chrome'));
        }
      }

      if (!window.deferredPrompt) {
        throw new Error(PWAUtils.i18n.t('install.cannot_install'));
      }

      window.deferredPrompt.prompt();
      const choiceResult = await window.deferredPrompt.userChoice;
      window.deferredPrompt = null;

      return choiceResult.outcome === 'accepted';
    },

    isInstalled: function() {
      return PWAUtils.device.isStandalone();
    },

    // Get installation instructions based on platform
    getInstructions: function() {
      const device = PWAUtils.device.getDeviceType();
      const browser = PWAUtils.device.getBrowser();

      if (device === 'ios') {
        return {
          platform: 'ios',
          browser: browser,
          needsSafari: browser !== 'safari',
          steps: [
            PWAUtils.i18n.t('install.ios_step1') || 'Tap the Share button',
            PWAUtils.i18n.t('install.ios_step2') || 'Select "Add to Home Screen"',
            PWAUtils.i18n.t('install.ios_step3') || 'Tap "Add"'
          ]
        };
      } else if (device === 'android') {
        return {
          platform: 'android',
          browser: browser,
          needsChrome: browser !== 'chrome',
          steps: [
            PWAUtils.i18n.t('install.android_step1') || 'Tap the menu button',
            PWAUtils.i18n.t('install.android_step2') || 'Select "Add to Home screen"',
            PWAUtils.i18n.t('install.android_step3') || 'Tap "Install"'
          ]
        };
      } else {
        return {
          platform: 'desktop',
          browser: browser,
          steps: [
            PWAUtils.i18n.t('install.desktop_step1') || 'Look for the install icon',
            PWAUtils.i18n.t('install.desktop_step2') || 'Click install',
            PWAUtils.i18n.t('install.desktop_step3') || 'Launch the app'
          ]
        };
      }
    }
  },
  
  // Helper utilities
  helpers: {
    toRad: function(degrees) {
      return degrees * (Math.PI / 180);
    },
    
    dataURLtoBlob: function(dataurl) {
      const arr = dataurl.split(',');
      const mime = arr[0].match(/:(.*?);/)[1];
      const bstr = atob(arr[1]);
      let n = bstr.length;
      const u8arr = new Uint8Array(n);
      
      while (n--) {
        u8arr[n] = bstr.charCodeAt(n);
      }
      
      return new Blob([u8arr], { type: mime });
    },
    
    formatFileSize: function(bytes) {
      if (bytes === 0) return '0 B';
      
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },
    
    formatDistance: function(kilometers) {
      if (kilometers < 1) {
        return Math.round(kilometers * 1000) + ' m';
      }
      return kilometers.toFixed(1) + ' km';
    },
    
    debounce: function(func, wait, immediate) {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          timeout = null;
          if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
      };
    },
    
    throttle: function(func, limit) {
      let inThrottle;
      return function(...args) {
        if (!inThrottle) {
          func.apply(this, args);
          inThrottle = true;
          setTimeout(() => inThrottle = false, limit);
        }
      };
    }
  },
  
  // UI utilities
  ui: {
    showToast: function(message, type = 'info', duration = 3000) {
      // Create toast element
      const toast = document.createElement('div');
      toast.className = `toast toast-${type}`;
      toast.textContent = message;
      
      // Style the toast
      Object.assign(toast.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        background: type === 'error' ? '#f44336' : type === 'success' ? '#4caf50' : '#2196f3',
        color: 'white',
        padding: '12px 20px',
        borderRadius: '4px',
        zIndex: '10000',
        fontSize: '14px',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
        transform: 'translateX(100%)',
        transition: 'transform 0.3s ease'
      });
      
      // Add to DOM
      document.body.appendChild(toast);
      
      // Show toast
      setTimeout(() => {
        toast.style.transform = 'translateX(0)';
      }, 100);
      
      // Hide and remove toast
      setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
          if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
          }
        }, 300);
      }, duration);
    },
    
    showConfirm: function(message, title = 'Confirm') {
      return new Promise((resolve) => {
        const result = confirm(title + '\n\n' + message);
        resolve(result);
      });
    },
    
    vibrate: function(pattern = [200]) {
      if ('vibrate' in navigator) {
        navigator.vibrate(pattern);
      }
    }
  }
};

// Initialize network event listeners
(function initNetworkListeners() {
  if (typeof window !== 'undefined') {
    window.addEventListener('online', () => {
      PWAUtils.ui.showToast(PWAUtils.i18n.t('network.online'), 'success');
      // Trigger sync if available
      if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
        navigator.serviceWorker.ready.then(registration => {
          return registration.sync.register('sync-data');
        }).catch(err => console.log('Background sync failed:', err));
      }
    });

    window.addEventListener('offline', () => {
      PWAUtils.ui.showToast(PWAUtils.i18n.t('network.offline'), 'error', 5000);
    });

    // Check connection speed on load
    if (PWAUtils.network.isSlowConnection()) {
      PWAUtils.ui.showToast(PWAUtils.i18n.t('network.slow_connection'), 'info');
    }
  }
})();

console.log('PWA utilities loaded successfully');
