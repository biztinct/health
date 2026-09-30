# -*- coding: utf-8 -*-
"""WS-2 — the client screen on the Workspace kit (docs/handovers/WORKSPACE_WS2_CLIENT.md §5).

The ops client screen (`view_health_patient_form_ops`) was restructured onto
the Workspace kit: identity row, notices, one Next step banner, masonry cards
that fold when empty, a Recent visits card and a pinned rail; the old identity
header, six stat tiles and action sidebar left the controller template. It
moves and restyles; it must not change what a user may do or when. These
tests pin exactly that:

  1  the anchors the inheriting views need still resolve (incl. People)
  2  the combined arch still carries every extension tab, and the main contact
     sits in the People panel
  3  no field that loaded before stopped loading (committed "before" lists)
  4  header buttons: same names/invisible/groups; all four under More
  5  the kit skeleton is there, once; the fold tray names real things; chatter
  6  get_client_profile_data returns next_visit / last_visit / recent_visits
  7  the chrome template lost the old header/tiles/sidebar, and nothing still
     t-inherits it against a class that is gone
  8  the two chatter-hide rules are gone
  9  every new string has Vietnamese that loads; no "Odoo" in them
 10  stylesheets keep the compiler rules

The "before" fixtures were captured from the carejiox view (id 5026) on
2026-09-29, before C1, with `get_combined_arch()` on a practice copy.
"""
import ast
import datetime
import glob
import os
import re

from lxml import etree

from odoo import fields
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

VIEW = 'health_fieldservice.view_health_patient_form_ops'

# ── §2: anchors the inheriting views resolve against THIS view's own arch ──
ANCHORS = {
    'health_invoicing': [
        "//page[@name='active_packages']//p[contains(@class,'text-muted')]",
        "//page[@name='financial_summary']//div[@class='bj-bookings-section']",
    ],
    'health_crm': ["//div[@name='people_panel']"],
    'health_twin': ['//notebook'],
    'health_cms_clinical': ['//notebook'],
    'health_bhyt': ['//notebook'],
    'health_careplan': ['//notebook'],
    'health_family_messages': ['//notebook'],
    'health_self_booking': ['//notebook'],
    'health_condition': ['//notebook'],
    'health_portal': ['//notebook'],
}

# ── the tab each installed extension adds ──
EXTENSION_PAGES = {
    'health_twin': ['twin_trends_ops'],
    'health_cms_clinical': ['vitals_thresholds_ops', 'consents_ops'],
    'health_bhyt': ['bhyt_ops'],
    'health_careplan': ['careplans_ops'],
    'health_family_messages': ['family_ops'],
    'health_self_booking': ['booking_links_ops'],
    'health_condition': ['diagnoses_ops'],
    'health_portal': ['portal_access_ops'],
}

# ── §4.2 fixture: <field name> set of the view's OWN arch, before C1 ──
OWN_FIELDS_BEFORE = {
    'active', 'address_search', 'age_display', 'allergies', 'amount_residual',
    'amount_total', 'birth_date', 'blood_group', 'booking_ids', 'catchment_province_id',
    'clinic_distance_display', 'clinic_drive_distance_km', 'clinic_drive_minutes',
    'commission_due_to', 'credit', 'date_localization', 'debit', 'deceased', 'deleted',
    'deleted_reason_id', 'email', 'estimated_duration', 'ethnicity', 'first_name',
    'gender_id', 'geo_coordinates_display', 'insurance_expiry', 'insurance_number',
    'insurance_provider', 'intake_diagnosis', 'intake_goal_of_care', 'intake_notes',
    'intake_referring_doctor_id', 'intake_required_equipment', 'invoice_date',
    'invoice_ids', 'is_patient', 'last_name', 'last_visit_date', 'lead_staff_id',
    'medical_history', 'middle_name', 'mobile', 'name', 'national_id', 'next_visit_date',
    'partner_latitude', 'partner_longitude', 'patient_category_id', 'patient_code_display',
    'patient_status', 'payment_method', 'payment_state', 'phone', 'primary_facility_id',
    'profession', 'referral_source', 'registration_date', 'scheduled_datetime',
    'service_type', 'source_details', 'source_type', 'state', 'timeline_html', 'title',
    'total_invoiced', 'vietnamese_address', 'vietnamese_name', 'visit_count',
}

