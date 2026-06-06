"""Legacy-reference fields for idempotent upserts.

Each migrated business record carries the old-system identifier so the
migration can be re-run safely (update-in-place, never duplicate) and so the
old code stays visible "for future reference".
"""
from odoo import models, fields


class ResPartnerLegacy(models.Model):
    _inherit = 'res.partner'

    legacy_client_code = fields.Char(
        'Legacy Client Code', index=True, copy=False,
        help='Client ID from the previous system (e.g. "02 0006826").')


class CrmLeadLegacy(models.Model):
    _inherit = 'crm.lead'

    legacy_contact_guid = fields.Char(
        'Legacy Contact GUID', index=True, copy=False,
        help='Contact ID (GUID) from the previous system.')


class FsoLegacy(models.Model):
    _inherit = 'health.fieldservice.order'

    legacy_booking_ref = fields.Char(
        'Legacy Booking Ref', index=True, copy=False,
        help='Stable hash of the legacy booking row for idempotent re-import.')
