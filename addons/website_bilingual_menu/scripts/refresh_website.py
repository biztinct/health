"""One-time Taupō website content refresh.

Run inside ``odoo-bin shell``. The resulting pages remain normal editable
Website Builder views; the module supplies only reusable presentation styles.
"""

from lxml import etree


def page(template_name, sections):
    return f"""<t t-name="{template_name}">
    <t t-call="website.layout">
        <div id="wrap" class="oe_structure oe_empty">
            {sections}
        </div>
    </t>
</t>"""


def hero(title, eyebrow=None):
    title_html = f"{title} / {eyebrow}" if eyebrow else title
    return f"""<section class="s_title thhs-page-hero o_colored_level" data-vcss="001" data-snippet="s_title" data-name="Page hero">
    <div class="container s_allow_columns">
        <h1>{title_html}</h1>
    </div>
</section>"""


def find_view(key):
    view = env["ir.ui.view"].search(  # noqa: F821 - provided by Odoo shell
        [("key", "=", key), ("website_id", "=", 1)], limit=1
    )
    if not view:
        raise RuntimeError(f"Website view not found: {key}")
    return view.with_context(lang="en_US")


def write_view(key, arch):
    view = find_view(key)
    etree.fromstring(arch.encode("utf-8"))
    view.write({"arch_db": arch})
    print(f"Updated {key} ({view.id})")


home = """<section class="s_banner_connected thhs-home-hero o_colored_level parallax" data-scroll-background-ratio="0.3" data-snippet="s_banner_connected" data-name="Home hero" data-parallax-type="zoomOut">
    <span class="s_parallax_bg oe_img_bg o_bg_img_center o_bg_img_origin_border_box" style="background-image: url('/web/image/780-6211f87d/Maunga%20only%20%281%29.webp');"/>
    <div class="container">
        <div class="row">
            <div class="col-lg-9">
                <div class="thhs-home-kicker">Nau mai, haere mai</div>
                <h1>Healthier futures for Taupō</h1>
                <p class="thhs-home-copy">Taupo Hospital &amp; Health Society supports the Taupō and Tūrangi region by strengthening local hospital and community health services.</p>
                <div class="d-flex flex-wrap gap-3">
                    <a class="btn btn-primary btn-lg" href="/what-we-do">Discover our work</a>
                    <a class="btn btn-outline-light btn-lg rounded-pill px-4" href="/contactus">Get in touch</a>
                </div>
            </div>
        </div>
    </div>
</section>
<section class="s_text_block thhs-impact-strip pb40 o_colored_level" data-snippet="s_text_block" data-name="Impact highlights">
    <div class="container">
        <div class="row g-4">
            <div class="col-md-4 thhs-impact-item"><strong>Local care</strong><span>Backing services close to home</span></div>
            <div class="col-md-4 thhs-impact-item"><strong>Community-led</strong><span>Guided by local needs and experience</span></div>
            <div class="col-md-4 thhs-impact-item"><strong>Equitable access</strong><span>Health support for everyone in our region</span></div>
        </div>
    </div>
</section>
<section class="s_three_columns thhs-section o_colored_level" data-snippet="s_three_columns" data-name="Our focus">
    <div class="container">
        <div class="row mb-5">
            <div class="col-lg-8">
                <div class="thhs-eyebrow">Our focus</div>
                <h2 class="display-4">Strong local care starts with community</h2>
                <p class="thhs-intro">We bring people, resources and local insight together to strengthen health and wellbeing across the Taupō region.</p>
            </div>
        </div>
        <div class="row g-4">
            <div class="col-lg-4"><div class="thhs-card"><i class="fa fa-hospital-o"/><h3>Support local care</h3><p>We help Taupō Hospital and local services build capability where it matters most.</p></div></div>
            <div class="col-lg-4"><div class="thhs-card"><i class="fa fa-users"/><h3>Strengthen community</h3><p>We listen to local voices and support practical initiatives that improve wellbeing.</p></div></div>
            <div class="col-lg-4"><div class="thhs-card"><i class="fa fa-heartbeat"/><h3>Champion equity</h3><p>We work toward fair access to physical, mental and spiritual health support.</p></div></div>
        </div>
    </div>
</section>
<section class="s_call_to_action thhs-section thhs-section-muted o_colored_level" data-snippet="s_call_to_action" data-name="Community call to action">
    <div class="container">
        <div class="row align-items-center g-4">
            <div class="col-lg-8"><div class="thhs-eyebrow">Together for Taupō</div><h2 class="display-5">Help us strengthen healthcare in our region</h2><p class="thhs-intro">Partnership, participation and generosity turn local ideas into practical support.</p></div>
            <div class="col-lg-4 text-lg-end"><a class="btn btn-primary btn-lg" href="/how-can-i-help">How you can help</a></div>
        </div>
    </div>
</section>"""
write_view("website.homepage", page("website.homepage", home))


