#!/usr/bin/env python3
"""Conservatively filter an NLLB health translation draft for safe application."""

import argparse
import json
import pathlib
import re

from po_catalog import PLACEHOLDER_RE, markup_signature


VIETNAMESE_RE = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệ"
    r"íìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]"
)
ENGLISH_RESIDUE_RE = re.compile(
    r"\b(?:the|this|that|with|from|for|and|or|to|of|in|on|by|new|"
    r"client|contact|booking|activity|service|search|staff|phone|reason|"
    r"status|notes?|source|wizard|cancel|referral|existing|selected|patient|"
    r"relationship|calendar|meeting|call|follow-up|create|save|view|failed|"
    r"error|please|cannot|will|has|have|was|are|is)\b",
    re.IGNORECASE,
)
TECHNICAL_RE = re.compile(
    r"https?://|\b(?:FHIR|SMART|OAuth|JWKS|UUID|JSON|XML|API|LOINC|RxNorm|"
    r"UCUM|ICD-?10|SQL|PBX)\b|^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$|"
    r"^[a-z][a-z0-9_]+$",
    re.IGNORECASE,
)
UNSAFE_SOURCE_RE = re.compile(r"<[^>]+>|\{\{|\{%|\b(?:class|style)=")
BAD_OUTPUT_RE = re.compile(
    r"TỪ KHÓA|Quýnh|Con yêu|SÃAFETY|\)\)|\(\(|\bAnh Count\b|"
    r"\b(?:Wizard|Count|Template)\b",
    re.IGNORECASE,
)


def rejection_reason(msgid, msgstr):
    if not msgstr or msgid.strip().casefold() == msgstr.strip().casefold():
        return "unchanged"
    if not VIETNAMESE_RE.search(msgstr):
        return "no_vietnamese"
    if TECHNICAL_RE.search(msgid):
        return "technical_identifier"
    if UNSAFE_SOURCE_RE.search(msgid):
        return "markup_or_template"
    if len(msgid) > 180:
        return "long_message"
    if ENGLISH_RESIDUE_RE.search(msgstr):
        return "english_residue"
    if BAD_OUTPUT_RE.search(msgstr):
        return "suspicious_output"
    if sorted(PLACEHOLDER_RE.findall(msgid)) != sorted(PLACEHOLDER_RE.findall(msgstr)):
        return "placeholder_mismatch"
    if markup_signature(msgid) != markup_signature(msgstr):
        return "markup_mismatch"
    if len(msgid) > 12 and not 0.3 <= len(msgstr) / len(msgid) <= 3.0:
        return "length_ratio"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=pathlib.Path)
    parser.add_argument("--approved", required=True, type=pathlib.Path)
    parser.add_argument("--rejected", required=True, type=pathlib.Path)
    args = parser.parse_args()

    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    approved = {}
    rejected = {}
    for msgid, msgstr in draft.items():
        reason = rejection_reason(msgid, msgstr)
        if reason:
            rejected[msgid] = {"draft": msgstr, "reason": reason}
        else:
            approved[msgid] = msgstr

    for path, value in ((args.approved, approved), (args.rejected, rejected)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Approved: {len(approved)}")
    print(f"Rejected for review: {len(rejected)}")


if __name__ == "__main__":
    main()
