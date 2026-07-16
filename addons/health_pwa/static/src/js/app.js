// Health PWA - Vue.js 3 Main Application

const APP_VI_FALLBACK_TRANSLATIONS = {
  'Close': 'Đóng',
  'Upcoming Bookings': 'Lịch hẹn sắp tới',
  'No upcoming bookings scheduled': 'Chưa có lịch hẹn sắp tới',
  'Quick Complete': 'Hoàn tất nhanh',
  'Completing...': 'Đang hoàn tất...',
  'Complete this visit in one tap': 'Hoàn tất lượt thăm khám này trong một chạm',
  'One-tap completion failed': 'Hoàn tất nhanh không thành công',
  'Service completed': 'Đã hoàn tất dịch vụ',
  // Offline visit actions (pwa-offline-actions §2.5) — VN-first fallback.
  'Saved offline — will sync when online': 'Đã lưu ngoại tuyến — sẽ đồng bộ khi có mạng',
  'Could not sync offline action — refreshed': 'Không thể đồng bộ thao tác ngoại tuyến — đã làm mới',
  'Pending sync': 'Chờ đồng bộ',
  // EMR point-of-care finalize (emr-record-spine phase 1.5) — VN-first fallback.
  'Signed': 'Đã ký',
  'Draft': 'Nháp',
  'Finalize & Sign': 'Hoàn tất & Ký',
  'Signing…': 'Đang ký…',
  'Signed medical record — locked': 'Hồ sơ bệnh án đã ký — đã khóa',
  'Signed by': 'Ký bởi',
  'Clinical note finalized and signed': 'Ghi chú lâm sàng đã hoàn tất và ký',
  'Finalization failed': 'Hoàn tất không thành công',
  'Requires an internet connection.': 'Cần kết nối internet.',
  'Connect to the internet to finalize & sign this note.': 'Kết nối internet để hoàn tất & ký ghi chú này.',
  'Finalize and sign this clinical note? Once signed it becomes a permanent, locked medical record and cannot be edited.': 'Hoàn tất và ký ghi chú lâm sàng này? Sau khi ký, ghi chú trở thành hồ sơ bệnh án cố định, bị khóa và không thể chỉnh sửa.',
  // EMR "Notes to sign" home card (emr-record-spine phase 1.7) — VN-first fallback.
  'Notes to sign': 'Ghi chú cần ký',
  'overdue': 'quá hạn',
  'Patient': 'Bệnh nhân',
};

// Lightweight translation helper: use PWAUtils.i18n for reactive language switching
// This allows translations to update when user changes language preference
const _t = (s) => {
  const isVietnamese = window.healthPWAConfig?.user_lang?.startsWith('vi');

  // Use PWAUtils.i18n for reactive translations based on window.healthPWAConfig.user_lang
  if (window.PWAUtils && window.PWAUtils.i18n && typeof window.PWAUtils.i18n.t === 'function') {
    const translated = window.PWAUtils.i18n.t(s);
    if (translated !== s) {
      return translated;
    }
    if (isVietnamese && APP_VI_FALLBACK_TRANSLATIONS[s]) {
      return APP_VI_FALLBACK_TRANSLATIONS[s];
    }
  }

  // Fallback to Odoo translations if available
  if (window.odoo && typeof window.odoo._t === 'function') {
    const translated = window.odoo._t(s);
    if (translated !== s) {
      return translated;
    }
  }

  if (isVietnamese && APP_VI_FALLBACK_TRANSLATIONS[s]) {
    return APP_VI_FALLBACK_TRANSLATIONS[s];
  }

  // Final fallback: return the key as-is
  return s;
};

const getPWALocale = () => (
  window.healthPWAConfig?.user_lang?.startsWith('vi') ? 'vi-VN' : 'en-US'
);

// Parse an Odoo datetime ("YYYY-MM-DD HH:MM:SS" assumed UTC, or ISO) into a
// local-timezone Date. Top-level on purpose: orders-view and
// past-bookings-view call this too — it used to live inside today-view's
// setup() closure, which made every other caller throw ReferenceError and
// broke those screens outright ("Failed to load orders").
const parseOdooDateTime = (dateTimeStr) => {
  if (!dateTimeStr) return new Date();
  if (dateTimeStr.includes('T')) {
    let isoString = dateTimeStr;
    if (!isoString.endsWith('Z') && !isoString.includes('+') && !isoString.includes('-', isoString.indexOf('T'))) {
      isoString += 'Z';
    }
    return new Date(isoString);
  }
  const parts = dateTimeStr.split(' ');
  if (parts.length >= 2) {
    const dateParts = parts[0].split('-');
    const timeParts = parts[1].split(':');
    if (dateParts.length === 3 && timeParts.length >= 2) {
      return new Date(Date.UTC(
        parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]),
        parseInt(timeParts[0]), parseInt(timeParts[1]), parseInt(timeParts[2]) || 0));
    }
  }
  if (!dateTimeStr.includes('Z') && !dateTimeStr.includes('+') && !dateTimeStr.includes('GMT')) {
    return new Date(dateTimeStr + 'Z');
  }
  return new Date(dateTimeStr);
};

// Shared booking status → label map. Top-level (parseOdooDateTime precedent,
// ledger §31 tail) so today-view, orders-view and past-bookings-view all use
// ONE superset map — the orders lists' local map missed 'confirmed',
// 'completed_pending_invoice' and 'closed' and rendered "UNKNOWN" chips for
// real states. VN-first labels resolve via _t. Falls back to the raw state
// (never the misleading "Unknown") for anything genuinely unmapped.
const getBookingStatusLabel = (state) => {
  const s = String(state || '');
  const labels = {
    'draft': _t('Booked'),
    'confirmed': _t('Confirmed'),
    'assigned': _t('Assigned'),
    'in_progress': _t('In Progress'),
    'completed': _t('Completed'),
    'completed_pending_invoice': _t('Pending Invoice'),
    'closed': _t('Closed'),
    'cancelled': _t('Cancelled'),
  };
  return labels[s] || s || _t('Unknown');
};

const cleanDisplayValue = (value, fallback = '') => {
  if (window.PWAUtils?.i18n?.clean) {
    return window.PWAUtils.i18n.clean(value, { fallback });
  }
  if (value === false || value === null || value === undefined) return fallback;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed || ['false', 'null', 'undefined'].includes(trimmed.toLowerCase())) {
      return fallback;
    }
    return trimmed;
  }
  return value;
};

const displayDbValue = (value, fallback = '') => {
  if (window.PWAUtils?.i18n?.display) {
    return window.PWAUtils.i18n.display(value, { fallback });
  }
  const cleaned = cleanDisplayValue(value, fallback);
  return cleaned ? _t(String(cleaned)) : fallback;
};

const displayError = (value) => {
  if (window.PWAUtils?.i18n?.error) {
    return window.PWAUtils.i18n.error(value);
  }
  return displayDbValue(value);
};

// Utility function to strip HTML tags from text
const stripHtmlTags = (html) => {
  if (!html) return '';
  // Create a temporary div element to parse HTML
  const temp = document.createElement('div');
  temp.innerHTML = html;
  // Return text content without HTML tags
  return temp.textContent || temp.innerText || '';
};

