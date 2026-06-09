# Quản trị — Người dùng, dữ liệu danh mục, định giá và cài đặt

Khu vực Quản trị là nơi thiết lập và cấu hình toàn bộ hệ thống: những người có thể đăng nhập, các danh mục tham chiếu được sử dụng ở các màn hình khác, cách tính giá và các tùy chọn áp dụng cho toàn công ty. Phần lớn nhân viên vận hành hằng ngày chỉ sử dụng một số ít màn hình trong khu vực này, nhưng mọi cấu hình phục vụ lịch hẹn, báo giá và lập lịch đều được quản lý tại đây.

## Làm quen với khu vực Quản trị

### Bảng điều khiển Quản trị

Bảng điều khiển Quản trị là điểm bắt đầu. Màn hình cung cấp cái nhìn nhanh về tình trạng hệ thống và các lối tắt đến những nội dung được thiết lập thường xuyên nhất.

![Bảng điều khiển Quản trị với các thẻ KPI, Thao tác nhanh và Hoạt động gần đây](IMG:admin_01_dashboard.png)

**Nội dung hiển thị trên màn hình**

- **Các thẻ KPI** có thể nhấp để mở danh sách tương ứng:
  - Người dùng đang hoạt động
  - Cơ sở đang hoạt động
  - Loại dịch vụ
  - Quy tắc định giá
  - Danh mục thiết bị
  - Sự kiện kiểm toán hôm nay
- Lưới **Thao tác nhanh** với các nút: Thêm người dùng, Thêm cơ sở, Quy tắc định giá, Nhật ký kiểm toán, Dữ liệu danh mục, Nhân viên y tế.
- Bảng **Hoạt động gần đây**, hiển thị những thay đổi được kiểm toán gần nhất trong hệ thống.

**Cách thực hiện**

1. Xem các **thẻ KPI** ở phía trên để nắm nhanh tổng số hiện tại.
2. Nhấp vào một **thẻ KPI** để mở trực tiếp danh sách tương ứng, ví dụ nhấp *Người dùng đang hoạt động* để mở danh sách người dùng.
3. Sử dụng nút **Thao tác nhanh** để bắt đầu ngay một công việc thường gặp. Ví dụ, *Thêm người dùng* mở trình hướng dẫn tạo người dùng; *Thêm cơ sở* mở biểu mẫu cơ sở mới.
4. Xem bảng **Hoạt động gần đây** để biết nội dung nào vừa được thay đổi và ai đã thực hiện thay đổi.

**Mẹo:** Khi chưa biết nên bắt đầu từ đâu, lưới Thao tác nhanh cung cấp những công việc quản trị phổ biến nhất, giúp bạn không phải tìm kiếm qua nhiều menu.

## Người dùng và quyền truy cập

### Người dùng và vai trò

Đây là danh sách tài khoản người dùng nội bộ, tức những người có thể đăng nhập vào hệ thống. Quan trọng hơn, đây cũng là nơi kiểm soát **những gì mỗi người được phép xem và thực hiện** bằng cách gán vai trò.

![Danh sách Người dùng và vai trò của các tài khoản nội bộ](IMG:admin_02_users.png)

**Nội dung hiển thị trên màn hình**

- Danh sách tất cả tài khoản người dùng nội bộ.
- Nút hoặc tùy chọn tạo người dùng mới, mở trình hướng dẫn tạo người dùng.

**Vai trò kiểm soát quyền truy cập như thế nào?**

Một vai trò tập hợp các quyền quyết định người dùng có thể xem những menu và bản ghi nào. Ví dụ:

| Vai trò | Dữ liệu được phép xem |
| --- | --- |
| Điều dưỡng | Chỉ các lịch hẹn được phân công và bệnh nhân thuộc khu vực phụ trách |
| Quản lý vận hành | Tất cả lịch hẹn trong khu vực phụ trách |
| Tài chính | Các bản ghi liên quan đến tài chính |
| Chủ sở hữu / Quản trị viên | Toàn bộ hệ thống |

**Cách thực hiện**

1. Mở **Người dùng và vai trò** để xem danh sách tài khoản.
2. Để thêm một người, tạo người dùng mới. Trình **hướng dẫn tạo người dùng** sẽ mở.
3. Trong trình hướng dẫn, nhập **tên**, **tên đăng nhập / email** và gán **vai trò**. Vai trò tự động áp dụng các quyền và nhóm phù hợp.
4. Lưu người dùng. Người đó có thể đăng nhập và chỉ nhìn thấy những menu, bản ghi mà vai trò cho phép.
5. Để thay đổi quyền truy cập của người dùng hiện có, mở tài khoản và **thay đổi vai trò / nhóm** tại đây.

