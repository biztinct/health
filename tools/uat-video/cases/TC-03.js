// TC-03 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-03", {
  title: "Online examination with 10% discount, price and invoice",
  title_vi: "Khám nội trực tuyến giảm 10%, giá và hóa đơn",
  expected: "bs_030 | Online internal examination / Khám nội trực tuyến: 1 × base 200,000 + adjustment 0 − base discount 10% = 180,000 VND. None — weekday, in hours\nTOTAL 180,000 VND; VAT 0; final due 180,000 VND. Parking 0 VND is staff reimbursement, excluded from client total.",
});
