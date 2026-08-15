"""Make board role labels and portraits cooperate with Website Builder.

Run inside ``odoo-bin shell -d thhs``. The script is idempotent: it removes
legacy inline image padding that interferes with Odoo's crop tool and marks
only genuine governance roles as ``lead`` text. All biography paragraphs and
images remain regular editable Website Builder content.
"""

from lxml import etree


ROLE_LABELS = {
    "CHAIRPERSON",
    "VICE-CHAIRPERSON",
    "VICE CHAIRPERSON",
    "TREASURER",
    "SECRETARY",
    "PATRON",
    "PATRONESS",
}


def class_tokens(element):
    return [token for token in element.get("class", "").split() if token]


def clean_image_style(image):
    declarations = []
    for declaration in image.get("style", "").split(";"):
        declaration = declaration.strip()
        if not declaration or ":" not in declaration:
            continue
        property_name = declaration.split(":", 1)[0].strip().lower()
        if property_name in {"padding", "min-height", "object-position"}:
            continue
        declarations.append(declaration)
    if declarations:
        image.set("style", "; ".join(declarations) + ";")
    else:
        image.attrib.pop("style", None)


page = env["website.page"].search(  # noqa: F821 - supplied by Odoo shell
    [("website_id", "=", 1), ("url", "=", "/our-board")], limit=1
)
if not page:
    raise RuntimeError("Website page not found: /our-board")

view = page.view_id.with_context(lang="en_US")
root = etree.fromstring(view.arch_db.encode("utf-8"))
board_sections = root.xpath(
    "//section[contains(concat(' ', normalize-space(@class), ' '), ' thhs-board-list ')]"
)
if not board_sections:
    raise RuntimeError("Board profiles section was not found")

profiles = board_sections[0].xpath(
    ".//*[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_item ')]"
)
for profile in profiles:
    images = profile.xpath(
        ".//img[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_img ')]"
    )
    for image in images:
        clean_image_style(image)

    bodies = profile.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_body ')]"
    )
    if not bodies:
        continue
    first_paragraphs = bodies[0].xpath("./h3[1]/following-sibling::p[1]")
    if not first_paragraphs:
        continue
    paragraph = first_paragraphs[0]
    label = " ".join(paragraph.itertext()).replace("\u2011", "-").strip().upper()
    classes = class_tokens(paragraph)
    if label in ROLE_LABELS:
        if "lead" not in classes:
            classes.append("lead")
    else:
        classes = [token for token in classes if token != "lead"]
    paragraph.set("class", " ".join(classes))

arch = etree.tostring(root, encoding="unicode")
etree.fromstring(arch.encode("utf-8"))
view.write({"arch_db": arch})
env.cr.commit()  # noqa: F821 - supplied by Odoo shell
print(f"Updated {len(profiles)} editable board profiles (view {view.id})")
