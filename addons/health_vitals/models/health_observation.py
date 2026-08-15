# -*- coding: utf-8 -*-
"""Clinical observation — one row = one observation (clinical spec §2.2.2).

Append-only clinical record (interop §6.7): no unlink below admin,
corrections go through state='entered_in_error' + re-entry. Value edits
on a final record by a head nurse flip the state to 'amended'
automatically (FHIR Observation.status lifecycle).
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# States that count for trending / clinical reads.
TREND_STATES = ('final', 'amended')


class HealthObservation(models.Model):
    _name = 'health.observation'
    _description = 'Clinical Observation'
    _inherit = ['mail.thread']
    _order = 'effective_datetime desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        compute='_compute_display_name', store=True)
    client_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        domain=[('is_patient', '=', True)], ondelete='restrict',
        index=True, tracking=True,
        help='FHIR Observation.subject')
    vitals_type_id = fields.Many2one(
        'health.vitals.type', string='Observation Type', required=True,
        ondelete='restrict', index=True,
        help='FHIR Observation.code')
    loinc_code = fields.Char(
        related='vitals_type_id.loinc_code', store=True,
        string='LOINC Code')
    value_quantity = fields.Float(
        string='Value', aggregator='avg',
        help='FHIR valueQuantity.value (required for numeric types, '
             'panels exempt).')
    value_text = fields.Char(
        string='Text Value', help='FHIR valueString (text types).')
    ucum_unit = fields.Char(
        related='vitals_type_id.ucum_unit', store=True,
        string='UCUM Unit')
    unit_display = fields.Char(
        related='vitals_type_id.unit_display', string='Unit')
    effective_datetime = fields.Datetime(
        string='Effective Datetime', required=True,
        default=fields.Datetime.now, index=True, tracking=True,
        help='FHIR effectiveDateTime')
    performer_id = fields.Many2one(
        'res.users', string='Performer',
        default=lambda self: self.env.uid,
        help='FHIR performer')
    method = fields.Char(help='FHIR method.text')
    body_position_id = fields.Many2one(
        'health.lookup.value',
        string='Body Position',
        domain="[('category_code', '=', 'body_position'), ('active', '=', True)]",
        ondelete='restrict',
        help='FHIR extension bodyPosition')
    device = fields.Char(help='FHIR device.display')
    order_id = fields.Many2one(
        'health.fieldservice.order', string='Visit',
        ondelete='set null', index=True,
        help='FHIR encounter')
    clinical_note_id = fields.Many2one(
        'health.clinical.note', string='Clinical Note',
        ondelete='set null', index=True,
        help='Back-compat linkage to the free-text note.')
    parent_id = fields.Many2one(
        'health.observation', string='Panel Observation',
        ondelete='cascade',
        help='Systolic/diastolic under a BP-panel row; FHIR '
             'Observation.component / hasMember.')
    child_ids = fields.One2many(
        'health.observation', 'parent_id', string='Panel Members')
    state = fields.Selection([
        ('preliminary', 'Preliminary'),
        ('final', 'Final'),
        ('amended', 'Amended'),
        ('entered_in_error', 'Entered in Error'),
    ], default='final', required=True, tracking=True,
        help="FHIR Observation.status ('entered_in_error' maps to "
             "'entered-in-error').")
    is_abnormal = fields.Boolean(
        readonly=True, index=True, help='Set by the threshold check.')
    alert_level = fields.Selection([
        ('none', 'None'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], default='none', readonly=True, tracking=True,
        help='Highest breached threshold.')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True,
        readonly=True, index=True,
        help='Catchment area used for filtering and access control')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def init(self):
        # Trend queries per DESIGN.md §7.3: composite index on
        # (client, type, datetime).
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS
                health_observation_trend_idx
            ON health_observation
                (client_id, vitals_type_id, effective_datetime)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('vitals_type_id.name', 'vitals_type_id.unit_display',
                 'vitals_type_id.decimals', 'value_quantity', 'value_text',
                 'client_id.name')
    def _compute_display_name(self):
        for rec in self:
            vtype = rec.vitals_type_id
            if vtype.value_type == 'quantity':
                value = ('%.*f' % (max(vtype.decimals, 0),
                                   rec.value_quantity or 0.0))
            elif vtype.value_type == 'string':
                value = rec.value_text or ''
            else:  # panel
                value = _('panel')
            unit = vtype.unit_display or ''
            rec.display_name = '%s: %s %s — %s' % (
                vtype.name or '', value, unit,
                rec.client_id.name or '')

    @api.depends('client_id.catchment_province_id',
                 'client_id.primary_facility_id.catchment_province_id')
    def _compute_catchment_province_id(self):
        for rec in self:
            rec.catchment_province_id = (
                rec.client_id._get_health_catchment_province()
                if rec.client_id else False)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('value_quantity', 'vitals_type_id')
    def _check_value(self):
        for rec in self:
            vtype = rec.vitals_type_id
            if vtype.value_type != 'quantity':
                continue
            value = rec.value_quantity or 0.0
            # Float columns cannot distinguish unset from 0.0 — a zero
            # is only valid when the plausible range admits it, which
            # doubles as the "value required" check for numeric types.
            if ((vtype.plausible_min and value < vtype.plausible_min)
                    or (vtype.plausible_max and value > vtype.plausible_max)):
                raise ValidationError(_(
                    '%(name)s: value %(value)s outside plausible range '
                    '[%(min)s – %(max)s].',
                    name=vtype.display_name, value=value,
                    min=vtype.plausible_min, max=vtype.plausible_max))

    # ------------------------------------------------------------------
    # Lifecycle — append-only discipline (interop §6.7)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('client_id'):
                # Derive the client from the visit / clinical note so
                # inline entry from the note form never needs it typed.
                if vals.get('order_id'):
                    vals['client_id'] = self.env[
                        'health.fieldservice.order'].browse(
                        vals['order_id']).patient_id.id
                elif vals.get('clinical_note_id'):
                    vals['client_id'] = self.env[
                        'health.clinical.note'].browse(
                        vals['clinical_note_id']).order_id.patient_id.id
        records = super().create(vals_list)
        records._check_thresholds()
        return records

    def write(self, vals):
        value_keys = {'value_quantity', 'value_text'}
        amending = value_keys & set(vals.keys())
        to_amend = self.browse()
        if amending:
            finals = self.filtered(lambda rec: rec.state == 'final')
            if finals and not self._can_amend():
                raise UserError(_(
                    'Only a head nurse (or above) can amend the value '
                    'of a final observation.'))
            if 'state' not in vals:
                to_amend = finals
        result = super().write(vals)
        if to_amend:
            super(HealthObservation, to_amend).write({'state': 'amended'})
        if amending:
            # Keep the alert flags consistent with the amended value.
            self._check_thresholds()
        return result

    def unlink(self):
        allowed = (
            self.env.su
            or self.env.user._is_admin()
            or self.env.user.has_group('health_base.group_healthcare_admin')
            or self.env.user.has_group('health_base.group_healthcare_owner'))
        if not allowed and any(
                rec.state != 'entered_in_error' for rec in self):
            raise UserError(_(
                'Clinical observations are append-only and cannot be '
                "deleted. Mark the record 'Entered in Error' and "
                're-enter the correct value instead.'))
        return super().unlink()

    def _can_amend(self):
        user = self.env.user
        return (self.env.su or user._is_admin()
                or user.has_group('health_base.group_healthcare_head_nurse')
                or user.has_group('health_base.group_healthcare_admin')
                or user.has_group('health_base.group_healthcare_owner'))

    def action_mark_entered_in_error(self):
        for rec in self:
            if rec.state == 'entered_in_error':
                raise UserError(_(
                    'Observation %s is already marked entered in error.')
                    % rec.display_name)
            rec.write({'state': 'entered_in_error'})
        return True

    # ------------------------------------------------------------------
    # Threshold evaluation + escalation (clinical spec §2.3)
    # ------------------------------------------------------------------
    def _check_thresholds(self):
        """Evaluate per-client alert thresholds for quantity
        observations. Critical is checked first; the first breached
        severity wins. Escalation never blocks the observation save.
        """
        Threshold = self.env['health.vitals.threshold']
        for rec in self:
            if (rec.vitals_type_id.value_type != 'quantity'
                    or rec.state == 'entered_in_error'):
                continue
            thresholds = Threshold.search([
                ('client_id', '=', rec.client_id.id),
                ('vitals_type_id', '=', rec.vitals_type_id.id),
                ('active', '=', True),
            ])
            breached = False
            # Critical first.
            for threshold in thresholds.sorted(
                    key=lambda t: t.severity != 'critical'):
                value = rec.value_quantity
                if ((threshold.min_value and value < threshold.min_value)
                        or (threshold.max_value
                            and value > threshold.max_value)):
                    rec.write({
                        'is_abnormal': True,
                        'alert_level': threshold.severity,
                    })
                    try:
                        rec._escalate_threshold_breach(threshold)
                    except Exception as exc:  # noqa: BLE001 — alerting
                        # must never block clinical data capture.
                        _logger.error(
                            'Vitals escalation failed for observation '
                            '%s: %s', rec.id, exc)
                    breached = True
                    break
            if not breached and rec.is_abnormal:
                # Re-evaluation after an amendment cleared the breach.
                rec.write({'is_abnormal': False, 'alert_level': 'none'})

    def _threshold_alert_message(self, threshold):
        self.ensure_one()
        return _(
            'ALERT: %(type)s %(value)s%(unit)s breached %(severity)s '
            'threshold [%(min)s-%(max)s]',
            type=self.vitals_type_id.name,
            value=self.value_quantity,
            unit=self.vitals_type_id.unit_display or '',
            severity=threshold.severity,
            min=threshold.min_value,
            max=threshold.max_value)

    def _escalate_threshold_breach(self, threshold):
        self.ensure_one()
        action = threshold.escalation_action
        message = self._threshold_alert_message(threshold)
        if action == 'none':
            return
        if action == 'chatter':
            self.client_id.message_post(
                body=message, subtype_xmlid='mail.mt_note')
            return
        # activity / activity_author
        user = False
        if action == 'activity_author' and 'health.careplan' in self.env:
            plan = self.env['health.careplan'].search([
                ('client_id', '=', self.client_id.id),
                ('state', 'in', ('active', 'under_review')),
            ], limit=1)
            user = plan.author_id if plan else False
        if not user:
            user = self._get_facility_manager_user()
        if not user:
            _logger.warning(
                'Vitals alert on observation %s: no facility manager '
                'user for client %s, cannot create activity.',
                self.id, self.client_id.name)
            return
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            _logger.warning('Todo activity type not found')
            return
        self.client_id.activity_schedule(
            activity_type_id=activity_type.id,
            summary=message,
            note=_(
                '<p><strong>Vitals threshold breached</strong></p>'
                '<p>Client: %(client)s</p>'
                '<p>%(message)s</p>'
                '<p>Observed: %(datetime)s</p>',
                client=self.client_id.name,
                message=message,
                datetime=self.effective_datetime),
            date_deadline=fields.Date.today() + timedelta(days=1),
            user_id=user.id,
        )

    def _get_facility_manager_user(self):
        """Facility-manager fallback (pattern:
        health_pwa api.py::_create_follow_up_activity)."""
        self.ensure_one()
        facility = self.client_id.primary_facility_id
        manager = facility.facility_manager_id if facility else False
        return manager.user_id if manager and manager.user_id else False

    # ------------------------------------------------------------------
    # Public interface (consumed by health_forms, PWA controller)
    # ------------------------------------------------------------------
    @api.model
    def create_coded(self, patient_id, loinc_code, value, uom=None,
                     fso_id=None, effective_datetime=None,
                     performer_id=None, source='manual', note=None):
        """Create one observation resolving the catalog row by LOINC
        code. Raises UserError on unknown code. Threshold evaluation
        runs in create(). Returns the created observation.
        """
        vtype = self.env['health.vitals.type'].get_by_code(loinc_code)
        if not vtype:
            raise UserError(_(
                'Unknown observation code: %s') % loinc_code)
        if vtype.value_type == 'panel':
            raise UserError(_(
                '%s is a panel type — use create_panel() with its '
                'components.') % vtype.display_name)
        if uom and vtype.ucum_unit and uom not in (
                vtype.ucum_unit, vtype.unit_display):
            # No unit conversion in v1 — record anyway, flag loudly.
            _logger.warning(
                'create_coded: unit mismatch for %s (got %s, catalog '
                '%s) — value stored unconverted.',
                loinc_code, uom, vtype.ucum_unit)
        vals = {
            'client_id': patient_id,
            'vitals_type_id': vtype.id,
            'order_id': fso_id or False,
            'effective_datetime': (effective_datetime
                                   or fields.Datetime.now()),
            'performer_id': performer_id or self.env.uid,
        }
        if vtype.value_type == 'quantity':
            vals['value_quantity'] = float(value)
        else:
            vals['value_text'] = str(value)
        observation = self.create(vals)
        if note or (source and source != 'manual'):
            parts = []
            if source and source != 'manual':
                parts.append(_('Source: %s') % source)
            if note:
                parts.append(note)
            observation.message_post(
                body=' — '.join(parts), subtype_xmlid='mail.mt_note')
        return observation

    @api.model
    def create_panel(self, client_id, panel_type_code, components,
                     **common):
        """Create a panel row + its component rows in one call (used by
        the PWA endpoint for blood pressure).

        components = [{'code': 'bp_sys', 'value': 120}, ...]; common
        carries effective_datetime / order_id / method / body_position /
        device / clinical_note_id / performer_id.
        """
        Type = self.env['health.vitals.type']
        panel_type = Type.get_by_code(panel_type_code)
        if not panel_type:
            raise UserError(_(
                'Unknown panel type code: %s') % panel_type_code)
        if panel_type.value_type != 'panel':
            raise UserError(_(
                '%s is not a panel type.') % panel_type.display_name)
        allowed = ('effective_datetime', 'order_id', 'method',
                   'body_position_id', 'device', 'clinical_note_id',
                   'performer_id', 'state')
        common_vals = {key: value for key, value in common.items()
                       if key in allowed and value}
        common_vals.setdefault(
            'effective_datetime', fields.Datetime.now())
        panel = self.create(dict(common_vals, **{
            'client_id': client_id,
            'vitals_type_id': panel_type.id,
        }))
        component_vals = []
        for component in components:
            ctype = Type.get_by_code(component.get('code'))
            if not ctype:
                raise UserError(_(
                    'Unknown observation code: %s')
                    % component.get('code'))
            component_vals.append(dict(common_vals, **{
                'client_id': client_id,
                'vitals_type_id': ctype.id,
                'value_quantity': float(component.get('value') or 0.0),
                'parent_id': panel.id,
            }))
        if component_vals:
            self.create(component_vals)
        return panel

    @api.model
    def get_trend(self, client_id, vitals_type_id, date_from=None,
                  date_to=None, limit=200):
        """Ordered [{datetime, value}] for graphs / PWA sparklines.
        Only 'final' and 'amended' observations count (entered-in-error
        rows are excluded from trends).
        """
        domain = [
            ('client_id', '=', client_id),
            ('vitals_type_id', '=', vitals_type_id),
            ('state', 'in', list(TREND_STATES)),
        ]
        if date_from:
            domain.append(('effective_datetime', '>=', date_from))
        if date_to:
            domain.append(('effective_datetime', '<=', date_to))
        # Take the most recent <limit> points, return them oldest-first.
        observations = self.search(
            domain, order='effective_datetime desc, id desc', limit=limit)
        return [{
            'datetime': fields.Datetime.to_string(obs.effective_datetime),
            'value': obs.value_quantity,
        } for obs in reversed(observations)]
