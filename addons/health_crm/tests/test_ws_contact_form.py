# -*- coding: utf-8 -*-
"""WS-3 — the CRM contact screen on the Workspace kit
(docs/handovers/WORKSPACE_WS3_CONTACT.md §5).

The CMS contact screen (`view_crm_contact_form_crm_center`) was restructured
onto the Workspace kit: identity row, a journey on contact_status, one Next
step banner, packed Overview cards and a pinned rail; the controller's old
identity header (and its Book / Log Activity / Escalate / Spam buttons) left
the chrome template, and the four actions became header buttons calling the
same methods. It moves and restyles; it must not change what a user may do.

  1  the Web Attribution anchor resolves; the combined arch still carries the
     web-leads and Google Ads additions
  2  no field that loaded before stopped loading (committed "before" list)
  3  header buttons: lifecycle four unchanged except `ws-more`; the four
     contact actions call the controller's methods; Spam under More
  4  the kit skeleton is there, once; journey attrs; widgets; People; the
     contact history outside .ws-page; first page `overview`
  5  the chrome template lost the profile header; nothing t-inherits it
  6  every contact status maps to a journey step, alias or terminal
  7  X1 label; X2 msgstrs in the owning catalogues; new strings translated,
     the contact view reads Vietnamese at the database; no "Odoo"
  8  the journey keeps the booking's cancelled chip (P5 must be inert there)

The "before" fixtures were read from the committed arch (git HEAD affc82af),
which is what carejiox served on 2026-09-29.
"""
import os
import re

from lxml import etree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

VIEW = 'health_crm.view_crm_contact_form_crm_center'

# ── §4.2 fixture: <field name> set of the view's OWN arch, before WS-3 ──
OWN_FIELDS_BEFORE = {
    'active', 'alley_number', 'apartment_number', 'building_name', 'catchment_province_id',
    'catchment_province_name', 'client_name', 'client_representative_id', 'clinical_priority',
    'contact_datetime', 'contact_outcome', 'contact_relationship_type', 'contact_source',
    'contact_status', 'contact_tag_ids', 'contact_type', 'contacting_on_behalf', 'day_open',
    'deleted', 'distance_from_clinic', 'district_id', 'duplicate_lead_count', 'email_from',
    'emergency_contact_id', 'full_vietnamese_address', 'healthcare_lead_source', 'house_number',
    'lead_reason_id', 'mode_of_contact_id', 'name', 'named_area', 'patient_id', 'phone',
    'preferred_language', 'primary_caregiver_id', 'primary_payer_id', 'reason_for_contact_id',
    'referrer_id', 'service_interest_id', 'service_requirements', 'street', 'sub_alley_number',
    'unique_contact_code', 'vietnamese_channel', 'ward_commune', 'zip',
}

# ...and what the two installed extensions add (their own archs, unchanged)
EXTENSION_FIELDS = {
    'health_web_leads': {'web_needs_review', 'city_conflict', 'city_source', 'web_form_id',
                         'external_submission_id', 'web_landing_url', 'web_touchpoint_ids',
                         'gclid', 'web_consent_bridged'},
    'health_google_ads': {'google_ads_origin', 'google_ads_match_status', 'wbraid', 'gbraid'},
}

# ── §4.3 fixture: lifecycle header buttons before — name: (invisible, groups) ──
LIFECYCLE_BEFORE = {
    'action_open_delete_wizard': ('deleted', None),
    'action_open_restore_wizard': ('not deleted', 'health_base.group_healthcare_custodian'),
    'action_open_archive_wizard': ('deleted or not active', 'health_base.group_healthcare_custodian'),
    'action_open_unarchive_wizard': ('active', 'health_base.group_healthcare_custodian'),
}
# the methods the old controller buttons called (crm_contact_form.js)
CONTROLLER_ACTIONS = {
    'action_convert_to_booking': False,   # Book — inline
    'action_log_as_lead': False,          # Log activity — inline
    'action_escalate_contact': False,     # Escalate — inline
    'action_mark_spam': True,             # Mark as spam — under More
}
PAGES_BEFORE = ['client_details', 'address', 'relationships', 'more_details']

