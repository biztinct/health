# -*- coding: utf-8 -*-
{
    'name': 'Health AI Retro-Coding Queue',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'LLM suggests ICD-10 codes for free-text clinical notes into a '
               'human review queue — the AI only ever suggests, a clinician '
               'click is the only thing that writes a code.',
    'description': """
Health AI Retro-Coding Queue (health_ai_coding)
===============================================

vietuat has months of free-text diagnoses with an empty coded sidecar. This
module runs a nightly, consent-gated, PSEUDONYMISED LLM sweep over un-coded
clinical notes and SUGGESTS ICD-10 codes into a review queue. A doctor or
head nurse approves or rejects; approving appends the code to the note's
existing ``condition_code_ids`` sidecar (the field Circular 13/2025 EMR
export reads).

Data sovereignty & privacy
---------------------------
* The AI **only ever suggests**. No code is ever written without a human click
  — not even at confidence 1.0.
* Note text is **pseudonymised** before it leaves the note (patient name,
  phone, email, address redacted) — this is pseudonymisation, not
  anonymisation. The real control is the Ollama-first / cloud-off default:
  ``enabled`` and ``allow_cloud`` both ship **False**; installing changes
  nothing until ops flips them, and a non-Ollama provider is refused unless
  cloud is explicitly allowed.
* The exact redacted prompt and raw response are stored in an append-only
  audit log, readable by managers only.
""",
    'author': 'Biztinct',
    'website': 'https://biztinct.com',
    'license': 'LGPL-3',
    'sequence': 165,
    'depends': [
        'biz_bi',
        'health_fhir_terminology',
        'health_consent',
        'health_fieldservice',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/health_ai_coding_security.xml',
        'data/ai_coding_config_params.xml',
        'data/ai_coding_cron.xml',
        'views/ai_coding_log_views.xml',
        'views/ai_code_suggestion_views.xml',
        'views/health_clinical_note_views.xml',
        'views/res_config_settings_views.xml',
        'views/ai_coding_menus.xml',
    ],
    'installable': True,
    'application': False,
}
