# -*- coding: utf-8 -*-
"""`health.consent` extension — the `web_form` evidence class (W3 §4.1a).

The consent bridge materialises a website checkbox claim as a real
`health.consent` record. That record must be *honest about its own
evidence*: it was not witnessed verbally, it carries no scanned form and no
signature — its evidence is the submission itself.

So the method Selection gets one new key, and `action_grant()` gets the gate
the core model does not have for it. **This is the whole reason the override
exists**: `health_consent.action_grant` checks evidence with per-method `if`
branches (`health_consent/models/health_consent.py:389-400`), NOT with a
whitelist —

    if self.method == 'verbal' and not self.verbal_witness_id: raise
    if self.method == 'written' and not self.evidence_attachment_ids: raise
    if self.method == 'digital_signature' and not self.signature: raise

— so a key added by `selection_add` falls through all three and grants with
no evidence at all. The extending module owns its own discipline.

`ondelete={'web_form': 'set default'}` is safe here even though
`health.consent.write()` refuses to touch evidence fields out of draft:
core's `_process_ondelete` wraps the write in `safe_write`
(`odoo/addons/base/models/ir_model.py:1722-1745`), catches the `UserError`
and falls back to a raw `UPDATE`. Verified on the server rather than assumed
— ledger §5.17 is about `cascade` on an unconditional `unlink()` guard, and
that trap does not reach this field.

NOTHING in `health_consent` is edited (W3 §2, binding).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# The evidence a `web_form` consent must carry before it may be granted.
# `scope_note` names the consent text version + the submission; the
# `client_mutation_id` is the idempotency key that ties the record back to
# the one submission that produced it. Without both, the record cannot be
# audited back to anything and must not exist in `active`.
WEB_FORM_METHOD = 'web_form'


class HealthConsent(models.Model):
    _inherit = 'health.consent'

    method = fields.Selection(
        selection_add=[(WEB_FORM_METHOD, 'Web form checkbox')],
        ondelete={WEB_FORM_METHOD: 'set default'})

    def action_grant(self):
        """Add the missing per-method evidence gate for `web_form`.

        Runs BEFORE `super()` so a refusal costs nothing — the core method's
        first act is `ensure_one()` and the supersede sweep is only reached
        after every guard. The loop is over `self` rather than a bare
        `ensure_one()` so this stays correct if the base ever grows a
        multi-record grant.
        """
        for consent in self:
            if consent.method != WEB_FORM_METHOD:
                continue
            if not consent.scope_note:
                raise UserError(_(
                    'A web-form consent must record what the visitor was '
                    'shown (consent text version and submission reference) '
                    'in Scope / Limitations before it can be granted.'))
            if not consent.client_mutation_id:
                raise UserError(_(
                    'A web-form consent must carry the submission '
                    'idempotency key before it can be granted.'))
        return super().action_grant()

    @api.model
    def _web_form_method_available(self):
        """True when this database really carries the `web_form` key.

        Cheap guard for the bridge: a registry where `selection_add` did not
        apply (a partial upgrade, a stale worker) must skip the bridge rather
        than write a value the column's CHECK-free Selection would later
        reject at flush (ledger §5.18's family).
        """
        selection = dict(self._fields['method']._description_selection(
            self.env))
        return WEB_FORM_METHOD in selection
