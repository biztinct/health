# -*- coding: utf-8 -*-
"""Everything this product tells the generic platform modules about itself.

FIVE REGISTRATIONS AND NOT A LINE MORE. This file has no model, no field and no
method that anything calls: it runs at import time, hands five facts to
`biz_tenants.models.tenants_common`, and stops.

⚠ IT MUST LOAD WHERE THE COCKPIT IS NOT INSTALLED. This module ships to every
customer's system (for the "About" door), and the cockpit ships to none of them.
So the import is guarded, and everything below it is skipped rather than
crashing a customer's system on a module it will never have.
"""
import logging

_logger = logging.getLogger(__name__)

# =============================================================================
# THE METERS' QUERIES, WRITTEN OUT HERE SO THEY CAN BE READ.
#
# Each one takes `%(start)s` and `%(end)s` — the period the platform is asking
# about — and each one guards on the table and the column it needs, so a
# customer who has not been brought in step yet gets "not available here"
# rather than an error that takes the other three down with it.
#
# ⚠ WHICH DATE A COMPLETED VISIT IS COUNTED ON, AND WHY IT IS THIS ONE.
# The visit record carries six dates. Measured on the clinic's own 975
# completed visits (2026-09-04):
#
#     booking_date            975 / 975   when somebody BOOKED it
#     scheduled_date          971 / 975   the day the visit was FOR
#     actual_end_datetime     870 / 975   when the nurse finished
#     actual_start_datetime    63 / 975   almost never filled
#
# `booking_date` is the fullest and it is the WRONG question: a visit booked in
# March and carried out in April would be counted in March, which is not the
# month the work was done. `actual_end_datetime` is the truest and loses one
# visit in nine, which on a month's billing is a discount nobody agreed to.
# `scheduled_date` is the day the visit was for, is a plain DATE so a month
# boundary needs no clock, and is filled on 99.6% of them. It is the one used.
#
# AND ONE FIGURE THAT LOOKS LIKE A FAULT AND IS NOT: this meter reads 0 for the
# current month on the clinic's own system. That is not the column — the clinic
# has no completed visits at all since July 2026 (2 in July, 8 in June, 917 in
# April). The number is right; the month is empty.
# =============================================================================
METERS = (
    {
        'key': 'patients',
        'label': "People in care",
        'unit': 'people',
        'help': "Everybody on the books right now — a count today, not a "
                "count over the period.",
        'table_guard': 'res_partner',
        'column_guard': 'res_partner.is_patient',
        'sql': "SELECT count(*) FROM res_partner "
               "WHERE is_patient AND active",
    },
    {
        'key': 'visits',
        'label': "Visits completed",
        'unit': 'visits',
        'help': "Counted on the day the visit was FOR, not the day it was "
                "booked.",
        'table_guard': 'health_fieldservice_order',
        'column_guard': 'health_fieldservice_order.scheduled_date',
        'sql': "SELECT count(*) FROM health_fieldservice_order "
               "WHERE state = 'completed' "
               "AND scheduled_date >= %(start)s AND scheduled_date <= %(end)s",
    },
    {
        'key': 'staff',
        'label': "Staff with a login",
        'unit': 'people',
        'help': "People who can sign in. Portal accounts are not counted.",
        'table_guard': 'res_users',
        'column_guard': 'res_users.share',
        'sql': "SELECT count(*) FROM res_users "
               "WHERE active AND share IS NOT TRUE",
    },
    {
        'key': 'invoices',
        'label': "Invoices issued",
        'unit': 'invoices',
        'help': "Customer invoices posted in the period. Drafts and "
                "cancellations are not counted — an invoice somebody is still "
                "working on has not been issued.",
        'table_guard': 'account_move',
        'column_guard': 'account_move.move_type',
        'sql': "SELECT count(*) FROM account_move "
               "WHERE move_type = 'out_invoice' AND state = 'posted' "
               "AND invoice_date >= %(start)s AND invoice_date <= %(end)s",
    },
)

# =============================================================================
# WHAT A CUSTOMER'S SYSTEM MUST NEVER RECEIVE.
#
# ⚠ AND THE ONE THAT COULD NOT BE HONOURED (ledger H57). `health_web_leads` —
# one customer's marketing-website funnel — belongs on this list by every
# argument, and it CANNOT go on it: `health_learn` and `health_cms_coverage`
# both declare it as a dependency, so the framework pulls it in whatever this
# list says. Every new customer therefore gets the web-leads screens, and they
# sit inert until somebody connects a website to them. Breaking those two
# dependencies is a piece of work of its own and is deliberately not done here.
#
# The lesson, for anything added below: a never-list is a statement about the
# DEPENDENCY GRAPH, not about a set of names.
# =============================================================================
NEVER = {
    'health_migration':
        "The tools that carried this clinic's own history across from the "
        "system it used before. They are one customer's move, not a part of "
        "the product, and inside somebody else's system they would offer to "
        "overwrite records that are already right.",
    'health_catchment_backfill':
        "A one-off repair that filled in which area each existing record "
        "belonged to. It has been run; running it anywhere else would rewrite "
        "rows nobody asked it to touch.",
}

NEVER_PREFIXES = ('biz_platform',)


def _register():
    """Hand the five facts over. Skipped where the cockpit is not installed."""
    try:
        from odoo.addons.biz_tenants.models import tenants_common as common
    except ImportError:
        # A customer's own system has this module and not the cockpit. That is
        # the normal case for every system but one, so it is not a warning.
        _logger.debug("health_tenancy: the customers screen is not on this "
                      "system, so nothing was registered with it.")
        return False

    # 1. Who we are and where we live. Every one of these is a DEFAULT behind a
    #    setting of the same meaning, because the platform's own address has
    #    already changed once in the middle of this programme and took
    #    seventeen written-down copies of itself with it.
    common.register_platform({
        'brand': 'Viet Uc Care',
        'apex': 'carejiox.com',
        'backend_prefix': '/bizapp',
        'template_db': 'carejiox_template',
    })

    # 2. What a customer never receives.
    common.register_never(NEVER, prefixes=NEVER_PREFIXES)

    # 3. What their use is measured in.
    for spec in METERS:
        common.register_meter(spec)

    # 4. Who their own administrator is. BY FIXED ID, never by name — the name
    #    is the one thing an administrator is invited to change. And never the
    #    system administrator permission: the cockpit refuses to finish
    #    provisioning if the role it is handed carries it.
    common.register_tenant_admin({
        'role_xmlid': 'health_access.role_owner',
        'group_xmlids': ('health_access.group_clinic_admin',),
    })

    # 5. Where their administrator lands on their first sign-in. Without one
    #    the framework drops somebody into the messaging app, which is a poor
    #    first impression of a clinical product.
    common.register_home_action('health_landing.action_admin_dashboard')
    return True


REGISTERED = _register()
