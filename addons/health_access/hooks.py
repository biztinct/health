# -*- coding: utf-8 -*-
"""The clinic's own words, and the carry-over from the app that held them.

THREE THINGS HAPPEN HERE, IN THIS ORDER, AND THE ORDER IS THE ARGUMENT.

  1. **The vocabulary.** Areas and abilities — the words this clinic already
     uses on its own screens. Registered at import time, seeded when the module
     lands. Nothing product-specific lives in `biz_access`; all of it lives here.

  2. **The roles, as bundles.** The nine roles this clinic runs on, each written
     down as the abilities it already carried and each given a fixed name of its
     own, so a data file, a later release or a hook can point at "the Nurse
     role" and be sure what it means.

  3. **The carry-over.** Everything the previous access application was holding
     — who is in which role, which left-menu entries each role opens, which
     applications each role does not see — written into the new shape BESIDE the
     old one, never instead of it.

WHY BESIDE AND NOT INSTEAD. The previous application is load-bearing on a live
clinic: seventy-nine gated menu entries, two and a half thousand hidden
applications, and every one of the people using it signed in this morning
expecting the same screens. So this writes a second copy of the same facts and
leaves the first exactly where it was; both are read, as an OR, and the proof
that the second says the same as the first is a person-by-person diff run before
anything is switched off. Switching the old one off is a separate step, taken
after that proof.

EVERY READ OF THE OLD APPLICATION IS GUARDED. `'access.role' in env`, and
`'access_role_id' in fields` — because the day it is uninstalled this module has
to install, upgrade and run exactly as before, and a hook that raised on a
missing model would make that day much longer than it needs to be.

IDEMPOTENT BY CONSTRUCTION, NOT BY A STAMP. Every step here finds what it would
have created and leaves it alone. It runs on a fresh install, on a database
somebody restored from a backup taken half-way through, and on any evening
somebody types the re-run door. A stamp saying "already done" is a stamp that is
wrong exactly once, on the database where it matters.

THE ONE EXCEPTION, AND WHY IT IS NOT THAT KIND OF STAMP. `_set_clinical_kinds`
reads a role's NAME once and never again, and it records WHICH ROLES it has
read. That is not "this migration ran"; it is the fact the step is about. Every
role starts on the same default, so "nobody has looked at this yet" and
"somebody looked and said no" are the same value in the field — and without the
list, a re-run would quietly overrule the second.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.exceptions import UserError

from odoo.addons.biz_access.hooks import (ensure_catalogue,  # noqa: F401
                                          register_catalogue)
from odoo.addons.biz_access.models.access_common import (register_areas,
                                                         register_manager_groups)

_logger = logging.getLogger(__name__)

# =============================================================================
# THE AREAS. The words on this clinic's own left menu, and nothing invented.
#
# `clinical` is the default because a clinic is mostly clinical: a new role
# somebody writes down without saying where it belongs is far more likely to be
# about care than about the ledger, and a default that is usually right is one
# fewer decision on a form.
# =============================================================================
AREAS = [
    ('clinical', 'Clinical care'),
    ('front_desk', 'Front desk & CRM'),
    ('operations', 'Operations'),
    ('finance', 'Finance'),
    ('admin', 'Administration'),
]
DEFAULT_AREA = 'clinical'

# =============================================================================
# ONE ABILITY PER PERMISSION, AND THAT IS A DECISION RATHER THAN A SHORTCUT.
#
# An ability is meant to be the unit somebody recognises, and two permissions
# that always travel together genuinely belong in one. But this catalogue exists
# first of all to write down NINE ROLES THAT ALREADY EXIST, exactly — the same
# people holding the same things the morning after as the morning before. A
# bundle that grouped two permissions would be exact only for the roles that
# happen to carry both; for any role carrying one of them it would either add
# something nobody granted or drop something somebody has.
#
# So: one ability per permission, each with an honest sentence. Grouping is a
# thing to do later, deliberately, once nothing depends on the mapping being
# reversible.
#
# `(technical_key, area, sequence, name, description, (group_xmlids,))`
# A missing xml-id is skipped with a log line rather than failing the install —
# a module that is not on this database is not a reason for the others to have
# no vocabulary.
# =============================================================================
ABILITIES = [
    ('sign-in', 'admin', 10, 'Sign in and use the basics',
     'Open the system, see the home screen and their own details. On its own '
     'it opens no patient record and no money.',
     ('base.group_user',)),

    ('care-base', 'clinical', 20, "See the clinic's patients and visits",
     'Look up a patient and read the visits arranged for them. It does not by '
     'itself allow writing clinical notes or changing a booking.',
     ('health_base.group_healthcare_base',)),

    ('reception', 'front_desk', 30, 'Work the front desk',
     'Book, move and check in visits, and keep patient contact details right. '
     'It does not include clinical records or invoicing.',
     ('health_base.group_healthcare_receptionist',)),

    ('nursing', 'clinical', 40, 'Give nursing care',
     'Run a visit, record observations and medicines given, and write the '
     'notes for it. It does not include leading the nursing team.',
     ('health_base.group_healthcare_nurse',)),

    ('head-nursing', 'clinical', 50, 'Lead the nursing team',
     'Everything nursing care involves, plus checking and signing off what the '
     'team has recorded. It does not make somebody a doctor.',
     ('health_base.group_healthcare_head_nurse',)),

    ('doctoring', 'clinical', 60, 'Practise as a doctor',
     'Diagnose, prescribe and sign off clinical records. It does not include '
     'running the roster or the money side of a visit.',
     ('health_base.group_healthcare_doctor',)),

    ('sales', 'front_desk', 70, 'Sell services and follow up leads',
     'Quote for care packages, follow up enquiries and close them. It opens no '
     'clinical record.',
     ('health_base.group_healthcare_sales',)),

    ('ops-manage', 'operations', 80, 'Run daily operations',
     "Plan the day's visits, staff them and deal with what goes wrong. It does "
     'not include hiring, pay or the accounts.',
     ('health_base.group_healthcare_operations_manager',)),

    ('finance-work', 'finance', 90, "Work the clinic's finances",
     'Read and work with what has been billed, collected and written off. It '
     'is not the accounting ledger itself.',
     ('health_base.group_healthcare_finance',)),

    ('care-manage', 'operations', 100, 'Manage the care team',
     'Oversee the clinical team and the work they are given, across the whole '
     'clinic. It does not by itself open the finances.',
     ('health_base.group_healthcare_manager',)),

    ('care-admin', 'admin', 110, "Administer the clinic's records",
     'Keep the reference lists behind every screen right — services, '
     'facilities, areas, price lists. It changes settings, not patients.',
     ('health_base.group_healthcare_admin',)),

    ('records-custody', 'admin', 120, 'Archive and restore records',
     'Put a record beyond everyday reach and bring it back if it was a '
     'mistake. It never destroys anything.',
     ('health_base.group_healthcare_custodian',)),

    ('ownership', 'admin', 130, "Own the clinic's data",
     'The last word on what happens to a record, including permanently '
     'removing one. It is not the system administrator permission and never '
     'carries it.',
     ('health_base.group_healthcare_owner',)),

    ('patient-portal', 'clinical', 140, 'Use the patient portal',
     'Reach the pages a patient and their family are shown. It grants nothing '
     'inside the clinic itself.',
     ('health_base.group_healthcare_patient',)),

    ('crm-work', 'front_desk', 150, 'Work enquiries and bookings',
     'Take an enquiry from first contact to a booked visit, and keep the '
     'follow-ups moving. It does not include changing how the pipeline works.',
     ('health_crm.group_health_crm_user',)),

    ('crm-manage', 'front_desk', 160, 'Manage enquiries and bookings',
     'Everything working enquiries involves, plus setting up the stages, the '
     'reasons and who picks work up.',
     ('health_crm.group_health_crm_manager',)),

    ('invoicing-work', 'finance', 170, 'Raise and send invoices',
     'Bill a visit or a package and send it out. It does not include changing '
     'prices or approving a write-off.',
     ('health_invoicing.group_health_invoicing_user',)),

    ('invoicing-manage', 'finance', 180, 'Manage invoicing',
     'Everything raising invoices involves, plus corrections, credit notes and '
     'how billing is set up.',
     ('health_invoicing.group_health_invoicing_manager',)),

    ('insurance-claims', 'finance', 190, 'Process insurance claims',
     'Prepare, send and chase claims for the care given. It does not change '
     'the clinical record the claim is about.',
     ('health_invoicing.group_insurance_claims',)),

    ('misa-sync', 'finance', 200, 'Run the accounting sync',
     'Send billing across to the connected accounting system and see what came '
     'back. It does not write in that system by hand.',
     ('health_invoicing.group_misa_integration',)),

    ('tax-compliance', 'finance', 210, 'Keep tax records compliant',
     'Maintain the tax details and the returns that go with billing. It does '
     'not issue the official invoices themselves.',
     ('health_invoicing.group_vietnamese_tax_compliance',)),

    ('red-invoice', 'finance', 220, 'Issue red invoices',
     'Issue and cancel the official tax invoices for care given. It is the '
     'last step of billing, not the first.',
     ('health_redinvoice.group_health_redinvoice_manager',)),

    ('accounting-invoices', 'finance', 230, 'Work in the accounting ledger',
     'Open and work with customer and supplier invoices in the accounts. It is '
     'not the whole of accounting.',
     ('account.group_account_invoice',)),

    ('staff-records', 'operations', 240, 'Manage staff records',
     'Keep the people records right — who works here, where and on what terms. '
     'It does not include pay.',
     ('hr.group_hr_user',)),

    ('sales-all-leads', 'front_desk', 250, 'See every lead',
     'See the whole pipeline rather than only their own enquiries. It changes '
     'what is visible, not what can be done.',
     ('sales_team.group_sale_salesman_all_leads',)),

    ('sales-manage', 'front_desk', 260, 'Manage the sales team',
     'Everything selling involves, plus the teams, the targets and who owns '
     'which enquiry.',
     ('sales_team.group_sale_manager',)),

    ('coaching-branch', 'operations', 270, 'Coach as a branch manager',
     'See and work the coaching and performance screens for one branch. It '
     'opens no clinical record and no money.',
     ('hr_development_ai.group_bfsi_branch_manager',)),

    ('user-admin', 'admin', 280, 'Add people and give out roles',
     'Add a colleague, switch one off and say which role each of them holds. '
     'It never includes the system administrator permission for the box.',
     ('health_access.group_clinic_admin',)),

    # ANALYTICS. Two abilities rather than one, because the two questions are
    # genuinely different: reading a dashboard somebody else built is not the
    # same job as building one, and every reporting rule in this system is
    # keyed on that ladder. They were missing while the four roles that get
    # Analytics were named in python, in two different modules, by matching the
    # word "Owner" against a row. Now the roles have fixed names and the
    # permission is written down where every other permission is.
    ('analytics-view', 'operations', 290, 'Read the reports',
     'Open the dashboards and reports somebody has already built, and filter '
     'them. It does not include building a new one.',
     ('biz_bi.group_bi_viewer',)),

    ('analytics-build', 'operations', 300, 'Build reports',
     'Everything reading reports involves, plus building new charts, lists '
     'and dashboards from the data this clinic already has. It changes no '
     'record it reports on.',
     ('biz_bi.group_bi_creator',)),
]

# =============================================================================
# THE ROLES. Named EXACTLY as the previous application named them, because the
# whole clinic already calls them that and a migration that also renamed things
# would be two changes wearing one coat.
#
# What each is MADE OF is never typed here: it is read off the live rows, in
# `_carry_roles` below. A table in a file and a row in a database are two
# statements of the same fact, and the file is the one that is out of date.
#
# `area` and `description` are this module's own contribution — the row said
# nothing about either — and `archived` is the one judgement call, explained
# where it is used.
# =============================================================================
ROLE_NOTES = {
    'Owner': {
        'area': 'admin',
        'description': "Runs the clinic and answers for its records. Opens "
                       "every part of the system this clinic uses, including "
                       "permanently removing a record — but never the system "
                       "administrator permission for the box itself.",
    },
    'Operations Manager': {
        'area': 'operations',
        'description': "Runs the day: the roster, the visits, the people and "
                       "the money that follows them. Everything an owner can "
                       "reach except the last word on removing records.",
    },
    'Branch Manager': {
        'area': 'operations',
        'description': "Coaches and reviews one branch's team. It opens the "
                       "performance screens and nothing clinical or financial.",
    },
    'Banker': {
        'area': 'finance',
        'description': "Kept from an earlier setup and held by nobody. It "
                       "carries nothing beyond signing in, which is why it is "
                       "put away rather than left on the board.",
        'archived': True,
    },
    'Nurse': {
        'area': 'clinical',
        'description': "Gives care and records it: visits, observations, "
                       "medicines and notes, plus the billing that goes with a "
                       "visit. It does not run the roster.",
    },
    'Doctor': {
        'area': 'clinical',
        'description': "Diagnoses, prescribes and signs off clinical records. "
                       "It opens the clinical screens and nothing else.",
    },
    'Accountant': {
        'area': 'finance',
        'description': "Owns the money: invoices, claims, tax, red invoices "
                       "and the accounting sync. It opens no clinical record.",
    },
    'Admin': {
        'area': 'admin',
        'description': "Adds colleagues, switches them off and says which role "
                       "each of them holds. It carries no clinical or "
                       "financial access of its own, and never the system "
                       "administrator permission.",
    },
    'CRM': {
        'area': 'front_desk',
        'description': "Works the front desk and the enquiry pipeline from "
                       "first contact to a booked visit. It opens no clinical "
                       "record.",
    },
}

#: The fixed name a role is known by underneath. `health_access.role_nurse`.
ROLE_XMLIDS = {
    'Owner': 'role_owner',
    'Operations Manager': 'role_operations_manager',
    'Branch Manager': 'role_branch_manager',
    'Banker': 'role_banker',
    'Nurse': 'role_nurse',
    'Doctor': 'role_doctor',
    'Accountant': 'role_accountant',
    'Admin': 'role_admin',
    'CRM': 'role_crm',
}

#: What a role is made of when there is no old application to read it off —
#: a fresh database, or a test. The live clinic never uses this: `_carry_roles`
#: reads the rows. Kept here so a brand-new database still boots with the nine
#: roles somebody can recognise rather than an empty board.
FRESH_ROLE_ABILITIES = {
    'Owner': ('sign-in', 'care-base', 'reception', 'nursing', 'head-nursing',
              'doctoring', 'sales', 'ops-manage', 'finance-work',
              'care-manage', 'care-admin', 'ownership', 'patient-portal',
              'crm-work', 'crm-manage', 'invoicing-work', 'invoicing-manage',
              'insurance-claims', 'misa-sync', 'tax-compliance', 'red-invoice',
              'accounting-invoices', 'staff-records', 'sales-all-leads',
              'user-admin', 'analytics-build'),
    'Operations Manager': (
        'sign-in', 'care-base', 'reception', 'nursing', 'head-nursing',
        'doctoring', 'sales', 'ops-manage', 'finance-work', 'care-manage',
        'care-admin', 'ownership', 'patient-portal', 'crm-work', 'crm-manage',
        'invoicing-work', 'invoicing-manage', 'insurance-claims', 'misa-sync',
        'tax-compliance', 'red-invoice', 'accounting-invoices',
        'staff-records', 'sales-manage', 'analytics-build'),
    'Branch Manager': ('sign-in', 'coaching-branch', 'analytics-build'),
    'Banker': ('sign-in',),
    'Nurse': ('sign-in', 'care-base', 'nursing', 'patient-portal',
              'invoicing-work', 'invoicing-manage', 'misa-sync',
              'accounting-invoices'),
    'Doctor': ('sign-in', 'doctoring'),
    'Accountant': ('sign-in', 'care-base', 'finance-work', 'ops-manage',
                   'invoicing-work', 'invoicing-manage', 'insurance-claims',
                   'misa-sync', 'tax-compliance', 'red-invoice',
                   'accounting-invoices', 'sales-manage', 'analytics-build'),
    'Admin': ('sign-in', 'user-admin'),
    'CRM': ('sign-in', 'care-base', 'ops-manage', 'sales', 'crm-work',
            'crm-manage', 'sales-manage'),
}

#: The top-bar branch that belonged to the application being retired. It went
#: with it, so carrying its rows across would have been writing down a fact
#: with a known expiry date.
LEGACY_MENU_XMLID = 'access_roles.access_role_menu_root'

#: The reason written on every grant this carry-over makes. It is what somebody
#: reads in the history months later when they ask why a person holds a role.
CARRY_REASON = 'carried over from the previous access app'

#: THIS CLINIC'S OWN ADMINISTRATOR TIER, and the one it replaces.
#:
#: The people, the privilege and the words on the screen are unchanged; only
#: the module that owns the row moved, because the one that owned it before is
#: being uninstalled and a permission group disappears with its module.
CLINIC_ADMIN_GROUP = 'health_access.group_clinic_admin'
LEGACY_ADMIN_GROUP = 'health_user_admin.group_health_user_admin'

#: Which roles get to build reports. Written down here, once, instead of being
#: matched by name in two different modules' python — which is what happened
#: while roles had no fixed names to point at.
ANALYTICS_ROLES = ('Owner', 'Operations Manager', 'Branch Manager',
                   'Accountant')
ANALYTICS_ABILITY = 'analytics-build'


# =============================================================================
# REGISTRATION — at import time, so it counts however this module is loaded.
# =============================================================================
register_areas(AREAS, default=DEFAULT_AREA)

# WHO MAY GIVE AND TAKE ROLES HERE. This clinic has its own administrator tier
# and it is the tier that has always added colleagues; the Access home is the
# screen it does that on now. `base.group_system` stays with the platform, held
# by one account, and is not added to anything (the two-ring rule).
#
# The group is this module's own (`security/health_access_security.xml`). It
# used to belong to the application being retired; the people in it, the
# privilege it carries and the name on their screen are unchanged.
register_manager_groups(CLINIC_ADMIN_GROUP)


def _seed(env):
    """Everything this clinic's board needs to exist. Create-only."""
    _ensure_abilities(env)
    _carry_roles(env)


