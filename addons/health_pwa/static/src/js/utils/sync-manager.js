// Health PWA - Sync Manager for Offline Data Synchronization

class HealthSyncManager {
  constructor(databases, config) {
    this.db = databases;
    this.config = config;
    this.isOnline = navigator.onLine;
    this.syncInProgress = false;
    this.lastSyncTime = null;
    this.syncQueue = [];
    
    // Load last sync time from storage
    this.loadSyncMetadata();
    
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
      await this.db.sync.put({
        _id: 'sync_metadata',
        lastSyncTime: this.lastSyncTime,
        updatedAt: new Date().toISOString()
      });
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
      console.log('Starting full data sync...');
      
      // Step 1: Push pending changes to server
      await this.pushPendingChanges();
      
      // Step 2: Pull changes from server
      await this.pullServerChanges();
      
      // Step 3: Update sync timestamp
      this.lastSyncTime = new Date().toISOString();
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
      console.log('Starting FULL data sync (ignoring timestamps)...');
      
      // Step 1: Push pending changes to server
      await this.pushPendingChanges();
      
      // Step 2: Pull ALL changes from server (force full sync)
      await this.pullServerChanges(true); // Pass true for force full
      
      // Step 3: Update sync timestamp
      this.lastSyncTime = new Date().toISOString();
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
      
      // Send changes to server
      const response = await fetch('/health_pwa/sync/push', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          changes: this.groupChangesByModel(pendingChanges)
        })
      });
      
      const result = await response.json();
      
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
      
    } catch (error) {
      console.error('Failed to pull server changes:', error);
      throw error;
    }
  }
  
  async applyServerChanges(changes) {
    // Apply patients changes
    if (changes.patients && changes.patients.records.length > 0) {
      await this.updateLocalData('patients', changes.patients.records);
    }
    
    // Apply field service orders changes
    if (changes.field_service_orders && changes.field_service_orders.records.length > 0) {
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
      
    } catch (error) {
      console.error('Failed to get pending changes:', error);
    }
    
    return pendingChanges;
  }
  
  groupChangesByModel(changes) {
    const grouped = {
      field_service_orders: [],
      patients: []
    };
    
    for (const change of changes) {
      if (change.model === 'health.fieldservice.order') {
        grouped.field_service_orders.push(change.data);
      } else if (change.model === 'res.partner' && change.data.is_patient) {
        grouped.patients.push(change.data);
      }
    }
    
    return grouped;
  }
  
  async clearPushedChanges(changes, results) {
    for (let i = 0; i < changes.length; i++) {
      const change = changes[i];
      const result = results[i];
      
      if (result && result.success) {
        try {
          await this.db.sync.remove(change);
        } catch (error) {
          console.error('Failed to clear pushed change:', error);
        }
      }
    }
  }
  
  async queueChange(model, recordId, data, operation = 'update') {
    try {
      const changeDoc = {
        _id: `pending_${model}_${recordId}_${Date.now()}`,
        model: model,
        recordId: recordId,
        operation: operation, // create, update, delete
        data: data,
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
  
  async backgroundSync() {
    if (!this.isOnline || this.syncInProgress) {
      return;
    }
    
    try {
      await this.performSync();
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