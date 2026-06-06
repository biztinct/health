{
    'name': 'Health Migration',
    'version': '19.0.1.0.0',
    'summary': 'Idempotent, reversible legacy-data migration toolkit',
    'description': """
Reusable ORM-based migration framework for importing legacy exports
(Contact_mig / Booking_mig and future files) into the health platform.

- Adds legacy-reference fields (legacy_client_code, legacy_contact_guid,
  legacy_booking_ref) for idempotent upserts.
- migration.xref: generic crosswalk for auto-created dimension records
  (staff stubs, services, facilities, tags).
- migration.baseline: reversible archive log (hide pre-existing demo/test
  data so only migrated records are visible).
- migration.runner: the importer (clients, bookings, sale lines, payments,
  staff assignments, contacts) with dry-run, value-maps and status/stage maps.
""",
    'author': 'Biztinct',
    'category': 'Tools',
    'depends': [
        'health_base',
        'health_fieldservice',
        'health_invoicing',
        'health_crm',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
