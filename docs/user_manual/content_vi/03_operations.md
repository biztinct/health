# Quản lý vận hành — Lịch hẹn, nhân viên và quy trình dịch vụ

Khu vực Quản lý vận hành là nơi điều hành hoạt động thăm khám tại nhà hằng ngày: theo dõi tình hình trong ngày, xử lý lịch hẹn từ yêu cầu ban đầu đến khi buổi thăm khám được đóng và thanh toán, quản lý bệnh nhân và nhân viên, phân công điều dưỡng, đồng thời đối soát tiền mặt mà nhân viên thu tại hiện trường.

Khu vực này gồm: **Bảng điều khiển** (Trung tâm vận hành), **Lịch hẹn**, **Bệnh nhân**, **Nhân viên** (Lịch trực / Lịch làm việc / Nghỉ phép), **Phân công nhân viên**, **Thu tiền** và **Khối lượng công việc**.

## Bảng điều khiển (Trung tâm vận hành)

### Trung tâm vận hành

Trung tâm vận hành là “bàn điều phối” trực tiếp trong ngày. Hãy sử dụng màn hình này vào đầu buổi sáng và trong suốt ngày làm việc để xem toàn bộ lịch hẹn, nhận biết những lịch vẫn chưa có điều dưỡng và phân công nhân viên chỉ bằng một thao tác.

![Bảng điều khiển Trung tâm vận hành với các thẻ KPI, hàng đợi lịch hẹn, danh sách nhân viên và dòng thời gian](IMG:ops_01_dashboard.png)

**Nội dung hiển thị trên màn hình:**

- **Các điều khiển phía trên:** chuyển ngày bằng mũi tên trước/sau và ngày hiện tại; bộ lọc thời gian (Hôm nay / Tuần / Tháng / Tất cả / Tùy chỉnh); bộ lọc Cơ sở (Tất cả cơ sở hoặc một cơ sở cụ thể); và nút làm mới.
- **Các thẻ KPI:** Tổng số lịch hẹn, Cần phân công (kèm số lượng khẩn cấp / bình thường), Đang thực hiện, Đã hoàn thành và Doanh thu.
- **Bảng Hàng đợi lịch hẹn** có ba thẻ: “Cần nhân viên” (kèm số lượng), “Tất cả hôm nay” và “Có vấn đề”. Mỗi thẻ lịch hẹn hiển thị thời gian, mã lịch hẹn, nhãn **KHẨN CẤP** nếu có mức ưu tiên cao, nhãn trạng thái, menu ba chấm, tên bệnh nhân, loại dịch vụ, thời lượng và địa điểm. Lịch chưa được phân công còn có danh sách **Phân công:** ngay trên thẻ.
- **Bảng Danh sách nhân viên:** mỗi nhân viên được hiển thị với ảnh đại diện, chấm trạng thái, tên và số lịch hẹn trong ngày.
- **Dòng thời gian hôm nay:** lưới thời gian từ 7 giờ đến 18 giờ, mỗi nhân viên một dòng và các khối dịch vụ được phân màu. Chú giải màu gồm: Thăm khám tại nhà, Tại phòng khám, Tư vấn, Theo dõi.
- **Các nút cuối trang:** “Xem tất cả lịch hẹn” và “Tạo lịch hẹn”.

**Cách thực hiện:**

1. Chọn **bộ lọc thời gian** (Hôm nay / Tuần / Tháng / Tất cả / Tùy chỉnh) và **bộ lọc Cơ sở** để xác định dữ liệu cần xem; toàn bộ bảng điều khiển sẽ cập nhật tương ứng.
2. Sử dụng mũi tên **trước / sau** để lùi hoặc tiến ngày, và nhấp **làm mới** để tải dữ liệu mới nhất.
3. Xem các **thẻ KPI** để nắm nhanh tình hình trong ngày; thẻ Cần phân công cho biết có bao nhiêu lịch hẹn, trong đó bao nhiêu lịch khẩn cấp, vẫn chưa có điều dưỡng.
4. Trong **Hàng đợi lịch hẹn**, chọn thẻ **Cần nhân viên** để chỉ xem các lịch đang chờ điều dưỡng, **Tất cả hôm nay** để xem toàn bộ lịch trong ngày, hoặc **Có vấn đề** để xem các lịch cần xử lý.
5. Để phân công nhanh một lịch chưa có nhân viên, mở danh sách **Phân công:**. Danh sách hiển thị các nhân viên đang sẵn sàng cùng khối lượng công việc hiện tại; chọn một người để phân công điều dưỡng ngay lập tức.
6. Để thực hiện thêm thao tác với lịch hẹn, mở **menu ba chấm**: Xem chi tiết, Phân công nhân viên, Bắt đầu dịch vụ, Thu tiền hoặc Hủy. Mỗi mục sẽ mở màn hình hoặc thao tác tương ứng.
7. Trong **Danh sách nhân viên**, nhấp vào một nhân viên để mở hồ sơ của họ.
8. Sử dụng **Tạo lịch hẹn** để tạo lịch mới hoặc **Xem tất cả lịch hẹn** để chuyển đến danh sách Lịch hẹn đầy đủ.

