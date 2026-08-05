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


def catalog_path(module):
    """Keep the module's existing Vietnamese filename, preferring vi.po."""
    i18n_dir = REPO_ROOT / "addons" / module / "i18n"
    for filename in ("vi.po", "vi_VN.po"):
        candidate = i18n_dir / filename
        if candidate.is_file():
            return candidate
    return i18n_dir / "vi.po"


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

    current = catalog_path(args.module)
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
    has_current = current.is_file() and current.stat().st_size > 0
    if current.is_file():
        shutil.copy2(current, backup)

    with tempfile.TemporaryDirectory() as temp_dir:
        combined = pathlib.Path(temp_dir) / "combined.po"
        if has_current:
            normalized = pathlib.Path(temp_dir) / "current-normalized.po"
            run(
                "msguniq",
                "--use-first",
                str(current),
                "-o",
                str(normalized),
            )
            if not normalized.is_file():
                shutil.copy2(current, normalized)
            run(
                "msgcat",
                "--use-first",
                str(normalized),
                str(args.export),
                "-o",
                str(combined),
            )
        else:
            shutil.copy2(args.export, combined)
        run(
            "msgmerge",
            "--no-fuzzy-matching",
            str(combined),
            str(args.export),
            "-o",
            str(output),
        )
        active_only = pathlib.Path(temp_dir) / "active-only.po"
        run("msgattrib", "--no-obsolete", str(output), "-o", str(active_only))
        shutil.copy2(active_only, output)

    run("msgfmt", "--check", "--check-format", "-o", "/dev/null", str(output))
    if has_current:
        print(f"Backup: {backup}")
    else:
        print(f"Initialized catalog: {current}")
    print(f"Candidate: {output}")

    if args.install:
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, current)
        print(f"Installed candidate at {current}")


if __name__ == "__main__":
    main()
