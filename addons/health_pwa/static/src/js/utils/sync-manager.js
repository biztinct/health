// Health PWA - Sync Manager for Offline Data Synchronization

class HealthSyncManager {
  constructor(databases, config) {
    this.db = databases;
    this.config = config;
    this.isOnline = navigator.onLine;
    this.syncInProgress = false;
    this.lastSyncTime = null;
    this.syncQueue = [];
    // FSO ids whose offline action was rejected in the last push (state
    // conflict / access denied) — app.js reads this after sync to toast +
    // refetch (pwa-offline-actions §2.5).
    this.lastRejectedActionFsoIds = [];
    
    // Load last sync time from storage, THEN run the one-time scope-purge
    // migration (pwa-sync-delta phase) once metadata is available. Keep the
    // promise: syncs must await it, or the shell's ~1s auto-sync can race the
    // purge (a delta finishing AFTER the purge would persist its watermark
    // over the nulled lastSyncTime and the full scoped re-pull never happens).
    this.migrationDone = this.loadSyncMetadata().then(() => this.runScopePurgeMigration());

    console.log('Health Sync Manager initialized');
  }
  
  async loadSyncMetadata() {
    try {
      const metadata = await this.db.sync.get('sync_metadata');
      this.lastSyncTime = metadata.lastSyncTime;
    } catch (error) {
      // First run - no sync metadata exists
      console.log('No previous sync metadata found');
    }
  }
  
  async saveSyncMetadata() {
    try {
      // PouchDB upsert: a put without the current _rev 409s on every run
      // after the first, so lastSyncTime never persists and every sync does a
      // full pull. Read the existing doc first and carry its _rev.
      const doc = {
        _id: 'sync_metadata',
        lastSyncTime: this.lastSyncTime,
        updatedAt: new Date().toISOString()
      };
      try {
        const existing = await this.db.sync.get('sync_metadata');
        doc._rev = existing._rev;
      } catch (getErr) {
        // 404 on first write is expected — leave _rev unset so put creates it.
        if (getErr && getErr.status !== 404) {
          throw getErr;
        }
      }
      await this.db.sync.put(doc);
    } catch (error) {
      console.error('Failed to save sync metadata:', error);
    }
  }
  
  async performSync() {
    if (this.syncInProgress) {
      console.log('Sync already in progress, skipping...');
      return;
    }
    
    if (!this.isOnline) {
      throw new Error('Cannot sync while offline');
    }
    
    this.syncInProgress = true;

    try {
      // One-time scope purge first: never let a delta interleave with (or
      // outlive) the migration — syncInProgress is already set, so no other
      // caller can slip in while we wait.
      if (this.migrationDone) {
        await this.migrationDone;
      }

      console.log('Starting full data sync...');

      // Step 1: Push pending changes to server
      await this.pushPendingChanges();
      
      // Step 2: Pull changes from server
      const pullResult = await this.pullServerChanges();

      // Step 2b: GC orphan patient docs (pwa-cache-hygiene). Runs AFTER
      // applyServerChanges succeeded (inside pullServerChanges). Skips itself on
      // a capped pull — order absence is not proof of de-scope when truncated.
      await this.gcOrphanPatients(this._pullWasCapped(pullResult));

      // Step 3: Update sync timestamp — prefer the server-authoritative
      // watermark over the (drifting) device clock; fall back for old servers.
      this.lastSyncTime = (pullResult && pullResult.watermark) || new Date().toISOString();
      await this.saveSyncMetadata();

      console.log('Sync completed successfully');
      
    } catch (error) {
      console.error('Sync failed:', error);
      throw error;
    } finally {
      this.syncInProgress = false;
    }
  }

