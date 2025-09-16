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
              
              <!-- Field Service Orders -->
              <orders-view v-else-if="state.currentRoute === 'orders'"
                :is-online="state.isOnline"
                @navigate="navigate">
              </orders-view>
              
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
                 :class="{ active: state.currentRoute === 'orders' || state.currentRoute === 'order' }">
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
            <div class="stat-card" @click="$emit('navigate', 'patients')">
              <div class="stat-icon">
                <i class="material-icons">people</i>
              </div>
              <div class="stat-content">
                <h3>Patients</h3>
                <p>Manage patient records</p>
              </div>
            </div>
            
            <div class="stat-card" @click="$emit('navigate', 'orders')">
              <div class="stat-icon">
                <i class="material-icons">assignment</i>
              </div>
              <div class="stat-content">
                <h3>Field Orders</h3>
                <p>View service orders</p>
              </div>
            </div>
            
            <div class="stat-card" @click="$emit('navigate', 'teams')">
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
        
        const loadOrders = async () => {
          try {
            isLoading.value = true;
            error.value = null;
            
            if (window.healthPWA?.storageManager) {
              const result = await window.healthPWA.storageManager.getFieldServiceOrders();
              orders.value = result.orders || [];
              console.log('Loaded orders:', orders.value.length);
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
          <div v-else-if="orders.length === 0" class="empty-state">
            <div class="empty-icon">
              <i class="material-icons">assignment_outlined</i>
            </div>
            <h3>No Orders Found</h3>
            <p>No field service orders have been synced yet.</p>
          </div>
          
          <!-- Orders List -->
          <div v-else class="list-view">
            <div 
              v-for="order in orders" 
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
      template: `
        <div class="order-detail-view">
          <div class="order-header">
            <h2>Order Details</h2>
            <p>ID: {{ orderId }}</p>
          </div>
          <div class="order-info">
            <p>Detailed order information will be loaded here.</p>
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