**Mẹo:** Số lượng trên thẻ “Cần nhân viên” và KPI “Cần phân công” là hai chỉ số nên được đưa về 0. Khi không còn lịch cần phân công, mọi bệnh nhân trong ngày đều đã có điều dưỡng phụ trách.

## Lịch hẹn

Một lịch hẹn tương ứng với một buổi thăm khám tại nhà đã được lên lịch, từ lúc tạo đến khi được đóng và thanh toán. Đây là quy trình trọng tâm của hoạt động hằng ngày, vì vậy các bước dưới đây được trình bày chi tiết.

### Xem lịch hẹn (Danh sách và Lịch)

Bạn có thể xem lịch hẹn dưới dạng danh sách có thể sắp xếp hoặc dưới dạng lịch, tùy theo công việc cần thực hiện.

![Danh sách Lịch hẹn](IMG:ops_02_bookings_list.png)

![Lịch hiển thị các lịch hẹn](IMG:ops_02d_bookings_calendar.png)

**Nội dung hiển thị trên màn hình:**

- **Dạng danh sách** gồm tất cả các lịch hẹn.
- **Dạng lịch** có thể chuyển giữa Ngày, Tuần và Tháng.

**Cách thực hiện:**

1. Sử dụng **dạng danh sách** để xem nhanh, sắp xếp và xử lý nhiều lịch hẹn cùng lúc.
2. Chuyển sang **dạng lịch**, sau đó chọn **Ngày**, **Tuần** hoặc **Tháng** để xem các lịch hẹn theo thời gian.
3. Nhấp vào một lịch hẹn để mở bản ghi đầy đủ.

### Hồ sơ lịch hẹn

Mỗi lịch hẹn được mở dưới dạng một hồ sơ duy nhất, cho biết chính xác lịch đang ở bước nào và thao tác tiếp theo cần thực hiện.

![Chi tiết một lịch hẹn đã hoàn thành với thanh vòng đời, các thẻ tóm tắt và thao tác nhanh](IMG:ops_02b_booking_detail.png)

**Nội dung hiển thị trên màn hình:**

- **Thanh tiến trình vòng đời:** Đã tạo → Đã xác nhận → Đã phân công → Đang thực hiện → Hoàn thành → Đã đóng.
- **Các thẻ tóm tắt:** Thời gian dự kiến, Loại dịch vụ, Thời lượng, Cơ sở và Khu vực phụ trách.
- Các bảng **Thông tin bệnh nhân** và **Phân công nhân viên**.
- Bảng **Hành động phù hợp tiếp theo**, đề xuất thao tác hữu ích nhất cần thực hiện.
- **Thao tác nhanh:** Chi tiết bệnh nhân, Xem báo giá, Xem thanh toán và Xem phân công.

**Cách thực hiện:**

1. Xem **thanh tiến trình vòng đời** để biết lịch hẹn đang ở giai đoạn nào.
2. Làm theo bảng **Hành động phù hợp tiếp theo**. Bảng này hiển thị nút phù hợp với trạng thái hiện tại.
3. Sử dụng **Thao tác nhanh** để chuyển đến bệnh nhân, báo giá, thanh toán hoặc phân công mà không cần rời khỏi lịch hẹn.

### Quy trình lịch hẹn đầy đủ

Dưới đây là toàn bộ vòng đời của một lịch hẹn. Mỗi bước nêu rõ thao tác cần thực hiện, kết quả của thao tác và trạng thái tiếp theo.

![Lịch hẹn ở trạng thái nháp với hành động phù hợp tiếp theo là Tạo báo giá](IMG:ops_02c_booking_draft.png)

