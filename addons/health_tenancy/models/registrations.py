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

    # ------------------------------------------------------------------
    # THE EIGHTEEN THE COMPUTATION EXPOSED (SAAS H4c §3.1).
    #
    # None of these is part of the product. They are on the master because the
    # master is ALSO the clinic that runs today, and a clinic accumulates
    # things over four years. Nothing in the care product declares any of them
    # as a dependency — which is exactly how they were found: the computed
    # module set contains 175 parts, and every one of these is outside it.
    #
    # Until this list existed, sending a release out would have installed a
    # warehouse, a sales pipeline and a website theme onto a home-care nurse's
    # system (ledger H83). Each reason below is written for the owner, because
    # it is shown to the owner on the "In step with master" screen.
    # ------------------------------------------------------------------
    'stock':
        "Inventory — warehouses, stock moves and deliveries. A home-care "
        "clinic keeps no warehouse, and the app puts a whole extra menu in "
        "front of every nurse.",
    'stock_account':
        "The accounting half of Inventory. It only means anything where "
        "Inventory itself is being used.",
    'stock_sms':
        "Text messages about deliveries. Part of Inventory.",
    'purchase_stock':
        "The join between purchase orders and a warehouse. Nothing to join "
        "without Inventory.",
    'sale_management':
        "The Sales app — quotations, a sales pipeline and an order book. The "
        "product bills for visits through its own invoicing; this is a second "
        "way of selling that nobody in a clinic uses.",
    'sale_pdf_quote_builder':
        "A quotation-document designer. Part of the Sales app.",
    'sale_project':
        "The join between the Sales app and projects.",
    'sale_project_stock_account':
        "A join between the Sales app, projects and a warehouse.",
    'sale_purchase_project':
        "A join between the Sales app, purchasing and projects.",
    'sale_service':
        "The part of the Sales app that lets a product be a service rather "
        "than a thing on a shelf. It only means anything where the Sales app "
        "itself is being used, and this product bills for visits through its "
        "own invoicing.",
    'sale_timesheet':
        "Billing time recorded on a project through the Sales app. The "
        "product bills for visits, not for timesheets.",
    'spreadsheet_dashboard_sale_timesheet':
        "A ready-made spreadsheet dashboard about billing timesheets.",
    'project_stock':
        "The join between projects and a warehouse.",
    'project_purchase_stock':
        "A join between projects, purchasing and a warehouse.",
    'project_stock_account':
        "A join between projects, a warehouse and the accounts.",
    'barcodes_gs1_nomenclature':
        "Barcode rules for retail and logistics packaging. The clinical "
        "barcode work in this product does not use them.",
    'base_automation':
        "A tool for writing automatic rules — 'when this changes, do that'. "
        "It can run code against any record in a system, so it is a "
        "platform-level tool rather than something to hand out with a "
        "clinic.",
    'theme_default':
        "A website theme. The product's own look is set by its theme "
        "settings, and this would sit unused in every customer's apps list.",
}

NEVER_PREFIXES = ('biz_platform',)

# =============================================================================
# HOW THE GENERIC COCKPIT RECOGNISES THIS PRODUCT'S OWN PARTS, AND THE TWO IT
# MUST BE TOLD ABOUT BY NAME.
#
# ⚠ `l10n_vn` PULLS TWO MORE IN WITH IT, AND THEY CANNOT BE REFUSED (H57's
# family, third sighting). The Vietnamese chart of accounts declares
# `base_iban` as a dependency, and `base_iban` is the trigger for
# `account_qr_code_sepa`, which the framework installs on its own. Both were on
# the first draft of the list above and both had to come off it: a never-list
# entry the framework overrules is not a rule, it is a lie in a screen. They
# are harmless — European bank-account validation and a European payment QR
# code, sitting unused — and the report says so plainly.
# =============================================================================
PRODUCT_PREFIXES = ('health_', 'biz_')

EXTRAS = (
    # The Vietnamese chart of accounts. No clinical module can declare it — the
    # product is meant to be sold in more than one country — and a clinic in
    # Vietnam without the Vietnamese accounts is not a working clinic.
    'l10n_vn',
    # ⚠ THE ONE JUDGEMENT CALL IN THIS PHASE, and it is reversible by deleting
    # this line. It puts a VietQR payment code on an invoice, so a patient can
    # pay by scanning it. Nothing depends on it, so the computation leaves it
    # out; the owner asked for Vietnamese invoicing and the clinic that runs
    # today has it with six bank accounts configured. It is listed explicitly
    # rather than left to arrive as a dependency of `l10n_vn` so that the
    # decision is written down where somebody can change their mind about it.
    'account_qr_code_emv',
)