background = hero("Our background", "About the Society") + """<section class="s_image_text thhs-section o_colored_level" data-snippet="s_image_text" data-name="Our story">
    <div class="container">
        <div class="row align-items-center g-5">
            <div class="col-lg-6"><img src="/web/image/867-c1651a7a/Taupo-Hospital__FocusFillWyItMC4zMSIsIjAuMDkiLDEwNzEsNzQ3XQ_ExtRewriteWyJqcGciLCJ3ZWJwIl0.webp" class="img img-fluid w-100" alt="Taupō Hospital" loading="lazy"/></div>
            <div class="col-lg-6"><div class="thhs-eyebrow">Rooted in community</div><h2 class="display-5">Local people supporting local health</h2><p class="thhs-intro">Taupo Hospital &amp; Health Society exists to support the continuation and development of health services for people across the Taupō region.</p><p>Our work is grounded in a simple belief: everyone should be able to access quality care and support, regardless of location or circumstance.</p><a class="btn btn-primary mt-3" href="/our-vision">Our vision and mission</a></div>
        </div>
    </div>
</section>"""
write_view("website.background", page("website.background", background))


vision = hero("Our vision", "He tirohanga whakamua") + """<section class="s_three_columns thhs-section thhs-section-muted o_colored_level" data-snippet="s_three_columns" data-name="Vision and mission">
    <div class="container">
        <div class="row g-4">
            <div class="col-lg-5"><div class="thhs-card"><div class="thhs-eyebrow">Our vision</div><h2>A healthier Taupō</h2><p class="thhs-intro">Every individual has equitable access to care and support, regardless of location or circumstance.</p></div></div>
            <div class="col-lg-7"><div class="thhs-card"><div class="thhs-eyebrow">Our mission</div><h2>Practical support with lasting impact</h2><ul class="mt-4"><li class="mb-3">Assist the continuation and development of healthcare services across the Taupō region.</li><li class="mb-3">Promote physical, mental and spiritual wellbeing without discrimination.</li><li class="mb-3">Support Taupō Hospital financially or through other practical assistance.</li><li>Advance education and community initiatives aligned with the Society’s aims.</li></ul></div></div>
        </div>
    </div>
</section>"""
write_view("website.our-vision", page("website.our-vision", vision))


what_we_do = hero("What we do", "Ā mātou mahi") + """<section class="s_text_image thhs-section o_colored_level" data-snippet="s_text_image" data-name="What we do introduction">
    <div class="container"><div class="row align-items-center g-5"><div class="col-lg-6"><div class="thhs-eyebrow">Local action</div><h2 class="display-5">Turning community support into better care</h2><p class="thhs-intro">We focus our effort where it can strengthen health services and improve wellbeing for people in our region.</p><p>That includes supporting hospital capability, backing aligned community initiatives and helping local voices shape future priorities.</p></div><div class="col-lg-6"><img src="/web/image/867-c1651a7a/Taupo-Hospital__FocusFillWyItMC4zMSIsIjAuMDkiLDEwNzEsNzQ3XQ_ExtRewriteWyJqcGciLCJ3ZWJwIl0.webp" class="img img-fluid w-100" alt="Taupō Hospital" loading="lazy"/></div></div></div>
</section>
<section class="s_three_columns thhs-section thhs-section-muted o_colored_level" data-snippet="s_three_columns" data-name="Areas of work"><div class="container"><div class="row g-4"><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-medkit"/><h3>Hospital support</h3><p>Equipment, resources and practical assistance that strengthen local clinical services.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-handshake-o"/><h3>Community partnerships</h3><p>Working alongside organisations whose aims align with health, education and wellbeing.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-comments-o"/><h3>Local advocacy</h3><p>Keeping regional needs visible and helping community experience inform priorities.</p></div></div></div></div></section>"""
write_view("website.what-we-do", page("website.what-we-do", what_we_do))


projects = hero("Our projects", "Ā mātou kaupapa") + """<section class="s_three_columns thhs-section o_colored_level" data-snippet="s_three_columns" data-name="Project focus"><div class="container"><div class="row mb-5"><div class="col-lg-8"><h2 class="display-5">Focused on practical local impact</h2><p class="thhs-intro">Our project portfolio connects community support with the needs of local health services.</p></div></div><div class="row g-4"><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-stethoscope"/><h3>Clinical capability</h3><p>Supporting equipment and resources that help clinicians deliver quality care locally.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-map-marker"/><h3>Care close to home</h3><p>Backing opportunities that make health support more accessible across our region.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-line-chart"/><h3>Future priorities</h3><p>Developing initiatives in response to community need and emerging opportunities.</p></div></div></div></div></section>"""
write_view("website.projects", page("website.projects", projects))


