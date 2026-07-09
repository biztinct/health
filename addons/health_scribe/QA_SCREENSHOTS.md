# health_scribe — Live browser QA (care.biztinct.com)

Performed on the vietuat UAT server against the deployed **1.9.0** shell
(the PWA "New Update Available" prompt fired on load — the SW `CACHE_VERSION`
bump is live). Verified via Chrome DevTools on the real PWA; the recording
lifecycle was driven through the actual `scribe.js` code path.

Shell wiring (evaluated on `/health_pwa`):

    scribe.js?v=1.9.0  and  scribe.css?v=1.9.0  both served
    window.healthScribe === object      (loaded)
    window.__scribeFetchWrapped === true (note-save upload seam installed)

## Mic block in the real clinical-note form

Flow: Today → in-progress booking **An Xu** → Booking Details → **Clinical
Notes** → **Add New Clinical Note**. The note-entry modal renders the Vue
`.photo-upload-container`; `scribe.js`'s MutationObserver injects the mic block
directly beneath the **ATTACH PHOTO** row (stable anchor confirmed).

1. **Idle** — label **"GHI ÂM (RECORD)"** + a single **"Ghi âm (Record)"**
   button with the inline mic SVG. Flat mono, neutral surface.

2. **Recording** — after tapping Record: a pulsing red dot, a live
   **tabular timer** ("0:49"), and a red-outlined **"Dừng (Stop)"** button.
   (Driven through the real MediaRecorder path on a synthesized audio stream,
   since the QA browser has no physical mic — equivalent to Chrome's
   `--use-fake-device`.)

3. **Preview** — after Stop: **"Đã ghi 59 giây (recorded 59s)"** in green plus
   **"Ghi lại (Re-record)"** and **"Xóa (Discard)"** buttons.

Offline/permission handling: tapping Record with no real mic rejects
`getUserMedia` → a graceful `NotAllowedError` alert, state stays idle (no
crash). Recording also refuses to start when `!navigator.onLine`
("Cần kết nối mạng để ghi âm").

## End-to-end save + upload (the fetch-wrap seam, zero app.js edits)

With a recording pending, typed a short note ("Bệnh nhân ổn định (ghi âm đính
kèm).") and tapped **Confirm and Save**. `scribe.js` observed the
`POST /clinical_notes` response, read the new `note_id`, and uploaded the
59-second recording to `/health_pwa/api/fso/<id>/upload_audio` — then cleared
the pending recording. Server-side confirmation:

    LATEST_JOB 75  state=pending  note=398  fso=1681 (An Xu)
    duration=59.0s  attachment=12180  IN_AUDIO_IDS=True
    note text = "Bệnh nhân ổn định (ghi âm đính kèm)."

So: record → preview → save → the note persists AND the audio is attached +
queued as a scribe job, with no edit to the shell `app.js`.

**Known limitation (documented):** the shell's `saveClinicalNotes` only fires
the note-save POST when there is note text OR a photo — a recording is not
counted as content, so an **audio-only** note (no text, no photo) is blocked by
the app before any POST, and the fetch-wrap has nothing to piggyback on.
Mirroring the photo posture without an app.js edit cannot change that gate;
the nurse records audio alongside a brief note (as above). Making a recording
count as content is a v2 item (needs the one whitelisted app.js line or a
Vue-model write).

## Transcription (server, no STT backend on vietuat)

Demoed with a stdlib-only stub (see the final report §b): sweep with
`stt_endpoint=''` leaves jobs pending (inert, green); pointing at the local
stub transcribed and appended the marked block into the (encrypted)
`clinical_notes`. Final switches restored: `enabled=True`, `stt_endpoint=''`,
`allow_cloud=False`.