# ...and what each installed extension added on top of it (their own archs)
EXTENSION_FIELDS_BEFORE = {
    'health_invoicing': {
        'active_packages_count', 'amount', 'currency_id', 'display_name', 'payment_method',
        'recent_payment_ids', 'remaining_prepaid_value', 'status', 'total_prepaid_value',
        'transaction_date',
    },
    'health_crm': {'allowed_main_contact_ids', 'main_contact_id', 'main_contact_phone'},
    'health_bhyt': {
        'bhyt_beneficiary_code', 'bhyt_coverage_rate', 'bhyt_provider_id',
        'bhyt_registered_facility', 'bhyt_valid', 'insurance_expiry', 'insurance_number',
    },
    'health_cms_clinical': {
        'active', 'consent_ids', 'consent_summary', 'consent_type_id', 'effective_date',
        'escalation_action', 'expiry_date', 'granted_by_partner_id', 'max_value', 'method',
        'min_value', 'name', 'notes', 'severity', 'state', 'vitals_threshold_ids',
        'vitals_type_id',
    },
}

# ── §4.3 fixture: header buttons before C1 — name: (invisible, groups, confirm) ──
BUTTONS_BEFORE = {
    'action_open_delete_wizard': ('deleted', None, None),
    'action_open_restore_wizard': ('not deleted', 'health_base.group_healthcare_custodian', None),
    'action_open_archive_wizard': ('deleted or not active', 'health_base.group_healthcare_custodian', None),
    'action_open_unarchive_wizard': ('active', 'health_base.group_healthcare_custodian', None),
}

# ── §4.2: the notebook's page order before C1 (own arch) ──
PAGES_BEFORE = ['profile_overview', 'bookings_journey', 'address_info', 'intake_notes',
                'insurance_billing', 'active_packages', 'healthcare_relationships',
                'clinical_notes', 'financial_summary']

CLIENT_WIDGETS = ('ws_client_next', 'ws_client_glance', 'ws_client_visits', 'ws_client_shortcuts')

# Files this phase wrote (user-visible strings live in them)
NEW_JS = {
    'health_fieldservice': ['static/src/js/ws_client_panels.js'],
    'health_invoicing': ['static/src/js/client_package_patch.js'],
}
NEW_XML = {
    'health_fieldservice': ['static/src/xml/ws_client_panels.xml'],
}
NEW_SCSS = [
    ('health_fieldservice', 'static/src/scss/ops_client_profile_form.scss'),
    ('health_fieldservice', 'static/src/scss/ops_client_profile.scss'),
]
# plain arch terms this phase introduced on the client view
NEW_ARCH_TERMS = ['Overview', 'Personal', 'Contact', 'Care', 'Identity', 'Commission',
                  'People', 'Active', 'Inactive', 'Referrer', 'Deceased', 'New booking']