successes = hero("Our impact", "Successes") + """<section class="s_three_columns thhs-section thhs-section-muted o_colored_level" data-snippet="s_three_columns" data-name="Impact stories"><div class="container"><div class="row mb-5"><div class="col-lg-8"><h2 class="display-5">Community support that delivers</h2><p class="thhs-intro">Every contribution helps build stronger local health services and better outcomes for our community.</p></div></div><div class="row g-4"><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-heartbeat"/><h3>$350,000 for cardiac diagnostics</h3><p>The Society raised funds to help provide state-of-the-art echocardiogram equipment for Taupō Hospital.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-users"/><h3>Community partnerships</h3><p>Governance, fundraising and local relationships help turn shared priorities into action.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-arrow-circle-o-right"/><h3>Building what comes next</h3><p>We continue to pursue opportunities that strengthen services and improve equitable access.</p></div></div></div></div></section>"""
write_view("website.successes", page("website.successes", successes))


news = hero("News &amp; updates", "Ngā karere") + """<section class="s_three_columns thhs-section o_colored_level" data-snippet="s_three_columns" data-name="News introduction"><div class="container"><div class="row mb-5"><div class="col-lg-8"><h2 class="display-5">What’s happening across our work</h2><p class="thhs-intro">This page is ready for Society news, project announcements and community updates using the Odoo Website Editor.</p></div></div><div class="row g-4"><div class="col-lg-6"><div class="thhs-card"><i class="fa fa-file-text-o"/><h3>Annual reports</h3><p>Read our latest reporting and learn more about the Society’s work.</p><a href="/annual-report" class="btn btn-primary mt-3">View reports</a></div></div><div class="col-lg-6"><div class="thhs-card"><i class="fa fa-calendar"/><h3>Community events</h3><p>See upcoming opportunities to connect, participate and support local health.</p><a href="/event" class="btn btn-primary mt-3">View events</a></div></div></div></div></section>"""
write_view("website.news", page("website.news", news))


hospital = hero("Our hospital", "Ā mātou hōhipera") + """<section class="s_image_text thhs-section o_colored_level" data-snippet="s_image_text" data-name="Hospital partnership"><div class="container"><div class="row align-items-center g-5"><div class="col-lg-6"><img src="/web/image/867-c1651a7a/Taupo-Hospital__FocusFillWyItMC4zMSIsIjAuMDkiLDEwNzEsNzQ3XQ_ExtRewriteWyJqcGciLCJ3ZWJwIl0.webp" class="img img-fluid w-100" alt="Taupō Hospital" loading="lazy"/></div><div class="col-lg-6"><div class="thhs-eyebrow">Care close to home</div><h2 class="display-5">Supporting the people who care for our region</h2><p class="thhs-intro">Taupō Hospital is central to the health and wellbeing of our community.</p><p>The Society provides practical support that helps strengthen local services and responds to opportunities identified with our health partners.</p><a class="btn btn-primary mt-3" href="/contactus">Talk with us</a></div></div></div></section>"""
write_view("website.our-hospital", page("website.our-hospital", hospital))


help_page = hero("How you can help", "Me pēhea koe e āwhina ai") + """<section class="s_three_columns thhs-section thhs-section-muted o_colored_level" data-snippet="s_three_columns" data-name="Ways to help"><div class="container"><div class="row mb-5"><div class="col-lg-8"><h2 class="display-5">Be part of healthier local futures</h2><p class="thhs-intro">There are many ways individuals, organisations and community groups can support the Society’s work.</p></div></div><div class="row g-4"><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-gift"/><h3>Contribute</h3><p>Support practical projects and resources that strengthen healthcare in our region.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-handshake-o"/><h3>Partner</h3><p>Work with us on initiatives aligned with community health, wellbeing and education.</p></div></div><div class="col-lg-4"><div class="thhs-card"><i class="fa fa-bullhorn"/><h3>Connect</h3><p>Share local needs, ideas and opportunities that could make a meaningful difference.</p></div></div></div><div class="text-center mt-5"><a class="btn btn-primary btn-lg" href="/contactus">Start a conversation</a></div></div></section>"""
write_view("website.how-can-i-help", page("website.how-can-i-help", help_page))


contact = hero("Contact us", "Whakapā mai") + """<section class="s_three_columns thhs-section o_colored_level" data-snippet="s_three_columns" data-name="Contact details"><div class="container"><div class="row g-5"><div class="col-lg-7"><div class="thhs-eyebrow">Let’s connect</div><h2 class="display-5">We’d like to hear from you</h2><p class="thhs-intro">Contact the Taupo Hospital &amp; Health Society to discuss our work, community needs, partnership opportunities or ways to help.</p><p class="text-muted">Additional contact information and enquiry options can be added here at any time with the Website Editor.</p></div><div class="col-lg-5"><div class="thhs-card"><h3>Taupo Hospital &amp; Health Society</h3><p class="mt-4"><i class="fa fa-map-marker"/> PO Box 233<br/>Taupō 3351<br/>New Zealand</p><p><i class="fa fa-phone"/> <a href="tel:+64273030642">+64 27 303 0642</a></p></div></div></div></div></section>"""
write_view("website.contactus", page("website.contactus", contact))