  async performFullSync() {
    if (this.syncInProgress) {
      console.log('Sync already in progress, skipping...');
      return;
    }
    
    if (!this.isOnline) {
      throw new Error('Cannot sync while offline');
    }
    
    this.syncInProgress = true;

    try {
      // Same migration gate as performSync (see comment there).
      if (this.migrationDone) {
        await this.migrationDone;
      }

      console.log('Starting FULL data sync (ignoring timestamps)...');
      
      // Step 1: Push pending changes to server
      await this.pushPendingChanges();
      
      // Step 2: Pull ALL changes from server (force full sync)
      const pullResult = await this.pullServerChanges(true); // Pass true for force full

      // Step 2b: GC orphan patient docs (pwa-cache-hygiene). Same skip-when-
      // capped interlock as performSync — a force-full pull for an owner/ops
      // device (scope = all orders) trips the cap and must NOT GC.
      await this.gcOrphanPatients(this._pullWasCapped(pullResult));

      // Step 3: Update sync timestamp — prefer the server watermark.
      this.lastSyncTime = (pullResult && pullResult.watermark) || new Date().toISOString();
      await this.saveSyncMetadata();

      console.log('Full sync completed successfully');
      
    } catch (error) {
      console.error('Full sync failed:', error);
      throw error;
    } finally {
      this.syncInProgress = false;
    }
  }
  
