from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION, WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_BREAK
from pathlib import Path


OUT = Path('/Users/adity/Documents/GitHub/health19/Health19_Omnichannel_CRM_Study_and_Implementation_Prompt.docx')
IMG_DIR = Path('/Users/adity/Documents/GitHub/health19/.codex-work/pancake-extracted/word/media')

NAVY = '0B2545'
BLUE = '0B6E99'
TEAL = '0E8A7B'
MINT = 'E8F5F2'
SKY = 'EAF4FA'
AMBER = 'B26A00'
AMBER_BG = 'FFF4DB'
RED = 'A61B2B'
RED_BG = 'FDECEF'
INK = '17212B'
MUTED = '5F6B76'
LIGHT = 'F3F6F8'
MID = 'D9E2E8'
WHITE = 'FFFFFF'


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tc_pr.append(shd)
    shd.set(qn('w:fill'), fill)


def set_cell_margins(cell, top=90, start=120, bottom=90, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in('w:tcMar')
    if tc_mar is None:
        tc_mar = OxmlElement('w:tcMar')
        tc_pr.append(tc_mar)
    for m, value in [('top', top), ('start', start), ('bottom', bottom), ('end', end)]:
        node = tc_mar.find(qn(f'w:{m}'))
        if node is None:
            node = OxmlElement(f'w:{m}')
            tc_mar.append(node)
        node.set(qn('w:w'), str(value))
        node.set(qn('w:type'), 'dxa')


def set_table_borders(table, color=MID, size='4'):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn('w:tblBorders'))
    if borders is None:
        borders = OxmlElement('w:tblBorders')
        tbl_pr.append(borders)
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        tag = f'w:{edge}'
        el = borders.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            borders.append(el)
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), size)
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement('w:tblHeader')
    tbl_header.set(qn('w:val'), 'true')
    tr_pr.append(tbl_header)


def set_table_width(table, widths):
    table.autofit = False
    total = sum(widths)
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn('w:tblW'))
    if tbl_w is None:
        tbl_w = OxmlElement('w:tblW')
        tbl_pr.append(tbl_w)
    tbl_w.set(qn('w:w'), str(int(total * 1440)))
    tbl_w.set(qn('w:type'), 'dxa')
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        grid_col = OxmlElement('w:gridCol')
        grid_col.set(qn('w:w'), str(int(width * 1440)))
        grid.append(grid_col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            width = widths[idx]
            cell.width = Inches(width)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn('w:tcW'))
            if tc_w is None:
                tc_w = OxmlElement('w:tcW')
                tc_pr.append(tc_w)
            tc_w.set(qn('w:w'), str(int(width * 1440)))
            tc_w.set(qn('w:type'), 'dxa')
            set_cell_margins(cell)


