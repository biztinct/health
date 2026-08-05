// Health Telehealth — "Vào video (Join video)" PWA action. Window global,
// plain JS (no Vue), no app.js edits (handover §2.4: zero lines this phase).
//
// Shares the daystrip card reveal row (health_pwa_daystrip, commit 1e6cee67):
// for booking cards whose today payload location === 'online', a third action
// button is appended into the existing .daystrip-actions row. If that row is
// absent (daystrip disabled) a minimal standalone action is injected instead,
// so the module degrades gracefully.
//
// Tapping calls GET /health_pwa/api/fso/<id>/tele/join, which returns {url}
// ONLY when the caller is assigned staff and the visit is joinable, then
// window.open()s the room. The room URL is NEVER cached or stored client-side.

(function () {
  const _t = (text) => window.odoo?._t?.(text)
    || window.PWAUtils?.i18n?.t?.(text)
    || text;
  'use strict';

  // location === 'online' identifies telemedicine cards (handover §1: today
  // payload location = fso.service_location or service_address).
  var onlineIds = {};        // fso_id -> true
  var renderPending = false;
  var observer = null;

  var ICON_VIDEO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>';

  function apiBase() {
    // Same-origin; the shell is served from the Odoo host.
    return '';
  }

  // ---- fetch-wrap data seam (daystrip precedent) ------------------------
  (function wrapFetch() {
    if (!window.fetch || window.__teleFetchWrapped) { return; }
    window.__teleFetchWrapped = true;
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var url = (typeof input === 'string') ? input : (input && input.url) || '';
      var promise = orig(input, init);
      if (url.indexOf('/health_pwa/api/assignments/today') !== -1) {
        promise.then(function (resp) {
          resp.clone().json().then(function (json) {
            if (json && json.success && json.data && json.data.bookings) {
              var map = {};
              json.data.bookings.forEach(function (b) {
                if (String(b.location || '').toLowerCase() === 'online') {
                  map[b.fso_id] = true;
                }
              });
              onlineIds = map;
              scheduleRender();
            }
          }).catch(function () { /* non-JSON — ignore */ });
        }).catch(function () { /* network error — ignore */ });
      }
      return promise;
    };
  })();

  // ---- join -------------------------------------------------------------
  function joinTele(fsoId) {
    // Open the window synchronously (in the click handler) so the popup
    // blocker allows it, then point it at the URL when the API answers.
    // NOTE: 'noopener' in the features string makes window.open return
    // null BY SPEC — that defeated the pre-open trick and left the async
    // open to be popup-blocked (iOS Safari). Open plain, sever opener by
    // hand.
    var win = null;
    try {
      win = window.open('', '_blank');
      if (win) { win.opener = null; }
    } catch (e) { win = null; }
    fetch(apiBase() + '/health_pwa/api/fso/' + fsoId + '/tele/join', {
      method: 'GET',
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    }).then(function (r) { return r.json(); }).then(function (json) {
      var url = json && json.data && json.data.url;
      if (url) {
        if (win) { win.location.href = url; }
        else { window.open(url, '_blank', 'noopener'); }
      } else {
        if (win) { win.close(); }
        alert(_t('The video room is not ready yet.'));
      }
    }).catch(function () {
      if (win) { win.close(); }
      alert(_t('Could not open the video room.'));
    });
  }

  // ---- card enhancement -------------------------------------------------
  function makeButton() {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'daystrip-act tele-join';
    b.innerHTML = ICON_VIDEO + '<span>Vào video</span>';
    return b;
  }

  function enhanceCards() {
    var cards = document.querySelectorAll(
      '.today-view .bookings-list .booking-card[data-fso-id]');
    Array.prototype.forEach.call(cards, function (card) {
      var fsoId = parseInt(card.getAttribute('data-fso-id'), 10);
      var isOnline = !!onlineIds[fsoId];
      var existing = card.querySelector('.tele-join');
      if (!isOnline) {
        if (existing && existing.parentNode) { existing.parentNode.removeChild(existing); }
        card.classList.remove('tele-card');
        return;
      }
      if (existing) { return; }
      var btn = makeButton();
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        joinTele(fsoId);
      });
      card.classList.add('tele-card');
      // Preferred: share the daystrip reveal row (swipe to reveal). Fallback:
      // a standalone row so the action still works without daystrip.
      var row = card.querySelector('.daystrip-actions');
      if (row) {
        row.appendChild(btn);
      } else {
        var solo = card.querySelector('.tele-actions');
        if (!solo) {
          solo = document.createElement('div');
          solo.className = 'tele-actions';
          card.appendChild(solo);
        }
        solo.appendChild(btn);
      }
    });
  }

  // ---- render orchestration --------------------------------------------
  function render() {
    renderPending = false;
    if (observer) { observer.disconnect(); }
    try {
      enhanceCards();
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
    setTimeout(render, 70);
  }

  function boot() {
    observer = new MutationObserver(function () { scheduleRender(); });
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) { scheduleRender(); }
    });
    scheduleRender();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.healthTelehealth = {
    render: render,
    _online: function () { return onlineIds; },
    join: joinTele,
  };
})();