register_catalogue(_seed, name='health_access.catalogue')


# =============================================================================
# 1. THE VOCABULARY
# =============================================================================
def _ensure_abilities(env):
    """Write down every ability, and leave alone any that is already there.

    CREATE-ONLY. An administrator may have reworded a sentence to suit the
    clinic, and an upgrade that put this file's wording back would be an upgrade
    that undoes somebody's work every release. What a NEW release may do is add
    an ability that did not exist; that is what runs here.
    """
    Ability = env['biz.access.ability'].sudo().with_context(active_test=False)
    made, skipped = 0, []
    for key, area, sequence, name, description, xmlids in ABILITIES:
        if Ability.search_count([('technical_key', '=', key)]):
            continue
        groups = env['res.groups'].sudo().browse()
        missing = False
        for xmlid in xmlids:
            group = env.ref(xmlid, raise_if_not_found=False)
            if not group:
                missing = True
                break
            groups |= group
        if missing or not groups:
            # A module that is not on this database is not an error. Gating a
            # role on nothing WOULD be, so the ability is simply not written.
            skipped.append(key)
            continue
        Ability.create({
            'technical_key': key,
            'name': name,
            'description': description,
            'area': area,
            'sequence': sequence,
            'group_ids': [(6, 0, groups.ids)],
        })
        made += 1
    _logger.info(
        'health_access: vocabulary — %s ability(ies) written down, %s skipped '
        'for a permission this database does not have (%s)',
        made, len(skipped), ', '.join(skipped) or 'none')
    return made