**Lưu ý:** Khả năng xem dữ liệu được quyết định hoàn toàn bởi vai trò đã gán. Nếu một người báo rằng họ “không nhìn thấy” lịch hẹn hoặc bệnh nhân, trước tiên hãy kiểm tra và điều chỉnh vai trò của họ trên màn hình này.

## Dữ liệu tham chiếu dùng chung trong ứng dụng

### Dữ liệu danh mục

Dữ liệu danh mục là màn hình gồm nhiều thẻ, dùng để quản lý các bảng tham chiếu mà toàn bộ ứng dụng sử dụng. Mọi nội dung xuất hiện trong danh sách lựa chọn ở các màn hình khác, như loại dịch vụ, triệu chứng hoặc nhà cung cấp bảo hiểm, đều được định nghĩa và duy trì tại đây.

![Màn hình Dữ liệu danh mục với các thẻ điều hướng giữa những bảng tham chiếu](IMG:admin_03_master_data.png)

**Nội dung hiển thị trên màn hình**

Mỗi thẻ là một danh sách kèm biểu mẫu cho một loại dữ liệu tham chiếu:

- **Cơ sở** — phòng khám / trung tâm chăm sóc tại nhà
- **Khu vực phụ trách** — khu vực địa lý cung cấp dịch vụ, được dùng để ghép bệnh nhân với nhân viên
- **Loại dịch vụ**
- **Triệu chứng**
- **Nguồn giới thiệu**
- Nhà cung cấp **bảo hiểm**
- **Mức độ khẩn cấp**
- **Nhóm bệnh nhân**
- **Chuyên khoa y tế**
- **Quận/Huyện**

**Cách thực hiện**

1. Mở **Dữ liệu danh mục** và chọn **thẻ** của danh sách cần quản lý, ví dụ *Loại dịch vụ*.
2. Để thêm một mục, tạo bản ghi mới trong danh sách của thẻ đó và nhập thông tin vào biểu mẫu.
3. Để thay đổi một mục, mở mục đó từ danh sách và chỉnh sửa.
4. Lưu. Mục mới hoặc đã cập nhật sẽ xuất hiện trong các **danh sách lựa chọn tương ứng trên toàn ứng dụng**.

**Mẹo:** Hãy duy trì chính xác dữ liệu Khu vực phụ trách. Dữ liệu này quyết định cách ghép bệnh nhân với nhân viên; một khu vực không còn chính xác có thể làm sai lệch việc phân công lịch hẹn.

### Định giá

Mục Định giá lưu các quy tắc được công cụ báo giá sử dụng để tự động tính phí. Khi một lịch hẹn được báo giá, các quy tắc sẽ tự động bổ sung khoản tiền phù hợp mà không cần nhập thủ công.

![Các quy tắc Định giá được công cụ báo giá sử dụng](IMG:admin_04_pricing.png)

**Nội dung hiển thị trên màn hình**

- **Quy tắc định giá**, có thể phụ thuộc vào:
  - Khoảng cách, theo dải khoảng cách hoặc đơn giá mỗi km
  - Khu vực
  - Loại dịch vụ
  - Thời gian
  - Mức độ khẩn cấp
- **Công cụ định giá**
- **Gói chăm sóc sức khỏe**

**Cách thực hiện**

1. Mở **Định giá** để xem các quy tắc hiện có.
2. Để thêm một khoản phí, tạo **quy tắc định giá** mới; chọn điều kiện áp dụng, ví dụ dải khoảng cách, khu vực, loại dịch vụ, thời gian hoặc mức độ khẩn cấp; sau đó nhập số tiền được cộng thêm.
3. Lưu quy tắc. Từ thời điểm đó, **công cụ báo giá** sẽ tự động áp dụng quy tắc khi một lịch hẹn đáp ứng điều kiện.
4. Quản lý **công cụ định giá** và **gói chăm sóc sức khỏe** trên cùng màn hình khi cần.

**Lưu ý:** Khoảng cách lái xe được tính trên lịch hẹn là dữ liệu đầu vào cho các quy tắc theo khoảng cách tại đây. Vì vậy, chi phí di chuyển được tự động áp dụng và không cần nhập thủ công.

## Nhân viên, thiết bị và lập lịch

### Nhân viên y tế

Đây là danh sách chính của nhân viên y tế, gồm điều dưỡng và bác sĩ. Thông tin được ghi nhận tại đây quyết định những ai có thể được phân công cho lịch hẹn.

![Danh sách chính Nhân viên y tế](IMG:admin_05_healthcare_staff.png)

**Nội dung hiển thị trên màn hình**

