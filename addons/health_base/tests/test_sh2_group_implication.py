# -*- coding: utf-8 -*-
"""SH-2 §5 (T-001) — the inverted `base.group_user → group_healthcare_base`
implication, the Doctor role it was masking, and the seven archived accounts.

Every assertion here is measured against the LIVE `res_groups_implied_rel`
table, never against the security XML: ledger §5.88 exists because on this
database the two disagreed for eight months. The XML declares 346 → 1; the
table ALSO held 1 → 346, which handed every internal user the whole
healthcare-base ACL surface (18 ACLs, 7 menus) including `health.ews.score`
read and full `1,1,1,1` on `health.fso.clinical.notes.wizard`.

The fix is `health_base/migrations/19.0.1.3.8/post-migrate.py`. These tests
assert the resulting live state, so they are the standing regression guard: if
somebody re-installs the pre-8be03c5e `menu_access.xml` or re-adds the edge by
hand, T5.2/T5.6 go red.
"""
import uuid

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

HEALTHCARE_BASE_XMLID = 'health_base.group_healthcare_base'
DOCTOR_GROUP_XMLID = 'health_base.group_healthcare_doctor'
DOCTOR_ROLE_XMLID = 'health_access.role_doctor'
NOTES_WIZARD = 'health.fso.clinical.notes.wizard'

# §5.5 — the seven accounts the user declared unused on 2026-08-03 and
# authorised archiving. They lose group 346 like everyone else.
UNUSED_LOGINS = (
    'nam.lh', 'anh.pd', 'mai.vt', 'tuan.hm', 'ha.dt', 'huong.nt', 'bao.tq',
)

# §5.1 — the ten clinicians who reached healthcare data ONLY through the
# defect, and who are carried across it by the Doctor-role repair.
DOCTOR_LOGINS = (
    'dhanoi', 'dhcmc', 'huynh', 'staff_130', 'staff_203', 'staff_205',
    'staff_207', 'staff_140', 'staff_155', 'staff_154',
)


