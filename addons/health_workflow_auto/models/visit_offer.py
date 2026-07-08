import logging
import secrets
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# lead.service_interest values that are NOT valid FSO service_type selections
# get mapped onto a safe default so FSO create() never raises.
_FSO_SERVICE_TYPES = {
    'home_visit', 'clinic_visit', 'consultation', 'emergency', 'follow_up',
    'preventive', 'rehabilitation', 'telemedicine', 'vaccination', 'diagnostic',
}


def _safe_phone(phone):
    """normalize_vn_phone raises on invalid; we want falsy-on-invalid (ledger §15)."""
    from odoo.addons.health_base.models.phone_utils import normalize_vn_phone
    try:
        return normalize_vn_phone(phone) or ''
    except ValidationError:
        return ''


class HealthVisitOfferSlot(models.Model):
    _name = 'health.visit.offer.slot'
    _description = 'First-Visit Offer Slot'
    _order = 'index'

    offer_id = fields.Many2one(
        'health.visit.offer', required=True, ondelete='cascade', index=True)
    index = fields.Integer(string='Slot #')
    slot_date = fields.Date()
    start_time = fields.Float(help='Wall-clock start hour (24h float) in the facility tz.')
    staff_id = fields.Many2one('hr.employee', string='Staff')
    confidence = fields.Float()
    taken = fields.Boolean(default=False)

    def _start_datetime_utc(self):
        """Convert (slot_date, start_time) wall-clock in facility tz -> naive UTC."""
        self.ensure_one()
        tz_name = (self.offer_id.fso_timezone or 'Asia/Ho_Chi_Minh')
        tz = pytz.timezone(tz_name)
        hours = int(self.start_time)
        minutes = int(round((self.start_time - hours) * 60))
        local = datetime.combine(self.slot_date, datetime.min.time()).replace(
            hour=hours, minute=minutes)
        return tz.localize(local).astimezone(pytz.UTC).replace(tzinfo=None)

    def label(self):
        """Human wall-clock label for the public page / ZNS params."""
        self.ensure_one()
        hours = int(self.start_time)
        minutes = int(round((self.start_time - hours) * 60))
        return '%s %02d:%02d' % (
            self.slot_date.strftime('%d/%m/%Y') if self.slot_date else '', hours, minutes)


