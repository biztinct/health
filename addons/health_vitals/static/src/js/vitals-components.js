// Health Vitals - UI components (spec §2.7 PWA frontend)
//
// VitalsEntrySheet — bottom sheet on the visit screen: numeric entry
//                    for the standard vital set, BP as a paired field,
//                    plausible-range validation from the types cache,
//                    threshold breach shown as inline alert banner.
// VitalsSparkline  — inline-SVG trend rendering for the client screen
//                    (exposed as healthVitals.renderSparkline).
//
// NOTE: the health_pwa Vue app instance is module-local (app.js never
// exposes it), so these are plain-DOM components injected as overlays —
// same visual language, flat mono colors only (no gradients), CSS-mask
// SVG icons only (hf-wt-ico convention — never emoji / font-awesome).

(function () {
  'use strict';

  const VI = {
    'Vitals': 'Sinh hiệu',
    'Record Vitals': 'Ghi sinh hiệu',
    'Blood pressure': 'Huyết áp',
    'Systolic': 'Tâm thu',
    'Diastolic': 'Tâm trương',
    'Save': 'Lưu',
    'Cancel': 'Hủy',
    'Vitals saved': 'Đã lưu sinh hiệu',
    'Saved offline — will sync when online': 'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng',
    'Value outside plausible range': 'Giá trị ngoài phạm vi hợp lệ',
    'Enter at least one value': 'Nhập ít nhất một giá trị',
    'Enter both systolic and diastolic': 'Nhập cả tâm thu và tâm trương',
    'Threshold alert': 'Cảnh báo ngưỡng',
    'Error': 'Lỗi',
    'Ý thức (ACVPU)': 'Ý thức (ACVPU)',
    'Đang thở oxy': 'Đang thở oxy',
    'Lưu lượng (L/phút)': 'Lưu lượng (L/phút)',
    '(ý thức mặc định A)': '(ý thức mặc định A)',
  };

  // NEWS2 band labels (Vietnamese-first, matching the sheet).
  const BAND_LABELS = {
    low: 'Thấp',
    low_medium: 'Thấp-Trung bình',
    medium: 'Trung bình',
    high: 'Cao',
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

  function typeLabel(type) {
    const isVietnamese = window.healthPWAConfig
      && window.healthPWAConfig.user_lang
      && window.healthPWAConfig.user_lang.indexOf('vi') === 0;
    return (isVietnamese && type.name_vi) ? type.name_vi : type.name;
  }

  function notify(message, kind) {
    if (window.healthPWA && window.healthPWA.showNotification) {
      window.healthPWA.showNotification(message, kind || 'info');
    } else {
      console.log('[Vitals]', message);
    }
  }

  // Flat mono palette (hard convention: no gradients / dual-tone).
  const COLORS = {
    surface: '#ffffff',
    text: '#212121',
    muted: '#616161',
    primary: '#1565c0',
    success: '#2e7d32',
    warning: '#e65100',
    danger: '#c62828',
    border: '#e0e0e0',
    field: '#f5f5f5',
  };

  // hf-wt-ico convention: CSS-mask SVG icon, mono flat color.
  const ICON_PULSE_SVG = encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    + '<path fill="black" d="M3 11h4l2-5 4 12 3-7h5v2h-3.7l-4.1 9.6'
    + 'L9.1 10.4 8.3 13H3z"/></svg>');

  // Default PWA entry set (spec §2.9: spo2_po is the field default).
  const ENTRY_CODES = ['hr', 'rr', 'temp', 'spo2_po', 'weight', 'pain'];

  function injectStyles() {
    if (document.getElementById('vitals-styles')) return;
    const style = document.createElement('style');
    style.id = 'vitals-styles';
    style.textContent = [
      '.vitals-sheet{position:fixed;left:0;right:0;bottom:0;z-index:9400;',
      'background:' + COLORS.surface + ';color:' + COLORS.text + ';',
      'border-top:1px solid ' + COLORS.border + ';padding:16px;',
      'box-shadow:0 -2px 8px rgba(0,0,0,0.15);max-height:80vh;overflow-y:auto;}',
      '.vitals-sheet h3{margin:0 0 12px;font-size:16px;}',
      '.vitals-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}',
      '.vitals-field{display:flex;flex-direction:column;gap:2px;}',
      '.vitals-field label{font-size:12px;color:' + COLORS.muted + ';}',
      '.vitals-field .vitals-unit{font-size:11px;color:' + COLORS.muted + ';}',
      '.vitals-field input{padding:10px;border:1px solid ' + COLORS.border + ';',
      'border-radius:6px;background:' + COLORS.field + ';font-size:16px;',
      'color:' + COLORS.text + ';width:100%;box-sizing:border-box;}',
      '.vitals-field input.vitals-invalid{border-color:' + COLORS.danger + ';}',
      '.vitals-bp{grid-column:1 / -1;display:flex;gap:8px;align-items:flex-end;}',
      '.vitals-bp .vitals-field{flex:1;}',
      '.vitals-actions{display:flex;gap:8px;margin-top:12px;}',
      '.vitals-btn{flex:1;padding:12px;border:none;border-radius:6px;',
      'font-size:15px;font-weight:600;cursor:pointer;}',
      '.vitals-btn--primary{background:' + COLORS.primary + ';color:#fff;}',
      '.vitals-btn--muted{background:' + COLORS.field + ';color:' + COLORS.text + ';}',
      '.vitals-alert{margin-top:10px;padding:10px;border-radius:6px;',
      'font-size:13px;color:#fff;}',
      '.vitals-alert--warning{background:' + COLORS.warning + ';}',
      '.vitals-alert--critical{background:' + COLORS.danger + ';}',
      '.vitals-error{margin-top:2px;font-size:11px;color:' + COLORS.danger + ';}',
      '.vitals-fab{position:fixed;right:16px;bottom:84px;z-index:9300;',
      'width:52px;height:52px;border-radius:26px;border:none;cursor:pointer;',
      'background:' + COLORS.primary + ';box-shadow:0 2px 6px rgba(0,0,0,0.25);}',
      '.vitals-fab .hf-wt-ico{display:block;width:26px;height:26px;margin:0 auto;',
      'background-color:#fff;-webkit-mask:url("data:image/svg+xml,' + ICON_PULSE_SVG + '") no-repeat center / contain;',
      'mask:url("data:image/svg+xml,' + ICON_PULSE_SVG + '") no-repeat center / contain;}',
      '.vitals-spark{display:block;width:100%;height:48px;}',
      '.vitals-spark polyline{fill:none;stroke:' + COLORS.primary + ';stroke-width:2;}',
      '.vitals-spark circle{fill:' + COLORS.primary + ';}',
      // ACVPU segmented row + O2 toggle (telemonitoring).
      '.vitals-seg{grid-column:1 / -1;display:flex;flex-direction:column;gap:4px;}',
      '.vitals-seg > label{font-size:12px;color:' + COLORS.muted + ';}',
      '.vitals-seg-row{display:flex;gap:6px;}',
      '.vitals-seg-btn{flex:1;padding:10px;border:1px solid ' + COLORS.border + ';',
      'border-radius:6px;background:' + COLORS.field + ';color:' + COLORS.text + ';',
      'font-size:15px;font-weight:600;cursor:pointer;}',
      '.vitals-seg-btn.vitals-seg-on{background:' + COLORS.primary + ';color:#fff;',
      'border-color:' + COLORS.primary + ';}',
      '.vitals-o2{grid-column:1 / -1;display:flex;flex-direction:column;gap:6px;}',
      '.vitals-o2-toggle{display:flex;align-items:center;gap:8px;font-size:14px;',
      'color:' + COLORS.text + ';}',
      '.vitals-o2-flow{display:none;}',
      '.vitals-o2-flow.vitals-o2-flow-on{display:flex;}',
      // NEWS2 band chip (flat mono, one color per band).
      '.vitals-news2{margin-top:10px;padding:10px 12px;border-radius:6px;',
      'font-size:14px;font-weight:700;color:#fff;}',
      '.vitals-news2--low{background:' + COLORS.success + ';}',
      '.vitals-news2--low_medium{background:#f9a825;}',
      '.vitals-news2--medium{background:' + COLORS.warning + ';}',
      '.vitals-news2--high{background:' + COLORS.danger + ';}',
    ].join('');
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------
  // VitalsEntrySheet
  // ---------------------------------------------------------------
  const VitalsEntrySheet = {
    element: null,

    async open(fsoId) {
      injectStyles();
      this.close();
      let types;
      try {
        types = await window.healthVitalsService.getTypes();
      } catch (error) {
        notify(_t('Error') + ': ' + error.message, 'error');
        return;
      }
      const sheet = document.createElement('div');
      sheet.className = 'vitals-sheet';
      sheet.innerHTML = this._render(types);
      document.body.appendChild(sheet);
      this.element = sheet;

      sheet.querySelector('.vitals-cancel')
        .addEventListener('click', () => this.close());
      sheet.querySelector('.vitals-save')
        .addEventListener('click', () => this._save(fsoId, types));
      sheet.querySelectorAll('input').forEach((input) => {
        input.addEventListener('input', () => {
          input.classList.remove('vitals-invalid');
          const err = input.parentElement.querySelector('.vitals-error');
          if (err) err.remove();
        });
      });
      // ACVPU segmented picker — single-select, re-click clears.
      sheet.querySelectorAll('[data-acvpu]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const wasOn = btn.classList.contains('vitals-seg-on');
          sheet.querySelectorAll('[data-acvpu]').forEach((b) =>
            b.classList.remove('vitals-seg-on'));
          if (!wasOn) btn.classList.add('vitals-seg-on');
        });
      });
      // O2 toggle reveals the flow input.
      const o2Toggle = sheet.querySelector('[data-o2-toggle]');
      if (o2Toggle) {
        o2Toggle.addEventListener('change', () => {
          const wrap = sheet.querySelector('[data-o2-flow-wrap]');
          if (wrap) {
            wrap.classList.toggle('vitals-o2-flow-on', o2Toggle.checked);
          }
        });
      }
    },

    close() {
      if (this.element) {
        this.element.remove();
        this.element = null;
      }
    },

    _fieldHtml(type, code) {
      const range = (type.plausible_min || type.plausible_max)
        ? ' (' + type.plausible_min + '–' + type.plausible_max + ')' : '';
      const step = type.decimals > 0
        ? String(Math.pow(10, -type.decimals)) : '1';
      return '<div class="vitals-field">'
        + '<label>' + typeLabel(type)
        + ' <span class="vitals-unit">' + (type.unit_display || '')
        + range + '</span></label>'
        + '<input type="number" inputmode="decimal" step="' + step
        + '" data-code="' + code + '"/>'
        + '</div>';
    },

    _render(types) {
      const bpSys = window.healthVitalsService.getTypeByCode(types, 'bp_sys');
      const bpDia = window.healthVitalsService.getTypeByCode(types, 'bp_dia');
      let html = '<h3>' + _t('Record Vitals') + '</h3>'
        + '<div class="vitals-grid">';
      if (bpSys && bpDia) {
        html += '<div class="vitals-bp">'
          + this._fieldHtml(bpSys, 'bp_sys')
          + this._fieldHtml(bpDia, 'bp_dia')
          + '</div>';
      }
      ENTRY_CODES.forEach((code) => {
        const type = window.healthVitalsService.getTypeByCode(types, code);
        if (type) html += this._fieldHtml(type, code);
      });
      // Telemonitoring controls — rendered only when the catalog carries
      // the codes (graceful when health_telemonitoring is not installed).
      const acvpuType =
        window.healthVitalsService.getTypeByCode(types, 'acvpu');
      if (acvpuType) {
        html += '<div class="vitals-seg">'
          + '<label>' + _t('Ý thức (ACVPU)') + '</label>'
          + '<div class="vitals-seg-row">'
          + ['A', 'C', 'V', 'P', 'U'].map((letter) =>
            '<button type="button" class="vitals-seg-btn" data-acvpu="'
            + letter + '">' + letter + '</button>').join('')
          + '</div></div>';
      }
      const o2Type =
        window.healthVitalsService.getTypeByCode(types, 'o2_flow');
      if (o2Type) {
        html += '<div class="vitals-o2">'
          + '<label class="vitals-o2-toggle">'
          + '<input type="checkbox" data-o2-toggle="1"/> '
          + _t('Đang thở oxy') + '</label>'
          + '<div class="vitals-field vitals-o2-flow" data-o2-flow-wrap="1">'
          + '<label>' + _t('Lưu lượng (L/phút)') + '</label>'
          + '<input type="number" inputmode="decimal" step="0.5" min="0.5"'
          + ' max="60" value="2" data-o2-flow="1"/>'
          + '</div></div>';
      }
      html += '</div>'
        + '<div class="vitals-alerts"></div>'
        + '<div class="vitals-actions">'
        + '<button type="button" class="vitals-btn vitals-btn--muted vitals-cancel">'
        + _t('Cancel') + '</button>'
        + '<button type="button" class="vitals-btn vitals-btn--primary vitals-save">'
        + _t('Save') + '</button>'
        + '</div>';
      return html;
    },

    _markInvalid(input, message) {
      input.classList.add('vitals-invalid');
      const error = document.createElement('div');
      error.className = 'vitals-error';
      error.textContent = message;
      input.parentElement.appendChild(error);
    },

    async _save(fsoId, types) {
      const sheet = this.element;
      if (!sheet) return;
      const service = window.healthVitalsService;
      const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
      const payload = { observations: [], bp: null };
      let hasInvalid = false;
      let sysValue = null;
      let diaValue = null;

      sheet.querySelectorAll('input[data-code]').forEach((input) => {
        const code = input.getAttribute('data-code');
        const raw = input.value.trim();
        if (raw === '') return;
        const type = service.getTypeByCode(types, code);
        const problem = service.validateValue(type, raw);
        if (problem) {
          hasInvalid = true;
          this._markInvalid(input, _t('Value outside plausible range'));
          return;
        }
        if (code === 'bp_sys') { sysValue = Number(raw); return; }
        if (code === 'bp_dia') { diaValue = Number(raw); return; }
        payload.observations.push({
          code: code,
          value: Number(raw),
          effective_datetime: now,
        });
      });

      // ACVPU (optional — untouched sends nothing).
      const acvpuBtn = sheet.querySelector('[data-acvpu].vitals-seg-on');
      if (acvpuBtn) {
        payload.observations.push({
          code: 'acvpu',
          value: acvpuBtn.getAttribute('data-acvpu'),
          effective_datetime: now,
        });
      }
      // Supplemental O2 (optional — only when the toggle is on).
      const o2Toggle = sheet.querySelector('[data-o2-toggle]');
      if (o2Toggle && o2Toggle.checked) {
        const flowInput = sheet.querySelector('[data-o2-flow]');
        const flow = flowInput ? Number(flowInput.value) : NaN;
        if (isNaN(flow) || flow <= 0 || flow > 60) {
          hasInvalid = true;
          if (flowInput) {
            this._markInvalid(flowInput, _t('Value outside plausible range'));
          }
        } else {
          payload.observations.push({
            code: 'o2_flow',
            value: flow,
            effective_datetime: now,
          });
        }
      }
      if (hasInvalid) return;

      if (sysValue !== null || diaValue !== null) {
        if (sysValue === null || diaValue === null) {
          notify(_t('Enter both systolic and diastolic'), 'error');
          return;
        }
        payload.bp = {
          systolic: sysValue,
          diastolic: diaValue,
          effective_datetime: now,
        };
      }
      if (!payload.observations.length && !payload.bp) {
        notify(_t('Enter at least one value'), 'error');
        return;
      }

      try {
        const result = await service.submitOrQueue(fsoId, payload);
        if (result.queued) {
          notify(_t('Saved offline — will sync when online'), 'info');
          this.close();
          return;
        }
        const ews = result.ews;
        const alerts = result.alerts || [];
        const hasEws = ews
          && ews.total !== null && ews.total !== undefined;
        if (hasEws || alerts.length) {
          this._showResult(ews, alerts);
          notify(_t('Vitals saved'), 'success');
          return; // keep the sheet open so the NEWS2/alert banner is seen
        }
        notify(_t('Vitals saved'), 'success');
        this.close();
      } catch (error) {
        notify(_t('Error') + ': ' + error.message, 'error');
      }
    },

    _showResult(ews, alerts) {
      const container = this.element
        && this.element.querySelector('.vitals-alerts');
      if (!container) return;
      container.innerHTML = '';
      // NEWS2 band chip ABOVE any threshold alert.
      if (ews && ews.total !== null && ews.total !== undefined) {
        const chip = document.createElement('div');
        chip.className = 'vitals-news2 vitals-news2--' + (ews.band || 'low');
        let text = 'NEWS2: ' + ews.total + ' — '
          + (BAND_LABELS[ews.band] || ews.band || '');
        if (ews.defaulted_consciousness) {
          text += ' ' + _t('(ý thức mặc định A)');
        }
        chip.textContent = text;
        container.appendChild(chip);
      }
      (alerts || []).forEach((alert) => {
        const banner = document.createElement('div');
        banner.className = 'vitals-alert vitals-alert--'
          + (alert.alert_level === 'critical' ? 'critical' : 'warning');
        banner.textContent = _t('Threshold alert') + ': ' + alert.message;
        container.appendChild(banner);
      });
      const save = this.element.querySelector('.vitals-save');
      if (save) save.remove();
      const cancel = this.element.querySelector('.vitals-cancel');
      if (cancel) cancel.textContent = _t('Vitals') + ' — OK';
    },
  };

  // ---------------------------------------------------------------
  // VitalsSparkline — inline SVG trend (client screen)
  // ---------------------------------------------------------------
  function renderSparkline(container, points) {
    injectStyles();
    if (!points || !points.length) {
      container.innerHTML = '';
      return;
    }
    const width = 200;
    const height = 48;
    const pad = 4;
    const values = points.map(function (point) { return point.v; });
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const span = (max - min) || 1;
    const coords = points.map(function (point, index) {
      const x = pad + (index * (width - 2 * pad))
        / Math.max(points.length - 1, 1);
      const y = height - pad - ((point.v - min) / span) * (height - 2 * pad);
      return x.toFixed(1) + ',' + y.toFixed(1);
    });
    const last = coords[coords.length - 1].split(',');
    container.innerHTML = '<svg class="vitals-spark" viewBox="0 0 '
      + width + ' ' + height + '" preserveAspectRatio="none">'
      + '<polyline points="' + coords.join(' ') + '"/>'
      + '<circle cx="' + last[0] + '" cy="' + last[1] + '" r="2.5"/>'
      + '</svg>';
  }

  async function renderTrend(container, patientId, typeCode, days) {
    try {
      const data = await window.healthVitalsService.getTrend(
        patientId, typeCode, days);
      renderSparkline(container, data.points);
      return data;
    } catch (error) {
      console.warn('[Vitals] trend load failed', error);
      return null;
    }
  }

  // ---------------------------------------------------------------
  // Wiring: floating action button on the visit screen
  // ---------------------------------------------------------------
  function currentFsoId() {
    const match = window.location.hash.match(/#\/orders\/(\d+)/);
    return match ? parseInt(match[1], 10) : null;
  }

  function syncFab() {
    const fsoId = currentFsoId();
    let fab = document.getElementById('vitals-fab');
    if (!fsoId) {
      if (fab) fab.remove();
      VitalsEntrySheet.close();
      return;
    }
    if (!fab) {
      injectStyles();
      fab = document.createElement('button');
      fab.id = 'vitals-fab';
      fab.className = 'vitals-fab';
      fab.type = 'button';
      fab.title = _t('Record Vitals');
      fab.setAttribute('aria-label', _t('Record Vitals'));
      fab.innerHTML = '<span class="hf-wt-ico"></span>';
      document.body.appendChild(fab);
    }
    fab.onclick = function () { VitalsEntrySheet.open(fsoId); };
  }

  window.addEventListener('hashchange', syncFab);
  document.addEventListener('DOMContentLoaded', syncFab);

  window.healthVitals = {
    entrySheet: VitalsEntrySheet,
    openEntrySheet: function (fsoId) {
      VitalsEntrySheet.open(fsoId || currentFsoId());
    },
    renderSparkline: renderSparkline,
    renderTrend: renderTrend,
  };
})();