1. **Tạo lịch hẹn (Nháp).** Nhấp **Tạo lịch hẹn** tại Trung tâm vận hành hoặc hồ sơ bệnh nhân. Nhập bệnh nhân (hệ thống kiểm tra trùng lặp để tránh tạo cùng một bệnh nhân nhiều lần), loại dịch vụ, cơ sở, ngày giờ và thời lượng. Lịch hẹn được lưu ở trạng thái **Nháp**.
2. **Tạo báo giá (vẫn ở trạng thái Nháp).** Trên lịch hẹn nháp, bảng **Hành động phù hợp tiếp theo** hiển thị **Tạo báo giá**. Nhấp vào nút này, thêm các dòng dịch vụ có đơn giá rồi lưu. Hệ thống có thể tự động áp dụng chi phí di chuyển theo khoảng cách.
3. **Xác nhận lịch hẹn (→ Đã xác nhận).** Sau khi có báo giá và đã đặt ngày, nhấp **Xác nhận lịch hẹn**. Hệ thống hoàn tất mã lịch hẹn và chuyển trạng thái sang **Đã xác nhận**; bệnh nhân đã được đặt lịch.
4. **Phân công nhân viên (→ Đã phân công).** Nhấp **Phân công nhân viên** hoặc sử dụng danh sách **Phân công** tại Trung tâm vận hành. Hệ thống tạo các phân công: điều dưỡng đầu tiên là người **Phụ trách chính**, những người còn lại là **Hỗ trợ**. Điều dưỡng được phân công sẽ nhận thông báo đẩy.
5. **Bắt đầu dịch vụ (→ Đang thực hiện).** Nhấp **Bắt đầu dịch vụ**. Hệ thống ghi nhận thời gian bắt đầu thực tế và khởi động bộ đếm giờ; lịch hẹn được hiển thị trong nhóm **Đang thực hiện**.
6. **Thêm ghi chú lâm sàng.** Trong buổi thăm khám, nhập ghi chú lâm sàng tại thẻ **Lâm sàng**. Đây là nội dung bắt buộc trước khi hoàn thành lịch hẹn.
7. **Hoàn thành dịch vụ (→ Hoàn thành).** Nhấp **Hoàn thành dịch vụ**. Hệ thống ghi nhận thời gian kết thúc. Lịch do nhân viên toàn thời gian thực hiện chuyển sang **Hoàn thành**; lịch do nhân viên bán thời gian thực hiện chuyển sang **Hoàn thành — Chờ lập hóa đơn**, nghĩa là bộ phận Vận hành cần lập hóa đơn.
8. **Tạo hóa đơn.** Nhấp **Tạo hóa đơn**. Hệ thống mở báo giá để kiểm tra lần cuối rồi tạo hóa đơn.
9. **Thu tiền.** Ghi nhận thanh toán bằng tiền mặt hoặc chuyển khoản.
10. **Đóng lịch hẹn (→ Đã đóng).** Nhấp **Đóng**. Thao tác này hoàn tất và khóa lịch hẹn.

**Các phương án khác trước khi hoàn thành dịch vụ:**

- **Hủy lịch hẹn** mở trình hướng dẫn hủy để nhập lý do và ghi chú; hệ thống hủy các phân công và thông báo cho nhân viên.
- **Đổi lịch** thay đổi ngày giờ và thực hiện phân công lại.

**Bảng tham chiếu nút:**

| Nút | Chức năng | Trạng thái sau thao tác |
| --- | --- | --- |
| Tạo lịch hẹn | Tạo lịch mới từ thông tin bệnh nhân và buổi thăm khám | Nháp |
| Tạo báo giá | Thêm các dòng dịch vụ có đơn giá, có thể bao gồm chi phí di chuyển | Nháp |
| Xác nhận lịch hẹn | Hoàn tất mã lịch hẹn; bệnh nhân được đặt lịch | Đã xác nhận |
| Phân công nhân viên | Tạo phân công; người đầu tiên phụ trách chính, những người còn lại hỗ trợ; gửi thông báo cho điều dưỡng | Đã phân công |
| Bắt đầu dịch vụ | Ghi nhận thời gian bắt đầu và khởi động bộ đếm giờ | Đang thực hiện |
| Hoàn thành dịch vụ | Ghi nhận thời gian kết thúc | Hoàn thành, hoặc Hoàn thành — Chờ lập hóa đơn đối với nhân viên bán thời gian |
| Tạo hóa đơn | Mở báo giá để kiểm tra và tạo hóa đơn | Hoàn thành |
| Đóng | Hoàn tất và khóa lịch hẹn | Đã đóng |
| Hủy lịch hẹn | Mở trình hướng dẫn hủy; hủy phân công và thông báo cho nhân viên | Đã hủy |
| Đổi lịch | Thay đổi ngày/giờ và thực hiện phân công lại | Ngày/giờ được thay đổi |

