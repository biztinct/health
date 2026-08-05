#!/usr/bin/env python3
"""Add literal health_* JavaScript _t() strings missing from module PO catalogs."""

import argparse
import ast
import importlib.util
import json
import pathlib
import re
import subprocess

from po_catalog import parse_entries


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
T_CALL_RE = re.compile(r"_t\(\s*(['\"])((?:\\.|(?!\1).)*)\1\s*\)")
JS_PAIR_RE = re.compile(
    r"^\s*('(?:\\.|[^'])*')\s*:\s*('(?:\\.|[^'])*')\s*,?\s*$"
)


def reviewed_js_translations():
    wrapper = REPO_ROOT / "VietTranslation" / "scripts" / "wrap_js_t.py"
    spec = importlib.util.spec_from_file_location("wrap_js_t", wrapper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reviewed = dict(module.VI_TRANSLATIONS)
    for relative, start_marker, end_marker in (
        (
            "addons/health_pwa/static/src/js/utils/pwa-utils.js",
            "    vi: {",
            "    en: {",
        ),
        (
            "addons/health_pwa/static/src/js/app.js",
            "const APP_VI_FALLBACK_TRANSLATIONS = {",
            "};",
        ),
    ):
        active = False
        for line in (REPO_ROOT / relative).read_text(encoding="utf-8").splitlines():
            if line.startswith(start_marker):
                active = True
                continue
            if active and line.startswith(end_marker):
                break
            if not active:
                continue
            match = JS_PAIR_RE.match(line)
            if match:
                reviewed[ast.literal_eval(match.group(1))] = ast.literal_eval(
                    match.group(2)
                )
    return reviewed


def module_catalog(module_dir):
    for filename in ("vi.po", "vi_VN.po"):
        candidate = module_dir / "i18n" / filename
        if candidate.is_file():
            return candidate
    return module_dir / "i18n" / "vi.po"


def literal_value(quote, body):
    try:
        return ast.literal_eval(quote + body + quote)
    except (SyntaxError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    reviewed = reviewed_js_translations()
    total = 0
    translated = 0

    for module_dir in sorted((REPO_ROOT / "addons").glob("health_*")):
        found = {}
        for js_path in sorted((module_dir / "static").glob("**/*.js")):
            if js_path.name.endswith(".min.js"):
                continue
            content = js_path.read_text(encoding="utf-8")
            for match in T_CALL_RE.finditer(content):
                msgid = literal_value(match.group(1), match.group(2))
                if not msgid:
                    continue
                relative = js_path.relative_to(REPO_ROOT / "addons")
                found.setdefault(msgid, f"code:addons/{relative}:0")
        if not found:
            continue

        catalog = module_catalog(module_dir)
        if catalog.is_file():
            content = catalog.read_text(encoding="utf-8")
            existing = {
                entry["msgid"]
                for entry in parse_entries(content.splitlines(keepends=True))
            }
        else:
            catalog.parent.mkdir(parents=True, exist_ok=True)
            content = (
                "# Translation of Odoo Server.\n"
                f"# Modules: {module_dir.name}\n\n"
                'msgid ""\nmsgstr ""\n'
                '"Project-Id-Version: Odoo Server 19.0\\n"\n'
                '"Language: vi\\n"\n'
                '"MIME-Version: 1.0\\n"\n'
                '"Content-Type: text/plain; charset=UTF-8\\n"\n'
                '"Content-Transfer-Encoding: 8bit\\n"\n'
                '"Plural-Forms: nplurals=1; plural=0;\\n"\n'
            )
            existing = set()

        missing = sorted(set(found) - existing)
        if not missing:
            continue
        total += len(missing)
        translated += sum(msgid in reviewed for msgid in missing)
        print(f"{catalog.relative_to(REPO_ROOT)}: {len(missing)}")
        if not args.apply:
            continue
        additions = []
        for msgid in missing:
            additions.extend(
                [
                    "",
                    f"#. module: {module_dir.name}",
                    "#. odoo-javascript",
                    f"#: {found[msgid]}",
                    f"msgid {json.dumps(msgid, ensure_ascii=False)}",
                    "msgstr "
                    + json.dumps(reviewed.get(msgid, ""), ensure_ascii=False),
                ]
            )
        catalog.write_text(
            content.rstrip() + "\n" + "\n".join(additions) + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["msgfmt", "--check", "--check-format", "-o", "/dev/null", str(catalog)],
            check=True,
        )

    action = "Added" if args.apply else "Would add"
    print(f"{action} {total} missing JavaScript entries; {translated} reviewed translations")


if __name__ == "__main__":
    main()
