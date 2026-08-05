#!/usr/bin/env python3
"""Draft missing PO translations with a local NLLB model."""

import argparse
import ast
import json
import pathlib
import re

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


TAG_RE = re.compile(r"(<[^>]+>)")
PLACEHOLDER_RE = re.compile(
    r"%(?:\([^)]+\))?[#0 +\-]?\d*(?:\.\d+)?[a-zA-Z]|\{\w+\}"
)
PROTECTED_RE = re.compile(
    r"\{\{.*?\}\}|\{%.*?%\}|"
    + PLACEHOLDER_RE.pattern
    + r"|&[a-zA-Z0-9#]+;"
    + r"|(?:[a-zA-Z_][a-zA-Z0-9_]*\.)+[a-zA-Z_][a-zA-Z0-9_]*"
    + r"|⚠️|✔|👤|🔍|←|→|•|·|●"
, re.DOTALL)
ENGLISH_RESIDUE_RE = re.compile(
    r"\b(?:the|this|that|with|from|for|and|or|to|of|in|on|by|new|"
    r"client|contact|booking|lead|activity|service|search|staff|phone|"
    r"reason|status|notes?|source|wizard|cancel|commission|referral|"
    r"duplicate|existing|selected|patient|relationship|calendar|meeting|"
    r"call|follow-up|create|save|view)\b",
    re.IGNORECASE,
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


def placeholders(text):
    values = PLACEHOLDER_RE.findall(text)
    named = {value for value in values if value.startswith(("%(", "{"))}
    positional = sorted(value for value in values if value not in named)
    return named, positional


def segment_content(segment):
    match = re.fullmatch(
        r"""([\s,;:()\[\]\-"'!?.]*)(.*?)([\s,;:()\[\]\-"'!?.]*)""",
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
            if content:
                yield content
            position = match.end()
        _leading, content, _trailing = segment_content(markup_part[position:])
        if content:
            yield content


def save_cache(cache_path, cache):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def translate_missing_segments(
    segments,
    cache,
    cache_path,
    model_path,
    batch_size,
):
    # Group similarly sized inputs to minimize tokenizer padding and make CPU
    # drafting substantially faster for mixed short labels and long messages.
    missing = sorted(set(segments) - set(cache), key=lambda text: (len(text), text))
    if not missing:
        return

    tokenizer = AutoTokenizer.from_pretrained(model_path, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        encoded = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )
        generated = model.generate(
            **encoded,
            max_new_tokens=max(
                32,
                min(160, encoded["input_ids"].shape[1] * 2 + 16),
            ),
            num_beams=1,
            no_repeat_ngram_size=3,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids("vie_Latn"),
        )
        translated = tokenizer.batch_decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        cache.update(zip(batch, translated))
        save_cache(cache_path, cache)
        print(
            f"Translated segments {min(start + len(batch), len(missing))}/{len(missing)}",
            flush=True,
        )


def translate_segment(segment, cache):
    leading, content, trailing = segment_content(segment)
    if not content:
        return segment
    return leading + cache[content] + trailing


def translate_text(text, cache):
    translated_parts = []
    position = 0
    for match in PROTECTED_RE.finditer(text):
        translated_parts.append(translate_segment(text[position : match.start()], cache))
        translated_parts.append(match.group(0))
        position = match.end()
    translated_parts.append(translate_segment(text[position:], cache))
    return "".join(translated_parts)


def translate_markup(text, cache):
    parts = TAG_RE.split(text)
    for index, part in enumerate(parts):
        if TAG_RE.fullmatch(part or ""):
            continue
        parts[index] = translate_text(part, cache)
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--cache", type=pathlib.Path)
    parser.add_argument(
        "--model",
        type=pathlib.Path,
        default=pathlib.Path("/private/tmp/nllb-200-distilled-600M"),
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--translate-all", action="store_true")
    parser.add_argument("--repair-placeholders", action="store_true")
    parser.add_argument("--repair-mixed-language", action="store_true")
    args = parser.parse_args()

    cache_path = args.cache or args.output.with_suffix(".cache.json")
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        cache = {}

    entries = parse_entries(args.catalog)
    targets = [
        (msgid, msgstr)
        for msgid, msgstr in entries
        if args.translate_all
        or not msgstr
        or (
            args.repair_placeholders
            and placeholders(msgid) != placeholders(msgstr)
        )
        or (
            args.repair_mixed_language
            and ENGLISH_RESIDUE_RE.search(msgstr)
        )
    ]
    segments = [
        segment
        for msgid, _msgstr in targets
        for segment in iter_text_segments(msgid)
    ]
    translate_missing_segments(
        segments,
        cache,
        cache_path,
        args.model,
        args.batch_size,
    )
    save_cache(cache_path, cache)

    mapping = {}
    for msgid, _msgstr in targets:
        translated = translate_markup(msgid, cache)
        if placeholders(msgid) != placeholders(translated):
            raise ValueError(f"Placeholder mismatch after translation: {msgid!r}")
        mapping[msgid] = translated

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(mapping)} draft translations to {args.output}")


if __name__ == "__main__":
    main()
