# -*- coding: utf-8 -*-
"""The customers this relay serves, and the two things it keeps in step.

One row per customer system the platform relays for. It is a CACHE of two
facts, both re-derived from the customers' own systems on a ten-minute cycle:

* **who owns which Page and which WhatsApp number** — the route table the
  webhook consults on every event, and the only thing standing between a
  clinic's messages and another clinic's inbox;
* **whether that customer holds the same Meta application as the platform** —
  because a customer whose copy of the secret is stale answers our forward with
  a 403, which is a queued delivery rather than a lost message, but still a
  channel that does not work until it is fixed.

Reads from a customer's system go through ``biz.tenants._pg_cursor`` (read
only, autocommit) and writes through ``biz.tenants._tenant_env`` (rail R5) —
never ``odoo.sql_db`` directly, and never from a public route.
"""
import json
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.health_care_command_channels.services import channel_crypto
from odoo.addons.health_care_command_channels.services.redact import redact

_logger = logging.getLogger(__name__)

# Route and push only for a customer whose system is actually serving people.
# A paused, closing or half-provisioned system must not receive a secret and
# must not be routed to.
SERVING_STATES = ('live', 'trial')

# A short name is the first label of a hostname and the name of a database.
SLUG_RE = re.compile(r'^[a-z0-9]{1,40}$')

# The customer-side parameter that sends their Messenger sign-in home to the
# platform's single callback address.
REDIRECT_BASE_PARAM = 'channel_hub.oauth_redirect_base'

# The throttle behind the "an unknown Page arrived — read the customers again"
# path. A webhook must never be able to make the platform open every customer's
# database on demand.
RESYNC_PARAM = 'channel_relay.last_resync_at'
RESYNC_MIN_SECONDS = 60

# What the platform stamps on the row it writes into a customer's system, so an
# operator opening that screen knows it is not theirs to edit.
PUSHED_NOTE = 'Pushed by the platform'


