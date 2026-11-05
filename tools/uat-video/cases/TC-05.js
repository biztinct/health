// TC-05 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-05", {
  title: "Sunday home wound care and extra hours with 10% discount, price and invoice",
  title_vi: "Thay băng và giờ bổ sung tại nhà Chủ nhật giảm 10%, giá và hóa đơn",
  expected: "đd_020 | Change wound dressing < 5cm / Thay băng vết thương < 5cm: 1 × base 200,000 + adjustment 0 − base discount 10% = 180,000 VND. None — single wound; no weekend rule for this item\nđd_240 | Nursing fee (Additional hours) / Phí điều dưỡng (Giờ bổ sung): 2 × base 150,000 + adjustment 50,000 − base discount 10% = 320,000 VND. Is after hours or weekend (Sunday): add 50,000 (seq 1)\nTOTAL 500,000 VND; VAT 0; final due 0 VND. Parking 0 VND is staff reimbursement, excluded from client total.",
});
