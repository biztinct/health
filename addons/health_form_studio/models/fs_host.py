# -*- coding: utf-8 -*-
"""The clinic's words for its hosts, in the reader's language.

A host's lock reasons and zone titles are data (JSON on `fs.host`), and JSON
is not translatable. The sentences the overlay ships are declared here as lazy
translations, so the export picks them up and `_fs_text` hands each reader
their own language. Every sentence in `data/fs_hosts.xml` needs its entry here
(`test_28` checks it).
"""
from odoo import models
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

HOST_TEXT = {
    # Incident
    'Identifies the incident on every report.':
        _lt('Identifies the incident on every report.'),
    'Drives the incident workflow.': _lt('Drives the incident workflow.'),
    'Links the incident to the client record.':
        _lt('Links the incident to the client record.'),
    'Used for statutory reporting deadlines.':
        _lt('Used for statutory reporting deadlines.'),
    'Counters': _lt('Counters'),
    'Drawn by the system.': _lt('Drawn by the system.'),
    # Client
    'Identifies the client everywhere.':
        _lt('Identifies the client everywhere.'),
    "Builds the client's name.": _lt("Builds the client's name."),
    'Used for age, consent and insurance.':
        _lt('Used for age, consent and insurance.'),
    'Used to reach the client and by the messaging channels.':
        _lt('Used to reach the client and by the messaging channels.'),
    'Decides which team can see this client.':
        _lt('Decides which team can see this client.'),
    'Links the client to their facility.':
        _lt('Links the client to their facility.'),
    'Stored encrypted by the system.': _lt('Stored encrypted by the system.'),
    'Used on insurance claims.': _lt('Used on insurance claims.'),
    'Drives pricing.': _lt('Drives pricing.'),
    'Used on clinical records.': _lt('Used on clinical records.'),
    'People': _lt('People'),
    # Contact
    'Identifies the contact.': _lt('Identifies the contact.'),
    'Used to reach the contact.': _lt('Used to reach the contact.'),
    'Drives the contact workflow.': _lt('Drives the contact workflow.'),
    'Decides who works this contact.': _lt('Decides who works this contact.'),
    'Decides which team can see this contact.':
        _lt('Decides which team can see this contact.'),
    'Used in channel reports.': _lt('Used in channel reports.'),
    'Links the contact to a client.': _lt('Links the contact to a client.'),
    'Written by the website and ads tracking.':
        _lt('Written by the website and ads tracking.'),
    'Contact history': _lt('Contact history'),
}


class FsHost(models.Model):
    _inherit = 'fs.host'

    def _fs_text(self, text):
        lazy = HOST_TEXT.get(text)
        if lazy is not None:
            return self.env._(lazy)
        return super()._fs_text(text)
