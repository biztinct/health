# CRM — Liên hệ và khách hàng tiềm năng

Khu vực CRM dùng để quản lý các yêu cầu tư vấn — những người gọi điện, nhắn tin hoặc liên hệ với phòng khám — và hỗ trợ bạn đưa từng người qua các bước để trở thành một lịch hẹn đã xác nhận. Chương này trình bày ba mục trong khu vực CRM: **Bảng điều khiển**, **Liên hệ** và **Hoạt động**.

## Tổng quan

Mỗi yêu cầu tư vấn được tạo thành một **liên hệ**. Trong quá trình làm việc với người đó, trạng thái liên hệ sẽ chuyển qua một vòng đời đơn giản:

- **Đang hoạt động (Liên hệ ban đầu)** — một yêu cầu tư vấn mới vừa được tiếp nhận.
- **Khách hàng tiềm năng** — liên hệ đã được đánh dấu để tiếp tục theo dõi.
- **Đặt lịch** — liên hệ đã đặt một dịch vụ.
- **Mất cơ hội đặt lịch** — việc đặt lịch không thành công.
- **Thư rác** — yêu cầu không hợp lệ và được đánh dấu để bỏ qua.

Bảng điều khiển cung cấp cái nhìn tổng quan; mục Liên hệ là nơi xử lý công việc hằng ngày; mục Hoạt động là bảng công việc theo dõi chung của cả nhóm.

## Bảng điều khiển

### Bảng điều khiển CRM

Bảng điều khiển CRM là trung tâm tổng quan nhanh. Hãy sử dụng màn hình này khi bắt đầu ca làm việc để biết có bao nhiêu yêu cầu mới, những trường hợp nào vẫn cần theo dõi và hiệu quả chuyển đổi của nhóm.

![Trung tâm CRM với các thẻ KPI, biểu đồ và bảng hoạt động](IMG:crm_01_dashboard.png)

**Nội dung hiển thị trên màn hình**

- Tiêu đề **“Trung tâm CRM — Quản lý bán hàng và liên hệ”**.
- **Bộ lọc thời gian** ở phía trên với các lựa chọn **Hôm nay**, **Tuần**, **Tháng**, **Tất cả** hoặc **Tùy chỉnh**, cùng nút **làm mới** để tải số liệu mới nhất.
- Một hàng **thẻ KPI** có thể nhấp vào:
  - **Liên hệ hôm nay** — các yêu cầu tư vấn được tiếp nhận trong ngày.
  - **Đang chờ theo dõi** — các khách hàng tiềm năng đang chờ được liên hệ lại.
  - **Khách hàng tiềm năng đang hoạt động** — các khách hàng tiềm năng đang được xử lý.
  - **Lịch hẹn tuần này** — các lịch hẹn được tạo trong tuần.
  - **Tỷ lệ chuyển đổi** — tỷ lệ chuyển đổi trong tháng hiện tại.
  - **Tỷ lệ thư rác** — tỷ lệ yêu cầu được đánh dấu là thư rác.
- Một hàng số liệu thứ hai: **Mới trong tháng**, **Đã chuyển đổi**, **Thất bại** và **Quy trình đang hoạt động**.
- Biểu đồ vòng **“Quy trình liên hệ”**, phân loại liên hệ theo trạng thái (Đặt lịch / Khách hàng tiềm năng / Mất cơ hội đặt lịch / Thư rác).
- Biểu đồ cột **“Các kênh nguồn”**, cho biết liên hệ đến từ đâu.
- Ba bảng thông tin:
  - **Liên hệ gần đây** — mỗi mục hiển thị chấm trạng thái, tên, kênh và thời gian.
  - **Lịch hẹn sắp tới** — các lịch hẹn tiếp theo.
  - **Trạng thái liên hệ** — mỗi trạng thái có một thanh và số lượng tương ứng.

**Cách thực hiện**

