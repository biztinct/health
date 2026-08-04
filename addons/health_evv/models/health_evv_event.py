# -*- coding: utf-8 -*-
"""EVV event — append-only, per-visit hash-chained record (spec A.2.2 / A.3).

Chain definition (spec A.3):
- ``payload_hash`` = SHA-256 of the canonical JSON bytes (recipe in
  :meth:`_canonical_payload_bytes` — mirrored byte-for-byte in the PWA
  JS, ``health_evv/static/src/js/evv-queue.js``).
- ``prev_hash`` = previous event's ``payload_hash`` (genesis = 64 * '0').
- ``chain_hash`` = SHA-256 over the concatenated lowercase hex strings
  ``prev_hash + payload_hash`` (utf-8).

Client hash mismatches are RECORDED, never rejected (offline clocks and
float rounding must not lose data).
"""
import hashlib
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GENESIS_HASH = '0' * 64

# Keys that the server may add to the payload AFTER the payload hash has
# been computed (or that only the server can know). They are excluded
# from the canonical bytes on BOTH sides so that server-side validation
# stays deterministic and the client can compute a matching hash:
# - client_hash_mismatch: forensic marker added by append_event()
# - attachment_id: server-assigned id for signature/photo payloads (the
#   image itself is bound to the chain via png_sha256, which IS hashed)
RESERVED_PAYLOAD_KEYS = ('client_hash_mismatch', 'attachment_id')


def _canonical_number(value, ndigits):
    """Round and normalize so Python json.dumps output matches JS
    JSON.stringify (integral floats serialize as '10', not '10.0')."""
    value = round(float(value or 0.0), ndigits)
    if value == int(value):
        return int(value)
    return value


