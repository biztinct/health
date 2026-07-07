// Health Careplan - API client + offline tick outbox (spec §1.7)
//
// Loaded BEFORE careplan-components.js: this file owns the offline
// mutation queue replayed against
// POST /health_pwa/api/careplan_tasks/<id>/update. Ticks queued
// offline are applied optimistically in the UI and synced when the
// connection returns (same submit-or-queue discipline as
// healthVitalsService).

(function () {
  'use strict';

  var OUTBOX_KEY = 'health_careplan_outbox';

  // ---------------------------------------------------------------
  // API
  // ---------------------------------------------------------------
  function getJson(url) {
    return fetch(url, { credentials: 'same-origin' })
      .then(function (response) { return response.json(); })
      .then(function (result) {
        if (!result.success) {
          throw new Error(result.error || 'Care plan error');
        }
        return result.data;
      });
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    }).then(function (response) { return response.json(); })
      .then(function (result) {
        if (!result.success) {
          throw new Error(result.error || 'Care plan error');
        }
        return result.data;
      });
  }

  function getFsoTasks(fsoId) {
    return getJson('/health_pwa/api/fso/' + fsoId + '/careplan_tasks');
  }

  function updateTask(taskId, payload) {
    return postJson(
      '/health_pwa/api/careplan_tasks/' + taskId + '/update', payload);
  }

  function addPrnTask(fsoId, activityId) {
    return postJson(
      '/health_pwa/api/fso/' + fsoId + '/careplan_tasks/add_prn',
      { activity_id: activityId });
  }

  function getPatientCareplans(patientId) {
    return getJson('/health_pwa/api/patients/' + patientId + '/careplans');
  }

  // ---------------------------------------------------------------
  // Offline tick outbox
  // ---------------------------------------------------------------
  function readOutbox() {
    try {
      var raw = localStorage.getItem(OUTBOX_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (error) {
      return [];
    }
  }

  function writeOutbox(items) {
    try {
      localStorage.setItem(OUTBOX_KEY, JSON.stringify(items));
    } catch (error) {
      console.warn('[Careplan] outbox write failed', error);
    }
  }

  function enqueue(taskId, payload) {
    var outbox = readOutbox().filter(function (item) {
      // Last tick per task wins — replace stale queued mutations.
      return item.task_id !== taskId;
    });
    outbox.push({
      task_id: taskId,
      payload: payload,
      queued_at: new Date().toISOString(),
    });
    writeOutbox(outbox);
  }

  var flushing = false;
  function flushOutbox() {
    if (flushing || !navigator.onLine) return Promise.resolve();
    flushing = true;
    var outbox = readOutbox();
    var remaining = [];
    var chain = Promise.resolve();
    outbox.forEach(function (item) {
      chain = chain.then(function () {
        return updateTask(item.task_id, item.payload).catch(
          function (error) {
            // Network failures retry; server-side rejections (4xx)
            // are final — do not retry forever.
            if (error instanceof TypeError) {
              remaining.push(item);
            } else {
              console.warn('[Careplan] queued tick rejected', error);
            }
          });
      });
    });
    return chain.then(function () {
      writeOutbox(remaining);
      flushing = false;
    }, function () {
      writeOutbox(remaining);
      flushing = false;
    });
  }

  // Submit-or-queue: the tick is never lost offline.
  function updateOrQueue(taskId, payload) {
    return updateTask(taskId, payload).catch(function (error) {
      if (error instanceof TypeError || !navigator.onLine) {
        enqueue(taskId, payload);
        return { queued: true, task_id: taskId, state: payload.state };
      }
      throw error;
    });
  }

  window.addEventListener('online', function () { flushOutbox(); });
  document.addEventListener('DOMContentLoaded', function () {
    flushOutbox();
  });

  window.healthCareplanService = {
    getFsoTasks: getFsoTasks,
    updateTask: updateTask,
    updateOrQueue: updateOrQueue,
    addPrnTask: addPrnTask,
    getPatientCareplans: getPatientCareplans,
    flushOutbox: flushOutbox,
    outboxCount: function () { return readOutbox().length; },
  };
})();
