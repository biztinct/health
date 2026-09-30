# -*- coding: utf-8 -*-
"""WS-1 — the booking screen on the Workspace kit (docs/handovers/WORKSPACE_WS1_BOOKING.md §5).

The booking screen (`view_health_fso_form_ops`) was restructured onto the
Workspace kit: identity row, journey, one Next step banner, masonry cards that
fold when empty, and a pinned rail. It moves and restyles; it must not change
what a user may do or when. These tests pin exactly that:

  1  every anchor the seven inheriting views need still resolves
  2  the combined arch still carries what each installed extension adds
  3  no field that loaded before stopped loading (committed "before" lists)
  4  header buttons: same names, same invisible/groups/confirm; nine in More
  5  the kit skeleton is there, once, and the fold tray names real things
  6  the old tiles and rail are gone from THIS view only
  7  the CMS consolidation rule (lazy booking tabs) still holds
  8  every new string has a Vietnamese translation that actually loads
  9  no new user-visible string says "Odoo"

The "before" fixtures below were captured from the live `carejiox` view
(id 5015) on 2026-09-29, before B1, with `get_combined_arch()`.
"""
import ast
import os
import re

from lxml import etree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

VIEW = 'health_fieldservice.view_health_fso_form_ops'
STANDARD_VIEW = 'health_fieldservice.view_health_fieldservice_order_form'

# ── §2: anchors the inheriting views resolve against THIS view's own arch ──
ANCHORS = {
    'health_invoicing': [
        "//field[@name='currency_id']",
        "//header/button[@name='action_check_and_open_quote_if_needed']",
        "//div[@name='draft_create_quote_card']",
        "//div[@name='draft_create_quote_card']//button[@name='action_create_and_open_quote']",
        "//div[@name='draft_confirm_client_card']",
        "//div[@name='draft_confirm_client_card']//div[contains(@class,'vu-action-card__subtitle')]",
        "//div[@name='draft_confirm_client_card']//button[@name='action_confirm_booking']",
        "//div[@name='location_details_card']",
        "//div[@name='quote_invoice_card']//field[@name='invoice_state']",
        "//div[@name='staff_assignments_card']",
        "//button[@name='action_view_all_invoices']",
    ],
    'health_redinvoice': ["//button[@name='action_view_all_invoices']"],
    'advanced_pricing': ["//page[@name='overview']"],
    'health_migration': ["//div[@name='location_details_card']"],
    'health_careplan': ['//notebook'],
    'health_family_link': ['//notebook'],
    'health_telehealth': ['//header', '//notebook'],
}

# ── §5.2: what each installed extension contributes to the combined arch ──
EXTENSION_MARKERS = {
    'health_invoicing': ['action_prepay_quote', 'payment_summary_card'],
    'health_telehealth': ['action_tele_join', 'telehealth_ops'],
    'health_redinvoice': ['action_open_red_invoice'],
    'advanced_pricing': ['name="pricing"'],
    'health_careplan': ['visit_tasks_ops'],
    'health_family_link': ['family_updates_ops'],
    'health_migration': ['legacy_audit_card'],
}

# ── §4.2 fixture: <field name> set of the view's OWN arch, before B1 ──
OWN_FIELDS_BEFORE = {
    'active', 'actual_duration', 'actual_duration_display', 'actual_end_datetime',
    'actual_start_datetime', 'adjusted_end_datetime', 'after_hours_charge',
    'assigned_doctor_ids', 'assigned_equipment_ids', 'assigned_staff_ids',
    'assignment_count', 'assignment_ids', 'booking_timezone', 'booking_user_id',
    'cancellation_date', 'cancellation_notes', 'cancellation_reason_id', 'cancelled_by',
    'category_of_service_id', 'clinical_note_count', 'clinical_note_ids',
    'clinical_notes_submitted', 'commission_amount', 'commission_due_to',
    'commission_duration', 'commission_percentage', 'communication_ids',
    'completion_notes', 'create_date', 'crm_lead_id', 'currency_id', 'deleted',
    'equipment_charge', 'equipment_checklist_complete', 'facility_id', 'follow_up_date',
    'follow_up_notes', 'follow_up_required', 'gps_coordinates', 'has_staff_assigned',
    'intake_notes', 'invoice_count', 'invoice_id', 'invoice_state', 'invoice_submitted',
    'is_read', 'lead_staff_id', 'message', 'message_type', 'name', 'operations_manager_id',
    'parking_charge', 'patient_address_display', 'patient_age',
    'patient_catchment_province_id', 'patient_code', 'patient_email', 'patient_id',
    'patient_national_id', 'patient_notes', 'patient_phone', 'priority', 'quote_count',
    'quote_state', 'referring_doctor_id', 'required_equipment', 'required_equipment_ids',
    'sale_order_id', 'scheduled_datetime', 'scheduled_duration', 'sender_id',
    'service_fee_vnd', 'service_location', 'service_rating', 'service_timer_active',
    'service_type', 'state', 'team_id', 'total_price', 'travel_charge', 'travel_distance',
    'travel_time_minutes', 'urgency_charge', 'urgency_level',
}

