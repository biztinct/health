# -*- coding: utf-8 -*-
"""UAT round 10, items 1 and 2 — data.

  * Users (their partner) and staff records (their resource) stored with the
    browser's alias "Asia/Saigon" move to "Asia/Ho_Chi_Minh". Only partners
    that belong to a login and resources that belong to a staff record.
  * Active staff records whose login is switched off are archived the way a
    switch-off now does it (marked "archived with their login", so switching
    the login back on restores them). Never the platform's own accounts.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE res_partner SET tz = 'Asia/Ho_Chi_Minh'
         WHERE tz = 'Asia/Saigon'
           AND id IN (SELECT partner_id FROM res_users)
     RETURNING id""")
    partners = [r[0] for r in cr.fetchall()]
    cr.execute("""
        UPDATE resource_resource SET tz = 'Asia/Ho_Chi_Minh'
         WHERE tz = 'Asia/Saigon'
           AND id IN (SELECT resource_id FROM hr_employee)
     RETURNING id""")
    resources = [r[0] for r in cr.fetchall()]
    _logger.info('health_access 19.0.1.9.1: time zone Asia/Saigon -> '
                 'Asia/Ho_Chi_Minh on user partners %s, staff resources %s',
                 partners, resources)

    env = api.Environment(cr, SUPERUSER_ID, {})
    Users = env['res.users'].with_context(active_test=False)
    employees = env['hr.employee'].with_context(active_test=False).search([
        ('active', '=', True), ('user_id', '!=', False),
        ('user_id.active', '=', False)])
    users = employees.mapped('user_id')
    before = set(employees.ids)
    Users.browse(users.ids)._sync_staff_with_login(False)
    employees.invalidate_recordset(['active'])
    archived = [e for e in employees if not e.active]
    _logger.info('health_access 19.0.1.9.1: archived %s staff record(s) whose '
                 'login is switched off: %s (of %s candidates)', len(archived),
                 ['%s %s' % (e.id, e.name) for e in archived], len(before))
