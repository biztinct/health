# -*- coding: utf-8 -*-
"""Role gating for the nineteen leaves — applied in python, not XML.

`access.role` records on this deployment are **database rows with no xml-id**
(measured: Owner, Operations Manager, Branch Manager, Banker, Nurse, Doctor,
Accountant, Admin, CRM — none of them appear in `ir_model_data`), so
`role_ids` cannot be seeded with `ref()`. The 34 gated items that shipped
before this module were gated the same way: by writing the relation, which is
why `grep role_ids data/*.xml` finds almost nothing and the live catalogue is
nonetheless role-aware.

Why gate at all — the defect this closes, found by driving the shell as the
real `crm` user after the first install: with no `role_ids`, all nineteen
leaves were served to every role. A receptionist was shown an entire FINANCE
section (which their sidebar has never had) and got
"You are not allowed to access 'BHYT Insurance Claim'" on click. The gate
below reproduces each section's own established convention:

    CRM       → Owner + CRM                     (as Dashboard, Care Command, Contacts, Activities)
    OPS       → Owner + Operations Manager       (as Bookings, Staff, Staff Schedule, Workload…)
    FINANCE   → Owner + Accountant               (as every FINANCE leaf)
    CLINICAL  → ungated                          (as all 24 existing CLINICAL items)

with ONE measured exception: `health.scribe.job` is readable only by Owner /
Operations Manager / Branch Manager, so **Voice Notes** is gated rather than
left as a leaf that refuses the clinical roles it would be drawn for. Every
other CLINICAL model here (condition, clinical note, careplan task, AI
suggestion, portal access, consent check log) is readable by the ungated
audience, verified per role before this file was written.

Runs from ``post_init_hook`` AND from the 19.0.1.1.0 migration, so a fresh
install and an upgrade of an already-installed copy converge on the same state.
"""
import logging

_logger = logging.getLogger(__name__)

# leaf xml-id -> role NAMES that may see it. Absent from this map ⇒ ungated.
ROLE_GATES = {
    # CRM
    'item_crm_channels_setup': ('Owner', 'CRM'),
    'item_crm_reply_templates': ('Owner', 'CRM'),
    'item_crm_followup_calendar': ('Owner', 'CRM'),
    'item_crm_relationships': ('Owner', 'CRM'),
    # OPERATIONS MANAGER
    'item_ops_telehealth': ('Owner', 'Operations Manager'),
    'item_ops_selfbooking': ('Owner', 'Operations Manager'),
    'item_ops_family_links': ('Owner', 'Operations Manager'),
    'item_ops_family_messages': ('Owner', 'Operations Manager'),
    'item_ops_route_feasibility': ('Owner', 'Operations Manager'),
    # CLINICAL — the one exception (see module docstring)
    'item_clin_voice_notes': ('Owner', 'Operations Manager', 'Branch Manager'),
    # FINANCE
    'item_fin_bhyt_claims': ('Owner', 'Accountant'),
    'item_fin_service_packages': ('Owner', 'Accountant'),
    'item_fin_red_invoice_log': ('Owner', 'Accountant'),
}


def apply_role_gates(env):
    """Write ``role_ids`` on the gated leaves. Idempotent, and never blinding.

    A role name this deployment does not have is skipped rather than written as
    an empty set: ``[(6, 0, [])]`` would gate the leaf to NOBODY, which is a
    worse outcome than leaving it visible (the model ACL still refuses the
    data). If NONE of a leaf's roles exist, the leaf is left ungated and the
    fact is logged — silence there would hide a feature completely.
    """
    by_name = {r.name: r.id for r in env['access.role'].sudo().search([])}
    gated = skipped = 0
    for xmlid, names in ROLE_GATES.items():
        item = env.ref('health_cms_coverage.%s' % xmlid,
                       raise_if_not_found=False)
        if not item:
            continue
        role_ids = [by_name[name] for name in names if name in by_name]
        if not role_ids:
            skipped += 1
            _logger.warning(
                'health_cms_coverage: none of the roles %s exist on this '
                'database — leaving %s visible to every role rather than '
                'hiding it from everyone', list(names), xmlid)
            continue
        item.sudo().write({'role_ids': [(6, 0, role_ids)]})
        gated += 1
    _logger.info('health_cms_coverage: role-gated %s sidebar leaves '
                 '(%s left ungated for want of a role)', gated, skipped)
    return gated


def post_init_hook(env):
    apply_role_gates(env)
