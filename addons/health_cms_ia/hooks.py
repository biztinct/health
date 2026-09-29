# -*- coding: utf-8 -*-
"""The consolidated left menu — every move, rename and gate, as tables.

WHAT THIS IS. MENU IA phase M2 (`docs/handovers/MENU_M2_CONSOLIDATION.md`).
Phase M1 drew the menu as a rail (one entry per SECTION), a tab column (the
section's ROOT entries) and a strip of segments (a root's CHILDREN). This fills
it: the 115 entries regrouped into nine areas and about fifty tabs, and every
entry given the roles that open it (the owner's gate matrix, §2b).

WHY PYTHON AND NOT A DATA FILE. Most of the rows are `noupdate="1"` in the
module that seeds them, so an upgrade never re-writes them and an XML edit here
would reach no database that already has them (ledger §5.116). The rows are
WRITTEN, from the install hook — and from a migration of this module, so a
later version can call the same function and converge.

THE ROWS THAT RE-ASSERT THEMSELVES. Eight seeds are `noupdate="0"`: every
upgrade of their module re-writes what they name. Those seeds were edited in
their own modules to name the FINAL place (and to stop naming `parent_id`
where the parent is one of this module's headings, which they cannot point at —
they load first). What the hook writes on those rows is therefore either the
same value the seed now says or a field the seed does not name, so an upgrade
of the seed module is a no-op for the move (test_03 parses every seed and
proves it).

IDEMPOTENT BY COMPARISON. Every writer reads the value first and writes only
what differs, so a second run changes nothing and logs zeros (test_01). The
GATES are also decided ONCE PER ENTRY (the AR-2 rule, `health_access`
`_gate_new_items`): an entry the hook has gated is written down, and a later
run leaves it exactly as whoever last changed it on the Screens lens left it.

FAIL-OPEN. A row whose module is not on this database is skipped and counted,
never raised on. A role that is not on this database is skipped; an entry is
never gated to NOBODY by accident (an empty gate means "everybody").

THE GATE RULE (§2b, owner rulings 2026-09-29). For every entry of the six
areas this module manages:

    wanted = (what it has today, or — when it has nothing — the area's roles,
              or the exact roles the ruling names for it)
             ∪ Owner ∪ Admin                        ("Owner and Admin keep
                                                      everything")
             ∪ the area's widening (Clinical: Doctor — Q6)
             ∪ the entry's own extras (Bookings: Doctor, Nurse; …)

and a role ADDED by this rule is kept only if its holders can actually open the
screen behind the entry (the door check, `role_can_read` — the AR-2 rule that
nobody is shown a door that refuses them). Nothing a role has today is ever
taken away by the check.

TWO ENTRIES STAY UNGATED ON PURPOSE: the Learn area's Training journey (the
owner's single deliberate exception — everybody may learn) and Home (it is not
a screen, it opens each person's own landing, and a rail that could draw no
Home would strand somebody with no way back).

HEADINGS ARE NOT GATED HERE. A heading with no screen and no roles of its own
is opened by whoever opens something inside it (`health_access`), which is the
only way one tab can hold screens for different people: a gate ON the heading
would flow down to every screen inside it and widen them all.

WHY NO GATE ON A SECTION. A block's gate is a union that no entry inside it can
narrow — "Operations Manager on the CRM block" would have opened Web & Ads to
them, "Admin on Settings" would have opened Customers. So the area's roles are
written on its tabs, one by one, where each can be narrowed.
"""

import logging

from odoo import SUPERUSER_ID

from .menu_vi import apply_names_vi

_logger = logging.getLogger(__name__)

M = 'health_cms_ia'

# =============================================================================
# THE ROLES, by fixed name.
# =============================================================================
OWNER = 'health_access.role_owner'
ADMIN = 'health_access.role_admin'
OPS = 'health_access.role_operations_manager'
BRANCH = 'health_access.role_branch_manager'
NURSE = 'health_access.role_nurse'
DOCTOR = 'health_access.role_doctor'
ACCOUNTANT = 'health_access.role_accountant'
CRM = 'health_access.role_crm'

# =============================================================================
# B — THE AREA NAMES. Display names only; keys, xml-ids and sequences stay.
# The Analytics block's name is its own updatable seed's (`biz_bi_cms`), which
# says "Analytics" now; it is listed so a database where that module has not
# been upgraded yet converges too.
# =============================================================================
SECTION_NAMES = {
    'health_cms_sidebar.section_crm': 'CRM',
    'health_cms_sidebar.section_ops': 'Operations',
    'health_cms_sidebar.section_finance': 'Finance',
    'health_cms_sidebar.section_clinical': 'Clinical',
    'health_cms_sidebar.section_interop': 'Compliance',
    'biz_bi_cms.section_analytics': 'Analytics',
    'health_cms_sidebar.section_admin': 'Settings',
}

