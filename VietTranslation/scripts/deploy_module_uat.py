#!/usr/bin/env python3
"""Validate, deploy, upgrade, translate, and log-check one Odoo 19 module."""

import argparse
import ast
import pathlib
import re
import subprocess
import tarfile
import tempfile
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_RE = re.compile(
    r"(?:health_[a-z0-9_]+|advanced_pricing|hr_development_ai)"
)


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def archive_filter(info):
    parts = pathlib.PurePosixPath(info.name).parts
    if "__pycache__" in parts or info.name.endswith((".pyc", ".DS_Store")):
        return None
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module")
    parser.add_argument("--host", default="VietUcUAT")
    parser.add_argument("--database", default="vietuat")
    parser.add_argument("--config", default="/etc/odoo-server.conf")
    parser.add_argument("--odoo-bin", default="/odoo/odoo-server/odoo-bin")
    parser.add_argument("--service", default="odoo-server")
    args = parser.parse_args()

    if not MODULE_RE.fullmatch(args.module):
        parser.error(
            "module must be health_*, advanced_pricing, or hr_development_ai"
        )

    module_dir = REPO_ROOT / "addons" / args.module
    manifest_path = module_dir / "__manifest__.py"
    catalog_path = module_dir / "i18n" / "vi_VN.po"
    if not manifest_path.is_file():
        parser.error(f"manifest does not exist: {manifest_path}")

    manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not version or not str(version).startswith("19.0."):
        parser.error(f"{args.module} is not an Odoo 19 module: {version!r}")

    if catalog_path.is_file():
        run(
            [
                "msgfmt",
                "--check",
                "--check-format",
                "-o",
                "/dev/null",
                str(catalog_path),
            ]
        )

    log_start = int(
        run(
            [
                "ssh",
                args.host,
                "sudo wc -l < /var/log/odoo/odoo-server.log",
            ],
            capture_output=True,
        ).stdout.strip()
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        archive = pathlib.Path(temp_dir) / f"{args.module}.tgz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(module_dir, arcname=args.module, filter=archive_filter)

        remote_archive = f"/tmp/{args.module}_deploy.tgz"
        run(["scp", str(archive), f"{args.host}:{remote_archive}"])
        run(
            [
                "ssh",
                args.host,
                (
                    f"sudo tar -xzf {remote_archive} "
                    f"-C /odoo/odoo-server/addons && "
                    f"sudo chown -R odoo:odoo "
                    f"/odoo/odoo-server/addons/{args.module}"
                ),
            ]
        )

    upgrade_command = (
        f"sudo systemctl stop {args.service} && "
        "sudo rm -f /var/run/odoo/odoo-server.pid "
        "/var/run/odoo-server.pid && "
        f"sudo -u odoo python3 {args.odoo_bin} "
        f"-c {args.config} -d {args.database} "
        f"-u {args.module} --stop-after-init --no-http "
        f"--pidfile=/tmp/odoo-upgrade-{args.module}.pid"
    )

    try:
        run(["ssh", args.host, upgrade_command])
        if catalog_path.is_file():
            run(
                [
                    "python3",
                    str(REPO_ROOT / "VietTranslation/scripts/import_module_uat.py"),
                    args.module,
                    "--host",
                    args.host,
                    "--database",
                    args.database,
                    "--config",
                    args.config,
                    "--odoo-bin",
                    args.odoo_bin,
                ]
            )
    finally:
        run(["ssh", args.host, f"sudo systemctl start {args.service}"])

    time.sleep(3)
    status = run(
        ["ssh", args.host, f"sudo systemctl is-active {args.service}"],
        capture_output=True,
    ).stdout.strip()
    logs = run(
        [
            "ssh",
            args.host,
            (
                f"sudo sed -n '{log_start + 1},$p' "
                "/var/log/odoo/odoo-server.log"
            ),
        ],
        capture_output=True,
    ).stdout

    summary_lines = [
        line
        for line in logs.splitlines()
        if args.module in line
        or "Modules loaded." in line
        or re.search(r"(^|\s)(ERROR|CRITICAL)\s", line)
    ]
    print(f"Deployed {args.module} {version}; service={status}")
    print("\n".join(summary_lines[-80:]))
    if re.search(r"(^|\s)(ERROR|CRITICAL)\s", logs, re.MULTILINE):
        raise RuntimeError(f"New Odoo log errors detected after {args.module}")


if __name__ == "__main__":
    main()