  async pushPendingChanges() {
    console.log('Pushing pending changes to server...');
    
    try {
      // Get pending changes from local queue
      const pendingChanges = await this.getPendingChanges();
      
      if (pendingChanges.length === 0) {
        console.log('No pending changes to push');
        return;
      }
      
      // Send changes to server. The route is type='jsonrpc': the payload MUST
      // ride the JSON-RPC params envelope or the server sees empty kwargs and
      // the push silently no-ops.
      const response = await fetch('/health_pwa/sync/push', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          jsonrpc: '2.0',
          method: 'call',
          params: {
            changes: this.groupChangesByModel(pendingChanges)
          }
        })
      });

      const rpc = await response.json();
      const result = rpc.result || rpc;

      if (result.success) {
        console.log(`Pushed ${pendingChanges.length} changes to server`);
        // Clear successfully pushed changes
        await this.clearPushedChanges(pendingChanges, result.results);
      } else {
        throw new Error(result.error || 'Failed to push changes');
      }
      
    } catch (error) {
      console.error('Failed to push changes:', error);
      throw error;
    }
  }
  
  async pullServerChanges(forceFull = false) {
    console.log('Pulling changes from server...');
    
    try {
      let url = '/health_pwa/sync/changes';
      const params = new URLSearchParams();
      
      if (forceFull) {
        params.append('force_full', 'true');
        console.log('Forcing full sync - ignoring timestamps');
      } else if (this.lastSyncTime) {
        params.append('since', this.lastSyncTime);
      }
      
      if (params.toString()) {
        url += '?' + params.toString();
      }
      
      const response = await fetch(url);
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || 'Failed to get server changes');
      }
      
      const changes = data.changes;
      console.log(`Received ${data.total_changes} changes from server`);
      
      // Apply changes to local databases
      await this.applyServerChanges(changes);

      // Return the parsed body so the caller can adopt the server watermark.
      return data;

    } catch (error) {
      console.error('Failed to pull server changes:', error);
      throw error;
    }
  }

  async runScopePurgeMigration() {
    // One-time cache purge for the sync-scope cutover (pwa-sync-delta phase).
    // Pre-scope devices cached EVERY patient (allergies / medical_history) and
    // every order; wipe orders + patients ONCE so the next pull re-populates
    // only the caller's scoped set. This purge is the actual field privacy
    // remediation for legacy caches.
    try {
      if (localStorage.getItem('health_pwa_scope_v') === '2') {
        return;
      }

      for (const dbName of ['orders', 'patients']) {
        const db = this.db[dbName];
        if (!db) {
          continue;
        }
        // allDocs -> remove loop. Do NOT db.destroy() — the handles are shared
        // with app.js and destroy() would invalidate them (fact 9).
        const all = await db.allDocs();
        for (const row of all.rows) {
          try {
            await db.remove(row.id, row.value.rev);
          } catch (removeErr) {
            // Ignore per-doc conflicts; the flag stays unset on a hard throw
            // so the whole migration retries next load.
          }
        }
      }

      // Force a full scoped re-pull on the next sync.
      this.lastSyncTime = null;
      await this.saveSyncMetadata();
      localStorage.setItem('health_pwa_scope_v', '2');
      console.log('health_pwa sync: scope-purge migration complete (orders + patients wiped)');
    } catch (error) {
      // Do NOT set the flag on failure — retry on the next app load.
      console.error('health_pwa sync: scope-purge migration failed, will retry', error);
    }
  }
  
  async applyServerChanges(changes) {
    // Apply patients changes
    if (changes.patients && changes.patients.records.length > 0) {
      await this.updateLocalData('patients', changes.patients.records);
    }
    
    // Apply field service orders changes
    if (changes.field_service_orders && changes.field_service_orders.records.length > 0) {
      // The server caps DATA upserts at 500 rows and now says so authoritatively
      // via the additive `capped` flag (pwa-cache-hygiene). Fall back to the
      // upsert-row count for an old server that never sends the flag. The
      // records list also carries id-only is_deleted removals, which are
      // uncapped and must not trip a spurious warning.
      const upsertCount = changes.field_service_orders.records.filter(
        (r) => !r.is_deleted).length;
      if (changes.field_service_orders.capped || upsertCount >= 500) {
        console.warn('health_pwa sync: order cap hit (500) — older orders not cached offline');
      }
      await this.updateLocalData('orders', changes.field_service_orders.records);
    }
    
    // Apply teams changes
    if (changes.teams && changes.teams.records.length > 0) {
      await this.updateLocalData('teams', changes.teams.records);
    }
    
    // Apply service types changes
    if (changes.service_types && changes.service_types.records.length > 0) {
      await this.updateLocalData('serviceTypes', changes.service_types.records);
    }
    
    // Apply facilities changes
    if (changes.facilities && changes.facilities.records.length > 0) {
      await this.updateLocalData('facilities', changes.facilities.records);
    }
  }
  
  _pullWasCapped(pullResult) {
    // True iff the server truncated the FSO upsert set (additive `capped`
    // flag from _get_fso_changes). An old server never sends it -> falsy.
    return !!(pullResult && pullResult.changes
      && pullResult.changes.field_service_orders
      && pullResult.changes.field_service_orders.capped);
  }

  async gcOrphanPatients(wasCapped) {
    // Client-side patient GC (pwa-cache-hygiene phase). A cached patient doc
    // whose id is no longer referenced by ANY cached order is deleted after a
    // successful, NON-capped sync. This is the actual fix for de-scoped
    // PATIENTS lingering on devices: server-side de-scoping happens with no
    // patient-row write (a nurse is de-assigned, an order ages past the 90-day
    // horizon), so no write-window feed could catch it — but the order cache
    // IS authoritative (orders get correct G-scoped removals), so patients
    // follow it referentially. Never throws: a GC failure must not fail sync.
    try {
      // Interlock (§0 item 3, BINDING): a capped pull truncated the order set,
      // so order absence is NOT proof of de-scope. Skipping GC here is what
      // keeps owner/ops devices (scope = all orders -> cap fires) from deleting
      // valid patients.
      if (wasCapped) {
        console.log('health_pwa sync: GC skipped (capped) — order pull truncated, patient set not authoritative');
        return;
      }

      const patientsDb = this.db.patients;
      const ordersDb = this.db.orders;
      if (!patientsDb || !ordersDb) {
        return;
      }

      // referenced = the set of patient_id integers across all cached orders.
      const referenced = new Set();
      const orderRows = await ordersDb.allDocs({ include_docs: true });
      for (const row of orderRows.rows) {
        const pid = row.doc && row.doc.patient_id;
        if (pid !== null && pid !== undefined) {
          referenced.add(Number(pid));
        }
      }

      // Remove every cached patient whose id is no longer referenced. Per-doc
      // try/catch keeps a single conflict (a concurrent write bumped _rev) from
      // aborting the sweep; the next GC pass retries it.
      let removed = 0;
      const patientRows = await patientsDb.allDocs();
      for (const row of patientRows.rows) {
        if (referenced.has(Number(row.id))) {
          continue;
        }
        try {
          await patientsDb.remove(row.id, row.value.rev);
          removed += 1;
        } catch (removeErr) {
          // conflict-safe: skip and let the next sweep retry.
        }
      }
      console.log(`health_pwa sync: patient GC removed ${removed} orphan doc(s)`);
    } catch (error) {
      // A GC failure must NEVER fail the sync (§0 item 3 / design item 4).
      console.error('health_pwa sync: patient GC failed (non-fatal)', error);
    }
  }

  async updateLocalData(dbName, records) {
    try {
      const db = this.db[dbName];
      if (!db) {
        console.error(`Database ${dbName} not found`);
        return;
      }
      
      for (const record of records) {
        if (record.is_deleted) {
          // Handle deletions
          try {
            const existingDoc = await db.get(record.id.toString());
            await db.remove(existingDoc);
            console.log(`Deleted ${dbName} record ${record.id}`);
          } catch (error) {
            // Record doesn't exist locally, ignore
          }
        } else {
          // Handle updates/inserts
          const docId = record.id.toString();
          
          try {
            // Try to get existing document to preserve _rev
            const existingDoc = await db.get(docId);
            const updatedDoc = {
              ...record,
              _id: docId,
              _rev: existingDoc._rev,
              syncedAt: new Date().toISOString()
            };
            await db.put(updatedDoc);
          } catch (error) {
            // Document doesn't exist, create new
            const newDoc = {
              ...record,
              _id: docId,
              syncedAt: new Date().toISOString()
            };
            await db.put(newDoc);
          }
        }
      }
      
      console.log(`Updated ${records.length} ${dbName} records locally`);
      
    } catch (error) {
      console.error(`Failed to update local ${dbName}:`, error);
    }
  }
  
  async getPendingChanges() {
    const pendingChanges = [];
    
    try {
      // Get pending changes from sync queue
      const queueDocs = await this.db.sync.allDocs({
        startkey: 'pending_',
        endkey: 'pending_\ufff0',
        include_docs: true
      });
      
      for (const row of queueDocs.rows) {
        pendingChanges.push(row.doc);
      }

      // allDocs returns docs in KEY order, not time order (fact 8). Actions
      // must replay before the field writes that follow them in real time and
      // before the pull, so sort the combined list by `timestamp` ascending.
      pendingChanges.sort((a, b) => {
        const ta = (a && a.timestamp) || '';
        const tb = (b && b.timestamp) || '';
        return ta < tb ? -1 : ta > tb ? 1 : 0;
      });

    } catch (error) {
      console.error('Failed to get pending changes:', error);
    }

    return pendingChanges;
  }

  groupChangesByModel(changes) {
    const grouped = {
      field_service_orders: [],
      patients: [],
      // Offline visit actions (pwa-offline-actions §2.2). Additive key; an old
      // server ignores it, a new one processes it FIRST.
      actions: []
    };

    for (const change of changes) {
      if (change.model === 'health.pwa.action') {
        grouped.actions.push({
          action_type: change.actionType,
          fso_id: change.recordId,
          client_action_uuid: change.clientActionUuid,
          client_ref: change.clientRef,
          claimed_at: change.claimedAt,
          payload: change.data || {}
        });
      } else if (change.model === 'health.fieldservice.order') {
        // Pass client_ref through (§2.4 — additive; server echoes it back).
        grouped.field_service_orders.push({ ...change.data, client_ref: change.clientRef });
      } else if (change.model === 'res.partner' && change.data.is_patient) {
        grouped.patients.push({ ...change.data, client_ref: change.clientRef });
      }
    }

    return grouped;
  }

  async clearPushedChanges(changes, results) {
    const resultList = results || [];
    // Ref-based acknowledgement (pwa-offline-actions §2.4): map each queued doc
    // to its result by client_ref (server results interleave models, so the
    // old index-based mapping misaligns). Clear a doc iff its result succeeded
    // OR it is terminally rejected (state_conflict / Access denied / Order not
    // found — retrying can never succeed; app.js surfaces a toast + refetch).
    const hasRefs = resultList.some(
      (r) => r && r.client_ref !== undefined && r.client_ref !== null);

    if (hasRefs) {
      // Surfaced to app.js after 'health-pwa-sync-completed' so a rejected
      // offline action toasts + refetches the affected booking (§2.5). Reset
      // each batch.
      this.lastRejectedActionFsoIds = [];
      const byRef = {};
      for (const r of resultList) {
        if (r && r.client_ref !== undefined && r.client_ref !== null) {
          byRef[r.client_ref] = r;
        }
      }
      for (const change of changes) {
        const result = byRef[change.clientRef];
        if (!result) continue;
        const rejectedAction = result.success === false &&
          (result.error === 'state_conflict' || result.error === 'Access denied'
           || result.error === 'Order not found');
        if (result.success || rejectedAction) {
          try {
            await this.db.sync.remove(change);
            if (rejectedAction && change.model === 'health.pwa.action'
                && change.recordId != null) {
              this.lastRejectedActionFsoIds.push(change.recordId);
            }
          } catch (error) {
            console.error('Failed to clear pushed change:', error);
          }
        }
      }
      return;
    }

    // Legacy fallback: no result carried a client_ref (old server) — clear by
    // index, success-only, exactly as before.
    for (let i = 0; i < changes.length; i++) {
      const change = changes[i];
      const result = resultList[i];

      if (result && result.success) {
        try {
          await this.db.sync.remove(change);
        } catch (error) {
          console.error('Failed to clear pushed change:', error);
        }
      }
    }
  }
  
  // Generate a UUID for offline-action idempotency / client_ref (crypto when
  // available, else an RFC-4122-ish fallback so old WebViews still work).
  _genUuid() {
    try {
      if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
      }
    } catch (e) { /* fall through */ }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  async queueChange(model, recordId, data, operation = 'update') {
    try {
      // Every queued doc carries a clientRef == its _id so the server can echo
      // it back per-result (pwa-offline-actions §2.4) — the client then clears
      // exactly the docs that succeeded, regardless of result order.
      const id = `pending_${model}_${recordId}_${Date.now()}`;
      const changeDoc = {
        _id: id,
        model: model,
        recordId: recordId,
        operation: operation, // create, update, delete
        data: data,
        clientRef: id,
        timestamp: new Date().toISOString(),
        retryCount: 0
      };

      await this.db.sync.put(changeDoc);
      console.log(`Queued ${operation} for ${model} ${recordId}`);

      // Try to sync immediately if online
      if (this.isOnline && !this.syncInProgress) {
        setTimeout(() => this.backgroundSync(), 1000);
      }

    } catch (error) {
      console.error('Failed to queue change:', error);
    }
  }

  // Queue an offline VISIT ACTION (pwa-offline-actions §2.5). Clones the
  // health_evv offline pattern: a client-side idempotency uuid + the device's
  // claimed timestamp, replayed idempotently by /health_pwa/sync/push. Returns
  // the queued doc _id (also the clientRef) so the caller can track it.
  async queueAction(actionType, fsoId, payload) {
    try {
      const id = `pending_action_${Date.now()}_${this._genUuid()}`;
      const changeDoc = {
        _id: id,
        model: 'health.pwa.action',
        actionType: actionType,
        recordId: fsoId,
        clientActionUuid: this._genUuid(),
        clientRef: id,
        claimedAt: new Date().toISOString(),
        data: payload || {},
        timestamp: new Date().toISOString(),
        retryCount: 0
      };

      await this.db.sync.put(changeDoc);
      console.log(`Queued action ${actionType} for FSO ${fsoId}`);

      if (this.isOnline && !this.syncInProgress) {
        setTimeout(() => this.backgroundSync(), 1000);
      }

      return id;
    } catch (error) {
      console.error('Failed to queue action:', error);
    }
  }

  // Return the set of FSO ids that currently have a queued (unsynced) action
  // (pwa-offline-actions §2.5 — drives the "Pending sync" badge). Cleared
  // naturally as clearPushedChanges removes the docs post-sync.
  async getPendingActionFsoIds() {
    const ids = new Set();
    try {
      const rows = await this.db.sync.allDocs({
        startkey: 'pending_action_',
        endkey: 'pending_action_\ufff0',
        include_docs: true
      });
      for (const row of rows.rows) {
        if (row.doc && row.doc.recordId != null) {
          ids.add(row.doc.recordId);
        }
      }
    } catch (error) {
      console.error('Failed to read pending actions:', error);
    }
    return ids;
  }

  // Optimistically patch a locally-cached order doc (pwa-offline-actions §2.5).
  // Reuses updateLocalData's _rev-preserving put so a reopen offline keeps the
  // optimistic state. Non-fatal: a missing doc is simply skipped.
  async patchLocalOrder(fsoId, patch) {
    try {
      const db = this.db.orders;
      if (!db) return;
      const docId = String(fsoId);
      const existing = await db.get(docId);
      await db.put({ ...existing, ...patch, _id: docId, _rev: existing._rev });
    } catch (error) {
      // Order not cached locally (offline-only device) — skip silently.
    }
  }
  
  async backgroundSync() {
    if (!this.isOnline || this.syncInProgress) {
      return;
    }

    try {
      await this.performSync();
      // The reconnect/visibility/queue drains all route through here, and the
      // root shell only dispatches this event from its own syncData() — so a
      // background drain must announce itself too, or the "Pending sync" badge
      // and rejected-action toast never fire until a manual sync or reload
      // (pwa-offline-actions review fix).
      window.dispatchEvent(new CustomEvent('health-pwa-sync-completed'));
    } catch (error) {
      console.error('Background sync failed:', error);
      // Don't throw error for background sync failures
    }
  }
  
  async syncWhenOnline() {
    if (!this.isOnline) {
      return;
    }
    
    console.log('Device back online, performing sync...');
    
    // Delay sync slightly to allow connection to stabilize
    setTimeout(() => {
      this.backgroundSync();
    }, 2000);
  }
  
  // Manual sync trigger for user-initiated sync
  async manualSync() {
    return this.performSync();
  }
  
  // Get sync status for UI
  getSyncStatus() {
    return {
      isOnline: this.isOnline,
      syncInProgress: this.syncInProgress,
      lastSyncTime: this.lastSyncTime,
      hasPendingChanges: this.syncQueue.length > 0
    };
  }
  
  // Update field service order
  async updateFieldServiceOrder(orderId, updateData) {
    await this.queueChange('health.fieldservice.order', orderId, updateData, 'update');
  }
  
  // Update patient (limited fields allowed from mobile)
  async updatePatient(patientId, updateData) {
    // Filter to only allowed fields for mobile updates
    const allowedFields = ['phone', 'mobile', 'next_visit_date'];
    const filteredData = {};
    
    for (const field of allowedFields) {
      if (updateData.hasOwnProperty(field)) {
        filteredData[field] = updateData[field];
      }
    }
    
    if (Object.keys(filteredData).length > 0) {
      await this.queueChange('res.partner', patientId, filteredData, 'update');
    }
  }
  
  // Reset sync state (for troubleshooting)
  async resetSyncState() {
    try {
      // Clear all pending changes
      const pendingDocs = await this.db.sync.allDocs({
        startkey: 'pending_',
        endkey: 'pending_\ufff0'
      });
      
      for (const row of pendingDocs.rows) {
        await this.db.sync.remove(row.id, row.value.rev);
      }
      
      // Reset sync metadata
      this.lastSyncTime = null;
      await this.saveSyncMetadata();
      
      console.log('Sync state reset completed');
      
    } catch (error) {
      console.error('Failed to reset sync state:', error);
    }
  }
  
  // Force full resync
  async forceFullSync() {
    this.lastSyncTime = null;
    return this.performSync();
  }
}

// Export for global use
window.HealthSyncManager = HealthSyncManager;
console.log('Health Sync Manager loaded');