# =============================================================================
# RENAMES — the words on a tab or a segment. English only; the Vietnamese is
# AR-3's. Every one of these rows is `noupdate="1"` except the two Analytics
# rows, whose seed says the same.
# =============================================================================
RENAME = {
    # CRM
    'health_cms_sidebar.item_crm_contacts': 'All contacts',
    # Operations
    'health_cms_coverage.item_ops_route_feasibility': 'Routes',
    # Clinical
    'health_cms_clinical.item_clin_worklist': 'Worklist',
    'health_cms_clinical.item_clin_alerts': 'Alerts',
    'health_cms_clinical.item_clin_news2': 'NEWS2',
    'health_cms_sidebar.item_clin_emar': 'Medications',
    'health_cms_sidebar.item_clin_emar_orders': 'Orders',
    'health_cms_sidebar.item_clin_incidents_register': 'Register',
    'health_cms_sidebar.item_clin_consents_expiring': 'Consents',
    # Finance
    'health_cms_sidebar.item_fin_payments': 'All payments',
    # Compliance
    'health_cms_sidebar.item_int_terminology': 'Terminology',
    'health_cms_sidebar.item_int_emr_export': 'Export',
    'health_cms_sidebar.item_int_emr_readiness': 'Readiness',
    # Analytics (the seed says the same — see above)
    'biz_bi_cms.item_analytics_data': 'Data',
    # Learn
    'health_access.item_admin_training': 'Training admin',
    # Settings
    'health_cms_sidebar.item_admin_dashboard': 'Overview',
    'health_cms_sidebar.item_admin_master_data': 'Facilities',
    'health_cms_sidebar.item_admin_cms_sidebar': 'Menu',
}

# =============================================================================
# C — THE MOVES. xml-id -> (section, parent or None, sequence).
#
# A parent named `health_cms_ia.parent_*` is one of this module's headings
# (`data/cms_sidebar_tabs.xml`). None = a root (a tab). Sequences are the
# target ones, in tens, unique per level.
# =============================================================================
S_CRM = 'health_cms_sidebar.section_crm'
S_OPS = 'health_cms_sidebar.section_ops'
S_FIN = 'health_cms_sidebar.section_finance'
S_CLIN = 'health_cms_sidebar.section_clinical'
S_INT = 'health_cms_sidebar.section_interop'
S_BI = 'biz_bi_cms.section_analytics'
S_ADMIN = 'health_cms_sidebar.section_admin'

P_CHANNELS = M + '.parent_crm_channels'
P_CONTACTS = M + '.parent_crm_contacts'
P_WEB = M + '.parent_crm_web'
P_PHONE = 'health_care_command_voip.item_phone'
P_SCHEDULE = M + '.parent_ops_schedule'
P_EXCEPTIONS = M + '.parent_ops_exceptions'
P_DEVELOPMENT = M + '.parent_ops_development'
P_CARE_INTEL = 'health_cms_clinical.item_clin_care_intel'
P_EMAR = 'health_cms_sidebar.item_clin_emar'
P_INCIDENTS = 'health_cms_sidebar.item_clin_incidents'
P_NOTES = M + '.parent_clin_notes'
P_RECEIVABLES = M + '.parent_fin_receivables'
P_PAYMENTS = M + '.parent_fin_payments'
P_TERMINOLOGY = 'health_cms_sidebar.item_int_terminology'
P_EMR = M + '.parent_int_emr'
P_DATA = 'biz_bi_cms.item_analytics_data'
P_PEOPLE = M + '.parent_admin_people'
P_MASTER = M + '.parent_admin_master'
P_CONNECTIONS = M + '.parent_admin_connections'
P_RECORDS = M + '.parent_admin_records'

