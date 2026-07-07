// Health Incident - types cache + API client + offline queue (spec §5.7)
//
// Loaded BEFORE incident-components.js: this file owns the incident
// type/severity reference cache and the offline queue replayed to
// POST /health_pwa/api/incidents. Write-mostly: no PouchDB read store
// is needed — the queue replays the POST with a client_mutation_id so
// a replayed mutation never duplicates (server-side idempotency).

(function () {
  'use strict';

  const TYPES_ENDPOINT = '/health_pwa/api/incidents/types';
  const TYPES_CACHE_KEY = 'health_incident_types';
  const TYPES_CACHE_TS_KEY = 'health_incident_types_ts';
  const TYPES_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // refresh daily
  const OUTBOX_KEY = 'health_incident_outbox';

  function newMutationId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return 'inc-' + Date.now() + '-'
      + Math.random().toString(36).slice(2, 12);
  }

  // ---------------------------------------------------------------
  // Types reference cache
  // ---------------------------------------------------------------
  function readCachedTypes() {
    try {
      const raw = localStorage.getItem(TYPES_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function writeCachedTypes(data) {
    try {
      localStorage.setItem(TYPES_CACHE_KEY, JSON.stringify(data));
      localStorage.setItem(TYPES_CACHE_TS_KEY, String(Date.now()));
    } catch (error) {
      console.warn('[Incident] types cache write failed', error);
    }
  }

  async function fetchTypes() {
    const response = await fetch(TYPES_ENDPOINT, { credentials: 'same-origin' });
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Incident types error');
    return result.data;
  }

  async function getTypes(forceRefresh) {
    const cached = readCachedTypes();
    const ts = parseInt(localStorage.getItem(TYPES_CACHE_TS_KEY) || '0', 10);
    const fresh = cached && (Date.now() - ts) < TYPES_CACHE_TTL_MS;
    if (cached && fresh && !forceRefresh) return cached;
    try {
      const data = await fetchTypes();
      writeCachedTypes(data);
      return data;
    } catch (error) {
      if (cached) return cached; // offline: serve stale reference data
      throw error;
    }
  }

  // ---------------------------------------------------------------
  // Submission + offline queue
  // ---------------------------------------------------------------
  async function submitIncident(payload) {
    const response = await fetch('/health_pwa/api/incidents', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Incident error');
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
      console.warn('[Incident] outbox write failed', error);
    }
  }

  function enqueue(payload) {
    const outbox = readOutbox();
    outbox.push({
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
      const outbox = readOutbox();
      const remaining = [];
      for (let i = 0; i < outbox.length; i++) {
        const item = outbox[i];
        try {
          await submitIncident(item.payload);
        } catch (error) {
          // Network errors retry; server-side rejection (4xx) is
          // final — the mutation id makes retries idempotent anyway.
          if (error instanceof TypeError) {
            remaining.push(item);
          } else {
            console.warn('[Incident] queued incident rejected', error);
          }
        }
      }
      writeOutbox(remaining);
    } finally {
      flushing = false;
    }
  }

  // Submit-or-queue: never lose an incident report offline. Every
  // payload carries a client_mutation_id before first submission so
  // replays after a mid-flight network failure never duplicate.
  async function submitOrQueue(payload) {
    if (!payload.client_mutation_id) {
      payload.client_mutation_id = newMutationId();
    }
    try {
      return await submitIncident(payload);
    } catch (error) {
      if (error instanceof TypeError || !navigator.onLine) {
        enqueue(payload);
        return { queued: true };
      }
      throw error;
    }
  }

  // ---------------------------------------------------------------
  // Reads (my reports)
  // ---------------------------------------------------------------
  async function getMyIncidents(params) {
    const query = new URLSearchParams(params || {}).toString();
    const response = await fetch(
      '/health_pwa/api/incidents/mine' + (query ? '?' + query : ''),
      { credentials: 'same-origin' });
    const result = await response.json();
    if (!result.success) throw new Error(result.error || 'Incident error');
    return result.data;
  }

  window.addEventListener('online', function () { flushOutbox(); });
  document.addEventListener('DOMContentLoaded', function () {
    flushOutbox();
    getTypes().catch(function () { /* offline first load */ });
  });

  window.healthIncidentService = {
    getTypes: getTypes,
    newMutationId: newMutationId,
    submitIncident: submitIncident,
    submitOrQueue: submitOrQueue,
    flushOutbox: flushOutbox,
    getMyIncidents: getMyIncidents,
    outboxCount: function () { return readOutbox().length; },
  };
})();
