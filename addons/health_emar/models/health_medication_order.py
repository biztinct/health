# -*- coding: utf-8 -*-
"""Medication order — the FHIR MedicationRequest side (spec §3.2.2).

Structured Dosage (dose qty/unit/route/frequency/PRN flag/start/end)
sits alongside the existing free-text
``health.clinical.note.medications_prescribed`` (coding-sidecar
pattern — the free text is never removed or migrated).

Schedule generation is timezone-aware: ``admin_times`` are wall-clock
times in the client's local timezone (facility / catchment timezone,
``Asia/Ho_Chi_Minh`` fallback — same basis as
``health.fieldservice.order.booking_timezone``), stored as naive UTC
on the administration rows.
"""
import logging
from datetime import datetime, time as dt_time, timedelta

import pytz

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Fields that must be set before an order can be activated (spec:
# "required-for-activate" — not required at draft time).
ACTIVATE_REQUIRED_FIELDS = [
    ('dose_quantity', 'Dose Quantity'),
    ('dose_unit', 'Dose Unit'),
    ('route', 'Route'),
    ('frequency', 'Frequency'),
    ('start_date', 'Start Date'),
]

# Default local slot times per frequency (spec §3.4). q4h/q6h/q8h/q12h
# are spread evenly from 06:00 across the 24h day.
FREQUENCY_DEFAULT_TIMES = {
    'od': ['08:00'],
    'bd': ['08:00', '20:00'],
    'tds': ['08:00', '13:00', '20:00'],
    'qid': ['06:00', '12:00', '18:00', '22:00'],
    'q4h': ['02:00', '06:00', '10:00', '14:00', '18:00', '22:00'],
    'q6h': ['00:00', '06:00', '12:00', '18:00'],
    'q8h': ['06:00', '14:00', '22:00'],
    'q12h': ['06:00', '18:00'],
    'weekly': ['08:00'],
}

SEVERITY_RANK = {'none': 0, 'minor': 1, 'moderate': 2, 'major': 3}


class HealthMedicationOrder(models.Model):
    _name = 'health.medication.order'
    _description = 'Medication Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    name = fields.Char(
        readonly=True, copy=False, default=lambda self: _('New'),
        string='Reference')
    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        domain=[('is_patient', '=', True)], ondelete='restrict',
        index=True, tracking=True, help='FHIR MedicationRequest.subject')
    medication_id = fields.Many2one(
        'health.medication', string='Medication', required=True,
        ondelete='restrict', tracking=True,
        help='FHIR MedicationRequest.medication')
    prescriber_id = fields.Many2one(
        'res.partner', string='Prescriber', tracking=True,
        help='External or internal prescribing doctor (contact record)')
    prescriber_name = fields.Char(
        string='Prescriber Name',
        help='Free-text fallback when no contact exists')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True,
        help="FHIR MedicationRequest.status (on_hold maps to 'on-hold')")
    dose_quantity = fields.Float(
        string='Dose Quantity', tracking=True,
        help='FHIR Dosage.doseAndRate.doseQuantity.value')
    dose_unit = fields.Char(
        string='Dose Unit', tracking=True,
        help='UCUM or common unit: mg, mL, tablet, IU, puff')
    route = fields.Selection([
        ('oral', 'Oral'),
        ('sublingual', 'Sublingual'),
        ('topical', 'Topical'),
        ('subcutaneous', 'Subcutaneous'),
        ('intramuscular', 'Intramuscular'),
        ('intravenous', 'Intravenous'),
        ('inhalation', 'Inhalation'),
        ('rectal', 'Rectal'),
        ('ophthalmic', 'Ophthalmic'),
        ('otic', 'Otic'),
        ('nasal', 'Nasal'),
        ('other', 'Other'),
    ], tracking=True, help='FHIR Dosage.route')
    frequency = fields.Selection([
        ('od', 'Once daily (OD)'),
        ('bd', 'Twice daily (BD)'),
        ('tds', 'Three times daily (TDS)'),
        ('qid', 'Four times daily (QID)'),
        ('q4h', 'Every 4 hours'),
        ('q6h', 'Every 6 hours'),
        ('q8h', 'Every 8 hours'),
        ('q12h', 'Every 12 hours'),
        ('weekly', 'Weekly'),
        ('prn', 'PRN / As needed'),
        ('other', 'Other — see instructions'),
    ], tracking=True, help='FHIR Dosage.timing')
    admin_times = fields.Char(
        string='Administration Times',
        help='Comma-separated local times HH:MM, e.g. 08:00,20:00. '
             'Optional; defaults per frequency.')
    is_prn = fields.Boolean(
        string='PRN', compute='_compute_is_prn', store=True,
        help='FHIR Dosage.asNeededBoolean')
    prn_reason = fields.Char(
        string='PRN Reason',
        help='FHIR Dosage.asNeededCodeableConcept.text')
    start_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True,
        help='FHIR dispenseRequest.validityPeriod.start / dosage '
             'boundsPeriod.start')
    end_date = fields.Date(
        tracking=True, help='boundsPeriod.end (open = long-term)')
    instructions = fields.Text(
        translate=True, help='FHIR Dosage.patientInstruction')
    interaction_warning = fields.Text(
        readonly=True, string='Interaction Warning')
    interaction_severity = fields.Selection([
        ('none', 'None'),
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
    ], default='none', readonly=True, tracking=True,
        string='Interaction Severity', help='Highest severity found')
    interaction_ack = fields.Boolean(
        string='Interaction Acknowledged', tracking=True,
        help='Head-nurse/doctor acknowledgement of major interactions')
    interaction_ack_by_id = fields.Many2one(
        'res.users', readonly=True, string='Acknowledged By')
    interaction_ack_date = fields.Datetime(
        readonly=True, string='Acknowledged On')
    administration_ids = fields.One2many(
        'health.medication.administration', 'order_id',
        string='Administrations')
    administration_count = fields.Integer(
        compute='_compute_administration_count')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    def init(self):
        # Odoo 19 does not materialize _sql_constraints — add the CHECK
        # constraints explicitly (platform gotcha). The same rules are
        # also enforced in Python for friendly errors.
        cr = self.env.cr
        for conname, definition in [
            ('health_medication_order_date_check',
             'CHECK (end_date IS NULL OR end_date >= start_date)'),
            ('health_medication_order_dose_positive',
             'CHECK (dose_quantity IS NULL OR dose_quantity > 0)'),
        ]:
            cr.execute(
                "SELECT 1 FROM pg_constraint WHERE conname = %s",
                (conname,))
            if not cr.fetchone():
                cr.execute(
                    "ALTER TABLE health_medication_order "
                    "ADD CONSTRAINT %s %s" % (conname, definition))

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('medication_id.name', 'client_id.name', 'name')
    def _compute_display_name(self):
        for order in self:
            order.display_name = '%s — %s (%s)' % (
                order.medication_id.name or '?',
                order.client_id.name or '?',
                order.name or _('New'))

    @api.depends('frequency')
    def _compute_is_prn(self):
        for order in self:
            order.is_prn = order.frequency == 'prn'

    def _compute_administration_count(self):
        counts = {}
        if self.ids:
            for group in self.env['health.medication.administration']._read_group(
                    [('order_id', 'in', self.ids)], ['order_id'], ['__count']):
                counts[group[0].id] = group[1]
        for order in self:
            order.administration_count = counts.get(order.id, 0)

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    # ------------------------------------------------------------------
    # Constraints (also enforced in create() — Odoo 19 gotcha:
    # api.constrains does not fire on create when none of the
    # constrained fields are in vals)
    # ------------------------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for order in self:
            if order.end_date and order.start_date \
                    and order.end_date < order.start_date:
                raise ValidationError(
                    _('End date must be on/after start date.'))

    @api.constrains('dose_quantity')
    def _check_dose_positive(self):
        for order in self:
            if order.dose_quantity and order.dose_quantity < 0:
                raise ValidationError(_('Dose must be positive.'))

    @api.constrains('frequency', 'prn_reason')
    def _check_prn_reason(self):
        for order in self:
            if order.is_prn and not order.prn_reason:
                raise ValidationError(
                    _('PRN orders require a PRN reason.'))

    @api.constrains('admin_times')
    def _check_admin_times(self):
        for order in self:
            order._parse_admin_times()  # raises on bad format

    def _parse_admin_times(self):
        """Return the list of (hour, minute) parsed from admin_times,
        or None when admin_times is empty."""
        self.ensure_one()
        if not self.admin_times:
            return None
        slots = []
        for chunk in self.admin_times.split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split(':')
            try:
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError()
            except (ValueError, IndexError):
                raise ValidationError(_(
                    'Invalid administration time %(chunk)s — use '
                    'comma-separated HH:MM local times, e.g. 08:00,20:00.',
                    chunk=chunk))
            slots.append((hour, minute))
        return slots or None

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'health.medication.order') or _('New')
            # Normalize unset dose (0.0 from form widgets) to NULL so the
            # dose_positive CHECK constraint only guards real values.
            if 'dose_quantity' in vals and not vals['dose_quantity']:
                vals['dose_quantity'] = False
        orders = super().create(vals_list)
        # Enforce constraints on create (gotcha: constrains may not fire).
        orders._check_dates()
        orders._check_dose_positive()
        orders._check_prn_reason()
        orders._check_admin_times()
        return orders

    def write(self, vals):
        if 'dose_quantity' in vals and not vals['dose_quantity']:
            vals = dict(vals, dose_quantity=False)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Group helpers
    # ------------------------------------------------------------------
    def _is_order_author(self):
        """head_nurse / doctor / manager+ may author & transition orders."""
        user = self.env.user
        return (self.env.su
                or user.has_group('health_base.group_healthcare_head_nurse')
                or user.has_group('health_base.group_healthcare_doctor')
                or user.has_group('health_base.group_healthcare_manager')
                or user.has_group('health_base.group_healthcare_admin')
                or user.has_group('health_base.group_healthcare_owner'))

    def _is_manager_plus(self):
        user = self.env.user
        return (self.env.su
                or user.has_group('health_base.group_healthcare_manager')
                or user.has_group('health_base.group_healthcare_admin')
                or user.has_group('health_base.group_healthcare_owner'))

    def _ensure_order_author(self):
        if not self._is_order_author():
            raise UserError(_(
                'Only head nurses, doctors and managers can manage '
                'medication orders.'))

    # ------------------------------------------------------------------
    # Timezone helpers (booking_timezone / Asia/Ho_Chi_Minh fallback
    # pattern — health.staff.assignment / FSO convention)
    # ------------------------------------------------------------------
    def _get_order_timezone(self):
        self.ensure_one()
        tz_name = (
            (self.client_id.primary_facility_id.timezone
             if self.client_id.primary_facility_id else False)
            or (self.catchment_province_id.timezone
                if self.catchment_province_id else False)
            or 'Asia/Ho_Chi_Minh')
        try:
            return pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone('Asia/Ho_Chi_Minh')

    # ------------------------------------------------------------------
    # State machine (§3.3)
    # ------------------------------------------------------------------
    def action_activate(self):
        self.ensure_one()
        self._ensure_order_author()
        if self.state != 'draft':
            raise UserError(_('Only draft orders can be activated.'))
        missing = [_(label) for field_name, label in ACTIVATE_REQUIRED_FIELDS
                   if not self[field_name]]
        if missing:
            raise UserError(_(
                'Cannot activate this order — missing: %s',
                ', '.join(missing)))
        check_vals = self._run_interaction_check()
        if (check_vals.get('interaction_severity') == 'major'
                and not self.interaction_ack):
            # Persist via a separate cursor BEFORE any write in this
            # transaction: writing first would lock the row and make the
            # second cursor block on our own lock (self-deadlock until
            # lock timeout). The UserError below rolls this transaction
            # back; the separate-cursor write is what survives.
            self._persist_interaction_result(check_vals)
            raise UserError(_(
                'Acknowledge major interaction first: a major drug '
                'interaction was detected. A head nurse, doctor or '
                'manager must acknowledge it before activation.'))
        self.write(dict(check_vals, state='active'))
        self.action_generate_schedule()
        return True

    def _persist_interaction_result(self, check_vals):
        """Write the interaction findings in an independent cursor so
        they survive the UserError rollback in action_activate."""
        if tools.config.get('test_enable') or tools.config.get('test_file'):
            # assertRaises wraps in a savepoint and rolls it back, so no
            # in-transaction write can survive; a second cursor would
            # deadlock with the test cursor. Tests simulate persistence
            # explicitly (see test_05_major_interaction_gate).
            return
        try:
            with self.pool.cursor() as cr:
                # Bound the wait in case some other transaction holds the
                # row — never hang a request on best-effort persistence.
                cr.execute("SET LOCAL lock_timeout = '2s'")
                self.with_env(self.env(cr=cr)).write(check_vals)
        except Exception:  # pragma: no cover - persistence is best-effort
            _logger.warning(
                'eMAR: could not persist interaction result for order %s',
                self.id, exc_info=True)

    def action_hold(self):
        self.ensure_one()
        self._ensure_order_author()
        if self.state != 'active':
            raise UserError(_('Only active orders can be put on hold.'))
        self._cancel_future_planned_administrations()
        self.write({'state': 'on_hold'})
        return True

    def action_resume(self):
        self.ensure_one()
        self._ensure_order_author()
        if self.state != 'on_hold':
            raise UserError(_('Only on-hold orders can be resumed.'))
        self.write({'state': 'active'})
        self.action_generate_schedule()
        return True

    def action_complete(self):
        self.ensure_one()
        self._ensure_order_author()
        if self.state != 'active':
            raise UserError(_('Only active orders can be completed.'))
        self.write({'state': 'completed'})
        return True

    def action_cancel(self):
        self.ensure_one()
        self._ensure_order_author()
        if self.state not in ('draft', 'active', 'on_hold'):
            raise UserError(_(
                'Only draft, active or on-hold orders can be cancelled.'))
        self._cancel_future_planned_administrations()
        self.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        self.ensure_one()
        if not self._is_manager_plus():
            raise UserError(_(
                'Only managers can reset a cancelled order to draft.'))
        if self.state != 'cancelled':
            raise UserError(_(
                'Only cancelled orders can be reset to draft.'))
        self.write({'state': 'draft'})
        return True

    def action_acknowledge_interaction(self):
        self.ensure_one()
        self._ensure_order_author()
        self.write({
            'interaction_ack': True,
            'interaction_ack_by_id': self.env.uid,
            'interaction_ack_date': fields.Datetime.now(),
        })
        self.message_post(body=_(
            'Major drug interaction acknowledged by %(user)s. '
            'Warning at acknowledgement: %(warning)s',
            user=self.env.user.name,
            warning=self.interaction_warning or '-'))
        return True

    def _cancel_future_planned_administrations(self):
        now = fields.Datetime.now()
        self.env['health.medication.administration'].search([
            ('order_id', 'in', self.ids),
            ('state', '=', 'planned'),
            ('planned_datetime', '>=', now),
        ]).write({'state': 'cancelled'})

    # ------------------------------------------------------------------
    # Interaction check (§3.4) — runs on activation against the client's
    # other active/on-hold orders. Combines the stored
    # health.medication.interaction catalog (offline-capable) with the
    # existing health.medication.safety RxNorm API check.
    # ------------------------------------------------------------------
    def _run_interaction_check(self):
        self.ensure_one()
        other_orders = self.search([
            ('client_id', '=', self.client_id.id),
            ('id', '!=', self.id),
            ('state', 'in', ('active', 'on_hold')),
        ])
        other_meds = other_orders.mapped('medication_id') - self.medication_id
        if not other_meds:
            return {'interaction_warning': False,
                    'interaction_severity': 'none'}

        findings = []
        # 1) Stored interaction catalog rows (health_base).
        stored = self.env['health.medication.interaction'].search([
            '|',
            '&', ('medication1_id', '=', self.medication_id.id),
                 ('medication2_id', 'in', other_meds.ids),
            '&', ('medication2_id', '=', self.medication_id.id),
                 ('medication1_id', 'in', other_meds.ids),
        ])
        for row in stored:
            findings.append({
                'medication1': row.medication1_id.name,
                'medication2': row.medication2_id.name,
                'severity': row.severity,
                'description': row.description,
                'source': row.source or _('Local catalog'),
            })
        # 2) Existing safety service (RxNorm API, takes medication names).
        api_unavailable = False
        med_names = [self.medication_id.name] + other_meds.mapped('name')
        try:
            findings += self.env['health.medication.safety'] \
                .check_drug_interactions(med_names) or []
        except Exception:
            _logger.warning(
                'eMAR: drug interaction check unavailable for order %s',
                self.id, exc_info=True)
            api_unavailable = True

        highest = 'none'
        lines = []
        seen = set()
        for finding in findings:
            severity = finding.get('severity')
            if severity not in ('minor', 'moderate', 'major'):
                # Map anything unknown to moderate (spec §3.4).
                severity = 'moderate'
            pair = tuple(sorted([str(finding.get('medication1')),
                                 str(finding.get('medication2'))]))
            if (pair, severity) in seen:
                continue
            seen.add((pair, severity))
            if SEVERITY_RANK[severity] > SEVERITY_RANK[highest]:
                highest = severity
            lines.append('%s + %s [%s]: %s (%s)' % (
                finding.get('medication1'), finding.get('medication2'),
                severity, finding.get('description') or '-',
                finding.get('source') or '-'))
        warning = '\n'.join(lines)
        if api_unavailable:
            warning = (warning + '\n' if warning else '') + _(
                'Interaction check unavailable')
        return {
            'interaction_warning': warning or False,
            'interaction_severity': highest,
        }

    # ------------------------------------------------------------------
    # Schedule generation (§3.4) — timezone-aware, idempotent
    # ------------------------------------------------------------------
    def _get_slot_times(self):
        """Local wall-clock (hour, minute) slot times for one order."""
        self.ensure_one()
        custom = self._parse_admin_times()
        if custom:
            return custom
        defaults = FREQUENCY_DEFAULT_TIMES.get(self.frequency) or []
        return [(int(value[:2]), int(value[3:])) for value in defaults]

    def action_generate_schedule(self, date_from=None, date_to=None):
        """Materialize planned administrations over a rolling horizon
        (ir.config_parameter health_emar.schedule_horizon_days,
        default 7). Non-PRN active orders only. Idempotent — existing
        slots (unique on order/planned_datetime) are skipped; slots
        cancelled by a hold are re-planned on resume."""
        Admin = self.env['health.medication.administration']
        horizon = int(self.env['ir.config_parameter'].sudo().get_param(
            'health_emar.schedule_horizon_days', '7') or 7)
        now_utc = fields.Datetime.now()
        touched = Admin.browse()
        for order in self:
            if order.state != 'active' or order.is_prn \
                    or order.frequency in (False, 'other', 'prn'):
                continue
            tz = order._get_order_timezone()
            today_local = datetime.now(tz).date()
            window_start = date_from or max(today_local, order.start_date)
            # Inclusive window covering exactly `horizon` days.
            window_stop = date_to or (
                window_start + timedelta(days=horizon - 1))
            if order.end_date:
                window_stop = min(window_stop, order.end_date)
            if window_stop < window_start:
                continue
            times = order._get_slot_times()
            if not times:
                continue
            existing = {
                admin.planned_datetime: admin
                for admin in Admin.with_context(active_test=False).search(
                    [('order_id', '=', order.id)])
            }
            day = window_start
            while day <= window_stop:
                if order.frequency == 'weekly' \
                        and day.weekday() != order.start_date.weekday():
                    day += timedelta(days=1)
                    continue
                for hour, minute in times:
                    local_dt = tz.localize(
                        datetime.combine(day, dt_time(hour, minute)))
                    utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                    if utc_dt < now_utc:
                        # Never materialize slots already in the past —
                        # the med was not orderable then.
                        continue
                    slot = existing.get(utc_dt)
                    if slot:
                        if slot.state == 'cancelled':
                            # Resume path (AC6): re-plan slots cancelled
                            # by a hold instead of violating the unique
                            # slot index.
                            slot.write({'state': 'planned', 'fso_id': False})
                            touched |= slot
                        continue
                    new_slot = Admin.create({
                        'order_id': order.id,
                        'planned_datetime': utc_dt,
                    })
                    existing[utc_dt] = new_slot
                    touched |= new_slot
                day += timedelta(days=1)
        touched._link_administrations_to_fso()
        return touched

    # ------------------------------------------------------------------
    # Nightly maintenance cron (§3.4) — 02:00
    # ------------------------------------------------------------------
    @api.model
    def _cron_emar_maintenance(self):
        # (1) Rolling horizon for all active non-PRN orders.
        active_orders = self.search([
            ('state', '=', 'active'), ('is_prn', '=', False)])
        active_orders.action_generate_schedule()
        # (2) Re-link unlinked planned slots to visits.
        self.env['health.medication.administration'].search([
            ('state', '=', 'planned'), ('fso_id', '=', False),
        ])._link_administrations_to_fso()
        # (3) Auto-complete orders past end_date with no planned slots.
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'active'),
            ('end_date', '!=', False),
            ('end_date', '<', today),
        ])
        for order in expired:
            remaining = self.env['health.medication.administration'] \
                .search_count([('order_id', '=', order.id),
                               ('state', '=', 'planned')])
            if not remaining:
                order.write({'state': 'completed'})
                order.message_post(body=_(
                    'Order auto-completed by eMAR maintenance: end date '
                    'passed and no planned administrations remain.'))
        # (4) Overdue planned slots stay 'planned' (surfaced by the
        # "Missed" filter) — clinical staff must record not_given
        # explicitly; no automatic state change.
        return True

    # ------------------------------------------------------------------
    # Smart button
    # ------------------------------------------------------------------
    def action_view_administrations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Administrations'),
            'res_model': 'health.medication.administration',
            'view_mode': 'list,form',
            'domain': [('order_id', '=', self.id)],
            'context': {'default_order_id': self.id},
        }
