# -*- coding: utf-8 -*-
{
    'name': 'Healthcare PHI Field Encryption',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Transparent field-level encryption (AES-256-GCM) for narrative PHI and identity numbers',
    'description': """
Field-level PHI encryption for health19
=======================================
Encrypts narrative protected health information and identity numbers at rest
while remaining fully transparent to forms, the PWA and all ORM consumers.

* res.partner: allergies, medical history, intake diagnosis/notes,
  emergency contact details, healthcare notes, National ID (CCCD/CMND),
  CCCD number
* health.clinical.note: all narrative clinical fields

Identity numbers keep exact-match search through HMAC blind indexes
(partial/ilike searches resolve as exact matches on the full number).

Key management: HEALTH_PHI_KEY environment variable (base64, 32 bytes) or,
when unset, a key derived from the database.secret system parameter.
Existing plaintext is migrated to ciphertext and the legacy columns are
dropped by the post-install hook.
""",
    'author': 'Biztinct',
    'depends': [
        'health_base',
        'health_crm',
        'health_fieldservice',
    ],
    'data': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
