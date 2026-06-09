# Phụ lục — Thuật ngữ, trạng thái và vai trò

Phụ lục này là tài liệu tham chiếu nhanh. Khi gặp một nhãn trạng thái, màu sắc hoặc tên vai trò trong CMS mà chưa rõ ý nghĩa, hãy tra cứu tại đây. Trong thời gian làm quen với hệ thống, bạn có thể mở phụ lục ở một thẻ trình duyệt riêng để tiện tham khảo.

## Tổng quan các trạng thái

Đây là những nhãn xuất hiện thường xuyên nhất trên các bản ghi trong CMS. Mỗi nhãn cho biết bản ghi đang ở giai đoạn nào trong quy trình.

### Trạng thái lịch hẹn

Lịch hẹn chuyển qua các trạng thái sau từ lúc được tạo đến khi hoàn tất. Trạng thái hiện tại quyết định những thao tác tiếp theo có thể thực hiện.

**Nội dung hiển thị trên màn hình:**

| Trạng thái | Ý nghĩa |
| --- | --- |
| Nháp | Đã tạo nhưng chưa được xác nhận |
| Đã xác nhận / Đã đặt lịch | Bệnh nhân đã xác nhận và lịch hẹn đã có báo giá |
| Đã phân công | Một nhân viên đã được phân công cho lịch hẹn |
| Đang thực hiện | Dịch vụ đang được thực hiện |
| Hoàn thành | Dịch vụ đã hoàn tất |
| Hoàn thành — Chờ lập hóa đơn | Dịch vụ do nhân viên bán thời gian thực hiện đã hoàn tất; văn phòng vẫn cần lập hóa đơn |
| Đã hủy | Lịch hẹn đã bị hủy |
| Đã đóng | Lịch hẹn đã được hoàn tất và khóa |

**Lưu ý:** “Hoàn thành — Chờ lập hóa đơn” không giống “Hoàn thành”. Trạng thái này có nghĩa là dịch vụ đã kết thúc nhưng việc lập hóa đơn vẫn chưa hoàn tất; văn phòng phải tạo hóa đơn trước khi có thể đóng lịch hẹn.

### Trạng thái liên hệ

Trạng thái liên hệ cho biết mối quan hệ hiện tại với một người hoặc khách hàng tiềm năng, giúp xác định ai cần được theo dõi và ai đã đặt lịch.

**Nội dung hiển thị trên màn hình:**

| Trạng thái | Ý nghĩa |
| --- | --- |
| Đang hoạt động / Liên hệ ban đầu | Một liên hệ mới hoặc đang được xử lý |
| Khách hàng tiềm năng | Liên hệ cần tiếp tục theo dõi |
| Đặt lịch | Liên hệ đã đặt một dịch vụ |
| Mất cơ hội đặt lịch | Cơ hội đặt lịch không chuyển đổi thành công |
| Thư rác | Liên hệ không hợp lệ hoặc không mong muốn |

### Trạng thái phân công

Trạng thái phân công theo dõi tiến độ của một nhân viên đối với một công việc, từ lúc được phân công đến khi hoàn thành.

**Nội dung hiển thị trên màn hình:**

| Trạng thái | Ý nghĩa |
| --- | --- |
| Đã phân công | Điều dưỡng đã được phân công công việc |
| Đã xác nhận | Điều dưỡng đã chấp nhận công việc |
| Đang thực hiện | Điều dưỡng đã bắt đầu công việc |
| Hoàn thành | Điều dưỡng đã hoàn thành công việc |
| Đã hủy | Phân công đã bị hủy |

**Lưu ý:** Một phân công thông thường chuyển theo thứ tự Đã phân công → Đã xác nhận → Đang thực hiện → Hoàn thành. Phân công có thể bị hủy tại bất kỳ thời điểm nào.

### Trạng thái thanh toán

Trạng thái thanh toán cho biết khoản tiền đang ở đâu. Điều này đặc biệt quan trọng khi điều dưỡng thu tiền mặt tại hiện trường.

**Nội dung hiển thị trên màn hình:**

| Trạng thái | Ý nghĩa |
| --- | --- |
| Đã thu | Khoản thanh toán đã được tiếp nhận |
| Chờ bàn giao | Tiền mặt đang do điều dưỡng giữ và chưa được bàn giao cho văn phòng |
| Đã bàn giao / Đã đối soát | Tiền mặt đã được bàn giao cho văn phòng và khớp với sổ sách |
| Thất bại / Đã hoàn tiền | Thanh toán không thành công hoặc đã được hoàn lại |

**Cảnh báo:** Trạng thái “Chờ bàn giao” có nghĩa là tiền mặt thực tế vẫn đang do điều dưỡng giữ. Khoản tiền này chưa được tính là đã về văn phòng cho đến khi trạng thái chuyển thành “Đã bàn giao / Đã đối soát”.

## Vai trò và quyền xem dữ liệu

Vai trò quyết định những màn hình và bản ghi mà người dùng có thể xem. Cơ chế này giúp mỗi người chỉ tập trung vào dữ liệu thuộc phạm vi trách nhiệm của mình.

### Ai được xem nội dung nào?

**Nội dung hiển thị trên màn hình:**

| Vai trò | Dữ liệu được phép xem |
| --- | --- |
| Điều dưỡng | Chỉ các lịch hẹn được phân công cho mình và bệnh nhân thuộc khu vực phụ trách |
| Quản lý vận hành | Tất cả lịch hẹn và bệnh nhân trong khu vực phụ trách |
| Tài chính | Các màn hình Tài chính |
| Chủ sở hữu / Quản trị viên | Toàn bộ hệ thống |

**Lưu ý:** Một người dùng có thể được gán nhiều vai trò. Quyền truy cập của họ là tổng hợp quyền của tất cả vai trò; ví dụ, người vừa có vai trò Tài chính vừa là Quản lý vận hành sẽ nhìn thấy cả hai nhóm màn hình.

## Mẹo hữu ích cho người dùng mới

Những thói quen nhỏ dưới đây sẽ giúp công việc hằng ngày trên CMS nhanh và hiệu quả hơn.

- **Thay đổi toàn bộ số liệu cùng lúc:** sử dụng bộ lọc thời gian trên bảng điều khiển để cập nhật đồng thời tất cả số liệu trên bảng đó.
- **Xem các bản ghi tạo nên một chỉ số:** nhấp vào một thẻ KPI để mở danh sách các bản ghi được tính trong chỉ số.
- **Quay lại bước trước:** sử dụng đường dẫn điều hướng ở góc trên bên trái để trở về màn hình trước.
- **Kiểm tra lịch sử bản ghi:** nhật ký trao đổi trên bản ghi lưu toàn bộ lịch sử, giúp bạn biết điều gì đã xảy ra và vào thời điểm nào.
- **Yêu cầu trợ giúp:** Trợ lý AI ở góc dưới bên phải có thể trả lời câu hỏi của bạn.

**Mẹo:** Khi một số liệu trên bảng điều khiển có vẻ bất thường, hãy nhấp vào thẻ KPI để xem các bản ghi thực tế trước khi báo cáo vấn đề. Dữ liệu chi tiết thường giải thích được nguyên nhân của số liệu.
