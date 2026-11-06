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


def _record_noun(env, model, records=None):
    """The singular word for one record of `model` on this product, or ''.

    UAT round 11, item 1: the round-6 message used the model's description
    ("this fields", "this zalo oa configuration") — plural or technical for
    most models. Only the record kinds a person here knows by name get a noun;
    everything else gets the neutral sentence. Models a database does not
    have simply never match. `records` (record-rule refusals) narrows the two
    models that hold more than one kind of thing.
    """
    nouns = {
        'health.fieldservice.order': env._('booking'),
        'crm.lead': env._('contact'),
        'sale.order': env._('quote'),
        'account.payment': env._('payment'),
        'health.payment.transaction': env._('payment record'),
        'hr.employee': env._('staff record'),
        'health.clinical.note': env._('clinical note'),
        'health.facility': env._('facility'),
        'health.incident': env._('incident'),
        'res.users': env._('user account'),
    }
    if model in nouns:
        return nouns[model]
    recs = records.sudo() if records is not None and len(records) else None
    if model == 'res.partner' and recs is not None and 'is_patient' in recs._fields \
            and all(recs.mapped('is_patient')):
        return env._('client')
    if model == 'account.move' and recs is not None \
            and set(recs.mapped('move_type')) <= {'out_invoice'}:
        return env._('invoice')
    return ''


def _plain_access_error(env, model, operation, technical, records=None):
    """The AccessError a non-admin sees for `operation` on `model`."""
    if env.su or env.user.has_group(ADMIN_GROUP):
        return technical
    _logger.info('Access refused (plain message shown), uid %s, model %s, '
                 'operation %s: %s', env.uid, model, operation, technical)
    # `self` carrying the user's language is what `_` reads (as core does).
    self = env['ir.model'].with_context(lang=env.user.lang or env.lang)
    thing = _record_noun(self.env, model, records)
    if thing:
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
    else:
        messages = {
            'read': _('You do not have access to this information. '
                      'Ask your administrator if you need it.'),
            'write': _('You cannot change this information. '
                       'Ask your administrator if you need it.'),
            'create': _('You cannot add this information. '
                        'Ask your administrator if you need it.'),
            'unlink': _('You cannot delete this information. '
                        'Ask your administrator if you need it.'),
        }
    plain = AccessError(messages.get(operation, messages['read']))
    if getattr(technical, 'context', None):
        plain.context = technical.context
    return plain


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _make_access_error(self, operation, records):
        technical = super()._make_access_error(operation, records)
        return _plain_access_error(self.env, records._name, operation, technical,
                                   records=records)


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    def _make_access_error(self, model, mode):
        technical = super()._make_access_error(model, mode)
        return _plain_access_error(self.env, model, mode, technical)
