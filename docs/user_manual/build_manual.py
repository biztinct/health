#!/usr/bin/env python3
"""Assemble the Viet UC CMS User Manual (.docx) from content/*.md + img/.

Reads the Markdown chapters (written from the drafting Workflow) using a small,
purpose-built parser matching the agreed convention, and builds a styled Word
document: cover page, auto Table-of-Contents field, heading styles, callout
boxes (Tip/Note/Warning), Markdown tables, bullet/numbered lists, embedded
screenshots (sized by orientation) with captions, page numbers, and a page
break per chapter.

Usage:  python3 build_manual.py
Then:   soffice --headless --convert-to pdf VietUC_CMS_User_Manual.docx
"""
import glob
import os
import re
import struct

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, 'img')
CONTENT = os.path.join(HERE, 'content')
OUT = os.path.join(HERE, 'VietUC_CMS_User_Manual.docx')

BRAND = RGBColor(0x1A, 0x23, 0x7E)      # navy
ACCENT = RGBColor(0xFB, 0x8C, 0x00)     # hibiscus orange
CALLOUT = {
    'Tip': (RGBColor(0x1B, 0x5E, 0x20), 'E8F5E9'),
    'Note': (RGBColor(0x0D, 0x47, 0xA1), 'E3F2FD'),
    'Warning': (RGBColor(0xB7, 0x1C, 0x1C), 'FFEBEE'),
}


# ----------------------------------------------------------------- helpers
def png_size(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(24)
        if head[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', head[16:24])
            return w, h
    except Exception:
        pass
    return None


def set_cell_shading(cell, fill_hex):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), fill_hex)
    cell._tc.get_or_add_tcPr().append(shd)


def create_decimal_numbering(doc):
    """Create a fresh decimal numbering definition; returns its numId.
    A new numId per list makes each numbered list restart at 1."""
    np = doc.part.numbering_part
    numbering = np.element
    abs_ids = [int(e.get(qn('w:abstractNumId'))) for e in numbering.findall(qn('w:abstractNum'))]
    num_ids = [int(e.get(qn('w:numId'))) for e in numbering.findall(qn('w:num'))]
    new_abs = (max(abs_ids) + 1) if abs_ids else 0
    new_num = (max(num_ids) + 1) if num_ids else 1
    abstractNum = OxmlElement('w:abstractNum'); abstractNum.set(qn('w:abstractNumId'), str(new_abs))
    lvl = OxmlElement('w:lvl'); lvl.set(qn('w:ilvl'), '0')
    for tag, val in [('w:start', '1'), ('w:numFmt', 'decimal'), ('w:lvlText', '%1.'), ('w:lvlJc', 'left')]:
        e = OxmlElement(tag); e.set(qn('w:val'), val); lvl.append(e)
    pPr = OxmlElement('w:pPr'); ind = OxmlElement('w:ind')
    ind.set(qn('w:left'), '720'); ind.set(qn('w:hanging'), '360'); pPr.append(ind); lvl.append(pPr)
    abstractNum.append(lvl)
    num = OxmlElement('w:num'); num.set(qn('w:numId'), str(new_num))
    absref = OxmlElement('w:abstractNumId'); absref.set(qn('w:val'), str(new_abs)); num.append(absref)
    numbering.insert(0, abstractNum)
    numbering.append(num)
    return new_num


def apply_numbering(paragraph, num_id):
    pPr = paragraph._p.get_or_add_pPr()
    numPr = OxmlElement('w:numPr')
    ilvl = OxmlElement('w:ilvl'); ilvl.set(qn('w:val'), '0'); numPr.append(ilvl)
    nid = OxmlElement('w:numId'); nid.set(qn('w:val'), str(num_id)); numPr.append(nid)
    pPr.append(numPr)


