# Part of the Viet Uc Care white-label layer. License LGPL-3.
import base64
import logging

from odoo import api, fields, models
from odoo.tools import file_open

from .brand_words import (
    debrand_translated_field,
    debrand_value,
    names_the_framework,
)

_logger = logging.getLogger(__name__)

# Default brand for this deployment. Any client database may override
# `biz_debranding.brand_name` (and the web_debranding params) before/after
# install — the seed never clobbers a value that is already customised.
DEFAULT_BRAND = "Viet Uc Care"
DEFAULT_WEBSITE = "https://care.biztinct.com"
DEFAULT_THEME_COLOR = "#1565C0"

# Brand icon reused from health_pwa so we ship no duplicate binary assets.
# (The PWA icon-*.png files are ASCII placeholders, not real images — use the
# valid brand logo instead.)
BRAND_ICON = "health_pwa/static/img/VietLogo.png"

# Copy for the records the framework seeds with its own name in them. Kept up
# here, with a `%s` for the brand, so every sentence a customer can read is in
# one place rather than buried in the method that writes it.
_WELCOME_SUBJECT = "Welcome to %s!"
_WELCOME_BODY = (
    "<p>Welcome to the #general channel.</p>"
    "<p>This channel is open to everybody here, for sharing anything the whole "
    "team should know.</p>"
)


