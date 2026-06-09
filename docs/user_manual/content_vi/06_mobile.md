# Ứng dụng di động dành cho điều dưỡng

Ứng dụng di động dành cho điều dưỡng được sử dụng trên điện thoại để xem lịch thăm khám, mở thông tin bệnh nhân, bắt đầu và hoàn thành dịch vụ, đồng thời đồng bộ công việc với văn phòng. Đây là một Ứng dụng Web Tiến bộ (PWA), nghĩa là ứng dụng chạy trong trình duyệt web trên điện thoại nhưng có thể hoạt động tương tự một ứng dụng thông thường.

## Bắt đầu sử dụng

### Mở và cài đặt ứng dụng

Đây là thao tác đầu tiên cần thực hiện trên điện thoại trước khi đi thăm khám. Bạn mở ứng dụng trong trình duyệt, đăng nhập một lần và có thể thêm ứng dụng vào Màn hình chính để từ đó mở như một ứng dụng thông thường.

**Cách thực hiện:**

1. Mở trình duyệt web trên điện thoại và truy cập **care.biztinct.com/health_pwa**.
2. Đăng nhập bằng tài khoản điều dưỡng, sử dụng tên đăng nhập và mật khẩu do văn phòng cung cấp.
3. Để sử dụng thuận tiện như một ứng dụng, chọn **Thêm vào Màn hình chính** trong trình duyệt. Biểu tượng ứng dụng sẽ xuất hiện trên điện thoại; chạm vào biểu tượng để mở trực tiếp Ứng dụng Điều dưỡng.

**Mẹo:** Sau khi thêm vào Màn hình chính, bạn không cần nhập lại địa chỉ web mỗi lần sử dụng. Chỉ cần chạm vào biểu tượng ứng dụng.

**Lưu ý:** Ứng dụng lưu tạm dữ liệu trên điện thoại để tiếp tục hoạt động khi tín hiệu mạng yếu. Các thay đổi sẽ tự động đồng bộ về hệ thống sau khi thiết bị kết nối mạng trở lại.

### Thanh điều hướng dưới cùng và phần đầu ứng dụng

Thanh điều hướng dưới cùng và phần đầu luôn hiển thị ở mọi màn hình, giúp bạn chuyển nhanh giữa các chức năng.

- **Thanh điều hướng dưới cùng gồm bốn thẻ:** Lịch hẹn, Bệnh nhân, Gọi, Hồ sơ. Chạm vào một thẻ để chuyển đến màn hình tương ứng.
- **Nút chuyển ngôn ngữ VI/EN ở phần đầu:** chạm để chuyển ứng dụng giữa tiếng Việt và tiếng Anh.
- **Chuông thông báo:** hiển thị số lượng thông báo mới; chạm để xem.

**Lưu ý:** Khi có phiên bản ứng dụng mới, hệ thống sẽ hiển thị một biểu ngữ. Chạm **Cập nhật ngay** để tải phiên bản mới nhất.

## Thẻ Lịch hẹn

Thẻ Lịch hẹn là màn hình làm việc chính trong ngày. Màn hình hiển thị các buổi thăm khám được phân công và cho phép xem theo Ngày, Tuần hoặc Tháng.

### Lịch hẹn — Dạng xem Ngày

Sử dụng dạng xem Ngày để theo dõi toàn bộ lịch của một ngày, mỗi buổi thăm khám được hiển thị trên một thẻ riêng. Đây là màn hình được sử dụng nhiều nhất khi đi thăm khám.

![Dạng xem Ngày liệt kê từng buổi thăm khám dưới dạng thẻ với thời gian, trạng thái và thao tác nhanh](IMG:pwa_01_today_day.png)

**Nội dung hiển thị trên màn hình:**

