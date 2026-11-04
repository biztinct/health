// UAT video-evidence kit: drives carejiox.com with Playwright, draws the evidence
// overlays inside the page (so they are part of the capture), records sharp frames
// over CDP screencast and assembles an H.264 MP4 with a Vietnamese subtitle track.
//
// A case calls kit.step / kit.click / kit.type / kit.proof. Every proof is also an
// assertion: the end card says PASS only when all of them matched on screen.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const FFMPEG = require('ffmpeg-static');
const fs = require('fs');
const path = require('path');

const BASE = 'https://carejiox.com';
const VIEW = { width: 1280, height: 720 };
const SCALE = 1.5;                       // 1280x720 layout captured at 1920x1080
const TZ = 'Asia/Ho_Chi_Minh';
const FPS = 25;

// ---------------------------------------------------------------- overlay (in page)
// Installed on every document. State lives in sessionStorage so captions survive
// the full page load after sign-in. Flat single colours only.
const OVERLAY = `(() => {
  if (window.__uv) return; window.__uv = true;
  const css = \`
  #uv-root, #uv-root * { box-sizing: border-box; font-family: Inter, "Segoe UI", Roboto, Arial, sans-serif; }
  #uv-root { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647; }
  #uv-cursor { position: fixed; left: -40px; top: -40px; width: 22px; height: 22px; transition: none; }
  .uv-ring { position: fixed; width: 34px; height: 34px; margin: -17px 0 0 -17px; border-radius: 50%;
             border: 3px solid #E53935; animation: uvring .6s ease-out forwards; }
  @keyframes uvring { from { transform: scale(.4); opacity: 1 } to { transform: scale(1.6); opacity: 0 } }
  #uv-badge { position: fixed; top: 9px; left: 50%; transform: translateX(-50%); background: #0F1640;
              color: #fff; font-size: 12px; font-weight: 600; padding: 5px 12px; border-radius: 6px;
              letter-spacing: .2px; white-space: nowrap; }
  #uv-badge b { color: #FFC857; font-weight: 700; }
  #uv-cap { position: fixed; left: 50%; bottom: 14px; transform: translateX(-50%); max-width: 1000px;
            background: #0F1640; color: #fff; font-size: 15px; font-weight: 500; padding: 9px 16px;
            border-radius: 8px; display: none; align-items: center; gap: 12px; }
  #uv-cap .n { background: #FFC857; color: #0F1640; font-weight: 800; font-size: 12px; padding: 3px 8px;
               border-radius: 5px; white-space: nowrap; }
  .uv-box { position: fixed; border: 3px solid #16A34A; border-radius: 6px; background: rgba(22,163,74,.08); }
  .uv-box.bad { border-color: #DC2626; background: rgba(220,38,38,.08); }
  #uv-cap.top { bottom: auto; top: 54px; }
  #uv-cap.ok { background: #15803D; }
  #uv-cap.bad { background: #B91C1C; }
  #uv-cap.ok .n, #uv-cap.bad .n { background: #fff; color: #15803D; }
  #uv-cap.bad .n { color: #B91C1C; }
  #uv-card { position: fixed; inset: 0; background: #F7F8FC; display: none; align-items: center;
             justify-content: center; pointer-events: auto; }
  #uv-card .c { width: 860px; background: #fff; border: 1px solid #DDE1EE; border-radius: 14px; padding: 34px 40px; }
  #uv-card .k { color: #5B6380; font-size: 12px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; }
  #uv-card h1 { margin: 6px 0 4px; font-size: 30px; color: #0F1640; }
  #uv-card .sub { color: #3B4262; font-size: 15px; margin-bottom: 18px; line-height: 1.45; }
  #uv-card table { width: 100%; border-collapse: collapse; font-size: 14px; }
  #uv-card td { padding: 7px 0; border-top: 1px solid #EEF0F6; vertical-align: top; color: #0F1640; }
  #uv-card td:first-child { width: 190px; color: #5B6380; font-weight: 600; }
  #uv-card .stamp { display: inline-block; margin-top: 16px; font-size: 22px; font-weight: 800; letter-spacing: 2px;
                    padding: 6px 18px; border: 3px solid #16A34A; color: #16A34A; border-radius: 8px; }
  #uv-card .stamp.bad { border-color: #DC2626; color: #DC2626; }
  \`;
  const mount = () => {
    if (document.getElementById('uv-root')) return;
    const st = document.createElement('style'); st.textContent = css; document.documentElement.appendChild(st);
    const r = document.createElement('div'); r.id = 'uv-root';
    r.innerHTML = '<div id="uv-badge"></div><div id="uv-cap"><span class="n"></span><span class="t"></span></div>'
      + '<div id="uv-card"><div class="c"></div></div>'
      + '<svg id="uv-cursor" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.6L21 11z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(r);
    const cur = document.getElementById('uv-cursor');
    const last = JSON.parse(sessionStorage.getItem('uv-mouse') || 'null');
    if (last) { cur.style.left = last[0] - 3 + 'px'; cur.style.top = last[1] - 2 + 'px'; }
    addEventListener('mousemove', e => { cur.style.left = e.clientX - 3 + 'px'; cur.style.top = e.clientY - 2 + 'px';
      sessionStorage.setItem('uv-mouse', JSON.stringify([e.clientX, e.clientY])); }, true);
    addEventListener('mousedown', e => { const g = document.createElement('div'); g.className = 'uv-ring';
      g.style.left = e.clientX + 'px'; g.style.top = e.clientY + 'px'; r.appendChild(g); setTimeout(() => g.remove(), 700); }, true);
    window.__uvRender();
    setInterval(window.__uvClock, 500);
  };
  window.__uvClock = () => {
    const b = document.getElementById('uv-badge'); if (!b) return;
    const s = JSON.parse(sessionStorage.getItem('uv-state') || '{}');
    const now = new Intl.DateTimeFormat('en-GB', { timeZone: '${TZ}', day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date());
    b.innerHTML = (s.badge || '') + ' &nbsp;·&nbsp; <b>' + now + '</b> Vietnam time';
  };
  window.__uvRender = () => {
    const s = JSON.parse(sessionStorage.getItem('uv-state') || '{}');
    const cap = document.getElementById('uv-cap'); if (!cap) return;
    const pr = s.proof;                 // a proof replaces the step caption while it is shown
    cap.className = (pr ? (s.proofOk ? 'ok' : 'bad') : '') + (s.capTop ? ' top' : '');
    const n = pr ? (s.proofOk ? '✓ PROOF' : '✗ NOT MATCHED') : s.n, t = pr || s.cap;
    cap.style.display = t ? 'flex' : 'none';
    cap.querySelector('.n').textContent = n || ''; cap.querySelector('.n').style.display = n ? '' : 'none';
    cap.querySelector('.t').textContent = t || '';
    const card = document.getElementById('uv-card');
    card.style.display = s.card ? 'flex' : 'none'; card.querySelector('.c').innerHTML = s.card || '';
    window.__uvClock();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();`;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// File and folder names that open on Windows too (no : / \\ ? * " < > |).
