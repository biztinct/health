# -*- coding: utf-8 -*-
"""Secure family <-> care-team messaging thread (FB-044).

One thread per (patient, relation) — families think in "my channel about Mum",
not per-visit; each message carries its own visit context. Purpose-built (NOT
``mail.message``: family members have no user account, so mail RBAC cannot
scope them). Bodies are PHI-encrypted on the message rows.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# purpose → ir.config_parameter holding the reply ZNS template id. Empty
# default => the reply ping row is silently NOT created (the standing safety
# posture, mirrors health_family_link).
_REPLY_TEMPLATE_PARAM = 'health_family_messages.zns_template_reply'
_ENABLED_PARAM = 'health_family_messages.enabled'
_MAX_PER_HOUR_PARAM = 'health_family_messages.max_per_hour'
_DEFAULT_MAX_PER_HOUR = 10
# FSO states whose visit is "live or upcoming" — used to mint a fresh family
# token to attach to a reply ping.
_OPEN_FSO_STATES = ('confirmed', 'assigned', 'in_progress')


class HealthFamilyThread(models.Model):
    _name = 'health.family.thread'
    _description = 'Family Message Thread'
    _order = 'last_message_at desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    patient_id = fields.Many2one(
        'res.partner', string='Patient', required=True, index=True,
        ondelete='cascade', domain=[('is_patient', '=', True)])
    relation_id = fields.Many2one(
        'health.client.relation', string='Family Relation', required=True,
        index=True, ondelete='cascade')
    facility_id = fields.Many2one(
        'health.facility', string='Facility',
        related='patient_id.primary_facility_id', store=True, index=True,
        help='Patient primary facility — used for inbox filtering.')
    catchment_province_id = fields.Many2one(
        'health.catchment.province', string='Catchment Area',
        compute='_compute_catchment_province_id', store=True, readonly=True,
        index=True, help='Catchment area used for access control.')
    state = fields.Selection([
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], default='active', required=True, index=True)
    message_ids = fields.One2many(
        'health.family.message', 'thread_id', string='Messages')
    last_message_at = fields.Datetime(
        string='Last Message', index=True,
        help='Stored for inbox ordering.')
    unread_ops_count = fields.Integer(
        string='Unread', default=0,
        help='Unread inbound (family → team) messages.')
    reply_text = fields.Char(
        string='Reply', help='Type a reply and click "Send reply".')
    messaging_enabled = fields.Boolean(
        compute='_compute_messaging_enabled',
        help='Global master switch — drives the inbox "disabled" banner.')

    def _compute_messaging_enabled(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            _ENABLED_PARAM, 'False') in ('True', 'true', '1')
        for thread in self:
            thread.messaging_enabled = enabled

    def init(self):
        # Conventions ledger §5.1 — _sql_constraints are not materialized in
        # Odoo 19; back the (patient, relation) uniqueness contract with a
        # real index (one channel per family relation).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                health_family_thread_patient_relation_uidx
            ON health_family_thread (patient_id, relation_id)
        """)

    @api.depends('patient_id', 'relation_id')
    def _compute_display_name(self):
        for thread in self:
            patient = thread.patient_id.name or ''
            rep = thread.relation_id.representative_id.name or ''
            thread.display_name = _('%(patient)s ↔ %(rep)s') % {
                'patient': patient, 'rep': rep} if (patient or rep) else _('Family thread')

    @api.depends('patient_id')
    def _compute_catchment_province_id(self):
        for thread in self:
            patient = thread.patient_id
            thread.catchment_province_id = (
                patient._get_health_catchment_province() if patient else False)

    # ------------------------------------------------------------------
    # Uniqueness pre-check (conventions §5.2 / §5.3 — DB index fires first)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            patient_id = vals.get('patient_id')
            relation_id = vals.get('relation_id')
            if patient_id and relation_id and self.search_count([
                    ('patient_id', '=', patient_id),
                    ('relation_id', '=', relation_id)]):
                raise UserError(_(
                    'A message thread already exists for this patient and '
                    'family relation.'))
        return super().create(vals_list)

    def unlink(self):
        # Deleting a thread would SQL-cascade its messages, silently bypassing
        # the message-level append-only unlink guard — so the parent carries
        # the same guard (system admin only; uninstall runs as superuser).
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                'Family threads hold append-only patient-record messages and '
                'cannot be deleted.'))
        return super().unlink()

    @api.model
    def _get_or_create(self, patient, relation):
        """Idempotent get-or-create for one (patient, relation) channel."""
        thread = self.sudo().search([
            ('patient_id', '=', patient.id),
            ('relation_id', '=', relation.id)], limit=1)
        if thread:
            return thread
        return self.sudo().create({
            'patient_id': patient.id,
            'relation_id': relation.id,
        })

    # ------------------------------------------------------------------
    # Inbound (family → team) — called from the public controller (sudo)
    # ------------------------------------------------------------------
    @api.model
    def _max_per_hour(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            _MAX_PER_HOUR_PARAM, _DEFAULT_MAX_PER_HOUR)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return _DEFAULT_MAX_PER_HOUR

    def _rate_exceeded(self):
        """True when this thread already took the hourly cap of inbound
        messages. The gateway.rate.counter is a per-minute fixed window with a
        global limit, so the per-token/hour contract is enforced here as a
        rolling message count instead (deviation, see report)."""
        self.ensure_one()
        window_start = fields.Datetime.now() - timedelta(hours=1)
        recent = self.env['health.family.message'].sudo().search_count([
            ('thread_id', '=', self.id),
            ('direction', '=', 'in'),
            ('create_date', '>=', window_start),
        ])
        return recent >= self._max_per_hour()

    def post_family_message(self, body, fso=None, author_label=None):
        """Append one inbound (family → team) message and fire the notify legs.
        Returns the created message, or an empty recordset when refused (rate
        cap / empty body). Runs sudo from the public controller."""
        self.ensure_one()
        Message = self.env['health.family.message'].sudo()
        if self.state != 'active':
            # Ops closed the channel — history stays visible on the token page
            # but no new inbound is accepted.
            _logger.info('Family thread %s is closed; message refused.', self.id)
            return Message
        text = Message._sanitize_body(body)
        if not text:
            return Message
        if self._rate_exceeded():
            _logger.info('Family thread %s hit the hourly message cap.', self.id)
            return Message
        message = Message.create({
            'thread_id': self.id,
            'direction': 'in',
            'body': text,
            'fso_id': fso.id if fso else False,
            'author_label': author_label or self.relation_id.display_name,
        })
        self.sudo().write({
            'last_message_at': fields.Datetime.now(),
            'unread_ops_count': self.unread_ops_count + 1,
        })
        # Notify legs are best-effort: a family message is patient-record
        # material and must never be lost to an alerting failure.
        try:
            self._notify_inbound(message, fso)
        except Exception:  # noqa: BLE001
            _logger.exception('Family message notify failed (thread %s)', self.id)
        return message

    def _notify_targets(self, fso):
        """Users to alert on inbound: the visit's lead nurse (via the STORED
        primary_nurse_id, not the non-stored lead_staff_id — §5.22) and the
        facility manager. sudo throughout (hr.employee reads trip the
        public-profile guard, §5.24; here we already run sudo from a public
        route)."""
        self.ensure_one()
        users = self.env['res.users'].sudo()
        fso = fso.sudo() if fso else fso
        if fso and fso.primary_nurse_id and fso.primary_nurse_id.user_id:
            users |= fso.primary_nurse_id.user_id
        facility = (fso.facility_id if fso else False) or \
            self.patient_id.primary_facility_id
        facility = facility.sudo() if facility else facility
        manager = facility.facility_manager_id if facility else False
        if manager and manager.user_id:
            users |= manager.user_id
        return users

    def _notify_inbound(self, message, fso):
        """Three best-effort notify legs (§2.3): PWA bell row + VAPID push for
        each target user, and a mail.activity on the visit/patient."""
        self.ensure_one()
        patient_name = self.patient_id.name or _('a patient')
        preview = (message.body or '')[:120]
        body_text = _('New message from %(who)s about %(patient)s: %(preview)s') % {
            'who': message.author_label or _('family'),
            'patient': patient_name, 'preview': preview}
        targets = self._notify_targets(fso)
        Notif = self.env['health.pwa.staff.notification'].sudo()
        push_config = self.env['health.pwa.config'].sudo().get_push_config()
        for user in targets:
            # (a) PWA bell queue row. NOTE: the shipped PWA bell switches on
            # notification_type with no default branch, so this new type renders
            # as an (empty) card in today's app shell — the working in-app signal
            # is the VAPID push below; a future PWA-versioned phase adds the case.
            try:
                Notif.create({
                    'user_id': user.id,
                    'fso_id': fso.id if fso else False,
                    'family_thread_id': self.id,
                    'notification_type': 'family_message',
                    'patient_name': patient_name,
                    'fso_name': fso.name if fso else '',
                    'message': body_text,
                })
            except Exception:  # noqa: BLE001 — one leg never blocks the others
                _logger.exception('Family bell notify failed for user %s', user.id)
            # (b) VAPID push (best-effort, carries the real content).
            if push_config:
                try:
                    push_config.send_push_notification(
                        user_id=user.id,
                        title=_('New family message'),
                        body=body_text,
                        data={'type': 'family_message',
                              'thread_id': self.id,
                              'fso_id': fso.id if fso else None},
                        tag='family-message-%s' % self.id)
                except Exception:  # noqa: BLE001
                    _logger.exception('Family push failed for user %s', user.id)
        # (c) mail.activity on the FSO (or patient) for the facility manager.
        self._schedule_activity(message, fso)

    def _schedule_activity(self, message, fso):
        activity_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return
        record = fso.sudo() if fso else self.patient_id.sudo()
        try:
            user = self._notify_targets(fso)[:1]
            record.activity_schedule(
                activity_type_id=activity_type.id,
                summary=_('Reply to family message'),
                note=_('A family member sent a message about %s.')
                % (self.patient_id.name or ''),
                user_id=user.id if user else self.env.uid)
        except Exception:  # noqa: BLE001 — alerting must never break capture
            _logger.exception('Family activity failed (thread %s)', self.id)

    # ------------------------------------------------------------------
    # Ops actions (backend inbox)
    # ------------------------------------------------------------------
    def _latest_open_fso(self):
        self.ensure_one()
        return self.env['health.fieldservice.order'].sudo().search([
            ('patient_id', '=', self.patient_id.id),
            ('state', 'in', _OPEN_FSO_STATES),
        ], order='scheduled_datetime desc', limit=1)

    def action_mark_read(self):
        for thread in self:
            thread.message_ids.filtered(
                lambda m: m.direction == 'in' and not m.read_by_ops
            ).write({'read_by_ops': True})
            thread.unread_ops_count = 0
            # Clear the staff bell rows for this thread. Today's app shell has
            # no render/dismiss case for the family_message type, so without
            # this the badge count would stay inflated forever once a family
            # message arrives — handling the thread is the dismissal.
            self.env['health.pwa.staff.notification'].sudo().search([
                ('family_thread_id', '=', thread.id),
                ('notification_type', '=', 'family_message'),
                ('is_read', '=', False),
            ]).write({'is_read': True})
        return True

    def _post_team_reply(self, body, author_user, fso=None, send_zns=True,
                         mark_read=True):
        """Shared team → family OUTBOUND core: create the 'out' message, refresh
        last_message_at, and (``mark_read=True``) `action_mark_read` — which
        ALSO clears the family_message PWA bell rows. For a reply
        (`send_zns=True`) it fires the `family_message_reply` ZNS ping. Used by
        the ops inbox (`action_send_reply`) and the PWA nurse reply endpoint;
        FB-047 passes `send_zns=False, mark_read=False` (a one-tap update is not
        the sender reading the thread) and sends its own `family_update` ping.
        Returns the created message; raises on an empty/over-cap body (shared
        `_sanitize_body`) or a closed thread."""
        self.ensure_one()
        if self.state != 'active':
            # Mirror of the inbound gate: a closed channel takes no new
            # messages from either side (history stays readable).
            raise UserError(_('This family message thread is closed.'))
        text = self.env['health.family.message']._sanitize_body(body)
        if not text:
            raise UserError(_('Message is empty.'))
        if fso is None:
            fso = self._latest_open_fso()
        message = self.env['health.family.message'].create({
            'thread_id': self.id,
            'direction': 'out',
            'body': text,
            'author_user_id': author_user.id,
            'author_label': author_user.name,
            'fso_id': fso.id if fso else False,
        })
        self.write({'last_message_at': fields.Datetime.now()})
        if mark_read:
            self.action_mark_read()
        if send_zns:
            try:
                self._send_reply_zns(message)
            except Exception:  # noqa: BLE001 — a send must never break the reply
                _logger.exception('Family reply ZNS failed (thread %s)', self.id)
        return message

    def action_send_reply(self):
        """Ops inbox reply — thin wrapper over `_post_team_reply`."""
        self.ensure_one()
        if not self.messaging_enabled:
            # The form banner promises "read-only until enabled"; enforce it
            # at the ORM level too, not just the readonly attr on reply_text.
            raise UserError(_(
                'Secure family messaging is disabled '
                '(health_family_messages.enabled).'))
        body = (self.reply_text or '').strip()
        if not body:
            raise UserError(_('Please type a reply first.'))
        self.write({'reply_text': False})
        self._post_team_reply(body, self.env.user)
        return True

    # ------------------------------------------------------------------
    # Reply ZNS ping (health_messaging rails, new purpose)
    # ------------------------------------------------------------------
    def _send_reply_zns(self, message):
        """Log + (respecting the rails) send one "you have a reply" ZNS. No
        template configured => the row is silently NOT created (no-phantom)."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        template_id = ICP.get_param(_REPLY_TEMPLATE_PARAM, '')
        if not template_id:
            return self.env['health.outbound.message']
        # sudo the family-relation/partner reads: the caller may be an ops user
        # without direct ACL on health.client.relation.
        partner = self.sudo().relation_id.representative_id
        if not partner:
            return self.env['health.outbound.message']
        dedup_key = 'famreply-%s-%s' % (self.id, message.id)
        Message = self.env['health.outbound.message'].sudo()
        existing = Message.search([('dedup_key', '=', dedup_key)], limit=1)
        if existing:
            return existing

        enabled = ICP.get_param('health_messaging.enabled', 'False') in (
            'True', 'true', '1')
        dry_run = ICP.get_param('health_messaging.dry_run', 'True') in (
            'True', 'true', '1')
        params = self._reply_zns_params()
        phone = self._safe_phone(partner.mobile or partner.phone)
        fso = self._latest_open_fso()
        msg = Message.create({
            'purpose': 'family_message_reply',
            'channel': 'zns',
            'partner_id': partner.id,
            'fso_id': fso.id if fso else False,
            'phone': phone,
            'dedup_key': dedup_key,
            'payload_json': params,
            'state': 'queued',
        })
        if not phone:
            msg.write({'state': 'skipped',
                       'error_text': _('No usable phone for the recipient.')})
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
        except Exception as exc:  # noqa: BLE001 — a send must never break flow
            msg.write({'state': 'failed', 'error_text': 'ZNS: %s' % exc})
        return msg

    def _reply_zns_params(self):
        """{patient_name, link} — link is a FRESH family token for the most
        recent live-or-upcoming visit, else omitted. sudo the relation/link
        reads: an ops caller has no direct ACL on health.client.relation."""
        self.ensure_one()
        thread = self.sudo()
        params = {'patient_name': thread.patient_id.name or ''}
        fso = self._latest_open_fso()
        if fso:
            link = self.env['health.family.link'].sudo()._get_or_create_link(
                fso, thread.relation_id)
            if link:
                params['link'] = link._page_url()
        return params

    @staticmethod
    def _safe_phone(phone):
        """normalize_vn_phone raises on invalid; we want falsy-on-invalid
        (conventions ledger §5.15)."""
        from odoo.addons.health_base.models.phone_utils import normalize_vn_phone
        from odoo.exceptions import ValidationError
        try:
            return normalize_vn_phone(phone) or ''
        except ValidationError:
            return ''
