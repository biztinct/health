# -*- coding: utf-8 -*-
"""What a customer's system is made of — the rule, with no registry anywhere.

SAAS H4c §5.1. Every case here is a fact about the COMPUTATION, so every one of
them is written against manifests declared in this file rather than against the
machine's. The one that matters most is `test_tripwire_*`: the day a part of
the product declares it needs the Inventory app, this file goes red and names
both modules, instead of a nurse waking up to a warehouse.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_tenants.models import module_set as mset
from odoo.addons.biz_tenants.models.module_set import (
    customer_module_set, dependency_conflicts, module_set_rows,
)

# A miniature of the real shape: a product on top, a few framework parts under
# it, and a family of apps beside it that nothing in the product needs.
MANIFESTS = {
    'base': {'depends': []},
    'web': {'depends': ['base']},
    'mail': {'depends': ['base']},
    'account': {'depends': ['base']},
    'hr': {'depends': ['base']},
    'hr_timesheet': {'depends': ['hr']},
    'sale': {'depends': ['account']},
    'purchase': {'depends': ['account']},
    'base_iban': {'depends': ['account', 'web']},
    # auto-installs itself the moment IBAN is present — the framework's rule,
    # not ours, and the reason a never-list cannot simply name it.
    'account_qr_code_sepa': {'depends': ['account', 'base_iban'],
                             'auto_install': True},
    'account_qr_code_emv': {'depends': ['account']},
    'l10n_vn': {'depends': ['account_qr_code_emv', 'base_iban', 'account'],
                'auto_install': ['account']},
    # The apps nothing in the product wants.
    'stock': {'depends': ['base']},
    'stock_account': {'depends': ['stock', 'account'], 'auto_install': True},
    'sale_management': {'depends': ['sale']},
    'theme_default': {'depends': ['web']},
    # The product.
    'health_base': {'depends': ['hr', 'mail']},
    'health_invoicing': {'depends': ['health_base', 'account', 'purchase',
                                     'hr_timesheet']},
    'health_fieldservice': {'depends': ['health_base', 'sale']},
    'biz_kit': {'depends': ['web']},
    'biz_tenants': {'depends': ['biz_kit']},
    'health_migration': {'depends': ['health_base']},
}

MASTER = sorted(MANIFESTS)

NEVER = {'biz_tenants', 'health_migration', 'stock', 'stock_account',
         'sale_management', 'theme_default'}

PREFIXES = ('health_', 'biz_')
EXTRAS = ('l10n_vn', 'account_qr_code_emv')


def answer(never=NEVER, manifests=None, master=None, extras=EXTRAS):
    return customer_module_set(master or MASTER, manifests or MANIFESTS,
                               never=never, prefixes=PREFIXES,
                               extras_names=extras)


@tagged('post_install', '-at_install')
class TestModuleSet(TransactionCase):
    """§5.1 — the computed set."""

    # ------------------------------------------------------------------ 5.1a
    def test_real_dependencies_are_in(self):
        """`sale`, `purchase` and `hr_timesheet` are in, because they are
        genuinely needed — and it is the APPS built on them that are not."""
        got = set(answer()['modules'])
        for name in ('sale', 'purchase', 'hr_timesheet'):
            self.assertIn(name, got,
                          "%s is a real dependency of the product" % name)
        self.assertNotIn('sale_management', got,
                         "the Sales APP is not the same thing as `sale`")

    def test_none_of_the_held_back_are_in(self):
        got = set(answer()['modules'])
        for name in ('stock', 'stock_account', 'sale_management',
                     'theme_default', 'biz_tenants', 'health_migration'):
            self.assertNotIn(name, got)

    def test_held_back_is_the_masters_remainder(self):
        res = answer()
        self.assertEqual(
            set(res['held_back']), set(MASTER) - set(res['modules']),
            "held back is everything the master has and a customer does not")

    # ------------------------------------------------------------------ 5.1b
    def test_extras_arrive_by_registration_not_by_the_closure(self):
        """An extra is in because it was ASKED FOR, and taking the
        registration away takes it out.

        `account_qr_code_emv` is the clean case: nothing depends on it and
        nothing auto-installs it, so it is in the answer only because the
        product named it.
        """
        with_extras = set(answer()['modules'])
        self.assertIn('account_qr_code_emv', with_extras)
        self.assertEqual(answer()['pulled_by']['account_qr_code_emv'], 'seed')
        without = set(answer(extras=())['modules'])
        self.assertNotIn('account_qr_code_emv', without,
                         "nothing in the product depends on the payment code")

    def test_a_country_pack_would_auto_install_and_that_is_why_it_is_asked_for(self):
        """⚠ THE FINDING THIS TEST EXISTS FOR, AND IT IS NOT OBVIOUS.

        A country's chart of accounts declares `auto_install = ['account']`,
        so this computation says the framework would install it on its own —
        and on the machine it does NOT, because the framework ALSO gates a
        country pack on the company's country, which no manifest can see. The
        blank system a customer is copied from has no country set, so it has
        no chart of accounts at all.

        That is exactly why the chart is ASKED FOR by name rather than left to
        the framework: the computation's answer here is optimistic, the
        machine's is empty, and the registration is what closes the gap.
        """
        res = answer(extras=())
        self.assertIn('l10n_vn', res['modules'])
        self.assertIn('l10n_vn', res['followers'],
                      'it arrives through the auto-install rule, not a depends')
        self.assertEqual(res['followers']['l10n_vn'], ['account'])

    def test_an_extra_brings_its_own_dependencies(self):
        """The Vietnamese chart needs IBAN, so IBAN is in — and IBAN then makes
        the framework install the European payment code on its own. This is the
        exact reason neither can be on the never-list (ledger H57's family)."""
        res = answer()
        self.assertIn('base_iban', res['modules'])
        self.assertEqual(res['pulled_by']['base_iban'], 'l10n_vn')
        self.assertIn('account_qr_code_sepa', res['modules'])
        self.assertIn('account_qr_code_sepa', res['followers'])

    def test_never_listing_something_a_wanted_part_needs_is_a_conflict(self):
        """A never-list entry that something in the answer NEEDS is reported,
        not silently broken. This is the exact case that took `base_iban` and
        `account_qr_code_sepa` off the list in this phase."""
        res = answer(never=NEVER | {'base_iban'})
        pairs = dict(dependency_conflicts(res))
        self.assertEqual(pairs.get('base_iban'), 'l10n_vn',
                         "the Vietnamese chart of accounts needs IBAN, so "
                         "refusing IBAN would be a rule the framework "
                         "overrules")
        self.assertIn('account_qr_code_sepa', res['followers'],
                      "and IBAN then makes the framework install the European "
                      "payment code on its own")

    # ------------------------------------------------------------- 5.1c the tripwire
    def test_tripwire_fires_when_the_product_gains_a_bad_dependency(self):
        """THE MAINTENANCE TRIPWIRE. The day somebody makes Inventory
        load-bearing, this is a failed test naming both modules."""
        clean = answer()
        self.assertEqual(clean['conflicts'], [],
                         "the product must not need anything held back")

        broken = dict(MANIFESTS)
        broken['health_fieldservice'] = {
            'depends': ['health_base', 'sale', 'stock']}
        res = answer(manifests=broken)
        pairs = dependency_conflicts(res)
        self.assertTrue(pairs, "a product module needing Inventory must fail")
        self.assertIn(('stock', 'health_fieldservice'), pairs,
                      "the failure names the held-back part AND what pulled it")

    def test_tripwire_names_the_module_that_pulled_it_transitively(self):
        broken = dict(MANIFESTS)
        broken['health_invoicing'] = {
            'depends': ['health_base', 'account', 'purchase', 'hr_timesheet',
                        'sale_management']}
        pairs = dict(dependency_conflicts(answer(manifests=broken)))
        self.assertEqual(pairs.get('sale_management'), 'health_invoicing')

    # ------------------------------------------------------------------ shape
    def test_seeds_are_the_products_own_parts_plus_the_extras(self):
        res = answer()
        self.assertIn('health_base', res['seeds'])
        self.assertIn('biz_kit', res['seeds'])
        self.assertIn('l10n_vn', res['seeds'])
        self.assertNotIn('biz_tenants', res['seeds'],
                         "the cockpit is never a seed of a customer's system")
        self.assertNotIn('account', res['seeds'],
                         "a framework part is reached, never seeded")

    def test_a_module_not_on_the_master_is_never_in_the_answer(self):
        res = answer(master=[m for m in MASTER if m != 'l10n_vn'])
        self.assertNotIn('l10n_vn', res['modules'],
                         "an extra the machine does not have cannot be given")

    def test_manifests_may_be_the_plain_shape(self):
        """`{name: [depends]}` is what a test wants to write; both are read."""
        plain = {k: v['depends'] for k, v in MANIFESTS.items()}
        self.assertEqual(answer(manifests=plain)['modules'],
                         [m for m in answer()['modules']
                          if m != 'account_qr_code_sepa'],
                         "the plain shape carries no auto-install information")

    def test_held_back_rows_carry_a_reason_each(self):
        rows = module_set_rows(answer(), {'stock': 'Inventory'})
        by_name = {r['module']: r for r in rows}
        self.assertIn('stock', by_name)
        self.assertEqual(by_name['stock']['label'], 'Inventory')
        self.assertTrue(by_name['stock']['reason'].strip(),
                        "every held-back row says why, on screen")

    def test_nothing_registered_answers_nothing_rather_than_everything(self):
        """A cockpit nobody has told what the product is must not decide that
        every module on the machine belongs to a customer."""
        res = customer_module_set(MASTER, MANIFESTS, never=NEVER,
                                  prefixes=(), extras_names=())
        self.assertEqual(res['modules'], [])
        self.assertEqual(set(res['held_back']), set(MASTER))


@tagged('post_install', '-at_install')
class TestModuleSetRegistry(TransactionCase):
    """The registrations themselves — first-wins, and read at call time."""

    def test_prefixes_and_extras_are_registered_by_the_product(self):
        self.assertTrue(mset.product_prefixes(),
                        "the overlay registers how this product is named")
        self.assertIn('health_', mset.product_prefixes())
        self.assertIn('l10n_vn', mset.extras())

    def test_registering_the_same_thing_twice_changes_nothing(self):
        before = (mset.product_prefixes(), mset.extras())
        mset.register_product_prefixes(('health_',))
        mset.register_extras(('l10n_vn',))
        self.assertEqual((mset.product_prefixes(), mset.extras()), before)

    def test_blank_registrations_are_ignored(self):
        before = mset.extras()
        mset.register_extras(('', None))
        self.assertEqual(mset.extras(), before)
