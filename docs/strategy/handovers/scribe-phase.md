# Handover: Ambient Scribe v1 — `health_scribe`

Read `docs/strategy/HANDOVER-CONVENTIONS.md` FIRST (definition of done =
its §8; gotcha ledger 19 entries — read all, §5.19 especially: this
phase touches clinical-note text). This is Tier 4's ambient scribe in
its v1 shape: the nurse taps a mic in the clinical-note form, speaks
her observations in Vietnamese, and the platform turns the recording
into note text — typed documentation without typing. Transcription
runs server-side against a PLUGGABLE HTTP STT backend (whisper.cpp /
faster-whisper / PhoWhisper behind an OpenAI-compatible endpoint).
**Nothing is installed on the Odoo server** (§1 hard rule — the
cryptography-chain incident), and with no backend configured the
module records + queues and waits.

Synergy: the appended transcript makes the note "text present, sidecar
empty" — the shipped `health_ai_coding` sweep picks it up with zero
new code. Voice → text → suggested ICD-10, human-gated at each step.

## 0. Scope (one new module `health_scribe`)

1. **PWA capture**: mic button in the clinical-note form
   (MediaRecorder, webm/opus), preview + duration cap, uploaded with
   the note save.
2. **Upload endpoint + `audio_ids`** on the note (photo-upload mirror)
   + a `health.scribe.job` per recording (sha256, state machine).
3. **Transcription sweep** (cron every 30 min): jobs → STT backend →
   transcript APPENDED to the note's `clinical_notes` inside a
   clearly-marked "auto transcript — please verify" block.
4. **Sovereignty gate**: default-deny cloud; the endpoint must be a
   private host unless `allow_cloud` is explicitly set.

⇒ **PWA bump required: 1.8.0 → 1.9.0** + manifest `.21 → .22`
(conventions §3); deploy health_pwa alongside (bump-only diff).

**Non-goals (binding):** offline audio queueing (photos aren't queued
offline today either — offline recording fails with a clear message,
v2 problem); EVV chain events for audio (scribe audio is
documentation, not visit-verification evidence — do NOT touch
health_evv); live/streaming transcription; speaker diarization;
translation; editing app.js beyond the whitelist in §2.2; pip
installs on the server (the STT backend is EXTERNAL by contract);
building STT into bi.ai.provider (it's chat-shaped — scribe gets its
own two config params).

## 1. Verified plumbing facts (do not re-derive; refs verified Jul 2026)

- **Note form seam**: the PWA clinical-note modal lives in app.js
  (~L1706 state, form markup ~L3551-3616); the photo block
  `.photo-upload-container` (~L3597-3610) is the insertion anchor —
  file input + `capturePhoto` handler + save-time FormData POST
  (~L2384-2461) is the exact pattern to mirror for audio.
- **Upload precedent**: `POST /health_pwa/api/fso/<int:order_id>/
  upload_image` (health_pwa/controllers/api.py:1043-1082) — multipart
  FormData, `request.httprequest.files.get(...)`, base64 →
  ir.attachment (res_model=health.clinical.note), `[(4, id)]` link,
  returns attachment_id/url. Photos are NOT offline-queued (the PWA
  refuses with "Cannot upload images while offline" ~L5753) — audio
  inherits that posture.
- **Note create endpoint**: `POST /health_pwa/api/fso/<id>/
  clinical_notes` (api.py:948-991) — the save flow your JS hooks
  after (photo precedent: note saved first, then media uploaded with
  note_id).
- **PHI (§5.19)**: `clinical_notes` is a NON-STORED compute backed by
  `clinical_notes_enc` when health_phi_encryption is installed —
  appending means read-modify-WRITE through the ORM field (the
  inverse encrypts), never SQL, never the `_enc` column directly. A
  transcript appended into `clinical_notes` is therefore encrypted at
  rest for free. ir.attachment binaries are NOT encrypted — the raw
  audio sits plaintext in the filestore; state this in the module
  description and store the file's sha256 on the job for integrity.
- **Consent**: recording is media → `check_consent(patient,
  'photography')` (the Photography/Media type, health_consent.py:74-82)
  logged at upload; AI processing of the text → the sweep gates on
  `check_consent(patient, 'data_sharing')` exactly like
  health_ai_coding's sweep. Both log-only (never block a nurse
  mid-visit), evidence rows are the record.
- **Sweep/queue precedent**: health_ai_coding's cron
  (ai_code_suggestion.py:247-282) — enabled gate → per-record
  savepoint → attempt counter capped at 3 → error-logged, sweep ends
  green. Cron XML: 20:00 UTC = 03:00 ICT for nightly; THIS module's
  cron is every 30 min (same-day value), interval_type minutes.
  No queue_job module exists — plain ir.cron only.
