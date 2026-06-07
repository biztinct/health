#!/usr/bin/env python3
"""Validate and import one module's vi_VN PO into VietUcUAT with overwrite."""

import argparse
import pathlib
import re
import subprocess


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module")
    parser.add_argument("--host", default="VietUcUAT")
    parser.add_argument("--database", default="vietuat")
    parser.add_argument("--config", default="/etc/odoo-server.conf")
    parser.add_argument("--odoo-bin", default="/odoo/odoo-server/odoo-bin")
    parser.add_argument("--catalog", type=pathlib.Path)
    args = parser.parse_args()

    if not re.fullmatch(r"(?:health_[a-z0-9_]+|advanced_pricing)", args.module):
        parser.error(
            "module must be a health_* technical module name or advanced_pricing"
        )

    catalog = args.catalog or (
        REPO_ROOT / "addons" / args.module / "i18n" / "vi_VN.po"
    )
    if not catalog.is_file():
        parser.error(f"catalog does not exist: {catalog}")

    subprocess.run(
        ["msgfmt", "--check", "--check-format", "-o", "/dev/null", str(catalog)],
        check=True,
    )

    remote_path = f"/tmp/{args.module}_vi_VN_import.po"
    subprocess.run(
        ["scp", str(catalog), f"{args.host}:{remote_path}"],
        check=True,
    )
    remote_code = f"""
from odoo.tools.translate import TranslationImporter

module = env['ir.module.module'].search([
    ('name', '=', {args.module!r}),
    ('state', '=', 'installed'),
], limit=1)
if not module:
    raise RuntimeError('Installed module not found: {args.module}')

importer = TranslationImporter(env.cr)
with open({remote_path!r}, 'rb') as catalog:
    importer.load(catalog, 'po', 'vi_VN', module={args.module!r})
importer.save(overwrite=True, force_overwrite=True)
env.cr.commit()
print('Imported {args.module} vi_VN with overwrite=True, force_overwrite=True')
"""
    remote_command = (
        f"sudo -u odoo python3 {args.odoo_bin} shell "
        f"-c {args.config} -d {args.database} --no-http "
        f"--pidfile=/tmp/odoo-translation-import-{args.module}.pid"
    )
    subprocess.run(
        ["ssh", args.host, remote_command],
        input=remote_code,
        text=True,
        check=True,
    )


if __name__ == "__main__":
    main()
