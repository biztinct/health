// TC-13 client test case (Ho Chi Minh City): re-book live on the client price list five weeks later
// (same weekday and time, no staff) and prove each line, rule and total; then prove the original
// 29 Oct booking's invoice. Data and helpers: tchcm_common.js.
const t = require('./tchcm_common');
const k = t.CASES['TC-13'];

module.exports = {
  meta: { ...t.meta('TC-13', k), expected: t.expected(k) },
  proofVi: {},
  async run(kit) { await t.runCase(kit, 'TC-13'); },
};
