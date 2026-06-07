#!/usr/bin/env python3
"""Merge and deploy one reviewed Odoo 19 core vi_VN code-translation override."""

import argparse
import datetime
import json
import pathlib
import subprocess

from po_catalog import parse_entries


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWED_MODULES = {"mail", "resource_mail", "web"}


def apply_overrides(base_catalog, overrides, module):
    lines = base_catalog.splitlines(keepends=True)
    entries = {
        entry["msgid"]: entry
        for entry in parse_entries(lines)
        if entry["msgid"]
    }
    missing = sorted(set(overrides) - set(entries))

    replacements = []
    for msgid, msgstr in overrides.items():
        if msgid in missing:
            continue
        entry = entries[msgid]
        replacement = f"msgstr {json.dumps(msgstr, ensure_ascii=False)}\n"
        replacements.append(
            (entry["msgstr_start"], entry["msgstr_end"], replacement)
        )

    for start, end, replacement in sorted(replacements, reverse=True):
        lines[start:end] = [replacement]

    still_missing = []
    for msgid in missing:
        obsolete_msgid = f"#~ msgid {json.dumps(msgid, ensure_ascii=False)}\n"
        try:
            index = lines.index(obsolete_msgid)
        except ValueError:
            still_missing.append(msgid)
            continue
        if index + 1 >= len(lines) or not lines[index + 1].startswith("#~ msgstr "):
            still_missing.append(msgid)
            continue
        lines[index : index + 2] = [
            f"#. module: {module}\n",
            "#. odoo-javascript\n",
            f"msgid {json.dumps(msgid, ensure_ascii=False)}\n",
            f"msgstr {json.dumps(overrides[msgid], ensure_ascii=False)}\n",
        ]

    for msgid in still_missing:
        lines.extend(
            [
                "\n",
                f"#. module: {module}\n",
                "#. odoo-javascript\n",
                f"msgid {json.dumps(msgid, ensure_ascii=False)}\n",
                f"msgstr {json.dumps(overrides[msgid], ensure_ascii=False)}\n",
            ]
        )
    return "".join(lines)


def catalog_values(path):
    return {
        entry["msgid"]: entry["msgstr"]
        for entry in parse_entries(
            path.read_text(encoding="utf-8").splitlines(keepends=True)
        )
        if entry["msgid"]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", choices=sorted(ALLOWED_MODULES))
    parser.add_argument("--host", default="VietUcUAT")
    args = parser.parse_args()

    override = (
        REPO_ROOT
        / "VietTranslation"
        / "core_overrides"
        / f"{args.module}_vi_VN.po"
    )
    if not override.is_file():
        parser.error(f"catalog does not exist: {override}")

    subprocess.run(
        ["msgfmt", "--check", "--check-format", "-o", "/dev/null", str(override)],
        check=True,
    )
    expected = catalog_values(override)

    date_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_catalog = f"/odoo/odoo-server/addons/{args.module}/i18n/vi.po"
    backup = (
        REPO_ROOT
        / "VietTranslation"
        / "po_backups"
        / "core"
        / f"{args.module}_vi_before_override_{date_stamp}.po"
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["scp", f"{args.host}:{remote_catalog}", str(backup)],
        check=True,
    )

    patched = (
        REPO_ROOT
        / "VietTranslation"
        / "reports"
        / "core_overrides"
        / f"{args.module}_vi_patched_{date_stamp}.po"
    )
    patched.parent.mkdir(parents=True, exist_ok=True)
    patched.write_text(
        apply_overrides(
            backup.read_text(encoding="utf-8"),
            expected,
            args.module,
        ),
        encoding="utf-8",
    )
    subprocess.run(
        ["msgfmt", "--check", "--check-format", "-o", "/dev/null", str(patched)],
        check=True,
    )

    remote_staging = f"/tmp/{args.module}_vi_core_override.po"
    subprocess.run(["scp", str(patched), f"{args.host}:{remote_staging}"], check=True)
    subprocess.run(
        [
            "ssh",
            args.host,
            (
                f"sudo install -o odoo -g ubuntu -m 0775 "
                f"{remote_staging} {remote_catalog}"
            ),
        ],
        check=True,
    )

    verification = patched.with_name(
        f"{args.module}_vi_deployed_{date_stamp}.po"
    )
    subprocess.run(
        ["scp", f"{args.host}:{remote_catalog}", str(verification)],
        check=True,
    )
    subprocess.run(
        [
            "msgfmt",
            "--check",
            "--check-format",
            "-o",
            "/dev/null",
            str(verification),
        ],
        check=True,
    )
    deployed = catalog_values(verification)
    mismatches = {
        msgid: (msgstr, deployed.get(msgid))
        for msgid, msgstr in expected.items()
        if deployed.get(msgid) != msgstr
    }
    if mismatches:
        details = "\n".join(
            f"{msgid!r}: expected {wanted!r}, deployed {found!r}"
            for msgid, (wanted, found) in sorted(mismatches.items())
        )
        raise RuntimeError(f"Core catalog deployment verification failed:\n{details}")

    print(
        f"Deployed and verified {len(expected)} reviewed translations "
        f"in {remote_catalog}"
    )
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