NEW_JS = ['static/src/js/ws_contact_panels.js']
NEW_XML = ['static/src/xml/ws_contact_panels.xml']
# plain arch terms this phase introduced on the contact view
NEW_ARCH_TERMS = ['Book', 'Log activity', 'Escalate', 'Mark as spam', 'First contact',
                  'Overview', 'How they reached us', 'Status', 'People', 'Handled by',
                  'Nobody yet', 'Linked client', 'Not linked yet',
                  'Created at the first booking.', 'Deleted', 'Archived']
# worded view terms that rightly stay as they are in Vietnamese: "Email" is
# the word Vietnamese uses (pre-existing on this view, unchanged by WS-3)
UNTRANSLATED_OK = {'Email'}
JOURNEY_LABELS = {'New': 'Mới', 'Following up': 'Đang theo dõi', 'Booked': 'Đã đặt lịch',
                  'Client': 'Khách hàng'}

# X2 — known wrong/missing Vietnamese on the three screens, by OWNING module
X2 = [
    ('health_invoicing', 'vi_VN.po', 'Pay Quote', 'Thanh toán báo giá'),
    ('health_fieldservice', 'vi_VN.po',
     '<strong><i class="fa fa-exclamation-triangle"/> ALLERGIES:</strong>',
     '<strong><i class="fa fa-exclamation-triangle"/> DỊ ỨNG:</strong>'),
    ('health_base', 'vi_VN.po', 'Gender', 'Giới tính'),
    ('advanced_pricing', 'vi_VN.po', 'Pricing', 'Giá'),
    ('health_careplan', 'vi.po', 'Visit Tasks', 'Nhiệm vụ theo lần khám'),
    ('health_family_link', 'vi.po', 'Family Updates', 'Cập nhật cho gia đình'),
    ('health_telehealth', 'vi.po', 'Telehealth', 'Khám từ xa'),
    ('health_fieldservice', 'vi_VN.po', 'Staff Overview', 'Tổng quan nhân viên'),
    ('health_fieldservice', 'vi_VN.po', 'Extra charges total', 'Tổng phụ phí'),
    ('health_crm', 'vi_VN.po', 'Book', 'Đặt lịch'),
]
# the occurrence each X2 label needs to reach the screen it is read on
X2_OCCURRENCES = {
    ('health_base', 'Gender'): 'model:ir.model.fields,field_description:health_base.field_res_partner__gender_id',
    ('advanced_pricing', 'Pricing'): 'model_terms:ir.ui.view,arch_db:advanced_pricing.view_health_fso_form_ops_pricing',
    ('health_careplan', 'Visit Tasks'): 'model_terms:ir.ui.view,arch_db:health_careplan.view_ops_booking_visit_tasks_tab',
    ('health_family_link', 'Family Updates'): 'model_terms:ir.ui.view,arch_db:health_family_link.view_ops_booking_family_tab',
    ('health_telehealth', 'Telehealth'): 'model_terms:ir.ui.view,arch_db:health_telehealth.view_fso_form_ops_telehealth',
    ('health_fieldservice', 'Staff Overview'): 'code:addons/health_fieldservice/static/src/xml/booking_side_sheet.xml:0',
    ('health_fieldservice', 'Extra charges total'): 'model_terms:ir.ui.view,arch_db:health_fieldservice.view_health_fso_form_ops',
}

T_CALL = re.compile(r'''_t\(\s*(["'])((?:\\.|(?!\1).)*)\1''')
TRANSLATABLE_ATTRS = ('string', 'title', 'placeholder', 'help', 'confirm', 'alt', 'aria-label')


