# -*- coding: utf-8 -*-
"""``web.leads.connector`` — the self-service Website Connector (W2.5 §5.1).

Before this phase, connecting a clinic's website to the CRM was a developer
job: SSH, a hand-created service user, `psql` for the city maps. This model is
that job turned into one screen — issue credentials, copy a ready-to-paste
`wp-config.php` block, edit the city maps, run a residue-free pipeline test,
watch a health strip, rotate or disconnect — with every action on the
record's chatter.

Three properties hold everywhere in this file and must survive any edit:

* **The secret plaintext is never stored, logged or returned.** It exists only
  inside the sticky notification `gateway.oauth.client.action_regenerate_
  secret()` builds (health_api_gateway/models/gateway_oauth_client.py:96-112).
  This model delegates to that method and never generates a secret of its own.
* **The two `ir.config_parameter` city maps stay the single source of truth**
  (handover fact #5). The connector is a WINDOW onto them: it reads them for
  display and writes them back on save. The install-time seeds
  (`data/web_leads_params.xml`, `noupdate="1"`) remain the defaults, and
  `web.lead.service` keeps reading the params, never this model.
* **Parameters are written as STRINGS** — `'True'` / `'False'` / `'0'`, never
  Python `False` (ledger §5.36: a falsy value handed to `set_param` UNLINKS
  the parameter, and an unlinked parameter is indistinguishable from one that
  was never set).
"""
import json
import logging
import uuid
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.health_api_gateway.controllers.gateway import ApiError

from .web_lead_service import (
    _FALSY_PARAM, CITY_HCM, CITY_HN, HEARTBEAT_STALE_HOURS, HEARTBEAT_SUMMARY,
    PARAM_FORM_CITY_MAP, PARAM_HEARTBEAT_ENABLED, PARAM_HEARTBEAT_USER,
    PARAM_URL_CITY_MAP)

_logger = logging.getLogger(__name__)

# The machine account the WordPress relay authenticates as. Hand-created on
# vietuat (id 6103) with NO xmlid, so provisioning finds it BY LOGIN and
# adopts it — creating a second one would leave the live OAuth client pointing
# at an account nobody maintains (handover fact #4).
SERVICE_LOGIN = 'svc_web_leads'
SERVICE_USER_NAME = 'Website Lead Relay (service)'
SERVICE_GROUP = 'health_web_leads.group_web_leads_service'

WRITE_SCOPE_REF = 'health_web_leads.scope_web_lead_write'
READ_SCOPE_REF = 'health_web_leads.scope_web_lead_read'
WRITE_SCOPE_CODE = 'web_lead.write'
READ_SCOPE_CODE = 'web_lead.read'

DEFAULT_CLIENT_NAME = 'WordPress pkgdvietuc'
TOKEN_LIFETIME = 3600

TOKEN_PATH = '/oauth/token'
CAPTURE_PATH = '/api/v1/web/leads'
RECONCILE_PATH = '/api/v1/web/leads/reconcile'

# Who may operate the connector. Mirrors the Channel Center's own gate
# (health_care_command_channels/models/care_channel_connection.py:142-146).
# The ACL file grants exactly this set; the method-level check is what stops a
# direct RPC reaching an action whose body runs through `sudo()`
# (ledger §5.37 corollary).
OPERATOR_GROUPS = (
    'base.group_system',
    'health_crm.group_health_crm_manager',
    'health_access.group_clinic_admin',
)

# The logical city keys `web.lead.service._derive_city` understands. Anything
# else in a map is a silent dead entry, so the form refuses it.
VALID_CITY_KEYS = (CITY_HN, CITY_HCM)

# NEVER a real secret. The block is copied into `wp-config.php` and the admin
# pastes the value they were shown once over this placeholder.
SECRET_PLACEHOLDER = '<the secret you copied when it was shown>'


class _PipelineTestRollback(Exception):
    """Private sentinel raised inside `action_test_pipeline`'s savepoint.

    A synthetic submission must leave NOTHING behind (rail R2), and the only
    reliable way to undo an ORM write is to make the savepoint roll back — so
    the happy path raises this, and the caller catches it immediately outside
    the `with` block. Ledger §5.55: the savepoint, not the `try`, is what
    keeps the outer transaction usable.
    """


