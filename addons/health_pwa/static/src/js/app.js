// Health PWA - Vue.js 3 Main Application

// Global app state and utilities
window.healthPWA = {
  config: window.healthPWAConfig || {},
  db: null,
  syncManager: null,
  storageManager: null,
  isOnline: navigator.onLine,
  installPrompt: null,
  
  // Notification system
  notifications: [],
  
  // App lifecycle methods
  init: function() {
    console.log('Health PWA initializing...', this.config);
    
    // Initialize PouchDB
    this.initDatabase();
    
    // Initialize sync manager
    this.initSyncManager();
    
    // Initialize storage manager
    this.initStorageManager();
    
    // Setup event listeners
    this.setupEventListeners();
    
    // Initialize Vue app
    this.initVueApp();
  },
  
  initDatabase: function() {
    try {
      // Initialize PouchDB databases for offline storage
      this.db = {
        patients: new PouchDB('health_patients'),
        orders: new PouchDB('health_orders'),
        teams: new PouchDB('health_teams'),
        serviceTypes: new PouchDB('health_service_types'),
        facilities: new PouchDB('health_facilities'),
        sync: new PouchDB('health_sync_meta')
      };
      
      console.log('PouchDB databases initialized');
    } catch (error) {
      console.error('Failed to initialize databases:', error);
    }
  },
  
  initSyncManager: function() {
    if (window.HealthSyncManager) {
      this.syncManager = new window.HealthSyncManager(this.db, this.config);
    }
  },
  
  initStorageManager: function() {
    if (window.HealthStorageManager) {
      this.storageManager = new window.HealthStorageManager(this.db);
    }
  },
  
  setupEventListeners: function() {
    // Online/offline status
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.notifyOnlineStatus(true);
      if (this.syncManager) {
        this.syncManager.syncWhenOnline();
      }
    });
    
    window.addEventListener('offline', () => {
      this.isOnline = false;
      this.notifyOnlineStatus(false);
    });
    
    // Service Worker messages
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', this.handleServiceWorkerMessage);
    }
    
    // App visibility change
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.syncManager) {
        this.syncManager.backgroundSync();
      }
    });
  },
  
  initVueApp: function() {
    const { createApp, ref, reactive, computed, onMounted, onUnmounted } = Vue;
    
    // Main Vue application
    const HealthApp = {
      setup() {
        // Reactive state
        const state = reactive({
          isLoading: true,
          currentRoute: 'dashboard',
          user: null,
          isOnline: window.healthPWA.isOnline,
          syncStatus: 'idle', // idle, syncing, completed, error
          notifications: [],
          bottomNavVisible: true
        });
        
        // Computed properties
        const isAuthenticated = computed(() => state.user !== null);
        const hasNotifications = computed(() => state.notifications.length > 0);
        
        // Navigation methods
        const navigate = (route, params = {}) => {
          state.currentRoute = route;
          // Update URL without page reload
          const url = params.id ? `#/${route}/${params.id}` : `#/${route}`;
          window.history.pushState({}, '', url);
          
          // Hide loading screen
          if (state.isLoading) {
            state.isLoading = false;
            document.getElementById('pwa-loading').style.display = 'none';
            document.getElementById('vue-app').style.display = 'block';
          }
        };
        
        const goBack = () => {
          window.history.back();
        };
        
        // Notification methods
        const showNotification = (message, type = 'info', duration = 5000) => {
          const notification = {
            id: Date.now(),
            message,
            type, // success, error, warning, info
            timestamp: new Date(),
            duration
          };
          
          state.notifications.push(notification);
          
          // Auto-remove notification
          setTimeout(() => {
            removeNotification(notification.id);
          }, duration);
        };
        
        const removeNotification = (id) => {
          const index = state.notifications.findIndex(n => n.id === id);
          if (index > -1) {
            state.notifications.splice(index, 1);
          }
        };
        
        // Data methods
        const loadUserData = async () => {
          try {
            const response = await fetch('/health_pwa/api/user/profile');
            const data = await response.json();
            
            if (data.success) {
              state.user = data.data;
            } else {
              console.error('Failed to load user data:', data.error);
            }
          } catch (error) {
            console.error('Error loading user data:', error);
            // Try to load from offline storage
            if (window.healthPWA.storageManager) {
              const userData = await window.healthPWA.storageManager.getUserProfile();
              if (userData) {
                state.user = userData;
                showNotification('Using cached user data (offline)', 'warning');
              }
            }
          }
        };
        
        const syncData = async (forceFull = false) => {
          if (!window.healthPWA.syncManager) return;
          
          state.syncStatus = 'syncing';
          showNotification('Syncing data...', 'info', 2000);
          
          try {
            if (forceFull) {
              await window.healthPWA.syncManager.performFullSync();
            } else {
              await window.healthPWA.syncManager.performSync();
            }
            state.syncStatus = 'completed';
            showNotification('Data synced successfully', 'success');
            
            // Emit sync completed event to refresh components
            window.dispatchEvent(new CustomEvent('health-pwa-sync-completed'));
            
          } catch (error) {
            state.syncStatus = 'error';
            showNotification('Sync failed: ' + error.message, 'error');
            console.error('Sync error:', error);
          }
        };
        
        // Lifecycle hooks
        onMounted(async () => {
          console.log('Vue app mounted');
          
          // Load user data
          await loadUserData();
          
          // Initial route handling
          const hash = window.location.hash.slice(1);
          if (hash) {
            const parts = hash.split('/');
            navigate(parts[1] || 'dashboard', { id: parts[2] });
          } else {
            navigate('dashboard');
          }
          
          // Perform initial sync if online
          if (state.isOnline) {
            setTimeout(() => syncData(), 1000);
          }
        });
        
        // Handle browser back/forward
        window.addEventListener('popstate', (event) => {
          const hash = window.location.hash.slice(1);
          if (hash) {
            const parts = hash.split('/');
            state.currentRoute = parts[1] || 'dashboard';
          }
        });
        
        // Update online status from global state
        window.healthPWA.updateAppOnlineStatus = (isOnline) => {
          state.isOnline = isOnline;
        };
        
        // Global notification method
        window.healthPWA.showNotification = showNotification;
        
        return {
          state,
          isAuthenticated,
          hasNotifications,
          navigate,
          goBack,
          showNotification,
          removeNotification,
          syncData,
          loadUserData
        };
      },
      
      template: `
        <div id="health-pwa-root" class="pwa-container">
          <!-- Loading State -->
          <div v-if="state.isLoading" class="pwa-loading-screen">
            <div class="loading-container">
              <div class="loading-logo">
                <img src="/health_pwa/static/icons/icon-192.png" alt="Health Mobile" width="80" height="80"/>
              </div>
              <div class="loading-text">
                <h3>Health Mobile</h3>
                <p>Loading healthcare data...</p>
              </div>
              <div class="loading-spinner">
                <div class="spinner"></div>
              </div>
            </div>
          </div>
          
          <!-- Main App -->
          <div v-else class="app-layout">
            <!-- Mobile Header -->
            <header class="mobile-header">
              <div class="mobile-header-left">
                <button v-if="state.currentRoute !== 'dashboard'" @click="goBack" class="mobile-header-back">
                  <i class="material-icons">arrow_back</i>
                </button>
              </div>
              <h1 class="mobile-header-title">{{ getRouteTitle() }}</h1>
              <div class="mobile-header-right">
                <div v-if="!state.isOnline" class="status-dot status-offline" title="Offline"></div>
                <div v-else-if="state.syncStatus === 'syncing'" class="status-dot status-sync" title="Syncing"></div>
                <div v-else class="status-dot status-online" title="Online"></div>
              </div>
            </header>
            
            <!-- Main Content -->
            <main class="mobile-content">
              <!-- Dashboard -->
              <dashboard-view v-if="state.currentRoute === 'dashboard'" 
                :user="state.user"
                :is-online="state.isOnline"
                @navigate="navigate"
                @sync="syncData">
              </dashboard-view>
              
              <!-- Patients -->
              <patients-view v-else-if="state.currentRoute === 'patients'"
                :is-online="state.isOnline"
                @navigate="navigate">
              </patients-view>
              
              <!-- Patient Detail -->
              <patient-detail-view v-else-if="state.currentRoute === 'patient'"
                :patient-id="getCurrentRouteId()"
                :is-online="state.isOnline"
                @navigate="navigate">
              </patient-detail-view>
              
              <!-- Bookings -->
              <orders-view v-else-if="state.currentRoute === 'orders'"
                :is-online="state.isOnline"
                @navigate="navigate">
              </orders-view>

              <!-- Past Bookings -->
              <past-bookings-view v-else-if="state.currentRoute === 'past-bookings'"
                :is-online="state.isOnline"
                @navigate="navigate">
              </past-bookings-view>

              <!-- Order Detail -->
              <order-detail-view v-else-if="state.currentRoute === 'order'"
                :order-id="getCurrentRouteId()"
                :is-online="state.isOnline"
                @navigate="navigate">
              </order-detail-view>
              
              <!-- Teams -->
              <teams-view v-else-if="state.currentRoute === 'teams'"
                :is-online="state.isOnline"
                @navigate="navigate">
              </teams-view>
              
              <!-- Profile -->
              <profile-view v-else-if="state.currentRoute === 'profile'"
                :user="state.user"
                :is-online="state.isOnline"
                @sync="syncData">
              </profile-view>
              
              <!-- Default/404 -->
              <div v-else class="error-view">
                <h2>Page Not Found</h2>
                <p>The requested page could not be found.</p>
                <button @click="navigate('dashboard')" class="btn btn-primary">Go to Dashboard</button>
              </div>
            </main>
            
            <!-- Mobile Bottom Navigation -->
            <nav v-if="state.bottomNavVisible" class="mobile-nav">
              <a @click.prevent="navigate('dashboard')" 
                 class="mobile-nav-item" 
                 :class="{ active: state.currentRoute === 'dashboard' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">dashboard</i>
                </div>
                <span class="mobile-nav-label">Dashboard</span>
              </a>
              
              <a @click.prevent="navigate('patients')" 
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'patients' || state.currentRoute === 'patient' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">people</i>
                </div>
                <span class="mobile-nav-label">Patients</span>
              </a>
              
              <a @click.prevent="navigate('orders')"
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'orders' || state.currentRoute === 'order' || state.currentRoute === 'past-bookings' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">assignment</i>
                </div>
                <span class="mobile-nav-label">Orders</span>
              </a>
              
              <a @click.prevent="navigate('teams')" 
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'teams' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">group</i>
                </div>
                <span class="mobile-nav-label">Teams</span>
              </a>
              
              <a @click.prevent="navigate('profile')" 
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'profile' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">account_circle</i>
                </div>
                <span class="mobile-nav-label">Profile</span>
              </a>
            </nav>
          </div>
          
          <!-- Notifications -->
          <div class="notification-container" style="position: fixed; top: 70px; right: 1rem; z-index: 2000;">
            <transition-group name="notification" tag="div">
              <div v-for="notification in state.notifications" 
                   :key="notification.id"
                   class="notification"
                   :class="'notification-' + notification.type"
                   @click="removeNotification(notification.id)">
                <div class="notification-content">
                  <span>{{ notification.message }}</span>
                  <button class="notification-close">&times;</button>
                </div>
              </div>
            </transition-group>
          </div>
        </div>
      `,
      
      methods: {
        getRouteTitle() {
          const titles = {
            dashboard: 'Dashboard',
            patients: 'Patients',
            patient: 'Patient Details',
            orders: 'Field Orders',
            'past-bookings': 'Past Bookings',
            order: 'Order Details',
            teams: 'Teams',
            profile: 'Profile'
          };
          return titles[this.state.currentRoute] || 'Health Mobile';
        },
        
        getCurrentRouteId() {
          const hash = window.location.hash.slice(1);
          const parts = hash.split('/');
          return parts[2] ? parseInt(parts[2]) : null;
        }
      }
    };
    
    // Create and mount Vue app
    const app = createApp(HealthApp);
    
    // Register global components (will be loaded from separate files)
    this.registerComponents(app);
    
    // Mount the app
    app.mount('#vue-app');
    
    console.log('Vue app created and mounted');
  },
  
  registerComponents: function(app) {
    // Dashboard Component
    app.component('dashboard-view', {
      props: ['user', 'isOnline'],
      emits: ['navigate', 'sync'],
      setup(props, { emit }) {
        const { ref } = Vue;
        const debugInfo = ref(null);
        
        const checkDebugInfo = async () => {
          try {
            const response = await fetch('/health_pwa/sync/debug');
            const data = await response.json();
            debugInfo.value = data;
            console.log('Debug Info:', data);
            alert('Debug info logged to console. Check browser console.');
          } catch (error) {
            console.error('Failed to get debug info:', error);
            alert('Failed to get debug info: ' + error.message);
          }
        };
        
        return {
          checkDebugInfo
        };
      },
      template: `
        <div class="dashboard-view">
          <div class="dashboard-header">
            <h2>Welcome back, {{ user?.name || 'User' }}</h2>
            <p v-if="!isOnline" class="offline-notice">
              <i class="material-icons">wifi_off</i>
              Working offline
            </p>
          </div>
          
          <div class="dashboard-stats">
            <div class="stat-card patients-card" @click="$emit('navigate', 'patients')">
              <div class="stat-icon">
                <i class="material-icons">people</i>
              </div>
              <div class="stat-content">
                <h3>Patients</h3>
                <p>Manage patient records</p>
              </div>
            </div>

            <div class="stat-card orders-card" @click="$emit('navigate', 'orders')">
              <div class="stat-icon">
                <i class="material-icons">assignment</i>
              </div>
              <div class="stat-content">
                <h3>Field Orders</h3>
                <p>View service orders</p>
              </div>
            </div>

            <div class="stat-card teams-card" @click="$emit('navigate', 'teams')">
              <div class="stat-icon">
                <i class="material-icons">group</i>
              </div>
              <div class="stat-content">
                <h3>Teams</h3>
                <p>Team management</p>
              </div>
            </div>
          </div>
          
          <div class="dashboard-actions">
            <button @click="$emit('sync')" class="btn btn-primary" :disabled="!isOnline">
              <i class="material-icons">sync</i>
              Sync Data
            </button>
            <button @click="$emit('sync', true)" class="btn btn-secondary" :disabled="!isOnline" title="Force full sync of all data">
              <i class="material-icons">refresh</i>
              Force Full Sync
            </button>
            <button @click="checkDebugInfo" class="btn btn-outline" :disabled="!isOnline" title="Check server data availability">
              <i class="material-icons">bug_report</i>
              Debug Info
            </button>
          </div>
        </div>
      `
    });
    
    // Patients view with real data
    app.component('patients-view', {
      props: ['isOnline'],
      emits: ['navigate'],
      setup(props, { emit }) {
        const { ref, onMounted, computed } = Vue;
        
        const patients = ref([]);
        const searchQuery = ref('');
        const isLoading = ref(true);
        const error = ref(null);
        
        const filteredPatients = computed(() => {
          if (!searchQuery.value) return patients.value;
          const query = searchQuery.value.toLowerCase();
          return patients.value.filter(patient => 
            (patient.name && patient.name.toLowerCase().includes(query)) ||
            (patient.patient_code && patient.patient_code.toLowerCase().includes(query)) ||
            (patient.phone && patient.phone.includes(query))
          );
        });
        
        const loadPatients = async () => {
          try {
            isLoading.value = true;
            error.value = null;
            
            if (window.healthPWA?.storageManager) {
              const result = await window.healthPWA.storageManager.getPatients();
              patients.value = result.patients || [];
              console.log('Loaded patients:', patients.value.length);
            } else {
              console.error('Storage manager not available');
            }
          } catch (err) {
            console.error('Failed to load patients:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };
        
        onMounted(() => {
          loadPatients();
          
          // Listen for sync completion to refresh data
          window.addEventListener('health-pwa-sync-completed', () => {
            console.log('Sync completed, refreshing patients...');
            loadPatients();
          });
        });
        
        const formatDate = (dateStr) => {
          if (!dateStr) return 'Never';
          const date = new Date(dateStr);
          const now = new Date();
          const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
          
          if (diffDays === 0) return 'Today';
          if (diffDays === 1) return 'Yesterday';
          if (diffDays < 7) return `${diffDays} days ago`;
          return date.toLocaleDateString();
        };
        
        const viewPatient = (patientId) => {
          emit('navigate', 'patient', { id: patientId });
        };
        
        return {
          patients,
          filteredPatients,
          searchQuery,
          isLoading,
          error,
          formatDate,
          viewPatient
        };
      },
      template: `
        <div class="patients-view">
          <div class="search-container">
            <div class="search-icon">
              <i class="material-icons">search</i>
            </div>
            <input 
              type="text" 
              class="search-input" 
              placeholder="Search patients..."
              v-model="searchQuery">
          </div>
          
          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>Loading patients...</p>
          </div>
          
          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <p>Failed to load patients: {{ error }}</p>
          </div>
          
          <!-- Empty State -->
          <div v-else-if="filteredPatients.length === 0" class="empty-state">
            <div class="empty-icon">
              <i class="material-icons">people_outline</i>
            </div>
            <h3>No Patients Found</h3>
            <p v-if="searchQuery">No patients match your search criteria.</p>
            <p v-else>No patients have been synced yet.</p>
          </div>
          
          <!-- Patients List -->
          <div v-else class="list-view">
            <div 
              v-for="patient in filteredPatients" 
              :key="patient.id"
              class="list-item" 
              @click="viewPatient(patient.id)">
              <div class="list-item-avatar">
                <i class="material-icons">person</i>
              </div>
              <div class="list-item-content">
                <h4 class="list-item-title">{{ patient.name || 'Unnamed Patient' }}</h4>
                <p class="list-item-subtitle">
                  <span v-if="patient.patient_code">ID: {{ patient.patient_code }}</span>
                  <span v-if="patient.patient_code && patient.phone"> • </span>
                  <span v-if="patient.phone">{{ patient.phone }}</span>
                </p>
              </div>
              <div class="list-item-meta">
                <div class="list-item-time">{{ formatDate(patient.last_visit_date) }}</div>
                <i class="material-icons">chevron_right</i>
              </div>
            </div>
          </div>
        </div>
      `
    });
    
    app.component('patient-detail-view', {
      props: ['patientId', 'isOnline'],
      emits: ['navigate'],
      setup(props, { emit }) {
        const { ref, onMounted } = Vue;
        
        const patient = ref(null);
        const isLoading = ref(true);
        const error = ref(null);
        
        const loadPatient = async () => {
          try {
            isLoading.value = true;
            error.value = null;
            
            if (window.healthPWA?.storageManager) {
              const patientData = await window.healthPWA.storageManager.getPatient(props.patientId);
              if (patientData) {
                patient.value = patientData;
                console.log('Loaded patient details:', patientData);
              } else {
                error.value = 'Patient not found';
              }
            } else {
              error.value = 'Storage manager not available';
            }
          } catch (err) {
            console.error('Failed to load patient:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };
        
        onMounted(() => {
          loadPatient();
        });
        
        const formatDate = (dateStr) => {
          if (!dateStr) return 'Not specified';
          return new Date(dateStr).toLocaleDateString();
        };
        
        const formatAge = (age) => {
          if (!age) return 'Unknown';
          return `${age} years old`;
        };
        
        const getStatusColor = (status) => {
          switch (status) {
            case 'active': return 'success';
            case 'new': return 'info';
            case 'inactive': return 'warning';
            case 'deceased': return 'danger';
            default: return 'secondary';
          }
        };
        
        return {
          patient,
          isLoading,
          error,
          formatDate,
          formatAge,
          getStatusColor
        };
      },
      template: `
        <div class="patient-detail-view">
          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>Loading patient details...</p>
          </div>
          
          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <h3>Error Loading Patient</h3>
            <p>{{ error }}</p>
            <button @click="$emit('navigate', 'patients')" class="btn btn-primary">Back to Patients</button>
          </div>
          
          <!-- Patient Details -->
          <div v-else-if="patient" class="patient-details">
            <!-- Patient Header -->
            <div class="patient-header-card">
              <div class="patient-avatar">
                <i class="material-icons">person</i>
              </div>
              <div class="patient-header-info">
                <h2>{{ patient.name || 'Unnamed Patient' }}</h2>
                <p class="patient-code" v-if="patient.patient_code">ID: {{ patient.patient_code }}</p>
                <span :class="'badge badge-' + getStatusColor(patient.patient_status)">
                  {{ patient.patient_status || 'Unknown Status' }}
                </span>
              </div>
            </div>
            
            <!-- Patient Information Sections -->
            <div class="patient-info-sections">
              
              <!-- Basic Information -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">person</i>
                  Basic Information
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.first_name || patient.last_name">
                    <label>Full Name</label>
                    <span>{{ [patient.first_name, patient.last_name].filter(Boolean).join(' ') || 'Not specified' }}</span>
                  </div>
                  <div class="info-item" v-if="patient.birth_date">
                    <label>Date of Birth</label>
                    <span>{{ formatDate(patient.birth_date) }}</span>
                  </div>
                  <div class="info-item" v-if="patient.age">
                    <label>Age</label>
                    <span>{{ formatAge(patient.age) }}</span>
                  </div>
                  <div class="info-item" v-if="patient.gender">
                    <label>Gender</label>
                    <span>{{ patient.gender }}</span>
                  </div>
                  <div class="info-item" v-if="patient.blood_group && patient.blood_group !== 'unknown'">
                    <label>Blood Group</label>
                    <span>{{ patient.blood_group.toUpperCase() }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Contact Information -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">contact_phone</i>
                  Contact Information
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.phone">
                    <label>Phone</label>
                    <span>{{ patient.phone }}</span>
                  </div>
                  <div class="info-item" v-if="patient.mobile">
                    <label>Mobile</label>
                    <span>{{ patient.mobile }}</span>
                  </div>
                  <div class="info-item" v-if="patient.email">
                    <label>Email</label>
                    <span>{{ patient.email }}</span>
                  </div>
                  <div class="info-item" v-if="patient.street || patient.city">
                    <label>Address</label>
                    <span>{{ [patient.street, patient.city].filter(Boolean).join(', ') || 'Not specified' }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Emergency Contact -->
              <div class="info-section" v-if="patient.emergency_contact_name || patient.emergency_contact_phone">
                <h3>
                  <i class="material-icons">emergency</i>
                  Emergency Contact
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.emergency_contact_name">
                    <label>Name</label>
                    <span>{{ patient.emergency_contact_name }}</span>
                  </div>
                  <div class="info-item" v-if="patient.emergency_contact_phone">
                    <label>Phone</label>
                    <span>{{ patient.emergency_contact_phone }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Medical Information -->
              <div class="info-section" v-if="patient.allergies || patient.medical_history">
                <h3>
                  <i class="material-icons">medical_services</i>
                  Medical Information
                </h3>
                <div class="info-grid">
                  <div class="info-item full-width" v-if="patient.allergies">
                    <label>Known Allergies</label>
                    <span>{{ patient.allergies }}</span>
                  </div>
                  <div class="info-item full-width" v-if="patient.medical_history">
                    <label>Medical History</label>
                    <span>{{ patient.medical_history }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Recent Orders -->
              <div class="info-section" v-if="patient.recent_orders && patient.recent_orders.length > 0">
                <h3>
                  <i class="material-icons">assignment</i>
                  Recent Orders
                </h3>
                <div class="orders-list">
                  <div 
                    v-for="order in patient.recent_orders" 
                    :key="order.id"
                    class="order-item"
                    @click="$emit('navigate', 'order', {id: order.id})">
                    <div class="order-content">
                      <h4>{{ order.service_type_name || 'Service Order' }}</h4>
                      <p>{{ formatDate(order.scheduled_datetime) }}</p>
                    </div>
                    <div class="order-status">
                      <span :class="'badge badge-' + getStatusColor(order.state)">{{ order.state }}</span>
                      <i class="material-icons">chevron_right</i>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- Visit History -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">history</i>
                  Visit History
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.last_visit_date">
                    <label>Last Visit</label>
                    <span>{{ formatDate(patient.last_visit_date) }}</span>
                  </div>
                  <div class="info-item" v-if="patient.next_visit_date">
                    <label>Next Visit</label>
                    <span>{{ formatDate(patient.next_visit_date) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Not Found -->
          <div v-else class="error-state">
            <div class="error-icon">
              <i class="material-icons">person_off</i>
            </div>
            <h3>Patient Not Found</h3>
            <p>The requested patient could not be found.</p>
            <button @click="$emit('navigate', 'patients')" class="btn btn-primary">Back to Patients</button>
          </div>
        </div>
      `
    });
    
    app.component('orders-view', {
      props: ['isOnline'],
      emits: ['navigate'],
      setup(props, { emit }) {
        const { ref, onMounted, computed } = Vue;

        const orders = ref([]);
        const isLoading = ref(true);
        const error = ref(null);

        // Computed property to filter upcoming bookings only
        const upcomingOrders = computed(() => {
          const now = new Date();
          return orders.value.filter(order => {
            if (!order.scheduled_datetime) return false;
            const scheduledDate = new Date(order.scheduled_datetime);
            return scheduledDate >= now;
          }).sort((a, b) => {
            // Sort by scheduled_datetime ascending (earliest first)
            return new Date(a.scheduled_datetime) - new Date(b.scheduled_datetime);
          });
        });

        const loadOrders = async () => {
          try {
            isLoading.value = true;
            error.value = null;

            if (window.healthPWA?.storageManager) {
              const result = await window.healthPWA.storageManager.getFieldServiceOrders();
              orders.value = result.orders || [];
              console.log('Loaded orders:', orders.value.length);
              console.log('Upcoming orders:', upcomingOrders.value.length);
            } else {
              console.error('Storage manager not available');
            }
          } catch (err) {
            console.error('Failed to load orders:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };
        
        onMounted(() => {
          loadOrders();
          
          // Listen for sync completion to refresh data
          window.addEventListener('health-pwa-sync-completed', () => {
            console.log('Sync completed, refreshing orders...');
            loadOrders();
          });
        });
        
        const formatDateTime = (dateTimeStr) => {
          if (!dateTimeStr) return 'Unscheduled';
          const date = new Date(dateTimeStr);
          return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        };
        
        const getStatusBadgeClass = (state) => {
          switch (state) {
            case 'draft': return 'badge badge-secondary';
            case 'assigned': return 'badge badge-warning';
            case 'in_progress': return 'badge badge-primary';
            case 'completed': return 'badge badge-success';
            case 'cancelled': return 'badge badge-danger';
            default: return 'badge badge-secondary';
          }
        };
        
        const getStatusLabel = (state) => {
          switch (state) {
            case 'draft': return 'Draft';
            case 'assigned': return 'Assigned';
            case 'in_progress': return 'In Progress';
            case 'completed': return 'Completed';
            case 'cancelled': return 'Cancelled';
            default: return 'Unknown';
          }
        };
        
        const viewOrder = (orderId) => {
          emit('navigate', 'order', { id: orderId });
        };
        
        return {
          orders,
          upcomingOrders,
          isLoading,
          error,
          formatDateTime,
          getStatusBadgeClass,
          getStatusLabel,
          viewOrder
        };
      },
      template: `
        <div class="orders-view">
          <!-- View Toggle Header -->
          <div class="view-toggle-header" style="padding: 1rem; background: #FBE3E1; border: none; margin-bottom: 1rem; border-radius: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <h3 style="margin: 0; color: #333; font-weight: 600;">Upcoming Bookings</h3>
              <button @click="$emit('navigate', 'past-bookings')" class="btn btn-secondary btn-sm" style="background: #E53935; color: white; border: none; padding: 0.5rem 1rem; border-radius: 8px;">
                View Past Bookings
              </button>
            </div>
          </div>

          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>Loading field service orders...</p>
          </div>
          
          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <p>Failed to load orders: {{ error }}</p>
          </div>
          
          <!-- Empty State -->
          <div v-else-if="upcomingOrders.length === 0" class="empty-state">
            <div class="empty-icon">
              <i class="material-icons">assignment_outlined</i>
            </div>
            <h3>No Upcoming Orders</h3>
            <p v-if="orders.length === 0">No field service orders have been synced yet.</p>
            <p v-else>No upcoming bookings found. All orders are in the past.</p>
          </div>
          
          <!-- Orders List -->
          <div v-else class="list-view">
            <div
              v-for="order in upcomingOrders"
              :key="order.id"
              class="list-item"
              @click="viewOrder(order.id)">
              <div class="list-item-avatar">
                <i class="material-icons">assignment</i>
              </div>
              <div class="list-item-content">
                <h4 class="list-item-title">
                  {{ order.service_type_name || 'Service Order' }} - {{ order.patient_name || 'Unknown Patient' }}
                </h4>
                <p class="list-item-subtitle">
                  Scheduled: {{ formatDateTime(order.scheduled_datetime) }}
                </p>
              </div>
              <div class="list-item-meta">
                <span :class="getStatusBadgeClass(order.state)">{{ getStatusLabel(order.state) }}</span>
                <i class="material-icons">chevron_right</i>
              </div>
            </div>
          </div>
        </div>
      `
    });

    app.component('past-bookings-view', {
      props: ['isOnline'],
      emits: ['navigate'],
      setup(props, { emit }) {
        const { ref, onMounted, computed } = Vue;

        const orders = ref([]);
        const isLoading = ref(true);
        const error = ref(null);

        // Computed property to filter past bookings only (last 50)
        const pastOrders = computed(() => {
          const now = new Date();
          return orders.value.filter(order => {
            if (!order.scheduled_datetime) return false;
            const scheduledDate = new Date(order.scheduled_datetime);
            return scheduledDate < now;
          }).sort((a, b) => {
            // Sort by scheduled_datetime descending (most recent first)
            return new Date(b.scheduled_datetime) - new Date(a.scheduled_datetime);
          }).slice(0, 50); // Limit to last 50 past bookings
        });

        const loadOrders = async () => {
          try {
            isLoading.value = true;
            error.value = null;

            if (window.healthPWA?.storageManager) {
              const result = await window.healthPWA.storageManager.getFieldServiceOrders();
              orders.value = result.orders || [];
              console.log('Loaded orders:', orders.value.length);
              console.log('Past orders:', pastOrders.value.length);
            } else {
              console.error('Storage manager not available');
            }
          } catch (err) {
            console.error('Failed to load orders:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };

        onMounted(() => {
          loadOrders();

          // Listen for sync completion to refresh data
          window.addEventListener('health-pwa-sync-completed', () => {
            console.log('Sync completed, refreshing past orders...');
            loadOrders();
          });
        });

        const formatDateTime = (dateTimeStr) => {
          if (!dateTimeStr) return 'Unscheduled';
          const date = new Date(dateTimeStr);
          return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        };

        const getStatusBadgeClass = (state) => {
          switch (state) {
            case 'draft': return 'badge badge-secondary';
            case 'assigned': return 'badge badge-warning';
            case 'in_progress': return 'badge badge-primary';
            case 'completed': return 'badge badge-success';
            case 'cancelled': return 'badge badge-danger';
            default: return 'badge badge-secondary';
          }
        };

        const getStatusLabel = (state) => {
          switch (state) {
            case 'draft': return 'Draft';
            case 'assigned': return 'Assigned';
            case 'in_progress': return 'In Progress';
            case 'completed': return 'Completed';
            case 'cancelled': return 'Cancelled';
            default: return 'Unknown';
          }
        };

        const viewOrder = (orderId) => {
          emit('navigate', 'order', { id: orderId });
        };

        return {
          orders,
          pastOrders,
          isLoading,
          error,
          formatDateTime,
          getStatusBadgeClass,
          getStatusLabel,
          viewOrder
        };
      },
      template: `
        <div class="past-bookings-view">
          <!-- View Toggle Header -->
          <div class="view-toggle-header" style="padding: 1rem; background: #FBE3E1; border: none; margin-bottom: 1rem; border-radius: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <h3 style="margin: 0; color: #333; font-weight: 600;">Past Bookings</h3>
              <button @click="$emit('navigate', 'orders')" class="btn btn-secondary btn-sm" style="background: #E53935; color: white; border: none; padding: 0.5rem 1rem; border-radius: 8px;">
                View Upcoming
              </button>
            </div>
          </div>

          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>Loading past bookings...</p>
          </div>

          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <p>Failed to load past bookings: {{ error }}</p>
          </div>

          <!-- Empty State -->
          <div v-else-if="pastOrders.length === 0" class="empty-state">
            <div class="empty-icon">
              <i class="material-icons">history</i>
            </div>
            <h3>No Past Bookings</h3>
            <p v-if="orders.length === 0">No field service orders have been synced yet.</p>
            <p v-else>No past bookings found. All orders are upcoming.</p>
          </div>

          <!-- Past Orders List -->
          <div v-else class="list-view">
            <div
              v-for="order in pastOrders"
              :key="order.id"
              class="list-item"
              @click="viewOrder(order.id)">
              <div class="list-item-avatar">
                <i class="material-icons">assignment</i>
              </div>
              <div class="list-item-content">
                <h4 class="list-item-title">
                  {{ order.service_type_name || 'Service Order' }} - {{ order.patient_name || 'Unknown Patient' }}
                </h4>
                <p class="list-item-subtitle">
                  Scheduled: {{ formatDateTime(order.scheduled_datetime) }}
                </p>
              </div>
              <div class="list-item-meta">
                <span :class="getStatusBadgeClass(order.state)">{{ getStatusLabel(order.state) }}</span>
                <i class="material-icons">chevron_right</i>
              </div>
            </div>
          </div>
        </div>
      `
    });

    app.component('order-detail-view', {
      props: ['orderId', 'isOnline'],
      emits: ['navigate'],
      setup(props, { emit }) {
        const { ref, onMounted, computed, watch } = Vue;

        const order = ref(null);
        const isLoading = ref(true);
        const error = ref(null);
        const timerInterval = ref(null);
        const currentTime = ref(new Date());
        const showClinicalNotes = ref(false);
        const showInvoice = ref(false);
        const clinicalNotesData = ref({
          clinical_notes: '',
          diagnosis: '',
          treatment_performed: '',
          medications_prescribed: '',
          vital_signs: ''
        });
        const capturedImages = ref([]);
        const quoteData = ref(null);
        const showPaymentWizard = ref(false);
        const paymentWizardData = ref({
          payment_choice: 'pay_now',
          payment_method: 'cash',
          service_notes: '',
          create_invoice_now: true
        });

        // Computed elapsed time for timer
        const elapsedTime = computed(() => {
          if (!order.value || !order.value.actual_start_datetime) return '00:00:00';

          const startTime = new Date(order.value.actual_start_datetime);
          const endTime = order.value.actual_end_datetime ? new Date(order.value.actual_end_datetime) : currentTime.value;
          const diff = Math.floor((endTime - startTime) / 1000);

          const hours = Math.floor(diff / 3600);
          const minutes = Math.floor((diff % 3600) / 60);
          const seconds = diff % 60;

          return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        });

        const loadOrder = async () => {
          try {
            isLoading.value = true;
            error.value = null;

            if (window.healthPWA?.storageManager) {
              const orderData = await window.healthPWA.storageManager.getFieldServiceOrder(props.orderId);
              if (orderData) {
                order.value = orderData;
                console.log('Loaded order details:', orderData);

                // Load clinical notes if available
                if (orderData.clinical_notes) {
                  clinicalNotesData.value.clinical_notes = orderData.clinical_notes;
                }
                if (orderData.diagnosis) {
                  clinicalNotesData.value.diagnosis = orderData.diagnosis;
                }

                // Start timer if service is in progress
                if (orderData.state === 'in_progress' && orderData.actual_start_datetime && !orderData.actual_end_datetime) {
                  startTimer();
                }
              } else {
                error.value = 'Order not found';
              }
            } else {
              error.value = 'Storage manager not available';
            }
          } catch (err) {
            console.error('Failed to load order:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };

        const startTimer = () => {
          if (timerInterval.value) clearInterval(timerInterval.value);
          timerInterval.value = setInterval(() => {
            currentTime.value = new Date();
          }, 1000);
        };

        const stopTimer = () => {
          if (timerInterval.value) {
            clearInterval(timerInterval.value);
            timerInterval.value = null;
          }
        };

        const handleStartService = async () => {
          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot start service while offline', 'error');
            return;
          }

          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/start`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({})
            });

            const data = await response.json();
            console.log('Start service response:', data);

            if (data.success && data.data) {
              order.value.state = data.data.state;
              order.value.actual_start_datetime = data.data.actual_start_datetime;
              startTimer();
              window.healthPWA.showNotification(data.data.message || 'Service started successfully!', 'success');

              // Reload order data
              await loadOrder();
            } else {
              window.healthPWA.showNotification('Failed to start service: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Start service error:', err);
            window.healthPWA.showNotification('Error starting service: ' + err.message, 'error');
          }
        };

        const openPaymentWizard = () => {
          // Validate clinical notes are filled before allowing completion
          if (!clinicalNotesData.value.clinical_notes || !clinicalNotesData.value.clinical_notes.trim()) {
            window.healthPWA.showNotification(
              'Please fill in Clinical Notes before completing the service. Click "Clinical Notes" button to add them.',
              'warning',
              7000
            );
            return;
          }

          if (!clinicalNotesData.value.treatment_performed || !clinicalNotesData.value.treatment_performed.trim()) {
            window.healthPWA.showNotification(
              'Please fill in Treatment Performed in Clinical Notes before completing the service.',
              'warning',
              7000
            );
            return;
          }

          // Load quote data to get calculated amount (but don't show invoice modal)
          loadQuote(false);
          showPaymentWizard.value = true;
        };

        const handleCompleteService = async () => {
          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot complete service while offline', 'error');
            return;
          }

          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/complete`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                payment_choice: paymentWizardData.value.payment_choice,
                payment_method: paymentWizardData.value.payment_method,
                service_notes: paymentWizardData.value.service_notes,
                create_invoice_now: paymentWizardData.value.create_invoice_now,
                clinical_notes: clinicalNotesData.value.clinical_notes
              })
            });

            const data = await response.json();
            console.log('Complete service response:', data);

            if (data.success && data.data) {
              // Stop timer first
              stopTimer();

              // Close payment wizard
              showPaymentWizard.value = false;

              // Show success notification
              window.healthPWA.showNotification(data.data.message || 'Service completed successfully!', 'success');

              // Update local order state immediately for UI responsiveness
              order.value.state = data.data.state;
              order.value.actual_end_datetime = data.data.actual_end_datetime;
              order.value.adjusted_end_datetime = data.data.adjusted_end_datetime;

              // Update PouchDB cache with new state
              if (window.healthPWA?.storageManager) {
                try {
                  await window.healthPWA.storageManager.updateFieldServiceOrder(props.orderId, {
                    state: data.data.state,
                    actual_end_datetime: data.data.actual_end_datetime,
                    adjusted_end_datetime: data.data.adjusted_end_datetime
                  });
                } catch (dbErr) {
                  console.error('Failed to update PouchDB:', dbErr);
                }
              }

              // Reload full order data from server to get latest information
              await loadOrder();
            } else {
              window.healthPWA.showNotification('Failed to complete service: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Complete service error:', err);
            window.healthPWA.showNotification('Error completing service: ' + err.message, 'error');
          }
        };

        const saveClinicalNotes = async () => {
          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot save clinical notes while offline', 'error');
            return;
          }

          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/clinical_notes`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify(clinicalNotesData.value)
            });

            const data = await response.json();
            console.log('Clinical notes response:', data);

            if (data.success) {
              window.healthPWA.showNotification(data.data.message || 'Clinical notes saved successfully!', 'success');
              showClinicalNotes.value = false;
            } else {
              window.healthPWA.showNotification('Failed to save clinical notes: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Save clinical notes error:', err);
            window.healthPWA.showNotification('Error saving clinical notes: ' + err.message, 'error');
          }
        };

        const captureImage = () => {
          const input = document.createElement('input');
          input.type = 'file';
          input.accept = 'image/*';
          input.capture = 'environment'; // Use rear camera on mobile

          input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (!props.isOnline) {
              window.healthPWA.showNotification('Cannot upload images while offline', 'error');
              return;
            }

            try {
              const formData = new FormData();
              formData.append('image', file);

              const response = await fetch(`/health_pwa/api/fso/${props.orderId}/upload_image`, {
                method: 'POST',
                body: formData
              });

              const data = await response.json();

              if (data.success) {
                capturedImages.value.push(data.data);
                window.healthPWA.showNotification('Image uploaded successfully!', 'success');
              } else {
                window.healthPWA.showNotification('Failed to upload image: ' + data.error, 'error');
              }
            } catch (err) {
              console.error('Image upload error:', err);
              window.healthPWA.showNotification('Error uploading image: ' + err.message, 'error');
            }
          };

          input.click();
        };

        const showProductCatalog = ref(false);
        const productCatalog = ref([]);
        const productSearch = ref('');
        const editingLine = ref(null);
        const showMap = ref(false);

        const loadQuote = async (showModal = true) => {
          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot load invoice while offline', 'error');
            return;
          }

          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/quote`);
            const data = await response.json();

            if (data.success) {
              quoteData.value = data.data;
              if (showModal) {
                showInvoice.value = true;
              }
            } else {
              if (showModal) {
                window.healthPWA.showNotification('No quote found for this order', 'warning');
              }
            }
          } catch (err) {
            console.error('Load quote error:', err);
            if (showModal) {
              window.healthPWA.showNotification('Error loading quote: ' + err.message, 'error');
            }
          }
        };

        const loadProductCatalog = async () => {
          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot load catalog while offline', 'error');
            return;
          }

          try {
            const searchParam = productSearch.value ? `&search=${encodeURIComponent(productSearch.value)}` : '';
            const response = await fetch(`/health_pwa/api/products/catalog?limit=50${searchParam}`);
            const data = await response.json();

            if (data.success) {
              productCatalog.value = data.data.products || [];
            }
          } catch (err) {
            console.error('Load catalog error:', err);
          }
        };

        const addProductToQuote = async (product) => {
          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/quote/update`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                action: 'add',
                line_data: {
                  product_id: product.id,
                  quantity: 1.0
                }
              })
            });

            const data = await response.json();

            if (data.success && data.data.quote) {
              quoteData.value = data.data.quote;
              showProductCatalog.value = false;
              window.healthPWA.showNotification('Product added successfully!', 'success');
            } else {
              window.healthPWA.showNotification('Failed to add product: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Add product error:', err);
            window.healthPWA.showNotification('Error adding product: ' + err.message, 'error');
          }
        };

        const updateQuoteLine = async (lineId, quantity, price) => {
          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/quote/update`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                action: 'update',
                line_data: {
                  line_id: lineId,
                  quantity: quantity,
                  price: price
                }
              })
            });

            const data = await response.json();

            if (data.success && data.data.quote) {
              quoteData.value = data.data.quote;
              editingLine.value = null;
              window.healthPWA.showNotification('Line updated successfully!', 'success');
            } else {
              window.healthPWA.showNotification('Failed to update line: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Update line error:', err);
            window.healthPWA.showNotification('Error updating line: ' + err.message, 'error');
          }
        };

        const removeQuoteLine = async (lineId) => {
          if (!confirm('Remove this line from the quote?')) return;

          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/quote/update`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                action: 'remove',
                line_data: {
                  line_id: lineId
                }
              })
            });

            const data = await response.json();

            if (data.success && data.data.quote) {
              quoteData.value = data.data.quote;
              window.healthPWA.showNotification('Line removed successfully!', 'success');
            } else {
              window.healthPWA.showNotification('Failed to remove line: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Remove line error:', err);
            window.healthPWA.showNotification('Error removing line: ' + err.message, 'error');
          }
        };

        const openMapLocation = () => {
          if (!order.value || !order.value.address) {
            window.healthPWA.showNotification('No address available', 'warning');
            return;
          }

          // Show embedded map modal
          showMap.value = true;
        };

        const formatDateTime = (dateTimeStr) => {
          if (!dateTimeStr) return 'Not set';
          const date = new Date(dateTimeStr);
          return date.toLocaleString();
        };

        const getStatusLabel = (state) => {
          switch (state) {
            case 'draft': return 'Draft';
            case 'confirmed': return 'Confirmed';
            case 'assigned': return 'Assigned';
            case 'in_progress': return 'In Progress';
            case 'completed': return 'Completed';
            case 'cancelled': return 'Cancelled';
            default: return 'Unknown';
          }
        };

        const getStatusBadgeClass = (state) => {
          switch (state) {
            case 'draft': return 'badge badge-secondary';
            case 'confirmed': return 'badge badge-info';
            case 'assigned': return 'badge badge-warning';
            case 'in_progress': return 'badge badge-primary';
            case 'completed': return 'badge badge-success';
            case 'cancelled': return 'badge badge-danger';
            default: return 'badge badge-secondary';
          }
        };

        onMounted(() => {
          loadOrder();
        });

        // Cleanup timer on unmount
        watch(() => order.value, () => {
          return () => stopTimer();
        });

        return {
          order,
          isLoading,
          error,
          elapsedTime,
          showClinicalNotes,
          showInvoice,
          clinicalNotesData,
          capturedImages,
          quoteData,
          showProductCatalog,
          productCatalog,
          productSearch,
          editingLine,
          showMap,
          showPaymentWizard,
          paymentWizardData,
          handleStartService,
          openPaymentWizard,
          handleCompleteService,
          saveClinicalNotes,
          captureImage,
          loadQuote,
          loadProductCatalog,
          addProductToQuote,
          updateQuoteLine,
          removeQuoteLine,
          openMapLocation,
          formatDateTime,
          getStatusLabel,
          getStatusBadgeClass
        };
      },
      template: `
        <div class="order-detail-view">
          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>Loading order details...</p>
          </div>

          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <h3>Error Loading Order</h3>
            <p>{{ error }}</p>
            <button @click="$emit('navigate', 'orders')" class="btn btn-primary">Back to Orders</button>
          </div>

          <!-- Order Details -->
          <div v-else-if="order" class="order-details">
            <!-- Client Header - Mobilesample clean design -->
            <div class="order-client-header">
              <h2>{{ order.patient?.name || order.patient_name || 'Unknown Client' }}</h2>
              <div class="order-client-meta">
                <span v-if="order.name" class="order-number">
                  📋 {{ order.name }}
                </span>
                <span v-if="order.name && order.state" class="separator">•</span>
                <span v-if="order.state"
                      class="badge"
                      :class="'status-' + order.state.replace('_', '-')">
                  {{ getStatusLabel(order.state) }}
                </span>
              </div>
            </div>

              <!-- Timer Card - Mobilesample clean design (no icon) -->
              <div v-if="order.state === 'in_progress' && order.actual_start_datetime"
                   class="order-timer-card">
                <!-- Timer Header: Label on left, Live indicator on right -->
                <div class="timer-header">
                  <span class="timer-label">Elapsed Time</span>
                  <div class="timer-status">
                    <div class="status-indicator"></div>
                    <span>Live</span>
                  </div>
                </div>

                <!-- Timer Display: Large number only -->
                <div class="timer-display">
                  <span class="timer-value">{{ elapsedTime }}</span>
                </div>

                <!-- Started Timestamp: Bottom with divider -->
                <div v-if="order.actual_start_datetime" class="timer-started">
                  <div class="timer-started-dot"></div>
                  <span class="timer-started-text">Started {{ formatDateTime(order.actual_start_datetime) }}</span>
                </div>
              </div>
            </div>

            <!-- Action Buttons -->
            <div class="order-actions">
              <!-- Location Map Button -->
              <button @click="openMapLocation"
                      class="btn btn-action btn-location"
                      :disabled="!order.address">
                <i class="material-icons">location_on</i>
                <span>Location Map</span>
              </button>

              <!-- Start Service Button (only for assigned state) -->
              <button v-if="order.state === 'assigned' || order.state === 'confirmed'"
                      @click="handleStartService"
                      class="btn btn-action btn-start"
                      :disabled="!isOnline">
                <i class="material-icons">play_arrow</i>
                <span>Start Service</span>
              </button>

              <!-- Clinical Notes Button -->
              <button @click="showClinicalNotes = true"
                      class="btn btn-action btn-clinical"
                      :disabled="order.state !== 'in_progress'">
                <i class="material-icons">note_add</i>
                <span>Clinical Notes</span>
              </button>

              <!-- Invoice Button -->
              <button @click="loadQuote"
                      class="btn btn-action btn-invoice"
                      :disabled="!isOnline">
                <i class="material-icons">receipt</i>
                <span>Invoice</span>
              </button>

              <!-- Complete Service Button (only for in_progress state) -->
              <button v-if="order.state === 'in_progress'"
                      @click="openPaymentWizard"
                      class="btn btn-action btn-complete"
                      :disabled="!isOnline">
                <i class="material-icons">check_circle</i>
                <span>Complete Service</span>
              </button>
            </div>

            <!-- Order Information Sections -->
            <div class="order-info-sections">

              <!-- Patient Information -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">person</i>
                  Patient Information
                </h3>
                <div class="info-grid">
                  <div class="info-item">
                    <label>Name</label>
                    <span>{{ order.patient_name || 'Not specified' }}</span>
                  </div>
                  <div class="info-item" v-if="order.patient_details">
                    <label>Age / Gender</label>
                    <span>{{ order.patient_details.age || '-' }} / {{ order.patient_details.gender || '-' }}</span>
                  </div>
                  <div class="info-item" v-if="order.phone">
                    <label>Phone</label>
                    <span>{{ order.phone }}</span>
                  </div>
                  <div class="info-item full-width" v-if="order.address">
                    <label>Address</label>
                    <span>{{ order.address }}</span>
                  </div>
                  <div class="info-item full-width" v-if="order.patient_details && order.patient_details.allergies">
                    <label>Allergies</label>
                    <span class="text-danger">{{ order.patient_details.allergies }}</span>
                  </div>
                </div>
              </div>

              <!-- Service Information -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">medical_services</i>
                  Service Information
                </h3>
                <div class="info-grid">
                  <div class="info-item">
                    <label>Scheduled Time</label>
                    <span>{{ formatDateTime(order.scheduled_datetime) }}</span>
                  </div>
                  <div class="info-item" v-if="order.estimated_duration">
                    <label>Estimated Duration</label>
                    <span>{{ order.estimated_duration }} hours</span>
                  </div>
                  <div class="info-item" v-if="order.team">
                    <label>Team</label>
                    <span>{{ order.team }}</span>
                  </div>
                  <div class="info-item" v-if="order.priority">
                    <label>Priority</label>
                    <span :class="order.priority === '3' ? 'text-danger' : ''">
                      {{ order.priority === '3' ? 'High' : order.priority === '2' ? 'Medium' : 'Low' }}
                    </span>
                  </div>
                  <div class="info-item full-width" v-if="order.description">
                    <label>Description</label>
                    <span>{{ order.description }}</span>
                  </div>
                </div>
              </div>

              <!-- Service Status -->
              <div class="info-section" v-if="order.actual_start_datetime">
                <h3>
                  <i class="material-icons">schedule</i>
                  Service Status
                </h3>
                <div class="info-grid">
                  <div class="info-item">
                    <label>Started At</label>
                    <span>{{ formatDateTime(order.actual_start_datetime) }}</span>
                  </div>
                  <div class="info-item" v-if="order.actual_end_datetime">
                    <label>Completed At</label>
                    <span>{{ formatDateTime(order.actual_end_datetime) }}</span>
                  </div>
                  <div class="info-item" v-if="order.actual_end_datetime">
                    <label>Duration</label>
                    <span>{{ order.actual_duration || '0' }} hours</span>
                  </div>
                  <div class="info-item" v-else>
                    <label>Elapsed Time</label>
                    <span class="text-primary">{{ elapsedTime }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Clinical Notes Modal -->
            <div v-if="showClinicalNotes" class="modal-overlay" @click.self="showClinicalNotes = false">
              <div class="modal-content clinical-notes-modal">
                <div class="modal-header">
                  <h3>
                    <i class="material-icons">note_add</i>
                    Clinical Notes
                  </h3>
                  <button @click="showClinicalNotes = false" class="modal-close">
                    <i class="material-icons">close</i>
                  </button>
                </div>
                <div class="modal-body">
                  <div class="form-group">
                    <label>Clinical Observations</label>
                    <textarea v-model="clinicalNotesData.clinical_notes"
                              rows="4"
                              placeholder="Enter clinical observations and notes..."></textarea>
                  </div>
                  <div class="form-group">
                    <label>Diagnosis</label>
                    <textarea v-model="clinicalNotesData.diagnosis"
                              rows="3"
                              placeholder="Enter diagnosis..."></textarea>
                  </div>
                  <div class="form-group">
                    <label>Treatment Performed</label>
                    <textarea v-model="clinicalNotesData.treatment_performed"
                              rows="3"
                              placeholder="Describe treatment provided..."></textarea>
                  </div>
                  <div class="form-group">
                    <label>Medications Prescribed</label>
                    <textarea v-model="clinicalNotesData.medications_prescribed"
                              rows="2"
                              placeholder="List medications..."></textarea>
                  </div>
                  <div class="form-group">
                    <label>Vital Signs</label>
                    <textarea v-model="clinicalNotesData.vital_signs"
                              rows="2"
                              placeholder="Blood pressure, temperature, heart rate..."></textarea>
                  </div>

                  <!-- Image Capture Section -->
                  <div class="form-group">
                    <label>Clinical Images</label>
                    <button @click="captureImage" class="btn btn-secondary btn-block">
                      <i class="material-icons">camera_alt</i>
                      Capture Image
                    </button>

                    <!-- Captured Images Display -->
                    <div v-if="capturedImages.length > 0" class="captured-images">
                      <div v-for="(image, index) in capturedImages" :key="index" class="captured-image">
                        <img :src="image.url" :alt="image.filename" />
                        <span>{{ image.filename }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="modal-footer">
                  <button @click="showClinicalNotes = false" class="btn btn-secondary">Cancel</button>
                  <button @click="saveClinicalNotes" class="btn btn-primary" :disabled="!isOnline">
                    <i class="material-icons">save</i>
                    Save Notes
                  </button>
                </div>
              </div>
            </div>

            <!-- Invoice Modal -->
            <div v-if="showInvoice" class="modal-overlay" @click.self="showInvoice = false">
              <div class="modal-content invoice-modal">
                <div class="modal-header">
                  <h3>
                    <i class="material-icons">receipt</i>
                    Invoice / Quote
                  </h3>
                  <button @click="showInvoice = false" class="modal-close">
                    <i class="material-icons">close</i>
                  </button>
                </div>
                <div class="modal-body" v-if="quoteData">
                  <div class="invoice-header">
                    <div class="invoice-info">
                      <h4>{{ quoteData.name }}</h4>
                      <span :class="'badge badge-' + (quoteData.state === 'sale' ? 'success' : 'info')">
                        {{ quoteData.state }}
                      </span>
                    </div>
                    <button @click="showProductCatalog = true; loadProductCatalog()" class="btn btn-sm btn-primary">
                      <i class="material-icons">add_shopping_cart</i>
                      Add Product
                    </button>
                  </div>

                  <div class="invoice-lines">
                    <table class="invoice-table">
                      <thead>
                        <tr>
                          <th>Product</th>
                          <th>Qty</th>
                          <th>Price</th>
                          <th>Total</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="line in quoteData.order_lines" :key="line.id">
                          <td>{{ line.product_name }}</td>
                          <td>
                            <input v-if="editingLine === line.id"
                                   type="number"
                                   :value="line.quantity"
                                   @change="line._newQty = $event.target.value"
                                   class="input-sm"
                                   min="0.01"
                                   step="0.01" />
                            <span v-else>{{ line.quantity }}</span>
                          </td>
                          <td>
                            <input v-if="editingLine === line.id"
                                   type="number"
                                   :value="line.unit_price"
                                   @change="line._newPrice = $event.target.value"
                                   class="input-sm"
                                   min="0"
                                   step="0.01" />
                            <span v-else>{{ line.unit_price.toLocaleString() }}</span>
                          </td>
                          <td>{{ line.total.toLocaleString() }}</td>
                          <td>
                            <div class="btn-group-sm">
                              <button v-if="editingLine === line.id"
                                      @click="updateQuoteLine(line.id, line._newQty || line.quantity, line._newPrice || line.unit_price)"
                                      class="btn btn-xs btn-success"
                                      title="Save">
                                <i class="material-icons">check</i>
                              </button>
                              <button v-if="editingLine === line.id"
                                      @click="editingLine = null"
                                      class="btn btn-xs btn-secondary"
                                      title="Cancel">
                                <i class="material-icons">close</i>
                              </button>
                              <button v-if="editingLine !== line.id"
                                      @click="editingLine = line.id"
                                      class="btn btn-xs btn-info"
                                      title="Edit">
                                <i class="material-icons">edit</i>
                              </button>
                              <button @click="removeQuoteLine(line.id)"
                                      class="btn btn-xs btn-danger"
                                      title="Delete">
                                <i class="material-icons">delete</i>
                              </button>
                            </div>
                          </td>
                        </tr>
                      </tbody>
                      <tfoot>
                        <tr>
                          <td colspan="4">Subtotal</td>
                          <td>{{ quoteData.amount_untaxed.toLocaleString() }}</td>
                        </tr>
                        <tr>
                          <td colspan="4">Tax</td>
                          <td>{{ quoteData.amount_tax.toLocaleString() }}</td>
                        </tr>
                        <tr class="total-row">
                          <td colspan="4"><strong>Total</strong></td>
                          <td><strong>{{ quoteData.amount_total.toLocaleString() }} {{ quoteData.currency }}</strong></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>
                <div class="modal-footer">
                  <button @click="showInvoice = false" class="btn btn-secondary">Close</button>
                </div>
              </div>
            </div>

            <!-- Product Catalog Modal -->
            <div v-if="showProductCatalog" class="modal-overlay" @click.self="showProductCatalog = false">
              <div class="modal-content catalog-modal">
                <div class="modal-header">
                  <h3>
                    <i class="material-icons">shopping_cart</i>
                    Product Catalog
                  </h3>
                  <button @click="showProductCatalog = false" class="modal-close">
                    <i class="material-icons">close</i>
                  </button>
                </div>
                <div class="modal-body">
                  <!-- Search Box -->
                  <div class="search-container mb-3">
                    <div class="search-icon">
                      <i class="material-icons">search</i>
                    </div>
                    <input
                      type="text"
                      class="search-input"
                      placeholder="Search products..."
                      v-model="productSearch"
                      @input="loadProductCatalog">
                  </div>

                  <!-- Product List -->
                  <div class="product-list">
                    <div v-for="product in productCatalog"
                         :key="product.id"
                         class="product-item"
                         @click="addProductToQuote(product)">
                      <div class="product-info">
                        <h4>{{ product.name }}</h4>
                        <p v-if="product.code">Code: {{ product.code }}</p>
                        <p class="product-price">{{ product.price.toLocaleString() }} {{ product.currency }}</p>
                      </div>
                      <button class="btn btn-sm btn-primary">
                        <i class="material-icons">add</i>
                      </button>
                    </div>
                  </div>

                  <div v-if="productCatalog.length === 0" class="empty-state">
                    <i class="material-icons">inventory_2</i>
                    <p>No products found</p>
                  </div>
                </div>
                <div class="modal-footer">
                  <button @click="showProductCatalog = false" class="btn btn-secondary">Close</button>
                </div>
              </div>
            </div>

            <!-- Map Modal -->
            <div v-if="showMap" class="modal-overlay" @click.self="showMap = false">
              <div class="modal-content map-modal">
                <div class="modal-header">
                  <h3>
                    <i class="material-icons">map</i>
                    Location Map
                  </h3>
                  <button @click="showMap = false" class="modal-close">
                    <i class="material-icons">close</i>
                  </button>
                </div>
                <div class="modal-body map-container">
                  <div class="address-display">
                    <i class="material-icons">place</i>
                    <span>{{ order.address }}</span>
                  </div>
                  <iframe
                    :src="'https://www.google.com/maps?q=' + encodeURIComponent(order.address) + '&output=embed'"
                    width="100%"
                    height="400"
                    style="border:0;"
                    allowfullscreen=""
                    loading="lazy"
                    referrerpolicy="no-referrer-when-downgrade">
                  </iframe>
                  <div class="map-actions">
                    <a :href="'https://www.google.com/maps/dir/?api=1&destination=' + encodeURIComponent(order.address)"
                       target="_blank"
                       class="btn btn-primary">
                      <i class="material-icons">directions</i>
                      Get Directions
                    </a>
                  </div>
                </div>
                <div class="modal-footer">
                  <button @click="showMap = false" class="btn btn-secondary">Close</button>
                </div>
              </div>
            </div>

            <!-- Payment Wizard Modal -->
            <div v-if="showPaymentWizard" class="modal-overlay" @click.self="showPaymentWizard = false">
              <div class="modal-content payment-wizard-modal" style="max-width: 600px;">
                <div class="modal-header">
                  <h3>
                    <i class="material-icons">payment</i>
                    Complete Service - Payment Collection
                  </h3>
                  <button @click="showPaymentWizard = false" class="modal-close">
                    <i class="material-icons">close</i>
                  </button>
                </div>
                <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                  <!-- Service Summary -->
                  <div class="form-section">
                    <h4 style="font-size: 14px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 12px;">Service Summary</h4>
                    <div class="info-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                      <div class="info-item">
                        <label style="font-size: 12px; color: #999;">Booking</label>
                        <span style="font-size: 14px; color: #333;">{{ order.name }}</span>
                      </div>
                      <div class="info-item">
                        <label style="font-size: 12px; color: #999;">Patient</label>
                        <span style="font-size: 14px; color: #333;">{{ order.patient_name }}</span>
                      </div>
                      <div class="info-item">
                        <label style="font-size: 12px; color: #999;">Calculated Invoice Amount</label>
                        <span style="font-size: 14px; color: #333;">{{ quoteData ? quoteData.amount_total.toLocaleString() + ' ' + quoteData.currency : 'N/A' }}</span>
                      </div>
                      <div class="info-item">
                        <label style="font-size: 12px; color: #999;">Final Invoice Amount</label>
                        <span style="font-size: 14px; font-weight: 600; color: #667eea;">{{ quoteData ? quoteData.amount_total.toLocaleString() + ' ' + quoteData.currency : 'N/A' }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Payment Collection -->
                  <div class="form-section" style="margin-top: 20px;">
                    <h4 style="font-size: 14px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 12px;">💰 Payment Collection</h4>
                    <div class="form-group">
                      <label style="display: flex; align-items: center; padding: 12px; border: 2px solid #e1e8ed; border-radius: 8px; margin-bottom: 8px; cursor: pointer;">
                        <input type="radio" v-model="paymentWizardData.payment_choice" value="pay_now" style="margin-right: 10px;">
                        <span style="font-weight: 500;">Pay Now - Collect Payment Immediately</span>
                      </label>
                      <label style="display: flex; align-items: center; padding: 12px; border: 2px solid #e1e8ed; border-radius: 8px; cursor: pointer;">
                        <input type="radio" v-model="paymentWizardData.payment_choice" value="pay_later" style="margin-right: 10px;">
                        <span style="font-weight: 500;">Pay Later - Send Invoice for Later Collection</span>
                      </label>
                    </div>

                    <!-- Payment Method (shown only for Pay Now) -->
                    <div v-if="paymentWizardData.payment_choice === 'pay_now'" class="form-group" style="margin-top: 16px;">
                      <label style="font-size: 12px; font-weight: 600; color: #333; margin-bottom: 8px; display: block;">Payment Method</label>
                      <select v-model="paymentWizardData.payment_method" class="form-control" style="padding: 10px; border: 1px solid #ddd; border-radius: 6px; width: 100%;">
                        <option value="cash">Cash</option>
                        <option value="bank_transfer">Bank Transfer</option>
                        <option value="credit_card">Credit Card</option>
                        <option value="qr_code">QR Code Payment</option>
                        <option value="prepaid">Prepaid Service Package</option>
                        <option value="other">Other Method</option>
                      </select>
                    </div>
                  </div>

                  <!-- Service Notes -->
                  <div class="form-section" style="margin-top: 20px;">
                    <h4 style="font-size: 14px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 12px;">📝 Service Notes</h4>
                    <div class="form-group">
                      <textarea v-model="paymentWizardData.service_notes"
                                rows="3"
                                placeholder="Additional notes about service delivery, patient condition, payment collection, etc."
                                style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px;"></textarea>
                    </div>
                  </div>

                  <!-- Invoice Processing -->
                  <div class="form-section" style="margin-top: 20px;">
                    <h4 style="font-size: 14px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 12px;">📋 Invoice Processing</h4>
                    <div class="form-group">
                      <label style="display: flex; align-items: center; cursor: pointer;">
                        <input type="checkbox" v-model="paymentWizardData.create_invoice_now" checked style="margin-right: 10px;">
                        <span style="font-weight: 500;">Create Invoice Now</span>
                      </label>
                    </div>
                  </div>
                </div>
                <div class="modal-footer">
                  <button @click="showPaymentWizard = false" class="btn btn-secondary">Cancel</button>
                  <button @click="handleCompleteService" class="btn btn-primary" :disabled="!isOnline">
                    <i class="material-icons">check_circle</i>
                    Complete Service
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      `
    });
    
    app.component('teams-view', {
      props: ['isOnline'],
      emits: ['navigate'],
      template: `
        <div class="teams-view">
          <h2>Teams</h2>
          <p>Team management interface will be implemented here.</p>
        </div>
      `
    });
    
    app.component('profile-view', {
      props: ['user', 'isOnline'],
      emits: ['sync'],
      template: `
        <div class="profile-view">
          <div class="profile-header">
            <div class="profile-avatar">
              <i class="material-icons">account_circle</i>
            </div>
            <h2>{{ user?.name || 'User' }}</h2>
            <p>{{ user?.email || 'No email' }}</p>
          </div>
          <div class="profile-actions">
            <button @click="$emit('sync')" class="btn btn-primary" :disabled="!isOnline">
              <i class="material-icons">sync</i>
              Sync Data
            </button>
          </div>
        </div>
      `
    });
  },
  
  handleServiceWorkerMessage: function(event) {
    const message = event.data;
    
    switch (message.type) {
      case 'BACKGROUND_SYNC':
        console.log('Background sync triggered by service worker');
        if (this.syncManager) {
          this.syncManager.backgroundSync();
        }
        break;
        
      case 'UPDATE_AVAILABLE':
        this.showNotification('App update available. Refresh to update.', 'info');
        break;
        
      default:
        console.log('Unknown service worker message:', message);
    }
  },
  
  notifyUpdate: function() {
    this.showNotification('New version available! Please refresh the app.', 'info');
  },
  
  notifyOnlineStatus: function(isOnline) {
    if (this.updateAppOnlineStatus) {
      this.updateAppOnlineStatus(isOnline);
    }
    
    const message = isOnline ? 'Back online - syncing data...' : 'Working offline';
    const type = isOnline ? 'success' : 'warning';
    this.showNotification(message, type);
  },
  
  showNotification: function(message, type = 'info') {
    if (window.healthPWA.showNotification) {
      window.healthPWA.showNotification(message, type);
    } else {
      console.log(`[${type.toUpperCase()}] ${message}`);
    }
  }
};

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  // Small delay to ensure all external libraries are loaded
  setTimeout(function() {
    window.healthPWA.init();
  }, 100);
});

console.log('Health PWA app.js loaded successfully');