def _read(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


def _po_entries(module, filename='vi_VN.po'):
    """msgid -> (msgstr, [occurrence lines]) for a module's catalogue."""
    body = _read(module, 'i18n/' + filename)
    out = {}
    for block in body.split('\n\n'):
        lines = block.strip().split('\n')

        def joined(key):
            i = next((n for n, l in enumerate(lines) if l.startswith(key + ' "')), None)
            if i is None:
                return None
            parts = [lines[i][len(key) + 1:]]
            for l in lines[i + 1:]:
                if not l.startswith('"'):
                    break
                parts.append(l)
            return ''.join(p[1:-1] for p in parts).replace('\\"', '"').replace('\\n', '\n')

        mid, mstr = joined('msgid'), joined('msgstr')
        if mid is None or mstr is None:
            continue
        out[mid] = (mstr, [l[3:] for l in lines if l.startswith('#: ')])
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


def _classes(el):
    return (el.get('class') or '').split()


@tagged('post_install', '-at_install')
class TestWsContactForm(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.view = cls.env.ref(VIEW)
        cls.own = etree.fromstring(cls.view.arch.encode())
        cls.combined = etree.fromstring(cls.view.get_combined_arch())
        cls.installed = set(cls.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))

    # 1 ────────────────────────────────────────────────────────────────────
    def test_01_extension_anchor_and_additions(self):
        self.assertEqual(len(self.own.xpath("//page[@name='more_details']")), 1)
        names = {f.get('name') for f in self.combined.iter('field')}
        pages = [p.get('name') for p in self.combined.iter('page')]
        if 'health_web_leads' in self.installed:
            self.assertIn('web_attribution', pages)
            # it still lands right after More Details
            self.assertEqual(pages[pages.index('more_details') + 1], 'web_attribution')
            self.assertTrue(EXTENSION_FIELDS['health_web_leads'] <= names,
                            EXTENSION_FIELDS['health_web_leads'] - names)
        if 'health_google_ads' in self.installed:
            self.assertTrue(EXTENSION_FIELDS['health_google_ads'] <= names,
                            EXTENSION_FIELDS['health_google_ads'] - names)

    # 2 ────────────────────────────────────────────────────────────────────
    def test_02_no_field_stopped_loading(self):
        names = {f.get('name') for f in self.own.iter('field')}
        self.assertTrue(OWN_FIELDS_BEFORE <= names,
                        'fields that stopped loading: %s' % sorted(OWN_FIELDS_BEFORE - names))
        fields = self.env['crm.lead']._fields
        for name in names:
            self.assertIn(name, fields, name)

    # 3 ────────────────────────────────────────────────────────────────────
    def test_03_header_buttons(self):
        buttons = {b.get('name'): b for b in self.own.xpath('/form/header/button')}
        for name, (invisible, groups) in LIFECYCLE_BEFORE.items():
            with self.subTest(button=name):
                b = buttons[name]
                self.assertEqual(b.get('invisible'), invisible)
                self.assertEqual(b.get('groups'), groups)
                self.assertIsNone(b.get('confirm'))
                self.assertIn('ws-more', _classes(b))
        for name, under_more in CONTROLLER_ACTIONS.items():
            with self.subTest(button=name):
                b = buttons[name]
                self.assertEqual(b.get('type'), 'object')
                self.assertTrue(hasattr(self.env['crm.lead'], name), name)
                self.assertEqual('ws-more' in _classes(b), under_more)
                # drawn for a saved contact, as the controller's header was
                self.assertEqual(b.get('invisible'), 'not id')
                self.assertIsNone(b.get('groups'))
                self.assertFalse({'oe_highlight', 'btn-primary'} & set(_classes(b)))
        # the controller called action_mark_spam, NOT the navigating variant
        self.assertNotIn('action_mark_spam_and_home', buttons)
        self.assertEqual(set(buttons), set(LIFECYCLE_BEFORE) | set(CONTROLLER_ACTIONS))
        # the controller still has the methods (kept one phase), same names
        js = _read('health_crm', 'static/src/js/crm_contact_form.js')
        for name in CONTROLLER_ACTIONS:
            self.assertIn('"%s"' % name, js)

    # 4 ────────────────────────────────────────────────────────────────────
    def test_04_workspace_skeleton(self):
        self.assertIn('ws-workspace', _classes(self.own))
        sheet = self.own.find('sheet')
        for cls in ('ws-page', 'ws-main', 'ws-rail', 'ws-hero', 'ws-next'):
            with self.subTest(cls=cls):
                self.assertEqual(len(sheet.xpath(".//div[contains(concat(' ', @class, ' '), ' %s ')]" % cls)), 1)
        journeys = self.own.xpath("//widget[@name='ws_journey']")
        self.assertEqual(len(journeys), 1)
        j = journeys[0]
        self.assertEqual(j.get('state_field'), 'contact_status')
        self.assertEqual(j.get('steps'), 'active,lead,booking,existing')
        self.assertEqual(j.get('terminal'), 'lost_booking,spam')
        self.assertEqual(j.get('aliases'), 'thinking:lead,recontact:lead,service_used:existing')
        steps = j.get('steps').split(',')
        dates = j.get('date_fields').split(',')
        self.assertEqual(len(steps), len(dates))
        for name in filter(None, dates):
            self.assertIn(name, self.env['crm.lead']._fields)
        rail = sheet.xpath(".//div[contains(concat(' ', @class, ' '), ' ws-rail ')]")[0]
        self.assertEqual({w.get('mode') for w in rail.xpath(".//widget[@name='ws_contact_glance']")},
                         {'glance', 'attention'})
        self.assertEqual(len(self.own.xpath("//widget[@name='ws_contact_next']")), 1)
        self.assertEqual(len(rail.xpath(".//div[@name='people_panel']")), 1)
        people = rail.xpath(".//div[@name='people_panel']")[0]
        self.assertTrue(people.xpath(".//field[@name='patient_id']"))
        self.assertTrue(people.xpath(".//field[@name='user_id']"))
        # the contact history: once, below the page, never inside it
        timelines = self.own.xpath("//widget[@name='contact_timeline']")
        self.assertEqual(len(timelines), 1)
        self.assertFalse(timelines[0].xpath("ancestor::div[contains(concat(' ', @class, ' '), ' ws-page ')]"))
        # the notes feed: the form's last child, after the sheet (the timeline
        # shows no notes and is refused for most people — see the arch)
        self.assertEqual(self.own.xpath('/form/*')[-1].tag, 'chatter')
        hide = re.compile(r'\.o-mail-(Form-chatter|ChatterContainer)[^{]*\{\s*display:\s*none', re.S)
        self.assertFalse(hide.search(_read('health_crm', 'static/src/scss/crm_contact_form.scss')))
        # first tab Overview, then the four old pages, same order
        pages = [p.get('name') for p in self.own.iter('page')]
        self.assertEqual(pages, ['overview'] + PAGES_BEFORE)
        # the ribbons became chips
        self.assertFalse(self.own.xpath("//widget[@name='web_ribbon']"))

    # 5 ────────────────────────────────────────────────────────────────────
    def test_05_chrome_template_lost_the_profile_header(self):
        chrome = _read('health_crm', 'static/src/xml/crm_contact_form.xml')
        for gone in ('crm-profile-header', 'crm-ph-', 'headerState', 'actionBook', 'actionMarkSpam'):
            self.assertNotIn(gone, chrome)
        for kept in ('crm-breadcrumb', 'FormStatusIndicator'):
            self.assertIn(kept, chrome)
        js = _read('health_crm', 'static/src/js/crm_contact_form.js')
        mounted = js.split('onMounted(')[1].split('});')[0]
        self.assertNotIn('_loadHeaderData', mounted)
        # nothing in any addon t-inherits the controller template any more
        addons = os.path.dirname(get_module_path('health_crm'))
        for root, _dirs, files in os.walk(addons):
            if '/static/src' not in root + '/':
                continue
            for fn in files:
                if not fn.endswith('.xml'):
                    continue
                with open(os.path.join(root, fn), encoding='utf-8', errors='ignore') as fh:
                    text = fh.read()
                self.assertNotIn('t-inherit="health_crm.CrmContactFormView"', text, fn)

    # 6 ────────────────────────────────────────────────────────────────────
    def test_06_every_status_has_a_place_on_the_journey(self):
        j = self.own.xpath("//widget[@name='ws_journey']")[0]
        steps = set(j.get('steps').split(','))
        aliases = dict(p.split(':') for p in j.get('aliases').split(','))
        terminal = set(j.get('terminal').split(','))
        self.assertTrue(set(aliases.values()) <= steps)
        selection = self.env['crm.lead']._fields['contact_status'].get_values(self.env)
        self.assertTrue(selection)
        for value in selection:
            with self.subTest(status=value):
                self.assertTrue(value in steps or value in aliases or value in terminal,
                                '%s would render a blank journey' % value)

    # 7 ────────────────────────────────────────────────────────────────────
    def test_07_labels_and_vietnamese(self):
        # X1 — the booking Pricing card's total_price reads as what it is
        booking = etree.fromstring(self.env.ref('health_fieldservice.view_health_fso_form_ops').arch.encode())
        card = booking.xpath("//div[@name='commission_fees_card']//field[@name='total_price']")
        self.assertEqual([f.get('string') for f in card], ['Extra charges total'])
        # X2 — each fixed in the catalogue of the module that owns it
        for module, fn, msgid, msgstr in X2:
            if module not in self.installed:
                continue
            with self.subTest(module=module, msgid=msgid):
                po = _po_entries(module, fn)
                self.assertIn(msgid, po)
                self.assertEqual(po[msgid][0], msgstr)
                occ = X2_OCCURRENCES.get((module, msgid))
                if occ:
                    self.assertIn(occ, po[msgid][1])
        # new strings: every _t literal / template string has Vietnamese with
        # its code occurrence; the arch terms have the view occurrence
        po = _po_entries('health_crm')
        wanted = []
        for rel in NEW_JS:
            wanted += [(m.group(2), rel) for m in T_CALL.finditer(_read('health_crm', rel))]
        for rel in NEW_XML:
            wanted += [(s, rel) for s in _template_strings(_read('health_crm', rel))]
        self.assertTrue(wanted)
        for msgid, rel in wanted:
            with self.subTest(msgid=msgid):
                self.assertIn(msgid, po, 'no Vietnamese for %r' % msgid)
                self.assertTrue(po[msgid][0], msgid)
                self.assertIn('code:addons/health_crm/%s:0' % rel, po[msgid][1])
        for term in NEW_ARCH_TERMS:
            with self.subTest(term=term):
                self.assertIn(term, po)
                self.assertTrue(po[term][0])
                self.assertIn('model_terms:ir.ui.view,arch_db:%s' % VIEW, po[term][1])
        theme = _po_entries('health_theme')
        for en, vi in JOURNEY_LABELS.items():
            with self.subTest(label=en):
                self.assertEqual(theme[en][0], vi)
                self.assertIn('code:addons/health_theme/static/src/js/ws_journey.js:0', theme[en][1])
        # …and the web catalogue really serves them at runtime (ledger §5.134)
        from odoo.tools.translate import code_translations
        served = {m['id']: m['string'] for m in
                  code_translations.get_web_translations('health_crm', 'vi_VN')['messages']}
        self.assertEqual(served.get('No outcome recorded yet.'), 'Chưa ghi nhận kết quả.')
        self.assertEqual(served.get('Open client'), 'Mở hồ sơ khách hàng')
        served = {m['id']: m['string'] for m in
                  code_translations.get_web_translations('health_theme', 'vi_VN')['messages']}
        self.assertEqual(served.get('Following up'), 'Đang theo dõi')

    def test_07b_every_worded_term_of_the_view_reads_vietnamese(self):
        """A view term is the WHOLE inline run of a block (ledger §5.246): ask
        the database, not the file."""
        if not self.env['res.lang'].search([('code', '=', 'vi_VN')]):
            self.skipTest('Vietnamese is not installed on this database')
        from odoo.tools.translate import xml_translate
        en = self.view.with_context(lang='en_US').arch_db
        vi = self.view.with_context(lang='vi_VN').arch_db
        terms = []
        xml_translate(terms.append, en)
        table = self.view._fields['arch_db'].get_translation_dictionary(en, {'vi_VN': vi})
        missing = sorted({
            t for t in terms
            if re.search(r'[A-Za-z]{2}', re.sub(r'<[^>]+>', '', t))
            and table.get(t, {}).get('vi_VN', t) == t
            and re.sub(r'<[^>]+>', '', t).strip() not in UNTRANSLATED_OK
        })
        self.assertFalse(missing, 'terms with no Vietnamese: %s' % missing)

    def test_07c_no_new_user_visible_string_names_the_framework(self):
        needle = re.compile(r'\bodoo\b', re.IGNORECASE)
        strings = []
        for rel in NEW_JS:
            strings += [m.group(2) for m in T_CALL.finditer(_read('health_crm', rel))]
        for rel in NEW_XML:
            strings += _template_strings(_read('health_crm', rel))
        for el in self.own.iter():
            if not isinstance(el.tag, str):
                continue
            strings += [el.get(a) for a in TRANSLATABLE_ATTRS if el.get(a)]
            strings += [t.strip() for t in (el.text, el.tail) if t and t.strip()]
        mine = {'code:addons/health_crm/%s:0' % rel for rel in NEW_JS + NEW_XML}
        mine.add('model_terms:ir.ui.view,arch_db:%s' % VIEW)
        strings += [msgstr for msgstr, occ in _po_entries('health_crm').values() if set(occ) & mine]
        for module, fn, _msgid, msgstr in X2:
            strings.append(msgstr)
        self.assertTrue(strings)
        leaks = sorted({s for s in strings if needle.search(s)})
        self.assertFalse(leaks, 'user-visible strings naming the framework: %s' % leaks)
        self.assertTrue(needle.search('Powered by Odoo'))

    # 8 ────────────────────────────────────────────────────────────────────
    def test_08_journey_is_inert_on_the_booking(self):
        """P5: without `terminal` the widget renders exactly as before — the
        booking's cancelled chip is still the literal template text, and the
        booking arch names no terminal."""
        xml = _read('health_theme', 'static/src/xml/ws_journey.xml')
        self.assertIn('<span t-if="isCancelled" class="ws-journey__chip">Cancelled</span>', xml)
        js = _read('health_theme', 'static/src/js/ws_journey.js')
        self.assertIn('return !this.props.terminal && this.rawState === "cancelled";', js)
        booking = self.env.ref('health_fieldservice.view_health_fso_form_ops').arch
        widget = etree.fromstring(booking.encode()).xpath("//widget[@name='ws_journey']")[0]
        self.assertIsNone(widget.get('terminal'))
        self.assertEqual(widget.get('aliases'), 'completed_pending_invoice:completed')

    def test_09_stylesheets_keep_the_compiler_rules(self):
        """No min()/max()/clamp() outside a custom property (libsass, ledger
        §5.68/§5.148); no gradients; the icons the screen names have masks."""
        math = re.compile(r'(?<![\w-])(min|max|clamp)\(')
        sheets = [('health_crm', 'static/src/scss/crm_contact_form.scss'),
                  ('health_theme', 'static/src/scss/ws_workspace.scss')]
        for module, rel in sheets:
            text = _read(module, rel)
            self.assertNotIn('gradient(', text)
            for lineno, line in enumerate(text.splitlines(), start=1):
                code = line.split('//', 1)[0]
                with self.subTest(file=rel, line=lineno):
                    if math.search(code):
                        self.assertTrue(code.strip().startswith('--'), line.strip())
        kit = _read('health_theme', 'static/src/scss/ws_workspace.scss')
        used = set(re.findall(r'data-icon="([a-z0-9-]+)"', self.view.arch))
        used |= set(re.findall(r"'(info|alert-triangle)'", _read('health_crm', NEW_XML[0])))
        for name in used:
            with self.subTest(icon=name):
                self.assertIn('"%s"' % name, kit + _read('health_theme', 'static/src/scss/backend_02_chatter_components.scss'))
            self.assertTrue(os.path.exists(os.path.join(
                get_module_path('health_theme'), 'static/src/img/lucide/%s.svg' % name)), name)
