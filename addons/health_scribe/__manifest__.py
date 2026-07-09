# -*- coding: utf-8 -*-
{
    'name': 'Health Ambient Scribe',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Voice → note text: the nurse records her observations in the '
               'clinical-note form; a pluggable server-side STT backend turns '
               'the recording into note text.',
    'description': """
Health Ambient Scribe v1 (health_scribe)
========================================

The nurse taps a mic button in the PWA clinical-note form, speaks her
observations in Vietnamese, and the platform transcribes the recording into
the note text — documentation without typing.

How it works
------------
* **Capture** (PWA): MediaRecorder (webm/opus) inside the clinical-note modal,
  next to the photo block. Recording refuses to start offline. The audio is
  uploaded when the note is saved (piggybacking the existing note-save flow via
  a fetch wrapper — ZERO edits to the shell app.js).
* **Transcription** (server): a 30-minute cron POSTs each pending recording to
  a PLUGGABLE OpenAI-compatible STT endpoint (whisper.cpp / faster-whisper /
  PhoWhisper behind an HTTP server) with multipart fields ``file`` / ``model``
  / ``language`` / ``response_format=json`` → ``{"text": "..."}``. The
  transcript is APPENDED into the note's ``clinical_notes`` inside a clearly
  marked "auto transcript — please verify" block.
* **Sovereignty**: NOTHING is installed on the Odoo server — the STT backend is
  external by contract. Default-deny cloud: the endpoint host must be private
  (localhost / RFC-1918) unless ``allow_cloud`` is explicitly set. With no
  endpoint configured the module records and queues, inert.

Synergy: the appended transcript makes the note "text present, sidecar empty",
so the shipped health_ai_coding sweep picks it up for ICD-10 suggestion with
zero new code. Voice → text → suggested code, human-gated at each step.

Privacy note
------------
The appended transcript lands in ``clinical_notes``, which is AES-encrypted at
rest when health_phi_encryption is installed. However the RAW AUDIO
(ir.attachment) and the ``health.scribe.job.transcript`` field are NOT
encrypted — the audio sits plaintext in the filestore. The file's sha256 is
stored on the job for integrity, and the job row is manager-read-only.
""",
    'author': 'Biztinct',
    'website': 'https://biztinct.com',
    'license': 'LGPL-3',
    'sequence': 166,
    'depends': [
        'health_pwa',
        'health_fieldservice',
        'health_consent',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/health_scribe_security.xml',
        'data/scribe_config_params.xml',
        'data/scribe_cron.xml',
        'views/scribe_job_views.xml',
        'views/health_clinical_note_views.xml',
        'views/res_config_settings_views.xml',
        'views/scribe_menus.xml',
        'views/pwa_shell_inherit.xml',
    ],
    'installable': True,
    'application': False,
}