class WebLeadsConnector(models.Model):
    _name = 'web.leads.connector'
    _description = 'Website Connector'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'company_id, id'

    name = fields.Char(
        string='Name', required=True, default='Website connector',
        tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)

    oauth_client_id = fields.Many2one(
        'gateway.oauth.client', string='OAuth Client', readonly=True,
        tracking=True, copy=False,
        help='The API-gateway client the WordPress relay authenticates with. '
             'Issued by the Get credentials button — never edited by hand.')

    state = fields.Selection(
        [('draft', 'Not connected'),
         ('credentials_issued', 'Credentials issued'),
         ('live', 'Live'),
         ('disconnected', 'Disconnected')],
        string='Status', compute='_compute_state',
        help='Live means at least one website submission has been received.')

    client_id_display = fields.Char(
        string='Client ID', related='oauth_client_id.client_id', readonly=True)
    wp_config_block = fields.Text(
        string='WordPress Configuration', compute='_compute_wp_config_block',
        help='Paste this into wp-config.php, then replace the placeholder '
             'with the secret you were shown once.')

    form_city_map_text = fields.Text(
        string='Form → City Map', compute='_compute_city_maps',
        inverse='_inverse_form_city_map_text',
        help='Which Contact Form 7 form belongs to which city, as JSON. '
             'Example: {"15838": "HN", "15670": "HCM"}. Only "HN" (Hà Nội) '
             'and "HCM" (Hồ Chí Minh) are accepted as values.')
    url_city_map_text = fields.Text(
        string='Page URL → City Map', compute='_compute_city_maps',
        inverse='_inverse_url_city_map_text',
        help='Which page-URL fragment belongs to which city, as JSON. '
             'Example: {"/lien-he-hanoi/": "HN", "/lien-he-tphcm/": "HCM"}. '
             'A fragment matches anywhere in the submitted page URL.')

    heartbeat_enabled = fields.Boolean(
        string='Daily Delivery Alert', compute='_compute_heartbeat',
        inverse='_inverse_heartbeat_enabled',
        help='Raise a to-do when no website submission has arrived for 24 '
             'hours. Leave this off until the WordPress relay is live, or '
             'every quiet night raises a false alarm.')
    heartbeat_user_id = fields.Many2one(
        'res.users', string='Alert Watcher', compute='_compute_heartbeat',
        inverse='_inverse_heartbeat_user',
        help='Who gets the to-do. Empty falls back to the API-gateway '
             'administrators, then to the system administrator.')

    last_received_at = fields.Datetime(
        string='Last Submission', compute='_compute_health', readonly=True)
    received_7d_count = fields.Integer(
        string='Submissions (7 days)', compute='_compute_health',
        readonly=True)
    health_note = fields.Char(
        string='Delivery Health', compute='_compute_health', readonly=True)

    # ------------------------------------------------------------------
    # Ledger §5.1 — `_sql_constraints` are NOT materialized on Odoo 19.
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS web_leads_connector_company_uidx
            ON web_leads_connector (company_id)
            WHERE company_id IS NOT NULL
        """)

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends('oauth_client_id', 'oauth_client_id.active')
    def _compute_state(self):
        """DELIBERATELY NOT STORED — see the phase report.

        `live` means "a WordPress touchpoint exists", and touchpoints are
        written by the capture endpoint in a transaction this model has no
        `@api.depends` path to. A stored field would therefore say
        `credentials_issued` forever after the first real submission; a
        non-stored one is simply right every time it is read. The statusbar
        widget renders a computed Selection fine (core precedent:
        `account.lock_exception.state`).
        """
        delivered = bool(self.env['health.lead.touchpoint'].sudo().search_count(
            [('source_system', '=', 'wordpress')], limit=1))
        for record in self:
            client = record.oauth_client_id.sudo()
            if not client:
                record.state = 'draft'
            elif not client.active:
                record.state = 'disconnected'
            elif delivered:
                record.state = 'live'
            else:
                record.state = 'credentials_issued'

    @api.depends('oauth_client_id', 'oauth_client_id.client_id')
    def _compute_wp_config_block(self):
        """The paste-ready block. It carries the client id and the endpoint
        URLs, and the SECRET PLACEHOLDER — never secret material, which is why
        rotating a secret leaves this text byte-identical (T3)."""
        base_url = (self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or '').rstrip('/')
        for record in self:
            client_id = record.oauth_client_id.sudo().client_id or ''
            record.wp_config_block = '\n'.join((
                "/* Viet Uc — website lead connector */",
                "define( 'VU_LEADS_TOKEN_URL',     '%s%s' );"
                % (base_url, TOKEN_PATH),
                "define( 'VU_LEADS_CAPTURE_URL',   '%s%s' );"
                % (base_url, CAPTURE_PATH),
                "define( 'VU_LEADS_RECONCILE_URL', '%s%s' );"
                % (base_url, RECONCILE_PATH),
                "define( 'VU_LEADS_CLIENT_ID',     '%s' );" % client_id,
                "define( 'VU_LEADS_CLIENT_SECRET', '%s' );"
                % SECRET_PLACEHOLDER,
            ))

    @api.depends('company_id')
    def _compute_city_maps(self):
        Param = self.env['ir.config_parameter'].sudo()
        form_raw = Param.get_param(PARAM_FORM_CITY_MAP)
        url_raw = Param.get_param(PARAM_URL_CITY_MAP)
        for record in self:
            record.form_city_map_text = self._pretty_json(form_raw)
            record.url_city_map_text = self._pretty_json(url_raw)

    @api.depends('company_id')
    def _compute_heartbeat(self):
        Param = self.env['ir.config_parameter'].sudo()
        enabled = self._param_is_true(Param.get_param(PARAM_HEARTBEAT_ENABLED))
        user = self._param_user(Param.get_param(PARAM_HEARTBEAT_USER))
        for record in self:
            record.heartbeat_enabled = enabled
            record.heartbeat_user_id = user.id if user else False

    @api.depends('oauth_client_id')
    def _compute_health(self):
        Touchpoint = self.env['health.lead.touchpoint'].sudo()
        newest = Touchpoint.search([('source_system', '=', 'wordpress')],
                                   order='received_at desc, id desc', limit=1)
        now = fields.Datetime.now()
        count = Touchpoint.search_count(
            [('source_system', '=', 'wordpress'),
             ('received_at', '>=', now - timedelta(days=7))])
        last = newest.received_at if newest else False
        for record in self:
            record.last_received_at = last
            record.received_7d_count = count
            if not last:
                record.health_note = _(
                    'No submission ever received — the website side is not '
                    'live yet.')
            else:
                hours = int((now - last).total_seconds() // 3600)
                if hours >= HEARTBEAT_STALE_HOURS:
                    record.health_note = _(
                        'Nothing for over %s hours — check the WordPress '
                        'relay.', hours)
                else:
                    record.health_note = _('Last submission %s hours ago.',
                                           hours)

    # ==================================================================
    # Inverses — the params are the store, this model is the window
    # ==================================================================
    def _inverse_form_city_map_text(self):
        for record in self:
            record._write_city_map(
                PARAM_FORM_CITY_MAP, record.form_city_map_text,
                _('Form → City map'))

    def _inverse_url_city_map_text(self):
        for record in self:
            record._write_city_map(
                PARAM_URL_CITY_MAP, record.url_city_map_text,
                _('Page URL → City map'))

    def _write_city_map(self, key, text, label):
        """Validate, persist to the parameter, and log the change on chatter.

        Silent on a no-op write: the form saves both map fields on every save,
        and a chatter entry per save would bury the edits that matter.
        """
        self.ensure_one()
        parsed = self._parse_city_map(text, label)
        Param = self.env['ir.config_parameter'].sudo()
        previous = Param.get_param(key) or ''
        new_raw = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        try:
            unchanged = json.loads(previous) == parsed
        except (ValueError, TypeError):
            unchanged = False
        if unchanged:
            return
        Param.set_param(key, new_raw)
        self.message_post(body=Markup('<p>%s</p><pre>%s</pre>') % (
            _('%(label)s updated by %(user)s. The capture endpoint reads the '
              'new map on its next submission.',
              label=label, user=self.env.user.name),
            new_raw))

    def _inverse_heartbeat_enabled(self):
        Param = self.env['ir.config_parameter'].sudo()
        for record in self:
            wanted = bool(record.heartbeat_enabled)
            if self._param_is_true(Param.get_param(
                    PARAM_HEARTBEAT_ENABLED)) == wanted:
                continue
            # Ledger §5.36 — the STRING, never Python False.
            Param.set_param(PARAM_HEARTBEAT_ENABLED,
                            'True' if wanted else 'False')
            record.message_post(body=Markup('<p>%s</p>') % (
                _('Daily delivery alert switched ON by %s.',
                  self.env.user.name) if wanted else
                _('Daily delivery alert switched OFF by %s.',
                  self.env.user.name)))

    def _inverse_heartbeat_user(self):
        Param = self.env['ir.config_parameter'].sudo()
        for record in self:
            previous_raw = Param.get_param(PARAM_HEARTBEAT_USER) or ''
            wanted = record.heartbeat_user_id
            # '0' rather than '' or False: §5.36 again — an empty/falsy value
            # UNLINKS the row, and `_heartbeat_user` already reads a dangling
            # id as "fall through to the group".
            new_raw = str(wanted.id) if wanted else '0'
            # The W1 seed ships the parameter EMPTY, which means exactly what
            # '0' means. Normalising here keeps a first save of an untouched
            # connector from posting a spurious "watcher cleared" note.
            if (str(previous_raw).strip() or '0') == new_raw:
                continue
            Param.set_param(PARAM_HEARTBEAT_USER, new_raw)
            record._reassign_heartbeat_activity(wanted)
            record.message_post(body=Markup('<p>%s</p>') % (
                _('Delivery-alert watcher set to %(watcher)s by %(user)s.',
                  watcher=wanted.name, user=self.env.user.name) if wanted else
                _('Delivery-alert watcher cleared by %s — alerts fall back to '
                  'the API-gateway administrators.', self.env.user.name)))

    def _reassign_heartbeat_activity(self, watcher):
        """Move any OPEN heartbeat to-do onto the new watcher (W2 review LOW).

        The alert's dedupe key is (user, summary) — `_heartbeat_alert` searches
        on both — so changing the watcher without moving the activity strands
        an open to-do on somebody who is no longer responsible, AND lets the
        next cron run raise a second one for the new watcher.
        """
        self.ensure_one()
        Activity = self.env['mail.activity'].sudo()
        # Ledger §5.89: these are MODEL-LESS activities; the summary constant
        # is the only thing that identifies them.
        open_alerts = Activity.search([('res_model', '=', False),
                                       ('summary', '=', HEARTBEAT_SUMMARY)])
        if not open_alerts:
            return
        target = watcher or self.env['web.lead.service']._heartbeat_user()
        if not target:
            return
        keep = open_alerts[0]
        if keep.user_id != target:
            keep.user_id = target.id
        duplicates = open_alerts - keep
        if duplicates:
            duplicates.unlink()

    # ==================================================================
    # Actions
    # ==================================================================
    def action_provision_credentials(self):
        """Idempotent adopt-or-create, then delegate the secret.

        Called by both header buttons: on a `draft` connector it reads as
        *Get credentials*, afterwards as *Rotate secret*. There is no separate
        rotate path because `action_regenerate_secret` already IS one
        (handover fact #2).
        """
        self.ensure_one()
        self._check_operator()

        group = self.env.ref(SERVICE_GROUP)
        user, user_created = self._ensure_service_user(group)
        client, client_created = self._ensure_oauth_client(user)

        had_secret = bool(client.client_secret_hash)
        action = client.action_regenerate_secret()

        self.message_post(body=Markup('<p>%s</p>') % (
            _('Credentials issued by %(user)s: service account %(login)s, '
              'OAuth client %(client)s. The secret was shown once and is not '
              'stored anywhere.',
              user=self.env.user.name, login=user.login, client=client.name)
            if not had_secret else
            _('Client secret rotated by %(user)s for OAuth client '
              '%(client)s. Update wp-config.php on the website — the previous '
              'secret stopped working immediately.',
              user=self.env.user.name, client=client.name)))
        if user_created or client_created:
            self.message_post(body=Markup('<p>%s</p>') % _(
                'Provisioning created: %s.',
                ', '.join(filter(None, [
                    _('the service user') if user_created else '',
                    _('the OAuth client') if client_created else '']))))
        else:
            self.message_post(body=Markup('<p>%s</p>') % _(
                'Provisioning adopted the existing service account and OAuth '
                'client — nothing was duplicated.'))

        return self._with_reload(action)

    def _ensure_service_user(self, group):
        """Find `svc_web_leads` (archived or not) or create it. Never touches
        an existing account's password — the relay's credential is the OAuth
        secret, not a login."""
        Users = self.env['res.users'].sudo()
        internal = self.env.ref('base.group_user')
        user = Users.with_context(active_test=False).search(
            [('login', '=', SERVICE_LOGIN)], limit=1)
        created = False
        if not user:
            user = Users.create({
                'name': SERVICE_USER_NAME,
                'login': SERVICE_LOGIN,
                'company_id': self.company_id.id,
                'company_ids': [(6, 0, self.company_id.ids)],
                # `base.group_user` is granted EXPLICITLY: on Odoo 19 it is
                # what makes an account an internal user, and the capture path
                # needs what hangs off it (mail.message, ir.sequence).
                'group_ids': [(6, 0, [internal.id, group.id])],
            })
            created = True
        else:
            missing = (internal | group) - user.group_ids
            if missing:
                user.write({'group_ids': [(4, gid) for gid in missing.ids]})
            if not user.active:
                user.active = True
        return user, created

    def _ensure_oauth_client(self, user):
        """Adopt the live client when one already fits, else create one.

        The vietuat client ("WordPress pkgdvietuc", id 122) has no xmlid, so
        the match is structural: active, owned by the service user, and
        carrying BOTH web_lead scopes.
        """
        Client = self.env['gateway.oauth.client'].sudo()
        write_scope = self.env.ref(WRITE_SCOPE_REF)
        read_scope = self.env.ref(READ_SCOPE_REF)
        wanted_codes = {WRITE_SCOPE_CODE, READ_SCOPE_CODE}

        client = self.oauth_client_id.sudo()
        created = False
        if not client:
            for candidate in Client.search([('user_id', '=', user.id),
                                            ('active', '=', True)],
                                           order='id asc'):
                if wanted_codes <= set(candidate.allowed_scope_ids.mapped(
                        'code')):
                    client = candidate
                    break
        if not client:
            client = Client.create({
                'name': DEFAULT_CLIENT_NAME,
                'user_id': user.id,
                'allowed_scope_ids': [(6, 0, (write_scope | read_scope).ids)],
                'token_lifetime': TOKEN_LIFETIME,
            })
            created = True
        else:
            if not client.active:
                client.active = True
            if client.user_id != user:
                client.user_id = user.id
            missing = (write_scope | read_scope) - client.allowed_scope_ids
            if missing:
                client.allowed_scope_ids = [(4, sid) for sid in missing.ids]
        if self.oauth_client_id != client:
            self.oauth_client_id = client.id
        return client, created

    def action_test_pipeline(self):
        """Run one synthetic submission through the REAL handler and undo it.

        What this proves: the city maps the admin just edited resolve, the
        catchment rows they name exist, and `process_submission` runs clean
        UNDER THE RIGHTS THE RELAY ACTUALLY HAS. What it cannot prove: HTTP
        authentication — the CRM does not know the client secret, so only a
        real submission from the WordPress plugin tests that half. The
        notification says so.

        The submission runs as the connector's own service user, not as the
        administrator who pressed the button. Two reasons, and the first was
        found by driving the screen rather than by a test: a CRM manager has
        `health.lead.touchpoint` create = 0 (security/ir.model.access.csv), so
        running as the operator made the button answer "You are not allowed to
        create Lead Touchpoint" for the exact persona the screen is for —
        every test passed because tests run as uid 1 (§5.4). The second is the
        better one: the relay's own rights are what the test should exercise,
        so an ACL regression on the service account shows up HERE. Before
        credentials exist there is no service user, and the run falls back to
        `sudo()` — the maps are still what is being validated.
        """
        self.ensure_one()
        self._check_operator()
        runner = self.oauth_client_id.sudo().user_id
        Service = self.env['web.lead.service']
        Runner = (Service.with_user(runner)
                  if runner and runner.active else Service.sudo())

        form_map = Service._json_param(PARAM_FORM_CITY_MAP)
        url_map = Service._json_param(PARAM_URL_CITY_MAP)
        form_id = str(next(iter(form_map), '') or 'connector-test')
        page_url = str(next(iter(url_map), '') or '')

        payload = {
            'submission_id': 'connector-test-%s' % uuid.uuid4().hex,
            'form_id': form_id,
            'name': 'Kiểm tra kết nối',
            'phone': '0900000000',
            'page_url': page_url or False,
            'anti_spam': {'honeypot_filled': False, 'token_ok': True},
        }
        city_key, city_source = Service._derive_city(payload)
        province = Service._resolve_catchment(city_key) if city_key \
            else self.env['health.catchment.province'].browse()

        outcome, failure = None, None
        try:
            with self.env.cr.savepoint():
                outcome = Runner.process_submission(payload)
                # ALWAYS roll back: a configuration test that leaves a lead
                # behind is a configuration test nobody dares run twice.
                raise _PipelineTestRollback()
        except _PipelineTestRollback:
            pass
        except ApiError as error:
            failure = str(getattr(error, 'message', error))
        except Exception as error:  # noqa: BLE001 — report, never 500 a button
            _logger.warning('web_leads: connector pipeline test failed',
                            exc_info=True)
            failure = str(error) or type(error).__name__
        # `cr.savepoint()` clears the precommit queue on the way out but NOT
        # the ORM cache, so without this the environment still believes in a
        # lead the database has already forgotten.
        self.env.invalidate_all()

        caveat = _(
            'This checks the city maps and the lead pipeline only. It cannot '
            'check HTTP authentication — the CRM never knows the client '
            'secret, so the live test is a real submission from the WordPress '
            'plugin.')
        if failure:
            self.message_post(body=Markup('<p>%s</p>') % _(
                'Pipeline test FAILED for %(user)s: %(reason)s',
                user=self.env.user.name, reason=failure))
            return self._notify(_('Website connector: pipeline test failed'),
                                '%s\n\n%s' % (failure, caveat),
                                kind='warning')

        source_labels = dict(self.env['crm.lead'].fields_get(
            ['city_source'])['city_source']['selection'])
        source_label = source_labels.get(city_source, city_source)
        if province:
            headline = _(
                'Pipeline OK — a submission on form %(form)s would create a '
                'lead in %(city)s (city from: %(source)s). Nothing was saved.',
                form=form_id, city=province.name, source=source_label)
        else:
            headline = _(
                'Pipeline OK — but a submission on form %(form)s would create '
                'a lead with NO city (city from: %(source)s), which flags it '
                'for review. Check the maps below. Nothing was saved.',
                form=form_id, source=source_label)
        lines = [headline]
        if outcome and outcome.get('status') != 'created':
            lines.append(_(
                'The synthetic submission resolved to "%s" rather than a new '
                'lead — an open lead already matches the test phone number.',
                outcome['status']))
        lines.append(caveat)

        self.message_post(body=Markup('<p>%s</p>') % _(
            'Pipeline test run by %(user)s: %(result)s',
            user=self.env.user.name, result=headline))
        return self._notify(_('Website connector: pipeline OK'),
                            '\n\n'.join(lines))

    def action_disconnect(self):
        """Archive the client — never delete it. The audit log references it,
        and a deleted client makes six months of `api.audit.log` unreadable."""
        self.ensure_one()
        self._check_operator()
        client = self.oauth_client_id.sudo()
        if not client:
            raise ValidationError(_('There is nothing to disconnect yet — no '
                                    'credentials have been issued.'))
        if client.active:
            client.active = False
        self.message_post(body=Markup('<p>%s</p>') % _(
            'Website disconnected by %(user)s: OAuth client %(client)s is '
            'archived, so its tokens no longer authenticate. The record is '
            'kept for the audit trail.',
            user=self.env.user.name, client=client.name))
        return self._with_reload(self._notify(
            _('Website disconnected'),
            _('The WordPress relay can no longer submit leads. Reconnect '
              'restores the client — rotate the secret afterwards.'),
            kind='warning'))

    def action_reconnect(self):
        self.ensure_one()
        self._check_operator()
        client = self.oauth_client_id.sudo()
        if not client:
            raise ValidationError(_('There are no credentials to reconnect — '
                                    'use Get credentials instead.'))
        if not client.active:
            client.active = True
        self.message_post(body=Markup('<p>%s</p>') % _(
            'Website reconnected by %(user)s. Rotate the secret unless the '
            'website still holds the previous one.', user=self.env.user.name))
        return self._with_reload(self._notify(
            _('Website reconnected'),
            _('Rotate the secret unless the website still holds the previous '
              'one.')))

    # ==================================================================
    # Helpers
    # ==================================================================
    def _check_operator(self):
        """Guard by group, then let the body run through `sudo()`.

        The header buttons are group-gated in the arch, but a view attribute
        is decoration: this is the check a direct RPC has to pass.
        """
        if self.env.su or any(self.env.user.has_group(group)
                              for group in OPERATOR_GROUPS):
            return
        raise AccessError(_(
            'Only a system administrator, a CRM manager or a user '
            'administrator may operate the website connector.'))

    def _with_reload(self, action):
        """Re-open this record behind the notification.

        `state` is a non-stored compute over the OAuth client, so an action
        that only returns a notification leaves the header and the status bar
        showing the state the record was in BEFORE the button ran — found by
        driving Disconnect and watching the buttons not move. The web client's
        `display_notification` handler returns `params.next` as its follow-up
        action (web/static/src/webclient/actions/action_service.js), and a
        client-side act_window keeps the sticky notification on screen, which
        is what the show-once secret depends on.
        """
        self.ensure_one()
        if isinstance(action, dict) and isinstance(action.get('params'), dict):
            action['params']['next'] = {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'views': [(False, 'form')],
                'target': 'current',
            }
        return action

    @staticmethod
    def _notify(title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message,
                       'type': kind, 'sticky': True},
        }

    @staticmethod
    def _pretty_json(raw):
        """Pretty-print a JSON parameter for the form.

        A value that does NOT parse is shown VERBATIM rather than swallowed:
        `web.lead.service._json_param` degrades a broken map to `{}` so
        capture never breaks (:211-227), which means the screen is the only
        place the breakage can surface.
        """
        raw = (raw or '').strip()
        if not raw:
            return '{}'
        try:
            return json.dumps(json.loads(raw), indent=2, ensure_ascii=False,
                              sort_keys=True)
        except (ValueError, TypeError):
            return raw

    @api.model
    def _parse_city_map(self, text, label):
        """Text → a validated `{key: "HN"|"HCM"}` dict, or ValidationError.

        Validation lives HERE rather than in an `@api.constrains` because the
        two map fields are non-stored computes and `@api.constrains` never
        fires for those — the inverse is the only hook a bad value passes
        through.
        """
        text = (text or '').strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            raise ValidationError(_(
                'The %s is not valid JSON. Expected an object such as '
                '{"15838": "HN", "15670": "HCM"}.', label))
        if not isinstance(parsed, dict):
            raise ValidationError(_(
                'The %s must be a JSON object, not a list or a plain value.',
                label))
        cleaned = {}
        for raw_key, raw_value in parsed.items():
            key = str(raw_key).strip()
            if not key:
                raise ValidationError(_(
                    'The %s has an entry with an empty key.', label))
            value = raw_value.strip().upper() \
                if isinstance(raw_value, str) else ''
            if value not in VALID_CITY_KEYS:
                raise ValidationError(_(
                    'The %(label)s entry "%(key)s" maps to "%(value)s", which '
                    'is not a city. Use "HN" for Hà Nội or "HCM" for Hồ Chí '
                    'Minh.', label=label, key=key, value=str(raw_value)))
            cleaned[key] = value
        return cleaned

    @staticmethod
    def _param_is_true(raw):
        """The SAME falsy set the cron reads with — imported, not retyped, so
        the screen can never disagree with `_cron_heartbeat` about what
        'off' means."""
        return str(raw or '').strip().lower() not in _FALSY_PARAM

    def _param_user(self, raw):
        Users = self.env['res.users'].sudo()
        try:
            user = Users.browse(int(str(raw or '').strip())).exists()
        except (TypeError, ValueError):
            return Users.browse()
        return user if user and user.active else Users.browse()
