// Health PWA Family Messaging — window global, plain JS (no Vue).
//
// Visit-context family-message panel + FB-047 one-tap post-visit update,
// injected into the order-detail screen without editing app.js (daystrip/
// scribe precedent). Two responsibilities:
//   1. Read the patient's family threads and reply as the field nurse.
//   2. FB-047: at visit completion, send a short human update fanned out to
//      every eligible family relation.
//
// Data seam (report point b): window.fetch is wrapped for the
// GET /health_pwa/api/fso/<id> response the order screen already loads — that
// tells us the current order id + patient + state. We then call our own
// /family_messages endpoint (nurse-scoped, sudo server-side) and inject the
// panel. Chosen over MutationObserver-only because reusing the real payload
// gives us the order state for free and keys the panel to the exact visit.
//
// SECURITY: family bodies are attacker-adjacent — every family/message text
// node is set via textContent (never innerHTML). Everything goes dark when
// the server reports enabled:false (master switch off / not assigned).
// Glove/sunlight compat lives in fammsg.css (--touch-target + html.vu-* rules).

(function () {
  'use strict';

  // ---- inline SVG (currentColor, no emoji) ------------------------------
  var ICON_CHAT =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M22 2 11 13"/><path d="M22 2 15 22 11 13 2 9z"/></svg>';

  // FB-047 canned VN quick phrases (tap to prefill, editable).
  var QUICK_PHRASES = [
    'Ca thăm khám đã hoàn tất tốt đẹp.',
    'Người bệnh ổn định, ăn uống tốt.',
    'Cần theo dõi thêm, chúng tôi sẽ liên hệ lại.',
  ];
  // FSO states where a post-visit update makes sense (completing/completed).
  var UPDATE_STATES = {
    in_progress: 1, completed: 1, completed_pending_invoice: 1, closed: 1,
  };
  var COLLAPSE_KEY = 'vu_fammsg_collapsed';

  var currentOrder = null;   // {id, patientId, state}
  var lastData = null;       // {enabled, can_update, threads}
  var box = null;            // the injected .fammsg-panel element
  var observer = null;
  var renderPending = false;

  // ---- small DOM helper (textContent — never innerHTML for data) --------
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text != null) { n.textContent = text; }
    return n;
  }

  function toast(msg) {
    if (window.healthPWA && window.healthPWA.showNotification) {
      window.healthPWA.showNotification(msg, 'info');
    }
  }

  // ---- fetch-wrap data seam ---------------------------------------------
  (function wrapFetch() {
    if (!window.fetch || window.__fammsgFetchWrapped) { return; }
    window.__fammsgFetchWrapped = true;
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var url = (typeof input === 'string') ? input : (input && input.url) || '';
      var promise = orig(input, init);
      // Only the bare order-detail GET: /health_pwa/api/fso/<id>  (id at end
      // or followed by ?query) — NOT the sub-routes like .../family_messages.
      var m = url.match(/\/health_pwa\/api\/fso\/(\d+)(?:\?|$)/);
      var method = (init && init.method ? init.method : 'GET').toUpperCase();
      if (m && method === 'GET') {
        promise.then(function (resp) {
          resp.clone().json().then(function (json) {
            if (json && json.success && json.data && json.data.id) {
              currentOrder = {
                id: json.data.id,
                patientId: (json.data.patient && json.data.patient.id) || null,
                state: json.data.state || '',
              };
              loadMessages();
            }
          }).catch(function () { /* non-JSON — ignore */ });
        }).catch(function () { /* network error — ignore */ });
      }
      return promise;
    };
  })();

  // ---- data load --------------------------------------------------------
  function loadMessages() {
    if (!currentOrder) { return; }
    fetch('/health_pwa/api/fso/' + currentOrder.id + '/family_messages',
          { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.success && j.data) {
          lastData = j.data;
          scheduleRender();
        } else {
          lastData = null;
          removePanel();
        }
      }).catch(function () { /* ignore */ });
  }

  // ---- injection (idempotent; render only via scheduleRender) -----------
  function ensurePanel() {
    var host = document.querySelector('.order-details');
    var anchor = host && host.querySelector('.order-actions');
    if (!host || !anchor) { box = null; return null; }
    var existing = host.querySelector('.fammsg-panel');
    if (existing) { box = existing; return box; }
    box = document.createElement('div');
    box.className = 'fammsg-panel';
    anchor.parentNode.insertBefore(box, anchor.nextSibling);
    return box;
  }

  function removePanel() {
    var existing = document.querySelector('.fammsg-panel');
    if (existing && existing.parentNode) {
      existing.parentNode.removeChild(existing);
    }
    box = null;
  }

  function renderNow() {
    if (!lastData || !lastData.enabled) { removePanel(); return; }
    if (!ensurePanel()) { return; }
    render();
  }

  function scheduleRender() {
    if (renderPending) { return; }
    renderPending = true;
    setTimeout(function () {
      renderPending = false;
      if (observer) { observer.disconnect(); }
      try { renderNow(); } catch (e) { /* never break the shell */ }
      finally {
        if (observer) {
          observer.observe(document.body, { childList: true, subtree: true });
        }
      }
    }, 70);
  }

  // ---- render -----------------------------------------------------------
  function render() {
    if (!box) { return; }
    box.innerHTML = '';
    var collapsed = localStorage.getItem(COLLAPSE_KEY) === '1';
    box.classList.toggle('fammsg-collapsed', collapsed);

    var header = el('div', 'fammsg-head');
    var icon = el('span', 'fammsg-head-icon');
    icon.innerHTML = ICON_CHAT;
    header.appendChild(icon);
    header.appendChild(el('span', 'fammsg-title',
      'Tin nhắn gia đình (Family messages)'));
    header.appendChild(el('span', 'fammsg-caret'));
    header.addEventListener('click', function () {
      var now = !box.classList.contains('fammsg-collapsed');
      box.classList.toggle('fammsg-collapsed', now);
      localStorage.setItem(COLLAPSE_KEY, now ? '1' : '0');
    });
    box.appendChild(header);

    var body = el('div', 'fammsg-body');
    box.appendChild(body);

    var threads = lastData.threads || [];
    if (!threads.length) {
      body.appendChild(el('div', 'fammsg-empty',
        'Chưa có tin nhắn từ gia đình. (No family messages yet.)'));
    }
    threads.forEach(function (th) { body.appendChild(renderThread(th)); });

    if (lastData.can_update && isCompleting()) {
      body.appendChild(renderUpdate());
    }
  }

  function renderThread(th) {
    var wrap = el('div', 'fammsg-thread');
    wrap.appendChild(el('div', 'fammsg-relation', th.relation || ''));
    var list = el('div', 'fammsg-list');
    (th.messages || []).forEach(function (m) {
      // Nurse perspective: team 'out' bubbles are "mine" (right), family
      // 'in' bubbles are the family's (left).
      var side = (m.direction === 'out') ? 'out' : 'in';
      var bubble = el('div', 'fammsg-msg fammsg-msg--' + side);
      bubble.appendChild(el('div', 'fammsg-msg-body', m.body || ''));
      var meta = (m.author || '') + (m.when ? ' · ' + m.when : '');
      bubble.appendChild(el('div', 'fammsg-meta', meta));
      list.appendChild(bubble);
    });
    wrap.appendChild(list);

    var compose = el('div', 'fammsg-compose');
    var ta = el('textarea', 'fammsg-input');
    ta.setAttribute('maxlength', '2000');
    ta.setAttribute('placeholder', 'Trả lời gia đình... (Reply to family...)');
    var btn = el('button', 'fammsg-send');
    btn.type = 'button';
    btn.innerHTML = ICON_SEND;
    btn.appendChild(el('span', null, 'Gửi'));
    btn.addEventListener('click', function () {
      sendReply(th.thread_id, ta, btn);
    });
    compose.appendChild(ta);
    compose.appendChild(btn);
    wrap.appendChild(compose);
    return wrap;
  }

  function renderUpdate() {
    var wrap = el('div', 'fammsg-update');
    wrap.appendChild(el('div', 'fammsg-update-title',
      'Gửi cập nhật cho gia đình (Send family update)'));

    var ta = el('textarea', 'fammsg-input');
    ta.setAttribute('maxlength', '2000');
    ta.setAttribute('placeholder', 'Nội dung cập nhật... (Update text...)');

    var chips = el('div', 'fammsg-chips');
    QUICK_PHRASES.forEach(function (phrase) {
      var chip = el('button', 'fammsg-chip', phrase);
      chip.type = 'button';
      chip.addEventListener('click', function () {
        ta.value = phrase;
        ta.focus();
      });
      chips.appendChild(chip);
    });
    wrap.appendChild(chips);
    wrap.appendChild(ta);

    var btn = el('button', 'fammsg-send fammsg-send--update');
    btn.type = 'button';
    btn.innerHTML = ICON_SEND;
    btn.appendChild(el('span', null, 'Gửi cập nhật'));
    btn.addEventListener('click', function () { sendUpdate(ta, btn); });
    wrap.appendChild(btn);
    return wrap;
  }

  function isCompleting() {
    return !!(currentOrder && UPDATE_STATES[currentOrder.state]);
  }

  // ---- actions ----------------------------------------------------------
  function sendReply(threadId, ta, btn) {
    var body = (ta.value || '').trim();
    if (!body || !currentOrder) { return; }
    btn.disabled = true;
    fetch('/health_pwa/api/fso/' + currentOrder.id + '/family_messages/reply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId, body: body }),
    }).then(function (r) { return r.json(); }).then(function (j) {
      btn.disabled = false;
      if (j && j.success) {
        ta.value = '';
        toast('Đã gửi trả lời. (Reply sent.)');
        loadMessages();
      } else {
        toast((j && j.error) || 'Không gửi được. (Send failed.)');
      }
    }).catch(function () {
      btn.disabled = false;
      toast('Lỗi mạng. (Network error.)');
    });
  }

  function sendUpdate(ta, btn) {
    var body = (ta.value || '').trim();
    if (!body || !currentOrder) { return; }
    btn.disabled = true;
    fetch('/health_pwa/api/fso/' + currentOrder.id + '/family_messages/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body: body }),
    }).then(function (r) { return r.json(); }).then(function (j) {
      btn.disabled = false;
      if (j && j.success) {
        ta.value = '';
        toast((j.data && j.data.message) || 'Đã gửi cập nhật.');
        loadMessages();
      } else {
        toast((j && j.error) || 'Không gửi được. (Send failed.)');
      }
    }).catch(function () {
      btn.disabled = false;
      toast('Lỗi mạng. (Network error.)');
    });
  }

  // ---- observer: re-inject if a Vue re-render wipes our panel -----------
  function initObserver() {
    if (observer) { return; }
    observer = new MutationObserver(function () {
      if (lastData && lastData.enabled &&
          !document.querySelector('.fammsg-panel')) {
        scheduleRender();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initObserver);
  } else {
    initObserver();
  }

  window.healthFamMsg = { _reload: loadMessages, _render: renderNow };
})();
