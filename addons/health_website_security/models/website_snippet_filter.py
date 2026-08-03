import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Models the PUBLIC /website/snippet/filters route may resolve when the CALLER
# supplies `res_model` — i.e. the single-record dynamic-snippet path that browses
# `self.env[res_model].browse([res_id])` under sudo. Only product templates ship
# a `dynamic_filter_template_*` view on this platform, so the legitimate surface
# is tiny. Anything not listed here — every `health.*` model, `res.users`,
# `res.partner`, `account.move`, … — is refused before the sudo browse.
#
# This gate applies ONLY to the caller-supplied `res_model`. Filters an admin
# configures through `filter_id` / `action_server_id` resolve their model from
# server-side configuration, not from the request, and are deliberately left
# alone: that is the intended dynamic-snippet feature, not the vulnerability.
PUBLIC_SNIPPET_MODEL_ALLOWLIST = frozenset({
    'product.product',
    'product.template',
})


class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _get_public_snippet_model_allowlist(self):
        """Models a public caller may name in `res_model`. Override to extend."""
        return PUBLIC_SNIPPET_MODEL_ALLOWLIST

    def _render(self, template_key, limit, search_domain=None, with_sample=False,
                res_model=None, res_id=None, **custom_template_data):
        """T-003: refuse a caller-supplied `res_model` that is not allow-listed.

        `/website/snippet/filters` is `auth='public'`; its `_prepare_values` /
        `_prepare_sample` browse `res_model`/`res_id` under sudo. We reject the
        model HERE, before super() reaches that browse. Returning `[]` is exactly
        what the route yields for "nothing found", so no new error surface is
        exposed to an attacker and no legitimate snippet is broken.
        """
        if res_model and res_model not in self._get_public_snippet_model_allowlist():
            _logger.warning(
                "T-003: refused website snippet render for non-allowlisted "
                "res_model %r (res_id=%r, template=%r)",
                res_model, res_id, template_key)
            return []
        return super()._render(
            template_key, limit, search_domain=search_domain,
            with_sample=with_sample, res_model=res_model, res_id=res_id,
            **custom_template_data)
