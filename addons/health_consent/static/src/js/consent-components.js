// Health Consent - PWA capture UI (spec §6.7 / §6.8).
//
// window.healthConsentUI — plain-DOM overlay components (the health_pwa
// Vue app instance is module-local, same constraint as health_evv /
// health_forms), same visual language, flat mono colors only:
//   openCapture(patientId, options) — bottom-sheet consent capture:
//       type/method/grantor pickers, scope note, expiry and a
//       signature pad for the digital_signature method.
//   openList(patientId)  — per-type status chips + consent history +
//       "New consent" CTA + withdraw (reason prompt).
//   checkPhotography(patientId) — §6.8.1 soft photography gate.
//
// Signature: inline pointer-events canvas with clear/undo. The
// health_evv pad (window.healthEVV.signaturePad) is feature-detected
// but NOT reused — it is hard-wired to the EVV signature endpoint, so
// (exactly like health_forms) a minimal local pad with the same
// interaction captures an arbitrary PNG instead.
//
// A non-blocking "Service consent missing" banner appears on visit
// screens (#/orders/<id>, hashchange wiring mirroring the EVV chip /
// forms FAB) with a capture CTA when status.service is false.

(function () {
  'use strict';

  var VI = {
    'Consents': 'Đồng ý điều trị',
    'New consent': 'Đồng ý mới',
    'Consent type': 'Loại đồng ý',
    'Method': 'Phương thức',
    'Granted by client': 'Do khách hàng đồng ý',
    'Grantor': 'Người đồng ý thay',
    'Scope / limitations': 'Phạm vi / giới hạn',
    'Expiry date (optional)': 'Ngày hết hạn (tùy chọn)',
    'Sign here': 'Ký tại đây',
    'Clear': 'Xóa',
    'Undo': 'Hoàn tác',
    'Save': 'Lưu',
    'Close': 'Đóng',
    'Cancel': 'Hủy',
    'Withdraw': 'Thu hồi',
    'Withdrawal reason': 'Lý do thu hồi',
    'Consent granted': 'Đã ghi nhận đồng ý',
    'Signature is required': 'Cần có chữ ký',
    'Select a grantor relation': 'Chọn người đồng ý thay',
    'Saved offline — will sync when online':
      'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng',
    'Service consent missing': 'Thiếu đồng ý dịch vụ',
    'Capture now': 'Ghi nhận ngay',
    'Dismiss': 'Bỏ qua',
    'Error': 'Lỗi',
    'Active': 'Hiệu lực',
    'Missing': 'Chưa có',
    'self': 'khách hàng',
  };

  function isVietnamese() {
    return Boolean(window.healthPWAConfig
      && window.healthPWAConfig.user_lang
      && window.healthPWAConfig.user_lang.indexOf('vi') === 0);
  }

  function _t(text) {
    if (window.PWAUtils && window.PWAUtils.i18n
        && typeof window.PWAUtils.i18n.t === 'function') {
      var translated = window.PWAUtils.i18n.t(text);
      if (translated !== text) return translated;
    }
    if (isVietnamese() && VI[text]) return VI[text];
    return text;
  }

  function bi(en, vi) {
    if (isVietnamese() && vi) return vi;
    return en || vi || '';
  }

  function notify(message, type) {
    if (window.healthPWA && window.healthPWA.showNotification) {
      window.healthPWA.showNotification(message, type || 'info');
    } else {
      console.log('[healthConsent]', message);
    }
  }

  function service() { return window.healthConsentService; }

  // Flat mono palette (hard convention: no gradients / dual-tone).
  var COLORS = {
    surface: '#ffffff',
    text: '#212121',
    muted: '#757575',
    border: '#e0e0e0',
    primary: '#1867c0',
    ok: '#2e7d32',
    warn: '#e65100',
    danger: '#c62828',
    scrim: 'rgba(33, 33, 33, 0.5)',
  };

  var stylesInjected = false;

  function injectStyles() {
    if (stylesInjected) return;
    stylesInjected = true;
    var css = ''
      + '.hc-overlay{position:fixed;inset:0;background:' + COLORS.scrim
      + ';z-index:9400;display:flex;align-items:flex-end;}'
      + '.hc-sheet{background:' + COLORS.surface + ';color:' + COLORS.text
      + ';width:100%;max-height:88vh;overflow-y:auto;border-radius:'
      + '12px 12px 0 0;padding:16px;box-sizing:border-box;}'
      + '.hc-title{font-size:17px;font-weight:600;margin:0 0 12px;}'
      + '.hc-label{font-size:13px;font-weight:600;margin:10px 0 4px;'
      + 'color:' + COLORS.muted + ';}'
      + '.hc-input,.hc-select{width:100%;box-sizing:border-box;'
      + 'padding:10px;border:1px solid ' + COLORS.border
      + ';border-radius:8px;font-size:15px;background:'
      + COLORS.surface + ';color:' + COLORS.text + ';}'
      + '.hc-row{display:flex;align-items:center;gap:8px;margin:10px 0;}'
      + '.hc-actions{display:flex;gap:8px;margin-top:16px;}'
      + '.hc-btn{flex:1;padding:12px;border:none;border-radius:8px;'
      + 'font-size:15px;font-weight:600;cursor:pointer;background:'
      + COLORS.primary + ';color:#ffffff;}'
      + '.hc-btn--muted{background:' + COLORS.border + ';color:'
      + COLORS.text + ';}'
      + '.hc-btn--danger{background:' + COLORS.danger + ';}'
      + '.hc-canvas{width:100%;height:160px;border:1px dashed '
      + COLORS.border + ';border-radius:8px;touch-action:none;'
      + 'background:' + COLORS.surface + ';}'
      + '.hc-chip{display:inline-block;padding:4px 10px;margin:0 6px '
      + '6px 0;border-radius:14px;font-size:12px;font-weight:600;'
      + 'color:#ffffff;}'
      + '.hc-chip--ok{background:' + COLORS.ok + ';}'
      + '.hc-chip--missing{background:' + COLORS.muted + ';}'
      + '.hc-item{padding:10px 0;border-bottom:1px solid '
      + COLORS.border + ';font-size:14px;display:flex;'
      + 'justify-content:space-between;align-items:center;gap:8px;}'
      + '.hc-item__meta{color:' + COLORS.muted + ';font-size:12px;}'
      + '.hc-link{background:none;border:none;color:' + COLORS.danger
      + ';font-size:13px;font-weight:600;cursor:pointer;padding:6px;}'
      + '.hc-banner{position:fixed;left:12px;right:12px;bottom:76px;'
      + 'z-index:9300;background:' + COLORS.warn + ';color:#ffffff;'
      + 'border-radius:10px;padding:12px;display:flex;align-items:'
      + 'center;gap:10px;font-size:14px;}'
      + '.hc-banner__text{flex:1;}'
      + '.hc-banner__btn{background:#ffffff;color:' + COLORS.warn
      + ';border:none;border-radius:8px;padding:8px 12px;font-weight:'
      + '600;cursor:pointer;font-size:13px;}'
      + '.hc-banner__close{background:none;border:none;color:#ffffff;'
      + 'font-size:18px;cursor:pointer;padding:2px 6px;}';
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------
  // Minimal signature pad (pointer events, PNG base64, clear/undo).
  // window.healthEVV.signaturePad exists on installs with health_evv
  // (feature-detectable) but submits straight to the EVV endpoint, so
  // it cannot hand back a PNG — same conclusion as health_forms.
  // ---------------------------------------------------------------
  function buildSignaturePad(container) {
    var canvas = document.createElement('canvas');
    canvas.className = 'hc-canvas';
    canvas.width = 600;
    canvas.height = 240;
    var context = canvas.getContext('2d');
    context.lineWidth = 2.5;
    context.lineCap = 'round';
    context.strokeStyle = COLORS.text;
    var drawing = false;
    var strokes = [];
    var current = null;

    function point(event) {
      var rect = canvas.getBoundingClientRect();
      return {
        x: (event.clientX - rect.left) * (canvas.width / rect.width),
        y: (event.clientY - rect.top) * (canvas.height / rect.height),
      };
    }

    function redraw() {
      context.clearRect(0, 0, canvas.width, canvas.height);
      strokes.forEach(function (stroke) {
        context.beginPath();
        stroke.forEach(function (p, index) {
          if (index === 0) context.moveTo(p.x, p.y);
          else context.lineTo(p.x, p.y);
        });
        context.stroke();
      });
    }

    canvas.addEventListener('pointerdown', function (event) {
      drawing = true;
      current = [point(event)];
      strokes.push(current);
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove', function (event) {
      if (!drawing) return;
      current.push(point(event));
      redraw();
    });
    ['pointerup', 'pointercancel'].forEach(function (name) {
      canvas.addEventListener(name, function () {
        drawing = false;
        current = null;
      });
    });

    var hint = document.createElement('div');
    hint.className = 'hc-label';
    hint.textContent = _t('Sign here');

    var actions = document.createElement('div');
    actions.className = 'hc-row';
    var undoButton = document.createElement('button');
    undoButton.type = 'button';
    undoButton.className = 'hc-btn hc-btn--muted';
    undoButton.textContent = _t('Undo');
    undoButton.addEventListener('click', function () {
      strokes.pop();
      redraw();
    });
    var clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.className = 'hc-btn hc-btn--muted';
    clearButton.textContent = _t('Clear');
    clearButton.addEventListener('click', function () {
      strokes = [];
      redraw();
    });
    actions.appendChild(undoButton);
    actions.appendChild(clearButton);

    container.appendChild(hint);
    container.appendChild(canvas);
    container.appendChild(actions);

    return {
      hasInk: function () { return strokes.length > 0; },
      toBase64: function () {
        return canvas.toDataURL('image/png').split(',', 2)[1];
      },
    };
  }

  // ---------------------------------------------------------------
  // Capture sheet
  // ---------------------------------------------------------------
  var CaptureSheet = {
    open: function (patientId, options) {
      options = options || {};
      injectStyles();
      var api = service();
      if (!api) return;

      Promise.all([api.getTypes(), api.getConsents(patientId)])
        .then(function (results) {
          CaptureSheet._render(patientId, results[0], results[1],
                               options);
        })
        .catch(function (error) {
          notify(_t('Error') + ': ' + (error && error.message || error),
                 'error');
        });
    },

    _render: function (patientId, types, consentData, options) {
      var overlay = document.createElement('div');
      overlay.className = 'hc-overlay';
      var sheet = document.createElement('div');
      sheet.className = 'hc-sheet';
      overlay.appendChild(sheet);
      overlay.addEventListener('click', function (event) {
        if (event.target === overlay) overlay.remove();
      });
      document.body.appendChild(overlay);

      var title = document.createElement('h3');
      title.className = 'hc-title';
      title.textContent = _t('New consent');
      sheet.appendChild(title);

      function labelled(text, node) {
        var label = document.createElement('div');
        label.className = 'hc-label';
        label.textContent = text;
        sheet.appendChild(label);
        sheet.appendChild(node);
      }

      var typeSelect = document.createElement('select');
      typeSelect.className = 'hc-select';
      (types.types || []).forEach(function (item) {
        var option = document.createElement('option');
        option.value = item.value;
        option.textContent = bi(item.label, item.label_vi);
        typeSelect.appendChild(option);
      });
      if (options.presetType) typeSelect.value = options.presetType;
      labelled(_t('Consent type'), typeSelect);

      var methodSelect = document.createElement('select');
      methodSelect.className = 'hc-select';
      (types.methods || []).forEach(function (item) {
        var option = document.createElement('option');
        option.value = item.value;
        option.textContent = bi(item.label, item.label_vi);
        methodSelect.appendChild(option);
      });
      methodSelect.value = 'digital_signature';
      labelled(_t('Method'), methodSelect);

      var selfRow = document.createElement('label');
      selfRow.className = 'hc-row';
      var selfCheckbox = document.createElement('input');
      selfCheckbox.type = 'checkbox';
      selfCheckbox.checked = true;
      var selfText = document.createElement('span');
      selfText.textContent = _t('Granted by client');
      selfRow.appendChild(selfCheckbox);
      selfRow.appendChild(selfText);
      sheet.appendChild(selfRow);

      var grantorSelect = document.createElement('select');
      grantorSelect.className = 'hc-select';
      (consentData.relations || []).forEach(function (relation) {
        var option = document.createElement('option');
        option.value = relation.id;
        option.textContent = relation.representative_name
          + ' (' + relation.role
          + (relation.relationship_type
             ? ' / ' + relation.relationship_type : '') + ')';
        grantorSelect.appendChild(option);
      });
      var grantorLabel = document.createElement('div');
      grantorLabel.className = 'hc-label';
      grantorLabel.textContent = _t('Grantor');
      sheet.appendChild(grantorLabel);
      sheet.appendChild(grantorSelect);
      grantorLabel.style.display = 'none';
      grantorSelect.style.display = 'none';
      selfCheckbox.addEventListener('change', function () {
        var show = !selfCheckbox.checked;
        grantorLabel.style.display = show ? '' : 'none';
        grantorSelect.style.display = show ? '' : 'none';
      });

      var scopeInput = document.createElement('input');
      scopeInput.type = 'text';
      scopeInput.className = 'hc-input';
      labelled(_t('Scope / limitations'), scopeInput);

      var expiryInput = document.createElement('input');
      expiryInput.type = 'date';
      expiryInput.className = 'hc-input';
      labelled(_t('Expiry date (optional)'), expiryInput);

      var padContainer = document.createElement('div');
      sheet.appendChild(padContainer);
      var pad = buildSignaturePad(padContainer);
      function syncPad() {
        padContainer.style.display =
          methodSelect.value === 'digital_signature' ? '' : 'none';
      }
      methodSelect.addEventListener('change', syncPad);
      syncPad();

      var actions = document.createElement('div');
      actions.className = 'hc-actions';
      var cancelButton = document.createElement('button');
      cancelButton.type = 'button';
      cancelButton.className = 'hc-btn hc-btn--muted';
      cancelButton.textContent = _t('Cancel');
      cancelButton.addEventListener('click', function () {
        overlay.remove();
      });
      var saveButton = document.createElement('button');
      saveButton.type = 'button';
      saveButton.className = 'hc-btn';
      saveButton.textContent = _t('Save');
      saveButton.addEventListener('click', function () {
        var payload = {
          consent_type: typeSelect.value,
          method: methodSelect.value,
          self_granted: selfCheckbox.checked,
          scope_note: scopeInput.value || '',
          expiry_date: expiryInput.value || null,
        };
        if (!selfCheckbox.checked) {
          if (!grantorSelect.value) {
            notify(_t('Select a grantor relation'), 'error');
            return;
          }
          payload.granted_by_relation_id =
            parseInt(grantorSelect.value, 10);
        }
        if (methodSelect.value === 'digital_signature') {
          if (!pad.hasInk()) {
            notify(_t('Signature is required'), 'error');
            return;
          }
          payload.signature_base64 = pad.toBase64();
        }
        saveButton.disabled = true;
        service().createConsent(patientId, payload)
          .then(function (result) {
            overlay.remove();
            notify(result && result.queued
              ? _t('Saved offline — will sync when online')
              : _t('Consent granted'), 'success');
            if (options.onSaved) options.onSaved(result);
          })
          .catch(function (error) {
            saveButton.disabled = false;
            notify(_t('Error') + ': '
              + (error && error.message || error), 'error');
          });
      });
      actions.appendChild(cancelButton);
      actions.appendChild(saveButton);
      sheet.appendChild(actions);
    },
  };

  // ---------------------------------------------------------------
  // Consent list sheet (client screen)
  // ---------------------------------------------------------------
  var ConsentList = {
    open: function (patientId) {
      injectStyles();
      var api = service();
      if (!api) return;
      var overlay = document.createElement('div');
      overlay.className = 'hc-overlay';
      var sheet = document.createElement('div');
      sheet.className = 'hc-sheet';
      overlay.appendChild(sheet);
      overlay.addEventListener('click', function (event) {
        if (event.target === overlay) overlay.remove();
      });
      document.body.appendChild(overlay);

      api.getConsents(patientId).then(function (data) {
        var title = document.createElement('h3');
        title.className = 'hc-title';
        title.textContent = _t('Consents');
        sheet.appendChild(title);

        var chips = document.createElement('div');
        Object.keys(data.status || {}).forEach(function (type) {
          var chip = document.createElement('span');
          var granted = data.status[type];
          chip.className = 'hc-chip '
            + (granted ? 'hc-chip--ok' : 'hc-chip--missing');
          chip.textContent = type + ' — '
            + (granted ? _t('Active') : _t('Missing'));
          chips.appendChild(chip);
        });
        sheet.appendChild(chips);

        (data.consents || []).forEach(function (consent) {
          var row = document.createElement('div');
          row.className = 'hc-item';
          var info = document.createElement('div');
          var head = document.createElement('div');
          head.textContent = consent.name + ' · ' + consent.consent_type
            + ' · ' + consent.state;
          var meta = document.createElement('div');
          meta.className = 'hc-item__meta';
          var grantor = consent.granted_by === 'self'
            ? _t('self')
            : (consent.granted_by && consent.granted_by.name || '');
          meta.textContent = consent.method + ' · ' + grantor
            + (consent.effective_date
               ? ' · ' + consent.effective_date : '')
            + (consent.expiry_date ? ' → ' + consent.expiry_date : '');
          info.appendChild(head);
          info.appendChild(meta);
          row.appendChild(info);
          if (consent.state === 'active') {
            var withdrawButton = document.createElement('button');
            withdrawButton.type = 'button';
            withdrawButton.className = 'hc-link';
            withdrawButton.textContent = _t('Withdraw');
            withdrawButton.addEventListener('click', function () {
              var reason = window.prompt(_t('Withdrawal reason'));
              if (!reason) return;
              api.withdraw(consent.id, reason).then(function () {
                overlay.remove();
                ConsentList.open(patientId);
              }).catch(function (error) {
                notify(_t('Error') + ': '
                  + (error && error.message || error), 'error');
              });
            });
            row.appendChild(withdrawButton);
          }
          sheet.appendChild(row);
        });

        var actions = document.createElement('div');
        actions.className = 'hc-actions';
        var closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'hc-btn hc-btn--muted';
        closeButton.textContent = _t('Close');
        closeButton.addEventListener('click', function () {
          overlay.remove();
        });
        var newButton = document.createElement('button');
        newButton.type = 'button';
        newButton.className = 'hc-btn';
        newButton.textContent = _t('New consent');
        newButton.addEventListener('click', function () {
          overlay.remove();
          CaptureSheet.open(patientId, {
            onSaved: function () { ConsentList.open(patientId); },
          });
        });
        actions.appendChild(closeButton);
        actions.appendChild(newButton);
        sheet.appendChild(actions);
      }).catch(function (error) {
        overlay.remove();
        notify(_t('Error') + ': ' + (error && error.message || error),
               'error');
      });
    },
  };

  // ---------------------------------------------------------------
  // Visit-start banner (#/orders/<id>): non-blocking "Service consent
  // missing" + capture CTA (spec §6.7/§6.8) — never blocks the visit.
  // ---------------------------------------------------------------
  var banner = null;
  var dismissedOrders = {};
  var lastOrderId = null;

  function removeBanner() {
    if (banner) { banner.remove(); banner = null; }
  }

  function showBanner(orderId, patientId) {
    removeBanner();
    injectStyles();
    banner = document.createElement('div');
    banner.className = 'hc-banner';
    var text = document.createElement('div');
    text.className = 'hc-banner__text';
    text.textContent = _t('Service consent missing');
    var captureButton = document.createElement('button');
    captureButton.type = 'button';
    captureButton.className = 'hc-banner__btn';
    captureButton.textContent = _t('Capture now');
    captureButton.addEventListener('click', function () {
      CaptureSheet.open(patientId, {
        presetType: 'service',
        onSaved: function () { removeBanner(); },
      });
    });
    var closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'hc-banner__close';
    closeButton.textContent = '×';
    closeButton.setAttribute('aria-label', _t('Dismiss'));
    closeButton.addEventListener('click', function () {
      dismissedOrders[orderId] = true;
      removeBanner();
    });
    banner.appendChild(text);
    banner.appendChild(captureButton);
    banner.appendChild(closeButton);
    document.body.appendChild(banner);
  }

  function syncBanner() {
    var match = /#\/orders\/(\d+)/.exec(window.location.hash);
    if (!match) {
      lastOrderId = null;
      removeBanner();
      return;
    }
    var orderId = parseInt(match[1], 10);
    if (orderId === lastOrderId) return;
    lastOrderId = orderId;
    removeBanner();
    if (dismissedOrders[orderId]) return;
    var api = service();
    if (!api) return;
    api.orderPatientId(orderId).then(function (patientId) {
      if (!patientId || lastOrderId !== orderId) return null;
      return api.getStatus(patientId).then(function (status) {
        if (lastOrderId !== orderId) return;
        if (!status.service && !dismissedOrders[orderId]) {
          showBanner(orderId, patientId);
        }
      });
    }).catch(function (error) {
      // Never block or nag on network failure — soft touchpoint only.
      console.warn('[healthConsent] banner check failed', error);
    });
  }

  window.addEventListener('hashchange', syncBanner);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncBanner);
  } else {
    syncBanner();
  }

  window.healthConsentUI = {
    openCapture: function (patientId, options) {
      CaptureSheet.open(patientId, options);
    },
    openList: function (patientId) { ConsentList.open(patientId); },
    // §6.8.1 soft photography gate for the PWA photo flow: resolves
    // true when clinical photos may be captured; when false the
    // caller should show the consent capture CTA instead of the
    // camera. health_pwa is untouched — adoption happens there.
    checkPhotography: function (patientId) {
      var api = service();
      if (!api) return Promise.resolve(true);
      return api.canCapturePhoto(patientId);
    },
  };
})();
