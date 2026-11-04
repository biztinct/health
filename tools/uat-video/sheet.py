"""Write the "Video evidence" column of an acceptance-results workbook from the
run.json files the recordings leave in each test folder.

usage:
  python3 sheet.py <source.xlsx> <out.xlsx> [--root <evidence root>]
                   [--combined "[CT,BK=]<combined video name>.mp4" ...] [--notes notes.json]
                   [--sheet "Test Results"] [--date "4 Nov 2026"]

--combined may be given once per combined video, prefixed with the test-ID groups
it holds ("AS,CR=Assignment ... .mp4"); without a prefix it applies to every row.
Rows are matched by the "Test ID" column. Only tests that have a run.json are
written; other rows are left as they are. notes.json is {"CT-06": "Process: ..."}
for a sentence that the run data cannot say (how the business does the step).
Never overwrite the client's original file: write a dated copy (it may be open in
Excel, and the original is the client's record).
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone

import openpyxl
from openpyxl.styles import Alignment, Font

HEADER = 'Video evidence (on-screen retest)'
SITE = 'carejiox.com'
TZ_LABEL = 'Vietnam time'
TZ_OFFSET = timedelta(hours=7)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--root', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '../../outputs/carejiox-uat-20261029/video-evidence'))
    ap.add_argument('--combined', action='append', default=[])
    ap.add_argument('--notes', default='')
    ap.add_argument('--sheet', default='Test Results')
    ap.add_argument('--date', default=(datetime.now(timezone.utc) + TZ_OFFSET).strftime('%-d %b %Y'))
    a = ap.parse_args()

    runs = {}
    for d in sorted(os.listdir(a.root)):
        f = os.path.join(a.root, d, 'run.json')
        if os.path.isfile(f):
            with open(f, encoding='utf-8') as fh:
                r = json.load(fh)
            r['folder'] = d
            runs[r['id']] = r
    combined = {}                      # test-ID group ('' = any) -> combined video name
    for spec in a.combined:
        groups, sep, name = spec.partition('=')
        if not sep:
            groups, name = '', spec
        for g in groups.split(','):
            combined[g.strip()] = name
    notes = {}
    if a.notes:
        with open(a.notes, encoding='utf-8') as fh:
            notes = json.load(fh)

    wb = openpyxl.load_workbook(a.src)
    ws = wb[a.sheet]
    head_row = next(r for r in range(1, 10)
                    if any(str(c.value or '').strip() == 'Test ID' for c in ws[r]))
    heads = {str(c.value or '').strip(): c.column for c in ws[head_row]}
    id_col = heads['Test ID']
    col = heads.get(HEADER)
    if not col:
        col = ws.max_column + 1
        h = ws.cell(head_row, col, HEADER)
        src = ws.cell(head_row, col - 1)
        h.font, h.fill, h.border = src.font.copy(), src.fill.copy(), src.border.copy()
        h.alignment = Alignment(wrap_text=True, vertical='top')
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 60

    written = []
    for row in range(head_row + 1, ws.max_row + 1):
        tid = str(ws.cell(row, id_col).value or '').strip()
        r = runs.get(tid)
        if not r:
            continue
        n = len(r['proofs'])
        good = sum(1 for p in r['proofs'] if p['ok'])
        verdict = 'PASS' if r['passed'] else 'FAIL'
        recs = '; '.join(f'{k}: {v}' for k, v in r.get('records', {}).items())
        rel = f"video-evidence/{r['folder']}/{r['file']}"
        whole = combined.get(tid.split('-')[0], combined.get(''))
        text = (f"{verdict} — retested on screen on {SITE}, {a.date} ({TZ_LABEL}); "
                f"{good} of {n} on-screen checks matched."
                + (f" Records: {recs}." if recs else '')
                + (f" {notes[tid]}" if tid in notes else '')
                + f"\nVideo: {rel}  ({round(r['seconds'])} s)."
                + (f" Also chapter {tid} of “{whole}”." if whole else '')
                + f" Still images of each check: video-evidence/{r['folder']}/proof-screenshots/")
        if not r['passed']:
            text += ' Not matched: ' + '; '.join(
                f"{p['label']} — {p['detail']}" for p in r['proofs'] if not p['ok'])
        c = ws.cell(row, col, text)
        c.alignment = Alignment(wrap_text=True, vertical='top')
        c.font = Font(color='FF20333F' if r['passed'] else 'FFB91C1C')
        c.hyperlink = rel
        written.append(f'{tid} {verdict}')

    wb.save(a.out)
    print(f'{a.out}: ' + (', '.join(written) or 'no matching rows'))


if __name__ == '__main__':
    main()
