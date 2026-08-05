#!/usr/bin/env python3
"""Draft blank PO translations with Google while withholding protected syntax."""

import argparse
import ast
import concurrent.futures
import json
import pathlib
import re
import time

import requests


TAG_RE = re.compile(r"(<[^>]+>)")
PLACEHOLDER_RE = re.compile(
    r"%(?:\([^)]+\))?[#0+\-]?\d*(?:\.\d+)?[diouxXeEfFgGcrsa]|\{\w+\}"
)
PROTECTED_RE = re.compile(
    r"\{\{.*?\}\}|\{%.*?%\}|"
    + PLACEHOLDER_RE.pattern
    + r"|https?://[^\s<>'\"]+|&[a-zA-Z0-9#]+;"
    + r"|(?:[a-zA-Z_][a-zA-Z0-9_]*\.)+[a-zA-Z_][a-zA-Z0-9_]*"
    + r"|\b[a-z][a-z0-9]*_[a-z0-9_]+\b"
    + r"|(?-i:\b(?:[A-Z][a-z0-9]+){2,}\b)"
    + r"|(?-i:\b[A-Z][A-Z0-9-]{1,}\b)"
    + r"|\b(?:FHIR|SMART|OAuth2?|JWKS|UUID|JSON|XML|API|LOINC|RxNorm|"
      r"UCUM|ICD-?10|SQL|PBX|VoIP24h|Zalo|BHYT|PWA|EVV|NEWS2|ACVPU|STT|"
      r"Health19|Meta|Microsoft|Ollama|Barthel|Braden)\b"
    + r"|⚠️|✔|👤|🔍|←|→|•|·|●",
    re.DOTALL | re.IGNORECASE,
)
VIETNAMESE_RE = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệ"
    r"íìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]"
)


def decode_po_string(line):
    value = line.strip()
    if value.startswith(("msgid ", "msgstr ")):
        value = value.split(" ", 1)[1]
    return ast.literal_eval(value)


def parse_entries(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    entries = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("msgid "):
            index += 1
            continue
        msgid = decode_po_string(lines[index])
        index += 1
        while index < len(lines) and lines[index].startswith('"'):
            msgid += decode_po_string(lines[index])
            index += 1
        if index >= len(lines) or not lines[index].startswith("msgstr "):
            continue
        msgstr = decode_po_string(lines[index])
        index += 1
        while index < len(lines) and lines[index].startswith('"'):
            msgstr += decode_po_string(lines[index])
            index += 1
        if msgid:
            entries.append((msgid, msgstr))
    return entries


def segment_content(segment):
    match = re.fullmatch(
        r'''([\s,;:()\[\]\-"'!?.]*)(.*?)([\s,;:()\[\]\-"'!?.]*)''',
        segment,
        flags=re.DOTALL,
    )
    return match.groups()


def iter_text_segments(text):
    for markup_part in TAG_RE.split(text):
        if TAG_RE.fullmatch(markup_part or ""):
            continue
        position = 0
        for match in PROTECTED_RE.finditer(markup_part):
            _leading, content, _trailing = segment_content(
                markup_part[position : match.start()]
            )
            if content and re.search(r"[A-Za-z]", content) and not VIETNAMESE_RE.search(content):
                yield content
            position = match.end()
        _leading, content, _trailing = segment_content(markup_part[position:])
        if content and re.search(r"[A-Za-z]", content) and not VIETNAMESE_RE.search(content):
            yield content


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def google_translate(text, context_prefix=""):
    for attempt in range(4):
        try:
            response = requests.get(
                "https://translate.googleapis.com/translate_a/single",
                params={
                    "client": "gtx",
                    "sl": "en",
                    "tl": "vi",
                    "dt": "t",
                    "q": context_prefix + text,
                },
                timeout=30,
            )
            response.raise_for_status()
            translated = "".join(part[0] for part in response.json()[0] if part[0])
            if context_prefix:
                _prefix, separator, translated = translated.partition(":")
                translated = translated.lstrip()
                if not separator or not translated:
                    # Very short labels occasionally make Google drop the
                    # separator. Fall back to the ordinary translation rather
                    # than retaining the translated context in the catalog.
                    return google_translate(text)
            if translated:
                return translated
        except (requests.RequestException, ValueError, KeyError, TypeError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Translation failed: {text!r}")


def translate_segment(segment, cache):
    leading, content, trailing = segment_content(segment)
    if not content or content not in cache:
        return segment
    return leading + cache[content] + trailing


def translate_text(text, cache):
    parts = []
    position = 0
    for match in PROTECTED_RE.finditer(text):
        parts.append(translate_segment(text[position : match.start()], cache))
        parts.append(match.group(0))
        position = match.end()
    parts.append(translate_segment(text[position:], cache))
    return "".join(parts)


def translate_markup(text, cache):
    parts = TAG_RE.split(text)
    for index, part in enumerate(parts):
        if not TAG_RE.fullmatch(part or ""):
            parts[index] = translate_text(part, cache)
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--cache", required=True, type=pathlib.Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--context-prefix",
        default="",
        help="English context ending in ':'; its translated prefix is removed",
    )
    args = parser.parse_args()

    cache = json.loads(args.cache.read_text(encoding="utf-8")) if args.cache.exists() else {}
    targets = [(msgid, msgstr) for msgid, msgstr in parse_entries(args.catalog) if not msgstr]
    segments = sorted(
        {
            segment
            for msgid, _msgstr in targets
            for segment in iter_text_segments(msgid)
            if segment not in cache
        },
        key=lambda value: (len(value), value),
    )
    for start in range(0, len(segments), args.workers):
        batch = segments[start : start + args.workers]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            translations = list(
                pool.map(
                    lambda value: google_translate(value, args.context_prefix),
                    batch,
                )
            )
        cache.update(zip(batch, translations))
        save_json(args.cache, cache)
        print(f"Translated segments {min(start + len(batch), len(segments))}/{len(segments)}", flush=True)

    mapping = {}
    for msgid, _msgstr in targets:
        translated = translate_markup(msgid, cache)
        if translated != msgid:
            mapping[msgid] = translated
    save_json(args.output, mapping)
    print(f"Wrote {len(mapping)} draft translations to {args.output}")


if __name__ == "__main__":
    main()
