# Tài chính — Hóa đơn, thanh toán và công nợ phải thu

Khu vực Tài chính là nơi xử lý mọi công việc liên quan đến tiền: lập hóa đơn, thu tiền và theo dõi những khách hàng vẫn còn nợ (công nợ phải thu, hay “AR”). Chương này hướng dẫn từng màn hình, từ Bảng điều khiển tổng quan đến sổ chi tiết công nợ phải thu.

Menu Tài chính gồm các mục:

- **Bảng điều khiển** — tổng quan Trung tâm tài chính
- **Hóa đơn** — tạo và quản lý hóa đơn
- **Bảng điều khiển công nợ phải thu** — xem công nợ còn tồn và tuổi nợ
- **Quản lý công nợ phải thu** — Thanh toán tài khoản, Tiền đang vận chuyển, Hoàn tiền / Ghi có
- **Thanh toán** — toàn bộ giao dịch thanh toán
- **Khách hàng quá hạn** — danh sách công việc thu hồi công nợ
- **Nhật ký VAT** — theo dõi VAT / hóa đơn đỏ
- **Giao dịch công nợ phải thu** — sổ chi tiết công nợ

## Bảng điều khiển (Trung tâm tài chính)

### Trung tâm tài chính

Đây là màn hình làm việc chính của bộ phận Tài chính. Màn hình cung cấp một cái nhìn tổng quan trực tiếp về doanh thu, số tiền khách hàng còn nợ, tiền đã thu và hoạt động gần đây, giúp bạn nhanh chóng nhận biết nội dung cần xử lý mà không phải mở nhiều danh sách.

![Bảng điều khiển Trung tâm tài chính với các thẻ KPI, thanh toán gần đây và xu hướng doanh thu](IMG:fin_01_dashboard.png)

**Nội dung hiển thị trên màn hình:**

- **Phần đầu** — có tiêu đề “Trung tâm tài chính — Lập hóa đơn, thanh toán và công nợ phải thu”, nút **Hóa đơn mới** và **bộ lọc thời gian** để chọn khoảng dữ liệu cần xem.
- **Các thẻ KPI** (có thể nhấp vào để mở dữ liệu chi tiết):
  - **Doanh thu** — doanh thu trong kỳ từ các hóa đơn đã ghi sổ.
  - **Công nợ phải thu còn tồn** — các khoản chưa thanh toán hoặc mới thanh toán một phần.
  - **Số tiền quá hạn** — khoản tiền đã quá ngày đến hạn.
  - **Tiền đã thu** — tổng các khoản thanh toán đã tiếp nhận.
  - **Gói đang hoạt động** — số lượng gói đang hoạt động và giá trị còn lại.
  - **Chờ bàn giao** — tiền mặt điều dưỡng đã thu nhưng vẫn đang trên đường bàn giao cho phòng khám.
- **Hàng trạng thái Hóa đơn đỏ** (hóa đơn điện tử VAT tại Việt Nam) — có thể hiển thị số lượng Đã phát hành, Thất bại, Chờ phát hành và Đã hủy.
- **Thanh toán gần đây** — danh sách gồm ảnh đại diện, khách hàng, mã tham chiếu, phương thức, số tiền và nhãn trạng thái như Đã thu, Chờ bàn giao hoặc Đã đối soát.
- **Xu hướng doanh thu** — biểu đồ cột của 6 tháng gần nhất.
- **Thao tác nhanh** — các nút lối tắt: Hóa đơn mới, Thanh toán, Bảng điều khiển công nợ phải thu, Nhật ký VAT.
- **Phân loại trạng thái hóa đơn** — tổng số theo trạng thái: Nháp, Đã ghi sổ, Đã thanh toán, Thanh toán một phần, Quá hạn, Đã hủy.

**Cách thực hiện:**

