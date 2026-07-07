// Health Forms - PWA form runner (spec §4.5 / §4.8).
//
// window.healthFormsRunner — plain-DOM overlay components (the
// health_pwa Vue app instance is module-local, same constraint as
// health_evv), same visual language, flat mono colors only:
//   openPicker(orderId) — bottom sheet listing applicable templates and
//                         completed instances for the visit.
//   openForm(orderId, schema) — full-screen runner rendering the §4.2
//                         schema: number/selection/multiselect/text/
//                         boolean/date/photo/signature/computed_score,
//                         visible_if evaluation and a live score footer.
//
// Signature: inline pointer-events canvas (the health_evv pad is
// hard-wired to the EVV signature endpoint, so it is not reusable for
// arbitrary answers; feature parity is kept with a minimal local pad).
// Photos: <input type="file" capture> read as base64 — the submit
// payload carries {"base64", "filename"} and the server rewrites it to
// {"attachment_id"}.
//
// An "Assessments" docked button is injected on visit screens
// (#/orders/<id>) via hashchange, mirroring the EVV chip wiring.

(function () {
  'use strict';

  var VI = {
    'Assessments': 'Đánh giá',
    'New assessment': 'Đánh giá mới',
    'Completed this visit': 'Đã hoàn thành trong lần khám này',
    'No forms apply to this visit': 'Không có biểu mẫu cho lần khám này',
    'Close': 'Đóng',
    'Submit': 'Gửi',
    'Cancel': 'Hủy',
    'Clear': 'Xóa',
    'Required questions are missing': 'Còn câu hỏi bắt buộc chưa trả lời',
    'Value out of range': 'Giá trị ngoài khoảng cho phép',
    'Total score': 'Tổng điểm',
    'Saved offline — will sync when online':
      'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng',
    'Assessment saved': 'Đã lưu đánh giá',
    'Take photo': 'Chụp ảnh',
    'Sign here': 'Ký tại đây',
    'Error': 'Lỗi',
    'Yes': 'Có',
    'No': 'Không',
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
      console.log('[healthForms]', message);
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
  };

  function injectStyles() {
    if (document.getElementById('hf-pwa-styles')) return;
    var style = document.createElement('style');
    style.id = 'hf-pwa-styles';
    style.textContent = [
      '.hf-sheet{position:fixed;left:0;right:0;bottom:0;z-index:9400;',
      'background:', COLORS.surface, ';color:', COLORS.text, ';',
      'border-top:1px solid ', COLORS.border, ';padding:16px;',
      'box-shadow:0 -2px 8px rgba(0,0,0,0.15);max-height:70vh;overflow-y:auto;}',
      '.hf-overlay{position:fixed;inset:0;z-index:9450;',
      'background:rgba(0,0,0,0.45);display:flex;align-items:flex-end;}',
      '.hf-runner{background:', COLORS.surface, ';color:', COLORS.text, ';',
      'width:100%;max-height:92vh;overflow-y:auto;padding:16px;',
      'border-radius:12px 12px 0 0;}',
      '.hf-runner h3{margin:0 0 12px;font-size:18px;}',
      '.hf-q{padding:10px 0;border-bottom:1px solid ', COLORS.border, ';}',
      '.hf-q__label{font-weight:600;margin-bottom:6px;}',
      '.hf-q__req{color:', COLORS.danger, ';margin-left:2px;}',
      '.hf-q__help{color:', COLORS.muted, ';font-size:12px;margin-bottom:6px;}',
      '.hf-q input[type=number],.hf-q input[type=date],.hf-q textarea{',
      'width:100%;padding:8px;border:1px solid ', COLORS.border, ';',
      'border-radius:6px;background:', COLORS.surface, ';color:', COLORS.text, ';}',
      '.hf-opt{display:flex;align-items:center;gap:8px;padding:6px 0;}',
      '.hf-btn{border:none;border-radius:6px;padding:10px 18px;',
      'font-size:15px;cursor:pointer;color:#ffffff;background:', COLORS.primary, ';}',
      '.hf-btn--muted{background:', COLORS.muted, ';}',
      '.hf-btn--success{background:', COLORS.success, ';}',
      '.hf-btn--list{display:block;width:100%;text-align:left;margin:6px 0;',
      'background:', COLORS.surface, ';color:', COLORS.text, ';',
      'border:1px solid ', COLORS.border, ';}',
      '.hf-actions{display:flex;gap:10px;justify-content:flex-end;',
      'padding-top:12px;}',
      '.hf-footer{display:flex;align-items:center;gap:10px;',
      'padding:10px 0;border-top:2px solid ', COLORS.text, ';margin-top:8px;}',
      '.hf-footer__total{font-size:20px;font-weight:700;}',
      '.hf-chip{color:#ffffff;border-radius:12px;padding:2px 12px;font-size:13px;}',
      '.hf-fab{position:fixed;right:16px;bottom:84px;z-index:9300;',
      'background:', COLORS.primary, ';color:#ffffff;border:none;',
      'border-radius:24px;padding:12px 18px;font-size:14px;',
      'box-shadow:0 2px 6px rgba(0,0,0,0.25);cursor:pointer;}',
      '.hf-canvas{width:100%;height:160px;border:1px dashed ', COLORS.border, ';',
      'border-radius:6px;touch-action:none;background:', COLORS.surface, ';}',
      '.hf-photo-preview{max-width:100%;max-height:160px;display:block;',
      'margin-top:6px;border:1px solid ', COLORS.border, ';border-radius:6px;}',
      '.hf-instance{display:flex;justify-content:space-between;',
      'padding:6px 0;color:', COLORS.muted, ';font-size:13px;}',
    ].join('');
    document.head.appendChild(style);
  }

  // ---------------------------------------------------------------
  // §4.2 contract evaluation (mirrors the Python and OWL renderers)
  // ---------------------------------------------------------------
  function isVisible(question, answers) {
    var condition = question.visible_if;
    if (!condition) return true;
    var answer = answers[condition.key];
    var value = condition.value;
    switch (condition.operator || '=') {
      case '=': return answer === value;
      case '!=': return answer !== value;
      case 'in':
        if (Array.isArray(answer)) {
          return Array.isArray(value)
            ? answer.some(function (a) { return value.indexOf(a) >= 0; })
            : answer.indexOf(value) >= 0;
        }
        return Array.isArray(value)
          ? value.indexOf(answer) >= 0 : answer === value;
      case '>=':
        return answer != null && parseFloat(answer) >= parseFloat(value);
      case '<=':
        return answer != null && parseFloat(answer) <= parseFloat(value);
      default: return true;
    }
  }

  function contribution(question, answers) {
    var answer = answers[question.key];
    var options = question.options || [];
    if (answer == null) return 0;
    switch (question.type) {
      case 'number': {
        var weight = question.score_weight || 0;
        var value = parseFloat(answer);
        return (weight > 0 && !isNaN(value)) ? value * weight : 0;
      }
      case 'selection': {
        var opt = options.filter(function (o) {
          return o.value === answer;
        })[0];
        return opt && opt.score != null ? opt.score : 0;
      }
      case 'multiselect': {
        if (!Array.isArray(answer)) return 0;
        return options.reduce(function (sum, o) {
          return answer.indexOf(o.value) >= 0 ? sum + (o.score || 0) : sum;
        }, 0);
      }
      case 'boolean': {
        var key = answer ? 'true' : 'false';
        var bopt = options.filter(function (o) {
          return String(o.value).toLowerCase() === key;
        })[0];
        return bopt && bopt.score != null ? bopt.score : 0;
      }
      default: return 0;
    }
  }

  function totalScore(schema, answers) {
    return (schema.questions || []).reduce(function (sum, question) {
      return isVisible(question, answers)
        ? sum + contribution(question, answers) : sum;
    }, 0);
  }

  function resolveBand(schema, total) {
    var bands = (schema.scoring && schema.scoring.bands) || [];
    for (var i = 0; i < bands.length; i += 1) {
      var min = bands[i].min == null ? -Infinity : bands[i].min;
      var max = bands[i].max == null ? Infinity : bands[i].max;
      if (total >= min && total <= max) return bands[i];
    }
    return null;
  }

  // ---------------------------------------------------------------
  // Question widgets (plain DOM)
  // ---------------------------------------------------------------
  function buildQuestion(question, answers, rerender) {
    var wrap = document.createElement('div');
    wrap.className = 'hf-q';
    wrap.dataset.key = question.key;

    var label = document.createElement('div');
    label.className = 'hf-q__label';
    label.textContent = bi(question.label, question.label_vi);
    if (question.required) {
      var req = document.createElement('span');
      req.className = 'hf-q__req';
      req.textContent = '*';
      label.appendChild(req);
    }
    wrap.appendChild(label);

    var help = bi(question.help, question.help_vi);
    if (help) {
      var helpEl = document.createElement('div');
      helpEl.className = 'hf-q__help';
      helpEl.textContent = help;
      wrap.appendChild(helpEl);
    }

    var type = question.type;
    if (type === 'number') {
      var num = document.createElement('input');
      num.type = 'number';
      num.inputMode = 'decimal';
      if (question.min != null) num.min = question.min;
      if (question.max != null) num.max = question.max;
      if (answers[question.key] != null) num.value = answers[question.key];
      num.addEventListener('change', function () {
        answers[question.key] =
          num.value === '' ? null : parseFloat(num.value);
        rerender();
      });
      wrap.appendChild(num);
    } else if (type === 'selection' || type === 'multiselect') {
      (question.options || []).forEach(function (option) {
        var row = document.createElement('label');
        row.className = 'hf-opt';
        var input = document.createElement('input');
        input.type = type === 'selection' ? 'radio' : 'checkbox';
        input.name = 'hf_' + question.key;
        if (type === 'selection') {
          input.checked = answers[question.key] === option.value;
        } else {
          input.checked = Array.isArray(answers[question.key])
            && answers[question.key].indexOf(option.value) >= 0;
        }
        input.addEventListener('change', function () {
          if (type === 'selection') {
            answers[question.key] = option.value;
          } else {
            var current = Array.isArray(answers[question.key])
              ? answers[question.key].slice() : [];
            var index = current.indexOf(option.value);
            if (index >= 0) current.splice(index, 1);
            else current.push(option.value);
            answers[question.key] = current;
          }
          rerender();
        });
        var text = document.createElement('span');
        text.textContent = bi(option.label, option.label_vi);
        row.appendChild(input);
        row.appendChild(text);
        wrap.appendChild(row);
      });
    } else if (type === 'boolean') {
      [{ v: true, l: _t('Yes') }, { v: false, l: _t('No') }]
        .forEach(function (choice) {
          var row = document.createElement('label');
          row.className = 'hf-opt';
          var input = document.createElement('input');
          input.type = 'radio';
          input.name = 'hf_' + question.key;
          input.checked = answers[question.key] === choice.v;
          input.addEventListener('change', function () {
            answers[question.key] = choice.v;
            rerender();
          });
          var text = document.createElement('span');
          text.textContent = choice.l;
          row.appendChild(input);
          row.appendChild(text);
          wrap.appendChild(row);
        });
    } else if (type === 'text') {
      var area = document.createElement('textarea');
      area.rows = 2;
      area.value = answers[question.key] || '';
      area.addEventListener('change', function () {
        answers[question.key] = area.value || null;
      });
      wrap.appendChild(area);
    } else if (type === 'date') {
      var date = document.createElement('input');
      date.type = 'date';
      if (answers[question.key]) date.value = answers[question.key];
      date.addEventListener('change', function () {
        answers[question.key] = date.value || null;
      });
      wrap.appendChild(date);
    } else if (type === 'photo') {
      var file = document.createElement('input');
      file.type = 'file';
      file.accept = 'image/*';
      file.setAttribute('capture', 'environment');
      var preview = document.createElement('img');
      preview.className = 'hf-photo-preview';
      preview.style.display = 'none';
      file.addEventListener('change', function () {
        var selected = file.files && file.files[0];
        if (!selected) return;
        var reader = new FileReader();
        reader.onload = function () {
          var dataUrl = String(reader.result);
          answers[question.key] = {
            base64: dataUrl.split(',', 2)[1],
            filename: selected.name || question.key + '.jpg',
            mimetype: selected.type || 'image/jpeg',
          };
          preview.src = dataUrl;
          preview.style.display = 'block';
        };
        reader.readAsDataURL(selected);
      });
      wrap.appendChild(file);
      wrap.appendChild(preview);
    } else if (type === 'signature') {
      buildSignaturePad(wrap, question, answers);
    } else if (type === 'computed_score') {
      var computed = document.createElement('div');
      computed.className = 'hf-footer__total';
      computed.dataset.hfComputed = '1';
      wrap.appendChild(computed);
    }
    return wrap;
  }

  // Minimal inline signature pad (pointer events, PNG base64). The
  // health_evv pad (window.healthEVV.signaturePad) submits straight to
  // the EVV endpoint, so it cannot capture an arbitrary form answer —
  // this local pad keeps the same interaction (draw / clear).
  function buildSignaturePad(wrap, question, answers) {
    var canvas = document.createElement('canvas');
    canvas.className = 'hf-canvas';
    canvas.width = 600;
    canvas.height = 240;
    var context = canvas.getContext('2d');
    context.lineWidth = 2.5;
    context.lineCap = 'round';
    context.strokeStyle = COLORS.text;
    var drawing = false;
    var hasInk = false;

    function point(event) {
      var rect = canvas.getBoundingClientRect();
      return {
        x: (event.clientX - rect.left) * (canvas.width / rect.width),
        y: (event.clientY - rect.top) * (canvas.height / rect.height),
      };
    }
    function commit() {
      if (!hasInk) return;
      answers[question.key] = {
        base64: canvas.toDataURL('image/png').split(',', 2)[1],
        filename: question.key + '.png',
        mimetype: 'image/png',
      };
    }
    canvas.addEventListener('pointerdown', function (event) {
      drawing = true;
      hasInk = true;
      var p = point(event);
      context.beginPath();
      context.moveTo(p.x, p.y);
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener('pointermove', function (event) {
      if (!drawing) return;
      var p = point(event);
      context.lineTo(p.x, p.y);
      context.stroke();
    });
    ['pointerup', 'pointercancel'].forEach(function (name) {
      canvas.addEventListener(name, function () {
        drawing = false;
        commit();
      });
    });

    var hint = document.createElement('div');
    hint.className = 'hf-q__help';
    hint.textContent = _t('Sign here');

    var clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'hf-btn hf-btn--muted';
    clear.textContent = _t('Clear');
    clear.addEventListener('click', function () {
      context.clearRect(0, 0, canvas.width, canvas.height);
      hasInk = false;
      answers[question.key] = null;
    });

    wrap.appendChild(hint);
    wrap.appendChild(canvas);
    wrap.appendChild(clear);
  }

  // ---------------------------------------------------------------
  // Runner overlay
  // ---------------------------------------------------------------
  var FormRunner = {
    open: function (orderId, schema) {
      injectStyles();
      var answers = {};
      var overlay = document.createElement('div');
      overlay.className = 'hf-overlay';
      var runner = document.createElement('div');
      runner.className = 'hf-runner';
      overlay.appendChild(runner);
      document.body.appendChild(overlay);

      function close() { overlay.remove(); }

      function render() {
        runner.innerHTML = '';
        var title = document.createElement('h3');
        title.textContent = bi(schema.title, schema.title_vi);
        runner.appendChild(title);

        (schema.questions || []).forEach(function (question) {
          if (!isVisible(question, answers)) return;
          runner.appendChild(buildQuestion(question, answers, render));
        });

        var total = totalScore(schema, answers);
        runner.querySelectorAll('[data-hf-computed]')
          .forEach(function (el) { el.textContent = String(total); });

        if (schema.scoring && schema.scoring.method === 'sum') {
          var footer = document.createElement('div');
          footer.className = 'hf-footer';
          var totalLabel = document.createElement('span');
          totalLabel.textContent = _t('Total score') + ':';
          var totalEl = document.createElement('span');
          totalEl.className = 'hf-footer__total';
          totalEl.textContent = String(total);
          footer.appendChild(totalLabel);
          footer.appendChild(totalEl);
          var band = resolveBand(schema, total);
          if (band) {
            var chip = document.createElement('span');
            chip.className = 'hf-chip';
            chip.style.backgroundColor = band.color || COLORS.muted;
            chip.textContent = bi(band.label, band.label_vi);
            footer.appendChild(chip);
          }
          runner.appendChild(footer);
        }

        var actions = document.createElement('div');
        actions.className = 'hf-actions';
        var cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'hf-btn hf-btn--muted';
        cancel.textContent = _t('Cancel');
        cancel.addEventListener('click', close);
        var submit = document.createElement('button');
        submit.type = 'button';
        submit.className = 'hf-btn hf-btn--success';
        submit.textContent = _t('Submit');
        submit.addEventListener('click', function () {
          FormRunner._submit(orderId, schema, answers, close, submit);
        });
        actions.appendChild(cancel);
        actions.appendChild(submit);
        runner.appendChild(actions);
      }

      render();
    },

    _validate: function (schema, answers) {
      var questions = (schema.questions || []).filter(function (question) {
        return isVisible(question, answers);
      });
      for (var i = 0; i < questions.length; i += 1) {
        var question = questions[i];
        var answer = answers[question.key];
        var empty = answer == null || answer === ''
          || (Array.isArray(answer) && !answer.length);
        if (question.required && question.type !== 'computed_score'
            && empty && answer !== false) {
          return _t('Required questions are missing') + ': '
            + bi(question.label, question.label_vi);
        }
        if (question.type === 'number' && answer != null && answer !== '') {
          var value = parseFloat(answer);
          if ((question.min != null && value < question.min)
              || (question.max != null && value > question.max)) {
            return _t('Value out of range') + ': '
              + bi(question.label, question.label_vi);
          }
        }
      }
      return null;
    },

    _submit: function (orderId, schema, answers, close, button) {
      var error = FormRunner._validate(schema, answers);
      if (error) {
        notify(error, 'warning');
        return;
      }
      button.disabled = true;
      window.healthFormsStore.submit(orderId, {
        template_id: schema.id,
        answers: answers,
      }).then(function (result) {
        close();
        if (result.queued) {
          notify(_t('Saved offline — will sync when online'), 'info');
        } else {
          var message = _t('Assessment saved');
          if (result.score_label || result.score_label_vi) {
            message += ': ' + result.total_score + ' — '
              + bi(result.score_label, result.score_label_vi);
          }
          notify(message, 'success');
          (result.observation_alerts || []).forEach(function (alert) {
            notify(alert.message, alert.alert_level === 'critical'
              ? 'error' : 'warning');
          });
        }
      }).catch(function (err) {
        button.disabled = false;
        notify(_t('Error') + ': ' + (err && err.message || err), 'error');
      });
    },
  };

  // ---------------------------------------------------------------
  // Picker sheet: applicable templates + completed instances
  // ---------------------------------------------------------------
  var FormPicker = {
    open: function (orderId) {
      injectStyles();
      var sheet = document.createElement('div');
      sheet.className = 'hf-sheet';
      sheet.innerHTML = '<h3>' + _t('Assessments') + '</h3>';
      document.body.appendChild(sheet);

      window.healthFormsStore.getFsoForms(orderId).then(function (data) {
        var templates = data.applicable_templates || [];
        var instances = data.instances || [];
        if (!templates.length) {
          var none = document.createElement('div');
          none.className = 'hf-instance';
          none.textContent = _t('No forms apply to this visit');
          sheet.appendChild(none);
        }
        templates.forEach(function (template) {
          var button = document.createElement('button');
          button.type = 'button';
          button.className = 'hf-btn hf-btn--list';
          button.textContent = bi(template.name, template.name_vi);
          button.addEventListener('click', function () {
            sheet.remove();
            window.healthFormsStore.getTemplateById(template.id)
              .then(function (schema) {
                if (schema) FormRunner.open(orderId, schema);
                else notify(_t('Error'), 'error');
              });
          });
          sheet.appendChild(button);
        });
        var completed = instances.filter(function (instance) {
          return instance.state === 'completed'
            || instance.state === 'amended';
        });
        if (completed.length) {
          var head = document.createElement('div');
          head.className = 'hf-q__label';
          head.style.marginTop = '10px';
          head.textContent = _t('Completed this visit');
          sheet.appendChild(head);
          completed.forEach(function (instance) {
            var row = document.createElement('div');
            row.className = 'hf-instance';
            row.textContent = instance.template_code + ' — '
              + instance.total_score
              + (instance.score_label
                 ? ' (' + bi(instance.score_label,
                             instance.score_label_vi) + ')' : '');
            sheet.appendChild(row);
          });
        }
        var actions = document.createElement('div');
        actions.className = 'hf-actions';
        var closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'hf-btn hf-btn--muted';
        closeButton.textContent = _t('Close');
        closeButton.addEventListener('click', function () { sheet.remove(); });
        actions.appendChild(closeButton);
        sheet.appendChild(actions);
      }).catch(function (err) {
        sheet.remove();
        notify(_t('Error') + ': ' + (err && err.message || err), 'error');
      });
    },
  };

  // ---------------------------------------------------------------
  // Visit-screen docked button (#/orders/<id>), EVV-chip style wiring
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
      fabButton.className = 'hf-fab';
      document.body.appendChild(fabButton);
    }
    fabButton.textContent = _t('Assessments');
    fabButton.onclick = function () { FormPicker.open(orderId); };
  }

  window.addEventListener('hashchange', syncFab);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncFab);
  } else {
    syncFab();
  }

  window.healthFormsRunner = {
    openPicker: function (orderId) { FormPicker.open(orderId); },
    openForm: function (orderId, schema) { FormRunner.open(orderId, schema); },
    totalScore: totalScore,
    resolveBand: resolveBand,
    isVisible: isVisible,
    contribution: contribution,
  };
})();
