# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""The framework's name, out of what is sent — and the URLs left intact.

Two halves, and the second is the one that matters. Taking a word out of an
email is easy; the risk in this change is that a careless replacement rewrites
a link. Every URL-shaped case below is a real string out of a stock template on
this deployment, and each of them must come back BYTE-IDENTICAL.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTheWordIsTakenOut(TransactionCase):
    def setUp(self):
        super().setUp()
        self.render = self.env["mail.render.mixin"]
        self.brand = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("biz_debranding.brand_name")
        )
        self.assertTrue(self.brand, "this database has no brand set")

    # ---------------------------------------------------------- it is taken out
    def test_a_subject_line_loses_it(self):
        """The part of an email somebody reads before deciding to trust it."""
        out = self.render.biz_debrand_words(
            "Invitation to activate two-factor authentication on your Odoo account"
        )
        self.assertNotIn("Odoo", out)
        self.assertIn(self.brand, out)

    def test_a_visible_sentence_loses_it(self):
        out = self.render.biz_debrand_words(
            '<p><span style="font-size: 10px;">Welcome to Odoo</span></p>'
        )
        self.assertNotIn("Odoo", out)
        self.assertIn("Welcome to %s" % self.brand, out)

    def test_a_meeting_invitation_loses_it(self):
        out = self.render.biz_debrand_words("<div><t>Odoo Discuss</t></div>")
        self.assertNotIn("Odoo", out)

    def test_a_signature_loses_it(self):
        out = self.render.biz_debrand_words("<p>Odoo S.A.</p>")
        self.assertNotIn("Odoo S", out)
        self.assertIn(self.brand, out)

    def test_what_a_screen_reader_says_loses_it(self):
        out = self.render.biz_debrand_words(
            '<img alt="Odoo" title="Odoo" src="/web/static/img/logo.png"/>'
        )
        self.assertNotIn('alt="Odoo"', out)
        self.assertNotIn('title="Odoo"', out)
        self.assertIn('src="/web/static/img/logo.png"', out)

    # -------------------------------------------------- and the links survive it
    def test_a_url_path_is_untouched(self):
        """`/odoo/…` is a real address on this build. Rewriting it breaks it."""
        src = (
            '<a t-attf-href="/odoo/{{ object.module_id.id }}/action-base_install'
            '_request.action_base_module">Install</a>'
        )
        self.assertEqual(self.render.biz_debrand_words(src), src)

    def test_a_hostname_is_untouched(self):
        src = '<a href="https://www.odoo.com?utm_source=db&amp;utm_medium=auth">x</a>'
        self.assertEqual(self.render.biz_debrand_words(src), src)

    def test_lowercase_is_never_touched(self):
        """Lowercase is what appears in paths, hostnames and identifiers."""
        for src in ("odoo-bin", "/odoo/action-5", "odoo.com", "from odoo import api"):
            self.assertEqual(self.render.biz_debrand_words(src), src, src)

    def test_the_bot_is_left_to_its_own_rename(self):
        """`OdooBot` has no boundary after the word, so it never matches here."""
        self.assertEqual(self.render.biz_debrand_words("OdooBot"), "OdooBot")

    def test_nothing_to_do_returns_the_value_itself(self):
        for src in ("", None, False, "a plain sentence"):
            self.assertEqual(self.render.biz_debrand_words(src), src)

    def test_a_broken_fragment_is_sent_as_it_was(self):
        """A white-label failure must never stop an email somebody is waiting for."""
        out = self.render.biz_debrand_words("<<< Odoo >>> <p unclosed")
        self.assertIsInstance(out, str)

    # ------------------------------------------------------------ the whole path
    def test_it_runs_on_every_rendered_template(self):
        rendered = self.render._render_template(
            "Your Odoo account", "res.partner", self.env.user.partner_id.ids
        )
        for value in rendered.values():
            self.assertNotIn("Odoo", value)


