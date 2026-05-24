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
      'Upcoming Bookings': 'Lịch hẹn sắp tới',
      'No upcoming bookings scheduled': 'Chưa có lịch hẹn sắp tới',
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
      'Clinical Note': 'Ghi chú lâm sàng',
      'New Clinical Note': 'Ghi chú lâm sàng mới',
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
      'Notes': 'Ghi chú',
      'Enter clinical notes...': 'Nhập ghi chú lâm sàng...',
      'No clinical notes yet.': 'Chưa có ghi chú lâm sàng.',
      'Tap the button below to add the first clinical note.': 'Nhấn nút bên dưới để thêm ghi chú lâm sàng đầu tiên.',
      'Add New Clinical Note': 'Thêm ghi chú lâm sàng mới',
      'Attach Photo': 'Đính kèm ảnh',
      'Take Photo': 'Chụp ảnh',
      'Confirm and Save': 'Xác nhận và lưu',
      'Images': 'Hình ảnh',
      'Save Notes': 'Lưu ghi chú',
      'Please provide clinical notes or take a photo before saving': 'Vui lòng nhập ghi chú lâm sàng hoặc chụp ảnh trước khi lưu',
      'Clinical note saved successfully': 'Đã lưu ghi chú lâm sàng thành công',
      'Error saving clinical note:': 'Lỗi khi lưu ghi chú lâm sàng:',
      'Failed to create clinical note': 'Không thể tạo ghi chú lâm sàng',
      'Create Invoice Now': 'Tạo hóa đơn ngay',
      'Amount': 'Số tiền',
      'Now': 'Ngay',
      'Later': 'Sau',
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
      'Not available': 'Không có dữ liệu',
      'Not applicable': 'Không áp dụng',
      'No data': 'Không có dữ liệu',
      'false': 'Không có dữ liệu',
      'female': 'Nữ',
      'male': 'Nam',
      'NEW': 'Mới',
      'N/A': 'Không áp dụng',
      'Trainer': 'Trainer',
      'Staff': 'Nhân viên',
      'Health Mobile': 'Health Mobile',
      'Loading healthcare data...': 'Đang tải dữ liệu y tế...',
      'Page Not Found': 'Không tìm thấy trang',
      'The requested page could not be found.': 'Không tìm thấy trang được yêu cầu.',
      'Go to Today': 'Đi đến hôm nay',
      'Patient Details': 'Chi tiết bệnh nhân',
      'Unnamed Patient': 'Bệnh nhân chưa đặt tên',
      'Unknown Patient': 'Bệnh nhân không xác định',
      'Unknown Client': 'Khách hàng không xác định',
      'Error Loading Order': 'Lỗi khi tải đơn dịch vụ',
      'Back to Orders': 'Quay lại danh sách đơn',
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
      'Next Booking': 'Lịch hẹn tiếp theo',
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
      'Please select a cancellation reason': 'Vui lòng chọn lý do hủy',
      'Visit cancelled successfully': 'Đã hủy lượt thăm thành công',
      'Failed to cancel visit': 'Không thể hủy lượt thăm',
      'Error cancelling visit:': 'Lỗi khi hủy lượt thăm:',
      'Staff unavailable': 'Nhân viên không có sẵn',
      'Equipment unavailable': 'Thiết bị không có sẵn',
      'Severe weather conditions': 'Điều kiện thời tiết nghiêm trọng',
      'Pandemic/Epidemic restrictions': 'Hạn chế do đại dịch/dịch bệnh',
      'Natural disaster': 'Thiên tai',
      'Patient is too ill to attend': 'Bệnh nhân quá yếu để tham dự',
      'Emergency situation': 'Tình huống khẩn cấp',
      'Service no longer needed': 'Dịch vụ không còn cần thiết',
      'Data entry error': 'Lỗi nhập dữ liệu',
      'Emergency/Force Majeure': 'Khẩn cấp/Bất khả kháng',
      'Schedule Next Appointment?': 'Lên lịch hẹn tiếp theo?',
      'No future visits are currently scheduled for': 'Hiện chưa có lượt thăm nào trong tương lai cho',
      'Schedule Next Visit': 'Lên lịch lượt thăm tiếp theo',
      'Client does not need or want a next visit': 'Khách hàng không cần hoặc không muốn lượt thăm tiếp theo',
      'Why is there no future visit?': 'Vì sao không có lượt thăm tiếp theo?',
      '-- Select a reason --': '-- Chọn lý do --',
      'Please explain:': 'Vui lòng giải thích:',
      'Explain why there is no future visit...': 'Giải thích vì sao không có lượt thăm tiếp theo...',
      'Need to Follow up': 'Cần theo dõi',
      'Submit': 'Gửi',
      'Patient died': 'Bệnh nhân đã mất',
      'Patient improved/recovered': 'Bệnh nhân đã cải thiện/phục hồi',
      'Patient admitted to hospital': 'Bệnh nhân đã nhập viện',
      'Patient declined further visits': 'Bệnh nhân từ chối các lượt thăm tiếp theo',
      'Patient moved/relocated': 'Bệnh nhân đã chuyển nơi ở',
      'Referred to another provider': 'Đã chuyển sang nhà cung cấp khác',
      'Other': 'Khác',
      'Next Appointment Details': 'Chi tiết lịch hẹn tiếp theo',
      'Schedule Next Appointment': 'Lên lịch hẹn tiếp theo',
      'Check my schedule': 'Kiểm tra lịch của tôi',
      'Appointment Date & Time': 'Ngày và giờ hẹn',
      'Date': 'Ngày',
      'Time': 'Giờ',
      'Services to be Provided': 'Dịch vụ sẽ cung cấp',
      'Qty:': 'SL:',
      'No services selected yet': 'Chưa chọn dịch vụ nào',
      'Add from Catalog': 'Thêm từ danh mục',
      'Assigned Healthcare Staff': 'Nhân viên y tế được phân công',
      'Booking credit:': 'Tín dụng đặt lịch:',
      'No staff assigned': 'Chưa phân công nhân viên',
      'Booking will be created in CONFIRMED state (unassigned)': 'Lịch hẹn sẽ được tạo ở trạng thái Đã xác nhận (chưa phân công)',
      'Assign different nurse': 'Phân công y tá khác',
      'Services': 'Dịch vụ',
      'Scheduled For': 'Lên lịch cho',
      'item(s)': 'mục',
      'at': 'lúc',
      'Schedule Visit': 'Lên lịch thăm',
      'Select Services from Catalog': 'Chọn dịch vụ từ danh mục',
      'Selected Services': 'Dịch vụ đã chọn',
      'Search Products': 'Tìm kiếm sản phẩm',
      'Product Catalog': 'Danh mục sản phẩm',
      'Search products...': 'Tìm kiếm sản phẩm...',
      'Search by product name or code...': 'Tìm theo tên hoặc mã sản phẩm...',
      'Loading products...': 'Đang tải sản phẩm...',
      'No products found': 'Không tìm thấy sản phẩm',
      'Add': 'Thêm',
      'Code:': 'Mã:',
      'Invoice / Quote': 'Hóa đơn / Báo giá',
      'Home Visit': 'Thăm khám tại nhà',
      'Clinic Visit': 'Thăm khám tại phòng khám',
      'Online Consultation': 'Tư vấn trực tuyến',
      'Emergency Visit': 'Thăm khám khẩn cấp',
      'Service': 'Dịch vụ',
      'Qty': 'SL',
      'QTY': 'SL',
      'Disc %': 'CK %',
      'DISC %': 'CK %',
      'Price': 'Đơn giá',
      'PRICE': 'Đơn giá',
      'Product': 'Dịch vụ',
      'Actions': 'Thao tác',
      'Subtotal': 'Tạm tính',
      'Tax': 'Thuế',
      'Total': 'Tổng cộng',
      'TOTAL': 'Tổng cộng',
      'Save Quote to display updated Total': 'Lưu báo giá để hiển thị tổng tiền đã cập nhật',
      'Add Product': 'Thêm dịch vụ',
      'Location Map': 'Bản đồ vị trí',
      'Live': 'Đang chạy',
      'Started': 'Bắt đầu',
      'Cannot load invoice while offline': 'Không thể tải hóa đơn khi ngoại tuyến',
      'No quote found for this order': 'Không tìm thấy báo giá cho đơn này',
      'Cannot save quote while offline': 'Không thể lưu báo giá khi ngoại tuyến',
      'Error loading quote: ': 'Lỗi khi tải báo giá: ',
      'Cannot load catalog while offline': 'Không thể tải danh mục khi ngoại tuyến',
      'Invoice verified and saved successfully!': 'Đã xác minh và lưu hóa đơn thành công!',
      'Cannot upload images while offline': 'Không thể tải ảnh lên khi ngoại tuyến',
      'Image uploaded successfully!': 'Đã tải ảnh lên thành công!',
      'Failed to upload image: ': 'Không thể tải ảnh lên: ',
      'Error uploading image: ': 'Lỗi khi tải ảnh lên: ',
      'Product added successfully!': 'Đã thêm dịch vụ thành công!',
      'Failed to add product: ': 'Không thể thêm dịch vụ: ',
      'Error adding product: ': 'Lỗi khi thêm dịch vụ: ',
      'Line updated successfully!': 'Đã cập nhật dòng thành công!',
      'Failed to update line: ': 'Không thể cập nhật dòng: ',
      'Error updating line: ': 'Lỗi khi cập nhật dòng: ',
      'Line removed successfully!': 'Đã xóa dòng thành công!',
      'Failed to remove line: ': 'Không thể xóa dòng: ',
      'Error removing line: ': 'Lỗi khi xóa dòng: ',
      'No address available': 'Không có địa chỉ',
      'Please provide a discount reason for: ': 'Vui lòng nhập lý do chiết khấu cho: ',
      'Invoice or Quote is required before completing the service.': 'Cần có hóa đơn hoặc báo giá trước khi hoàn tất dịch vụ.',
      'Alternatively, a service package must be assigned if payment is prepaid.': 'Ngoài ra, cần gán gói dịch vụ nếu thanh toán trả trước.',
      'Invoice or Quote is required before completing the service. Alternatively, a service package must be assigned if payment is prepaid.': 'Cần có hóa đơn hoặc báo giá trước khi hoàn tất dịch vụ. Ngoài ra, cần gán gói dịch vụ nếu thanh toán trả trước.',
      'Service cannot be started because the booking is still in Draft status. Please confirm or assign the booking before starting service.': 'Không thể bắt đầu dịch vụ vì lịch hẹn vẫn ở trạng thái Nháp. Vui lòng xác nhận hoặc phân công lịch hẹn trước khi bắt đầu dịch vụ.',
      'Service cannot be started in the current booking status. Please check the booking before starting service.': 'Không thể bắt đầu dịch vụ ở trạng thái hiện tại. Vui lòng kiểm tra lịch hẹn trước khi bắt đầu dịch vụ.',
      'Cannot complete service in draft state': 'Không thể hoàn tất dịch vụ khi lịch hẹn còn ở trạng thái Nháp.',
      'Cannot complete service in confirmed state': 'Không thể hoàn tất dịch vụ khi lịch hẹn chưa bắt đầu.',
      'Cannot complete service in assigned state': 'Không thể hoàn tất dịch vụ khi lịch hẹn chưa bắt đầu.',
      'Please add verification notes explaining the changes made to Qty or Discount.': 'Vui lòng thêm ghi chú xác minh để giải thích các thay đổi về số lượng hoặc chiết khấu.',
      'Error saving quote: ': 'Lỗi khi lưu báo giá: ',
      'Failed to save quote: ': 'Không thể lưu báo giá: ',
      'Please verify the invoice first and click Save Quote.': 'Vui lòng xác minh hóa đơn trước và nhấn Lưu báo giá.',
      'Error: Server returned status ': 'Lỗi: Máy chủ trả về trạng thái ',
      '. Please try again.': '. Vui lòng thử lại.',
      'Error: Invalid response from server. Details: ': 'Lỗi: Phản hồi từ máy chủ không hợp lệ. Chi tiết: ',
      'Service completed successfully!': 'Hoàn tất dịch vụ thành công!',
      'Error completing payment: ': 'Lỗi khi hoàn tất thanh toán: ',
      'Failed to complete payment: ': 'Không thể hoàn tất thanh toán: ',
      'Error: ': 'Lỗi: ',
      'Error starting service: ': 'Lỗi khi bắt đầu dịch vụ: ',
      'Service started successfully!': 'Bắt đầu dịch vụ thành công!',
      'Failed to start service: ': 'Không thể bắt đầu dịch vụ: ',
      'Please fill in Clinical Notes before completing the service. Click "Clinical Notes" button to add them.': 'Vui lòng nhập ghi chú lâm sàng trước khi hoàn tất dịch vụ. Nhấn nút "Ghi chú lâm sàng" để thêm ghi chú.',
      'Please select a Payment Method before collecting payment.': 'Vui lòng chọn phương thức thanh toán trước khi thu tiền.',
      'No booking selected': 'Chưa chọn lịch hẹn',
      'Failed to complete service: ': 'Không thể hoàn tất dịch vụ: ',
      'Error completing service: ': 'Lỗi khi hoàn tất dịch vụ: ',
      'Please select a reason': 'Vui lòng chọn lý do',
      'Please enter explanation for "Other" reason': 'Vui lòng nhập giải thích cho lý do "Khác"',
      'Noted: Patient does not need future visits': 'Đã ghi nhận: Bệnh nhân không cần các lượt thăm tiếp theo',
      'Failed to submit: ': 'Không thể gửi: ',
      'Error submitting: ': 'Lỗi khi gửi: ',
      'Please select a date': 'Vui lòng chọn ngày',
      'Please select a time': 'Vui lòng chọn giờ',
      'Please add at least one service': 'Vui lòng thêm ít nhất một dịch vụ',
      'Please assign a nurse': 'Vui lòng phân công y tá',
      'Cannot schedule while offline': 'Không thể lên lịch khi ngoại tuyến',
      'Next visit scheduled successfully!': 'Đã lên lịch lượt thăm tiếp theo thành công!',
      'Failed to schedule: ': 'Không thể lên lịch: ',
      'Error scheduling: ': 'Lỗi khi lên lịch: ',
      'Cannot start service while offline': 'Không thể bắt đầu dịch vụ khi ngoại tuyến',
      'Cannot complete service while offline': 'Không thể hoàn tất dịch vụ khi ngoại tuyến',
      'Cannot save clinical notes while offline': 'Không thể lưu ghi chú lâm sàng khi ngoại tuyến',
      'Failed to save clinical notes: ': 'Không thể lưu ghi chú lâm sàng: ',
      'Error saving clinical notes: ': 'Lỗi khi lưu ghi chú lâm sàng: ',
      'Cannot check next visit while offline': 'Không thể kiểm tra lượt thăm tiếp theo khi ngoại tuyến',
      'Failed to check next visit status': 'Không thể kiểm tra trạng thái lượt thăm tiếp theo',
      'Error checking next visit: ': 'Lỗi khi kiểm tra lượt thăm tiếp theo: ',
      'Cannot submit while offline': 'Không thể gửi khi ngoại tuyến',
      'Unknown error': 'Lỗi không xác định',
      'Error:': 'Lỗi:',

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
      'Upcoming Bookings': 'Upcoming Bookings',
      'No upcoming bookings scheduled': 'No upcoming bookings scheduled',
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
      'Clinical Note': 'Clinical Note',
      'New Clinical Note': 'New Clinical Note',
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
      'Notes': 'Notes',
      'Enter clinical notes...': 'Enter clinical notes...',
      'No clinical notes yet.': 'No clinical notes yet.',
      'Tap the button below to add the first clinical note.': 'Tap the button below to add the first clinical note.',
      'Add New Clinical Note': 'Add New Clinical Note',
      'Attach Photo': 'Attach Photo',
      'Take Photo': 'Take Photo',
      'Confirm and Save': 'Confirm and Save',
      'Images': 'Images',
      'Save Notes': 'Save Notes',
      'Please provide clinical notes or take a photo before saving': 'Please provide clinical notes or take a photo before saving',
      'Clinical note saved successfully': 'Clinical note saved successfully',
      'Error saving clinical note:': 'Error saving clinical note:',
      'Failed to create clinical note': 'Failed to create clinical note',
      'Create Invoice Now': 'Create Invoice Now',
      'Amount': 'Amount',
      'Now': 'Now',
      'Later': 'Later',
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
      'Not available': 'Not available',
      'Not applicable': 'Not applicable',
      'No data': 'No data',
      'false': 'Not available',
      'female': 'female',
      'male': 'male',
      'NEW': 'NEW',
      'N/A': 'N/A',
      'Trainer': 'Trainer',
      'Staff': 'Staff',
      'Health Mobile': 'Health Mobile',
      'Loading healthcare data...': 'Loading healthcare data...',
      'Page Not Found': 'Page Not Found',
      'The requested page could not be found.': 'The requested page could not be found.',
      'Go to Today': 'Go to Today',
      'Patient Details': 'Patient Details',
      'Unnamed Patient': 'Unnamed Patient',
      'Unknown Patient': 'Unknown Patient',
      'Unknown Client': 'Unknown Client',
      'Error Loading Order': 'Error Loading Order',
      'Back to Orders': 'Back to Orders',
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
      'Next Booking': 'Next Booking',
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
      'Please select a cancellation reason': 'Please select a cancellation reason',
      'Visit cancelled successfully': 'Visit cancelled successfully',
      'Failed to cancel visit': 'Failed to cancel visit',
      'Error cancelling visit:': 'Error cancelling visit:',
      'Staff unavailable': 'Staff unavailable',
      'Equipment unavailable': 'Equipment unavailable',
      'Severe weather conditions': 'Severe weather conditions',
      'Pandemic/Epidemic restrictions': 'Pandemic/Epidemic restrictions',
      'Natural disaster': 'Natural disaster',
      'Patient is too ill to attend': 'Patient is too ill to attend',
      'Emergency situation': 'Emergency situation',
      'Service no longer needed': 'Service no longer needed',
      'Data entry error': 'Data entry error',
      'Emergency/Force Majeure': 'Emergency/Force Majeure',
      'Schedule Next Appointment?': 'Schedule Next Appointment?',
      'No future visits are currently scheduled for': 'No future visits are currently scheduled for',
      'Schedule Next Visit': 'Schedule Next Visit',
      'Client does not need or want a next visit': 'Client does not need or want a next visit',
      'Why is there no future visit?': 'Why is there no future visit?',
      '-- Select a reason --': '-- Select a reason --',
      'Please explain:': 'Please explain:',
      'Explain why there is no future visit...': 'Explain why there is no future visit...',
      'Need to Follow up': 'Need to Follow up',
      'Submit': 'Submit',
      'Patient died': 'Patient died',
      'Patient improved/recovered': 'Patient improved/recovered',
      'Patient admitted to hospital': 'Patient admitted to hospital',
      'Patient declined further visits': 'Patient declined further visits',
      'Patient moved/relocated': 'Patient moved/relocated',
      'Referred to another provider': 'Referred to another provider',
      'Other': 'Other',
      'Next Appointment Details': 'Next Appointment Details',
      'Schedule Next Appointment': 'Schedule Next Appointment',
      'Check my schedule': 'Check my schedule',
      'Appointment Date & Time': 'Appointment Date & Time',
      'Date': 'Date',
      'Time': 'Time',
      'Services to be Provided': 'Services to be Provided',
      'Qty:': 'Qty:',
      'No services selected yet': 'No services selected yet',
      'Add from Catalog': 'Add from Catalog',
      'Assigned Healthcare Staff': 'Assigned Healthcare Staff',
      'Booking credit:': 'Booking credit:',
      'No staff assigned': 'No staff assigned',
      'Booking will be created in CONFIRMED state (unassigned)': 'Booking will be created in CONFIRMED state (unassigned)',
      'Assign different nurse': 'Assign different nurse',
      'Services': 'Services',
      'Scheduled For': 'Scheduled For',
      'item(s)': 'item(s)',
      'at': 'at',
      'Schedule Visit': 'Schedule Visit',
      'Select Services from Catalog': 'Select Services from Catalog',
      'Selected Services': 'Selected Services',
      'Search Products': 'Search Products',
      'Product Catalog': 'Product Catalog',
      'Search products...': 'Search products...',
      'Search by product name or code...': 'Search by product name or code...',
      'Loading products...': 'Loading products...',
      'No products found': 'No products found',
      'Add': 'Add',
      'Code:': 'Code:',
      'Invoice / Quote': 'Invoice / Quote',
      'Home Visit': 'Home Visit',
      'Clinic Visit': 'Clinic Visit',
      'Online Consultation': 'Online Consultation',
      'Emergency Visit': 'Emergency Visit',
      'Service': 'Service',
      'Qty': 'Qty',
      'QTY': 'QTY',
      'Disc %': 'Disc %',
      'DISC %': 'DISC %',
      'Price': 'Price',
      'PRICE': 'PRICE',
      'Product': 'Product',
      'Actions': 'Actions',
      'Subtotal': 'Subtotal',
      'Tax': 'Tax',
      'Total': 'Total',
      'TOTAL': 'TOTAL',
      'Save Quote to display updated Total': 'Save Quote to display updated Total',
      'Add Product': 'Add Product',
      'Location Map': 'Location Map',
      'Live': 'Live',
      'Started': 'Started',
      'Cannot load invoice while offline': 'Cannot load invoice while offline',
      'No quote found for this order': 'No quote found for this order',
      'Cannot save quote while offline': 'Cannot save quote while offline',
      'Error loading quote: ': 'Error loading quote: ',
      'Cannot load catalog while offline': 'Cannot load catalog while offline',
      'Invoice verified and saved successfully!': 'Invoice verified and saved successfully!',
      'Cannot upload images while offline': 'Cannot upload images while offline',
      'Image uploaded successfully!': 'Image uploaded successfully!',
      'Failed to upload image: ': 'Failed to upload image: ',
      'Error uploading image: ': 'Error uploading image: ',
      'Product added successfully!': 'Product added successfully!',
      'Failed to add product: ': 'Failed to add product: ',
      'Error adding product: ': 'Error adding product: ',
      'Line updated successfully!': 'Line updated successfully!',
      'Failed to update line: ': 'Failed to update line: ',
      'Error updating line: ': 'Error updating line: ',
      'Line removed successfully!': 'Line removed successfully!',
      'Failed to remove line: ': 'Failed to remove line: ',
      'Error removing line: ': 'Error removing line: ',
      'No address available': 'No address available',
      'Please provide a discount reason for: ': 'Please provide a discount reason for: ',
      'Invoice or Quote is required before completing the service.': 'Invoice or Quote is required before completing the service.',
      'Alternatively, a service package must be assigned if payment is prepaid.': 'Alternatively, a service package must be assigned if payment is prepaid.',
      'Invoice or Quote is required before completing the service. Alternatively, a service package must be assigned if payment is prepaid.': 'Invoice or Quote is required before completing the service. Alternatively, a service package must be assigned if payment is prepaid.',
      'Service cannot be started because the booking is still in Draft status. Please confirm or assign the booking before starting service.': 'Service cannot be started because the booking is still in Draft status. Please confirm or assign the booking before starting service.',
      'Service cannot be started in the current booking status. Please check the booking before starting service.': 'Service cannot be started in the current booking status. Please check the booking before starting service.',
      'Cannot complete service in draft state': 'Cannot complete service in draft state',
      'Cannot complete service in confirmed state': 'Cannot complete service in confirmed state',
      'Cannot complete service in assigned state': 'Cannot complete service in assigned state',
      'Please add verification notes explaining the changes made to Qty or Discount.': 'Please add verification notes explaining the changes made to Qty or Discount.',
      'Error saving quote: ': 'Error saving quote: ',
      'Failed to save quote: ': 'Failed to save quote: ',
      'Please verify the invoice first and click Save Quote.': 'Please verify the invoice first and click Save Quote.',
      'Error: Server returned status ': 'Error: Server returned status ',
      '. Please try again.': '. Please try again.',
      'Error: Invalid response from server. Details: ': 'Error: Invalid response from server. Details: ',
      'Service completed successfully!': 'Service completed successfully!',
      'Error completing payment: ': 'Error completing payment: ',
      'Failed to complete payment: ': 'Failed to complete payment: ',
      'Error: ': 'Error: ',
      'Error starting service: ': 'Error starting service: ',
      'Service started successfully!': 'Service started successfully!',
      'Failed to start service: ': 'Failed to start service: ',
      'Please fill in Clinical Notes before completing the service. Click "Clinical Notes" button to add them.': 'Please fill in Clinical Notes before completing the service. Click "Clinical Notes" button to add them.',
      'Please select a Payment Method before collecting payment.': 'Please select a Payment Method before collecting payment.',
      'No booking selected': 'No booking selected',
      'Failed to complete service: ': 'Failed to complete service: ',
      'Error completing service: ': 'Error completing service: ',
      'Please select a reason': 'Please select a reason',
      'Please enter explanation for "Other" reason': 'Please enter explanation for "Other" reason',
      'Noted: Patient does not need future visits': 'Noted: Patient does not need future visits',
      'Failed to submit: ': 'Failed to submit: ',
      'Error submitting: ': 'Error submitting: ',
      'Please select a date': 'Please select a date',
      'Please select a time': 'Please select a time',
      'Please add at least one service': 'Please add at least one service',
      'Please assign a nurse': 'Please assign a nurse',
      'Cannot schedule while offline': 'Cannot schedule while offline',
      'Next visit scheduled successfully!': 'Next visit scheduled successfully!',
      'Failed to schedule: ': 'Failed to schedule: ',
      'Error scheduling: ': 'Error scheduling: ',
      'Cannot start service while offline': 'Cannot start service while offline',
      'Cannot complete service while offline': 'Cannot complete service while offline',
      'Cannot save clinical notes while offline': 'Cannot save clinical notes while offline',
      'Failed to save clinical notes: ': 'Failed to save clinical notes: ',
      'Error saving clinical notes: ': 'Error saving clinical notes: ',
      'Cannot check next visit while offline': 'Cannot check next visit while offline',
      'Failed to check next visit status': 'Failed to check next visit status',
      'Error checking next visit: ': 'Error checking next visit: ',
      'Cannot submit while offline': 'Cannot submit while offline',
      'Unknown error': 'Unknown error',
      'Error:': 'Error:',

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
    },

    clean: function(value, options = {}) {
      const fallback = options.fallback || '';
      if (value === false || value === null || value === undefined) return fallback;
      if (typeof value === 'string') {
        const trimmed = value.trim();
        if (!trimmed || trimmed.toLowerCase() === 'false' || trimmed.toLowerCase() === 'null' || trimmed.toLowerCase() === 'undefined') {
          return fallback;
        }
        return trimmed;
      }
      return value;
    },

    display: function(value, options = {}) {
      const cleaned = this.clean(value, options);
      if (cleaned === '') return options.fallback || '';

      const lang = window.healthPWAConfig?.user_lang?.startsWith('vi') ? 'vi' : 'en';
      if (lang !== 'vi') return cleaned;

      const text = String(cleaned);
      const mappedWhole = this.t(text);
      if (mappedWhole !== text) return mappedWhole;

      return text.replace(/\b(Home Visit|Clinic Visit|Online Consultation|Emergency Visit|Service)\b/g, (match) => this.t(match));
    },

    error: function(value) {
      const text = this.clean(value);
      if (!text) return '';

      const normalized = text.replace(/\s+/g, ' ').trim();
      const quoteError = 'Invoice or Quote is required before completing the service. Alternatively, a service package must be assigned if payment is prepaid.';
      if (normalized.includes('Invoice or Quote is required before completing the service') && normalized.includes('service package must be assigned')) {
        return this.t(quoteError);
      }
      const completeStateMatch = normalized.match(/^Cannot complete service in (.+) state$/);
      if (completeStateMatch) {
        const stateLabel = this.display(completeStateMatch[1].replace(/_/g, ' '));
        return window.healthPWAConfig?.user_lang?.startsWith('vi')
          ? `Không thể hoàn tất dịch vụ khi lịch hẹn ở trạng thái ${stateLabel}.`
          : normalized;
      }
      return this.display(normalized);
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
