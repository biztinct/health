// Health PWA - Storage Manager for Local Data Operations

class HealthStorageManager {
  constructor(databases) {
    this.db = databases;
    this.cache = new Map(); // In-memory cache for frequently accessed data
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes cache timeout
    
    console.log('Health Storage Manager initialized');
  }
  
  // Generic cache methods
  setCache(key, data, ttl = this.cacheTimeout) {
    this.cache.set(key, {
      data: data,
      timestamp: Date.now(),
      ttl: ttl
    });
  }
  
  getCache(key) {
    const cached = this.cache.get(key);
    if (!cached) return null;
    
    if (Date.now() - cached.timestamp > cached.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    return cached.data;
  }
  
  clearCache(pattern = null) {
    if (pattern) {
      const regex = new RegExp(pattern);
      for (const key of this.cache.keys()) {
        if (regex.test(key)) {
          this.cache.delete(key);
        }
      }
    } else {
      this.cache.clear();
    }
  }
  
  // Patient operations
  async getPatients(options = {}) {
    const cacheKey = `patients_${JSON.stringify(options)}`;
    const cached = this.getCache(cacheKey);
    if (cached) return cached;

    try {
      const {
        limit = null,  // No limit by default - load all patients
        skip = 0,
        search = '',
        status = ''
      } = options;

      // Get all patients from local database
      let result = await this.db.patients.allDocs({
        include_docs: true,
        limit: limit ? limit + skip : undefined  // undefined = load all
      });

      let patients = result.rows.map(row => row.doc).slice(skip);
      
      // Apply filters
      if (search) {
        const searchLower = search.toLowerCase();
        patients = patients.filter(patient => 
          (patient.name && patient.name.toLowerCase().includes(searchLower)) ||
          (patient.patient_code && patient.patient_code.toLowerCase().includes(searchLower)) ||
          (patient.phone && patient.phone.includes(search)) ||
          (patient.mobile && patient.mobile.includes(search))
        );
      }
      
      if (status) {
        patients = patients.filter(patient => patient.patient_status === status);
      }
      
      // Sort by name
      patients.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
      
      const response = {
        patients: patients,
        total_count: patients.length,
        has_more: false, // Local storage doesn't paginate the same way
        from_cache: true
      };
      
      this.setCache(cacheKey, response);
      return response;
      
    } catch (error) {
      console.error('Failed to get patients from storage:', error);
      return {
        patients: [],
        total_count: 0,
        has_more: false,
        error: error.message
      };
    }
  }
  
  async getPatient(patientId) {
    const cacheKey = `patient_${patientId}`;
    const cached = this.getCache(cacheKey);
    if (cached) return cached;
    
    try {
      const patient = await this.db.patients.get(patientId.toString());
      
      // Get recent orders for this patient
      const recentOrders = await this.getPatientOrders(patientId, { limit: 10 });
      
      const patientData = {
        ...patient,
        recent_orders: recentOrders.orders,
        from_cache: true
      };
      
      this.setCache(cacheKey, patientData);
      return patientData;
      
    } catch (error) {
      if (error.status === 404) {
        return null;
      }
      console.error('Failed to get patient from storage:', error);
      throw error;
    }
  }
  
  async savePatient(patientData) {
    try {
      const docId = patientData.id.toString();
      
      // Get existing document to preserve _rev if it exists
      let existingDoc = null;
      try {
        existingDoc = await this.db.patients.get(docId);
      } catch (error) {
        // Document doesn't exist, that's fine
      }
      
      const doc = {
        ...patientData,
        _id: docId,
        _rev: existingDoc?._rev,
        updatedAt: new Date().toISOString()
      };
      
      const result = await this.db.patients.put(doc);
      
      // Clear related cache
      this.clearCache('patient_');
      this.clearCache('patients_');
      
      return result;
      
    } catch (error) {
      console.error('Failed to save patient:', error);
      throw error;
    }
  }
  
  // Booking operations
  async getFieldServiceOrders(options = {}) {
    const cacheKey = `orders_${JSON.stringify(options)}`;
    const cached = this.getCache(cacheKey);
    if (cached) return cached;

    try {
      const {
        limit = null,  // No limit by default - load all orders
        skip = 0,
        teamId = null,
        stage = '',
        patientId = null,
        dateFrom = null,
        dateTo = null
      } = options;

      // Load all documents or up to specified limit
      let result = await this.db.orders.allDocs({
        include_docs: true,
        limit: limit ? limit + skip : undefined  // undefined = load all
      });

      let orders = result.rows.map(row => row.doc).slice(skip);
      
      // Apply filters
      if (teamId) {
        orders = orders.filter(order => order.team_id === teamId);
      }
      
      if (stage) {
        orders = orders.filter(order => order.stage_name === stage);
      }
      
      if (patientId) {
        orders = orders.filter(order => order.patient_id === patientId);
      }
      
      if (dateFrom) {
        orders = orders.filter(order => 
          order.scheduled_datetime && order.scheduled_datetime >= dateFrom
        );
      }
      
      if (dateTo) {
        orders = orders.filter(order => 
          order.scheduled_datetime && order.scheduled_datetime <= dateTo
        );
      }
      
      // Sort by scheduled date (most recent first)
      orders.sort((a, b) => {
        const dateA = new Date(a.scheduled_datetime || 0);
        const dateB = new Date(b.scheduled_datetime || 0);
        return dateB - dateA;
      });
      
      const response = {
        orders: orders,
        total_count: orders.length,
        has_more: false,
        from_cache: true
      };
      
      this.setCache(cacheKey, response);
      return response;
      
    } catch (error) {
      console.error('Failed to get orders from storage:', error);
      return {
        orders: [],
        total_count: 0,
        has_more: false,
        error: error.message
      };
    }
  }
  
  async getFieldServiceOrder(orderId) {
    const cacheKey = `order_${orderId}`;
    const cached = this.getCache(cacheKey);
    if (cached) return cached;
    
    try {
      const order = await this.db.orders.get(orderId.toString());
      
      // Get patient details if patient_id exists
      let patient = null;
      if (order.patient_id) {
        try {
          patient = await this.getPatient(order.patient_id);
        } catch (error) {
          console.warn('Failed to get patient details for order:', error);
        }
      }
      
      const orderData = {
        ...order,
        patient_details: patient,
        from_cache: true
      };
      
      this.setCache(cacheKey, orderData);
      return orderData;
      
    } catch (error) {
      if (error.status === 404) {
        return null;
      }
      console.error('Failed to get order from storage:', error);
      throw error;
    }
  }
  
  async saveFieldServiceOrder(orderData) {
    try {
      const docId = orderData.id.toString();
      
      // Get existing document to preserve _rev if it exists
      let existingDoc = null;
      try {
        existingDoc = await this.db.orders.get(docId);
      } catch (error) {
        // Document doesn't exist, that's fine
      }
      
      const doc = {
        ...orderData,
        _id: docId,
        _rev: existingDoc?._rev,
        updatedAt: new Date().toISOString()
      };
      
      const result = await this.db.orders.put(doc);
      
      // Clear related cache
      this.clearCache('order_');
      this.clearCache('orders_');
      
      return result;
      
    } catch (error) {
      console.error('Failed to save order:', error);
      throw error;
    }
  }
  
  async getPatientOrders(patientId, options = {}) {
    return this.getFieldServiceOrders({
      ...options,
      patientId: patientId
    });
  }
  
  // Teams operations
  async getTeams() {
    const cacheKey = 'teams_all';
    const cached = this.getCache(cacheKey);
    if (cached) return cached;
    
    try {
      const result = await this.db.teams.allDocs({
        include_docs: true
      });
      
      const teams = result.rows.map(row => row.doc);
      
      // Sort by name
      teams.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
      
      const response = {
        teams: teams,
        from_cache: true
      };
      
      this.setCache(cacheKey, response);
      return response;
      
    } catch (error) {
      console.error('Failed to get teams from storage:', error);
      return {
        teams: [],
        error: error.message
      };
    }
  }
  
  // Service Types operations
  async getServiceTypes() {
    const cacheKey = 'service_types_all';
    const cached = this.getCache(cacheKey);
    if (cached) return cached;
    
    try {
      const result = await this.db.serviceTypes.allDocs({
        include_docs: true
      });
      
      const serviceTypes = result.rows.map(row => row.doc);
      
      // Sort by name
      serviceTypes.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
      
      const response = {
        service_types: serviceTypes,
        from_cache: true
      };
      
      this.setCache(cacheKey, response);
      return response;
      
    } catch (error) {
      console.error('Failed to get service types from storage:', error);
      return {
        service_types: [],
        error: error.message
      };
    }
  }
  
  // Facilities operations
  async getFacilities() {
    const cacheKey = 'facilities_all';
    const cached = this.getCache(cacheKey);
    if (cached) return cached;
    
    try {
      const result = await this.db.facilities.allDocs({
        include_docs: true
      });
      
      const facilities = result.rows.map(row => row.doc);
      
      // Sort by name
      facilities.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
      
      const response = {
        facilities: facilities,
        from_cache: true
      };
      
      this.setCache(cacheKey, response);
      return response;
      
    } catch (error) {
      console.error('Failed to get facilities from storage:', error);
      return {
        facilities: [],
        error: error.message
      };
    }
  }
  
  // User profile operations
  async saveUserProfile(userData) {
    try {
      const doc = {
        _id: 'user_profile',
        ...userData,
        updatedAt: new Date().toISOString()
      };
      
      // Try to get existing document to preserve _rev
      try {
        const existing = await this.db.sync.get('user_profile');
        doc._rev = existing._rev;
      } catch (error) {
        // Document doesn't exist, that's fine
      }
      
      await this.db.sync.put(doc);
      this.clearCache('user_profile');
      
    } catch (error) {
      console.error('Failed to save user profile:', error);
      throw error;
    }
  }
  
  async getUserProfile() {
    const cacheKey = 'user_profile';
    const cached = this.getCache(cacheKey);
    if (cached) return cached;
    
    try {
      const profile = await this.db.sync.get('user_profile');
      this.setCache(cacheKey, profile);
      return profile;
      
    } catch (error) {
      if (error.status === 404) {
        return null;
      }
      console.error('Failed to get user profile:', error);
      throw error;
    }
  }
  
  // Statistics and dashboard data
  async getDashboardStats() {
    const cacheKey = 'dashboard_stats';
    const cached = this.getCache(cacheKey);
    if (cached) return cached;
    
    try {
      // Get counts from local databases
      const patientsResult = await this.db.patients.allDocs();
      const ordersResult = await this.db.orders.allDocs({ include_docs: true });
      const teamsResult = await this.db.teams.allDocs();
      
      const activePatients = patientsResult.total_rows;
      const totalOrders = ordersResult.total_rows;
      
      // Count pending orders
      const pendingOrders = ordersResult.rows.filter(row => {
        const doc = row.doc;
        return doc.stage_name && !['Completed', 'Cancelled'].includes(doc.stage_name);
      }).length;
      
      // Count today's orders
      const today = new Date().toISOString().split('T')[0];
      const todayOrders = ordersResult.rows.filter(row => {
        const doc = row.doc;
        if (!doc.scheduled_datetime) return false;
        const orderDate = doc.scheduled_datetime.split('T')[0];
        return orderDate === today;
      }).length;
      
      const stats = {
        active_patients: activePatients,
        total_orders: totalOrders,
        pending_orders: pendingOrders,
        today_orders: todayOrders,
        user_teams_count: teamsResult.total_rows,
        last_updated: new Date().toISOString(),
        from_cache: true
      };
      
      this.setCache(cacheKey, stats, 2 * 60 * 1000); // Cache for 2 minutes
      return stats;
      
    } catch (error) {
      console.error('Failed to get dashboard stats:', error);
      return {
        active_patients: 0,
        total_orders: 0,
        pending_orders: 0,
        today_orders: 0,
        user_teams_count: 0,
        error: error.message
      };
    }
  }
  
  // Search functionality
  async searchData(query, types = ['patients', 'orders']) {
    const results = {
      patients: [],
      orders: [],
      total: 0
    };
    
    if (!query || query.length < 2) {
      return results;
    }
    
    const queryLower = query.toLowerCase();
    
    try {
      // Search patients
      if (types.includes('patients')) {
        const patientsResult = await this.db.patients.allDocs({ include_docs: true });
        results.patients = patientsResult.rows
          .map(row => row.doc)
          .filter(patient => 
            (patient.name && patient.name.toLowerCase().includes(queryLower)) ||
            (patient.patient_code && patient.patient_code.toLowerCase().includes(queryLower)) ||
            (patient.phone && patient.phone.includes(query)) ||
            (patient.mobile && patient.mobile.includes(query))
          )
          .slice(0, 10); // Limit results
      }
      
      // Search orders
      if (types.includes('orders')) {
        const ordersResult = await this.db.orders.allDocs({ include_docs: true });
        results.orders = ordersResult.rows
          .map(row => row.doc)
          .filter(order => 
            (order.name && order.name.toLowerCase().includes(queryLower)) ||
            (order.patient_name && order.patient_name.toLowerCase().includes(queryLower)) ||
            (order.description && order.description.toLowerCase().includes(queryLower))
          )
          .slice(0, 10); // Limit results
      }
      
      results.total = results.patients.length + results.orders.length;
      
    } catch (error) {
      console.error('Search failed:', error);
      results.error = error.message;
    }
    
    return results;
  }
  
  // Database management
  async clearAllData() {
    try {
      // Clear all databases
      await Promise.all([
        this.db.patients.destroy(),
        this.db.orders.destroy(),
        this.db.teams.destroy(),
        this.db.serviceTypes.destroy(),
        this.db.facilities.destroy()
      ]);
      
      // Clear cache
      this.clearCache();
      
      console.log('All local data cleared');
      
    } catch (error) {
      console.error('Failed to clear data:', error);
      throw error;
    }
  }
  
  async getStorageInfo() {
    try {
      const info = {
        patients: await this.db.patients.info(),
        orders: await this.db.orders.info(),
        teams: await this.db.teams.info(),
        serviceTypes: await this.db.serviceTypes.info(),
        facilities: await this.db.facilities.info(),
        sync: await this.db.sync.info()
      };
      
      let totalDocs = 0;
      let totalSize = 0;
      
      for (const [dbName, dbInfo] of Object.entries(info)) {
        totalDocs += dbInfo.doc_count;
        // Estimate size (PouchDB doesn't provide exact size)
        totalSize += dbInfo.doc_count * 1000; // Rough estimate
      }
      
      return {
        databases: info,
        totalDocuments: totalDocs,
        estimatedSize: totalSize,
        estimatedSizeMB: Math.round(totalSize / 1024 / 1024 * 100) / 100
      };
      
    } catch (error) {
      console.error('Failed to get storage info:', error);
      return null;
    }
  }
}

// Export for global use
window.HealthStorageManager = HealthStorageManager;
console.log('Health Storage Manager loaded');