MOVE = {
    # ------------------------------------------------------------------ CRM
    # 10 Dashboard stays where it is.
    'health_care_command.item_care_command': (S_CRM, None, 20),
    'health_care_command_channels.item_channel_center': (S_CRM, P_CHANNELS, 10),
    'health_care_command_channels.item_contact_capture': (S_CRM, P_CHANNELS, 20),
    'health_access.item_crm_channel_audit': (S_CRM, P_CHANNELS, 30),
    'health_access.item_crm_channel_messages': (S_CRM, P_CHANNELS, 40),
    'health_access.item_crm_watch_phrases': (S_CRM, P_CHANNELS, 50),
    P_PHONE: (S_CRM, None, 40),
    'health_care_command_voip.item_phone_calls': (S_CRM, P_PHONE, 10),
    'health_care_command_voip.item_phone_callbacks': (S_CRM, P_PHONE, 20),
    'health_care_command_voip.item_phone_recordings': (S_CRM, P_PHONE, 30),
    'health_care_command_voip.item_phone_records': (S_CRM, P_PHONE, 40),
    'health_cms_sidebar.item_crm_contacts': (S_CRM, P_CONTACTS, 10),
    'health_cms_coverage.item_crm_relationships': (S_CRM, P_CONTACTS, 20),
    'health_cms_sidebar.item_crm_activities': (S_CRM, None, 60),
    'health_web_leads.item_web_touchpoints': (S_CRM, P_WEB, 10),
    'health_web_leads.item_lead_analysis': (S_CRM, P_WEB, 20),
    'health_google_ads.item_google_ads': (S_CRM, P_WEB, 30),
    # ----------------------------------------------------------- Operations
    # 10 Dashboard, 20 Bookings, 30 Clients stay.
    'health_cms_sidebar.item_ops_roster': (S_OPS, P_SCHEDULE, 10),
    'health_cms_sidebar.item_ops_staff_timeoff': (S_OPS, P_SCHEDULE, 20),
    'health_cms_sidebar.item_ops_workload': (S_OPS, P_SCHEDULE, 30),
    'health_cms_sidebar.item_ops_collections': (S_OPS, None, 50),
    'health_cms_coverage.item_ops_family_messages': (S_OPS, None, 60),
    'health_cms_coverage.item_ops_route_feasibility': (S_OPS, None, 70),
    'health_access.item_ops_visit_offers': (S_OPS, P_EXCEPTIONS, 10),
    'health_access.item_ops_timecard_mismatches': (S_OPS, P_EXCEPTIONS, 20),
    'health_access.item_ops_employee_development': (S_OPS, P_DEVELOPMENT, 10),
    'health_access.item_ops_coaching': (S_OPS, P_DEVELOPMENT, 20),
    # ------------------------------------------------------------- Clinical
    # 10 Observations, 30 Medications, 40 Assessments, 50 Incidents,
    # 60 Consents stay.
    P_CARE_INTEL: (S_CLIN, None, 20),
    'health_cms_clinical.item_clin_worklist': (S_CLIN, P_CARE_INTEL, 10),
    'health_cms_clinical.item_clin_alerts': (S_CLIN, P_CARE_INTEL, 20),
    'health_cms_clinical.item_clin_news2': (S_CLIN, P_CARE_INTEL, 30),
    'health_cms_sidebar.item_clin_emar_orders': (S_CLIN, P_EMAR, 10),
    'health_cms_sidebar.item_clin_emar_admin': (S_CLIN, P_EMAR, 20),
    'health_cms_sidebar.item_clin_incidents_register': (S_CLIN, P_INCIDENTS, 10),
    'health_cms_sidebar.item_clin_incidents_actions': (S_CLIN, P_INCIDENTS, 20),
    'health_cms_sidebar.item_clin_incidents_analysis': (S_CLIN, P_INCIDENTS, 30),
    'health_cms_coverage.item_clin_unsigned_notes': (S_CLIN, P_NOTES, 10),
    'health_cms_coverage.item_clin_voice_notes': (S_CLIN, P_NOTES, 20),
    'health_cms_coverage.item_clin_coding_review': (S_CLIN, P_NOTES, 30),
    # -------------------------------------------------------------- Finance
    # 10 Dashboard, 20 Invoices stay.
    'health_cms_sidebar.item_fin_ar_dashboard': (S_FIN, P_RECEIVABLES, 10),
    'health_cms_sidebar.item_fin_ar_transactions': (S_FIN, P_RECEIVABLES, 20),
    'health_cms_sidebar.item_fin_overdue': (S_FIN, P_RECEIVABLES, 30),
    'health_cms_sidebar.item_fin_payments': (S_FIN, P_PAYMENTS, 10),
    'health_cms_sidebar.item_fin_ar_account_payment': (S_FIN, P_PAYMENTS, 20),
    'health_cms_sidebar.item_fin_ar_cash_transit': (S_FIN, P_PAYMENTS, 30),
    'health_cms_sidebar.item_fin_ar_refund': (S_FIN, P_PAYMENTS, 40),
    'health_cms_sidebar.item_fin_vat_log': (S_FIN, None, 50),
    'health_cms_coverage.item_fin_bhyt_claims': (S_FIN, None, 60),
    'health_cms_coverage.item_fin_service_packages': (S_FIN, None, 70),
    'health_cms_coverage.item_fin_red_invoice_log': (S_FIN, None, 80),
    # ----------------------------------------------------------- Compliance
    P_TERMINOLOGY: (S_INT, None, 10),
    'health_cms_sidebar.item_int_term_codes': (S_INT, P_TERMINOLOGY, 10),
    'health_cms_sidebar.item_int_term_systems': (S_INT, P_TERMINOLOGY, 20),
    'health_cms_sidebar.item_int_term_import': (S_INT, P_TERMINOLOGY, 30),
    'health_cms_sidebar.item_int_emr_export': (S_INT, P_EMR, 10),
    'health_cms_sidebar.item_int_emr_readiness': (S_INT, P_EMR, 20),
    'health_cms_sidebar.item_int_messaging': (S_INT, None, 30),
    'health_cms_sidebar.item_int_evv': (S_INT, None, 40),
    # ------------------------------------------------------------ Analytics
    # The seed (`biz_bi_cms`, noupdate="0") says the same; listed so a
    # database where that module has not been upgraded converges too.
    'biz_bi_cms.item_analytics_refresh': (S_BI, P_DATA, 30),
    'biz_bi_cms.item_analytics_pipelines': (S_BI, P_DATA, 40),
    'biz_bi_cms.item_analytics_model': (S_BI, P_DATA, 50),
    'biz_bi_cms.item_analytics_glossary': (S_BI, P_DATA, 60),
    'biz_bi_cms.item_analytics_import': (S_BI, P_DATA, 70),
    # ------------------------------------------------------------- Settings
    # 10 Overview stays.
    'health_cms_sidebar.item_admin_users': (S_ADMIN, P_PEOPLE, 10),
    'health_access.item_admin_access': (S_ADMIN, P_PEOPLE, 20),
    'health_cms_sidebar.item_admin_staff': (S_ADMIN, P_PEOPLE, 30),
    'health_cms_sidebar.item_admin_master_data': (S_ADMIN, P_MASTER, 10),
    'health_cms_sidebar.item_admin_pricing': (S_ADMIN, P_MASTER, 20),
    'health_cms_sidebar.item_admin_equipment': (S_ADMIN, P_MASTER, 30),
    'health_cms_sidebar.item_admin_holidays': (S_ADMIN, P_MASTER, 40),
    'health_cms_sidebar.item_clin_vitals_types': (S_ADMIN, P_MASTER, 50),
    'health_cms_sidebar.item_clin_emar_catalog': (S_ADMIN, P_MASTER, 60),
    'health_cms_sidebar.item_clin_forms_templates': (S_ADMIN, P_MASTER, 70),
    'health_cms_clinical.item_clin_devices': (S_ADMIN, P_MASTER, 80),
    'health_cms_sidebar.item_admin_field_req': (S_ADMIN, P_MASTER, 90),
    'health_cms_coverage.item_crm_channels_setup': (S_ADMIN, P_CONNECTIONS, 10),
    'health_cms_coverage.item_crm_reply_templates': (S_ADMIN, P_CONNECTIONS, 20),
    'health_care_command_channels.item_golive_studio': (S_ADMIN, P_CONNECTIONS, 30),
    'health_web_leads.item_web_leads_connector': (S_ADMIN, P_CONNECTIONS, 40),
    'health_google_ads.item_google_ads_platform': (S_ADMIN, P_CONNECTIONS, 50),
    'health_care_command_voip.item_phone_settings': (S_ADMIN, P_CONNECTIONS, 60),
    'health_care_command_voip.item_phone_extensions': (S_ADMIN, P_CONNECTIONS, 70),
    'health_cms_sidebar.item_admin_audit': (S_ADMIN, P_RECORDS, 10),
    'health_cms_sidebar.item_admin_data_lifecycle': (S_ADMIN, P_RECORDS, 20),
    'health_cms_coverage.item_clin_consent_log': (S_ADMIN, P_RECORDS, 30),
    'health_cms_sidebar.item_admin_cms_sidebar': (S_ADMIN, None, 60),
    'health_cms_sidebar.item_admin_settings': (S_ADMIN, None, 70),
    'health_tenancy.item_admin_about': (S_ADMIN, None, 80),
    'health_tenancy.item_admin_customers': (S_ADMIN, None, 90),
}

