// TC-06 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-06", {
  title: "Saturday evening home examination, price and invoice",
  title_vi: "Khám tại nhà tối thứ Bảy, giá và hóa đơn",
  expected: "bs_020 | Internal examination / Khám nội khoa: 1 × base 500,000 + adjustment 150,000 − base discount 0% = 650,000 VND. Is after hours or weekend (Saturday): add 150,000 (seq 1); starts before 20:00 so the night add does not apply; distance 6 km — bs_020 distance rule starts at 10 km, so no distance add\nTOTAL 650,000 VND; VAT 0; final due 650,000 VND. Parking 100,000 VND is staff reimbursement, excluded from client total.",
});