- **HTTP-call template**: bi_ai.py `_complete_ollama` (L174-189) —
  requests.post(json=..., timeout=...), raise_for_status, caller
  wraps. Scribe's variant is multipart: OpenAI-compatible
  `POST <endpoint>` with fields `file` (the audio), `model`,
  `language`, `response_format=json` → `{"text": "..."}` (this shape
  is what whisper.cpp server / faster-whisper-server / OpenAI all
  speak — state the contract in the module description).
- **Sovereignty precedent**: health_ai_coding.allow_cloud /
  health_routes.use_external_router (default-deny, one warning line,
  zero calls).
- **PWA**: version places per conventions §3, current 1.8.0/.21.
  Shell-inherit + `window.*` global module pattern (ergo/daystrip/
  telehealth precedents). getUserMedia needs the secure context —
  care.biztinct.com is https; handle NotAllowedError gracefully
  (vi-first message).

## 2. Architecture

### 2.1 `health.scribe.job`

| field | notes |
|---|---|
| note_id | m2o health.clinical.note, required, index, ondelete cascade |
| fso_id / patient_id | related stored (grouping + catchment rule) |
| attachment_id | m2o ir.attachment (the audio), ondelete set null |
| audio_sha256 | Char — computed server-side at upload from the bytes |
| duration_s | Float (client-reported, informational) |
| state | pending / done / failed (failed = attempts exhausted) |
| attempts / last_attempt | Integer / Datetime, cap `health_scribe.max_attempts` (3) |
| transcript | Text — the raw STT output (kept for audit even after append) |
| error | Char — last failure |
One job per attachment (search-first). No unlink below manager.
Note: `transcript` on the job is NOT covered by health_phi_encryption
(it only wraps note fields) — say so in the description; the
authoritative copy lands in the encrypted `clinical_notes`, and the
job row is manager-read-only (§3) for that reason.

### 2.2 PWA capture (`scribe.js` + `scribe.css`, shell inherit)

- Mic button injected inside the clinical-note modal next to the
  photo block (stable anchor `.photo-upload-container`; MutationObserver
  for modal open — the daystrip fetch-wrap seam doesn't apply here).
  States: idle → recording (elapsed timer, hard stop at
  `health_scribe.max_seconds`, default 300) → preview (duration +
  re-record + discard). vi-first labels ("Ghi âm (Record)"), inline
  SVG, ergo-compatible CSS (vu-glove 64px, vu-sunlight mono).
- MediaRecorder `audio/webm;codecs=opus` with a fallback to the
  browser default mimetype; refuse to start offline (the photo
  posture) with "Cần kết nối mạng để ghi âm (recording needs a
  connection)".
- On note save (mirror the photo flow): note first, then
  `POST /health_pwa/api/fso/<id>/upload_audio` FormData
  {audio, note_id, duration_s}.
- **app.js edits: ZERO.** If the modal proves unhookable from outside
  (it's Vue-rendered), the fallback is ONE whitelisted line adding a
  stable class/data-attr to the modal container — quote it verbatim
  in the report if you need it; more than that = redesign.

### 2.3 Upload endpoint (this module's controller)

`POST /health_pwa/api/fso/<int:order_id>/upload_audio` — clone
upload_image's auth/access/envelope verbatim (`auth='user'`,
`_check_api_access`), then: mimetype must start `audio/` (400
otherwise), size cap `health_scribe.max_bytes` (default 15 MB),
sha256 the bytes, create attachment + `[(4, ...)]` onto the new
`audio_ids` m2m (note inherit — the ONLY note schema touch besides
nothing), create the job (pending), log-only
`check_consent(patient, 'photography')`. Returns job_id +
attachment_id. Replay-safe: same sha256 + note → return the existing
job (idempotent re-upload after a flaky connection).

### 2.4 Transcription sweep (`cron_scribe_transcribe`, every 30 min)

Gates in order: `health_scribe.enabled` (default **True** — capture
is harmless and the sweep is inert without an endpoint) →
`stt_endpoint` configured (empty → return, jobs stay pending, ONE
debug line not a warning-per-run) → **private-host rule**: unless
`health_scribe.allow_cloud` (default **False**), the endpoint host
must be localhost/127.x/10.x/172.16-31.x/192.168.x (parse with
urllib + ipaddress; hostname that doesn't resolve to private →
refuse with one warning). Then per pending job (savepoint, batch cap
default 10, oldest first): POST the audio multipart (§1 contract,
`language` = `health_scribe.language` default 'vi', timeout
`stt_timeout_s` default 120) → `{"text"}` → job.transcript + state
done → **append to the note**:

```
<p><em>🎙 no — NO emoji. Use plain text:</em></p>
<p><em>[Bản ghi âm tự động — vui lòng kiểm tra
(auto transcript — please verify)]</em></p>
<p>{text}</p>
```