- Phần đầu gồm **ngày hiện tại**, nút **Hôm nay**, mũi tên **trước/sau** và **bộ chọn ngày** để chuyển đến một ngày bất kỳ.
- Nút chuyển **Ngày / Tuần / Tháng** để thay đổi cách hiển thị lịch thăm khám.
- Một **thẻ lịch hẹn** cho mỗi buổi thăm khám, gồm:
  - **Thời gian** và **thời lượng** của buổi thăm khám.
  - **Trạng thái**, ví dụ Hoàn thành hoặc Đã phân công.
  - **Tên và mã bệnh nhân**.
  - **Loại dịch vụ**.
  - Các nút nhanh **Gọi** và **Bản đồ**.

**Cách thực hiện:**

1. Chạm **Hôm nay** để quay lại các lịch thăm khám của ngày hiện tại bất cứ lúc nào.
2. Chạm mũi tên **trước/sau** để chuyển từng ngày hoặc chạm **bộ chọn ngày** để chuyển thẳng đến một ngày cụ thể.
3. Trên thẻ lịch hẹn, chạm **Gọi** để gọi cho bệnh nhân hoặc **Bản đồ** để xem chỉ đường đến địa điểm thăm khám.
4. Chạm vào khu vực còn lại của thẻ để mở bảng chi tiết lịch hẹn (xem phần *Mở lịch hẹn* bên dưới).

**Mẹo:** Trạng thái trên mỗi thẻ được cập nhật theo thời gian thực, giúp bạn nhanh chóng nhận biết buổi thăm khám nào đã hoàn thành và buổi nào chưa thực hiện.

### Lịch hẹn — Dạng xem Tuần

Sử dụng dạng xem Tuần để biết các buổi thăm khám được phân bổ như thế nào trong cả tuần.

![Dạng xem Tuần nhóm các buổi thăm khám theo ngày](IMG:pwa_03_week.png)

**Nội dung hiển thị trên màn hình:**

- Phần đầu ngày và nút chuyển **Ngày / Tuần / Tháng** giống dạng xem Ngày.
- Các buổi thăm khám được **nhóm theo ngày** trong tuần.

**Cách thực hiện:**

1. Chạm **Tuần** trên nút chuyển để mở dạng xem này.
2. Sử dụng mũi tên **trước/sau** hoặc **bộ chọn ngày** để chuyển giữa các tuần.
3. Chạm vào một buổi thăm khám để mở bảng chi tiết.

### Lịch hẹn — Dạng xem Tháng

Sử dụng dạng xem Tháng để có cái nhìn tổng quan về những ngày có lịch thăm khám.

![Dạng xem Tháng dưới dạng lịch, có chấm đánh dấu những ngày có lịch thăm khám](IMG:pwa_04_month.png)

**Nội dung hiển thị trên màn hình:**

- **Lịch tháng** đầy đủ.
- Các **chấm đánh dấu** trên những ngày có lịch thăm khám.

**Cách thực hiện:**

1. Chạm **Tháng** trên nút chuyển để mở dạng xem này.
2. Tìm các **chấm đánh dấu** để biết ngày nào có lịch thăm khám.
3. Chạm vào một ngày để xem các lịch hẹn của ngày đó.

### Mở lịch hẹn và quy trình thực hiện dịch vụ của điều dưỡng

Khi chạm vào một buổi thăm khám, bảng chi tiết sẽ mở. Tại đây, bạn thực hiện lần lượt các bước của buổi thăm khám bằng các nút thao tác dịch vụ. Đây là quy trình cốt lõi trong công việc hằng ngày trên ứng dụng.

![Bảng chi tiết lịch hẹn với các nút thao tác dịch vụ](IMG:pwa_02_booking_detail.png)

**Nội dung hiển thị trên màn hình:**

- Chi tiết của buổi thăm khám.
- Các **nút thao tác dịch vụ** hướng dẫn bạn qua từng bước: Chấp nhận, Bắt đầu dịch vụ, Hoàn thành.

**Cách thực hiện — quy trình dịch vụ của điều dưỡng:**

1. **Chấp nhận** phân công để xác nhận. Thao tác này cho văn phòng biết bạn đã tiếp nhận buổi thăm khám.
2. Khi đến nơi, chạm **Bắt đầu dịch vụ** để khởi động bộ đếm giờ của buổi thăm khám.
3. **Ghi nhận thông tin lâm sàng** trong quá trình thực hiện.
4. Khi kết thúc, chạm **Hoàn thành** để hoàn tất dịch vụ.