# The header's own standing action (added with the Quick-actions rethink): it is
# the one primary button and is NOT under More.
HEADER_PRIMARY = 'action_open_quick_booking_owl'
CRM_VIEW = 'health_crm.view_health_patient_form_ops_crm_maincontact'
# worded terms of the client view that need no translation: this placeholder
# is ALREADY Vietnamese ("Vietnamese name"), so it rightly maps to itself
UNTRANSLATED_OK = {'Tên tiếng Việt'}

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
class TestWsClientForm(TransactionCase):

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
                                    '%s anchors on %s — gone from the client view' % (module, xp))
        # the People panel is ONE div, in the rail
        panels = self.own.xpath("//div[@name='people_panel']")
        self.assertEqual(len(panels), 1)
        self.assertTrue(panels[0].xpath("ancestor::div[contains(@class,'ws-rail')]"))
        # health_crm's view now targets the People panel, not a banner
        crm = self.env.ref(CRM_VIEW, raise_if_not_found=False)
        if crm:
            self.assertIn("people_panel", crm.arch)
            self.assertNotIn("alert alert-danger", crm.arch)

    # 2 ────────────────────────────────────────────────────────────────────
    def test_02_combined_arch_carries_every_extension(self):
        checked = 0
        for module, pages in EXTENSION_PAGES.items():
            if module not in self.installed:
                continue
            for page in pages:
                with self.subTest(module=module, page=page):
                    self.assertTrue(self.combined.xpath('//notebook/page[@name="%s"]' % page))
                    checked += 1
        self.assertTrue(checked, 'no extension installed — the test measured nothing')
        if 'health_crm' in self.installed:
            self.assertTrue(self.combined.xpath(
                "//div[@name='people_panel']//field[@name='main_contact_id']"),
                'the main contact picker must sit in the People panel')
        if 'health_invoicing' in self.installed:
            self.assertTrue(self.combined.xpath(
                "//page[@name='active_packages']//widget[@name='vu_active_packages']"))
            self.assertTrue(self.combined.xpath(
                "//page[@name='financial_summary']//field[@name='recent_payment_ids']"))

    # 3 ────────────────────────────────────────────────────────────────────
    def test_03_no_field_stopped_loading(self):
        own_after = {n.get('name') for n in self.own.xpath('//field')}
        missing = OWN_FIELDS_BEFORE - own_after
        self.assertFalse(missing, 'fields dropped from the client view: %s' % sorted(missing))
        combined_after = {n.get('name') for n in self.combined.xpath('//field')}
        for module, names in EXTENSION_FIELDS_BEFORE.items():
            if module in self.installed:
                gone = names - combined_after
                self.assertFalse(gone, '%s fields no longer load: %s' % (module, sorted(gone)))
        # the notebook keeps every page, same names, same order
        self.assertEqual([p.get('name') for p in self.own.xpath('//notebook/page')], PAGES_BEFORE)

    # 4 ────────────────────────────────────────────────────────────────────
    def test_04_header_buttons_keep_their_conditions(self):
        own_buttons = {b.get('name'): b for b in self.own.xpath('//header/button')}
        self.assertEqual(set(own_buttons), set(BUTTONS_BEFORE) | {HEADER_PRIMARY})
        primary = own_buttons[HEADER_PRIMARY]
        self.assertEqual(primary.get('type'), 'object')
        self.assertIn('oe_highlight', (primary.get('class') or '').split())
        self.assertNotIn('ws-more', (primary.get('class') or '').split())
        self.assertTrue(hasattr(self.env['res.partner'], HEADER_PRIMARY))
        # first in the header: the kit paints only the first visible button primary
        self.assertEqual(self.own.xpath('//header/button')[0].get('name'), HEADER_PRIMARY)
        for name, (invisible, groups, confirm) in BUTTONS_BEFORE.items():
            with self.subTest(button=name):
                b = own_buttons[name]
                self.assertEqual((b.get('invisible'), b.get('groups'), b.get('confirm')),
                                 (invisible, groups, confirm))
                self.assertIn('ws-more', (b.get('class') or '').split())

    # 5 ────────────────────────────────────────────────────────────────────
    def test_05_workspace_skeleton(self):
        self.assertIn('ws-workspace', (self.own.get('class') or '').split())
        self.assertIn('ops-client-profile-form', (self.own.get('class') or '').split())
        sheet = self.own.xpath('//sheet')[0]

        def count(cls):
            return len(sheet.xpath(".//div[contains(concat(' ', normalize-space(@class), ' '), ' %s ')]" % cls))

        for cls in ('ws-page', 'ws-main', 'ws-rail', 'ws-hero', 'ws-next'):
            self.assertEqual(count(cls), 1, cls)
        for widget in CLIENT_WIDGETS:
            self.assertTrue(sheet.xpath(".//widget[@name='%s']" % widget), widget)
        rail = sheet.xpath(".//div[contains(@class,'ws-rail')]")[0]
        modes = [w.get('mode') for w in rail.xpath(".//widget[@name='ws_client_glance']")]
        self.assertEqual(modes, ['attention', 'glance'])
        # quick actions come first in the rail, as tiles
        self.assertEqual(rail.xpath('./widget')[0].get('name'), 'ws_client_shortcuts')
        self.assertTrue(sheet.xpath(".//div[contains(@class,'ws-next')]/widget[@name='ws_client_next']"))
        self.assertTrue(sheet.xpath(".//div[contains(@class,'ws-pack')]/widget[@name='ws_client_visits']"))
        # the fold tray names real cards and real fields
        trays = sheet.xpath(".//widget[@name='ws_fold_tray']")
        self.assertEqual(len(trays), 1)
        cards = ast.literal_eval(trays[0].get('options'))['cards']
        self.assertEqual(set(cards), {'identity_card', 'commission_card'})
        model_fields = self.env['res.partner']._fields
        for card, names in cards.items():
            with self.subTest(card=card):
                self.assertEqual(len(self.own.xpath("//div[@name='%s']" % card)), 1)
                for name in names:
                    self.assertIn(name, model_fields)
                    self.assertTrue(self.own.xpath("//div[@name='%s']//field[@name='%s']" % (card, name)))
        # allergies stay in the main column, above the tabs, never in a folding card
        allergy = sheet.xpath(".//div[contains(@class,'ws-banner--allergy')]")
        self.assertEqual(len(allergy), 1)
        self.assertEqual(allergy[0].get('invisible'), 'not allergies')
        self.assertFalse(allergy[0].xpath('ancestor::notebook'))
        # the notes feed is back: last child of the form, outside the sheet
        self.assertEqual(self.own.xpath('/form/*')[-1].tag, 'chatter')
        # the wrong label is gone
        self.assertFalse(self.own.xpath("//field[@string='Commission Duration']"))
        self.assertNotIn('Commission Duration', self.view.arch)
        # Overview is the first tab and is called Overview
        first = self.own.xpath('//notebook/page')[0]
        self.assertEqual((first.get('name'), first.get('string')), ('profile_overview', 'Overview'))

    # 6 ────────────────────────────────────────────────────────────────────
    def test_06_profile_data_next_last_recent(self):
        Partner = self.env['res.partner']
        facility = self.env['health.facility'].search([], limit=1)
        self.assertTrue(facility, 'a facility is needed to book a visit')
        province = facility.catchment_province_id
        client = Partner.create({
            'name': 'WS2 Visits Client', 'is_patient': True,
            'catchment_province_id': province.id,
        })
        lonely = Partner.create({
            'name': 'WS2 No Visits Client', 'is_patient': True,
            'catchment_province_id': province.id,
        })
        FSO = self.env['health.fieldservice.order']
        now = fields.Datetime.now()
        future = FSO.create({
            'patient_id': client.id, 'facility_id': facility.id,
            'scheduled_datetime': now + datetime.timedelta(days=5),
        })
        past = FSO.create({
            'patient_id': client.id, 'facility_id': facility.id,
            'scheduled_datetime': now - datetime.timedelta(days=10),
        })
        # states set directly: the lifecycle gates are not what this test is about
        self.env.flush_all()
        self.env.cr.execute("UPDATE health_fieldservice_order SET state='confirmed' WHERE id=%s", [future.id])
        self.env.cr.execute("UPDATE health_fieldservice_order SET state='completed' WHERE id=%s", [past.id])
        self.env.invalidate_all()

        data = Partner.get_client_profile_data(client.id)
        self.assertEqual(data['next_visit']['id'], future.id)
        self.assertEqual(data['next_visit']['name'], future.name)
        self.assertEqual(data['next_visit']['scheduled_datetime'],
                         fields.Datetime.to_string(future.scheduled_datetime))
        self.assertEqual(data['last_visit']['id'], past.id)
        recent = data['recent_visits']
        self.assertEqual([r['id'] for r in recent], [future.id, past.id], 'newest first')
        self.assertEqual(recent[1]['state'], 'completed')
        self.assertTrue(recent[1]['state_label'])
        self.assertLessEqual(len(recent), 5)
        for key in ('id', 'name', 'scheduled_datetime', 'service_type_label', 'state', 'state_label'):
            self.assertIn(key, recent[0])
        # the existing contract is untouched
        for key in ('profile', 'stats', 'bookings', 'packages', 'payments', 'timeline'):
            self.assertIn(key, data)

        empty = Partner.get_client_profile_data(lonely.id)
        self.assertIs(empty['next_visit'], False)
        self.assertIs(empty['last_visit'], False)
        self.assertEqual(empty['recent_visits'], [])

    # 7 ────────────────────────────────────────────────────────────────────
    def test_07_chrome_template_lost_the_old_header_and_nothing_hangs_on_it(self):
        chrome = _read('health_fieldservice', 'static/src/xml/ops_client_profile_form.xml')
        for gone in ('ph-kpis', 'ph-header', 'ops-cp-sidebar', 'ops-content-with-sidebar', 'ph-actions'):
            self.assertNotIn(gone, chrome)
        self.assertIn('bd-breadcrumb', chrome, 'the breadcrumb bar stays')
        self.assertIn('FormStatusIndicator', chrome, 'the save indicator stays')
        root = etree.fromstring(chrome.encode())
        classes = set()
        for el in root.iter():
            if isinstance(el.tag, str):
                classes |= set((el.get('class') or '').split())
        # every template in the repo that extends the chrome must hang on a class
        # that still exists (a dangling xpath breaks EVERY backend page)
        addons = os.path.dirname(get_module_path('health_fieldservice'))
        hooked = 0
        for path in glob.glob(os.path.join(addons, '*', 'static', 'src', '**', '*.xml'), recursive=True):
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            if 'health_fieldservice.OpsClientProfileFormView' not in text or 't-inherit' not in text:
                continue
            hooked += 1
            for cls in re.findall(r"hasclass\('([^']+)'\)", text):
                with self.subTest(file=path, cls=cls):
                    self.assertIn(cls, classes, '%s hangs on .%s, which is gone' % (path, cls))
        # health_crm's header extension is deleted with its asset lines
        crm = get_module_path('health_crm')
        if crm:
            self.assertFalse(os.path.exists(os.path.join(crm, 'static/src/xml/ops_client_profile_header.xml')))
            self.assertFalse(os.path.exists(os.path.join(crm, 'static/src/js/ops_client_profile_header.js')))
            self.assertNotIn('ops_client_profile_header', _read('health_crm', '__manifest__.py'))
        self.assertEqual(hooked, 0, 'no module extends the chrome template any more')
        # the controller no longer fetches the profile on mount (the panels do, once)
        controller = _read('health_fieldservice', 'static/src/js/ops_client_profile_form.js')
        mounted = controller.split('onMounted(', 1)[1].split('});', 1)[0]
        self.assertNotIn('_loadProfileData', mounted)
        self.assertIn('loadClientProfile', controller)

    # 8 ────────────────────────────────────────────────────────────────────
    def test_08_the_chatter_is_no_longer_hidden(self):
        hide = re.compile(r'\.o-mail-(Form-chatter|ChatterContainer)[^{]*\{\s*display:\s*none', re.S)
        for rel in ('static/src/scss/ops_booking_form.scss',
                    'static/src/scss/ops_client_profile_form.scss'):
            with self.subTest(file=rel):
                self.assertFalse(hide.search(_read('health_fieldservice', rel)))
        booking = self.env.ref('health_fieldservice.view_health_fso_form_ops').arch
        self.assertIn('<chatter', booking)

    # 9 ────────────────────────────────────────────────────────────────────
    def test_09_every_new_string_is_translated(self):
        for module in NEW_JS:
            po = _po_entries(module)
            wanted = []
            for rel in NEW_JS[module]:
                wanted += [(m.group(2), rel) for m in T_CALL.finditer(_read(module, rel))]
            for rel in NEW_XML.get(module, []):
                wanted += [(s, rel) for s in _template_strings(_read(module, rel))]
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
        if 'health_crm' in self.installed:
            crm_po = _po_entries('health_crm')
            self.assertEqual(crm_po['Main contact'][0], 'Liên hệ chính')
            self.assertIn('model_terms:ir.ui.view,arch_db:%s' % CRM_VIEW, crm_po['Main contact'][1])
        # …and the web catalogue really serves them at runtime (ledger §5.134)
        from odoo.tools.translate import code_translations
        served = {m['id']: m['string'] for m in
                  code_translations.get_web_translations('health_fieldservice', 'vi_VN')['messages']}
        self.assertEqual(served.get('Recent visits'), 'Lượt thăm gần đây')
        self.assertEqual(served.get('No visit is booked.'), 'Chưa có lịch hẹn.')
        served = {m['id']: m['string'] for m in
                  code_translations.get_web_translations('health_invoicing', 'vi_VN')['messages']}
        self.assertEqual(served.get('Buy a package'), 'Mua gói dịch vụ')

    def test_09b_every_worded_term_of_the_view_reads_vietnamese(self):
        """A view term is the WHOLE inline run of a block, so a plain msgid can
        silently never match (ledger §5.246). Ask the database."""
        if not self.env['res.lang'].search([('code', '=', 'vi_VN')]):
            self.skipTest('Vietnamese is not installed on this database')
        from odoo.tools.translate import xml_translate
        for xmlid in (VIEW, CRM_VIEW):
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if not view:
                continue
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
            with self.subTest(view=xmlid):
                self.assertFalse(missing, '%s terms with no Vietnamese: %s' % (xmlid, missing))

    def test_09c_no_new_user_visible_string_names_the_framework(self):
        needle = re.compile(r'\bodoo\b', re.IGNORECASE)
        strings = []
        for module, rels in NEW_JS.items():
            for rel in rels:
                strings += [m.group(2) for m in T_CALL.finditer(_read(module, rel))]
        for module, rels in NEW_XML.items():
            for rel in rels:
                strings += _template_strings(_read(module, rel))
        for el in self.own.iter():
            if not isinstance(el.tag, str):
                continue
            strings += [el.get(a) for a in TRANSLATABLE_ATTRS if el.get(a)]
            strings += [t.strip() for t in (el.text, el.tail) if t and t.strip()]
        for module in NEW_JS:
            mine = ['code:addons/%s/%s:0' % (module, rel)
                    for rel in NEW_JS[module] + NEW_XML.get(module, [])]
            mine.append('model_terms:ir.ui.view,arch_db:%s' % VIEW)
            strings += [msgstr for msgstr, occ in _po_entries(module).values()
                        if set(occ) & set(mine)]
        self.assertTrue(strings)
        leaks = sorted({s for s in strings if needle.search(s)})
        self.assertFalse(leaks, 'user-visible strings naming the framework: %s' % leaks)
        self.assertTrue(needle.search('Powered by Odoo'))

    # 10 ───────────────────────────────────────────────────────────────────
    def test_10_stylesheets_keep_the_compiler_rules(self):
        """No min()/max()/clamp() in a plain property (libsass kills the whole
        bundle, ledger §5.68/§5.148), no gradients in the client workspace."""
        math = re.compile(r'(?<![\w-])(min|max|clamp)\(')
        for module, rel in NEW_SCSS:
            for lineno, line in enumerate(_read(module, rel).splitlines(), start=1):
                code = line.split('//', 1)[0]
                with self.subTest(file=rel, line=lineno):
                    if math.search(code):
                        self.assertTrue(code.strip().startswith('--'),
                                        'CSS math outside a custom property: %s' % line.strip())
        client_ws = _read('health_fieldservice', 'static/src/scss/ops_client_profile_form.scss').split('WORKSPACE (WS-2)')[1]
        self.assertNotIn('gradient(', client_ws)
        # every icon the client panels name has a mask rule
        panels = _read('health_fieldservice', 'static/src/js/ws_client_panels.js') + \
            _read('health_fieldservice', 'static/src/xml/ws_client_panels.xml') + \
            _read('health_invoicing', 'static/src/js/client_package_patch.js')
        used = set(re.findall(r'icon: "([a-z0-9-]+)"', panels)) | set(re.findall(r'data-icon="([a-z0-9-]+)"', panels))
        kit = _read('health_theme', 'static/src/scss/ws_workspace.scss')
        for name in used:
            with self.subTest(icon=name):
                self.assertTrue('"%s"' % name in kit or '"%s"' % name in client_ws, name)