@tagged('post_install', '-at_install')
class TestSh2GroupImplication(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.healthcare_base = cls.env.ref(HEALTHCARE_BASE_XMLID)
        cls.doctor_group = cls.env.ref(DOCTOR_GROUP_XMLID)
        cls.base_user_group = cls.env.ref('base.group_user')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _live_closure(self, group_ids):
        """Groups reachable from `group_ids` through `res_groups_implied_rel`.

        Ledger §5.88 rule (a): compute closures with a recursive query over the
        TARGET database, never by reading `implied_ids` in source. `flush_all`
        first — the recursive query is raw SQL and cannot see pending ORM
        writes (§5.9's family).
        """
        self.env.flush_all()
        self.env.cr.execute("""
            WITH RECURSIVE closure(gid) AS (
                SELECT unnest(%s::int[])
                UNION
                SELECT rel.hid
                  FROM res_groups_implied_rel rel
                  JOIN closure ON closure.gid = rel.gid
            )
            SELECT gid FROM closure
        """, (list(group_ids),))
        return {row[0] for row in self.env.cr.fetchall()}

    def _user_closure(self, user):
        return self._live_closure(user.group_ids.ids)

    def _plain_internal_user(self, tag):
        """A user holding `base.group_user` and no healthcare group at all."""
        user = new_test_user(
            self.env, login='sh2_%s_%s' % (tag, uuid.uuid4().hex[:5]),
            password='sh2_probe_password', groups='base.group_user')
        self.assertNotIn(
            self.healthcare_base.id, self._user_closure(user),
            'fixture problem: a base.group_user-only user still reaches '
            'group_healthcare_base — the probe cannot see the defect')
        return user

    # ------------------------------------------------------------------
    # The edge itself
    # ------------------------------------------------------------------
    def test_sh2_00_the_inverted_edge_is_gone(self):
        """The one row this phase deletes: (gid=1, hid=346)."""
        self.env.cr.execute(
            "SELECT 1 FROM res_groups_implied_rel WHERE gid = %s AND hid = %s",
            (self.base_user_group.id, self.healthcare_base.id))
        self.assertFalse(
            self.env.cr.fetchall(),
            'res_groups_implied_rel still holds base.group_user -> '
            'group_healthcare_base — the SH-2 migration did not apply')

        self.assertNotIn(
            self.healthcare_base.id,
            self._live_closure([self.base_user_group.id]),
            'group_healthcare_base is STILL reachable from base.group_user')

    def test_sh2_00b_the_declared_direction_survives(self):
        """346 → 1 is the direction the XML asks for and must stay."""
        self.assertIn(
            self.base_user_group.id,
            self._live_closure([self.healthcare_base.id]),
            'group_healthcare_base no longer implies base.group_user — the '
            'deletion took the wrong row')

    def test_sh2_00c_scope_discipline_only_one_edge_removed(self):
        """Eleven other forward edges of base.group_user are load-bearing.

        `1 → 7` (`base.group_no_one`) especially: every tenant-admin guard on
        this database checks group_no_one on DIRECT containment only, precisely
        because base.group_user implies it. An implementer "tidying up all of
        base.group_user's forward edges" would invalidate that reasoning.

        The count of remaining edges is deployment-specific (it depends on
        which optional addons are installed), so the exact before/after count
        is evidence for the report's psql snapshot, not for an assertion here.
        What IS invariant is which edge went and which one stayed.
        """
        self.env.cr.execute(
            "SELECT hid FROM res_groups_implied_rel WHERE gid = %s",
            (self.base_user_group.id,))
        forward = {row[0] for row in self.env.cr.fetchall()}
        self.assertNotIn(self.healthcare_base.id, forward)
        self.assertIn(self.env.ref('base.group_no_one').id, forward,
                      '1 -> base.group_no_one was removed; every tenant-admin '
                      'guard checks it on DIRECT containment only')

    # ------------------------------------------------------------------
    # T5.2 — the negative on the clinical-note entry surface
    # ------------------------------------------------------------------
    def test_sh2_t52_notes_wizard_denied_to_plain_internal_user(self):
        """`health.fso.clinical.notes.wizard` was granted to 346 at full
        `1,1,1,1` — a clinical-note entry surface every internal user could
        reach. Not in the ticket; found by the SH-2 blast-radius measurement.
        """
        if NOTES_WIZARD not in self.env:
            self.skipTest(
                '%s is not installed on this database (health_fieldservice '
                'absent) — nothing to assert' % NOTES_WIZARD)
        user = self._plain_internal_user('t52')
        with self.assertRaises(AccessError):
            self.env[NOTES_WIZARD].with_user(user).search([], limit=1)

    def test_sh2_t52b_ews_score_denied_to_plain_internal_user(self):
        """The ticket's headline ACL, asserted here too so the guard does not
        depend on health_web_leads being installed (T5.1 is its twin)."""
        if 'health.ews.score' not in self.env:
            self.skipTest('health.ews.score is not installed')
        user = self._plain_internal_user('t52b')
        with self.assertRaises(AccessError):
            self.env['health.ews.score'].with_user(user).search([], limit=1)

    # ------------------------------------------------------------------
    # T5.3 — the ten doctors still reach 346 after the role repair
    # ------------------------------------------------------------------
    def _doctor_bundle(self):
        """The Doctor role, as the Access home holds it.

        The repair this file guards was made against the previous access
        application's row. That row is gone; the same fact is now the Doctor
        BUNDLE, which carries the same permission group and is the thing the
        clinicians actually hold. The assertion did not change — only where the
        Doctor role is written down.
        """
        if 'biz.access.role' not in self.env:
            return None
        return self.env.ref(DOCTOR_ROLE_XMLID, raise_if_not_found=False)

    def test_sh2_t53_doctor_role_grants_the_doctor_group(self):
        role = self._doctor_bundle()
        if not role:
            self.skipTest('the Access home is not installed on this database')
        self.assertIn(
            self.doctor_group, role.sudo().group_ids,
            'the Doctor role still grants base.group_user and nothing else — '
            'the ten doctors are locked out')

    def test_sh2_t53b_every_doctor_role_user_still_reaches_346(self):
        """Assert via the LIVE closure, not by reading XML (§5.88 rule a).

        "The doctors" are the people whose JOB is the Doctor role — the field
        that replaced the previous application's one-role-per-person pointer —
        rather than everybody who happens to hold the bundle (an owner holds
        it too, and an owner is not a doctor).
        """
        role = self._doctor_bundle()
        if not role:
            self.skipTest('the Access home is not installed on this database')
        users = self.env['res.users'].sudo().search(
            [('job_role_id', '=', role.id), ('active', '=', True)])
        if not users:
            self.skipTest('nobody on this database is employed as a doctor')
        for user in users:
            with self.subTest(login=user.login):
                self.assertIn(
                    self.doctor_group.id, user.all_group_ids.ids,
                    '%s did not receive %s from the role repair'
                    % (user.login, DOCTOR_GROUP_XMLID))
                self.assertIn(
                    self.healthcare_base.id, self._user_closure(user),
                    '%s no longer reaches group_healthcare_base' % user.login)

    def test_sh2_t53c_the_ten_named_clinicians_are_covered(self):
        """The specific logins §5.1 enumerated, checked by name.

        `test_sh2_t53b` already covers the live roster whatever it contains;
        this one is the named tripwire, so that a clinician quietly dropping
        off the role is a red test rather than a silent loss of access.
        """
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        present = Users.search([('login', 'in', list(DOCTOR_LOGINS))])
        if not present:
            self.skipTest(
                'none of the ten SH-2 clinician logins exist here — not the '
                'deployment this phase repaired')
        for user in present:
            with self.subTest(login=user.login):
                self.assertIn(
                    self.healthcare_base.id, self._user_closure(user),
                    '%s lost healthcare access — the Doctor-role repair did '
                    'not cover this clinician' % user.login)
        self.assertEqual(
            sorted(present.mapped('login')), sorted(DOCTOR_LOGINS),
            'the §5.1 clinician roster changed; missing: %s'
            % sorted(set(DOCTOR_LOGINS) - set(present.mapped('login'))))

    # ------------------------------------------------------------------
    # T5.6 — the seven accounts no longer reach 346
    # ------------------------------------------------------------------
    def test_sh2_t56_the_seven_no_longer_reach_346(self):
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        for login in UNUSED_LOGINS:
            user = Users.search([('login', '=', login)], limit=1)
            if not user:
                continue
            with self.subTest(login=login):
                self.assertNotIn(
                    self.healthcare_base.id, self._user_closure(user),
                    '%s still reaches group_healthcare_base' % login)

    # ------------------------------------------------------------------
    # T5.7 — archived, not deleted; partners untouched
    # ------------------------------------------------------------------
    def test_sh2_t57_the_seven_are_archived_and_their_partners_are_not(self):
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        found = Users.search([('login', 'in', list(UNUSED_LOGINS))])
        self.assertEqual(
            len(found), len(UNUSED_LOGINS),
            'a user row disappeared — SH-2 archives, it never deletes. '
            'Present: %s' % sorted(found.mapped('login')))
        for user in found:
            with self.subTest(login=user.login):
                self.assertFalse(
                    user.active, '%s was not archived' % user.login)
                self.assertTrue(
                    user.partner_id.active,
                    'res.partner %s (id %s) was archived too — the partner is '
                    'referenced by historical documents and must stay active'
                    % (user.partner_id.name, user.partner_id.id))
