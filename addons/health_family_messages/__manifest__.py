{
    'name': 'Health Family Messages',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'FB-044: secure two-way, consent-gated, PHI-encrypted messaging '
               'between a patient\'s family and the care team',
    'author': 'Biztinct',
    'description': """
Secure Family Messaging (FB-044)
================================

Turns the outbound-only family channel into a two-way one. A family member
using the tokenized ``/family/visit/<token>`` page (no login) can read the
thread and send a message while the token is live; ops read and reply from a
backend "Family Messages" inbox in the Operations Center.

- **Storage**: purpose-built ``health.family.thread`` (one per patient +
  relation) and append-only ``health.family.message`` rows — NOT mail.message
  (family members have no user account, so mail RBAC cannot scope them).
  Message bodies are PHI-encrypted at rest (the clinical-note dual-field
  pattern) and can never be edited or deleted below system admin.
- **Consent**: sending requires ``receives_visit_updates`` AND the shipped
  ``health.consent`` ``data_sharing`` check — the same gate as the visit page.
- **Notify**: an inbound message alerts the visit's lead nurse and the facility
  manager (PWA bell row + VAPID push + a mail.activity fallback). An ops reply
  can ping the family over ZNS through the shipped messaging rails (new purpose
  ``family_message_reply``, empty template default = silent).
- **Safety**: master switch ``health_family_messages.enabled`` defaults False —
  messaging is dark on install and go-live is a manual param flip.
""",
    'depends': [
        'health_family_link',
        'health_messaging',
        'health_pwa',
        'health_phi_encryption',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/health_family_messages_security.xml',
        'data/family_messages_config_params.xml',
        'views/family_messages_templates.xml',
        'views/family_messages_views.xml',
    ],
    'installable': True,
    'application': False,
    'sequence': 147,
    'license': 'LGPL-3',
}
