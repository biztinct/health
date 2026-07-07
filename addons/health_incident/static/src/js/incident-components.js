// Health Incident - UI components (spec §5.7 PWA frontend)
//
// IncidentReportSheet — "Report Incident" quick-capture bottom sheet
//   on the visit screen (#/orders/<id>) and client screen
//   (#/patient/<id>): type picker, severity slider 1-5, what happened,
//   immediate action, optional photos (base64 → ir.attachment),
//   offline-queued with client_mutation_id. Incidents created from the
//   PWA start in 'reported'.
//
// NOTE: the health_pwa Vue app instance is module-local (app.js never
// exposes it), so these are plain-DOM components injected as overlays —
// same visual language, flat mono colors only (no gradients), CSS-mask
// SVG icons only (hf-wt-ico convention — never emoji / font-awesome).

(function () {
  'use strict';

  const VI = {
    'Report Incident': 'Báo cáo sự cố',
    'Incident type': 'Loại sự cố',
    'Severity': 'Mức độ nghiêm trọng',
    'What happened': 'Điều gì đã xảy ra',
    'Immediate action taken': 'Hành động xử lý ngay',
    'Photos (optional)': 'Ảnh (không bắt buộc)',
    'Submit': 'Gửi',
    'Cancel': 'Hủy',
    'Incident reported': 'Đã báo cáo sự cố',
    'Saved offline — will sync when online': 'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng',
    'Describe what happened': 'Mô tả điều đã xảy ra',
    'Select an incident type': 'Chọn loại sự cố',
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

  function optionLabel(option) {
    const isVietnamese = window.healthPWAConfig
      && window.healthPWAConfig.user_lang
      && window.healthPWAConfig.user_lang.indexOf('vi') === 0;
    return (isVietnamese && option.label_vi) ? option.label_vi : option.label;
  }

  function notify(message, kind) {
    if (window.healthPWA && window.healthPWA.showNotification) {
      window.healthPWA.showNotification(message, kind || 'info');
    } else {
      console.log('[Incident]', message);
    }
  }

  // Flat mono palette (hard convention: no gradients / dual-tone).
  const COLORS = {
    surface: '#ffffff',
    text: '#212121',
    muted: '#616161',
    primary: '#1565c0',
    danger: '#c62828',
    border: '#e0e0e0',
    field: '#f5f5f5',
  };

  // hf-wt-ico convention: CSS-mask SVG icon, mono flat color
  // (warning-triangle glyph).
  const ICON_ALERT_SVG = encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    + '<path fill="black" d="M12 2 1 21h22L12 2zm1 14h-2v2h2v-2zm0-7h-2v5'
    + 'h2V9z"/></svg>');

  function injectStyles() {
    if (document.getElementById('incident-styles')) return;
    const style = document.createElement('style');
    style.id = 'incident-styles';
    style.textContent = [
      '.incident-sheet{position:fixed;left:0;right:0;bottom:0;z-index:9410;',
      'background:' + COLORS.surface + ';color:' + COLORS.text + ';',
      'border-top:1px solid ' + COLORS.border + ';padding:16px;',
      'box-shadow:0 -2px 8px rgba(0,0,0,0.15);max-height:85vh;overflow-y:auto;}',
      '.incident-sheet h3{margin:0 0 12px;font-size:16px;}',
      '.incident-field{display:flex;flex-direction:column;gap:4px;margin-bottom:10px;}',
      '.incident-field label{font-size:12px;color:' + COLORS.muted + ';}',
      '.incident-field select,.incident-field textarea,.incident-field input[type=file]{',
      'padding:10px;border:1px solid ' + COLORS.border + ';border-radius:6px;',
      'background:' + COLORS.field + ';font-size:15px;color:' + COLORS.text + ';',
      'width:100%;box-sizing:border-box;}',
      '.incident-field textarea{min-height:64px;resize:vertical;}',
      '.incident-severity{display:flex;align-items:center;gap:10px;}',
      '.incident-severity input[type=range]{flex:1;accent-color:' + COLORS.primary + ';}',
      '.incident-severity .incident-severity-value{min-width:44px;text-align:center;',
      'font-weight:600;padding:6px 8px;border-radius:6px;',
      'background:' + COLORS.field + ';color:' + COLORS.text + ';}',
      '.incident-severity .incident-severity-value.incident-severe{',
      'background:' + COLORS.danger + ';color:#fff;}',
      '.incident-severity-label{font-size:12px;color:' + COLORS.muted + ';margin-top:2px;}',
      '.incident-actions{display:flex;gap:8px;margin-top:12px;}',
      '.incident-btn{flex:1;padding:12px;border:none;border-radius:6px;',
      'font-size:15px;font-weight:600;cursor:pointer;}',
      '.incident-btn--primary{background:' + COLORS.danger + ';color:#fff;}',
      '.incident-btn--muted{background:' + COLORS.field + ';color:' + COLORS.text + ';}',
      '.incident-error{margin-top:2px;font-size:11px;color:' + COLORS.danger + ';}',
      '.incident-fab{position:fixed;right:16px;bottom:144px;z-index:9300;',
      'width:52px;height:52px;border-radius:26px;border:none;cursor:pointer;',
      'background:' + COLORS.danger + ';box-shadow:0 2px 6px rgba(0,0,0,0.25);}',
      '.incident-fab .hf-wt-ico{display:block;width:26px;height:26px;margin:0 auto;',
      'background-color:#fff;-webkit-mask:url("data:image/svg+xml,' + ICON_ALERT_SVG + '") no-repeat center / contain;',
      'mask:url("data:image/svg+xml,' + ICON_ALERT_SVG + '") no-repeat center / contain;}',
    ].join('');
    document.head.appendChild(style);
  }

  function readFileAsBase64(file) {
    return new Promise(function (resolve, reject) {
      const reader = new FileReader();
      reader.onload = function () {
        const raw = String(reader.result || '');
        resolve(raw.indexOf(',') >= 0 ? raw.split(',')[1] : raw);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // ---------------------------------------------------------------
  // IncidentReportSheet
  // ---------------------------------------------------------------
  const IncidentReportSheet = {
    element: null,

    async open(context) {
      injectStyles();
      this.close();
      let refData;
      try {
        refData = await window.healthIncidentService.getTypes();
      } catch (error) {
        notify(_t('Error') + ': ' + error.message, 'error');
        return;
      }
      const sheet = document.createElement('div');
      sheet.className = 'incident-sheet';
      sheet.innerHTML = this._render(refData);
      document.body.appendChild(sheet);
      this.element = sheet;
      this._context = context || {};

      const slider = sheet.querySelector('.incident-severity input');
      slider.addEventListener('input', () => {
        this._syncSeverity(refData);
      });
      this._syncSeverity(refData);
      sheet.querySelector('.incident-cancel')
        .addEventListener('click', () => this.close());
      sheet.querySelector('.incident-submit')
        .addEventListener('click', () => this._submit());
    },

    close() {
      if (this.element) {
        this.element.remove();
        this.element = null;
      }
      this._context = {};
    },

    _render(refData) {
      let typeOptions = '<option value="">'
        + _t('Select an incident type') + '</option>';
      (refData.types || []).forEach(function (type) {
        typeOptions += '<option value="' + type.code + '">'
          + optionLabel(type) + '</option>';
      });
      return '<h3>' + _t('Report Incident') + '</h3>'
        + '<div class="incident-field">'
        + '<label>' + _t('Incident type') + '</label>'
        + '<select class="incident-type">' + typeOptions + '</select>'
        + '</div>'
        + '<div class="incident-field">'
        + '<label>' + _t('Severity') + '</label>'
        + '<div class="incident-severity">'
        + '<input type="range" min="1" max="5" step="1" value="2"/>'
        + '<span class="incident-severity-value">2</span>'
        + '</div>'
        + '<div class="incident-severity-label"></div>'
        + '</div>'
        + '<div class="incident-field">'
        + '<label>' + _t('What happened') + '</label>'
        + '<textarea class="incident-description" placeholder="'
        + _t('Describe what happened') + '"></textarea>'
        + '</div>'
        + '<div class="incident-field">'
        + '<label>' + _t('Immediate action taken') + '</label>'
        + '<textarea class="incident-immediate"></textarea>'
        + '</div>'
        + '<div class="incident-field">'
        + '<label>' + _t('Photos (optional)') + '</label>'
        + '<input type="file" class="incident-photos" accept="image/*"'
        + ' capture="environment" multiple/>'
        + '</div>'
        + '<div class="incident-actions">'
        + '<button type="button" class="incident-btn incident-btn--muted incident-cancel">'
        + _t('Cancel') + '</button>'
        + '<button type="button" class="incident-btn incident-btn--primary incident-submit">'
        + _t('Submit') + '</button>'
        + '</div>';
    },

    _syncSeverity(refData) {
      const sheet = this.element;
      if (!sheet) return;
      const slider = sheet.querySelector('.incident-severity input');
      const badge = sheet.querySelector('.incident-severity-value');
      const label = sheet.querySelector('.incident-severity-label');
      const value = slider.value;
      badge.textContent = value;
      badge.classList.toggle('incident-severe', Number(value) >= 4);
      const option = (refData.severities || []).filter(function (severity) {
        return severity.code === value;
      })[0];
      label.textContent = option ? optionLabel(option) : '';
    },

    async _submit() {
      const sheet = this.element;
      if (!sheet) return;
      const type = sheet.querySelector('.incident-type').value;
      const description = sheet
        .querySelector('.incident-description').value.trim();
      if (!type) {
        notify(_t('Select an incident type'), 'error');
        return;
      }
      if (!description) {
        notify(_t('Describe what happened'), 'error');
        return;
      }
      const payload = {
        incident_type: type,
        severity: sheet.querySelector('.incident-severity input').value,
        description: description,
        immediate_actions: sheet
          .querySelector('.incident-immediate').value.trim(),
        incident_datetime: new Date().toISOString()
          .replace(/\.\d{3}Z$/, 'Z'),
        photos: [],
      };
      if (this._context.orderId) payload.order_id = this._context.orderId;
      if (this._context.clientId) payload.client_id = this._context.clientId;

      const files = sheet.querySelector('.incident-photos').files;
      for (let i = 0; i < files.length; i++) {
        try {
          payload.photos.push({
            base64: await readFileAsBase64(files[i]),
            filename: files[i].name,
            mimetype: files[i].type || 'image/jpeg',
          });
        } catch (error) {
          console.warn('[Incident] photo read failed', error);
        }
      }

      const submit = sheet.querySelector('.incident-submit');
      submit.disabled = true;
      try {
        const result = await window.healthIncidentService
          .submitOrQueue(payload);
        if (result.queued) {
          notify(_t('Saved offline — will sync when online'), 'info');
        } else {
          notify(_t('Incident reported') + ': ' + result.name, 'success');
        }
        this.close();
      } catch (error) {
        submit.disabled = false;
        notify(_t('Error') + ': ' + error.message, 'error');
      }
    },
  };

  // ---------------------------------------------------------------
  // Wiring: report-incident action on the visit and client screens
  // ---------------------------------------------------------------
  function currentContext() {
    const orderMatch = window.location.hash.match(/#\/orders\/(\d+)/);
    if (orderMatch) return { orderId: parseInt(orderMatch[1], 10) };
    const patientMatch = window.location.hash.match(/#\/patient\/(\d+)/);
    if (patientMatch) return { clientId: parseInt(patientMatch[1], 10) };
    return null;
  }

  function syncFab() {
    const context = currentContext();
    let fab = document.getElementById('incident-fab');
    if (!context) {
      if (fab) fab.remove();
      IncidentReportSheet.close();
      return;
    }
    if (!fab) {
      injectStyles();
      fab = document.createElement('button');
      fab.id = 'incident-fab';
      fab.className = 'incident-fab';
      fab.type = 'button';
      fab.title = _t('Report Incident');
      fab.setAttribute('aria-label', _t('Report Incident'));
      fab.innerHTML = '<span class="hf-wt-ico"></span>';
      document.body.appendChild(fab);
    }
    fab.onclick = function () { IncidentReportSheet.open(context); };
  }

  window.addEventListener('hashchange', syncFab);
  document.addEventListener('DOMContentLoaded', syncFab);

  window.healthIncidents = {
    reportSheet: IncidentReportSheet,
    openReportSheet: function (context) {
      IncidentReportSheet.open(context || currentContext() || {});
    },
  };
})();