def _abilities_by_group(env):
    """`{permission id: the ability that wraps it}`.

    One ability per permission is what makes this a mapping rather than a
    choice, and it is the whole reason the carry-over below can be exact.
    """
    out = {}
    for ability in env['biz.access.ability'].sudo().with_context(
            active_test=False).search([]):
        for group in ability.group_ids:
            out.setdefault(group.id, ability)
    return out


# =============================================================================
# 2. THE ROLES
# =============================================================================
def _carry_roles(env):
    """The nine roles, written down as bundles of what they already carried.

    READ OFF THE LIVE ROWS, NEVER OFF A TABLE IN THIS FILE. The previous
    application's rows are the fact; a list here would be a second statement of
    it, and the second statement is the one that goes stale. The table in this
    file is used only where there are no rows to read — a fresh database, or a
    test — and then it is honestly a seed rather than a migration.

    IT REFUSES RATHER THAN APPROXIMATES. If a role carries a permission that no
    ability wraps, the bundle would be a SMALLER role wearing the same name, and
    somebody would be quietly granted less than the board says. So it stops, and
    names the permission that needs an ability.
    """
    Role = env['biz.access.role'].sudo().with_context(active_test=False)
    by_group = _abilities_by_group(env)
    old_roles = _old_roles(env)

    made = 0
    for name, group_ids in old_roles.items():
        if Role.search_count([('name', '=', name)]):
            _ensure_role_xmlid(env, Role.search([('name', '=', name)], limit=1))
            continue
        abilities = env['biz.access.ability'].sudo().browse()
        unmapped = []
        for gid in group_ids:
            ability = by_group.get(gid)
            if ability is None:
                unmapped.append(gid)
            else:
                abilities |= ability
        if unmapped:
            names = env['res.groups'].sudo().browse(unmapped).mapped(
                'display_name')
            xmlids = _xmlids_of(env, unmapped)
            raise UserError(
                "The \"%s\" role carries a permission nothing in the "
                "catalogue covers yet: %s (%s). Writing the role down without "
                "it would hand out less than the role does today. Add an "
                "ability for it and run this again."
                % (name, ', '.join(names), ', '.join(xmlids)))

        notes = ROLE_NOTES.get(name, {})
        role = Role.create({
            'name': name,
            'description': notes.get('description') or '',
            'area': notes.get('area') or _dominant_area(abilities),
            'sequence': (made + 1) * 10,
            'ability_ids': [(6, 0, abilities.ids)],
        })
        # A ROLE OF NOTHING BUT SIGNING IN IS HELD BY EVERY COLLEAGUE IN THE
        # BUILDING, and would therefore open every left-menu entry it is put on
        # to all of them. Nobody holds it today and nobody is meant to, so it is
        # written down — the history points at it by name — and put away.
        if notes.get('archived'):
            role.write({'active': False})
        _ensure_role_xmlid(env, role)
        made += 1

    _logger.info(
        'health_access: roles — %s role(s) written down as bundles, %s already '
        'there', made, len(old_roles) - made)
    return made


