"""Clean up the temporary spacing class used during resize verification.

Run inside ``odoo-bin shell -d thhs``. This is intentionally narrow: it only
removes the ``pt16`` class accidentally applied to the General Manager update
while testing the Website Builder resize controls.
"""

from lxml import etree


page = env["website.page"].search(  # noqa: F821 - supplied by Odoo shell
    [("website_id", "=", 1), ("url", "=", "/news")], limit=1
)
if not page:
    raise RuntimeError("Website page not found: /news")

view = page.view_id.with_context(lang="en_US")
root = etree.fromstring(view.arch_db.encode("utf-8"))
sections = root.xpath(
    "//section[contains(concat(' ', normalize-space(@class), ' '), ' thhs-news-lead ')]"
)
if not sections:
    raise RuntimeError("General Manager update section was not found")

section = sections[0]
classes = [token for token in section.get("class", "").split() if token != "pt16"]
section.set("class", " ".join(classes))

arch = etree.tostring(root, encoding="unicode")
etree.fromstring(arch.encode("utf-8"))
view.write({"arch_db": arch})
env.cr.commit()  # noqa: F821 - supplied by Odoo shell
print(f"Restored default General Manager update spacing (view {view.id})")
