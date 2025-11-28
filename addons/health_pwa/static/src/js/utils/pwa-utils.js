// Health PWA - Utility Functions for PWA Features

window.PWAUtils = {

  // Localization - Vietnamese and English translations
  i18n: {
    vi: {
      // UI Labels
      'Day': 'Ngày',
      'Week': 'Tuần',
      'Month': 'Tháng',
      'Today': 'Hôm nay',
      'Select date': 'Chọn ngày',
      'Loading bookings...': 'Đang tải lịch hẹn...',
      'Loading details...': 'Đang tải chi tiết...',
      'Close': 'Đóng',
      'Booking Details': 'Chi tiết đặt lịch',
      'Scheduled Visit': 'Lịch thăm khám',
      'Date & Time:': 'Ngày & Giờ:',
      'Services:': 'Dịch vụ:',
      'Package:': 'Gói:',
      'Contact Information': 'Thông tin liên hệ',
      'Address:': 'Địa chỉ:',
      'Primary Contact:': 'Liên hệ chính:',
      'Call': 'Gọi',
      'View Intake Summary': 'Xem tóm tắt tiếp nhận',
      'Cancel/Refuse Visit': 'Hủy/Từ chối lượt thăm',
      'Start Service': 'Bắt đầu dịch vụ',
      'Clinical Notes': 'Ghi chú lâm sàng',
      'Diagnosis': 'Chẩn đoán',
      'Type here...': 'Nhập tại đây...',
      'Referring Doctor': 'Bác sĩ giới thiệu',
      'Goal of Care': 'Mục tiêu chăm sóc',
      'Required Equipment': 'Thiết bị yêu cầu',
      'Intake Notes': 'Ghi chú tiếp nhận',
      'Verification Notes': 'Ghi chú xác minh',
      'Required: Explain the changes made to Qty or Discount...': 'Bắt buộc: Giải thích các thay đổi về Số lượng hoặc Chiết khấu...',
      'Add any general comments about this invoice...': 'Thêm bất kỳ ghi chú chung nào về hóa đơn này...',
      'Invoice verified successfully!': 'Xác minh hóa đơn thành công!',
      'Cancel': 'Hủy',
      'Save Quote': 'Lưu báo giá',
      'Payment': 'Thanh toán',
      'Complete Service - Payment Collection': 'Hoàn tất dịch vụ - Thu tiền',
      'Payment Timing': 'Thời điểm thanh toán',
      'Pay Now': 'Trả ngay',
      'Pay Later': 'Trả sau',
      'Payment Method': 'Phương thức thanh toán',
      'Cash': 'Tiền mặt',
      'Card': 'Thẻ',
      'Bank Transfer': 'Chuyển khoản',
      'Service Notes': 'Ghi chú dịch vụ',
      'Enter any additional service or payment notes...': 'Nhập thêm ghi chú dịch vụ hoặc thanh toán...',
      'Create Invoice Now': 'Tạo hóa đơn ngay',
      'Amount': 'Số tiền',
      'Now': 'Ngay',
      'Complete Payment': 'Hoàn tất thanh toán',
      'Not set': 'Chưa thiết lập',
      'Draft': 'Nháp',
      'Confirmed': 'Đã xác nhận',
      'Assigned': 'Đã phân công',
      'In Progress': 'Đang thực hiện',
      'Completed': 'Đã hoàn thành',
      'Cancelled': 'Đã hủy',
      'Unknown': 'Không xác định',

      // Camera messages
      'camera.not_supported': 'Camera không được hỗ trợ trên thiết bị này',
      'camera.permission_denied': 'Quyền truy cập camera bị từ chối',
      'camera.access_failed': 'Không thể truy cập camera',
      'camera.no_file_selected': 'Chưa chọn tệp',

      // Location messages
      'location.not_supported': 'Định vị không được hỗ trợ',
      'location.permission_denied': 'Quyền truy cập vị trí bị từ chối',
      'location.unavailable': 'Vị trí không khả dụng',
      'location.timeout': 'Yêu cầu vị trí hết thời gian',
      'location.failed': 'Không thể lấy vị trí',
      'location.watch_failed': 'Không thể theo dõi vị trí',

      // Notification messages
      'notification.not_supported': 'Thông báo đẩy không được hỗ trợ',
      'notification.permission_not_granted': 'Quyền thông báo chưa được cấp',
      'notification.new_booking': 'Lịch hẹn mới',
      'notification.booking_reminder': 'Nhắc nhở lịch hẹn',
      'notification.booking_cancelled': 'Lịch hẹn đã hủy',
      'notification.status_update': 'Cập nhật trạng thái',
      'notification.view': 'Xem',

      // Installation messages
      'install.cannot_install': 'Không thể cài đặt ứng dụng lúc này',
      'install.use_safari': 'Vui lòng sử dụng Safari để cài đặt trên iOS',
      'install.use_chrome': 'Vui lòng sử dụng Chrome để cài đặt trên Android',
      'install.ios_step1': 'Nhấn nút Chia sẻ',
      'install.ios_step2': 'Chọn "Thêm vào Màn hình chính"',
      'install.ios_step3': 'Nhấn "Thêm"',
      'install.android_step1': 'Nhấn nút menu',
      'install.android_step2': 'Chọn "Thêm vào Màn hình chính"',
      'install.android_step3': 'Nhấn "Cài đặt"',
      'install.desktop_step1': 'Tìm biểu tượng cài đặt',
      'install.desktop_step2': 'Nhấn cài đặt',
      'install.desktop_step3': 'Khởi chạy ứng dụng',

      // Network messages
      'network.offline': 'Bạn đang ngoại tuyến',
      'network.online': 'Đã kết nối lại',
      'network.slow_connection': 'Kết nối chậm được phát hiện',

      // Storage messages
      'storage.quota_exceeded': 'Dung lượng lưu trữ đã đầy',
      'storage.low_space': 'Dung lượng lưu trữ sắp hết'
    },
    en: {
      // UI Labels
      'Day': 'Day',
      'Week': 'Week',
      'Month': 'Month',
      'Today': 'Today',
      'Select date': 'Select date',
      'Loading bookings...': 'Loading bookings...',
      'Loading details...': 'Loading details...',
      'Close': 'Close',
      'Booking Details': 'Booking Details',
      'Scheduled Visit': 'Scheduled Visit',
      'Date & Time:': 'Date & Time:',
      'Services:': 'Services:',
      'Package:': 'Package:',
      'Contact Information': 'Contact Information',
      'Address:': 'Address:',
      'Primary Contact:': 'Primary Contact:',
      'Call': 'Call',
      'View Intake Summary': 'View Intake Summary',
      'Cancel/Refuse Visit': 'Cancel/Refuse Visit',
      'Start Service': 'Start Service',
      'Clinical Notes': 'Clinical Notes',
      'Diagnosis': 'Diagnosis',
      'Type here...': 'Type here...',
      'Referring Doctor': 'Referring Doctor',
      'Goal of Care': 'Goal of Care',
      'Required Equipment': 'Required Equipment',
      'Intake Notes': 'Intake Notes',
      'Verification Notes': 'Verification Notes',
      'Required: Explain the changes made to Qty or Discount...': 'Required: Explain the changes made to Qty or Discount...',
      'Add any general comments about this invoice...': 'Add any general comments about this invoice...',
      'Invoice verified successfully!': 'Invoice verified successfully!',
      'Cancel': 'Cancel',
      'Save Quote': 'Save Quote',
      'Payment': 'Payment',
      'Complete Service - Payment Collection': 'Complete Service - Payment Collection',
      'Payment Timing': 'Payment Timing',
      'Pay Now': 'Pay Now',
      'Pay Later': 'Pay Later',
      'Payment Method': 'Payment Method',
      'Cash': 'Cash',
      'Card': 'Card',
      'Bank Transfer': 'Bank Transfer',
      'Service Notes': 'Service Notes',
      'Enter any additional service or payment notes...': 'Enter any additional service or payment notes...',
      'Create Invoice Now': 'Create Invoice Now',
      'Amount': 'Amount',
      'Now': 'Now',
      'Complete Payment': 'Complete Payment',
      'Not set': 'Not set',
      'Draft': 'Draft',
      'Confirmed': 'Confirmed',
      'Assigned': 'Assigned',
      'In Progress': 'In Progress',
      'Completed': 'Completed',
      'Cancelled': 'Cancelled',
      'Unknown': 'Unknown',

      // Camera messages
      'camera.not_supported': 'Camera not supported on this device',
      'camera.permission_denied': 'Camera permission denied',
      'camera.access_failed': 'Failed to access camera',
      'camera.no_file_selected': 'No file selected',

      // Location messages
      'location.not_supported': 'Geolocation not supported',
      'location.permission_denied': 'Location permission denied',
      'location.unavailable': 'Location unavailable',
      'location.timeout': 'Location request timeout',
      'location.failed': 'Failed to get location',
      'location.watch_failed': 'Failed to watch location',

      // Notification messages
      'notification.not_supported': 'Push notifications not supported',
      'notification.permission_not_granted': 'Notification permission not granted',
      'notification.new_booking': 'New Booking',
      'notification.booking_reminder': 'Booking Reminder',
      'notification.booking_cancelled': 'Booking Cancelled',
      'notification.status_update': 'Status Update',
      'notification.view': 'View',

      // Installation messages
      'install.cannot_install': 'App cannot be installed at this time',
      'install.use_safari': 'Please use Safari to install on iOS',
      'install.use_chrome': 'Please use Chrome to install on Android',
      'install.ios_step1': 'Tap the Share button',
      'install.ios_step2': 'Select "Add to Home Screen"',
      'install.ios_step3': 'Tap "Add"',
      'install.android_step1': 'Tap the menu button',
      'install.android_step2': 'Select "Add to Home screen"',
      'install.android_step3': 'Tap "Install"',
      'install.desktop_step1': 'Look for the install icon',
      'install.desktop_step2': 'Click install',
      'install.desktop_step3': 'Launch the app',

      // Network messages
      'network.offline': 'You are offline',
      'network.online': 'Back online',
      'network.slow_connection': 'Slow connection detected',

      // Storage messages
      'storage.quota_exceeded': 'Storage quota exceeded',
      'storage.low_space': 'Low storage space'
    },

    t: function(key) {
      const lang = window.healthPWAConfig?.user_lang?.startsWith('vi') ? 'vi' : 'en';
      return this[lang][key] || this.en[key] || key;
    }
  },

  // Device and platform detection
  device: {
    isIOS: function() {
      return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    },

    isAndroid: function() {
      return /Android/.test(navigator.userAgent);
    },

    isMobile: function() {
      return this.isIOS() || this.isAndroid() || /Mobi|Android/i.test(navigator.userAgent);
    },

    isStandalone: function() {
      return window.matchMedia('(display-mode: standalone)').matches ||
             window.navigator.standalone === true ||
             document.referrer.includes('android-app://');
    },

    getDeviceType: function() {
      if (this.isIOS()) return 'ios';
      if (this.isAndroid()) return 'android';
      return 'desktop';
    },

    // Get iOS version
    getIOSVersion: function() {
      if (!this.isIOS()) return null;

      const match = navigator.userAgent.match(/OS (\d+)_(\d+)_?(\d+)?/);
      if (match) {
        return {
          major: parseInt(match[1], 10),
          minor: parseInt(match[2], 10),
          patch: parseInt(match[3] || 0, 10),
          version: `${match[1]}.${match[2]}${match[3] ? '.' + match[3] : ''}`
        };
      }
      return null;
    },

    // Check if iOS version supports PWA features
    supportsPWA: function() {
      if (this.isIOS()) {
        const version = this.getIOSVersion();
        // PWA support started in iOS 11.3
        if (version) {
          return version.major > 11 || (version.major === 11 && version.minor >= 3);
        }
        return false;
      }
      return true; // Android and desktop generally support PWAs
    },

    // Get browser name
    getBrowser: function() {
      const ua = navigator.userAgent;

      if (ua.includes('Safari') && !ua.includes('Chrome') && !ua.includes('CriOS')) {
        return 'safari';
      }
      if (ua.includes('Chrome') || ua.includes('CriOS')) {
        return 'chrome';
      }
      if (ua.includes('Firefox') || ua.includes('FxiOS')) {
        return 'firefox';
      }
      if (ua.includes('Edge')) {
        return 'edge';
      }
      return 'unknown';
    },

    // Check if using correct browser for PWA installation
    isCorrectBrowser: function() {
      const browser = this.getBrowser();

      if (this.isIOS()) {
        return browser === 'safari';
      }
      if (this.isAndroid()) {
        return browser === 'chrome';
      }
      return true; // Desktop - most browsers support PWA
    },

    supportsCamera: function() {
      return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    },

    supportsGeolocation: function() {
      return !!navigator.geolocation;
    },

    supportsPushNotifications: function() {
      return 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
    }
  },
  
  // Camera utilities
  camera: {
    async requestPermission() {
      if (!PWAUtils.device.supportsCamera()) {
        throw new Error(PWAUtils.i18n.t('camera.not_supported'));
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'environment', // Use back camera
            width: { ideal: 1280 },
            height: { ideal: 720 }
          }
        });

        // Stop the stream immediately as we just wanted to check permission
        stream.getTracks().forEach(track => track.stop());
        return true;

      } catch (error) {
        console.error('Camera permission denied:', error);
        throw new Error(PWAUtils.i18n.t('camera.permission_denied'));
      }
    },
    
    async capturePhoto(options = {}) {
      const {
        facingMode = 'environment',
        width = 1280,
        height = 720,
        quality = 0.8
      } = options;
      
      return new Promise(async (resolve, reject) => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: facingMode,
              width: { ideal: width },
              height: { ideal: height }
            }
          });
          
          // Create video element to display camera feed
          const video = document.createElement('video');
          video.srcObject = stream;
          video.autoplay = true;
          video.playsInline = true; // Important for iOS
          
          // Create canvas for capturing
          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d');
          
          // Wait for video to be ready
          video.addEventListener('loadedmetadata', () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
          });
          
          // Return capture function and cleanup
          resolve({
            video: video,
            capture: () => {
              context.drawImage(video, 0, 0);
              const dataUrl = canvas.toDataURL('image/jpeg', quality);
              
              // Stop camera
              stream.getTracks().forEach(track => track.stop());
              
              return {
                dataUrl: dataUrl,
                blob: PWAUtils.helpers.dataURLtoBlob(dataUrl)
              };
            },
            cleanup: () => {
              stream.getTracks().forEach(track => track.stop());
            }
          });
          
        } catch (error) {
          console.error('Failed to access camera:', error);
          reject(new Error(PWAUtils.i18n.t('camera.access_failed')));
        }
      });
    },

    // Fallback for iOS - use file input
    createFileInput(accept = 'image/*') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = accept;
      input.capture = 'environment'; // Hint for camera

      return new Promise((resolve, reject) => {
        input.addEventListener('change', (event) => {
          const file = event.target.files[0];
          if (file) {
            resolve(file);
          } else {
            reject(new Error(PWAUtils.i18n.t('camera.no_file_selected')));
          }
        });

        input.click();
      });
    }
  },
  
  // Geolocation utilities
  location: {
    async getCurrentPosition(options = {}) {
      if (!PWAUtils.device.supportsGeolocation()) {
        throw new Error(PWAUtils.i18n.t('location.not_supported'));
      }

      const defaultOptions = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000 // 5 minutes
      };

      const geoOptions = { ...defaultOptions, ...options };

      return new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            resolve({
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              accuracy: position.coords.accuracy,
              timestamp: position.timestamp
            });
          },
          (error) => {
            let messageKey = 'location.failed';
            switch (error.code) {
              case error.PERMISSION_DENIED:
                messageKey = 'location.permission_denied';
                break;
              case error.POSITION_UNAVAILABLE:
                messageKey = 'location.unavailable';
                break;
              case error.TIMEOUT:
                messageKey = 'location.timeout';
                break;
            }
            reject(new Error(PWAUtils.i18n.t(messageKey)));
          },
          geoOptions
        );
      });
    },

    watchPosition(callback, errorCallback, options = {}) {
      if (!PWAUtils.device.supportsGeolocation()) {
        throw new Error(PWAUtils.i18n.t('location.not_supported'));
      }

      const defaultOptions = {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000 // 1 minute
      };

      const geoOptions = { ...defaultOptions, ...options };

      return navigator.geolocation.watchPosition(
        (position) => {
          callback({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: position.timestamp
          });
        },
        (error) => {
          let messageKey = 'location.watch_failed';
          switch (error.code) {
            case error.PERMISSION_DENIED:
              messageKey = 'location.permission_denied';
              break;
            case error.POSITION_UNAVAILABLE:
              messageKey = 'location.unavailable';
              break;
            case error.TIMEOUT:
              messageKey = 'location.timeout';
              break;
          }
          errorCallback(new Error(PWAUtils.i18n.t(messageKey)));
        },
        geoOptions
      );
    },
    
    calculateDistance(lat1, lon1, lat2, lon2) {
      // Haversine formula
      const R = 6371; // Earth's radius in kilometers
      const dLat = PWAUtils.helpers.toRad(lat2 - lat1);
      const dLon = PWAUtils.helpers.toRad(lon2 - lon1);
      
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(PWAUtils.helpers.toRad(lat1)) * Math.cos(PWAUtils.helpers.toRad(lat2)) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c; // Distance in kilometers
    }
  },
  
  // Push notification utilities
  notifications: {
    async requestPermission() {
      if (!PWAUtils.device.supportsPushNotifications()) {
        throw new Error(PWAUtils.i18n.t('notification.not_supported'));
      }

      const permission = await Notification.requestPermission();
      return permission === 'granted';
    },

    async showNotification(title, options = {}) {
      if (Notification.permission !== 'granted') {
        console.warn(PWAUtils.i18n.t('notification.permission_not_granted'));
        return;
      }

      const defaultOptions = {
        icon: '/health_pwa/static/icons/icon-192.png',
        badge: '/health_pwa/static/icons/icon-96.png',
        vibrate: [200, 100, 200],
        tag: 'health-pwa'
      };

      const notificationOptions = { ...defaultOptions, ...options };

      if ('serviceWorker' in navigator) {
        const registration = await navigator.serviceWorker.ready;
        return registration.showNotification(title, notificationOptions);
      } else {
        return new Notification(title, notificationOptions);
      }
    },

    // Helper to show booking notifications with Vietnamese translations
    async showBookingNotification(type, booking) {
      const titleKey = `notification.${type}`;
      const title = PWAUtils.i18n.t(titleKey);

      const body = booking.patient_name || booking.name || '';
      const data = {
        type: type,
        booking_id: booking.id,
        url: `/health_pwa#/bookings/${booking.id}`
      };

      return this.showNotification(title, {
        body: body,
        data: data,
        actions: [
          {
            action: 'view',
            title: PWAUtils.i18n.t('notification.view') || 'View',
            icon: '/health_pwa/static/icons/icon-96.png'
          }
        ]
      });
    }
  },
  
  // Storage utilities
  storage: {
    // Check available storage quota
    async getStorageQuota() {
      if ('storage' in navigator && 'estimate' in navigator.storage) {
        const estimate = await navigator.storage.estimate();
        return {
          quota: estimate.quota,
          usage: estimate.usage,
          available: estimate.quota - estimate.usage,
          usagePercentage: Math.round((estimate.usage / estimate.quota) * 100)
        };
      }
      return null;
    },
    
    // Check if storage is persistent
    async isPersistent() {
      if ('storage' in navigator && 'persist' in navigator.storage) {
        return await navigator.storage.persisted();
      }
      return false;
    },
    
    // Request persistent storage
    async requestPersistent() {
      if ('storage' in navigator && 'persist' in navigator.storage) {
        return await navigator.storage.persist();
      }
      return false;
    }
  },
  
  // Network utilities
  network: {
    isOnline: function() {
      return navigator.onLine;
    },
    
    getConnectionInfo: function() {
      if ('connection' in navigator) {
        const connection = navigator.connection;
        return {
          effectiveType: connection.effectiveType,
          downlink: connection.downlink,
          rtt: connection.rtt,
          saveData: connection.saveData
        };
      }
      return null;
    },
    
    isSlowConnection: function() {
      const info = this.getConnectionInfo();
      if (info) {
        return info.effectiveType === 'slow-2g' || info.effectiveType === '2g';
      }
      return false;
    }
  },
  
  // App installation utilities
  installation: {
    canInstall: function() {
      return window.deferredPrompt !== null;
    },

    async promptInstall() {
      // Check if using correct browser
      if (!PWAUtils.device.isCorrectBrowser()) {
        const device = PWAUtils.device.getDeviceType();
        if (device === 'ios') {
          throw new Error(PWAUtils.i18n.t('install.use_safari'));
        } else if (device === 'android') {
          throw new Error(PWAUtils.i18n.t('install.use_chrome'));
        }
      }

      if (!window.deferredPrompt) {
        throw new Error(PWAUtils.i18n.t('install.cannot_install'));
      }

      window.deferredPrompt.prompt();
      const choiceResult = await window.deferredPrompt.userChoice;
      window.deferredPrompt = null;

      return choiceResult.outcome === 'accepted';
    },

    isInstalled: function() {
      return PWAUtils.device.isStandalone();
    },

    // Get installation instructions based on platform
    getInstructions: function() {
      const device = PWAUtils.device.getDeviceType();
      const browser = PWAUtils.device.getBrowser();

      if (device === 'ios') {
        return {
          platform: 'ios',
          browser: browser,
          needsSafari: browser !== 'safari',
          steps: [
            PWAUtils.i18n.t('install.ios_step1') || 'Tap the Share button',
            PWAUtils.i18n.t('install.ios_step2') || 'Select "Add to Home Screen"',
            PWAUtils.i18n.t('install.ios_step3') || 'Tap "Add"'
          ]
        };
      } else if (device === 'android') {
        return {
          platform: 'android',
          browser: browser,
          needsChrome: browser !== 'chrome',
          steps: [
            PWAUtils.i18n.t('install.android_step1') || 'Tap the menu button',
            PWAUtils.i18n.t('install.android_step2') || 'Select "Add to Home screen"',
            PWAUtils.i18n.t('install.android_step3') || 'Tap "Install"'
          ]
        };
      } else {
        return {
          platform: 'desktop',
          browser: browser,
          steps: [
            PWAUtils.i18n.t('install.desktop_step1') || 'Look for the install icon',
            PWAUtils.i18n.t('install.desktop_step2') || 'Click install',
            PWAUtils.i18n.t('install.desktop_step3') || 'Launch the app'
          ]
        };
      }
    }
  },
  
  // Helper utilities
  helpers: {
    toRad: function(degrees) {
      return degrees * (Math.PI / 180);
    },
    
    dataURLtoBlob: function(dataurl) {
      const arr = dataurl.split(',');
      const mime = arr[0].match(/:(.*?);/)[1];
      const bstr = atob(arr[1]);
      let n = bstr.length;
      const u8arr = new Uint8Array(n);
      
      while (n--) {
        u8arr[n] = bstr.charCodeAt(n);
      }
      
      return new Blob([u8arr], { type: mime });
    },
    
    formatFileSize: function(bytes) {
      if (bytes === 0) return '0 B';
      
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },
    
    formatDistance: function(kilometers) {
      if (kilometers < 1) {
        return Math.round(kilometers * 1000) + ' m';
      }
      return kilometers.toFixed(1) + ' km';
    },
    
    debounce: function(func, wait, immediate) {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          timeout = null;
          if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
      };
    },
    
    throttle: function(func, limit) {
      let inThrottle;
      return function(...args) {
        if (!inThrottle) {
          func.apply(this, args);
          inThrottle = true;
          setTimeout(() => inThrottle = false, limit);
        }
      };
    }
  },
  
  // UI utilities
  ui: {
    showToast: function(message, type = 'info', duration = 3000) {
      // Create toast element
      const toast = document.createElement('div');
      toast.className = `toast toast-${type}`;
      toast.textContent = message;
      
      // Style the toast
      Object.assign(toast.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        background: type === 'error' ? '#f44336' : type === 'success' ? '#4caf50' : '#2196f3',
        color: 'white',
        padding: '12px 20px',
        borderRadius: '4px',
        zIndex: '10000',
        fontSize: '14px',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
        transform: 'translateX(100%)',
        transition: 'transform 0.3s ease'
      });
      
      // Add to DOM
      document.body.appendChild(toast);
      
      // Show toast
      setTimeout(() => {
        toast.style.transform = 'translateX(0)';
      }, 100);
      
      // Hide and remove toast
      setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
          if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
          }
        }, 300);
      }, duration);
    },
    
    showConfirm: function(message, title = 'Confirm') {
      return new Promise((resolve) => {
        const result = confirm(title + '\n\n' + message);
        resolve(result);
      });
    },
    
    vibrate: function(pattern = [200]) {
      if ('vibrate' in navigator) {
        navigator.vibrate(pattern);
      }
    }
  }
};

// Initialize network event listeners
(function initNetworkListeners() {
  if (typeof window !== 'undefined') {
    window.addEventListener('online', () => {
      PWAUtils.ui.showToast(PWAUtils.i18n.t('network.online'), 'success');
      // Trigger sync if available
      if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
        navigator.serviceWorker.ready.then(registration => {
          return registration.sync.register('sync-data');
        }).catch(err => console.log('Background sync failed:', err));
      }
    });

    window.addEventListener('offline', () => {
      PWAUtils.ui.showToast(PWAUtils.i18n.t('network.offline'), 'error', 5000);
    });

    // Check connection speed on load
    if (PWAUtils.network.isSlowConnection()) {
      PWAUtils.ui.showToast(PWAUtils.i18n.t('network.slow_connection'), 'info');
    }
  }
})();

console.log('PWA utilities loaded successfully');