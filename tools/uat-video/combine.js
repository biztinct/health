// Join recorded test videos into one MP4 with a chapter per test and one Vietnamese
// subtitle track (each test's captions shifted to its place in the whole).
// usage: node combine.js "<output name>" <test folder> [<test folder> ...]
// Test folders are under the evidence root (config.js evidenceRoot, or EVIDENCE_ROOT).
const { execFileSync } = require('child_process');
const FFMPEG = require('ffmpeg-static');
const fs = require('fs');
const path = require('path');
const CFG = require('./config');

const root = process.env.EVIDENCE_ROOT || CFG.evidenceRoot;
const [outName, ...dirs] = process.argv.slice(2);

const duration = (file) => {
  let err = '';
  try { execFileSync(FFMPEG, ['-hide_banner', '-i', file], { stdio: 'pipe' }); } catch (e) { err = e.stderr.toString(); }
  const m = err.match(/Duration: (\d+):(\d+):(\d+\.\d+)/);
  return (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]);
};
const srtTime = (s) => {
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${x.toFixed(3).padStart(6, '0').replace('.', ',')}`;
};
const parseSrt = (txt) => txt.trim().split(/\n\s*\n/).map((b) => {
  const [, times, ...lines] = b.split('\n');
  const [a, z] = times.split(' --> ').map((t) => { const [hms, ms] = t.split(','); const [h, m, s] = hms.split(':').map(Number); return h * 3600 + m * 60 + s + ms / 1000; });
  return { a, z, text: lines.join('\n') };
});

const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'uatv-'));
let offset = 0;
const list = [], chapters = [], cues = [];
for (const d of dirs) {
  const dir = path.join(root, d);
  const mp4 = fs.readdirSync(dir).find((f) => f.endsWith('.mp4'));
  const srt = fs.readdirSync(dir).find((f) => f.endsWith('.srt'));
  const file = path.join(dir, mp4);
  const len = duration(file);
  list.push(`file '${file.replace(/'/g, "'\\''")}'`);
  chapters.push({ start: offset, end: offset + len, title: mp4.replace(/\.mp4$/, '') });
  if (srt) for (const c of parseSrt(fs.readFileSync(path.join(dir, srt), 'utf8'))) cues.push({ a: c.a + offset, z: c.z + offset, text: c.text });
  offset += len;
}
fs.writeFileSync(path.join(tmp, 'list.txt'), list.join('\n') + '\n');
fs.writeFileSync(path.join(tmp, 'vi.srt'), cues.map((c, i) => `${i + 1}\n${srtTime(c.a)} --> ${srtTime(c.z)}\n${c.text}\n`).join('\n'));
fs.writeFileSync(path.join(tmp, 'meta.txt'), ';FFMETADATA1\n' + `title=${outName}\n` + chapters.map((c) =>
  `[CHAPTER]\nTIMEBASE=1/1000\nSTART=${Math.round(c.start * 1000)}\nEND=${Math.round(c.end * 1000)}\ntitle=${c.title}\n`).join(''));

const out = path.join(root, `${outName}.mp4`);
execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(tmp, 'list.txt'),
  '-i', path.join(tmp, 'vi.srt'), '-i', path.join(tmp, 'meta.txt'),
  '-map', '0:v', '-map', '1:0', '-map_metadata', '2', '-map_chapters', '2',
  '-c:v', 'copy', '-c:s', 'mov_text', '-metadata:s:s:0', `language=${CFG.sub.code}`, '-metadata:s:s:0', `title=${CFG.sub.title}`,
  '-movflags', '+faststart', out]);
fs.copyFileSync(path.join(tmp, 'vi.srt'), path.join(root, `${outName} - ${CFG.sub.file} captions.srt`));
fs.rmSync(tmp, { recursive: true, force: true });
console.log(`${out} · ${(fs.statSync(out).size / 1048576).toFixed(1)} MB · ${Math.round(offset)} s · ${chapters.length} chapters`);
chapters.forEach((c) => console.log(`  ${new Date(c.start * 1000).toISOString().slice(14, 19)}  ${c.title}`));