@tagged("post_install", "-at_install")
class TestTheSeededRecords(TransactionCase):
    """Rows the framework writes once, which no render-time pass can reach."""

    def setUp(self):
        super().setUp()
        self.brand = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("biz_debranding.brand_name")
        )

    def test_the_periodic_digest_is_named_and_quiet(self):
        digest = self.env.ref("digest.digest_digest_default", raise_if_not_found=False)
        if not digest:
            self.skipTest("this database has no periodic digest")
        self.assertNotIn("Odoo", digest.name or "")
        self.assertIn(self.brand, digest.name or "")
        self.assertEqual(
            digest.state,
            "deactivated",
            "the periodic digest would email every member of staff the day an "
            "outgoing mail account is connected",
        )

    def test_the_welcome_message_is_ours(self):
        message = self.env.ref(
            "mail.module_install_notification", raise_if_not_found=False
        )
        if not message:
            self.skipTest("this database has no seeded welcome message")
        self.assertNotIn("Odoo", message.subject or "")
        self.assertNotIn("Odoo", str(message.body or ""))
        self.assertIn(self.brand, message.subject or "")

    def test_the_notification_preference_is_ours(self):
        group = self.env.ref(
            "mail.group_mail_notification_type_inbox", raise_if_not_found=False
        )
        if not group:
            self.skipTest("this database has no such preference")
        self.assertNotIn("Odoo", group.name or "")

    def test_it_is_renamed_in_every_language_not_just_english(self):
        """The leak that only shows in the language most of the staff read.

        `write()` on a translatable field touches the language the environment
        is in and no other, so the first version of this renamed the English
        and left "Nhận thông báo trong Odoo" in Vietnamese — on a platform
        whose clinics start in Vietnamese.
        """
        group = self.env.ref(
            "mail.group_mail_notification_type_inbox", raise_if_not_found=False
        )
        if not group:
            self.skipTest("this database has no such preference")
        for lang in self.env["res.lang"].search([]):
            name = group.with_context(lang=lang.code).name or ""
            self.assertNotIn(
                "Odoo", name, "still names the framework in %s" % lang.code
            )

    def test_the_digest_is_renamed_in_every_language(self):
        digest = self.env.ref("digest.digest_digest_default", raise_if_not_found=False)
        if not digest:
            self.skipTest("this database has no periodic digest")
        for lang in self.env["res.lang"].search([]):
            name = digest.with_context(lang=lang.code).name or ""
            self.assertNotIn(
                "Odoo", name, "still names the framework in %s" % lang.code
            )

    def test_a_translation_keeps_its_own_grammar(self):
        """The WORD is substituted, so a Vietnamese sentence stays Vietnamese."""
        from odoo.addons.biz_debranding.models.brand_words import debrand_text

        self.assertEqual(
            debrand_text("Nhận thông báo trong Odoo", "Viet Uc Care"),
            "Nhận thông báo trong Viet Uc Care",
        )

    def test_no_seeded_or_assistant_message_names_the_framework(self):
        """No message from the assistant still says the framework's NAME.

        Asserted on the word, not on the substring, and the difference is the
        point: plenty of these messages carry `/odoo/1/action-…` in a link, and
        the sweep is right to leave that alone. A test that asked for the
        substring would be demanding that the links be broken.
        """
        from odoo.addons.biz_debranding.models.brand_words import (
            names_the_framework,
        )

        candidates = self.env["mail.message"].sudo().search(
            ["|", ("subject", "ilike", "Odoo"), ("body", "ilike", "Odoo")]
        )
        seeded = set(
            self.env["ir.model.data"]
            .sudo()
            .search([("model", "=", "mail.message")])
            .mapped("res_id")
        )
        bot = self.env.ref("base.partner_root")
        candidates = candidates.filtered(
            lambda m: m.id in seeded or m.author_id == bot
        )
        offenders = [
            m.id
            for m in candidates
            if names_the_framework(m.subject) or names_the_framework(m.body)
        ]
        self.assertFalse(
            offenders,
            "a seeded or assistant message still names the framework: %s" % offenders,
        )

    def test_a_persons_own_message_is_never_touched(self):
        """A debranding pass that edits somebody's words is not a debranding pass.

        The author has to be a REAL partner. In a test the environment is the
        superuser, and the superuser's partner IS `base.partner_root` — the
        same partner the assistant posts as — so a message written the obvious
        way is genuinely the assistant's and is rewritten, correctly. That
        cost a test cycle; hence the throwaway partner.
        """
        someone = self.env["res.partner"].sudo().create({"name": "A Colleague"})
        self.assertNotEqual(someone.id, self.env.ref("base.partner_root").id)
        theirs = (
            self.env["mail.message"]
            .sudo()
            .create(
                {
                    "subject": "My own note about Odoo",
                    "body": "<p>I wrote this about Odoo myself.</p>",
                    "author_id": someone.id,
                    "model": "res.partner",
                    "res_id": someone.id,
                }
            )
        )
        self.env["res.config.settings"]._biz_rebrand_bot_messages(self.brand)
        theirs.invalidate_recordset()
        self.assertIn("Odoo", theirs.subject)
        self.assertIn("Odoo", str(theirs.body))

    def test_re_running_it_changes_nothing(self):
        """It runs on every upgrade, so it has to be safe to run twice."""
        settings = self.env["res.config.settings"]
        settings._biz_debrand_seeded_records(self.brand)
        digest = self.env.ref("digest.digest_digest_default", raise_if_not_found=False)
        if digest:
            self.assertNotIn("Odoo", digest.name or "")
            self.assertNotIn(self.brand + " " + self.brand, digest.name or "")
