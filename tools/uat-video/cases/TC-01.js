// TC-01 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-01", {
  title: "Weekday clinic examination, price and invoice",
  title_vi: "Khám tại phòng khám ngày thường, giá và hóa đơn",
  expected: "bs_020 | Internal examination / Khám nội khoa: 1 × base 500,000 + adjustment 0 − base discount 0% = 500,000 VND. None — weekday, in hours, at clinic\nTOTAL 500,000 VND; VAT 0; final due 0 VND. Parking 0 VND is staff reimbursement, excluded from client total.",
});
