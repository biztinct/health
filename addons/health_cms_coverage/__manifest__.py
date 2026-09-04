# -*- coding: utf-8 -*-
{
    'name': 'Healthcare CMS — Shipped-Feature Sidebar Coverage',
    'version': '19.0.1.4.1',
    'category': 'Healthcare',
    'summary': 'Puts nineteen already-shipped features into the /bizapp sidebar '
               '(CRM, Operations, Clinical, Finance). Data glue plus a role-'
               'gating hook — no models, and no existing menu touched.',
    'description': """
Sidebar coverage for features that shipped without a way in
=============================================================

A login lands in ``/bizapp`` and ``/odoo`` redirects straight back into it —
for the administrator too. The shell's app switcher lists only its own apps, so
a backend ``menuitem`` is **not** a reachable surface: 128 menus our modules
ship were reachable only by typing a URL (audit:
``docs/strategy/cms-sidebar-menu-coverage.html``, ledger §5.69).

This module adds the **table A** leaves for the four business sections the user
selected — CRM, OPERATIONS MANAGER, CLINICAL, FINANCE — and nothing else. The
ADMIN and proposed ANALYTICS leaves, the optional configuration screens and the
already-reachable duplicates are deliberately untouched.

Nineteen leaves covering twenty-three backend menus:

* **CRM** — Channels (setup) *(+ Channel Messages, Channel Audit)*, Reply
  Templates *(+ Watchlist Phrases)*, Follow-up Calendar, Relationships.
* **OPERATIONS MANAGER** — Telehealth, Self-Booking Invites, Family Links,
  Family Messages, Route Feasibility.
* **CLINICAL** — Diagnoses, Unsigned Notes, Voice Notes, Coding Review, Visit
  Tasks, Patient Portal *(+ My Care Access Log)*, Consent Check Log.
* **FINANCE** — BHYT Claims, Service Packages, Red Invoice Log.

Three rules this module follows, each paid for by a live failure:

* **Every item is a ROOT leaf.** An item with children becomes a
  non-navigating expander, so hanging one under an existing leaf would stop
  that leaf opening (§5.69a). Items that belong "under" an existing screen
  ship as siblings instead.
* **No ``match_models``, ever.** The model index is last-wins, so a satellite
  leaf declaring a model an existing leaf already owns steals its highlight
  for every action with no xml-id (§5.94). Only ``match_action_xmlids``.
* **A glue module, not an edit to health_cms_sidebar.** Four modules depend on
  that one and two of them (health_care_command,
  health_care_command_deps → channels) would close a dependency loop if it
  depended on them back — and a loop's symptom is a green "0 of 0 tests"
  (§5.71). Depending downstream on everything it references is the
  health_cms_clinical pattern and cannot loop.

**Visibility follows each section's own convention**, which lives in the
database rather than in XML (34 pre-existing leaves are gated that way, which is
why the seed files look ungated): CRM → Owner + CRM, OPERATIONS → Owner +
Operations Manager, FINANCE → Owner + Accountant, CLINICAL → ungated like all 24
of its existing items. The single measured exception is Voice Notes: only Owner
/ Operations Manager / Branch Manager can read `health.scribe.job`, so it is
gated instead of being drawn for roles that would be refused.

That gating is not decoration. The first install shipped these leaves ungated
and driving the shell as the real `crm` user showed the cost: a receptionist was
served an entire FINANCE section their sidebar has never had, and clicking it
answered "You are not allowed to access 'BHYT Insurance Claim'". See
``hooks.py``.
    """,
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': [
        'health_cms_sidebar',
        # Every module whose action a leaf points at. All are DOWNSTREAM of
        # health_cms_sidebar or unrelated to it, so this module can depend on
        # them without closing the loop that editing health_cms_sidebar's own
        # depends would (§5.71 — walked transitively before writing this list).
        'health_crm',
        'health_care_command',
        'health_care_command_channels',
        'health_telehealth',
        'health_self_booking',
        'health_family_link',
        'health_family_messages',
        'health_routes',
        'health_condition',
        'health_emr',
        'health_scribe',
        'health_ai_coding',
        'health_careplan',
        'health_portal',
        'health_consent',
        'health_bhyt',
        'health_invoicing',
        'health_redinvoice',
        # Added for the 19.0.1.2.0 menu consolidation: it WRITES sidebar rows
        # owned by these two (relocating Monitoring Devices out of the Care
        # Intelligence expander; re-homing Campaign Review's match target onto
        # the Web Touchpoints leaf), so it must load after them. Neither
        # depends on this module, so there is no loop.
        'health_cms_clinical',
        'health_web_leads',
        # The role bundles the nineteen leaves are gated to. Already transitive
        # through health_web_leads; named explicitly because this module now
        # writes `biz_role_ids` and resolves `health_access.role_*` by name.
        'health_access',
    ],
    'data': [
        'data/cms_sidebar_items_features.xml',
    ],
    # The entries are `noupdate` rows an upgrade does not re-assert, so the gate cannot
    # be seeded with ref() — the gating is written by the hook, exactly as the
    # 34 pre-existing gated leaves were. Also re-applied by the 19.0.1.1.0
    # migration so an upgrade converges with a fresh install.
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 141,
}
