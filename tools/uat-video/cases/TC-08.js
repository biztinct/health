// TC-08 client test case (Hanoi): re-booked live 5 weeks later + the original booking's invoice.
// All logic and data: tchn_common.js.
module.exports = require('./tchn_common').make("TC-08", {
  title: "Home injections and ultrasound with 10% discount, price and invoice",
  title_vi: "Tiêm và siêu âm tại nhà giảm 10%, giá và hóa đơn",
  expected: "đd_060 | Intramuscular/intradermal/subcutaneous injection / Tiêm bắp/ trong da/ dưới da: 3 × base 150,000 + adjustment -200,000 − base discount 10% = 205,000 VND. After 1st injection: replace 50,000 for injections 2 and 3 → 150,000 + 2 × 50,000 = 250,000 (seq 1)\nbs_040 | Ultrasound + reading results / Siêu âm + đọc kết quả: 1 × base 300,000 + adjustment 200,000 − base discount 10% = 470,000 VND. Is service at home: add 200,000 (seq 1)\nTOTAL 675,000 VND; VAT 0; final due 0 VND. Parking 100,000 VND is staff reimbursement, excluded from client total.",
});