**Lưu ý:** Sự khác biệt giữa nhân viên toàn thời gian và bán thời gian có ảnh hưởng tại bước 7. Lịch do nhân viên bán thời gian thực hiện sẽ chuyển sang **Hoàn thành — Chờ lập hóa đơn** và không tự hoàn tất quy trình; bạn phải lập hóa đơn cho lịch đó.

**Cảnh báo:** Phải có ghi chú lâm sàng trước khi hoàn thành dịch vụ (bước 6). Nếu chưa có ghi chú, hệ thống sẽ không cho phép chuyển lịch hẹn sang trạng thái Hoàn thành.

## Bệnh nhân

### Danh sách bệnh nhân

Danh sách Bệnh nhân là danh bạ những người được phòng khám chăm sóc. Sử dụng danh sách này để tìm một bệnh nhân và thực hiện thao tác ngay.

![Danh sách Bệnh nhân với thông tin bệnh nhân và các thao tác nhanh](IMG:ops_03_clients_list.png)

**Nội dung hiển thị trên màn hình:**

- Mỗi dòng bệnh nhân hiển thị **Mã bệnh nhân**, **số điện thoại** và **lần thăm khám gần nhất**.
- Các thao tác nhanh trên mỗi dòng: **Đặt lịch**, **Định kỳ**, **Thu tiền** và **Thanh toán**.

**Cách thực hiện:**

1. Tìm bệnh nhân cần xử lý trong danh sách.
2. Sử dụng các thao tác nhanh trên dòng: **Đặt lịch** để tạo một lịch hẹn riêng lẻ; **Định kỳ** để thiết lập lịch hẹn lặp lại; **Thu tiền** để ghi nhận tiền mặt đã thu; hoặc **Thanh toán** để tiếp nhận một khoản thanh toán.
3. Nhấp vào bệnh nhân để mở hồ sơ đầy đủ.

### Hồ sơ bệnh nhân

Hồ sơ bệnh nhân cung cấp toàn bộ thông tin về một người: lịch sử, tổng chi tiêu, địa chỉ sinh sống và tuyến đường điều dưỡng sẽ di chuyển.

![Hồ sơ bệnh nhân với các thẻ KPI, địa chỉ, tuyến đường trên bản đồ và thao tác nhanh](IMG:ops_03b_client_profile.png)

**Nội dung hiển thị trên màn hình:**

- **Các thẻ KPI:** Tổng số lịch hẹn, Gói đang hoạt động, Tổng chi tiêu, Số tiền còn nợ, Mức độ hài lòng và Giới thiệu.
- **Chi tiết địa chỉ**, bao gồm **khoảng cách lái xe** đến phòng khám.
- **Vị trí trên bản đồ** hiển thị tuyến đường.
- Nút **Tạo lịch hẹn** và bảng **Thao tác nhanh:** Xem lịch hẹn, Tạo lịch hẹn định kỳ, Mua nhanh gói dịch vụ, Tạo hóa đơn, Xem hóa đơn và Các gói đã mua.

**Cách thực hiện:**

1. Xem các **thẻ KPI** để nắm nhanh lịch sử của bệnh nhân và số tiền còn nợ.
2. Nhập hoặc chỉnh sửa **địa chỉ**. Hệ thống tự động xác định tọa độ; **tuyến đường và khoảng cách** sẽ xuất hiện trên bản đồ.
3. Sử dụng **Tạo lịch hẹn** để tạo lịch cho bệnh nhân này hoặc chọn một **Thao tác nhanh** để xem lịch hẹn, thiết lập lịch định kỳ, mua gói dịch vụ, tạo hoặc xem hóa đơn, hoặc xem các gói đã mua.

**Lưu ý:** Khoảng cách lái xe hiển thị tại đây được sử dụng để tính giá. Đây là dữ liệu đầu vào cho chi phí di chuyển theo khoảng cách có thể xuất hiện trên báo giá.

## Nhân viên

### Lịch trực

Lịch trực cho biết ai đang làm việc và khối lượng công việc hiện tại của họ.