1. Sử dụng **bộ lọc thời gian** ở phần đầu để đặt khoảng ngày. Tất cả các thẻ KPI sẽ cập nhật theo khoảng thời gian đã chọn.
2. Nhấp vào một **thẻ KPI**, ví dụ Công nợ phải thu còn tồn, để mở danh sách các bản ghi tạo nên chỉ số đó.
3. Nhấp vào một dòng trong **Thanh toán gần đây** để mở khoản thanh toán và xem đầy đủ chi tiết.
4. Nhấp vào một nút **Thao tác nhanh** để chuyển thẳng đến màn hình tương ứng: **Hóa đơn mới** bắt đầu tạo hóa đơn; **Thanh toán** mở danh sách thanh toán; **Bảng điều khiển công nợ phải thu** mở dữ liệu công nợ; **Nhật ký VAT** mở dữ liệu theo dõi VAT.
5. Xem **Phân loại trạng thái hóa đơn** để biết có bao nhiêu hóa đơn vẫn ở trạng thái Nháp, Đã ghi sổ, Quá hạn và các trạng thái khác.

**Mẹo:** Thẻ KPI là cách nhanh nhất để kiểm tra một số liệu có vẻ bất thường. Nếu Số tiền quá hạn cao, hãy nhấp vào thẻ để xem chính xác những hóa đơn nào đã quá hạn.

## Hóa đơn

### Danh sách hóa đơn

Đây là nơi quản lý hóa đơn. Sử dụng màn hình này để tạo hóa đơn mới, kiểm tra hóa đơn hiện có, xác nhận để ghi nhận doanh thu và theo dõi tình trạng thanh toán.

![Danh sách Hóa đơn với các thẻ trạng thái và bộ lọc ngày](IMG:fin_02_invoices_list.png)

**Nội dung hiển thị trên màn hình:**

- **Các thẻ trạng thái** — lọc hóa đơn theo từng giai đoạn.
- **Bộ lọc ngày** — thu hẹp danh sách theo khoảng thời gian.
- Mỗi hóa đơn một dòng, hiển thị khách hàng và các thông tin chính.

Khi mở một hóa đơn, biểu mẫu có dạng như sau:

![Biểu mẫu hóa đơn hiển thị khách hàng, các dòng chi tiết, tổng tiền và trạng thái thanh toán](IMG:fin_02b_invoice_form.png)

- **Khách hàng** — người nhận hóa đơn.
- **Các dòng chi tiết** — dịch vụ hoặc sản phẩm được tính phí.
- **Tổng tiền** — tổng số tiền phải thanh toán.
- **Trạng thái thanh toán** — cho biết hóa đơn đang ở trạng thái Nháp, Đã ghi sổ, Đã thanh toán hoặc trạng thái khác.

**Cách thực hiện — quy trình từ hóa đơn đến thanh toán:**

1. Hóa đơn được tạo từ một lịch hẹn đã hoàn thành hoặc bằng cách nhấp **Hóa đơn mới**.
2. Hóa đơn bắt đầu ở trạng thái **Nháp**. Khi còn ở trạng thái Nháp, bạn có thể chỉnh sửa.
3. Nhấp **Xác nhận / Ghi sổ** để ghi sổ hóa đơn. Sau khi ghi sổ, hóa đơn được tính vào doanh thu và công nợ phải thu còn tồn.
4. Ghi nhận một khoản **thanh toán** cho hóa đơn bằng tiền mặt hoặc chuyển khoản.
5. Khi đã thanh toán đủ, trạng thái hóa đơn tự động chuyển thành **Đã thanh toán**.

**Lưu ý:** Đối với hóa đơn đã ghi sổ, bạn còn có thể phát hành hóa đơn điện tử VAT, thường được gọi là “hóa đơn đỏ”. Sau khi phát hành, hóa đơn sẽ xuất hiện trong **Nhật ký VAT**.

**Tóm tắt trạng thái hóa đơn:**

| Trạng thái | Ý nghĩa |
|---|---|
| Nháp | Mới được tạo, vẫn có thể chỉnh sửa và chưa được tính vào doanh thu. |
| Đã ghi sổ | Đã xác nhận; được tính vào doanh thu và công nợ phải thu còn tồn. |
| Thanh toán một phần | Đã nhận một phần tiền nhưng vẫn còn số dư phải thu. |
| Đã thanh toán | Đã thanh toán đầy đủ. |
| Quá hạn | Đã ghi sổ nhưng chưa thanh toán và đã quá ngày đến hạn. |
| Đã hủy | Hóa đơn đã bị hủy và không còn là khoản phải thu. |