Append = `note.clinical_notes = (note.clinical_notes or '') + block`
through the ORM (§5.19 — the compute/inverse handles encryption).
Sweep also gates each job on `check_consent(patient, 'data_sharing')`
— False → job failed with error 'consent', no STT call. Empty/blank
STT text → attempt++, not an append. Provider down → attempt++,
sweep green (vietuat reality: no backend).

### 2.5 Backend UI

Jobs list (filter pending/failed) under the clinical menu next to the
AI coding queue; note form shows the audio players (attachment links)
+ a "Transcribe now" button (manager+, calls the same per-job path)
for retry-after-fix. Flat mono, no emoji.

## 3. Module skeleton

Depends `['health_pwa', 'health_fieldservice', 'health_consent']`.
Config params: enabled(True) / stt_endpoint('') / language('vi') /
allow_cloud(False) / max_seconds(300) / max_bytes(15728640) /
max_attempts(3) / batch_cap(10) / stt_timeout_s(120) — Settings block
per the self_booking pattern. ACL: jobs read manager+ ONLY (transcript
is unencrypted PHI-adjacent text), the nurse never needs the job row
(her output is the note); note audio_ids visible to whoever reads the
note. Catchment rule on jobs. vi.po.

## 4. Tests (`tests/test_scribe.py`)

Mock at `requests.post` (or a module-level `_stt_call` seam — your
call, report it). Cases:
1. Upload: happy path (attachment + audio_ids + job pending + sha256
   correct + consent check-log row); non-audio mimetype → 400; over
   max_bytes → 400; replay same sha256 → same job, no dup.
2. Sweep gates: enabled=False → nothing; endpoint empty → jobs stay
   pending, zero calls; public endpoint + allow_cloud=False → refused,
   zero calls (mock-not-called); private endpoint passes the rule
   (10.x and localhost variants); allow_cloud=True lets a public host
   through.
3. Happy transcription: mocked `{"text": "bệnh nhân ổn định"}` → job
   done, transcript stored, note.clinical_notes contains the marker
   block AND the text (read back through the ORM field — proves the
   §5.19 encrypted path); with health_phi_encryption installed assert
   `clinical_notes_enc` is set (skipTest if module absent).
4. Robustness: STT raising → attempt++/pending; attempts exhausted →
   failed; blank text → attempt++ no append; savepoint isolation (bad
   job doesn't kill the batch); consent False → failed('consent'),
   zero calls for that job.
5. Idempotency: re-running the sweep never double-appends (state
   guard); "Transcribe now" on a done job is a no-op.
6. Shell HttpCase: scribe.js/css served at ?v=1.9.0, version strings
   1.9.0 (5-place guard), daystrip/telehealth/ergo assets co-resident.
   (Their version-pin tests need the 1.8.0→1.9.0 bump — grep
   `addons/*/tests` for the old version, ledger precedent.)
7. ACL: plain nurse reading a job → AccessError; manager OK.

## 5. Deploy & verify

- `-i health_scribe -u health_pwa --test-tags /health_scribe,
  /health_pwa_daystrip,/health_telehealth,/health_pwa_ergo` (the three
  shell co-residents pin the version). Port-wait loop after stop;
  results from the logfile, YOUR timestamp.
- **Browser QA on care.biztinct.com REQUIRED with committed evidence**
  (QA_SCREENSHOTS.md precedent): the mic button in the note form,
  recording state with timer, preview, a saved note with the audio
  attachment; then the demo below.
- Live demo: no STT backend exists on vietuat — demo BOTH halves:
  (a) record + upload on a demo FSO → job pending, sweep runs green
  and leaves it pending (endpoint empty); (b) start a 6-line python3
  **stdlib-only** stub on the server (`python3 -m http.server`-style
  handler returning `{"text": "…"}` on 127.0.0.1:8123 — NO pip),
  point stt_endpoint at it, run the sweep, show the transcript block
  landing in the note (and the ai_coding synergy if its sweep is
  enabled=False — just note the note is now eligible), then kill the
  stub and CLEAR stt_endpoint. Final positions: enabled=True,
  stt_endpoint='', allow_cloud=False.
- health_pwa diff = version bump ONLY. vi.po, conventions §8,
  commit+push on 19.0.

## 6. Report-back extras

(a) final `health_scribe.*` positions; (b) demo note/job ids, the
exact appended block text, and the stub-server code you used;
(c) which mimetype the recorder produced on the QA device and the
fallback behavior; (d) the modal-injection seam you used (observer
target; whether the whitelisted fallback line was needed — quote it);
(e) the sha256-replay behavior verified; (f) any new ledger-grade
gotcha (explicitly flagged).