def _old_roles(env):
    """`{role name: [permission ids]}` — from the live rows where there are any.

    Ordered so the board reads the way the clinic thinks: the roles come back in
    the order the previous application listed them.
    """
    if 'access.role' in env:
        rows = env['access.role'].sudo().with_context(
            active_test=False).search([], order='id')
        if rows:
            return {r.name: r.groups_ids.ids for r in rows if r.name}

    # No previous application on this database: seed the nine from the table,
    # by ability rather than by permission.
    Ability = env['biz.access.ability'].sudo().with_context(active_test=False)
    out = {}
    for name, keys in FRESH_ROLE_ABILITIES.items():
        abilities = Ability.search([('technical_key', 'in', list(keys))])
        if abilities:
            out[name] = abilities.group_ids.ids
    return out


def _ensure_role_xmlid(env, role):
    """Give a role a fixed name of its own.

    WHY IT MATTERS MORE THAN IT LOOKS. Without one, every data file and every
    hook that wants to say "gate this on the Nurse role" has to find it by
    searching for the word "Nurse" — which is how two modules on this database
    came to gate themselves in Python by name-matching. With one, they can point
    at it. `noupdate` so that renaming a role on its own card is safe: the fixed
    name goes on pointing at the same row.
    """
    if not role or not role.name:
        return False
    key = ROLE_XMLIDS.get(role.name)
    if not key:
        return False
    Data = env['ir.model.data'].sudo()
    existing = Data.search([('module', '=', 'health_access'),
                            ('name', '=', key)], limit=1)
    if existing:
        if existing.res_id != role.id:
            existing.write({'res_id': role.id})
        return True
    Data.create({
        'module': 'health_access',
        'name': key,
        'model': 'biz.access.role',
        'res_id': role.id,
        'noupdate': True,
    })
    return True


def _dominant_area(abilities):
    order = [key for key, _label in AREAS]
    counts = {}
    for ability in abilities:
        if ability.area:
            counts[ability.area] = counts.get(ability.area, 0) + 1
    if not counts:
        return DEFAULT_AREA
    return sorted(counts, key=lambda k: (-counts[k], order.index(k)
                                         if k in order else 99))[0]


def _xmlids_of(env, group_ids):
    rows = env['ir.model.data'].sudo().search([
        ('model', '=', 'res.groups'), ('res_id', 'in', list(group_ids))])
    return ['%s.%s' % (r.module, r.name) for r in rows] or ['no fixed name']


def role_by_name(env, name):
    """The bundle called `name`, archived included, or an empty recordset."""
    return env['biz.access.role'].sudo().with_context(
        active_test=False).search([('name', '=', name)], limit=1)


# =============================================================================
# 3. THE CARRY-OVER
# =============================================================================
def migrate_legacy(env):
    """Write everything the previous application held into the new shape.

    Four steps, each one idempotent, each one leaving the old rows exactly where
    they are. Every step logs the line somebody will look for in the server log
    afterwards, because a migration whose only evidence is that nothing broke is
    a migration nobody can check.
    """
    if 'access.role' not in env:
        _logger.info(
            'health_access: carry-over — the previous access application is '
            'not on this database, so there is nothing to carry over')
        return {'roles': 0, 'holders': [], 'gates': 0, 'menus': 0}

    roles = _carry_roles(env)
    holders = _carry_holders(env)
    gates = _carry_rail_gates(env)
    menus = _carry_menu_hides(env)
    return {'roles': roles, 'holders': holders, 'gates': gates, 'menus': menus}


