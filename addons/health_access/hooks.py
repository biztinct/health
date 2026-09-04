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
     ('health_user_admin.group_health_user_admin',)),
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
              'user-admin'),
    'Operations Manager': (
        'sign-in', 'care-base', 'reception', 'nursing', 'head-nursing',
        'doctoring', 'sales', 'ops-manage', 'finance-work', 'care-manage',
        'care-admin', 'ownership', 'patient-portal', 'crm-work', 'crm-manage',
        'invoicing-work', 'invoicing-manage', 'insurance-claims', 'misa-sync',
        'tax-compliance', 'red-invoice', 'accounting-invoices',
        'staff-records', 'sales-manage'),
    'Branch Manager': ('sign-in', 'coaching-branch'),
    'Banker': ('sign-in',),
    'Nurse': ('sign-in', 'care-base', 'nursing', 'patient-portal',
              'invoicing-work', 'invoicing-manage', 'misa-sync',
              'accounting-invoices'),
    'Doctor': ('sign-in', 'doctoring'),
    'Accountant': ('sign-in', 'care-base', 'finance-work', 'ops-manage',
                   'invoicing-work', 'invoicing-manage', 'insurance-claims',
                   'misa-sync', 'tax-compliance', 'red-invoice',
                   'accounting-invoices', 'sales-manage'),
    'Admin': ('sign-in', 'user-admin'),
    'CRM': ('sign-in', 'care-base', 'ops-manage', 'sales', 'crm-work',
            'crm-manage', 'sales-manage'),
}

#: The top-bar branch that belongs to the application being retired. It goes
#: with it, so carrying its rows across would be writing down a fact with a
#: known expiry date. The old application still hides it in the meantime.
LEGACY_MENU_XMLID = 'access_roles.access_role_menu_root'

#: The reason written on every grant this carry-over makes. It is what somebody
#: reads in the history months later when they ask why a person holds a role.
CARRY_REASON = 'carried over from the previous access app'


# =============================================================================
# REGISTRATION — at import time, so it counts however this module is loaded.
# =============================================================================
register_areas(AREAS, default=DEFAULT_AREA)

# WHO MAY GIVE AND TAKE ROLES HERE. This clinic has its own administrator tier
# and it is the tier that has always added colleagues; the Access home is the
# screen it does that on now. `base.group_system` stays with the platform, held
# by one account, and is not added to anything (the two-ring rule).
register_manager_groups('health_user_admin.group_health_user_admin')


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
    # And the same gate on the older lane, while the older lane is still read —
    # so the entry behaves identically for somebody whose role has been carried
    # over and somebody whose has not.
    if 'access.role' in env and 'role_ids' in item._fields:
        old = env['access.role'].sudo().with_context(active_test=False).search(
            [('name', 'in', list(ADMIN_ITEM_ROLES))])
        if old:
            item.sudo().write({'role_ids': [(6, 0, old.ids)]})
    _logger.info(
        'health_access: the Access home entry on the left menu is open to %s',
        ', '.join(roles.mapped('name')) or 'nobody yet')
    return True


def post_init_hook(env):
    """Everything, in order, the day this module lands."""
    if not isinstance(env, api.Environment):            # pragma: no cover
        env = api.Environment(env, SUPERUSER_ID, {})
    ensure_catalogue(env)
    migrate_legacy(env)
    _gate_admin_item(env)
