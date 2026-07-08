// Health PWA Day-Strip + "On My Way" — window global, plain JS (no Vue).
//
// Three responsibilities, injected into the shell without editing app.js
// beyond the whitelisted data-fso-id/status attributes (handover §2.5):
//   1. "Đang đến (On my way)" verb on today's confirmed/assigned cards —
//      posts a travel_start EVV event through the SHARED offline queue
//      (window.healthEvvQueue); flips to "Hủy (Cancel)" -> travel_cancel.
//      One active travel per device (localStorage single source of truth);
//      starting a second auto-cancels the first.
//   2. Swipe-to-reveal action row (Gọi (Call) / Đang đến (On my way)).
//      Reveal-only: a swipe NEVER fires an action. >=40px horizontal with
//      vertical tolerance; stopPropagation so it never fights the existing
//      app.js date-swipe (app.js:1473).
//   3. Day-strip header: a self-rendered 06:00-20:00 timeline above the day
//      list, one block per booking (status-colored, flat mono), a now-marker,
//      tap a block -> smooth-scroll to its card.
//
// Data seam (report point b): window.fetch is wrapped for the
// /health_pwa/api/assignments/today response. Chosen over a MutationObserver
// or the whitelisted window hook because reusing the real response yields the
// exact structured payload the strip needs (scheduled_datetime, duration,
// status, phone, staff_id), keyed to the SAME load the day list renders — no
// DOM time re-parsing, no strip/list divergence, and no second app.js edit.
//
// window.healthErgo compat: honors --touch-target (glove) and provides
// explicit html.vu-glove / html.vu-sunlight rules for every element in
// daystrip.css.

