# -*- coding: utf-8 -*-
{
    'name': 'Care Command — Unified Work Layer',
    'version': '19.0.2.0.0',
    'category': 'Healthcare/CRM',
    'summary': 'Omnichannel triage wall + messenger thread over Zalo, Calls, Email and ZNS',
    'description': """
Care Command (Phase 1)
======================

A single omnichannel entry point for the sales/care team. A heat *wall*
triages open conversations by urgency; clicking a tile opens a *messenger
thread* with identity/booking context and claim/ownership.

Phase 1 is a **unified read + work layer** built on top of the existing
channel silos — it never owns message content and never edits the host
modules' behaviour:

- ``care.conversation`` — a thin work-item spine (one record per person-ish
  anchor) maintained by additive, exception-isolated ingestion hooks on
  ``zalo.message``, ``voip.call.log``, ``crm.lead`` and inbound ``mail.message``
  email.
- Read services for the wall/list and the merged cross-channel timeline.
- Claim / release / take-over with a race guard + chatter audit.
- Outbound reply from the composer: Zalo (existing send path) and Email
  (threaded ``message_post``).
- OWL client action ``care_command`` + a CMS sidebar entry after the CRM
  Dashboard.

No AI. No clinical content. No new channels beyond Zalo / Calls / Email / ZNS.
    """,
    'author': 'I Am Dream Catcher Ltd',
    'website': 'https://vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'mail',
        'bus',
        'health_base',
        'health_crm',
        'health_zalo',
        'health_fieldservice',
        'health_cms_sidebar',
        # NOTE: health_voip24h is an OPTIONAL/soft dependency, NOT declared
        # here. It does not install on Odoo 19 (it still uses the removed
        # res.groups.category_id), so it is uninstalled on vietuat. Every
        # voip.call.log read in this addon is guarded with
        # `if 'voip.call.log' in self.env` (health_messaging pattern, §6.4).
        # The Calls dock channel renders but stays inert (0) until VoIP is
        # made O19-compatible + installed; live call INGESTION then needs the
        # voip create-hook re-added (a one-class follow-up).
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/care_command_security.xml',
        'views/care_command_actions.xml',
        'data/cms_sidebar_items_care_command.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # plain CSS (data-URI mask icons — kept out of scss; libsass mangles them)
            'health_care_command/static/src/css/care_command_icons.css',
            'health_care_command/static/src/scss/care_command.scss',
            'health_care_command/static/src/js/care_command.js',
            'health_care_command/static/src/xml/care_command.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
    'sequence': 125,
}