def _carry_holders(env):
    """Everybody keeps what they had, and the history says how they got it.

    Through `biz.access.grant`, not through a raw write, for two reasons. It
    adds only the part somebody is MISSING — a person who already reaches four
    of a role's five permissions gets the fifth, and the audit row records the
    one thing that actually changed. And it writes that audit row at all, so the
    question "why does this person hold that" has an answer months later.
    """
    Users = env['res.users'].sudo()
    if 'access_role_id' not in Users._fields:
        return []
    facade = env['biz.access'].sudo().with_user(SUPERUSER_ID)
    carried = []
    users = Users.search([('active', '=', True), ('share', '=', False),
                          ('access_role_id', '!=', False)])
    for user in users:
        old = user.access_role_id
        role = role_by_name(env, old.name or '')
        if not role or not role.group_ids:
            continue
        held = set(user.all_group_ids.ids)
        if set(role.group_ids.ids) <= held:
            continue                    # already holds it in full
        missing = role.group_ids.filtered(lambda g: g.id not in held)
        try:
            facade.grant(role.id, user.id, reason=CARRY_REASON)
            carried.append({
                'user': user.name or '', 'login': user.login or '',
                'role': role.name or '',
                'gained': missing.mapped('display_name'),
            })
        except Exception:                           # noqa: BLE001
            _logger.warning(
                'health_access: %s could not be given "%s" as part of the '
                'carry-over', user.login or user.id, role.name, exc_info=True)
    _logger.info(
        'health_access: carry-over — %s of %s people with a role needed '
        'something added: %s', len(carried), len(users),
        '; '.join('%s (+%s)' % (c['login'], ', '.join(c['gained']))
                  for c in carried) or 'none')
    return carried


def _carry_rail_gates(env):
    """Every left-menu gate, written on the new lane beside the old one.

    THE OLD LANE IS NEVER TOUCHED. `role_ids` on an entry is the previous
    application's column and it stays exactly as it is; this writes the new
    column only. The two are then read as an OR, so this step cannot take a
    screen away from anybody — it can only ever be a second way in.
    """
    Item = env['cms.sidebar.item'].sudo().with_context(active_test=False)
    Section = env['cms.sidebar.section'].sudo().with_context(active_test=False)
    if 'biz_role_ids' not in Item._fields:             # pragma: no cover
        return 0
    if 'role_ids' not in Item._fields:
        # The older column has gone with the application that owned it. There
        # is nothing left to copy FROM, and this step is done.
        return 0

    written = 0
    for section in Section.search([]):
        wanted = _bundles_for(env, section.role_ids)
        if set(section.biz_role_ids.ids) != set(wanted.ids):
            section.write({'biz_role_ids': [(6, 0, wanted.ids)]})
            written += 1
    for item in Item.search([]):
        wanted = _bundles_for(env, item.role_ids)
        if set(item.biz_role_ids.ids) != set(wanted.ids):
            item.write({'biz_role_ids': [(6, 0, wanted.ids)]})
            written += 1
    _logger.info(
        'health_access: carry-over — %s left-menu row(s) now carry the same '
        'gate on the new lane', written)
    return written


def _bundles_for(env, old_roles):
    """The bundles that stand for these old roles, matched by name."""
    out = env['biz.access.role'].sudo().browse()
    for old in old_roles:
        role = role_by_name(env, old.name or '')
        if role:
            out |= role
    return out


def _carry_menu_hides(env):
    """Which applications each role does not see, off the old profiles.

    THREE THINGS HAPPEN TO THE LIST ON THE WAY ACROSS, and each one is a
    decision.

      * **It is compressed to the top-most rows.** The old profiles store every
        descendant — six hundred rows to say "not these nine applications" —
        and a stored descendant is a row that goes stale the day a module adds a
        screen. The new list holds the branch heads and the branch is worked out
        at read time.
      * **The branch of the application being retired is dropped.** It goes away
        with that application; carrying it across would be writing down a fact
        with a known expiry date. The old rule still hides it in the meantime.
      * **A profile linked to no role is skipped entirely.** Two of them are
        named "NOT USED" and mean it; a profile nobody's role points at was
        never deciding anything.

    A ROLE WITH NO PROFILE KEEPS AN EMPTY LIST, and that is a fact carried over
    rather than a gap left behind. A doctor on this clinic sees the whole top bar
    today, because the previous application has no profile for the Doctor role —
    "hides nothing" is what an absent profile MEANT, and the new rule reads it
    the same way. Reading it instead as "said nothing" is what took 489 screens
    off one doctor the first time this ran; the story is in
    `biz_access/models/ir_ui_menu.py`.
    """
    if 'role.management' not in env:
        return 0
    Role = env['biz.access.role'].sudo().with_context(active_test=False)
    if 'hidden_menu_ids' not in Role._fields:          # pragma: no cover
        return 0

    legacy_root = env.ref(LEGACY_MENU_XMLID, raise_if_not_found=False)
    legacy_prefix = (legacy_root.parent_path or '') if legacy_root else ''

    touched = 0
    for profile in env['role.management'].sudo().search([]):
        if not profile.role_ids:
            continue
        menus = profile.menu_ids.sudo().filtered('active')
        if legacy_prefix:
            menus = menus.filtered(
                lambda m: not (m.parent_path or '').startswith(legacy_prefix))
        heads = _branch_heads(menus)
        for old in profile.role_ids:
            role = role_by_name(env, old.name or '')
            if not role:
                continue
            if set(role.hidden_menu_ids.ids) == set(heads.ids):
                continue
            role.write({'hidden_menu_ids': [(6, 0, heads.ids)]})
            touched += 1
            _logger.info(
                'health_access: carry-over — "%s" does not see %s top-bar '
                'branch(es), from %s rows on the "%s" profile',
                role.name, len(heads), len(profile.menu_ids), profile.name)
    _logger.info(
        'health_access: carry-over — %s role(s) were given a top-bar list',
        touched)
    return touched


def _branch_heads(menus):
    """Only the rows nothing else in the set already covers.

    A menu whose parent is also in the set is already hidden by the parent, so
    keeping it makes the list longer and says nothing new.
    """
    paths = [(m, m.parent_path or '') for m in menus]
    keep = menus.browse()
    for menu, path in paths:
        covered = any(
            other.id != menu.id and other_path and path.startswith(other_path)
            for other, other_path in paths)
        if not covered:
            keep |= menu
    return keep


# =============================================================================
# THE RAIL ITEM'S OWN GATE
#
# The data file cannot write it. An xml `ref()` can only point at a row that
# exists when the file is read, and the roles are created by this hook — which
# runs after it. So the entry ships ungated and the gate is written here, once
# the roles are there to point at.
# =============================================================================
ADMIN_ITEM_XMLID = 'health_access.item_admin_access'
ADMIN_ITEM_ROLES = ('Owner', 'Admin')

#: THE DOORS ADDED WHEN THE BAR ABOVE THE SCREEN WAS PUT AWAY.
#:
#: Entry → the roles it opens for. Written here rather than in the data file
#: for the same reason the entry above is: a `ref()` in XML can only point at a
#: row that exists when the file is read, and on a new database the roles are
#: created afterwards.
#:
#: A PARENT'S GATE FLOWS DOWN, so only the parent is named: gating six voice
#: screens one by one would be six chances to disagree with each other.
NEW_ITEM_ROLES = {
    'health_access.item_crm_channel_audit': ('Owner', 'CRM'),
    'health_access.item_crm_channel_messages': ('Owner', 'CRM'),
    'health_access.item_crm_watch_phrases': ('Owner', 'CRM'),
    'health_access.item_crm_zalo': ('Owner', 'CRM', 'Operations Manager'),
    'health_access.item_ops_voice': ('Owner', 'Operations Manager'),
    'health_access.item_ops_visit_offers': ('Owner', 'Operations Manager'),
    'health_access.item_ops_timecard_mismatches': (
        'Owner', 'Operations Manager'),
    'health_access.item_ops_employee_development': ('Owner', 'Branch Manager'),
    'health_access.item_ops_coaching': ('Owner', 'Branch Manager'),
    'health_access.item_admin_training': ('Owner', 'Admin'),
}

