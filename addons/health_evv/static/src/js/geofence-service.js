// Health EVV - GeofenceService (spec A.5)
//
// Battery-conscious strategy (constants below):
// 1. While the app is foregrounded on a visit, poll a COARSE fix
//    (enableHighAccuracy:false) every COARSE_POLL_MS.
// 2. When the coarse fix is within NEAR_ENTER_M of the visit's geofence
//    centre, switch to watchPosition high-accuracy mode.
// 3. Drop back to coarse polling when farther than NEAR_EXIT_M
//    (hysteresis) or after check-in completes.
// 4. Stop watching entirely once checked-in and inside the fence;
//    resume EXIT_RESUME_BEFORE_END_MS before the scheduled end for
//    exit (check-out) detection.
// 5. Everything stops when the page is hidden longer than
//    HIDE_STOP_MS. LIMITATION: PWAs have no background geolocation —
//    prompts fire on the next app open.
//
// Enter/exit NEVER auto-submit: they only emit window CustomEvents
// ('evv:geofence-enter' / 'evv:geofence-exit') consumed by the prompt
// sheet in evv-components.js (one explicit tap required — VN labour +
// trust posture).

(function () {
  'use strict';

  // --- Battery strategy constants (documented above) ---------------
  const COARSE_POLL_MS = 3 * 60 * 1000;   // coarse fix every 3 min
  const NEAR_ENTER_M = 400;               // switch to high accuracy
  const NEAR_EXIT_M = 600;                // hysteresis back to coarse
  const HIDE_STOP_MS = 10 * 60 * 1000;    // stop after 10 min hidden
  const EXIT_RESUME_BEFORE_END_MS = 15 * 60 * 1000; // exit-watch resume
  const HIGH_ACCURACY_OPTIONS = {
    enableHighAccuracy: true,
    maximumAge: 10000,
    timeout: 15000,
  };
  const COARSE_OPTIONS = {
    enableHighAccuracy: false,
    maximumAge: 60000,
    timeout: 20000,
  };

  function haversineMeters(lat1, lng1, lat2, lng2) {
    const R = 6371000.0;
    const rad = Math.PI / 180;
    const p1 = lat1 * rad;
    const p2 = lat2 * rad;
    const dPhi = (lat2 - lat1) * rad;
    const dLambda = (lng2 - lng1) * rad;
    const a = Math.sin(dPhi / 2) * Math.sin(dPhi / 2)
      + Math.cos(p1) * Math.cos(p2)
        * Math.sin(dLambda / 2) * Math.sin(dLambda / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  class EvvGeofenceService {
    constructor() {
      this.fsoId = null;
      this.config = null;         // {geofence:{lat,lng,radius_m,enabled}, staff_id, ...}
      this.pollTimer = null;
      this.watchId = null;
      this.hiddenSince = null;
      this.insideFence = false;
      this.enterPrompted = false;
      this.exitPrompted = false;
      this.lastPosition = null;
      this.resumeTimer = null;

      document.addEventListener(
        'visibilitychange', this._onVisibility.bind(this));
    }

    // ------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------
    async startForOrder(fsoId) {
      if (this.fsoId === fsoId && (this.pollTimer || this.watchId)) return;
      this.stop();
      this.fsoId = fsoId;
      this.insideFence = false;
      this.enterPrompted = false;
      this.exitPrompted = false;

      this.config = await this._loadConfig(fsoId);
      if (!this.config || !this.config.geofence
          || !this.config.geofence.enabled) {
        console.log('EVV geofence: disabled/no coords for FSO', fsoId);
        return;
      }
      if (this.config.checked_out) return;
      console.log('EVV geofence: coarse polling started for FSO', fsoId);
      this._coarseTick();
      this.pollTimer = setInterval(
        this._coarseTick.bind(this), COARSE_POLL_MS);
    }

    stop() {
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
      if (this.resumeTimer) { clearTimeout(this.resumeTimer); this.resumeTimer = null; }
      this._stopWatch();
      this.fsoId = null;
      this.config = null;
    }

    async _loadConfig(fsoId) {
      try {
        const response = await fetch(
          '/health_pwa/api/fso/' + fsoId + '/evv/config');
        const result = await response.json();
        if (result.success) {
          if (window.healthEvvQueue) {
            window.healthEvvQueue.cacheConfig(fsoId, result.data);
          }
          return result.data;
        }
      } catch (error) {
        console.warn('EVV geofence: config fetch failed, trying cache', error);
      }
      if (window.healthEvvQueue) {
        return window.healthEvvQueue.getConfig(fsoId);
      }
      return null;
    }

    // ------------------------------------------------------------
    // Coarse polling (strategy step 1-2)
    // ------------------------------------------------------------
    _coarseTick() {
      if (document.hidden || !navigator.geolocation || !this.config) return;
      navigator.geolocation.getCurrentPosition(
        this._onCoarsePosition.bind(this),
        function (error) { console.warn('EVV coarse fix failed', error.message); },
        COARSE_OPTIONS);
    }

    _onCoarsePosition(position) {
      const distance = this._distanceTo(position);
      if (distance === null) return;
      console.log('EVV geofence: coarse fix at', Math.round(distance), 'm');
      if (distance <= NEAR_ENTER_M && !this.watchId) {
        this._startWatch();
      }
    }

    // ------------------------------------------------------------
    // High-accuracy watch (strategy step 2-4)
    // ------------------------------------------------------------
    _startWatch() {
      if (this.watchId || !navigator.geolocation) return;
      console.log('EVV geofence: high-accuracy watch started');
      this.watchId = navigator.geolocation.watchPosition(
        this._onPosition.bind(this),
        function (error) { console.warn('EVV watch error', error.message); },
        HIGH_ACCURACY_OPTIONS);
    }

    _stopWatch() {
      if (this.watchId !== null && navigator.geolocation) {
        navigator.geolocation.clearWatch(this.watchId);
        console.log('EVV geofence: high-accuracy watch stopped');
      }
      this.watchId = null;
    }

    _distanceTo(position) {
      const fence = this.config && this.config.geofence;
      if (!fence || !fence.enabled) return null;
      this.lastPosition = {
        lat: position.coords.latitude,
        lng: position.coords.longitude,
        accuracy_m: position.coords.accuracy,
        timestamp: position.timestamp,
      };
      return haversineMeters(
        position.coords.latitude, position.coords.longitude,
        fence.lat, fence.lng);
    }

    _onPosition(position) {
      const distance = this._distanceTo(position);
      if (distance === null) return;
      const fence = this.config.geofence;
      const wasInside = this.insideFence;
      this.insideFence = distance <= (fence.radius_m || 150);

      window.dispatchEvent(new CustomEvent('evv:position', {
        detail: {
          fso_id: this.fsoId,
          distance_m: distance,
          inside: this.insideFence,
          position: this.lastPosition,
        },
      }));

      if (!this.config.checked_in) {
        // Arrival detection.
        if (this.insideFence && !wasInside && !this.enterPrompted) {
          this.enterPrompted = true;
          window.dispatchEvent(new CustomEvent('evv:geofence-enter', {
            detail: this._eventDetail(distance),
          }));
        }
        // Hysteresis: fall back to coarse polling when far away again.
        if (distance > NEAR_EXIT_M) {
          this._stopWatch();
        }
      } else if (!this.config.checked_out) {
        // Departure detection after check-in.
        if (!this.insideFence && wasInside && !this.exitPrompted) {
          this.exitPrompted = true;
          window.dispatchEvent(new CustomEvent('evv:geofence-exit', {
            detail: this._eventDetail(distance),
          }));
        }
      }
    }

    _eventDetail(distance) {
      return {
        fso_id: this.fsoId,
        distance_m: distance,
        position: this.lastPosition,
        config: this.config,
      };
    }

    // ------------------------------------------------------------
    // Check-in/out notifications from the prompt sheet
    // ------------------------------------------------------------
    onCheckedIn() {
      if (!this.config) return;
      this.config.checked_in = true;
      // Strategy step 4: stop watching once checked-in and inside;
      // resume shortly before the scheduled end for exit detection.
      this._stopWatch();
      const scheduledEnd = this.config.scheduled_end
        ? new Date(this.config.scheduled_end).getTime() : null;
      const resumeIn = scheduledEnd
        ? Math.max(scheduledEnd - Date.now() - EXIT_RESUME_BEFORE_END_MS, 0)
        : EXIT_RESUME_BEFORE_END_MS;
      this.resumeTimer = setTimeout(this._startWatch.bind(this), resumeIn);
    }

    onCheckedOut() {
      if (this.config) this.config.checked_out = true;
      this.stop();
    }

    // ------------------------------------------------------------
    // Visibility (strategy step 5)
    // ------------------------------------------------------------
    _onVisibility() {
      if (document.hidden) {
        this.hiddenSince = Date.now();
        setTimeout(this._maybeStopHidden.bind(this), HIDE_STOP_MS + 1000);
      } else {
        this.hiddenSince = null;
        if (this.fsoId && !this.pollTimer && this.config) {
          // Resume after coming back to foreground.
          this._coarseTick();
          this.pollTimer = setInterval(
            this._coarseTick.bind(this), COARSE_POLL_MS);
        }
      }
    }

    _maybeStopHidden() {
      if (this.hiddenSince && Date.now() - this.hiddenSince >= HIDE_STOP_MS) {
        console.log('EVV geofence: page hidden >10 min — stopping GPS');
        if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
        this._stopWatch();
      }
    }
  }

  window.healthEvvGeofence = new EvvGeofenceService();

  // Follow the PWA hash router: activate on the visit detail screen
  // (#/orders/<id>), stop when leaving it.
  function syncWithRoute() {
    const match = window.location.hash.match(/#\/orders\/(\d+)/);
    if (match) {
      window.healthEvvGeofence.startForOrder(parseInt(match[1], 10));
    } else if (window.healthEvvGeofence.fsoId) {
      window.healthEvvGeofence.stop();
    }
  }
  window.addEventListener('hashchange', syncWithRoute);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncWithRoute);
  } else {
    syncWithRoute();
  }
})();
