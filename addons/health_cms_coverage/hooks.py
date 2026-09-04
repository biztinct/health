# -*- coding: utf-8 -*-
"""Role gating for the nineteen leaves — applied in python, not XML.

WHY PYTHON RATHER THAN A `ref()` IN THE DATA FILE. The entries are
``noupdate="1"``: once a row is on a live database, what somebody has since
done to it is the truth and an upgrade re-asserting this file would undo their
work. So the gate has to be WRITTEN, from the install hook and from the
migration, which is the same reason ``consolidate_sidebar`` below is python.

(It used to be python for a second reason as well: the roles were database rows
with no fixed name, so nothing could point at them. They have fixed names now —
``health_access.role_*`` — which is why the map below reads like a list of names
rather than a list of words to match.)

Why gate at all — the defect this closes, found by driving the shell as the
real `crm` user after the first install: with no gate, all nineteen leaves were
served to every role. A receptionist was shown an entire FINANCE section (which
their sidebar has never had) and got
"You are not allowed to access 'BHYT Insurance Claim'" on click. The gate
below reproduces each section's own established convention:

    CRM       → Owner + CRM                     (as Dashboard, Care Command, Contacts, Activities)
    OPS       → Owner + Operations Manager       (as Bookings, Staff, Staff Schedule, Workload…)
    FINANCE   → Owner + Accountant               (as every FINANCE leaf)
    CLINICAL  → ungated                          (as all 24 existing CLINICAL items)

with ONE measured exception: `health.scribe.job` is readable only by Owner and
Operations Manager, so **Voice Notes** is gated rather than left as a leaf that
refuses the clinical roles it would be drawn for. (Branch Manager was on that
list until H2b asked the permissions table rather than trusting the note, and
found it could not open the screen either.) Every
other CLINICAL model here (condition, clinical note, careplan task, AI
suggestion, portal access, consent check log) is readable by the ungated
audience, verified per role before this file was written.

Runs from ``post_init_hook`` AND from a migration, so a fresh install and an
upgrade of an already-installed copy converge on the same state.
"""
import logging

_logger = logging.getLogger(__name__)

# Fixed names for the roles, so nothing here matches a word against a row.
OWNER = 'health_access.role_owner'
CRM = 'health_access.role_crm'
OPS_MANAGER = 'health_access.role_operations_manager'
ACCOUNTANT = 'health_access.role_accountant'

# leaf xml-id -> the roles that may see it. Absent from this map ⇒ ungated.
ROLE_GATES = {
    # CRM
    'item_crm_channels_setup': (OWNER, CRM),
    'item_crm_reply_templates': (OWNER, CRM),
    'item_crm_followup_calendar': (OWNER, CRM),
    'item_crm_relationships': (OWNER, CRM),
    # OPERATIONS MANAGER
    'item_ops_telehealth': (OWNER, OPS_MANAGER),
    'item_ops_selfbooking': (OWNER, OPS_MANAGER),
    'item_ops_family_links': (OWNER, OPS_MANAGER),
    'item_ops_family_messages': (OWNER, OPS_MANAGER),
    'item_ops_route_feasibility': (OWNER, OPS_MANAGER),
    # CLINICAL — the one exception (see module docstring). BRANCH MANAGER WAS
    # ON THIS LIST AND COULD NOT OPEN IT: `health.scribe.job` is readable by
    # the healthcare administrator, manager and owner permissions, and a branch
    # manager carries none of them. Measured by asking the permissions table
    # role by role, which is what H2b's door check does for every entry.
    'item_clin_voice_notes': (OWNER, OPS_MANAGER),
    # FINANCE
    'item_fin_bhyt_claims': (OWNER, ACCOUNTANT),
    'item_fin_service_packages': (OWNER, ACCOUNTANT),
    'item_fin_red_invoice_log': (OWNER, ACCOUNTANT),
}


def apply_role_gates(env):
    """Write the gate on the gated leaves. Idempotent, and never blinding.

    A role this deployment does not have is skipped rather than written as an
    empty set: ``[(6, 0, [])]`` would gate the leaf to NOBODY, which is a worse
    outcome than leaving it visible (the model's own permissions still refuse
    the data). If NONE of a leaf's roles exist, the leaf is left ungated and
    the fact is logged — silence there would hide a feature completely.
    """
    gated = skipped = 0
    for xmlid, role_xmlids in ROLE_GATES.items():
        item = env.ref('health_cms_coverage.%s' % xmlid,
                       raise_if_not_found=False)
        if not item:
            continue
        roles = env['biz.access.role'].sudo().browse()
        for role_xmlid in role_xmlids:
            role = env.ref(role_xmlid, raise_if_not_found=False)
            if role:
                roles |= role
        if not roles:
            skipped += 1
            _logger.warning(
                'health_cms_coverage: none of the roles %s exist on this '
                'database — leaving %s visible to every role rather than '
                'hiding it from everyone', list(role_xmlids), xmlid)
            continue
        if set(item.biz_role_ids.ids) != set(roles.ids):
            item.sudo().write({'biz_role_ids': [(6, 0, roles.ids)]})
        gated += 1
    _logger.info('health_cms_coverage: role-gated %s sidebar leaves '
                 '(%s left ungated for want of a role)', gated, skipped)
    return gated


