#!/usr/bin/env python3
"""Fill blank health_* PO entries from unambiguous reviewed health translations."""

import argparse
import collections
import json
import pathlib
import subprocess

from po_catalog import markup_signature, parse_entries, placeholder_signature


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def catalogs():
    for module_dir in sorted((REPO_ROOT / "addons").glob("health_*")):
        for filename in ("vi.po", "vi_VN.po"):
            catalog = module_dir / "i18n" / filename
            if catalog.is_file():
                yield catalog
                break


def valid_pair(msgid, msgstr):
    return (
        bool(msgstr)
        and msgstr != msgid
        and placeholder_signature(msgid) == placeholder_signature(msgstr)
        and markup_signature(msgid) == markup_signature(msgstr)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    paths = list(catalogs())
    translations = collections.defaultdict(set)
    parsed = {}
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        entries = parse_entries(lines)
        parsed[path] = (lines, entries)
        for entry in entries:
            if "fuzzy" not in entry["flags"] and valid_pair(
                entry["msgid"], entry["msgstr"]
            ):
                translations[entry["msgid"]].add(entry["msgstr"])

    memory = {
        msgid: next(iter(values))
        for msgid, values in translations.items()
        if len(values) == 1
    }
    conflicts = {msgid: values for msgid, values in translations.items() if len(values) > 1}
    total = 0
    changed_files = 0
    for path, (lines, entries) in parsed.items():
        replacements = []
        for entry in entries:
            if entry["msgstr"] or entry["msgid"] not in memory:
                continue
            replacements.append(
                (
                    entry["msgstr_start"],
                    entry["msgstr_end"],
                    "msgstr "
                    + json.dumps(memory[entry["msgid"]], ensure_ascii=False)
                    + "\n",
                )
            )
        if not replacements:
            continue
        total += len(replacements)
        changed_files += 1
        print(f"{path.relative_to(REPO_ROOT)}: {len(replacements)}")
        if args.apply:
            for start, end, replacement in reversed(replacements):
                lines[start:end] = [replacement]
            path.write_text("".join(lines), encoding="utf-8")
            subprocess.run(
                [
                    "msgfmt",
                    "--check",
                    "--check-format",
                    "-o",
                    "/dev/null",
                    str(path),
                ],
                check=True,
            )

    action = "Applied" if args.apply else "Would apply"
    print(f"{action} {total} translations across {changed_files} catalogs")
    print(f"Skipped {len(conflicts)} conflicting translation-memory msgids")


if __name__ == "__main__":
    main()
