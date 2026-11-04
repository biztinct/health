// Record one acceptance test as video evidence.
// usage: node run.js CT-01 [--out <dir>]
const path = require('path');
const fs = require('fs');
const { Kit, safeName } = require('./kit');
const CFG = require('./config');

(async () => {
  const id = process.argv[2];
  const oi = process.argv.indexOf('--out');
  const root = oi > 0 ? process.argv[oi + 1] : CFG.evidenceRoot;
  const tc = require(`./cases/${id}.js`);
  const outDir = path.join(root, safeName(`${tc.meta.id} ${tc.meta.title}`));
  fs.mkdirSync(outDir, { recursive: true });
  const kit = new Kit(tc.meta, outDir);
  kit._proofVi = tc.proofVi || {};
  const started = Date.now();
  await kit.start();
  try {
    await kit.titleCard();
    await tc.run(kit);
  } catch (e) {
    console.log('  STEP ERROR:', e.message.split('\n')[0]);
    await kit.page.screenshot({ path: path.join(outDir, 'error.png') }).catch(() => {});
    kit.proofs.push({ label: 'Script reached the end', ok: false, detail: e.message.split('\n')[0] });
  }
  const file = await kit.finish();
  const mb = (fs.statSync(file).size / 1048576).toFixed(1);
  console.log(`${tc.meta.id}: ${kit.passed ? 'PASS' : 'FAIL'} · ${mb} MB · ${((Date.now() - started) / 1000).toFixed(0)}s · ${file}`);
  console.log('  records:', JSON.stringify(kit.records));
  process.exit(kit.passed ? 0 : 1);
})();
