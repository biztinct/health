// Health Forms - PWA data layer (spec §4.8).
//
// window.healthFormsStore:
//   getTemplates(force)        — §4.2 schemas, cached in localStorage so
//                                cached forms keep working offline.
//   getFsoForms(orderId)       — applicable templates + existing instances.
//   submit(orderId, payload)   — POST to the submit endpoint; on network
//                                failure the payload (photos/signature as
//                                base64) is queued in the outbox with its
//                                client_uuid; replay is idempotent
//                                server-side.
//   flushOutbox()              — replays queued submissions (also wired
//                                to the window 'online' event).
//
// Plain JS + window globals — health_pwa files are never touched; these
// scripts are injected through QWeb inheritance of health_pwa.app_shell.

(function () {
  'use strict';

  var TEMPLATES_KEY = 'health_forms_templates_v1';
  var OUTBOX_KEY = 'health_forms_outbox_v1';

  function readStorage(key, fallback) {
    try {
      var raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeStorage(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.warn('[healthForms] localStorage write failed', error);
    }
  }

  function apiGet(url) {
    return fetch(url, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    }).then(function (response) {
      return response.json();
    }).then(function (envelope) {
      if (!envelope.success) {
        throw new Error(envelope.error || 'API error');
      }
      return envelope.data;
    });
  }

  function apiPost(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    }).then(function (response) {
      return response.json();
    }).then(function (envelope) {
      if (!envelope.success) {
        throw new Error(envelope.error || 'API error');
      }
      return envelope.data;
    });
  }

  function uuid4() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,
      function (c) {
        var r = Math.random() * 16 | 0;
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
      });
  }

  var healthFormsStore = {
    // ---------------------------------------------------------------
    // Templates (reference data, offline-cached)
    // ---------------------------------------------------------------
    getTemplates: function (force) {
      var cached = readStorage(TEMPLATES_KEY, null);
      if (cached && !force) {
        // Refresh in the background, serve the cache now.
        healthFormsStore._refreshTemplates();
        return Promise.resolve(cached);
      }
      return healthFormsStore._refreshTemplates().catch(function () {
        return cached || [];
      });
    },

    _refreshTemplates: function () {
      return apiGet('/health_pwa/api/forms/templates')
        .then(function (data) {
          var templates = data.templates || [];
          writeStorage(TEMPLATES_KEY, templates);
          return templates;
        });
    },

    getTemplateById: function (templateId) {
      return healthFormsStore.getTemplates().then(function (templates) {
        return templates.find(function (template) {
          return template.id === templateId;
        }) || null;
      });
    },

    // ---------------------------------------------------------------
    // Per-visit forms
    // ---------------------------------------------------------------
    getFsoForms: function (orderId) {
      return apiGet('/health_pwa/api/fso/' + orderId + '/forms');
    },

    getPatientForms: function (patientId, templateCode) {
      var url = '/health_pwa/api/patients/' + patientId + '/forms';
      if (templateCode) {
        url += '?template_code=' + encodeURIComponent(templateCode);
      }
      return apiGet(url);
    },

    // ---------------------------------------------------------------
    // Submit + offline outbox (idempotent via client_uuid)
    // ---------------------------------------------------------------
    submit: function (orderId, payload) {
      payload = payload || {};
      if (!payload.client_uuid) {
        payload.client_uuid = uuid4();
      }
      return apiPost(
        '/health_pwa/api/fso/' + orderId + '/forms/submit', payload
      ).catch(function (error) {
        // Network/offline failure: queue the whole payload for replay.
        healthFormsStore._enqueue(orderId, payload);
        return { queued: true, client_uuid: payload.client_uuid,
                 error: String(error && error.message || error) };
      });
    },

    _enqueue: function (orderId, payload) {
      var outbox = readStorage(OUTBOX_KEY, []);
      var exists = outbox.some(function (item) {
        return item.payload.client_uuid === payload.client_uuid;
      });
      if (!exists) {
        outbox.push({ order_id: orderId, payload: payload,
                      queued_at: new Date().toISOString() });
        writeStorage(OUTBOX_KEY, outbox);
      }
    },

    outboxCount: function () {
      return readStorage(OUTBOX_KEY, []).length;
    },

    flushOutbox: function () {
      var outbox = readStorage(OUTBOX_KEY, []);
      if (!outbox.length) {
        return Promise.resolve({ flushed: 0 });
      }
      var remaining = [];
      var flushed = 0;
      var chain = Promise.resolve();
      outbox.forEach(function (item) {
        chain = chain.then(function () {
          return apiPost(
            '/health_pwa/api/fso/' + item.order_id + '/forms/submit',
            item.payload
          ).then(function () {
            flushed += 1;
          }).catch(function () {
            remaining.push(item);
          });
        });
      });
      return chain.then(function () {
        writeStorage(OUTBOX_KEY, remaining);
        return { flushed: flushed, remaining: remaining.length };
      });
    },

    uuid4: uuid4,
  };

  window.healthFormsStore = healthFormsStore;

  window.addEventListener('online', function () {
    healthFormsStore.flushOutbox().then(function (result) {
      if (result.flushed && window.healthPWA
          && window.healthPWA.showNotification) {
        window.healthPWA.showNotification(
          result.flushed + ' assessment(s) synced', 'success');
      }
    });
  });
})();