# =============================================================================
# RETIRED — switched off, never deleted, and the screen it opened is claimed by
# the heading that now holds what it held (MATCH_EXTRA), so a deep link to it
# keeps the shell and lights the right tab.
#
# AR Management was a launcher of exactly three cards — Account Payment, Cash
# In Transit, Refund / Credit — which are now three segments of Payments,
# beside the payments list itself.
# =============================================================================
RETIRE = {
    'health_cms_sidebar.item_fin_ar_management': P_PAYMENTS,
}

# Screens a heading answers for beyond its own children's (§5.150: the leaf's
# own action is still matched first, so this only decides the unclaimed).
MATCH_EXTRA = {
    P_PAYMENTS: {
        'xmlids': ('health_invoicing.action_fin_ar_management',),
        'tags': ('fin_ar_management',),
    },
}

# A screen somebody else merely BORROWED while it had no entry of its own.
# The highlight index is last-wins, so the borrower would steal it.
RELEASE = {
    'health_cms_coverage.item_crm_reply_templates': (
        'health_care_command.action_care_watch_phrase',),
}

# =============================================================================
# D — THE GATES (§2b). See the module docstring for the rule.
# =============================================================================
#: The areas this module gates. Analytics is "as today" (`biz_bi_cms` owns and
#: re-decides it); Home and Learn are left as they are (see the docstring).
AREA_ROLES = {
    S_CRM: (CRM, OWNER, ADMIN, OPS),
    S_OPS: (OWNER, ADMIN, OPS, BRANCH),
    S_CLIN: (DOCTOR, OWNER, ADMIN),
    S_FIN: (ACCOUNTANT, OWNER, ADMIN),
    S_INT: (OWNER, ADMIN, DOCTOR),
    S_ADMIN: (OWNER, ADMIN),
}

#: "Owner and Admin keep everything."
ALWAYS = (OWNER, ADMIN)

#: An area that OPENS WIDER than its entries do today (Q6: the Clinical area
#: opens for Doctor, Owner and Admin; the entry gates inside follow).
WIDEN = {
    S_CLIN: (DOCTOR,),
}

#: The roles the ruling names outright for an entry that has no gate today —
#: used instead of the area's roles.
EXACT = {
    'health_care_command_channels.item_channel_center': (CRM, OWNER, OPS),
    'health_care_command_channels.item_contact_capture': (CRM, OWNER, OPS),
    'health_web_leads.item_web_touchpoints': (CRM, OWNER),
    'health_web_leads.item_lead_analysis': (CRM, OWNER),
    'health_google_ads.item_google_ads': (CRM, OWNER),
    # Phone: the roles holding "Handle calls" (given below).
    'health_care_command_voip.item_phone_calls': (OWNER, CRM, OPS),
    'health_care_command_voip.item_phone_callbacks': (OWNER, CRM, OPS),
    'health_care_command_voip.item_phone_recordings': (OWNER, CRM, OPS),
    'health_care_command_voip.item_phone_records': (OWNER, CRM, OPS),
    # Settings: the roles holding "Set up the phone system", and the set-up
    # screens the ruling names.
    'health_care_command_voip.item_phone_settings': (OWNER, ADMIN),
    'health_care_command_voip.item_phone_extensions': (OWNER, ADMIN),
    'health_cms_sidebar.item_admin_settings': (OWNER, ADMIN),
    'health_cms_sidebar.item_admin_data_lifecycle': (OWNER, ADMIN),
    'health_care_command_channels.item_golive_studio': (OWNER, ADMIN),
    'health_web_leads.item_web_leads_connector': (OWNER, ADMIN),
}

