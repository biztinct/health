# -*- coding: utf-8 -*-
"""Reply templates for the four adapter channels.

Phase 5 shipped all eight channel keys on ``care.conversation`` but NOT on
``care.reply.template`` (verified: care_reply_template.py:24-35 still lists
any/zalo/call/email/zns), so a WhatsApp conversation could only ever show
"Any channel" chips. ``selection_add`` closes that gap here rather than in the
core, keeping the core free of adapter-channel names.

``ondelete='set default'`` on every added value: uninstalling this module must
not delete a manager's templates, and the model's default channel is ``any``,
which is exactly the honest fallback for a template whose channel disappeared.
"""
from odoo import fields, models


class CareReplyTemplateChannelExt(models.Model):
    _inherit = 'care.reply.template'

    channel = fields.Selection(
        selection_add=[
            ('whatsapp', 'WhatsApp'),
            ('fb', 'Messenger'),
            ('telegram', 'Telegram'),
            ('webchat', 'Web chat'),
        ],
        ondelete={
            'whatsapp': 'set default',
            'fb': 'set default',
            'telegram': 'set default',
            'webchat': 'set default',
        },
    )
