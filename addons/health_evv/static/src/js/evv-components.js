// Health EVV - UI components (spec A.5 / F.1)
//
// EvvPromptSheet  — bottom sheet: "Check in?" / "Check out?" one-tap on
//                   geofence enter/exit events. NEVER auto-submits.
// EvvSignaturePad — canvas 3:2, pointer events, undo/clear, PNG data
//                   URL, signer name + relationship; offline-queueable.
// EvvStatusChip   — small visit-header chip: fence distance + state.
//
// NOTE: the health_pwa Vue app instance is module-local (app.js never
// exposes it), so these are plain-DOM components injected as overlays —
// same visual language, flat mono colors only (no gradients).

(function () {
  'use strict';

  const VI = {
    'You have arrived — Check in?': 'Bạn đã đến nơi — Check in?',
    'Leaving the location — Check out?': 'Bạn đang rời đi — Check out?',
    'Check In': 'Check in',
    'Check Out': 'Check out',
    'Dismiss': 'Bỏ qua',
    'Client / Family Signature': 'Chữ ký khách hàng / người nhà',
    'Signer name': 'Tên người ký',
    'Client': 'Khách hàng',
    'Family Member': 'Người nhà',
    'Caregiver': 'Người chăm sóc',
    'Other': 'Khác',
    'Clear': 'Xóa',
    'Undo': 'Hoàn tác',
    'Save Signature': 'Lưu chữ ký',
    'Cancel': 'Hủy',
    'Checked in': 'Đã check in',
    'Checked out': 'Đã check out',
    'Saved offline — will sync when online': 'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng',
    'Signature saved': 'Đã lưu chữ ký',
    'Please sign and enter the signer name': 'Vui lòng ký và nhập tên người ký',
    'Error': 'Lỗi',
  };

  function _t(text) {
    if (window.PWAUtils && window.PWAUtils.i18n
        && typeof window.PWAUtils.i18n.t === 'function') {
      const translated = window.PWAUtils.i18n.t(text);
      if (translated !== text) return translated;
    }
    const isVietnamese = window.healthPWAConfig
      && window.healthPWAConfig.user_lang
      && window.healthPWAConfig.user_lang.indexOf('vi') === 0;
    if (isVietnamese && VI[text]) return VI[text];
    return text;
  }

  function notify(message, type) {
    if (window.healthPWA && window.healthPWA.showNotification) {
      window.healthPWA.showNotification(message, type || 'info');
    } else {
      console.log('[EVV]', message);
    }
  }

  // Flat mono palette (hard convention: no gradients / dual-tone).
  const COLORS = {
    surface: '#ffffff',
    text: '#212121',
    muted: '#616161',
    primary: '#1565c0',
    success: '#2e7d32',
    danger: '#c62828',
    border: '#e0e0e0',
  };

  function injectStyles() {
    if (document.getElementById('evv-styles')) return;
    const style = document.createElement('style');
    style.id = 'evv-styles';
    style.textContent = [
      '.evv-sheet{position:fixed;left:0;right:0;bottom:0;z-index:9500;',
      'background:' + COLORS.surface + ';color:' + COLORS.text + ';',
      'border-top:1px solid ' + COLORS.border + ';padding:16px;',
      'box-shadow:0 -2px 8px rgba(0,0,0,0.15);',
      'transform:translateY(100%);transition:transform .25s ease;}',
      '.evv-sheet.evv-open{transform:translateY(0);}',
      '.evv-sheet__msg{font-size:16px;font-weight:600;margin-bottom:12px;}',
      '.evv-sheet__row{display:flex;gap:8px;}',
      '.evv-btn{flex:1;border:none;border-radius:8px;padding:12px;',
      'font-size:15px;font-weight:600;cursor:pointer;}',
      '.evv-btn--primary{background:' + COLORS.primary + ';color:#fff;}',
      '.evv-btn--success{background:' + COLORS.success + ';color:#fff;}',
      '.evv-btn--muted{background:#f5f5f5;color:' + COLORS.muted + ';}',
      '.evv-overlay{position:fixed;inset:0;z-index:9600;',
      'background:rgba(0,0,0,0.5);display:flex;align-items:center;',
      'justify-content:center;padding:16px;}',
      '.evv-pad{background:' + COLORS.surface + ';border-radius:12px;',
      'padding:16px;width:100%;max-width:420px;}',
      '.evv-pad h3{margin:0 0 12px;font-size:16px;color:' + COLORS.text + ';}',
      '.evv-pad canvas{width:100%;border:1px dashed ' + COLORS.border + ';',
      'border-radius:8px;touch-action:none;background:#fafafa;}',
      '.evv-pad input,.evv-pad select{width:100%;margin-top:8px;',
      'padding:10px;border:1px solid ' + COLORS.border + ';',
      'border-radius:8px;font-size:14px;}',
      '.evv-pad__actions{display:flex;gap:8px;margin-top:12px;}',
      '.evv-chip{position:fixed;top:64px;right:12px;z-index:9400;',
      'background:' + COLORS.primary + ';color:#fff;border-radius:16px;',
      'padding:4px 12px;font-size:12px;font-weight:600;}',
      '.evv-chip--inside{background:' + COLORS.success + ';}',
    ].join('');
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------
  // EvvPromptSheet
  // ---------------------------------------------------------------
  const EvvPromptSheet = {
    element: null,
    show: function (message, buttonLabel, buttonClass, onTap) {
      injectStyles();
      this.hide();
      const sheet = document.createElement('div');
      sheet.className = 'evv-sheet';
      sheet.innerHTML =
        '<div class="evv-sheet__msg"></div>' +
        '<div class="evv-sheet__row">' +
        '<button class="evv-btn evv-btn--muted" data-evv="dismiss"></button>' +
        '<button class="evv-btn ' + buttonClass + '" data-evv="ok"></button>' +
        '</div>';
      sheet.querySelector('.evv-sheet__msg').textContent = message;
      sheet.querySelector('[data-evv="dismiss"]').textContent = _t('Dismiss');
      sheet.querySelector('[data-evv="ok"]').textContent = buttonLabel;
      const self = this;
      sheet.querySelector('[data-evv="dismiss"]')
        .addEventListener('click', function () { self.hide(); });
      sheet.querySelector('[data-evv="ok"]')
        .addEventListener('click', function () {
          self.hide();
          onTap();
        });
      document.body.appendChild(sheet);
      this.element = sheet;
      requestAnimationFrame(function () { sheet.classList.add('evv-open'); });
    },
    hide: function () {
      if (this.element) {
        this.element.remove();
        this.element = null;
      }
    },
  };

  // ---------------------------------------------------------------
  // EvvStatusChip
  // ---------------------------------------------------------------
  const EvvStatusChip = {
    element: null,
    update: function (distanceM, inside) {
      injectStyles();
      if (!this.element) {
        this.element = document.createElement('div');
        this.element.className = 'evv-chip';
        document.body.appendChild(this.element);
      }
      this.element.classList.toggle('evv-chip--inside', !!inside);
      this.element.textContent = 'EVV ' + Math.round(distanceM) + ' m';
    },
    remove: function () {
      if (this.element) { this.element.remove(); this.element = null; }
    },
  };

  // ---------------------------------------------------------------
  // EvvSignaturePad
  // ---------------------------------------------------------------
  const EvvSignaturePad = {
    open: function (fsoId) {
      injectStyles();
      const overlay = document.createElement('div');
      overlay.className = 'evv-overlay';
      overlay.innerHTML =
        '<div class="evv-pad">' +
        '<h3></h3>' +
        '<canvas width="600" height="400"></canvas>' +
        '<input type="text" data-evv="name"/>' +
        '<select data-evv="rel">' +
        '<option value="client"></option>' +
        '<option value="family" selected="selected"></option>' +
        '<option value="caregiver"></option>' +
        '<option value="other"></option>' +
        '</select>' +
        '<div class="evv-pad__actions">' +
        '<button class="evv-btn evv-btn--muted" data-evv="cancel"></button>' +
        '<button class="evv-btn evv-btn--muted" data-evv="undo"></button>' +
        '<button class="evv-btn evv-btn--muted" data-evv="clear"></button>' +
        '</div>' +
        '<div class="evv-pad__actions">' +
        '<button class="evv-btn evv-btn--success" data-evv="save"></button>' +
        '</div>' +
        '</div>';
      overlay.querySelector('h3').textContent = _t('Client / Family Signature');
      overlay.querySelector('[data-evv="name"]')
        .setAttribute('placeholder', _t('Signer name'));
      const relLabels = {
        client: _t('Client'), family: _t('Family Member'),
        caregiver: _t('Caregiver'), other: _t('Other'),
      };
      overlay.querySelectorAll('[data-evv="rel"] option')
        .forEach(function (option) {
          option.textContent = relLabels[option.value];
        });
      overlay.querySelector('[data-evv="cancel"]').textContent = _t('Cancel');
      overlay.querySelector('[data-evv="undo"]').textContent = _t('Undo');
      overlay.querySelector('[data-evv="clear"]').textContent = _t('Clear');
      overlay.querySelector('[data-evv="save"]').textContent = _t('Save Signature');

      const canvas = overlay.querySelector('canvas');
      const context = canvas.getContext('2d');
      context.lineWidth = 2.5;
      context.lineCap = 'round';
      context.strokeStyle = COLORS.text;
      let drawing = false;
      let strokes = [];
      let currentStroke = null;
      let hasInk = false;

      function canvasPoint(event) {
        const rect = canvas.getBoundingClientRect();
        return {
          x: (event.clientX - rect.left) * (canvas.width / rect.width),
          y: (event.clientY - rect.top) * (canvas.height / rect.height),
        };
      }
      function redraw() {
        context.clearRect(0, 0, canvas.width, canvas.height);
        strokes.forEach(function (stroke) {
          context.beginPath();
          stroke.forEach(function (point, index) {
            if (index === 0) context.moveTo(point.x, point.y);
            else context.lineTo(point.x, point.y);
          });
          context.stroke();
        });
        hasInk = strokes.length > 0;
      }
      canvas.addEventListener('pointerdown', function (event) {
        drawing = true;
        currentStroke = [canvasPoint(event)];
        canvas.setPointerCapture(event.pointerId);
      });
      canvas.addEventListener('pointermove', function (event) {
        if (!drawing) return;
        currentStroke.push(canvasPoint(event));
        strokes.push(currentStroke);
        redraw();
        strokes.pop();
        // live preview of the in-progress stroke
        context.beginPath();
        currentStroke.forEach(function (point, index) {
          if (index === 0) context.moveTo(point.x, point.y);
          else context.lineTo(point.x, point.y);
        });
        context.stroke();
      });
      function endStroke() {
        if (!drawing) return;
        drawing = false;
        if (currentStroke && currentStroke.length > 1) {
          strokes.push(currentStroke);
        }
        currentStroke = null;
        redraw();
      }
      canvas.addEventListener('pointerup', endStroke);
      canvas.addEventListener('pointercancel', endStroke);

      overlay.querySelector('[data-evv="undo"]')
        .addEventListener('click', function () {
          strokes.pop();
          redraw();
        });
      overlay.querySelector('[data-evv="clear"]')
        .addEventListener('click', function () {
          strokes = [];
          redraw();
        });
      overlay.querySelector('[data-evv="cancel"]')
        .addEventListener('click', function () { overlay.remove(); });

      overlay.querySelector('[data-evv="save"]')
        .addEventListener('click', async function () {
          const signerName =
            overlay.querySelector('[data-evv="name"]').value.trim();
          if (!hasInk || !signerName) {
            notify(_t('Please sign and enter the signer name'), 'warning');
            return;
          }
          const relationship =
            overlay.querySelector('[data-evv="rel"]').value;
          const dataUrl = canvas.toDataURL('image/png');
          const imageB64 = dataUrl.split(',', 2)[1];
          overlay.remove();
          await submitSignature(fsoId, imageB64, signerName, relationship);
        });

      document.body.appendChild(overlay);
    },
  };

  // ---------------------------------------------------------------
  // Submission helpers
  // ---------------------------------------------------------------
  function currentPosition() {
    const geofence = window.healthEvvGeofence;
    return (geofence && geofence.lastPosition)
      || { lat: 0.0, lng: 0.0, accuracy_m: 0.0 };
  }

  async function buildEvent(fsoId, eventType, payload) {
    const queue = window.healthEvvQueue;
    const config = (window.healthEvvGeofence
      && window.healthEvvGeofence.config)
      || await queue.getConfig(fsoId) || {};
    const position = currentPosition();
    return {
      fso_id: fsoId,
      event_type: eventType,
      event_datetime: window.healthEvvCanonical.canonicalDatetime(new Date()),
      lat: position.lat, lng: position.lng,
      accuracy_m: position.accuracy_m || 0.0,
      staff_id: config.staff_id || 0,
      device_uuid: queue.deviceUuid(),
      client_event_uuid: queue.newEventUuid(),
      payload: payload || {},
    };
  }

  async function submitEvent(fsoId, eventType, payload) {
    const event = await buildEvent(fsoId, eventType, payload);
    if (!navigator.onLine) {
      await window.healthEvvQueue.enqueue(event);
      notify(_t('Saved offline — will sync when online'), 'info');
      return { queued: true };
    }
    try {
      event.client_hash = await window.healthEvvCanonical.hashEvent(event);
      const response = await fetch(
        '/health_pwa/api/fso/' + fsoId + '/evv/event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(event),
        });
      const result = await response.json();
      if (!result.success) throw new Error(result.error || 'EVV error');
      return result.data;
    } catch (error) {
      // Network/server hiccup — fall back to the offline queue.
      console.warn('EVV online submit failed, queueing', error);
      await window.healthEvvQueue.enqueue(event);
      notify(_t('Saved offline — will sync when online'), 'info');
      return { queued: true };
    }
  }

  async function submitSignature(fsoId, imageB64, signerName, relationship) {
    const event = await buildEvent(fsoId, 'signature', {
      signer_name: signerName,
      signer_relationship: relationship,
    });
    // png_sha256 binds the image into the hash chain; compute it
    // client-side (online AND offline) so the client hash can match
    // the server's recomputation.
    try {
      const binary = atob(imageB64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      event.payload.png_sha256 = Array.from(new Uint8Array(digest))
        .map(function (b) { return b.toString(16).padStart(2, '0'); })
        .join('');
    } catch (error) {
      console.warn('EVV: png_sha256 computation failed', error);
    }
    if (!navigator.onLine) {
      event.image_b64 = imageB64;
      await window.healthEvvQueue.enqueue(event);
      notify(_t('Saved offline — will sync when online'), 'info');
      return;
    }
    try {
      event.client_hash = await window.healthEvvCanonical.hashEvent(event);
      const response = await fetch(
        '/health_pwa/api/fso/' + fsoId + '/evv/signature', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_base64: imageB64,
            signer_name: signerName,
            signer_relationship: relationship,
            lat: event.lat, lng: event.lng,
            accuracy_m: event.accuracy_m,
            device_uuid: event.device_uuid,
            client_event_uuid: event.client_event_uuid,
            client_hash: event.client_hash,
            event_datetime: event.event_datetime,
          }),
        });
      const result = await response.json();
      if (!result.success) throw new Error(result.error || 'EVV error');
      notify(_t('Signature saved'), 'success');
    } catch (error) {
      console.warn('EVV signature online submit failed, queueing', error);
      event.image_b64 = imageB64;
      await window.healthEvvQueue.enqueue(event);
      notify(_t('Saved offline — will sync when online'), 'info');
    }
  }

  // ---------------------------------------------------------------
  // Wiring: geofence events -> one-tap prompts (never auto-submit)
  // ---------------------------------------------------------------
  window.addEventListener('evv:position', function (event) {
    EvvStatusChip.update(event.detail.distance_m, event.detail.inside);
  });
  window.addEventListener('hashchange', function () {
    if (!/#\/orders\/\d+/.test(window.location.hash)) {
      EvvStatusChip.remove();
      EvvPromptSheet.hide();
    }
  });

  window.addEventListener('evv:geofence-enter', function (event) {
    const fsoId = event.detail.fso_id;
    EvvPromptSheet.show(
      _t('You have arrived — Check in?'), _t('Check In'),
      'evv-btn--primary',
      async function () {
        await submitEvent(fsoId, 'checkin', {});
        notify(_t('Checked in'), 'success');
        if (window.healthEvvGeofence) window.healthEvvGeofence.onCheckedIn();
      });
  });

  window.addEventListener('evv:geofence-exit', function (event) {
    const fsoId = event.detail.fso_id;
    EvvPromptSheet.show(
      _t('Leaving the location — Check out?'), _t('Check Out'),
      'evv-btn--success',
      async function () {
        await submitEvent(fsoId, 'checkout', {});
        notify(_t('Checked out'), 'success');
        if (window.healthEvvGeofence) window.healthEvvGeofence.onCheckedOut();
        // Offer signature capture right after check-out when missing.
        const config = await window.healthEvvQueue.getConfig(fsoId);
        if (!config || !config.signature_done) {
          EvvSignaturePad.open(fsoId);
        }
      });
  });

  window.healthEVV = {
    promptSheet: EvvPromptSheet,
    signaturePad: EvvSignaturePad,
    statusChip: EvvStatusChip,
    submitEvent: submitEvent,
    submitSignature: submitSignature,
    openSignaturePad: function (fsoId) { EvvSignaturePad.open(fsoId); },
  };
})();
