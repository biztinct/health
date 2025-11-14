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
          currentRoute: 'today',
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
            navigate(parts[1] || 'today', { id: parts[2] });
          } else {
            navigate('today');
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
            state.currentRoute = parts[1] || 'today';
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
                <button v-if="state.currentRoute !== 'today'" @click="goBack" class="mobile-header-back">
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
              <!-- Today -->
              <today-view v-if="state.currentRoute === 'today'"
                :user="state.user"
                :is-online="state.isOnline"
                @navigate="navigate"
                @sync="syncData">
              </today-view>
              
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
                <button @click="navigate('today')" class="btn btn-primary">Go to Today</button>
              </div>
            </main>
            
            <!-- Mobile Bottom Navigation -->
            <nav v-if="state.bottomNavVisible" class="mobile-nav">
              <a @click.prevent="navigate('today')"
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'today' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">calendar_today</i>
                </div>
                <span class="mobile-nav-label">Booking</span>
              </a>

              <a @click.prevent="navigate('patients')"
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'patients' || state.currentRoute === 'patient' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">people</i>
                </div>
                <span class="mobile-nav-label">Patients</span>
              </a>

              <a @click.prevent="navigate('call')"
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'call' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">call</i>
                </div>
                <span class="mobile-nav-label">Call</span>
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
            today: 'Today',
            patients: 'Patients',
            patient: 'Patient Details',
            call: 'Call Clinic',
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

    // Booking view - shows field service order bookings with date navigation and calendar picker
    app.component('today-view', {
      props: ['user', 'isOnline'],
      emits: ['navigate', 'sync'],
      setup(props, { emit }) {
        const { ref, onMounted, onUnmounted, computed } = Vue;

        const bookings = ref([]);
        const isLoading = ref(true);
        const error = ref(null);
        const staffName = ref('');
        const displayDate = ref(new Date().toLocaleDateString());
        const currentDate = ref(new Date());
        const touchStartX = ref(0);
        const touchStartY = ref(0);
        const isTransitioning = ref(false);

        // View mode: 'day', 'week', 'month'
        const viewMode = ref('day');

        // Calendar picker state
        const isCalendarOpen = ref(false);
        const calendarMonth = ref(new Date());
        const datesWithBookings = ref(new Set());
        const monthBookings = ref({});

        // Grouped bookings for Week and Month views
        const groupedBookings = ref({});

        // Future bookings modal state
        const isFutureBookingsOpen = ref(false);
        const futureBookingsByDate = ref({});
        const loadingFutureBookings = ref(false);

        // Helper function to parse datetime from API (Odoo returns UTC datetimes)
        // Convert UTC datetime string to local timezone Date object
        const parseOdooDateTime = (dateTimeStr) => {
          if (!dateTimeStr) return new Date();

          // Handle ISO format (with or without Z suffix)
          // ISO format: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM:SSZ
          if (dateTimeStr.includes('T')) {
            // If it's ISO format but missing Z suffix, append it to force UTC parsing
            let isoString = dateTimeStr;
            if (!isoString.endsWith('Z') && !isoString.includes('+') && !isoString.includes('-', isoString.indexOf('T'))) {
              isoString += 'Z';
            }
            return new Date(isoString);
          }

          // Handle format: "2025-01-15 15:00:00" (Odoo format, assumed UTC)
          // Split datetime and parse
          const parts = dateTimeStr.split(' ');
          if (parts.length >= 2) {
            const dateParts = parts[0].split('-'); // YYYY-MM-DD
            const timeParts = parts[1].split(':'); // HH:MM:SS

            if (dateParts.length === 3 && timeParts.length >= 2) {
              const year = parseInt(dateParts[0]);
              const month = parseInt(dateParts[1]) - 1; // JS months are 0-indexed
              const day = parseInt(dateParts[2]);
              const hours = parseInt(timeParts[0]);
              const minutes = parseInt(timeParts[1]);
              const seconds = parseInt(timeParts[2]) || 0;

              // Create UTC date
              const utcDate = new Date(Date.UTC(year, month, day, hours, minutes, seconds));
              return utcDate;
            }
          }

          // Fallback to standard parsing (as UTC if possible)
          // Try to interpret as UTC by appending Z if it doesn't have timezone info
          if (!dateTimeStr.includes('Z') && !dateTimeStr.includes('+') && !dateTimeStr.includes('GMT')) {
            return new Date(dateTimeStr + 'Z');
          }
          return new Date(dateTimeStr);
        };

        // Convert local date and time to ISO format with timezone for API submission
        // Takes local date (YYYY-MM-DD), local time (HH:MM), and user timezone
        const convertLocalDateTimeToISO = (localDate, localTime, userTimezone) => {
          if (!localDate || !localTime) return null;

          try {
            // Create a date object from local date/time
            const [year, month, day] = localDate.split('-').map(Number);
            const [hours, minutes] = localTime.split(':').map(Number);

            // Use Intl API to get the correct offset for the given timezone
            // This accounts for DST properly
            const tempDate = new Date(year, month - 1, day, hours, minutes, 0);

            // Get timezone offset in minutes
            const formatter = new Intl.DateTimeFormat('en-US', {
              timeZone: userTimezone,
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: false
            });

            const parts = formatter.formatToParts(tempDate);
            const tzDate = new Date(
              parseInt(parts.find(p => p.type === 'year').value),
              parseInt(parts.find(p => p.type === 'month').value) - 1,
              parseInt(parts.find(p => p.type === 'day').value),
              parseInt(parts.find(p => p.type === 'hour').value),
              parseInt(parts.find(p => p.type === 'minute').value),
              parseInt(parts.find(p => p.type === 'second').value)
            );

            // Calculate offset in milliseconds
            const offset = tempDate.getTime() - tzDate.getTime();
            const offsetHours = Math.floor(Math.abs(offset) / (1000 * 60 * 60));
            const offsetMinutes = Math.floor((Math.abs(offset) % (1000 * 60 * 60)) / (1000 * 60));
            const sign = offset >= 0 ? '+' : '-';
            const tzString = `${sign}${String(offsetHours).padStart(2, '0')}:${String(offsetMinutes).padStart(2, '0')}`;

            // Return ISO format with timezone
            return `${localDate}T${localTime}:00${tzString}`;
          } catch (err) {
            console.error('Error converting datetime:', err);
            // Fallback: just return the date-time string without timezone
            return `${localDate}T${localTime}:00`;
          }
        };

        // Format booking time with correct timezone handling
        const getFormattedBookingTime = (booking) => {
          if (!booking || !booking.scheduled_datetime) return '--:--';
          const dateObj = parseOdooDateTime(booking.scheduled_datetime);
          return dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
        };

        // Load bookings for a specific date
        const loadBookingsForDate = async (dateObj) => {
          try {
            isLoading.value = true;
            error.value = null;

            // Format date for API (YYYY-MM-DD)
            const year = dateObj.getFullYear();
            const month = String(dateObj.getMonth() + 1).padStart(2, '0');
            const day = String(dateObj.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;

            const response = await fetch(`/health_pwa/api/assignments/today?date=${dateStr}`);
            const result = await response.json();

            if (result.success && result.data) {
              // Sort bookings by scheduled_datetime in ascending order
              const bookingsList = result.data.bookings || [];
              bookingsList.sort((a, b) => {
                const timeA = parseOdooDateTime(a.scheduled_datetime).getTime();
                const timeB = parseOdooDateTime(b.scheduled_datetime).getTime();
                return timeA - timeB;
              });

              // Add formatted time to each booking
              bookingsList.forEach(booking => {
                booking.formatted_time = getFormattedBookingTime(booking);
              });

              bookings.value = bookingsList;
              staffName.value = result.data.staff_name || 'Staff';
              displayDate.value = dateObj.toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              });
              console.log('Loaded bookings for', dateStr, ':', bookings.value.length);
            } else {
              error.value = result.error || 'Failed to load bookings';
              bookings.value = [];
              console.error('Error:', error.value);
            }
          } catch (err) {
            console.error('Failed to load bookings:', err);
            error.value = err.message;
            bookings.value = [];
          } finally {
            isLoading.value = false;
          }
        };

        // Navigate forward (next day/week/month based on view mode)
        const goToNext = () => {
          if (isTransitioning.value) return;
          isTransitioning.value = true;

          if (viewMode.value === 'day') {
            const nextDate = new Date(currentDate.value);
            nextDate.setDate(nextDate.getDate() + 1);
            currentDate.value = nextDate;
            loadBookingsForDate(nextDate);
          } else if (viewMode.value === 'week') {
            const nextDate = new Date(currentDate.value);
            nextDate.setDate(nextDate.getDate() + 7);
            currentDate.value = nextDate;
            loadBookingsForWeek(nextDate);
          } else if (viewMode.value === 'month') {
            const nextDate = new Date(currentDate.value);
            nextDate.setMonth(nextDate.getMonth() + 1);
            currentDate.value = nextDate;
            loadBookingsForMonth(nextDate);
          }

          setTimeout(() => { isTransitioning.value = false; }, 300);
        };

        // Navigate backward (previous day/week/month based on view mode)
        const goToPrevious = () => {
          if (isTransitioning.value) return;
          isTransitioning.value = true;

          if (viewMode.value === 'day') {
            const prevDate = new Date(currentDate.value);
            prevDate.setDate(prevDate.getDate() - 1);
            currentDate.value = prevDate;
            loadBookingsForDate(prevDate);
          } else if (viewMode.value === 'week') {
            const prevDate = new Date(currentDate.value);
            prevDate.setDate(prevDate.getDate() - 7);
            currentDate.value = prevDate;
            loadBookingsForWeek(prevDate);
          } else if (viewMode.value === 'month') {
            const prevDate = new Date(currentDate.value);
            prevDate.setMonth(prevDate.getMonth() - 1);
            currentDate.value = prevDate;
            loadBookingsForMonth(prevDate);
          }

          setTimeout(() => { isTransitioning.value = false; }, 300);
        };

        // Change view mode
        const setViewMode = (mode) => {
          viewMode.value = mode;
          if (mode === 'day') {
            loadBookingsForDate(currentDate.value);
          } else if (mode === 'week') {
            loadBookingsForWeek(currentDate.value);
          } else if (mode === 'month') {
            loadBookingsForMonth(currentDate.value);
          }
        };

        // Go back to today
        const goToToday = () => {
          if (isTransitioning.value) return;
          isTransitioning.value = true;
          const today = new Date();
          currentDate.value = today;
          // Always switch to day view when clicking "Today"
          viewMode.value = 'day';
          loadBookingsForDate(today);
          setTimeout(() => { isTransitioning.value = false; }, 300);
        };

        // Load bookings for an entire week
        const loadBookingsForWeek = async (dateInWeek) => {
          try {
            isLoading.value = true;
            error.value = null;

            // Get start of week (Sunday)
            const weekStart = new Date(dateInWeek);
            weekStart.setDate(weekStart.getDate() - weekStart.getDay());

            // Get end of week (Saturday)
            const weekEnd = new Date(weekStart);
            weekEnd.setDate(weekEnd.getDate() + 6);

            const year = weekStart.getFullYear();
            const month = String(weekStart.getMonth() + 1).padStart(2, '0');
            const day = String(weekStart.getDate()).padStart(2, '0');
            const dateFrom = `${year}-${month}-${day}`;

            const endYear = weekEnd.getFullYear();
            const endMonth = String(weekEnd.getMonth() + 1).padStart(2, '0');
            const endDay = String(weekEnd.getDate()).padStart(2, '0');
            const dateTo = `${endYear}-${endMonth}-${endDay}`;

            // Fetch all bookings for the week using FSO endpoint with date range
            const response = await fetch(`/health_pwa/api/fso?date_from=${dateFrom}&date_to=${dateTo}&limit=200`);
            const result = await response.json();

            if (result.success && result.data) {
              staffName.value = result.data.staff_name || 'Staff';

              // Group bookings by date
              const grouped = {};
              (result.data.orders || []).forEach(order => {
                const bookingDate = parseOdooDateTime(order.scheduled_datetime).toLocaleDateString('en-US', {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                });
                if (!grouped[bookingDate]) {
                  grouped[bookingDate] = [];
                }
                grouped[bookingDate].push({
                  id: order.id,
                  fso_id: order.id,
                  fso_name: order.name,
                  patient_name: order.patient_name,
                  patient_id: order.patient_id,
                  patient_phone: order.phone,
                  service_type: order.service_type,
                  appointment_type: '',
                  scheduled_datetime: order.scheduled_datetime,
                  scheduled_time: parseOdooDateTime(order.scheduled_datetime).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
                  status: order.status,
                  status_display: order.status_display,
                  location: order.address,
                  priority: order.priority,
                  duration_minutes: 0,
                  assignment_role: 'staff',
                  notes: order.description || ''
                });
              });

              // Sort bookings within each date by scheduled time (ascending)
              Object.keys(grouped).forEach(dateStr => {
                grouped[dateStr].sort((a, b) => {
                  const timeA = parseOdooDateTime(a.scheduled_datetime).getTime();
                  const timeB = parseOdooDateTime(b.scheduled_datetime).getTime();
                  return timeA - timeB;
                });
              });

              // Sort date groups in ascending order (oldest date first)
              const sortedGrouped = {};
              Object.keys(grouped)
                .sort((a, b) => {
                  const dateA = parseOdooDateTime(grouped[a][0].scheduled_datetime);
                  const dateB = parseOdooDateTime(grouped[b][0].scheduled_datetime);
                  return dateA - dateB;
                })
                .forEach(dateStr => {
                  sortedGrouped[dateStr] = grouped[dateStr];
                });

              groupedBookings.value = sortedGrouped;
              displayDate.value = `Week of ${weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
              console.log('Loaded week bookings:', sortedGrouped);
            } else {
              error.value = result.error || 'Failed to load week bookings';
            }
          } catch (err) {
            console.error('Failed to load week bookings:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };

        // Load bookings for an entire month
        const loadBookingsForMonth = async (dateInMonth) => {
          try {
            isLoading.value = true;
            error.value = null;

            const year = dateInMonth.getFullYear();
            const month = String(dateInMonth.getMonth() + 1).padStart(2, '0');

            const dateFrom = `${year}-${month}-01`;
            const lastDay = new Date(year, dateInMonth.getMonth() + 1, 0).getDate();
            const dateTo = `${year}-${month}-${lastDay}`;

            // Fetch all bookings for the month
            const response = await fetch(`/health_pwa/api/fso?date_from=${dateFrom}&date_to=${dateTo}&limit=200`);
            const result = await response.json();

            if (result.success && result.data) {
              staffName.value = result.data.staff_name || 'Staff';

              // Group bookings by date
              const grouped = {};
              (result.data.orders || []).forEach(order => {
                const bookingDate = parseOdooDateTime(order.scheduled_datetime).toLocaleDateString('en-US', {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                });
                if (!grouped[bookingDate]) {
                  grouped[bookingDate] = [];
                }
                grouped[bookingDate].push({
                  id: order.id,
                  fso_id: order.id,
                  fso_name: order.name,
                  patient_name: order.patient_name,
                  patient_id: order.patient_id,
                  patient_phone: order.phone,
                  service_type: order.service_type,
                  appointment_type: '',
                  scheduled_datetime: order.scheduled_datetime,
                  scheduled_time: parseOdooDateTime(order.scheduled_datetime).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
                  status: order.status,
                  status_display: order.status_display,
                  location: order.address,
                  priority: order.priority,
                  duration_minutes: 0,
                  assignment_role: 'staff',
                  notes: order.description || ''
                });
              });

              // Sort bookings within each date by scheduled time (ascending)
              Object.keys(grouped).forEach(dateStr => {
                grouped[dateStr].sort((a, b) => {
                  const timeA = parseOdooDateTime(a.scheduled_datetime).getTime();
                  const timeB = parseOdooDateTime(b.scheduled_datetime).getTime();
                  return timeA - timeB;
                });
              });

              // Sort date groups in ascending order (oldest date first)
              const sortedGrouped = {};
              Object.keys(grouped)
                .sort((a, b) => {
                  const dateA = parseOdooDateTime(grouped[a][0].scheduled_datetime);
                  const dateB = parseOdooDateTime(grouped[b][0].scheduled_datetime);
                  return dateA - dateB;
                })
                .forEach(dateStr => {
                  sortedGrouped[dateStr] = grouped[dateStr];
                });

              groupedBookings.value = sortedGrouped;
              displayDate.value = dateInMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
              console.log('Loaded month bookings:', sortedGrouped);
            } else {
              error.value = result.error || 'Failed to load month bookings';
            }
          } catch (err) {
            console.error('Failed to load month bookings:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };

        // Load all bookings for a month to determine which dates have bookings
        const loadMonthBookings = async (monthDate) => {
          try {
            const year = monthDate.getFullYear();
            const month = String(monthDate.getMonth() + 1).padStart(2, '0');

            // Get first and last day of month
            const firstDay = new Date(year, monthDate.getMonth(), 1);
            const lastDay = new Date(year, monthDate.getMonth() + 1, 0);

            const dateFrom = `${year}-${month}-01`;
            const dateTo = `${year}-${month}-${lastDay.getDate()}`;

            // Fetch bookings for entire month
            const response = await fetch(
              `/health_pwa/api/fso?date_from=${dateFrom}&date_to=${dateTo}&limit=100`
            );
            const result = await response.json();

            if (result.success && result.data && result.data.orders) {
              const datesSet = new Set();
              const bookingsMap = {};

              result.data.orders.forEach(order => {
                if (order.scheduled_datetime) {
                  const orderDate = parseOdooDateTime(order.scheduled_datetime);
                  const dateStr = `${orderDate.getFullYear()}-${String(orderDate.getMonth() + 1).padStart(2, '0')}-${String(orderDate.getDate()).padStart(2, '0')}`;
                  datesSet.add(dateStr);

                  if (!bookingsMap[dateStr]) {
                    bookingsMap[dateStr] = 0;
                  }
                  bookingsMap[dateStr]++;
                }
              });

              datesWithBookings.value = datesSet;
              monthBookings.value = bookingsMap;
              console.log('Loaded month bookings:', datesWithBookings.value);
            }
          } catch (err) {
            console.error('Failed to load month bookings:', err);
          }
        };

        // Toggle calendar open/close
        const toggleCalendar = async () => {
          if (!isCalendarOpen.value) {
            // Opening calendar - load month bookings
            await loadMonthBookings(calendarMonth.value);
          }
          isCalendarOpen.value = !isCalendarOpen.value;
        };

        // Toggle future bookings modal
        const toggleFutureBookings = async () => {
          if (!isFutureBookingsOpen.value) {
            // Opening future bookings - load all upcoming bookings
            await loadFutureBookings();
          }
          isFutureBookingsOpen.value = !isFutureBookingsOpen.value;
        };

        // Load future bookings from API
        const loadFutureBookings = async () => {
          loadingFutureBookings.value = true;
          try {
            const response = await fetch('/health_pwa/api/future_bookings');
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data.data && data.data.bookings_by_date) {
              futureBookingsByDate.value = data.data.bookings_by_date;
            } else {
              futureBookingsByDate.value = {};
            }
          } catch (error) {
            console.error('Error loading future bookings:', error);
            futureBookingsByDate.value = {};
          } finally {
            loadingFutureBookings.value = false;
          }
        };

        // Change calendar month
        const changeCalendarMonth = async (offset) => {
          const newMonth = new Date(calendarMonth.value);
          newMonth.setMonth(newMonth.getMonth() + offset);
          calendarMonth.value = newMonth;
          await loadMonthBookings(newMonth);
        };

        // Select date from calendar
        const selectCalendarDate = (day) => {
          const selectedDate = new Date(calendarMonth.value.getFullYear(), calendarMonth.value.getMonth(), day);
          currentDate.value = selectedDate;
          viewMode.value = 'day'; // Highlight Day button when calendar date selected
          loadBookingsForDate(selectedDate);
          isCalendarOpen.value = false;
        };

        // Generate calendar grid
        const getCalendarDays = computed(() => {
          const year = calendarMonth.value.getFullYear();
          const month = calendarMonth.value.getMonth();
          const firstDay = new Date(year, month, 1);
          const lastDay = new Date(year, month + 1, 0);
          const daysInMonth = lastDay.getDate();
          const startingDayOfWeek = firstDay.getDay();

          const days = [];

          // Empty cells for days before month starts
          for (let i = 0; i < startingDayOfWeek; i++) {
            days.push(null);
          }

          // Days of the month
          for (let day = 1; day <= daysInMonth; day++) {
            days.push(day);
          }

          return days;
        });

        // Check if a date has bookings
        const hasBookingsOnDate = (day) => {
          if (!day) return false;
          const dateStr = `${calendarMonth.value.getFullYear()}-${String(calendarMonth.value.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          return datesWithBookings.value.has(dateStr);
        };

        // Get booking count for a date
        const getBookingCount = (day) => {
          if (!day) return 0;
          const dateStr = `${calendarMonth.value.getFullYear()}-${String(calendarMonth.value.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          return monthBookings.value[dateStr] || 0;
        };

        // Touch handlers for swipe detection - only horizontal swipes
        const handleTouchStart = (e) => {
          if (e.touches && e.touches.length > 0) {
            touchStartX.value = e.touches[0].clientX;
            touchStartY.value = e.touches[0].clientY;
            console.log('Touch start at X:', touchStartX.value, 'Y:', touchStartY.value);
          }
        };

        const handleTouchEnd = (e) => {
          if (e.changedTouches && e.changedTouches.length > 0) {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const diffX = touchStartX.value - touchEndX;
            const diffY = Math.abs(touchStartY.value - touchEndY);
            const threshold = 30; // Minimum swipe distance

            console.log('Touch end - DiffX:', diffX, 'DiffY:', diffY, 'Threshold:', threshold);

            // Only trigger horizontal swipe if horizontal movement is greater than vertical
            if (Math.abs(diffX) > threshold && Math.abs(diffX) > diffY) {
              if (diffX > 0) {
                // Swiped left - next period
                console.log('Swiped left - going to next');
                goToNext();
              } else {
                // Swiped right - previous period
                console.log('Swiped right - going to previous');
                goToPrevious();
              }
            }
          }
        };

        // Check if booking is running late
        const isRunningLate = (booking) => {
          if (!booking || !booking.scheduled_datetime) return false;
          const now = new Date();
          const bookedTime = parseOdooDateTime(booking.scheduled_datetime);
          // Check if current time is past booking time and status is pending (draft, confirmed, assigned)
          const pendingStatuses = ['draft', 'confirmed', 'assigned'];
          return now > bookedTime && pendingStatuses.includes(booking.status);
        };

        const getStatusColor = (booking) => {
          if (!booking) return '#95a5a6';

          // Support both 'status' (old) and 'state' (new API) properties
          const status = booking.status || booking.state || '';

          // Check for Running Late (orange)
          if (isRunningLate(booking)) {
            return '#f39c12'; // Orange
          }

          const colors = {
            'draft': '#3498db',                      // Blue - Booked
            'confirmed': '#3498db',                  // Blue - Confirmed
            'assigned': '#3498db',                   // Blue - Assigned
            'in_progress': '#2ecc71',                // Green - In Progress
            'completed': '#95a5a6',                  // Grey - Completed
            'completed_pending_invoice': '#95a5a6', // Grey - Pending Invoice
            'closed': '#95a5a6',                     // Grey - Closed
            'cancelled': '#e74c3c'                   // Red - Cancelled
          };
          return colors[status] || '#95a5a6';
        };

        const getStatusDisplay = (booking) => {
          if (!booking) return 'Unknown';

          // Show "Running Late" if applicable
          if (isRunningLate(booking)) {
            return 'Running Late';
          }

          // Support both 'status' (old) and 'state' (new API) properties
          const status = booking.status || booking.state || '';
          const displayMap = {
            'draft': 'Booked',
            'confirmed': 'Confirmed',
            'assigned': 'Assigned',
            'in_progress': 'In Progress',
            'completed': 'Completed',
            'completed_pending_invoice': 'Pending Invoice',
            'closed': 'Closed',
            'cancelled': 'Cancelled'
          };
          return displayMap[status] || status || 'Unknown';
        };

        const callPatient = (phone) => {
          if (phone) {
            window.location.href = `tel:${phone}`;
          } else {
            alert('No phone number available');
          }
        };

        // Open Google Maps with location
        const openMap = (location, patientName) => {
          if (location) {
            const encodedLocation = encodeURIComponent(location);
            const mapsUrl = `https://www.google.com/maps/search/${encodedLocation}`;
            window.open(mapsUrl, '_blank');
          } else {
            alert('Location not available');
          }
        };

        // Booking detail view state
        const selectedBookingId = ref(null);
        const selectedBookingDetail = ref(null);
        const isLoadingDetail = ref(false);
        const detailError = ref(null);

        // Fetch full booking details for inline expansion
        const fetchBookingDetail = async (bookingId) => {
          try {
            isLoadingDetail.value = true;
            detailError.value = null;

            const response = await fetch(`/health_pwa/api/fso/${bookingId}`);
            const result = await response.json();

            if (result.success && result.data) {
              selectedBookingDetail.value = result.data;
              // Initialize clinical notes text from loaded booking
              clinicalNotesText.value = result.data.clinical_notes || '';
              console.log('Loaded booking detail:', result.data);
            } else {
              detailError.value = result.error || 'Failed to load booking details';
              console.error('Error loading detail:', detailError.value);
            }
          } catch (err) {
            console.error('Failed to fetch booking detail:', err);
            detailError.value = err.message;
          } finally {
            isLoadingDetail.value = false;
          }
        };

        // Toggle booking detail expansion
        const toggleBookingDetail = async (bookingId) => {
          if (selectedBookingId.value === bookingId) {
            // Close if already open
            selectedBookingId.value = null;
            selectedBookingDetail.value = null;
            clinicalNotesText.value = '';
          } else {
            // Open and fetch details
            selectedBookingId.value = bookingId;
            await fetchBookingDetail(bookingId);
          }
        };

        // Computed property for formatted scheduled datetime (handles timezone correctly)
        const formattedScheduledDateTime = computed(() => {
          if (!selectedBookingDetail.value || !selectedBookingDetail.value.scheduled_datetime) {
            return 'TBD';
          }
          const dateObj = parseOdooDateTime(selectedBookingDetail.value.scheduled_datetime);
          return dateObj.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        });

        // Intake Summary Modal state
        const showIntakeSummaryModal = ref(false);
        const selectedBookingForIntake = ref(null);

        // Toggle intake summary modal
        const toggleIntakeSummaryModal = () => {
          showIntakeSummaryModal.value = !showIntakeSummaryModal.value;
        };

        // Service Start state
        const serviceStartedForBooking = ref(null); // Stores which booking has service started
        const showClinicalNotesModal = ref(false);
        const clinicalNotesText = ref('');
        const clinicalObservations = ref('');  // Doctor-specific field
        const diagnosis = ref('');  // Doctor-specific field
        const treatmentPerformed = ref('');  // Doctor-specific field
        const capturedPhoto = ref(null);
        const photoPreviewUrl = ref(null);

        // Timer state
        const timerInterval = ref(null);
        const currentTime = ref(new Date());
        const showInvoiceModal = ref(false);
        const quoteData = ref(null);

        // Invoice verification and payment workflow
        const quoteVerified = ref(false);
        const quoteComments = ref('');
        const showPaymentWizard = ref(false);
        const paymentWizardData = ref({
          payment_choice: 'pay_now',
          payment_method: 'cash',
          service_notes: '',
          create_invoice_now: true
        });

        // Track the completed booking ID for modal workflows
        const completedBookingId = ref(null);

        // Client Details View State
        const showClientDetailsView = ref(false);
        const currentClientData = ref({
          id: null,
          name: '',
          phone: '',
          age: null,
          gender: '',
          patient_code: ''
        });

        // Next Visit Modal State Management
        const showNextVisitModalA = ref(false);  // Modal for "No next visit scheduled"
        const showNextVisitModalB = ref(false);  // Modal for "Schedule next visit"
        const nextVisitData = ref({
          has_next_visit: false,
          patient_name: '',
          patient_id: null,
          next_visit_date: null,
          next_fso_id: null,
          quote_items: [],
          assigned_nurse_id: null,
          assigned_nurse_name: '',
          assigned_staff: [],
          assignment_notes: ''
        });
        const nextVisitFormData = ref({
          scheduled_date: null,
          scheduled_time: null,
          quote_items: [],
          assigned_nurse_id: null,
          no_future_visit_reason: '',
          other_reason_text: ''
        });
        const noFutureVisitReasons = [
          { value: 'patient_died', label: 'Patient died' },
          { value: 'improved', label: 'Patient improved/recovered' },
          { value: 'hospital', label: 'Patient admitted to hospital' },
          { value: 'declined', label: 'Patient declined further visits' },
          { value: 'moved', label: 'Patient moved/relocated' },
          { value: 'referral', label: 'Referred to another provider' },
          { value: 'other', label: 'Other' }
        ];
        const showNoFutureVisitDropdown = ref(false);

        // Product Catalog Modal State
        const showProductCatalogModal = ref(false);
        const catalogProducts = ref([]);
        const catalogSearchQuery = ref('');
        const catalogLoading = ref(false);
        const catalogError = ref(null);

        // Current User Information
        const currentUser = ref({
          id: null,
          name: 'Loading...',
          employee_id: null,
          employee_name: '',
          timezone: 'UTC',
          is_doctor: false
        });

        // Load product catalog
        const loadProductCatalog = async () => {
          try {
            catalogLoading.value = true;
            catalogError.value = null;

            let url = '/health_pwa/api/products/catalog?limit=100';
            if (catalogSearchQuery.value) {
              url += `&search=${encodeURIComponent(catalogSearchQuery.value)}`;
            }

            const response = await fetch(url);
            const result = await response.json();

            if (result.success && result.data) {
              catalogProducts.value = result.data.products || [];
              console.log('Loaded products:', catalogProducts.value.length);
            } else {
              catalogError.value = result.error || 'Failed to load products';
              console.error('Error loading catalog:', catalogError.value);
            }
          } catch (err) {
            console.error('Error loading product catalog:', err);
            catalogError.value = err.message;
          } finally {
            catalogLoading.value = false;
          }
        };

        // Add product to next visit quote (or increment quantity if already added)
        const addProductToQuote = (product) => {
          if (!nextVisitFormData.value.quote_items) {
            nextVisitFormData.value.quote_items = [];
          }

          // Check if product already exists in quote items
          const existingItem = nextVisitFormData.value.quote_items.find(item => item.product_id === product.id);

          if (existingItem) {
            // If product already exists, increment quantity
            existingItem.quantity += 1;
            console.log(`Quantity increased for ${product.name} to ${existingItem.quantity}`);
          } else {
            // If product doesn't exist, add it
            nextVisitFormData.value.quote_items.push({
              product_id: product.id,
              product_name: product.name,
              quantity: 1,
              unit_price: product.price
            });
            console.log('Product added to quote:', product.name);
          }

          // Keep catalog modal open so user can add more products
          // Don't close here - let user click "Done" button to close
        };

        // Load current user information
        const loadCurrentUser = async () => {
          try {
            const response = await fetch('/health_pwa/api/current_user');
            const result = await response.json();

            if (result.success && result.data) {
              currentUser.value = result.data;
              // Pre-populate assigned nurse ID when opening modal
            } else {
              console.error('Failed to load current user:', result.error);
            }
          } catch (err) {
            console.error('Error loading current user:', err);
          }
        };

        // Open product catalog modal
        const openProductCatalogModal = async () => {
          console.log('Opening product catalog modal');
          showProductCatalogModal.value = true;
          await loadProductCatalog();
        };

        // Computed elapsed time for timer
        const elapsedTime = computed(() => {
          if (!selectedBookingDetail.value || !selectedBookingDetail.value.actual_start_datetime) return '00:00:00';

          const startTime = parseOdooDateTime(selectedBookingDetail.value.actual_start_datetime);
          const endTime = currentTime.value;
          const diff = Math.floor((endTime - startTime) / 1000);

          const hours = Math.floor(diff / 3600);
          const minutes = Math.floor((diff % 3600) / 60);
          const seconds = diff % 60;

          return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        });

        // Check if clinical notes are valid (has text OR image)
        const isClinicalNotesComplete = computed(() => {
          // Check local unsaved state
          const hasLocalNotes = clinicalNotesText.value && clinicalNotesText.value.trim().length > 0;
          const hasLocalImage = photoPreviewUrl.value !== null && photoPreviewUrl.value !== undefined && photoPreviewUrl.value !== '';

          // Check server-saved state
          const hasServerNotes = selectedBookingDetail.value?.clinical_notes &&
                                  selectedBookingDetail.value.clinical_notes.trim().length > 0;

          // Return true if either local unsaved OR server-saved clinical notes exist
          return (hasLocalNotes || hasLocalImage) || hasServerNotes;
        });

        // Start timer function
        const startTimer = () => {
          if (timerInterval.value) clearInterval(timerInterval.value);
          timerInterval.value = setInterval(() => {
            currentTime.value = new Date();
          }, 1000);
        };

        // Stop timer function
        const stopTimer = () => {
          if (timerInterval.value) {
            clearInterval(timerInterval.value);
            timerInterval.value = null;
          }
        };

        // Load quote data for invoice
        const loadQuoteData = async (bookingId) => {
          try {
            const response = await fetch(`/health_pwa/api/fso/${bookingId}/quote`);
            const result = await response.json();
            if (result.success && result.data) {
              quoteData.value = result.data;
              // Store original values for each line immediately upon loading
              if (quoteData.value && quoteData.value.order_lines) {
                quoteData.value.order_lines.forEach(line => {
                  // Ensure values are stored as numbers for proper comparison
                  line.original_quantity = parseFloat(line.quantity) || 0;
                  line.original_discount = parseFloat(line.discount) || 0;
                  // Ensure current values are also numbers
                  line.quantity = parseFloat(line.quantity) || 0;
                  line.discount = parseFloat(line.discount) || 0;
                });
              }
              console.log('Loaded quote data:', result.data);
            } else {
              console.error('Error loading quote:', result.error);
            }
          } catch (err) {
            console.error('Error loading quote data:', err);
          }
        };

        // Open invoice modal - now for verification
        const openInvoiceModal = async () => {
          if (selectedBookingId.value) {
            await loadQuoteData(selectedBookingId.value);
            quoteVerified.value = false; // Reset verification state
            quoteComments.value = ''; // Clear comments
            showInvoiceModal.value = true;
          }
        };

        // Save quote with verification comments
        const saveQuoteWithComments = async () => {
          if (!selectedBookingId.value) {
            console.error('Missing booking ID');
            return;
          }

          // Validate that Verification Notes are filled if any line modifications exist
          if (hasLineModifications.value && (!quoteComments.value || !quoteComments.value.trim())) {
            alert('Please add verification notes explaining the changes made to Qty or Discount.');
            return;
          }

          try {
            // Prepare modified line items for backend sync
            const modifiedLineItems = [];
            if (quoteData.value && quoteData.value.order_lines) {
              for (const line of quoteData.value.order_lines) {
                if (!line) continue;

                // Check if this line has Qty or Discount changes
                const qtyChanged = line.quantity !== (line.original_quantity || line.quantity);
                const discountChanged = (line.discount || 0) !== (line.original_discount !== undefined ? line.original_discount : 0);

                if (qtyChanged || discountChanged) {
                  // Validate that discount reason is provided if discount is applied
                  if (line.discount > 0 && !line.discount_reason?.trim()) {
                    alert(`Please provide a discount reason for: ${line.product_name}`);
                    return;
                  }

                  console.log(`Collecting modified line ${line.id}:`, {
                    quantity: line.quantity,
                    discount: line.discount || 0,
                    discount_reason: line.discount_reason || ''
                  });

                  modifiedLineItems.push({
                    line_id: line.id,
                    quantity: line.quantity,
                    discount: line.discount || 0,
                    discount_reason: line.discount_reason || ''
                  });
                }
              }
            }

            console.log('Modified lines to save:', modifiedLineItems);

            const response = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/quote/save`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                comments: quoteComments.value,
                modified_lines: modifiedLineItems  // Send actual modified line data
              })
            });

            const result = await response.json();
            if (result.success) {
              console.log('Quote verified and saved:', result.data);
              quoteVerified.value = true; // Mark as verified
              // Reload quote data to get updated totals from backend
              await loadQuoteData(selectedBookingId.value);
              // Reset comments field after successful save
              quoteComments.value = '';
            } else {
              console.error('Error saving quote:', result.error);
              alert('Error saving quote: ' + result.error);
            }
          } catch (err) {
            console.error('Error saving quote:', err);
            alert('Failed to save quote: ' + err.message);
          }
        };

        // Detect if any line items have modifications (Qty or Discount changes)
        const hasLineModifications = computed(() => {
          if (!quoteData.value || !quoteData.value.order_lines) return false;
          return quoteData.value.order_lines.some(line => {
            if (!line) return false;
            // Compare current values with original values
            const originalQty = line.original_quantity !== undefined ? line.original_quantity : line.quantity;
            const originalDiscount = line.original_discount !== undefined ? line.original_discount : (line.discount || 0);

            const qtyChanged = line.quantity !== originalQty;
            const discountChanged = (line.discount || 0) !== originalDiscount;

            console.log(`Line ${line.product_name}: qty ${line.quantity} vs ${originalQty} (changed: ${qtyChanged}), discount ${line.discount || 0} vs ${originalDiscount} (changed: ${discountChanged})`);

            return qtyChanged || discountChanged;
          });
        });

        // Simple flag to show message - directly check if any line has qty or discount changes
        const showSaveMessage = computed(() => {
          if (!quoteData.value || !quoteData.value.order_lines) return false;
          for (const line of quoteData.value.order_lines) {
            if (!line) continue;
            const qtyDifferent = line.original_quantity !== undefined && line.quantity !== line.original_quantity;
            // Check if discount CHANGED from original, not just if it exists
            const originalDiscount = line.original_discount !== undefined ? line.original_discount : 0;
            const discountDifferent = (line.discount || 0) !== originalDiscount;
            if (qtyDifferent || discountDifferent) {
              return true;
            }
          }
          return false;
        });

        // Open payment wizard (only after quote verification)
        const openPaymentWizard = () => {
          if (!quoteVerified.value) {
            alert('Please verify the invoice first and click Save Quote.');
            return;
          }
          showPaymentWizard.value = true;
        };

        // Complete payment and service
        const completePayment = async () => {
          if (!selectedBookingId.value) {
            console.error('No booking selected');
            return;
          }

          try {
            const response = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/complete`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                payment_choice: paymentWizardData.value.payment_choice,
                payment_method: paymentWizardData.value.payment_method,
                service_notes: paymentWizardData.value.service_notes,
                create_invoice_now: paymentWizardData.value.create_invoice_now
              })
            });

            // Check if response status is OK
            if (!response.ok) {
              const errorText = await response.text();
              console.error(`Server error (${response.status}): ${errorText}`);
              alert(`Error: Server returned status ${response.status}. Please try again.`);
              return;
            }

            let result;
            try {
              result = await response.json();
            } catch (jsonError) {
              const responseText = await response.text();
              console.error('Failed to parse JSON response:', responseText);
              alert('Error: Invalid response from server. Details: ' + responseText.substring(0, 100));
              return;
            }
            if (result.success) {
              console.log('Service completed successfully');
              showPaymentWizard.value = false;
              showInvoiceModal.value = false;
              quoteVerified.value = false;
              quoteComments.value = '';

              // Save the completed booking ID for modal workflows
              completedBookingId.value = selectedBookingId.value;

              // Close the completed booking detail view to prevent confusion
              console.log('Closing completed booking detail view');
              selectedBookingId.value = null;
              selectedBookingDetail.value = null;

              // Check for next visit and open appropriate modal
              console.log('Checking next visit status for patient...');
              const statusResponse = await fetch(`/health_pwa/api/fso/${completedBookingId.value}/next_visit_status`);
              const statusData = await statusResponse.json();

              if (statusData.success) {
                // Update next visit data from status response
                nextVisitData.value.has_next_visit = statusData.data.has_next_visit;
                nextVisitData.value.patient_name = statusData.data.patient_name;
                nextVisitData.value.patient_id = statusData.data.patient_id;
                nextVisitData.value.next_visit_date = statusData.data.next_visit_date;
                nextVisitData.value.next_fso_id = statusData.data.next_fso_id;
                nextVisitData.value.assignment_notes = statusData.data.assignment_notes;

                if (statusData.data.has_next_visit) {
                  // Next visit already scheduled - populate Modal B with existing FSO details
                  console.log('Next visit already scheduled for:', statusData.data.next_visit_date);

                  // Store the next FSO ID for potential assignment deletion
                  nextVisitData.value.next_fso_id = statusData.data.next_fso_id;

                  // Parse and populate the date/time
                  if (statusData.data.next_visit_date) {
                    const nextDate = parseOdooDateTime(statusData.data.next_visit_date);
                    // Use local date methods to get the correct local date
                    const year = nextDate.getFullYear();
                    const month = String(nextDate.getMonth() + 1).padStart(2, '0');
                    const day = String(nextDate.getDate()).padStart(2, '0');
                    nextVisitFormData.value.scheduled_date = `${year}-${month}-${day}`; // YYYY-MM-DD format
                    nextVisitFormData.value.scheduled_time = `${String(nextDate.getHours()).padStart(2, '0')}:${String(nextDate.getMinutes()).padStart(2, '0')}`; // HH:MM format
                  }

                  // Populate assigned nurse with both ID and name
                  if (statusData.data.assigned_nurse && statusData.data.assigned_nurse.id) {
                    nextVisitFormData.value.assigned_nurse_id = statusData.data.assigned_nurse.id;
                    nextVisitFormData.value.assigned_nurse_name = statusData.data.assigned_nurse.name || '';
                  } else {
                    nextVisitFormData.value.assigned_nurse_id = null;
                    nextVisitFormData.value.assigned_nurse_name = '';
                  }

                  // Populate quote items if available
                  if (statusData.data.quote_items && statusData.data.quote_items.length > 0) {
                    nextVisitFormData.value.quote_items = statusData.data.quote_items;
                  } else {
                    nextVisitFormData.value.quote_items = [];
                  }

                  // Open Modal B with pre-populated data
                  showNextVisitModalB.value = true;
                  // Refresh bookings after a short delay to ensure UI updates
                  setTimeout(() => {
                    loadBookingsForDate(currentDate.value);
                  }, 300);
                } else {
                  // No next visit - open Modal A to ask if patient wants future visit
                  console.log('No next visit scheduled - opening modal to schedule');
                  showNextVisitModalA.value = true;
                  // Refresh bookings after a short delay to ensure UI updates
                  setTimeout(() => {
                    loadBookingsForDate(currentDate.value);
                  }, 300);
                }
              } else {
                // Error checking next visit - just refresh
                console.error('Error checking next visit:', statusData.error);
                alert('Service completed successfully!');
                loadBookingsForDate(currentDate.value);
              }
            } else {
              console.error('Error completing payment:', result.error);
              alert('Error completing payment: ' + result.error);
            }
          } catch (err) {
            console.error('Error completing payment:', err);
            alert('Failed to complete payment: ' + err.message);
          }
        };

        // Start service
        const startService = async () => {
          if (selectedBookingId.value) {
            try {
              console.log('Starting service for booking:', selectedBookingId.value);
              console.log('Current booking state:', selectedBookingDetail.value?.state);

              // Call API to start service
              const response = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/start`, {
                method: 'POST'
              });

              const result = await response.json();
              console.log('API Response:', result);
              console.log('Response Status:', response.status);

              if (result.success) {
                console.log('Service started successfully');
                serviceStartedForBooking.value = selectedBookingId.value;
                // Update the booking detail with new state
                if (selectedBookingDetail.value) {
                  selectedBookingDetail.value.state = result.data.state;
                  selectedBookingDetail.value.actual_start_datetime = result.data.actual_start_datetime;
                }
                // Start the timer
                startTimer();
                console.log('Service started for booking:', selectedBookingId.value);
              } else {
                console.error('Error starting service:', result.error);
                alert('Error: ' + result.error);
              }
            } catch (err) {
              console.error('Error starting service:', err);
              alert('Error starting service: ' + err.message);
            }
          } else {
            console.error('No booking selected');
          }
        };

        // Open clinical notes modal
        const openClinicalNotesModal = () => {
          showClinicalNotesModal.value = true;
          if (currentUser.value.is_doctor) {
            // Doctor mode: populate three separate fields
            clinicalObservations.value = selectedBookingDetail.value?.clinical_notes || '';
            diagnosis.value = selectedBookingDetail.value?.diagnosis || '';
            treatmentPerformed.value = selectedBookingDetail.value?.treatment_performed || '';
          } else {
            // Non-doctor mode: use single notes field
            clinicalNotesText.value = selectedBookingDetail.value?.clinical_notes || '';
          }
        };

        // Close clinical notes modal
        const closeClinicalNotesModal = () => {
          showClinicalNotesModal.value = false;
          clinicalNotesText.value = '';
          clinicalObservations.value = '';
          diagnosis.value = '';
          treatmentPerformed.value = '';
          capturedPhoto.value = null;
          photoPreviewUrl.value = null;
        };

        // Capture photo from camera
        const capturePhoto = async (event) => {
          const file = event.target.files?.[0];
          if (file) {
            capturedPhoto.value = file;
            // Create preview URL
            photoPreviewUrl.value = URL.createObjectURL(file);
            console.log('Photo captured:', file.name);
          }
        };

        // Save clinical notes and photo
        const saveClinicalNotes = async () => {
          try {
            if (!selectedBookingId.value) {
              console.error('No booking selected');
              return;
            }

            // Determine validation based on user role
            let hasNotes = false;
            let requestData = {};

            if (currentUser.value.is_doctor) {
              // Doctor mode: validate three fields
              hasNotes =
                (clinicalObservations.value && clinicalObservations.value.trim().length > 0) ||
                (diagnosis.value && diagnosis.value.trim().length > 0) ||
                (treatmentPerformed.value && treatmentPerformed.value.trim().length > 0);

              requestData = {
                clinical_notes: clinicalObservations.value,
                diagnosis: diagnosis.value,
                treatment_performed: treatmentPerformed.value,
                medications_prescribed: '',
                vital_signs: ''
              };
            } else {
              // Non-doctor mode: validate single field
              hasNotes = clinicalNotesText.value && clinicalNotesText.value.trim().length > 0;
              requestData = {
                clinical_notes: clinicalNotesText.value,
                diagnosis: '',
                treatment_performed: '',
                medications_prescribed: '',
                vital_signs: ''
              };
            }

            const hasPhoto = capturedPhoto.value !== null;

            if (!hasNotes && !hasPhoto) {
              alert('Please provide clinical notes or take a photo before saving');
              console.error('Please provide clinical notes or photo');
              return;
            }

            // Step 1: Upload photo if available
            if (hasPhoto) {
              console.log('Uploading photo...');
              const photoFormData = new FormData();
              photoFormData.append('image', capturedPhoto.value);

              try {
                const photoResponse = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/upload_image`, {
                  method: 'POST',
                  body: photoFormData
                });

                const photoResult = await photoResponse.text();
                let parsedPhotoResult;
                try {
                  parsedPhotoResult = JSON.parse(photoResult);
                } catch (e) {
                  console.warn('Photo upload response parsing issue:', photoResult);
                }

                if (photoResponse.ok) {
                  console.log('Photo uploaded successfully');
                } else {
                  console.warn('Photo upload returned non-200 status:', photoResponse.status);
                  alert('Warning: Photo upload failed but clinical notes will still be saved');
                }
              } catch (photoErr) {
                console.warn('Error uploading photo:', photoErr);
                // Don't stop the process if photo upload fails - continue with notes
              }
            }

            // Step 2: Save clinical notes if text is provided
            if (hasNotes) {
              console.log('Saving clinical notes...');

              const response = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/clinical_notes`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
              });

              const responseText = await response.text();
              let result;
              try {
                result = JSON.parse(responseText);
              } catch (e) {
                console.error('Failed to parse response:', responseText);
                throw new Error('Invalid server response');
              }

              if (!response.ok || !result.data) {
                throw new Error(result.error || 'Failed to save clinical notes');
              }

              console.log('Clinical notes saved successfully');
            }

            // Step 3: Update UI and close modal on success
            if (selectedBookingDetail.value && hasNotes) {
              selectedBookingDetail.value.clinical_notes = clinicalNotesText.value;
            }
            alert('Clinical notes saved successfully');
            closeClinicalNotesModal();
          } catch (err) {
            console.error('Error saving clinical notes:', err);
            alert('Error saving clinical notes: ' + err.message);
          }
        };

        // Complete service without quote (for today-view)
        const completeServiceWithoutQuoteInTodayView = async () => {
          if (!selectedBookingId.value) {
            alert('No booking selected');
            return;
          }

          try {
            const response = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/complete_without_quote`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                service_notes: 'Service completed without invoice',
              })
            });

            const data = await response.json();
            console.log('Complete service without quote response:', data);

            if (data.success && data.data) {
              console.log('Service completed successfully');
              // Save the completed booking ID for modal workflows
              completedBookingId.value = selectedBookingId.value;
              // Reset the service started flag
              serviceStartedForBooking.value = null;
              // Close the booking detail
              selectedBookingId.value = null;
              selectedBookingDetail.value = null;

              // Check for next visit and open appropriate modal
              console.log('Checking next visit status for patient...');
              const statusResponse = await fetch(`/health_pwa/api/fso/${completedBookingId.value}/next_visit_status`);
              const statusData = await statusResponse.json();

              if (statusData.success) {
                // Update next visit data from status response
                nextVisitData.value.has_next_visit = statusData.data.has_next_visit;
                nextVisitData.value.patient_name = statusData.data.patient_name;
                nextVisitData.value.patient_id = statusData.data.patient_id;
                nextVisitData.value.next_visit_date = statusData.data.next_visit_date;
                nextVisitData.value.next_fso_id = statusData.data.next_fso_id;
                nextVisitData.value.assignment_notes = statusData.data.assignment_notes;

                if (statusData.data.has_next_visit) {
                  // Next visit already scheduled - populate Modal B with existing FSO details
                  console.log('Next visit already scheduled for:', statusData.data.next_visit_date);

                  // Store the next FSO ID for potential assignment deletion
                  nextVisitData.value.next_fso_id = statusData.data.next_fso_id;

                  // Parse and populate the date/time
                  if (statusData.data.next_visit_date) {
                    const nextDate = parseOdooDateTime(statusData.data.next_visit_date);
                    // Use local date methods to get the correct local date
                    const year = nextDate.getFullYear();
                    const month = String(nextDate.getMonth() + 1).padStart(2, '0');
                    const day = String(nextDate.getDate()).padStart(2, '0');
                    nextVisitFormData.value.scheduled_date = `${year}-${month}-${day}`; // YYYY-MM-DD format
                    nextVisitFormData.value.scheduled_time = `${String(nextDate.getHours()).padStart(2, '0')}:${String(nextDate.getMinutes()).padStart(2, '0')}`; // HH:MM format
                  }

                  // Populate assigned nurse with both ID and name
                  if (statusData.data.assigned_nurse && statusData.data.assigned_nurse.id) {
                    nextVisitFormData.value.assigned_nurse_id = statusData.data.assigned_nurse.id;
                    nextVisitFormData.value.assigned_nurse_name = statusData.data.assigned_nurse.name || '';
                  } else {
                    nextVisitFormData.value.assigned_nurse_id = null;
                    nextVisitFormData.value.assigned_nurse_name = '';
                  }

                  // Populate quote items if available
                  if (statusData.data.quote_items && statusData.data.quote_items.length > 0) {
                    nextVisitFormData.value.quote_items = statusData.data.quote_items;
                  } else {
                    nextVisitFormData.value.quote_items = [];
                  }

                  // Open Modal B with pre-populated data
                  showNextVisitModalB.value = true;
                  // Refresh bookings after a short delay to ensure UI updates
                  setTimeout(() => {
                    loadBookingsForDate(currentDate.value);
                  }, 300);
                } else {
                  // No next visit - open Modal A to ask if patient wants future visit
                  console.log('No next visit scheduled - opening modal');
                  showNextVisitModalA.value = true;
                  // Refresh bookings after a short delay to ensure UI updates
                  setTimeout(() => {
                    loadBookingsForDate(currentDate.value);
                  }, 300);
                }
              } else {
                // Error checking next visit - just refresh
                console.error('Error checking next visit:', statusData.error);
                alert('Service completed successfully!');
                loadBookingsForDate(currentDate.value);
              }
            } else {
              alert('Failed to complete service: ' + (data.error || 'Unknown error'));
            }
          } catch (err) {
            console.error('Complete service without quote error:', err);
            alert('Error completing service: ' + err.message);
          }
        };

        // Handle "No Future Visit" submission from Modal A
        const submitNoFutureVisit = async () => {
          if (!nextVisitFormData.value.no_future_visit_reason) {
            alert('Please select a reason');
            return;
          }

          if (nextVisitFormData.value.no_future_visit_reason === 'other' && !nextVisitFormData.value.other_reason_text) {
            alert('Please enter explanation for "Other" reason');
            return;
          }

          try {
            const reasonLabel = noFutureVisitReasons.find(r => r.value === nextVisitFormData.value.no_future_visit_reason)?.label || nextVisitFormData.value.no_future_visit_reason;
            const finalReason = nextVisitFormData.value.no_future_visit_reason === 'other'
              ? `Other: ${nextVisitFormData.value.other_reason_text}`
              : reasonLabel;

            const response = await fetch(`/health_pwa/api/fso/${completedBookingId.value}/no_future_visit`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                reason: finalReason
              })
            });

            const data = await response.json();
            console.log('No future visit response:', data);

            if (data.success) {
              alert('Noted: Patient does not need future visits');
              showNextVisitModalA.value = false;
              // Close modal and refresh to show today's bookings
              completedBookingId.value = null;
              // Reset form
              nextVisitFormData.value.no_future_visit_reason = '';
              nextVisitFormData.value.other_reason_text = '';
              // Refresh bookings list to reflect the change
              await loadBookingsForDate(currentDate.value);
            } else {
              alert('Failed to submit: ' + (data.error || 'Unknown error'));
            }
          } catch (err) {
            console.error('Submit no future visit error:', err);
            alert('Error submitting: ' + err.message);
          }
        };

        // Handle assignment deletion for next visit when nurse is cleared
        const deleteNextVisitAssignment = async (fsoId) => {
          try {
            if (!fsoId) return;

            // Call API to delete assignments for this FSO
            const response = await fetch(`/health_pwa/api/fso/${fsoId}/delete_assignments`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({})
            });

            const data = await response.json();
            if (data.success) {
              console.log('Assignments deleted successfully');
            } else {
              console.error('Failed to delete assignments:', data.error);
            }
          } catch (err) {
            console.error('Error deleting assignments:', err);
          }
        };

        // Handle "Schedule Next Visit" from Modal B
        const scheduleNextVisit = async () => {
          // Validation
          if (!nextVisitFormData.value.scheduled_date) {
            alert('Please select a date');
            return;
          }

          if (!nextVisitFormData.value.scheduled_time) {
            alert('Please select a time');
            return;
          }

          if (!nextVisitFormData.value.quote_items || nextVisitFormData.value.quote_items.length === 0) {
            alert('Please add at least one service');
            return;
          }

          // Optional: assigned_nurse_id can be null for unassigned bookings
          // No validation needed - user can choose to leave it unassigned

          try {
            // Convert local date/time to ISO format with timezone
            const isoDateTime = convertLocalDateTimeToISO(
              nextVisitFormData.value.scheduled_date,
              nextVisitFormData.value.scheduled_time,
              currentUser.value.timezone || 'UTC'
            );

            // Build request body - don't send assigned_staff_id when editing existing appointment
            const requestBody = {
              next_visit_date: isoDateTime,
              scheduled_datetime: isoDateTime,
              quote_items: nextVisitFormData.value.quote_items,
            };

            // Only send assigned_staff_id and next_fso_id for new appointments
            // When editing existing appointment (has_next_visit=true), do NOT update assignments
            if (!nextVisitData.value.has_next_visit) {
              requestBody.assigned_staff_id = nextVisitFormData.value.assigned_nurse_id;
            } else {
              // When editing existing, send next_fso_id so backend knows to update
              requestBody.next_fso_id = nextVisitData.value.next_fso_id;
            }

            const response = await fetch(`/health_pwa/api/fso/${completedBookingId.value}/schedule_next_visit`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify(requestBody)
            });

            const data = await response.json();
            console.log('Schedule next visit response:', data);

            if (data.success) {
              alert('Next visit scheduled successfully!');
              showNextVisitModalB.value = false;
              showProductCatalogModal.value = false; // Close catalog modal if still open
              // Refresh bookings for the newly scheduled date - convert string to Date object
              const scheduledDateObj = parseOdooDateTime(nextVisitFormData.value.scheduled_date + ' 00:00:00');
              await loadBookingsForDate(scheduledDateObj);
              completedBookingId.value = null;
              // Reset form
              nextVisitFormData.value = {
                scheduled_date: null,
                scheduled_time: null,
                quote_items: [],
                assigned_nurse_id: null,
                no_future_visit_reason: '',
                other_reason_text: ''
              };
              // Reset next visit data
              nextVisitData.value = {
                has_next_visit: false,
                patient_name: '',
                patient_id: null,
                next_visit_date: null,
                next_fso_id: null,
                assigned_staff: [],
                assignment_notes: ''
              };
            } else {
              alert('Failed to schedule: ' + (data.error || 'Unknown error'));
            }
          } catch (err) {
            console.error('Schedule next visit error:', err);
            alert('Error scheduling: ' + err.message);
          }
        };

        // Show client details view after booking completion
        const showClientDetails = (patientData) => {
          currentClientData.value = {
            id: patientData.patient_id,
            name: patientData.patient_name,
            phone: patientData.phone || 'N/A',
            age: patientData.age,
            gender: patientData.gender || 'N/A',
            patient_code: patientData.patient_code || 'N/A'
          };
          showClientDetailsView.value = true;
          showNextVisitModalA.value = false;
          showNextVisitModalB.value = false;
        };

        // Open next booking modal from client details
        const openNextBookingFromClientDetails = async () => {
          try {
            // For now, directly open Modal A (we can enhance to check if next visit exists)
            // Reset form with current user's employee ID
            nextVisitFormData.value = {
              scheduled_date: null,
              scheduled_time: null,
              quote_items: [],
              assigned_nurse_id: currentUser.value.employee_id,
              assigned_nurse_name: '',
              no_future_visit_reason: '',
              other_reason_text: ''
            };
            // Update nextVisitData with current patient
            nextVisitData.value.patient_id = currentClientData.value.id;
            nextVisitData.value.patient_name = currentClientData.value.name;

            showClientDetailsView.value = false;
            showNextVisitModalA.value = true;
          } catch (err) {
            console.error('Error opening next booking:', err);
            alert('Error: ' + err.message);
          }
        };

        // Open Modal B with current user pre-populated
        const openNextVisitModal = () => {
          // Reset form with current user's employee ID
          nextVisitFormData.value = {
            scheduled_date: null,
            scheduled_time: null,
            quote_items: [],
            assigned_nurse_id: currentUser.value.employee_id,  // Pre-populate with current user's employee ID
            assigned_nurse_name: currentUser.value.name || '',  // Pre-populate with current user's name
            no_future_visit_reason: '',
            other_reason_text: ''
          };
          showNextVisitModalA.value = false;
          showNextVisitModalB.value = true;
        };

        onMounted(() => {
          loadBookingsForDate(currentDate.value);
          loadMonthBookings(currentDate.value); // Load current month bookings
          loadCurrentUser(); // Load current user info
        });

        onUnmounted(() => {
          // Cleanup timer on unmount
          stopTimer();
        });

        return {
          bookings,
          groupedBookings,
          isLoading,
          error,
          staffName,
          displayDate,
          currentDate,
          viewMode,
          loadBookingsForDate,
          loadBookingsForWeek,
          loadBookingsForMonth,
          goToNext,
          goToPrevious,
          goToToday,
          setViewMode,
          handleTouchStart,
          handleTouchEnd,
          getStatusColor,
          getStatusDisplay,
          isRunningLate,
          callPatient,
          openMap,
          isTransitioning,
          // Calendar functions
          isCalendarOpen,
          calendarMonth,
          toggleCalendar,
          changeCalendarMonth,
          selectCalendarDate,
          getCalendarDays,
          hasBookingsOnDate,
          getBookingCount,
          datesWithBookings,
          // Future bookings modal
          isFutureBookingsOpen,
          futureBookingsByDate,
          loadingFutureBookings,
          loadFutureBookings,
          toggleFutureBookings,
          // Booking detail expansion
          selectedBookingId,
          selectedBookingDetail,
          isLoadingDetail,
          detailError,
          fetchBookingDetail,
          toggleBookingDetail,
          formattedScheduledDateTime,
          // Intake summary modal
          showIntakeSummaryModal,
          selectedBookingForIntake,
          toggleIntakeSummaryModal,
          // Service start and clinical notes
          serviceStartedForBooking,
          showClinicalNotesModal,
          clinicalNotesText,
          clinicalObservations,  // Doctor-specific field
          diagnosis,  // Doctor-specific field
          treatmentPerformed,  // Doctor-specific field
          capturedPhoto,
          photoPreviewUrl,
          startService,
          openClinicalNotesModal,
          closeClinicalNotesModal,
          capturePhoto,
          saveClinicalNotes,
          completeServiceWithoutQuoteInTodayView,
          // Timer and invoice
          timerInterval,
          currentTime,
          showInvoiceModal,
          quoteData,
          elapsedTime,
          isClinicalNotesComplete,
          startTimer,
          stopTimer,
          loadQuoteData,
          openInvoiceModal,
          // Invoice verification and payment workflow
          quoteVerified,
          quoteComments,
          hasLineModifications,
          showSaveMessage,
          showPaymentWizard,
          paymentWizardData,
          saveQuoteWithComments,
          openPaymentWizard,
          completePayment,
          // Next visit modal workflow
          completedBookingId,
          showNextVisitModalA,
          showNextVisitModalB,
          nextVisitData,
          nextVisitFormData,
          noFutureVisitReasons,
          showNoFutureVisitDropdown,
          submitNoFutureVisit,
          scheduleNextVisit,
          deleteNextVisitAssignment,
          openNextVisitModal,
          // Client details view
          showClientDetailsView,
          currentClientData,
          showClientDetails,
          openNextBookingFromClientDetails,
          // Product catalog modal
          showProductCatalogModal,
          catalogProducts,
          catalogSearchQuery,
          catalogLoading,
          catalogError,
          loadProductCatalog,
          addProductToQuote,
          openProductCatalogModal,
          // Current user info
          currentUser,
          // Timezone conversion helper
          convertLocalDateTimeToISO
        };
      },
      template: `
        <div class="today-view" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
          <!-- Header with centered navigation -->
          <div class="booking-header-main">
            <button @click="goToPrevious" class="btn-nav-arrow-header">
              <i class="material-icons">chevron_left</i>
            </button>

            <button @click="goToToday" class="tab-btn" :class="{ active: new Date().toDateString() === currentDate.toDateString() }">
              Today
            </button>

            <button @click="goToNext" class="btn-nav-arrow-header">
              <i class="material-icons">chevron_right</i>
            </button>
          </div>

          <!-- View mode tabs -->
          <div class="view-tabs">
            <button
              @click="setViewMode('day')"
              :class="{ active: viewMode === 'day' }"
              class="tab-btn tab-day"
            >
              Day
            </button>
            <button
              @click="setViewMode('week')"
              :class="{ active: viewMode === 'week' }"
              class="tab-btn tab-week"
            >
              Week
            </button>
            <button
              @click="setViewMode('month')"
              :class="{ active: viewMode === 'month' }"
              class="tab-btn tab-month"
            >
              Month
            </button>

            <button @click="toggleCalendar" class="btn-calendar-icon" title="Select date">
              <i class="material-icons">calendar_month</i>
            </button>
          </div>

          <!-- Date and staff info -->
          <div class="booking-date-section">
            <p class="staff-name">{{ staffName }}</p>
            <p class="date-display">{{ displayDate }}</p>
          </div>

          <!-- Content based on view mode -->
          <div v-if="isLoading" class="loading-spinner">
            <div class="spinner"></div>
            <p>Loading bookings...</p>
          </div>

          <div v-else-if="error" class="error-message">
            <i class="material-icons">error</i>
            <p>{{ error }}</p>
            <button @click="goToToday" class="btn btn-secondary">Retry</button>
          </div>

          <!-- Day view -->
          <div v-else-if="viewMode === 'day'">
            <div v-if="bookings.length === 0" class="empty-state">
              <i class="material-icons">event_note</i>
              <p>No bookings scheduled for this day</p>
            </div>

            <div v-else class="bookings-list">
              <div v-for="booking in bookings" :key="booking.fso_id" class="booking-card" @click="toggleBookingDetail(booking.fso_id)">
                  <!-- Header with time and status -->
                  <div class="booking-card-header">
                    <div class="booking-time-badge">{{ booking.formatted_time || booking.scheduled_time }}</div>
                    <div class="status-badge" :style="{ backgroundColor: getStatusColor(booking) }">
                      {{ getStatusDisplay(booking) }}
                    </div>
                  </div>

                  <!-- Patient info -->
                  <div class="booking-patient-section">
                    <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                  </div>

                  <!-- Service type with action buttons inline -->
                  <div class="booking-service-row">
                    <p v-if="booking.service_type" class="booking-service-type">{{ booking.service_type }}</p>
                    <div class="booking-action-icons">
                      <button @click.stop="callPatient(booking.patient_phone)" class="btn-icon-action btn-icon-call" title="Call patient">
                        <i class="material-icons">call</i>
                      </button>
                      <button @click.stop="openMap(booking.location, booking.patient_name)" class="btn-icon-action btn-icon-map" title="Open map">
                        <i class="material-icons">map</i>
                      </button>
                    </div>
                  </div>
              </div>
            </div>
          </div>

          <!-- Week view -->
          <div v-else-if="viewMode === 'week'">
            <div v-if="Object.keys(groupedBookings).length === 0" class="empty-state">
              <i class="material-icons">event_note</i>
              <p>No bookings scheduled for this week</p>
            </div>

            <div v-else class="grouped-bookings-list">
              <div v-for="(dateBookings, dateStr) in groupedBookings" :key="dateStr" class="date-group">
                <h4 class="date-group-title">{{ dateStr }}</h4>
                <div v-for="booking in dateBookings" :key="booking.fso_id" class="booking-card-container">
                  <!-- Clickable booking card -->
                  <div @click="toggleBookingDetail(booking.fso_id)" class="booking-card" :class="{ expanded: selectedBookingId === booking.fso_id }">
                    <!-- Header with time and status -->
                    <div class="booking-card-header">
                      <div class="booking-time-badge">{{ booking.scheduled_time }}</div>
                      <div class="status-badge" :style="{ backgroundColor: getStatusColor(booking) }">
                        {{ getStatusDisplay(booking) }}
                      </div>
                    </div>

                    <!-- Patient info -->
                    <div class="booking-patient-section">
                      <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                    </div>

                    <!-- Service type with action buttons inline -->
                    <div class="booking-service-row">
                      <p v-if="booking.service_type" class="booking-service-type">{{ booking.service_type }}</p>
                      <div class="booking-action-icons">
                        <button @click.stop="callPatient(booking.patient_phone)" class="btn-icon-action btn-icon-call" title="Call patient">
                          <i class="material-icons">call</i>
                        </button>
                        <button @click.stop="openMap(booking.location, booking.patient_name)" class="btn-icon-action btn-icon-map" title="Open map">
                          <i class="material-icons">map</i>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Month view -->
          <div v-else-if="viewMode === 'month'">
            <div v-if="Object.keys(groupedBookings).length === 0" class="empty-state">
              <i class="material-icons">event_note</i>
              <p>No bookings scheduled for this month</p>
            </div>

            <div v-else class="grouped-bookings-list">
              <div v-for="(dateBookings, dateStr) in groupedBookings" :key="dateStr" class="date-group">
                <h4 class="date-group-title">{{ dateStr }}</h4>
                <div v-for="booking in dateBookings" :key="booking.fso_id" class="booking-card-container">
                  <!-- Clickable booking card -->
                  <div @click="toggleBookingDetail(booking.fso_id)" class="booking-card" :class="{ expanded: selectedBookingId === booking.fso_id }">
                    <!-- Header with time and status -->
                    <div class="booking-card-header">
                      <div class="booking-time-badge">{{ booking.scheduled_time }}</div>
                      <div class="status-badge" :style="{ backgroundColor: getStatusColor(booking) }">
                        {{ getStatusDisplay(booking) }}
                      </div>
                    </div>

                    <!-- Patient info -->
                    <div class="booking-patient-section">
                      <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                    </div>

                    <!-- Service type with action buttons inline -->
                    <div class="booking-service-row">
                      <p v-if="booking.service_type" class="booking-service-type">{{ booking.service_type }}</p>
                      <div class="booking-action-icons">
                        <button @click.stop="callPatient(booking.patient_phone)" class="btn-icon-action btn-icon-call" title="Call patient">
                          <i class="material-icons">call</i>
                        </button>
                        <button @click.stop="openMap(booking.location, booking.patient_name)" class="btn-icon-action btn-icon-map" title="Open map">
                          <i class="material-icons">map</i>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Shared Booking Detail Modal -->
        <div v-if="selectedBookingId" class="modal-backdrop" @click="toggleBookingDetail(selectedBookingId)">
          <div class="booking-detail-modal" @click.stop>
            <div v-if="isLoadingDetail" class="detail-loading">
              <div class="spinner-small"></div>
              <p>Loading details...</p>
            </div>
            <div v-else-if="detailError" class="detail-error">
              <p>{{ detailError }}</p>
              <button class="btn btn-secondary" @click="toggleBookingDetail(selectedBookingId)">Close</button>
            </div>
            <div v-else-if="selectedBookingDetail" class="booking-detail-modal-content">
              <!-- Modal header with close button -->
              <div class="modal-header">
                <div class="header-content">
                  <h3 class="modal-title">Booking Details</h3>
                  <!-- Timer Display when service is in progress -->
                  <div v-if="serviceStartedForBooking === selectedBookingId" class="timer-badge">
                    <i class="material-icons">schedule</i>
                    <span>{{ elapsedTime }}</span>
                  </div>
                </div>
                <button @click="toggleBookingDetail(selectedBookingId)" class="btn-modal-close">
                  <i class="material-icons">close</i>
                </button>
              </div>

              <!-- Modal scrollable content -->
              <div class="modal-body">
                <!-- Scheduled Visit Section -->
                <div class="detail-section">
                  <h4 class="section-title">Scheduled Visit</h4>
                  <div class="detail-row">
                    <span class="label">Date & Time:</span>
                    <span class="value">{{ formattedScheduledDateTime }}</span>
                  </div>
                  <div v-if="selectedBookingDetail.quote_items.length > 0" class="detail-row">
                    <span class="label">Services:</span>
                    <span class="value">{{ selectedBookingDetail.quote_items.map(item => item.product_name).join(', ') }}</span>
                  </div>
                  <div v-if="selectedBookingDetail.package && selectedBookingDetail.package.name" class="detail-row">
                    <span class="label">Package:</span>
                    <span class="value">{{ selectedBookingDetail.package.name }}</span>
                  </div>
                </div>

                <!-- Contact Information Section -->
                <div class="detail-section">
                  <h4 class="section-title">Contact Information</h4>
                  <div v-if="selectedBookingDetail.address" class="detail-row">
                    <span class="label">
                      <i class="material-icons icon-inline">location_on</i>
                      Address:
                    </span>
                    <button @click="openMap(selectedBookingDetail.address, selectedBookingDetail.patient.name)" class="detail-link">
                      {{ selectedBookingDetail.address }}
                    </button>
                  </div>
                  <div v-if="selectedBookingDetail.primary_contact" class="detail-row">
                    <span class="label">Primary Contact:</span>
                    <div class="contact-info">
                      <span class="contact-name">{{ selectedBookingDetail.primary_contact.name }}</span>
                      <button @click.stop="callPatient(selectedBookingDetail.primary_contact.phone)" class="btn-icon-action btn-icon-call-small" title="Call">
                        <i class="material-icons">call</i>
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Intake Summary Button -->
                <button @click="toggleIntakeSummaryModal" class="btn-intake-summary">
                  <i class="material-icons">description</i>
                  <span>View Intake Summary</span>
                  <i class="material-icons">chevron_right</i>
                </button>
              </div>

              <!-- Modal footer with action buttons -->
              <div class="modal-footer">
                <!-- Before service start (hidden when completed) -->
                <div v-if="serviceStartedForBooking !== selectedBookingId && selectedBookingDetail?.state !== 'in_progress' && selectedBookingDetail?.state !== 'completed'" class="modal-footer-content">
                  <button class="btn btn-danger">Cancel/Refuse Visit</button>
                  <button @click="startService" class="btn btn-success">Start Service</button>
                </div>

                <!-- After service start or when already in progress -->
                <div v-if="serviceStartedForBooking === selectedBookingId || selectedBookingDetail?.state === 'in_progress'" class="modal-footer-content">
                  <button @click="openClinicalNotesModal" class="btn btn-clinical-notes">
                    <i class="material-icons">description</i>
                    <span>Clinical Notes</span>
                  </button>
                  <!-- Verify Invoice Button (always visible, disabled when no quote or clinical notes incomplete) -->
                  <button @click="openInvoiceModal"
                          :disabled="!selectedBookingDetail?.confirmation_requirements?.has_quote_with_items || !isClinicalNotesComplete"
                          class="btn btn-invoice"
                          :title="!selectedBookingDetail?.confirmation_requirements?.has_quote_with_items
                            ? 'No quote available'
                            : !isClinicalNotesComplete
                            ? 'Please fill in the clinical notes or take image of the notes to raise Invoice'
                            : 'Verify Invoice'">
                    <i class="material-icons">receipt</i>
                    <span>Verify Invoice</span>
                  </button>
                  <!-- Complete Service Button (shown only when no quote) -->
                  <button v-if="!selectedBookingDetail?.confirmation_requirements?.has_quote_with_items"
                          @click="completeServiceWithoutQuoteInTodayView"
                          :disabled="!isClinicalNotesComplete"
                          class="btn btn-success btn-complete-service"
                          :title="!isClinicalNotesComplete ? 'Please fill in the clinical notes or take image of the notes to Complete this service' : 'Complete Service'">
                    <i class="material-icons">check_circle</i>
                    <span>Complete Service</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Intake Summary Modal -->
        <div v-if="showIntakeSummaryModal && selectedBookingDetail" class="modal-backdrop" @click="toggleIntakeSummaryModal">
          <div class="intake-summary-modal" @click.stop>
            <!-- Modal header with back button -->
            <div class="modal-header">
              <button @click="toggleIntakeSummaryModal" class="btn-modal-back">
                <i class="material-icons">chevron_left</i>
              </button>
              <h3 class="modal-title">Intake Notes</h3>
              <div style="width: 40px;"></div>
            </div>

            <!-- Modal scrollable content -->
            <div class="modal-body">
              <!-- Diagnosis -->
              <div class="intake-form-group">
                <label class="intake-form-label">Diagnosis</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.diagnosis" placeholder="Type here..." readonly></textarea>
              </div>

              <!-- Referring Doctor -->
              <div class="intake-form-group">
                <div class="intake-form-header">
                  <label class="intake-form-label">Referring Doctor</label>
                  <button v-if="selectedBookingDetail.referring_doctor_name"
                    @click="callPatient(selectedBookingDetail.referring_doctor_phone || '')"
                    class="btn-icon-action btn-icon-call-small"
                    title="Call Referring Doctor">
                    <i class="material-icons">call</i>
                  </button>
                </div>
                <p class="intake-form-value">{{ selectedBookingDetail.referring_doctor_name || 'N/A' }}</p>
              </div>

              <!-- Goal of Care -->
              <div class="intake-form-group">
                <label class="intake-form-label">Goal of Care</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.goal_of_care" placeholder="Type here..." readonly></textarea>
              </div>

              <!-- Required Equipment -->
              <div class="intake-form-group">
                <label class="intake-form-label">Required Equipment</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.required_equipment" placeholder="Type here..." readonly></textarea>
              </div>

              <!-- Intake Notes -->
              <div class="intake-form-group">
                <label class="intake-form-label">Intake Notes</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.intake_notes" placeholder="Type here..." readonly></textarea>
              </div>
            </div>
          </div>
        </div>

        <!-- Clinical Notes Modal -->
        <div v-if="showClinicalNotesModal && selectedBookingDetail" class="modal-backdrop" @click="closeClinicalNotesModal">
          <div class="clinical-notes-modal" @click.stop>
            <!-- Modal header -->
            <div class="modal-header">
              <h3 class="modal-title">{{ currentUser.is_doctor ? 'Clinical Notes' : 'Clinical Notes' }}</h3>
              <button @click="closeClinicalNotesModal" class="btn-modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>

            <!-- Modal content -->
            <div class="modal-body">
              <!-- Doctor mode: Three separate fields -->
              <template v-if="currentUser.is_doctor">
                <!-- Clinical Observations -->
                <div class="clinical-form-group">
                  <label class="clinical-form-label">Clinical Observations</label>
                  <textarea
                    v-model="clinicalObservations"
                    class="clinical-form-field"
                    placeholder="Enter clinical observations..."
                    rows="4"></textarea>
                </div>

                <!-- Diagnosis -->
                <div class="clinical-form-group">
                  <label class="clinical-form-label">Diagnosis</label>
                  <textarea
                    v-model="diagnosis"
                    class="clinical-form-field"
                    placeholder="Enter diagnosis..."
                    rows="4"></textarea>
                </div>

                <!-- Treatment Performed -->
                <div class="clinical-form-group">
                  <label class="clinical-form-label">Treatment Performed</label>
                  <textarea
                    v-model="treatmentPerformed"
                    class="clinical-form-field"
                    placeholder="Describe treatment provided..."
                    rows="4"></textarea>
                </div>
              </template>

              <!-- Non-doctor mode: Single notes field -->
              <template v-else>
                <div class="clinical-form-group">
                  <label class="clinical-form-label">Notes</label>
                  <textarea
                    v-model="clinicalNotesText"
                    class="clinical-form-field"
                    placeholder="Enter clinical notes..."
                    rows="6"></textarea>
                </div>
              </template>

              <!-- Photo capture section (for both modes) -->
              <div class="clinical-form-group">
                <label class="clinical-form-label">Attach Photo</label>
                <div class="photo-upload-container">
                  <input
                    type="file"
                    ref="photoInput"
                    @change="capturePhoto"
                    accept="image/*"
                    capture="environment"
                    class="photo-input"
                  />
                  <button @click="$refs.photoInput?.click()" class="btn-photo-capture">
                    <i class="material-icons">camera_alt</i>
                    <span>Take Photo</span>
                  </button>
                </div>

                <!-- Photo preview -->
                <div v-if="photoPreviewUrl" class="photo-preview">
                  <img :src="photoPreviewUrl" alt="Preview" />
                  <button @click="() => { capturedPhoto = null; photoPreviewUrl = null; }" class="btn-remove-photo">
                    <i class="material-icons">close</i>
                  </button>
                </div>
              </div>
            </div>

            <!-- Modal footer -->
            <div class="clinical-modal-footer">
              <button @click="closeClinicalNotesModal" class="btn btn-secondary">Cancel</button>
              <button @click="saveClinicalNotes" class="btn btn-success">Save</button>
            </div>
          </div>
        </div>

        <!-- Invoice Verification Modal -->
        <div v-if="showInvoiceModal && quoteData" class="modal-overlay" @click.self="showInvoiceModal = false">
          <div class="modal-content invoice-modal">
            <div class="modal-header">
              <h3>
                <i class="material-icons">receipt</i>
                Verify Invoice
              </h3>
              <button @click="showInvoiceModal = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div class="modal-body" v-if="quoteData">
              <!-- Quote Information -->
              <div class="invoice-header">
                <div class="invoice-info">
                  <h4>{{ quoteData.name }}</h4>
                  <span :class="'badge badge-' + (quoteData.state === 'sale' ? 'success' : 'info')">
                    {{ quoteData.state }}
                  </span>
                </div>
              </div>

              <!-- Quote Items Table - Editable Qty and Discount -->
              <div class="invoice-lines">
                <!-- Message to Save Quote if modifications detected -->
                <div v-if="showSaveMessage" class="info-message-box">
                  Save Quote to display updated Total
                </div>

                <!-- Invoice Items - Card Layout -->
                <div class="invoice-items-container">
                  <template v-for="line in quoteData.order_lines" :key="line.id">
                    <!-- Product Card -->
                    <div class="invoice-item-card">
                      <!-- Row 1: Product Name (Full Width) -->
                      <div class="invoice-item-row-product">
                        <div class="product-name-cell">{{ line.product_name }}</div>
                      </div>

                      <!-- Row 2: Qty, Disc%, Price, Total -->
                      <div class="invoice-item-row-details">
                        <div class="detail-cell qty-cell">
                          <label>Qty</label>
                          <input
                            type="number"
                            v-model.number="line.quantity"
                            class="editable-input"
                            min="1"
                            step="0.01">
                        </div>
                        <div class="detail-cell disc-cell">
                          <label>Disc %</label>
                          <input
                            type="number"
                            v-model.number="line.discount"
                            class="editable-input"
                            min="0"
                            max="100"
                            step="0.01"
                            placeholder="0">
                        </div>
                        <div class="detail-cell price-cell">
                          <label>Price</label>
                          <span>{{ line.unit_price.toLocaleString() }}</span>
                        </div>
                        <div class="detail-cell total-cell">
                          <label>Total</label>
                          <span>{{ (line.quantity * line.unit_price * (1 - (line.discount || 0) / 100)).toLocaleString() }}</span>
                        </div>
                      </div>

                      <!-- Row 3: Discount Reason (When Applicable) -->
                      <div v-if="line.discount > 0" class="invoice-item-row-reason">
                        <label class="discount-reason-label">Discount Reason:</label>
                        <input
                          type="text"
                          v-model="line.discount_reason"
                          class="editable-input discount-reason-input-full"
                          placeholder="Required: Explain discount"
                          required>
                      </div>
                    </div>
                  </template>
                </div>

                <!-- Totals Section -->
                <div class="invoice-totals">
                  <div class="totals-row">
                    <span>Subtotal</span>
                    <span>{{ quoteData.amount_untaxed.toLocaleString() }}</span>
                  </div>
                  <div class="totals-row">
                    <span>Tax</span>
                    <span>{{ quoteData.amount_tax.toLocaleString() }}</span>
                  </div>
                  <div class="totals-row totals-total">
                    <strong>Total</strong>
                    <strong>{{ quoteData.amount_total.toLocaleString() }} {{ quoteData.currency }}</strong>
                  </div>
                </div>
              </div>

              <!-- Verification Notes - Mandatory if changes made -->
              <div v-if="!quoteVerified" class="form-group">
                <label class="clinical-form-label">
                  Verification Notes
                  <span v-if="hasLineModifications" class="required-indicator">*</span>
                </label>
                <textarea
                  v-model="quoteComments"
                  class="clinical-form-field"
                  :placeholder="hasLineModifications ? 'Required: Explain the changes made to Qty or Discount...' : 'Add any general comments about this invoice...'"
                  rows="3"></textarea>
              </div>

              <!-- Success Message -->
              <div v-if="quoteVerified" class="success-message">
                <i class="material-icons">check_circle</i>
                <p>Invoice verified successfully!</p>
              </div>
            </div>

            <!-- Modal Footer -->
            <div class="modal-footer">
              <button @click="showInvoiceModal = false" class="btn btn-secondary">Cancel</button>
              <button v-if="!quoteVerified" @click="saveQuoteWithComments" class="btn btn-primary">
                <i class="material-icons">save</i>
                <span>Save Quote</span>
              </button>
              <button v-else @click="openPaymentWizard" class="btn btn-success">
                <i class="material-icons">payment</i>
                <span>Payment</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Payment Wizard Modal -->
        <div v-if="showPaymentWizard && quoteVerified" class="modal-overlay" @click.self="showPaymentWizard = false">
          <div class="modal-content payment-wizard-modal">
            <div class="modal-header">
              <h3>
                <i class="material-icons">payment</i>
                Complete Service - Payment Collection
              </h3>
              <button @click="showPaymentWizard = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>

            <div class="modal-body">
              <!-- Payment Choice Section -->
              <div class="form-section">
                <h4>Payment Timing</h4>
                <div class="form-group">
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_choice"
                      value="pay_now">
                    <span>Pay Now</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_choice"
                      value="pay_later">
                    <span>Pay Later</span>
                  </label>
                </div>
              </div>

              <!-- Payment Method Section (only show if paying now) -->
              <div v-if="paymentWizardData.payment_choice === 'pay_now'" class="form-section">
                <h4>Payment Method</h4>
                <div class="form-group">
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_method"
                      value="cash">
                    <span>Cash</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_method"
                      value="card">
                    <span>Card</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_method"
                      value="bank_transfer">
                    <span>Bank Transfer</span>
                  </label>
                </div>
              </div>

              <!-- Service Notes -->
              <div class="form-section">
                <h4>Service Notes</h4>
                <div class="form-group">
                  <textarea
                    v-model="paymentWizardData.service_notes"
                    class="clinical-form-field"
                    placeholder="Enter any additional service or payment notes..."
                    rows="3"></textarea>
                </div>
              </div>

              <!-- Invoice Creation Option -->
              <div class="form-section">
                <div class="form-group">
                  <label>
                    <input
                      type="checkbox"
                      v-model="paymentWizardData.create_invoice_now">
                    <span>Create Invoice Now</span>
                  </label>
                </div>
              </div>

              <!-- Order Summary -->
              <div class="info-grid">
                <div class="info-item">
                  <label>Amount</label>
                  <span>{{ quoteData?.amount_total?.toLocaleString() || '0' }} {{ quoteData?.currency || 'VND' }}</span>
                </div>
                <div class="info-item">
                  <label>Payment</label>
                  <span>{{ paymentWizardData.payment_choice === 'pay_now' ? 'Now' : 'Later' }}</span>
                </div>
              </div>
            </div>

            <div class="modal-footer">
              <button @click="showPaymentWizard = false" class="btn btn-secondary">Cancel</button>
              <button @click="completePayment" class="btn btn-success">
                <i class="material-icons">check_circle</i>
                <span>Complete Service</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Client Details View -->
        <div v-if="showClientDetailsView" class="client-details-view">
          <div class="client-details-container">
            <div class="client-details-header">
              <h2>
                <i class="material-icons">person</i>
                {{ currentClientData.name }}
              </h2>
              <button @click="showClientDetailsView = false" class="btn-back">
                <i class="material-icons">arrow_back</i>
              </button>
            </div>

            <div class="client-details-card">
              <div class="detail-item">
                <label>Patient Code</label>
                <span>{{ currentClientData.patient_code }}</span>
              </div>
              <div class="detail-item">
                <label>Phone</label>
                <span>{{ currentClientData.phone }}</span>
              </div>
              <div class="detail-item">
                <label>Age</label>
                <span>{{ currentClientData.age || 'N/A' }}</span>
              </div>
              <div class="detail-item">
                <label>Gender</label>
                <span>{{ currentClientData.gender }}</span>
              </div>
            </div>

            <button @click="openNextBookingFromClientDetails" class="btn btn-primary btn-lg next-booking-btn">
              <i class="material-icons">add_event</i>
              Next Booking
            </button>
          </div>
        </div>

        <!-- Next Visit Modal A: No future visit scheduled -->
        <div v-if="showNextVisitModalA" class="modal-overlay" @click.self="showNextVisitModalA = false">
          <div class="modal-content next-visit-modal">
            <div class="modal-header">
              <h3>
                <i class="material-icons">calendar_today</i>
                Schedule Next Appointment?
              </h3>
              <button @click="showNextVisitModalA = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div class="modal-body">
              <p class="next-visit-message">
                No future visits are currently scheduled for <strong>{{ nextVisitData.patient_name }}</strong>
              </p>

              <div class="next-visit-actions">
                <!-- Button 1: Schedule Next Visit -->
                <button @click="openNextVisitModal" class="btn btn-primary btn-lg">
                  <i class="material-icons">add_event</i>
                  Schedule Next Visit
                </button>

                <!-- Button 2: Client does not need future visits -->
                <button @click="showNoFutureVisitDropdown = !showNoFutureVisitDropdown" class="btn btn-secondary btn-lg">
                  <i class="material-icons">block</i>
                  Client does not need or want a next visit
                </button>
              </div>

              <!-- Dropdown for no future visit reasons -->
              <div v-if="showNoFutureVisitDropdown" class="no-future-visit-section">
                <label class="form-label">Why is there no future visit?</label>
                <select v-model="nextVisitFormData.no_future_visit_reason" class="form-control">
                  <option value="">-- Select a reason --</option>
                  <option v-for="reason in noFutureVisitReasons" :key="reason.value" :value="reason.value">
                    {{ reason.label }}
                  </option>
                </select>

                <!-- Text input for "Other" reason -->
                <div v-if="nextVisitFormData.no_future_visit_reason === 'other'" class="other-reason-section">
                  <label class="form-label">Please explain:</label>
                  <textarea
                    v-model="nextVisitFormData.other_reason_text"
                    class="form-control"
                    placeholder="Explain why there is no future visit..."
                    rows="3"></textarea>
                </div>

                <!-- Submit button for no future visit -->
                <div class="form-actions">
                  <button @click="showNoFutureVisitDropdown = false" class="btn btn-secondary">Cancel</button>
                  <button @click="submitNoFutureVisit" class="btn btn-success">Submit</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Next Visit Modal B: Schedule next appointment -->
        <div v-if="showNextVisitModalB" class="modal-overlay" @click.self="showNextVisitModalB = false">
          <div class="modal-content next-visit-modal">
            <div class="modal-header">
              <div class="header-content">
                <!-- Show "Next Appointment Details" when editing existing, otherwise "Schedule Next Appointment" -->
                <h3 v-if="nextVisitData.has_next_visit">
                  <i class="material-icons">edit</i>
                  Next Appointment Details
                </h3>
                <h3 v-else>
                  <i class="material-icons">event</i>
                  Schedule Next Appointment
                </h3>
              </div>
              <button @click="showNextVisitModalB = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div class="modal-body">
              <!-- Check My Schedule Button -->
              <div class="check-schedule-section">
                <button @click="toggleFutureBookings" class="btn btn-secondary btn-check-schedule">
                  <i class="material-icons">calendar_today</i>
                  Check my schedule
                </button>
              </div>

              <!-- Date and Time Section -->
              <div class="form-section">
                <h4>Appointment Date &amp; Time</h4>
                <div class="form-row date-time-row">
                  <div class="form-group date-time-group">
                    <div class="date-time-input">
                      <label class="date-time-label">Date</label>
                      <input
                        type="date"
                        v-model="nextVisitFormData.scheduled_date"
                        class="form-control date-time-control">
                    </div>
                  </div>
                  <div class="form-group date-time-group">
                    <div class="date-time-input">
                      <label class="date-time-label">Time</label>
                      <input
                        type="time"
                        v-model="nextVisitFormData.scheduled_time"
                        class="form-control date-time-control">
                    </div>
                  </div>
                </div>
              </div>

              <!-- Services Section -->
              <div class="form-section">
                <h4>Services to be Provided</h4>
                <div v-if="nextVisitFormData.quote_items && nextVisitFormData.quote_items.length > 0" class="services-list">
                  <div v-for="(item, index) in nextVisitFormData.quote_items" :key="index" class="service-item">
                    <span class="service-name">{{ item.product_name || item.name }}</span>
                    <span class="service-qty">Qty: {{ item.quantity }}</span>
                    <button @click="nextVisitFormData.quote_items.splice(index, 1)" class="btn-remove">
                      <i class="material-icons">delete</i>
                    </button>
                  </div>
                </div>
                <div v-else class="no-services-message">
                  No services selected yet
                </div>
                <button @click="openProductCatalogModal" class="btn btn-secondary btn-sm">
                  <i class="material-icons">add</i>
                  Add from Catalog
                </button>
              </div>

              <!-- Assigned Healthcare Staff Section -->
              <div class="form-section">
                <h4>Assigned Healthcare Staff</h4>
                <div class="form-group">
                  <!-- Show all assigned staff when editing existing appointment -->
                  <div v-if="nextVisitData.has_next_visit && nextVisitData.assigned_staff && nextVisitData.assigned_staff.length > 0" class="assigned-staff-list">
                    <div v-for="staff in nextVisitData.assigned_staff" :key="staff.id" class="assigned-staff-box">
                      <div class="assigned-staff-display">
                        <i class="material-icons">person_check</i>
                        <div class="staff-info">
                          <strong>{{ staff.name }}</strong>
                          <small class="staff-role">{{ staff.role }}</small>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Show single nurse for new appointment -->
                  <div v-else-if="!nextVisitData.has_next_visit && nextVisitFormData.assigned_nurse_id" class="assigned-staff-box">
                    <div class="assigned-staff-display">
                      <i class="material-icons">person_check</i>
                      <strong>{{ nextVisitFormData.assigned_nurse_name || currentUser.name }}</strong>
                    </div>
                  </div>

                  <!-- Show unassigned message -->
                  <div v-else class="unassigned-staff-box">
                    <i class="material-icons">person_outline</i>
                    <strong>No staff assigned</strong>
                    <small v-if="!nextVisitData.has_next_visit">Booking will be created in CONFIRMED state (unassigned)</small>
                  </div>

                  <!-- Show clear assignment button only for new appointments -->
                  <div v-if="!nextVisitData.has_next_visit && nextVisitFormData.assigned_nurse_id" class="button-row">
                    <button @click="() => {
                      deleteNextVisitAssignment(nextVisitData.next_fso_id);
                      nextVisitFormData.assigned_nurse_id = null;
                    }" class="btn-clear-assignment">
                      <i class="material-icons">close</i>
                      Clear Assignment
                    </button>
                  </div>
                </div>
              </div>

              <!-- Order Summary -->
              <div class="order-summary">
                <div class="summary-item">
                  <label>Services</label>
                  <span>{{ nextVisitFormData.quote_items?.length || 0 }} item(s)</span>
                </div>
                <div class="summary-item">
                  <label>Scheduled For</label>
                  <span v-if="nextVisitFormData.scheduled_date && nextVisitFormData.scheduled_time">
                    {{ nextVisitFormData.scheduled_date }} at {{ nextVisitFormData.scheduled_time }}
                  </span>
                  <span v-else>Not set</span>
                </div>
              </div>
            </div>

            <div class="modal-footer">
              <button @click="showNextVisitModalB = false" class="btn btn-secondary">Cancel</button>
              <button @click="scheduleNextVisit" class="btn btn-success">
                <i class="material-icons">check_circle</i>
                Schedule Visit
              </button>
            </div>
          </div>
        </div>

        <!-- Product Catalog Modal - LAST for highest z-index layering -->
        <div v-if="showProductCatalogModal" class="modal-overlay catalog-modal-overlay" @click.self="showProductCatalogModal = false">
          <div class="modal-content product-catalog-modal">
            <div class="modal-header">
              <h3>
                <i class="material-icons">shopping_cart</i>
                Select Services from Catalog
              </h3>
              <button @click="showProductCatalogModal = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div class="modal-body">
              <!-- Selected Products Summary - Show at Top -->
              <div v-if="nextVisitFormData.quote_items && nextVisitFormData.quote_items.length > 0" class="form-section selected-items-summary">
                <h4>Selected Services</h4>
                <div class="selected-items-list">
                  <div v-for="(item, index) in nextVisitFormData.quote_items" :key="index" class="selected-item">
                    <div class="selected-item-info">
                      <span class="selected-item-name">{{ item.product_name }}</span>
                      <span class="selected-item-qty">Qty: {{ item.quantity }}</span>
                    </div>
                    <button @click="nextVisitFormData.quote_items.splice(index, 1)" class="btn-remove-small">
                      <i class="material-icons">close</i>
                    </button>
                  </div>
                </div>
              </div>

              <!-- Search Section -->
              <div class="form-section search-section-compact">
                <label class="search-label-centered">Search Products</label>
                <input
                  type="text"
                  v-model="catalogSearchQuery"
                  placeholder="Search by product name or code..."
                  class="form-control search-control-clean"
                  @keyup="loadProductCatalog">
              </div>

              <!-- Loading State -->
              <div v-if="catalogLoading" class="loading-state">
                <p>Loading products...</p>
              </div>

              <!-- Error State -->
              <div v-else-if="catalogError" class="error-state">
                <p style="color: #e74c3c;">Error: {{ catalogError }}</p>
              </div>

              <!-- Products Grid -->
              <div v-else-if="catalogProducts.length > 0" class="products-grid">
                <div v-for="product in catalogProducts" :key="product.id" class="product-card">
                  <div class="product-info">
                    <h5 class="product-name">{{ product.name }}</h5>
                    <p class="product-code" v-if="product.code">Code: {{ product.code }}</p>
                    <p class="product-price">
                      {{ product.price.toLocaleString() }} {{ product.currency }}
                    </p>
                    <p class="product-category" v-if="product.category">{{ product.category }}</p>
                  </div>
                  <button @click="addProductToQuote(product)" class="btn btn-primary btn-sm">
                    <i class="material-icons">add_shopping_cart</i>
                    Add
                  </button>
                </div>
              </div>

              <!-- Empty State -->
              <div v-else class="empty-state">
                <p>No products found</p>
              </div>
            </div>

            <div class="modal-footer">
              <button @click="showProductCatalogModal = false" class="btn btn-secondary">Close</button>
            </div>
          </div>
        </div>

        <!-- Calendar Picker Modal -->
        <div v-if="isCalendarOpen" class="calendar-overlay" @click.self="toggleCalendar">
          <div class="calendar-modal">
            <div class="calendar-header">
              <button @click="changeCalendarMonth(-1)" class="btn-month-nav">
                <i class="material-icons">chevron_left</i>
              </button>
              <h3 class="calendar-month-title">{{ calendarMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) }}</h3>
              <button @click="changeCalendarMonth(1)" class="btn-month-nav">
                <i class="material-icons">chevron_right</i>
              </button>
            </div>

            <div class="calendar-weekdays">
              <div class="weekday">Sun</div>
              <div class="weekday">Mon</div>
              <div class="weekday">Tue</div>
              <div class="weekday">Wed</div>
              <div class="weekday">Thu</div>
              <div class="weekday">Fri</div>
              <div class="weekday">Sat</div>
            </div>

            <div class="calendar-grid">
              <button
                v-for="(day, index) in getCalendarDays"
                :key="index"
                @click="day ? selectCalendarDate(day) : null"
                :class="{
                  'calendar-day': true,
                  'empty': !day,
                  'has-booking': day && hasBookingsOnDate(day),
                  'is-today': day && new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), day).toDateString() === new Date().toDateString(),
                  'is-selected': day && new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), day).toDateString() === currentDate.toDateString()
                }"
              >
                {{ day }}
                <span v-if="day && hasBookingsOnDate(day)" class="booking-dot"></span>
              </button>
            </div>

            <button @click="toggleCalendar" class="btn-close-calendar">Close</button>
          </div>
        </div>

        <!-- Future Bookings Modal -->
        <div v-if="isFutureBookingsOpen" class="calendar-overlay" @click.self="toggleFutureBookings">
          <div class="calendar-modal future-bookings-modal">
            <div class="future-bookings-top-bar">
              <button @click="toggleFutureBookings" class="btn-close-modal">
                <span>Close</span>
              </button>
            </div>

            <div class="future-bookings-header">
              <h3>Upcoming Bookings</h3>
            </div>

            <div class="future-bookings-content">
              <div v-if="loadingFutureBookings" class="loading-spinner">
                <div class="spinner"></div>
                <p>Loading bookings...</p>
              </div>

              <div v-else-if="Object.keys(futureBookingsByDate).length === 0" class="empty-state">
                <i class="material-icons">calendar_today</i>
                <p>No upcoming bookings scheduled</p>
              </div>

              <div v-else class="grouped-bookings-list">
                <div v-for="(dateData, dateStr) in futureBookingsByDate" :key="dateStr" class="date-group">
                  <h4 class="date-group-title">{{ dateData.date_display }}</h4>
                  <div v-for="booking in dateData.bookings" :key="booking.id" class="booking-card-container">
                    <!-- Booking card -->
                    <div class="booking-card">
                      <!-- Header with time and status -->
                      <div class="booking-card-header">
                        <div class="booking-time-badge">{{ booking.scheduled_time }}</div>
                        <div class="status-badge" :style="{ backgroundColor: getStatusColor({state: booking.state}) }">
                          {{ getStatusDisplay({state: booking.state}) }}
                        </div>
                      </div>

                      <!-- Patient info -->
                      <div class="booking-patient-section">
                        <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                      </div>

                      <!-- Service type with action buttons inline -->
                      <div class="booking-service-row">
                        <p v-if="booking.service_type" class="booking-service-type">{{ booking.service_type }}</p>
                        <div class="booking-action-icons">
                          <button @click.stop="callPatient(booking.phone)" class="btn-icon-action btn-icon-call" title="Call patient">
                            <i class="material-icons">call</i>
                          </button>
                          <button v-if="booking.address" @click.stop="openMap({gps_coordinates: booking.address}, booking.patient_name)" class="btn-icon-action btn-icon-map" title="Open map">
                            <i class="material-icons">map</i>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
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
            const scheduledDate = parseOdooDateTime(order.scheduled_datetime);
            return scheduledDate >= now;
          }).sort((a, b) => {
            // Sort by scheduled_datetime ascending (earliest first)
            return parseOdooDateTime(a.scheduled_datetime) - parseOdooDateTime(b.scheduled_datetime);
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
            const scheduledDate = parseOdooDateTime(order.scheduled_datetime);
            return scheduledDate < now;
          }).sort((a, b) => {
            // Sort by scheduled_datetime descending (most recent first)
            return parseOdooDateTime(b.scheduled_datetime) - parseOdooDateTime(a.scheduled_datetime);
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

    /* ========================================
       LEGACY CODE - Order Detail View Component
       This component is no longer used - the Booking List Modal View is the active interface
       Commented out to eliminate duplicate code and reduce confusion
       ======================================== */
    /*
    app.component('order-detail-view', {
      props: ['orderId', 'isOnline'],
      emits: ['navigate'],
      setup(props, { emit }) {
        console.log('=== order-detail-view COMPONENT SETUP CALLED ===');
        const { ref, onMounted, computed, watch } = Vue;

        const order = ref(null);
        const isLoading = ref(true);
        const error = ref(null);
        const timerInterval = ref(null);
        const currentTime = ref(new Date());
        const showClinicalNotes = ref(false);
        const showInvoice = ref(false);

        // Add a watcher to log when showInvoice changes
        watch(showInvoice, (newVal) => {
          console.log('showInvoice changed to:', newVal);
        });

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

        // Add a watcher to log when showPaymentWizard changes
        watch(showPaymentWizard, (newVal) => {
          console.log('showPaymentWizard changed to:', newVal);
          console.log('Current showPaymentWizard.value:', showPaymentWizard.value);
        });

        const paymentWizardData = ref({
          payment_choice: 'pay_now',
          payment_method: 'cash',
          service_notes: '',
          create_invoice_now: true
        });

        // Quote verification tracking
        const quoteVerified = ref(false);
        const quoteComments = ref('');

        // Next Visit Modal State Management
        const showNextVisitModalA = ref(false);  // Modal for "No next visit scheduled"
        const showNextVisitModalB = ref(false);  // Modal for "Schedule next visit"
        const nextVisitData = ref({
          has_next_visit: false,
          patient_name: '',
          next_visit_date: null,
          next_fso_id: null,
          quote_items: [],
          assigned_nurse_id: null,
          assigned_nurse_name: '',
          assigned_staff: []
        });
        const nextVisitFormData = ref({
          scheduled_date: null,
          scheduled_time: null,
          quote_items: [],
          assigned_nurse_id: null,
          no_future_visit_reason: '',
          other_reason_text: ''
        });
        const showNoFutureVisitDropdown = ref(false);
        const noFutureVisitReasons = [
          { value: 'patient_died', label: 'Patient died' },
          { value: 'improved', label: 'Patient improved/recovered' },
          { value: 'hospital', label: 'Patient admitted to hospital' },
          { value: 'declined', label: 'Patient declined further visits' },
          { value: 'moved', label: 'Patient moved/relocated' },
          { value: 'referral', label: 'Referred to another provider' },
          { value: 'other', label: 'Other' }
        ];

        // Computed elapsed time for timer
        const elapsedTime = computed(() => {
          if (!order.value || !order.value.actual_start_datetime) return '00:00:00';

          const startTime = parseOdooDateTime(order.value.actual_start_datetime);
          const endTime = order.value.actual_end_datetime ? parseOdooDateTime(order.value.actual_end_datetime) : currentTime.value;
          const diff = Math.floor((endTime - startTime) / 1000);

          const hours = Math.floor(diff / 3600);
          const minutes = Math.floor((diff % 3600) / 60);
          const seconds = diff % 60;

          return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        });

        const loadOrder = async () => {
          console.log('=== loadOrder called ===');
          try {
            isLoading.value = true;
            error.value = null;

            if (window.healthPWA?.storageManager) {
              console.log('Retrieving order data from PouchDB for orderId:', props.orderId);
              const orderData = await window.healthPWA.storageManager.getFieldServiceOrder(props.orderId);
              console.log('Retrieved order data:', orderData);

              if (orderData) {
                order.value = orderData;
                console.log('Loaded order details:', orderData);

                // Load clinical notes if available
                console.log('Processing clinical notes from order...');
                if (orderData.clinical_notes) {
                  console.log('Setting clinical_notes:', orderData.clinical_notes);
                  clinicalNotesData.value.clinical_notes = orderData.clinical_notes;
                }
                if (orderData.diagnosis) {
                  console.log('Setting diagnosis:', orderData.diagnosis);
                  clinicalNotesData.value.diagnosis = orderData.diagnosis;
                }
                if (orderData.treatment_performed) {
                  console.log('Setting treatment_performed:', orderData.treatment_performed);
                  clinicalNotesData.value.treatment_performed = orderData.treatment_performed;
                }
                if (orderData.medications_prescribed) {
                  console.log('Setting medications_prescribed:', orderData.medications_prescribed);
                  clinicalNotesData.value.medications_prescribed = orderData.medications_prescribed;
                }
                if (orderData.vital_signs) {
                  console.log('Setting vital_signs:', orderData.vital_signs);
                  clinicalNotesData.value.vital_signs = orderData.vital_signs;
                }

                console.log('Final clinicalNotesData.value:', clinicalNotesData.value);

                // Start timer if service is in progress
                if (orderData.state === 'in_progress' && orderData.actual_start_datetime && !orderData.actual_end_datetime) {
                  console.log('Starting timer...');
                  startTimer();
                }
              } else {
                console.log('❌ Order not found in storage');
                error.value = 'Order not found';
              }
            } else {
              console.log('❌ Storage manager not available');
              error.value = 'Storage manager not available';
            }
          } catch (err) {
            console.error('Failed to load order:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
            console.log('=== loadOrder completed ===');
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
          console.log('=== openPaymentWizard called ===');
          console.log('clinicalNotesData.value:', clinicalNotesData.value);
          console.log('clinicalNotesData.value.clinical_notes:', clinicalNotesData.value.clinical_notes);
          console.log('showPaymentWizard.value (before):', showPaymentWizard.value);

          // Validate clinical notes are filled before allowing completion
          // Only clinical_notes text is required (user provided clinical notes text)
          if (!clinicalNotesData.value.clinical_notes || !clinicalNotesData.value.clinical_notes.trim()) {
            console.log('❌ Clinical notes validation FAILED');
            console.log('clinical_notes is empty or whitespace:', !clinicalNotesData.value.clinical_notes || !clinicalNotesData.value.clinical_notes.trim());
            window.healthPWA.showNotification(
              'Please fill in Clinical Notes before completing the service. Click "Clinical Notes" button to add them.',
              'warning',
              7000
            );
            return;
          }

          console.log('✅ Clinical notes validation PASSED');

          // Load quote data to get calculated amount (but don't show invoice modal)
          console.log('Calling loadQuote(false)...');
          loadQuote(false);

          console.log('Setting showPaymentWizard.value = true');
          showPaymentWizard.value = true;
          console.log('showPaymentWizard.value (after):', showPaymentWizard.value);
          console.log('=== openPaymentWizard completed ===');
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
          console.log('=== saveClinicalNotes called ===');
          console.log('clinicalNotesData.value:', clinicalNotesData.value);

          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot save clinical notes while offline', 'error');
            return;
          }

          try {
            console.log('Posting clinical notes to server...');
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
              console.log('✅ Clinical notes saved successfully');
              window.healthPWA.showNotification(data.data.message || 'Clinical notes saved successfully!', 'success');
              showClinicalNotes.value = false;

              // Update local clinicalNotesData state immediately
              // This ensures the payment wizard validation can pass without waiting for server reload
              clinicalNotesData.value = {
                ...clinicalNotesData.value,
                // Keep the values the user just saved
              };
              console.log('Updated local clinicalNotesData:', clinicalNotesData.value);

              // Reload order data from server to refresh cache
              // This ensures PouchDB is updated with latest clinical notes
              try {
                console.log('Fetching fresh order data from server...');
                const refreshResponse = await fetch(`/health_pwa/api/fso/${props.orderId}`, {
                  headers: {
                    'Content-Type': 'application/json',
                  }
                });
                const refreshData = await refreshResponse.json();
                console.log('Server refresh response:', refreshData);

                if (refreshData.success && refreshData.data) {
                  console.log('✅ Server returned fresh order data');
                  console.log('Server clinical_notes:', refreshData.data.clinical_notes);
                  // Update PouchDB with latest order data
                  if (window.healthPWA?.storageManager) {
                    console.log('Updating PouchDB...');
                    await window.healthPWA.storageManager.updateFieldServiceOrder(props.orderId, refreshData.data);
                    console.log('PouchDB updated, calling loadOrder()...');
                    // Now reload to populate clinicalNotesData from refreshed cache
                    await loadOrder();
                    console.log('After loadOrder, clinicalNotesData.value:', clinicalNotesData.value);
                  }
                } else {
                  console.log('❌ Server refresh returned success=false');
                }
              } catch (refreshErr) {
                console.warn('Could not refresh order from server:', refreshErr);
                console.log('Trying to load from local cache anyway...');
                // Still try to load from local cache even if refresh fails
                await loadOrder();
              }
            } else {
              console.log('❌ Clinical notes API returned success=false, error:', data.error);
              window.healthPWA.showNotification('Failed to save clinical notes: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Save clinical notes error:', err);
            window.healthPWA.showNotification('Error saving clinical notes: ' + err.message, 'error');
          }
          console.log('=== saveClinicalNotes completed ===');
        };

        const completeServiceWithoutQuote = async () => {
          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot complete service while offline', 'error');
            return;
          }

          try {
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/complete_without_quote`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                service_notes: 'Service completed without invoice',
              })
            });

            const data = await response.json();
            console.log('Complete service without quote response:', data);

            if (data.success && data.data) {
              // Stop timer first
              stopTimer();

              // Show success notification
              window.healthPWA.showNotification(data.data.message || 'Service completed successfully!', 'success');

              // Update local order state immediately for UI responsiveness
              order.value.state = data.data.state;
              order.value.actual_end_datetime = data.data.actual_end_datetime;

              // Update PouchDB cache with new state
              if (window.healthPWA?.storageManager) {
                try {
                  await window.healthPWA.storageManager.updateFieldServiceOrder(props.orderId, {
                    state: data.data.state,
                    actual_end_datetime: data.data.actual_end_datetime
                  });
                } catch (dbErr) {
                  console.error('Failed to update PouchDB:', dbErr);
                }
              }

              // Reload full order data from server to get latest information
              await loadOrder();

              // Check next visit status and show appropriate modal
              setTimeout(() => {
                checkNextVisitAndShowModal();
              }, 500);
            } else {
              window.healthPWA.showNotification('Failed to complete service: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Complete service without quote error:', err);
            window.healthPWA.showNotification('Error completing service: ' + err.message, 'error');
          }
        };

        // API Functions for Next Visit Workflow
        const checkNextVisitAndShowModal = async () => {
          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot check next visit while offline', 'error');
            return;
          }

          try {
            console.log('Checking next visit status for orderId:', props.orderId);
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/next_visit_status`);
            const data = await response.json();
            console.log('Next visit status response:', data);

            if (data.success) {
              nextVisitData.value = data.data;

              if (data.data.has_next_visit) {
                // Scenario B: Next visit exists - populate form with existing data
                const nextDate = new Date(data.data.next_visit_date);
                // Use local date methods to get the correct local date
                const year = nextDate.getFullYear();
                const month = String(nextDate.getMonth() + 1).padStart(2, '0');
                const day = String(nextDate.getDate()).padStart(2, '0');
                nextVisitFormData.value.scheduled_date = `${year}-${month}-${day}`;
                nextVisitFormData.value.scheduled_time = `${String(nextDate.getHours()).padStart(2, '0')}:${String(nextDate.getMinutes()).padStart(2, '0')}`;
                nextVisitFormData.value.quote_items = data.data.quote_items || [];

                // Populate assigned nurse with both ID and name from API response
                if (data.data.assigned_nurse && data.data.assigned_nurse.id) {
                  nextVisitFormData.value.assigned_nurse_id = data.data.assigned_nurse.id;
                  nextVisitFormData.value.assigned_nurse_name = data.data.assigned_nurse.name || '';
                } else {
                  nextVisitFormData.value.assigned_nurse_id = null;
                  nextVisitFormData.value.assigned_nurse_name = '';
                }
                showNextVisitModalB.value = true;
              } else {
                // Scenario A: No next visit scheduled
                showNextVisitModalA.value = true;
              }
            } else {
              window.healthPWA.showNotification('Failed to check next visit status', 'error');
            }
          } catch (err) {
            console.error('Check next visit error:', err);
            window.healthPWA.showNotification('Error checking next visit: ' + err.message, 'error');
          }
        };

        const submitNoFutureVisit = async () => {
          if (!nextVisitFormData.value.no_future_visit_reason) {
            window.healthPWA.showNotification('Please select a reason', 'error');
            return;
          }

          if (nextVisitFormData.value.no_future_visit_reason === 'other' && !nextVisitFormData.value.other_reason_text) {
            window.healthPWA.showNotification('Please enter explanation for "Other" reason', 'error');
            return;
          }

          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot submit while offline', 'error');
            return;
          }

          try {
            const reasonLabel = noFutureVisitReasons.find(r => r.value === nextVisitFormData.value.no_future_visit_reason)?.label || nextVisitFormData.value.no_future_visit_reason;
            const finalReason = nextVisitFormData.value.no_future_visit_reason === 'other'
              ? `Other: ${nextVisitFormData.value.other_reason_text}`
              : reasonLabel;

            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/no_future_visit`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                reason: finalReason
              })
            });

            const data = await response.json();
            console.log('No future visit response:', data);

            if (data.success) {
              window.healthPWA.showNotification('Noted: Patient does not need future visits', 'success');
              showNextVisitModalA.value = false;
              // Reset form
              nextVisitFormData.value.no_future_visit_reason = '';
              nextVisitFormData.value.other_reason_text = '';
              // Close modal and navigate back to today's bookings
              emit('navigate', 'today');
            } else {
              window.healthPWA.showNotification('Failed to submit: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Submit no future visit error:', err);
            window.healthPWA.showNotification('Error submitting: ' + err.message, 'error');
          }
        };

        const scheduleNextVisit = async () => {
          // Validation
          if (!nextVisitFormData.value.scheduled_date) {
            window.healthPWA.showNotification('Please select a date', 'error');
            return;
          }

          if (!nextVisitFormData.value.scheduled_time) {
            window.healthPWA.showNotification('Please select a time', 'error');
            return;
          }

          if (!nextVisitFormData.value.quote_items || nextVisitFormData.value.quote_items.length === 0) {
            window.healthPWA.showNotification('Please add at least one service', 'error');
            return;
          }

          if (!nextVisitFormData.value.assigned_nurse_id) {
            window.healthPWA.showNotification('Please assign a nurse', 'error');
            return;
          }

          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot schedule while offline', 'error');
            return;
          }

          try {
            const dateTimeStr = `${nextVisitFormData.value.scheduled_date}T${nextVisitFormData.value.scheduled_time}:00`;

            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/schedule_next_visit`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                scheduled_datetime: dateTimeStr,
                quote_items: nextVisitFormData.value.quote_items,
                assigned_nurse_id: nextVisitFormData.value.assigned_nurse_id
              })
            });

            const data = await response.json();
            console.log('Schedule next visit response:', data);

            if (data.success) {
              window.healthPWA.showNotification('Next visit scheduled successfully!', 'success');
              showNextVisitModalB.value = false;
              // Reset form
              nextVisitFormData.value = {
                scheduled_date: null,
                scheduled_time: null,
                quote_items: [],
                assigned_nurse_id: null,
                no_future_visit_reason: '',
                other_reason_text: ''
              };
            } else {
              window.healthPWA.showNotification('Failed to schedule: ' + (data.error || 'Unknown error'), 'error');
            }
          } catch (err) {
            console.error('Schedule next visit error:', err);
            window.healthPWA.showNotification('Error scheduling: ' + err.message, 'error');
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
          console.log('=== loadQuote called with showModal:', showModal, '===');

          if (!props.isOnline) {
            console.log('❌ loadQuote: Not online');
            window.healthPWA.showNotification('Cannot load invoice while offline', 'error');
            return;
          }

          try {
            console.log('Fetching quote from API for orderId:', props.orderId);
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/quote`);
            const data = await response.json();

            console.log('Quote API response:', data);

            if (data.success) {
              console.log('✅ Quote loaded successfully');
              quoteData.value = data.data;
              console.log('quoteData.value set to:', quoteData.value);
              if (showModal) {
                console.log('showModal is true, setting showInvoice.value = true');
                showInvoice.value = true;
              } else {
                console.log('showModal is false, NOT showing invoice modal');
              }
            } else {
              console.log('❌ Quote API returned success=false, error:', data.error);
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
          console.log('=== loadQuote completed ===');
        };

        const saveQuoteWithComments = async () => {
          console.log('=== saveQuoteWithComments called ===');

          if (!props.isOnline) {
            window.healthPWA.showNotification('Cannot save quote while offline', 'error');
            return;
          }

          try {
            console.log('Sending quote save request with comments:', quoteComments.value);
            const response = await fetch(`/health_pwa/api/fso/${props.orderId}/quote/save`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                quote_id: quoteData.value.id,
                comments: quoteComments.value
              })
            });

            const data = await response.json();
            console.log('Quote save response:', data);

            if (data.success) {
              console.log('✅ Quote saved successfully with comments');
              quoteVerified.value = true;
              showInvoice.value = false;
              window.healthPWA.showNotification(
                'Invoice verified and saved successfully!',
                'success',
                3000
              );
            } else {
              console.log('❌ Quote save failed:', data.error);
              window.healthPWA.showNotification(
                'Failed to save quote: ' + (data.error || 'Unknown error'),
                'error'
              );
            }
          } catch (err) {
            console.error('Save quote error:', err);
            window.healthPWA.showNotification(
              'Error saving quote: ' + err.message,
              'error'
            );
          }
          console.log('=== saveQuoteWithComments completed ===');
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
          console.log('=== order-detail-view MOUNTED ===');
          console.log('orderId:', props.orderId);
          console.log('showPaymentWizard ref:', showPaymentWizard);
          console.log('openPaymentWizard function:', typeof openPaymentWizard);
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
          completeServiceWithoutQuote,
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
          getStatusBadgeClass,
          quoteVerified,
          quoteComments,
          saveQuoteWithComments,
          // Next Visit Modal
          showNextVisitModalA,
          showNextVisitModalB,
          nextVisitData,
          nextVisitFormData,
          showNoFutureVisitDropdown,
          noFutureVisitReasons,
          checkNextVisitAndShowModal,
          submitNoFutureVisit,
          scheduleNextVisit
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

              <!-- Verify Invoice Button (renamed from Invoice) -->
              <button @click="loadQuote(true)"
                      class="btn btn-action btn-invoice"
                      :disabled="!isOnline || !order.confirmation_requirements?.has_quote_with_items"
                      :title="!order.confirmation_requirements?.has_quote_with_items ? 'No quote associated with this booking' : 'Verify and review invoice'">
                <i class="material-icons">receipt</i>
                <span>Verify Invoice</span>
              </button>

              <!-- Payment Button (appears only after quote is verified) -->
              <button v-if="quoteVerified && order.state === 'in_progress'"
                      @click="openPaymentWizard"
                      class="btn btn-action btn-payment"
                      :disabled="!isOnline"
                      title="Proceed to payment collection">
                <i class="material-icons">payment</i>
                <span>Payment</span>
              </button>

              <!-- Complete Service Button - No Quote (when no quote exists) -->
              <button v-if="order.state === 'in_progress' && !order.confirmation_requirements?.has_quote_with_items"
                      @click="completeServiceWithoutQuote"
                      class="btn btn-action btn-complete-no-quote"
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

                  <!-- Invoice Comments Section -->
                  <div class="form-section" style="margin-top: 20px; border-top: 1px solid var(--border-color); padding-top: 20px;">
                    <h4 style="font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; margin-bottom: 12px;">📝 Invoice Comments</h4>
                    <div class="form-group">
                      <textarea v-model="quoteComments"
                                rows="3"
                                placeholder="Add any comments or notes about this invoice (optional)..."
                                style="width: 100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; font-size: 14%;"></textarea>
                    </div>
                  </div>
                </div>

                <div class="modal-footer">
                  <button @click="showInvoice = false" class="btn btn-secondary">Cancel</button>
                  <button @click="saveQuoteWithComments" class="btn btn-primary" title="Save invoice with comments">
                    <i class="material-icons">save</i>
                    Save Quote
                  </button>
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
    */
    /* END OF LEGACY ORDER-DETAIL-VIEW COMPONENT */

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

    // Call view - displays clinic phone and initiates calls
    app.component('call-view', {
      props: ['isOnline'],
      emits: ['navigate'],
      setup(props, { emit }) {
        const { ref, onMounted } = Vue;

        const clinicPhone = ref('');
        const clinicName = ref('');
        const isLoading = ref(true);
        const error = ref(null);

        const loadClinicConfig = async () => {
          try {
            isLoading.value = true;
            error.value = null;

            const response = await fetch('/health_pwa/api/config/clinic-phone');
            const result = await response.json();

            if (result.success && result.data) {
              clinicPhone.value = result.data.clinic_phone_number || 'N/A';
              clinicName.value = result.data.clinic_name || 'VAFHS Clinic';
              console.log('Loaded clinic config:', clinicName.value, clinicPhone.value);
            } else {
              error.value = result.error || 'Failed to load clinic information';
              console.error('Error:', error.value);
            }
          } catch (err) {
            console.error('Failed to load clinic config:', err);
            error.value = err.message;
          } finally {
            isLoading.value = false;
          }
        };

        const initiateCall = () => {
          if (clinicPhone.value && clinicPhone.value !== 'N/A') {
            // Remove spaces and special characters for tel link
            const phoneDigits = clinicPhone.value.replace(/[^\d+]/g, '');
            window.location.href = `tel:${phoneDigits}`;
          } else {
            alert('Clinic phone number not available');
          }
        };

        const copyPhone = () => {
          if (clinicPhone.value && clinicPhone.value !== 'N/A') {
            navigator.clipboard.writeText(clinicPhone.value);
            alert('Phone number copied to clipboard!');
          }
        };

        onMounted(() => {
          loadClinicConfig();
        });

        return {
          clinicPhone,
          clinicName,
          isLoading,
          error,
          initiateCall,
          copyPhone,
          loadClinicConfig
        };
      },
      template: `
        <div class="call-view">
          <div class="call-header">
            <h2>
              <i class="material-icons">call</i>
              Contact Clinic
            </h2>
          </div>

          <div v-if="isLoading" class="loading-spinner">
            <div class="spinner"></div>
            <p>Loading clinic information...</p>
          </div>

          <div v-else-if="error" class="error-message">
            <i class="material-icons">error</i>
            <p>{{ error }}</p>
            <button @click="loadClinicConfig" class="btn btn-secondary">Retry</button>
          </div>

          <div v-else class="call-container">
            <div class="clinic-card">
              <div class="clinic-info">
                <h3 class="clinic-name">{{ clinicName }}</h3>
                <p class="clinic-phone-label">Phone Number</p>
                <p class="clinic-phone">{{ clinicPhone }}</p>
              </div>

              <div class="call-actions">
                <button @click="initiateCall" class="btn btn-call-primary">
                  <i class="material-icons">call</i>
                  <span>Call Now</span>
                </button>
                <button @click="copyPhone" class="btn btn-copy">
                  <i class="material-icons">content_copy</i>
                  <span>Copy Number</span>
                </button>
              </div>

              <div class="call-info-box">
                <i class="material-icons">info</i>
                <p>Tap "Call Now" to initiate a call to the clinic directly from your phone.</p>
              </div>
            </div>
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
