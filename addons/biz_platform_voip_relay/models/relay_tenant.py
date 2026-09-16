# -*- coding: utf-8 -*-
"""The customers this relay serves, and the two things it keeps in step.

One row per customer system the platform relays phone traffic for. It is a
CACHE of one fact and the pusher of another, both re-derived on a ten-minute
cycle:

* **which call-back addresses a customer's system answers to** — the routing
  table the call-back address consults on every delivery, and the only thing
  standing between one clinic's patient calls and another clinic's screens.
  READ from the customer's own system, never typed here;
* **that the customer's system should publish the PLATFORM's address to the
  phone supplier rather than its own** — written into the customer's system as
  a setting, so that when an operator there presses "Register the call-back
  address", the address that goes to the supplier is this platform's.

Reads from a customer's system go through ``biz.tenants._pg_cursor`` (read only,
autocommit) and writes through ``biz.tenants._tenant_env`` (rail R5) — never
``odoo.sql_db`` directly, and never from a public route.

Nothing in here ever reads, stores or transports a customer's call-back token.
The relay works entirely on the public half of the address; see
``services/relay.py`` for why that is the whole security design.
"""
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Relay only for a customer whose system is actually serving people. A paused,
# closing or half-provisioned system must not be routed to.
SERVING_STATES = ('live', 'trial')

# A short name is the first label of a hostname and the name of a database.
SLUG_RE = re.compile(r'^[a-z0-9]{1,40}$')

# The customer-side setting that makes their system publish the platform's
# call-back address to the phone supplier instead of their own.
CALLBACK_BASE_PARAM = 'voip24h.callback_base'

# The throttle behind the "an address I do not recognise arrived — read the
# customers again" path. A public route must never be able to make the platform
# open every customer's database on demand.
RESYNC_PARAM = 'voip_relay.last_resync_at'
RESYNC_MIN_SECONDS = 60