def _normalize_json(value):
    """Recursively normalize payload values so Python json.dumps matches
    JS JSON.stringify: integral floats become ints ('0', never '0.0')."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    if isinstance(value, dict):
        return {key: _normalize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item) for item in value]
    return value


class HealthEvvEvent(models.Model):
    _name = 'health.evv.event'
    _description = 'EVV Event'
    _order = 'fso_id, sequence, id'

    fso_id = fields.Many2one(
        'health.fieldservice.order', string='Visit', required=True,
        index=True, ondelete='restrict')
    # The record rules here have always walked `fso_id.catchment_province_id`
    # (evv_security.xml:48). Storing it makes the same truth filterable, which
    # is what the injected search facet needs — a facet cannot sit on a path.
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        related='fso_id.catchment_province_id', store=True, index=True,
        readonly=True)
    sequence = fields.Integer(
        required=True, readonly=True,
        help='Position in the per-visit chain (1-based, server-assigned).')
    event_type = fields.Selection([
        ('checkin', 'Check-in'),
        ('checkout', 'Check-out'),
        ('signature', 'Signature'),
        ('task_attest', 'Task Attestation'),
        ('photo', 'Photo'),
    ], required=True)
    event_datetime = fields.Datetime(
        required=True, help='Device wall-clock (UTC) at capture.')
    server_datetime = fields.Datetime(
        default=fields.Datetime.now, readonly=True,
        help='Server receipt time (drift detection).')
    lat = fields.Float(
        string='Latitude', digits=(10, 7),
        help='Device latitude at capture (0.0 allowed for signature '
             'events when GPS is off).')
    lng = fields.Float(string='Longitude', digits=(10, 7))
    accuracy_m = fields.Float(string='GPS Accuracy (m)')
    distance_m = fields.Float(
        string='Distance from Geofence (m)',
        compute='_compute_distance', store=True)
    inside_geofence = fields.Boolean(
        compute='_compute_distance', store=True)
    staff_id = fields.Many2one(
        'hr.employee', string='Staff', required=True,
        help='Acting nurse (request.env.user.employee_id).')
    device_uuid = fields.Char(size=64, string='Device UUID')
    client_event_uuid = fields.Char(
        size=64, required=True, index=True, string='Client Event UUID',
        help='Client-generated UUIDv4 — idempotency key '
             '(unique per visit).')
    payload = fields.Json(
        help="Type-specific payload. signature: {signer_name, "
             "signer_relationship, attachment_id, png_sha256}; "
             "task_attest: {task_code, done}; photo: {attachment_id, "
             "caption}.")
    payload_hash = fields.Char(size=64, required=True, readonly=True)
    prev_hash = fields.Char(size=64, required=True, readonly=True)
    chain_hash = fields.Char(size=64, required=True, readonly=True, index=True)
    origin = fields.Selection([
        ('online', 'Online'),
        ('offline_sync', 'Offline Sync'),
    ], default='online')
    chain_valid = fields.Boolean(
        default=True, readonly=True,
        help='Set to False by the chain validator when tampering is '
             'detected at or after this event.')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('fso_client_uuid_uniq', 'unique(fso_id, client_event_uuid)',
         'Duplicate EVV event (idempotency key already used for this visit).'),
        ('fso_sequence_uniq', 'unique(fso_id, sequence)',
         'Duplicate EVV chain sequence for this visit.'),
    ]

    def init(self):
        # Odoo 19 no longer materializes _sql_constraints — create the
        # unique indexes explicitly (required for idempotent replay and
        # for the per-FSO chain integrity).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_evv_event_fso_uuid_uidx
            ON health_evv_event (fso_id, client_event_uuid)
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_evv_event_fso_seq_uidx
            ON health_evv_event (fso_id, sequence)
        """)

    # ------------------------------------------------------------------
    # Geofence
    # ------------------------------------------------------------------
    @api.depends('lat', 'lng', 'accuracy_m',
                 'fso_id.patient_id.partner_latitude',
                 'fso_id.patient_id.partner_longitude',
                 'fso_id.patient_id.geofence_radius_m',
                 'fso_id.patient_id.geofence_enabled')
    def _compute_distance(self):
        from odoo.addons.health_base.models.geo_utils import haversine_km
        max_accuracy = float(self.env['ir.config_parameter'].sudo().get_param(
            'health_evv.default_accuracy_max_m', '100'))
        for event in self:
            partner = event.fso_id.patient_id
            if (not partner or not partner.geofence_enabled
                    or not partner.partner_latitude
                    or not partner.partner_longitude):
                # No usable fence — cannot measure; treat as compliant so
                # a disabled fence never blocks verification.
                event.distance_m = 0.0
                event.inside_geofence = True
                continue
            distance = haversine_km(
                event.lat or 0.0, event.lng or 0.0,
                partner.partner_latitude, partner.partner_longitude,
            ) * 1000.0
            event.distance_m = distance
            event.inside_geofence = bool(
                distance <= (partner.geofence_radius_m or 150)
                and (event.accuracy_m or 0.0) <= max_accuracy
            )

    # ------------------------------------------------------------------
    # Immutability — append-only for everyone, superuser included.
    # ------------------------------------------------------------------
    def write(self, vals):
        if set(vals.keys()) - {'chain_valid'}:
            raise UserError(_(
                'EVV events are append-only and can never be modified. '
                'To correct an event, append a new one with '
                "payload={'corrects': <event_id>, ...}."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_(
            'EVV events are append-only and can never be deleted.'))

    # ------------------------------------------------------------------
    # Hash chain
    # ------------------------------------------------------------------
    @api.model
    def _canonical_payload_bytes(self, vals):
        """Canonical JSON bytes of an event dict (spec A.2.2).

        json.dumps of {fso_id, event_type, event_datetime (iso,
        'YYYY-MM-DDTHH:MM:SSZ'), lat (round 7), lng (round 7),
        accuracy_m (round 1), staff_id, device_uuid, client_event_uuid,
        payload (sorted keys)} with sort_keys=True,
        separators=(',', ':'), ensure_ascii=False -> utf-8 bytes.

        THIS EXACT RECIPE IS MIRRORED IN JS (evv-queue.js /
        GeofenceService); integral floats are normalized to ints so both
        serializers emit identical bytes.
        """
        payload = _normalize_json({
            key: value
            for key, value in (vals.get('payload') or {}).items()
            if key not in RESERVED_PAYLOAD_KEYS
        })
        event_dt = vals.get('event_datetime')
        if isinstance(event_dt, str):
            event_dt = fields.Datetime.to_datetime(
                event_dt.replace('Z', '').replace('T', ' '))
        fso_id = vals.get('fso_id')
        if isinstance(fso_id, models.BaseModel):
            fso_id = fso_id.id
        staff_id = vals.get('staff_id')
        if isinstance(staff_id, models.BaseModel):
            staff_id = staff_id.id
        canonical = {
            'fso_id': int(fso_id or 0),
            'event_type': vals.get('event_type') or '',
            'event_datetime': (
                event_dt.strftime('%Y-%m-%dT%H:%M:%SZ') if event_dt else ''),
            'lat': _canonical_number(vals.get('lat'), 7),
            'lng': _canonical_number(vals.get('lng'), 7),
            'accuracy_m': _canonical_number(vals.get('accuracy_m'), 1),
            'staff_id': int(staff_id or 0),
            'device_uuid': vals.get('device_uuid') or '',
            'client_event_uuid': vals.get('client_event_uuid') or '',
            'payload': payload,
        }
        return json.dumps(
            canonical, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False,
        ).encode('utf-8')

    def _record_canonical_vals(self):
        """Rebuild the append-time vals dict from a stored record (used
        by validate_chain to re-derive the hashes)."""
        self.ensure_one()
        return {
            'fso_id': self.fso_id.id,
            'event_type': self.event_type,
            'event_datetime': self.event_datetime,
            'lat': self.lat,
            'lng': self.lng,
            'accuracy_m': self.accuracy_m,
            'staff_id': self.staff_id.id,
            'device_uuid': self.device_uuid or '',
            'client_event_uuid': self.client_event_uuid or '',
            'payload': self.payload or {},
        }

    @api.model
    def append_event(self, fso, vals, client_hash=None):
        """Append one event to the visit's chain (spec A.2.2).

        Locks the FSO row (SELECT ... FOR UPDATE), reads the last event,
        computes sequence / payload_hash / prev_hash / chain_hash and
        creates the row. If ``client_hash`` differs from the server
        recomputation, the event is created anyway with
        payload['client_hash_mismatch'] (tamper-evident, not
        tamper-rejecting). Idempotent on (fso_id, client_event_uuid).
        """
        fso.ensure_one()
        client_event_uuid = (vals.get('client_event_uuid') or '').strip()
        if not client_event_uuid:
            raise UserError(_('EVV event is missing client_event_uuid.'))

        domain = [('fso_id', '=', fso.id),
                  ('client_event_uuid', '=', client_event_uuid)]
        existing = self.search(domain, limit=1)
        if existing:
            return existing

        # Serialize chain appends per visit.
        self.env.cr.execute(
            "SELECT id FROM health_fieldservice_order "
            "WHERE id = %s FOR UPDATE", (fso.id,))
        existing = self.search(domain, limit=1)
        if existing:
            return existing

        last = self.search(
            [('fso_id', '=', fso.id)], order='sequence desc', limit=1)
        sequence = (last.sequence if last else 0) + 1
        prev_hash = last.payload_hash if last else GENESIS_HASH

        vals = dict(vals, fso_id=fso.id,
                    client_event_uuid=client_event_uuid)
        payload_hash = hashlib.sha256(
            self._canonical_payload_bytes(vals)).hexdigest()
        chain_hash = hashlib.sha256(
            (prev_hash + payload_hash).encode('utf-8')).hexdigest()

        payload = dict(vals.get('payload') or {})
        if client_hash and client_hash != payload_hash:
            payload['client_hash_mismatch'] = client_hash
            _logger.warning(
                'EVV client hash mismatch on FSO %s (%s, uuid %s): '
                'client=%s server=%s',
                fso.id, vals.get('event_type'), client_event_uuid,
                client_hash, payload_hash)

        event_dt = vals.get('event_datetime')
        if isinstance(event_dt, str):
            event_dt = fields.Datetime.to_datetime(
                event_dt.replace('Z', '').replace('T', ' '))

        staff_id = vals.get('staff_id')
        if isinstance(staff_id, models.BaseModel):
            staff_id = staff_id.id

        return self.create({
            'fso_id': fso.id,
            'sequence': sequence,
            'event_type': vals.get('event_type'),
            'event_datetime': event_dt or fields.Datetime.now(),
            'lat': vals.get('lat') or 0.0,
            'lng': vals.get('lng') or 0.0,
            'accuracy_m': vals.get('accuracy_m') or 0.0,
            'staff_id': staff_id,
            'device_uuid': vals.get('device_uuid') or '',
            'client_event_uuid': client_event_uuid,
            'payload': payload,
            'payload_hash': payload_hash,
            'prev_hash': prev_hash,
            'chain_hash': chain_hash,
            'origin': vals.get('origin') or 'online',
        })

    @api.model
    def validate_chain(self, fso):
        """Re-derive every payload_hash / prev_hash / chain_hash for the
        visit's events in sequence order.

        Returns ``{'valid': bool, 'first_bad_sequence': int | None}``.
        Flags ``chain_valid=False`` on the bad tail via direct SQL
        (bypassing the write() guard).
        """
        fso.ensure_one()
        events = self.search([('fso_id', '=', fso.id)], order='sequence asc')
        prev_hash = GENESIS_HASH
        first_bad_sequence = None
        for event in events:
            payload_hash = hashlib.sha256(self._canonical_payload_bytes(
                event._record_canonical_vals())).hexdigest()
            chain_hash = hashlib.sha256(
                (prev_hash + payload_hash).encode('utf-8')).hexdigest()
            if (payload_hash != event.payload_hash
                    or event.prev_hash != prev_hash
                    or chain_hash != event.chain_hash):
                first_bad_sequence = event.sequence
                break
            prev_hash = event.payload_hash

        valid = first_bad_sequence is None
        if events:
            if valid:
                self.env.cr.execute(
                    "UPDATE health_evv_event SET chain_valid = TRUE "
                    "WHERE fso_id = %s", (fso.id,))
            else:
                self.env.cr.execute(
                    "UPDATE health_evv_event "
                    "SET chain_valid = (sequence < %s) "
                    "WHERE fso_id = %s", (first_bad_sequence, fso.id))
            events.invalidate_recordset(['chain_valid'])
            # Direct SQL bypasses the ORM: refresh the FSO's stored EVV
            # status explicitly.
            fso._compute_evv_status()
        return {'valid': valid, 'first_bad_sequence': first_bad_sequence}

    # ------------------------------------------------------------------
    # Cron (spec A.7)
    # ------------------------------------------------------------------
    @api.model
    def cron_validate_chains(self, days=2):
        """Nightly: validate_chain() for every FSO having EVV events with
        a write-window in the last <days> days; on failure post a
        mail.activity to the FSO's facility manager."""
        since = fields.Datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            "SELECT DISTINCT fso_id FROM health_evv_event "
            "WHERE create_date >= %s OR write_date >= %s", (since, since))
        fso_ids = [row[0] for row in self.env.cr.fetchall()]
        checked, tampered = 0, 0
        for fso in self.env['health.fieldservice.order'].browse(fso_ids):
            result = self.validate_chain(fso)
            checked += 1
            if not result['valid']:
                tampered += 1
                self._post_tamper_activity(fso, result['first_bad_sequence'])
        _logger.info(
            'EVV nightly chain validation: %s visit chains checked, '
            '%s tampered.', checked, tampered)
        return {'checked': checked, 'tampered': tampered}

    @api.model
    def _post_tamper_activity(self, fso, first_bad_sequence):
        """Alert the facility manager (mirrors the follow-up-activity
        pattern of HealthPWAAPIController._create_follow_up_activity)."""
        try:
            facility = fso.patient_id.primary_facility_id
            if not facility:
                _logger.warning(
                    'EVV tamper on FSO %s: no primary facility, cannot '
                    'create activity.', fso.id)
                return
            manager = facility.facility_manager_id
            manager_user = manager.user_id if manager else False
            if not manager_user:
                _logger.warning(
                    'EVV tamper on FSO %s: facility %s has no manager '
                    'user, cannot create activity.', fso.id, facility.name)
                return
            activity_type = self.env.ref(
                'mail.mail_activity_data_todo', raise_if_not_found=False)
            if not activity_type:
                return
            fso.activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('EVV TAMPER DETECTED: %s') % fso.name,
                note=_(
                    '<p><strong>EVV chain validation failed</strong></p>'
                    '<p>Booking: %(booking)s</p>'
                    '<p>First bad sequence: %(sequence)s</p>'
                    '<p>The visit event chain no longer verifies — '
                    'investigate for tampering.</p>',
                    booking=fso.name, sequence=first_bad_sequence),
                date_deadline=fields.Date.today() + timedelta(days=1),
                user_id=manager_user.id,
            )
        except Exception as exc:  # noqa: BLE001 — alerting never breaks the cron
            _logger.error(
                'EVV tamper activity creation failed for FSO %s: %s',
                fso.id, exc)
