import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Field Service Order',
        index=True, copy=False,
        help='Visit this attendance was auto-created from (PWA check-in/out).')
    attendance_source = fields.Selection(
        [('manual', 'Manual'), ('pwa_visit', 'PWA Visit')],
        default='manual', required=True,
        help='How this attendance row was created.')


class HealthFieldServiceOrderAttendance(models.Model):
    """E.4 — auto-fill hr.attendance from visit check-in / check-out.

    Payroll truth stays on hr.attendance; per-visit truth stays on the FSO.
    A nightly reconcile surfaces >15-min gaps for a human without ever
    silently overwriting payroll.
    """
    _inherit = 'health.fieldservice.order'

    @api.model
    def _timecard_sync_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'health_workflow_auto.timecard_sync_enabled', 'False'
        ) in ('True', 'true', '1')

    def _visit_employees(self):
        """Employees on this visit (lead + assignments) that have a linked user."""
        self.ensure_one()
        emps = self.lead_staff_id | self.assignment_ids.mapped('staff_id')
        return emps.filtered(lambda e: e.user_id)

    def action_start_service(self):
        res = super().action_start_service()
        for o in self:
            if o._timecard_sync_enabled():
                o._attendance_open()
        return res

    def _attendance_open(self):
        """Open an hr.attendance per visiting employee unless one is already open.

        A nurse chaining visits keeps ONE open attendance — per-visit truth lives
        on the FSO, so we do not create a second row while one is open.
        """
        self.ensure_one()
        start = self.actual_start_datetime or fields.Datetime.now()
        Attendance = self.env['hr.attendance']
        for emp in self._visit_employees():
            open_att = Attendance.search([
                ('employee_id', '=', emp.id),
                ('check_out', '=', False),
            ], limit=1)
            if open_att:
                continue
            try:
                # Guard against the standard hr.attendance overlap constraint
                # (a manually-closed attendance overlapping this check-in would
                # raise) — a failed open must never block starting the visit.
                with self.env.cr.savepoint():
                    Attendance.create({
                        'employee_id': emp.id,
                        'check_in': start,
                        'fso_id': self.id,
                        'attendance_source': 'pwa_visit',
                    })
            except Exception as exc:  # noqa: BLE001
                _logger.warning('Timecard: could not open attendance for employee '
                                '%s on FSO %s: %s', emp.id, self.name, exc)

    def action_complete_service(self):
        res = super().action_complete_service()
        # A6: close AFTER super() so actual_end_datetime is populated.
        for o in self:
            if o._timecard_sync_enabled():
                o._attendance_close()
        return res

    def _attendance_close(self):
        """Close attendances opened by this FSO. Manual attendances untouched."""
        self.ensure_one()
        end = self.actual_end_datetime or fields.Datetime.now()
        atts = self.env['hr.attendance'].search([
            ('fso_id', '=', self.id),
            ('check_out', '=', False),
        ])
        for att in atts:
            try:
                with self.env.cr.savepoint():
                    att.check_out = end
            except Exception as exc:  # noqa: BLE001
                _logger.warning('Timecard: could not close attendance %s for FSO '
                                '%s: %s', att.id, self.name, exc)
