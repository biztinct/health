# Part of the Viet Uc Care white-label layer. License LGPL-3.
"""Where the framework's name is recognised, and where it is left alone.

One regular expression, used by everything in this module, so there is one
answer to "is this the product's name or is it an address" rather than three
that drift apart.

THE RULE, AND WHY IT IS THIS NARROW. A blind search-and-replace over rendered
mail corrupts the product: stock bodies on this build carry
`t-attf-href="/odoo/{{ object.module_id.id }}/action-…"`, a real URL path here,
and `https://www.odoo.com?utm_source=…`. Rewriting either produces a link that
goes nowhere, silently, in a message somebody has already received. So a match
needs all of:

  * the exact capitalised word `Odoo` — never lowercase `odoo`, because
    lowercase is what appears in paths, hostnames and identifiers;
  * nothing word-like, `/`, `.` or `-` immediately before it;
  * nothing word-like, `.` or `-` immediately after it.

That one rule is what keeps `odoo.com`, `/odoo/`, `odoo-bin`, `Odoo.sh` and
`OdooBot` out of it. `OdooBot` has no boundary after the word, so it never
matches here — the bot is renamed by its own record, not by this.
"""

import logging
import re

from lxml import html

_logger = logging.getLogger(__name__)

BRANDED_WORD = re.compile(r"(?<![\w./-])Odoo(?![\w.-])")

# Attributes a person can end up reading or hearing.
SPOKEN_ATTRS = ("alt", "title")


def names_the_framework(text):
    return bool(text) and bool(BRANDED_WORD.search(str(text)))


def debrand_text(text, brand):
    """Plain text: a subject line, a permission label, a translated sentence.

    Substituting the WORD rather than replacing the whole sentence is what lets
    a translation keep its own grammar: "Nhận thông báo trong Odoo" becomes
    "Nhận thông báo trong {brand}" and stays Vietnamese, where writing the
    English string over it would quietly un-translate the screen.
    """
    if not text:
        return text
    return BRANDED_WORD.sub(brand, str(text))


def debrand_html(text, brand):
    """HTML: text nodes and spoken attributes only.

    The parser is the guard, not the regular expression — nothing inside a tag
    (no href, no style, no `t-att` expression) can be reached even in principle.
    """
    if not text:
        return text
    fragment = html.fragment_fromstring(str(text), create_parent="div")
    for node in fragment.iter():
        if names_the_framework(node.text):
            node.text = BRANDED_WORD.sub(brand, node.text)
        if names_the_framework(node.tail):
            node.tail = BRANDED_WORD.sub(brand, node.tail)
        for attr in SPOKEN_ATTRS:
            current = node.get(attr)
            if names_the_framework(current):
                node.set(attr, BRANDED_WORD.sub(brand, current))
    out = html.tostring(fragment, method="html", encoding="unicode")
    # `create_parent` added a wrapper this text never had; take it back off so
    # the caller gets the same shape it handed in.
    if out.startswith("<div>") and out.endswith("</div>"):
        out = out[len("<div>"): -len("</div>")]
    return out


def debrand_value(text, brand):
    """Either kind, decided by whether it looks like markup."""
    if not text:
        return text
    raw = str(text)
    if "<" in raw and ">" in raw:
        return debrand_html(raw, brand)
    return debrand_text(raw, brand)


def debrand_translated_field(record, field, brand):
    """Rewrite one translatable field in EVERY language this database speaks.

    `write()` on a translatable field only touches the language the environment
    happens to be in. That is the whole reason this helper exists: renaming a
    permission left "Receive notifications in {brand}" in English beside
    "Nhận thông báo trong Odoo" in Vietnamese — and a clinic here reads the
    Vietnamese one. A leak that only shows in the language most of the staff
    use is the worst shape this bug can take.

    Returns the languages it changed, for the log line.
    """
    changed = []
    langs = record.env["res.lang"].sudo().search([])
    for code in langs.mapped("code") or ["en_US"]:
        localised = record.sudo().with_context(lang=code)
        current = localised[field]
        if not names_the_framework(current):
            continue
        localised.write({field: debrand_value(current, brand)})
        changed.append(code)
    return changed