(function () {
  'use strict';

  // ---- constants --------------------------------------------------------
  // Mirrors app.js STATUS_PALETTE so strip blocks match the card accents.
  var PALETTE = {
    late: '#FB8C00', upcoming: '#1565C0', inprogress: '#43A047',
    done: '#94A3B8', cancelled: '#E53935',
  };
  var DAY_START_MIN = 6 * 60;    // 06:00
  var DAY_END_MIN = 20 * 60;     // 20:00
  var SPAN_MIN = DAY_END_MIN - DAY_START_MIN;   // 840
  var TICKS = [6, 9, 12, 15, 18, 20];
  var ACTIVE_KEY = 'vu_daystrip_active';   // localStorage: {"fso_id": N}
  var SWIPE_MIN = 40;            // px horizontal to latch the reveal open
  var GEO_TIMEOUT = 5000;

  // ---- inline SVG (currentColor, no emoji) ------------------------------
  var ICON_CALL =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 ' +
    '19.8 19.8 0 0 1-3.1-8.7A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.7a2 2 0 0 1-.5 2.1L8 9.6a16 16 0 0 0 6 6l1.1-1.1a2 2 0 0 1 2.1-.5c.9.3 1.8.5 2.7.6a2 2 0 0 1 1.7 2z"/></svg>';
  var ICON_NAV =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>';
  var ICON_X =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M18 6 6 18M6 6l12 12"/></svg>';

  // ---- state ------------------------------------------------------------
  var lastToday = { date: null, bookings: [], staffId: 0 };
  var renderPending = false;
  var observer = null;

  // ---- date/format helpers ---------------------------------------------
  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function toDate(s) {
    if (!s) { return null; }
    var iso = String(s).replace(' ', 'T');
    if (!/[zZ]$/.test(iso) && !/[+]\d\d:?\d\d$/.test(iso)) { iso += 'Z'; }
    var d = new Date(iso);
    return isNaN(d.getTime()) ? null : d;
  }
  function localMinutes(s) {
    var d = toDate(s);
    return d ? d.getHours() * 60 + d.getMinutes() : null;
  }
  function labelOf(s) {
    var d = toDate(s);
    return d ? pad(d.getHours()) + ':' + pad(d.getMinutes()) : '';
  }
  function nowMinutes() {
    var d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
  function todayLocalISO() {
    var d = new Date();
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }
  function dateParamFromUrl(url) {
    var m = /[?&]date=(\d{4}-\d{2}-\d{2})/.exec(url || '');
    return m ? m[1] : todayLocalISO();
  }
  function escAttr(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // Status -> color, mirroring app.js statusKey() incl. the running-late rule.
  function statusColor(status, scheduledDatetime) {
    var s = String(status || '').toLowerCase();
    if (s === 'in_progress') { return PALETTE.inprogress; }
    if (s === 'completed' || s === 'completed_pending_invoice' || s === 'closed') {
      return PALETTE.done;
    }
    if (s === 'cancelled') { return PALETTE.cancelled; }
    if (s === 'draft' || s === 'confirmed' || s === 'assigned') {
      var d = toDate(scheduledDatetime);
      if (d && d.getTime() < Date.now()) { return PALETTE.late; }
    }
    return PALETTE.upcoming;
  }
  function eligible(status) {
    var s = String(status || '').toLowerCase();
    return s === 'confirmed' || s === 'assigned';
  }

  // ---- active-travel record (localStorage = single source of truth) -----
  function getActive() {
    try {
      var raw = localStorage.getItem(ACTIVE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }
  function setActive(v) {
    try {
      if (v) { localStorage.setItem(ACTIVE_KEY, JSON.stringify(v)); }
      else { localStorage.removeItem(ACTIVE_KEY); }
    } catch (e) { /* private mode */ }
  }

  // ---- fetch-wrap data seam --------------------------------------------
  (function wrapFetch() {
    if (!window.fetch || window.__daystripFetchWrapped) { return; }
    window.__daystripFetchWrapped = true;
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var url = (typeof input === 'string') ? input : (input && input.url) || '';
      var promise = orig(input, init);
      if (url.indexOf('/health_pwa/api/assignments/today') !== -1) {
        promise.then(function (resp) {
          resp.clone().json().then(function (json) {
            if (json && json.success && json.data) {
              lastToday = {
                date: dateParamFromUrl(url),
                bookings: json.data.bookings || [],
                staffId: json.data.staff_id || 0,
              };
              scheduleRender();
            }
          }).catch(function () { /* non-JSON — ignore */ });
        }).catch(function () { /* network error — ignore */ });
      }
      return promise;
    };
  })();

  // ---- geolocation (graceful: null on deny/timeout) ---------------------
  function getPos() {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) { resolve(null); return; }
      var done = false;
      var timer = setTimeout(function () {
        if (!done) { done = true; resolve(null); }
      }, GEO_TIMEOUT);
      navigator.geolocation.getCurrentPosition(
        function (p) {
          if (done) { return; }
          done = true; clearTimeout(timer);
          resolve({ lat: p.coords.latitude, lng: p.coords.longitude, acc: p.coords.accuracy });
        },
        function () {
          if (done) { return; }
          done = true; clearTimeout(timer); resolve(null);
        },
        { enableHighAccuracy: true, timeout: GEO_TIMEOUT, maximumAge: 0 });
    });
  }

  // ---- travel posting via the shared EVV queue --------------------------
  // Reuses window.healthEvvQueue (evv-queue.js): enqueue() stores locally +
  // computes the client hash, flush() pushes when online (background sync /
  // 'online' listener carry it otherwise -> origin 'offline_sync').
  function postTravel(fsoId, type, pos) {
    var q = window.healthEvvQueue;
    if (!q || !q.enqueue) { return Promise.resolve(null); }
    return q.enqueue({
      fso_id: fsoId,
      event_type: type,
      event_datetime: new Date(),
      lat: pos ? pos.lat : 0,
      lng: pos ? pos.lng : 0,
      accuracy_m: pos ? pos.acc : 0,
      staff_id: lastToday.staffId || 0,
      payload: {},
    }).then(function () {
      if (q.flush) { return q.flush(); }
    }).catch(function () { /* queued; sync later */ });
  }

  function startTravel(fsoId) {
    var active = getActive();
    if (active && active.fso_id !== fsoId) {
      postTravel(active.fso_id, 'travel_cancel', null);   // one active per device
    }
    setActive({ fso_id: fsoId });
    render();
    getPos().then(function (pos) { postTravel(fsoId, 'travel_start', pos); });
  }
  function cancelTravel(fsoId) {
    setActive(null);
    render();
    postTravel(fsoId, 'travel_cancel', null);
  }
  function onVerb(fsoId) {
    var active = getActive();
    if (active && active.fso_id === fsoId) { cancelTravel(fsoId); }
    else { startTravel(fsoId); }
  }

  // ---- card enhancement: reveal row + verb ------------------------------
  function actionsWidth(card) {
    var row = card.querySelector('.daystrip-actions');
    return (row && row.offsetWidth) || 150;
  }

  function buildActions(card, fsoId, phone, status) {
    var row = document.createElement('div');
    row.className = 'daystrip-actions';

    var call = document.createElement('button');
    call.type = 'button';
    call.className = 'daystrip-act daystrip-act--call';
    call.innerHTML = ICON_CALL + '<span>Gọi</span>';
    call.addEventListener('click', function (e) {
      e.stopPropagation();
      if (phone) { window.location.href = 'tel:' + phone; }
    });
    row.appendChild(call);

    if (eligible(status)) {
      var verb = document.createElement('button');
      verb.type = 'button';
      verb.className = 'daystrip-act daystrip-act--go';
      verb.addEventListener('click', function (e) {
        e.stopPropagation();
        onVerb(fsoId);
      });
      row.appendChild(verb);
    }
    return row;
  }

  function syncVerb(card, fsoId) {
    var active = getActive();
    var isActive = !!(active && active.fso_id === fsoId);
    card.classList.toggle('daystrip-card--go', isActive);
    var verb = card.querySelector('.daystrip-act--go');
    if (verb) {
      verb.classList.toggle('is-active', isActive);
      verb.innerHTML = isActive
        ? (ICON_X + '<span>Hủy</span>')
        : (ICON_NAV + '<span>Đang đến</span>');
    }
  }

  function setReveal(card, offset) {
    var row = card.querySelector('.daystrip-actions');
    if (!row) { return; }
    var w = actionsWidth(card);
    var pct = 100 * (1 - Math.min(1, Math.abs(offset) / w));   // 0 -> 100% (hidden)
    row.style.transform = 'translateX(' + pct + '%)';
    card.classList.toggle('daystrip-revealed', Math.abs(offset) > 4);
  }

  function bindSwipe(card) {
    if (card.dataset.dsSwipe) { return; }
    card.dataset.dsSwipe = '1';
    var startX = 0, startY = 0, dx = 0, horizontal = false, moved = false;
    var opened = false;

    card.addEventListener('touchstart', function (e) {
      if (!e.touches || !e.touches.length) { return; }
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      dx = 0; horizontal = false; moved = false;
    }, { passive: true });

    card.addEventListener('touchmove', function (e) {
      if (!e.touches || !e.touches.length) { return; }
      dx = e.touches[0].clientX - startX;
      var dy = e.touches[0].clientY - startY;
      if (!horizontal) {
        if (Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy)) { horizontal = true; }
        else if (Math.abs(dy) > 10) { return; }   // vertical scroll wins
        else { return; }
      }
      e.stopPropagation();                 // don't feed the date-swipe
      if (e.cancelable) { e.preventDefault(); }
      moved = true;
      var base = opened ? -actionsWidth(card) : 0;
      var off = Math.max(-actionsWidth(card), Math.min(0, base + dx));
      setReveal(card, off);
    }, { passive: false });

    card.addEventListener('touchend', function (e) {
      if (!horizontal) { return; }
      e.stopPropagation();
      var base = opened ? -actionsWidth(card) : 0;
      var off = base + dx;
      if (off <= -SWIPE_MIN) { opened = true; setReveal(card, -actionsWidth(card)); }
      else { opened = false; setReveal(card, 0); }
      if (moved) { card.dataset.dsSwiped = String(Date.now()); }
    }, { passive: true });

    // Swallow the synthetic click after a swipe so the card's detail toggle
    // (app.js @click) does not fire from a reveal gesture.
    card.addEventListener('click', function (e) {
      var ts = parseInt(card.dataset.dsSwiped || '0', 10);
      if (ts && (Date.now() - ts) < 350) { e.stopPropagation(); e.preventDefault(); }
    }, true);

    card._dsClose = function () { opened = false; setReveal(card, 0); };
  }

  function enhanceCards() {
    var byId = {};
    (lastToday.bookings || []).forEach(function (b) { byId[b.fso_id] = b; });
    var cards = document.querySelectorAll(
      '.today-view .bookings-list .booking-card[data-fso-id]');
    Array.prototype.forEach.call(cards, function (card) {
      var fsoId = parseInt(card.getAttribute('data-fso-id'), 10);
      var b = byId[fsoId] || {};
      var status = card.getAttribute('data-fso-status') || b.status || '';
      var phone = b.patient_phone || '';
      if (!card.querySelector('.daystrip-actions')) {
        card.classList.add('daystrip-card');
        card.appendChild(buildActions(card, fsoId, phone, status));
        setReveal(card, 0);
        bindSwipe(card);
      }
      syncVerb(card, fsoId);
    });
  }

  // ---- day-strip header -------------------------------------------------
  function stripHtml() {
    var html = '<div class="daystrip-track">';
    TICKS.forEach(function (h) {
      var left = (h * 60 - DAY_START_MIN) / SPAN_MIN * 100;
      html += '<div class="daystrip-tick" style="left:' + left + '%">'
        + '<span>' + pad(h) + ':00</span></div>';
    });
    (lastToday.bookings || []).forEach(function (b) {
      var m = localMinutes(b.scheduled_datetime);
      if (m === null) { return; }
      var dur = parseInt(b.scheduled_duration, 10) || 60;
      var left = (m - DAY_START_MIN) / SPAN_MIN * 100;
      var width = dur / SPAN_MIN * 100;
      if (left + width < 0 || left > 100) { return; }   // fully outside window
      left = Math.max(0, left);
      width = Math.max(1.6, Math.min(width, 100 - left));
      var color = statusColor(b.status, b.scheduled_datetime);
      html += '<button type="button" class="daystrip-block" '
        + 'data-fso-id="' + b.fso_id + '" '
        + 'title="' + escAttr(labelOf(b.scheduled_datetime) + '  ' + (b.patient_name || '')) + '" '
        + 'style="left:' + left + '%;width:' + width + '%;background:' + color + '"></button>';
    });
    if (lastToday.date === todayLocalISO()) {
      var nm = nowMinutes();
      if (nm >= DAY_START_MIN && nm <= DAY_END_MIN) {
        var nl = (nm - DAY_START_MIN) / SPAN_MIN * 100;
        html += '<div class="daystrip-now" style="left:' + nl + '%"></div>';
      }
    }
    html += '</div>';
    return html;
  }

  function wireStrip(strip) {
    Array.prototype.forEach.call(
      strip.querySelectorAll('.daystrip-block'), function (block) {
        block.addEventListener('click', function () {
          var id = block.getAttribute('data-fso-id');
          var card = document.querySelector(
            '.today-view .bookings-list .booking-card[data-fso-id="' + id + '"]');
          if (card) {
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            card.classList.add('daystrip-hi');
            setTimeout(function () { card.classList.remove('daystrip-hi'); }, 1200);
          }
        });
      });
  }

  function removeStrip() {
    var strip = document.getElementById('daystrip-strip');
    if (strip && strip.parentNode) { strip.parentNode.removeChild(strip); }
  }

  function buildStrip() {
    var view = document.querySelector('.today-view');
    if (!view) { removeStrip(); return; }
    var summary = view.querySelector('.bk-summary');
    var list = view.querySelector('.bookings-list');
    var empty = view.querySelector('.empty-state');
    var anchor = summary || list || empty;
    if (!anchor || !anchor.parentNode) { removeStrip(); return; }
    var host = anchor.parentNode;
    var strip = document.getElementById('daystrip-strip');
    if (!strip) {
      strip = document.createElement('div');
      strip.id = 'daystrip-strip';
      strip.className = 'daystrip-strip';
    }
    if (strip.parentNode !== host || strip.nextSibling !== anchor) {
      host.insertBefore(strip, anchor);
    }
    strip.innerHTML = stripHtml();
    wireStrip(strip);
  }

  // ---- render orchestration --------------------------------------------
  function render() {
    renderPending = false;
    if (observer) { observer.disconnect(); }
    try {
      var dayActive = !!document.querySelector('.bk-seg.sel-day');
      if (!dayActive) { removeStrip(); return; }
      enhanceCards();
      buildStrip();
    } catch (e) {
      /* never break the shell */
    } finally {
      if (observer) {
        observer.observe(document.body, { childList: true, subtree: true });
      }
    }
  }
  function scheduleRender() {
    if (renderPending) { return; }
    renderPending = true;
    setTimeout(render, 60);
  }

  // ---- boot -------------------------------------------------------------
  function boot() {
    observer = new MutationObserver(function () { scheduleRender(); });
    observer.observe(document.body, { childList: true, subtree: true });

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) { scheduleRender(); }
    });
    // Cross-tab: the active-travel record lives in localStorage, so a start /
    // cancel in one tab fires a 'storage' event that re-syncs the other tab's
    // verb (report point e).
    window.addEventListener('storage', function (e) {
      if (e.key === ACTIVE_KEY) { scheduleRender(); }
    });
    // Tap outside an open card closes its reveal.
    document.addEventListener('click', function (e) {
      Array.prototype.forEach.call(
        document.querySelectorAll('.booking-card.daystrip-revealed'), function (card) {
          if (!card.contains(e.target) && card._dsClose) { card._dsClose(); }
        });
    }, true);

    scheduleRender();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.healthDaystrip = {
    render: render,
    _state: function () { return lastToday; },
    getActive: getActive,
  };
})();
