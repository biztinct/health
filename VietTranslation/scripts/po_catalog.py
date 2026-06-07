#!/usr/bin/env python3
"""Audit PO catalogs and apply reviewed, exact-match translations."""

import argparse
import ast
import json
import pathlib
import re
import sys


PLACEHOLDER_RE = re.compile(
    r"%(?:\([^)]+\))?[#0 +\-]?\d*(?:\.\d+)?[a-zA-Z](?!\w)|\{\w+\}"
)
TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
LOCALIZABLE_ATTRIBUTE_RE = re.compile(r'\s(?:title|alt|placeholder)="[^"]*"')


def decode_po_string(line):
    value = line.strip()
    if value.startswith(("msgid ", "msgstr ")):
        value = value.split(" ", 1)[1]
    return ast.literal_eval(value)


def parse_entries(lines):
    entries = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("msgid "):
            index += 1
            continue

        msgid_start = index
        msgid = decode_po_string(lines[index])
        index += 1
        while index < len(lines) and lines[index].startswith('"'):
            msgid += decode_po_string(lines[index])
            index += 1

        if index >= len(lines) or not lines[index].startswith("msgstr "):
            index += 1
            continue

        msgstr_start = index
        msgstr = decode_po_string(lines[index])
        index += 1
        while index < len(lines) and lines[index].startswith('"'):
            msgstr += decode_po_string(lines[index])
            index += 1

        flags = []
        cursor = msgid_start - 1
        while cursor >= 0 and lines[cursor].strip():
            if lines[cursor].startswith("#,"):
                flags.extend(part.strip() for part in lines[cursor][2:].split(","))
            cursor -= 1

        entries.append(
            {
                "msgid": msgid,
                "msgstr": msgstr,
                "msgstr_start": msgstr_start,
                "msgstr_end": index,
                "flags": flags,
            }
        )
    return entries


def markup_signature(text):
    tags = []
    for tag in TAG_RE.findall(text):
        tags.append(LOCALIZABLE_ATTRIBUTE_RE.sub("", tag))
    return tags


def audit(path, show_same_source=False):
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    entries = [entry for entry in parse_entries(lines) if entry["msgid"]]
    untranslated = [entry for entry in entries if not entry["msgstr"]]
    same_source = [
        entry
        for entry in entries
        if entry["msgstr"] and entry["msgstr"] == entry["msgid"]
    ]
    fuzzy = [entry for entry in entries if "fuzzy" in entry["flags"]]
    placeholder_mismatches = [
        entry
        for entry in entries
        if sorted(PLACEHOLDER_RE.findall(entry["msgid"]))
        != sorted(PLACEHOLDER_RE.findall(entry["msgstr"]))
    ]
    markup_mismatches = [
        entry
        for entry in entries
        if entry["msgstr"]
        and markup_signature(entry["msgid"]) != markup_signature(entry["msgstr"])
    ]

    print(f"Catalog: {path}")
    print(f"Entries: {len(entries)}")
    print(f"Translated: {len(entries) - len(untranslated)}")
    print(f"Untranslated: {len(untranslated)}")
    print(f"Same as source: {len(same_source)}")
    print(f"Fuzzy: {len(fuzzy)}")
    print(f"Placeholder mismatches: {len(placeholder_mismatches)}")
    print(f"HTML/XML markup mismatches: {len(markup_mismatches)}")

    if untranslated:
        print("\nUntranslated msgids:")
        for entry in untranslated:
            print(f"- {entry['msgid']!r}")

    if show_same_source and same_source:
        print("\nSame-as-source msgids:")
        for entry in same_source:
            print(f"- {entry['msgid']!r}")

    if placeholder_mismatches:
        print("\nPlaceholder mismatches:")
        for entry in placeholder_mismatches:
            print(f"- {entry['msgid']!r}")

    if markup_mismatches:
        print("\nHTML/XML markup mismatches:")
        for entry in markup_mismatches:
            print(f"- {entry['msgid']!r}")


def apply_mapping(path, mapping_path, output, overwrite=False):
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    entries = parse_entries(lines)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in mapping.items()
    ):
        raise ValueError("Mapping must be a JSON object of string msgid/msgstr pairs")

    available = {entry["msgid"] for entry in entries}
    unknown = sorted(set(mapping) - available)
    if unknown:
        print("Mapping contains msgids absent from the catalog:", file=sys.stderr)
        for msgid in unknown:
            print(f"- {msgid!r}", file=sys.stderr)
        return 2

    replacements = []
    for entry in entries:
        if entry["msgid"] not in mapping:
            continue
        if entry["msgstr"] and not overwrite:
            continue
        encoded = json.dumps(mapping[entry["msgid"]], ensure_ascii=False)
        replacements.append(
            (entry["msgstr_start"], entry["msgstr_end"], f"msgstr {encoded}\n")
        )

    for start, end, replacement in reversed(replacements):
        lines[start:end] = [replacement]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8")
    print(f"Applied {len(replacements)} reviewed translations to {output}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("catalog", type=pathlib.Path)
    audit_parser.add_argument("--show-same-source", action="store_true")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("catalog", type=pathlib.Path)
    apply_parser.add_argument("mapping", type=pathlib.Path)
    apply_parser.add_argument("--output", required=True, type=pathlib.Path)
    apply_parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()
    if args.command == "audit":
        audit(args.catalog, show_same_source=args.show_same_source)
        return 0
    return apply_mapping(
        args.catalog,
        args.mapping,
        args.output,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    raise SystemExit(main())
