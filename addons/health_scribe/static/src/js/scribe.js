// Health Ambient Scribe — mic capture in the PWA clinical-note modal.
// Window global, plain IIFE (no Vue), ZERO app.js edits (handover §2.2/§2.4).
//
// Two seams, both borrowed from shipped modules:
//  1. MutationObserver (telehealth precedent) injects a mic block next to the
//     note modal's stable `.photo-upload-container` anchor.
//  2. fetch-wrap (telehealth/daystrip precedent): when the note-save POST to
//     /clinical_notes returns a note_id, if a recording is pending we upload it
//     to /upload_audio with that note_id — mirroring the photo flow from the
//     outside, so app.js is never touched.
//
// Recording refuses to start offline (the photo posture). getUserMedia needs a
// secure context — care.biztinct.com is https.

(function () {
  'use strict';

  // Mirrors the server default health_scribe.max_seconds; the real safety gate
  // is the server's max_bytes on upload.
  var MAX_SECONDS = 300;
  var MIME_CANDIDATES = [
    'audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus',
  ];

  var pendingAudio = null;     // {blob, durationS} once recorded
  var mediaRecorder = null;
  var chunks = [];
  var stream = null;
  var startMs = 0;
  var timer = null;
  var hardStop = null;
  var box = null;              // the injected .scribe-container element
  var observer = null;
  var renderPending = false;

  var ICON_MIC =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>' +
    '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/>' +
    '<line x1="8" y1="23" x2="16" y2="23"/></svg>';
  var ICON_STOP =
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' +
    '<rect x="6" y="6" width="12" height="12" rx="2"/></svg>';
  var ICON_TRASH =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>' +
    '<path d="M10 11v6M14 11v6"/></svg>';

  function pickMime() {
    if (!window.MediaRecorder) { return null; }
    for (var i = 0; i < MIME_CANDIDATES.length; i++) {
      try {
        if (MediaRecorder.isTypeSupported(MIME_CANDIDATES[i])) {
          return MIME_CANDIDATES[i];
        }
      } catch (e) { /* ignore */ }
    }
    return '';   // let the browser choose its default
  }

  function fmt(sec) {
    var m = Math.floor(sec / 60), s = sec % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  // ---- render the injected block per state ------------------------------
  function render(state, extra) {
    if (!box) { return; }
    var html = '<label class="clinical-form-label">Ghi âm (Record)</label>';
    if (state === 'recording') {
      html +=
        '<div class="scribe-row scribe-recording">' +
        '<span class="scribe-dot"></span>' +
        '<span class="scribe-timer">' + fmt(extra || 0) + '</span>' +
        '<button type="button" class="scribe-btn scribe-stop">' + ICON_STOP +
        '<span>Dừng (Stop)</span></button></div>';
    } else if (state === 'preview') {
      html +=
        '<div class="scribe-row scribe-preview">' +
        '<span class="scribe-ok">Đã ghi ' + (extra || 0) +
        ' giây (recorded ' + (extra || 0) + 's)</span>' +
        '<button type="button" class="scribe-btn scribe-rerec">' + ICON_MIC +
        '<span>Ghi lại (Re-record)</span></button>' +
        '<button type="button" class="scribe-btn scribe-discard">' + ICON_TRASH +
        '<span>Xóa (Discard)</span></button></div>';
    } else {
      html +=
        '<div class="scribe-row scribe-idle">' +
        '<button type="button" class="scribe-btn scribe-record">' + ICON_MIC +
        '<span>Ghi âm (Record)</span></button></div>';
    }
    box.innerHTML = html;
    var q = function (c) { return box.querySelector(c); };
    if (q('.scribe-record')) { q('.scribe-record').onclick = startRecording; }
    if (q('.scribe-stop')) { q('.scribe-stop').onclick = stopRecording; }
    if (q('.scribe-rerec')) { q('.scribe-rerec').onclick = startRecording; }
    if (q('.scribe-discard')) { q('.scribe-discard').onclick = discard; }
  }

  // ---- recording lifecycle ---------------------------------------------
  function cleanupStream() {
    if (timer) { clearInterval(timer); timer = null; }
    if (hardStop) { clearTimeout(hardStop); hardStop = null; }
    if (stream) {
      try { stream.getTracks().forEach(function (t) { t.stop(); }); }
      catch (e) { /* ignore */ }
      stream = null;
    }
  }

  function startRecording() {
    if (!navigator.onLine) {
      alert('Cần kết nối mạng để ghi âm (recording needs a connection)');
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia ||
        !window.MediaRecorder) {
      alert('Thiết bị không hỗ trợ ghi âm (recording is not supported)');
      return;
    }
    pendingAudio = null;
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
      stream = s;
      chunks = [];
      var mime = pickMime();
      try {
        mediaRecorder = mime ? new MediaRecorder(s, { mimeType: mime })
                             : new MediaRecorder(s);
      } catch (e) {
        mediaRecorder = new MediaRecorder(s);
      }
      mediaRecorder.ondataavailable = function (ev) {
        if (ev.data && ev.data.size > 0) { chunks.push(ev.data); }
      };
      mediaRecorder.onstop = function () {
        var durationS = Math.max(1, Math.round((Date.now() - startMs) / 1000));
        var type = (mediaRecorder && mediaRecorder.mimeType) ||
          'audio/webm';
        var blob = new Blob(chunks, { type: type });
        cleanupStream();
        pendingAudio = { blob: blob, durationS: durationS };
        render('preview', durationS);
      };
      startMs = Date.now();
      mediaRecorder.start();
      render('recording', 0);
      timer = setInterval(function () {
        render('recording', Math.floor((Date.now() - startMs) / 1000));
      }, 500);
      hardStop = setTimeout(stopRecording, MAX_SECONDS * 1000);
    }).catch(function (err) {
      cleanupStream();
      if (err && err.name === 'NotAllowedError') {
        alert('Vui lòng cho phép micro để ghi âm (please allow microphone access)');
      } else {
        alert('Không thể bắt đầu ghi âm (could not start recording)');
      }
    });
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      try { mediaRecorder.stop(); } catch (e) { cleanupStream(); render('idle'); }
    }
  }

  function discard() {
    pendingAudio = null;
    render('idle');
  }

  // ---- injection --------------------------------------------------------
  function inject() {
    var anchor = document.querySelector('.photo-upload-container');
    if (!anchor) {
      // Modal closed — drop our reference so a fresh recording starts next time.
      box = null;
      return;
    }
    if (anchor.parentNode &&
        anchor.parentNode.querySelector('.scribe-container')) {
      box = anchor.parentNode.querySelector('.scribe-container');
      return;
    }
    box = document.createElement('div');
    box.className = 'scribe-container clinical-form-group';
    anchor.parentNode.insertBefore(box, anchor.nextSibling);
    render(pendingAudio ? 'preview' : 'idle',
           pendingAudio ? pendingAudio.durationS : 0);
  }

  function scheduleRender() {
    if (renderPending) { return; }
    renderPending = true;
    setTimeout(function () {
      renderPending = false;
      if (observer) { observer.disconnect(); }
      try { inject(); } catch (e) { /* never break the shell */ }
      finally {
        if (observer) {
          observer.observe(document.body, { childList: true, subtree: true });
        }
      }
    }, 70);
  }

  // ---- fetch-wrap: upload audio when the note is saved ------------------
  (function wrapFetch() {
    if (!window.fetch || window.__scribeFetchWrapped) { return; }
    window.__scribeFetchWrapped = true;
    var orig = window.fetch.bind(window);
    window.fetch = function (input, init) {
      var url = (typeof input === 'string') ? input : (input && input.url) || '';
      var promise = orig(input, init);
      var m = url.match(/\/health_pwa\/api\/fso\/(\d+)\/clinical_notes/);
      if (m && pendingAudio) {
        var orderId = m[1];
        promise.then(function (resp) {
          resp.clone().json().then(function (json) {
            var noteId = json && json.data && json.data.note_id;
            if (noteId && pendingAudio) {
              uploadAudio(orderId, noteId, pendingAudio);
            }
          }).catch(function () { /* non-JSON — ignore */ });
        }).catch(function () { /* network error — ignore */ });
      }
      return promise;
    };
  })();

  function uploadAudio(orderId, noteId, rec) {
    var fd = new FormData();
    fd.append('audio', rec.blob, 'recording.webm');
    fd.append('note_id', noteId);
    fd.append('duration_s', rec.durationS);
    // The wrapped fetch is safe here: /upload_audio does not match the
    // /clinical_notes trigger, so it passes straight through.
    fetch('/health_pwa/api/fso/' + orderId + '/upload_audio', {
      method: 'POST',
      credentials: 'same-origin',
      body: fd,
    }).then(function () {
      pendingAudio = null;
      render('idle');
    }).catch(function () { /* leave the recording for a manual retry */ });
  }

  function boot() {
    observer = new MutationObserver(function () { scheduleRender(); });
    observer.observe(document.body, { childList: true, subtree: true });
    scheduleRender();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.healthScribe = {
    _pending: function () { return pendingAudio; },
    _inject: inject,
    discard: discard,
  };
})();
