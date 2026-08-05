#!/usr/bin/env python3
"""Apply an exact msgid/msgstr JSON mapping to blank health_* PO entries."""

import argparse
import json
import pathlib
import subprocess

from po_catalog import parse_entries


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=pathlib.Path)
    args = parser.parse_args()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    total = 0
    changed = 0
    for module_dir in sorted((REPO_ROOT / "addons").glob("health_*")):
        catalog = next(
            (
                path
                for path in (
                    module_dir / "i18n" / "vi.po",
                    module_dir / "i18n" / "vi_VN.po",
                )
                if path.is_file()
            ),
            None,
        )
        if catalog is None:
            continue
        lines = catalog.read_text(encoding="utf-8").splitlines(keepends=True)
        replacements = []
        for entry in parse_entries(lines):
            if entry["msgstr"] or entry["msgid"] not in mapping:
                continue
            replacements.append(
                (
                    entry["msgstr_start"],
                    entry["msgstr_end"],
                    "msgstr "
                    + json.dumps(mapping[entry["msgid"]], ensure_ascii=False)
                    + "\n",
                )
            )
        if not replacements:
            continue
        for start, end, replacement in reversed(replacements):
            lines[start:end] = [replacement]
        catalog.write_text("".join(lines), encoding="utf-8")
        subprocess.run(
            ["msgfmt", "--check", "--check-format", "-o", "/dev/null", str(catalog)],
            check=True,
        )
        total += len(replacements)
        changed += 1
        print(f"{catalog.relative_to(REPO_ROOT)}: {len(replacements)}")
    print(f"Applied {total} translations across {changed} catalogs")


if __name__ == "__main__":
    main()
