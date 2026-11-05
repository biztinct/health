// TC-04 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-04", {
  title: "Home wound care at 6 km, price and invoice",
  title_vi: "Thay băng tại nhà 6 km, giá và hóa đơn",
  expected: "đd_020 | Change wound dressing < 5cm / Thay băng vết thương < 5cm: 3 × base 200,000 + adjustment -250,000 − base discount 0% = 350,000 VND. Subsequent wounds on same visit: replace 50,000 for wounds 2 and 3 → 200,000 + 2 × 50,000 = 300,000 (seq 1); distance 6 km — any nursing service 5–8 km: add 50,000 (seq 5, once per visit, on this line) → 350,000\nđd_220 | Capillary blood glucose test / Kiểm tra đường huyết mao mạch: 1 × base 50,000 + adjustment 0 − base discount 0% = 50,000 VND. None — item added by the nurse at the visit\nTOTAL 400,000 VND; VAT 0; final due 0 VND. Parking 100,000 VND is staff reimbursement, excluded from client total.",
});