const safeName = (s) => String(s).replace(/\s*:\s*/g, ' - ').replace(/[\\/?*"<>|]/g, '-');

class Kit {
  constructor(meta, outDir) {
    this.meta = meta;            // { id, title, criterion, role, login, password, data, expected }
    this.outDir = outDir;
    this.framesDir = path.join(outDir, '.frames');
    this.proofDir = path.join(outDir, 'proof-screenshots');
    this.cues = [];              // { t, n, en, vi }
    this.proofs = [];            // { label, ok, detail }
    this.records = {};           // ids collected for the end card
    this.frames = [];
    this.proofN = 0;
  }

  // ------------------------------------------------------------ lifecycle
  async start() {
    fs.rmSync(this.framesDir, { recursive: true, force: true });
    fs.mkdirSync(this.framesDir, { recursive: true });
    fs.mkdirSync(this.proofDir, { recursive: true });
    this.browser = await chromium.launch();
    this.context = await this.browser.newContext({
      viewport: VIEW, deviceScaleFactor: SCALE, locale: 'en-US', timezoneId: TZ,
      permissions: ['geolocation', 'notifications'], geolocation: { latitude: 21.0136, longitude: 105.8487 },
    });
    await this.context.addInitScript(OVERLAY);
    this.page = await this.context.newPage();
    this.page.setDefaultTimeout(20000);
    // Surface what a screen refuses quietly: failed calls and script errors.
    this.page.on('response', async (r) => {
      if (!r.url().includes('/web/dataset/call_kw')) return;
      try { const j = await r.json(); if (j.error) console.log('  RPC ERROR', r.url().split('/').slice(-2).join('/'), '—', (j.error.data && j.error.data.message || '').slice(0, 200)); } catch (e) { /* not json */ }
    });
    this.page.on('pageerror', (e) => console.log('  PAGE ERROR', e.message.slice(0, 200)));
    this.cdp = await this.context.newCDPSession(this.page);
    this.cdp.on('Page.screencastFrame', async (f) => {
      const file = path.join(this.framesDir, `f${String(this.frames.length).padStart(6, '0')}.jpg`);
      fs.writeFileSync(file, Buffer.from(f.data, 'base64'));
      this.frames.push({ file, t: f.metadata.timestamp });
      try { await this.cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) { /* closing */ }
    });
    await this.page.goto(BASE + '/web/login');
    await this.cdp.send('Page.startScreencast', {
      format: 'jpeg', quality: 92, maxWidth: VIEW.width * SCALE, maxHeight: VIEW.height * SCALE, everyNthFrame: 1,
    });
    this.t0 = Date.now() / 1000;
    await this._state({ badge: `${esc(this.meta.id)} · ${esc(this.meta.short || this.meta.title)} · ${esc(this.meta.role)}` });
  }

  async finish() {
    const ok = this.proofs.length > 0 && this.proofs.every((p) => p.ok);
    this.passed = ok;
    await this.endCard(ok);
    await sleep(6000);
    await this.cdp.send('Page.stopScreencast');
    await sleep(300);
    const lastT = Date.now() / 1000;
    await this.browser.close();
    return this._encode(lastT, ok);
  }

  // ------------------------------------------------------------ overlay state
  async _state(patch) {
    this.state = { ...(this.state || {}), ...patch };
    const s = JSON.stringify(this.state);
    await this.page.evaluate((v) => { sessionStorage.setItem('uv-state', v); window.__uvRender && window.__uvRender(); }, s)
      .catch(() => {});
  }

  async titleCard() {
    const m = this.meta;
    const now = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, dateStyle: 'long', timeStyle: 'medium' }).format(new Date());
    const rows = [
      ['Acceptance criterion', m.criterion],
      ['Signed in as', `${m.role} — user “${m.login}”`],
      ['System', 'carejiox.com (live system), English, Vietnam time'],
      ['Test data', m.data],
      ['Recorded', `${now} (Vietnam time)`],
    ];
    const html = `<div class="k">Acceptance test evidence · ${esc(m.id)}</div><h1>${esc(m.title)}</h1>`
      + `<div class="sub">This recording repeats the test on the live screens, step by step. Green boxes mark the proof for each expected result.</div>`
      + `<table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</table>`;
    await this._state({ card: html, cap: '', n: '' });
    this._cue('', `${m.id} — ${m.title}`, `${m.id} — ${m.title_vi || m.title}`);
    await sleep(7000);
    await this._state({ card: '' });
  }

  async endCard(ok) {
    const m = this.meta;
    const failed = this.proofs.filter((p) => !p.ok);
    const rows = [
      ['Expected result', m.expected],
      ['What the screens showed', this.proofs.map((p) => `${p.ok ? '✓' : '✗'} ${p.label}`).join('<br>')],
      ['Records created', Object.entries(this.records).map(([k, v]) => `${k}: ${v}`).join(' · ') || '—'],
    ];
    const html = `<div class="k">Result · ${esc(m.id)}</div><h1>${esc(m.title)}</h1>`
      + `<table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${k === 'What the screens showed' ? v : esc(v)}</td></tr>`).join('')}</table>`
      + `<div class="stamp ${ok ? '' : 'bad'}">${ok ? 'PASS' : 'FAIL'}</div>`
      + (failed.length ? `<div class="sub" style="margin-top:10px;color:#DC2626">Not matched: ${failed.map((f) => esc(f.label + ' — ' + f.detail)).join('; ')}</div>` : '');
    await this._state({ card: html, cap: '', n: '' });
    this._cue('', ok ? 'Result: PASS' : 'Result: FAIL', ok ? 'Kết quả: ĐẠT' : 'Kết quả: KHÔNG ĐẠT');
  }

  // ------------------------------------------------------------ actions
  _cue(n, en, vi) { this.cues.push({ t: Date.now() / 1000, n, en, vi }); }

  async step(n, en, vi) {
    await this._state({ n: `STEP ${n}`, cap: en });
    this._cue(n, en, vi);
    this.lastStep = { n, en, vi };
    await this.brandCheck(`step ${n}`).catch(() => {});
    await sleep(1600);
  }

  async note(en, vi) {                 // caption without a step number
    await this._state({ n: '', cap: en });
    this._cue('', en, vi);
    await sleep(1400);
  }

  // Keep the caption bar off whatever is being clicked or proved.
  async _capClear(bottom) {
    const top = bottom > 640;
    if (top !== !!(this.state && this.state.capTop)) await this._state({ capTop: top });
  }

  async moveTo(locator) {
    await locator.scrollIntoViewIfNeeded();
    const b = await locator.boundingBox();
    if (!b) throw new Error('not visible: ' + locator);
    await this._capClear(b.y + b.height);
    const x = b.x + b.width / 2, y = b.y + Math.min(b.height / 2, 18);
    await this.page.mouse.move(x, y, { steps: 18 });
    await sleep(250);
    return { x, y };
  }

  async click(locator, after = 900) {
    const { x, y } = await this.moveTo(locator);
    await this.page.mouse.click(x, y);
    await sleep(after);
  }

  async type(locator, text, after = 500) {
    await this.click(locator, 200);
    await this.page.keyboard.press('ControlOrMeta+A');
    await this.page.keyboard.type(String(text), { delay: 55 });
    await sleep(after);
  }

  // A selection field: a <select>, or the searchable drop-down menu this version
  // renders (click the field, then the option).
  async select(field, label, after = 900) {
    const native = field.locator('select');
    if (await native.count()) {
      await this.moveTo(native);
      await this.page.mouse.down(); await this.page.mouse.up();
      await native.selectOption({ label });
    } else {
      await this.click(field.locator('input').first(), 600);
      await this.click(this.page.locator('.o_select_menu_item').filter({ hasText: new RegExp(`^\\s*${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`) }).first(), 300);
    }
    await sleep(after);
  }

  // A date-time field: open it, type the value, confirm.
  async datetime(field, typed, after = 700) {
    await this.click(field.locator('button, input').first(), 500);
    await this.page.keyboard.press('ControlOrMeta+A');
    await this.page.keyboard.type(typed, { delay: 55 });
    await this.page.keyboard.press('Enter');
    await sleep(300);
    await this.page.keyboard.press('Escape');
    await sleep(after);
  }

  async hold(ms) { await sleep(ms); }

  // Switch area on the left rail (Home, CRM, Operations, Finance...). The rail
  // slides open while hovered, so park the pointer over the page afterwards.
  async area(name) {
    await this.click(this.page.getByRole('button', { name: new RegExp(`^${name}\\b`) }).first(), 1200);
    await this.page.mouse.move(760, 400, { steps: 12 });
    await sleep(900);
  }

  // Draw a green box around each element, check the expectation, save a still, hold.
  // The label shows in the caption bar (green, red when not matched) so it never
  // covers the screen being proved.
  // expect: string (must appear in the boxed text), RegExp, or
  //         async function(text, locators) => bool (e.g. to read input values).
  async proof(locators, label, expect, hold = 3200) {
    const list = Array.isArray(locators) ? locators : [locators];
    let text = '', ok = true, detail = '';
    try {
      await list[0].scrollIntoViewIfNeeded();
      await sleep(300);
      for (const l of list) text += ' ' + (await l.innerText()).replace(/\s+/g, ' ');
      if (typeof expect === 'string') ok = text.toLowerCase().includes(expect.toLowerCase());
      else if (expect instanceof RegExp) ok = expect.test(text);
      else if (typeof expect === 'function') ok = !!(await expect(text, list));
      if (!ok) detail = `saw “${text.trim().slice(0, 80)}”`;
    } catch (e) { ok = false; detail = e.message.split('\n')[0]; }
    const boxes = [];
    for (const l of list) { const b = await l.boundingBox().catch(() => null); if (b) boxes.push(b); }
    await this._capClear(Math.max(0, ...boxes.map((b) => b.y + b.height)));
    await this.page.evaluate(({ boxes, ok }) => {
      const r = document.getElementById('uv-root'); if (!r) return;
      boxes.forEach((b) => {
        const d = document.createElement('div'); d.className = 'uv-box uv-tmp' + (ok ? '' : ' bad');
        Object.assign(d.style, { left: b.x - 5 + 'px', top: b.y - 4 + 'px', width: b.width + 10 + 'px', height: b.height + 8 + 'px' });
        r.appendChild(d);
      });
    }, { boxes, ok });
    await this._state({ proof: label, proofOk: ok });
    this.proofs.push({ label, ok, detail });
    this.proofN += 1;
    await sleep(500);
    await this.page.screenshot({ path: path.join(this.proofDir, `${String(this.proofN).padStart(2, '0')} ${label.replace(/[\\/:*?"<>|]/g, '-')}.png`) });
    this._cue('', (ok ? '✓ ' : '✗ ') + label, (ok ? '✓ ' : '✗ ') + (this._proofVi && this._proofVi[label] || label));
    await sleep(hold);
    await this.page.evaluate(() => document.querySelectorAll('.uv-tmp').forEach((e) => e.remove()));
    await this._state({ proof: '' });
    if (this.lastStep) this._cue(this.lastStep.n, this.lastStep.en, this.lastStep.vi);
    if (!ok) console.log(`  PROOF FAILED: ${label} — ${detail}`);
    return ok;
  }

  // Values of form fields by technical name, inside an optional scope.
  async fieldValues(names, scope) {
    const root = scope || this.page;
    const out = {};
    for (const n of names) {
      const w = root.locator(`.o_field_widget[name="${n}"]`).filter({ visible: true }).first();
      const input = w.locator('input, textarea, select').first();
      out[n] = (await input.count()) ? (await input.inputValue()).trim() : (await w.innerText()).trim();
    }
    return out;
  }

  // ------------------------------------------------------------ app helpers
  async login() {
    await this.step(1, `Sign in as ${this.meta.role} (${this.meta.login})`, `Đăng nhập với vai trò ${this.meta.role_vi || this.meta.role} (${this.meta.login})`);
    await this._signIn(this.meta.login, this.meta.password, false);
  }

  // Sign out and sign in as someone else in the same recording; `pwa` lands in the nurse app.
  async switchUser(n, user, pwa) {
    const p = this.page;
    await this.step(n, `Sign in as ${user.role} (${user.login})${pwa ? ' in the nurse app' : ''}`,
      `Đăng nhập với vai trò ${user.role_vi || user.role} (${user.login})${pwa ? ' trên ứng dụng điều dưỡng' : ''}`);
    await this._state({ badge: `${esc(this.meta.id)} · ${esc(this.meta.short || this.meta.title)} · ${esc(user.role)}` });
    await p.goto(BASE + '/web/session/logout');
    await p.goto(BASE + '/web/login' + (pwa ? '?redirect=%2Fhealth_pwa%3F%23%2Ftoday' : ''));
    await this._state({});
    await this._signIn(user.login, user.password, pwa);
  }

  async _signIn(login, password, pwa) {
    const p = this.page;
    await this.type(p.locator('#login'), login);
    await this.type(p.locator('#password'), password);
    await Promise.all([p.waitForURL(pwa ? /health_pwa/ : /\/bizapp/, { timeout: 45000 }), this.click(p.locator('button.btn-primary:has-text("Log in")'), 0)]);
    await p.waitForLoadState('networkidle').catch(() => {});
    await this._state({});
    if (pwa) {
      // The nurse app reminds the user to allow phone notifications, which a recording
      // browser cannot do. Say so and dismiss it on screen, as a nurse would.
      const banner = p.locator('button').filter({ hasText: /Đóng \/ Dismiss/ }).filter({ visible: true }).first();
      await banner.waitFor({ timeout: 10000 }).catch(() => {});
      if (await banner.count()) {
        await this.note('The nurse app asks to turn on phone notifications: Dismiss', 'Ứng dụng nhắc bật thông báo trên điện thoại: Đóng');
        // it also closes by itself after a few seconds
        if (await banner.isVisible()) await banner.click({ timeout: 3000 }).catch(() => {});
        await banner.waitFor({ state: 'hidden', timeout: 10000 }).catch(() => {});
      }
      // an install prompt may sit hidden behind the page: dismiss it quietly if present
      await p.locator('button').filter({ hasText: /^\s*Để sau\s*Later\s*$/ }).first().click({ timeout: 1500 }).catch(() => {});
    } else {
      await this.dismissReleaseToast();
    }
  }

  async dismissReleaseToast() {
    await sleep(1200);
    await this.page.evaluate(() => document.querySelectorAll('.o_notification').forEach((n) => {
      if (/was updated to release/.test(n.innerText)) n.querySelector('.o_notification_close, button')?.click();
    }));
  }

  // White-label guard: the brand word must never be on screen (overlay excluded).
  async brandCheck(where) {
    const hit = await this.page.evaluate(() => {
      const root = document.getElementById('uv-root');
      // visible text only: scripts and hidden templates are not on screen
      const txt = [...document.body.querySelectorAll('*')].filter((e) => !root || !root.contains(e))
        .filter((e) => e.children.length === 0 && !/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(e.tagName)
          && e.getClientRects().length > 0).map((e) => e.innerText || '').join(' ');
      return /odoo/i.test(txt) ? txt.match(/.{0,40}odoo.{0,40}/i)[0] : '';
    });
    if (hit) { console.log(`  BRAND WORD ON SCREEN at ${where}: ${hit}`); this.brandHits = (this.brandHits || []).concat(where); }
  }

  // ------------------------------------------------------------ encode
  _encode(lastT, ok) {
    const f = this.frames;
    if (!f.length) throw new Error('no frames captured');
    const list = f.map((fr, i) => {
      const next = i + 1 < f.length ? f[i + 1].t : lastT;
      return `file '${fr.file}'\nduration ${Math.max(0.001, next - fr.t).toFixed(4)}`;
    }).join('\n') + `\nfile '${f[f.length - 1].file}'\n`;
    const listFile = path.join(this.framesDir, 'list.txt');
    fs.writeFileSync(listFile, list);
    const base = safeName(`${this.meta.id} ${this.meta.title} - ${ok ? 'PASS' : 'FAIL'}`);
    const raw = path.join(this.framesDir, 'video.mp4');
    execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', listFile,
      '-vf', `fps=${FPS},scale=1920:1080:flags=lanczos,format=yuv420p`, '-c:v', 'libx264', '-preset', 'slow',
      '-crf', String(this.crf || 24), '-tune', 'stillimage', '-movflags', '+faststart', raw]);
    // Vietnamese captions as a switchable subtitle track (off by default).
    const t0 = f[0].t;
    const srt = this._srt(t0, lastT, 'vi');
    const srtFile = path.join(this.outDir, `${this.meta.id} captions - Vietnamese.srt`);
    fs.writeFileSync(srtFile, srt);
    const out = path.join(this.outDir, base + '.mp4');
    for (const old of fs.readdirSync(this.outDir).filter((n) => n.endsWith('.mp4'))) fs.rmSync(path.join(this.outDir, old));
    execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-i', raw, '-i', srtFile, '-map', '0:v', '-map', '1:0',
      '-c:v', 'copy', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=vie', '-metadata:s:s:0', 'title=Tiếng Việt',
      '-disposition:s:0', '0', '-metadata', `title=${base}`, '-movflags', '+faststart', out]);
    fs.writeFileSync(path.join(this.outDir, 'run.json'), JSON.stringify({
      id: this.meta.id, passed: ok, proofs: this.proofs, records: this.records, brandHits: this.brandHits || [],
      seconds: +(lastT - t0).toFixed(1), file: path.basename(out),
      chapters: this.cues.filter((c, i, a) => c.n && a.findIndex((x) => x.n === c.n) === i).map((c) => ({ t: +(c.t - t0).toFixed(2), n: c.n, en: c.en })),
    }, null, 1));
    fs.rmSync(this.framesDir, { recursive: true, force: true });
    return out;
  }

  _srt(t0, lastT, lang) {
    const ts = (s) => { s = Math.max(0, s); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = (s % 60);
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${x.toFixed(3).padStart(6, '0').replace('.', ',')}`; };
    return this.cues.map((c, i) => {
      const end = i + 1 < this.cues.length ? this.cues[i + 1].t : lastT;
      const txt = (c.n ? `Bước ${c.n}: ` : '') + c[lang];
      return `${i + 1}\n${ts(c.t - t0)} --> ${ts(end - t0)}\n${txt}\n`;
    }).join('\n');
  }
}

module.exports = { Kit, BASE, sleep, safeName };