- Danh sách tất cả nhân viên y tế.
- Hồ sơ, vai trò, cơ sở / khu vực phụ trách, kỹ năng và khu vực dịch vụ của từng người.

**Cách thực hiện**

1. Mở **Nhân viên y tế** để xem danh sách.
2. Để thêm một người, tạo hồ sơ nhân viên mới và nhập **thông tin cá nhân**, **vai trò**, **cơ sở / khu vực phụ trách**, **kỹ năng** và **khu vực dịch vụ**.
3. Để cập nhật, mở hồ sơ nhân viên và chỉnh sửa các thông tin trên.
4. Lưu. Những thông tin này quyết định **ai có thể được phân công cho lịch hẹn**, ví dụ hệ thống sẽ đối chiếu kỹ năng và khu vực dịch vụ của nhân viên với yêu cầu của lịch hẹn.

**Mẹo:** Luôn cập nhật khu vực phụ trách, kỹ năng và khu vực dịch vụ của từng người để hệ thống đề xuất đúng nhân viên khi phân công lịch hẹn.

### Thiết bị

Thiết bị là danh mục các thiết bị di động có thể được gắn với lịch hẹn.

![Danh mục Thiết bị](IMG:admin_06_equipment.png)

**Nội dung hiển thị trên màn hình**

- Danh sách thiết bị di động.

**Cách thực hiện**

1. Mở **Thiết bị** để xem danh mục.
2. Để thêm thiết bị, tạo bản ghi thiết bị mới và lưu.
3. Thiết bị sau đó có thể được **gắn với lịch hẹn**.

### Ngày nghỉ lễ

Lịch ngày nghỉ lễ có ảnh hưởng đến việc xếp lịch và định giá. Hãy thêm các ngày nghỉ tại đây để hệ thống nhận biết ngày lễ khi sắp xếp buổi thăm khám và tính báo giá.

![Lịch Ngày nghỉ lễ](IMG:admin_07_holidays.png)

## Tuân thủ và cấu hình

### Nhật ký kiểm toán

Đây là bản ghi chỉ đọc, lưu lại ai đã thay đổi nội dung gì và vào thời điểm nào nhằm phục vụ tuân thủ. Bạn không thể chỉnh sửa nhật ký; hãy sử dụng để tra cứu và xác nhận sự việc đã xảy ra. Bảng Hoạt động gần đây trên Bảng điều khiển là phần tóm tắt nhanh từ cùng nguồn thông tin.

![Nhật ký kiểm toán các thay đổi](IMG:admin_08_audit.png)

### Yêu cầu trường dữ liệu

Đây là nơi cấu hình những trường nào trên biểu mẫu là bắt buộc. Sử dụng để bảo đảm nhân viên nhập đầy đủ thông tin thiết yếu trước khi có thể lưu bản ghi.

![Cấu hình Yêu cầu trường dữ liệu](IMG:admin_09_field_req.png)

### Cấu hình thanh bên CMS

Đây là màn hình nâng cao dùng để định nghĩa chính menu bên trái, gồm các nhóm và các mục bên trong. Thay đổi tại đây sẽ làm thay đổi giao diện điều hướng của mọi người dùng, vì vậy thông thường chỉ nên sử dụng trong quá trình thiết lập hệ thống.

![Cấu hình thanh bên CMS](IMG:admin_10_cms_sidebar.png)

**Cảnh báo:** Cấu hình thanh bên CMS kiểm soát menu của tất cả người dùng. Chỉ thay đổi khi bạn hiểu rõ tác động; một cấu hình sai có thể làm ẩn những menu mà nhân viên cần sử dụng.

### Cài đặt

Cài đặt là nơi quản lý cấu hình áp dụng cho toàn hệ thống và mọi người dùng trong công ty.

![Màn hình Cài đặt hệ thống](IMG:admin_11_settings.png)

**Các nội dung được thiết lập tại đây**

- Nhà cung cấp bản đồ / khóa API
- Tùy chọn lập hóa đơn
- Tích hợp

**Cách thực hiện**

1. Mở **Cài đặt**.
2. Tìm tùy chọn cần thiết lập, ví dụ **nhà cung cấp bản đồ / khóa API**, **lập hóa đơn** hoặc một **tích hợp**.
3. Nhập hoặc cập nhật giá trị rồi lưu. Thay đổi sẽ áp dụng cho toàn công ty.

**Lưu ý:** Đây là các tùy chọn dùng chung cho toàn công ty, vì vậy thay đổi sẽ ảnh hưởng đến mọi người dùng. Hãy thiết lập một lần trong quá trình triển khai và chỉ cập nhật khi có nội dung như khóa API hoặc tích hợp cần thay đổi.
