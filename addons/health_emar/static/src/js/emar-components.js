// Health eMAR - per-visit medication checklist UI (spec §3.7).
//
// window.healthEmarComponents — plain-DOM overlay components (the
// health_pwa Vue app instance is module-local, same constraint as
// health_forms/health_evv). A docked "Medications" button appears on
// the visit screen (#/orders/<id>); it opens a bottom sheet listing
// the administrations due in the visit window with one-tap
// given / not-given-with-reason / refused-with-reason actions and a
// PRN "+ dose" section. Offline ticks are queued by emar-store.js.
//
// UI rules: flat mono colors only, no gradients, no emoji, no
// font-awesome (hard project conventions).

(function () {
  'use strict';

  var COLORS = {
    surface: '#ffffff',
    text: '#212121',
    muted: '#616161',
    primary: '#1565c0',
    success: '#2e7d32',
    danger: '#c62828',
    warning: '#ef6c00',
    border: '#e0e0e0',
  };

  var STATE_LABELS = {
    planned: ['Due', 'Đến giờ'],
    given: ['Given', 'Đã cho uống'],
    not_given: ['Not given', 'Không cho uống'],
    refused: ['Refused', 'Từ chối'],
    cancelled: ['Cancelled', 'Đã hủy'],
  };

  var STATE_COLORS = {
    planned: COLORS.primary,
    given: COLORS.success,
    not_given: COLORS.warning,
    refused: COLORS.danger,
    cancelled: COLORS.muted,
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
      if (translated && translated !== text) return translated;
    }
    return text;
  }

  function bi(en, vi) {
    return (isVietnamese() && vi) ? vi : (en || vi || '');
  }

  function stateLabel(state) {
    var pair = STATE_LABELS[state] || [state, state];
    return bi(pair[0], pair[1]);
  }

  function notify(message, type) {
    if (window.healthPWA && window.healthPWA.showNotification) {
      window.healthPWA.showNotification(message, type || 'info');
    } else {
      console.log('[healthEmar]', type || 'info', message);
    }
  }

  function localTime(iso) {
    if (!iso) return '';
    var date = new Date(iso.indexOf('Z') === -1 && iso.indexOf('+') === -1
      ? iso + 'Z' : iso);
    if (isNaN(date.getTime())) return iso;
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function injectStyles() {
    if (document.getElementById('he-pwa-styles')) return;
    var style = document.createElement('style');
    style.id = 'he-pwa-styles';
    style.textContent = [
      '.he-sheet{position:fixed;left:0;right:0;bottom:0;z-index:9500;',
      'background:', COLORS.surface, ';color:', COLORS.text, ';',
      'border-top:1px solid ', COLORS.border, ';padding:16px;',
      'box-shadow:0 -2px 8px rgba(0,0,0,0.15);max-height:75vh;overflow-y:auto;}',
      '.he-sheet h3{margin:0 0 12px;font-size:18px;}',
      '.he-row{padding:10px 0;border-bottom:1px solid ', COLORS.border, ';}',
      '.he-row__head{display:flex;justify-content:space-between;',
      'align-items:center;gap:8px;}',
      '.he-row__med{font-weight:600;}',
      '.he-row__meta{color:', COLORS.muted, ';font-size:13px;margin-top:2px;}',
      '.he-chip{color:#ffffff;border-radius:12px;padding:2px 12px;',
      'font-size:13px;white-space:nowrap;}',
      '.he-chip--pending{outline:1px dashed ', COLORS.muted, ';}',
      '.he-actions{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;}',
      '.he-btn{border:none;border-radius:6px;padding:10px 16px;',
      'font-size:14px;cursor:pointer;color:#ffffff;background:', COLORS.primary, ';}',
      '.he-btn--success{background:', COLORS.success, ';}',
      '.he-btn--warning{background:', COLORS.warning, ';}',
      '.he-btn--danger{background:', COLORS.danger, ';}',
      '.he-btn--muted{background:', COLORS.muted, ';}',
      '.he-btn--list{display:block;width:100%;text-align:left;margin:6px 0;',
      'background:', COLORS.surface, ';color:', COLORS.text, ';',
      'border:1px solid ', COLORS.border, ';}',
      '.he-section{font-weight:600;margin:14px 0 4px;}',
      '.he-note{width:100%;padding:8px;border:1px solid ', COLORS.border, ';',
      'border-radius:6px;margin-top:8px;background:', COLORS.surface, ';',
      'color:', COLORS.text, ';}',
      '.he-footer{display:flex;gap:10px;justify-content:flex-end;',
      'padding-top:12px;}',
      '.he-fab{position:fixed;right:16px;bottom:140px;z-index:9300;',
      'background:', COLORS.primary, ';color:#ffffff;border:none;',
      'border-radius:24px;padding:12px 18px;font-size:14px;',
      'box-shadow:0 2px 6px rgba(0,0,0,0.25);cursor:pointer;}',
      '.he-empty{color:', COLORS.muted, ';padding:8px 0;}',
    ].join('');
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------
  // Reason picker sheet (seeded not-given/refused reasons)
  // ---------------------------------------------------------------
  var ReasonPicker = {
    open: function (status, onPick) {
      injectStyles();
      var applies = status === 'refused' ? 'refused' : 'not_given';
      var reasons = (window.healthEmarStore.getReasons() || [])
        .filter(function (reason) {
          return reason.applies_to === applies
            || reason.applies_to === 'both';
        });
      var sheet = document.createElement('div');
      sheet.className = 'he-sheet';
      var title = document.createElement('h3');
      title.textContent = status === 'refused'
        ? bi('Why was it refused?', 'Lý do từ chối?')
        : bi('Why was it not given?', 'Lý do không cho uống?');
      sheet.appendChild(title);
      if (!reasons.length) {
        var empty = document.createElement('div');
        empty.className = 'he-empty';
        empty.textContent = _t('No reasons available — go online once to sync');
        sheet.appendChild(empty);
      }
      var note = document.createElement('textarea');
      note.className = 'he-note';
      note.rows = 2;
      note.placeholder = bi('Notes (optional)', 'Ghi chú (tùy chọn)');
      reasons.forEach(function (reason) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'he-btn he-btn--list';
        button.textContent = bi(reason.name, reason.name_vi);
        button.addEventListener('click', function () {
          var notes = note.value || '';
          sheet.remove();
          onPick(reason, notes);
        });
        sheet.appendChild(button);
      });
      sheet.appendChild(note);
      var footer = document.createElement('div');
      footer.className = 'he-footer';
      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'he-btn he-btn--muted';
      cancel.textContent = _t('Cancel');
      cancel.addEventListener('click', function () { sheet.remove(); });
      footer.appendChild(cancel);
      sheet.appendChild(footer);
      document.body.appendChild(sheet);
    },
  };

  // ---------------------------------------------------------------
  // Per-visit medication checklist sheet
  // ---------------------------------------------------------------
  var MedChecklist = {
    open: function (orderId) {
      injectStyles();
      var sheet = document.createElement('div');
      sheet.className = 'he-sheet';
      sheet.innerHTML = '<h3>' + bi('Medications', 'Thuốc') + '</h3>';
      document.body.appendChild(sheet);
      MedChecklist._load(sheet, orderId);
    },

    _load: function (sheet, orderId) {
      window.healthEmarStore.getFsoMedications(orderId)
        .then(function (data) {
          MedChecklist._render(sheet, orderId, data);
        })
        .catch(function (error) {
          sheet.remove();
          notify(_t('Error') + ': ' + (error && error.message || error),
            'error');
        });
    },

    _reload: function (sheet, orderId) {
      while (sheet.childNodes.length > 1) {
        sheet.removeChild(sheet.lastChild);
      }
      MedChecklist._load(sheet, orderId);
    },

    _render: function (sheet, orderId, data) {
      var administrations = data.administrations || [];
      if (!administrations.length) {
        var empty = document.createElement('div');
        empty.className = 'he-empty';
        empty.textContent = bi('No medications due this visit',
          'Không có thuốc trong lần thăm khám này');
        sheet.appendChild(empty);
      }
      administrations.forEach(function (admin) {
        sheet.appendChild(
          MedChecklist._renderRow(sheet, orderId, admin));
      });

      var prnOrders = data.prn_orders || [];
      if (prnOrders.length) {
        var section = document.createElement('div');
        section.className = 'he-section';
        section.textContent = bi('PRN / As needed', 'PRN / Khi cần');
        sheet.appendChild(section);
        prnOrders.forEach(function (order) {
          var button = document.createElement('button');
          button.type = 'button';
          button.className = 'he-btn he-btn--list';
          button.textContent = '+ '
            + bi(order.medication_name, order.medication_name_vi)
            + (order.dose ? ' — ' + order.dose : '')
            + (order.prn_reason ? ' (' + order.prn_reason + ')' : '');
          button.addEventListener('click', function () {
            button.disabled = true;
            window.healthEmarStore.createPrnDose(orderId, order.id)
              .then(function () {
                notify(bi('PRN dose added', 'Đã thêm liều PRN'), 'success');
                MedChecklist._reload(sheet, orderId);
              })
              .catch(function (error) {
                button.disabled = false;
                notify(_t('Error') + ': '
                  + (error && error.message || error), 'error');
              });
          });
          sheet.appendChild(button);
        });
      }

      var footer = document.createElement('div');
      footer.className = 'he-footer';
      var close = document.createElement('button');
      close.type = 'button';
      close.className = 'he-btn he-btn--muted';
      close.textContent = _t('Close');
      close.addEventListener('click', function () { sheet.remove(); });
      footer.appendChild(close);
      sheet.appendChild(footer);
    },

    _renderRow: function (sheet, orderId, admin) {
      var row = document.createElement('div');
      row.className = 'he-row';
      var head = document.createElement('div');
      head.className = 'he-row__head';
      var med = document.createElement('div');
      med.className = 'he-row__med';
      med.textContent = bi(admin.medication_name, admin.medication_name_vi);
      var chip = document.createElement('span');
      chip.className = 'he-chip'
        + (admin.pending_sync ? ' he-chip--pending' : '');
      chip.style.background = STATE_COLORS[admin.state] || COLORS.muted;
      chip.textContent = stateLabel(admin.state)
        + (admin.pending_sync
           ? ' · ' + bi('queued', 'chờ đồng bộ') : '');
      head.appendChild(med);
      head.appendChild(chip);
      row.appendChild(head);
      var meta = document.createElement('div');
      meta.className = 'he-row__meta';
      meta.textContent = [
        localTime(admin.planned_datetime),
        admin.dose,
        admin.route,
        admin.is_prn_dose ? 'PRN' : '',
      ].filter(Boolean).join(' · ');
      row.appendChild(meta);
      if (admin.instructions) {
        var instructions = document.createElement('div');
        instructions.className = 'he-row__meta';
        instructions.textContent = admin.instructions;
        row.appendChild(instructions);
      }
      if (admin.state === 'planned') {
        row.appendChild(
          MedChecklist._renderActions(sheet, orderId, admin));
      }
      return row;
    },

    _renderActions: function (sheet, orderId, admin) {
      var actions = document.createElement('div');
      actions.className = 'he-actions';

      function record(payload, doneMessage) {
        window.healthEmarStore.recordAdministration(admin.id, payload)
          .then(function (result) {
            notify(result.queued
              ? bi('Saved offline — will sync when online',
                   'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng')
              : doneMessage, result.queued ? 'info' : 'success');
            MedChecklist._reload(sheet, orderId);
          })
          .catch(function (error) {
            notify(_t('Error') + ': '
              + (error && error.message || error), 'error');
            MedChecklist._reload(sheet, orderId);
          });
      }

      var given = document.createElement('button');
      given.type = 'button';
      given.className = 'he-btn he-btn--success';
      given.textContent = bi('Given', 'Đã cho uống');
      given.addEventListener('click', function () {
        record({
          status: 'given',
          actual_datetime: new Date().toISOString(),
        }, bi('Dose recorded', 'Đã ghi nhận liều'));
      });
      actions.appendChild(given);

      var notGiven = document.createElement('button');
      notGiven.type = 'button';
      notGiven.className = 'he-btn he-btn--warning';
      notGiven.textContent = bi('Not given', 'Không cho uống');
      notGiven.addEventListener('click', function () {
        ReasonPicker.open('not_given', function (reason, notes) {
          record({
            status: 'not_given',
            reason_id: reason.id,
            notes: notes,
          }, bi('Recorded as not given', 'Đã ghi nhận không cho uống'));
        });
      });
      actions.appendChild(notGiven);

      var refused = document.createElement('button');
      refused.type = 'button';
      refused.className = 'he-btn he-btn--danger';
      refused.textContent = bi('Refused', 'Từ chối');
      refused.addEventListener('click', function () {
        ReasonPicker.open('refused', function (reason, notes) {
          record({
            status: 'refused',
            reason_id: reason.id,
            notes: notes,
          }, bi('Refusal recorded', 'Đã ghi nhận từ chối'));
        });
      });
      actions.appendChild(refused);

      return actions;
    },
  };

  // ---------------------------------------------------------------
  // Visit-screen docked button (#/orders/<id>) — sits above the
  // health_forms FAB (bottom:84px), never overlapping.
  // ---------------------------------------------------------------
  var fabButton = null;

  function syncFab() {
    var match = /#\/orders\/(\d+)/.exec(window.location.hash);
    if (!match) {
      if (fabButton) { fabButton.remove(); fabButton = null; }
      return;
    }
    var orderId = parseInt(match[1], 10);
    injectStyles();
    if (!fabButton) {
      fabButton = document.createElement('button');
      fabButton.type = 'button';
      fabButton.className = 'he-fab';
      document.body.appendChild(fabButton);
    }
    var queued = window.healthEmarStore.outboxSize();
    fabButton.textContent = bi('Medications', 'Thuốc')
      + (queued ? ' (' + queued + ')' : '');
    fabButton.onclick = function () { MedChecklist.open(orderId); };
  }

  window.addEventListener('hashchange', syncFab);
  window.addEventListener('online', function () {
    window.healthEmarStore.flushOutbox().then(function (flushed) {
      if (flushed) {
        notify(bi('Medication ticks synced', 'Đã đồng bộ thuốc'),
          'success');
      }
      syncFab();
    });
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncFab);
  } else {
    syncFab();
  }

  window.healthEmarComponents = {
    openChecklist: function (orderId) { MedChecklist.open(orderId); },
    openReasonPicker: function (status, onPick) {
      ReasonPicker.open(status, onPick);
    },
  };
})();
