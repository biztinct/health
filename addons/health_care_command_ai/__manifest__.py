# -*- coding: utf-8 -*-
{
    "name": "Care Command — AI Assist",
    "version": "19.0.1.0.0",
    "category": "Healthcare/CRM",
    "summary": "Optional, config-gated AI drafts + continuity brief over Care "
               "Command — Ollama-first, never auto-send",
    "description": """
Care Command — AI Assist (Phase 4)
==================================

An OPTIONAL layer over Care Command. It is a **configuration, not a feature of
the core**: installing this module changes nothing until a manager turns it on.

- **Reply drafts** — a "Draft" button in the composer proposes a polite
  Vietnamese reply from the (redacted) conversation timeline. It only ever
  fills the composer; the human still edits and sends.
- **Continuity brief** — an on-demand "AI" card summarises the conversation in
  3-5 bullets for an agent taking over.

Principles (all binding):

- **OFF by default**; a manager flips the master switch in Settings.
- **Ollama-first** — a cloud provider is refused unless cloud is explicitly
  allowed (data sovereignty).
- **Redacted** — the partner's and lead's name/phone/email are stripped before
  any text reaches the model; the same redacted string is what we log.
- **Never a send path** — AI output lands in an editable composer or a labeled
  card. The only send remains the existing human one.
- **No clinical content** — the prompt sees the (non-clinical) care timeline +
  status/booking facts only.

The core ``health_care_command`` module stays AI-free; this module composes from
its public service seams and patches its OWL action from its own asset bundle.
    """,
    "author": "I Am Dream Catcher Ltd",
    "website": "https://vafhs.com",
    "license": "LGPL-3",
    "depends": [
        "health_care_command",
        "biz_bi",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # No new mask icons — we reuse the core's ic-* classes (their
            # data-URI masks live in health_care_command's plain .css, §5.51).
            "health_care_command_ai/static/src/scss/care_command_ai.scss",
            "health_care_command_ai/static/src/js/care_command_ai.js",
            "health_care_command_ai/static/src/xml/care_command_ai.xml",
        ],
    },
    "installable": True,
    # Installing this module is itself the opt-in (handover §2).
    "auto_install": False,
    "application": False,
    "sequence": 126,
}
