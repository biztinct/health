// Health Careplan - UI components (spec §1.7 PWA frontend)
//
// CareTasksSheet — visit-screen checklist card: tick / not-done with
//                  a coded reason picker + optional note, PRN add.
//                  Opened from a docked button on #/orders/<id>
//                  (health_forms FAB wiring pattern).
//
// NOTE: the health_pwa Vue app instance is module-local (app.js never
// exposes it), so these are plain-DOM components injected as overlays —
// same visual language, flat mono colors only (no gradients), CSS-mask
// SVG icons only (hf-wt-ico convention — never emoji / font-awesome).

(function () {
  'use strict';

  var VI = {
    'Care Tasks': 'Nhiệm vụ chăm sóc',
    'No care-plan tasks for this visit': 'Không có nhiệm vụ chăm sóc cho lần khám này',
    'Done': 'Hoàn thành',
    'Not done': 'Không thực hiện',
    'Undo': 'Hoàn tác',
    'Close': 'Đóng',
    'Cancel': 'Hủy',
    'Save': 'Lưu',
    'Reason': 'Lý do',
    'Optional note': 'Ghi chú (tùy chọn)',
    'A reason is required': 'Cần chọn lý do',
    'Add as-needed task': 'Thêm nhiệm vụ khi cần',
    'Task updated': 'Đã cập nhật nhiệm vụ',
    'Saved offline — will sync when online': 'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng',
    'Client Refused': 'Khách hàng từ chối',
    'Client Unavailable/Asleep': 'Khách hàng vắng mặt/đang ngủ',
    'Withheld — Clinical Judgement': 'Tạm hoãn — đánh giá lâm sàng',
    'Missing Supplies/Equipment': 'Thiếu vật tư/thiết bị',
    'Ran Out of Time': 'Hết thời gian',
    'Other': 'Khác',
    'Error': 'Lỗi',
  };

  var NOT_DONE_REASONS = [
    ['client_refused', 'Client Refused'],
    ['client_unavailable', 'Client Unavailable/Asleep'],
    ['clinical_judgement', 'Withheld — Clinical Judgement'],
    ['no_supplies', 'Missing Supplies/Equipment'],
    ['out_of_time', 'Ran Out of Time'],
    ['other', 'Other'],
  ];

  function _t(text) {
    if (window.PWAUtils && window.PWAUtils.i18n
        && typeof window.PWAUtils.i18n.t === 'function') {
      var translated = window.PWAUtils.i18n.t(text);
      if (translated !== text) return translated;
    }
    var isVietnamese = window.healthPWAConfig
      && window.healthPWAConfig.user_lang
      && window.healthPWAConfig.user_lang.indexOf('vi') === 0;
    if (isVietnamese && VI[text]) return VI[text];
    return text;
  }

  function notify(message, kind) {
    if (window.healthPWA && window.healthPWA.showNotification) {
      window.healthPWA.showNotification(message, kind || 'info');
    } else {
      console.log('[Careplan]', message);
    }
  }

  // Flat mono palette (hard convention: no gradients / dual-tone).
  var COLORS = {
    surface: '#ffffff',
    text: '#212121',
    muted: '#616161',
    primary: '#1565c0',
    success: '#2e7d32',
    danger: '#c62828',
    border: '#e0e0e0',
    field: '#f5f5f5',
  };

  // hf-wt-ico convention: CSS-mask SVG icons, mono flat color.
  var ICON_CHECKLIST_SVG = encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    + '<path fill="black" d="M3 5h2v2H3zm4 0h14v2H7zM3 11h2v2H3zm4 0h14'
    + 'v2H7zM3 17h2v2H3zm4 0h14v2H7z"/></svg>');
  var ICON_CHECK_SVG = encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    + '<path fill="black" d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4'
    + '-1.4z"/></svg>');
  var ICON_CROSS_SVG = encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    + '<path fill="black" d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6'
    + ' 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>');

  function injectStyles() {
    if (document.getElementById('careplan-styles')) return;
    var style = document.createElement('style');
    style.id = 'careplan-styles';
    style.textContent = [
      '.hcp-sheet{position:fixed;left:0;right:0;bottom:0;z-index:9400;',
      'background:' + COLORS.surface + ';color:' + COLORS.text + ';',
      'border-top:1px solid ' + COLORS.border + ';padding:16px;',
      'box-shadow:0 -2px 8px rgba(0,0,0,0.15);max-height:80vh;overflow-y:auto;}',
      '.hcp-sheet h3{margin:0 0 12px;font-size:16px;}',
      '.hcp-task{display:flex;align-items:flex-start;gap:10px;',
      'padding:10px 0;border-bottom:1px solid ' + COLORS.border + ';}',
      '.hcp-task__body{flex:1;min-width:0;}',
      '.hcp-task__name{font-size:14px;font-weight:600;}',
      '.hcp-task__name--done{text-decoration:line-through;color:' + COLORS.muted + ';}',
      '.hcp-task__meta{font-size:12px;color:' + COLORS.muted + ';margin-top:2px;}',
      '.hcp-task__instr{font-size:12px;color:' + COLORS.muted + ';margin-top:4px;}',
      '.hcp-task__actions{display:flex;gap:6px;flex-shrink:0;}',
      '.hcp-ico-btn{width:38px;height:38px;border-radius:6px;border:1px solid '
      + COLORS.border + ';background:' + COLORS.field + ';cursor:pointer;}',
      '.hcp-ico-btn .hf-wt-ico{display:block;width:20px;height:20px;margin:0 auto;',
      'background-color:' + COLORS.muted + ';}',
      '.hcp-ico-btn--done{background:' + COLORS.success + ';border-color:'
      + COLORS.success + ';}',
      '.hcp-ico-btn--done .hf-wt-ico{background-color:#fff;}',
      '.hcp-ico-btn--notdone{background:' + COLORS.danger + ';border-color:'
      + COLORS.danger + ';}',
      '.hcp-ico-btn--notdone .hf-wt-ico{background-color:#fff;}',
      '.hcp-ico--check{-webkit-mask:url("data:image/svg+xml,' + ICON_CHECK_SVG
      + '") no-repeat center / contain;mask:url("data:image/svg+xml,'
      + ICON_CHECK_SVG + '") no-repeat center / contain;}',
      '.hcp-ico--cross{-webkit-mask:url("data:image/svg+xml,' + ICON_CROSS_SVG
      + '") no-repeat center / contain;mask:url("data:image/svg+xml,'
      + ICON_CROSS_SVG + '") no-repeat center / contain;}',
      '.hcp-ico--list{-webkit-mask:url("data:image/svg+xml,' + ICON_CHECKLIST_SVG
      + '") no-repeat center / contain;mask:url("data:image/svg+xml,'
      + ICON_CHECKLIST_SVG + '") no-repeat center / contain;}',
      '.hcp-reason{margin:8px 0;padding:10px;border:1px solid ' + COLORS.border + ';',
      'border-radius:6px;background:' + COLORS.field + ';}',
      '.hcp-reason label{display:block;font-size:12px;color:' + COLORS.muted + ';',
      'margin-bottom:4px;}',
      '.hcp-reason select,.hcp-reason input{width:100%;box-sizing:border-box;',
      'padding:8px;border:1px solid ' + COLORS.border + ';border-radius:6px;',
      'background:' + COLORS.surface + ';font-size:14px;color:' + COLORS.text + ';',
      'margin-bottom:6px;}',
      '.hcp-actions{display:flex;gap:8px;margin-top:12px;}',
      '.hcp-btn{flex:1;padding:12px;border:none;border-radius:6px;',
      'font-size:15px;font-weight:600;cursor:pointer;}',
      '.hcp-btn--primary{background:' + COLORS.primary + ';color:#fff;}',
      '.hcp-btn--danger{background:' + COLORS.danger + ';color:#fff;}',
      '.hcp-btn--muted{background:' + COLORS.field + ';color:' + COLORS.text + ';}',
      '.hcp-btn--list{display:block;width:100%;margin-bottom:6px;text-align:left;',
      'padding:10px;border:1px solid ' + COLORS.border + ';border-radius:6px;',
      'background:' + COLORS.surface + ';color:' + COLORS.text + ';font-size:14px;',
      'cursor:pointer;}',
      '.hcp-empty{padding:12px 0;font-size:13px;color:' + COLORS.muted + ';}',
      '.hcp-fab{position:fixed;right:16px;bottom:144px;z-index:9300;',
      'width:52px;height:52px;border-radius:26px;border:none;cursor:pointer;',
      'background:' + COLORS.success + ';box-shadow:0 2px 6px rgba(0,0,0,0.25);}',
      '.hcp-fab .hf-wt-ico{display:block;width:24px;height:24px;margin:0 auto;',
      'background-color:#fff;}',
      '.hcp-fab__count{position:absolute;top:-4px;right:-4px;min-width:20px;',
      'height:20px;border-radius:10px;background:' + COLORS.danger + ';color:#fff;',
      'font-size:11px;font-weight:700;line-height:20px;text-align:center;',
      'padding:0 4px;box-sizing:border-box;}',
    ].join('');
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------
  // CareTasksSheet
  // ---------------------------------------------------------------
  var CareTasksSheet = {
    element: null,
    fsoId: null,

    open: function (fsoId) {
      injectStyles();
      this.close();
      this.fsoId = fsoId;
      var sheet = document.createElement('div');
      sheet.className = 'hcp-sheet';
      sheet.innerHTML = '<h3>' + _t('Care Tasks') + '</h3>';
      document.body.appendChild(sheet);
      this.element = sheet;
      this._load();
    },

    close: function () {
      if (this.element) {
        this.element.remove();
        this.element = null;
        this.fsoId = null;
      }
    },

    _load: function () {
      var self = this;
      window.healthCareplanService.getFsoTasks(this.fsoId)
        .then(function (data) {
          if (!self.element) return;
          self._render(data);
        })
        .catch(function (error) {
          notify(_t('Error') + ': ' + error.message, 'error');
          self.close();
        });
    },

    _render: function (data) {
      var sheet = this.element;
      var self = this;
      sheet.innerHTML = '<h3>' + _t('Care Tasks')
        + (data.careplan
           ? ' — ' + (data.careplan.title || data.careplan.name) : '')
        + '</h3>';

      var tasks = data.tasks || [];
      if (!tasks.length) {
        var empty = document.createElement('div');
        empty.className = 'hcp-empty';
        empty.textContent = _t('No care-plan tasks for this visit');
        sheet.appendChild(empty);
      }
      tasks.forEach(function (task) {
        sheet.appendChild(self._taskRow(task));
      });

      (data.prn_activities || []).forEach(function (activity) {
        var already = tasks.some(function (task) {
          return task.activity_id === activity.id && task.is_prn;
        });
        if (already) return;
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'hcp-btn--list';
        button.textContent = _t('Add as-needed task') + ': ' + activity.name;
        button.addEventListener('click', function () {
          window.healthCareplanService.addPrnTask(self.fsoId, activity.id)
            .then(function () { self._load(); })
            .catch(function (error) {
              notify(_t('Error') + ': ' + error.message, 'error');
            });
        });
        sheet.appendChild(button);
      });

      var actions = document.createElement('div');
      actions.className = 'hcp-actions';
      var closeButton = document.createElement('button');
      closeButton.type = 'button';
      closeButton.className = 'hcp-btn hcp-btn--muted';
      closeButton.textContent = _t('Close');
      closeButton.addEventListener('click', function () { self.close(); });
      actions.appendChild(closeButton);
      sheet.appendChild(actions);
    },

    _taskRow: function (task) {
      var self = this;
      var row = document.createElement('div');
      row.className = 'hcp-task';

      var body = document.createElement('div');
      body.className = 'hcp-task__body';
      var name = document.createElement('div');
      name.className = 'hcp-task__name'
        + (task.state === 'done' ? ' hcp-task__name--done' : '');
      name.textContent = task.name + (task.is_prn ? ' (PRN)' : '');
      body.appendChild(name);
      if (task.state === 'not_done' && task.not_done_reason) {
        var meta = document.createElement('div');
        meta.className = 'hcp-task__meta';
        var reasonRow = NOT_DONE_REASONS.filter(function (pair) {
          return pair[0] === task.not_done_reason;
        })[0];
        meta.textContent = _t('Not done') + ': '
          + (reasonRow ? _t(reasonRow[1]) : task.not_done_reason)
          + (task.not_done_note ? ' — ' + task.not_done_note : '');
        body.appendChild(meta);
      }
      if (task.instructions) {
        var instructions = document.createElement('div');
        instructions.className = 'hcp-task__instr';
        // instructions is server-side HTML — render as text to stay
        // injection-safe in the overlay.
        var scratch = document.createElement('div');
        scratch.innerHTML = task.instructions;
        instructions.textContent = scratch.textContent.trim();
        body.appendChild(instructions);
      }
      row.appendChild(body);

      var actions = document.createElement('div');
      actions.className = 'hcp-task__actions';
      if (task.state === 'pending') {
        actions.appendChild(this._iconButton(
          'hcp-ico--check', _t('Done'), function () {
            self._tick(task, { state: 'done' });
          }));
        actions.appendChild(this._iconButton(
          'hcp-ico--cross', _t('Not done'), function () {
            self._openReasonPicker(task, row);
          }));
      } else {
        var stateButton = this._iconButton(
          task.state === 'done' ? 'hcp-ico--check' : 'hcp-ico--cross',
          _t('Undo'), function () {
            self._tick(task, { state: 'pending' });
          });
        stateButton.classList.add(task.state === 'done'
          ? 'hcp-ico-btn--done' : 'hcp-ico-btn--notdone');
        actions.appendChild(stateButton);
      }
      row.appendChild(actions);
      return row;
    },

    _iconButton: function (iconClass, label, onClick) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'hcp-ico-btn';
      button.title = label;
      button.setAttribute('aria-label', label);
      button.innerHTML = '<span class="hf-wt-ico ' + iconClass
        + '"></span>';
      button.addEventListener('click', onClick);
      return button;
    },

    _openReasonPicker: function (task, row) {
      var self = this;
      var existing = row.querySelector('.hcp-reason');
      if (existing) { existing.remove(); return; }
      var picker = document.createElement('div');
      picker.className = 'hcp-reason';
      var label = document.createElement('label');
      label.textContent = _t('Reason');
      picker.appendChild(label);
      var select = document.createElement('select');
      var placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = '—';
      select.appendChild(placeholder);
      NOT_DONE_REASONS.forEach(function (pair) {
        var option = document.createElement('option');
        option.value = pair[0];
        option.textContent = _t(pair[1]);
        select.appendChild(option);
      });
      picker.appendChild(select);
      var note = document.createElement('input');
      note.type = 'text';
      note.placeholder = _t('Optional note');
      picker.appendChild(note);
      var actions = document.createElement('div');
      actions.className = 'hcp-actions';
      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'hcp-btn hcp-btn--muted';
      cancel.textContent = _t('Cancel');
      cancel.addEventListener('click', function () { picker.remove(); });
      var save = document.createElement('button');
      save.type = 'button';
      save.className = 'hcp-btn hcp-btn--danger';
      save.textContent = _t('Save');
      save.addEventListener('click', function () {
        if (!select.value) {
          notify(_t('A reason is required'), 'warning');
          return;
        }
        self._tick(task, {
          state: 'not_done',
          not_done_reason: select.value,
          not_done_note: note.value.trim(),
        });
      });
      actions.appendChild(cancel);
      actions.appendChild(save);
      picker.appendChild(actions);
      row.appendChild(picker);
    },

    _tick: function (task, payload) {
      var self = this;
      window.healthCareplanService.updateOrQueue(task.id, payload)
        .then(function (result) {
          if (result.queued) {
            notify(_t('Saved offline — will sync when online'), 'info');
          } else {
            notify(_t('Task updated'), 'success');
          }
          syncFab();
          self._load();
        })
        .catch(function (error) {
          notify(_t('Error') + ': ' + error.message, 'error');
        });
    },
  };

  // ---------------------------------------------------------------
  // Wiring: docked button on the visit screen (#/orders/<id>),
  // stacked above the vitals FAB. Badge shows open task count.
  // ---------------------------------------------------------------
  function currentFsoId() {
    var match = window.location.hash.match(/#\/orders\/(\d+)/);
    return match ? parseInt(match[1], 10) : null;
  }

  function syncFab() {
    var fsoId = currentFsoId();
    var fab = document.getElementById('careplan-fab');
    if (!fsoId) {
      if (fab) fab.remove();
      CareTasksSheet.close();
      return;
    }
    injectStyles();
    if (!fab) {
      fab = document.createElement('button');
      fab.id = 'careplan-fab';
      fab.className = 'hcp-fab';
      fab.type = 'button';
      fab.title = _t('Care Tasks');
      fab.setAttribute('aria-label', _t('Care Tasks'));
      fab.innerHTML = '<span class="hf-wt-ico hcp-ico--list"></span>'
        + '<span class="hcp-fab__count" style="display:none"></span>';
      document.body.appendChild(fab);
    }
    fab.onclick = function () { CareTasksSheet.open(fsoId); };
    window.healthCareplanService.getFsoTasks(fsoId).then(function (data) {
      var current = document.getElementById('careplan-fab');
      if (!current) return;
      var tasks = data.tasks || [];
      if (!tasks.length && !(data.prn_activities || []).length) {
        current.remove();
        return;
      }
      var open = tasks.filter(function (task) {
        return task.state === 'pending';
      }).length;
      var badge = current.querySelector('.hcp-fab__count');
      if (badge) {
        badge.textContent = String(open);
        badge.style.display = open ? 'block' : 'none';
      }
    }).catch(function () { /* offline: keep the button */ });
  }

  window.addEventListener('hashchange', syncFab);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncFab);
  } else {
    syncFab();
  }

  window.healthCareplan = {
    tasksSheet: CareTasksSheet,
    openTasksSheet: function (fsoId) {
      CareTasksSheet.open(fsoId || currentFsoId());
    },
  };
})();
