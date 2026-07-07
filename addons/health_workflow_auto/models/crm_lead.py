import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    """E.5 — launch an instant first-visit offer when a lead is qualified."""
    _inherit = 'crm.lead'

    visit_offer_ids = fields.One2many('health.visit.offer', 'lead_id')
    visit_offer_count = fields.Integer(compute='_compute_visit_offer_count')

    def _compute_visit_offer_count(self):
        for lead in self:
            lead.visit_offer_count = len(lead.visit_offer_ids)

    def action_convert_to_client(self):
        res = super().action_convert_to_client()
        for lead in self:
            try:
                lead._launch_first_visit_offer()
            except Exception:  # noqa: BLE001 — offer failure must never block qualify
                _logger.exception('First-visit offer failed for lead %s', lead.id)
        return res

    def action_send_first_visit_offer(self):
        """Manual button — idempotent (skips if an unexpired sent offer exists)."""
        self.ensure_one()
        offer = self._launch_first_visit_offer(manual=True)
        if not offer:
            return True
        return True

    def _offer_partner(self):
        self.ensure_one()
        return self.patient_id or self.partner_id

    def _launch_first_visit_offer(self, manual=False):
        self.ensure_one()
        now = fields.Datetime.now()
        # Idempotent: an unexpired 'sent' offer already covers this lead.
        existing = self.visit_offer_ids.filtered(
            lambda o: o.state == 'sent' and (not o.expires_at or o.expires_at > now))
        if existing:
            return existing[:1]

        partner = self._offer_partner()
        # sudo: qualification can be run by users without sales-model write rights;
        # the offer is an internal record and the send path re-sudos as needed.
        Offer = self.env['health.visit.offer'].sudo()

        # No usable partner/phone -> lead activity instead of a crash.
        from odoo.addons.health_workflow_auto.models.visit_offer import _safe_phone
        phone = _safe_phone((partner.mobile or partner.phone) if partner else '') \
            or _safe_phone(getattr(self, 'mobile', '') or self.phone)
        if not partner or not phone:
            try:
                self.activity_schedule(
                    'mail.mail_activity_data_call',
                    summary=_('First-visit offer: no phone on file'),
                    note=_('Could not auto-send a first-visit offer (no usable '
                           'phone). Please contact the client.'),
                    user_id=self.user_id.id or self.env.uid,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning('Lead %s offer-activity failed: %s', self.id, exc)
            return Offer

        # Skip if the lead already has an open FSO (a booking is in flight).
        open_fso = self.env['health.fieldservice.order'].search_count([
            ('crm_lead_id', '=', self.id),
            ('state', 'not in', ('cancelled', 'closed')),
        ]) if 'crm_lead_id' in self.env['health.fieldservice.order']._fields else 0
        if open_fso:
            return Offer

        slots = Offer._propose_first_visit_slots(self)
        facility = partner.primary_facility_id
        offer = Offer.create({
            'lead_id': self.id,
            'partner_id': partner.id,
            'fso_timezone': (facility.timezone if facility and getattr(
                facility, 'timezone', False) else 'Asia/Ho_Chi_Minh'),
            'slot_ids': [(0, 0, {
                'index': i + 1,
                'slot_date': s['date'],
                'start_time': s['start_time'],
                'staff_id': s['staff_id'],
                'confidence': s['confidence'],
            }) for i, s in enumerate(slots)],
        })
        offer._send_offer_zns()
        return offer