| Nút | Chức năng |
| --- | --- |
| Chấp nhận | Xác nhận tiếp nhận phân công |
| Bắt đầu dịch vụ | Khởi động bộ đếm giờ khi đến nơi |
| Hoàn thành | Đánh dấu dịch vụ đã hoàn tất |

**Lưu ý:** Khi bạn thực hiện các bước trên, trạng thái lịch hẹn được cập nhật theo thời gian thực và đồng bộ về văn phòng, giúp nhóm vận hành luôn theo dõi được tiến độ hiện tại.

## Thẻ Bệnh nhân

### Danh sách bệnh nhân

Thẻ Bệnh nhân cho phép tìm kiếm những người thuộc phạm vi chăm sóc để xem thông tin trước hoặc trong buổi thăm khám.

![Thẻ Bệnh nhân với danh sách có thể tìm kiếm và thông tin chi tiết](IMG:pwa_05_patients.png)

**Nội dung hiển thị trên màn hình:**

- Ô **tìm kiếm** bệnh nhân.
- **Danh sách bệnh nhân** và **thông tin chi tiết**, giới hạn trong các bệnh nhân thuộc khu vực phụ trách của bạn.

**Cách thực hiện:**

1. Nhập tên vào ô **tìm kiếm** để tìm bệnh nhân.
2. Chạm vào một bệnh nhân để xem thông tin.

**Lưu ý:** Bạn chỉ có thể xem bệnh nhân thuộc khu vực phụ trách của mình.

## Thẻ Gọi

### Gọi nhanh cho phòng khám

Thẻ Gọi là lối tắt để gọi cho phòng khám bất cứ khi nào cần liên hệ với văn phòng.

![Thẻ Gọi cho phép gọi số điện thoại phòng khám chỉ bằng một thao tác](IMG:pwa_06_call.png)

**Cách thực hiện:**

1. Chạm vào thẻ **Gọi**.
2. Chạm nút gọi để **quay số điện thoại của phòng khám**.

## Thẻ Hồ sơ

### Hồ sơ, đồng bộ và đăng xuất

Thẻ Hồ sơ hiển thị tài khoản đang đăng nhập và cung cấp các nút để đồng bộ dữ liệu hoặc đăng xuất an toàn.

![Thẻ Hồ sơ hiển thị tên, email, nút Đồng bộ dữ liệu và Đăng xuất](IMG:pwa_07_profile.png)

**Nội dung hiển thị trên màn hình:**

- **Tên** và **email** của bạn.
- Nút **Đồng bộ dữ liệu**.
- Nút **Đăng xuất** màu đỏ.

**Cách thực hiện:**

1. Chạm **Đồng bộ dữ liệu** để tải dữ liệu mới nhất từ văn phòng và gửi lên các thay đổi đã thực hiện khi không có mạng.
2. Chạm **Đăng xuất** khi kết thúc sử dụng ứng dụng.

| Nút | Chức năng |
| --- | --- |
| Đồng bộ dữ liệu | Tải dữ liệu mới nhất và gửi lên các thay đổi đã thực hiện ngoại tuyến |
| Đăng xuất | Đăng xuất và xóa dữ liệu bệnh nhân được lưu tạm trên thiết bị |

**Cảnh báo:** Khi đăng xuất, dữ liệu bệnh nhân được lưu tạm trên thiết bị sẽ bị xóa để bảo vệ quyền riêng tư. Chỉ đăng xuất khi thực sự kết thúc phiên làm việc và phải bảo đảm mọi thay đổi ngoại tuyến đã được đồng bộ trước đó.

**Mẹo:** Nếu dữ liệu có vẻ chưa cập nhật, hãy chạm **Đồng bộ dữ liệu**. Đây cũng là cách gửi các thay đổi ngoại tuyến về văn phòng sau khi thiết bị có kết nối mạng trở lại.
