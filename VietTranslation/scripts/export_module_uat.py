#!/usr/bin/env python3
"""Export one installed module's vi_VN catalog from VietUcUAT."""

import argparse
import datetime
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
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if not re.fullmatch(r"(?:health_[a-z0-9_]+|advanced_pricing)", args.module):
        parser.error(
            "module must be a health_* technical module name or advanced_pricing"
        )

    date_stamp = datetime.date.today().strftime("%Y%m%d")
    output = args.output or (
        REPO_ROOT
        / "VietTranslation"
        / "exports"
        / args.module
        / f"vi_VN_odoo19_export_{date_stamp}.po"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    remote_path = f"/tmp/{args.module}_vi_VN_export.po"
    remote_code = f"""
import io
from odoo.tools.translate import trans_export

module = env['ir.module.module'].search([
    ('name', '=', {args.module!r}),
    ('state', '=', 'installed'),
], limit=1)
if not module:
    raise RuntimeError('Installed module not found: {args.module}')

buffer = io.BytesIO()
trans_export('vi_VN', [{args.module!r}], buffer, 'po', env)
with open({remote_path!r}, 'wb') as export_file:
    export_file.write(buffer.getvalue())
print({remote_path!r})
"""
    remote_command = (
        f"sudo -u odoo python3 {args.odoo_bin} shell "
        f"-c {args.config} -d {args.database} --no-http "
        f"--pidfile=/tmp/odoo-translation-export-{args.module}.pid"
    )
    subprocess.run(
        ["ssh", args.host, remote_command],
        input=remote_code,
        text=True,
        check=True,
    )
    subprocess.run(
        ["scp", f"{args.host}:{remote_path}", str(output)],
        check=True,
    )
    subprocess.run(
        ["msgfmt", "--check", "--check-format", "-o", "/dev/null", str(output)],
        check=True,
    )
    print(f"Exported {args.module} to {output}")


if __name__ == "__main__":
    main()
