"""Apply the editable About Us title design to the site's content pages.

Run this file inside ``odoo-bin shell -d thhs``.  It updates only the first
title section of each listed page.  Existing heading content is retained.  A
meaningful legacy eyebrow is moved after the English heading when the heading
is not bilingual already; empty or duplicate eyebrow rows are removed.  The
result remains normal content that editors can change with Website Builder.

The source section is read from ``/background`` rather than duplicated here.
That makes the script idempotent and keeps the Website Builder's attachment
metadata, background picker and vertical resize handles intact.
"""

import re

from lxml import etree


WEBSITE_ID = 1
SOURCE_URL = "/background"
TARGET_URLS = (
    "/annual-report",
    "/contactus",
    "/how-can-i-help",
    "/news",
    "/our-board",
    "/our-hospital",
    "/our-vision",
    "/projects",
    "/successes",
    "/what-we-do",
)

BACKGROUND_ATTRS = (
    "data-attachment-id",
    "data-format-mimetype",
    "data-mimetype",
    "data-mimetype-before-conversion",
    "data-original-id",
    "data-original-src",
    "data-resize-width",
)

SOURCE_VISUAL_CLASSES = {
    "oe_img_bg",
    "o_bg_img_center",
    "o_bg_img_origin_border_box",
    "o_cc",
    "o_cc3",
}


def page_view(url):
    page = env["website.page"].search(  # noqa: F821 - supplied by Odoo shell
        [("website_id", "=", WEBSITE_ID), ("url", "=", url)], limit=1
    )
    if not page:
        raise RuntimeError(f"Website page not found: {url}")
    return page.view_id.with_context(lang="en_US")


def first_section(root, url):
    sections = root.xpath("//div[@id='wrap']/section[1]")
    if not sections:
        raise RuntimeError(f"No first section found on {url}")
    return sections[0]


def class_tokens(section):
    return [token for token in section.get("class", "").split() if token]


source_view = page_view(SOURCE_URL)
source_root = etree.fromstring(source_view.arch_db.encode("utf-8"))
source_section = first_section(source_root, SOURCE_URL)

if "oe_img_bg" not in class_tokens(source_section):
    raise RuntimeError("The About Us source title does not have an editable background")

source_style = source_section.get("style", "")
if "background-image" not in source_style:
    raise RuntimeError("The About Us source title does not contain a background image")

for url in TARGET_URLS:
    view = page_view(url)
    root = etree.fromstring(view.arch_db.encode("utf-8"))
    section = first_section(root, url)

    # Preserve the page's snippet/structure classes, while replacing its old
    # background and padding presentation with the editable source settings.
    classes = []
    for token in class_tokens(section):
        if token == "thhs-page-hero":
            continue
        if token in SOURCE_VISUAL_CLASSES:
            continue
        if re.fullmatch(r"p[bt](?:0|4|8|12|16|20|24|28|32|36|40|44|48|52|56|60|64|68|72|76|80|84|88|92|96|100|104|108|112|116|120|124|128|132|136|140|144|148|152|156|160|164|168|172|176|180|184|188|192|196|200|204|208|212|216|220|224|228|232|236|240|244|248|252|256)", token):
            continue
        classes.append(token)

    for token in class_tokens(source_section):
        if token in SOURCE_VISUAL_CLASSES and token not in classes:
            classes.append(token)
    classes.extend(["thhs-unified-title", "pt0", "pb32"])
    section.set("class", " ".join(dict.fromkeys(classes)))

    for attr in BACKGROUND_ATTRS:
        section.attrib.pop(attr, None)
        value = source_section.get(attr)
        if value:
            section.set(attr, value)
    section.set("style", source_style)

    # The source design has a single English / Māori heading and no separate
    # eyebrow row.  Consolidate a meaningful legacy eyebrow only when the
    # heading is not bilingual already, then remove all old eyebrow wrappers.
    headings = section.xpath(".//h1[1] | .//h2[1] | .//h3[1]")
    heading = headings[0] if headings else None
    heading_text = " ".join(heading.itertext()).strip() if heading is not None else ""
    eyebrow_nodes = section.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' thhs-eyebrow ')]"
    )
    eyebrow_texts = []
    for eyebrow in eyebrow_nodes:
        text = " ".join(eyebrow.itertext()).replace("\u200b", "").strip()
        if text and text not in eyebrow_texts:
            eyebrow_texts.append(text)

    if heading is not None and eyebrow_texts and "/" not in heading_text and "|" not in heading_text:
        suffix = " / " + " / ".join(eyebrow_texts)
        if len(heading):
            heading[-1].tail = (heading[-1].tail or "") + suffix
        else:
            heading.text = (heading.text or "") + suffix

    for eyebrow in eyebrow_nodes:
        eyebrow.getparent().remove(eyebrow)

    arch = etree.tostring(root, encoding="unicode")
    etree.fromstring(arch.encode("utf-8"))
    view.write({"arch_db": arch})
    print(f"Unified editable title design: {url} (view {view.id})")

env.cr.commit()  # noqa: F821 - supplied by Odoo shell
print(f"Updated {len(TARGET_URLS)} page titles from {SOURCE_URL}")
