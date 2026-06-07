#!/usr/bin/env python3
"""Merge a fresh Odoo export with an existing reviewed module catalog."""

import argparse
import datetime
import pathlib
import re
import shutil
import subprocess
import tempfile


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def run(*command):
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module")
    parser.add_argument("export", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"(?:health_[a-z0-9_]+|advanced_pricing)", args.module):
        parser.error(
            "module must be a health_* technical module name or advanced_pricing"
        )

    current = REPO_ROOT / "addons" / args.module / "i18n" / "vi_VN.po"
    if not current.is_file():
        parser.error(f"current catalog does not exist: {current}")
    if not args.export.is_file():
        parser.error(f"fresh export does not exist: {args.export}")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = (
        REPO_ROOT
        / "VietTranslation"
        / "po_backups"
        / f"{args.module}_vi_VN_before_refresh_{stamp}.po"
    )
    output = args.output or (
        REPO_ROOT
        / "VietTranslation"
        / "exports"
        / args.module
        / "vi_VN_merged_candidate.po"
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, backup)

    with tempfile.TemporaryDirectory() as temp_dir:
        combined = pathlib.Path(temp_dir) / "combined.po"
        run(
            "msgcat",
            "--use-first",
            str(current),
            str(args.export),
            "-o",
            str(combined),
        )
        run(
            "msgmerge",
            "--no-fuzzy-matching",
            str(combined),
            str(args.export),
            "-o",
            str(output),
        )

    run("msgfmt", "--check", "--check-format", "-o", "/dev/null", str(output))
    print(f"Backup: {backup}")
    print(f"Candidate: {output}")

    if args.install:
        shutil.copy2(output, current)
        print(f"Installed candidate at {current}")


if __name__ == "__main__":
    main()
