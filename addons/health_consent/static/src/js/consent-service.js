// Health Consent - PWA API client + offline capture queue (spec §6.7).
//
// window.healthConsentService — API layer consumed by
// consent-components.js:
//   getTypes()                 — selection labels (en/vi), 5-min cache.
//   getConsents(patientId)     — consents + status + grantor relations.
//   getStatus(patientId)       — {service, data_sharing, ...} booleans,
//                                5-min cache (storage-manager convention).
//   createConsent(patientId, payload) — POST; on network failure the
//                                mutation is queued in localStorage with
//                                a client_mutation_id idempotency key and
//                                replayed when back online (append-only
//                                offline discipline, interop §6.7).
//   withdraw(consentId, reason)
//   orderPatientId(orderId)    — resolves the client of a visit via the
//                                existing health_pwa FSO detail endpoint
//                                (read-only; health_pwa is not modified).
//   canCapturePhoto(patientId) — photography soft check (spec §6.8.1):
//                                the PWA checks status.photography before
//                                opening the camera for clinical photos.
//                                Server-side hard enforcement lands with
//                                the api-gateway phase.

(function () {
  'use strict';

  var QUEUE_KEY = 'healthConsentQueue';
  var CACHE_TTL = 5 * 60 * 1000; // 5 minutes, storage-manager convention
  var statusCache = {}; // patientId -> {at, status}
  var typesCache = null;

  function uuid() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return 'cns-' + Date.now() + '-'
      + Math.random().toString(16).slice(2, 10);
  }

  function apiFetch(url, options) {
    options = options || {};
    options.credentials = 'same-origin';
    options.headers = options.headers || {};
    if (options.body) {
      options.headers['Content-Type'] = 'application/json';
    }
    return fetch(url, options).then(function (response) {
      return response.json().then(function (envelope) {
        if (!envelope.success) {
          var error = new Error(envelope.error || 'Request failed');
          error.status = response.status;
          throw error;
        }
        return envelope.data;
      });
    });
  }

  // ---------------------------------------------------------------
  // Offline capture queue (localStorage, replayed on 'online')
  // ---------------------------------------------------------------
  function readQueue() {
    try {
      return JSON.parse(window.localStorage.getItem(QUEUE_KEY)) || [];
    } catch (error) {
      return [];
    }
  }

  function writeQueue(queue) {
    try {
      window.localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
    } catch (error) {
      console.warn('[healthConsent] queue persist failed', error);
    }
  }

  function postConsent(patientId, payload) {
    return apiFetch(
      '/health_pwa/api/patients/' + patientId + '/consents',
      { method: 'POST', body: JSON.stringify(payload) });
  }

  function flushQueue() {
    var queue = readQueue();
    if (!queue.length || !navigator.onLine) return Promise.resolve();
    var item = queue[0];
    // Idempotent replay: the server no-ops on a known
    // client_mutation_id, so re-sending is always safe.
    return postConsent(item.patient_id, item.payload)
      .then(function () {
        queue.shift();
        writeQueue(queue);
        invalidateStatus(item.patient_id);
        return flushQueue();
      })
      .catch(function (error) {
        if (error && error.status >= 400 && error.status < 500) {
          // Rejected by business rules — drop it, do not loop forever.
          console.warn('[healthConsent] queued consent rejected', error);
          queue.shift();
          writeQueue(queue);
          return flushQueue();
        }
        // Still offline / server error: retry later.
        return null;
      });
  }

  window.addEventListener('online', function () { flushQueue(); });
  setTimeout(flushQueue, 4000);

  // ---------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------
  function invalidateStatus(patientId) {
    delete statusCache[patientId];
  }

  var service = {
    getTypes: function () {
      if (typesCache && (Date.now() - typesCache.at) < CACHE_TTL) {
        return Promise.resolve(typesCache.data);
      }
      return apiFetch('/health_pwa/api/consents/types')
        .then(function (data) {
          typesCache = { at: Date.now(), data: data };
          return data;
        });
    },

    getConsents: function (patientId) {
      return apiFetch(
        '/health_pwa/api/patients/' + patientId + '/consents')
        .then(function (data) {
          statusCache[patientId] = {
            at: Date.now(), status: data.status || {},
          };
          return data;
        });
    },

    getStatus: function (patientId) {
      var cached = statusCache[patientId];
      if (cached && (Date.now() - cached.at) < CACHE_TTL) {
        return Promise.resolve(cached.status);
      }
      return service.getConsents(patientId).then(function (data) {
        return data.status || {};
      });
    },

    createConsent: function (patientId, payload) {
      payload = payload || {};
      if (!payload.client_mutation_id) {
        payload.client_mutation_id = uuid();
      }
      return postConsent(patientId, payload)
        .then(function (data) {
          invalidateStatus(patientId);
          return data;
        })
        .catch(function (error) {
          if (error && error.status >= 400 && error.status < 500) {
            throw error; // business rejection — surface to the user
          }
          // Network / server failure: queue for idempotent replay.
          var queue = readQueue();
          queue.push({ patient_id: patientId, payload: payload });
          writeQueue(queue);
          return { queued: true };
        });
    },

    withdraw: function (consentId, reason) {
      return apiFetch(
        '/health_pwa/api/consents/' + consentId + '/withdraw',
        { method: 'POST', body: JSON.stringify({ reason: reason }) })
        .then(function (data) {
          statusCache = {};
          return data;
        });
    },

    orderPatientId: function (orderId) {
      return apiFetch('/health_pwa/api/fso/' + orderId)
        .then(function (data) {
          return (data && data.patient && data.patient.id) || null;
        });
    },

    canCapturePhoto: function (patientId) {
      return service.getStatus(patientId).then(function (status) {
        return Boolean(status && status.photography);
      }).catch(function () {
        // Deny-by-default is for sharing; photo capture must not be
        // hard-blocked by a network error (log-only phase, §6.8.1).
        return true;
      });
    },

    invalidateStatus: invalidateStatus,
    flushQueue: flushQueue,
    pendingCount: function () { return readQueue().length; },
  };

  window.healthConsentService = service;
})();