#: Roles an entry opens for ON TOP of everything above.
EXTRA = {
    'health_cms_sidebar.item_ops_bookings': (DOCTOR, NURSE),
    'health_cms_sidebar.item_ops_clients': (DOCTOR, NURSE),
    'health_cms_sidebar.item_ops_roster': (NURSE,),
    'health_cms_sidebar.item_ops_staff_timeoff': (NURSE,),
    'health_cms_sidebar.item_ops_workload': (NURSE,),
}

PLATFORM_ONLY_GOOGLE_ADS = 'health_google_ads.item_google_ads_platform'

#: Left exactly as they are.
UNTOUCHED = (
    # "Customers stays Owner-only" — the platform's own list of clinics.
    'health_tenancy.item_admin_customers',
    # The page a switched-off part of the product lands on; never a menu row.
    'health_tenancy.item_feature_off_shell',
    # The platform's own Google Ads application (owner ruling 2026-09-29,
    # AR-3 G2): drawn for the platform administrator ONLY, by
    # `health_access.PLATFORM_ONLY_ITEMS`, so it carries no role at all.
    PLATFORM_ONLY_GOOGLE_ADS,
)

#: The records a DASHBOARD reads, for the door check. A client action has no
#: model of its own to ask the permissions table about, so "could this role
#: open it" is asked of the records the screen is built from.
DOOR_MODELS = {
    'health_crm.action_crm_dashboard': 'crm.lead',
    'health_care_command.action_care_command': 'care.conversation',
    'health_care_command_channels.action_channel_center':
        'care.channel.connection',
    'health_care_command_channels.action_channel_golive_studio':
        'care.channel.connection',
    'health_fieldservice.action_ops_command_center':
        'health.fieldservice.order',
    'health_fieldservice.action_staff_workload_dashboard':
        'health.staff.assignment',
    'health_invoicing.action_fin_dashboard': 'account.move',
    'hr_development_ai.action_hr_development_dashboard': 'hr.employee',
    'hr_development_ai.action_bfsi_coaching_workspace': 'hr.employee',
}

#: The entries this hook has gated — not a "this ran" stamp but the list of
#: individual entries whose gate is now somebody's to change by hand (AR-2).
GATE_HANDLED_PARAM = 'health_cms_ia.gated_items_handled'

# =============================================================================
# THE PHONE ABILITIES (from AR-2, until now held by nobody).
# ability key -> the roles it is written onto.
# =============================================================================
PHONE_ABILITIES = {
    'calls-handle': (OWNER, CRM, OPS),
    'phone-setup': (OWNER, ADMIN),
}
PHONE_REASON = ('the phone screens on the consolidated menu (owner ruling, '
                'menu phase M2)')

# =============================================================================
# AR-3 — THE M2 FOLLOW-UPS (owner rulings 2026-09-29).
# =============================================================================
#: G1: the Doctor role reads the clinic's patients and visits, so the Bookings
#: tab (EXTRA above) opens for a doctor. The door check refused it in M2: the
#: bookings model was readable only by the nursing tier and up. `health_access`
#: now gives the doctor tier read access to the visits arranged for them.
DOCTOR_ABILITIES = {
    'care-base': (DOCTOR,),
}
DOCTOR_REASON = ('the Bookings tab for doctors (owner ruling 2026-09-29, '
                 'access phase AR-3)')
#: G1: the entries a doctor is added to once the door opens, and only then.
DOCTOR_ENTRIES = ('health_cms_sidebar.item_ops_bookings',)