class HealthVisitOffer(models.Model):
    _name = 'health.visit.offer'
    _description = 'First-Visit Offer'
    _order = 'create_date desc'

    name = fields.Char(default='New', readonly=True, copy=False)
    lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', required=True)
    token = fields.Char(
        required=True, index=True, copy=False,
        default=lambda self: secrets.token_urlsafe(24))
    state = fields.Selection([
        ('sent', 'Sent'), ('accepted', 'Accepted'),
        ('expired', 'Expired'), ('cancelled', 'Cancelled'),
    ], default='sent', required=True, index=True, tracking=True)
    expires_at = fields.Datetime(
        default=lambda self: fields.Datetime.now() + timedelta(hours=48))
    slot_ids = fields.One2many('health.visit.offer.slot', 'offer_id')
    fso_id = fields.Many2one('health.fieldservice.order', readonly=True, copy=False)
    # A2 override: link to the shipped health.outbound.message (not health.message.delivery).
    outbound_message_id = fields.Many2one(
        'health.outbound.message', readonly=True, copy=False)
    fso_timezone = fields.Char(
        help='Facility timezone snapshot used to render/parse slot wall-clock times.')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    _inherit = ['mail.thread']

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS health_visit_offer_token_uidx
            ON health_visit_offer (token)
        """)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'health.visit.offer') or _('Offer')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Slot proposal — reuse the availability matrix + assignment engine
    # ------------------------------------------------------------------
    @api.model
    def _propose_first_visit_slots(self, lead, count=3, horizon_days=7):
        """Return up to `count` earliest feasible {date, start_time, staff_id,
        staff_name, confidence} slots for a lead's first visit.

        Thin wrapper over ``_propose_slots_for_partner`` (extracted for the
        self-booking phase, A1): resolves the lead's partner and delegates.
        The lead path is byte-identical to the pre-refactor behavior.
        """
        partner = lead.patient_id or lead.partner_id
        return self._propose_slots_for_partner(
            partner, count=count, horizon_days=horizon_days)

    @api.model
    def _propose_slots_for_partner(self, partner, count=3, horizon_days=7):
        """Return up to `count` earliest feasible {date, start_time, staff_id,
        staff_name, confidence} slots for a partner's visit.

        Partner-level core of the slot proposer — needs NO crm.lead, so
        both the first-visit offer and the client self-booking invite share
        it (self-booking handover A1)."""
        if not partner:
            return []
        facility = partner.primary_facility_id
        province = partner.catchment_province_id
        Matrix = self.env['health.staff.availability.matrix']
        engine = self.env['health.ai.assignment.engine'].search([], limit=1)

        # Transient FSO-like context for the confidence scorer. The engine reads
        # recordset attributes off it; if any are absent it raises, so scoring is
        # wrapped defensively and falls back to a neutral 0.5 (ranking stays
        # earliest-first per the spec).
        fso_ctx = self.env['health.fieldservice.order'].new({
            'patient_id': partner.id,
            'facility_id': facility.id if facility else False,
        })

        today = fields.Date.today()
        candidates = []
        for day_offset in range(horizon_days):
            day = today + timedelta(days=day_offset)
            domain = [
                ('availability_date', '=', day),
                ('status', '=', 'available'),
                ('remaining_capacity', '>', 0),
                ('conflict_detected', '=', False),
            ]
            if province:
                domain += ['|',
                           ('catchment_province_id', '=', province.id),
                           ('catchment_province_id', '=', False)]
            rows = Matrix.search(domain, order='availability_date, start_time')
            for row in rows:
                if not row.staff_id:
                    continue
                confidence = 0.5
                try:
                    if engine:
                        confidence = engine._calculate_assignment_confidence(
                            fso_ctx, row.staff_id)
                except Exception:  # noqa: BLE001 — confidence is a soft ranker
                    confidence = 0.5
                candidates.append({
                    'date': day,
                    'start_time': row.start_time,
                    'staff_id': row.staff_id.id,
                    'staff_name': row.staff_id.name or '',
                    'confidence': confidence,
                })

        # Earliest first; within an identical (day, time) keep the highest
        # confidence staff; return the first `count` distinct (day, time) slots.
        candidates.sort(key=lambda c: (c['date'], c['start_time'], -c['confidence']))
        result, seen = [], set()
        for cand in candidates:
            key = (cand['date'], cand['start_time'])
            if key in seen:
                continue
            seen.add(key)
            result.append(cand)
            if len(result) >= count:
                break
        return result

    # ------------------------------------------------------------------
    # Sending (ZNS through the shipped messaging safety rails)
    # ------------------------------------------------------------------
    def _fso_service_type(self):
        self.ensure_one()
        interest = self.lead_id.service_interest
        if interest in _FSO_SERVICE_TYPES:
            return interest
        return 'consultation'

    @api.model
    def _offer_service_product(self):
        """Default billable service product for the first-visit booking.

        Booking confirmation requires a quote line (or prepaid package), so the
        offer attaches one line for this product. Configurable via
        health_workflow_auto.offer_service_product_id; otherwise the first
        saleable service product is used."""
        pid = self.env['ir.config_parameter'].sudo().get_param(
            'health_workflow_auto.offer_service_product_id')
        if pid:
            product = self.env['product.product'].browse(int(pid)).exists()
            if product:
                return product
        product = self.env['product.product'].search(
            [('sale_ok', '=', True), ('type', '=', 'service')], limit=1)
        return product or self.env['product.product'].search(
            [('sale_ok', '=', True)], limit=1)

    def _base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'http://localhost:8069').rstrip('/')

    def _send_offer_zns(self):
        """Log + send the offer over ZNS, honoring health_messaging safety rails.

        Mirrors health_messaging's ZNS step: respect enabled/dry_run exactly
        (dry_run -> simulated, no real send), reuse the zalo client accessor and
        the try/except normalize_vn_phone pattern. Degrades gracefully when no
        template is configured (offer still created; a lead activity asks the
        owner to send it manually).
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('health_messaging.enabled', 'False') in ('True', 'true', '1')
        dry_run = ICP.get_param('health_messaging.dry_run', 'True') in ('True', 'true', '1')
        template_id = ICP.get_param(
            'health_workflow_auto.zns_template_visit_offer', '')

        phone = _safe_phone(self.partner_id.mobile or self.partner_id.phone)
        msg = self.env['health.outbound.message'].sudo().create({
            'purpose': 'visit_offer',
            'channel': 'zns',
            'partner_id': self.partner_id.id,
            'phone': phone,
            'dedup_key': 'offer-%s' % self.id,
            'state': 'queued',
        })
        self.outbound_message_id = msg.id

        if not template_id or not phone:
            msg.write({'state': 'skipped',
                       'error_text': _('No ZNS template configured or no phone.')})
            self._activity_send_manually()
            return msg
        if not enabled:
            msg.state = 'skipped'
            return msg
        if dry_run:
            msg.write({'state': 'simulated', 'sent_at': fields.Datetime.now()})
            return msg

        params = self._zns_params()
        try:
            from odoo.addons.health_zalo.services.zalo_api import get_api_client
            config = self.env['zalo.config'].search([('active', '=', True)], limit=1)
            result = get_api_client(self.env).send_zns_notification(
                config, phone, template_id, params)
            if isinstance(result, dict) and result.get('error') and result.get('error') != 0:
                msg.write({'state': 'failed',
                           'error_text': 'ZNS error: %s' % (
                               result.get('message') or result.get('error'))})
            else:
                msg.write({'state': 'sent', 'sent_at': fields.Datetime.now()})
        except Exception as exc:  # noqa: BLE001
            msg.write({'state': 'failed', 'error_text': 'ZNS: %s' % exc})
        return msg

    def _zns_params(self):
        self.ensure_one()
        slots = self.slot_ids.sorted('index')
        link = '%s/booking/offer/%s' % (self._base_url(), self.token)
        return {
            'customer_name': self.partner_id.name or '',
            'slot1': slots[0].label() if len(slots) > 0 else '',
            'slot2': slots[1].label() if len(slots) > 1 else '',
            'slot3': slots[2].label() if len(slots) > 2 else '',
            'link': link,
        }

    def _activity_send_manually(self):
        self.ensure_one()
        try:
            self.lead_id.activity_schedule(
                'mail.mail_activity_data_call',
                summary=_('Send first-visit offer manually'),
                note=_('Automatic ZNS could not be sent for this first-visit '
                       'offer. Please contact the client and offer a slot.'),
                user_id=self.lead_id.user_id.id or self.env.uid,
            )
        except Exception as exc:  # noqa: BLE001
            _logger.warning('Visit offer: could not schedule manual activity: %s', exc)

    # ------------------------------------------------------------------
    # Acceptance (row-locked, race-safe) — called by the public controller
    # ------------------------------------------------------------------
    def _slot_feasible(self, slot):
        """Re-validate a slot against the live availability matrix."""
        self.ensure_one()
        Matrix = self.env['health.staff.availability.matrix']
        return bool(Matrix.search_count([
            ('staff_id', '=', slot.staff_id.id),
            ('availability_date', '=', slot.slot_date),
            ('status', '=', 'available'),
            ('remaining_capacity', '>', 0),
            ('conflict_detected', '=', False),
        ]))

    def accept_slot(self, slot_index):
        """Accept a slot: create + confirm an FSO assigned to the slot staff.

        Race-safe: row-locks the offer (FOR UPDATE) so a double-tap books exactly
        one FSO. Returns a dict describing the outcome (never raises for expected
        conditions so the public page can render a friendly result).
        """
        self.ensure_one()
        # Row lock — serialize concurrent accepts of the same offer.
        self.env.cr.execute(
            "SELECT id FROM health_visit_offer WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset(['state'])

        if self.state == 'accepted':
            return {'ok': False, 'reason': 'already_accepted', 'fso': self.fso_id}
        if self.state != 'sent' or (self.expires_at and self.expires_at < fields.Datetime.now()):
            return {'ok': False, 'reason': 'expired'}

        slot = self.slot_ids.filtered(lambda s: s.index == int(slot_index))[:1]
        if not slot:
            return {'ok': False, 'reason': 'invalid_slot'}
        if not slot.staff_id or not self._slot_feasible(slot):
            slot.taken = True
            return {'ok': False, 'reason': 'infeasible'}

        partner = self.partner_id
        facility = partner.primary_facility_id
        # Create a draft FSO via the shared quick-booking builder (inherits all
        # its defaulting), then confirm + assign per spec steps 3-4.
        # NB: no lead_id here — passing it makes the quick-booking builder write
        # contact_outcome on the lead, which re-creates a patient partner without
        # a catchment province and raises. patient_id is already resolved; the
        # offer keeps the lead link (offer.lead_id) separately.
        product = self._offer_service_product()
        vals = {
            'patient_id': partner.id,
            'date': slot.slot_date.strftime('%Y-%m-%d'),
            'time_hour': slot.start_time,
            'duration_hours': 2,
            'facility_id': facility.id if facility else False,
            'service_type': self._fso_service_type(),
            'draft_only': True,
        }
        # A quote line is required for booking confirmation.
        if product:
            vals['product_lines'] = [{'product_id': product.id, 'qty': 1}]
        create_res = self.env['health.fieldservice.order'].action_create_from_quick_booking_owl(vals)
        if not create_res.get('success'):
            return {'ok': False, 'reason': 'create_failed',
                    'detail': create_res.get('error')}
        fso = self.env['health.fieldservice.order'].browse(create_res['booking_id'])

        # Assign the slot staff first (moves draft -> assigned) so the booking
        # confirmation's staff gate is satisfied, then confirm.
        fso.action_assign_staff_to_fso(slot.staff_id.id, assignment_role='lead')
        fso.action_confirm_booking()

        # Reserve the slot on the availability matrix.
        try:
            self.env['health.staff.availability.matrix'].book_staff_slot(
                slot.staff_id.id, slot._start_datetime_utc(), 120, fso_id=fso.id)
        except Exception as exc:  # noqa: BLE001 — reservation is best-effort
            _logger.warning('Visit offer: could not reserve matrix slot: %s', exc)

        self.write({'state': 'accepted', 'fso_id': fso.id})
        slot.taken = True
        try:
            self.lead_id.message_post(body=_(
                'First-visit offer accepted — booking %s created for %s.'
            ) % (fso.name or fso.id, slot.label()))
        except Exception:  # noqa: BLE001
            pass
        return {'ok': True, 'fso': fso, 'slot': slot}

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def cron_expire_offers(self):
        now = fields.Datetime.now()
        due = self.search([('state', '=', 'sent'), ('expires_at', '<', now)])
        for offer in due:
            offer.state = 'expired'
            try:
                offer.lead_id.activity_schedule(
                    'mail.mail_activity_data_call',
                    summary=_('First-visit offer expired'),
                    note=_('The first-visit offer expired without a booking. '
                           'Please call the client.'),
                    user_id=offer.lead_id.user_id.id or self.env.uid,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning('Visit offer expire: activity failed: %s', exc)
        return True
