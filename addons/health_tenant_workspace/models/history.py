"""Readable channel history, without exposing provider responses or secrets."""
from odoo import SUPERUSER_ID, _, models
from odoo.exceptions import AccessError
from odoo.fields import Domain


class WorkspaceHistory(models.AbstractModel):
    _inherit = 'health.tenant.workspace'

    def _channel_history_labels(self):
        return {
            'connect_start': _('Connection setup started'),
            'callback_ok': _('Connection sign-in completed'),
            'callback_denied': _('Connection sign-in declined'),
            'callback_error': _('Connection sign-in failed'),
            'resource_selected': _('Connection account selected'),
            'webhook_subscribed': _('Incoming updates enabled'),
            'test_ok': _('Connection test passed'),
            'test_fail': _('Connection test failed'),
            'reconnect': _('Reconnection started'),
            'disconnect': _('Connection disconnected'),
            'secret_rotated': _('Connection credentials updated'),
            'refresh_ok': _('Connection access renewed'),
            'refresh_fail': _('Connection access renewal failed'),
            'health_transition': _('Connection status changed'),
            'health_check': _('Connection check recorded'),
            'webhook_ignored': _('Incoming update ignored'),
            'send_failed': _('Message could not be sent'),
            'webhook_failed': _('Incoming update setup failed'),
            'approvals_refreshed': _('Provider permissions checked'),
            'verify_token_generated': _('Connection verification set up'),
            'preflight': _('Connection readiness checked'),
            'webhook_handshake': _('Incoming connection verified'),
            'webhook_probe': _('Unverified connection request received'),
            'golive_invite_sent': _('Connection setup invitation sent'),
            'golive_invite_viewed': _('Connection setup invitation opened'),
            'golive_invite_revoked': _('Connection setup invitation withdrawn'),
            'relay_forwarded': _('Incoming update forwarded to the clinic'),
            'relay_failed': _('Incoming update could not reach the clinic'),
            'relay_routed_signin': _('Connection sign-in directed to the clinic'),
            'relay_pushed': _('Shared connection settings applied'),
            'phone_server_set': _('Phone server settings saved'),
            'phone_extension_saved': _('Phone extension saved'),
            'phone_extension_removed': _('Phone extension removed'),
        }

    def _channel_history_descriptions(self):
        """Use the same translated descriptions for rendering and SQL search."""
        labels = self._channel_history_labels()
        disabled = Domain('event', '=', 'webhook_ignored') & Domain('detail_redacted', '=', 'state disabled')
        failed = Domain('event', '=', 'health_check') & Domain('detail_redacted', '=like', 'failure #%')
        descriptions = [(Domain('event', '=', event) & ~disabled & ~failed, label)
                        for event, label in labels.items()]
        descriptions += [
            (disabled, _('Incoming update ignored because the connection is disabled')),
            (failed, _('Connection check failed')),
            (Domain('event', 'not in', list(labels)), _('Connection activity recorded')),
        ]
        return descriptions

    def _channel_history_channels(self):
        return dict(self.env['care.channel.connection']._fields['channel']._description_selection(self.env))

    def _channel_history_domain(self, query):
        descriptions = self._channel_history_descriptions()
        channels = self._channel_history_channels()
        words = str(query)[:100].casefold().split()
        return Domain.AND([
            Domain.OR([
                *(domain for domain, label in descriptions if word in label.casefold()),
                Domain('channel', 'in', [key for key, label in channels.items() if word in label.casefold()]),
                Domain('connection_id.account_label', 'ilike', word),
                Domain('connection_id.account_label', '=', False) & Domain('connection_id.resource_display_name', 'ilike', word),
            ]) for word in words
        ])

    def _channel_history_summary(self, record):
        # Read only known metadata. Even redacted provider errors can contain
        # payloads, so do not copy detail_redacted into the timeline.
        label = self._channel_history_labels().get(record.event, _('Connection activity recorded'))
        if record.event == 'webhook_ignored' and record.detail_redacted == 'state disabled':
            label = _('Incoming update ignored because the connection is disabled')
        elif record.event == 'health_check' and (record.detail_redacted or '').startswith('failure #'):
            label = _('Connection check failed')
        channel = self._channel_history_channels().get(record.channel, _('Connection'))
        account = ''
        if record.connection_id:
            try:
                record.connection_id.check_access('read')
                account = record.connection_id.account_label or record.connection_id.resource_display_name or ''
            except AccessError:
                pass
        connection = _('%(channel)s (%(account)s)', channel=channel, account=account) if account else channel
        title = _('%(connection)s: %(event)s', connection=connection, event=label)
        user = record.user_id
        if not user or user.id == SUPERUSER_ID:
            actor = _('System')
        elif user == self.env.ref('base.public_user'):
            actor = _('External service')
        else:
            actor = user.name
        return title, actor
