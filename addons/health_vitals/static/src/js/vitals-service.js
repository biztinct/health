// Health Vitals - types cache + API client + offline outbox (spec §2.7)
//
// Loaded BEFORE vitals-components.js: this file owns the observation
// type reference cache and the offline outbox replayed to
// POST /health_pwa/api/fso/<id>/vitals. Clinical data is append-only
// offline: queued observations are only ever created, never edited.

(function () {
  'use strict';

  const TYPES_ENDPOINT = '/health_pwa/api/vitals/types';
  const TYPES_CACHE_KEY = 'health_vitals_types';
  const TYPES_CACHE_TS_KEY = 'health_vitals_types_ts';
  const TYPES_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // refresh daily
  const OUTBOX_KEY = 'health_vitals_outbox';

  // ---------------------------------------------------------------
  // Types reference cache (PouchDB-equivalent local store)
  // ---------------------------------------------------------------
  function readCachedTypes() {
    try {
      const raw = localStorage.getItem(TYPES_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function writeCachedTypes(types) {
    try {
      localStorage.setItem(TYPES_CACHE_KEY, JSON.stringify(types));
      localStorage.setItem(TYPES_CACHE_TS_KEY, String(Date.now()));
    } catch (error) {
      console.warn('[Vitals] types cache write failed', error);
    }
  }

  async function fetchTypes() {
    const response = await fetch(TYPES_ENDPOINT, { credentials: 'same-origin' });
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Vitals types error');
    return result.data.types || [];
  }

  async function getTypes(forceRefresh) {
    const cached = readCachedTypes();
    const ts = parseInt(localStorage.getItem(TYPES_CACHE_TS_KEY) || '0', 10);
    const fresh = cached && (Date.now() - ts) < TYPES_CACHE_TTL_MS;
    if (cached && fresh && !forceRefresh) return cached;
    try {
      const types = await fetchTypes();
      writeCachedTypes(types);
      return types;
    } catch (error) {
      if (cached) return cached; // offline: serve stale reference data
      throw error;
    }
  }

  function getTypeByCode(types, code) {
    for (let i = 0; i < types.length; i++) {
      if (types[i].code === code) return types[i];
    }
    return null;
  }

  // Plausible-range client-side validation (mirror of the server
  // _check_value constraint). Returns null when OK, message when not.
  function validateValue(type, value) {
    const numeric = Number(value);
    if (value === '' || value === null || isNaN(numeric)) {
      return 'missing';
    }
    if (type.plausible_min && numeric < type.plausible_min) return 'range';
    if (type.plausible_max && numeric > type.plausible_max) return 'range';
    return null;
  }

  // ---------------------------------------------------------------
  // Submission + offline outbox
  // ---------------------------------------------------------------
  async function submitVitals(fsoId, payload) {
    const response = await fetch(
      '/health_pwa/api/fso/' + fsoId + '/vitals', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Vitals error');
    return result.data;
  }

  function readOutbox() {
    try {
      const raw = localStorage.getItem(OUTBOX_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (error) {
      return [];
    }
  }

  function writeOutbox(items) {
    try {
      localStorage.setItem(OUTBOX_KEY, JSON.stringify(items));
    } catch (error) {
      console.warn('[Vitals] outbox write failed', error);
    }
  }

  function enqueue(fsoId, payload) {
    const outbox = readOutbox();
    outbox.push({
      fso_id: fsoId,
      payload: payload,
      queued_at: new Date().toISOString(),
    });
    writeOutbox(outbox);
  }

  let flushing = false;
  async function flushOutbox() {
    if (flushing || !navigator.onLine) return;
    flushing = true;
    try {
      let outbox = readOutbox();
      const remaining = [];
      for (let i = 0; i < outbox.length; i++) {
        const item = outbox[i];
        try {
          await submitVitals(item.fso_id, item.payload);
        } catch (error) {
          // Server-side rejection (4xx) is final — plausible range or
          // unknown code; do not retry forever. Network errors retry.
          if (error instanceof TypeError) {
            remaining.push(item);
          } else {
            console.warn('[Vitals] queued vitals rejected', error);
          }
        }
      }
      writeOutbox(remaining);
    } finally {
      flushing = false;
    }
  }

  // Submit-or-queue: never lose point-of-care data offline.
  async function submitOrQueue(fsoId, payload) {
    try {
      return await submitVitals(fsoId, payload);
    } catch (error) {
      if (error instanceof TypeError || !navigator.onLine) {
        enqueue(fsoId, payload);
        return { queued: true, created_ids: [], alerts: [] };
      }
      throw error;
    }
  }

  // ---------------------------------------------------------------
  // Reads (client screen)
  // ---------------------------------------------------------------
  async function getPatientVitals(patientId, params) {
    const query = new URLSearchParams(params || {}).toString();
    const response = await fetch(
      '/health_pwa/api/patients/' + patientId + '/vitals'
      + (query ? '?' + query : ''), { credentials: 'same-origin' });
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Vitals error');
    return result.data;
  }

  async function getTrend(patientId, typeCode, days) {
    const query = new URLSearchParams({
      type_code: typeCode,
      days: String(days || 30),
    }).toString();
    const response = await fetch(
      '/health_pwa/api/patients/' + patientId + '/vitals/trend?' + query,
      { credentials: 'same-origin' });
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Vitals error');
    return result.data;
  }

  window.addEventListener('online', function () { flushOutbox(); });
  document.addEventListener('DOMContentLoaded', function () {
    flushOutbox();
    getTypes().catch(function () { /* offline first load */ });
  });

  window.healthVitalsService = {
    getTypes: getTypes,
    getTypeByCode: getTypeByCode,
    validateValue: validateValue,
    submitVitals: submitVitals,
    submitOrQueue: submitOrQueue,
    flushOutbox: flushOutbox,
    getPatientVitals: getPatientVitals,
    getTrend: getTrend,
    outboxCount: function () { return readOutbox().length; },
  };
})();