// Global app state and utilities
const __existingHealthPWA = window.healthPWA || {};
window.healthPWA = {
  // preserve any preloaded l10n or other props set before this script
  ...__existingHealthPWA,
  config: window.healthPWAConfig || __existingHealthPWA.config || {},
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
    console.log('[health_pwa] translation debug', {
      hasOdoo: !!window.odoo,
      has_t: !!(window.odoo && window.odoo._t),
      lang: window.odoo?.session_info?.user_context?.lang || window.healthPWAConfig?.user_lang,
      sampleDay: _t('Day'),
      preloadEntries: window.healthPWA?.l10n ? Object.keys(window.healthPWA.l10n).length : 0,
      preloadHasDay: !!(window.healthPWA?.l10n && window.healthPWA.l10n['Day']),
    });
    
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
          bottomNavVisible: true,
          viewKey: 0, // Key to force component refresh when navigating to same route
          pendingAssignments: [],
          notifPanelOpen: false,
          notifRespondingId: null, // ID of assignment being responded to
          // Shared booking modal: set by openBooking() to hand a fso id (and
          // the route to return to on close) down to today-view, which owns
          // the modal. This is how orders/past-bookings/the bell/deep links
          // all reach the ONE modal (see openBooking below).
          pendingBooking: null,
        });
        
        // Computed properties
        const isAuthenticated = computed(() => state.user !== null);
        const hasNotifications = computed(() => state.notifications.length > 0);

        // Language helper — reads from same localStorage key as the VI/EN toggle
        const getLang = () => localStorage.getItem('pwa_preferred_language') || 'vi';
        const t = (vi, en) => getLang() === 'en' ? en : vi;
        
        // Open the shared booking-detail modal for a given FSO id, from ANY
        // route. The modal lives inside today-view (it drags along the
        // Start/EVV/clinical-notes/invoice/next-visit flows and the family
        // panel's DOM seam), so we land on today-view and hand it the id via
        // state.pendingBooking; today-view opens the modal and returns to the
        // origin route when it is closed. All the old dead ends
        // (orders/past-bookings rows, the bell card, #/order/<id> deep links,
        // push taps) funnel through here instead of the deleted order screen.
        const openBooking = (fsoId) => {
          const id = parseInt(fsoId);
          if (!id) return;
          const origin = state.currentRoute;
          const returnRoute = (origin && origin !== 'order' && origin !== 'today') ? origin : null;
          state.pendingBooking = { id, returnRoute };
          // Route to today-view (force a remount if already there so the
          // freshly-mounted view consumes pendingBooking on mount).
          navigate('today');
        };

        // Navigation methods
        const navigate = (route, params = {}) => {
          // The order-detail SCREEN is dead code (ledger §31): every request to
          // view an order becomes an open of the shared modal on today-view.
          if (route === 'order') {
            openBooking(params.id);
            return;
          }

          // If navigating to the same route, increment viewKey to force component refresh
          // This clears any open modals or pending states
          if (state.currentRoute === route) {
            state.viewKey++;
          }

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

        // Pending assignment notifications
        const fetchPendingNotifications = async () => {
          if (!state.isOnline) return;
          try {
            const resp = await fetch('/health_pwa/api/notifications/pending');
            const data = await resp.json();
            if (data.success && data.data) {
              state.pendingAssignments = data.data.notifications || [];
            }
          } catch (err) {
            console.warn('[Notifications] Failed to fetch:', err);
          }
        };

        const toggleNotifPanel = () => {
          state.notifPanelOpen = !state.notifPanelOpen;
          if (state.notifPanelOpen) {
            fetchPendingNotifications();
          }
        };

        const respondToAssignment = async (assignmentId, action) => {
          state.notifRespondingId = assignmentId;
          try {
            const resp = await fetch(`/health_pwa/api/assignments/${assignmentId}/respond`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ action }),
            });
            const data = await resp.json();
            if (data.success) {
              showNotification(
                action === 'accept' ? 'Assignment confirmed!' : 'Assignment declined.',
                action === 'accept' ? 'success' : 'warning'
              );
              // Refresh the list
              await fetchPendingNotifications();
              // Refresh today view if we're on it
              if (state.currentRoute === 'today') {
                state.viewKey++;
              }
            } else {
              showNotification(data.error || 'Failed to respond', 'error');
            }
          } catch (err) {
            showNotification('Network error', 'error');
          } finally {
            state.notifRespondingId = null;
          }
        };

        const dismissNotification = async (notifId) => {
          state.notifRespondingId = notifId;
          try {
            const resp = await fetch(`/health_pwa/api/notifications/${notifId}/dismiss`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
            });
            const data = await resp.json();
            if (data.success) {
              await fetchPendingNotifications();
            }
          } catch (err) {
            console.warn('Failed to dismiss notification:', err);
          } finally {
            state.notifRespondingId = null;
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

          // Fetch pending notifications
          await fetchPendingNotifications();
          // Poll every 30 seconds for new notifications
          setInterval(fetchPendingNotifications, 30000);

          // Auto-open notification panel if URL has showNotifications param
          if (window.location.hash.includes('showNotifications=1')) {
            state.notifPanelOpen = true;
            // Clean up the URL
            window.history.replaceState({}, '', '/health_pwa#/today');
          }

          // Listen for push notification events to refresh and auto-open panel
          if ('serviceWorker' in navigator) {
            navigator.serviceWorker.addEventListener('message', (event) => {
              if (event.data && event.data.type === 'PUSH_RECEIVED') {
                fetchPendingNotifications();
                // Auto-open the notification panel
                state.notifPanelOpen = true;
              }
            });
          }
        });
        
        // Handle browser back/forward
        window.addEventListener('popstate', (event) => {
          const hash = window.location.hash.slice(1);
          if (hash) {
            const parts = hash.split('/');
            const route = parts[1] || 'today';
            // #/order/<id> is the dead screen — resolve it to the shared modal.
            if (route === 'order') {
              openBooking(parts[2]);
              return;
            }
            state.currentRoute = route;
          }
        });
        
        // Update online status from global state
        window.healthPWA.updateAppOnlineStatus = (isOnline) => {
          state.isOnline = isOnline;
        };
        
        // Global notification method
        window.healthPWA.showNotification = showNotification;

        // Handle call button click
        const handleCallClick = () => {
          const companyPhone = window.healthPWAConfig?.companyPhone;

          if (!companyPhone || companyPhone.trim() === '') {
            // No phone number configured - show error dialog
            const lang = window.healthPWAConfig?.user_lang || 'vi_VN';
            const isVietnamese = lang.startsWith('vi');

            const message = isVietnamese
              ? 'Số điện thoại công ty chưa được cấu hình. Vui lòng liên hệ quản trị viên để thiết lập số điện thoại.'
              : 'Company phone number is not configured. Please contact your administrator to set up the phone number.';

            alert(message);
            return;
          }

          // Open phone dialer with company phone number
          window.location.href = `tel:${companyPhone}`;
        };

        return {
          state,
          isAuthenticated,
          hasNotifications,
          navigate,
          openBooking,
          goBack,
          showNotification,
          removeNotification,
          syncData,
          loadUserData,
          handleCallClick,
          toggleNotifPanel,
          respondToAssignment,
          dismissNotification,
          fetchPendingNotifications,
          getLang,
          t,
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
                <h3>{{ _t('Health Mobile') }}</h3>
                <p>{{ _t('Loading healthcare data...') }}</p>
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
              <h1 class="mobile-header-title">
                <img v-if="state.currentRoute === 'today'" class="header-logo" src="/health_pwa/static/img/VietLogo.png" alt="Việt Úc"/>
                <span v-else>{{ getRouteTitle() }}</span>
              </h1>
              <div class="mobile-header-right">
                <button class="notif-bell-btn" @click="toggleNotifPanel" :class="{ active: state.notifPanelOpen }">
                  <i class="material-icons">notifications</i>
                  <span v-if="state.pendingAssignments.length > 0" class="notif-badge">{{ state.pendingAssignments.length }}</span>
                </button>
                <div v-if="!state.isOnline" class="status-dot status-offline" :title="_t('Offline')"></div>
                <div v-else-if="state.syncStatus === 'syncing'" class="status-dot status-sync" :title="_t('Syncing')"></div>
                <div v-else class="status-dot status-online" :title="_t('Online')"></div>
              </div>
            </header>

            <!-- Notification Panel -->
            <div v-if="state.notifPanelOpen" class="notif-panel-overlay" @click="toggleNotifPanel"></div>
            <transition name="slide-down">
              <div v-if="state.notifPanelOpen" class="notif-panel">
                <div class="notif-panel-header">
                  <h3>📋 {{ t('Thông báo', 'Notifications') }}</h3>
                  <button @click="toggleNotifPanel" class="notif-panel-close"><i class="material-icons">close</i></button>
                </div>
                <div v-if="state.pendingAssignments.length === 0" class="notif-panel-empty">
                  <i class="material-icons" style="font-size:48px;opacity:0.3">notifications_none</i>
                  <p>{{ t('Không có thông báo mới', 'No pending notifications') }}</p>
                </div>
                <div v-else class="notif-panel-list">
                  <div v-for="notif in state.pendingAssignments" :key="notif.type + '-' + notif.id" class="notif-card" :class="'notif-card--' + notif.type">

                    <!-- ASSIGNMENT notification -->
                    <template v-if="notif.type === 'assignment'">
                      <div class="notif-card-header">
                        <span class="notif-type-badge notif-badge-assignment">{{ t('Xác nhận', 'Confirm') }}</span>
                        <span class="notif-time">{{ notif.scheduled_datetime }}</span>
                        <button class="notif-dismiss-x" @click.stop="dismissNotification(notif.id)" :title="_t('Dismiss')">&times;</button>
                      </div>
                      <div class="notif-card-body">
                        <div class="notif-detail"><i class="material-icons">person</i> {{ notif.patient_name }}</div>
                        <div class="notif-detail"><i class="material-icons">event</i> {{ notif.fso_name }}</div>
                        <div v-if="notif.service_type" class="notif-detail"><i class="material-icons">medical_services</i> {{ notif.service_type }}</div>
                      </div>
                      <div class="notif-card-actions">
                        <button class="notif-btn notif-btn-accept" @click="respondToAssignment(notif.id, 'accept')" :disabled="state.notifRespondingId === notif.id">
                          <i class="material-icons">check_circle</i> {{ t('Chấp nhận', 'Accept') }}
                        </button>
                        <button class="notif-btn notif-btn-decline" @click="respondToAssignment(notif.id, 'decline')" :disabled="state.notifRespondingId === notif.id">
                          <i class="material-icons">cancel</i> {{ t('Từ chối', 'Decline') }}
                        </button>
                      </div>
                    </template>

                    <!-- CANCELLED notification -->
                    <template v-else-if="notif.type === 'cancelled'">
                      <div class="notif-card-header">
                        <span class="notif-type-badge notif-badge-cancelled">{{ t('Đã hủy', 'Cancelled') }}</span>
                        <button class="notif-dismiss-x" @click.stop="dismissNotification(notif.id)" :title="_t('Dismiss')">&times;</button>
                      </div>
                      <div class="notif-card-body">
                        <div class="notif-detail"><i class="material-icons">person</i> {{ notif.patient_name }}</div>
                        <div class="notif-detail"><i class="material-icons">event</i> {{ notif.fso_name }}</div>
                        <div v-if="notif.message" class="notif-detail notif-message">{{ notif.message }}</div>
                      </div>
                      <div class="notif-card-actions">
                        <button class="notif-btn notif-btn-ok" @click="dismissNotification(notif.id)" :disabled="state.notifRespondingId === notif.id">
                          <i class="material-icons">done</i> OK
                        </button>
                      </div>
                    </template>

                    <!-- RESCHEDULED notification -->
                    <template v-else-if="notif.type === 'rescheduled'">
                      <div class="notif-card-header">
                        <span class="notif-type-badge notif-badge-rescheduled">{{ t('Đã đổi lịch', 'Rescheduled') }}</span>
                        <button class="notif-dismiss-x" @click.stop="dismissNotification(notif.id)" :title="_t('Dismiss')">&times;</button>
                      </div>
                      <div class="notif-card-body">
                        <div class="notif-detail"><i class="material-icons">person</i> {{ notif.patient_name }}</div>
                        <div class="notif-detail"><i class="material-icons">event</i> {{ notif.fso_name }}</div>
                        <div v-if="notif.old_datetime" class="notif-detail notif-old-date">
                          <i class="material-icons">event_busy</i>
                          <span style="text-decoration:line-through;opacity:0.6">{{ notif.old_datetime }}</span>
                        </div>
                        <div v-if="notif.new_datetime" class="notif-detail notif-new-date">
                          <i class="material-icons">event_available</i>
                          <strong>{{ notif.new_datetime }}</strong>
                        </div>
                      </div>
                      <div class="notif-card-actions">
                        <button class="notif-btn notif-btn-ok" @click="dismissNotification(notif.id)" :disabled="state.notifRespondingId === notif.id">
                          <i class="material-icons">done</i> OK
                        </button>
                      </div>
                    </template>

                    <!-- FAMILY MESSAGE notification (health_pwa_family) -->
                    <template v-else-if="notif.type === 'family_message'">
                      <div class="notif-card-header">
                        <span class="notif-type-badge notif-badge-family">{{ t('Tin nhắn gia đình', 'Family message') }}</span>
                        <button class="notif-dismiss-x" @click.stop="dismissNotification(notif.id)" :title="_t('Dismiss')">&times;</button>
                      </div>
                      <div class="notif-card-body">
                        <div class="notif-detail"><i class="material-icons">person</i> {{ notif.patient_name }}</div>
                        <div v-if="notif.message" class="notif-detail notif-message">{{ notif.message }}</div>
                      </div>
                      <div class="notif-card-actions">
                        <button v-if="notif.fso_id" class="notif-btn notif-btn-view" @click="state.notifPanelOpen = false; openBooking(notif.fso_id)">
                          <i class="material-icons">visibility</i> {{ t('Xem', 'View') }}
                        </button>
                        <button class="notif-btn notif-btn-ok" @click="dismissNotification(notif.id)" :disabled="state.notifRespondingId === notif.id">
                          <i class="material-icons">done</i> OK
                        </button>
                      </div>
                    </template>

                  </div>
                </div>
              </div>
            </transition>
            
            <!-- Main Content -->
            <main class="mobile-content">
              <!-- Today -->
              <today-view v-if="state.currentRoute === 'today'"
                :key="state.viewKey"
                :user="state.user"
                :is-online="state.isOnline"
                :pending-booking="state.pendingBooking"
                @consume-booking="state.pendingBooking = null"
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

              <!-- Order Detail screen removed (ledger §31): the booking-detail
                   modal on today-view is the visit surface. Reaching an order
                   opens that modal via openBooking()/navigate('order'). -->

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
                <h2>{{ _t('Page Not Found') }}</h2>
                <p>{{ _t('The requested page could not be found.') }}</p>
                <button @click="navigate('today')" class="btn btn-primary">{{ _t('Go to Today') }}</button>
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
                <span class="mobile-nav-label">{{ _t('Booking') }}</span>
              </a>

              <a @click.prevent="navigate('patients')"
                class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'patients' || state.currentRoute === 'patient' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">people</i>
                </div>
                <span class="mobile-nav-label">{{ _t('Patients') }}</span>
              </a>

              <a @click.prevent="handleCallClick()"
                 class="mobile-nav-item">
                <div class="mobile-nav-icon">
                  <i class="material-icons">call</i>
                </div>
                <span class="mobile-nav-label">{{ _t('Call') }}</span>
              </a>

              <a @click.prevent="navigate('profile')"
                 class="mobile-nav-item"
                 :class="{ active: state.currentRoute === 'profile' }">
                <div class="mobile-nav-icon">
                  <i class="material-icons">account_circle</i>
                </div>
                <span class="mobile-nav-label">{{ _t('Profile') }}</span>
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
            today: 'Việt Úc',
            patients: _t('Patients'),
            patient: _t('Patient Details'),
            profile: _t('Profile')
          };
          return titles[this.state.currentRoute] || _t('Health Mobile');
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
    app.config.globalProperties._t = _t;
    // Global initials helper (avatar text) available to every component template
    app.config.globalProperties.initials = (name) => {
      if (!name) return '?';
      const parts = String(name).trim().split(/\s+/).filter(Boolean);
      if (!parts.length) return '?';
      const first = parts[0][0] || '';
      const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
      return (first + last).toUpperCase() || '?';
    };
    // App version (shown on the Profile screen)
    app.config.globalProperties.pwaVersion = (window.healthPWAConfig && window.healthPWAConfig.version) || '';
    app.provide('_t', _t);
    
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
            <h2>{{ _t('Welcome back') }}, {{ user?.name || _t('User') }}</h2>
            <p v-if="!isOnline" class="offline-notice">
              <i class="material-icons">wifi_off</i>
              {{ _t('Working offline') }}
            </p>
          </div>
          
          <div class="dashboard-stats">
            <div class="stat-card patients-card" @click="$emit('navigate', 'patients')">
              <div class="stat-icon">
                <i class="material-icons">people</i>
              </div>
              <div class="stat-content">
                <h3>{{ _t('Patients') }}</h3>
                <p>{{ _t('Manage patient records') }}</p>
              </div>
            </div>

            <div class="stat-card orders-card" @click="$emit('navigate', 'orders')">
              <div class="stat-icon">
                <i class="material-icons">assignment</i>
              </div>
              <div class="stat-content">
                <h3>{{ _t('Field Orders') }}</h3>
                <p>{{ _t('View service orders') }}</p>
              </div>
            </div>

            <div class="stat-card teams-card" @click="$emit('navigate', 'teams')">
              <div class="stat-icon">
                <i class="material-icons">group</i>
              </div>
              <div class="stat-content">
                <h3>{{ _t('Teams') }}</h3>
                <p>{{ _t('Team management') }}</p>
              </div>
            </div>
          </div>
          
          <div class="dashboard-actions">
            <button @click="$emit('sync')" class="btn btn-primary" :disabled="!isOnline">
              <i class="material-icons">sync</i>
              {{ _t('Sync Data') }}
            </button>
            <button @click="$emit('sync', true)" class="btn btn-secondary" :disabled="!isOnline" :title="_t('Force full sync of all data')">
              <i class="material-icons">refresh</i>
              {{ _t('Force Full Sync') }}
            </button>
            <button @click="checkDebugInfo" class="btn btn-outline" :disabled="!isOnline" :title="_t('Check server data availability')">
              <i class="material-icons">bug_report</i>
              {{ _t('Debug Info') }}
            </button>
          </div>
        </div>
      `
    });

    // Booking view - shows field service order bookings with date navigation and calendar picker
    app.component('today-view', {
      props: ['user', 'isOnline', 'pendingBooking'],
      emits: ['navigate', 'sync', 'consume-booking'],
      setup(props, { emit }) {
        const { ref, onMounted, onUnmounted, computed } = Vue;

        const bookings = ref([]);
        const isLoading = ref(true);
        const error = ref(null);
        const staffName = ref('');
        const displayDate = ref(new Date().toLocaleDateString(getPWALocale()));
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
              staffName.value = result.data.staff_name || _t('Staff');
              displayDate.value = dateObj.toLocaleDateString(getPWALocale(), {
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
          console.log('goToNext called - viewMode:', viewMode.value, 'currentDate:', currentDate.value);
          if (isTransitioning.value) {
            console.log('Blocked by transition');
            return;
          }
          isTransitioning.value = true;

          if (viewMode.value === 'day') {
            const nextDate = new Date(currentDate.value);
            nextDate.setDate(nextDate.getDate() + 1);
            currentDate.value = nextDate;
            console.log('Day view - moving to:', nextDate);
            loadBookingsForDate(nextDate);
          } else if (viewMode.value === 'week') {
            const nextDate = new Date(currentDate.value);
            nextDate.setDate(nextDate.getDate() + 7);
            currentDate.value = nextDate;
            console.log('Week view - moving to:', nextDate);
            loadBookingsForWeek(nextDate);
          } else if (viewMode.value === 'month') {
            const nextDate = new Date(currentDate.value);
            nextDate.setMonth(nextDate.getMonth() + 1);
            currentDate.value = nextDate;
            console.log('Month view - moving to:', nextDate);
            loadBookingsForMonth(nextDate);
          }

          setTimeout(() => { isTransitioning.value = false; }, 300);
        };

        // Navigate backward (previous day/week/month based on view mode)
        const goToPrevious = () => {
          console.log('goToPrevious called - viewMode:', viewMode.value, 'currentDate:', currentDate.value);
          if (isTransitioning.value) {
            console.log('Blocked by transition');
            return;
          }
          isTransitioning.value = true;

          if (viewMode.value === 'day') {
            const prevDate = new Date(currentDate.value);
            prevDate.setDate(prevDate.getDate() - 1);
            currentDate.value = prevDate;
            console.log('Day view - moving to:', prevDate);
            loadBookingsForDate(prevDate);
          } else if (viewMode.value === 'week') {
            const prevDate = new Date(currentDate.value);
            prevDate.setDate(prevDate.getDate() - 7);
            currentDate.value = prevDate;
            console.log('Week view - moving to:', prevDate);
            loadBookingsForWeek(prevDate);
          } else if (viewMode.value === 'month') {
            const prevDate = new Date(currentDate.value);
            prevDate.setMonth(prevDate.getMonth() - 1);
            currentDate.value = prevDate;
            console.log('Month view - moving to:', prevDate);
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
              staffName.value = result.data.staff_name || _t('Staff');

              // Group bookings by date
              const grouped = {};
              (result.data.orders || []).forEach(order => {
                const bookingDate = parseOdooDateTime(order.scheduled_datetime).toLocaleDateString(getPWALocale(), {
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
                  patient_code: order.patient_code || order.patient_ref || '',
                  patient_id: order.patient_id,
                  patient_phone: order.phone,
                  patient_zalo: order.patient_zalo || null,
                  service_type: order.service_type,
                  appointment_type: order.appointment_type || '',
                  scheduled_datetime: order.scheduled_datetime,
                  scheduled_time: parseOdooDateTime(order.scheduled_datetime).toLocaleTimeString(getPWALocale(), { hour: '2-digit', minute: '2-digit' }),
                  scheduled_duration: order.scheduled_duration || 60,
                  status: order.status,
                  status_display: order.status_display,
                  location: order.address,
                  priority: order.priority,
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
              displayDate.value = `${_t('Week of')} ${weekStart.toLocaleDateString(getPWALocale(), { month: 'short', day: 'numeric' })}`;
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
              staffName.value = result.data.staff_name || _t('Staff');

              // Group bookings by date
              const grouped = {};
              (result.data.orders || []).forEach(order => {
                const bookingDate = parseOdooDateTime(order.scheduled_datetime).toLocaleDateString(getPWALocale(), {
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
                  patient_code: order.patient_code || order.patient_ref || '',
                  patient_id: order.patient_id,
                  patient_phone: order.phone,
                  patient_zalo: order.patient_zalo || null,
                  service_type: order.service_type,
                  appointment_type: order.appointment_type || '',
                  scheduled_datetime: order.scheduled_datetime,
                  scheduled_time: parseOdooDateTime(order.scheduled_datetime).toLocaleTimeString(getPWALocale(), { hour: '2-digit', minute: '2-digit' }),
                  scheduled_duration: order.scheduled_duration || 60,
                  status: order.status,
                  status_display: order.status_display,
                  location: order.address,
                  priority: order.priority,
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
              displayDate.value = dateInMonth.toLocaleDateString(getPWALocale(), { month: 'long', year: 'numeric' });
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
          const status = String(booking.status || booking.state || '').toLowerCase();

          // Check for Running Late (Hibiscus Orange)
          if (isRunningLate(booking)) {
            return '#FB8C00'; // Hibiscus Orange
          }

          const colors = {
            'draft': '#1565C0',                      // Deep Blue - Booked
            'confirmed': '#1565C0',                  // Deep Blue - Confirmed
            'assigned': '#1565C0',                   // Deep Blue - Assigned
            'in_progress': '#43A047',                // Leaf Green - In Progress
            'completed': '#94A3B8',                  // Grey - Completed
            'completed_pending_invoice': '#94A3B8', // Grey - Pending Invoice
            'closed': '#94A3B8',                     // Grey - Closed
            'cancelled': '#E53935'                   // Hibiscus Red - Cancelled
          };
          return colors[status] || '#94A3B8';
        };

        const getStatusDisplay = (booking) => {
          if (!booking) return _t('Unknown');

          // Show "Running Late" if applicable
          if (isRunningLate(booking)) {
            return _t('Running Late');
          }

          // Support both 'status' (old) and 'state' (new API) properties
          const status = booking.status || booking.state || '';
          return getBookingStatusLabel(status);
        };

        // --- Brand status palette for redesigned cards (tint + accent + text) ---
        const statusKey = (booking) => {
          if (!booking) return 'upcoming';
          if (isRunningLate(booking)) return 'late';
          const s = String(booking.status || booking.state || '').toLowerCase();
          if (s === 'in_progress') return 'inprogress';
          if (['completed', 'completed_pending_invoice', 'closed'].includes(s)) return 'done';
          if (s === 'cancelled') return 'cancelled';
          return 'upcoming';
        };
        const STATUS_PALETTE = {
          late:       { ac: '#FB8C00', bg: '#FEE8C9', tx: '#9C4C00' },
          upcoming:   { ac: '#1565C0', bg: '#E4F4FD', tx: '#1356A9' },
          inprogress: { ac: '#43A047', bg: '#DBF0DB', tx: '#2E6B33' },
          done:       { ac: '#94A3B8', bg: '#EEF1F8', tx: '#475569' },
          cancelled:  { ac: '#E53935', bg: '#FBE3E1', tx: '#C32B2E' },
        };
        const statusAccent = (booking) => STATUS_PALETTE[statusKey(booking)].ac;
        const statusChip = (booking) => {
          const p = STATUS_PALETTE[statusKey(booking)];
          return { background: p.bg, color: p.tx };
        };
        const initials = (name) => {
          if (!name) return '?';
          const parts = String(name).trim().split(/\s+/).filter(Boolean);
          if (!parts.length) return '?';
          const first = parts[0][0] || '';
          const last = parts.length > 1 ? parts[parts.length - 1][0] : '';
          return (first + last).toUpperCase() || '?';
        };

        // Day summary counts (visits / late / done) for the Today pills
        const daySummary = computed(() => {
          const list = bookings.value || [];
          let late = 0, done = 0;
          list.forEach(b => {
            const k = statusKey(b);
            if (k === 'late') late++;
            else if (k === 'done') done++;
          });
          return { visits: list.length, late, done };
        });
        // Whether the currently viewed date is today (to highlight the Today button)
        const isToday = computed(() => {
          try { return new Date().toDateString() === currentDate.value.toDateString(); }
          catch (e) { return false; }
        });

        const callPatient = (phone) => {
          if (phone) {
            window.location.href = `tel:${phone}`;
          } else {
            alert(_t('No phone number available'));
          }
        };

        const callZalo = (zaloId) => {
          if (zaloId) {
            window.location.href = `https://zalo.me/${zaloId}`;
          }
        };

        // Open Google Maps with location
        const openMap = (location, patientName) => {
          if (location) {
            const encodedLocation = encodeURIComponent(location);
            const mapsUrl = `https://www.google.com/maps/search/${encodedLocation}`;
            window.open(mapsUrl, '_blank');
          } else {
            alert(_t('Location not available'));
          }
        };

        // Booking detail view state
        const selectedBookingId = ref(null);
        const selectedBookingDetail = ref(null);
        const isLoadingDetail = ref(false);
        const detailError = ref(null);
        // When the modal is opened from another route (orders/past-bookings/the
        // bell/a deep link, via the root openBooking() bridge), remember where
        // to return so closing the modal feels like an in-place overlay rather
        // than stranding the nurse on today-view. Null for a normal today tap.
        const modalReturnRoute = ref(null);
        // One-tap quick-complete (health_workflow_auto §2.5). onetapEligible
        // gates the footer button; set only after the live eligibility GET says
        // yes. onetapSubmitting disables the button during completion.
        const onetapEligible = ref(false);
        const onetapSubmitting = ref(false);

        // Offline visit actions (pwa-offline-actions §2.5): the set of FSO ids
        // that currently have a queued (unsynced) Start/notes action, driving
        // the "Chờ đồng bộ / Pending sync" badge on the card + modal header.
        const pendingActionFsoIds = ref(new Set());
        const hasPendingAction = (fsoId) => pendingActionFsoIds.value.has(fsoId);
        const refreshPendingActions = async () => {
          try {
            const sm = window.healthPWA && window.healthPWA.syncManager;
            if (sm && typeof sm.getPendingActionFsoIds === 'function') {
              pendingActionFsoIds.value = new Set(await sm.getPendingActionFsoIds());
            }
          } catch (e) {
            // Non-fatal: the badge just stays as-is.
          }
        };
        // After a sync resolves, the queue drains → recompute the badge set and
        // surface any rejected offline action (state conflict / access denied)
        // as a toast + detail refetch for the affected booking.
        const onSyncCompleted = () => {
          refreshPendingActions();
          const sm = window.healthPWA && window.healthPWA.syncManager;
          const rejected = (sm && sm.lastRejectedActionFsoIds) || [];
          // Consume the rejected set: an empty-queue sync skips
          // clearPushedChanges entirely, so without this reset the same
          // rejection re-toasts on every later sync (review fix).
          if (sm) {
            sm.lastRejectedActionFsoIds = [];
          }
          if (rejected.length) {
            window.healthPWA.showNotification(
              _t('Could not sync offline action — refreshed'), 'error');
            if (selectedBookingId.value && rejected.includes(selectedBookingId.value)) {
              fetchBookingDetail(selectedBookingId.value);
            }
            loadBookingsForDate(currentDate.value);
          }
        };

        // Fetch full booking details for inline expansion
        const fetchBookingDetail = async (bookingId) => {
          try {
            isLoadingDetail.value = true;
            detailError.value = null;
            onetapEligible.value = false;

            const response = await fetch(`/health_pwa/api/fso/${bookingId}`);
            const result = await response.json();

            if (result.success && result.data) {
              result.data.diagnosis = cleanDisplayValue(result.data.diagnosis);
              result.data.referring_doctor_name = cleanDisplayValue(result.data.referring_doctor_name);
              result.data.goal_of_care = cleanDisplayValue(result.data.goal_of_care);
              result.data.required_equipment = cleanDisplayValue(result.data.required_equipment);
              result.data.intake_notes = cleanDisplayValue(result.data.intake_notes);
              selectedBookingDetail.value = result.data;
              console.log('Loaded booking detail:', result.data);
              // One-tap eligibility (§2.5): re-check on every detail load.
              checkOnetapEligibility(bookingId, result.data.state);
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

        // One-tap quick-complete (§2.5). Guarded on window.healthOnetap so an
        // uninstalled health_workflow_auto stays silent. Eligibility is a live
        // GET, so the button never appears offline (server returns eligible:false
        // reason:'offline'). Re-checked on every detail (re)load.
        const checkOnetapEligibility = async (bookingId, state) => {
          onetapEligible.value = false;
          if (!window.healthOnetap || state !== 'in_progress') return;
          try {
            const res = await window.healthOnetap.checkEligible(bookingId);
            // Guard against a late response flipping the button for a booking
            // the nurse has since navigated away from.
            if (selectedBookingId.value === bookingId && res && res.eligible) {
              onetapEligible.value = true;
            }
          } catch (err) {
            console.warn('One-tap eligibility check failed:', err);
          }
        };

        const runOneTap = async () => {
          const bookingId = selectedBookingId.value;
          if (!bookingId || !window.healthOnetap) return;
          onetapSubmitting.value = true;
          try {
            const res = await window.healthOnetap.complete(bookingId);
            if (res && res.completed) {
              onetapEligible.value = false;
              if (window.healthPWA && window.healthPWA.showNotification) {
                window.healthPWA.showNotification(res.message || _t('Service completed'), 'success');
              }
              // Refresh the modal (state/buttons) and the day list.
              await fetchBookingDetail(bookingId);
              loadBookingsForDate(currentDate.value);
            } else if (res && res.needs_review) {
              // Quote drifted vs the booking snapshot — hand off to the existing
              // quote/complete flow (no diff UI in v1; the `changed` payload is
              // ignored per §2.5).
              onetapEligible.value = false;
              await openInvoiceModal();
            }
          } catch (err) {
            console.error('One-tap completion failed:', err);
            if (window.healthPWA && window.healthPWA.showNotification) {
              window.healthPWA.showNotification(_t('One-tap completion failed'), 'error');
            }
          } finally {
            onetapSubmitting.value = false;
          }
        };

        // Toggle booking detail expansion
        const toggleBookingDetail = async (bookingId) => {
          if (selectedBookingId.value === bookingId) {
            // Close if already open
            selectedBookingId.value = null;
            selectedBookingDetail.value = null;
            clinicalNotesText.value = '';
            onetapEligible.value = false;
            // If this modal was opened from another screen, go back to it.
            const rr = modalReturnRoute.value;
            modalReturnRoute.value = null;
            if (rr) {
              emit('navigate', rr);
            }
          } else {
            // Open and fetch details (a direct today tap — clear any stale
            // return route so closing stays on today).
            modalReturnRoute.value = null;
            selectedBookingId.value = bookingId;
            await fetchBookingDetail(bookingId);
          }
        };

        // Open the modal for a booking handed down by the root openBooking()
        // bridge (orders/past-bookings/the bell/a deep link). Same fetch as a
        // today tap — the GET /health_pwa/api/fso/<id> the family panel keys on
        // still fires — but remembers the origin route for close.
        const openBookingFromRoute = async (bookingId, returnRoute) => {
          modalReturnRoute.value = returnRoute || null;
          selectedBookingId.value = bookingId;
          await fetchBookingDetail(bookingId);
        };

        // Consume a pending booking the root handed down (on mount / remount).
        const consumePendingBooking = () => {
          const pb = props.pendingBooking;
          if (pb && pb.id) {
            emit('consume-booking');
            openBookingFromRoute(pb.id, pb.returnRoute);
          }
        };

        // Computed property for formatted scheduled datetime (handles timezone correctly)
        const formattedScheduledDateTime = computed(() => {
          if (!selectedBookingDetail.value || !selectedBookingDetail.value.scheduled_datetime) {
            return 'TBD';
          }
          const dateObj = parseOdooDateTime(selectedBookingDetail.value.scheduled_datetime);
          return dateObj.toLocaleString(getPWALocale(), { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
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
        const showClinicalNoteForm = ref(false);
        const viewingClinicalNote = ref(null);
        const clinicalNotesText = ref('');
        const clinicalObservations = ref('');
        const diagnosis = ref('');
        const treatmentPerformed = ref('');
        const capturedPhoto = ref(null);
        const photoPreviewUrl = ref(null);

        const injectionCount = ref(1);
        const medicationCount = ref(1);
        const woundCount = ref(1);
        const ivFluidCount = ref(0);

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

        // Cancellation Modal State
        const showCancellationModal = ref(false);
        const cancellationReasons = ref([]);
        const cancellationFormData = ref({
          reason_id: null,
          notes: ''
        });
        const cancellationSubmitting = ref(false);

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
          other_reason_text: '',
          need_follow_up: false
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
          is_doctor: false,
          booking_credit: 0
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

            // Check if response is HTML (session expired / login redirect)
            const contentType = response.headers.get('content-type') || '';
            if (!response.ok || !contentType.includes('application/json')) {
              if (response.status === 303 || response.redirected || contentType.includes('text/html')) {
                catalogError.value = 'Session expired. Please reload the page.';
                console.error('Catalog API returned non-JSON (likely session expired)');
                return;
              }
              catalogError.value = `Server error (${response.status})`;
              return;
            }

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
          if (selectedBookingDetail.value?.clinical_notes_submitted) {
            return true;
          }
          const notesList = selectedBookingDetail.value?.clinical_notes_list || [];
          return notesList.length > 0;
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
              alert(_t('Please add verification notes explaining the changes made to Qty or Discount.'));
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
                    alert(_t('Please provide a discount reason for: ') + line.product_name);
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
              alert(_t('Error saving quote: ') + displayError(result.error));
            }
          } catch (err) {
            console.error('Error saving quote:', err);
            alert(_t('Failed to save quote: ') + err.message);
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
            alert(_t('Please verify the invoice first and click Save Quote.'));
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
              alert(_t('Error: Server returned status ') + response.status + _t('. Please try again.'));
              return;
            }

            let result;
            try {
              result = await response.json();
            } catch (jsonError) {
              const responseText = await response.text();
              console.error('Failed to parse JSON response:', responseText);
              alert(_t('Error: Invalid response from server. Details: ') + responseText.substring(0, 100));
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
                alert(_t('Service completed successfully!'));
                loadBookingsForDate(currentDate.value);
              }
            } else {
              console.error('Error completing payment:', result.error);
              alert(_t('Error completing payment: ') + displayError(result.error));
            }
          } catch (err) {
            console.error('Error completing payment:', err);
            alert(_t('Failed to complete payment: ') + err.message);
          }
        };

        // Load cancellation reasons from backend
        const loadCancellationReasons = async () => {
          if (cancellationReasons.value.length > 0) return;
          try {
            const lang = window.healthPWAConfig?.user_lang || 'en_US';
            const response = await fetch(`/health_pwa/api/cancellation_reasons?lang=${encodeURIComponent(lang)}`);
            const data = await response.json();
            if (data.success && data.data?.reasons) {
              cancellationReasons.value = data.data.reasons;
            }
          } catch (err) {
            console.error('Error loading cancellation reasons:', err);
          }
        };

        // Cancel/Refuse visit - open modal
        const cancelVisit = async () => {
          if (!selectedBookingId.value) return;
          await loadCancellationReasons();
          cancellationFormData.value = { reason_id: null, notes: '' };
          cancellationSubmitting.value = false;
          showCancellationModal.value = true;
        };

        // Submit cancellation
        const submitCancellation = async () => {
          if (!cancellationFormData.value.reason_id) {
            window.healthPWA.showNotification(_t('Please select a cancellation reason'), 'error');
            return;
          }
          cancellationSubmitting.value = true;
          try {
            const response = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/cancel`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                cancellation_reason_id: cancellationFormData.value.reason_id,
                cancellation_notes: cancellationFormData.value.notes.trim()
              })
            });
            const result = await response.json();
            if (result.success) {
              window.healthPWA.showNotification(_t('Visit cancelled successfully'), 'success');
              showCancellationModal.value = false;
              selectedBookingId.value = null;
              selectedBookingDetail.value = null;
              await loadBookingsForDate(currentDate.value);
            } else {
              window.healthPWA.showNotification(displayError(result.error) || _t('Failed to cancel visit'), 'error');
            }
          } catch (err) {
            console.error('Error cancelling visit:', err);
            window.healthPWA.showNotification(_t('Error cancelling visit:') + ' ' + err.message, 'error');
          } finally {
            cancellationSubmitting.value = false;
          }
        };

        // Start service
        const startService = async () => {
          if (selectedBookingId.value) {
            // Offline: queue an idempotent Start action (client uuid + claimed
            // timestamp), optimistically mark the visit in-progress locally and
            // replay at the next sync (pwa-offline-actions §2.5). Uses the same
            // online signal the modal already reads (the is-online prop).
            if (!props.isOnline || !navigator.onLine) {
              const bookingId = selectedBookingId.value;
              try {
                const sm = window.healthPWA && window.healthPWA.syncManager;
                if (sm && typeof sm.queueAction === 'function') {
                  await sm.queueAction('start_service', bookingId, {});
                  await sm.patchLocalOrder(bookingId, {
                    state: 'in_progress', pendingSync: true,
                    actual_start_datetime: new Date().toISOString(),
                  });
                }
                serviceStartedForBooking.value = bookingId;
                if (selectedBookingDetail.value) {
                  selectedBookingDetail.value.state = 'in_progress';
                  selectedBookingDetail.value.actual_start_datetime = new Date().toISOString();
                }
                pendingActionFsoIds.value = new Set([...pendingActionFsoIds.value, bookingId]);
                startTimer();
                window.healthPWA.showNotification(
                  _t('Saved offline — will sync when online'), 'success');
              } catch (err) {
                console.error('Failed to queue offline start:', err);
                window.healthPWA.showNotification(
                  _t('Error starting service: ') + err.message, 'error');
              }
              return;
            }
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
                alert(_t('Error: ') + displayError(result.error));
              }
            } catch (err) {
              console.error('Error starting service:', err);
              alert(_t('Error starting service: ') + err.message);
            }
          } else {
            console.error('No booking selected');
          }
        };

        const openClinicalNotesModal = () => {
          showClinicalNotesModal.value = true;
          showClinicalNoteForm.value = false;
          viewingClinicalNote.value = null;
        };

        // Keep the finalize path reachable AFTER the visit is delivered
        // (emr-record-spine phase 1.7 fix). The "Clinical Notes" footer button
        // above only renders for in_progress / just-started visits, but an
        // OVERDUE unsigned draft — the exact population the "Notes to sign" card
        // surfaces — lives on a visit that is already completed/closed. Without
        // this the card row deep-links to a modal with no way to reach the
        // Finalize & Sign button. Show ONLY the notes button (never the
        // completion actions), and ONLY for a delivered visit that still has an
        // unsigned draft (so it never duplicates the in_progress button and
        // never appears on a fully-signed completed visit).
        const hasUnsignedDraftToSign = computed(() => {
          const d = selectedBookingDetail.value;
          if (!d) return false;
          const delivered = ['completed', 'completed_pending_invoice', 'closed']
            .includes(d.state);
          if (!delivered) return false;
          return (d.clinical_notes_list || []).some((n) => n.emr_state === 'draft');
        });

        const openNewClinicalNoteForm = () => {
          showClinicalNoteForm.value = true;
          viewingClinicalNote.value = null;
          clinicalNotesText.value = '';
          clinicalObservations.value = '';
          diagnosis.value = '';
          treatmentPerformed.value = '';
          capturedPhoto.value = null;
          photoPreviewUrl.value = null;
          injectionCount.value = 0;
          medicationCount.value = 0;
          woundCount.value = 0;
          ivFluidCount.value = 0;
        };

        const viewExistingNote = (note) => {
          viewingClinicalNote.value = note;
          showClinicalNoteForm.value = false;
        };

        const backToNotesList = () => {
          showClinicalNoteForm.value = false;
          viewingClinicalNote.value = null;
        };

        // EMR "Notes to sign" home card (emr-record-spine phase 1.7). A
        // read-only, ONLINE-only nudge: lists the nurse's OWN unsigned draft
        // notes so aging drafts don't pile up invisibly (Phase-1.6 raises a
        // backend mail.activity she never sees in the PWA). Each row deep-links
        // to the booking modal's existing Finalize & Sign button — this card
        // finalizes nothing itself.
        const unsignedNotes = ref([]);
        const unsignedCount = computed(() => unsignedNotes.value.length);
        const overdueNotesCount = computed(
          () => unsignedNotes.value.filter((n) => n.overdue).length);

        const loadUnsignedNotes = async () => {
          if (!props.isOnline && !navigator.onLine) return;
          try {
            const resp = await fetch('/health_pwa/api/clinical_notes/unsigned');
            const result = await resp.json();
            if (result.success && result.data) {
              unsignedNotes.value = result.data.notes || [];
            }
          } catch (err) {
            console.warn('[NotesToSign] Failed to fetch:', err);
          }
        };

        // Relative age label (VN-first, no catalog pluralization) from age_hours.
        const noteAgeLabel = (row) => {
          const h = row.age_hours || 0;
          const vi = (window.healthPWAConfig?.user_lang || 'vi').startsWith('vi');
          if (h < 1) return vi ? 'vừa xong' : 'just now';
          if (h < 24) return vi ? `${h} giờ trước` : `${h} hour${h === 1 ? '' : 's'} ago`;
          const d = Math.floor(h / 24);
          return vi ? `${d} ngày trước` : `${d} day${d === 1 ? '' : 's'} ago`;
        };

        // Row tap → open the shared booking modal (openBooking bridge via
        // navigate('order', …)) where the finalize button already lives.
        const openUnsignedNote = (row) => {
          if (!row || !row.order_id) return;
          emit('navigate', 'order', { id: row.order_id });
        };

        // EMR point-of-care finalize (emr-record-spine phase 1.5). Signs the
        // note as THIS nurse via the online-only endpoint; the server attributes
        // the signature to her and locks the record. Online-only (the legal
        // signing act is server-authoritative — no offline queue), so a draft
        // note stays fully editable offline until the nurse signs it online.
        const finalizingNote = ref(false);
        const finalizeNote = async (note) => {
          if (!note || note.emr_state === 'final') return;
          if (!props.isOnline && !navigator.onLine) {
            window.healthPWA.showNotification(
              _t('Connect to the internet to finalize & sign this note.'), 'warning');
            return;
          }
          if (!window.confirm(_t('Finalize and sign this clinical note? Once signed it becomes a permanent, locked medical record and cannot be edited.'))) {
            return;
          }
          finalizingNote.value = true;
          try {
            const bookingId = selectedBookingId.value;
            const response = await fetch(
              `/health_pwa/api/fso/${bookingId}/clinical_notes/${note.id}/finalize`,
              { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}) });
            const result = await response.json();
            if (result.success && result.data) {
              window.healthPWA.showNotification(
                _t('Clinical note finalized and signed'), 'success');
              // Refetch so the note (and its list chip) reflect the signed
              // state; re-point the open note at the refreshed record.
              await fetchBookingDetail(bookingId);
              const list = selectedBookingDetail.value?.clinical_notes_list || [];
              viewingClinicalNote.value = list.find((n) => n.id === note.id) || null;
              // Re-fetch the "Notes to sign" card so the just-signed note drops off.
              loadUnsignedNotes();
            } else {
              window.healthPWA.showNotification(
                result.error || _t('Finalization failed'), 'error');
            }
          } catch (err) {
            window.healthPWA.showNotification(
              _t('Finalization failed') + ': ' + err.message, 'error');
          } finally {
            finalizingNote.value = false;
          }
        };

        const closeClinicalNotesModal = () => {
          showClinicalNotesModal.value = false;
          showClinicalNoteForm.value = false;
          viewingClinicalNote.value = null;
          clinicalNotesText.value = '';
          clinicalObservations.value = '';
          diagnosis.value = '';
          treatmentPerformed.value = '';
          capturedPhoto.value = null;
          photoPreviewUrl.value = null;
          injectionCount.value = 0;
          medicationCount.value = 0;
          woundCount.value = 0;
          ivFluidCount.value = 0;
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

        const saveClinicalNotes = async () => {
          try {
            if (!selectedBookingId.value) return;

            let hasNotes = false;
            let requestData = {};

            if (currentUser.value.is_doctor) {
              hasNotes =
                (clinicalObservations.value && clinicalObservations.value.trim().length > 0) ||
                (diagnosis.value && diagnosis.value.trim().length > 0) ||
                (treatmentPerformed.value && treatmentPerformed.value.trim().length > 0);
              requestData = {
                clinical_notes: clinicalObservations.value,
                diagnosis: diagnosis.value,
                treatment_performed: treatmentPerformed.value,
                injection_count: injectionCount.value,
                medication_count: medicationCount.value,
                wound_count: woundCount.value,
                iv_fluid_count: ivFluidCount.value,
              };
            } else {
              hasNotes = clinicalNotesText.value && clinicalNotesText.value.trim().length > 0;
              requestData = {
                clinical_notes: clinicalNotesText.value,
                injection_count: injectionCount.value,
                medication_count: medicationCount.value,
                wound_count: woundCount.value,
                iv_fluid_count: ivFluidCount.value,
              };
            }

            const hasPhoto = capturedPhoto.value !== null;

            if (!hasNotes && !hasPhoto) {
              alert(_t('Please provide clinical notes or take a photo before saving'));
              return;
            }

            // Offline: queue the note payload (text fields only — photos stay
            // online-only, phase non-goal) and replay as a clinical.note create
            // at the next sync (pwa-offline-actions §2.5). Keep the text in the
            // form state; show the pending badge + the same toast.
            if (!props.isOnline || !navigator.onLine) {
              const bookingId = selectedBookingId.value;
              if (!hasNotes) {
                alert(_t('Please provide clinical notes or take a photo before saving'));
                return;
              }
              try {
                const sm = window.healthPWA && window.healthPWA.syncManager;
                if (sm && typeof sm.queueAction === 'function') {
                  await sm.queueAction('save_clinical_notes', bookingId, requestData);
                }
                pendingActionFsoIds.value = new Set([...pendingActionFsoIds.value, bookingId]);
                window.healthPWA.showNotification(
                  _t('Saved offline — will sync when online'), 'success');
                showClinicalNoteForm.value = false;
                viewingClinicalNote.value = null;
              } catch (err) {
                console.error('Failed to queue offline clinical note:', err);
                alert(_t('Error saving clinical note:') + ' ' + err.message);
              }
              return;
            }

            // Step 1: Create the clinical note record
            const response = await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/clinical_notes`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(hasNotes ? requestData : { clinical_notes: '(Photo attached)' })
            });
            const result = await response.json();
            if (!response.ok || !result.data) {
              throw new Error(result.error || _t('Failed to create clinical note'));
            }
            const noteId = result.data.note_id;

            // Step 2: Upload photo if captured, linking to the new note
            if (hasPhoto && noteId) {
              const photoFormData = new FormData();
              photoFormData.append('image', capturedPhoto.value);
              photoFormData.append('note_id', noteId);
              try {
                await fetch(`/health_pwa/api/fso/${selectedBookingId.value}/upload_image`, {
                  method: 'POST',
                  body: photoFormData
                });
              } catch (photoErr) {
                console.warn('Photo upload failed:', photoErr);
              }
            }

            // Step 3: Refresh booking detail to get updated notes list
            await fetchBookingDetail(selectedBookingId.value);

            alert(_t('Clinical note saved successfully'));
            showClinicalNoteForm.value = false;
            viewingClinicalNote.value = null;
          } catch (err) {
            console.error('Error saving clinical note:', err);
            alert(_t('Error saving clinical note:') + ' ' + err.message);
          }
        };

        // Complete service without quote (for today-view)
        const completeServiceWithoutQuoteInTodayView = async () => {
          if (!selectedBookingId.value) {
            alert(_t('No booking selected'));
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
                alert(_t('Service completed successfully!'));
                loadBookingsForDate(currentDate.value);
              }
            } else {
              alert(_t('Failed to complete service: ') + displayError(data.error || _t('Unknown error')));
            }
          } catch (err) {
            console.error('Complete service without quote error:', err);
            alert(_t('Error completing service: ') + err.message);
          }
        };

        // Handle "No Future Visit" submission from Modal A
        const submitNoFutureVisit = async () => {
          if (!nextVisitFormData.value.no_future_visit_reason) {
            alert(_t('Please select a reason'));
            return;
          }

          if (nextVisitFormData.value.no_future_visit_reason === 'other' && !nextVisitFormData.value.other_reason_text) {
            alert(_t('Please enter explanation for "Other" reason'));
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
                reason: finalReason,
                need_follow_up: nextVisitFormData.value.need_follow_up || false
              })
            });

            const data = await response.json();
            console.log('No future visit response:', data);

            if (data.success) {
              alert(_t('Noted: Patient does not need future visits'));
              showNextVisitModalA.value = false;
              // Close modal and refresh to show today's bookings
              completedBookingId.value = null;
              // Reset form
              nextVisitFormData.value.no_future_visit_reason = '';
              nextVisitFormData.value.other_reason_text = '';
              nextVisitFormData.value.need_follow_up = false;
              // Refresh bookings list to reflect the change
              await loadBookingsForDate(currentDate.value);
            } else {
              alert(_t('Failed to submit: ') + displayError(data.error || _t('Unknown error')));
            }
          } catch (err) {
            console.error('Submit no future visit error:', err);
            alert(_t('Error submitting: ') + err.message);
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
            alert(_t('Please select a date'));
            return;
          }

          if (!nextVisitFormData.value.scheduled_time) {
            alert(_t('Please select a time'));
            return;
          }

          if (!nextVisitFormData.value.quote_items || nextVisitFormData.value.quote_items.length === 0) {
            alert(_t('Please add at least one service'));
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

            const requestBody = {
              next_visit_date: isoDateTime,
              scheduled_datetime: isoDateTime,
              quote_items: nextVisitFormData.value.quote_items,
            };

            if (!nextVisitData.value.has_next_visit) {
              requestBody.assigned_staff_id = nextVisitFormData.value.assigned_nurse_id;
            } else {
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
              alert(_t('Next visit scheduled successfully!'));
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
                other_reason_text: '',
                need_follow_up: false
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
              alert(_t('Failed to schedule: ') + displayError(data.error || _t('Unknown error')));
            }
          } catch (err) {
            console.error('Schedule next visit error:', err);
            alert(_t('Error scheduling: ') + err.message);
          }
        };

        // Show client details view after booking completion
        const showClientDetails = (patientData) => {
          currentClientData.value = {
            id: patientData.patient_id,
            name: patientData.patient_name,
            phone: patientData.phone || _t('N/A'),
            age: patientData.age,
            gender: patientData.gender || _t('N/A'),
            patient_code: patientData.patient_code || _t('N/A')
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
              other_reason_text: '',
              need_follow_up: false
            };
            // Update nextVisitData with current patient
            nextVisitData.value.patient_id = currentClientData.value.id;
            nextVisitData.value.patient_name = currentClientData.value.name;

            showClientDetailsView.value = false;
            showNextVisitModalA.value = true;
          } catch (err) {
            console.error('Error opening next booking:', err);
            alert(_t('Error: ') + err.message);
          }
        };

        // Open Modal B with current user pre-populated
        const openNextVisitModal = () => {
          // Reset form with current user's employee ID
          nextVisitFormData.value = {
            scheduled_date: null,
            scheduled_time: null,
            quote_items: [],
            assigned_nurse_id: currentUser.value.employee_id,
            assigned_nurse_name: currentUser.value.name || '',
            no_future_visit_reason: '',
            other_reason_text: '',
            need_follow_up: false
          };
          showNextVisitModalA.value = false;
          showNextVisitModalB.value = true;
        };

        onMounted(() => {
          loadBookingsForDate(currentDate.value);
          loadMonthBookings(currentDate.value); // Load current month bookings
          loadCurrentUser(); // Load current user info
          // If the root handed us a booking to open (from another route), do it.
          consumePendingBooking();
          // "Notes to sign" home card (emr phase 1.7): seed on mount.
          loadUnsignedNotes();
          // Offline-action badge: seed the set and refresh it after every sync.
          refreshPendingActions();
          window.addEventListener('health-pwa-sync-completed', onSyncCompleted);
        });

        onUnmounted(() => {
          // Cleanup timer on unmount
          stopTimer();
          window.removeEventListener('health-pwa-sync-completed', onSyncCompleted);
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
          statusKey,
          statusAccent,
          statusChip,
          initials,
          daySummary,
          isToday,
          isRunningLate,
          callPatient,
          callZalo,
          openMap,
          isTransitioning,
          // Calendar functions
          getPWALocale,
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
          hasPendingAction,
          formattedScheduledDateTime,
          // Intake summary modal
          showIntakeSummaryModal,
          selectedBookingForIntake,
          toggleIntakeSummaryModal,
          // Service start and clinical notes
          serviceStartedForBooking,
          onetapEligible,
          onetapSubmitting,
          runOneTap,
          showClinicalNotesModal,
          showClinicalNoteForm,
          viewingClinicalNote,
          clinicalNotesText,
          clinicalObservations,
          diagnosis,
          treatmentPerformed,
          capturedPhoto,
          photoPreviewUrl,
          injectionCount,
          medicationCount,
          woundCount,
          ivFluidCount,
          startService,
          cancelVisit,
          openClinicalNotesModal,
          hasUnsignedDraftToSign,
          closeClinicalNotesModal,
          openNewClinicalNoteForm,
          viewExistingNote,
          backToNotesList,
          finalizeNote,
          finalizingNote,
          // "Notes to sign" home card (emr phase 1.7)
          unsignedNotes,
          unsignedCount,
          overdueNotesCount,
          loadUnsignedNotes,
          noteAgeLabel,
          openUnsignedNote,
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
          // Cancellation modal
          showCancellationModal,
          cancellationReasons,
          cancellationFormData,
          cancellationSubmitting,
          submitCancellation,
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
          convertLocalDateTimeToISO,
          cleanDisplayValue,
          displayDbValue,
          displayError,
          // Translation helper
          _t
        };
      },
      template: `
        <div class="today-view" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
          <!-- Consolidated day sub-header -->
          <div class="bk-sub">
            <!-- Row 1: full date (left) + staff name (right, light grey) -->
            <div class="bk-toprow">
              <div class="bk-date">{{ displayDate }}</div>
              <div class="bk-staff">{{ staffName }}</div>
            </div>
            <!-- Row 2: Today (all views) + date navigation -->
            <div class="bk-navrow">
              <button @click="goToToday" class="bk-today" :class="{ 'is-current': isToday }" :title="_t('Jump to today')">{{ _t('Today') }}</button>
              <div class="bk-navbtns">
                <button @click="goToPrevious" class="bk-rnd" :title="_t('Previous')">
                  <i class="material-icons">chevron_left</i>
                </button>
                <button @click="toggleCalendar" class="bk-rnd solid" :title="_t('Select date')">
                  <i class="material-icons">calendar_month</i>
                </button>
                <button @click="goToNext" class="bk-rnd" :title="_t('Next')">
                  <i class="material-icons">chevron_right</i>
                </button>
              </div>
            </div>

            <!-- Segmented control with sliding pill -->
            <div class="bk-seg" :class="'sel-' + viewMode">
              <span class="bk-seg-pill"></span>
              <button @click="setViewMode('day')" :class="{ on: viewMode === 'day' }">{{ _t('Day') }}</button>
              <button @click="setViewMode('week')" :class="{ on: viewMode === 'week' }">{{ _t('Week') }}</button>
              <button @click="setViewMode('month')" :class="{ on: viewMode === 'month' }">{{ _t('Month') }}</button>
            </div>
          </div>

          <!-- Notes to sign (emr-record-spine phase 1.7): the nurse's OWN
               unsigned drafts, deep-linking to the booking modal's existing
               Finalize & Sign button. Hidden entirely when empty. Read-only
               nudge — flat mono, no gradient (feedback_mono_colors). -->
          <div v-if="unsignedCount > 0" class="notes-to-sign-card"
               style="margin:12px;border:1px solid #E0E0E0;border-radius:12px;background:#FFFFFF;overflow:hidden;">
            <div class="nts-header"
                 style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-bottom:1px solid #F0F0F0;">
              <div style="display:flex;align-items:center;gap:8px;font-weight:600;color:#263238;">
                <i class="material-icons" style="color:#1565C0;font-size:20px;">edit_note</i>
                <span>{{ _t('Notes to sign') }}</span>
                <span style="background:#1565C0;color:#FFFFFF;border-radius:10px;padding:1px 8px;font-size:12px;font-weight:600;">{{ unsignedCount }}</span>
              </div>
              <span v-if="overdueNotesCount > 0"
                    style="display:flex;align-items:center;gap:4px;color:#FB8C00;font-size:12px;font-weight:600;">
                <i class="material-icons" style="font-size:16px;">schedule</i>
                {{ overdueNotesCount }} {{ _t('overdue') }}
              </span>
            </div>
            <div class="nts-list">
              <div v-for="row in unsignedNotes" :key="row.note_id"
                   @click="openUnsignedNote(row)"
                   style="display:flex;align-items:center;justify-content:space-between;padding:11px 14px;border-top:1px solid #F5F5F5;cursor:pointer;">
                <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
                  <div style="display:flex;align-items:center;gap:6px;font-weight:500;color:#37474F;">
                    <i v-if="row.overdue" class="material-icons" style="color:#FB8C00;font-size:18px;">warning</i>
                    <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ row.patient_name || _t('Patient') }}</span>
                  </div>
                  <div style="font-size:12px;color:#90A4A4;">{{ noteAgeLabel(row) }}</div>
                </div>
                <i class="material-icons" style="color:#B0BEC5;flex-shrink:0;">chevron_right</i>
              </div>
            </div>
          </div>

          <!-- Content based on view mode -->
            <div v-if="isLoading" class="loading-spinner">
              <div class="spinner"></div>
              <p>{{ _t('Loading bookings...') }}</p>
            </div>

          <div v-else-if="error" class="error-message">
            <i class="material-icons">error</i>
            <p>{{ error }}</p>
            <button @click="goToToday" class="btn btn-secondary">{{ _t('Retry') }}</button>
          </div>

          <!-- Day view -->
          <div v-else-if="viewMode === 'day'">
            <!-- Day summary pills -->
            <div v-if="bookings.length" class="bk-summary">
              <span class="bk-chip"><span class="dot" style="background:#1565C0"></span><b>{{ daySummary.visits }}</b> {{ _t('visits') }}</span>
              <span class="bk-chip"><span class="dot" style="background:#FB8C00"></span><b>{{ daySummary.late }}</b> {{ _t('late') }}</span>
              <span class="bk-chip"><span class="dot" style="background:#43A047"></span><b>{{ daySummary.done }}</b> {{ _t('done') }}</span>
            </div>

            <div v-if="bookings.length === 0" class="empty-state">
              <i class="material-icons">event_note</i>
              <p>{{ _t('No bookings scheduled for this day') }}</p>
            </div>

            <div v-else class="bookings-list">
              <div v-for="booking in bookings" :key="booking.fso_id" class="booking-card" :data-fso-id="booking.fso_id" :data-fso-status="booking.status" :style="{ '--ac': statusAccent(booking) }" @click="toggleBookingDetail(booking.fso_id)">
                  <!-- Header with time and status -->
                  <div class="booking-card-header">
                    <div class="booking-time-badge">
                      {{ booking.formatted_time || booking.scheduled_time }}<small>{{ booking.scheduled_duration }} min</small>
                    </div>
                    <div class="status-badge" :style="statusChip(booking)">
                      {{ getStatusDisplay(booking) }}
                    </div>
                    <!-- Pending offline-action badge (pwa-offline-actions §2.5,
                         flat mono amber, material-icons glyph per PWA idiom,
                         no emoji/gradient) -->
                    <span v-if="hasPendingAction(booking.fso_id)" class="status-badge"
                          :title="_t('Pending sync')"
                          style="background:#d97706;color:#fff;display:inline-flex;align-items:center;gap:2px;">
                      <i class="material-icons" style="font-size:13px;">sync</i>{{ _t('Pending sync') }}
                    </span>
                  </div>

                  <!-- Patient info -->
                  <div class="booking-patient-section">
                    <div class="bk-avatar">{{ initials(booking.patient_name) }}</div>
                    <div class="bk-who">
                      <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                      <span v-if="booking.patient_code" class="bk-code">{{ booking.patient_code }}</span>
                    </div>
                  </div>

                  <!-- Service type with action buttons inline -->
                  <div class="booking-service-row">
                    <p v-if="booking.service_type" class="booking-service-type">
                      {{ displayDbValue(booking.service_type) }}
                      <span v-if="booking.lead_staff_name" class="booking-lead-inline">
                        ({{ cleanDisplayValue(booking.lead_staff_name) }})
                      </span>
                    </p>
                    <div class="booking-action-icons">
                      <button @click.stop="callPatient(booking.patient_phone)" class="btn-icon-action btn-icon-call" :title="_t('Call patient')">
                        <i class="material-icons">call</i>
                      </button>
                      <button v-if="booking.patient_zalo" @click.stop="callZalo(booking.patient_zalo)" class="btn-icon-action btn-icon-zalo" :title="_t('Zalo call')">
                        <i class="material-icons">chat</i>
                      </button>
                      <button @click.stop="openMap(booking.location, booking.patient_name)" class="btn-icon-action btn-icon-map" :title="_t('Open map')">
                        <i class="material-icons">map</i>
                      </button>
                    </div>
                  </div>

                  <!-- Lead nurse name -->
              </div>
            </div>
          </div>

          <!-- Week view -->
          <div v-else-if="viewMode === 'week'">
            <div v-if="Object.keys(groupedBookings).length === 0" class="empty-state">
              <i class="material-icons">event_note</i>
              <p>{{ _t('No bookings scheduled for this week') }}</p>
            </div>

            <div v-else class="grouped-bookings-list">
              <div v-for="(dateBookings, dateStr) in groupedBookings" :key="dateStr" class="date-group">
                <h4 class="date-group-title">{{ dateStr }}</h4>
                <div v-for="booking in dateBookings" :key="booking.fso_id" class="booking-card-container">
                  <!-- Clickable booking card -->
                  <div @click="toggleBookingDetail(booking.fso_id)" class="booking-card" :class="{ expanded: selectedBookingId === booking.fso_id }" :style="{ '--ac': statusAccent(booking) }">
                    <!-- Header with time and status -->
                    <div class="booking-card-header">
                      <div class="booking-time-badge">
                        {{ booking.scheduled_time }}<small>{{ booking.scheduled_duration || 60 }} min</small>
                      </div>
                      <div class="status-badge" :style="statusChip(booking)">
                        {{ getStatusDisplay(booking) }}
                      </div>
                    </div>

                    <!-- Patient info -->
                    <div class="booking-patient-section">
                      <div class="bk-avatar">{{ initials(booking.patient_name) }}</div>
                      <div class="bk-who">
                        <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                        <span v-if="booking.patient_code" class="bk-code">{{ booking.patient_code }}</span>
                      </div>
                    </div>

                    <!-- Service type with action buttons inline -->
                    <div class="booking-service-row">
                    <p v-if="booking.service_type" class="booking-service-type">
                      {{ displayDbValue(booking.service_type) }}
                      <span v-if="booking.lead_staff_name" class="booking-lead-inline">
                        ({{ cleanDisplayValue(booking.lead_staff_name) }})
                      </span>
                    </p>
                      <div class="booking-action-icons">
                        <button @click.stop="callPatient(booking.patient_phone)" class="btn-icon-action btn-icon-call" :title="_t('Call patient')">
                          <i class="material-icons">call</i>
                        </button>
                        <button @click.stop="openMap(booking.location, booking.patient_name)" class="btn-icon-action btn-icon-map" :title="_t('Open map')">
                          <i class="material-icons">map</i>
                        </button>
                      </div>
                    </div>

                    <!-- Lead nurse name -->
              </div>
            </div>
          </div>
            </div>
          </div>

          <!-- Month view -->
          <div v-else-if="viewMode === 'month'">
            <div v-if="Object.keys(groupedBookings).length === 0" class="empty-state">
              <i class="material-icons">event_note</i>
              <p>{{ _t('No bookings scheduled for this month') }}</p>
            </div>

            <div v-else class="grouped-bookings-list">
              <div v-for="(dateBookings, dateStr) in groupedBookings" :key="dateStr" class="date-group">
                <h4 class="date-group-title">{{ dateStr }}</h4>
                <div v-for="booking in dateBookings" :key="booking.fso_id" class="booking-card-container">
                  <!-- Clickable booking card -->
                  <div @click="toggleBookingDetail(booking.fso_id)" class="booking-card" :class="{ expanded: selectedBookingId === booking.fso_id }" :style="{ '--ac': statusAccent(booking) }">
                    <!-- Header with time and status -->
                    <div class="booking-card-header">
                      <div class="booking-time-badge">
                        {{ booking.scheduled_time }}<small>{{ booking.scheduled_duration || 60 }} min</small>
                      </div>
                      <div class="status-badge" :style="statusChip(booking)">
                        {{ getStatusDisplay(booking) }}
                      </div>
                    </div>

                    <!-- Patient info -->
                    <div class="booking-patient-section">
                      <div class="bk-avatar">{{ initials(booking.patient_name) }}</div>
                      <div class="bk-who">
                        <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                        <span v-if="booking.patient_code" class="bk-code">{{ booking.patient_code }}</span>
                      </div>
                    </div>

                    <!-- Service type with action buttons inline -->
                    <div class="booking-service-row">
                    <p v-if="booking.service_type" class="booking-service-type">
                      {{ displayDbValue(booking.service_type) }}
                      <span v-if="booking.lead_staff_name" class="booking-lead-inline">
                        ({{ cleanDisplayValue(booking.lead_staff_name) }})
                      </span>
                    </p>
                      <div class="booking-action-icons">
                        <button @click.stop="callPatient(booking.patient_phone)" class="btn-icon-action btn-icon-call" :title="_t('Call patient')">
                          <i class="material-icons">call</i>
                        </button>
                        <button @click.stop="openMap(booking.location, booking.patient_name)" class="btn-icon-action btn-icon-map" :title="_t('Open map')">
                          <i class="material-icons">map</i>
                        </button>
                      </div>
                    </div>

                    <!-- Lead nurse name -->
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
              <p>{{ _t('Loading details...') }}</p>
            </div>
            <div v-else-if="detailError" class="detail-error">
              <p>{{ detailError }}</p>
              <button class="btn btn-secondary" @click="toggleBookingDetail(selectedBookingId)">{{ _t('Close') }}</button>
            </div>
            <div v-else-if="selectedBookingDetail" class="booking-detail-modal-content">
              <!-- Drag handle -->
              <div class="sheet-handle"></div>
              <!-- Modal header with close button -->
              <div class="modal-header">
                <div class="header-content">
                  <h3 class="modal-title">{{ _t('Booking Details') }}</h3>
                  <span class="status-badge sheet-status" :style="statusChip(selectedBookingDetail)">{{ getStatusDisplay(selectedBookingDetail) }}</span>
                  <!-- Pending offline-action badge (pwa-offline-actions §2.5) -->
                  <span v-if="hasPendingAction(selectedBookingId)" class="status-badge sheet-status"
                        :title="_t('Pending sync')"
                        style="background:#d97706;color:#fff;display:inline-flex;align-items:center;gap:2px;">
                    <i class="material-icons" style="font-size:13px;">sync</i>{{ _t('Pending sync') }}
                  </span>
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
              <!-- Client Name Banner -->
              <div v-if="selectedBookingDetail?.patient_name" class="client-name-banner">
                <i class="material-icons">person</i>
                <span>{{ selectedBookingDetail.patient_name }}</span>
                <span v-if="selectedBookingDetail?.patient_code || selectedBookingDetail?.patient?.patient_code" style="margin-left: auto; font-weight: 600; color: #333; font-size: 13px;">{{ selectedBookingDetail.patient_code || selectedBookingDetail.patient?.patient_code }}</span>
              </div>

              <!-- Modal scrollable content -->
              <div class="modal-body">
                <!-- Scheduled Visit Section -->
                <div class="detail-section">
                  <h4 class="section-title">{{ _t('Scheduled Visit') }}</h4>
                  <div class="detail-row">
                    <span class="label">{{ _t('Date & Time:') }}</span>
                    <span class="value">{{ formattedScheduledDateTime }}</span>
                  </div>
                  <div v-if="selectedBookingDetail.quote_items.length > 0" class="detail-row">
                    <span class="label">{{ _t('Services:') }}</span>
                    <span class="value">{{ selectedBookingDetail.quote_items.map(item => item.product_name).join(', ') }}</span>
                  </div>
                  <div v-if="selectedBookingDetail.package && selectedBookingDetail.package.name" class="detail-row">
                    <span class="label">{{ _t('Package:') }}</span>
                    <span class="value">{{ selectedBookingDetail.package.name }}</span>
                  </div>
                  <div v-if="selectedBookingDetail.category_of_service && selectedBookingDetail.category_of_service.name" class="detail-row">
                    <span class="label">{{ _t('Category of Service:') }}</span>
                    <span class="value">{{ selectedBookingDetail.category_of_service.name }}</span>
                  </div>
                </div>

                <!-- Contact Information Section -->
                <div class="detail-section">
                  <h4 class="section-title">{{ _t('Contact Information') }}</h4>
                  <div v-if="selectedBookingDetail.address" class="detail-row">
                    <span class="label">
                      <i class="material-icons icon-inline">location_on</i>
                      {{ _t('Address:') }}
                    </span>
                    <button @click="openMap(selectedBookingDetail.address, selectedBookingDetail.patient.name)" class="detail-link">
                      {{ selectedBookingDetail.address }}
                    </button>
                  </div>
                  <div v-if="selectedBookingDetail.primary_contact" class="detail-row">
                    <span class="label">{{ _t('Primary Contact:') }}</span>
                    <div class="contact-info">
                      <span class="contact-name">{{ selectedBookingDetail.primary_contact.name }}</span>
                      <button @click.stop="callPatient(selectedBookingDetail.primary_contact.phone)" class="btn-icon-action btn-icon-call-small" :title="_t('Call')">
                        <i class="material-icons">call</i>
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Intake Summary Button -->
                <button @click="toggleIntakeSummaryModal" class="btn-intake-summary">
                  <i class="material-icons">description</i>
                  <span>{{ _t('View Intake Summary') }}</span>
                  <i class="material-icons">chevron_right</i>
                </button>
              </div>

              <!-- Modal footer with action buttons -->
              <div class="modal-footer">
                <!-- Before service start (hidden when completed) -->
                <div v-if="serviceStartedForBooking !== selectedBookingId && selectedBookingDetail?.state !== 'in_progress' && selectedBookingDetail?.state !== 'completed'" class="modal-footer-content">
                  <button @click="cancelVisit" class="btn btn-ghost-danger">{{ _t('Cancel/Refuse Visit') }}</button>
                  <button @click="startService" class="btn btn-success">{{ _t('Start Service') }}</button>
                </div>

                <!-- After service start or when already in progress -->
                <div v-if="serviceStartedForBooking === selectedBookingId || selectedBookingDetail?.state === 'in_progress'" class="modal-footer-content">
                  <button @click="openClinicalNotesModal" class="btn btn-clinical-notes">
                    <i class="material-icons">description</i>
                    <span>{{ _t('Clinical Notes') }}</span>
                  </button>
                  <!-- View Quote Button (always visible, disabled when no quote or clinical notes incomplete) -->
                  <button @click="openInvoiceModal"
                          :disabled="!selectedBookingDetail?.confirmation_requirements?.has_quote_with_items || !isClinicalNotesComplete"
                          class="btn btn-invoice"
                          :title="!selectedBookingDetail?.confirmation_requirements?.has_quote_with_items
                            ? _t('No quote available')
                            : !isClinicalNotesComplete
                            ? _t('Please fill in the clinical notes or take image of the notes to view Quote')
                            : _t('View Quote')">
                    <i class="material-icons">receipt</i>
                    <span>{{ _t('View Quote') }}</span>
                  </button>
                  <!-- Complete Service Button (shown only when no quote) -->
                  <button v-if="!selectedBookingDetail?.confirmation_requirements?.has_quote_with_items"
                          @click="completeServiceWithoutQuoteInTodayView"
                          :disabled="!isClinicalNotesComplete"
                          class="btn btn-success btn-complete-service"
                          :title="!isClinicalNotesComplete ? _t('Please fill in the clinical notes or take image of the notes to Complete this service') : _t('Complete Service')">
                    <i class="material-icons">check_circle</i>
                    <span>{{ _t('Complete Service') }}</span>
                  </button>
                  <!-- One-tap quick complete (health_workflow_auto §2.5) — only
                       when window.healthOnetap reports the visit eligible (quote
                       unchanged vs booking snapshot). Guarded: an uninstalled
                       module leaves onetapEligible false, so nothing renders. -->
                  <button v-if="onetapEligible"
                          @click="runOneTap"
                          :disabled="onetapSubmitting"
                          class="btn btn-success btn-onetap-complete"
                          :title="_t('Complete this visit in one tap')">
                    <i class="material-icons">bolt</i>
                    <span>{{ onetapSubmitting ? _t('Completing...') : _t('Quick Complete') }}</span>
                  </button>
                </div>

                <!-- Sign an aging draft after the visit is delivered (emr phase
                     1.7 fix): the finalize path must stay reachable for
                     completed/closed visits — exactly where the "Notes to sign"
                     card's overdue drafts live. Only the notes button, only when
                     an unsigned draft remains (no completion actions here). -->
                <div v-if="hasUnsignedDraftToSign" class="modal-footer-content">
                  <button @click="openClinicalNotesModal" class="btn btn-clinical-notes">
                    <i class="material-icons">description</i>
                    <span>{{ _t('Clinical Notes') }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Cancellation Modal -->
        <div v-if="showCancellationModal" class="modal-backdrop" @click="showCancellationModal = false" style="background: white;">
          <div class="modal-container" @click.stop style="max-width: 420px;">
            <div class="modal-header" style="background: #E53935; color: white;">
              <h3 style="color: white;">
                <i class="material-icons">cancel</i>
                {{ _t('Cancel/Refuse Visit') }}
              </h3>
              <button @click="showCancellationModal = false" class="modal-close" style="color: white;">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div v-if="selectedBookingDetail?.patient_name" class="client-name-banner">
              <i class="material-icons">person</i>
              <span>{{ selectedBookingDetail.patient_name }}</span>
              <span v-if="selectedBookingDetail?.patient_code || selectedBookingDetail?.patient?.patient_code" style="margin-left: auto; font-weight: 600; color: #333; font-size: 13px;">{{ selectedBookingDetail.patient_code || selectedBookingDetail.patient?.patient_code }}</span>
            </div>
            <div class="modal-body">
              <div style="margin-bottom: 16px;">
                <label style="display: block; font-size: 14px; font-weight: 600; color: #333; margin-bottom: 8px;">
                  {{ _t('Cancellation Reason') }} <span style="color: #E53935;">*</span>
                </label>
                <select v-model="cancellationFormData.reason_id"
                  style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; background: white; appearance: auto;">
                  <option :value="null" disabled>{{ _t('Select a reason...') }}</option>
                  <optgroup v-if="cancellationReasons.filter(r => r.reason_type === 'patient').length" :label="_t('Patient-initiated')">
                    <option v-for="r in cancellationReasons.filter(r => r.reason_type === 'patient')" :key="r.id" :value="r.id">{{ _t(r.name) }}</option>
                  </optgroup>
                  <optgroup v-if="cancellationReasons.filter(r => r.reason_type === 'provider').length" :label="_t('Provider-initiated')">
                    <option v-for="r in cancellationReasons.filter(r => r.reason_type === 'provider')" :key="r.id" :value="r.id">{{ _t(r.name) }}</option>
                  </optgroup>
                  <optgroup v-if="cancellationReasons.filter(r => r.reason_type === 'system').length" :label="_t('System/Technical')">
                    <option v-for="r in cancellationReasons.filter(r => r.reason_type === 'system')" :key="r.id" :value="r.id">{{ _t(r.name) }}</option>
                  </optgroup>
                  <optgroup v-if="cancellationReasons.filter(r => r.reason_type === 'emergency').length" :label="_t('Emergency')">
                    <option v-for="r in cancellationReasons.filter(r => r.reason_type === 'emergency')" :key="r.id" :value="r.id">{{ _t(r.name) }}</option>
                  </optgroup>
                </select>
              </div>
              <div style="margin-bottom: 16px;">
                <label style="display: block; font-size: 14px; font-weight: 600; color: #333; margin-bottom: 8px;">
                  {{ _t('Cancellation Notes') }}
                </label>
                <textarea v-model="cancellationFormData.notes"
                  :placeholder="_t('Additional details about the cancellation...')"
                  style="width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; min-height: 80px; resize: vertical; box-sizing: border-box;"
                  rows="3"></textarea>
              </div>
              <div style="padding: 10px; background: #fff3e0; border-radius: 8px; border: 1px solid #ffe0b2; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: #e65100;">
                  <i class="material-icons" style="font-size: 18px;">warning</i>
                  <span>{{ _t('Cancellation details will be logged for record-keeping.') }}</span>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <div class="modal-footer-content">
                <button @click="showCancellationModal = false" class="btn btn-secondary">{{ _t('Go Back') }}</button>
                <button @click="submitCancellation" class="btn btn-danger" :disabled="!cancellationFormData.reason_id || cancellationSubmitting">
                  <span v-if="cancellationSubmitting">{{ _t('Cancelling...') }}</span>
                  <span v-else>{{ _t('Confirm Cancellation') }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Intake Summary Modal -->
        <div v-if="showIntakeSummaryModal && selectedBookingDetail" class="modal-backdrop" @click="toggleIntakeSummaryModal">
          <div class="intake-summary-modal" @click.stop>
            <!-- Modal scrollable content (header inside body so it scrolls) -->
            <div class="modal-body">
              <!-- Header row inside scrollable area -->
              <div class="intake-scroll-header">
                <button @click="toggleIntakeSummaryModal" class="btn-modal-back">
                  <i class="material-icons">chevron_left</i>
                </button>
                <h3 class="modal-title">{{ _t('Intake Notes') }}</h3>
                <div style="width: 40px;"></div>
              </div>
              <!-- Client Name Banner -->
              <div v-if="selectedBookingDetail?.patient_name" class="client-name-banner">
                <i class="material-icons">person</i>
                <span>{{ selectedBookingDetail.patient_name }}</span>
                <span v-if="selectedBookingDetail?.patient_code || selectedBookingDetail?.patient?.patient_code" style="margin-left: auto; font-weight: 600; color: #333; font-size: 13px;">{{ selectedBookingDetail.patient_code || selectedBookingDetail.patient?.patient_code }}</span>
              </div>
              <!-- Diagnosis -->
              <div class="intake-form-group">
                <label class="intake-form-label">{{ _t('Diagnosis') }}</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.diagnosis" :placeholder="_t('Type here...')" readonly></textarea>
              </div>

              <!-- Referring Doctor -->
              <div class="intake-form-group">
                <div class="intake-form-header">
                  <label class="intake-form-label">{{ _t('Referring Doctor') }}</label>
                  <button v-if="selectedBookingDetail.referring_doctor_name"
                    @click="callPatient(selectedBookingDetail.referring_doctor_phone || '')"
                    class="btn-icon-action btn-icon-call-small"
                    :title="_t('Call Referring Doctor')">
                    <i class="material-icons">call</i>
                  </button>
                </div>
                <p class="intake-form-value">{{ cleanDisplayValue(selectedBookingDetail.referring_doctor_name, _t('N/A')) }}</p>
              </div>

              <!-- Goal of Care -->
              <div class="intake-form-group">
                <label class="intake-form-label">{{ _t('Goal of Care') }}</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.goal_of_care" :placeholder="_t('Type here...')" readonly></textarea>
              </div>

              <!-- Required Equipment -->
              <div class="intake-form-group">
                <label class="intake-form-label">{{ _t('Required Equipment') }}</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.required_equipment" :placeholder="_t('Type here...')" readonly></textarea>
              </div>

              <!-- Intake Notes -->
              <div class="intake-form-group">
                <label class="intake-form-label">{{ _t('Intake Notes') }}</label>
                <textarea class="intake-form-field" v-model="selectedBookingDetail.intake_notes" :placeholder="_t('Type here...')" readonly></textarea>
              </div>
            </div>
          </div>
        </div>

        <!-- Clinical Notes Modal (3 panels: list / form / read-only detail) -->
        <div v-if="showClinicalNotesModal && selectedBookingDetail" class="modal-backdrop" @click="closeClinicalNotesModal">
          <div class="clinical-notes-modal" @click.stop>
            <div class="modal-header">
              <div style="display:flex;align-items:center;gap:8px;">
                <button v-if="showClinicalNoteForm || viewingClinicalNote" @click="backToNotesList" class="btn-modal-back" style="padding:4px;">
                  <i class="material-icons">arrow_back</i>
                </button>
                <h3 class="modal-title">{{ showClinicalNoteForm ? _t('New Clinical Note') : viewingClinicalNote ? _t('Clinical Note') : _t('Clinical Notes') }}</h3>
              </div>
              <button @click="closeClinicalNotesModal" class="btn-modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div v-if="selectedBookingDetail?.patient_name" class="client-name-banner">
              <i class="material-icons">person</i>
              <span>{{ selectedBookingDetail.patient_name }}</span>
              <span v-if="selectedBookingDetail?.patient_code || selectedBookingDetail?.patient?.patient_code" style="margin-left: auto; font-weight: 600; color: #333; font-size: 13px;">{{ selectedBookingDetail.patient_code || selectedBookingDetail.patient?.patient_code }}</span>
            </div>

            <!-- PANEL 1: Notes List (kanban cards) -->
            <div v-if="!showClinicalNoteForm && !viewingClinicalNote" class="modal-body" style="padding: 12px;">
              <div v-if="!selectedBookingDetail?.clinical_notes_list || selectedBookingDetail.clinical_notes_list.length === 0"
                   style="text-align:center; padding: 24px 12px; color: #999;">
                <i class="material-icons" style="font-size:48px; margin-bottom:8px;">note_add</i>
                <p>{{ _t('No clinical notes yet.') }}</p>
                <p style="font-size:13px;">{{ _t('Tap the button below to add the first clinical note.') }}</p>
              </div>
              <div v-else style="display:flex; flex-direction:column; gap:10px;">
                <div v-for="note in selectedBookingDetail.clinical_notes_list" :key="note.id"
                     @click="viewExistingNote(note)"
                     style="background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:12px; cursor:pointer; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <span style="display:flex; align-items:center; gap:6px;">
                      <strong style="font-size:14px;">{{ note.author }}</strong>
                      <span v-if="note.emr_state === 'final'" style="font-size:10px; font-weight:600; background:#e8f5e9; color:#2e7d32; padding:2px 6px; border-radius:10px;">{{ _t('Signed') }}</span>
                      <span v-else-if="note.emr_state === 'draft'" style="font-size:10px; font-weight:600; background:#fff3e0; color:#e65100; padding:2px 6px; border-radius:10px;">{{ _t('Draft') }}</span>
                    </span>
                    <small style="color:#999; font-size:11px;">{{ new Date(note.date).toLocaleString() }}</small>
                  </div>
                  <div style="font-size:12px; color:#1565C0; margin-bottom:4px;">{{ note.author_role }}</div>
                  <div v-if="note.clinical_notes" style="font-size:13px; color:#333; margin-bottom:4px; white-space:pre-line; max-height:60px; overflow:hidden; text-overflow:ellipsis;">{{ note.clinical_notes.replace(/<[^>]*>/g, '') }}</div>
                  <div v-if="note.diagnosis" style="font-size:12px; color:#666;"><strong>{{ _t('Diagnosis:') }}</strong> {{ note.diagnosis }}</div>
                  <div v-if="note.images && note.images.length > 0" style="display:flex; gap:4px; margin-top:6px;">
                    <div v-for="img in note.images.slice(0,3)" :key="img.id" style="width:40px;height:40px;border-radius:6px;overflow:hidden;border:1px solid #ddd;">
                      <img :src="img.url" style="width:100%;height:100%;object-fit:cover;" />
                    </div>
                    <div v-if="note.images.length > 3" style="width:40px;height:40px;border-radius:6px;background:#f0f0f0;display:flex;align-items:center;justify-content:center;font-size:11px;color:#666;">+{{ note.images.length - 3 }}</div>
                  </div>
                </div>
              </div>
              <div class="clinical-modal-footer">
                <button @click="openNewClinicalNoteForm" class="btn btn-success" style="width:100%;">
                  <i class="material-icons" style="vertical-align:middle;margin-right:4px;">add</i>
                  {{ _t('Add New Clinical Note') }}
                </button>
              </div>
            </div>

            <!-- PANEL 2: View Existing Note (read-only) -->
            <div v-if="viewingClinicalNote && !showClinicalNoteForm" class="modal-body" style="padding: 12px;">
              <div style="background:#f8f9fa; border-radius:8px; padding:12px; margin-bottom:12px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                  <strong>{{ viewingClinicalNote.author }}</strong>
                  <small style="color:#999;">{{ new Date(viewingClinicalNote.date).toLocaleString() }}</small>
                </div>
                <div style="font-size:12px; color:#1565C0;">{{ viewingClinicalNote.author_role }}</div>
              </div>

              <!-- EMR finalize (emr-record-spine phase 1.5): signed banner or sign action -->
              <div v-if="viewingClinicalNote.emr_state === 'final'" style="background:#e8f5e9; border:1px solid #a5d6a7; border-radius:8px; padding:10px 12px; margin-bottom:12px;">
                <div style="font-weight:600; color:#2e7d32; font-size:13px; display:flex; align-items:center; gap:4px;">
                  <i class="material-icons" style="font-size:16px;">lock</i>{{ _t('Signed medical record — locked') }}
                </div>
                <div v-if="viewingClinicalNote.signed_by" style="font-size:12px; color:#555; margin-top:2px;">
                  {{ _t('Signed by') }} {{ viewingClinicalNote.signed_by }}<span v-if="viewingClinicalNote.signed_datetime"> · {{ new Date(viewingClinicalNote.signed_datetime).toLocaleString() }}</span>
                </div>
              </div>
              <div v-else-if="viewingClinicalNote.emr_state === 'draft'" style="margin-bottom:12px;">
                <button @click="finalizeNote(viewingClinicalNote)" :disabled="finalizingNote" class="btn btn-primary" style="width:100%;">
                  <i class="material-icons" style="vertical-align:middle; margin-right:4px;">verified</i>
                  {{ finalizingNote ? _t('Signing…') : _t('Finalize & Sign') }}
                </button>
                <div style="font-size:11px; color:#999; text-align:center; margin-top:4px;">{{ _t('Requires an internet connection.') }}</div>
              </div>

              <div v-if="viewingClinicalNote.clinical_notes" class="clinical-form-group">
                <label class="clinical-form-label">{{ _t('Clinical Notes') }}</label>
                <div style="padding:8px 12px; background:#fff; border:1px solid #e0e0e0; border-radius:8px; white-space:pre-line; font-size:14px;" v-html="viewingClinicalNote.clinical_notes"></div>
              </div>
              <div v-if="viewingClinicalNote.diagnosis" class="clinical-form-group">
                <label class="clinical-form-label">{{ _t('Diagnosis') }}</label>
                <div style="padding:8px 12px; background:#fff; border:1px solid #e0e0e0; border-radius:8px; font-size:14px;">{{ viewingClinicalNote.diagnosis }}</div>
              </div>
              <div v-if="viewingClinicalNote.treatment_performed" class="clinical-form-group">
                <label class="clinical-form-label">{{ _t('Treatment Performed') }}</label>
                <div style="padding:8px 12px; background:#fff; border:1px solid #e0e0e0; border-radius:8px; font-size:14px;">{{ viewingClinicalNote.treatment_performed }}</div>
              </div>
              <div v-if="viewingClinicalNote.medications_prescribed" class="clinical-form-group">
                <label class="clinical-form-label">{{ _t('Medications Prescribed') }}</label>
                <div style="padding:8px 12px; background:#fff; border:1px solid #e0e0e0; border-radius:8px; font-size:14px;">{{ viewingClinicalNote.medications_prescribed }}</div>
              </div>
              <div v-if="viewingClinicalNote.vital_signs" class="clinical-form-group">
                <label class="clinical-form-label">{{ _t('Vital Signs') }}</label>
                <div style="padding:8px 12px; background:#fff; border:1px solid #e0e0e0; border-radius:8px; font-size:14px;">{{ viewingClinicalNote.vital_signs }}</div>
              </div>
              <div v-if="viewingClinicalNote.injection_count || viewingClinicalNote.medication_count || viewingClinicalNote.wound_count || viewingClinicalNote.iv_fluid_count"
                   style="background:#f8f9fa; border-radius:8px; padding:12px; margin-bottom:12px;">
                <label class="clinical-form-label" style="font-weight:600; margin-bottom:8px; display:block;">{{ _t('Service Procedures') }}</label>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; font-size:13px;">
                  <div v-if="viewingClinicalNote.injection_count"><strong>{{ _t('Injections:') }}</strong> {{ viewingClinicalNote.injection_count }}</div>
                  <div v-if="viewingClinicalNote.medication_count"><strong>{{ _t('Medications:') }}</strong> {{ viewingClinicalNote.medication_count }}</div>
                  <div v-if="viewingClinicalNote.wound_count"><strong>{{ _t('Wounds:') }}</strong> {{ viewingClinicalNote.wound_count }}</div>
                  <div v-if="viewingClinicalNote.iv_fluid_count"><strong>{{ _t('IV Bags:') }}</strong> {{ viewingClinicalNote.iv_fluid_count }}</div>
                </div>
              </div>
              <div v-if="viewingClinicalNote.images && viewingClinicalNote.images.length > 0" class="clinical-form-group">
                <label class="clinical-form-label">{{ _t('Images') }}</label>
                <div style="display:flex; flex-wrap:wrap; gap:8px;">
                  <div v-for="img in viewingClinicalNote.images" :key="img.id" style="border:1px solid #ddd; border-radius:8px; overflow:hidden; width:100px; height:100px;">
                    <img :src="img.url" :alt="img.filename" style="width:100%; height:100%; object-fit:cover;" />
                  </div>
                </div>
              </div>
            </div>

            <!-- PANEL 3: New Clinical Note Form -->
            <div v-if="showClinicalNoteForm" class="modal-body">
              <template v-if="currentUser.is_doctor">
                <div class="clinical-form-group">
                  <label class="clinical-form-label">{{ _t('Clinical Observations') }}</label>
                  <textarea v-model="clinicalObservations" class="clinical-form-field" :placeholder="_t('Enter clinical observations...')" rows="4"></textarea>
                </div>
                <div class="clinical-form-group">
                  <label class="clinical-form-label">{{ _t('Diagnosis') }}</label>
                  <textarea v-model="diagnosis" class="clinical-form-field" :placeholder="_t('Enter diagnosis...')" rows="3"></textarea>
                </div>
                <div class="clinical-form-group">
                  <label class="clinical-form-label">{{ _t('Treatment Performed') }}</label>
                  <textarea v-model="treatmentPerformed" class="clinical-form-field" :placeholder="_t('Describe treatment provided...')" rows="3"></textarea>
                </div>
              </template>
              <template v-else>
                <div class="clinical-form-group">
                  <label class="clinical-form-label">{{ _t('Notes') }}</label>
                  <textarea v-model="clinicalNotesText" class="clinical-form-field" :placeholder="_t('Enter clinical notes...')" rows="6"></textarea>
                </div>
              </template>

              <div class="clinical-form-group" style="background:#f8f9fa; border-radius:8px; padding:12px; margin-bottom:12px;">
                <label class="clinical-form-label" style="font-weight:600; margin-bottom:8px; display:block;">{{ _t('Service Procedures') }}</label>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                  <div>
                    <label style="font-size:12px; color:#666;">{{ _t('Injections') }}</label>
                    <input type="number" v-model.number="injectionCount" min="0" class="clinical-form-field" style="padding:6px 10px; text-align:center;" />
                  </div>
                  <div>
                    <label style="font-size:12px; color:#666;">{{ _t('Medications') }}</label>
                    <input type="number" v-model.number="medicationCount" min="0" class="clinical-form-field" style="padding:6px 10px; text-align:center;" />
                  </div>
                  <div>
                    <label style="font-size:12px; color:#666;">{{ _t('Wounds') }}</label>
                    <input type="number" v-model.number="woundCount" min="0" class="clinical-form-field" style="padding:6px 10px; text-align:center;" />
                  </div>
                  <div>
                    <label style="font-size:12px; color:#666;">{{ _t('IV Fluid Bags') }}</label>
                    <input type="number" v-model.number="ivFluidCount" min="0" class="clinical-form-field" style="padding:6px 10px; text-align:center;" />
                  </div>
                </div>
              </div>

              <div class="clinical-form-group">
                <label class="clinical-form-label">{{ _t('Attach Photo') }}</label>
                <div class="photo-upload-container">
                  <input type="file" ref="photoInput" @change="capturePhoto" accept="image/*" capture="environment" class="photo-input" />
                  <button @click="$refs.photoInput?.click()" class="btn-photo-capture">
                    <i class="material-icons">camera_alt</i>
                    <span>{{ _t('Take Photo') }}</span>
                  </button>
                </div>
                <div v-if="photoPreviewUrl" class="photo-preview">
                  <img :src="photoPreviewUrl" alt="Preview" />
                  <button @click="() => { capturedPhoto = null; photoPreviewUrl = null; }" class="btn-remove-photo">
                    <i class="material-icons">close</i>
                  </button>
                </div>
              </div>

              <div class="clinical-modal-footer">
                <button @click="backToNotesList" class="btn btn-secondary">{{ _t('Cancel') }}</button>
                <button @click="saveClinicalNotes" class="btn btn-success">{{ _t('Confirm and Save') }}</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Invoice Verification Modal -->
        <div v-if="showInvoiceModal && quoteData" class="modal-overlay" @click.self="showInvoiceModal = false">
          <div class="modal-content invoice-modal">
            <div class="modal-header">
              <h3>
                <i class="material-icons">receipt</i>
                {{ _t('View Quote') }} <span v-if="quoteData" style="font-weight: 400; font-size: 14px; color: #666; margin-left: 4px;">{{ quoteData.name }}</span>
              </h3>
              <button @click="showInvoiceModal = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <!-- Client Name Banner -->
            <div v-if="selectedBookingDetail?.patient_name" class="client-name-banner">
              <i class="material-icons">person</i>
              <span>{{ selectedBookingDetail.patient_name }}</span>
              <span v-if="selectedBookingDetail?.patient?.patient_code" style="margin-left: auto; font-weight: 600; color: #333; font-size: 13px;">{{ selectedBookingDetail.patient.patient_code }}</span>
            </div>
            <div class="modal-body" v-if="quoteData">
              <!-- Quote Information -->
              <div class="invoice-header">
                <div class="invoice-info">
                  <span :class="'badge badge-' + (quoteData.state === 'sale' ? 'success' : 'info')">
                    {{ quoteData.state }}
                  </span>
                </div>
              </div>

              <!-- Quote Items Table - Editable Qty and Discount -->
              <div class="invoice-lines">
                <!-- Message to Save Quote if modifications detected -->
                <div v-if="showSaveMessage" class="info-message-box">
                  {{ _t('Save Quote to display updated Total') }}
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
                          <label>{{ _t('Qty') }}</label>
                          <input
                            type="number"
                            v-model.number="line.quantity"
                            class="editable-input"
                            min="1"
                            step="0.01">
                        </div>
                        <div class="detail-cell disc-cell">
                          <label>{{ _t('Disc %') }}</label>
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
                          <label>{{ _t('Price') }}</label>
                          <span>{{ line.unit_price.toLocaleString() }}</span>
                        </div>
                        <div class="detail-cell total-cell">
                          <label>{{ _t('Total') }}</label>
                          <span>{{ (line.quantity * line.unit_price * (1 - (line.discount || 0) / 100)).toLocaleString() }}</span>
                        </div>
                      </div>

                      <!-- Row 3: Discount Reason (When Applicable) -->
                      <div v-if="line.discount > 0" class="invoice-item-row-reason">
                        <label class="discount-reason-label">{{ _t('Discount Reason:') }}</label>
                        <input
                          type="text"
                          v-model="line.discount_reason"
                          class="editable-input discount-reason-input-full"
                          :placeholder="_t('Required: Explain discount')"
                          required>
                      </div>
                    </div>
                  </template>
                </div>

                <!-- Totals Section -->
                <div class="invoice-totals">
                  <div class="totals-row">
                    <span>{{ _t('Subtotal') }}</span>
                    <span>{{ quoteData.amount_untaxed.toLocaleString() }}</span>
                  </div>
                  <div class="totals-row">
                    <span>{{ _t('Tax') }}</span>
                    <span>{{ quoteData.amount_tax.toLocaleString() }}</span>
                  </div>
                  <div class="totals-row totals-total">
                    <strong>{{ _t('Total') }}</strong>
                    <strong>{{ quoteData.amount_total.toLocaleString() }} {{ quoteData.currency }}</strong>
                  </div>
                </div>
              </div>

              <!-- Verification Notes - Mandatory if changes made -->
              <div v-if="!quoteVerified" class="form-group">
                <label class="clinical-form-label">
                  {{ _t('Verification Notes') }}
                  <span v-if="hasLineModifications" class="required-indicator">*</span>
                </label>
                <textarea
                  v-model="quoteComments"
                  class="clinical-form-field"
                  :placeholder="hasLineModifications ? _t('Required: Explain the changes made to Qty or Discount...') : _t('Add any general comments about this invoice...')"
                  rows="3"></textarea>
              </div>

              <!-- Success Message -->
              <div v-if="quoteVerified" class="success-message">
                <i class="material-icons">check_circle</i>
                <p>{{ _t('Invoice verified successfully!') }}</p>
              </div>
            </div>

            <!-- Modal Footer -->
            <div class="modal-footer">
              <button @click="showInvoiceModal = false" class="btn btn-secondary">{{ _t('Cancel') }}</button>
              <button v-if="!quoteVerified" @click="saveQuoteWithComments" class="btn btn-primary">
                <i class="material-icons">save</i>
                <span>{{ _t('Save Quote') }}</span>
              </button>
              <button v-else @click="openPaymentWizard" class="btn btn-success">
                <i class="material-icons">payment</i>
                <span>{{ _t('Payment') }}</span>
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
                    {{ _t('Complete Service - Payment Collection') }}
                  </h3>
                  <button @click="showPaymentWizard = false" class="modal-close">
                    <i class="material-icons">close</i>
                  </button>
                </div>
                <!-- Client Name Banner -->
                <div v-if="selectedBookingDetail?.patient_name" class="client-name-banner">
                  <i class="material-icons">person</i>
                  <span>{{ selectedBookingDetail.patient_name }}</span>
                  <span v-if="selectedBookingDetail?.patient_code || selectedBookingDetail?.patient?.patient_code" style="margin-left: auto; font-weight: 600; color: #333; font-size: 13px;">{{ selectedBookingDetail.patient_code || selectedBookingDetail.patient?.patient_code }}</span>
                </div>

              <div class="modal-body">
                <!-- Payment Choice Section -->
                <div class="form-section">
                <h4>{{ _t('Payment Timing') }}</h4>
                <div class="form-group">
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_choice"
                      value="pay_now">
                    <span>{{ _t('Pay Now') }}</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_choice"
                      value="pay_later">
                    <span>{{ _t('Pay Later') }}</span>
                  </label>
                </div>
              </div>

              <!-- Payment Method Section (only show if paying now) -->
              <div v-if="paymentWizardData.payment_choice === 'pay_now'" class="form-section">
                <h4>{{ _t('Payment Method') }}</h4>
                <div class="form-group">
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_method"
                      value="cash">
                    <span>{{ _t('Cash') }}</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_method"
                      value="card">
                    <span>{{ _t('Card') }}</span>
                  </label>
                  <label>
                    <input
                      type="radio"
                      v-model="paymentWizardData.payment_method"
                      value="bank_transfer">
                    <span>{{ _t('Bank Transfer') }}</span>
                  </label>
                </div>
              </div>

              <!-- Service Notes -->
              <div class="form-section">
                <h4>{{ _t('Service Notes') }}</h4>
                <div class="form-group">
                  <textarea
                    v-model="paymentWizardData.service_notes"
                    class="clinical-form-field"
                    :placeholder="_t('Enter any additional service or payment notes...')"
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
                    <span>{{ _t('Create Invoice Now') }}</span>
                  </label>
                </div>
              </div>

              <!-- Order Summary -->
              <div class="info-grid">
                <div class="info-item">
                  <label>{{ _t('Amount') }}</label>
                  <span>{{ quoteData?.amount_total?.toLocaleString() || '0' }} {{ quoteData?.currency || 'VND' }}</span>
                </div>
                <div class="info-item">
                  <label>{{ _t('Payment') }}</label>
                  <span>{{ paymentWizardData.payment_choice === 'pay_now' ? _t('Now') : _t('Later') }}</span>
                </div>
              </div>
            </div>

            <div class="modal-footer">
              <button @click="showPaymentWizard = false" class="btn btn-secondary">{{ _t('Cancel') }}</button>
              <button @click="completePayment" class="btn btn-success">
                <i class="material-icons">check_circle</i>
                <span>{{ _t('Complete Service') }}</span>
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
                <label>{{ _t('Patient Code') }}</label>
                <span>{{ _t(currentClientData.patient_code) }}</span>
              </div>
              <div class="detail-item">
                <label>{{ _t('Phone') }}</label>
                <span>{{ currentClientData.phone }}</span>
              </div>
              <div class="detail-item">
                <label>{{ _t('Age') }}</label>
                <span>{{ currentClientData.age || _t('N/A') }}</span>
              </div>
              <div class="detail-item">
                <label>{{ _t('Gender') }}</label>
                <span>{{ _t(currentClientData.gender) }}</span>
              </div>
            </div>

            <button @click="openNextBookingFromClientDetails" class="btn btn-primary btn-lg next-booking-btn">
              <i class="material-icons">add_event</i>
              {{ _t('Next Booking') }}
            </button>
          </div>
        </div>

        <!-- Next Visit Modal A: No future visit scheduled -->
        <div v-if="showNextVisitModalA" class="modal-overlay" @click.self="showNextVisitModalA = false">
          <div class="modal-content next-visit-modal">
            <div class="modal-header">
              <h3>
                <i class="material-icons">calendar_today</i>
                {{ _t('Schedule Next Appointment?') }}
              </h3>
              <button @click="showNextVisitModalA = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div class="modal-body">
              <p class="next-visit-message">
                {{ _t('No future visits are currently scheduled for') }} <strong>{{ nextVisitData.patient_name }}</strong>
              </p>

              <div class="next-visit-actions">
                <!-- Button 1: Schedule Next Visit -->
                <button @click="openNextVisitModal" class="btn btn-primary btn-lg">
                  <i class="material-icons">add_event</i>
                  {{ _t('Schedule Next Visit') }}
                </button>

                <!-- Button 2: Client does not need future visits -->
                <button @click="showNoFutureVisitDropdown = !showNoFutureVisitDropdown" class="btn btn-secondary btn-lg">
                  <i class="material-icons">block</i>
                  {{ _t('Client does not need or want a next visit') }}
                </button>
              </div>

              <!-- Dropdown for no future visit reasons -->
              <div v-if="showNoFutureVisitDropdown" class="no-future-visit-section">
                <label class="form-label">{{ _t('Why is there no future visit?') }}</label>
                <select v-model="nextVisitFormData.no_future_visit_reason" class="form-control">
                  <option value="">{{ _t('-- Select a reason --') }}</option>
                  <option v-for="reason in noFutureVisitReasons" :key="reason.value" :value="reason.value">
                    {{ _t(reason.label) }}
                  </option>
                </select>

                <!-- Text input for "Other" reason -->
                <div v-if="nextVisitFormData.no_future_visit_reason === 'other'" class="other-reason-section">
                  <label class="form-label">{{ _t('Please explain:') }}</label>
                  <textarea
                    v-model="nextVisitFormData.other_reason_text"
                    class="form-control"
                    :placeholder="_t('Explain why there is no future visit...')"
                    rows="3"></textarea>
                </div>

                <!-- Need to Follow up checkbox -->
                <div style="margin-top: 12px; padding: 12px; background: #f8f9fa; border-radius: 8px; border: 1px solid #e0e0e0;">
                  <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin: 0; font-size: 14px; font-weight: 500; color: #333;">
                    <input type="checkbox" v-model="nextVisitFormData.need_follow_up" style="width: 18px; height: 18px; accent-color: #1976d2; cursor: pointer;">
                    {{ _t('Need to Follow up') }}
                  </label>
                </div>

                <!-- Submit button for no future visit -->
                <div class="form-actions">
                  <button @click="showNoFutureVisitDropdown = false" class="btn btn-secondary">{{ _t('Cancel') }}</button>
                  <button @click="submitNoFutureVisit" class="btn btn-success">{{ _t('Submit') }}</button>
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
                  {{ _t('Next Appointment Details') }}
                </h3>
                <h3 v-else>
                  <i class="material-icons">event</i>
                  {{ _t('Schedule Next Appointment') }}
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
                  {{ _t('Check my schedule') }}
                </button>
              </div>

              <!-- Date and Time Section -->
              <div class="form-section">
                <h4>{{ _t('Appointment Date & Time') }}</h4>
                <div class="form-row date-time-row">
                  <div class="form-group date-time-group">
                    <div class="date-time-input">
                      <label class="date-time-label">{{ _t('Date') }}</label>
                      <input
                        type="date"
                        v-model="nextVisitFormData.scheduled_date"
                        class="form-control date-time-control">
                    </div>
                  </div>
                  <div class="form-group date-time-group">
                    <div class="date-time-input">
                      <label class="date-time-label">{{ _t('Time') }}</label>
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
                <h4>{{ _t('Services to be Provided') }}</h4>
                <div v-if="nextVisitFormData.quote_items && nextVisitFormData.quote_items.length > 0" class="services-list">
                  <div v-for="(item, index) in nextVisitFormData.quote_items" :key="index" class="service-item">
                    <span class="service-name">{{ item.product_name || item.name }}</span>
                    <span class="service-qty">{{ _t('Qty:') }} {{ item.quantity }}</span>
                    <button @click="nextVisitFormData.quote_items.splice(index, 1)" class="btn-remove">
                      <i class="material-icons">delete</i>
                    </button>
                  </div>
                </div>
                <div v-else class="no-services-message">
                  {{ _t('No services selected yet') }}
                </div>
                <button @click="openProductCatalogModal" class="btn btn-secondary btn-sm">
                  <i class="material-icons">add</i>
                  {{ _t('Add from Catalog') }}
                </button>
              </div>

              <!-- Assigned Healthcare Staff Section -->
              <div class="form-section">
                <h4>{{ _t('Assigned Healthcare Staff') }}</h4>
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
                      <div class="staff-info">
                        <strong>{{ nextVisitFormData.assigned_nurse_name || currentUser.name }}</strong>
                        <small class="booking-credit-display" v-if="currentUser.booking_credit > 0">
                          {{ _t('Booking credit:') }} {{ currentUser.booking_credit }}
                        </small>
                      </div>
                    </div>
                  </div>

                  <!-- Show unassigned message -->
                  <div v-else class="unassigned-staff-box">
                    <i class="material-icons">person_outline</i>
                    <strong>{{ _t('No staff assigned') }}</strong>
                    <small v-if="!nextVisitData.has_next_visit">{{ _t('Booking will be created in CONFIRMED state (unassigned)') }}</small>
                  </div>

                  <!-- Show clear assignment button only for new appointments -->
                  <div v-if="!nextVisitData.has_next_visit && nextVisitFormData.assigned_nurse_id" class="button-row">
                    <button @click="() => {
                      deleteNextVisitAssignment(nextVisitData.next_fso_id);
                      nextVisitFormData.assigned_nurse_id = null;
                    }" class="btn-clear-assignment">
                      <i class="material-icons">close</i>
                      {{ _t('Assign different nurse') }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- Order Summary -->
              <div class="order-summary">
                <div class="summary-item">
                  <label>{{ _t('Services') }}</label>
                  <span>{{ nextVisitFormData.quote_items?.length || 0 }} {{ _t('item(s)') }}</span>
                </div>
                <div class="summary-item">
                  <label>{{ _t('Scheduled For') }}</label>
                  <span v-if="nextVisitFormData.scheduled_date && nextVisitFormData.scheduled_time">
                    {{ nextVisitFormData.scheduled_date }} {{ _t('at') }} {{ nextVisitFormData.scheduled_time }}
                  </span>
                  <span v-else>{{ _t('Not set') }}</span>
                </div>
              </div>
            </div>

            <div class="modal-footer">
              <button @click="showNextVisitModalB = false" class="btn btn-secondary">{{ _t('Cancel') }}</button>
              <button @click="scheduleNextVisit" class="btn btn-success">
                <i class="material-icons">check_circle</i>
                {{ _t('Schedule Visit') }}
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
                {{ _t('Select Services from Catalog') }}
              </h3>
              <button @click="showProductCatalogModal = false" class="modal-close">
                <i class="material-icons">close</i>
              </button>
            </div>
            <div class="modal-body">
              <!-- Selected Products Summary - Show at Top -->
              <div v-if="nextVisitFormData.quote_items && nextVisitFormData.quote_items.length > 0" class="form-section selected-items-summary">
                <h4>{{ _t('Selected Services') }}</h4>
                <div class="selected-items-list">
                  <div v-for="(item, index) in nextVisitFormData.quote_items" :key="index" class="selected-item">
                    <div class="selected-item-info">
                      <span class="selected-item-name">{{ item.product_name }}</span>
                      <span class="selected-item-qty">{{ _t('Qty:') }} {{ item.quantity }}</span>
                    </div>
                    <button @click="nextVisitFormData.quote_items.splice(index, 1)" class="btn-remove-small">
                      <i class="material-icons">close</i>
                    </button>
                  </div>
                </div>
              </div>

              <!-- Search Section -->
              <div class="form-section search-section-compact">
                <label class="search-label-centered">{{ _t('Search Products') }}</label>
                <input
                  type="text"
                  v-model="catalogSearchQuery"
                  :placeholder="_t('Search by product name or code...')"
                  class="form-control search-control-clean"
                  @keyup="loadProductCatalog">
              </div>

              <!-- Loading State -->
              <div v-if="catalogLoading" class="loading-state">
                <p>{{ _t('Loading products...') }}</p>
              </div>

              <!-- Error State -->
              <div v-else-if="catalogError" class="error-state">
                <p style="color: #E53935;">{{ _t('Error:') }} {{ catalogError }}</p>
              </div>

              <!-- Products Grid -->
              <div v-else-if="catalogProducts.length > 0" class="products-grid">
                <div v-for="product in catalogProducts" :key="product.id" class="product-card">
                  <div class="product-info">
                    <h5 class="product-name">{{ product.name }}</h5>
                    <p class="product-code" v-if="product.code">{{ _t('Code:') }} {{ product.code }}</p>
                    <p class="product-price">
                      {{ product.price.toLocaleString() }} {{ product.currency }}
                    </p>
                    <p class="product-category" v-if="product.category">{{ product.category }}</p>
                  </div>
                  <button @click="addProductToQuote(product)" class="btn btn-primary btn-sm">
                    <i class="material-icons">add_shopping_cart</i>
                    {{ _t('Add') }}
                  </button>
                </div>
              </div>

              <!-- Empty State -->
              <div v-else class="empty-state">
                <p>{{ _t('No products found') }}</p>
              </div>
            </div>

            <div class="modal-footer">
              <button @click="showProductCatalogModal = false" class="btn btn-secondary">{{ _t('Close') }}</button>
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
              <h3 class="calendar-month-title">{{ calendarMonth.toLocaleDateString(getPWALocale(), { month: 'long', year: 'numeric' }) }}</h3>
              <button @click="changeCalendarMonth(1)" class="btn-month-nav">
                <i class="material-icons">chevron_right</i>
              </button>
            </div>

            <div class="calendar-weekdays">
              <div class="weekday">{{ _t('Sun') }}</div>
              <div class="weekday">{{ _t('Mon') }}</div>
              <div class="weekday">{{ _t('Tue') }}</div>
              <div class="weekday">{{ _t('Wed') }}</div>
              <div class="weekday">{{ _t('Thu') }}</div>
              <div class="weekday">{{ _t('Fri') }}</div>
              <div class="weekday">{{ _t('Sat') }}</div>
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

            <button @click="toggleCalendar" class="btn-close-calendar">{{ _t('Close') }}</button>
          </div>
        </div>

        <!-- Future Bookings Modal -->
        <div v-if="isFutureBookingsOpen" class="calendar-overlay" @click.self="toggleFutureBookings">
          <div class="calendar-modal future-bookings-modal">
            <div class="future-bookings-top-bar">
              <button @click="toggleFutureBookings" class="btn-close-modal">
                <span>{{ _t('Close') }}</span>
              </button>
            </div>

            <div class="future-bookings-header">
              <h3>{{ _t('Upcoming Bookings') }}</h3>
            </div>

            <div class="future-bookings-content">
              <div v-if="loadingFutureBookings" class="loading-spinner">
                <div class="spinner"></div>
                <p>{{ _t('Loading bookings...') }}</p>
              </div>

              <div v-else-if="Object.keys(futureBookingsByDate).length === 0" class="empty-state">
                <i class="material-icons">calendar_today</i>
                <p>{{ _t('No upcoming bookings scheduled') }}</p>
              </div>

              <div v-else class="grouped-bookings-list">
                <div v-for="(dateData, dateStr) in futureBookingsByDate" :key="dateStr" class="date-group">
                  <h4 class="date-group-title">{{ dateData.date_display }}</h4>
                  <div v-for="booking in dateData.bookings" :key="booking.id" class="booking-card-container">
                    <!-- Booking card -->
                    <div class="booking-card" :style="{ '--ac': statusAccent({state: booking.state}) }">
                      <!-- Header with time and status -->
                      <div class="booking-card-header">
                        <div class="booking-time-badge">
                          {{ booking.scheduled_time }}<small>{{ booking.scheduled_duration || 60 }} min</small>
                        </div>
                        <div class="status-badge" :style="statusChip({state: booking.state})">
                          {{ getStatusDisplay({state: booking.state}) }}
                        </div>
                      </div>

                      <!-- Patient info -->
                      <div class="booking-patient-section">
                        <div class="bk-avatar">{{ initials(booking.patient_name) }}</div>
                        <div class="bk-who">
                          <h3 class="booking-patient-name">{{ booking.patient_name }}</h3>
                          <span v-if="booking.patient_code" class="bk-code">{{ booking.patient_code }}</span>
                        </div>
                      </div>

                      <!-- Service type with action buttons inline -->
                      <div class="booking-service-row">
                    <p v-if="booking.service_type" class="booking-service-type">
                      {{ displayDbValue(booking.service_type) }}
                      <span v-if="booking.lead_staff_name" class="booking-lead-inline">
                        ({{ cleanDisplayValue(booking.lead_staff_name) }})
                      </span>
                    </p>
                        <div class="booking-action-icons">
                          <button @click.stop="callPatient(booking.phone)" class="btn-icon-action btn-icon-call" :title="_t('Call patient')">
                            <i class="material-icons">call</i>
                          </button>
                          <button v-if="booking.address" @click.stop="openMap({gps_coordinates: booking.address}, booking.patient_name)" class="btn-icon-action btn-icon-map" :title="_t('Open map')">
                            <i class="material-icons">map</i>
                          </button>
                        </div>
                      </div>

                      <!-- Lead nurse name -->
                      <div v-if="booking.lead_staff_name" class="booking-lead-nurse">
                        {{ cleanDisplayValue(booking.lead_staff_name) }}
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
          if (!dateStr) return _t('Never');
          const date = new Date(dateStr);
          const now = new Date();
          const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
          
          if (diffDays === 0) return _t('Today');
          if (diffDays === 1) return _t('Yesterday');
          if (diffDays < 7) return `${diffDays} ${_t('days ago')}`;
          return date.toLocaleDateString(getPWALocale());
        };
        
        const viewPatient = (patientId) => {
          emit('navigate', 'patient', { id: patientId });
        };

        const callPatient = (phone) => {
          if (phone) {
            window.location.href = `tel:${phone}`;
          } else {
            alert(_t('No phone number available'));
          }
        };

        const callZalo = (zaloId) => {
          if (zaloId) {
            window.location.href = `https://zalo.me/${zaloId}`;
          }
        };

        const openMap = (location, patientName) => {
          if (location) {
            const encodedLocation = encodeURIComponent(location);
            const mapsUrl = `https://www.google.com/maps/search/${encodedLocation}`;
            window.open(mapsUrl, '_blank');
          } else {
            alert(_t('Location not available'));
          }
        };

        return {
          patients,
          filteredPatients,
          searchQuery,
          isLoading,
          error,
          formatDate,
          viewPatient,
          callPatient,
          callZalo,
          openMap
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
              :placeholder="_t('Search patients...')"
              v-model="searchQuery">
          </div>
          
          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>{{ _t('Loading patients...') }}</p>
          </div>
          
          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <p>{{ _t('Failed to load patients') }}: {{ error }}</p>
          </div>
          
          <!-- Empty State -->
          <div v-else-if="filteredPatients.length === 0" class="empty-state">
            <div class="empty-icon">
              <i class="material-icons">people_outline</i>
            </div>
            <h3>{{ _t('No Patients Found') }}</h3>
            <p v-if="searchQuery">{{ _t('No patients match your search criteria.') }}</p>
            <p v-else>{{ _t('No patients have been synced yet.') }}</p>
          </div>
          
          <!-- Patients List -->
          <div v-else class="bookings-list">
            <div
              v-for="patient in filteredPatients"
              :key="patient.id"
              class="booking-card pt-card"
              @click="viewPatient(patient.id)">

              <!-- Avatar + name/code + quick actions -->
              <div class="pt-top">
                <div class="bk-avatar">{{ initials(patient.name) }}</div>
                <div class="bk-who">
                  <h3 class="booking-patient-name">{{ patient.name || _t('Unnamed Patient') }}</h3>
                  <span v-if="patient.patient_code" class="bk-code">{{ patient.patient_code }}</span>
                </div>
                <div class="booking-action-icons">
                  <button v-if="patient.phone" @click.stop="callPatient(patient.phone)" class="btn-icon-action btn-icon-call" :title="_t('Call patient')">
                    <i class="material-icons">call</i>
                  </button>
                  <button v-if="patient.zalo_user_id" @click.stop="callZalo(patient.zalo_user_id)" class="btn-icon-action btn-icon-zalo" :title="_t('Zalo call')">
                    <i class="material-icons">chat</i>
                  </button>
                  <button @click.stop="openMap(patient.street || patient.street2, patient.name)" class="btn-icon-action btn-icon-map" :title="_t('Open map')">
                    <i class="material-icons">map</i>
                  </button>
                </div>
              </div>

              <!-- Patient address -->
              <div class="pt-addr">
                <i class="material-icons">location_on</i>
                <span>{{ patient.street || patient.street2 || _t('No address provided') }}</span>
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
          if (!dateStr) return _t('Not specified');
          return new Date(dateStr).toLocaleDateString(getPWALocale());
        };
        
        const formatAge = (age) => {
          if (!age) return _t('Unknown');
          return `${age} ${_t('years old')}`;
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
            <p>{{ _t('Loading patient details...') }}</p>
          </div>
          
          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <h3>{{ _t('Error Loading Patient') }}</h3>
            <p>{{ error }}</p>
            <button @click="$emit('navigate', 'patients')" class="btn btn-primary">{{ _t('Back to Patients') }}</button>
          </div>
          
          <!-- Patient Details -->
          <div v-else-if="patient" class="patient-details">
            <!-- Patient Header -->
            <div class="patient-header-card">
              <div class="patient-avatar">{{ initials(patient.name) }}</div>
              <div class="patient-header-info">
                <h2>{{ patient.name || _t('Unnamed Patient') }}</h2>
                <p class="patient-code" v-if="patient.patient_code">ID: {{ patient.patient_code }}</p>
                <span :class="'badge badge-' + getStatusColor(patient.patient_status)">
                  {{ patient.patient_status || _t('Unknown Status') }}
                </span>
              </div>
            </div>
            
            <!-- Patient Information Sections -->
            <div class="patient-info-sections">
              
              <!-- Basic Information -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">person</i>
                  {{ _t('Basic Information') }}
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.first_name || patient.last_name">
                    <label>{{ _t('Full Name') }}</label>
                    <span>{{ [patient.first_name, patient.last_name].filter(Boolean).join(' ') || _t('Not specified') }}</span>
                  </div>
                  <div class="info-item" v-if="patient.birth_date">
                    <label>{{ _t('Date of Birth') }}</label>
                    <span>{{ formatDate(patient.birth_date) }}</span>
                  </div>
                  <div class="info-item" v-if="patient.age">
                    <label>{{ _t('Age') }}</label>
                    <span>{{ formatAge(patient.age) }}</span>
                  </div>
                  <div class="info-item" v-if="patient.gender">
                    <label>{{ _t('Gender') }}</label>
                    <span>{{ patient.gender }}</span>
                  </div>
                  <div class="info-item" v-if="patient.blood_group && patient.blood_group !== 'unknown'">
                    <label>{{ _t('Blood Group') }}</label>
                    <span>{{ patient.blood_group.toUpperCase() }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Contact Information -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">contact_phone</i>
                  {{ _t('Contact Information') }}
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.phone">
                    <label>{{ _t('Phone') }}</label>
                    <span>{{ patient.phone }}</span>
                  </div>
                  <div class="info-item" v-if="patient.mobile">
                    <label>{{ _t('Mobile') }}</label>
                    <span>{{ patient.mobile }}</span>
                  </div>
                  <div class="info-item" v-if="patient.email">
                    <label>{{ _t('Email') }}</label>
                    <span>{{ patient.email }}</span>
                  </div>
                  <div class="info-item" v-if="patient.street || patient.city">
                    <label>{{ _t('Address') }}</label>
                    <span>{{ [patient.street, patient.city].filter(Boolean).join(', ') || _t('Not specified') }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Emergency Contact -->
              <div class="info-section" v-if="patient.emergency_contact_name || patient.emergency_contact_phone">
                <h3>
                  <i class="material-icons">emergency</i>
                  {{ _t('Emergency Contact') }}
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.emergency_contact_name">
                    <label>{{ _t('Name') }}</label>
                    <span>{{ patient.emergency_contact_name }}</span>
                  </div>
                  <div class="info-item" v-if="patient.emergency_contact_phone">
                    <label>{{ _t('Phone') }}</label>
                    <span>{{ patient.emergency_contact_phone }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Medical Information -->
              <div class="info-section" v-if="patient.allergies || patient.medical_history">
                <h3>
                  <i class="material-icons">medical_services</i>
                  {{ _t('Medical Information') }}
                </h3>
                <div class="info-grid">
                  <div class="info-item full-width" v-if="patient.allergies">
                    <label>{{ _t('Known Allergies') }}</label>
                    <span>{{ patient.allergies }}</span>
                  </div>
                  <div class="info-item full-width" v-if="patient.medical_history">
                    <label>{{ _t('Medical History') }}</label>
                    <span>{{ patient.medical_history }}</span>
                  </div>
                </div>
              </div>
              
              <!-- Recent Orders -->
              <div class="info-section" v-if="patient.recent_orders && patient.recent_orders.length > 0">
                <h3>
                  <i class="material-icons">assignment</i>
                  {{ _t('Recent Orders') }}
                </h3>
                <div class="orders-list">
                  <div 
                    v-for="order in patient.recent_orders" 
                    :key="order.id"
                    class="order-item"
                    @click="$emit('navigate', 'order', {id: order.id})">
                    <div class="order-content">
                      <h4>{{ displayDbValue(order.service_type_name || _t('Service Order')) }}</h4>
                      <p>{{ formatDate(order.scheduled_datetime) }}</p>
                    </div>
                    <div class="order-status">
                      <span :class="'badge badge-' + getStatusColor(order.state)">{{ displayDbValue(order.state) }}</span>
                      <i class="material-icons">chevron_right</i>
                    </div>
                  </div>
                </div>
              </div>
              
              <!-- Visit History -->
              <div class="info-section">
                <h3>
                  <i class="material-icons">history</i>
                  {{ _t('Visit History') }}
                </h3>
                <div class="info-grid">
                  <div class="info-item" v-if="patient.last_visit_date">
                    <label>{{ _t('Last Visit') }}</label>
                    <span>{{ formatDate(patient.last_visit_date) }}</span>
                  </div>
                  <div class="info-item" v-if="patient.next_visit_date">
                    <label>{{ _t('Next Visit') }}</label>
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
            <h3>{{ _t('Patient Not Found') }}</h3>
            <p>{{ _t('The requested patient could not be found.') }}</p>
            <button @click="$emit('navigate', 'patients')" class="btn btn-primary">{{ _t('Back to Patients') }}</button>
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
          if (!dateTimeStr) return _t('Unscheduled');
          const date = new Date(dateTimeStr);
          return date.toLocaleDateString(getPWALocale()) + ' ' + date.toLocaleTimeString(getPWALocale(), { hour: '2-digit', minute: '2-digit' });
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
        
        const getStatusLabel = (state) => getBookingStatusLabel(state);
        
        const viewOrder = (orderId) => {
          emit('navigate', 'order', { id: orderId });
        };
        
        return {
          orders,
          upcomingOrders,
          isLoading,
          error,
          formatDateTime,
          displayDbValue,
          getStatusBadgeClass,
          getStatusLabel,
          viewOrder
        };
      },
      template: `
        <div class="orders-view">
          <!-- View Toggle Header -->
          <div class="view-toggle-header">
            <h3>{{ _t('Upcoming Bookings') }}</h3>
            <button @click="$emit('navigate', 'past-bookings')" class="btn-past-bookings">
              <i class="material-icons">history</i>
              {{ _t('Past') }}
            </button>
          </div>

          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>{{ _t('Loading field service orders...') }}</p>
          </div>
          
          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <p>{{ _t('Failed to load orders:') }} {{ error }}</p>
          </div>
          
          <!-- Empty State -->
          <div v-else-if="upcomingOrders.length === 0" class="empty-state">
            <div class="empty-icon">
              <i class="material-icons">assignment_outlined</i>
            </div>
            <h3>{{ _t('No Upcoming Orders') }}</h3>
            <p v-if="orders.length === 0">{{ _t('No field service orders have been synced yet.') }}</p>
            <p v-else>{{ _t('No upcoming bookings found. All orders are in the past.') }}</p>
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
                  {{ displayDbValue(order.service_type_name || _t('Service Order')) }} - {{ order.patient_name || _t('Unknown Patient') }} <span v-if="order.patient_code" style="font-weight: 400; font-size: 12px; color: #666;">{{ order.patient_code }}</span>
                </h4>
                <p class="list-item-subtitle">
                  {{ _t('Scheduled:') }} {{ formatDateTime(order.scheduled_datetime) }}
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
          if (!dateTimeStr) return _t('Unscheduled');
          const date = new Date(dateTimeStr);
          return date.toLocaleDateString(getPWALocale()) + ' ' + date.toLocaleTimeString(getPWALocale(), { hour: '2-digit', minute: '2-digit' });
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

        const getStatusLabel = (state) => getBookingStatusLabel(state);

        const viewOrder = (orderId) => {
          emit('navigate', 'order', { id: orderId });
        };

        return {
          orders,
          pastOrders,
          isLoading,
          error,
          formatDateTime,
          displayDbValue,
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
              <h3 style="margin: 0; color: #333; font-weight: 600;">{{ _t('Past Bookings') }}</h3>
              <button @click="$emit('navigate', 'orders')" class="btn btn-secondary btn-sm" style="background: #E53935; color: white; border: none; padding: 0.5rem 1rem; border-radius: 8px;">
                {{ _t('View Upcoming') }}
              </button>
            </div>
          </div>

          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <div class="loading-spinner">
              <div class="spinner"></div>
            </div>
            <p>{{ _t('Loading past bookings...') }}</p>
          </div>

          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <div class="error-icon">
              <i class="material-icons">error</i>
            </div>
            <p>{{ _t('Failed to load past bookings:') }} {{ error }}</p>
          </div>

          <!-- Empty State -->
          <div v-else-if="pastOrders.length === 0" class="empty-state">
            <div class="empty-icon">
              <i class="material-icons">history</i>
            </div>
            <h3>{{ _t('No Past Bookings') }}</h3>
            <p v-if="orders.length === 0">{{ _t('No field service orders have been synced yet.') }}</p>
            <p v-else>{{ _t('No past bookings found. All orders are upcoming.') }}</p>
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
                  {{ displayDbValue(order.service_type_name || _t('Service Order')) }} - {{ order.patient_name || _t('Unknown Patient') }} <span v-if="order.patient_code" style="font-weight: 400; font-size: 12px; color: #666;">{{ order.patient_code }}</span>
                </h4>
                <p class="list-item-subtitle">
                  {{ _t('Scheduled:') }} {{ formatDateTime(order.scheduled_datetime) }}
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


    app.component('teams-view', {
      props: ['isOnline'],
      emits: ['navigate'],
      template: `
        <div class="teams-view">
          <h2>{{ _t('Teams') }}</h2>
          <p>{{ _t('Team management interface will be implemented here.') }}</p>
        </div>
      `
    });
    
    app.component('profile-view', {
      props: ['user', 'isOnline'],
      emits: ['sync'],
      template: `
        <div class="profile-view">
          <div class="profile-header">
            <div class="profile-avatar">{{ initials(user?.name) }}</div>
            <h2>{{ user?.name || _t('User') }}</h2>
            <p>{{ user?.email || _t('No email') }}</p>
          </div>
          <div class="profile-actions">
            <button @click="$emit('sync')" class="btn btn-primary" :disabled="!isOnline">
              <i class="material-icons">sync</i>
              {{ _t('Sync Data') }}
            </button>
          </div>
          <p class="profile-version">Viet Uc · v{{ pwaVersion }}</p>
          <div class="profile-actions">
            <button @click="logout" class="btn btn-danger" :disabled="loggingOut">
              <i class="material-icons">logout</i>
              {{ loggingOut ? _t('Logging out…') : _t('Log Out') }}
            </button>
          </div>
        </div>
      `,
      data() {
        return { loggingOut: false };
      },
      methods: {
        async logout() {
          if (this.loggingOut) return;
          if (!window.confirm(this._t(
            'Log out of Viet Uc? Sync your data first — any unsynced changes will be lost, and offline data on this device will be cleared.'
          ))) {
            return;
          }
          this.loggingOut = true;
          // Wipe locally-cached PII (PouchDB stores + in-memory cache) so a lost
          // or shared device retains no patient/booking data after logout.
          try {
            const sm = window.healthPWA && window.healthPWA.storageManager;
            if (sm && sm.clearAllData) {
              await sm.clearAllData();
            }
          } catch (e) {
            console.warn('logout: clearAllData failed', e);
          }
          // Drop service-worker caches (cached API responses / assets).
          try {
            if (window.caches) {
              const keys = await caches.keys();
              await Promise.all(keys.map((k) => caches.delete(k)));
            }
          } catch (e) {
            console.warn('logout: cache clear failed', e);
          }
          try { localStorage.clear(); } catch (e) { /* ignore */ }
          // End the Odoo session, then return to the PWA (which bounces to login).
          window.location.href =
            '/web/session/logout?redirect=' + encodeURIComponent('/health_pwa');
        }
      }
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
            alert(_t('Clinic phone number not available'));
          }
        };

        const copyPhone = () => {
          if (clinicPhone.value && clinicPhone.value !== 'N/A') {
            navigator.clipboard.writeText(clinicPhone.value);
            alert(_t('Phone number copied to clipboard!'));
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
              {{ _t('Contact Clinic') }}
            </h2>
          </div>

          <div v-if="isLoading" class="loading-spinner">
            <div class="spinner"></div>
            <p>{{ _t('Loading clinic information...') }}</p>
          </div>

          <div v-else-if="error" class="error-message">
            <i class="material-icons">error</i>
            <p>{{ error }}</p>
            <button @click="loadClinicConfig" class="btn btn-secondary">{{ _t('Retry') }}</button>
          </div>

          <div v-else class="call-container">
            <div class="clinic-card">
              <div class="clinic-info">
                <h3 class="clinic-name">{{ clinicName }}</h3>
                <p class="clinic-phone-label">{{ _t('Phone Number') }}</p>
                <p class="clinic-phone">{{ clinicPhone }}</p>
              </div>

              <div class="call-actions">
                <button @click="initiateCall" class="btn btn-call-primary">
                  <i class="material-icons">call</i>
                  <span>{{ _t('Call Now') }}</span>
                </button>
                <button @click="copyPhone" class="btn btn-copy">
                  <i class="material-icons">content_copy</i>
                  <span>{{ _t('Copy Number') }}</span>
                </button>
              </div>

              <div class="call-info-box">
                <i class="material-icons">info</i>
                <p>{{ _t('Tap "Call Now" to initiate a call to the clinic directly from your phone.') }}</p>
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