class ChannelRelayTenant(models.Model):
    _name = 'channel.relay.tenant'
    _description = 'Customer served by the channel relay'
    _order = 'slug'

    slug = fields.Char(
        string='Short name', required=True, index=True,
        help='The first word of this customer\'s web address, and the name of '
             'their system on this machine.')
    name = fields.Char(string='Customer')
    active = fields.Boolean(default=True)
    host = fields.Char(
        string='Address', compute='_compute_host',
        help='The address this customer\'s messages are forwarded to.')

    credentials_pushed_at = fields.Datetime(
        string='Application sent on', readonly=True)
    pushed_secret_hint = fields.Char(
        string='Secret sent', readonly=True,
        help='The last four characters of the secret this customer was given '
             '— enough to tell two secrets apart, useless on its own.')
    # DEVIATION D1 (see the phase report): the handover's field list does not
    # name this one, but "in step" is defined as *also* holding the same extra
    # configuration, and that cannot be answered without remembering which keys
    # were sent. Without it, adding the sign-in configuration ids to the
    # platform application would leave every customer reading "in step" while
    # holding an application that cannot sign anybody in.
    pushed_extra_keys = fields.Char(
        string='Settings sent', readonly=True,
        help='Which pieces of the Meta application configuration this customer '
             'was given.')
    in_step = fields.Boolean(
        string='In step', compute='_compute_in_step',
        help='This customer holds the same Meta application id and secret as '
             'the platform. When it is empty, press "Send the Meta '
             'application to every customer now".')

    route_ids = fields.One2many(
        'channel.relay.route', 'tenant_id', string='Pages and numbers')
    route_count = fields.Integer(
        string='Pages and numbers', compute='_compute_counts')
    pending_count = fields.Integer(
        string='Waiting to retry', compute='_compute_counts')
    last_forward_at = fields.Datetime(
        string='Last message forwarded', readonly=True)
    last_error = fields.Char(string='Last problem', readonly=True)

    # ------------------------------------------------------------------
    # DB constraints (ledger §5.1 — _sql_constraints are not materialised)
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS channel_relay_tenant_slug_uniq
            ON channel_relay_tenant (slug)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('slug')
    def _compute_host(self):
        service = self.env['biz.tenants']
        for rec in self:
            rec.host = service._tenant_host(rec.slug) if rec.slug else ''

    @api.depends('route_ids')
    def _compute_counts(self):
        Route = self.env['channel.relay.route'].sudo()
        Delivery = self.env['channel.relay.delivery'].sudo()
        routes = dict(Route._read_group(
            [('tenant_id', 'in', self.ids)], ['tenant_id'], ['__count']))
        pending = dict(Delivery._read_group(
            [('tenant_id', 'in', self.ids), ('state', '=', 'pending')],
            ['tenant_id'], ['__count']))
        for rec in self:
            rec.route_count = routes.get(rec, 0)
            rec.pending_count = pending.get(rec, 0)

    @api.depends('pushed_secret_hint', 'pushed_extra_keys')
    def _compute_in_step(self):
        app = self._master_app()
        hint = app.secret_hint if app else ''
        wanted = self._extra_keys(app.extra_json if app else '')
        for rec in self:
            held = {k for k in (rec.pushed_extra_keys or '').split(',') if k}
            rec.in_step = bool(
                hint and rec.pushed_secret_hint == hint and wanted <= held)

    # ------------------------------------------------------------------
    # The platform's own Meta application
    # ------------------------------------------------------------------
    @api.model
    def _master_app(self):
        return self.env['channel.platform.app'].sudo()._get_for_provider('meta')

    @staticmethod
    def _extra_keys(raw):
        try:
            parsed = json.loads(raw or '{}')
        except ValueError:
            return set()
        return set(parsed) if isinstance(parsed, dict) else set()

    @staticmethod
    def _hint_for(secret):
        """The hint exactly as ``action_set_secret`` computes it."""
        return '••••' + (secret[-4:] if len(secret or '') >= 8 else '')

    # ------------------------------------------------------------------
    # The sign-in allowlist (safety rail 3)
    # ------------------------------------------------------------------
    @api.model
    def _slug_from_state(self, state):
        """Which customer a sign-in ticket belongs to, or None.

        The ``<slug>~`` prefix is ROUTING, not trust: the answer is only ever a
        short name that names an ACTIVE row of this table. The regex is defence
        in depth; the table is the gate. An open redirect on an OAuth callback
        is a phishing primitive, so nothing else may ever be redirected to.
        """
        if not state or not isinstance(state, str) or '~' not in state:
            return None
        slug = state.split('~', 1)[0]
        if not SLUG_RE.match(slug):
            return None
        if not self.sudo().search_count(
                [('slug', '=', slug), ('active', '=', True)]):
            return None
        return slug

    def _tenant_url(self):
        self.ensure_one()
        return self.env['biz.tenants']._tenant_url(self.slug)

    # ==================================================================
    # Reconcile — the route table and the credentials push
    # ==================================================================
    @api.model
    def _reconcile(self, push_credentials=True):
        """Bring the customer list, the route table and the secrets in step.

        Returns a small counter dict for the operator's notification and the
        cron's log line. Never raises for ONE customer's failure: the row keeps
        the reason and the run carries on with the next.
        """
        counts = {'customers': 0, 'routes': 0, 'pushed': 0, 'problems': 0}
        if 'biz.tenant' not in self.env:
            # Only the platform's own system has the customer list. Anywhere
            # else this module has no work to do rather than an error to raise.
            _logger.info('channel relay: no customer list on this system')
            return counts
        service = self.env['biz.tenants']
        rows = self._sync_customers()
        counts['customers'] = len(rows)
        counts['routes'] = self._sync_routes(service, rows, counts)
        if push_credentials:
            counts['pushed'] = self._push_credentials(service, rows, counts)
        _logger.info('channel relay: reconcile %s', counts)
        return counts

    def _sync_customers(self):
        """Create/reactivate a row per serving customer, archive the rest."""
        Tenant = self.env['biz.tenant'].sudo()
        serving = {}
        for tenant in Tenant.search([('state', 'in', list(SERVING_STATES))]):
            slug = (tenant.slug or '').strip()
            if slug and SLUG_RE.match(slug):
                serving[slug] = tenant
        existing = self.sudo().with_context(active_test=False).search([])
        by_slug = {row.slug: row for row in existing}
        live = self.sudo().browse()
        for slug, tenant in sorted(serving.items()):
            row = by_slug.get(slug)
            if row:
                vals = {}
                if not row.active:
                    vals['active'] = True
                if (row.name or '') != (tenant.name or ''):
                    vals['name'] = tenant.name
                if vals:
                    row.write(vals)
            else:
                row = self.sudo().create({'slug': slug, 'name': tenant.name})
            live |= row
        stale = existing.filtered(
            lambda r: r.active and r.slug not in serving)
        if stale:
            stale.write({'active': False})
        return live

    def _sync_routes(self, service, rows, counts):
        """Re-read who owns which Page and which WhatsApp number.

        READ ONLY, one autocommit cursor per customer. A customer whose system
        is behind on releases (no connection table yet) is SKIPPED with a
        warning — never a failure that takes the customers after it down.
        """
        Route = self.env['channel.relay.route'].sudo()
        claimed = {}
        total = 0
        for row in rows:
            try:
                pairs = self._read_resources(service, row.slug)
            except Exception as exc:  # noqa: BLE001 — one customer, not the run
                _logger.warning('channel relay: could not read %s: %s',
                                row.slug, type(exc).__name__)
                row.write({'last_error': redact(
                    'could not read this customer: %s' % exc)})
                counts['problems'] += 1
                continue
            if pairs is None:
                _logger.warning('channel relay: %s has no channel connections '
                                'table yet — skipped', row.slug)
                continue
            keep = set()
            for channel, resource_id in pairs:
                key = (channel, resource_id)
                owner = claimed.get(key)
                if owner and owner != row.slug:
                    # Never let routing become a coin flip: the FIRST customer
                    # seen keeps the Page, the second is told, loudly.
                    message = ('Page/number %s is connected by two customers: '
                               '%s, %s' % (resource_id, owner, row.slug))
                    row.write({'last_error': redact(message)})
                    self.env['care.channel.audit']._log(
                        'relay_failed', channel=channel, detail=message)
                    counts['problems'] += 1
                    continue
                claimed[key] = row.slug
                keep.add(key)
                Route._upsert(row, channel, resource_id)
                total += 1
            gone = Route.search([('tenant_id', '=', row.id)]).filtered(
                lambda r: (r.channel, r.resource_external_id) not in keep)
            if gone:
                gone.unlink()
        return total

    def _read_resources(self, service, slug):
        """[(channel, resource id)] a customer owns, or None if it cannot say."""
        with service._pg_cursor(slug) as cr:
            cr.execute("SELECT to_regclass('public.care_channel_connection')")
            row = cr.fetchone()
            if not row or not row[0]:
                return None
            cr.execute("""
                SELECT channel, resource_external_id
                  FROM care_channel_connection
                 WHERE active
                   AND resource_external_id IS NOT NULL
                   AND channel IN ('whatsapp', 'fb')
                 ORDER BY channel, resource_external_id
            """)
            return [(r[0], str(r[1])) for r in cr.fetchall() if r[1]]

    def _push_credentials(self, service, rows, counts):
        """Give every serving customer the platform's Meta application.

        The secret is encrypted INSIDE the customer's own environment, because
        this box sets no shared key and every database therefore derives its own
        from its own ``database.secret`` (ledger §5.172). A token minted here
        would be undecryptable there.
        """
        app = self._master_app()
        if not app or not app.client_id:
            _logger.warning('channel relay: no Meta application on the '
                            'platform — nothing to send')
            return 0
        try:
            secret = app._get_secret()
        except Exception:  # noqa: BLE001 — a corrupt secret must not be sent
            _logger.warning('channel relay: the platform Meta secret could '
                            'not be read — nothing sent')
            return 0
        if not secret:
            _logger.warning('channel relay: the platform Meta application has '
                            'no secret yet — nothing sent')
            return 0
        client_id = app.client_id
        extra_json = app.extra_json or '{}'
        hint = self._hint_for(secret)
        keys = ','.join(sorted(self._extra_keys(extra_json)))
        platform_url = service._platform_url()
        pushed = 0
        for row in rows:
            try:
                changed = self._push_one(service, row, client_id, extra_json,
                                         secret, hint, platform_url)
            except Exception as exc:  # noqa: BLE001 — one customer, not the run
                _logger.exception('channel relay: sending the Meta '
                                  'application to %s failed', row.slug)
                row.write({'last_error': redact(str(exc))})
                self.env['care.channel.audit']._log(
                    'relay_failed',
                    detail='%s: could not receive the platform application'
                           % row.slug)
                counts['problems'] += 1
                continue
            row.write({
                'credentials_pushed_at': fields.Datetime.now(),
                'pushed_secret_hint': hint,
                'pushed_extra_keys': keys,
                'last_error': False,
            })
            if changed:
                pushed += 1
                self.env['care.channel.audit']._log(
                    'relay_pushed',
                    detail='%s received the platform Meta application'
                           % row.slug)
        return pushed

    def _push_one(self, service, row, client_id, extra_json, secret, hint,
                  platform_url):
        """Write the application into ONE customer's system. True if it moved."""
        with service._tenant_env(row.slug) as tenv:
            App = tenv['channel.platform.app'].sudo()
            app = App._get_for_provider('meta')
            if not app:
                app = App.create({'provider': 'meta'})
            same = (app.client_id == client_id
                    and (app.extra_json or '') == extra_json
                    and app.secret_hint == hint)
            if not same:
                # NOT action_set_secret: it is gated on the CALLING user's
                # groups and returns a client notification. The two writes it
                # makes are exactly these two, under sudo, with the secret
                # encrypted in the environment it is being stored in.
                app.write({
                    'client_id': client_id,
                    'extra_json': extra_json,
                    'client_secret_enc': channel_crypto.encrypt(tenv, secret),
                    'secret_hint': hint,
                    'environment_note': PUSHED_NOTE,
                })
                tenv['care.channel.audit']._log(
                    'secret_rotated', detail='pushed by the platform')
            icp = tenv['ir.config_parameter'].sudo()
            if platform_url and icp.get_param(REDIRECT_BASE_PARAM) != platform_url:
                icp.set_param(REDIRECT_BASE_PARAM, platform_url)
            return not same

    # ------------------------------------------------------------------
    # The throttled resync a webhook is allowed to ask for
    # ------------------------------------------------------------------
    @api.model
    def _maybe_resync(self, reason=''):
        """Re-read the route table, at most once a minute. Never raises.

        A public route must not be able to make the platform open every
        customer's database on demand, so this is throttled on a parameter and
        reads routes only — the credentials push stays with the cron and the
        operator's button.
        """
        icp = self.env['ir.config_parameter'].sudo()
        now = fields.Datetime.now()
        raw = icp.get_param(RESYNC_PARAM)
        if raw:
            try:
                last = fields.Datetime.to_datetime(raw)
            except (TypeError, ValueError):
                last = None
            if last and (now - last) < timedelta(seconds=RESYNC_MIN_SECONDS):
                return False
        icp.set_param(RESYNC_PARAM, fields.Datetime.to_string(now))
        try:
            with self.env.cr.savepoint():
                self._reconcile(push_credentials=False)
        except Exception:  # noqa: BLE001 — a webhook must survive this
            _logger.exception('channel relay: resync (%s) failed', reason)
            return False
        return True

    # ------------------------------------------------------------------
    # Crons + the operator's buttons
    # ------------------------------------------------------------------
    @api.model
    def _cron_reconcile(self):
        return self._reconcile(push_credentials=True)

    def action_push_credentials(self):
        """Header button: send the Meta application to every customer now."""
        counts = self.sudo()._reconcile(push_credentials=True)
        return self._notify(
            _('The Meta application was sent'),
            _('%(customers)s customers, %(pushed)s updated, '
              '%(problems)s problems.', **counts))

    def action_sync_routes(self):
        """Header button: re-read who owns which Page and number."""
        counts = self.sudo()._reconcile(push_credentials=False)
        return self._notify(
            _('Pages and numbers re-read'),
            _('%(customers)s customers, %(routes)s pages and numbers, '
              '%(problems)s problems.', **counts))

    @staticmethod
    def _notify(title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message,
                       'type': 'success', 'sticky': False},
        }
