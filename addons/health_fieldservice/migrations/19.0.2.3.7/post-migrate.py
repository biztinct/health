# -*- coding: utf-8 -*-
"""Post-migration: assign Nurse/Doctor access roles to assigned booking staff.

Wraps health.staff.assignment.migrate_booking_staff_roles() so every upgrade /
data load gives assigned staff the correct access role (creating an internal,
no-invitation user when they have none) and clears the deprecated
`healthcare_role` tag. The method is idempotent — a re-run no-ops on staff that
already hold the right role, so this is safe to run on every upgrade to 2.3.7+.

Scope is intentionally limited to the ROLE migration. Province/Facility back-fill
is handled separately (operational data correction), NOT in this migration.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    summary = env['health.staff.assignment'].migrate_booking_staff_roles()
    if summary.get('error'):
        _logger.warning("Staff-role migration skipped: %s", summary['error'])
        return
    _logger.info(
        "Staff-role migration done: %s nurses, %s doctors, %s users created, "
        "%s healthcare_role cleaned, %s skipped, %s already correct, %s kept other role",
        summary.get('nurses_done', 0), summary.get('doctors_done', 0),
        summary.get('users_created', 0), summary.get('cleaned', 0),
        summary.get('skipped', 0), summary.get('already_ok', 0),
        summary.get('kept_other_role', 0),
    )
