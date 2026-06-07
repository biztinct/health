#!/usr/bin/env python3
"""Prepare exact and intentionally unchanged translations for health_pwa."""

import argparse
import ast
import json
import pathlib
import re
import sys

import po_catalog


JS_PAIR_RE = re.compile(
    r"^\s*'((?:\\.|[^'])*)':\s*'((?:\\.|[^'])*)',?\s*$"
)
VIETNAMESE_PREFIXES = (
    "Bạn ",
    "Chọn ",
    "Khởi ",
    "Không ",
    "Nhấn ",
    "Quay ",
    "Thử ",
    "Tìm ",
    "Từ ",
    "Xác nhận ",
)
UNCHANGED_VALUES = {
    "EN",
    "Health Mobile",
    "ID",
    "Viet Uc",
    "Viet Uc v",
    "VI",
}


def decode_js_string(value):
    return ast.literal_eval("'" + value + "'")


def load_vi_map(path):
    translations = {}
    in_vi = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\s*vi:\s*\{\s*$", line):
            in_vi = True
            continue
        if in_vi and re.match(r"^\s*\},\s*$", line):
            break
        if not in_vi:
            continue
        match = JS_PAIR_RE.match(line)
        if match:
            translations[decode_js_string(match.group(1))] = decode_js_string(
                match.group(2)
            )
    if not translations:
        raise ValueError(f"No Vietnamese translations found in {path}")
    return translations


def intentionally_unchanged(msgid):
    return (
        msgid.startswith("// Health PWA Service Worker v")
        or re.fullmatch(r"\d+\.\d+\.\d+", msgid) is not None
        or msgid in UNCHANGED_VALUES
        or "material-icons" in msgid
        or "data-lang=" in msgid
        or "lang-content" in msgid
        or "pwa-install-step-en" in msgid
        or msgid.startswith(("<strong>Bước ", "<strong>Lưu ý:"))
        or msgid.startswith(VIETNAMESE_PREFIXES)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=pathlib.Path)
    parser.add_argument(
        "--pwa-utils",
        type=pathlib.Path,
        default=pathlib.Path(
            "addons/health_pwa/static/src/js/utils/pwa-utils.js"
        ),
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()

    lines = args.catalog.read_text(encoding="utf-8").splitlines(keepends=True)
    entries = [entry for entry in po_catalog.parse_entries(lines) if entry["msgid"]]
    available = {entry["msgid"] for entry in entries}
    vi_map = load_vi_map(args.pwa_utils)

    mapping = {
        msgid: translation
        for msgid, translation in vi_map.items()
        if msgid in available
    }
    unchanged = {
        msgid: msgid for msgid in available if intentionally_unchanged(msgid)
    }
    mapping.update(unchanged)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(mapping)} mappings: "
        f"{len(mapping) - len(unchanged)} exact Vietnamese, "
        f"{len(unchanged)} intentionally unchanged"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
