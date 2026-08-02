#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WHO ICD-10 ClaML XML → the `medical.code.import` CSV (health19 GC-2 / D4).

The WHO distributes ICD-10 as ClaML (Classification Markup Language). This
converter turns one ClaML file into the five-column CSV the Odoo importer
wizard already accepts:

    code,display,display_vi,parent_code,synonyms

`display_vi` is emitted EMPTY — the Vietnamese column is filled by
`icd10_vi_merge.py` from the MOH-KCB translation table, as a separate step, so
that a re-run of either side cannot silently overwrite the other.

Standard library only, and it never talks to the network: the WHO release is
licensed content that a human accepts and downloads (see
docs/conformance/icd10-load-runbook.md). This script only transforms a file
that is already on disk.

Usage
-----
    python3 tools/icd10_claml_to_csv.py ICD10_2019_ClaML.xml -o icd10.csv
    python3 tools/icd10_claml_to_csv.py icd10.xml --chapter I --chapter E \
        -o icd10_IE.csv

Exit status is 0 on success, 1 on an unreadable/unparsable input.
"""

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from collections import Counter

# ClaML elements we deliberately consume. Anything else inside a <Class> is
# counted and skipped — reported at the end, never silently dropped.
HANDLED_CLASS_CHILDREN = {'SuperClass', 'SubClass', 'Rubric', 'Meta'}
# Rubric kinds: 'preferred' is the display; these become `synonyms`.
SYNONYM_KINDS = ('inclusion', 'preferredLong', 'text')
# Class kinds that are real, importable codes. 'chapter'/'block' rows carry the
# hierarchy, so they are kept too — the importer resolves parent_code by code.
KEPT_KINDS = ('chapter', 'block', 'category', 'subcategory', 'modifiedcategory')


def label_text(node):
    """Flatten a <Label>, dropping the inline markup ClaML uses inside it
    (<Reference>, <Term>, <Fragment>, <Include>). `itertext` keeps the words
    in document order; whitespace is normalized so the CSV stays one line."""
    return ' '.join(''.join(node.itertext()).split())


def rubric_labels(class_node, kind):
    labels = []
    for rubric in class_node.findall('Rubric'):
        if rubric.get('kind') != kind:
            continue
        for label in rubric.findall('Label'):
            text = label_text(label)
            if text:
                labels.append(text)
    return labels


def parse_classes(path, unknown_counter):
    """Yield one dict per <Class>. Uses iterparse + clear() so a 60 MB WHO
    release does not need 1 GB of RAM."""
    for _event, elem in ET.iterparse(path, events=('end',)):
        if elem.tag != 'Class':
            continue
        code = (elem.get('code') or '').strip()
        kind = (elem.get('kind') or '').strip()
        for child in elem:
            if child.tag not in HANDLED_CLASS_CHILDREN:
                unknown_counter[child.tag] += 1
        preferred = rubric_labels(elem, 'preferred')
        synonyms = []
        for syn_kind in SYNONYM_KINDS:
            synonyms.extend(rubric_labels(elem, syn_kind))
        supers = [s.get('code') for s in elem.findall('SuperClass')
                  if s.get('code')]
        yield {
            'code': code,
            'kind': kind,
            'display': preferred[0] if preferred else '',
            'parent_code': supers[0] if supers else '',
            # ';' is the importer's synonym separator, so it must not appear
            # inside a synonym.
            'synonyms': ';'.join(s.replace(';', ',') for s in synonyms),
        }
        elem.clear()


def root_chapter(code, parents, cache):
    """Walk SuperClass links up to the chapter. Cycle-safe (a malformed file
    must not hang the converter)."""
    seen = set()
    current = code
    while current and current not in seen:
        seen.add(current)
        parent = parents.get(current)
        if not parent:
            return current
        if parent in cache:
            return cache[parent]
        current = parent
    return current


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='WHO ICD-10 ClaML XML → medical.code.import CSV')
    parser.add_argument('claml', help='ClaML XML file (already downloaded)')
    parser.add_argument('-o', '--output', default='-',
                        help='output CSV path (default: stdout)')
    parser.add_argument('--chapter', action='append', default=[],
                        metavar='CODE',
                        help='keep only this chapter (repeatable, e.g. -- '
                             '--chapter I --chapter E)')
    parser.add_argument('--include-kinds', default=','.join(KEPT_KINDS),
                        help='comma-separated Class kinds to keep '
                             '(default: %(default)s)')
    args = parser.parse_args(argv)

    kept_kinds = {k.strip() for k in args.include_kinds.split(',') if k.strip()}
    unknown = Counter()
    try:
        classes = list(parse_classes(args.claml, unknown))
    except (OSError, ET.ParseError) as exc:
        print('error: cannot read %s: %s' % (args.claml, exc), file=sys.stderr)
        return 1

    parents = {c['code']: c['parent_code'] for c in classes if c['code']}
    chapter_cache = {}
    wanted_chapters = set(args.chapter)

    rows, skipped_kind, skipped_chapter, skipped_no_display = [], 0, 0, 0
    for cls in classes:
        if not cls['code']:
            continue
        if cls['kind'] and cls['kind'] not in kept_kinds:
            skipped_kind += 1
            continue
        if wanted_chapters:
            chapter = root_chapter(cls['code'], parents, chapter_cache)
            chapter_cache[cls['code']] = chapter
            if chapter not in wanted_chapters:
                skipped_chapter += 1
                continue
        if not cls['display']:
            # The importer would count this as malformed anyway; drop it here
            # so the CSV that reaches the wizard is clean, and report it.
            skipped_no_display += 1
            continue
        rows.append([cls['code'], cls['display'], '',
                     cls['parent_code'], cls['synonyms']])

    handle = (sys.stdout if args.output == '-'
              else open(args.output, 'w', encoding='utf-8', newline=''))
    try:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(['code', 'display', 'display_vi', 'parent_code',
                         'synonyms'])
        writer.writerows(rows)
    finally:
        if handle is not sys.stdout:
            handle.close()

    print('classes read      : %d' % len(classes), file=sys.stderr)
    print('rows written      : %d' % len(rows), file=sys.stderr)
    print('skipped (kind)    : %d' % skipped_kind, file=sys.stderr)
    print('skipped (chapter) : %d' % skipped_chapter, file=sys.stderr)
    print('skipped (no label): %d' % skipped_no_display, file=sys.stderr)
    if unknown:
        print('unhandled ClaML elements inside <Class> (skipped): %s'
              % ', '.join('%s=%d' % item for item in sorted(unknown.items())),
              file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