#: The two screens "Channels (setup)" merely BORROWED before either had a door
#: of its own. The menu's highlight index is last-wins, so leaving them on the
#: borrower would light up the wrong entry now that each has its own.
BORROWED_MATCHES = (
    'health_care_command_channels.action_care_channel_message',
    'health_care_command_channels.action_care_channel_audit',
)
BORROWER_XMLID = 'health_cms_coverage.item_crm_channels_setup'


def _gate_admin_item(env):
    """Only the people who run the clinic see the Access home on the rail."""
    item = env.ref(ADMIN_ITEM_XMLID, raise_if_not_found=False)
    if not item:
        return False
    roles = env['biz.access.role'].sudo().browse()
    for name in ADMIN_ITEM_ROLES:
        roles |= role_by_name(env, name)
    if roles:
        item.sudo().write({'biz_role_ids': [(6, 0, roles.ids)]})
    _logger.info(
        'health_access: the Access home entry on the left menu is open to %s',
        ', '.join(roles.mapped('name')) or 'nobody yet')
    return True


# =============================================================================
# 4. THE RETIREMENT
#
# The carry-over above put everything the previous application held into the
# new shape and left the old rows where they were, so that both could be read
# and neither could take anything away. This is the other end of that: the
# facts that were still only in the old shape, moved before the application
# holding them is removed.
#
# EVERY STEP RUNS WHILE THE OLD APPLICATION IS STILL INSTALLED, and every step
# also runs correctly on a database where it never was. That is not belt and
# braces — it is the difference between a migration and a one-off script: this
# same code is what a brand-new clinic runs on the day it is created.
# =============================================================================
def retire_legacy(env):
    """Everything that has to be true before the old application is removed."""
    kinds = _set_clinical_kinds(env)
    jobs = _carry_jobs(env)
    swapped = _swap_admin_group(env)
    analytics = _carry_analytics(env)
    return {'kinds': kinds, 'jobs': jobs, 'admins': swapped,
            'analytics': analytics}


#: WHICH ROLES HAVE ALREADY BEEN READ. Not a "this migration ran" stamp — the
#: kind this file's own docstring warns against — but a list of the individual
#: roles whose name has been read ONCE. It is what makes "once" mean once.
KINDS_READ_PARAM = 'health_access.clinical_kinds_read'


def _set_clinical_kinds(env):
    """What each role COUNTS AS, read once off the name it already had.

    The product used to ask "is there the word 'doctor' in this role's name"
    every time it wanted to know whether somebody was a doctor. That is right
    for the nine roles this clinic has and wrong for the tenth, so the answer
    is written down as a field instead — and it is written down by applying
    exactly the old rule ONCE, so that nothing changes on the day it ships and
    nothing changes again afterwards.

    ONCE HAS TO BE RECORDED, BECAUSE THE FIELD CANNOT SAY IT. Every role starts
    on `other`, so "still on the default" and "somebody looked at this and said
    it is not a doctor" are the same value. Reading the name again would
    overrule the second — quietly, months later, the next time anybody pressed
    the re-run door. So the roles whose name has been read are written down,
    and a role on that list is never read again.
    """
    Role = env['biz.access.role'].sudo().with_context(active_test=False)
    if 'clinical_kind' not in Role._fields:                # pragma: no cover
        return 0
    from .models.access_role import kind_from_name        # noqa: PLC0415

    Param = env['ir.config_parameter'].sudo()
    raw = Param.get_param(KINDS_READ_PARAM) or ''
    already = {int(x) for x in raw.split(',') if x.strip().isdigit()}

    written, read = [], set()
    for role in Role.search([]):
        if role.id in already:
            continue
        read.add(role.id)
        kind = kind_from_name(role.name)
        if kind == 'other' or role.clinical_kind == kind:
            continue
        role.write({'clinical_kind': kind})
        written.append('%s → %s' % (role.name, kind))
    if read:
        Param.set_param(KINDS_READ_PARAM,
                        ','.join(str(i) for i in sorted(already | read)))
    _logger.info(
        'health_access: retirement — %s role(s) now say what they count as: %s '
        '(%s role name(s) read for the first time)',
        len(written), '; '.join(written) or 'none', len(read))
    return len(written)