1. Chọn khoảng thời gian trong **bộ lọc thời gian** (Hôm nay / Tuần / Tháng / Tất cả / Tùy chỉnh). Toàn bộ bảng điều khiển sẽ cập nhật theo khoảng thời gian đã chọn.
2. Nhấp **làm mới** bất cứ lúc nào để tải số liệu mới nhất.
3. Nhấp vào một **thẻ KPI** để mở trực tiếp danh sách liên hệ hoặc lịch hẹn đã được lọc tương ứng.
4. Trên biểu đồ vòng **Quy trình liên hệ**, nhấp vào một phần, ví dụ **Khách hàng tiềm năng**, để mở danh sách liên hệ theo trạng thái đó.
5. Trong **Liên hệ gần đây**, nhấp vào một dòng để mở liên hệ hoặc nhấp **Xem tất cả** để mở toàn bộ danh sách liên hệ.
6. Trong **Lịch hẹn sắp tới**, nhấp vào một mục để mở lịch hẹn đó.

**Mẹo:** Mỗi thẻ KPI và mỗi phần của biểu đồ đều là một lối tắt. Nếu một số liệu có vẻ bất thường, hãy nhấp vào để xem chính xác những liên hệ tạo nên số liệu đó.

## Liên hệ

### Danh sách liên hệ

Liên hệ là danh sách làm việc gồm tất cả các yêu cầu tư vấn. Tại đây, bạn có thể xem trạng thái của từng người, thực hiện thao tác nhanh và mở hồ sơ đầy đủ. Đây là nơi xử lý phần lớn công việc CRM hằng ngày.

![Danh sách liên hệ với các thẻ trạng thái và nút thao tác nhanh trên từng dòng](IMG:crm_02_contacts_list.png)

**Nội dung hiển thị trên màn hình**

- Các thẻ lọc danh sách: **Tất cả**, **Đang hoạt động**, **Khách hàng tiềm năng**, **Đặt lịch**, **Thất bại** và **Thư rác**.
- **Bộ lọc ngày** để thu hẹp danh sách theo thời điểm tiếp nhận liên hệ.
- Trên mỗi dòng có các **nút thao tác nhanh**: **Đặt lịch**, **Ghi nhận hoạt động**, **Chuyển cấp** và **Thư rác**.

**Cách thực hiện**

1. Nhấp vào một thẻ, ví dụ **Khách hàng tiềm năng**, để chỉ hiển thị các liên hệ có trạng thái đó.
2. Sử dụng **bộ lọc ngày** để tập trung vào một khoảng thời gian cụ thể.
3. Trên một dòng bất kỳ, sử dụng các nút thao tác nhanh để xử lý mà không cần mở liên hệ (xem bảng tham chiếu nút bên dưới).
4. Nhấp vào dòng của một liên hệ để mở **biểu mẫu liên hệ** đầy đủ.

### Biểu mẫu liên hệ

Khi mở một liên hệ, hệ thống hiển thị biểu mẫu đầy đủ cùng các nút thao tác chính ở phần đầu. Sử dụng màn hình này khi cần xử lý chi tiết một yêu cầu: đặt lịch, ghi nhận hoạt động theo dõi, chuyển cấp hoặc đóng yêu cầu.

![Biểu mẫu liên hệ với các nút thao tác ở phần đầu](IMG:crm_02b_contact_form.png)

**Nội dung hiển thị trên màn hình**

- Thông tin chi tiết của liên hệ.
- Phần đầu có các nút thao tác chính: **Đặt lịch**, **Ghi nhận hoạt động**, **Ghi nhận là khách hàng tiềm năng**, **Chuyển cấp**, **Thư rác** và, khi liên hệ đã ở trạng thái đặt lịch, **Mất cơ hội đặt lịch**.

**Cách thực hiện**

