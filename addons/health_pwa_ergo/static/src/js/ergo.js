// Health PWA Ergonomic Modes — glove + sunlight (window global, plain JS).
//
// Device-local by design (nurse phones are personal). Zero Vue/app.js hooks:
// toggles two independent classes on <html> and renders its own bottom sheet.
//   window.healthErgo.get() / .set(modes) / .toggleSheet()
// State: { glove: false, sunlight: 'off'|'on'|'auto' } in localStorage.vu_ergo_modes.

(function () {
  'use strict';

  const _t = (text) => window.odoo?._t?.(text)
    || window.PWAUtils?.i18n?.t?.(text)
    || text;

  var STORAGE_KEY = 'vu_ergo_modes';
  var DEFAULTS = { glove: false, sunlight: 'off' };
  var root = document.documentElement;

  // --- persistence ---------------------------------------------------------
  function read() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) { return { glove: false, sunlight: 'off' }; }
      var v = JSON.parse(raw);
      return {
        glove: !!v.glove,
        sunlight: (v.sunlight === 'on' || v.sunlight === 'auto') ? v.sunlight : 'off',
      };
    } catch (e) {
      return { glove: false, sunlight: 'off' };
    }
  }

  function write(modes) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(modes));
    } catch (e) { /* private mode can throw — ignore */ }
  }

  var state = read();

  // --- class application ---------------------------------------------------
  // The stored preference drives glove directly; sunlight 'on' => class on,
  // 'off' => off, 'auto' => decided by sensor/time (applySunlightAuto). Auto
  // decisions only add/remove the class, never rewrite the stored preference.
  function applyGlove() {
    root.classList.toggle('vu-glove', !!state.glove);
  }

  function setSunlightClass(on) {
    root.classList.toggle('vu-sunlight', !!on);
  }

  function applySunlight() {
    if (state.sunlight === 'on') {
      stopAuto();
      setSunlightClass(true);
    } else if (state.sunlight === 'off') {
      stopAuto();
      setSunlightClass(false);
    } else { // auto
      startAuto();
    }
  }

  function applyAll() {
    applyGlove();
    applySunlight();
    syncPillGlove();
  }

  // --- public API ----------------------------------------------------------
  function get() {
    return { glove: state.glove, sunlight: state.sunlight };
  }

  function set(modes) {
    modes = modes || {};
    if (typeof modes.glove === 'boolean') { state.glove = modes.glove; }
    if (modes.sunlight === 'on' || modes.sunlight === 'off' || modes.sunlight === 'auto') {
      state.sunlight = modes.sunlight;
    }
    write(state);
    applyAll();
    renderSheetControls();
    return get();
  }

  // --- sunlight auto: sensor with time-window fallback ---------------------
  var sensor = null;
  var timeTimer = null;
  var lastAutoOn = null;
  var debounceUntil = 0;

  function stopAuto() {
    try { if (sensor) { sensor.stop(); } } catch (e) { /* ignore */ }
    sensor = null;
    if (timeTimer) { clearInterval(timeTimer); timeTimer = null; }
    document.removeEventListener('visibilitychange', evalTimeWindow);
    lastAutoOn = null;
  }

  function startAuto() {
    stopAuto();
    // AmbientLightSensor is behind a Chrome/Android flag — availability is the
    // exception, never a requirement. Guard the constructor AND onerror.
    var Sensor = window.AmbientLightSensor;
    if (typeof Sensor === 'function') {
      try {
        sensor = new Sensor({ frequency: 1 });
        sensor.addEventListener('reading', onSensorReading);
        sensor.addEventListener('error', function () { fallbackToTime(); });
        sensor.start();
        return;
      } catch (e) {
        sensor = null;
      }
    }
    fallbackToTime();
  }

  function onSensorReading() {
    try {
      var now = Date.now();
      if (now < debounceUntil) { return; }
      var lux = sensor && typeof sensor.illuminance === 'number' ? sensor.illuminance : 0;
      // Hysteresis: on >= 10000 lux, off < 5000; hold between.
      var next = lastAutoOn;
      if (lux >= 10000) { next = true; }
      else if (lux < 5000) { next = false; }
      if (next !== lastAutoOn) {
        lastAutoOn = next;
        setSunlightClass(next);
        debounceUntil = now + 30000; // 30s debounce
      }
    } catch (e) { fallbackToTime(); }
  }

  function fallbackToTime() {
    try { if (sensor) { sensor.stop(); } } catch (e) { /* ignore */ }
    sensor = null;
    evalTimeWindow();
    if (!timeTimer) {
      timeTimer = setInterval(evalTimeWindow, 15 * 60 * 1000); // every 15 min
    }
    document.addEventListener('visibilitychange', evalTimeWindow);
  }

  function evalTimeWindow() {
    if (state.sunlight !== 'auto') { return; }
    var h = new Date().getHours();
    setSunlightClass(h >= 9 && h < 16); // daylight window, device-local
  }

  // --- toggle UI: fixed pill + self-rendered bottom sheet ------------------
  var pill = null;
  var sheet = null;

  var ICON_SUN =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="12" cy="12" r="4"/>' +
    '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2' +
    'M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';

  function buildPill() {
    if (pill) { return; }
    pill = document.createElement('button');
    pill.type = 'button';
    pill.id = 'vu-ergo-pill';
    pill.setAttribute('aria-label', 'Chế độ hiển thị (Display modes)');
    pill.innerHTML = ICON_SUN;
    pill.addEventListener('click', toggleSheet);
    document.body.appendChild(pill);
    syncPillGlove();
  }

  function syncPillGlove() {
    if (pill) { pill.classList.toggle('vu-ergo-pill--glove', !!state.glove); }
  }

  function segButton(label, active, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'vu-ergo-seg' + (active ? ' vu-ergo-seg--on' : '');
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }

  function renderSheetControls() {
    if (!sheet) { return; }
    var body = sheet.querySelector('.vu-ergo-sheet-body');
    if (!body) { return; }
    body.innerHTML = '';

    // Glove: on/off
    var gRow = document.createElement('div');
    gRow.className = 'vu-ergo-row';
    var gLabel = document.createElement('div');
    gLabel.className = 'vu-ergo-label';
    gLabel.textContent = _t('Glove mode');
    var gSeg = document.createElement('div');
    gSeg.className = 'vu-ergo-segs';
    gSeg.appendChild(segButton('Tắt (Off)', !state.glove, function () { set({ glove: false }); }));
    gSeg.appendChild(segButton('Bật (On)', state.glove, function () { set({ glove: true }); }));
    gRow.appendChild(gLabel);
    gRow.appendChild(gSeg);

    // Sunlight: off/on/auto
    var sRow = document.createElement('div');
    sRow.className = 'vu-ergo-row';
    var sLabel = document.createElement('div');
    sLabel.className = 'vu-ergo-label';
    sLabel.textContent = _t('Sunlight mode');
    var sSeg = document.createElement('div');
    sSeg.className = 'vu-ergo-segs';
    sSeg.appendChild(segButton('Tắt (Off)', state.sunlight === 'off', function () { set({ sunlight: 'off' }); }));
    sSeg.appendChild(segButton('Bật (On)', state.sunlight === 'on', function () { set({ sunlight: 'on' }); }));
    sSeg.appendChild(segButton('Tự động (Auto)', state.sunlight === 'auto', function () { set({ sunlight: 'auto' }); }));
    sRow.appendChild(sLabel);
    sRow.appendChild(sSeg);

    body.appendChild(gRow);
    body.appendChild(sRow);
  }

  function buildSheet() {
    if (sheet) { return; }
    sheet = document.createElement('div');
    sheet.id = 'vu-ergo-sheet';
    sheet.className = 'vu-ergo-sheet-overlay';
    sheet.setAttribute('hidden', 'hidden');
    sheet.innerHTML =
      '<div class="vu-ergo-sheet" role="dialog" aria-label="Chế độ hiển thị">' +
      '<div class="vu-ergo-sheet-head">Chế độ hiển thị (Display modes)' +
      '<button type="button" class="vu-ergo-close" aria-label="Đóng (Close)">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M18 6 6 18M6 6l12 12"/></svg></button></div>' +
      '<div class="vu-ergo-sheet-body"></div></div>';
    sheet.addEventListener('click', function (e) {
      if (e.target === sheet || (e.target.closest && e.target.closest('.vu-ergo-close'))) {
        closeSheet();
      }
    });
    document.body.appendChild(sheet);
    renderSheetControls();
  }

  function toggleSheet() {
    buildSheet();
    if (sheet.hasAttribute('hidden')) {
      renderSheetControls();
      sheet.removeAttribute('hidden');
    } else {
      closeSheet();
    }
  }

  function closeSheet() {
    if (sheet) { sheet.setAttribute('hidden', 'hidden'); }
  }

  // --- boot ----------------------------------------------------------------
  function boot() {
    applyAll();
    buildPill();
    buildSheet();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.healthErgo = {
    get: get,
    set: set,
    toggleSheet: toggleSheet,
  };
})();