**Cảnh báo:** Chỉ chỉnh sửa hóa đơn khi còn ở trạng thái **Nháp**. Sau khi ghi sổ, hóa đơn đã được tính vào doanh thu và công nợ phải thu, vì vậy mọi thay đổi cần được thực hiện thận trọng.

## Công nợ phải thu

### Bảng điều khiển công nợ phải thu

Bảng điều khiển công nợ phải thu hiển thị toàn bộ số tiền khách hàng vẫn còn nợ. Sử dụng màn hình này để trả lời ba câu hỏi: “Ai đang nợ?”, “Nợ bao nhiêu?” và “Đã quá hạn bao lâu?”, bao gồm cả phân tích tuổi nợ.

![Bảng điều khiển công nợ phải thu hiển thị dữ liệu dưới dạng danh sách, bảng tổng hợp và biểu đồ](IMG:fin_03_ar_dashboard.png)

**Nội dung hiển thị trên màn hình:**

- Công nợ phải thu còn tồn được trình bày dưới dạng **danh sách**, **bảng tổng hợp** và **biểu đồ**.

**Cách thực hiện:**

1. Sử dụng dạng **danh sách** để xem từng khoản công nợ còn tồn theo khách hàng.
2. Chuyển sang **bảng tổng hợp** để tổng hợp và nhóm công nợ, ví dụ theo khách hàng hoặc kỳ.
3. Chuyển sang **biểu đồ** để xem trực quan tổng công nợ và tuổi nợ.

**Mẹo:** Sử dụng màn hình này để phân tích tuổi nợ, tức thời gian hóa đơn đã ở trạng thái chưa thanh toán, từ đó xác định khách hàng cần được liên hệ trước.

### Quản lý công nợ phải thu

Quản lý công nợ phải thu là menu con gồm ba công cụ: ghi nhận thanh toán, theo dõi tiền mặt do điều dưỡng thu và phát hành chứng từ ghi có.

![Sổ giao dịch công nợ phải thu](IMG:fin_08_ar_transactions.png)

**Nội dung hiển thị trong menu con:**

- **Thanh toán tài khoản** — mở trình hướng dẫn thu tiền để ghi nhận khoản thanh toán cho khách hàng hoặc hóa đơn.
- **Tiền đang vận chuyển** — tiền mặt do điều dưỡng thu và đang chờ bàn giao cho phòng khám; đây cũng là chỉ số **Chờ bàn giao** trên Bảng điều khiển.
- **Hoàn tiền / Ghi có** — các chứng từ ghi có cho khách hàng.

**Cách thực hiện:**

1. Chọn **Thanh toán tài khoản** khi khách hàng thanh toán. Trình hướng dẫn thu tiền sẽ mở; ghi nhận khoản thanh toán cho khách hàng hoặc hóa đơn tương ứng.
2. Chọn **Tiền đang vận chuyển** để xem tiền mặt điều dưỡng đã thu nhưng chưa được bàn giao và đối soát tại phòng khám.
3. Chọn **Hoàn tiền / Ghi có** để phát hành chứng từ ghi có cho khách hàng.

**Lưu ý:** “Tiền đang vận chuyển” và KPI “Chờ bàn giao” trên Bảng điều khiển cùng chỉ một loại dữ liệu: tiền mặt do điều dưỡng thu nhưng chưa được bàn giao cho phòng khám.

## Thanh toán và thu hồi công nợ

### Thanh toán

Màn hình này liệt kê tất cả giao dịch thanh toán. Sử dụng để xác nhận một khoản thanh toán cụ thể, kiểm tra phương thức và số tiền, hoặc xem khoản tiền đã được đối soát hay chưa.

![Danh sách Thanh toán với phương thức, số tiền, ngày và trạng thái](IMG:fin_05_payments.png)

**Nội dung hiển thị trên màn hình:**

- Mỗi khoản thanh toán một dòng, gồm **phương thức**, **số tiền**, **ngày** và **trạng thái**.

**Trạng thái thanh toán:**