def add_runs(paragraph, text):
    """Render inline **bold** and `code`."""
    for part in re.split(r'(\*\*.+?\*\*|`.+?`)', text):
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            r = paragraph.add_run(part[2:-2]); r.bold = True
        elif part.startswith('`') and part.endswith('`'):
            r = paragraph.add_run(part[1:-1]); r.font.name = 'Consolas'; r.font.size = Pt(9.5)
        else:
            paragraph.add_run(part)


def add_toc(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    for kind, txt in [('begin', None), ('instr', 'TOC \\o "1-3" \\h \\z \\u'),
                      ('separate', None), ('text', 'Update this field (select all, press F9) to build the contents.'),
                      ('end', None)]:
        if kind == 'instr':
            e = OxmlElement('w:instrText'); e.set(qn('xml:space'), 'preserve'); e.text = txt
        elif kind == 'text':
            e = OxmlElement('w:t'); e.text = txt
        else:
            e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), kind)
        run._r.append(e)


def add_page_number_footer(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run('Viet UC CMS — User Manual    |    Page ')
    for kind, txt in [('begin', None), ('instr', 'PAGE'), ('end', None)]:
        if kind == 'instr':
            e = OxmlElement('w:instrText'); e.set(qn('xml:space'), 'preserve'); e.text = txt
        else:
            e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), kind)
        p.add_run()._r.append(e)


def add_image(doc, filename, caption):
    path = os.path.join(IMG, filename)
    if not os.path.exists(path):
        doc.add_paragraph('[missing screenshot: %s]' % filename)
        return
    size = png_size(path)
    width = Inches(6.2)
    if size and size[1] and size[0] / size[1] < 0.9:   # portrait (mobile)
        width = Inches(2.6)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=width)
    cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cap.add_run('Figure: ' + caption); r.italic = True; r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)


def add_callout(doc, kind, text):
    color, fill = CALLOUT[kind]
    tbl = doc.add_table(rows=1, cols=1)
    tbl.style = 'Table Grid'
    cell = tbl.cell(0, 0)
    set_cell_shading(cell, fill)
    p = cell.paragraphs[0]
    lbl = p.add_run(kind.upper() + '  '); lbl.bold = True; lbl.font.color.rgb = color
    add_runs(p, text)
    doc.add_paragraph()


def add_md_table(doc, rows):
    cols = max(len(r) for r in rows)
    tbl = doc.add_table(rows=0, cols=cols)
    tbl.style = 'Light Grid Accent 1'
    for ri, row in enumerate(rows):
        cells = tbl.add_row().cells
        for ci in range(cols):
            txt = row[ci] if ci < len(row) else ''
            cell = cells[ci]
            cell.paragraphs[0].text = ''
            add_runs(cell.paragraphs[0], txt)
            if ri == 0:
                for rn in cell.paragraphs[0].runs:
                    rn.bold = True
    doc.add_paragraph()


# --------------------------------------------------------------- md parser
IMG_RE = re.compile(r'^!\[(.*?)\]\(IMG:(.+?)\)\s*$')
CALLOUT_RE = re.compile(r'^\*\*(Tip|Note|Warning):\*\*\s*(.*)$')