# ==========================================================================
# MENU CONSOLIDATION (19.0.1.2.0)
#
# Menus whose records are now tabs on the client or booking record are retired,
# config leaves move to ADMIN, and the accumulated nav debt is cleaned.
#
# WHY PYTHON AND NOT AN XML EDIT
# ------------------------------
# `data/cms_sidebar_items_features.xml` is ``noupdate="1"`` (line 2), as are the
# health_cms_sidebar seeds this re-points. Editing those records has no effect
# on upgrade - the rows have to be written. Same reason apply_role_gates exists.
#
# Runs from ``post_init_hook`` AND from the 19.0.1.2.0 migration, so a fresh
# install and an upgrade converge on the same sidebar. A migration alone would
# leave every NEW database with the un-consolidated menu.
#
# WHAT IS NOT DONE HERE
# ---------------------
# No action, model, field or backend ``ir.ui.menu`` is deleted. Only
# ``cms.sidebar.item`` rows change, and retirement is ``active = False`` rather
# than unlink, so it stays reversible and ``match_action_xmlids`` keeps
# resolving deep links for anyone holding one.
#
# FAIL-OPEN, like apply_role_gates: an xmlid this database does not have
# (module not installed) is skipped silently rather than raising.
# ==========================================================================


# --------------------------------------------------------------------------
# B1 — leaves whose records are now tabs on the client or booking record.
# The tab that replaces each one is named so this stays auditable.
# --------------------------------------------------------------------------
RETIRE = {
    # → Contacts, as a calendar view mode
    'health_cms_coverage.item_crm_followup_calendar': 'Contacts (calendar view)',
    # NB Campaign Review is NOT retired here. health_web_leads' sidebar seed is
    # noupdate="0", so an upgrade of that module rewrites the record and would
    # resurrect the leaf. It declares active="False" in its own seed instead.
    # → Booking › Telehealth
    'health_cms_coverage.item_ops_telehealth': 'Booking › Telehealth',
    # → Client › Booking Links
    'health_cms_coverage.item_ops_selfbooking': 'Client › Booking Links',
    # → Booking › Family Updates
    'health_cms_coverage.item_ops_family_links': 'Booking › Family Updates',
    # → Client › Diagnoses
    'health_cms_coverage.item_clin_diagnoses': 'Client › Diagnoses',
    # → Client › Care Plans
    'health_cms_sidebar.item_clin_careplan': 'Client › Care Plans',
    # → Client › Portal Access
    'health_cms_coverage.item_clin_patient_portal': 'Client › Portal Access',
    # → Booking › Visit Tasks
    'health_cms_coverage.item_clin_visit_tasks': 'Booking › Visit Tasks',
    # → Client › Alert Thresholds (health_cms_clinical tab, already shipped)
    'health_cms_sidebar.item_clin_vitals_thresholds': 'Client › Alert Thresholds',
    # → Client › Consents (health_cms_clinical tab, already shipped)
    'health_cms_sidebar.item_clin_consents_all': 'Client › Consents',
}

# --------------------------------------------------------------------------
# B2 — work queues kept, but slimmed. Family Messages stays: unread_ops_count
# and last_message_at exist to drive a cross-client reply queue, and deleting
# it would leave no way to see what needs a reply without opening each client.
# --------------------------------------------------------------------------
RENAME = {
    'health_cms_coverage.item_ops_family_messages': 'Family Inbox',
}

# --------------------------------------------------------------------------
# B4 — config tables move out of the daily-work sections into ADMIN.
#
# section_id + sequence + parent_id. ``match_action_xmlids`` is left alone so
# highlight resolution is unchanged.
#
# parent_id MUST be cleared, not just section_id. Four of these are seeded as
# CHILDREN of a clinical expander (Observation Types under "Vitals &
# Observations", Medication Catalog under "Medications (eMAR)", Form Templates
# under "Clinical Forms", Monitoring Devices under "Care Intelligence").
# Moving only section_id leaves them parented to an expander in a section they
# no longer belong to — they render nested in the wrong place, AND they still
# count as that expander's children, which silently blocks the B5 collapse
# below. Clearing parent_id is a no-op for the ones that are already roots.
# --------------------------------------------------------------------------
RELOCATE_TO_ADMIN = [
    # from CRM (roots)
    ('health_cms_coverage.item_crm_channels_setup', 110),
    ('health_cms_coverage.item_crm_reply_templates', 111),
    # NB Website Connector is NOT listed. health_web_leads' sidebar seed is
    # noupdate="0", so every upgrade of that module rewrites the record and
    # would drag it back into CRM (measured on UAT). It declares
    # section_admin in its own seed instead.
    # from CLINICAL (the first three are children of expanders)
    ('health_cms_sidebar.item_clin_vitals_types', 120),
    ('health_cms_sidebar.item_clin_emar_catalog', 121),
    ('health_cms_sidebar.item_clin_forms_templates', 122),
    ('health_cms_clinical.item_clin_devices', 123),
    ('health_cms_coverage.item_clin_consent_log', 124),
]

