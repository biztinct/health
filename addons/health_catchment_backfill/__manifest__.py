{
    'name': 'Healthcare Catchment Backfill',
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Security',
    'summary': "One-time backfill of Doctor-role users' catchment province from their facility",
    'description': """
Healthcare Catchment Backfill
=============================

Closes T-012. A ``res.users`` with ``catchment_province_id`` NULL is *denied
every row* on the catchment-narrowed clinical models — the rule domain
``['&', ('catchment_province_id','=',user.catchment_province_id.id),
       ('catchment_province_id','!=',False)]`` is unsatisfiable when the user's
own field is empty (ledger §5.117). After phase SH-2 gave the Doctor role its
healthcare group, eight of the ten doctors held the permission but saw nothing.

This module's ``post_init_hook`` sets ``catchment_province_id`` for every
``access.role`` "Doctor" user that has none, deriving it from the catchment
province of the user's healthcare facility (``hr.employee.healthcare_facility_id
.catchment_province_id``). The rule is self-validating: the two doctors who
already carry a catchment (Hanoi, HCMC) match their facility's province exactly.

Scope is DELIBERATELY doctors only. Nurses share the same latent NULL-catchment
condition, but populating their province would expand patient visibility for
~40 accounts — a separate access decision, not part of this fix. Idempotent:
only NULL-catchment rows are touched.
""",
    'author': 'VAFHS Development Team',
    'website': 'https://www.vafhs.com',
    'license': 'LGPL-3',
    'depends': ['health_base'],
    'data': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
