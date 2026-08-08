# -*- coding: utf-8 -*-
"""Menu consolidation (19.0.1.2.0) — the sidebar shrank, nothing became
unreachable.

The consolidation retires sidebar leaves whose records are now tabs on the
client or booking record. Three things can silently go wrong, and each has a
test here:

1. A leaf is retired but its records have nowhere to live — the feature simply
   disappears from the UI. Guarded by asserting the replacement TAB exists in
   the combined arch of the ops view (T2/T3).
2. A leaf is retired and its action falls out of ``get_match_keys()``, which
   filters ``active = True``. The action stays reachable, but opening it drops
   the CMS shell and dumps the user into the bare Odoo backend. Guarded by T4.
3. An expander is left wrapping zero or one child, or a relocated child keeps
   its old parent — both produce dead or mis-nested nav. Guarded by T5/T6.

NB on arch assertions: use ``get_combined_arch()``, never ``get_view()``.
get_view postprocessing strips ``<page groups="...">`` for a user who is not a
member, and tests run as superuser — which would mask successfully merged
pages. Combined arch proves the xpath matched. (Same reasoning as
health_cms_clinical/tests/test_cms_clinical.py.)
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.health_cms_coverage.hooks import (
    ATTACH_MATCH,
    COLLAPSE,
    RELOCATE_TO_ADMIN,
    RENAME,
    RETIRE,
)

# Every tab the consolidation added, and the ops view it must appear on.
CLIENT_TABS = (
    'booking_links_ops',    # health_self_booking
    'family_ops',           # health_family_messages
    'careplans_ops',        # health_careplan
    'portal_access_ops',    # health_portal
    'diagnoses_ops',        # health_condition
)
BOOKING_TABS = (
    'telehealth_ops',       # health_telehealth
    'family_updates_ops',   # health_family_link
    'visit_tasks_ops',      # health_careplan
)


@tagged('post_install', '-at_install')
class TestCmsConsolidation(TransactionCase):

    def _ref(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    # ------------------------------------------------------------------
    # T1 — retirement is reversible: inactive, never unlinked, action intact
    # ------------------------------------------------------------------
    def test_01_retired_leaves_are_deactivated_not_deleted(self):
        for xmlid, tab in RETIRE.items():
            item = self._ref(xmlid)
            if not item:
                continue  # module not installed on this database
            self.assertFalse(
                item.active,
                '%s should be retired (its records are now %s)' % (xmlid, tab))
            self.assertTrue(
                item.action_xmlid,
                '%s must keep its action_xmlid — retirement is reversible and '
                'deep links still resolve through it' % xmlid)
            self.assertTrue(
                self.env.ref(item.action_xmlid, raise_if_not_found=False),
                '%s: the action behind a retired leaf must still exist — '
                'consolidation moves menus, it does not delete features'
                % xmlid)

    # ------------------------------------------------------------------
    # T2 — the client tabs that replace the retired client leaves exist
    # ------------------------------------------------------------------
    def test_02_client_tabs_are_on_the_ops_profile(self):
        ops_view = self.env.ref(
            'health_fieldservice.view_health_patient_form_ops')
        arch = ops_view.get_combined_arch()
        for page_name in CLIENT_TABS:
            self.assertIn(
                page_name, arch,
                '%r must be a page on the OPS client profile — the standard '
                'partner form is not what the CMS renders, so a page added '
                'there would be masked' % page_name)

    # ------------------------------------------------------------------
    # T3 — same for the booking tabs
    # ------------------------------------------------------------------
    def test_03_booking_tabs_are_on_the_ops_booking_form(self):
        ops_view = self.env.ref('health_fieldservice.view_health_fso_form_ops')
        arch = ops_view.get_combined_arch()
        for page_name in BOOKING_TABS:
            self.assertIn(
                page_name, arch,
                '%r must be a page on the OPS booking form' % page_name)

    def test_03b_join_video_reaches_the_ops_booking_form(self):
        """The Join Video button was declared only on the STANDARD FSO form,
        so it never rendered on the surface ops actually uses. Consolidation
        re-declared it on the ops view; this stops it regressing."""
        ops_view = self.env.ref('health_fieldservice.view_health_fso_form_ops')
        arch = ops_view.get_combined_arch()
        self.assertIn('action_tele_join', arch)

    # ------------------------------------------------------------------
    # T4 — no retired action falls out of the shell allowlist
    # ------------------------------------------------------------------
    def test_04_retired_actions_keep_the_cms_shell(self):
        """``get_match_keys()`` filters active=True. Every action behind a
        retired leaf must still be in that payload via ATTACH_MATCH, or the
        tab that navigates to it would drop the sidebar and strand the user in
        the bare Odoo backend."""
        xmlids = set(self.env['cms.sidebar.item'].get_match_keys()['xmlids'])
        for xmlid in RETIRE:
            item = self._ref(xmlid)
            if not item:
                continue
            # The leaf's ENTIRE match list has to survive, not just its
            # action_xmlid — a leaf can answer for several screens (e.g.
            # Patient Portal also matched the portal access LOG), and any one
            # left behind is a screen that opens outside the CMS shell.
            targets = {item.action_xmlid} | {
                v.strip() for v in (item.match_action_xmlids or '').split(',')
                if v.strip()}
            for target in targets - {False, ''}:
                if not target:
                    continue
                self.assertIn(
                    target, xmlids,
                    '%s answered for %s before it was retired; that action is '
                    'no longer in the shell allowlist, so opening it would '
                    'kick the user out of the CMS' % (xmlid, target))

    def test_04b_attach_match_targets_are_declared_on_live_hosts(self):
        """Each adopting leaf must itself be ACTIVE, or it contributes nothing
        to get_match_keys() and T4 passes only by accident."""
        for host_xmlid, action_xmlids in ATTACH_MATCH.items():
            host = self._ref(host_xmlid)
            if not host:
                continue
            self.assertTrue(
                host.active,
                '%s adopts match targets but is itself retired' % host_xmlid)
            declared = {v.strip() for v in
                        (host.match_action_xmlids or '').split(',') if v.strip()}
            for action_xmlid in action_xmlids:
                if not self.env.ref(action_xmlid, raise_if_not_found=False):
                    continue
                self.assertIn(action_xmlid, declared, host_xmlid)
            # Idempotence: consolidate_sidebar runs from BOTH post_init_hook
            # and the migration, so a second pass must not double an entry.
            raw = [v.strip() for v in
                   (host.match_action_xmlids or '').split(',') if v.strip()]
            self.assertEqual(len(raw), len(set(raw)),
                             '%s has duplicate match targets — the re-home '
                             'step is not idempotent' % host_xmlid)

    # ------------------------------------------------------------------
    # T5 — config leaves really landed in ADMIN, children detached
    # ------------------------------------------------------------------
    def test_05_config_leaves_moved_to_admin(self):
        admin = self.env.ref('health_cms_sidebar.section_admin')
        for xmlid, _sequence in RELOCATE_TO_ADMIN:
            item = self._ref(xmlid)
            if not item:
                continue
            self.assertEqual(item.section_id, admin, xmlid)
            self.assertTrue(item.active,
                            '%s is relocated, not retired' % xmlid)
            # Four of these are seeded as children of a clinical expander.
            # Moving only section_id would mis-nest them AND keep them counting
            # as that expander's children, silently blocking its collapse.
            self.assertFalse(
                item.parent_id,
                '%s must be detached from its old expander, or it keeps '
                'rendering inside it in the old section' % xmlid)

    def test_05b_hook_never_writes_an_updatable_record(self):
        """Everything this hook writes must live in a ``noupdate="1"`` seed.

        A record whose ir.model.data row is updatable gets REWRITTEN FROM XML
        on every upgrade of its owning module, silently reverting anything the
        hook wrote. Measured on UAT twice: upgrading health_web_leads dragged
        Website Connector back into CRM and wiped Campaign Review's re-homed
        match target. Both now declare the consolidated state in their own
        seed; this stops anyone re-adding them here.
        """
        Data = self.env['ir.model.data'].sudo()
        written = (
            list(RETIRE)
            + list(RENAME)
            + [x for x, _s in RELOCATE_TO_ADMIN]
            + list(ATTACH_MATCH)
            + [x for pair in COLLAPSE for x in pair]
        )
        offenders = []
        for xmlid in written:
            module, name = xmlid.split('.', 1)
            row = Data.search([('module', '=', module), ('name', '=', name)],
                              limit=1)
            if row and not row.noupdate:
                offenders.append(xmlid)
        self.assertFalse(
            offenders,
            'these records are updatable, so an upgrade of their owning module '
            'will revert what consolidate_sidebar wrote — declare the '
            'consolidated state in that module\'s own seed instead: %s'
            % offenders)

    # ------------------------------------------------------------------
    # T6 — no expander is left wrapping a single child
    # ------------------------------------------------------------------
    def test_06_collapsed_expanders_promoted_their_survivor(self):
        Item = self.env['cms.sidebar.item'].with_context(active_test=False)
        for expander_xmlid, survivor_xmlid in COLLAPSE:
            expander = self._ref(expander_xmlid)
            survivor = self._ref(survivor_xmlid)
            if not expander or not survivor:
                continue
            if expander.active:
                # Left standing on purpose: another module still contributes
                # more than one child. Then it must have >1, or it is a dead
                # one-child expander costing a pointless click.
                children = Item.search([('parent_id', '=', expander.id),
                                        ('active', '=', True)])
                self.assertGreater(
                    len(children), 1,
                    '%s is an active expander with %s active children — an '
                    'item with children never navigates, so this costs a '
                    'click for nothing' % (expander_xmlid, len(children)))
                continue
            self.assertFalse(
                survivor.parent_id,
                '%s must be promoted to a root leaf when its expander is '
                'collapsed' % survivor_xmlid)
            self.assertTrue(survivor.active, survivor_xmlid)

    def test_07_no_active_expander_is_childless(self):
        """A parent with no visible children renders as an accordion that
        opens onto nothing. Sweeps the WHOLE live catalogue, not just the
        items this module touched."""
        Item = self.env['cms.sidebar.item']
        for item in Item.search([('active', '=', True)]):
            if item.action_xmlid or item.action_tag:
                continue  # navigable leaf
            children = Item.search([('parent_id', '=', item.id),
                                    ('active', '=', True)])
            self.assertTrue(
                children,
                '%r is an expander with no action and no active children — '
                'it draws and does nothing' % item.name)

    # ------------------------------------------------------------------
    # T8 — the kept work queue was renamed, not removed
    # ------------------------------------------------------------------
    def test_08_family_inbox_survives_as_a_queue(self):
        """The per-client Family tab cannot replace the cross-client unread
        queue — without it nobody can see what needs a reply without opening
        every client in turn."""
        for xmlid, new_name in RENAME.items():
            item = self._ref(xmlid)
            if not item:
                continue
            self.assertTrue(item.active, '%s must stay a menu item' % xmlid)
            self.assertEqual(item.name, new_name, xmlid)

    # ------------------------------------------------------------------
    # T9 — the eager-load rule the tabs exist to respect
    # ------------------------------------------------------------------
    def test_09_new_tabs_add_no_x2many_to_the_ops_archs(self):
        """Tab RENDERING is lazy but tab DATA FETCHING is not: every field in
        the arch is pulled by the single web_read on page open. Each new tab
        must therefore be a lazy view_widget, never a <field> list, or it taxes
        every client/booking open for users who never click it."""
        from lxml import etree

        for view_xmlid, page_names in (
            ('health_fieldservice.view_health_patient_form_ops', CLIENT_TABS),
            ('health_fieldservice.view_health_fso_form_ops', BOOKING_TABS),
        ):
            arch = etree.fromstring(
                self.env.ref(view_xmlid).get_combined_arch())
            for page_name in page_names:
                pages = arch.xpath('//page[@name="%s"]' % page_name)
                self.assertTrue(pages, '%s: %s missing' % (view_xmlid,
                                                           page_name))
                page = pages[0]
                self.assertTrue(
                    page.xpath('.//widget'),
                    '%s must render through a lazy view_widget' % page_name)
                self.assertFalse(
                    page.xpath('.//field'),
                    '%s declares a <field>: that is fetched eagerly in the '
                    'page-open web_read and defeats the whole point of the '
                    'lazy widget' % page_name)