# --------------------------------------------------------------------------
# B5 — expanders left with one (or zero) navigable children after the above.
# An item with children is NON-NAVIGATING (cms_sidebar.js:141-147), so an
# expander wrapping a single leaf costs a pointless click. Deactivate the
# expander and promote the survivor to a root leaf at the expander's sequence.
# --------------------------------------------------------------------------
COLLAPSE = [
    # (expander xmlid, survivor xmlid)
    ('health_cms_sidebar.item_ops_staff',
     'health_cms_sidebar.item_ops_staff_timeoff'),
    ('health_cms_sidebar.item_clin_vitals',
     'health_cms_sidebar.item_clin_vitals_obs'),
    ('health_cms_sidebar.item_clin_forms',
     'health_cms_sidebar.item_clin_forms_instances'),
    ('health_cms_sidebar.item_clin_consents',
     'health_cms_sidebar.item_clin_consents_expiring'),
]

# Rows seeded then deactivated by the ops_schedule cutover. They are already
# active=False; this only makes sure they stay that way and are not children of
# a now-deactivated expander.
ALREADY_RETIRED = [
    'health_cms_sidebar.item_ops_staff_roster',
    'health_cms_sidebar.item_ops_staff_schedules',
]


# --------------------------------------------------------------------------
# Re-home the retired leaves' match targets onto the leaf that now owns them.
#
# WHY THIS IS NOT OPTIONAL. ``get_match_keys()`` filters ``active = True``
# (cms_sidebar_item.py), and the frontend feeds that payload into the
# custom-sidebar registry to decide "is this screen mine?". Retire a leaf and
# its action drops out of the allowlist — so opening that action drops the CMS
# shell entirely and dumps the user into the bare Odoo backend.
#
# The tab widgets navigate to precisely these actions (openInvite, openThread,
# openCondition, openCareplan, openAccess, openLink, openSession), so without
# this every consolidated tab would kick the user out of the CMS on click.
#
# Attaching them to the parent leaf also makes the highlight correct: viewing a
# telehealth session now lights up "Bookings", which is where the user
# conceptually is. Uses match_action_xmlids, never match_models — the model
# index is last-wins and would steal an existing leaf's highlight.
# --------------------------------------------------------------------------
ATTACH_MATCH = {
    # host leaf xml-id -> action xmlids it should now also answer for
    'health_cms_sidebar.item_ops_clients': (
        'health_self_booking.action_selfbook_invite',
        'health_careplan.action_health_careplan',
        'health_portal.action_portal_access',
        # A retired leaf's ENTIRE match_action_xmlids list has to be re-homed,
        # not just its action_xmlid: item_clin_patient_portal also answered for
        # the access log, and dropping it would strand that screen outside the
        # CMS shell. Caught on UAT by test_04.
        'health_portal.action_portal_access_log',
        'health_condition.action_health_condition',
        # Retired in favour of the health_cms_clinical tabs that already
        # shipped (Alert Thresholds / Consents on the ops client profile).
        'health_vitals.action_health_vitals_threshold',
        'health_consent.action_health_consent',
        # NB deliberately NOT health_family_messages.action_family_messages:
        # that leaf is KEPT (renamed "Family Inbox"), and the xmlid index is
        # last-wins — declaring it here would steal its own leaf's highlight.
    ),
    'health_cms_sidebar.item_ops_bookings': (
        'health_telehealth.action_telehealth_session',
        'health_family_link.action_family_link',
        'health_careplan.action_health_careplan_task',
    ),
    'health_cms_sidebar.item_crm_contacts': (
        'health_crm.action_crm_followup_calendar',
    ),
    # NB Campaign Review is NOT re-homed here. health_web_leads' sidebar seed
    # is noupdate="0", so every upgrade of that module rewrites the Web
    # Touchpoints record and would wipe anything appended from outside
    # (measured on UAT). It is declared in that module's own seed instead.
}


def _get(env, xmlid):
    """Resolve a sidebar item, or None when the module is not installed."""
    return env.ref(xmlid, raise_if_not_found=False)


