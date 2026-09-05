# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""The framework's name, taken out of everything that is rendered and sent.

WHY THIS EXISTS BESIDE `mail_debranding` AND NOT INSIDE IT. The OCA module we
depend on removes the "Powered by …" ANCHOR from a rendered body — it looks for
`<a href="…odoo.com">` and takes the whole link out. That is the right fix for a
link, and it is the only fix it makes. It leaves the bare WORD alone, in three
places that reach a real person:

  * a SUBJECT LINE — "Invitation to activate two-factor authentication on your
    Odoo account" is the framework's name in the one part of an email a person
    reads before deciding whether to trust it. `remove_href_odoo` returns early
    for anything under twenty characters and otherwise only touches anchors, so
    a subject passes through it untouched.
  * VISIBLE SENTENCES — "Welcome to Odoo", "Odoo Discuss" in a meeting
    invitation, "Odoo S.A." as a signature.
  * the `alt` and `title` ATTRIBUTES, which are what a screen reader says out
    loud and what a browser shows when an image does not load.

THE REPLACEMENT IS DELIBERATELY NARROW, AND THE NARROWNESS IS THE WHOLE POINT.
A blind search-and-replace over a rendered template corrupts the product: these
bodies carry `t-attf-href="/odoo/{{ object.module_id.id }}/action-…"` — a real
URL path on this build — and `https://www.odoo.com?utm_source=…`. Rewriting
either produces a link that goes nowhere, and it does it silently, in an email
somebody already received. So:

  * only the exact capitalised word `Odoo` is matched, never lowercase `odoo`,
    because lowercase is what appears in paths (`/odoo/`), hostnames
    (`odoo.com`) and identifiers (`odoo-bin`);
  * a match is refused when the character before it is a word character, `/`,
    `.` or `-`, and when the character after it is a word character, `.` or `-`.
    That single rule is what keeps `odoo.com`, `/odoo/`, `Odoo.sh` and
    `OdooBot` out of it — `OdooBot` has no boundary after `Odoo`, so it never
    matches, and the bot has its own rename elsewhere in this module;
  * in HTML the replacement walks TEXT NODES ONLY (plus `alt`/`title`), so
    nothing inside a tag — no href, no style, no `t-att` expression — can be
    touched even in principle. The parser is the guard, not the regular
    expression.

IT RUNS AT RENDER, NOT ON THE STORED RECORD. Rewriting the thirteen stored
templates would be a one-off that a module upgrade can undo, that a second
database does not get, and that cannot be reversed without knowing what was
there before. Rendering is the last moment before a person sees the words, it
covers every template at once including ones installed later, and switching
this module off restores the framework's own text exactly.
"""

import logging

from markupsafe import Markup

from odoo import api, models

from .brand_words import debrand_value, names_the_framework

_logger = logging.getLogger(__name__)


class MailRenderMixin(models.AbstractModel):
    _inherit = "mail.render.mixin"

    @api.model
    def _biz_brand(self):
        """The product's name, or None when this database has not set one.

        Read through `ir.config_parameter` rather than held in a module-level
        variable: the brand is per database, and this process serves several.
        """
        brand = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("biz_debranding.brand_name")
            or ""
        ).strip()
        return brand or None

    @api.model
    def biz_debrand_words(self, value):
        """Take the framework's name out of one rendered value.

        Returns the value unchanged — same type — when there is nothing to do.
        Never raises: a white-label failure must not stop an email somebody is
        waiting for, so the worst case is the untouched text plus a line in the
        log saying why.
        """
        if not value:
            return value
        brand = self._biz_brand()
        if not brand:
            return value

        was_markup = isinstance(value, Markup)
        was_bytes = isinstance(value, bytes)
        text = value.decode() if was_bytes else str(value)

        if not names_the_framework(text):
            return value

        try:
            text = debrand_value(text, brand)
        except Exception:  # noqa: BLE001
            # The reason goes in the LINE, not only in the traceback: a silent
            # white-label failure is a leak nobody will ever grep for.
            _logger.warning(
                "biz_debranding: could not take the framework name out of a "
                "rendered value; it was sent as the framework wrote it",
                exc_info=True,
            )
            return value

        if was_bytes:
            return text.encode()
        if was_markup:
            return Markup(text)
        return text

    @api.model
    def _render_template(
        self,
        template_src,
        model,
        res_ids,
        engine="inline_template",
        add_context=None,
        options=None,
    ):
        """Every rendered subject and body, after the anchors have gone.

        `super()` here is `mail_debranding`'s, which strips the "Powered by"
        links; this pass takes the word out of what is left. The order matters
        only in that doing it this way round means the word inside a link that
        is about to be deleted is never rewritten first.
        """
        rendered = super()._render_template(
            template_src,
            model,
            res_ids,
            engine=engine,
            add_context=add_context,
            options=options,
        )
        for key, value in rendered.items():
            rendered[key] = self.biz_debrand_words(value)
        return rendered
