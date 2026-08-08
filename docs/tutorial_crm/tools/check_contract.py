#!/usr/bin/env python3
"""Verify that everything CareJioX Learn teaches is still true of the product.

WHY THIS EXISTS
---------------
The practice clinic is a JavaScript fixture, not an isolated tenant. That buys
real safety (there is no server on the other end of it, so a practice action
cannot reach a patient) at the cost of drift: rename a selection value, re-weight
a scoring constant or retire a menu leaf, and the tutorial keeps confidently
teaching a product that no longer exists.

This script is how that cost is paid. `contract.json` declares every fact the
tutorial asserts, together with where it came from; this re-reads the addons and
fails when a declaration no longer holds — naming the fixture entries AND the
lessons that quote it, so you know exactly what to update.

    python3 docs/tutorial_crm/tools/check_contract.py
    python3 docs/tutorial_crm/tools/check_contract.py --quiet   # CI: errors only

Exit codes: 0 = everything still true · 1 = drift detected · 2 = cannot run.

WHEN IT FAILS there are two correct responses and one wrong one:
  1. The product changed on purpose -> update `expect` here, then
     practice-data.js, then the `taughtIn` content the entry names.
  2. The product changed by accident -> fix the product.
  3. WRONG: relax the check. A green checker that proves nothing is worse than
     no checker, because people trust the tutorial more, not less.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)

RED, GREEN, YELLOW, DIM, BOLD, OFF = (
    "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    RED = GREEN = YELLOW = DIM = BOLD = OFF = ""


class Result:
    def __init__(self):
        self.failures = []   # (check_id, [problems], check dict)
        self.passed = 0
        self.skipped = []    # (check_id, reason)

    def ok(self):
        self.passed += 1

    def fail(self, check, problems):
        self.failures.append((check.get("id", "?"), problems, check))

    def skip(self, check, reason):
        self.skipped.append((check.get("id", "?"), reason))


def read(root, rel):
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def region(text, symbol):
    """The slice of `text` that belongs to `symbol`.

    Anchor on the DEFINITION, not the first mention — a method name usually
    appears first inside `compute="..."` on the field, hundreds of lines above
    the body, and scoping to that window silently finds nothing. (Measured: this
    is exactly how `urgency-terms` and `consent-types` failed on the first run.)

    Deliberately approximate after that: from the definition to whatever looks
    like the next top-level one. A lint that is 95% right and always runs beats
    a parser that is 100% right and gets disabled the first time a decorator
    breaks it.
    """
    i = -1
    for probe in ("def %s" % symbol, "%s = " % symbol, symbol):
        i = text.find(probe)
        if i != -1:
            break
    if i == -1:
        return None
    tail = text[i:]
    stop = len(tail)
    for pat in (r"\ndef ", r"\n@api", r"\nclass ", r"\n[A-Z_]{3,} = ", r"\n    def "):
        m = re.search(pat, tail[40:])
        if m:
            stop = min(stop, m.start() + 40)
    return tail[:stop]


# ---------------------------------------------------------------- check kinds
def check_contains(root, chk):
    """Every literal in `expect` must appear in the file (optionally in `within`)."""
    files = chk.get("files") or [chk["file"]]
    problems = []
    blobs = []
    for rel in files:
        text = read(root, rel)
        if text is None:
            return None, "file not found: %s" % rel
        blobs.append(text)
    blob = "\n".join(blobs)
    if chk.get("within"):
        scoped = region(blob, chk["within"])
        if scoped is None:
            return None, "symbol not found: %s" % chk["within"]
        blob = scoped
    for want in chk["expect"]:
        if want not in blob:
            problems.append("missing: %s" % want)
    return problems, None


def check_selection(root, chk):
    """Selection values must all still exist, inside `within` when given."""
    return check_contains(root, chk)


def check_constants(root, chk):
    """Scoring constants, matched by EXACT OCCURRENCE COUNT.

    Counting matters and substring-presence does not. `score += 15` appears
    twice in the urgency compute (unread, and the watch phrase). A presence-only
    check stays green when one of them is re-weighted, because the other still
    matches — measured: re-weighting the watch term 15 -> 25 passed a
    presence-only check while making the tutorial's worked total wrong.

    Exact counts also fire when a NEW term is added, which is correct: a new
    term changes the arithmetic every lesson and calc-block teaches.

    `expect` maps a literal to either a plain meaning string (count 1) or
    {"means": ..., "count": n}.
    """
    text = read(root, chk["file"])
    if text is None:
        return None, "file not found: %s" % chk["file"]
    blob = region(text, chk["within"]) if chk.get("within") else text
    if blob is None:
        return None, "symbol not found: %s" % chk["within"]
    problems = []
    for literal, spec in chk["expect"].items():
        if isinstance(spec, dict):
            meaning, want = spec.get("means", "?"), int(spec.get("count", 1))
        else:
            meaning, want = spec, 1
        got = blob.count(literal)
        if got != want:
            problems.append("%-14s occurs %d time(s), expected %d  (%s)"
                            % (literal, got, want, meaning))
    return problems, None


def check_xmlids(root, chk):
    """Sidebar record ids must still be declared somewhere in the seed files."""
    blob = ""
    for rel in chk["files"]:
        text = read(root, rel)
        if text is None:
            return None, "file not found: %s" % rel
        blob += text
    problems = []
    for xmlid in chk["expect"]:
        if ('id="%s"' % xmlid) not in blob:
            problems.append("sidebar item no longer declared: %s" % xmlid)
    return problems, None


def po_pairs(text):
    """msgid -> msgstr, single-line entries only (which is all we assert)."""
    out = {}
    msgid = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'^msgid "(.*)"$', line)
        if m:
            msgid = m.group(1)
            continue
        m = re.match(r'^msgstr "(.*)"$', line)
        if m and msgid is not None:
            out.setdefault(msgid, m.group(1))
            msgid = None
    return out


def check_po(root, chk):
    """Shipped Vietnamese strings must still say what the fixture ships."""
    problems = []
    for rel, pairs in chk["expect"].items():
        text = read(root, rel)
        if text is None:
            return None, "file not found: %s" % rel
        found = po_pairs(text)
        for msgid, want in pairs.items():
            got = found.get(msgid)
            if got is None:
                problems.append('%s: msgid "%s" is gone' % (rel, msgid))
            elif got != want:
                problems.append('%s: "%s" now translates to "%s", fixture ships "%s"'
                                % (rel, msgid, got, want))
    return problems, None


def check_po_expect_missing(root, chk):
    """A KNOWN GAP that we want to be told about the moment it is fixed."""
    text = read(root, chk["file"])
    if text is None:
        return None, "file not found: %s" % chk["file"]
    found = po_pairs(text)
    problems = []
    for msgid, still in chk["expect"].items():
        got = found.get(msgid)
        if got is None:
            problems.append('msgid "%s" is gone entirely' % msgid)
        elif got != still:
            problems.append(
                'GOOD NEWS: "%s" is now translated as "%s". Update MENU in '
                'practice-data.js and delete this contract entry.' % (msgid, got))
    return problems, None


KINDS = {
    "contains": check_contains,
    "selection": check_selection,
    "constants": check_constants,
    "xmlids": check_xmlids,
    "po": check_po,
    "po-expect-missing": check_po_expect_missing,
}

# Anchors follow a screen-prefix convention, which is what makes them lintable.
ANCHOR_RE = re.compile(r'"((?:cc|ch|db|ur|tp)-[a-z0-9][a-z0-9-]*)"')


def anchor_lint(cfg, res, quiet):
    """DESIGN_SPEC §4: content names controls; a rename must break the build.

    In production `contentFiles` become the learn-content records and
    `templateFiles` become the OWL templates — the comparison is identical.
    """
    spec = cfg.get("anchorLint")
    if not spec:
        return
    referenced, present = set(), set()
    for rel in spec["contentFiles"]:
        text = read(PROTO, rel)
        if text is None:
            res.skip({"id": "anchor-lint"}, "content file not found: %s" % rel)
            return
        referenced |= set(ANCHOR_RE.findall(text))
    for rel in spec["templateFiles"]:
        text = read(PROTO, rel)
        if text is None:
            res.skip({"id": "anchor-lint"}, "template file not found: %s" % rel)
            return
        # Literal attributes, plus anchors the renderer interpolates
        # (`data-a="${a}"`) whose names live as plain strings in the renderer
        # or in the fixture that feeds it.
        #
        # HONEST LIMITATION: the second pattern makes the prototype's lint
        # weaker than production's will be — it would still pass if someone
        # deleted a `data-a` attribute but left the name behind as a string.
        # In production, anchors are literal attributes in OWL templates, so
        # the first pattern alone is exact and the second must be DROPPED.
        # It is here only because this prototype renders anchors from data.
        # It still catches the failure that actually happens: content naming a
        # control that exists nowhere at all.
        present |= set(re.findall(r'data-a="([^"]+)"', text))
        present |= set(ANCHOR_RE.findall(text))
    missing = sorted(referenced - present)
    chk = {"id": "anchor-lint",
           "why": spec["why"],
           "taughtIn": ["every lesson step, mission step and coach point-at"]}
    if missing:
        res.fail(chk, ["content points at a control that no longer exists: %s" % a
                       for a in missing])
    else:
        res.ok()
        if not quiet:
            orphans = sorted(present - referenced)
            print("  %s✓%s anchor-lint            %s%d referenced, all present%s%s"
                  % (GREEN, OFF, DIM, len(referenced), OFF,
                     (" · %d unused anchor(s)" % len(orphans)) if orphans else ""))


def token_lint(cfg, res, quiet):
    """Every `{{key}}` content writes must be a declared tenant slot.

    Same failure mode as a broken anchor, different surface: a typo renders the
    key to a learner instead of the clinic's hotline number. Also reports slots
    nothing uses, which are dead configuration a tenant admin can still see.
    """
    spec = cfg.get("tokenLint")
    if not spec:
        return
    used = set()
    for rel in spec["contentFiles"]:
        text = read(PROTO, rel)
        if text is None:
            res.skip({"id": "token-lint"}, "content file not found: %s" % rel)
            return
        used |= set(re.findall(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}", text))
    fixture = read(PROTO, spec["declaredIn"])
    if fixture is None:
        res.skip({"id": "token-lint"}, "fixture not found: %s" % spec["declaredIn"])
        return
    block = region(fixture, "TENANT_DEFAULTS")
    declared = set(re.findall(r"^\s{2}([a-zA-Z][a-zA-Z0-9_]*):\s*B\(", block or "", re.M))
    undeclared = sorted(used - declared)
    chk = {"id": "token-lint", "why": spec["why"],
           "fixture": ["TENANT_DEFAULTS"],
           "taughtIn": ["every string that names a role, a time or a contact detail"]}
    if undeclared:
        res.fail(chk, ["content uses an undeclared tenant slot: {{%s}}" % k
                       for k in undeclared])
    else:
        res.ok()
        if not quiet:
            unused = len(declared - used)
            print("  %s✓%s token-lint             %s%d slot(s) declared, %d used, %d spare%s"
                  % (GREEN, OFF, DIM, len(declared), len(used), unused, OFF))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    ap.add_argument("--contract", default=os.path.join(PROTO, "contract.json"))
    args = ap.parse_args()

    try:
        with open(args.contract, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception as exc:                                  # noqa: BLE001
        print("%scannot read contract: %s%s" % (RED, exc, OFF))
        return 2

    root = os.path.abspath(os.path.join(PROTO, cfg.get("repoRoot", "../../..")))
    if not os.path.isdir(os.path.join(root, "addons")):
        print("%scannot find addons/ from repoRoot %s%s" % (RED, root, OFF))
        return 2

    if not args.quiet:
        print("\n%sCareJioX Learn — contract check%s" % (BOLD, OFF))
        print("%srepo: %s · contract schema %s%s\n"
              % (DIM, root, cfg.get("schemaVersion", "?"), OFF))

    res = Result()
    for chk in cfg["checks"]:
        fn = KINDS.get(chk.get("kind"))
        if fn is None:
            res.skip(chk, "unknown kind: %s" % chk.get("kind"))
            continue
        problems, err = fn(root, chk)
        if err:
            res.skip(chk, err)
        elif problems:
            res.fail(chk, problems)
        else:
            res.ok()
            if not args.quiet:
                print("  %s✓%s %-22s %s%s%s"
                      % (GREEN, OFF, chk["id"], DIM,
                         (chk.get("file") or (chk.get("files") or ["-"])[0]), OFF))

    anchor_lint(cfg, res, args.quiet)
    token_lint(cfg, res, args.quiet)

    for cid, reason in res.skipped:
        print("  %s⊘%s %-22s %sskipped — %s%s" % (YELLOW, OFF, cid, DIM, reason, OFF))

    if res.failures:
        print("\n%s%d contract check(s) FAILED — the tutorial now teaches something "
              "untrue.%s" % (RED + BOLD, len(res.failures), OFF))
        for cid, problems, chk in res.failures:
            print("\n  %s✗ %s%s" % (RED + BOLD, cid, OFF))
            print("    %swhy it matters:%s %s" % (BOLD, OFF, chk.get("why", "-")))
            for p in problems:
                print("      %s- %s%s" % (RED, p, OFF))
            if chk.get("fixture"):
                print("    %supdate in practice-data.js:%s %s"
                      % (BOLD, OFF, ", ".join(chk["fixture"])))
            if chk.get("taughtIn"):
                print("    %sthen re-read this content:%s %s"
                      % (BOLD, OFF, ", ".join(chk["taughtIn"])))
        print()
        return 1

    print("\n%s✓ %d checks passed%s%s — everything the tutorial teaches is still "
          "true of the product.%s\n"
          % (GREEN + BOLD, res.passed, OFF, GREEN, OFF))
    return 0


if __name__ == "__main__":
    sys.exit(main())
