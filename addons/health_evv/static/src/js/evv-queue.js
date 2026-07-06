// Health EVV - Offline event queue + canonical hashing (spec A.5 / F.2)
//
// Loaded BEFORE geofence-service.js and evv-components.js: this file owns
// the canonical-JSON + SHA-256 recipe that MUST stay byte-identical to
// the server implementation in
// health_evv/models/health_evv_event.py::_canonical_payload_bytes.
//
// Canonical recipe (server-mirrored):
//   {accuracy_m (round 1), client_event_uuid, device_uuid,
//    event_datetime ('YYYY-MM-DDTHH:MM:SSZ', seconds precision),
//    event_type, fso_id, lat (round 7), lng (round 7),
//    payload (sorted keys, reserved keys excluded), staff_id}
//   -> JSON with sorted keys, separators (',', ':'), no spaces, UTF-8.
//   Integral floats serialize as integers ('10', never '10.0') on both
//   sides. Reserved payload keys excluded from the hash on both sides:
//   client_hash_mismatch, attachment_id.

(function () {
  'use strict';

  const RESERVED_PAYLOAD_KEYS = ['client_hash_mismatch', 'attachment_id'];
  const PUSH_ENDPOINT = '/health_pwa/api/evv/push';
  const MAX_PUSH_BATCH = 200;
  const DEVICE_UUID_KEY = 'health_evv_device_uuid';
  const GENESIS_HASH = '0'.repeat(64);

  // ---------------------------------------------------------------
  // Canonical JSON + SHA-256 (WebCrypto)
  // ---------------------------------------------------------------
  function canonicalNumber(value, digits) {
    const factor = Math.pow(10, digits);
    const rounded = Math.round((Number(value) || 0) * factor) / factor;
    return rounded; // JSON.stringify(10.0) === '10' — matches server int-normalization
  }

  function stableStringify(value) {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'number' || typeof value === 'boolean') {
      return JSON.stringify(value);
    }
    if (typeof value === 'string') return JSON.stringify(value);
    if (Array.isArray(value)) {
      return '[' + value.map(stableStringify).join(',') + ']';
    }
    const keys = Object.keys(value).sort();
    return '{' + keys.map(function (key) {
      return JSON.stringify(key) + ':' + stableStringify(value[key]);
    }).join(',') + '}';
  }

  function canonicalDatetime(value) {
    // Seconds precision, 'YYYY-MM-DDTHH:MM:SSZ'
    if (!value) return '';
    const date = (value instanceof Date) ? value : new Date(value);
    if (isNaN(date.getTime())) return String(value);
    return date.toISOString().replace(/\.\d{3}Z$/, 'Z');
  }

  function canonicalPayloadString(event) {
    const payload = {};
    Object.keys(event.payload || {}).forEach(function (key) {
      if (RESERVED_PAYLOAD_KEYS.indexOf(key) === -1) {
        payload[key] = event.payload[key];
      }
    });
    const canonical = {
      accuracy_m: canonicalNumber(event.accuracy_m, 1),
      client_event_uuid: event.client_event_uuid || '',
      device_uuid: event.device_uuid || '',
      event_datetime: canonicalDatetime(event.event_datetime),
      event_type: event.event_type || '',
      fso_id: parseInt(event.fso_id, 10) || 0,
      lat: canonicalNumber(event.lat, 7),
      lng: canonicalNumber(event.lng, 7),
      payload: payload,
      staff_id: parseInt(event.staff_id, 10) || 0,
    };
    return stableStringify(canonical);
  }

  async function sha256Hex(text) {
    const bytes = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest))
      .map(function (b) { return b.toString(16).padStart(2, '0'); })
      .join('');
  }

  async function hashEvent(event) {
    return sha256Hex(canonicalPayloadString(event));
  }

  // ---------------------------------------------------------------
  // Offline queue (PouchDB, F.2: store 'evv_events' + 'evv_config')
  // ---------------------------------------------------------------
  class EvvQueue {
    constructor() {
      this.db = new PouchDB('health_evv_events');
      this.configDb = new PouchDB('health_evv_config');
      this.flushing = false;
    }

    deviceUuid() {
      let uuid = localStorage.getItem(DEVICE_UUID_KEY);
      if (!uuid) {
        uuid = (crypto.randomUUID && crypto.randomUUID())
          || 'dev-' + Math.random().toString(36).slice(2) + Date.now();
        localStorage.setItem(DEVICE_UUID_KEY, uuid);
      }
      return uuid;
    }

    newEventUuid() {
      return (crypto.randomUUID && crypto.randomUUID())
        || 'evt-' + Math.random().toString(36).slice(2) + Date.now();
    }

    // Per-device client-side chaining (server chain is authoritative
    // and re-sequences on sync).
    async _lastClientHash() {
      const result = await this.db.allDocs({ include_docs: true });
      let last = null;
      result.rows.forEach(function (row) {
        if (!last || (row.doc.queued_at || '') > (last.queued_at || '')) {
          last = row.doc;
        }
      });
      return (last && last.client_hash) || GENESIS_HASH;
    }

    async enqueue(event) {
      // event: {fso_id, event_type, event_datetime, lat, lng,
      //         accuracy_m, staff_id, payload, image_b64?}
      const doc = Object.assign({}, event);
      doc.device_uuid = this.deviceUuid();
      doc.client_event_uuid = doc.client_event_uuid || this.newEventUuid();
      doc.event_datetime = canonicalDatetime(
        doc.event_datetime || new Date());
      doc.prev_client_hash = await this._lastClientHash();
      doc.client_hash = await hashEvent(doc);
      doc._id = doc.client_event_uuid;
      doc.synced = false;
      doc.queued_at = new Date().toISOString();
      try {
        await this.db.put(doc);
      } catch (error) {
        if (error.status !== 409) throw error; // 409 = already queued
      }
      this.registerBackgroundSync();
      return doc;
    }

    async pending() {
      const result = await this.db.allDocs({ include_docs: true });
      return result.rows
        .map(function (row) { return row.doc; })
        .filter(function (doc) { return !doc.synced; })
        .sort(function (a, b) {
          return (a.event_datetime || '').localeCompare(b.event_datetime || '');
        });
    }

    async _markSynced(doc) {
      doc.synced = true;
      doc.synced_at = new Date().toISOString();
      try {
        await this.db.put(doc);
      } catch (error) {
        console.warn('EVV queue: mark synced failed', error);
      }
    }

    async flush() {
      if (this.flushing || !navigator.onLine) return { accepted: 0 };
      this.flushing = true;
      try {
        const pending = await this.pending();
        if (!pending.length) return { accepted: 0 };

        // Signatures carry an image and go to the signature endpoint.
        const signatures = pending.filter(function (doc) {
          return doc.event_type === 'signature' && doc.image_b64;
        });
        const plain = pending.filter(function (doc) {
          return !(doc.event_type === 'signature' && doc.image_b64);
        });

        let accepted = 0;
        for (const doc of signatures) {
          try {
            const response = await fetch(
              '/health_pwa/api/fso/' + doc.fso_id + '/evv/signature', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  image_base64: doc.image_b64,
                  signer_name: (doc.payload || {}).signer_name || '',
                  signer_relationship:
                    (doc.payload || {}).signer_relationship || 'other',
                  lat: doc.lat, lng: doc.lng, accuracy_m: doc.accuracy_m,
                  device_uuid: doc.device_uuid,
                  client_event_uuid: doc.client_event_uuid,
                  client_hash: doc.client_hash,
                  event_datetime: doc.event_datetime,
                  origin: 'offline_sync',
                }),
              });
            const result = await response.json();
            if (result.success) {
              accepted += 1;
              await this._markSynced(doc);
            }
          } catch (error) {
            console.warn('EVV signature flush failed', error);
          }
        }

        for (let i = 0; i < plain.length; i += MAX_PUSH_BATCH) {
          const batch = plain.slice(i, i + MAX_PUSH_BATCH);
          try {
            const response = await fetch(PUSH_ENDPOINT, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                events: batch.map(function (doc) {
                  return {
                    fso_id: doc.fso_id,
                    event_type: doc.event_type,
                    event_datetime: doc.event_datetime,
                    lat: doc.lat, lng: doc.lng,
                    accuracy_m: doc.accuracy_m,
                    device_uuid: doc.device_uuid,
                    client_event_uuid: doc.client_event_uuid,
                    client_hash: doc.client_hash,
                    payload: doc.payload || {},
                    origin: 'offline_sync',
                  };
                }),
              }),
            });
            const result = await response.json();
            if (result.success) {
              accepted += result.data.accepted || 0;
              const okUuids = {};
              (result.data.results || []).forEach(function (row) {
                if (!row.error) okUuids[row.client_event_uuid] = true;
              });
              for (const doc of batch) {
                if (okUuids[doc.client_event_uuid]) {
                  await this._markSynced(doc);
                }
              }
            }
          } catch (error) {
            console.warn('EVV push flush failed', error);
          }
        }
        console.log('EVV queue flushed:', accepted, 'events accepted');
        return { accepted: accepted };
      } finally {
        this.flushing = false;
      }
    }

    registerBackgroundSync() {
      // Background Sync where available; iOS falls back to the
      // 'online' listener below + flush on app resume.
      if ('serviceWorker' in navigator && 'SyncManager' in window) {
        navigator.serviceWorker.ready.then(function (registration) {
          return registration.sync.register('evv-flush');
        }).catch(function () { /* unsupported — online fallback */ });
      }
    }

    // ------------------------------------------------------------
    // Geofence config cache (store 'evv_config', F.2)
    // ------------------------------------------------------------
    async cacheConfig(fsoId, config) {
      const docId = String(fsoId);
      let existing = null;
      try { existing = await this.configDb.get(docId); } catch (e) { /* new */ }
      const doc = Object.assign({ _id: docId }, config, { fso_id: fsoId });
      if (existing) doc._rev = existing._rev;
      try { await this.configDb.put(doc); } catch (e) { /* best effort */ }
    }

    async getConfig(fsoId) {
      try {
        return await this.configDb.get(String(fsoId));
      } catch (error) {
        return null;
      }
    }
  }

  window.healthEvvCanonical = {
    canonicalPayloadString: canonicalPayloadString,
    canonicalDatetime: canonicalDatetime,
    sha256Hex: sha256Hex,
    hashEvent: hashEvent,
  };
  window.healthEvvQueue = new EvvQueue();

  window.addEventListener('online', function () {
    window.healthEvvQueue.flush();
  });
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && navigator.onLine) {
      window.healthEvvQueue.flush();
    }
  });
  // Service worker message from Background Sync ('evv-flush' tag).
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function (event) {
      if (event.data && event.data.type === 'EVV_FLUSH') {
        window.healthEvvQueue.flush();
      }
    });
  }
})();
