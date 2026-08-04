"""Legacy-reference fields for idempotent upserts.

Each migrated business record carries the old-system identifier so the
migration can be re-run safely (update-in-place, never duplicate) and so the
old code stays visible "for future reference".

Beyond the three upsert keys, this module also holds the legacy *audit* fields
(who created/modified the row in Pancake) and the small business fields the
legacy export carries but the platform had no home for (client type, second
phone, first-service date). Marketing/ad identifiers are bundled into a single
JSON field rather than one column per tracker.
"""
from odoo import models, fields


class ResPartnerLegacy(models.Model):
    _inherit = 'res.partner'

    legacy_client_code = fields.Char(
        'Legacy Client Code', index=True, copy=False,
        help='Client ID from the previous system (e.g. "02 0006826").')

    legacy_ad_ids = fields.Json(
        'Legacy Marketing IDs', copy=False,
        help='Pancake channel/ad identifiers kept as one JSON blob '
             '(page_id, ad_id, ad_id_fb, ad_id_tiktok, conversation_id, psid, '
             'facebook_link, pancake_customer_id).')


class CrmLeadLegacy(models.Model):
    _inherit = 'crm.lead'

    legacy_contact_guid = fields.Char(
        'Legacy Contact GUID', index=True, copy=False,
        help='Contact ID (GUID) from the previous system.')

    legacy_created_by = fields.Char(
        'Legacy Created By', copy=False,
        help='Operator who created the record in the previous system.')

    legacy_lastcontactuser = fields.Char(
        'Legacy Last Contact User', copy=False,
        help='Last operator who contacted this lead in the previous system.')

    legacy_owner = fields.Char(
        'Legacy Owner', copy=False,
        help='Owner recorded in the previous system when it could not be '
             'matched to a platform user.')

    legacy_ad_ids = fields.Json(
        'Legacy Marketing IDs', copy=False,
        help='Pancake channel/ad identifiers kept as one JSON blob.')


class FsoLegacy(models.Model):
    _inherit = 'health.fieldservice.order'

    legacy_booking_ref = fields.Char(
        'Legacy Booking Ref', index=True, copy=False,
        help='Stable hash of the legacy booking row for idempotent re-import.')

    legacy_created_by = fields.Char(
        'Legacy Created By', copy=False,
        help='Operator who created the booking in the previous system.')

    legacy_modified_by = fields.Char(
        'Legacy Modified By', copy=False,
        help='Operator who last modified the booking in the previous system.')

    legacy_modified_on = fields.Datetime(
        'Legacy Modified On', copy=False,
        help='Last modification timestamp from the previous system.')

    legacy_owner = fields.Char(
        'Legacy Owner', copy=False,
        help='Clinic owner/person in charge recorded in the previous system '
             '(phòng khám Owner).')
