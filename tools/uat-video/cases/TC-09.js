// TC-09 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-09", {
  title: "Four hours home personal care at 6 km, price and invoice",
  title_vi: "Chăm sóc cá nhân tại nhà 4 giờ 6 km, giá và hóa đơn",
  expected: "đd_190 | Daytime personal care (minimum 3 hours) / Chăm sóc cá nhân ban ngày (tối thiểu 3 giờ): 4 × base 100,000 + adjustment 50,000 − base discount 0% = 450,000 VND. Distance 6 km — any nursing service 5–8 km: add 50,000 (seq 5) → 450,000\nTOTAL 450,000 VND; VAT 0; final due 450,000 VND. Parking 0 VND is staff reimbursement, excluded from client total.",
});