def consolidate_sidebar(env):
    """Retire consolidated leaves, relocate config, collapse dead expanders."""
    admin = env.ref('health_cms_sidebar.section_admin',
                    raise_if_not_found=False)

    retired = relocated = collapsed = renamed = 0

    # Relationships is once again a first-class CRM workspace.  An older
    # consolidation retired that leaf and attached its action to Operations >
    # Clients.  When the leaf was restored both items claimed the same action;
    # the last-wins frontend index highlighted Clients.  Make ownership
    # exclusive and idempotent on both fresh installs and upgrades.
    relationships = _get(env, 'health_cms_coverage.item_crm_relationships')
    if relationships:
        relationships.write({'active': True})
    clients = _get(env, 'health_cms_sidebar.item_ops_clients')
    if clients:
        stale_action = 'health_crm.action_health_client_relation'
        matches = [
            value.strip()
            for value in (clients.match_action_xmlids or '').split(',')
            if value.strip() and value.strip() != stale_action
        ]
        clients.write({'match_action_xmlids': ','.join(matches)})

    # --- B1: retire leaves whose records are now record tabs -----------
    for xmlid, tab in RETIRE.items():
        item = _get(env, xmlid)
        if not item:
            _logger.info('Sidebar consolidation: %s absent, skipped.', xmlid)
            continue
        if item.active:
            item.write({'active': False})
            retired += 1
            _logger.info('Sidebar consolidation: retired %s -> %s', xmlid, tab)

    # --- B2: rename the queues that are KEPT ---------------------------
    for xmlid, new_name in RENAME.items():
        item = _get(env, xmlid)
        if item and item.name != new_name:
            item.write({'name': new_name})
            renamed += 1

    # --- B4: relocate config leaves to ADMIN ---------------------------
    if admin:
        for xmlid, sequence in RELOCATE_TO_ADMIN:
            item = _get(env, xmlid)
            if not item:
                continue
            # parent_id MUST be cleared, not just section_id — see the comment
            # on RELOCATE_TO_ADMIN. Leaving it set both mis-nests the leaf and
            # blocks the collapse of the expander it used to hang under.
            item.write({
                'section_id': admin.id,
                'parent_id': False,
                'sequence': sequence,
            })
            relocated += 1
    else:
        _logger.warning('Sidebar consolidation: ADMIN section missing, '
                        'config leaves left where they are.')

    # --- B5: collapse expanders left with a single child ---------------
    # An item WITH children is non-navigating (cms_sidebar.js onItemClick), so
    # an expander wrapping one leaf costs a pointless click.
    for expander_xmlid, survivor_xmlid in COLLAPSE:
        expander = _get(env, expander_xmlid)
        survivor = _get(env, survivor_xmlid)
        if not expander or not survivor or not expander.active:
            continue
        siblings = env['cms.sidebar.item'].search([
            ('parent_id', '=', expander.id),
            ('active', '=', True),
        ])
        if len(siblings) > 1:
            _logger.info('Sidebar consolidation: %s still has %s active '
                         'children, not collapsing.',
                         expander_xmlid, len(siblings))
            continue
        survivor.write({
            'parent_id': False,
            'section_id': expander.section_id.id,
            'sequence': expander.sequence,
        })
        expander.write({'active': False})
        collapsed += 1

    # --- Re-home the retired leaves' match targets ---------------------
    # Must run AFTER retirement: these keep the CMS shell (and the highlight)
    # on screens whose own leaf no longer exists. See ATTACH_MATCH.
    attached = 0
    for host_xmlid, action_xmlids in ATTACH_MATCH.items():
        host = _get(env, host_xmlid)
        if not host:
            _logger.info('Sidebar consolidation: match host %s absent, the '
                         'actions it would adopt keep no CMS shell.',
                         host_xmlid)
            continue
        declared = [v.strip() for v in (host.match_action_xmlids or '').split(',')
                    if v.strip()]
        for action_xmlid in action_xmlids:
            # Only adopt actions this database actually has, and never
            # duplicate an entry on re-run.
            if action_xmlid in declared:
                continue
            if not env.ref(action_xmlid, raise_if_not_found=False):
                continue
            declared.append(action_xmlid)
            attached += 1
        host.write({'match_action_xmlids': ','.join(declared)})

    # --- B5: keep the ops_schedule cutover corpses down ----------------
    for xmlid in ALREADY_RETIRED:
        item = _get(env, xmlid)
        if item and item.active:
            item.write({'active': False})

    _logger.info('CMS sidebar consolidation: %s retired, %s relocated to '
                 'ADMIN, %s expanders collapsed, %s renamed, %s match '
                 'targets re-homed.',
                 retired, relocated, collapsed, renamed, attached)
    return retired


def post_init_hook(env):
    apply_role_gates(env)
    consolidate_sidebar(env)