| Trạng thái | Ý nghĩa |
|---|---|
| Đã thu | Khoản thanh toán đã được tiếp nhận. |
| Chờ bàn giao | Tiền mặt do điều dưỡng giữ và chưa được bàn giao cho phòng khám. |
| Đã bàn giao | Tiền mặt đã được bàn giao. |
| Đã đối soát | Khoản thanh toán đã được khớp và xác nhận trong sổ sách. |

**Cách thực hiện:**

1. Tìm khoản thanh toán theo khách hàng, ngày hoặc số tiền.
2. Nhấp vào một dòng thanh toán để mở và xem đầy đủ chi tiết.
3. Kiểm tra cột **trạng thái** để biết mỗi khoản thanh toán đang ở bước nào, từ Đã thu đến Đã đối soát.

### Khách hàng quá hạn

Đây là danh sách công việc thu hồi công nợ: các hóa đơn đã ghi sổ, chưa thanh toán và đã quá ngày đến hạn. Sử dụng màn hình này để biết chính xác cần liên hệ khách hàng nào để thu tiền.

![Danh sách Khách hàng quá hạn gồm các hóa đơn đã ghi sổ, chưa thanh toán và quá hạn](IMG:fin_06_overdue.png)

**Nội dung hiển thị trên màn hình:**

- Danh sách **hóa đơn đã ghi sổ, chưa thanh toán và đã quá ngày đến hạn**.

**Cách thực hiện:**

1. Mở màn hình này để lấy danh sách các khoản công nợ quá hạn.
2. Lần lượt liên hệ từng khách hàng để thu hồi khoản thanh toán.
3. Khi thanh toán được tiếp nhận và hóa đơn được tất toán, hóa đơn sẽ tự động không còn xuất hiện trong danh sách.

**Mẹo:** Kiểm tra Khách hàng quá hạn thường xuyên. Đây là cách trực tiếp nhất để kiểm soát công nợ phải thu.

## Thuế và sổ chi tiết

### Nhật ký VAT

Nhật ký VAT theo dõi các hóa đơn khách hàng đã ghi sổ phục vụ mục đích VAT và hóa đơn đỏ. Sử dụng màn hình này khi cần kiểm tra hoặc xử lý hóa đơn điện tử VAT tại Việt Nam.

![Nhật ký VAT của các hóa đơn khách hàng đã ghi sổ dùng để theo dõi VAT và hóa đơn đỏ](IMG:fin_07_vat_log.png)

**Nội dung hiển thị trên màn hình:**

- Danh sách **hóa đơn khách hàng đã ghi sổ** được theo dõi cho mục đích VAT / hóa đơn đỏ.

**Cách thực hiện:**

1. Mở Nhật ký VAT để kiểm tra các hóa đơn đã ghi sổ liên quan đến VAT.
2. Đối chiếu với hàng trạng thái Hóa đơn đỏ trên Bảng điều khiển (Đã phát hành, Thất bại, Chờ phát hành, Đã hủy) để xác định hóa đơn nào vẫn cần xử lý.

**Lưu ý:** Có thể phát hành hóa đơn điện tử VAT, hay “hóa đơn đỏ”, cho một hóa đơn đã ghi sổ. Sau khi phát hành, hóa đơn được theo dõi tại đây.

### Giao dịch công nợ phải thu

Giao dịch công nợ phải thu là sổ chi tiết công nợ. Sử dụng khi cần xem toàn bộ lịch sử từng dòng giao dịch thay vì chỉ xem số liệu tổng hợp.

![Sổ chi tiết Giao dịch công nợ phải thu](IMG:fin_08_ar_transactions.png)

**Nội dung hiển thị trên màn hình:**

- **Sổ chi tiết công nợ phải thu**, gồm đầy đủ từng giao dịch công nợ.

**Cách thực hiện:**

1. Mở Giao dịch công nợ phải thu khi cần truy vết chi tiết một khoản công nợ.
2. Kiểm tra từng bút toán để đối soát số dư hoặc điều tra tài khoản của một khách hàng cụ thể.

**Mẹo:** Sử dụng Bảng điều khiển công nợ phải thu để xem tổng quan và tuổi nợ; chuyển sang Giao dịch công nợ phải thu khi cần dữ liệu chi tiết đến từng giao dịch.
