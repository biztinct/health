# Part of biz_errors — the branded breakdown screen.
# License LGPL-3.
"""Plain access-refused messages (UAT round 6, item 9a).

Core builds the refusal with the technical model name ("(health.fieldservice.
order)") and a joke about top-secret records and cookies. A person using the
product gets one plain sentence naming the kind of record instead; the full
technical message is still built — and logged — so support can read it.
System administrators keep the core text.
"""
import logging

from odoo import _, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

ADMIN_GROUP = 'base.group_system'


def _plain_access_error(env, model, operation, technical):
    """The AccessError a non-admin sees for `operation` on `model`."""
    if env.su or env.user.has_group(ADMIN_GROUP):
        return technical
    _logger.info('Access refused (plain message shown), uid %s, model %s, '
                 'operation %s: %s', env.uid, model, operation, technical)
    # `self` carrying the user's language is what `_` reads (as core does).
    self = env['ir.model'].with_context(lang=env.user.lang or env.lang)
    name = (self._get(model).name or '').strip()
    thing = name.lower() if name and 'odoo' not in name.lower() else _('record')
    messages = {
        'read': _('You do not have access to this %(thing)s. '
                  'Ask your administrator if you need it.', thing=thing),
        'write': _('You cannot change this %(thing)s. '
                   'Ask your administrator if you need it.', thing=thing),
        'create': _('You cannot create a new %(thing)s. '
                    'Ask your administrator if you need it.', thing=thing),
        'unlink': _('You cannot delete this %(thing)s. '
                    'Ask your administrator if you need it.', thing=thing),
    }
    plain = AccessError(messages.get(operation, messages['read']))
    if getattr(technical, 'context', None):
        plain.context = technical.context
    return plain


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _make_access_error(self, operation, records):
        technical = super()._make_access_error(operation, records)
        return _plain_access_error(self.env, records._name, operation, technical)


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    def _make_access_error(self, model, mode):
        technical = super()._make_access_error(model, mode)
        return _plain_access_error(self.env, model, mode, technical)