def _carry_jobs(env):
    """Everybody's JOB, from the one role the old application gave them.

    READ BY SQL AND WRITTEN BY SQL, and both halves of that are deliberate.

      * READ, because this has to keep working on a database where the old
        MODEL is already gone — a re-run, a restore, the day after the
        uninstall. `to_regclass` asks the database rather than the registry.
      * WRITTEN, because writing the job through the ORM GRANTS the role, and
        every one of these people already holds it: the carry-over gave it to
        them, with an audit row saying so. A second grant would either refuse
        or write a second row claiming this was the moment they got it, and
        neither is true.

    The stored fields that read the job are recomputed explicitly afterwards,
    because a column written behind the ORM's back is a column the ORM has no
    reason to think has changed.
    """
    Users = env['res.users'].sudo()
    if 'job_role_id' not in Users._fields:                 # pragma: no cover
        return 0

    env.cr.execute("SELECT to_regclass('public.access_role')")
    if not (env.cr.fetchone() or [None])[0]:
        _logger.info(
            'health_access: retirement — no previous access application on '
            'this database, so nobody has a job to carry over from one')
        return 0
    env.cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'res_users' AND column_name = 'access_role_id'
    """)
    if not env.cr.fetchone():
        return 0

    env.cr.execute("SELECT id, name FROM access_role")
    by_old_id = {}
    unmapped = []
    for old_id, name in env.cr.fetchall():
        bundle = role_by_name(env, name or '')
        if bundle:
            by_old_id[old_id] = bundle.id
        else:
            unmapped.append(name or old_id)
    if unmapped:
        # Never silent. A role with no bundle means somebody's job cannot be
        # written, and the person it belongs to would quietly become "no job".
        _logger.warning(
            'health_access: retirement — %s previous role(s) have no bundle of '
            'the same name, so nobody employed as one gets a job: %s',
            len(unmapped), ', '.join(str(n) for n in unmapped))

    env.cr.execute("""
        SELECT id, access_role_id FROM res_users
         WHERE access_role_id IS NOT NULL AND job_role_id IS NULL
    """)
    touched = []
    for uid, old_id in env.cr.fetchall():
        new_id = by_old_id.get(old_id)
        if not new_id:
            continue
        env.cr.execute(
            "UPDATE res_users SET job_role_id = %s WHERE id = %s",
            (new_id, uid))
        touched.append(uid)

    if touched:
        _recompute_job_readers(env, touched)
    _logger.info(
        'health_access: retirement — %s colleague(s) now have their job '
        'written on their record', len(touched))
    return len(touched)


def _recompute_job_readers(env, user_ids):
    """Put the ORM back in step with a column written underneath it.

    Four stored fields on the staff record and two on the login are computed
    from the job. They are recomputed by name rather than by hoping `modified`
    walks far enough, because "the roster still calls them a nurse" is exactly
    the failure this whole change exists to avoid.
    """
    env.invalidate_all()
    Users = env['res.users'].sudo()
    users = Users.browse(list(user_ids)).exists()
    for name in ('is_doctor_role', 'is_nurse_role'):
        if name in Users._fields:
            env.add_to_compute(Users._fields[name], users)
    env.flush_all()

    Employee = env['hr.employee'].sudo().with_context(active_test=False)
    employees = Employee.search([])
    if 'job_role_id' in Employee._fields:
        env.add_to_compute(Employee._fields['job_role_id'], employees)
        env.flush_all()
    for name in ('is_doctor_role', 'is_nurse_role', 'is_om_role',
                 'access_role_display'):
        if name in Employee._fields:
            env.add_to_compute(Employee._fields[name], employees)
    env.flush_all()


def _swap_admin_group(env):
    """The clinic's administrators keep being administrators.

    Their permission group belonged to the application being removed, and a
    permission group disappears with its module. This one is the same tier
    under a name this module owns: everybody who held the old one joins the
    new one, and the ability that hands it out points at the new one, so every
    bundle carrying "add people and give out roles" recomputes onto it.

    NOBODY IS TAKEN OUT OF THE OLD GROUP. It is about to be deleted along with
    its module; removing people from it first would be work with no effect and
    one more thing to get wrong.
    """
    new_group = env.ref(CLINIC_ADMIN_GROUP, raise_if_not_found=False)
    if not new_group:                                      # pragma: no cover
        _logger.error(
            'health_access: retirement — %s does not exist, so the clinic has '
            'no administrator tier to move its people into', CLINIC_ADMIN_GROUP)
        return 0
    old_group = env.ref(LEGACY_ADMIN_GROUP, raise_if_not_found=False)

    moved = []
    if old_group:
        for user in old_group.sudo().all_user_ids:
            if new_group in user.sudo().all_group_ids:
                continue
            user.sudo().write({'group_ids': [(4, new_group.id)]})
            moved.append(user.login or str(user.id))

    # The ability points at the new group, and every bundle holding it
    # recomputes — `biz.access.role.group_ids` is stored and computed from the
    # abilities, so this is the one write that moves nine roles at once.
    ability = env['biz.access.ability'].sudo().with_context(
        active_test=False).search([('technical_key', '=', 'user-admin')],
                                  limit=1)
    if ability and ability.group_ids != new_group:
        ability.write({'group_ids': [(6, 0, new_group.ids)]})
        _logger.info(
            'health_access: retirement — "add people and give out roles" now '
            'hands out the clinic administrator permission this module owns')

    _logger.info(
        'health_access: retirement — %s clinic administrator(s) moved onto the '
        'new permission: %s', len(moved), ', '.join(moved) or 'none needed')
    return len(moved)


def _carry_analytics(env):
    """Who may build a report, said once, where every other permission is said.

    Two modules used to answer this in python by matching the words "Owner",
    "Operations Manager", "Branch Manager" and "Accountant" against a row — one
    to draw the Analytics entry on the left menu, the other to hand out the
    permission behind it. They had to, because roles had no fixed names to
    point at. They do now, so the answer becomes an ability on four bundles,
    and the two copies of the list go away with the modules that held them.

    THE ORDER HERE IS THE WHOLE PROBLEM, AND A REAL DOCTOR FOUND IT. Adding an
    ability to a role makes the role BIGGER, and holding a role means holding
    all of it — so the moment "build reports" joined the Branch Manager bundle,
    anybody who did not already have the reporting permission STOPPED HOLDING
    that bundle, and lost every left-menu entry it opened. On this clinic that
    was one doctor who carries the branch-manager permission by accident of
    history: two entries gone, and the role gone with them.

    So the people to give the permission to are worked out from the role
    WITHOUT it — everybody who holds every OTHER permission in the bundle —
    rather than from the role as it now stands. That is also what makes this
    idempotent and self-repairing: run it on a database where the ability was
    added without the grant and it finds exactly the people who were dropped.

    ADDITIVE, NEVER SUBTRACTIVE. A role that already carries it is left alone,
    and nobody is taken out of the permission — losing a role has never removed
    a permission on this system and this is not the place to start.
    """
    ability = env['biz.access.ability'].sudo().with_context(
        active_test=False).search([('technical_key', '=', ANALYTICS_ABILITY)],
                                  limit=1)
    if not ability:
        _logger.warning(
            'health_access: retirement — the "%s" ability is not on this '
            'database (the reporting module may not be installed), so no role '
            'was given it', ANALYTICS_ABILITY)
        return 0
    reporting = ability.group_ids

    added, granted = [], []
    for name in ANALYTICS_ROLES:
        role = role_by_name(env, name)
        if not role:
            continue
        # THE HOLDERS OF THE ROLE WITHOUT THE REPORTING PERMISSION. Worked out
        # before anything is written, and re-worked out on every run, so this
        # says the same thing whether the ability was added a second ago or a
        # release ago.
        needed = set((role.group_ids - reporting).ids)
        candidates = env['res.users'].sudo().search(
            [('active', '=', True), ('share', '=', False)])
        due = [u for u in candidates
               if needed and needed <= set(u.all_group_ids.ids)]

        if ability not in role.ability_ids:
            role.write({'ability_ids': [(4, ability.id)]})
            added.append(role.name)

        for user in due:
            missing = reporting.filtered(
                lambda g: g.id not in set(user.all_group_ids.ids))
            if not missing:
                continue
            user.write({'group_ids': [(4, g.id) for g in missing]})
            user.invalidate_recordset(['group_ids'])
            granted.append(user.login or str(user.id))

    _logger.info(
        'health_access: retirement — %s role(s) gained "build reports" (%s); '
        '%s person(s) needed the permission itself so as not to stop holding '
        'their role: %s',
        len(added), ', '.join(added) or 'none', len(set(granted)),
        ', '.join(sorted(set(granted))) or 'none')
    return len(added)


def model_behind(env, item):
    """The model an entry's screen opens, or `''` when it opens no records."""
    if not item.action_xmlid:
        return ''
    action = env.ref(item.action_xmlid, raise_if_not_found=False)
    if not action:
        return ''
    return getattr(action.sudo(), 'res_model', '') or ''