# Preserve all board biographies while adding durable editor-friendly styling hooks.
board_view = find_view("website.our-board")
board_root = etree.fromstring(board_view.arch_db.encode("utf-8"))
board_title = board_root.xpath("//div[@id='wrap']/section[1]")[0]
board_title.set("class", "s_text_block thhs-page-hero o_colored_level")
heading = board_title.xpath(".//h1")[0]
for child in list(heading):
    heading.remove(child)
heading.text = "Our Board | Mana whakahaere"
board_section = board_root.xpath("//section[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list ')]")[0]
board_section.set("class", board_section.get("class", "") + " thhs-board-list")
for item in board_section.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_item ')]"):
    item.set("class", item.get("class", "") + " thhs-board-profile")
    names = item.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_body ')]//h3[1]")
    images = item.xpath(".//img[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_img ')]")
    if names and images:
        images[0].set("alt", " ".join(names[0].itertext()).strip())
board_view.write({"arch_db": etree.tostring(board_root, encoding="unicode")})
print(f"Updated website.our-board ({board_view.id})")


# Add the premium title treatment to the existing annual report without touching its report card.
annual_view = find_view("website.annual-report")
annual_root = etree.fromstring(annual_view.arch_db.encode("utf-8"))
annual_title = annual_root.xpath("//div[@id='wrap']/section[1]")[0]
annual_title.set("class", annual_title.get("class", "") + " thhs-page-hero")
annual_heading = annual_title.xpath(".//h2[1]")
if annual_heading:
    for child in list(annual_heading[0]):
        annual_heading[0].remove(child)
    annual_heading[0].text = "Annual Reports | Ngā Pūrongo ā-tau"
annual_view.write({"arch_db": etree.tostring(annual_root, encoding="unicode")})
print(f"Updated website.annual-report ({annual_view.id})")


footer_arch = """<data inherit_id="website.layout" name="Default" active="True">
    <xpath expr="//div[@id='footer']" position="replace">
        <div id="footer" class="oe_structure oe_structure_solo text-break" t-ignore="true" t-if="not no_footer">
            <section class="s_text_block thhs-footer o_colored_level" data-snippet="s_text_block" data-name="Taupō footer">
                <div class="container">
                    <div class="row g-5">
                        <div class="col-lg-5 thhs-footer-brand"><strong>Taupo Hospital &amp; Health Society</strong><p>Supporting stronger local health services and healthier futures across the Taupō region.</p></div>
                        <div class="col-6 col-lg-2"><h5>Explore</h5><ul class="list-unstyled"><li><a href="/background">About us</a></li><li><a href="/what-we-do">What we do</a></li><li><a href="/our-board">Our board</a></li><li><a href="/projects">Projects</a></li></ul></div>
                        <div class="col-6 col-lg-2"><h5>Connect</h5><ul class="list-unstyled"><li><a href="/news">News</a></li><li><a href="/event">Events</a></li><li><a href="/how-can-i-help">How to help</a></li><li><a href="/contactus">Contact us</a></li></ul></div>
                        <div class="col-lg-3"><h5>Contact</h5><p>PO Box 233<br/>Taupō 3351<br/>New Zealand</p><p><a href="tel:+64273030642">+64 27 303 0642</a></p></div>
                    </div>
                </div>
            </section>
        </div>
    </xpath>
</data>"""
footer_view = find_view("website.footer_custom")
etree.fromstring(footer_arch.encode("utf-8"))
footer_view.write({"arch_db": footer_arch})
print(f"Updated website.footer_custom ({footer_view.id})")


website = env["website"].browse(1)  # noqa: F821
website.write({"name": "Taupo Hospital & Health Society"})
print("Updated website name")


# Polish the existing top-level menu labels while keeping them editor-managed.
menu_names = {
    11: "About Us|Ā mātou tangata",
    16: "Latest News & Reports|Ngā karere",
    21: "Our Projects|Ā mātou kaupapa",
    35: "Events|Takahanga",
    38: "Our Hospital|Ā mātou hōhipera",
}
for menu_id, menu_name in menu_names.items():
    menu = env["website.menu"].browse(menu_id).with_context(lang="en_US")  # noqa: F821
    if menu.exists() and menu.website_id.id == 1:
        menu.write({"name": menu_name})
print("Polished bilingual menu labels")


env.cr.commit()  # noqa: F821
print("Taupō website refresh committed")