# =============================================================================
# helpers
# =============================================================================
def _ref(env, xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


def _item(env, xmlid):
    rec = _ref(env, xmlid)
    if rec and rec._name == 'cms.sidebar.item':
        return rec.sudo().with_context(active_test=False)
    return None


def _roles(env, xmlids):
    Role = env['biz.access.role'].sudo().with_context(active_test=False)
    out = Role.browse()
    for xmlid in xmlids or ():
        role = _ref(env, xmlid)
        if role:
            out |= role
    return out


def _split(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


def _xmlid_of(env, record):
    return record.get_external_id().get(record.id) or str(record.id)


# =============================================================================
# 1. THE PHONE ABILITIES, onto the roles — nobody stops holding their role.
# =============================================================================
def grant_phone_abilities(env):
    """Write "Handle calls" and "Set up the phone system" onto their roles."""
    return grant_abilities(env, PHONE_ABILITIES, PHONE_REASON)


def grant_abilities(env, table, reason):
    """Write each ability of `table` (`{key: role xml-ids}`) onto its roles.

    THE `_carry_analytics` LESSON (health_access): adding an ability makes a
    role BIGGER, and holding a role means holding all of it — so the people who
    held the role a moment ago would STOP holding it and lose every entry it
    opens. So the people to give the new permission to are worked out from the
    role WITHOUT it (everybody holding every OTHER permission in it), and each
    is given it through the roles board's own grant, which adds only the
    missing part and writes the history row ("audit line").

    Idempotent and self-repairing: a second run finds the ability on the role
    and nobody missing it, and writes nothing.
    """
    Ability = env['biz.access.ability'].sudo().with_context(active_test=False)
    facade = env['biz.access'].sudo().with_user(SUPERUSER_ID)
    Users = env['res.users'].sudo()
    report = {'roles': [], 'people': []}
    for key, role_xmlids in table.items():
        ability = Ability.search([('technical_key', '=', key)], limit=1)
        if not ability or not ability.group_ids:
            _logger.warning('health_cms_ia: the "%s" ability is not on this '
                            'database; no role was given it', key)
            continue
        for role in _roles(env, role_xmlids):
            needed = set((role.group_ids - ability.group_ids).ids)
            due = []
            if needed:
                for user in Users.search([('active', '=', True),
                                          ('share', '=', False)]):
                    held = set(user.all_group_ids.ids)
                    if needed <= held and not set(ability.group_ids.ids) <= held:
                        due.append(user)
            if ability not in role.ability_ids:
                role.write({'ability_ids': [(4, ability.id)]})
                report['roles'].append('%s +%s' % (role.name, ability.name))
                _logger.info('health_cms_ia: role "%s" now carries "%s"',
                             role.name, ability.name)
            for user in due:
                if user.id == SUPERUSER_ID:
                    continue
                if set(role.group_ids.ids) <= set(user.all_group_ids.ids):
                    continue
                try:
                    facade.grant(role.id, user.id, reason=reason)
                    user.invalidate_recordset(['group_ids', 'all_group_ids'])
                    report['people'].append('%s (%s)' % (user.login, role.name))
                except Exception:                               # noqa: BLE001
                    _logger.warning(
                        'health_cms_ia: %s could not be given the rest of '
                        '"%s"', user.login, role.name, exc_info=True)
    _logger.info('health_cms_ia: abilities (%s) — %s role change(s): %s; %s '
                 'person(s) given the missing permission so as to keep their '
                 'role: %s', reason, len(report['roles']),
                 ', '.join(report['roles']) or 'none', len(report['people']),
                 ', '.join(report['people']) or 'none')
    return report


# =============================================================================
# 2. B + C — names, positions, retirements, match lists.
# =============================================================================
def apply_names(env, log):
    for xmlid, name in SECTION_NAMES.items():
        section = _ref(env, xmlid)
        if not section:
            continue
        section = section.sudo().with_context(lang='en_US', active_test=False)
        if section.name != name:
            log['section_renames'].append('%s: %s -> %s'
                                          % (xmlid, section.name, name))
            section.write({'name': name})
    for xmlid, name in RENAME.items():
        item = _item(env, xmlid)
        if not item:
            log['missing'].append(xmlid)
            continue
        item = item.with_context(lang='en_US')
        if item.name != name:
            log['renames'].append('%s: %s -> %s' % (xmlid, item.name, name))
            item.write({'name': name})


def apply_moves(env, log):
    for xmlid, (section_xmlid, parent_xmlid, sequence) in MOVE.items():
        item = _item(env, xmlid)
        section = _ref(env, section_xmlid)
        if not item or not section:
            log['missing'].append(xmlid)
            continue
        parent = _item(env, parent_xmlid) if parent_xmlid else None
        if parent_xmlid and not parent:
            log['missing'].append('%s (parent %s)' % (xmlid, parent_xmlid))
            continue
        vals = {}
        if item.section_id != section:
            vals['section_id'] = section.id
        want_parent = parent.id if parent else False
        if (item.parent_id.id or False) != want_parent:
            vals['parent_id'] = want_parent
        if item.sequence != sequence:
            vals['sequence'] = sequence
        if vals:
            log['moves'].append('%s: %s' % (xmlid, ', '.join(
                '%s %s->%s' % (k, _was(item, k), vals[k]) for k in vals)))
            item.write(vals)


def _was(item, field):
    value = item[field]
    return value.id if hasattr(value, 'id') else value


def apply_retirements(env, log):
    for xmlid in RETIRE:
        item = _item(env, xmlid)
        if not item:
            continue
        # Anything still under it goes first (it should have been moved).
        kids = env['cms.sidebar.item'].sudo().search(
            [('parent_id', '=', item.id), ('active', '=', True)])
        if kids:
            log['missing'].append('%s still has %s child(ren); not retired'
                                  % (xmlid, len(kids)))
            continue
        if item.active:
            item.write({'active': False})
            log['retired'].append(xmlid)


def apply_matches(env, log):
    """A heading answers for the screens nobody else owns (MATCH_EXTRA), and
    a borrower hands back what it borrowed (RELEASE).

    §5.150: the leaf whose OWN action is on display wins over any entry that
    merely lists it. Written on this module's own headings only.
    """
    Item = env['cms.sidebar.item'].sudo()
    rows = env['ir.model.data'].sudo().search(
        [('module', '=', M), ('model', '=', 'cms.sidebar.item')])
    for row in rows:
        parent = Item.with_context(active_test=False).browse(row.res_id).exists()
        if not parent:
            continue
        xmlid = '%s.%s' % (M, row.name)
        # NOT the children's own screens: the M1 resolver indexes every
        # screen inside a tab with that tab as its root (`_buildMatchIndex`),
        # so opening one already lights the tab — and a second entry claiming
        # the same screen is exactly what `health_cms_coverage` test_04b
        # forbids. Only what no entry owns any more is claimed.
        xmlids, tags = [], []
        extra = MATCH_EXTRA.get(xmlid) or {}
        for value in extra.get('xmlids', ()):
            if value not in xmlids and _ref(env, value):
                xmlids.append(value)
        for value in extra.get('tags', ()):
            if value not in tags:
                tags.append(value)
        vals = {}
        if _split(parent.match_action_xmlids) != xmlids:
            vals['match_action_xmlids'] = ','.join(xmlids)
        if _split(parent.match_action_tags) != tags:
            vals['match_action_tags'] = ','.join(tags)
        if vals:
            log['matches'].append(xmlid)
            parent.write(vals)
    for host_xmlid, released in RELEASE.items():
        host = _item(env, host_xmlid)
        if not host:
            continue
        declared = _split(host.match_action_xmlids)
        kept = [v for v in declared if v not in released]
        if kept != declared:
            host.write({'match_action_xmlids': ','.join(kept)})
            log['released'].append('%s: %s' % (host_xmlid, ', '.join(
                v for v in declared if v in released)))


def settle_headings(env, log):
    """A heading of ours with nothing inside it is switched off, and one that
    has something inside it again is switched back on (a module installed
    later). Children first is not needed: this module's headings hold leaves.
    """
    Item = env['cms.sidebar.item'].sudo()
    rows = env['ir.model.data'].sudo().search(
        [('module', '=', M), ('model', '=', 'cms.sidebar.item')])
    for row in rows:
        heading = Item.with_context(active_test=False).browse(row.res_id).exists()
        if not heading:
            continue
        alive = bool(Item.search_count([('parent_id', '=', heading.id),
                                        ('active', '=', True)]))
        if heading.active != alive:
            heading.write({'active': alive})
            log['headings'].append('%s.%s %s' % (M, row.name,
                                                 'on' if alive else 'off'))


# =============================================================================
# 3. D — THE GATES.
# =============================================================================
def _gate_handled(env):
    raw = env['ir.config_parameter'].sudo().get_param(GATE_HANDLED_PARAM) or ''
    return {int(x) for x in raw.split(',') if x.strip().isdigit()}


def _mark_gate_handled(env, ids):
    ids = {int(i) for i in ids if i}
    already = _gate_handled(env)
    if ids <= already:
        return
    env['ir.config_parameter'].sudo().set_param(
        GATE_HANDLED_PARAM, ','.join(str(i) for i in sorted(already | ids)))


def door_model(env, item):
    """The records the screen behind an entry opens, or '' for none known."""
    from odoo.addons.health_access.models.cms_sidebar import _model_behind
    if item.action_xmlid and item.action_xmlid in DOOR_MODELS:
        model = DOOR_MODELS[item.action_xmlid]
        return model if model in env else ''
    return _model_behind(env, item)


def can_open(env, role, item):
    """Could somebody holding `role` open the screen behind `item`?"""
    from odoo.addons.health_access.hooks import role_can_read
    model = door_model(env, item)
    if not model:
        return True
    return role_can_read(env, role, model)


def _is_heading(item):
    return not item.action_xmlid and not item.action_tag


def gate_targets(env):
    """The entries the gate rule writes on, as `{id: xml-id}`.

    Every entry of the six managed areas, EXCEPT:
      * a heading with no gate of its own (this module's, Phone, Terminology):
        it is opened by whoever opens something inside it, and a gate on it
        would flow down and widen every screen inside;
      * a child with no gate of its own under a GATED heading: it already
        inherits that heading's roles, which the rule widens there;
      * the UNTOUCHED rows.
    """
    Item = env['cms.sidebar.item'].sudo().with_context(active_test=False)
    sections = [_ref(env, x) for x in AREA_ROLES]
    section_ids = [s.id for s in sections if s]
    untouched = {r.id for r in (_item(env, x) for x in UNTOUCHED) if r}
    out = {}
    for item in Item.search([('section_id', 'in', section_ids)]):
        if item.id in untouched:
            continue
        if _is_heading(item) and not item.biz_role_ids:
            continue
        if (item.parent_id and not item.biz_role_ids
                and item.parent_id.biz_role_ids):
            continue
        out[item.id] = _xmlid_of(env, item)
    return out


def apply_gates(env, log):
    """The §2b rule, entry by entry, once per entry (see the docstring)."""
    Item = env['cms.sidebar.item'].sudo().with_context(active_test=False)
    handled = _gate_handled(env)
    always = _roles(env, ALWAYS)
    touched = set()
    for item_id, xmlid in gate_targets(env).items():
        if item_id in handled:
            continue
        item = Item.browse(item_id)
        section_xmlid = _xmlid_of(env, item.section_id)
        area = _roles(env, AREA_ROLES.get(section_xmlid, ()))
        today = item.biz_role_ids
        if today:
            base = today
        elif xmlid in EXACT:
            base = _roles(env, EXACT[xmlid])
        else:
            base = area
        wanted = (base | always | _roles(env, WIDEN.get(section_xmlid, ()))
                  | _roles(env, EXTRA.get(xmlid, ())))
        added = wanted - today
        # "OWNER AND ADMIN KEEP EVERYTHING": on an entry that is open to
        # everybody today they already see it, so the door check (which asks
        # the ROLE's permissions, not the person's — an Admin account often
        # carries more) must not take it away from them.
        kept = always if not today else always.browse()
        able = added.filtered(lambda r: r in kept or can_open(env, r, item))
        refused = added - able
        final = today | able
        if not final:
            # NEVER GATE TO NOBODY. Nobody on the list can open the screen
            # (only the platform administrator can), so the ruled roles are
            # written anyway — an entry with no gate is open to EVERYBODY.
            final = base | always
            log['refused_everyone'].append('%s (%s)' % (
                xmlid, door_model(env, item)))
        if refused:
            log['narrowed'].append('%s: not %s (cannot open %s)' % (
                xmlid, ', '.join(sorted(refused.mapped('name'))),
                door_model(env, item)))
        touched.add(item_id)
        if set(final.ids) != set(today.ids):
            log['gates'].append('%s: %s -> %s' % (
                xmlid, ', '.join(sorted(today.mapped('name'))) or 'everybody',
                ', '.join(sorted(final.mapped('name')))))
            item.write({'biz_role_ids': [(6, 0, final.ids)]})
    _mark_gate_handled(env, touched)
    Item.invalidate_model(['effective_biz_role_ids'])


# =============================================================================
# H — the product switches follow the rows.
# =============================================================================
def rewire_features(env, log):
    """`health_tenancy.wire_features` again, now that rows have moved: its
    table names the new Channels heading and the phone rows that left the
    Phone heading, whose key they no longer inherit."""
    try:
        from odoo.addons.health_tenancy.hooks import wire_features
    except ImportError:                                  # pragma: no cover
        return
    report = wire_features(env)
    log['features'] = list(report.get('wired') or [])


# =============================================================================
# AR-3 G1/G2 — the two M2 follow-ups that touch a gate.
# =============================================================================
def apply_followups(env, log):
    """G1: a doctor opens Bookings. G2: the Google Ads application is the
    platform's alone. Both idempotent, both run on both paths (post_init and
    the 19.0.1.1.0 migration), both logged.

    G1 ADDS, NEVER REPLACES: Doctor joins the entry's roles only when a doctor
    can actually open the screen behind it (the door check — M2 refused it for
    want of exactly this), and whatever else is written there stays. It is
    written through `biz_role_ids` like every other gate.

    G2 EMPTIES the entry's roles. An entry with no roles is normally open to
    everybody; this one is on `health_access.PLATFORM_ONLY_ITEMS`, which draws
    it for the platform administrator and nobody else, and keeps it active so
    the administrator still reaches it from the menu.
    """
    grant = grant_abilities(env, DOCTOR_ABILITIES, DOCTOR_REASON)
    log['doctor_roles'] = grant['roles']
    log['doctor_people'] = grant['people']
    doctor = _ref(env, DOCTOR)
    if doctor:
        for xmlid in DOCTOR_ENTRIES:
            item = _item(env, xmlid)
            if not item or doctor in item.biz_role_ids:
                continue
            if not can_open(env, doctor, item):
                log['narrowed'].append('%s: not Doctor (cannot open %s)'
                                       % (xmlid, door_model(env, item)))
                continue
            item.write({'biz_role_ids': [(4, doctor.id)]})
            log['gates'].append('%s: + Doctor' % xmlid)
    item = _item(env, PLATFORM_ONLY_GOOGLE_ADS)
    if item:
        vals = {}
        if item.biz_role_ids:
            vals['biz_role_ids'] = [(5, 0, 0)]
        if not item.active and env.ref(item.action_xmlid or '',
                                       raise_if_not_found=False):
            vals['active'] = True
        if vals:
            log['gates'].append('%s: %s -> platform administrator only' % (
                PLATFORM_ONLY_GOOGLE_ADS,
                ', '.join(sorted(item.biz_role_ids.mapped('name'))) or 'none'))
            item.write(vals)
    env['cms.sidebar.item'].invalidate_model(['effective_biz_role_ids'])


# =============================================================================
# THE WHOLE THING
# =============================================================================
def consolidate_ia(env):
    """Everything, in order. Returns the move log (counts per table)."""
    log = {k: [] for k in ('section_renames', 'renames', 'moves', 'retired',
                           'matches', 'released', 'headings', 'gates',
                           'narrowed', 'refused_everyone', 'missing',
                           'features', 'names_vi')}
    phone = grant_phone_abilities(env)
    apply_names(env, log)
    apply_moves(env, log)
    apply_retirements(env, log)
    apply_matches(env, log)
    settle_headings(env, log)
    rewire_features(env, log)
    apply_gates(env, log)
    apply_followups(env, log)
    apply_names_vi(env, log)
    log['phone_roles'] = phone['roles']
    log['phone_people'] = phone['people']
    for key, rows in log.items():
        for row in rows:
            _logger.info('health_cms_ia: %s | %s', key, row)
    _logger.info('health_cms_ia: consolidation — %s',
                 ', '.join('%s %s' % (len(v), k) for k, v in log.items()))
    return log


def post_init_hook(env):
    consolidate_ia(env)
