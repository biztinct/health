# -*- coding: utf-8 -*-
"""Shared vocabulary for catchment scoping.

Everything that both the view injector and the sidebar need to agree on lives
here, so the two never drift: the group that may cross areas, the default field
name, and the filter names the sidebar puts into ``search_default_*``.
"""

# The one role allowed to see, and switch to, another catchment area. Chosen
# because it is already the bypass group on the live rules — see
# health_base/security/health_security.xml:183 (all partners) and :234 (all
# facilities). Admin is NOT included: an admin manages users, which is a
# different thing from reading another area's patient data.
OWNER_GROUP = 'health_base.group_healthcare_owner'

# Groups whose members are pinned to their own area. Used by the province
# visibility rule; deliberately excludes admin and owner.
SCOPED_GROUPS = (
    'health_base.group_healthcare_receptionist',
    'health_base.group_healthcare_nurse',
    'health_base.group_healthcare_head_nurse',
    'health_base.group_healthcare_doctor',
    'health_base.group_healthcare_sales',
    'health_base.group_healthcare_finance',
    'health_base.group_healthcare_operations_manager',
    'health_base.group_healthcare_manager',
)

# The field name 56 models already use. A model that stores its area under a
# different name declares `_catchment_field` on the class instead — hr.employee
# does, because it shipped as `staff_catchment_province_id` long before this.
DEFAULT_CATCHMENT_FIELD = 'catchment_province_id'

# Filter names. `MINE` is what the sidebar defaults on for everybody; `PER_AREA`
# is the per-province filter an owner switches to.
FILTER_MINE = 'catchment_mine'
FILTER_PER_AREA = 'catchment_p%s'


# ---------------------------------------------------------------------------
# Global (AND-ed) scoping
# ---------------------------------------------------------------------------
# Odoo ORs together every group rule that matches any group the user is in, and
# ANDs the global ones on top. A per-group catchment rule is therefore only as
# strong as the most permissive rule the user picks up from anywhere else — and
# measured on this database, 17 models leaked across areas because of exactly
# that. crm.lead was the clearest: the stock Sales rule "All Leads"
# ([(1,'=',1)], group "User: All Documents") ORs the catchment rule away
# entirely, so a Hà Nội user saw all 296 leads. res.partner was the worst: a Hà
# Nội doctor could read 150 Ho Chi Minh City patients.
#
# These models therefore get a GLOBAL rule, which cannot be OR-ed away. The
# per-group rules stay: they are still the ones that grant, and the global one
# only ever narrows.
#
# res.users is deliberately NOT in this list. A global rule on res.users is a
# well-known way to break login and every user-name render across the product,
# and the exposure there (seeing colleagues' names) is not worth that risk. It
# keeps its group rule.
GLOBAL_SCOPED_MODELS = (
    'res.partner',
    'crm.lead',
    'account.move',
    'account.move.line',
    'account.payment',
    'health.facility',
    'health.client.relation',
    'health.staff.assignment',
    'health.staff.availability.matrix',
    'health.payment.transaction',
    'health.ar.transaction.log',
    'health.service.package',
    'health.outbound.message',
    'hr.employee',
    'redinvoice.request',
    'fhir.submission.log',
)


def global_catchment_domain(field):
    """The domain text for a global catchment rule on `field`.

    Three audiences, one expression:

    * anyone who is not a scoped healthcare user — owners, portal patients,
      public and integration users — passes straight through, so their own
      rules keep governing them and nothing outside healthcare changes;
    * a scoped user sees their own area;
    * plus records with NO area at all.

    That last clause is what makes this safe to switch on. 292 of 296 leads,
    37 of 96 employees and most partners carry no area, and hiding them would
    take real work away from everyone rather than protect anything. The
    property being enforced is "you never see ANOTHER area's records", not
    "you only see records that name your area".
    """
    return (
        "[(1, '=', 1)] if not user.catchment_enforced else "
        "['|', ('{f}', '=', False), ('{f}', '=', user.catchment_province_id.id)]"
    ).format(f=field)


def catchment_field_of(model):
    """Return the name of `model`'s catchment field, or None if it has none.

    `model` is a recordset (an empty one is fine). Models with no area — the
    reference catalogues, the CMS config, terminology — return None and are
    left completely alone: no filter, no field, no behaviour change.
    """
    field = getattr(model, '_catchment_field', DEFAULT_CATCHMENT_FIELD)
    if field not in model._fields:
        return None
    # A non-stored field cannot be searched, so a filter on it would raise
    # rather than filter. Better to skip than to ship a broken facet.
    if not model._fields[field].store:
        return None
    return field
