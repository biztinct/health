// Health PWA - Utility Functions for PWA Features

window.PWAUtils = {
  
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
        throw new Error('Camera not supported on this device');
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
        throw new Error('Camera permission denied');
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
          reject(error);
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
            reject(new Error('No file selected'));
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
        throw new Error('Geolocation not supported');
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
            let message = 'Failed to get location';
            switch (error.code) {
              case error.PERMISSION_DENIED:
                message = 'Location permission denied';
                break;
              case error.POSITION_UNAVAILABLE:
                message = 'Location unavailable';
                break;
              case error.TIMEOUT:
                message = 'Location request timeout';
                break;
            }
            reject(new Error(message));
          },
          geoOptions
        );
      });
    },
    
    watchPosition(callback, errorCallback, options = {}) {
      if (!PWAUtils.device.supportsGeolocation()) {
        throw new Error('Geolocation not supported');
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
          let message = 'Failed to watch location';
          switch (error.code) {
            case error.PERMISSION_DENIED:
              message = 'Location permission denied';
              break;
            case error.POSITION_UNAVAILABLE:
              message = 'Location unavailable';
              break;
            case error.TIMEOUT:
              message = 'Location request timeout';
              break;
          }
          errorCallback(new Error(message));
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
        throw new Error('Push notifications not supported');
      }
      
      const permission = await Notification.requestPermission();
      return permission === 'granted';
    },
    
    async showNotification(title, options = {}) {
      if (Notification.permission !== 'granted') {
        console.warn('Notification permission not granted');
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
      if (!window.deferredPrompt) {
        throw new Error('App cannot be installed at this time');
      }
      
      window.deferredPrompt.prompt();
      const choiceResult = await window.deferredPrompt.userChoice;
      window.deferredPrompt = null;
      
      return choiceResult.outcome === 'accepted';
    },
    
    isInstalled: function() {
      return PWAUtils.device.isStandalone();
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

console.log('PWA utilities loaded successfully');