# ...and what the installed extensions added on top of it (combined arch)
EXTENSION_FIELDS_BEFORE = {
    'health_invoicing': {
        'amount', 'collected_by_id', 'display_name', 'insurance_claim_id',
        'is_invoice_paid', 'is_invoiced', 'is_package_service', 'outstanding_amount',
        'package_ids', 'payment_method', 'payment_transaction_count',
        'payment_transaction_ids', 'status', 'total_paid_amount', 'transaction_date',
        'transaction_type',
    },
    'health_migration': {
        'legacy_booking_ref', 'legacy_created_by', 'legacy_modified_by',
        'legacy_modified_on', 'legacy_owner',
    },
    'advanced_pricing': {'pricing_breakdown_html'},
    'health_redinvoice': {'red_invoice_state'},
    'health_telehealth': {'telehealth_session_state'},
}

# ── §4.3 fixture: header buttons before B1 — name: (invisible, groups, confirm) ──
OWN_BUTTONS_BEFORE = {
    'action_manual_assign_staff': ("state != 'confirmed'", None, None),
    'action_start_service': ("state != 'assigned' or not assignment_ids", None, None),
    'action_open_duplicate_booking_wizard': ("state in ('cancelled', 'closed')", None, None),
    'action_open_reschedule_wizard': (
        "state in ('completed', 'completed_pending_invoice', 'cancelled', 'closed')", None, None),
    'action_cancel_booking': (
        "state in ('completed', 'completed_pending_invoice', 'cancelled', 'closed')", None,
        'Are you sure you want to cancel this booking?'),
    'action_open_new_booking_wizard': (None, None, None),
    'action_ai_assign_staff': ('True', None, None),
    'action_check_and_open_quote_if_needed': (
        '1', 'health_base.group_healthcare_operations_manager', None),
    'action_open_delete_wizard': ('deleted', None, None),
    'action_open_restore_wizard': ('not deleted', 'health_base.group_healthcare_custodian', None),
    'action_open_archive_wizard': (
        'deleted or not active', 'health_base.group_healthcare_custodian', None),
    'action_open_unarchive_wizard': ('active', 'health_base.group_healthcare_custodian', None),
}
EXTENSION_BUTTONS_BEFORE = {
    'health_invoicing': {
        'action_prepay_quote': (
            "state in ('draft', 'completed', 'completed_pending_invoice', 'cancelled', 'closed') "
            "or not sale_order_id or is_invoice_paid",
            'health_invoicing.group_health_invoicing_user', None),
        'action_complete_service_with_payment': (
            "state != 'in_progress' or is_invoiced",
            'health_invoicing.group_health_invoicing_user', None),
    },
    'health_telehealth': {
        'action_tele_join': ("telehealth_session_state != 'open'", None, None),
    },
}
WS_MORE_BUTTONS = {
    'action_manual_assign_staff', 'action_start_service',
    'action_open_duplicate_booking_wizard', 'action_cancel_booking',
    'action_open_new_booking_wizard', 'action_open_delete_wizard',
    'action_open_restore_wizard', 'action_open_archive_wizard',
    'action_open_unarchive_wizard',
}
PRIMARY_CLASSES = {'oe_highlight', 'btn-primary'}

