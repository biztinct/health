# -*- coding: utf-8 -*-
"""The clinic's words for its hosts, in the reader's language.

A host's lock reasons and zone titles are data (JSON on `fs.host`), and JSON
is not translatable. The sentences the overlay ships are declared here as lazy
translations, so the export picks them up and `_fs_text` hands each reader
their own language.
"""
from odoo import models
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

HOST_TEXT = {
    'Identifies the incident on every report.':
        _lt('Identifies the incident on every report.'),
    'Drives the incident workflow.': _lt('Drives the incident workflow.'),
    'Links the incident to the client record.':
        _lt('Links the incident to the client record.'),
    'Used for statutory reporting deadlines.':
        _lt('Used for statutory reporting deadlines.'),
    'Counters': _lt('Counters'),
    'Drawn by the system.': _lt('Drawn by the system.'),
}


class FsHost(models.Model):
    _inherit = 'fs.host'

    def _fs_text(self, text):
        lazy = HOST_TEXT.get(text)
        if lazy is not None:
            return self.env._(lazy)
        return super()._fs_text(text)
