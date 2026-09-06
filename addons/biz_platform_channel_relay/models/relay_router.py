# -*- coding: utf-8 -*-
"""The routing decision, as model code so a plain test can drive it.

The controller above this is a shell: it reads the raw bytes, checks Meta's
signature and hands the verified batch here (the same posture the OAuth
callback already uses — logic in a model, three lines in the route, ledger
§5.32). Everything below runs only on a batch Meta really signed.

Nothing from a payload — no phone number, no wa_id, no page id, no text — may
reach a log line, an audit detail or a stored error. Short names, channels and
counts, and nothing else.
"""
import hashlib
import hmac
import json
import logging

from odoo import api, fields, models

from odoo.addons.health_care_command_channels.services.redact import redact

from ..services import relay

_logger = logging.getLogger(__name__)


class ChannelRelayRouter(models.AbstractModel):
    _name = 'channel.relay.router'
    _description = 'Channel relay router'

    # ------------------------------------------------------------------
    # The one entry point
    # ------------------------------------------------------------------
    @api.model
    def _route_meta(self, channel, payload):
        """Split one verified Meta batch and deliver each share.

        Returns ``{'local', 'forwarded', 'queued', 'unknown'}`` for the
        caller's single log line. NEVER raises: the route answers Meta 200 from
        the moment the signature checked out, whatever happens in here.
        """
        counts = {'local': 0, 'forwarded': 0, 'queued': 0, 'unknown': 0}
        try:
            self._route(channel, payload, counts)
        except Exception:  # noqa: BLE001 — 200 after verification, always
            _logger.exception('channel relay: routing failed (%s)', channel)
        return counts

    # ------------------------------------------------------------------
    def _classify(self, channel, resource_ids):
        """resource id -> (kind, slug, owner). The platform's own clinic first.

        The platform is a clinic too, so a Page connected HERE is served here
        and never forwarded. Everything else is looked up in the route table,
        and anything left over is an unknown contact.
        """
        Connection = self.env['care.channel.connection']
        Route = self.env['channel.relay.route']
        mapping = {}
        for resource_id in resource_ids:
            connection = Connection._find_for_resource(channel, resource_id)
            if connection:
                mapping[resource_id] = (relay.LOCAL, None, connection)
                continue
            tenant = Route._find(channel, resource_id)
            if tenant:
                mapping[resource_id] = (relay.TENANT, tenant.slug, tenant)
            else:
                mapping[resource_id] = (relay.UNKNOWN, None, None)
        return mapping

    def _route(self, channel, payload, counts):
        Message = self.env['care.channel.message']
        resource_ids = Message._meta_resource_ids(channel, payload)
        if not resource_ids:
            return counts

        mapping = self._classify(channel, resource_ids)
        if any(kind == relay.UNKNOWN for kind, _s, _o in mapping.values()):
            # A Page nobody here recognises is the ordinary shape of "a
            # customer connected something a minute ago". Re-read the route
            # table once — throttled, routes only, never a registry — and look
            # again before calling it unknown.
            self.env['channel.relay.tenant']._maybe_resync(
                reason='unknown resource')
            mapping = self._classify(channel, resource_ids)

        buckets = relay.split_payload(
            channel, payload,
            lambda rid: mapping.get(rid, (relay.UNKNOWN, None, None))[:2])

        # THE CUSTOMERS FIRST, AND EACH BUCKET IN ITS OWN SAVEPOINT.
        # These three do very different work and only one of them is the
        # platform's own business. If the local ingest raised — and it reaches
        # a long way into this system's clinical spine — every OTHER clinic's
        # messages in the same batch would be lost, unqueued, with Meta already
        # answered 200 and no redelivery coming. Worse, a database-level error
        # poisons the cursor, so the queue write that was meant to save them
        # would fail too (ledger §5.55). Forwarding is therefore done first,
        # and each bucket is isolated so one can never take another down.
        for name, run in (
                ('forward', lambda: self._forward_tenants(
                    channel, mapping, buckets.get('tenants') or {}, counts)),
                ('local', lambda: self._deliver_local(
                    channel, mapping, buckets.get(relay.LOCAL), counts)),
                ('unknown', lambda: self._capture_unknown(
                    channel, mapping, buckets.get(relay.UNKNOWN), counts))):
            try:
                with self.env.cr.savepoint():
                    run()
            except Exception:  # noqa: BLE001 — one bucket, never the batch
                _logger.exception('channel relay: the %s share of a %s batch '
                                  'could not be handled', name, channel)
        return counts

    # ------------------------------------------------------------------
    def _deliver_local(self, channel, mapping, sub, counts):
        """Ingest the platform's own share, and ONLY its own share.

        Never the whole batch: the ingest path captures the payload it could
        not use, and handing it everything would copy other clinics' messages
        into this system's unrouted queue.
        """
        if not sub:
            return
        Message = self.env['care.channel.message']
        seen = set()
        for kind, _slug, owner in mapping.values():
            if kind != relay.LOCAL or not owner or owner.id in seen:
                continue
            seen.add(owner.id)
            Message._dispatch_connection(owner, sub)
            counts['local'] += 1

    def _capture_unknown(self, channel, mapping, sub, counts):
        if not sub:
            return
        Message = self.env['care.channel.message']
        dump = Message._dump(sub)
        Capture = self.env['care.contact.capture']
        for resource_id, (kind, _slug, _owner) in mapping.items():
            if kind != relay.UNKNOWN:
                continue
            Capture._capture('unknown_resource', channel,
                             resource_external_id=resource_id, raw=dump)
            counts['unknown'] += 1

    def _forward_tenants(self, channel, mapping, tenant_subs, counts):
        if not tenant_subs:
            return
        secret = self._app_secret()
        if not secret:
            # Unreachable in practice — the signature check upstream needs the
            # same secret — but a forward we cannot sign is one the customer
            # would refuse, so it is not sent and not queued.
            _logger.warning('channel relay: no platform secret to re-sign '
                            'with; %s customers not forwarded',
                            len(tenant_subs))
            return
        owners = {slug: owner for kind, slug, owner in mapping.values()
                  if kind == relay.TENANT and slug}
        Delivery = self.env['channel.relay.delivery']
        for slug, sub in tenant_subs.items():
            tenant = owners.get(slug)
            if not tenant:
                continue
            body = json.dumps(sub, separators=(',', ':')).encode('utf-8')
            signature = 'sha256=' + hmac.new(
                secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
            entry_count = len(sub.get('entry') or [])
            try:
                relay.forward(self.env, tenant, channel, body, signature)
            except Exception as exc:  # noqa: BLE001 — every failure is a queue
                Delivery._queue(tenant, channel, body, signature, entry_count,
                                str(exc))
                counts['queued'] += 1
                self.env['care.channel.audit']._log(
                    'relay_failed', channel=channel,
                    detail='%s %s' % (slug, redact(str(exc)) or ''))
                continue
            counts['forwarded'] += 1
            tenant.sudo().write({'last_forward_at': fields.Datetime.now()})
            self.env['care.channel.audit']._log(
                'relay_forwarded', channel=channel,
                detail='%s %s %s entries' % (slug, channel, entry_count))

    def _app_secret(self):
        app = self.env['channel.platform.app'].sudo()._get_for_provider('meta')
        if not app:
            return ''
        try:
            return app._get_secret() or ''
        except Exception:  # noqa: BLE001 — a corrupt secret signs nothing
            _logger.warning('channel relay: the platform Meta secret could '
                            'not be read')
            return ''
