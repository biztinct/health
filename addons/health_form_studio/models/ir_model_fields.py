# -*- coding: utf-8 -*-
"""The cipher behind Form Studio's encrypted fields on the clinic's screens.

Health information typed into a Studio text field on the Client record is
stored with the same key and the same token format as the client's own
encrypted fields (identity numbers, allergies, notes):
`health_phi_encryption.models.phi_crypto` — AES-256-GCM, `enc$1$` tokens, the
key from `HEALTH_PHI_KEY` or derived from the database secret. Nothing here
encrypts by itself; the engine asks for the pair when it builds a field.
"""
from odoo import api, models

from odoo.addons.health_phi_encryption.models import phi_crypto


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    @api.model
    def _fs_cipher(self):
        return (phi_crypto.encrypt, phi_crypto.decrypt,
                phi_crypto.DECRYPT_ERROR_MARKER)