![Lịch trực nhân viên hiển thị trạng thái sẵn sàng và khối lượng công việc trong ngày](IMG:ops_04_staff_roster.png)

**Nội dung hiển thị trên màn hình:**

- **Trạng thái sẵn sàng** và **khối lượng công việc hôm nay** của từng nhân viên.

**Cách thực hiện:**

1. Kiểm tra lịch trực để biết ai đang sẵn sàng trước khi phân công công việc.
2. Xem khối lượng công việc hôm nay của từng người để phân bổ lịch hẹn hợp lý.

### Lịch làm việc

Lịch làm việc hiển thị giờ làm việc thông thường của từng nhân viên.

![Lịch giờ làm việc của nhân viên](IMG:ops_05_schedules.png)

**Nội dung hiển thị trên màn hình:**

- **Giờ làm việc** của từng nhân viên.

**Cách thực hiện:**

1. Mở Lịch làm việc để xác nhận giờ làm của điều dưỡng trước khi xếp lịch thăm khám.

### Nghỉ phép

Mục Nghỉ phép liệt kê thời gian nghỉ của nhân viên để tránh phân công người đang vắng mặt.

**Nội dung hiển thị trên màn hình:**

- Danh sách **nghỉ phép** của nhân viên.

**Cách thực hiện:**

1. Kiểm tra mục Nghỉ phép trước khi phân công một buổi thăm khám để bảo đảm điều dưỡng không nghỉ vào thời điểm đó.

## Phân công nhân viên

### Dòng thời gian phân công nhân viên

Phân công nhân viên là màn hình dòng thời gian hiển thị mọi phân công của tất cả nhân viên trong ngày, giúp bạn biết ai đang thực hiện công việc gì và vào thời điểm nào.

![Dòng thời gian phân công theo nhân viên và thời gian](IMG:ops_06_staff_assignment.png)

**Nội dung hiển thị trên màn hình:**

- **Dòng thời gian** của các phân công, được bố trí theo nhân viên và thời gian.

**Cách thực hiện:**

1. Xem dòng thời gian để biết các lịch được phân công cho từng điều dưỡng trong ngày.
2. Theo dõi từng phân công qua các trạng thái: **đã phân công** → **đã xác nhận** (điều dưỡng chấp nhận trên ứng dụng di động) → **đang thực hiện** (điều dưỡng bắt đầu) → **hoàn thành**.

**Lưu ý:** Điều dưỡng chấp nhận, bắt đầu và hoàn thành phân công trên ứng dụng di động. Xem chương Ứng dụng di động để biết quy trình dành cho điều dưỡng.

## Thu tiền

### Đối soát tiền thu

Màn hình Thu tiền là nơi đối soát tiền mặt do điều dưỡng thu tại hiện trường. Khi điều dưỡng nhận tiền mặt trong một buổi thăm khám, khoản tiền được đánh dấu là “chờ bàn giao” cho văn phòng; văn phòng xác nhận đã nhận tiền tại màn hình này.

![Màn hình Thu tiền dùng để đối soát tiền mặt được thu tại hiện trường](IMG:ops_07_collections.png)

**Nội dung hiển thị trên màn hình:**

- Tiền mặt do điều dưỡng thu tại hiện trường và đang **chờ bàn giao** cho văn phòng.

**Cách thực hiện:**

1. Kiểm tra các khoản tiền mặt đang chờ bàn giao.
2. Đối soát từng khoản khi tiền được bàn giao cho văn phòng.

**Mẹo:** Đối soát thường xuyên giúp số liệu tiền mặt tại hiện trường và sổ sách văn phòng luôn khớp nhau, tránh bỏ sót bất kỳ khoản tiền nào đã thu trong buổi thăm khám.

## Khối lượng công việc

### Bảng khối lượng công việc

Khối lượng công việc là bảng điều khiển cho biết mức độ bận rộn của nhân viên, giúp phân bổ các buổi thăm khám đồng đều và tránh để một người bị quá tải.

![Bảng điều khiển mức sử dụng nhân viên và khối lượng phân công](IMG:ops_08_workload.png)

**Nội dung hiển thị trên màn hình:**

- Bảng điều khiển về **mức sử dụng nhân viên** và **khối lượng phân công**.

**Cách thực hiện:**

1. Xem mức sử dụng và khối lượng phân công của từng nhân viên.
2. Dựa trên dữ liệu để cân đối lại công việc: chuyển bớt phân công từ nhân viên đang quá tải sang người còn khả năng tiếp nhận.
