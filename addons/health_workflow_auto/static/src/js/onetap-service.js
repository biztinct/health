// Health Workflow Auto — one-tap visit completion (E.2, handover A3)
//
// Injected into the PWA app shell without touching health_pwa. Exposes the
// window.healthOnetap* globals the visit screen uses to decide whether to show
// the one-tap button and to run it. ONLINE-ONLY: eligibility is a live GET, so
// the button never appears offline (falls back to the normal quote flow).

(function () {
  'use strict';

  const ELIGIBLE_URL = function (id) {
    return '/health_pwa/api/fso/' + id + '/onetap_eligible';
  };
  const COMPLETE_URL = function (id) {
    return '/health_pwa/api/fso/' + id + '/complete_onetap';
  };

  function isOnline() {
    return typeof navigator === 'undefined' || navigator.onLine !== false;
  }

  // Returns {eligible, reason} or {eligible:false, reason:'offline'} when offline.
  async function checkEligible(orderId) {
    if (!isOnline()) {
      return { eligible: false, reason: 'offline' };
    }
    try {
      const resp = await fetch(ELIGIBLE_URL(orderId), {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
      });
      const json = await resp.json();
      if (json && json.success && json.data) {
        return json.data;
      }
      return { eligible: false, reason: 'error' };
    } catch (error) {
      return { eligible: false, reason: 'error' };
    }
  }

  // Runs one-tap completion. Returns the server data envelope:
  //  - {completed:true, state, verified_quote:true} on success
  //  - {completed:false, needs_review:true, changed:{...}} when the quote changed
  //    (caller should route to the existing quote screen)
  async function complete(orderId, opts) {
    opts = opts || {};
    const body = {
      service_notes: opts.serviceNotes || '',
      payment_choice: opts.paymentChoice || 'pay_later',
    };
    if (opts.paymentMethod) {
      body.payment_method = opts.paymentMethod;
    }
    const resp = await fetch(COMPLETE_URL(orderId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    });
    const json = await resp.json();
    if (json && json.success && json.data) {
      return json.data;
    }
    throw new Error((json && json.error) || 'One-tap completion failed');
  }

  window.healthOnetap = {
    checkEligible: checkEligible,
    complete: complete,
    isOnline: isOnline,
  };
  window.healthOnetapReady = true;
})();
