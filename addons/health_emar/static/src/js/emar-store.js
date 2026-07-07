// Health eMAR - PWA data layer (spec §3.7).
//
// window.healthEmarStore:
//   getFsoMedications(orderId, force) — per-visit checklist: slots
//                             linked to the visit + unlinked planned
//                             slots due in the visit window, PRN orders
//                             and the not-given reason catalog. Cached
//                             per visit in localStorage so an offline
//                             visit still shows its checklist.
//   recordAdministration(adminId, payload) — one-tap tick (given /
//                             not_given / refused with reason). On
//                             network failure the mutation is queued in
//                             the outbox with a client_mutation_id;
//                             replay is idempotent server-side (same
//                             status = success no-op, different status
//                             = conflict surfaced to the nurse).
//   createPrnDose(fsoId, medicationOrderId) — PRN '+ dose'.
//   getPatientOrders(patientId) — active med orders for a client.
//   flushOutbox()             — replays queued ticks (also wired to
//                             the window 'online' event).
//
// Plain JS + window globals — health_pwa files are never touched; these
// scripts are injected through QWeb inheritance of health_pwa.app_shell.

(function () {
  'use strict';

  var MEDS_CACHE_KEY = 'health_emar_fso_meds_v1';
  var REASONS_KEY = 'health_emar_reasons_v1';
  var OUTBOX_KEY = 'health_emar_outbox_v1';

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
      console.warn('[healthEmar] localStorage write failed', error);
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
      return response.json().then(function (envelope) {
        if (!envelope.success) {
          var error = new Error(envelope.error || 'API error');
          error.status = response.status;
          error.conflict = response.status === 409;
          throw error;
        }
        return envelope.data;
      });
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

  function isNetworkError(error) {
    // fetch() rejects with TypeError on network failure; API errors
    // carry .status.
    return !(error && error.status);
  }

  var healthEmarStore = {
    // ---------------------------------------------------------------
    // Per-visit checklist (cached per visit for offline)
    // ---------------------------------------------------------------
    getFsoMedications: function (orderId, force) {
      var cache = readStorage(MEDS_CACHE_KEY, {});
      var cached = cache[String(orderId)] || null;
      if (cached && !force) {
        // Refresh in the background, serve the cache now.
        healthEmarStore._refreshFsoMedications(orderId)
          .catch(function () { /* offline — cache already served */ });
        return Promise.resolve(cached);
      }
      return healthEmarStore._refreshFsoMedications(orderId)
        .catch(function (error) {
          if (cached) return cached;
          throw error;
        });
    },

    _refreshFsoMedications: function (orderId) {
      return apiGet('/health_pwa/api/fso/' + orderId + '/medications')
        .then(function (data) {
          var cache = readStorage(MEDS_CACHE_KEY, {});
          cache[String(orderId)] = data;
          writeStorage(MEDS_CACHE_KEY, cache);
          if (data.reasons) {
            // Reasons reference store (offline-cached catalog).
            writeStorage(REASONS_KEY, data.reasons);
          }
          return data;
        });
    },

    getReasons: function () {
      return readStorage(REASONS_KEY, []);
    },

    // ---------------------------------------------------------------
    // Recording ticks (offline queue)
    // ---------------------------------------------------------------
    recordAdministration: function (adminId, payload) {
      var body = Object.assign({}, payload, {
        client_mutation_id: payload.client_mutation_id || uuid4(),
      });
      return apiPost(
        '/health_pwa/api/administrations/' + adminId + '/record', body
      ).then(function (data) {
        healthEmarStore._applyLocalState(adminId, data.state);
        return data;
      }).catch(function (error) {
        if (error.conflict) {
          throw error;
        }
        if (isNetworkError(error)) {
          healthEmarStore._queueMutation(adminId, body);
          healthEmarStore._applyLocalState(adminId, body.status, true);
          return { admin_id: adminId, state: body.status, queued: true };
        }
        throw error;
      });
    },

    _queueMutation: function (adminId, body) {
      var outbox = readStorage(OUTBOX_KEY, []);
      var exists = outbox.some(function (entry) {
        return entry.admin_id === adminId;
      });
      if (!exists) {
        outbox.push({
          admin_id: adminId,
          body: body,
          queued_at: new Date().toISOString(),
        });
        writeStorage(OUTBOX_KEY, outbox);
      }
    },

    _applyLocalState: function (adminId, state, queued) {
      var cache = readStorage(MEDS_CACHE_KEY, {});
      Object.keys(cache).forEach(function (key) {
        (cache[key].administrations || []).forEach(function (admin) {
          if (admin.id === adminId) {
            admin.state = state;
            admin.pending_sync = Boolean(queued);
          }
        });
      });
      writeStorage(MEDS_CACHE_KEY, cache);
    },

    outboxSize: function () {
      return readStorage(OUTBOX_KEY, []).length;
    },

    flushOutbox: function () {
      var outbox = readStorage(OUTBOX_KEY, []);
      if (!outbox.length) return Promise.resolve(0);
      var remaining = [];
      var flushed = 0;
      var chain = Promise.resolve();
      outbox.forEach(function (entry) {
        chain = chain.then(function () {
          return apiPost(
            '/health_pwa/api/administrations/' + entry.admin_id
              + '/record', entry.body
          ).then(function (data) {
            flushed += 1;
            healthEmarStore._applyLocalState(entry.admin_id, data.state);
          }).catch(function (error) {
            if (error.conflict) {
              // Recorded differently on the server — drop the queued
              // tick, server state wins (surfaced on next refresh).
              flushed += 1;
              return;
            }
            if (isNetworkError(error)) {
              remaining.push(entry);
            }
            // Validation errors are dropped (bad payload will never
            // succeed) — the slot stays planned server-side.
          });
        });
      });
      return chain.then(function () {
        writeStorage(OUTBOX_KEY, remaining);
        return flushed;
      });
    },

    // ---------------------------------------------------------------
    // PRN + client orders
    // ---------------------------------------------------------------
    createPrnDose: function (fsoId, medicationOrderId) {
      return apiPost(
        '/health_pwa/api/fso/' + fsoId + '/medications/prn',
        { order_id: medicationOrderId }
      ).then(function (data) {
        var cache = readStorage(MEDS_CACHE_KEY, {});
        var entry = cache[String(fsoId)];
        if (entry) {
          entry.administrations = entry.administrations || [];
          entry.administrations.push(data);
          writeStorage(MEDS_CACHE_KEY, cache);
        }
        return data;
      });
    },

    getPatientOrders: function (patientId) {
      return apiGet('/health_pwa/api/patients/' + patientId
        + '/medication_orders');
    },
  };

  window.addEventListener('online', function () {
    healthEmarStore.flushOutbox();
  });

  window.healthEmarStore = healthEmarStore;
})();