def render_markdown(doc, md):
    lines = md.split('\n')
    i = 0
    cur_num_id = None   # active numbered-list id; reset whenever a non-list line appears
    while i < len(lines):
        line = lines[i].rstrip()
        is_numbered = bool(re.match(r'^\s*\d+[.)]\s+', line))
        if not is_numbered:
            cur_num_id = None
        if not line.strip():
            i += 1
            continue
        # image
        m = IMG_RE.match(line)
        if m:
            add_image(doc, m.group(2).strip(), m.group(1).strip() or m.group(2))
            i += 1
            continue
        # callout
        m = CALLOUT_RE.match(line)
        if m:
            add_callout(doc, m.group(1), m.group(2))
            i += 1
            continue
        # table block
        if line.lstrip().startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|?[\s:|-]+\|?\s*$', lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                raw = lines[i].strip().strip('|')
                if re.match(r'^[\s:|-]+$', raw):
                    i += 1
                    continue
                rows.append([c.strip() for c in raw.split('|')])
                i += 1
            add_md_table(doc, rows)
            continue
        # headings
        if line.startswith('# '):
            if getattr(doc, '_seen_h1', False):
                doc.add_page_break()
            doc._seen_h1 = True
            doc.add_heading(line[2:].strip(), level=1)
            i += 1
            continue
        if line.startswith('## '):
            doc.add_heading(line[3:].strip(), level=2)
            i += 1
            continue
        if line.startswith('### '):
            doc.add_heading(line[4:].strip(), level=3)
            i += 1
            continue
        if line.startswith('#### '):
            doc.add_heading(line[5:].strip(), level=4)
            i += 1
            continue
        # numbered list (each fresh list restarts at 1 via its own numId)
        m = re.match(r'^\s*\d+[.)]\s+(.*)$', line)
        if m:
            if cur_num_id is None:
                cur_num_id = create_decimal_numbering(doc)
            p = doc.add_paragraph(style='List Paragraph')
            apply_numbering(p, cur_num_id)
            add_runs(p, m.group(1))
            i += 1
            continue
        # bullet list
        m = re.match(r'^\s*[-*]\s+(.*)$', line)
        if m:
            p = doc.add_paragraph(style='List Bullet')
            add_runs(p, m.group(1))
            i += 1
            continue
        # plain paragraph
        p = doc.add_paragraph()
        add_runs(p, line)
        i += 1


# ------------------------------------------------------------------- build
def build():
    doc = Document()
    # base styles
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)
    for lvl, sz, col in [(1, 20, BRAND), (2, 15, BRAND), (3, 12.5, ACCENT)]:
        st = doc.styles['Heading %d' % lvl]
        st.font.size = Pt(sz); st.font.color.rgb = col; st.font.bold = True

    # ---- cover page
    for _ in range(4):
        doc.add_paragraph()
    t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run('VIET UC CMS'); r.bold = True; r.font.size = Pt(40); r.font.color.rgb = BRAND
    s = doc.add_paragraph(); s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = s.add_run('User Manual'); r.font.size = Pt(26); r.font.color.rgb = ACCENT
    sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run('Home Healthcare Operations Platform'); r.font.size = Pt(13); r.italic = True
    for _ in range(8):
        doc.add_paragraph()
    meta = doc.add_paragraph(); meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run('Comprehensive guide to every menu and workflow — web + mobile\n').italic = True
    meta.add_run('Version 1.0').bold = True
    doc.add_page_break()

    # ---- TOC page (title is a plain styled paragraph, NOT a Heading,
    #      so it does not list itself inside the contents)
    toc_title = doc.add_paragraph()
    r = toc_title.add_run('Table of Contents'); r.bold = True; r.font.size = Pt(20); r.font.color.rgb = BRAND
    doc._seen_h1 = True  # so the first real chapter still page-breaks
    note = doc.add_paragraph()
    add_runs(note, '**Note:** This is an editable Word document. To refresh the page numbers below, select all (Ctrl+A / Cmd+A) and press F9, then choose "Update entire table". The PDF version already has them filled in.')
    add_toc(doc)
    doc.add_page_break()
    doc._seen_h1 = False  # next "# " starts chapters without an extra leading break

    # ---- chapters in filename order
    files = sorted(glob.glob(os.path.join(CONTENT, '*.md')))
    if not files:
        raise SystemExit('No content/*.md files found — run the drafting step first.')
    for path in files:
        with open(path, encoding='utf-8') as f:
            render_markdown(doc, f.read())

    # ---- footer page numbers on the body section
    add_page_number_footer(doc.sections[0])

    # tell Word/LibreOffice to update fields (incl. the TOC) on open
    upd = OxmlElement('w:updateFields'); upd.set(qn('w:val'), 'true')
    doc.settings.element.append(upd)

    doc.save(OUT)
    print('Wrote', OUT)
    return OUT


if __name__ == '__main__':
    build()