def set_font(run, size=None, bold=None, color=INK, name='Aptos'):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn('w:ascii'), name)
    run._element.get_or_add_rPr().rFonts.set(qn('w:hAnsi'), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_hyperlink(paragraph, text, url, color=BLUE, underline=True):
    part = paragraph.part
    rid = part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), rid)
    run = OxmlElement('w:r')
    r_pr = OxmlElement('w:rPr')
    c = OxmlElement('w:color')
    c.set(qn('w:val'), color)
    r_pr.append(c)
    if underline:
        u = OxmlElement('w:u')
        u.set(qn('w:val'), 'single')
        r_pr.append(u)
    r_fonts = OxmlElement('w:rFonts')
    r_fonts.set(qn('w:ascii'), 'Aptos')
    r_fonts.set(qn('w:hAnsi'), 'Aptos')
    r_pr.append(r_fonts)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '18')
    r_pr.append(sz)
    run.append(r_pr)
    text_node = OxmlElement('w:t')
    text_node.text = text
    run.append(text_node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_page_field(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run('Page ')
    set_font(run, 9, color=MUTED)
    fld_char1 = OxmlElement('w:fldChar')
    fld_char1.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = ' PAGE '
    fld_char2 = OxmlElement('w:fldChar')
    fld_char2.set(qn('w:fldCharType'), 'end')
    r = paragraph.add_run()._r
    r.append(fld_char1)
    r.append(instr)
    r.append(fld_char2)


doc = Document()
sec = doc.sections[0]
sec.page_width = Inches(8.5)
sec.page_height = Inches(11)
sec.top_margin = Inches(0.8)
sec.bottom_margin = Inches(0.78)
sec.left_margin = Inches(0.82)
sec.right_margin = Inches(0.82)
sec.header_distance = Inches(0.35)
sec.footer_distance = Inches(0.35)

styles = doc.styles
normal = styles['Normal']
normal.font.name = 'Aptos'
normal._element.rPr.rFonts.set(qn('w:ascii'), 'Aptos')
normal._element.rPr.rFonts.set(qn('w:hAnsi'), 'Aptos')
normal.font.size = Pt(10.2)
normal.font.color.rgb = RGBColor.from_string(INK)
normal.paragraph_format.space_after = Pt(5)
normal.paragraph_format.line_spacing = 1.12

for name, size, color, before, after in [
    ('Title', 29, NAVY, 0, 10),
    ('Subtitle', 13, MUTED, 0, 14),
    ('Heading 1', 18, NAVY, 16, 8),
    ('Heading 2', 13.5, BLUE, 12, 5),
    ('Heading 3', 11.5, TEAL, 8, 3),
]:
    st = styles[name]
    st.font.name = 'Aptos Display' if name in ('Title', 'Heading 1') else 'Aptos'
    st._element.rPr.rFonts.set(qn('w:ascii'), st.font.name)
    st._element.rPr.rFonts.set(qn('w:hAnsi'), st.font.name)
    st.font.size = Pt(size)
    st.font.color.rgb = RGBColor.from_string(color)
    st.font.bold = name != 'Subtitle'
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True

for sname in ('List Bullet', 'List Number'):
    st = styles[sname]
    st.font.name = 'Aptos'
    st.font.size = Pt(10.1)
    st.paragraph_format.left_indent = Inches(0.34)
    st.paragraph_format.first_line_indent = Inches(-0.18)
    st.paragraph_format.space_after = Pt(3.5)
    st.paragraph_format.line_spacing = 1.12

for sname, fill, border, color in [
    ('Callout', SKY, BLUE, NAVY),
    ('Recommendation', MINT, TEAL, NAVY),
    ('Caution', AMBER_BG, AMBER, INK),
    ('Risk', RED_BG, RED, INK),
]:
    st = styles.add_style(sname, WD_STYLE_TYPE.PARAGRAPH)
    st.font.name = 'Aptos'
    st.font.size = Pt(10.2)
    st.font.color.rgb = RGBColor.from_string(color)
    st.paragraph_format.left_indent = Inches(0.18)
    st.paragraph_format.right_indent = Inches(0.18)
    st.paragraph_format.space_before = Pt(6)
    st.paragraph_format.space_after = Pt(7)
    st.paragraph_format.line_spacing = 1.12
    p_pr = st.element.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    p_pr.append(shd)
    p_bdr = OxmlElement('w:pBdr')
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'single')
    left.set(qn('w:sz'), '18')
    left.set(qn('w:space'), '8')
    left.set(qn('w:color'), border)
    p_bdr.append(left)
    p_pr.append(p_bdr)


def add_para(text='', style=None, bold_lead=None):
    p = doc.add_paragraph(style=style)
    if bold_lead and text.startswith(bold_lead):
        a = p.add_run(bold_lead)
        set_font(a, bold=True)
        b = p.add_run(text[len(bold_lead):])
        set_font(b)
    else:
        r = p.add_run(text)
        set_font(r)
    return p


def bullet(text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    if level:
        p.paragraph_format.left_indent = Inches(0.6)
    r = p.add_run(text)
    set_font(r, 10.1)
    return p


def number(text):
    p = doc.add_paragraph(style='List Number')
    r = p.add_run(text)
    set_font(r, 10.1)
    return p


def callout(label, text, style='Callout'):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.keep_together = True
    r = p.add_run(label + '  ')
    set_font(r, 10.2, True, NAVY)
    r2 = p.add_run(text)
    set_font(r2, 10.2, False, INK)
    return p


def add_table(headers, rows, widths, font_size=8.7, header_fill=NAVY):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_repeat_table_header(table.rows[0])
    header_pr = table.rows[0]._tr.get_or_add_trPr()
    header_pr.append(OxmlElement('w:cantSplit'))
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        set_cell_shading(cell, header_fill)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(h)
        set_font(r, font_size, True, WHITE)
    for ridx, row in enumerate(rows):
        table_row = table.add_row()
        row_pr = table_row._tr.get_or_add_trPr()
        row_pr.append(OxmlElement('w:cantSplit'))
        cells = table_row.cells
        for i, val in enumerate(row):
            cell = cells[i]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if ridx % 2:
                set_cell_shading(cell, 'F8FAFB')
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.02
            r = p.add_run(str(val))
            set_font(r, font_size, i == 0, INK)
    set_table_width(table, widths)
    set_table_borders(table)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    set_font(r, 8.8, False, MUTED)
    r.italic = True


def add_picture_with_alt(path, width, title, description):
    shape = doc.add_picture(str(path), width=width)
    shape._inline.docPr.set('title', title)
    shape._inline.docPr.set('descr', description)
    return shape


def section_header(section, label='HEALTH19 | CARE COMMAND CENTER'):
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    p = section.header.paragraphs[0]
    p.clear()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(label)
    set_font(r, 8.5, True, MUTED)
    footer = section.footer.paragraphs[0]
    footer.clear()
    add_page_field(footer)


section_header(sec)

# Cover
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(42)
r = p.add_run('HEALTH19 PRODUCT STUDY')
set_font(r, 10, True, TEAL)
p = doc.add_paragraph(style='Title')
p.add_run('Care Command Center').bold = True
p = doc.add_paragraph(style='Subtitle')
p.add_run('Current evidence review of omnichannel CRM, contact-centre and healthcare communication systems — with a differentiated UX and full Odoo 19 implementation prompt')

callout('DECISION', 'Build a native, healthcare-first agent workspace inside Health19. Treat VoIP24h and Zalo OA/ZCC as first-class channels, preserve the existing CRM and booking workflows, and add a canonical interaction layer, relationship-aware identity resolution, safety-governed AI and supervisor operations.', 'Recommendation')

meta = [
    ('Prepared for', 'Health19 / VAFHS Sales Admins and Managers'),
    ('Evidence current to', '19 July 2026 (Australia/Sydney)'),
    ('Platform context', 'Odoo 19; health_crm 19.0.1.5.8; existing Zalo, VoIP24h, messaging, consent and PHI modules'),
    ('Evidence types', 'Official product documentation; attached Pancake screenshots; local repository inspection'),
]
add_table(['Field', 'Detail'], meta, [1.45, 5.05], 9.2, TEAL)

add_para('This report distinguishes product facts from design recommendations. “Verified” means supported by an official source or the supplied screenshots. “Proposed” means a Health19 product decision that still requires design, legal, security and clinical governance approval.', style='Caution')

doc.add_page_break()

doc.add_heading('1. Executive recommendation', level=1)
add_para('Health19 should create a new CRM Center entry point named Care Command. It should be the daily operating surface for Sales Admins and Managers to answer and place calls, manage chats, resolve identities, book services, coordinate follow-ups and supervise queues without moving among separate Zalo, VoIP, CRM and booking screens.')

callout('NORTH STAR', 'Within five seconds of opening any interaction, an authorised user should know: who is speaking; for whom; why now; what has already happened; what is booked; what is risky; what consent applies; and the safest next action.', 'Recommendation')

add_para('Why this is differentiated')
for t in [
    'Generic platforms centre the ticket, conversation or customer. Health19 should centre the care relationship: caller, patient/client, caregiver, payer, referrer and responsible care team are distinct entities.',
    'Generic AI summarises text. Health19 should create a structured continuity brief that reconciles conversations, calls, bookings, commitments, consent and escalation state, with citations back to source events.',
    'Generic routing optimises speed or capacity. Health19 should route using availability, workload, language, location, channel skill, continuity of ownership, patient relationship and safety constraints.',
    'Generic supervisor dashboards show volume and handle time. Health19 should add missed-care recovery, risk queues, unresolved commitments, identity conflicts, AI overrides and consent exceptions.',
]:
    bullet(t)

doc.add_heading('Recommended product shape', level=2)
add_table(
    ['Layer', 'Recommendation', 'Primary outcome'],
    [
        ('Entry point', 'CRM Center > Care Command (default daily workspace for authorised Sales/Admin roles)', 'One place to work'),
        ('Agent experience', 'Adaptive four-zone workspace: navigation, queue, interaction, patient/care rail', 'Fast context without clutter'),
        ('Manager experience', 'Live operations view, queue controls, coaching, QA and AI governance', 'Actionable supervision'),
        ('Channel core', 'Canonical conversation/interaction models; adapters for Zalo, VoIP24h, email, web chat, social and future CCaaS', 'No channel silos'),
        ('AI core', 'Continuity brief, relationship resolver, safety shield, next-best-action, live assist and wrap-up', 'Reduced cognitive load'),
        ('Trust core', 'Consent, least privilege, encryption, redaction, retention, immutable audit and human review', 'Healthcare-safe operations'),
    ],
    [1.05, 3.6, 1.85], 9.0, NAVY
)

doc.add_heading('2. Evidence method and interpretation', level=1)
add_para('The study reviewed current public documentation available on 19 July 2026, the four screenshots embedded in pancake.docx, and the Health19 repository. Product packaging changes frequently; plan-specific, regional, add-on and contractual conditions must be validated during procurement.')
add_table(
    ['Marker', 'Meaning'],
    [
        ('V', 'Verified product capability from an official vendor source listed in Appendix A.'),
        ('P', 'Visible in the user-supplied Pancake screenshot set.'),
        ('R', 'Health19 recommendation; not a claim about a competitor.'),
        ('NV', 'Not verified in the sources reviewed. This does not prove the capability is absent.'),
    ],
    [0.75, 5.75], 9.2, BLUE
)
callout('COMPLIANCE NOTE', 'HIPAA, HDS, SOC or “healthcare-ready” claims are not blanket approval. A deployment is compliant only when the exact products, features, regions, subprocessors, configuration, contract/BAA, retention, integrations and operating practices are in scope. Vietnam-specific privacy, cybersecurity, medical-record and telecom requirements require local legal review.', 'Risk')

doc.add_heading('3. Pancake screenshot review', level=1)
add_para('The screenshots show an omnichannel commerce workspace with page-level colour coding, per-page and multipage settings, round-robin assignment controls, an inbox/message/customer-information layout, conversation tags and order context. Pancake’s current public pages also describe unified conversations across Facebook, Instagram, WhatsApp, TikTok and more; its CRM describes Zalo lead sync, and its POS describes recorded call management and scheduled calls. [S01–S03]')

if (IMG_DIR / 'image4.png').exists():
    add_picture_with_alt(
        IMG_DIR / 'image4.png', Inches(6.65),
        'Pancake conversation workspace',
        'Supplied Pancake screenshot showing a three-pane agent workspace: conversation queue on the left, active chat and composer in the centre, and customer notes and order context on the right.',
    )
    add_caption('Figure 1. Supplied Pancake conversation workspace (P): list, conversation, composer/tags and commerce-oriented context rail.')

doc.add_heading('What works', level=2)
for t in [
    'Three-pane spatial model keeps the queue, active thread and context visible.',
    'Channel/page markers and avatars make high-volume scanning faster.',
    'Round-robin, online-status and re-assignment controls expose operational policy.',
    'Quick tags and reply controls support sales teams working at speed.',
]:
    bullet(t)

doc.add_heading('Where it can be materially improved for healthcare', level=2)
add_table(
    ['Observed pattern (P)', 'Operational risk', 'Health19 response (R)'],
    [
        ('Dense conversation list; colour and badges compete', 'Urgency, SLA and ownership are hard to parse', 'One dominant priority signal; semantic queue reasons; SLA countdown; keyboard triage'),
        ('Long free-form message history', 'Agents re-read; continuity depends on memory', 'Five-second Continuity Brief with evidence links and refresh state'),
        ('Right rail is notes/orders', 'No care relationship, consent or clinical escalation context', 'Patient/caller relationship card, booking timeline, consent and safety panel'),
        ('Flat tags across composer', 'Tag sprawl; inconsistent outcomes', 'Structured outcome, intent, risk, commitment and next-action controls'),
        ('Routing as a settings form', 'Difficult to predict impact or detect conflicts', 'Visual policy builder, simulation, versioning, explain-why and rollback'),
        ('Round robin dominates', 'Fairness can conflict with skill, continuity or urgency', 'Constraint-first scoring: safety > skill > continuity > SLA > workload'),
        ('Multiple page/account colour indicators', 'Colour alone is inaccessible and can become arbitrary', 'Icon + label + brand accent; never use colour as sole signal'),
        ('No visible AI provenance or clinical safety', 'Automation could appear authoritative', 'Source-grounded AI, confidence, review controls and prohibited-action policy'),
    ],
    [1.65, 2.15, 2.7], 8.7, NAVY
)

if (IMG_DIR / 'image3.png').exists():
    add_picture_with_alt(
        IMG_DIR / 'image3.png', Inches(6.6),
        'Pancake round-robin routing configuration',
        'Supplied Pancake screenshot showing round-robin assignment options, online-status and timed-reassignment controls, and per-page agent allocation lists.',
    )
    add_caption('Figure 2. Supplied Pancake routing configuration (P): rich controls, but limited hierarchy, simulation and policy explanation.')

# Landscape matrix section
matrix_sec = doc.add_section(WD_SECTION.NEW_PAGE)
matrix_sec.orientation = WD_ORIENT.LANDSCAPE
matrix_sec.page_width = Inches(11)
matrix_sec.page_height = Inches(8.5)
matrix_sec.top_margin = Inches(0.55)
matrix_sec.bottom_margin = Inches(0.55)
matrix_sec.left_margin = Inches(0.55)
matrix_sec.right_margin = Inches(0.55)
matrix_sec.header_distance = Inches(0.25)
matrix_sec.footer_distance = Inches(0.25)
section_header(matrix_sec, 'HEALTH19 | VERIFIED COMPETITOR MATRIX')

doc.add_heading('4. Cited competitor matrix', level=1)
add_para('Compact findings below are product-level, not a procurement score. “Voice” distinguishes native/in-workspace capability from partner integration. Healthcare posture is verified only where the reviewed official source makes a specific statement; otherwise it is marked NV.')

matrix = [
    ('Pancake', 'V unified messaging; Facebook, Instagram, WhatsApp, TikTok; CRM adds Zalo sync. P three-pane inbox.', 'V POS call recording/scheduling; screenshots do not show in-thread voice.', 'P round robin, online status, timed reassignment; V CRM workflows.', 'V/P central lead/contact data; AI chatbot marketed. Deep identity and agent copilot NV.', 'Manager statistics visible; healthcare claims are marketing-level, contractual privacy posture NV.', 'Best for social commerce; weak healthcare context. [S01–S03]'),
    ('Intercom', 'V shared inbox for email, chat, phone, WhatsApp, SMS and social; configurable details/Copilot rail.', 'V inbound/outbound web inbox calling; balanced call assignment.', 'V team inboxes, workflows, capacity/assignment; bot inbox separates AI work.', 'V IDs and contact merge rules; Copilot, compose, translate and per-thread summaries.', 'V reporting and Fin analysis. HIPAA BAA on Expert; AU AI data processing caveat documented.', 'Best modern inbox + AI ergonomics; phone merge limits. [S04–S08]'),
    ('Zendesk', 'V Agent Workspace unifies email, messaging, voice in one ticket with context/apps rail.', 'V Talk voice; voice AI agent is EAP and explicitly not emergency triage.', 'V capacity, SLA, priority, skill, queues, focus mode and unified presence.', 'Customer context and custom objects; AI summary, intent and agent assist.', 'Strong routing/supervisor ecosystem. HIPAA can be configured; Healthcare Agreement/settings required.', 'Best ticket operations and governance; can feel case-centric. [S09–S13]'),
    ('Salesforce Service / Agentforce', 'V unified service console and contact center across voice, WhatsApp and digital.', 'V native/partner telephony, recording/transcription and supervisor controls.', 'V Omni-Channel unified routing, skills, capacity, flows, callbacks and AI agents.', 'V Data 360 identity resolution and unified profiles; Agentforce plans/actions.', 'Enterprise command centre. HIPAA-ready features require scoped BAA/config; some features excluded.', 'Best CRM/data/workflow depth; highest configuration complexity. [S14–S19]'),
    ('Zoho Desk', 'V unified interface across 10+ channels including telephony.', 'V Zoho Voice/telephony available; exact bundle varies.', 'V direct, sequential, load and skill-based assignment with thresholds/backlog.', 'Contact/ticket context; V Zia assistance and insights.', 'Admin reporting. V BAA available; ePHI fields, encryption, RBAC and audit guidance.', 'Best value/compliance controls; less premium agent UX. [S20–S23]'),
    ('Freshdesk Omni', 'V 2025 command centre unifies email, chat, WhatsApp, Facebook and Instagram.', 'Voice within Freshdesk suite; packaging/region must be confirmed.', 'V unified admin, automation, prioritisation and Omniroute.', 'V 360 contact history and channel identifiers; Freddy replies, summaries, KB and insights.', 'Omnichannel analytics. V BAA scope includes Freshdesk/Chat/Caller/Omnichannel with mandatory config.', 'Balanced mid-market suite; verify new Omni packaging. [S24–S26]'),
    ('HubSpot Service Hub', 'V Help Desk with chat, email, WhatsApp and calling channel threads.', 'V HubSpot-number inbound calling in Help Desk; simultaneous ring.', 'V team/user, capacity and skill routing on eligible plans.', 'Strong CRM record context; Breeze customer agent/reply recommendations and handoff.', 'Service analytics. V sensitive-data controls and BAA for qualifying Enterprise customers.', 'Best CRM usability and sales/service continuity; less CCaaS depth. [S27–S31]'),
    ('Genesys Cloud CX', 'V all-in-one voice/digital interface across email, chat, voice, messaging, callbacks.', 'V carrier-grade native/BYOC voice and WEM ecosystem.', 'V standard, bullseye, preferred, direct and predictive routing by KPI.', 'CRM integrations; Agent Copilot gives next actions, knowledge, summaries and wrap-up.', 'V detailed Copilot/queue analytics and WEM. Trust centre lists HIPAA/HITRUST.', 'Best routing science and enterprise operations; heavy platform. [S32–S36]'),
    ('NICE CXone', 'V Agent Workspace handles voice and Digital Experience channels; embedded variants.', 'V integrated softphone and enterprise recording.', 'V unified/advanced routing and capacity across interaction types.', 'CRM data mapping; Copilot offers real-time/journey summaries, sentiment, KB and task assist.', 'Best-in-class WEM/QA/compliance. Trust centre supports HIPAA controls/BAA scope review.', 'Best supervisor and quality depth; complex and costly. [S37–S41]'),
    ('Twilio Flex', 'V programmable UI for voice and messaging; Conversations includes SMS, WhatsApp, chat, Messenger beta.', 'V native programmable voice/IVR.', 'V TaskRouter skills, priorities, queues, capacity, FIFO/LIFO and round robin.', 'Unified Profiles and Agent Copilot are public beta; post-work summaries/sentiment.', 'Highly customisable. Critical: Copilot and Unified Profiles are not HIPAA-eligible.', 'Best build-your-own substrate; healthcare AI exclusions are decisive. [S42–S46]'),
    ('Talkdesk', 'V Agent Workspace unifies voice, SMS, chat, email, social and apps.', 'V native contact-centre voice, IVR, transfer, voicemail.', 'V queues, simplified/Studio routing, manual or auto-accept.', 'Customer history; Copilot real-time transcription, knowledge, guidance, summaries and next steps.', 'Strong WEM/analytics. Healthcare Experience Cloud markets encrypted HIPAA handling and BAA.', 'Best healthcare CCaaS reference architecture. [S47–S51]'),
    ('Front', 'V collaborative inbox; new workspace; email/chat/SMS plus partner voice.', 'V in-inbox voice via Aircall, Dialpad, RingCentral or Zoom; routing remains with partner.', 'V rules, round robin/load balancing, goals and collision detection.', 'Phone match to contacts; AI summaries and Autopilot routing.', 'Good team analytics; healthcare/BAA posture NV in reviewed sources.', 'Best collaboration UX; partner voice/threading constraints. [S52–S56]'),
    ('Kustomer', 'V customer timeline and conversations with Kustomer Voice in the same environment.', 'V native voice, IVR, warm/cold transfer, recordings, transcripts and summaries.', 'V queues, capacity/weights, skills, auto/manual accept, requeue, attribute routing.', 'Customer-centric record; IQ classification can route; strong timeline continuity.', 'Live/routing metrics; healthcare contractual posture NV in reviewed sources.', 'Best customer-timeline mental model; adapt it to caller/patient. [S57–S61]'),
    ('Respond.io', 'V inbox across channels with chat/call views and contact side rail.', 'V VoIP and WhatsApp calls, mobile, recording/transcript and AI-to-human transfer.', 'V manual/workflow assignment; AI agent checks availability and hands off.', 'Single contact record; AI assist, audio transcription and closing summaries.', 'Reports and permissions; healthcare/BAA posture NV.', 'Best messaging-led operator flow; AI transfer currently loses pre-transfer context on fallback. [S62–S66]'),
    ('SleekFlow', 'V shared inbox for WhatsApp, Instagram, Messenger, email, VoIP, SMS and TikTok.', 'V calls logged/transcribed/summarised in inbox.', 'V Flow Builder, round-robin queue, AI-first contact handling and team handoff.', 'Built-in CRM and full history; AI writing, summary, AgentFlow and execution trace.', 'Analytics and RBAC; healthcare/BAA posture NV.', 'Best APAC social selling + inspectable AI; healthcare controls unverified. [S67–S71]'),
    ('Zalo OA Manager / MCC', 'V native Zalo OA messaging on web/mobile, labels, notes, assignment and chatbot.', 'V Mini Call Center for OA calls; simple, no integration team required.', 'V manual assignment; chatbot can classify. Advanced capacity routing NV.', 'Zalo UID plus user-shared fields; customer list and labels.', 'OA operational statistics; healthcare data-contract posture requires local review.', 'Essential Vietnam-native channel, not a complete omnichannel CRM. [S72–S76]'),
    ('Zalo OA OpenAPI / ZCC', 'V API/webhook integration of multiple OAs into CRM/omnichannel systems.', 'V ZCC connects OA voice to enterprise SIP/PBX; outbound by phone or UID.', 'Routing handled by enterprise telephony/CRM design.', 'UID is OA-scoped; Health19 must reconcile UID, phone, partner and patient IDs.', 'Audit/compliance must be built in the integrated system.', 'Recommended Zalo architecture for Health19 at scale. [S72–S76]'),
]

add_table(
    ['Product', 'Workspace / channels', 'Voice', 'Routing', 'Identity + AI', 'Supervisor + health', 'Health19 takeaway / sources'],
    matrix,
    [0.82, 1.47, 1.08, 1.28, 1.76, 1.63, 1.86],
    7.15,
    NAVY,
)

# Back to portrait
portrait = doc.add_section(WD_SECTION.NEW_PAGE)
portrait.orientation = WD_ORIENT.PORTRAIT
portrait.page_width = Inches(8.5)
portrait.page_height = Inches(11)
portrait.top_margin = Inches(0.8)
portrait.bottom_margin = Inches(0.78)
portrait.left_margin = Inches(0.82)
portrait.right_margin = Inches(0.82)
portrait.header_distance = Inches(0.35)
portrait.footer_distance = Inches(0.35)
section_header(portrait)

doc.add_heading('5. Best-in-class patterns to combine', level=1)
patterns = [
    ('Intercom', 'Fast, configurable inbox; details/Copilot rail; immediate summaries', 'Make AI peripheral but always one click away; preserve reading space.'),
    ('Zendesk', 'Single ticket across channels; unified status; focus mode', 'Treat real-time work as interruptive and protect agent attention.'),
    ('Salesforce', 'CRM + channel + routing + workflow + identity', 'Use a single capacity truth and let context drive actions.'),
    ('Genesys', 'Predictive/bullseye/preferred-agent routing', 'Simulate and optimise routing against explicit KPIs.'),
    ('NICE', 'Supervisor, quality, WEM and continuous compliance', 'Make operations and governance first-class, not reporting afterthoughts.'),
    ('Talkdesk', 'Industry workspace and context-aware copilot', 'Shape screens and AI around healthcare workflows, not generic support.'),
    ('Front', 'Collaboration, collision detection and approachable shared inbox', 'Make co-ownership visible and prevent duplicate replies.'),
    ('Kustomer', 'Customer timeline with all interaction types', 'Use a unified chronology, adapted to caller–patient relationships.'),
    ('Respond.io / SleekFlow', 'APAC messaging breadth, AI handoff, execution trace', 'Optimise for Zalo/WhatsApp/social realities and expose AI reasoning evidence.'),
    ('Zalo OA/ZCC', 'Vietnam-native messaging, OA voice, UID and SIP integration', 'Treat Zalo as a first-class transport with explicit policy/identity constraints.'),
]
add_table(['Reference', 'Pattern', 'Health19 application'], patterns, [1.25, 2.35, 2.9], 8.8, TEAL)

doc.add_heading('6. Differentiated Health19 experience', level=1)
doc.add_heading('6.1 The “Care Command” information architecture', level=2)
add_table(
    ['Zone', 'Default content', 'Interaction principle'],
    [
        ('1. Command rail (72–240 px)', 'My work, unassigned, callbacks, risk, follow-up, supervisor, channel health', 'Persistent, keyboard reachable, role-aware'),
        ('2. Queue (320–380 px)', 'Priority, patient/caller, reason, SLA, channel, owner, last event', 'Progressive disclosure; one primary urgency cue'),
        ('3. Interaction canvas (fluid)', 'Mixed-channel timeline, call controls, composer, notes, collaboration', 'Conversation first; events stay chronological across channels'),
        ('4. Care context rail (340–400 px)', 'Continuity Brief, relationship, patient, booking, consent, safety, commitments', 'Adaptive cards; pin what matters; no tab hunting'),
    ],
    [1.55, 3.0, 1.95], 9.0, NAVY
)

doc.add_heading('6.2 Five-second AI Continuity Brief', level=2)
callout('EXAMPLE', 'Lan is contacting Health19 for her father, Minh (caregiver relationship verified). She requested a nurse visit yesterday for dizziness. A booking exists tomorrow at 10:30 AM. Her latest Zalo message says the dizziness is worse. No clinical escalation has been recorded. Recommended next action: confirm current red-flag symptoms using the approved script, then escalate to the clinical queue if any trigger is positive.', 'Recommendation')
add_para('The brief is a structured UI object, not a paragraph dump. It must show:')
for t in [
    'Speaker and patient: names, relationship, verification state and ambiguity warning.',
    'Reason now: current intent and what changed since the last contact.',
    'Care state: bookings, service, location, assigned team and recent outcome.',
    'Safety state: non-diagnostic risk signals, protocol trigger and escalation status.',
    'Commitments: promised callbacks, documents, payments or visits with owner and due time.',
    'Consent/privacy: permission to discuss, preferred channel, opt-in window and recording consent.',
    'Recommended action: one primary action and up to two alternatives, with the policy source.',
    'Evidence and freshness: source-event links, generated time, confidence and “refresh” control.',
]:
    bullet(t)

doc.add_heading('6.3 AI features that create defensible differentiation', level=2)
ai_rows = [
    ('Continuity Brief', 'Cross-channel, relationship-aware summary with evidence links', 'Agent verifies; stale state displayed'),
    ('Relationship Resolver', 'Suggests caller ↔ patient ↔ caregiver/payer/referrer links', 'Never auto-merges patient identities'),
    ('Safety Shield', 'Detects approved red-flag phrases and missing escalation', 'No diagnosis; deterministic protocol and human escalation'),
    ('Next Best Action', 'Ranks booking, callback, information, consent and escalation actions', 'Displays why; agent retains control'),
    ('Bilingual Care Composer', 'Drafts Vietnamese/English replies in approved tone and reading level', 'PHI/channel rules checked before send'),
    ('Live Call Companion', 'Real-time transcript, intent, checklist, knowledge and commitment capture', 'Recording/transcription consent enforced'),
    ('Commitment Ledger', 'Extracts “I will call/send/book” promises and creates owned tasks', 'Human confirms before task creation where ambiguous'),
    ('After-contact Wrap-up', 'Summary, outcome, disposition, follow-up and CRM updates', 'Diff preview; explicit save'),
    ('Missed-care Recovery', 'Prioritises missed calls/no-shows using booking and vulnerability context', 'No autonomous clinical prioritisation'),
    ('Supervisor Radar', 'Surfaces queue anomalies, repeated contacts, risky silence and AI overrides', 'Minimum necessary access; no covert staff scoring'),
    ('Identity Conflict Guard', 'Explains matching signals and separates shared-phone households', 'No silent reassignment or destructive merge'),
    ('AI Trace', 'Shows sources, policy, actions, model/version and user edits', 'Immutable audit; feedback loop for governance'),
]
add_table(['Capability', 'Experience', 'Guardrail'], ai_rows, [1.45, 3.05, 2.0], 8.6, TEAL)

doc.add_heading('6.4 Signature micro-interactions', level=2)
for t in [
    'Incoming call “context bloom”: a compact caller card expands into identity candidates, caller–patient relationship and today’s booking before answer.',
    'Hold-to-confirm merge: identity merges require comparison of conflicting fields and a reason; a safe link is offered before a destructive merge.',
    'Live commitment chips: dates, times and promises become reviewable chips beside the composer, then sync to activities only when confirmed.',
    'Safety ribbon: a quiet persistent ribbon shows “No escalation,” “Escalation open” or “Clinician accepted,” with time and owner.',
    'Channel-aware composer: Zalo/WhatsApp windows, attachment limits, templates and consent are visible before the user writes an invalid response.',
    'One-key flow: J/K queue navigation, A assign, C call, R reply, N internal note, B book, E escalate, W wrap up; every shortcut shown in command palette.',
    'Calm mode during voice: queue chrome recedes, transcript and checklist expand, and non-urgent notifications pause.',
]:
    bullet(t)

doc.add_heading('7. Routing, automation and supervision', level=1)
doc.add_heading('7.1 Constraint-first routing', level=2)
add_para('Do not use round robin as the governing model. Use it only as the final tie-breaker after hard eligibility and continuity rules.')
add_table(
    ['Order', 'Decision', 'Examples'],
    [
        ('1', 'Safety / legal eligibility', 'Clinical escalation permission, consent, language, record access'),
        ('2', 'Channel eligibility', 'Zalo-trained, voice-ready, signed in, recording notice enabled'),
        ('3', 'Relationship continuity', 'Current owner, recent agent, named care coordinator'),
        ('4', 'Skill / location', 'Vietnamese, province, service knowledge, payer/referrer workflow'),
        ('5', 'Urgency and SLA', 'Worsening symptoms, missed-call recovery, booking within 24 hours'),
        ('6', 'Capacity and focus', 'Voice consumes full real-time capacity; messaging weighted'),
        ('7', 'Fairness tie-break', 'Longest idle or round robin among equal candidates'),
    ],
    [0.6, 2.05, 3.85], 9.0, NAVY
)

doc.add_heading('7.2 Routing policy studio', level=2)
for t in [
    'Natural-language rule summary beside the actual structured conditions.',
    'Test with historical or synthetic interactions before publish.',
    'Explain why a specific interaction reached a specific queue/agent.',
    'Version, draft, approve, schedule, compare and roll back policies.',
    'Conflict detection for shadowed rules, dead ends, unavailable skills and unsafe fallbacks.',
    'Separate business-hours, after-hours, outage and surge policies.',
]:
    bullet(t)

doc.add_heading('7.3 Manager / supervisor cockpit', level=2)
add_table(
    ['View', 'Answer in one glance', 'Actions'],
    [
        ('Live operations', 'Volume, oldest wait, SLA risk, available capacity by channel', 'Rebalance, pause intake, open overflow'),
        ('Risk queue', 'Unacknowledged escalation, repeated contact, worsening language, no owner', 'Assign, join, escalate, audit'),
        ('Agent focus', 'Current real-time interaction, weighted load, after-contact work', 'Coach, monitor where lawful, change capacity'),
        ('Journey quality', 'Transfers, repeat contact, identity conflicts, missed commitments', 'Review case, create coaching, repair workflow'),
        ('AI governance', 'Automation rate, override rate, unsupported claims, source coverage', 'Disable capability, sample, label, improve content'),
        ('Channel health', 'Webhook lag, delivery failures, token expiry, telephony quality', 'Fail over, retry, notify technical owner'),
    ],
    [1.2, 3.15, 2.15], 8.8, TEAL
)

doc.add_heading('8. Healthcare privacy, safety and trust requirements', level=1)
for t in [
    'Minimum necessary view: agents see only the care context required for their role and task; clinical details are not automatically exposed.',
    'Consent ledger: purpose, channel, subject, representative authority, provenance, expiry and revocation are first-class fields.',
    'No autonomous diagnosis or emergency prioritisation: AI may identify an approved phrase and start a deterministic escalation protocol, never decide clinical severity.',
    'Recording and transcription: obtain and store consent state before capture; provide pause/redaction and retention controls.',
    'Identity integrity: phone numbers are signals, not unique patients; shared household devices and representatives must be expected.',
    'Approved AI boundary: no PHI is sent to a model or subprocessor unless that exact feature, region and contract are approved. Fall back to non-AI workflow.',
    'Auditability: append-only event trail for routing, access, AI generation, evidence, edits, sends, merges, escalation and supervisor intervention.',
    'Data lifecycle: explicit retention, legal hold, export, deletion/anonymisation and backup policies per interaction artefact.',
    'Break glass: elevated access requires reason, time limit, notification and post-event review.',
    'Message safety: templates and composer checks prevent sending sensitive detail to an unverified or non-consented channel.',
]:
    bullet(t)

callout('DESIGN RULE', 'Never communicate “AI confidence” with a reassuring green percentage alone. Show what the AI knows, what it does not know, the supporting events and the next human verification step.', 'Risk')

doc.add_heading('9. Health19 fit and target architecture', level=1)
add_para('Verified from the local repository, Health19 already has the necessary foundations: a custom CRM Center and OWL components; caller/client relationship fields and booking conversion; Zalo OA OAuth/webhooks and conversation models; VoIP24h call logs, recordings, matching and popups; consent and PHI-encryption modules; outbound messaging; and secure family messaging. The missing capability is a canonical, cross-channel work layer and a unified operational UI.')

add_table(
    ['Existing module', 'Keep / reuse', 'Add or change'],
    [
        ('health_crm', 'CRM Center, contacts/leads, caller relationship, booking wizards, activities', 'Add Care Command entry and integration services; do not replace proven booking flow'),
        ('health_zalo', 'OA config, OAuth, webhooks, conversations/messages, bus notifications', 'Adapter into canonical conversation; assignment, SLA, consent and identity link state'),
        ('health_voip24h', 'CDR, recordings, click-to-dial, caller match, incoming popup', 'Real-time interaction lifecycle, queue/agent state, transcript/summary abstraction'),
        ('health_messaging', 'ZNS/email/call fallback and safety switches', 'Expose delivery state and retry timeline in Care Command'),
        ('health_family_messages', 'Consent-gated, encrypted family threads and notifications', 'Optional adapter with stricter role visibility; do not flatten into public chat'),
        ('health_consent / health_phi_encryption', 'Consent decisions, PHI encryption patterns', 'Mandatory gates for AI, composer, recordings, exports and identity merge'),
        ('New health_omnichannel', 'Canonical work models, OWL workspace, routing, presence, AI governance, supervisor', 'Owns orchestration; adapters remain source-specific'),
    ],
    [1.45, 2.75, 2.3], 8.7, NAVY
)

doc.add_heading('9.1 Canonical models', level=2)
add_table(
    ['Model', 'Purpose / important fields'],
    [
        ('health.channel.account', 'Provider/account/brand, channel type, company, credentials reference, health state'),
        ('health.channel.identity', 'Provider-scoped external ID, phone/email, partner/patient link, verification, confidence, provenance'),
        ('health.conversation', 'Cross-channel case container, caller, patient, relationship, state, priority, SLA, queue, owner'),
        ('health.interaction', 'Immutable message/call/note/system event; direction, timestamps, source IDs, payload reference'),
        ('health.routing.queue / rule', 'Eligibility, weights, capacity, overflow, hours, priority, versions and explanation'),
        ('health.agent.presence', 'Status, channel capacities, skills, focus state, last assignment'),
        ('health.interaction.brief', 'Structured AI/human brief, source event IDs, model/prompt version, verification state'),
        ('health.commitment', 'Promised action, owner, due time, source event, completion and breach state'),
        ('health.escalation', 'Protocol, trigger, non-clinical evidence, owner, acceptance and resolution timestamps'),
        ('health.ai.audit', 'Input references, redaction, output, source coverage, actions, user edits, approval/override'),
    ],
    [2.0, 4.5], 8.8, TEAL
)

doc.add_heading('9.2 Non-negotiable architectural decisions', level=2)
for t in [
    'Use provider adapters and idempotent external IDs. Never duplicate an interaction on webhook retry.',
    'Canonical interaction records reference source records; do not destructively migrate or delete source histories in phase 1.',
    'Use Odoo bus for live UI updates and a durable job/outbox pattern for outbound delivery, webhook processing and AI tasks.',
    'Keep PHI payloads encrypted; store search-safe derived metadata separately and minimally.',
    'Use a stable patient/partner ID as the identity anchor. Phone, email and Zalo UID are match signals with provenance.',
    'All AI outputs are derived artefacts. They never replace the immutable interaction record.',
    'Feature flags and simulation mode are required for each channel, routing policy and AI capability.',
]:
    bullet(t)

doc.add_heading('10. Delivery roadmap', level=1)
add_table(
    ['Phase', 'Scope', 'Exit criteria'],
    [
        ('0 — foundations', 'Event model, permissions, consent/AI policy, UX prototype, migration mapping', 'Threat model and clinical/legal sign-off; synthetic demo'),
        ('1 — unified read', 'Care Command shell; Zalo + VoIP histories; identity and relationship rail', 'No duplicate events; role tests; <2 s open on representative data'),
        ('2 — work + route', 'Assignment, presence, SLAs, callbacks, composer, dialler and explainable routing', 'Replayable routing tests; delivery/outbox resilience'),
        ('3 — AI assist', 'Continuity Brief, wrap-up, bilingual draft, commitments and source trace', 'Offline fallback; human review; hallucination and PHI leakage test suite'),
        ('4 — supervisor', 'Live operations, quality samples, coaching, AI governance and channel health', 'Manager scenario tests; audited interventions'),
        ('5 — optimisation', 'Predictive recommendations, staffing, expanded channels and optional CCaaS adapter', 'Measured benefit without safety or fairness regression'),
    ],
    [1.1, 3.25, 2.15], 8.7, NAVY
)

doc.add_heading('11. Full implementation prompt for the Health19 coding agent', level=1)
callout('HOW TO USE', 'Paste the following section into the implementation task. It is intentionally explicit. The coding agent must inspect the repository, preserve existing behaviour, implement incrementally, test, and stop for decisions that affect clinical/legal policy or external credentials.', 'Callout')

prompt_sections = [
('ROLE AND OUTCOME', [
    'You are a senior Odoo 19 product engineer, OWL frontend architect, contact-centre designer and healthcare privacy engineer working inside the existing Health19 repository.',
    'Build a production-quality, healthcare-first omnichannel agent workspace named “Care Command” for Sales Admins and Managers. It must unify calls, Zalo messages and follow-up work while preserving Health19’s existing CRM, booking, consent, PHI encryption, messaging and family-communication behaviour.',
    'The outcome is not a generic ticket inbox and not a visual clone of Pancake. It is a differentiated care-relationship workspace where an agent understands caller, patient, relationship, intent, booking, consent, commitments, safety/escalation state and next action within five seconds.',
]),
('REPOSITORY CONTEXT TO VERIFY BEFORE EDITING', [
    'Inspect AGENTS.md if present and follow it. Inspect git status and preserve unrelated user changes.',
    'Read addons/health_crm/__manifest__.py, its CRM Center OWL components/views and the caller/client/booking flows.',
    'Read addons/health_zalo models, controllers, services, bus code and chat components. Confirm the currently supported Zalo API version rather than trusting manifest prose.',
    'Read addons/health_voip24h call models, webhook/event services, recordings, click-to-dial and popup components.',
    'Read addons/health_messaging, health_family_messages, health_consent and health_phi_encryption, including their safety switches and tests.',
    'Document the actual current model names, security groups, menus, endpoints and event flows before designing migrations.',
]),
('SCOPE AND MODULE BOUNDARY', [
    'Create a new installable addon addons/health_omnichannel unless repository conventions strongly favour extending an existing addon. Explain any different choice before implementation.',
    'Depend on web, mail, bus, health_base, health_crm, health_zalo, health_voip24h, health_consent and health_phi_encryption. Make health_messaging and health_family_messages optional adapters if dependency cycles would result.',
    'Keep provider-specific records authoritative in phase 1. Add canonical models that reference them; use idempotent adapter services and immutable external IDs.',
    'Add CRM Center > Care Command directly after Dashboard. The menu/action must be limited to the existing healthcare CRM user/manager groups, with a separate supervisor capability for managers.',
    'Do not modify vendor/core Odoo files. Use inheritance, registries, services, patches only where required, and local assets.',
]),
('TARGET USER EXPERIENCE', [
    'Implement an OWL client action with responsive desktop-first layout and four adaptive zones: command rail, queue list, interaction canvas and care context rail.',
    'Command rail: My Work, Unassigned, Calls, Messages, Callbacks, Follow-ups, Risk/Escalations, Supervisor (manager only), Channel Health (manager/admin only). Show counts and oldest/SLA state, not decorative badges.',
    'Queue list: each row shows one semantic priority, patient or unknown caller, representative relationship, reason/intent, channel, SLA countdown, owner and last interaction preview. Provide fast search, saved views and keyboard navigation.',
    'Interaction canvas: one chronological timeline mixing Zalo messages, voice calls, recordings/transcripts, delivery events, internal notes, assignments, bookings, commitments and escalation events. Preserve provider/source badges and deep links.',
    'Composer: Reply, internal note and call modes. Show channel/account, consent, supported content, messaging-window/template constraint and recipient identity. Prevent invalid sends before submission. Include bilingual draft assistance only when AI is enabled and approved.',
    'Care context rail: Continuity Brief first; then caller/patient relationship, identity verification, active booking, service/area, consent, safety/escalation, commitments and contact history. Cards are collapsible and pinnable. Never expose unnecessary clinical data.',
    'Voice calm mode: when a call is active, reduce unrelated chrome, enlarge call controls/transcript/checklist and pause non-urgent notifications.',
    'Provide a command palette and shortcuts: J/K queue navigation; A assign; C call; R reply; N note; B book; E escalate; W wrap up. Do not override browser/accessibility shortcuts.',
]),
('VISUAL DESIGN SYSTEM', [
    'Use Health19 theme tokens where available. If missing, introduce CSS custom properties scoped to .o_health_care_command.',
    'Design for calm clinical operations: warm white/very light blue-gray canvas; navy ink; teal action accent; amber caution; red only for safety/overdue states; no gradients, glassmorphism, neon, emoji buttons or excessive pills.',
    'Use an 8 px spacing system, minimum 44 px interactive targets, strong focus outlines, WCAG AA contrast, text+icon status encoding and reduced-motion support.',
    'Optimise information density through hierarchy and progressive disclosure, not tiny text. Default body >=14 px equivalent; queue metadata >=12 px; critical timers >=13 px and never colour-only.',
    'Make loading, empty, offline, permission-denied, provider-degraded and stale-AI states explicit and useful.',
]),
('CANONICAL DATA MODEL', [
    'Implement health.channel.account: company, provider, channel_type, external_account_id, active, health/status timestamps and safe credential/config reference.',
    'Implement health.channel.identity: account, external_id, identifier_type, normalised value, partner_id, patient/client link if applicable, verification state, confidence, provenance, valid dates and unique constraints.',
    'Implement health.conversation: company, subject, caller partner, patient/client, relationship type, state, priority, queue, assignee, SLA timestamps, active channel, last interaction and canonical external key.',
    'Implement health.interaction as append-oriented: conversation, source model/res_id, source external ID, channel/account, kind, direction, actor, occurred_at, delivery state, redacted preview, encrypted payload/content reference, attachments and event metadata. Restrict write/delete after ingestion to system workflows.',
    'Implement routing queue/rule/version, agent presence/capacity/skill, interaction brief, commitment, escalation and AI audit models described in the product brief. Reuse existing models when they already meet the requirement; do not create duplicates for naming convenience.',
    'Add SQL and Python constraints for company isolation, provider idempotency and coherent caller/patient relationship state.',
]),
('IDENTITY AND RELATIONSHIP RESOLUTION', [
    'Never treat a phone number as a unique patient. Model shared numbers, representatives and households.',
    'Normalise Vietnam phone numbers, email addresses and provider IDs. Preserve raw values and provenance.',
    'Match in layers: verified canonical ID; provider external ID; exact normalised phone/email; existing relationship; name/address/date signals. Return candidates with reasons and conflicts.',
    'Auto-link only high-confidence, non-conflicting identities allowed by policy. Otherwise show a comparison drawer with Link, Create New, Keep Separate and Merge (privileged) actions.',
    'A merge must display changed fields, affected conversations/bookings/relationships, require a reason, create an audit event and support an administrator recovery path. Prefer linking identities over destructive merging.',
]),
('ROUTING AND PRESENCE', [
    'Implement constraint-first routing in this order: safety/legal eligibility; channel eligibility; relationship continuity; skill/location; urgency/SLA; capacity/focus; fairness tie-break.',
    'Voice uses full real-time capacity by default. Messaging and asynchronous work use configurable weights. An active voice call suppresses new real-time work unless a manager-approved policy says otherwise.',
    'Support direct, preferred-owner, longest-idle, round-robin, least-loaded and skill-based tie-breakers, plus overflow and after-hours policies.',
    'Every assignment records policy version, evaluated facts, excluded agents and the final reason. Expose “Why routed here?” to authorised users.',
    'Build a routing policy studio with draft/publish, validation, simulation on synthetic/historical facts, conflict/dead-end detection, version comparison and rollback. Do not expose raw Python domains to ordinary managers.',
]),
('AI CONTINUITY BRIEF AND ASSISTANCE', [
    'Build the Continuity Brief as a structured record and UI, not unstructured HTML. Required fields: speaker/patient/relationship; reason now and change; recent care state; booking; safety signals; escalation; consent; commitments; recommended action; uncertainty; source interaction IDs; generated_at; model/prompt version; verified_by/at.',
    'Generate asynchronously after material events and on demand. Show stale/generating/error states without blocking the conversation.',
    'All factual claims in the brief must map to source interactions or canonical records. The UI opens the cited source event. Unsupported fields remain Unknown; never infer demographic or clinical facts.',
    'Implement human review for wrap-up, disposition, new commitments, CRM updates and outbound drafts. Show a diff before applying structured changes.',
    'Implement policy-grounded bilingual Vietnamese/English drafting, tone/readability controls, approved knowledge retrieval and source display.',
    'Implement a deterministic Safety Shield: configurable approved phrase/pattern triggers may open a non-clinical escalation checklist. AI must not diagnose, score clinical severity, recommend treatment or dispatch emergency care. Display the organisation’s approved emergency wording and human escalation path.',
    'Implement AI audit records containing redacted input references, sources, output, actions proposed/taken, user edits, approval/override, model and prompt versions. Never log secrets or unnecessary PHI.',
    'If no approved model/service configuration exists, ship AI features disabled with deterministic mock/provider interfaces for tests. The core workspace must work fully without AI.',
]),
('CHANNEL ADAPTERS', [
    'Zalo: ingest existing zalo.conversation/zalo.message events into canonical records idempotently; maintain OA-scoped UID identity; expose delivery/window/template rules; use the existing API/token manager; publish state through Odoo bus.',
    'VoIP24h: map CDR lifecycle, caller/called numbers, extensions, recording, match confidence, call outcome and activities. Preserve current popups/click-to-dial while adding Care Command call controls and live event updates.',
    'Use an adapter registry/interface so email, web chat, WhatsApp/social or a future Genesys/NICE/Talkdesk/Twilio provider can be added without changing the workspace domain model.',
    'Outbound operations use a transactional outbox/job model with idempotency key, retry policy, terminal failure, manual retry and channel-health reporting.',
]),
('SUPERVISOR EXPERIENCE', [
    'Manager-only live dashboard: queue volume, oldest wait, SLA at risk, capacity, active calls/messages, callbacks, after-contact work and channel health.',
    'Risk queue: unacknowledged escalations, repeated contacts, worsening-language trigger, identity conflict, missed commitment and booking within 24 hours without resolution.',
    'Allow reassign, rebalance, open overflow, join/coach where lawful, and inspect routing explanation. Every intervention is audited.',
    'AI governance: volume, acceptance/edit/override rates, source coverage, unsupported-output flags, capability kill switches and sampled review workflow. Do not create opaque employee rankings or emotion scoring.',
]),
('SECURITY, PRIVACY AND SAFETY', [
    'Apply Odoo record rules and field groups for company, clinic/facility, role and minimum necessary access. Add tests proving cross-company and role isolation.',
    'Use health_phi_encryption patterns for interaction content, transcript, AI artefacts and sensitive notes. Avoid searchable plaintext copies of PHI.',
    'Gate message send, recording, transcription, AI processing, export and representative disclosure through health_consent or an explicit policy service. Record the decision and policy version.',
    'Sanitise attachments, validate MIME/size, use access-controlled download routes and never expose provider URLs or tokens directly.',
    'Add immutable audit events for access to sensitive interaction detail, identity link/merge, consent override, AI use, outbound send, recording playback/download and supervisor intervention.',
    'Add configurable retention and legal-hold hooks. Do not implement silent hard deletes of interaction history.',
]),
('PERFORMANCE AND RESILIENCE', [
    'Paginate/virtualise large queues and timelines. Do not load full recordings, transcripts or message bodies until requested.',
    'Index company/state/queue/assignee/priority/SLA/last_interaction and provider external IDs. Measure representative query plans.',
    'Use optimistic UI only for reversible low-risk actions; show confirmed provider delivery state for sends.',
    'Handle duplicate/out-of-order webhooks, bus reconnect, provider outage, expired Zalo token, telephony degradation and AI timeout. Provide reconciliation jobs and admin diagnostics.',
]),
('TESTS AND ACCEPTANCE', [
    'Write unit tests for identifier normalisation, idempotent adapter ingestion, relationship candidates, routing eligibility/scoring, SLA timers, consent gates, encryption, outbox retries and AI-source validation.',
    'Write security tests for agent vs manager vs system admin, cross-company isolation, recording/transcript access and privileged merge.',
    'Write OWL/QUnit tests for queue loading, keyboard navigation, interaction selection, live bus updates, stale brief, consent-blocked send, identity conflict and active-call calm mode.',
    'Create end-to-end tours for: new unknown inbound call; returning caregiver calling for an existing patient; Zalo message that worsens a prior symptom statement; missed call callback; duplicate shared phone; booking creation from conversation; after-hours routing; manager intervention; provider outage; AI disabled.',
    'Accessibility acceptance: keyboard-only completion of core workflow, visible focus, semantic labels, screen-reader status announcements, AA contrast and reduced motion.',
    'Performance acceptance on a documented representative dataset: workspace shell interactive within 2 seconds on a normal office connection; queue change feedback within 300 ms after cached data; selected conversation first useful content within 1 second excluding provider media; no unbounded ORM reads.',
]),
('IMPLEMENTATION SEQUENCE', [
    '1. Produce a concise repository findings note and model/flow map. Do not code until existing models and extension points are confirmed.',
    '2. Scaffold the addon, permissions, menu/action and empty OWL shell behind a feature flag.',
    '3. Implement canonical read models and idempotent Zalo/VoIP adapters with migrations/reconciliation.',
    '4. Build unified read-only workspace and relationship/identity rail; verify performance and permissions.',
    '5. Add assignment, presence, SLA, routing explanation, composer/dial actions and durable outbox.',
    '6. Add Continuity Brief provider interface, deterministic fake, approved provider integration only if configuration exists, source trace and review flows.',
    '7. Add supervisor cockpit, routing studio and AI governance.',
    '8. Run targeted tests, full addon tests, lint/assets checks and browser tours. Fix failures; do not hide them.',
]),
('DELIVERABLES', [
    'Code and migrations within scoped addons; no unrelated formatting or rewrites.',
    'Architecture note with data flow, trust boundaries, provider adapters, routing explanation and AI boundary.',
    'Administrator guide for queues, presence, channels, consent, recording, retention, AI and emergency wording.',
    'Agent and manager quick-start guide with keyboard shortcuts and failure states.',
    'Test evidence, screenshots of the implemented desktop states and a list of deferred decisions/risks.',
]),
('STOP CONDITIONS / REQUIRED HUMAN DECISIONS', [
    'Stop and request direction before enabling any real outbound channel, recording, transcription or AI provider; before changing clinical escalation wording; before destructive identity migration; before storing new categories of PHI; or if the requested behaviour conflicts with existing consent/security constraints.',
    'Do not claim regulatory compliance. Implement controls and document the exact configuration requiring legal, security and clinical approval.',
]),
]

for title, items in prompt_sections:
    doc.add_heading(title, level=2)
    for item in items:
        bullet(item)

doc.add_heading('12. Definition of “wow” for this product', level=1)
add_para('“Wow” is not animation or novelty. It is the feeling that the system has quietly assembled the right context, protected attention, prevented a dangerous mistake and made the next safe action obvious. The following measures make that testable:')
add_table(
    ['Moment', 'Target experience', 'Measure'],
    [
        ('Open conversation', 'Five-second accurate continuity understanding', 'Agent can answer 7 context questions without scrolling'),
        ('Incoming call', 'Caller and patient relationship visible before answer when known', 'Context card ready before or within 1 s of accept'),
        ('Identity conflict', 'No silent wrong-patient match', '100% conflicts require explicit resolution'),
        ('Compose/send', 'Channel and consent constraints are obvious', 'Invalid or unapproved send blocked before provider call'),
        ('Wrap up', 'One review replaces duplicate typing', 'Disposition, summary, commitments and follow-up confirmed in <30 s'),
        ('Supervisor surge', 'Operational cause and action visible together', 'Rebalance/overflow action within two clicks'),
        ('AI trust', 'Every material claim can be inspected', 'Source coverage shown; unsupported fields remain Unknown'),
    ],
    [1.25, 3.55, 1.7], 8.8, TEAL
)

doc.add_heading('Appendix A. Sources', level=1)
add_para('All competitor capabilities are cited to official vendor documentation or official product pages. Sources were accessed 19 July 2026. Public pages may describe add-ons, previews, EAP/beta features or plan-specific capabilities; validate exact entitlement and region.')

sources = [
('S01', 'Pancake — omnichannel business messaging platform', 'https://pancake.vn/'),
('S02', 'Pancake CRM — omnichannel lead/customer management including Zalo sync', 'https://crm.pancake.vn/'),
('S03', 'Pancake POS — telesales, call recording and call scheduling', 'https://order.pancake.vn/'),
('S04', 'Intercom — AI-powered omnichannel inbox', 'https://www.intercom.com/helpdesk/inbox'),
('S05', 'Intercom — take calls from the Inbox', 'https://www.intercom.com/help/en/articles/8488917-take-calls-from-the-inbox'),
('S06', 'Intercom — Inbox AI features: Copilot, compose and summarise', 'https://www.intercom.com/help/en/articles/6955446-ai-features-available-in-the-inbox'),
('S07', 'Intercom — contact identity and user IDs', 'https://www.intercom.com/help/en/articles/12292449-understanding-and-managing-user-ids'),
('S08', 'Intercom — HIPAA attestation and Expert-plan BAA', 'https://www.intercom.com/help/en/articles/8827723-contacts-faqs'),
('S09', 'Zendesk — Agent Workspace', 'https://support.zendesk.com/hc/en-us/articles/4408821259930-About-the-Zendesk-Agent-Workspace/'),
('S10', 'Zendesk — omnichannel routing', 'https://support.zendesk.com/hc/en-us/articles/4409149119514-About-omnichannel-routing'),
('S11', 'Zendesk — routing configuration and focus mode', 'https://support.zendesk.com/hc/en-us/articles/4828787357210-Managing-your-omnichannel-routing-configuration'),
('S12', 'Zendesk — voice AI agent EAP and healthcare limitation', 'https://support.zendesk.com/hc/en-us/articles/10169333291290-Creating-an-AI-agent-for-the-voice-channel-EAP'),
('S13', 'Zendesk — HIPAA posture and configuration', 'https://support.zendesk.com/hc/en-us/articles/4408820063898-Is-Zendesk-HIPAA-compliant'),
('S14', 'Salesforce — Agentforce Contact Center', 'https://help.salesforce.com/s/articleView?id=support_channels.htm&language=en_US'),
('S15', 'Salesforce — Service Cloud / Agentforce Service', 'https://www.salesforce.com/service/cloud/'),
('S16', 'Salesforce — Omni-Channel unified voice routing', 'https://help.salesforce.com/s/articleView?id=service.voice_omni_unified_routing.htm&language=en_US'),
('S17', 'Salesforce — route to an Agentforce Service Agent', 'https://help.salesforce.com/s/articleView?id=service.omnichannel_route_to_ai_agent_target.htm&language=en_US&type=5'),
('S18', 'Salesforce — Data 360 identity resolution and unified profiles', 'https://help.salesforce.com/s/articleView?id=data.c360_a_data_cloud.htm&language=en_US'),
('S19', 'Salesforce — HIPAA feature restrictions', 'https://help.salesforce.com/s/articleView?id=xcloud.base_manage_your_compliance.htm&language=en_US&type=5'),
('S20', 'Zoho Desk — omnichannel customer service', 'https://www.zoho.com/desk/omnichannel-customer-service.html'),
('S21', 'Zoho Desk — assignment rules: load, sequential and skills', 'https://help.zoho.com/portal/en/kb/desk/automation/assignment-rules-notification/articles/assigning-tickets-using-workflows-assignment-rule'),
('S22', 'Zoho Desk — Zia overview', 'https://help.zoho.com/portal/en/kb/desk/zia/overview/articles/understanding-zia-s-capabilities'),
('S23', 'Zoho Desk — HIPAA compliance guide and BAA', 'https://help.zoho.com/portal/en/kb/desk/user-management-and-security/compliance/articles/hipaa-compliance-guide'),
('S24', 'Freshdesk — Omni 2025 upgrade and unified command centre', 'https://support.freshdesk.com/support/solutions/articles/50000012004-overview-of-freshdesk-omni-2025-upgrade'),
('S25', 'Freshdesk — Omni capabilities and Freddy AI', 'https://support.freshdesk.com/support/solutions/articles/50000011785-getting-started-with-freshdesk-omni'),
('S26', 'Freshworks — HIPAA configuration and BAA scope', 'https://support.freshworks.com/support/solutions/articles/238735-hipaa-configuration-guide'),
('S27', 'HubSpot — route tickets in Help Desk', 'https://knowledge.hubspot.com/help-desk/route-tickets-in-help-desk'),
('S28', 'HubSpot — calling channel in Help Desk', 'https://knowledge.hubspot.com/calling/set-up-a-calling-channel-in-help-desk'),
('S29', 'HubSpot — Breeze customer agent and reply recommendations', 'https://knowledge.hubspot.com/customer-agent/understand-the-customer-agent'),
('S30', 'HubSpot — store sensitive data and apply BAA', 'https://knowledge.hubspot.com/account-security/store-sensitive-data'),
('S31', 'HubSpot — healthcare CRM and qualifying Enterprise BAA', 'https://www.hubspot.com/products/crm/healthcare'),
('S32', 'Genesys — advanced routing overview', 'https://help.mypurecloud.com/articles/advanced-routing-overview/'),
('S33', 'Genesys — predictive routing', 'https://help.mypurecloud.com/articles/about-predictive-routing/'),
('S34', 'Genesys — create Agent Copilot', 'https://help.mypurecloud.com/articles/create-a-new-genesys-agent-copilot/'),
('S35', 'Genesys — Agent Copilot performance dashboard', 'https://help.mypurecloud.com/articles/genesys-agent-copilot-performance-dashboard/'),
('S36', 'Genesys — Cloud Trust Center compliance', 'https://www.genesys.com/trust-center/compliance'),
('S37', 'NICE CXone — Agent Workspace FAQ and channel support', 'https://help.nice-incontact.com/content/agent/agentapplicationadministration/cxoneagent/faqs.htm'),
('S38', 'NICE CXone — Copilot for Agents in Agent Workspace', 'https://help.nice-incontact.com/content/agent/cxoneagent/enlightencopilotforagentscxa.htm'),
('S39', 'NICE CXone — platform availability and advanced routing', 'https://help.nice-incontact.com/content/platformrequirements/platformavailability.htm'),
('S40', 'NICE — CXone security and reliability', 'https://www.nice.com/resources/nice-cxone-security-reliability-pci-compliance'),
('S41', 'NICE — healthcare experience and BAA posture', 'https://www.nice.com/industries/healthcare'),
('S42', 'Twilio Flex — routing core concepts', 'https://www.twilio.com/docs/flex/admin-guide/core-concepts/routing'),
('S43', 'Twilio Flex — Conversations channels and orchestration', 'https://www.twilio.com/docs/flex/developer/conversations'),
('S44', 'Twilio Flex — AI overview and HIPAA exclusion', 'https://www.twilio.com/docs/flex/ai'),
('S45', 'Twilio — Architecting for HIPAA', 'https://www.twilio.com/content/dam/twilio-com/global/en/other/hipaa/pdf/Architecting-for-HIPAA.pdf'),
('S46', 'Twilio — HIPAA Eligible Services', 'https://www.twilio.com/content/dam/twilio-com/global/en/other/hipaa/pdf/HIPAA-Eligible-Services.pdf'),
('S47', 'Talkdesk — Agent Workspace', 'https://www.talkdesk.com/cloud-contact-center/omnichannel-engagement/agent-workspace/'),
('S48', 'Talkdesk — Digital Engagement FAQ and routing', 'https://support.talkdesk.com/hc/en-us/articles/4416787592731-Talkdesk-Digital-Engagement-FAQ'),
('S49', 'Talkdesk — Copilot overview', 'https://support.talkdesk.com/hc/en-us/articles/360045123011-Copilot-Overview'),
('S50', 'Talkdesk — Copilot summarisation, next steps and disposition', 'https://support.talkdesk.com/hc/en-us/articles/16761287647259-Copilot-Automatic-Summarization-Agent-Next-Steps-and-Disposition'),
('S51', 'Talkdesk — Healthcare Experience Cloud', 'https://www.talkdesk.com/call-center-solutions/healthcare/'),
('S52', 'Front — new inbox experience', 'https://help.front.com/en/articles/3889728'),
('S53', 'Front — routing and triage rules', 'https://help.front.com/en/articles/2120'),
('S54', 'Front — rules, goals and load balancing', 'https://help.front.com/en/articles/2105'),
('S55', 'Front — AI conversation summaries', 'https://help.front.com/en/articles/1164608'),
('S56', 'Front — Aircall voice in the inbox', 'https://help.front.com/en/articles/3553088'),
('S57', 'Kustomer — route Voice calls to teams', 'https://help.kustomer.com/en_us/route-kustomer-voice-calls-to-your-team-ByuFCWYEa'),
('S58', 'Kustomer — Voice integration and transfers', 'https://help.kustomer.com/kustomer-voice-B1uGhF9Ti'),
('S59', 'Kustomer — Voice assistant and IVR', 'https://help.kustomer.com/en_us/set-up-voice-assistant-rJNZl9DUp'),
('S60', 'Kustomer — route Voice by customer attribute', 'https://help.kustomer.com/en_us/routing-kustomer-voice-calls-by-customer-attribute-HkHCZF71zg'),
('S61', 'Kustomer — classification models with queues', 'https://help.kustomer.com/en_us/classification-model-in-routing-B12i6Iu_v'),
('S62', 'Respond.io — Inbox structure and calls', 'https://respond.io/help/inbox/getting-started-with-inbox'),
('S63', 'Respond.io — manage calls, recordings, transcripts and AI transfer', 'https://respond.io/help/inbox/managing-calls-in-inbox'),
('S64', 'Respond.io — assignment and AI closing summary', 'https://respond.io/help/inbox/assigning-and-closing-a-conversation'),
('S65', 'Respond.io — managing conversations and AI assist', 'https://respond.io/help/inbox/managing-conversations-in-inbox'),
('S66', 'Respond.io — AI agent assignment and human takeover', 'https://respond.io/help/quick-start/responding-to-messages'),
('S67', 'SleekFlow — platform and shared inbox', 'https://help.sleekflow.io/en_US/getting-started/welcome-to-sleekflow'),
('S68', 'SleekFlow — AI-to-team round-robin flow', 'https://help.sleekflow.io/en_US/manage-and-assign-new-contacts-using-agentflow'),
('S69', 'SleekFlow — omnichannel inbox and VoIP summaries', 'https://sleekflow.io/inbox'),
('S70', 'SleekFlow — AI execution trace', 'https://help.sleekflow.io/en_US/view-ai-message%E2%80%99s-execution-trace-in-inbox'),
('S71', 'SleekFlow — AI feature catalogue', 'https://sleekflow.helpjuice.com/en_US/sleekflow_ai'),
('S72', 'Zalo OA — messaging and voice customer care', 'https://oa.zalo.me/home/resources/library/cham-soc-khach-hang-hieu-qua-voi-nhan-tin-va-goi-thoai_729563123387551711'),
('S73', 'Zalo OA — OpenAPI for CRM/omnichannel integration', 'https://oa.zalo.me/home/function/extension'),
('S74', 'Zalo OA — conversation operations and assignment', 'https://oa.zalo.me/home/resources/library/toi-uu-quy-trinh-cham-soc-khach-hang-tren-zalo-oa_6458345622407562285'),
('S75', 'Zalo OA — Mini Call Center and Zalo Cloud Connect', 'https://oa.zalo.me/home/call'),
('S76', 'Zalo OA — built-in chatbot', 'https://oa.zalo.me/home/resources/library/tu-dong-hoa-cham-soc-khach-hang-voi-zalo-chatbot_6352033339970702125'),
]

for sid, title, url in sources:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.first_line_indent = Inches(-0.18)
    p.paragraph_format.space_after = Pt(2.5)
    r = p.add_run(f'[{sid}] ')
    set_font(r, 9, True, NAVY)
    add_hyperlink(p, title, url)

doc.add_heading('Appendix B. Local Health19 evidence reviewed', level=1)
for path, note in [
    ('addons/health_crm/__manifest__.py', 'CRM Center, Odoo 19 version and existing OWL assets.'),
    ('addons/health_crm/views/crm_center_views.xml', 'Contact/client/list/calendar actions and Health19 workflow fields.'),
    ('addons/health_crm/static/src/js/', 'CRM Center sidebar, dashboard and contact/timeline components.'),
    ('addons/health_zalo/', 'OA OAuth/API/webhooks, conversations/messages, live bus and OWL chat surfaces.'),
    ('addons/health_voip24h/', 'Call logs, recordings, matching, click-to-dial and incoming popup services.'),
    ('addons/health_messaging/', 'ZNS/email/call fallback with off-by-default safety controls.'),
    ('addons/health_family_messages/', 'Consent-gated, encrypted, append-only family messaging.'),
]:
    bullet(f'{path} — {note}')

callout('FINAL PRODUCT PRINCIPLE', 'Make the safest next action feel effortless, and make every automated conclusion inspectable.', 'Recommendation')

# Core properties
doc.core_properties.title = 'Health19 Care Command Center — competitor study and implementation prompt'
doc.core_properties.subject = 'Omnichannel healthcare CRM, contact centre, UX and AI implementation brief'
doc.core_properties.author = 'Health19 product research'
doc.core_properties.keywords = 'Health19, Odoo 19, omnichannel, CRM, contact centre, Zalo, VoIP, healthcare, AI'

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print(OUT)
