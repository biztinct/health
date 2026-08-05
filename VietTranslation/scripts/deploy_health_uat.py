#!/usr/bin/env python3
"""Deploy and import all installed health_* Vietnamese catalogs in one window."""

import argparse
import ast
import json
import pathlib
import re
import subprocess
import tarfile
import tempfile
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_RE = re.compile(r"health_[a-z0-9_]+")
MARKER = "HEALTH_MODULES_JSON="


def run(command, **kwargs):
    return subprocess.run(command, check=True, text=True, **kwargs)


def remote_shell(args, code, pid_name):
    command = (
        f"sudo -u odoo python3 {args.odoo_bin} shell "
        f"-c {args.config} -d {args.database} --no-http "
        f"--pidfile=/tmp/{pid_name}.pid"
    )
    return run(
        ["ssh", args.host, command],
        input=code,
        capture_output=True,
    ).stdout


def installed_health_modules(args):
    output = remote_shell(
        args,
        """
import json
names = env['ir.module.module'].search([
    ('name', '=like', 'health_%'),
    ('state', '=', 'installed'),
]).mapped('name')
print('HEALTH_MODULES_JSON=' + json.dumps(sorted(names)))
""",
        "odoo-health-deploy-inventory",
    )
    marker_line = next(
        (line for line in reversed(output.splitlines()) if line.startswith(MARKER)),
        None,
    )
    if marker_line is None:
        raise RuntimeError("Could not read installed health module inventory")
    modules = json.loads(marker_line[len(MARKER) :])
    if not modules or any(not MODULE_RE.fullmatch(name) for name in modules):
        raise RuntimeError(f"Invalid installed health module inventory: {modules!r}")
    return modules


def catalog_for(module_dir):
    for filename in ("vi.po", "vi_VN.po"):
        path = module_dir / "i18n" / filename
        if path.is_file():
            return path
    return None


def archive_filter(info):
    parts = pathlib.PurePosixPath(info.name).parts
    if "__pycache__" in parts or info.name.endswith((".pyc", ".DS_Store")):
        return None
    return info


def validate_inventory(installed):
    deploy = []
    skipped = []
    for module in installed:
        module_dir = REPO_ROOT / "addons" / module
        manifest_path = module_dir / "__manifest__.py"
        if not manifest_path.is_file():
            raise RuntimeError(f"Installed module is missing locally: {module}")
        manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        if not str(manifest.get("version", "")).startswith("19.0."):
            raise RuntimeError(f"Not an Odoo 19 module: {module}")
        catalog = catalog_for(module_dir)
        if catalog is None:
            skipped.append(module)
            continue
        run(
            [
                "msgfmt",
                "--check",
                "--check-format",
                "-o",
                "/dev/null",
                str(catalog),
            ],
            stderr=subprocess.DEVNULL,
        )
        deploy.append((module, module_dir, catalog))
    return deploy, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="VietUcUAT")
    parser.add_argument("--database", default="vietuat")
    parser.add_argument("--config", default="/etc/odoo-server.conf")
    parser.add_argument("--odoo-bin", default="/odoo/odoo-server/odoo-bin")
    parser.add_argument("--service", default="odoo-server")
    parser.add_argument(
        "--module",
        action="append",
        dest="requested_modules",
        help="Deploy only this installed health_* module (repeatable)",
    )
    args = parser.parse_args()

    installed = installed_health_modules(args)
    if args.requested_modules:
        requested = list(dict.fromkeys(args.requested_modules))
        invalid = [name for name in requested if not MODULE_RE.fullmatch(name)]
        if invalid:
            parser.error("invalid health module: " + ", ".join(invalid))
        unavailable = [name for name in requested if name not in installed]
        if unavailable:
            parser.error("module is not installed: " + ", ".join(unavailable))
        installed = requested
    deploy, skipped = validate_inventory(installed)
    modules = [item[0] for item in deploy]
    if not modules:
        raise RuntimeError("No installed health modules have Vietnamese catalogs")
    print(f"Installed health modules: {len(installed)}")
    print(f"Deploying catalogs: {len(modules)}")
    if skipped:
        print("Skipping without catalog: " + ", ".join(skipped))

    log_start = int(
        run(
            ["ssh", args.host, "sudo wc -l < /var/log/odoo/odoo-server.log"],
            capture_output=True,
        ).stdout.strip()
    )

    remote_archive = "/tmp/health_modules_translation_deploy.tgz"
    with tempfile.TemporaryDirectory() as temp_dir:
        archive = pathlib.Path(temp_dir) / "health_modules_translation_deploy.tgz"
        with tarfile.open(archive, "w:gz") as tar:
            for module, module_dir, _catalog in deploy:
                tar.add(module_dir, arcname=module, filter=archive_filter)
        run(["scp", str(archive), f"{args.host}:{remote_archive}"])
    run(
        [
            "ssh",
            args.host,
            (
                f"sudo tar -xzf {remote_archive} -C /odoo/odoo-server/addons && "
                "sudo chown -R odoo:odoo "
                + " ".join(
                    f"/odoo/odoo-server/addons/{module}" for module in modules
                )
            ),
        ]
    )

    upgrade_command = (
        f"sudo systemctl stop {args.service} && "
        "sudo rm -f /var/run/odoo/odoo-server.pid /var/run/odoo-server.pid && "
        f"sudo -u odoo python3 {args.odoo_bin} "
        f"-c {args.config} -d {args.database} "
        f"-u {','.join(modules)} --stop-after-init --no-http "
        "--pidfile=/tmp/odoo-health-translation-upgrade.pid"
    )
    imports = [
        (module, f"/odoo/odoo-server/addons/{module}/i18n/{catalog.name}")
        for module, _module_dir, catalog in deploy
    ]
    import_code = f"""
from odoo.tools.translate import TranslationImporter

imports = {imports!r}
for module, path in imports:
    importer = TranslationImporter(env.cr)
    with open(path, 'rb') as catalog:
        importer.load(catalog, 'po', 'vi_VN', module=module)
    importer.save(overwrite=True, force_overwrite=True)
    env.cr.commit()
    print('IMPORTED_VI_VN=' + module)
print('IMPORT_COUNT=' + str(len(imports)))
"""

    try:
        run(["ssh", args.host, upgrade_command])
        output = remote_shell(
            args,
            import_code,
            "odoo-health-translation-import",
        )
        imported = [
            line[len("IMPORTED_VI_VN=") :]
            for line in output.splitlines()
            if line.startswith("IMPORTED_VI_VN=")
        ]
        if imported != modules:
            raise RuntimeError(
                f"Imported {len(imported)} of {len(modules)} catalogs"
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
            f"sudo sed -n '{log_start + 1},$p' /var/log/odoo/odoo-server.log",
        ],
        capture_output=True,
    ).stdout
    errors = [
        line
        for line in logs.splitlines()
        if re.search(r"(^|\s)(ERROR|CRITICAL)\s", line)
    ]
    print(f"Deployed and imported {len(modules)} health catalogs; service={status}")
    if errors:
        print("\n".join(errors[-80:]))
        raise RuntimeError("New Odoo ERROR/CRITICAL log entries detected")
    if status != "active":
        raise RuntimeError(f"Odoo service is not active: {status}")


if __name__ == "__main__":
    main()