BOOKING_TABS = ('visit_tasks_ops', 'family_updates_ops', 'telehealth_ops')

# Files this phase wrote (user-visible strings live in them)
NEW_JS = {
    'health_theme': ['static/src/js/ws_journey.js', 'static/src/js/ws_fold_tray.js',
                     'static/src/js/ws_statusbar_more.js'],
    'health_fieldservice': ['static/src/js/ws_booking_glance.js'],
}
NEW_XML = {
    'health_theme': ['static/src/xml/ws_journey.xml', 'static/src/xml/ws_fold_tray.xml',
                     'static/src/xml/ws_statusbar_more.xml'],
    'health_fieldservice': ['static/src/xml/ws_booking_glance.xml'],
}
NEW_SCSS = [
    ('health_theme', 'static/src/scss/ws_workspace.scss'),
    ('health_fieldservice', 'static/src/scss/ops_booking_form.scss'),
]
# journey labels are handed to _t() at render from the arch attribute
JOURNEY_LABELS = ['Created', 'Confirmed', 'Assigned', 'In progress', 'Completed', 'Closed']
# arch text this phase introduced on the booking view
# (plain terms only — a title with an icon span beside it is ONE markup term,
#  covered by test_08b against the database instead)
NEW_ARCH_TERMS = ['Next step', 'People', 'Quick actions', 'Created', 'Deleted', 'Archived',
                  'Urgent', 'Emergency', 'Home Visit', 'Clinic Visit', 'Teleconsultation',
                  'Hospital Visit', 'Lab Visit', 'Rescheduled']
# worded terms of the booking view that were untranslated before WS-1 and stay so
# (the catalogue's msgstr for "min" is "min"; "km" is a unit)
UNTRANSLATED_OK = {'min', 'km'}

T_CALL = re.compile(r'''_t\(\s*(["'])((?:\\.|(?!\1).)*)\1''')
TRANSLATABLE_ATTRS = ('string', 'title', 'placeholder', 'help', 'confirm', 'alt', 'aria-label')