def role_can_read(env, role, model_name):
    """Could somebody holding this role open that screen at all?

    ASKED OF THE PERMISSIONS TABLE, not by making a person and trying. A door
    on a menu that answers "you are not allowed to access this" is a dead end,
    and the whole promise of putting these entries here was that everything a
    role needs is on the menu — not that everything is on the menu.

    A permission row with no group on it is open to everybody with a login, so
    it settles the question on its own. Otherwise the role opens the screen
    when any row's group is one it carries, over the whole implication closure
    — a role that carries a manager tier reaches what the officer tier opens.
    """
    if not model_name or model_name not in env:
        return True                     # opens no records; nothing to refuse
    acls = env['ir.model.access'].sudo().search(
        [('model_id.model', '=', model_name), ('perm_read', '=', True)])
    if not acls:
        return True                     # ungoverned; the framework lets it by
    if any(not acl.group_id for acl in acls):
        return True
    closure = role.group_ids | role.group_ids.all_implied_ids
    return any(acl.group_id in closure for acl in acls)


def _gate_new_items(env):
    """Who opens each new door — and whether the door leads anywhere.

    THREE JOBS, AND THE SECOND AND THIRD ARE THE INTERESTING ONES.

    Writing the gate is ordinary. Switching an entry OFF when the screen behind
    it is not on this database is the part that matters: these entries name
    screens belonging to nine different applications, and a clinic that has not
    bought the voice system would otherwise get a "Voice" heading with six
    entries under it that each answer "that screen does not exist".

    And NARROWING THE GATE TO THE ROLES THAT CAN ACTUALLY OPEN IT. A screen
    reached only through the application bar was reached by whoever the screen
    itself lets in; putting it on the left menu does not change who that is. A
    role that would be shown the entry and then refused the data is a role
    being set up to fail, so it is not shown the entry. Where NO role can open
    it, the entry is switched off entirely and the fact is logged — the screen
    is still there for the platform administrator, who keeps the bar.

    All three are re-decided on every run, so the day somebody gives a role the
    permission behind one of these screens, the next run puts the door back.
    """
    Item = env['cms.sidebar.item'].sudo().with_context(active_test=False)
    gated = switched_off = narrowed = 0
    no_audience = []
    for xmlid, names in NEW_ITEM_ROLES.items():
        item = env.ref(xmlid, raise_if_not_found=False)
        if not item:
            continue
        roles = env['biz.access.role'].sudo().browse()
        for name in names:
            roles |= role_by_name(env, name)
        if not roles:
            # NEVER GATE TO NOBODY BY ACCIDENT. An entry limited to a role that
            # does not exist is hidden from everybody, which is a worse answer
            # than showing it to somebody whose permissions will politely
            # refuse — and this branch is about a MISSING ROLE, not about a
            # screen nobody may open.
            _logger.warning(
                'health_access: none of the roles %s exist, so "%s" is left '
                'open to everybody rather than hidden from everybody',
                list(names), xmlid)
            continue

        # Where an entry is a heading, the screens are its children's; the
        # heading itself is judged by whether anything under it survives.
        model = model_behind(env, item)
        if model:
            able = roles.filtered(lambda r: role_can_read(env, r, model))
        else:
            able = roles
        if able != roles:
            narrowed += 1
            _logger.info(
                'health_access: "%s" is not offered to %s — they cannot open '
                '%s', item.name,
                ', '.join((roles - able).mapped('name')), model)
        if not able:
            no_audience.append('%s (%s)' % (item.name, model))
        if set(item.biz_role_ids.ids) != set(able.ids):
            item.write({'biz_role_ids': [(6, 0, able.ids)]})
            gated += 1

    # Every entry this module ships, its children included. CHILDREN FIRST,
    # because a heading is alive exactly when something under it is, and a
    # heading judged before its children would be judged on yesterday's answer.
    ours = Item.search([('id', 'in', _our_new_item_ids(env))])
    leaves = ours.filtered(lambda i: i.action_xmlid)
    headings = ours - leaves
    for item in leaves:
        model = model_behind(env, item)
        opens = bool(env.ref(item.action_xmlid, raise_if_not_found=False))
        if opens and model:
            # SOMEBODY has to be able to open it. The audience is whatever the
            # entry inherits — its own roles, its heading's, its block's.
            audience = item.effective_biz_role_ids.filtered('active')
            if audience:
                opens = any(role_can_read(env, r, model) for r in audience)
                if not opens:
                    no_audience.append('%s (%s)' % (item.name, model))
        if item.active != opens:
            item.write({'active': opens})
            switched_off += 0 if opens else 1
    for item in headings:
        alive = bool(Item.search_count(
            [('parent_id', '=', item.id), ('active', '=', True)]))
        if item.active != alive:
            item.write({'active': alive})
            switched_off += 0 if alive else 1
    _logger.info(
        'health_access: %s new left-menu entry(ies) gated, %s narrowed to the '
        'roles that can open them, %s switched off because nothing on this '
        'database can open them%s',
        gated, narrowed, switched_off,
        (' — ' + '; '.join(no_audience)) if no_audience else '')
    return gated


def _our_new_item_ids(env):
    """The ids of every entry `data/cms_sidebar_items_topbar.xml` created."""
    rows = env['ir.model.data'].sudo().search([
        ('module', '=', 'health_access'),
        ('model', '=', 'cms.sidebar.item'),
    ])
    return [r.res_id for r in rows]


def post_init_hook(env):
    """Everything, in order, the day this module lands."""
    if not isinstance(env, api.Environment):            # pragma: no cover
        env = api.Environment(env, SUPERUSER_ID, {})
    ensure_catalogue(env)
    migrate_legacy(env)
    retire_legacy(env)
    _gate_admin_item(env)
    _gate_new_items(env)
    _release_borrowed_matches(env)


def _release_borrowed_matches(env):
    """Hand two screens back now that each has a door of its own.

    "Channels (setup)" answered for the message store and the ops audit while
    neither had an entry on this menu. Both do now, and the highlight index is
    last-wins, so leaving them declared on the borrower would light up the
    wrong entry when somebody opens one.
    """
    host = env.ref(BORROWER_XMLID, raise_if_not_found=False)
    if not host or 'match_action_xmlids' not in host._fields:
        return 0
    declared = [v.strip() for v in (host.match_action_xmlids or '').split(',')
                if v.strip()]
    kept = [v for v in declared if v not in BORROWED_MATCHES]
    if kept == declared:
        return 0
    host.sudo().write({'match_action_xmlids': ','.join(kept)})
    _logger.info(
        'health_access: "%s" no longer answers for %s — each has its own '
        'entry now', host.name, ', '.join(set(declared) - set(kept)))
    return len(declared) - len(kept)
