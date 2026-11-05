// TC-07 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-07", {
  title: "Public holiday night home examination, price and invoice",
  title_vi: "Khám tại nhà đêm ngày lễ, giá và hóa đơn",
  expected: "bs_020 | Internal examination / Khám nội khoa: 1 × base 500,000 + adjustment 2,200,000 − base discount 0% = 2,700,000 VND. PUBLIC HOLIDAY (test, 19 Oct): is after hours or weekend: add 150,000 (seq 1) + starting after 20:00: add 250,000 (seq 2) → 900,000; is public holiday: multiply × 3 (seq 4) → 2,700,000\nTOTAL 2,700,000 VND; VAT 0; final due 0 VND. Parking 0 VND is staff reimbursement, excluded from client total.",
});
