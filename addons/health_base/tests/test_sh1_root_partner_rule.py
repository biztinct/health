# -*- coding: utf-8 -*-
"""SH-1 §6 (T-002) — the chatter AccessError for ops/CRM personas.

Core mail dereferences `base.partner_root.email_normalized` WITHOUT sudo in
two places in the LIVE `mail/models/models.py` (v1.19): line 406 in
`_message_get_default_recipients` (composer + mail templates) and line 557 in
`_message_get_suggested_recipients_batch`, which every chatter render drives
unconditionally. An internal user who cannot read that one partner therefore
gets an AccessError dialog instead of a chatter.

For an ops persona the applicable `res.partner` rules are the global rule 2
plus the group rule "User: Own Partner Record" (`[('id','=',user.partner_id.id)]`);
`base.partner_root` fails it, group rules OR together, so the union is empty
and the record is denied. Clinical staff never saw it because the healthcare
staff rule has an `('is_patient','=',False)` branch that matches the root
partner — the ops persona holds none of that rule's groups.

§5.4 applies with full force: a uid-1 test cannot see this bug at all
(`ir_rule._get_rules` returns an empty recordset when `self.env.su`), so every
assertion below runs `with_user(ops)`.
"""
import uuid

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

RULE_XMLID = 'health_base.rule_internal_read_root_partner'


@tagged('post_install', '-at_install')
class TestSh1RootPartnerRule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.province = env['health.catchment.province'].search([], limit=1) or \
            env['health.catchment.province'].create({'name': 'SH1 T002 P'})
        # Reproduces uid 40 (`crm`)'s effective rule set: base.group_user plus
        # an operations group, and NOTHING from the healthcare-staff rule's
        # group list (receptionist / nurse / doctor / manager) — that rule's
        # is_patient=False branch would otherwise match the root partner and
        # mask the defect entirely.
        cls.ops = new_test_user(
            env, login='sh1_t002_ops_%s' % uuid.uuid4().hex[:5],
            password='sh1_t002_ops_pw',
            groups='base.group_user,'
                   'health_base.group_healthcare_operations_manager',
            catchment_province_id=cls.province.id)
        cls.root = env.ref('base.partner_root')
        cls.rule = env.ref(RULE_XMLID)

    # ------------------------------------------------------------------
    # T6.1 — the positive: a chatter render no longer raises
    # ------------------------------------------------------------------
    def test_61_suggested_recipients_does_not_raise_for_ops(self):
        for group in ('health_base.group_healthcare_nurse',
                      'health_base.group_healthcare_doctor',
                      'health_base.group_healthcare_receptionist',
                      'health_base.group_healthcare_manager',
                      'health_base.group_healthcare_owner',
                      'base.group_system'):
            self.assertFalse(
                self.ops.has_group(group),
                'fixture problem: the persona holds %s, which carries a '
                'partner rule that matches the root partner — this test '
                'would pass before the fix' % group)
        # a mail.thread record the persona can read (rule "User: Own Partner")
        rec = self.ops.partner_id.with_user(self.ops)
        rec._message_get_suggested_recipients_batch(
            reply_discussion=True, no_create=True)

    def test_61b_root_partner_is_readable(self):
        self.assertEqual(
            self.root.with_user(self.ops).read(['id'])[0]['id'], self.root.id)

    # ------------------------------------------------------------------
    # T6.2 — the anti-trap negative: EXACTLY one record widened
    # ------------------------------------------------------------------
    def _readable_ids(self, Partner, rule_active):
        """Readable partner ids with the rule toggled on/off.

        `ir_rule._get_rules` selects from `ir_rule` with RAW SQL
        (`self.env.execute_query`), so an un-flushed ORM write to `active` is
        invisible to it and the rule stays effective — the first run of this
        test measured no difference at all for exactly that reason (§5.9's
        family: raw SQL races pending ORM flushes). Flush first, THEN drop the
        `_compute_domain` ormcache, then search.

        `active_test=False` is load-bearing too (§5.27): `base.partner_root`
        is ARCHIVED on this database (`res_partner.active = f`), so a plain
        `search([])` carries an implicit `('active','=',True)` and drops it
        from BOTH sides — the difference is then empty and the test fails
        against a perfectly correct rule. Record rules apply to `read` on an
        archived record all the same, which is why the chatter still raised.
        """
        self.rule.active = rule_active
        self.env.flush_all()
        self.env.registry.clear_cache()
        try:
            return Partner.search([]).ids
        finally:
            if not rule_active:
                self.rule.active = True
                self.env.flush_all()
                self.env.registry.clear_cache()

    def test_62_widening_is_exactly_the_root_partner(self):
        """The most important test in this phase.

        `ir.rule._compute_global` makes a rule GLOBAL iff its `groups` field
        is empty, and global rules are AND-ed into every partner query for
        every user — a `groups`-less version of this record would collapse
        res.partner to a single row system-wide. This measures the real
        before/after by toggling the rule inside the test transaction.
        """
        Partner = self.env['res.partner'].with_user(self.ops) \
                      .with_context(active_test=False)

        before = set(self._readable_ids(Partner, rule_active=False))
        after = set(self._readable_ids(Partner, rule_active=True))

        self.assertEqual(after - before, {self.root.id},
                         'the rule widened more than the root partner')
        self.assertEqual(before - after, set(),
                         'the rule NARROWED the readable partner set')
        self.assertNotIn(self.root.id, before,
                         'the persona could already read the root partner — '
                         'the fixture does not reproduce the defect')

    def test_62b_rule_shape_is_group_bound_and_read_only(self):
        """Structural guard on the trap, independent of the data."""
        self.assertTrue(self.rule.active)
        self.assertFalse(
            self.rule['global'],
            'the rule is GLOBAL — it is AND-ed into every partner query for '
            'every user and collapses res.partner system-wide')
        self.assertEqual(self.rule.groups, self.env.ref('base.group_user'))
        self.assertTrue(self.rule.perm_read)
        for perm in ('perm_write', 'perm_create', 'perm_unlink'):
            self.assertFalse(self.rule[perm], '%s must stay off' % perm)
        self.assertEqual(self.rule.model_id.model, 'res.partner')
        self.assertEqual(self.rule.domain_force,
                         "[('id', '=', %d)]" % self.root.id)

    # ------------------------------------------------------------------
    # T6.3 — write is still denied
    # ------------------------------------------------------------------
    def test_63_write_on_the_root_partner_is_still_denied(self):
        with self.assertRaises(AccessError):
            self.root.with_user(self.ops).write({'comment': 'nope'})
