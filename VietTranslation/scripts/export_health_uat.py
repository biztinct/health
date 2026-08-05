#!/usr/bin/env python3
"""Export every installed health_* vi_VN catalog from VietUcUAT in one session."""

import argparse
import datetime
import pathlib
import re
import subprocess
import tarfile
import tempfile


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_RE = re.compile(r"health_[a-z0-9_]+")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="VietUcUAT")
    parser.add_argument("--database", default="vietuat")
    parser.add_argument("--config", default="/etc/odoo-server.conf")
    parser.add_argument("--odoo-bin", default="/odoo/odoo-server/odoo-bin")
    parser.add_argument(
        "--reuse-remote-archive",
        action="store_true",
        help="copy the existing /tmp archive without running Odoo export again",
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=REPO_ROOT / "VietTranslation" / "exports",
    )
    args = parser.parse_args()

    remote_archive = "/tmp/health_vi_VN_exports.tar.gz"
    remote_code = f"""
import io
import pathlib
import shutil
import tarfile
import tempfile
from odoo.tools.translate import trans_export

modules = env['ir.module.module'].search([
    ('name', '=like', 'health_%'),
    ('state', '=', 'installed'),
], order='name')
temp_dir = pathlib.Path(tempfile.mkdtemp(prefix='health-translation-export-'))
try:
    for module in modules:
        buffer = io.BytesIO()
        trans_export('vi_VN', [module.name], buffer, 'po', env)
        (temp_dir / f'{{module.name}}.po').write_bytes(buffer.getvalue())
    with tarfile.open({remote_archive!r}, 'w:gz') as archive:
        for catalog in sorted(temp_dir.glob('health_*.po')):
            archive.add(catalog, arcname=catalog.name)
finally:
    shutil.rmtree(temp_dir)
print(f'Exported {{len(modules)}} installed health modules')
"""
    remote_command = (
        f"sudo -u odoo python3 {args.odoo_bin} shell "
        f"-c {args.config} -d {args.database} --no-http "
        "--pidfile=/tmp/odoo-health-translation-export.pid"
    )
    if not args.reuse_remote_archive:
        subprocess.run(
            ["ssh", args.host, remote_command],
            input=remote_code,
            text=True,
            check=True,
        )

    date_stamp = datetime.date.today().strftime("%Y%m%d")
    with tempfile.TemporaryDirectory() as temp_dir:
        local_archive = pathlib.Path(temp_dir) / "health_vi_VN_exports.tar.gz"
        subprocess.run(
            ["scp", f"{args.host}:{remote_archive}", str(local_archive)],
            check=True,
        )
        with tarfile.open(local_archive, "r:gz") as archive:
            members = archive.getmembers()
            if not members or any(
                not member.isfile() or not MODULE_RE.fullmatch(pathlib.Path(member.name).stem)
                for member in members
            ):
                raise RuntimeError("Remote export contained an unexpected archive member")
            for member in members:
                module = pathlib.Path(member.name).stem
                output = (
                    args.output_dir
                    / module
                    / f"vi_VN_odoo19_export_{date_stamp}.po"
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Could not read {member.name}")
                content = source.read()
                if not content:
                    output.unlink(missing_ok=True)
                    print(f"Skipped empty export: {module}")
                    continue
                output.write_bytes(content)
                subprocess.run(
                    [
                        "msgfmt",
                        "--check",
                        "--check-format",
                        "-o",
                        "/dev/null",
                        str(output),
                    ],
                    check=True,
                )
                print(output)


if __name__ == "__main__":
    main()