def _read_icon_b64():
    try:
        with file_open(BRAND_ICON, "rb") as f:
            return base64.b64encode(f.read())
    except Exception:
        _logger.warning("biz_debranding: could not read brand icon %s", BRAND_ICON, exc_info=True)
        return None


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Single SaaS brand knob. Kept in sync with the web_debranding params so
    # the whole white-label follows one field, per database.
    biz_brand_name = fields.Char(
        string="Brand Name",
        config_parameter="biz_debranding.brand_name",
        help="Product name shown everywhere in place of Odoo "
             "(browser title, backend, emails, PWA, bot).",
    )
    biz_brand_website = fields.Char(
        string="Brand Website",
        config_parameter="biz_debranding.brand_website",
        help="Replaces odoo.com links across the UI.",
    )
    biz_theme_color = fields.Char(
        string="Brand Theme Color",
        config_parameter="biz_debranding.theme_color",
        help="PWA / mobile theme color (hex, e.g. #1565C0).",
    )

    # ------------------------------------------------------------------
    # Seeding — runs on install AND every upgrade (via data <function>),
    # so the white-label identity is re-applied idempotently.
    # ------------------------------------------------------------------
    @api.model
    def _biz_apply_brand(self):
        icp = self.env["ir.config_parameter"].sudo()

        brand = (icp.get_param("biz_debranding.brand_name") or DEFAULT_BRAND).strip()
        website = (icp.get_param("biz_debranding.brand_website") or DEFAULT_WEBSITE).strip()
        theme_color = (icp.get_param("biz_debranding.theme_color") or DEFAULT_THEME_COLOR).strip()

        # Canonical brand params (source of truth for web_debranding + PWA).
        icp.set_param("biz_debranding.brand_name", brand)
        icp.set_param("biz_debranding.brand_website", website)
        icp.set_param("biz_debranding.theme_color", theme_color)

        # Drive the installed debranding suite; fixes the single-slash
        # `https:/care.biztinct.com` bug that was live.
        icp.set_param("web_debranding.new_name", brand)
        icp.set_param("web_debranding.new_title", brand)
        icp.set_param("web_debranding.new_website", website)
        icp.set_param("web_debranding.new_documentation_website", website + "/documentation/")

        # health_pwa.theme_color is seeded with noupdate=1, so an upgrade never
        # rewrites the stale aubergine value — overwrite it to the brand color.
        icp.set_param("health_pwa.theme_color", theme_color)

        icon_b64 = _read_icon_b64()

        # Favicon: web_debranding only defaults it for NEW companies, so set it
        # explicitly on every existing company. Best-effort.
        if icon_b64:
            for company in self.env["res.company"].sudo().search([]):
                try:
                    company.favicon = icon_b64
                except Exception:
                    _logger.warning("biz_debranding: favicon on %s failed", company.name, exc_info=True)

        # Website identity: the login/portal/website tab title and favicon come
        # from the website record, not the company. Brand every website.
        if "website" in self.env:
            for site in self.env["website"].sudo().search([]):
                try:
                    vals = {"name": brand}
                    if icon_b64:
                        vals["favicon"] = icon_b64
                    site.write(vals)
                except Exception:
                    _logger.warning("biz_debranding: website branding on %s failed", site.name, exc_info=True)

        # OdooBot → brand bot. Name rebrand always runs; avatar best-effort.
        bot = self.env.ref("base.partner_root", raise_if_not_found=False)
        if bot:
            bot.sudo().write({"name": brand})
            if icon_b64:
                try:
                    bot.sudo().write({"image_1920": icon_b64})
                except Exception:
                    _logger.warning("biz_debranding: bot avatar failed", exc_info=True)

        self._biz_debrand_seeded_records(brand)

        _logger.info("biz_debranding: white-label identity applied as %r", brand)
        return True

    # ------------------------------------------------------------------
    # Records the framework seeds with its own name in them.
    #
    # These are not rendered from a template, so the render-time pass in
    # mail_render_debrand.py never sees them: they are ROWS, written once when
    # a module is installed, and they sit there until somebody rewrites them.
    # Every one of them below is reachable by an ordinary user of a customer's
    # database, which is the whole test (standing white-label rule).
    #
    # Runs on install AND on every upgrade, through the same <function> as the
    # rest of the identity, so a database that exists already is repaired and a
    # database made tomorrow never shows it in the first place.
    # ------------------------------------------------------------------
    @api.model
    def _biz_debrand_seeded_records(self, brand):
        self._biz_quiet_the_periodic_digest(brand)
        self._biz_rebrand_seeded_message(brand)
        self._biz_rebrand_notification_group(brand)
        self._biz_rebrand_bot_messages(brand)

    @api.model
    def _biz_quiet_the_periodic_digest(self, brand):
        """The one that would actually have SENT.

        `digest.digest` is a scheduled summary of a database's numbers, mailed
        to everybody who is subscribed to it, and the framework ships it
        ACTIVATED and named after itself. It has never gone out on this
        platform for one reason only — there is no outgoing mail account — so
        the day one is connected it would post "Your Odoo Periodic Digest" to
        every member of staff of every clinic. On the golden template it was set
        to DAILY, which is what every new clinic would have inherited.

        Two changes, and they are different in kind:
          * the NAME is white-labelling and is not negotiable;
          * switching it OFF is a judgement, and a reversible one — Settings →
            General Settings → Statistics, one click. A periodic email about
            their own numbers is not something any clinic here asked for, and
            an unsolicited round of them on the day mail is connected is not a
            way to introduce the platform to somebody's staff.

        Deliberately does NOT touch a digest somebody has made themselves: only
        the framework's own seeded record, found by its external id.
        """
        if "digest.digest" not in self.env:
            return
        digest = self.env.ref("digest.digest_digest_default", raise_if_not_found=False)
        if not digest:
            return
        # The name is translatable, so it is rewritten in EVERY language this
        # database speaks — see `debrand_translated_field`. Writing it the
        # ordinary way renamed the English and left the Vietnamese saying
        # "Tóm tắt định kỳ Odoo của bạn", which is the language the clinics
        # here actually read.
        langs = debrand_translated_field(digest, "name", brand)
        if digest.sudo().state == "activated":
            digest.sudo().write({"state": "deactivated"})
            _logger.info(
                "biz_debranding: the periodic digest is switched off "
                "(Settings → General Settings → Statistics turns it back on)"
            )
        if langs:
            _logger.info(
                "biz_debranding: the periodic digest was renamed in %s",
                ", ".join(langs),
            )

    @api.model
    def _biz_rebrand_seeded_message(self, brand):
        """"Welcome to Odoo!" — the first thing in every inbox.

        Written into the #general channel when the messaging app installs, so
        it is sitting in the inbox of every database made from the template.
        Rewritten rather than deleted: deleting a message leaves a channel whose
        first entry is missing, and the sentence itself is a perfectly good
        welcome once it is wearing the right name.
        """
        message = self.env.ref(
            "mail.module_install_notification", raise_if_not_found=False
        )
        if not message:
            return
        message = message.sudo()
        subject = message.subject or ""
        if "Odoo" not in subject:
            return
        message.write(
            {
                "subject": _WELCOME_SUBJECT % brand,
                # No brand in the body on purpose — it names the channel, not
                # the product — so it is NOT formatted. `"…" % brand` on a
                # string with no placeholder raises, and it raises inside the
                # data-file <function> that runs on every upgrade, which takes
                # the whole upgrade with it. Found by the rehearsal.
                "body": _WELCOME_BODY,
            }
        )
        _logger.info("biz_debranding: the seeded welcome message now says %r", brand)

    @api.model
    def _biz_rebrand_notification_group(self, brand):
        """"Receive notifications in Odoo" — a permission NAME, and those show.

        It is the label on the notification preference every user can see on
        their own account.
        """
        group = self.env.ref(
            "mail.group_mail_notification_type_inbox", raise_if_not_found=False
        )
        if not group:
            return
        # Translatable, and the Vietnamese is the one that mattered here.
        debrand_translated_field(group, "name", brand)

    @api.model
    def _biz_rebrand_bot_messages(self, brand):
        """Messages the framework has already put in people's inboxes.

        Beyond the one seeded welcome there are others: the assistant's own
        "…chat helps employees collaborate efficiently" introduction, an
        onboarding tip, and — on a database that has been running a while —
        every periodic digest raised before the digest was renamed, sitting in
        the outgoing queue titled after the framework.

        NARROWED TO THE ASSISTANT'S OWN MESSAGES, and that is the safety
        argument. Every one of these is authored by `base.partner_root`, the
        account the framework posts as; a person's own message is never
        touched, because a debranding pass that edits somebody's words is not a
        debranding pass. The word is substituted rather than the sentence
        replaced, so a message keeps its meaning and its language.
        """
        Message = self.env["mail.message"].sudo()
        bot = self.env.ref("base.partner_root", raise_if_not_found=False)

        # TWO SAFE DISCRIMINATORS, AND NEITHER IS "IT MENTIONS THE WORD".
        #
        #   1. authored by `base.partner_root` — the account the framework
        #      posts as;
        #   2. carrying an EXTERNAL ID — a message a module SEEDED. A record
        #      created by a data file is not correspondence; nobody typed it.
        #      This is what reaches the demo conversations, which are authored
        #      by invented people and so are invisible to rule 1 while being
        #      just as much the framework's own words.
        #
        # Anything that is neither is somebody's actual message and is left
        # exactly as they wrote it.
        seeded_ids = (
            self.env["ir.model.data"]
            .sudo()
            .search([("model", "=", "mail.message")])
            .mapped("res_id")
        )
        # Prefix notation, spelled out rather than assembled cleverly: "whose
        # it is" AND "does it say the word".
        if bot:
            whose = ["|", ("id", "in", seeded_ids), ("author_id", "=", bot.id)]
        else:
            whose = [("id", "in", seeded_ids)]
        says_it = ["|", ("subject", "ilike", "Odoo"), ("body", "ilike", "Odoo")]
        candidates = Message.search(whose + says_it)
        touched = 0
        for message in candidates:
            vals = {}
            if names_the_framework(message.subject):
                vals["subject"] = debrand_value(message.subject, brand)
            if names_the_framework(message.body):
                vals["body"] = debrand_value(message.body, brand)
            if not vals:
                continue
            try:
                message.write(vals)
                touched += 1
            except Exception:  # noqa: BLE001
                # One message that refuses to be rewritten must not stop the
                # rest, and the reason belongs in the line, not the traceback.
                _logger.warning(
                    "biz_debranding: message %s kept the framework's name",
                    message.id,
                    exc_info=True,
                )
        if touched:
            _logger.info(
                "biz_debranding: %s message(s) from the assistant now say %r",
                touched,
                brand,
            )

    def set_values(self):
        super().set_values()
        # Re-apply the whole identity so a brand change from the settings page
        # propagates to companies, websites, bot and the debranding suite.
        self._biz_apply_brand()