# =============================================================================
# THE TEN PARTS OF THE PRODUCT THAT CAN BE SWITCHED OFF (owner's decision 7).
#
# A FEATURE IS NOT A MODULE. "Family" is a portal and a message store and a
# visit page; "AI" is the coding review and the voice notes. What a clinic buys
# is not the same shape as what an engineer installs, and this list is written
# in the first vocabulary.
#
# ⚠ SWITCHING ONE OFF REMOVES NOTHING. The doors close; every record ever made
# is still there, and switching it back on brings the screens back with the
# data behind them. That sentence is on the screen as well, because it is the
# first question anybody asks.
#
# `blurb` IS WRITTEN FOR THE CUSTOMER, not for us: it is the sentence somebody
# in the clinic reads on the page they land on when they follow an old link to
# a screen that is closed. So it says what they would be able to do, not what
# the module is called.
# =============================================================================
FEATURES = (
    {'key': 'care_command', 'name': "Care Command", 'sequence': 10,
     'blurb': "One place where every message, call and enquiry from families "
              "arrives, is answered and is followed up — instead of a "
              "different inbox for each way people get in touch."},
    {'key': 'telehealth', 'name': "Telehealth", 'sequence': 20,
     'blurb': "Video visits: a waiting room a family can join from a link, "
              "and the visit recorded on the same booking as any other."},
    {'key': 'family', 'name': "Family access", 'sequence': 30,
     'blurb': "The family's own pages — what happened on a visit, the "
              "records they are allowed to see, and two-way messages with "
              "the care team."},
    {'key': 'telemonitoring', 'name': "Deterioration watch", 'sequence': 40,
     'blurb': "Readings from monitoring devices, an early-warning score on "
              "every one of them, and a worklist of the people whose "
              "numbers are heading the wrong way."},
    {'key': 'bhyt', 'name': "Health-insurance claims", 'sequence': 50,
     'blurb': "Preparing and tracking national health-insurance claims for "
              "the visits that are covered."},
    {'key': 'redinvoice', 'name': "Red invoice", 'sequence': 60,
     'blurb': "Issuing official tax invoices to the tax authority from the "
              "invoice you already raised, and keeping the log of them."},
    {'key': 'analytics', 'name': "Analytics", 'sequence': 70,
     'blurb': "Building your own reports and dashboards from your own "
              "numbers, and scheduling them to arrive."},
    {'key': 'ai', 'name': "Assisted notes and coding", 'sequence': 80,
     'blurb': "Turning what a nurse dictated into a note, and suggesting the "
              "diagnosis codes for a visit for somebody to approve."},
    {'key': 'voice', 'name': "Phone system", 'sequence': 90,
     'blurb': "Calls in and out from inside the system: the call log, missed "
              "calls, recordings and extensions."},
    {'key': 'learn', 'name': "Training", 'sequence': 100,
     'blurb': "The learning journey, the practice tasks and the coach that "
              "sits beside somebody while they work."},
)


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

    # 2b. And how the cockpit recognises what a customer IS made of, so the
    #     answer is computed from this product's own dependencies rather than
    #     written down twice (SAAS H4c §3.1).
    try:
        from odoo.addons.biz_tenants.models import module_set
    except ImportError:                                      # pragma: no cover
        module_set = None
    if module_set is not None:
        module_set.register_product_prefixes(PRODUCT_PREFIXES)
        module_set.register_extras(EXTRAS)

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

    # 6. Which parts of the product can be sold separately, and what a customer
    #    LOSES when one is off (SAAS H4c §3.4).
    common.register_features(FEATURES)

    # 7. And how to draw a miniature of this product's own left menu, so the
    #    matrix can show what a customer will see before anybody presses
    #    anything. The function takes `env` because one registration serves
    #    every database this process ever loads (ledger H6).
    from .cms_sidebar import menu_preview as _preview
    common.register_menu_preview(_preview)
    return True


REGISTERED = _register()