1. Để chuyển yêu cầu tư vấn thành lịch hẹn, nhấp **Đặt lịch**. Trình hướng dẫn **Đặt lịch nhanh** sẽ mở. Hệ thống tìm kiếm khách hàng hiện có để tránh tạo hồ sơ trùng lặp — hãy xác nhận khách hàng phù hợp hoặc tạo khách hàng mới, sau đó nhập **loại dịch vụ**, **cơ sở**, **ngày/giờ** và **thời lượng**. Nhấp **Tạo lịch hẹn**; trạng thái của liên hệ sẽ chuyển thành **đặt lịch**.
2. Để lên lịch theo dõi, nhấp **Ghi nhận hoạt động** và tạo cuộc gọi hoặc cuộc họp cho liên hệ.
3. Để lưu yêu cầu và xử lý sau, nhấp **Ghi nhận là khách hàng tiềm năng**. Trạng thái sẽ chuyển thành **khách hàng tiềm năng**.
4. Để chuyển liên hệ cho chuyên viên phù hợp, nhấp **Chuyển cấp**. Liên hệ sẽ được chuyển đến Điều dưỡng trưởng, Quản lý vận hành hoặc Bác sĩ trực.
5. Nếu yêu cầu không hợp lệ, nhấp **Thư rác**. Liên hệ được đánh dấu là thư rác và số điện thoại của họ được ghi nhận để nhận diện về sau.
6. Nếu việc đặt lịch không thành công, nhấp **Mất cơ hội đặt lịch** (chỉ hiển thị khi trạng thái là **đặt lịch**) và ghi nhận lý do.

**Bảng tham chiếu nút**

| Nút | Chức năng | Trạng thái sau thao tác |
|---|---|---|
| Đặt lịch | Mở trình hướng dẫn Đặt lịch nhanh; tìm/xác nhận khách hàng, nhập loại dịch vụ, cơ sở, ngày-giờ và thời lượng, sau đó tạo lịch hẹn | đặt lịch |
| Ghi nhận hoạt động | Lên lịch hoạt động theo dõi (cuộc gọi/cuộc họp) cho liên hệ | không thay đổi |
| Ghi nhận là khách hàng tiềm năng | Lưu liên hệ để tiếp tục theo dõi | khách hàng tiềm năng |
| Chuyển cấp | Chuyển liên hệ đến chuyên viên (Điều dưỡng trưởng / Quản lý vận hành / Bác sĩ trực) | không thay đổi |
| Thư rác | Đánh dấu liên hệ là thư rác và ghi nhận số điện thoại | thư rác |
| Mất cơ hội đặt lịch | Ghi nhận lý do mất cơ hội (chỉ khi trạng thái là đặt lịch) | mất cơ hội đặt lịch |

**Lưu ý:** Trình hướng dẫn **Đặt lịch** kiểm tra khách hàng hiện có trước khi tạo hồ sơ mới. Luôn xác nhận bản ghi phù hợp khi hệ thống đề xuất để tránh tạo hồ sơ khách hàng trùng lặp.

**Mẹo:** Các nút thao tác nhanh trên từng dòng danh sách (**Đặt lịch**, **Ghi nhận hoạt động**, **Chuyển cấp**, **Thư rác**) có cùng chức năng với các nút tương ứng trên biểu mẫu liên hệ. Hãy sử dụng cách nhanh nhất cho công việc đang thực hiện.

## Hoạt động

### Bảng hoạt động

Bảng Hoạt động là danh sách công việc theo dõi chung của nhóm. Mọi cuộc gọi, cuộc họp, email hoặc nhiệm vụ được lên lịch cho một liên hệ đều xuất hiện tại đây để không công việc nào bị bỏ sót.

![Bảng Hoạt động được nhóm theo loại hoạt động](IMG:crm_03_activities.png)

**Nội dung hiển thị trên màn hình**

- Bảng các hoạt động đã lên lịch, được nhóm theo loại: **Việc cần làm**, **Email**, **Cuộc gọi**, **Cuộc họp** và **Tài liệu**.
- **Bộ lọc loại** để chỉ hiển thị một loại hoạt động.
- **Bộ lọc ngày**: **Tất cả ngày**, **Hôm nay**, **Tuần này** hoặc **Tháng này**.
- Nút **+ Lên lịch hoạt động**.

**Cách thực hiện**

1. Sử dụng **bộ lọc loại** để tập trung vào một loại hoạt động, ví dụ chỉ xem **Cuộc gọi**.
2. Sử dụng **bộ lọc ngày** để hiển thị các hoạt động đến hạn **Hôm nay**, **Tuần này**, **Tháng này** hoặc trong **Tất cả ngày**.
3. Nhấp **+ Lên lịch hoạt động**, chọn liên hệ và tạo hoạt động.

**Mẹo:** Hãy kiểm tra bảng này thường xuyên. Đây là nơi cả nhóm theo dõi những người cần được liên hệ lại và thời điểm cần thực hiện.
