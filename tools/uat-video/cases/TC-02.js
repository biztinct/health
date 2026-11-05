// TC-02 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-02", {
  title: "Clinic ultrasound and ECG with 10% discount, price and invoice",
  title_vi: "Siêu âm và điện tim tại phòng khám giảm 10%, giá và hóa đơn",
  expected: "bs_040 | Ultrasound + reading results / Siêu âm + đọc kết quả: 1 × base 300,000 + adjustment 0 − base discount 10% = 270,000 VND. None — at clinic (home add of 200,000 does not apply)\nbs_050 | ECG + reading results / Điện tim + đọc kết quả: 1 × base 300,000 + adjustment 0 − base discount 10% = 270,000 VND. None — at clinic (home add of 200,000 does not apply)\nTOTAL 540,000 VND; VAT 0; final due 0 VND. Parking 0 VND is staff reimbursement, excluded from client total.",
});
