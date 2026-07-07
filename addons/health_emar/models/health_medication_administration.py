# -*- coding: utf-8 -*-
"""Medication administration record — FHIR MedicationAdministration
(spec §3.2.3).

Append-only discipline (aged-care audit requirement): once a tick is
recorded (given / not_given / refused) the row is immutable except
``notes``. Corrections follow the health.observation amended lifecycle
— head_nurse+ may amend the recorded values; the amendment is flagged
(``is_amended`` + who/when) and the before→after trail is preserved in
the chatter (mail.thread tracking), never silently edited.
"""
import logging
from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

RECORDED_STATES = ('given', 'not_given', 'refused')
# Non-clinical/technical fields always writable (mail machinery etc.).
AMEND_EXEMPT_FIELDS = {'notes'}


class HealthMedicationAdministration(models.Model):
    _name = 'health.medication.administration'
    _description = 'Medication Administration Record'
    _inherit = ['mail.thread']
    _order = 'planned_datetime desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    order_id = fields.Many2one(
        'health.medication.order', string='Medication Order',
        required=True, ondelete='cascade', index=True)
    client_id = fields.Many2one(
        related='order_id.client_id', store=True, index=True,
        string='Client')
    medication_id = fields.Many2one(
        related='order_id.medication_id', store=True,
        string='Medication')
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit',
        ondelete='set null', index=True,
        help='The visit it is administered in; FHIR context')
    nurse_id = fields.Many2one(
        'res.users', string='Nurse', readonly=True,
        help='Set on recording; FHIR performer')
    planned_datetime = fields.Datetime(
        required=True, index=True, string='Planned Time',
        help='Scheduled slot (UTC; generated from admin_times in the '
             'booking timezone — fso.booking_timezone when linked, else '
             'facility/catchment timezone, Asia/Ho_Chi_Minh fallback)')
    actual_datetime = fields.Datetime(
        readonly=True, string='Actual Time',
        help='When actually given/attempted')
    state = fields.Selection([
        ('planned', 'Planned'),
        ('given', 'Given'),
        ('not_given', 'Not Given'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled'),
    ], default='planned', required=True, tracking=True, index=True,
        help='FHIR MedicationAdministration.status: given→completed, '
             'not_given/refused→not-done (+statusReason), '
             'cancelled→stopped')
    reason_id = fields.Many2one(
        'health.medication.notgiven.reason', string='Reason',
        tracking=True, help='FHIR statusReason — aged-care audit '
                            'requirement for not-given/refused ticks')
    dose_given = fields.Float(
        tracking=True,
        help='FHIR dosage.dose.value (may differ from ordered); '
             'defaults from the order dose on recording')
    dose_unit = fields.Char(
        related='order_id.dose_unit', store=True, string='Unit')
    witness_id = fields.Many2one(
        'res.users', string='Witness',
        help='Double-signoff (high-risk meds); FHIR performer with '
             'function code witness')
    notes = fields.Text(help='FHIR note')
    is_prn_dose = fields.Boolean(
        default=False, readonly=True,
        help='Created ad-hoc for a PRN order')
    is_amended = fields.Boolean(
        default=False, readonly=True, copy=False,
        help='A recorded tick was corrected by a head nurse+ '
             '(amendment audit — original values in the chatter)')
    amended_by_id = fields.Many2one(
        'res.users', readonly=True, copy=False, string='Amended By')
    amended_date = fields.Datetime(
        readonly=True, copy=False, string='Amended On')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')

    def init(self):
        # Odoo 19 does not materialize _sql_constraints — unique slot
        # index created explicitly. PRN doses get
        # planned_datetime = creation instant (always unique in
        # practice); the constraint stays global per spec.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_medication_administration_uniq_slot
            ON health_medication_administration (order_id, planned_datetime)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('medication_id.name', 'client_id.name',
                 'planned_datetime', 'fso_id.booking_timezone')
    def _compute_display_name(self):
        for admin in self:
            local = ''
            if admin.planned_datetime:
                tz = admin._get_local_timezone()
                local = pytz.utc.localize(admin.planned_datetime) \
                    .astimezone(tz).strftime('%d/%m %H:%M')
            admin.display_name = '%s %s — %s' % (
                admin.medication_id.name or '?', local,
                admin.client_id.name or '?')

    @api.depends('order_id.client_id.catchment_province_id',
                 'order_id.client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            client = rec.order_id.client_id
            rec.catchment_province_id = (
                client._get_health_catchment_province() if client else False)

    def _get_local_timezone(self):
        """Booking timezone when a visit is linked, else the order's
        facility/catchment timezone (Asia/Ho_Chi_Minh fallback)."""
        self.ensure_one()
        if self.fso_id and self.fso_id.booking_timezone:
            try:
                return pytz.timezone(self.fso_id.booking_timezone)
            except pytz.UnknownTimeZoneError:
                pass
        if self.order_id:
            return self.order_id._get_order_timezone()
        return pytz.timezone('Asia/Ho_Chi_Minh')

    def _get_local_date(self):
        self.ensure_one()
        if not self.planned_datetime:
            return False
        return pytz.utc.localize(self.planned_datetime) \
            .astimezone(self._get_local_timezone()).date()

    # ------------------------------------------------------------------
    # Constraints (also enforced in create()/recording methods —
    # Odoo 19 gotcha: constrains may not fire on create)
    # ------------------------------------------------------------------
    @api.constrains('state', 'reason_id')
    def _check_reason_required(self):
        for admin in self:
            if admin.state in ('not_given', 'refused'):
                if not admin.reason_id:
                    raise ValidationError(_(
                        'A reason is required when recording a dose as '
                        'not given or refused (audit requirement).'))
                admin._check_reason_applies(admin.state, admin.reason_id)

    @api.model
    def _check_reason_applies(self, state, reason):
        expected = 'refused' if state == 'refused' else 'not_given'
        if reason.applies_to not in (expected, 'both'):
            raise ValidationError(_(
                'Reason "%(reason)s" does not apply to %(state)s '
                'administrations.', reason=reason.name, state=state))

    # ------------------------------------------------------------------
    # ORM overrides — append-only discipline
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        admins = super().create(vals_list)
        admins._check_reason_required()
        return admins

    def write(self, vals):
        protected = {
            key for key in vals
            if key not in AMEND_EXEMPT_FIELDS
            and not key.startswith('message_')
            and not key.startswith('activity_')
        }
        recorded = self.filtered(lambda a: a.state in RECORDED_STATES) \
            if protected else self.browse()
        if recorded:
            if not self._is_head_nurse_plus():
                raise UserError(_(
                    'Recorded administrations are append-only: only the '
                    'notes may be edited. Ask a head nurse to amend the '
                    'record (correction is logged, never silent).'))
            # Amendment path (health.observation amended lifecycle):
            # flag + audit; old→new values are captured by tracking and
            # an explicit chatter message.
            for admin in recorded:
                before = ', '.join(
                    '%s: %s' % (key, admin[key]) for key in sorted(protected))
                admin.message_post(body=_(
                    'Administration amended by %(user)s. Previous values '
                    '— %(before)s', user=self.env.user.name, before=before))
            amend_vals = dict(vals, is_amended=True,
                              amended_by_id=self.env.uid,
                              amended_date=fields.Datetime.now())
            result = super(HealthMedicationAdministration,
                           recorded).write(amend_vals)
            remaining = self - recorded
            if remaining:
                result = super(HealthMedicationAdministration,
                               remaining).write(vals)
            return result
        return super().write(vals)

    def unlink(self):
        if not self._is_admin_plus():
            blocked = self.filtered(
                lambda a: a.state not in ('planned', 'cancelled'))
            if blocked:
                raise UserError(_(
                    'Recorded administrations cannot be deleted '
                    '(clinical record integrity).'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Group helpers
    # ------------------------------------------------------------------
    def _is_head_nurse_plus(self):
        user = self.env.user
        return (self.env.su
                or user.has_group('health_base.group_healthcare_head_nurse')
                or user.has_group('health_base.group_healthcare_admin')
                or user.has_group('health_base.group_healthcare_owner'))

    def _is_admin_plus(self):
        user = self.env.user
        return (self.env.su
                or user.has_group('health_base.group_healthcare_admin')
                or user.has_group('health_base.group_healthcare_owner'))

    # ------------------------------------------------------------------
    # Recording methods (§3.3) — the PWA tick backend. Recording is
    # allowed for nurse+ (ACL: nurses have write on this model).
    # ------------------------------------------------------------------
    def _ensure_planned(self):
        self.ensure_one()
        if self.state != 'planned':
            raise UserError(_(
                'This administration is already recorded (%s) — '
                'administrations are append-only.', self.state))

    def action_record_given(self, actual_datetime=None, dose_given=None,
                            witness_id=None, notes=None):
        self._ensure_planned()
        if self.order_id.state != 'active':
            raise UserError(_(
                'Doses can only be recorded against an active order.'))
        vals = {
            'state': 'given',
            'nurse_id': self.env.uid,
            'actual_datetime': actual_datetime or fields.Datetime.now(),
            'dose_given': dose_given or self.order_id.dose_quantity,
        }
        if witness_id:
            vals['witness_id'] = witness_id
        if notes:
            vals['notes'] = notes
        self.write(vals)
        return True

    def action_record_not_given(self, reason_id, notes=None):
        self._ensure_planned()
        reason = self._browse_reason(reason_id)
        self._check_reason_applies('not_given', reason)
        vals = {
            'state': 'not_given',
            'nurse_id': self.env.uid,
            'actual_datetime': fields.Datetime.now(),
            'reason_id': reason.id,
        }
        if notes:
            vals['notes'] = notes
        self.write(vals)
        return True

    def action_record_refused(self, reason_id, notes=None):
        self._ensure_planned()
        reason = self._browse_reason(reason_id)
        self._check_reason_applies('refused', reason)
        vals = {
            'state': 'refused',
            'nurse_id': self.env.uid,
            'actual_datetime': fields.Datetime.now(),
            'reason_id': reason.id,
        }
        if notes:
            vals['notes'] = notes
        self.write(vals)
        return True

    def action_cancel_slot(self):
        for admin in self:
            if admin.state != 'planned':
                raise UserError(_(
                    'Only planned administrations can be cancelled.'))
        if not self._is_head_nurse_plus():
            raise UserError(_(
                'Only head nurses and above can cancel planned '
                'administration slots.'))
        self.write({'state': 'cancelled'})
        return True

    def _browse_reason(self, reason_id):
        reason = self.env['health.medication.notgiven.reason'].browse(
            int(reason_id)) if reason_id else None
        if not reason or not reason.exists():
            raise UserError(_(
                'A valid reason is required (audit requirement).'))
        return reason

    # UI wrappers — the API methods above take positional args which
    # form-view buttons cannot pass; the backend form lets the user set
    # reason_id on the planned row first, then press the button.
    def action_ui_record_given(self):
        return self.action_record_given()

    def action_ui_record_not_given(self):
        self.ensure_one()
        if not self.reason_id:
            raise UserError(_('Set the reason first (audit requirement).'))
        return self.action_record_not_given(self.reason_id.id)

    def action_ui_record_refused(self):
        self.ensure_one()
        if not self.reason_id:
            raise UserError(_('Set the reason first (audit requirement).'))
        return self.action_record_refused(self.reason_id.id)

    # ------------------------------------------------------------------
    # PRN doses (§3.4)
    # ------------------------------------------------------------------
    @api.model
    def create_prn_dose(self, order, fso=None):
        """Ad-hoc dose for a PRN order (PWA '+ dose' button): a slot at
        'now', immediately ready to record."""
        if not order or order.state != 'active':
            raise UserError(_(
                'PRN doses can only be created for active orders.'))
        if not order.is_prn:
            raise UserError(_(
                'Ad-hoc doses are only allowed for PRN orders.'))
        return self.create({
            'order_id': order.id,
            'planned_datetime': fields.Datetime.now(),
            'is_prn_dose': True,
            'fso_id': fso.id if fso else False,
        })

    # ------------------------------------------------------------------
    # FSO slot linking (§3.4)
    # ------------------------------------------------------------------
    def _link_administrations_to_fso(self):
        """Link unlinked planned slots to the client's visit on the
        slot's local date (state confirmed/assigned/in_progress; nearest
        scheduled_datetime wins)."""
        FSO = self.env['health.fieldservice.order'].sudo()
        for admin in self.filtered(
                lambda a: a.state == 'planned' and not a.fso_id):
            local_date = admin._get_local_date()
            if not local_date:
                continue
            candidates = FSO.search([
                ('patient_id', '=', admin.client_id.id),
                ('state', 'in', ('confirmed', 'assigned', 'in_progress')),
                ('scheduled_date', '=', local_date),
            ])
            if not candidates:
                continue
            best = min(candidates, key=lambda fso: abs(
                (fso.scheduled_datetime or admin.planned_datetime)
                - admin.planned_datetime))
            admin.write({'fso_id': best.id})
        return True

    def _fso_date_matches(self):
        """True when the linked visit is still on the slot's local date."""
        self.ensure_one()
        if not self.fso_id or not self.fso_id.scheduled_date:
            return False
        return self.fso_id.scheduled_date == self._get_local_date()
