import logging
import secrets
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_DEFAULT_TZ = 'Asia/Ho_Chi_Minh'
# FSO states that count as a finished visit (source for A3 branch 2 + guards).
_COMPLETED_STATES = ('completed', 'completed_pending_invoice', 'closed')
# Valid FSO service_type selections — package/last-FSO service types that are
# not one of these get mapped to a safe default so FSO create() never raises
# (mirrors health_workflow_auto.visit_offer._FSO_SERVICE_TYPES).
_FSO_SERVICE_TYPES = {
    'home_visit', 'clinic_visit', 'consultation', 'emergency', 'follow_up',
    'preventive', 'rehabilitation', 'telemedicine', 'vaccination', 'diagnostic',
}
# Fixed booking duration for a self-rebooked visit (hours) — mirrors the
# first-visit offer's accept pipeline (2h => scheduled_duration 120).
_BOOKING_DURATION_HOURS = 2


def _safe_phone(phone):
    """normalize_vn_phone raises on invalid; we want falsy-on-invalid
    (conventions ledger §5.15)."""
    from odoo.addons.health_base.models.phone_utils import normalize_vn_phone
    try:
        return normalize_vn_phone(phone) or ''
    except ValidationError:
        return ''


class HealthSelfbookInvite(models.Model):
    """A2 — a tokenized, no-login rebook invite per patient.

    One ACTIVE invite per patient (search-first). The proposed slots and the
    resolved service (package / product) are SNAPSHOTTED at invite creation
    so the page is stable; the booked slot is re-verified under a row lock at
    accept time (B). No expiry cron — expiry is checked at render time
    (family-link precedent).
    """
    _name = 'health.selfbook.invite'
    _description = 'Client Self-Booking Invite'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='cascade')
    token = fields.Char(
        required=True, index=True, copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        help='Capability token — the page URL is a capability URL. '
             'Never logged at info level.')
    state = fields.Selection([
        ('sent', 'Sent'),
        ('booked', 'Booked'),
        ('revoked', 'Revoked'),
    ], default='sent', required=True, index=True)
    expires_at = fields.Datetime(
        help='create + health_self_booking.invite_ttl_days. Checked at render '
             'time (no cron).')
    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Booked Visit',
        readonly=True, copy=False, ondelete='set null')
    # A3 — resolved and snapshotted at invite time so the page is stable.
    package_id = fields.Many2one(
        'health.service.package', string='Prepaid Package',
        readonly=True, ondelete='set null',
        help='Snapshot: active package the rebook consumes, if any (A3.1).')
    service_product_id = fields.Many2one(
        'product.product', string='Service Product',
        readonly=True, ondelete='set null',
        help='Snapshot: billable service line for the rebooked visit when no '
             'package applies (A3.2 / A3.3).')
    service_type = fields.Char(
        readonly=True,
        help='Snapshot: FSO service_type for the rebooked visit.')
    fso_timezone = fields.Char(
        help='Facility timezone snapshot used to render/parse slot wall-clock '
             'times before an FSO exists.')
    # slots snapshotted at invite creation so accept indexes are stable
    # (report point d — modeled as Json rather than a child model, matching
    # the A2 field spec ``slots_json``; simpler than the offer's child model
    # because the invite is read-only to the public and never edits a slot).
    slots_json = fields.Json(
        string='Proposed Slots',
        help='Snapshot of proposed {date, start_time, staff_id, staff_name, '
             'confidence} slots at invite creation.')
    outbound_message_id = fields.Many2one(
        'health.outbound.message', string='Invite Message',
        readonly=True, copy=False, ondelete='set null')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True, help='Catchment area used for access control.')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    def init(self):
        # Conventions ledger §5.1 — _sql_constraints are not materialized in
        # Odoo 19; back the token uniqueness contract with a real index.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_selfbook_invite_token_uidx
            ON health_selfbook_invite (token)
        """)

    @api.depends('patient_id', 'state')
    def _compute_display_name(self):
        for invite in self:
            name = invite.patient_id.name or ''
            invite.display_name = _('Rebook invite: %(patient)s') % {
                'patient': name} if name else _('Rebook invite')

    @api.depends('patient_id')
    def _compute_catchment_province_id(self):
        for invite in self:
            patient = invite.patient_id
            invite.catchment_province_id = (
                patient._get_health_catchment_province() if patient else False)

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------
    @api.model
    def _icp(self):
        return self.env['ir.config_parameter'].sudo()

    @api.model
    def _int_param(self, key, default):
        try:
            return int(self._icp().get_param(key, default))
        except (TypeError, ValueError):
            return default

    @api.model
    def _ttl_days(self):
        return self._int_param('health_self_booking.invite_ttl_days', 14)

    @api.model
    def _slot_count(self):
        return self._int_param('health_self_booking.slot_count', 6)

    @api.model
    def _horizon_days(self):
        return self._int_param('health_self_booking.horizon_days', 10)

    @api.model
    def _safe_service_type(self, service_type):
        return service_type if service_type in _FSO_SERVICE_TYPES else 'home_visit'

    # ------------------------------------------------------------------
    # A3 — resolve what "book again" offers (precedence, at invite time)
    # ------------------------------------------------------------------
    @api.model
    def _resolve_booking_source(self, patient):
        """A3 precedence. Returns {package_id, service_product_id,
        service_type} or None when nothing bookable exists (never create an
        invite that cannot confirm)."""
        # 1. Patient's most recent ACTIVE package with remaining services.
        package = self.env['health.service.package'].sudo().search([
            ('patient_id', '=', patient.id),
            ('state', '=', 'active'),
            ('remaining_services', '>', 0),
        ], order='create_date desc', limit=1)
        if package:
            return {
                'package_id': package.id,
                'service_product_id': False,
                'service_type': self._safe_service_type(package.service_type),
            }
        # 2. First service line of the patient's most recent completed FSO's
        #    quote. FSO -> quote field name is ``sale_order_id`` (report c).
        last_fso = self.env['health.fieldservice.order'].sudo().search([
            ('patient_id', '=', patient.id),
            ('state', 'in', list(_COMPLETED_STATES)),
        ], order='scheduled_datetime desc, id desc', limit=1)
        if last_fso and last_fso.sale_order_id and last_fso.sale_order_id.order_line:
            lines = last_fso.sale_order_id.order_line
            line = lines.filtered(
                lambda l: l.product_id and l.product_id.type == 'service')[:1]
            line = line or lines.filtered(lambda l: l.product_id)[:1]
            if line:
                return {
                    'package_id': False,
                    'service_product_id': line.product_id.id,
                    'service_type': self._safe_service_type(last_fso.service_type),
                }
        # 3. Config fallback product.
        pid = self._icp().get_param(
            'health_self_booking.fallback_service_product_id')
        if pid:
            product = self.env['product.product'].browse(int(pid)).exists()
            if product:
                return {
                    'package_id': False,
                    'service_product_id': product.id,
                    'service_type': 'home_visit',
                }
        return None

    # ------------------------------------------------------------------
    # A4 — slot snapshot (config count/horizon, preferred-staff stable sort)
    # ------------------------------------------------------------------
    @api.model
    def _snapshot_slots(self, patient):
        """Propose slots for the patient and serialize them to JSON.

        A4: preferred_staff_id (if set) sorts first WITHIN the same date
        (stable — preference, not a filter). Zero slots is allowed (the page
        renders a call-us body)."""
        raw = self.env['health.visit.offer']._propose_slots_for_partner(
            patient, count=self._slot_count(), horizon_days=self._horizon_days())
        pref_id = patient.preferred_staff_id.id if patient.preferred_staff_id else False
        if pref_id:
            # Python sort is stable: within an equal date the preferred staff's
            # slots (key 0) precede the others (key 1); order otherwise kept.
            raw = sorted(raw, key=lambda s: (
                s['date'], 0 if s['staff_id'] == pref_id else 1))
        slots = []
        for cand in raw:
            day = cand['date']
            slots.append({
                'date': day.strftime('%Y-%m-%d') if hasattr(day, 'strftime') else str(day),
                'start_time': float(cand['start_time']),
                'staff_id': cand['staff_id'],
                'staff_name': cand['staff_name'] or '',
                'confidence': cand.get('confidence', 0.5),
            })
        return slots

    # ------------------------------------------------------------------
    # Get-or-create (idempotent, one active invite per patient)
    # ------------------------------------------------------------------
    @api.model
    def _active_invite(self, patient):
        return self.sudo().search([
            ('patient_id', '=', patient.id),
            ('state', '=', 'sent'),
            ('expires_at', '>', fields.Datetime.now()),
        ], order='create_date desc', limit=1)

    @api.model
    def _get_or_create_invite(self, patient, raise_if_no_source=False):
        """Return the patient's active invite, creating one if none is live.

        Resolves + snapshots the booking source (A3) and slots (A4) on create.
        When nothing is bookable: raises UserError if ``raise_if_no_source``
        (the manual button), else returns an empty recordset (auto path skips).
        """
        if not patient:
            if raise_if_no_source:
                raise UserError(_('No patient to send a booking link to.'))
            return self.browse()
        existing = self._active_invite(patient)
        if existing:
            return existing
        source = self._resolve_booking_source(patient)
        if not source:
            if raise_if_no_source:
                raise UserError(_(
                    'Cannot create a booking link: this client has no active '
                    'package, no previous booked service, and no fallback '
                    'service product is configured.'))
            return self.browse()
        facility = patient.primary_facility_id
        tz_name = (facility.timezone if facility and getattr(facility, 'timezone', False)
                   else _DEFAULT_TZ)
        return self.sudo().create({
            'patient_id': patient.id,
            'expires_at': fields.Datetime.now() + timedelta(days=self._ttl_days()),
            'package_id': source['package_id'],
            'service_product_id': source['service_product_id'],
            'service_type': source['service_type'],
            'fso_timezone': tz_name,
            'slots_json': self._snapshot_slots(patient),
        })

    def _is_expired(self):
        self.ensure_one()
        return bool(self.expires_at and self.expires_at < fields.Datetime.now())

    # ------------------------------------------------------------------
    # URL / timezone helpers
    # ------------------------------------------------------------------
    def _base_url(self):
        return self._icp().get_param(
            'web.base.url', 'http://localhost:8069').rstrip('/')

    def _page_url(self):
        self.ensure_one()
        return '%s/booking/self/%s' % (self._base_url(), self.token)

    def _tz(self):
        self.ensure_one()
        name = (self.fso_id.booking_timezone if self.fso_id else False) \
            or self.fso_timezone or _DEFAULT_TZ
        try:
            return pytz.timezone(name)
        except pytz.UnknownTimeZoneError:
            return pytz.timezone(_DEFAULT_TZ)

    def _wall(self, dt):
        """Naive-UTC datetime -> wall-clock in the facility timezone (the +7h
        class of bug is the most-hit mistake in this codebase)."""
        if not dt:
            return None
        return pytz.utc.localize(dt).astimezone(self._tz())

    @staticmethod
    def _given_name(name):
        """Vietnamese given name is the last token (mirrors the offer/family
        pages' split(' ')[-1])."""
        return (name or '').split(' ')[-1]

    def _slot_start_datetime_utc(self, slot):
        """(slot['date'], slot['start_time']) wall-clock in the invite tz ->
        naive UTC (mirrors HealthVisitOfferSlot._start_datetime_utc)."""
        self.ensure_one()
        day = datetime.strptime(slot['date'], '%Y-%m-%d').date()
        start = float(slot['start_time'])
        hours = int(start)
        minutes = int(round((start - hours) * 60))
        local = datetime.combine(day, datetime.min.time()).replace(
            hour=hours, minute=minutes)
        return self._tz().localize(local).astimezone(pytz.UTC).replace(tzinfo=None)

    def _slot_label(self, slot):
        """Human wall-clock parts for one snapshotted slot."""
        self.ensure_one()
        day = datetime.strptime(slot['date'], '%Y-%m-%d').date()
        start = float(slot['start_time'])
        hours = int(start)
        minutes = int(round((start - hours) * 60))
        return {
            'date_label': day.strftime('%d/%m/%Y'),
            'time_label': '%02d:%02d' % (hours, minutes),
            'staff_name': self._given_name(slot.get('staff_name')),
        }

    # ------------------------------------------------------------------
    # Render-data assembly (A5) — factored out for direct testing
    # ------------------------------------------------------------------
    def _service_label(self):
        self.ensure_one()
        if self.package_id:
            return _('gói của bạn (your package)')
        if self.service_product_id:
            return self.service_product_id.name or _('dịch vụ (service)')
        return _('dịch vụ (service)')

    def _facility_phone(self):
        self.ensure_one()
        facility = self.patient_id.primary_facility_id
        return (facility.phone or '') if facility else ''

    def _page_context(self):
        """Server-side render data. modes: sent (slot list, possibly empty ->
        call-us) / booked (summary) / neutral. Invalid / expired / revoked are
        turned into neutral by the controller before this is called."""
        self.ensure_one()
        base = {
            'token': self.token,
            'patient_name': self._given_name(self.patient_id.name),
            'service_label': self._service_label(),
            'facility_phone': self._facility_phone(),
        }
        if self.state == 'booked':
            fso = self.fso_id
            start = self._wall(fso.scheduled_datetime) if fso else None
            end = self._wall(fso.estimated_end_datetime) if fso else None
            base.update({
                'mode': 'booked',
                'visit_date': start.strftime('%d/%m/%Y') if start else '',
                'time_window': ('%s - %s' % (
                    start.strftime('%H:%M'), end.strftime('%H:%M'))
                    if start and end else (
                        start.strftime('%H:%M') if start else '')),
                'staff_name': self._given_name(
                    fso.lead_staff_id.name) if fso and fso.lead_staff_id else '',
            })
            return base
        # sent — build the slot list from the snapshot.
        slots = []
        for idx, slot in enumerate(self.slots_json or []):
            label = self._slot_label(slot)
            slots.append({
                'index': idx,
                'date_label': label['date_label'],
                'time_label': label['time_label'],
                'staff_name': label['staff_name'],
            })
        base.update({'mode': 'sent', 'slots': slots})
        return base

    # ------------------------------------------------------------------
    # Accept (row-locked, race-safe) — called by the public controller (A5)
    # ------------------------------------------------------------------
    def _slot_feasible(self, staff_id, day):
        """Re-validate a snapshotted slot against the live availability
        matrix (a link can be opened days after the slots were proposed)."""
        self.ensure_one()
        return bool(self.env['health.staff.availability.matrix'].sudo().search_count([
            ('staff_id', '=', staff_id),
            ('availability_date', '=', day),
            ('status', '=', 'available'),
            ('remaining_capacity', '>', 0),
            ('conflict_detected', '=', False),
        ]))

    def accept_slot(self, slot_index):
        """Book the chosen slot: create + confirm an FSO for the patient.

        Race-safe: row-locks the invite (FOR UPDATE) so a double-POST books
        exactly one FSO. Never raises for expected conditions so the public
        page can render a friendly result.
        """
        self.ensure_one()
        # Row lock — serialize concurrent accepts of the same invite.
        self.env.cr.execute(
            "SELECT id FROM health_selfbook_invite WHERE id = %s FOR UPDATE",
            (self.id,))
        self.invalidate_recordset(['state', 'fso_id'])

        if self.state == 'booked':
            return {'ok': False, 'reason': 'already_booked', 'fso': self.fso_id}
        if self.state != 'sent' or self._is_expired():
            return {'ok': False, 'reason': 'expired'}

        slots = self.slots_json or []
        try:
            slot = slots[int(slot_index)]
        except (IndexError, ValueError, TypeError):
            return {'ok': False, 'reason': 'invalid_slot'}

        staff_id = slot.get('staff_id')
        day = datetime.strptime(slot['date'], '%Y-%m-%d').date()
        if not staff_id or not self._slot_feasible(staff_id, day):
            return {'ok': False, 'reason': 'infeasible'}

        # Re-validate the snapshotted booking source under the lock. A package
        # can be exhausted between invite and accept; a snapshotted product can
        # be archived. Bail out BEFORE creating a draft FSO that could not then
        # be confirmed (never leave a dangling draft).
        use_package = bool(self.package_id) and self.package_id.remaining_services > 0
        use_product = bool(self.service_product_id) and self.service_product_id.active
        if not use_package and not use_product:
            return {'ok': False, 'reason': 'infeasible'}

        patient = self.patient_id
        facility = patient.primary_facility_id
        FSO = self.env['health.fieldservice.order'].sudo()
        vals = {
            'patient_id': patient.id,
            'date': day.strftime('%Y-%m-%d'),
            'time_hour': float(slot['start_time']),
            'duration_hours': _BOOKING_DURATION_HOURS,
            'facility_id': facility.id if facility else False,
            'service_type': self.service_type or 'home_visit',
            'draft_only': True,
        }
        # A3: package path books against the package (no quote line, confirm
        # reserves 1 service); product path attaches a quote line.
        if not use_package and use_product:
            vals['product_lines'] = [{'product_id': self.service_product_id.id, 'qty': 1}]

        create_res = FSO.action_create_from_quick_booking_owl(vals)
        if not create_res.get('success'):
            return {'ok': False, 'reason': 'create_failed',
                    'detail': create_res.get('error')}
        fso = FSO.browse(create_res['booking_id'])

        if use_package:
            try:
                fso.write({'package_ids': [(4, self.package_id.id)]})
            except Exception as exc:  # noqa: BLE001
                _logger.warning('Self-booking: could not attach package: %s', exc)

        # Assign the slot staff (draft -> assigned) so the confirmation staff
        # gate is satisfied, then confirm.
        fso.action_assign_staff_to_fso(staff_id, assignment_role='lead')
        fso.action_confirm_booking()

        # Reserve the slot on the availability matrix (best-effort).
        try:
            self.env['health.staff.availability.matrix'].sudo().book_staff_slot(
                staff_id, self._slot_start_datetime_utc(slot),
                _BOOKING_DURATION_HOURS * 60, fso_id=fso.id)
        except Exception as exc:  # noqa: BLE001 — reservation is best-effort
            _logger.warning('Self-booking: could not reserve matrix slot: %s', exc)

        self.write({'state': 'booked', 'fso_id': fso.id})
        return {'ok': True, 'fso': fso, 'slot': slot}

    # ------------------------------------------------------------------
    # Sending (ZNS through the shipped messaging safety rails — A6)
    # ------------------------------------------------------------------
    def _zns_params(self):
        self.ensure_one()
        first = (self.slots_json or [])[:1]
        first_label = self._slot_label(first[0]) if first else {}
        return {
            'customer_name': self.patient_id.name or '',
            'service_name': self._service_label(),
            'slot1': ('%s %s' % (first_label.get('date_label', ''),
                                 first_label.get('time_label', ''))).strip(),
            'link': self._page_url(),
        }

    def _send_invite_zns(self):
        """Log + send the invite over ZNS honoring health_messaging's rails.

        Respects health_messaging.enabled / dry_run exactly (dry_run ->
        simulated, no real send). No template configured => the row is
        silently NOT created (family-link precedent). Dedup key
        ``selfbook-<invite_id>`` makes a re-send a no-op. Recipient is the
        PATIENT (the data subject) — mobile then phone.
        """
        self.ensure_one()
        ICP = self._icp()
        template_id = ICP.get_param('health_self_booking.zns_template_invite', '')
        if not template_id:
            return self.env['health.outbound.message']
        dedup_key = 'selfbook-%s' % self.id
        Message = self.env['health.outbound.message'].sudo()
        existing = Message.search([('dedup_key', '=', dedup_key)], limit=1)
        if existing:
            if self.outbound_message_id.id != existing.id:
                self.sudo().write({'outbound_message_id': existing.id})
            return existing

        enabled = ICP.get_param('health_messaging.enabled', 'False') in (
            'True', 'true', '1')
        dry_run = ICP.get_param('health_messaging.dry_run', 'True') in (
            'True', 'true', '1')
        phone = _safe_phone(self.patient_id.mobile or self.patient_id.phone)
        params = self._zns_params()
        msg = Message.create({
            'purpose': 'selfbook_invite',
            'channel': 'zns',
            'partner_id': self.patient_id.id,
            'phone': phone,
            'dedup_key': dedup_key,
            'payload_json': params,
            'state': 'queued',
        })
        self.sudo().write({'outbound_message_id': msg.id})

        if not phone:
            msg.write({'state': 'skipped',
                       'error_text': _('No usable phone for the patient.')})
            return msg
        if not enabled:
            msg.state = 'skipped'
            return msg
        if dry_run:
            msg.write({'state': 'simulated', 'sent_at': fields.Datetime.now()})
            return msg

        try:
            from odoo.addons.health_zalo.services.zalo_api import get_api_client
            config = self.env['zalo.config'].search([('active', '=', True)], limit=1)
            result = get_api_client(self.env).send_zns_notification(
                config, phone, template_id, params)
            if isinstance(result, dict) and result.get('error') \
                    and result.get('error') != 0:
                msg.write({'state': 'failed',
                           'error_text': 'ZNS error: %s' % (
                               result.get('message') or result.get('error'))})
            else:
                msg.write({'state': 'sent', 'sent_at': fields.Datetime.now()})
        except Exception as exc:  # noqa: BLE001 — a send must never break the flow
            msg.write({'state': 'failed', 'error_text': 'ZNS: %s' % exc})
        return msg

    # ------------------------------------------------------------------
    # Public entry points for the manual button / auto hook
    # ------------------------------------------------------------------
    @api.model
    def send_invite_for_patient(self, patient, raise_if_no_source=False):
        """Get-or-create the patient's active invite and send its ZNS."""
        invite = self._get_or_create_invite(
            patient, raise_if_no_source=raise_if_no_source)
        if invite:
            invite._send_invite_zns()
        return invite