class VoipRelayTenant(models.Model):
    _name = 'voip.relay.tenant'
    _description = 'Customer served by the phone relay'
    _order = 'slug'

    slug = fields.Char(
        string='Short name', required=True, index=True,
        help="The first word of this customer's web address, and the name of "
             'their system on this machine.')
    name = fields.Char(string='Customer')
    active = fields.Boolean(default=True)
    host = fields.Char(
        string='Address', compute='_compute_host',
        help="The address this customer's calls are handed to.")

    route_ids = fields.One2many(
        'voip.relay.route', 'tenant_id', string='Addresses and hotlines')
    receiver_count = fields.Integer(
        string='Call-back addresses', compute='_compute_counts')
    hotline_count = fields.Integer(
        string='Hotlines', compute='_compute_counts')
    pending_count = fields.Integer(
        string='Waiting to retry', compute='_compute_counts')

    callback_base_pushed_at = fields.Datetime(
        string='Address published on', readonly=True,
        help='When this customer was last told to give the phone supplier this '
             "platform's address instead of their own.")
    in_step = fields.Boolean(
        string='In step', compute='_compute_in_step',
        search='_search_in_step',
        help='This customer knows to point their phone supplier at this '
             'platform, and this platform knows at least one address they '
             'answer to.')

    last_forward_at = fields.Datetime(
        string='Last call handed over', readonly=True)
    last_error = fields.Char(string='Last problem', readonly=True)

    # ------------------------------------------------------------------
    # DB constraints (ledger §5.1)
    # ------------------------------------------------------------------
    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS voip_relay_tenant_slug_uniq
            ON voip_relay_tenant (slug)
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('slug')
    def _compute_host(self):
        service = self.env['biz.tenants']
        for rec in self:
            rec.host = service._tenant_host(rec.slug) if rec.slug else ''

    @api.depends('route_ids', 'route_ids.kind')
    def _compute_counts(self):
        Route = self.env['voip.relay.route'].sudo()
        Delivery = self.env['voip.relay.delivery'].sudo()
        receivers = dict(Route._read_group(
            [('tenant_id', 'in', self.ids), ('kind', '=', 'receiver')],
            ['tenant_id'], ['__count']))
        hotlines = dict(Route._read_group(
            [('tenant_id', 'in', self.ids), ('kind', '=', 'hotline')],
            ['tenant_id'], ['__count']))
        pending = dict(Delivery._read_group(
            [('tenant_id', 'in', self.ids), ('state', '=', 'pending')],
            ['tenant_id'], ['__count']))
        for rec in self:
            rec.receiver_count = receivers.get(rec, 0)
            rec.hotline_count = hotlines.get(rec, 0)
            rec.pending_count = pending.get(rec, 0)

    @api.depends('callback_base_pushed_at', 'route_ids', 'route_ids.kind')
    def _compute_in_step(self):
        for rec in self:
            rec.in_step = bool(rec.callback_base_pushed_at
                               and rec.receiver_count)

    def _search_in_step(self, operator, value):
        """"Not set up yet" is the first thing an operator looks for.

        Both halves of it are worked out rather than stored — one of them
        counts rows in another table — so this walks the customers and hands
        back the answer as a list of ids. A platform holds one row per clinic,
        so that is a handful of records, not a table scan.
        """
        if operator not in ('=', '!='):
            raise ValueError('Unsupported operator %s for "in step"' % operator)
        rows = self.sudo().with_context(active_test=False).search([])
        ids = rows.filtered('in_step').ids
        wanted = (operator == '=') == bool(value)
        return [('id', 'in' if wanted else 'not in', ids)]

    # ------------------------------------------------------------------
    @api.model
    def _own_slug(self):
        """This system's own name. A customer may never be called it."""
        return (self.env.cr.dbname or '').strip()

    def _tenant_url(self):
        self.ensure_one()
        return self.env['biz.tenants']._tenant_url(self.slug)

    # ==================================================================
    # Reconcile — the routing table and the published address
    # ==================================================================
    @api.model
    def _reconcile(self, push_settings=True):
        """Bring the customer list, the routing table and the published
        call-back address in step.

        Returns a small counter dict for the operator's notification and the
        cron's log line. Never raises for ONE customer's failure: the row keeps
        the reason and the run carries on with the next.
        """
        counts = {'customers': 0, 'addresses': 0, 'pushed': 0, 'problems': 0}
        if 'biz.tenant' not in self.env:
            # Only the platform's own system has the customer list. Anywhere
            # else this module has no work to do rather than an error to raise.
            _logger.info('voip relay: no customer list on this system')
            return counts
        service = self.env['biz.tenants']
        rows = self._sync_customers()
        counts['customers'] = len(rows)
        counts['addresses'] = self._sync_receivers(service, rows, counts)
        if push_settings:
            counts['pushed'] = self._push_callback_base(service, rows, counts)
        _logger.info('voip relay: reconcile %s', counts)
        return counts

    def _sync_customers(self):
        """Create/reactivate a row per serving customer, archive the rest."""
        Tenant = self.env['biz.tenant'].sudo()
        # The platform never relays to itself. A customer row whose short name
        # is this database would make the relay hand a call straight back into
        # the route it arrived on — an infinite loop across the loopback
        # interface. It should never exist, but a mis-typed row in the cockpit
        # is one keystroke and this is one line.
        own = self._own_slug()
        serving = {}
        for tenant in Tenant.search([('state', 'in', list(SERVING_STATES))]):
            slug = (tenant.slug or '').strip()
            if slug and slug == own:
                _logger.warning('voip relay: %r is this platform itself — not '
                                'relayed for', slug)
                continue
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
        stale = existing.filtered(lambda r: r.active and r.slug not in serving)
        if stale:
            stale.write({'active': False})
        return live

    def _sync_receivers(self, service, rows, counts):
        """Re-read which call-back addresses each customer's system answers to.

        READ ONLY, one autocommit cursor per customer. A customer whose system
        is behind on releases (no phone tables yet) is SKIPPED with a warning —
        never a failure that takes the customers after it down.

        Hotline rows are an operator's to keep; only ``receiver`` rows are
        re-derived here, and only ``receiver`` rows are removed when they are
        no longer found.
        """
        Route = self.env['voip.relay.route'].sudo()
        claimed = {}
        total = 0
        for row in rows:
            try:
                receivers = self._read_receivers(service, row.slug)
            except Exception as exc:  # noqa: BLE001 — one customer, not the run
                _logger.warning('voip relay: could not read %s: %s',
                                row.slug, type(exc).__name__)
                row.write({'last_error':
                           'could not read this customer: %s'
                           % type(exc).__name__})
                counts['problems'] += 1
                continue
            if receivers is None:
                _logger.warning('voip relay: %s has no phone settings table '
                                'yet — skipped', row.slug)
                continue
            keep = set()
            for receiver_id in receivers:
                owner = claimed.get(receiver_id)
                if owner and owner != row.slug:
                    # Never let routing become a coin flip: the FIRST customer
                    # seen keeps the address, the second is told, loudly. Two
                    # customers cannot honestly mint the same random address,
                    # so this means one database was copied from another and
                    # the copy has to be re-minted before it is served.
                    message = ('One call-back address is answered by two '
                               'customers: %s, %s' % (owner, row.slug))
                    row.write({'last_error': message})
                    _logger.error('voip relay: %s', message)
                    counts['problems'] += 1
                    continue
                claimed[receiver_id] = row.slug
                keep.add(receiver_id)
                Route._upsert(row, 'receiver', receiver_id)
                total += 1
            gone = Route.search([('tenant_id', '=', row.id),
                                 ('kind', '=', 'receiver')]).filtered(
                lambda r: r.key not in keep)
            if gone:
                gone.unlink()
        return total

    def _read_receivers(self, service, slug):
        """The call-back addresses a customer answers to, or None if it cannot say.

        ONLY ``receiver_id`` is selected. The token columns beside it in that
        table are never read, never transported and never stored here.
        """
        with service._pg_cursor(slug) as cr:
            cr.execute("SELECT to_regclass('public.voip_config')")
            row = cr.fetchone()
            if not row or not row[0]:
                return None
            cr.execute("""
                SELECT receiver_id
                  FROM voip_config
                 WHERE active
                   AND receiver_id IS NOT NULL
                   AND receiver_id <> ''
                 ORDER BY receiver_id
            """)
            return [str(r[0]) for r in cr.fetchall() if r[0]]

    def _push_callback_base(self, service, rows, counts):
        """Tell every serving customer to publish THIS platform's address.

        Without this the customer's own "Register the call-back address" button
        would hand the phone supplier that customer's own address, the supplier
        would call it directly, and this relay would never see the traffic. It
        would still work — but only for as long as the supplier is willing to
        hold a different address per customer, which is the thing this module
        exists to stop needing.
        """
        platform_url = service._platform_url()
        if not platform_url:
            _logger.warning('voip relay: this platform has no address of its '
                            'own configured — nothing published')
            return 0
        pushed = 0
        for row in rows:
            try:
                changed = self._push_one(service, row, platform_url)
            except Exception as exc:  # noqa: BLE001 — one customer, not the run
                _logger.exception('voip relay: publishing the platform address '
                                  'to %s failed', row.slug)
                row.write({'last_error': 'could not publish the platform '
                                         'address: %s' % type(exc).__name__})
                counts['problems'] += 1
                continue
            row.write({'callback_base_pushed_at': fields.Datetime.now(),
                       'last_error': False})
            if changed:
                pushed += 1
        return pushed

    def _push_one(self, service, row, platform_url):
        """Write the setting into ONE customer's system. True if it moved."""
        with service._tenant_env(row.slug) as tenv:
            icp = tenv['ir.config_parameter'].sudo()
            if icp.get_param(CALLBACK_BASE_PARAM) == platform_url:
                return False
            icp.set_param(CALLBACK_BASE_PARAM, platform_url)
            return True

    # ------------------------------------------------------------------
    # The throttled resync a call-back address is allowed to ask for
    # ------------------------------------------------------------------
    @api.model
    def _maybe_resync(self, reason=''):
        """Re-read the routing table, at most once a minute. Never raises.

        A public route must not be able to make the platform open every
        customer's database on demand, so this is throttled on a parameter and
        re-reads addresses only — publishing the platform address stays with
        the cron and the operator's button.
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
                self._reconcile(push_settings=False)
        except Exception:  # noqa: BLE001 — a call-back must survive this
            _logger.exception('voip relay: resync (%s) failed', reason)
            return False
        return True

    # ------------------------------------------------------------------
    # Crons + the operator's buttons
    # ------------------------------------------------------------------
    @api.model
    def _cron_reconcile(self):
        return self._reconcile(push_settings=True)

    def action_sync_now(self):
        """Header button: re-read the customers and publish the address."""
        counts = self.sudo()._reconcile(push_settings=True)
        return self._notify(
            _('The customers were re-read'),
            _('%(customers)s customers, %(addresses)s call-back addresses, '
              '%(problems)s problems.', **counts))

    @staticmethod
    def _notify(title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message,
                       'type': 'success', 'sticky': False},
        }
