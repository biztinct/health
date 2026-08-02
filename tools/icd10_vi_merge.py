#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge a MOH-KCB Vietnamese ICD-10 translation into the importer CSV
(health19 GC-2 / D4).

Input A is the five-column importer CSV produced by `icd10_claml_to_csv.py`
(or any file with the same header). Input B is the MOH translation table,
keyed by ICD-10 code. Output is input A with `display_vi` filled in.

Nothing is ever dropped silently:

- a translation whose code is NOT in the base file is written to
  `--unmatched-out` (default `<output>.unmatched.csv`) and counted;
- a base row with no translation keeps its (empty) `display_vi`, is counted,
  and can be listed with `--report-untranslated`.

CSV only, standard library only. The MOH file usually arrives as .xlsx —
convert it first (LibreOffice: `soffice --headless --convert-to csv file.xlsx`,
or Excel "Save As → CSV UTF-8"), because a spreadsheet parser is a dependency
this repo does not need and the server must not grow (conventions §1).

Usage
-----
    python3 tools/icd10_vi_merge.py icd10.csv moh_vi.csv -o icd10_vi.csv
    python3 tools/icd10_vi_merge.py icd10.csv moh_vi.csv -o out.csv \\
        --vi-code-col "Mã ICD" --vi-display-col "Tên tiếng Việt"
"""

import argparse
import csv
import sys

BASE_COLUMNS = ['code', 'display', 'display_vi', 'parent_code', 'synonyms']
# Header spellings seen in MOH-KCB / hospital exports, lowercased.
CODE_HEADERS = ('code', 'icd10', 'icd-10', 'ma icd', 'mã icd', 'ma_icd',
                'mabenh', 'mã bệnh', 'ma benh')
VI_HEADERS = ('display_vi', 'vi', 'tieng viet', 'tiếng việt', 'ten benh',
              'tên bệnh', 'ten tieng viet', 'tên tiếng việt', 'tenbenh',
              'vietnamese')


def normalize_code(value):
    """ICD-10 codes travel with and without the dot, and spreadsheets love a
    stray space or a lowercase letter. Compare on a canonical form; the base
    file's own spelling is what gets written out."""
    return (value or '').strip().upper().replace('.', '').replace(' ', '')


def pick_column(header, candidates, explicit, what):
    if explicit:
        if explicit not in header:
            raise SystemExit('error: column %r not found in the translation '
                             'file (header: %s)' % (explicit, ', '.join(header)))
        return header.index(explicit)
    for index, name in enumerate(header):
        if (name or '').strip().lower() in candidates:
            return index
    raise SystemExit(
        'error: could not identify the %s column in the translation file. '
        'Header is: %s — pass it explicitly.' % (what, ', '.join(header)))


def read_translations(path, code_col, vi_col):
    with open(path, encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise SystemExit('error: %s is empty' % path)
    header = rows[0]
    code_index = pick_column(header, CODE_HEADERS, code_col, 'code')
    vi_index = pick_column(header, VI_HEADERS, vi_col, 'Vietnamese display')
    table, order = {}, []
    for row in rows[1:]:
        if len(row) <= max(code_index, vi_index):
            continue
        code, display_vi = row[code_index].strip(), row[vi_index].strip()
        if not code or not display_vi:
            continue
        key = normalize_code(code)
        if key not in table:
            order.append((code, display_vi))
        table[key] = display_vi
    return table, order


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Fill display_vi in an importer CSV from a MOH-KCB '
                    'translation table')
    parser.add_argument('base', help='importer CSV (5 columns)')
    parser.add_argument('translations', help='MOH translation CSV')
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('--unmatched-out', default=None,
                        help='where to write translations with no matching '
                             'code (default: <output>.unmatched.csv)')
    parser.add_argument('--vi-code-col', default=None)
    parser.add_argument('--vi-display-col', default=None)
    parser.add_argument('--overwrite', action='store_true',
                        help='replace a display_vi the base file already '
                             'carries (default: keep it)')
    parser.add_argument('--report-untranslated', action='store_true',
                        help='list the codes left without Vietnamese')
    args = parser.parse_args(argv)

    table, _order = read_translations(
        args.translations, args.vi_code_col, args.vi_display_col)

    with open(args.base, encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise SystemExit('error: %s is empty' % args.base)
    header = [c.strip() for c in rows[0]]
    if header[:len(BASE_COLUMNS)] != BASE_COLUMNS:
        raise SystemExit('error: %s does not start with the importer header '
                         '%s (got %s)' % (args.base, BASE_COLUMNS, header))

    used, filled, kept, untranslated = set(), 0, 0, []
    out_rows = []
    for row in rows[1:]:
        row = list(row) + [''] * (len(BASE_COLUMNS) - len(row))
        key = normalize_code(row[0])
        translation = table.get(key)
        if translation and (args.overwrite or not row[2].strip()):
            row[2] = translation
            filled += 1
            used.add(key)
        elif translation:
            kept += 1
            used.add(key)
        else:
            untranslated.append(row[0])
        out_rows.append(row)

    with open(args.output, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(BASE_COLUMNS)
        writer.writerows(out_rows)

    unmatched = [(code, display) for code, display in _order
                 if normalize_code(code) not in used]
    unmatched_path = args.unmatched_out or (args.output + '.unmatched.csv')
    if unmatched:
        with open(unmatched_path, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle, lineterminator='\n')
            writer.writerow(['code', 'display_vi'])
            writer.writerows(unmatched)

    print('base rows          : %d' % len(out_rows), file=sys.stderr)
    print('translations read  : %d' % len(table), file=sys.stderr)
    print('display_vi filled  : %d' % filled, file=sys.stderr)
    print('display_vi kept    : %d' % kept, file=sys.stderr)
    print('untranslated rows  : %d' % len(untranslated), file=sys.stderr)
    print('unmatched codes    : %d%s'
          % (len(unmatched), (' → %s' % unmatched_path) if unmatched else ''),
          file=sys.stderr)
    if args.report_untranslated and untranslated:
        print('untranslated: %s' % ', '.join(untranslated), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