def _read(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


def _po_entries(module):
    """msgid -> (msgstr, [occurrence lines]) for the module's vi_VN catalogue."""
    body = _read(module, 'i18n/vi_VN.po')
    out = {}
    for block in body.split('\n\n'):
        lines = block.strip().split('\n')
        mid = next((l for l in lines if l.startswith('msgid "')), None)
        mstr = next((l for l in lines if l.startswith('msgstr "')), None)
        if not mid or not mstr:
            continue
        key = mid[len('msgid "'):-1].replace('\\"', '"')
        val = mstr[len('msgstr "'):-1].replace('\\"', '"')
        out[key] = (val, [l[3:] for l in lines if l.startswith('#: ')])
    return out


def _template_strings(xml_text):
    """Text nodes + translatable attributes of an OWL template file."""
    root = etree.fromstring(xml_text.encode())
    out = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        for attr in TRANSLATABLE_ATTRS:
            if el.get(attr):
                out.append(el.get(attr))
        for text in (el.text, el.tail):
            if text and text.strip() and re.search(r'[A-Za-z]', text):
                out.append(text.strip())
    return out


@tagged('post_install', '-at_install')
class TestWsBookingForm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.view = cls.env.ref(VIEW)
        cls.own = etree.fromstring(cls.view.arch.encode())
        cls.combined = etree.fromstring(cls.view.get_combined_arch())
        cls.installed = set(cls.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))

    # 1 ────────────────────────────────────────────────────────────────────
    def test_01_every_extension_anchor_resolves(self):
        for module, xpaths in ANCHORS.items():
            for xp in xpaths:
                with self.subTest(module=module, xpath=xp):
                    self.assertTrue(self.own.xpath(xp),
                                    '%s anchors on %s — gone from the booking view' % (module, xp))
        # invoicing hangs its hidden money fields after the FIRST currency_id:
        # it must still be the hidden dependency block, not a card field
        first = self.own.xpath("//field[@name='currency_id']")[0]
        self.assertEqual(first.get('invisible'), '1')
        self.assertEqual(first.getparent().tag, 'sheet')

    # 2 ────────────────────────────────────────────────────────────────────
    def test_02_combined_arch_carries_every_installed_extension(self):
        arch = self.view.get_combined_arch()
        checked = 0
        for module, markers in EXTENSION_MARKERS.items():
            if module not in self.installed:
                continue
            for marker in markers:
                with self.subTest(module=module, marker=marker):
                    self.assertIn(marker, arch)
                    checked += 1
        self.assertTrue(checked, 'no extension installed — the test measured nothing')
        # the cards added "after location_details_card" land in the Overview pack
        for card in ('payment_summary_card', 'legacy_audit_card'):
            nodes = self.combined.xpath("//div[@name='%s']" % card)
            if nodes:
                self.assertTrue(nodes[0].xpath("ancestor::div[contains(@class,'ws-pack')]"),
                                '%s should sit in the Overview card pack' % card)
        # the Red Invoice quick action lands in the Shortcuts panel
        for node in self.combined.xpath("//button[@name='action_open_red_invoice']"):
            self.assertTrue(node.xpath("ancestor::div[contains(@class,'ws-panel--links')]"))

    # 3 ────────────────────────────────────────────────────────────────────
    def test_03_no_field_stopped_loading(self):
        own_after = {n.get('name') for n in self.own.xpath('//field')}
        missing = OWN_FIELDS_BEFORE - own_after
        self.assertFalse(missing, 'fields dropped from the booking view: %s' % sorted(missing))
        combined_after = {n.get('name') for n in self.combined.xpath('//field')}
        for module, names in EXTENSION_FIELDS_BEFORE.items():
            if module in self.installed:
                gone = names - combined_after
                self.assertFalse(gone, '%s fields no longer load: %s' % (module, sorted(gone)))

    # 4 ────────────────────────────────────────────────────────────────────
    def test_04_header_buttons_keep_their_conditions(self):
        own_buttons = {b.get('name'): b for b in self.own.xpath('//header/button')}
        for name, (invisible, groups, confirm) in OWN_BUTTONS_BEFORE.items():
            with self.subTest(button=name):
                self.assertIn(name, own_buttons)
                b = own_buttons[name]
                self.assertEqual((b.get('invisible'), b.get('groups'), b.get('confirm')),
                                 (invisible, groups, confirm))
        combined_buttons = {b.get('name'): b for b in self.combined.xpath('//header/button')}
        for module, table in EXTENSION_BUTTONS_BEFORE.items():
            if module not in self.installed:
                continue
            for name, (invisible, groups, confirm) in table.items():
                with self.subTest(button=name):
                    b = combined_buttons[name]
                    self.assertEqual((b.get('invisible'), b.get('groups'), b.get('confirm')),
                                     (invisible, groups, confirm))
        # the nine go under More, and none of them keeps a primary colour
        for name in WS_MORE_BUTTONS:
            classes = set((own_buttons[name].get('class') or '').split())
            self.assertIn('ws-more', classes, name)
            self.assertFalse(classes & PRIMARY_CLASSES, name)
        # the banner owns the one primary: no header button of THIS view has one
        for name, b in own_buttons.items():
            self.assertFalse(set((b.get('class') or '').split()) & PRIMARY_CLASSES, name)
        # and the ones that stay inline stay inline
        self.assertNotIn('ws-more', own_buttons['action_open_reschedule_wizard'].get('class') or '')

    # 5 ────────────────────────────────────────────────────────────────────
    def test_05_workspace_skeleton(self):
        self.assertIn('ws-workspace', (self.own.get('class') or '').split())
        sheet = self.own.xpath('//sheet')[0]

        def count(cls):
            return len(sheet.xpath(".//div[contains(concat(' ', normalize-space(@class), ' '), ' %s ')]" % cls))

        for cls in ('ws-page', 'ws-main', 'ws-rail'):
            self.assertEqual(count(cls), 1, cls)
        self.assertEqual(len(sheet.xpath(".//widget[@name='ws_journey']")), 1)
        trays = sheet.xpath(".//widget[@name='ws_fold_tray']")
        self.assertEqual(len(trays), 1)
        cards = ast.literal_eval(trays[0].get('options'))['cards']
        self.assertEqual(set(cards), {'care_team_card', 'commission_fees_card',
                                      'additional_charges_card', 'notes_card'})
        model_fields = self.env['health.fieldservice.order']._fields
        for card, names in cards.items():
            with self.subTest(card=card):
                self.assertEqual(len(self.own.xpath("//div[@name='%s']" % card)), 1)
                for name in names:
                    self.assertIn(name, model_fields)
        # the journey only names states the model has
        journey = sheet.xpath(".//widget[@name='ws_journey']")[0]
        states = {k for k, _v in model_fields['state']._description_selection(self.env)}
        for step in journey.get('steps').split(','):
            self.assertIn(step, states)
        for name in filter(None, journey.get('date_fields').split(',')):
            self.assertIn(name, model_fields)
        # the rail and the main column hold what the handover places there
        self.assertTrue(sheet.xpath(".//div[contains(@class,'ws-rail')]//widget[@name='ws_booking_glance'][@mode='glance']"))
        self.assertTrue(sheet.xpath(".//div[contains(@class,'ws-rail')]//widget[@name='ws_booking_glance'][@mode='attention']"))
        self.assertTrue(sheet.xpath(".//div[contains(@class,'ws-rail')]//div[contains(@class,'vu-client-card')]"))
        self.assertEqual(len(sheet.xpath(".//div[contains(@class,'ws-next')]//widget[@name='ws_booking_hint']")), 7)
        # chatter still at the bottom, outside the sheet
        self.assertEqual(self.own.xpath('/form/*')[-1].tag, 'chatter')

    # 6 ────────────────────────────────────────────────────────────────────
    def test_06_old_tiles_and_rail_gone_from_this_view_only(self):
        own_text = etree.tostring(self.own, encoding='unicode')
        self.assertNotIn('vu_progress_rail', own_text)
        self.assertNotIn('vu-quick-info', own_text)
        standard = self.env.ref(STANDARD_VIEW).get_combined_arch()
        self.assertIn('vu_progress_rail', standard, 'the standard form is a non-goal — untouched')

    # 7 ────────────────────────────────────────────────────────────────────
    def test_07_booking_tabs_stay_lazy_widgets(self):
        """Mirror of health_cms_coverage T3/T9 on the new arch (that suite
        runs too; this keeps the rule next to the change that could break it)."""
        for page_name in BOOKING_TABS:
            pages = self.combined.xpath('//page[@name="%s"]' % page_name)
            if not pages:
                continue  # its module is not installed on this database
            self.assertTrue(pages[0].xpath('.//widget'))
            self.assertFalse(pages[0].xpath('.//field'))
        # every page the view had before is still there, same order after Overview
        names = [p.get('name') for p in self.own.xpath('//notebook/page')]
        self.assertEqual(names, ['overview', 'clinical_notes', 'planning', 'execution',
                                 'tracking', 'cancellation', 'completion', 'communication'])

    # 8 ────────────────────────────────────────────────────────────────────
    def test_08_every_new_string_is_translated(self):
        for module in ('health_theme', 'health_fieldservice'):
            po = _po_entries(module)
            wanted = []
            for rel in NEW_JS[module]:
                wanted += [(m.group(2), rel) for m in T_CALL.finditer(_read(module, rel))]
            for rel in NEW_XML[module]:
                wanted += [(s, rel) for s in _template_strings(_read(module, rel))]
            if module == 'health_theme':
                wanted += [(label, 'static/src/js/ws_journey.js') for label in JOURNEY_LABELS]
            self.assertTrue(wanted)
            for msgid, rel in wanted:
                with self.subTest(module=module, msgid=msgid):
                    self.assertIn(msgid, po, '%s: no Vietnamese for %r' % (module, msgid))
                    msgstr, occurrences = po[msgid]
                    self.assertTrue(msgstr, msgid)
                    self.assertIn('code:addons/%s/%s:0' % (module, rel), occurrences)
        po = _po_entries('health_fieldservice')
        for term in NEW_ARCH_TERMS:
            with self.subTest(term=term):
                self.assertIn(term, po)
                self.assertTrue(po[term][0])
                self.assertIn('model_terms:ir.ui.view,arch_db:%s' % VIEW, po[term][1])
        # …and the web catalogue really serves them at runtime (ledger §5.134)
        from odoo.tools.translate import code_translations
        served = {m['id']: m['string'] for m in
                  code_translations.get_web_translations('health_fieldservice', 'vi_VN')['messages']}
        self.assertEqual(served.get('Needs attention'), 'Cần chú ý')
        served = {m['id']: m['string'] for m in
                  code_translations.get_web_translations('health_theme', 'vi_VN')['messages']}
        self.assertEqual(served.get('More'), 'Thêm')
        self.assertEqual(served.get('Not filled yet'), 'Chưa điền')

    def test_08b_every_worded_term_of_the_view_reads_vietnamese(self):
        """A view term is the WHOLE inline run of a block (icon span + title is
        one term), so a plain msgid can silently never match. Ask the database
        what a Vietnamese reader actually gets."""
        if not self.env['res.lang'].search([('code', '=', 'vi_VN')]):
            self.skipTest('Vietnamese is not installed on this database')
        from odoo.tools.translate import xml_translate
        view = self.view
        en = view.with_context(lang='en_US').arch_db
        vi = view.with_context(lang='vi_VN').arch_db
        terms = []
        xml_translate(terms.append, en)
        table = view._fields['arch_db'].get_translation_dictionary(en, {'vi_VN': vi})
        missing = sorted({
            t for t in terms
            if re.search(r'[A-Za-z]{2}', re.sub(r'<[^>]+>', '', t))
            and table.get(t, {}).get('vi_VN', t) == t
            and re.sub(r'<[^>]+>', '', t).strip() not in UNTRANSLATED_OK
        })
        self.assertFalse(missing, 'booking view terms with no Vietnamese: %s' % missing)

    # 9 ────────────────────────────────────────────────────────────────────
    def test_09_no_new_user_visible_string_names_the_framework(self):
        needle = re.compile(r'\bodoo\b', re.IGNORECASE)
        strings = []
        for module, rels in NEW_JS.items():
            for rel in rels:
                strings += [m.group(2) for m in T_CALL.finditer(_read(module, rel))]
        for module, rels in NEW_XML.items():
            for rel in rels:
                strings += _template_strings(_read(module, rel))
        # the booking view's own arch: text + translatable attributes
        for el in self.own.iter():
            if not isinstance(el.tag, str):
                continue
            strings += [el.get(a) for a in TRANSLATABLE_ATTRS if el.get(a)]
            strings += [t.strip() for t in (el.text, el.tail) if t and t.strip()]
        # Vietnamese for the new files and for this view's terms
        for module in ('health_theme', 'health_fieldservice'):
            mine = ['code:addons/%s/%s:0' % (module, rel)
                    for rel in NEW_JS[module] + NEW_XML[module]]
            mine.append('model_terms:ir.ui.view,arch_db:%s' % VIEW)
            strings += [msgstr for msgstr, occ in _po_entries(module).values()
                        if set(occ) & set(mine)]
        self.assertTrue(strings)
        leaks = sorted({s for s in strings if needle.search(s)})
        self.assertFalse(leaks, 'user-visible strings naming the framework: %s' % leaks)
        # and the matcher would catch a real one
        self.assertTrue(needle.search('Powered by Odoo'))

    # 10 ───────────────────────────────────────────────────────────────────
    def test_10_new_stylesheets_keep_the_compiler_rules(self):
        """No min()/max()/clamp() in a plain property (libsass kills the whole
        bundle, ledger §5.68/§5.148), no gradients (flat mono rule)."""
        math = re.compile(r'(?<![\w-])(min|max|clamp)\(')
        for module, rel in NEW_SCSS:
            for lineno, line in enumerate(_read(module, rel).splitlines(), start=1):
                code = line.split('//', 1)[0]
                with self.subTest(file=rel, line=lineno):
                    if math.search(code):
                        self.assertTrue(code.strip().startswith('--'),
                                        'CSS math outside a custom property: %s' % line.strip())
        kit = _read('health_theme', 'static/src/scss/ws_workspace.scss')
        self.assertNotIn('gradient(', kit)
        booking_ws = _read('health_fieldservice', 'static/src/scss/ops_booking_form.scss').split('WORKSPACE (WS-1)')[1]
        self.assertNotIn('gradient(', booking_ws)
