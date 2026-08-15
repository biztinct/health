"""Refresh the editable board and news pages for Taupō Hospital.

Run inside ``odoo-bin shell`` after upgrading the module.  Page content is
stored as ordinary Website Builder sections and images are public Odoo
attachments, so editors can continue changing text and replacing imagery.
"""

import base64
import os

from lxml import etree
from odoo.modules.module import get_module_path


WEBSITE_ID = 1


def find_view(key):
    view = env["ir.ui.view"].search(  # noqa: F821 - supplied by Odoo shell
        [("key", "=", key), ("website_id", "=", WEBSITE_ID)], limit=1
    )
    if not view:
        raise RuntimeError(f"Website view not found: {key}")
    return view.with_context(lang="en_US")


def add_class(element, class_name):
    classes = element.get("class", "").split()
    if class_name not in classes:
        classes.append(class_name)
    element.set("class", " ".join(classes))


def image_attachment(filename, display_name, view):
    module_path = get_module_path("website_bilingual_menu")
    path = os.path.join(
        module_path, "static", "src", "img", "news", filename
    )
    if not os.path.isfile(path):
        raise RuntimeError(f"Bundled news image not found: {filename}")
    with open(path, "rb") as image_file:
        datas = base64.b64encode(image_file.read())

    attachment = env["ir.attachment"].search(  # noqa: F821
        [
            ("name", "=", display_name),
            ("res_model", "=", "ir.ui.view"),
            ("res_id", "=", view.id),
        ],
        limit=1,
    )
    values = {
        "name": display_name,
        "type": "binary",
        "datas": datas,
        "mimetype": "image/jpeg",
        "public": True,
        "res_model": "ir.ui.view",
        "res_id": view.id,
    }
    if attachment:
        attachment.write(values)
    else:
        attachment = env["ir.attachment"].create(values)  # noqa: F821
    return attachment


def editable_image(attachment, alt, css_class="thhs-news-image"):
    return (
        f'<img src="/web/image/{attachment.id}" '
        f'data-original-id="{attachment.id}" data-original-src="/web/image/{attachment.id}" '
        f'data-mimetype="image/jpeg" class="img img-fluid o_we_custom_image {css_class}" '
        f'alt="{alt}" loading="lazy"/>'
    )


# Board: preserve every biography and image while adding idempotent styling hooks.
board_view = find_view("website.our-board")
board_root = etree.fromstring(board_view.arch_db.encode("utf-8"))
wrap = board_root.xpath("//div[@id='wrap']")[0]
title_sections = wrap.xpath("./section[1]")
if title_sections:
    add_class(title_sections[0], "thhs-page-hero")
    headings = title_sections[0].xpath(".//h1[1] | .//h2[1]")
    if headings:
        for child in list(headings[0]):
            headings[0].remove(child)
        headings[0].text = "Our Board | Mana whakahaere"

board_sections = board_root.xpath(
    "//section[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list ')]"
)
if not board_sections:
    raise RuntimeError("Board media-list section was not found")
board_section = board_sections[0]
add_class(board_section, "thhs-board-list")
board_section.set("data-name", "Board profiles")
for item in board_section.xpath(
    ".//*[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_item ')]"
):
    add_class(item, "thhs-board-profile")
    names = item.xpath(
        ".//*[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_body ')]//h3[1]"
    )
    images = item.xpath(
        ".//img[contains(concat(' ', normalize-space(@class), ' '), ' s_media_list_img ')]"
    )
    if names and images:
        images[0].set("alt", " ".join(names[0].itertext()).strip())
        images[0].set("loading", "lazy")
board_arch = etree.tostring(board_root, encoding="unicode")
etree.fromstring(board_arch.encode("utf-8"))
board_view.write({"arch_db": board_arch})
print(f"Updated editable board view {board_view.id}")


# News: convert the supplied Word stories into normal editable website sections.
news_view = find_view("website.news")
ngaire = image_attachment("ngaire-buchanan.jpeg", "Ngaire Buchanan - Taupo Hospital", news_view)
maaike = image_attachment("maaike-koha.jpeg", "Maaike de Goede koha - Taupo Hospital", news_view)
rmip = image_attachment("rmip-team.jpeg", "Taupo Hospital rural medical team", news_view)

ngaire_image = editable_image(ngaire, "Taupō Hospital General Manager Ngaire Buchanan")
maaike_image = editable_image(maaike, "Maaike de Goede and Ralston D’Souza with the donated pātiki artwork")
rmip_image = editable_image(rmip, "Taupō Hospital rural medical team")

news_arch = f"""<t t-name="website.news">
    <t t-call="website.layout">
        <div id="wrap" class="oe_structure oe_empty">
            <section class="s_title thhs-page-hero o_colored_level" data-vcss="001" data-snippet="s_title" data-name="News hero">
                <div class="container s_allow_columns">
                    <div class="thhs-eyebrow">Latest news &amp; reports</div>
                    <h1>News | Ngā karere</h1>
                </div>
            </section>

            <section class="s_image_text thhs-news-lead o_colored_level" data-snippet="s_image_text" data-name="General Manager update">
                <div class="container">
                    <article class="thhs-news-feature">
                        <div>{ngaire_image}</div>
                        <div class="thhs-news-copy">
                            <div class="thhs-eyebrow">Hospital update</div>
                            <h2>Ten months on in Taupō</h2>
                            <p class="thhs-intro">At the end of July, I will have been in the general manager role for 10 months.</p>
                            <p>There has been a lot going on over that time. For me, it has been learning about the community in a community, from the community.</p>
                            <p>I’ve also been learning about the one service, two sites model and working in partnership with the overarching service managers, senior leaders and our clinicians.</p>
                            <p><strong>Ngaire Buchanan</strong><br/>General Manager, Taupō Hospital</p>
                        </div>
                    </article>
                </div>
            </section>

            <section class="s_text_block thhs-section o_colored_level" data-snippet="s_text_block" data-name="Ten months on full update">
                <div class="container">
                    <div class="thhs-news-body">
                        <div class="thhs-news-stats">
                            <div><strong>42,700</strong><span>Current Taupō / Tūrangi population</span></div>
                            <div><strong>67,400</strong><span>Forecast population by 2060</span></div>
                            <div><strong>19,000</strong><span>Emergency presentations each year</span></div>
                        </div>
                        <p>Taking on the Taupō ED management on a temporary basis has added to my understanding of how everything works here.</p>
                        <p>The Taupō / Tūrangi population is currently at 42,700 and forecast to grow to approximately 67,400 by 2060. Five years ago, the population was approximately 28,000. The growth rate in 2024/25 was 1.2 per cent higher than the national average. Our Māori population is currently at 31 percent. And we know, with Taupō as a tourist destination, we double (80,000) our population in our high seasons and the events we have here.</p>
                        <p>Currently we have approximately 19,000 presentations to our emergency department every year. In 2019 it was 12,000.</p>
                        <h3>Planning together for local care</h3>
                        <p>That means we need to work collaboratively and carefully plan to continue to provide appropriate care for our community. This is not simply building more, but thinking creatively about how we can provide the services in a different way across the patient population.</p>
                        <p>We cannot do this alone. Taupō Hospital has great community connections with our hospital representatives on a range of local leadership groups including the Taupō / Tūrangi Leadership Groups and the Regional Clinical Rural Network, with a link to the National Clinical Rural Network. All groups have a wide range of membership including primary health care, iwi, Iwi Māori Partnership Board (IMPB), planning and secondary services.</p>
                        <p>The opportunities within all groups include working in partnership towards rural generalism pathways and cross-professional workforce planning and population outcomes.</p>
                        <h3>Growing rural skills and services</h3>
                        <p>Within Taupō / Tūrangi we are developing endoscopy training for rural generalists, with Taupō recently securing funding for training, and we are strengthening our RMO workforce. Our innovative approach has seen our specialists working in partnership with iwi to run marae-based outreach clinics.</p>
                        <p>We are delighted that Taupō has recently been successful in gaining fifth-year medical students as part of the Rural Medical Immersion Program (Auckland University), which is a training programme across both primary care and secondary care for a one-year term of their training.</p>
                        <p>Closer still to home, the hospital has celebrated our first official nurse practitioner—we are very proud of home-grown ED nurse Hailey Holmes—and we have a second senior nurse, Jason Tillman, close to achieving his registration in New Zealand.</p>
                        <p>The outpatient project, to bring care closer to home for our residents, is well underway with multiple new outpatient appointments being delivered on site. The next stage is to increase our telemedicine capabilities on site and then into our patients’ homes.</p>
                        <p>Surgical services have been ensuring our operating room is up to date and ready for increasing services on site. In the next six months, I am charged with getting the theatre used 10 half-days a week for surgery or endoscopy.</p>
                        <h3>Safe care, as close to home as possible</h3>
                        <p>With the strengthening of our Clinical Governance on site and improved recruitment, we now have a designated person providing liaison between Rotorua and Taupō. The two EDs have completed a planning session identifying four areas to work on together.</p>
                        <p>The latest programme of work to begin is our strategy for our Taupō inpatient unit (TIU), which will see more Taupō patients being able to be cared for acutely in the TIU.</p>
                        <p>We are working with the Lakes Integrated Community Health Service (LICHS) team to introduce Hospital in the Home (HiTH). This will give us the capacity to accommodate further patients requiring care in TIU and we will not need to transfer so many to Rotorua unless for specialist care.</p>
                        <blockquote class="thhs-news-quote">With all of these matters on the go, it makes for exciting times. It is a group effort, with one goal in mind: the patients and their whānau, to provide the best, most appropriate and safe care as close to home as possible.</blockquote>
                        <p>I am certainly looking forward to the next year with our teams and communities.</p>
                        <p><strong>Ngaire Buchanan</strong><br/>General Manager, Taupō Hospital</p>
                    </div>
                </div>
            </section>

            <section class="s_three_columns thhs-section thhs-section-muted o_colored_level" data-snippet="s_three_columns" data-name="More hospital news">
                <div class="container">
                    <div class="row mb-5">
                        <div class="col-lg-8">
                            <div class="thhs-eyebrow">Our people</div>
                            <h2 class="display-5">Building the future of rural medicine</h2>
                        </div>
                    </div>
                    <div class="thhs-news-grid">
                        <article class="thhs-news-article">
                            <div>{maaike_image}</div>
                            <div class="thhs-news-copy">
                                <div class="thhs-eyebrow">Our people</div>
                                <h2>Taupō experience leads PGY1 to rural medicine</h2>
                                <p>PGY1 House Officer Maaike de Goede (Ngāti Maniapoto, Ngāti Haua) enjoyed her three-month placement at Taupō Hospital so much, she’s aiming to specialise in rural medicine.</p>
                                <p>She says there’s lots of great support at Taupō and Clinical Director Ralston D’Souza is creating an environment where people want to return.</p>
                                <p class="thhs-news-caption">Maaike (pictured left) donated this artwork, accepted by Ralston D’Souza on behalf of Taupō Hospital.</p>
                                <blockquote class="thhs-news-quote">“This koha is a piece that was personally hand woven. It depicts a pātiki, or flounder fish in English. The pātiki is an important pattern used in tukutuku as it symbolises abundance, prosperity, manaakitanga, and the community’s ability to provide—all things that perfectly sum up Taupō Hospital.”</blockquote>
                                <p>“I aim to do rural medicine. I’m rural medicine to my core. I don’t enjoy big hospitals. If I could sign up for longer than three months at Taupō Hospital, I would,” Maaike says.</p>
                                <p>Maaike chose to do all her placements in Rotorua Hospital while she was studying medicine.</p>
                                <p>“In a smaller hospital I get to know everyone—orderlies, kitchen staff, there’s no hierarchy. In Taupō it’s even better.”</p>
                                <p>“I feel like as soon as I got here, I was accepted and fitted in straight away. I go for a swim in the lake every week with the CNM, then go for croissants and coffee with people in the community.”</p>
                            </div>
                        </article>

                        <article class="thhs-news-article">
                            <div>{rmip_image}</div>
                            <div class="thhs-news-copy">
                                <div class="thhs-eyebrow">News</div>
                                <h2>Excitement and pride for Taupō Hospital</h2>
                                <p class="thhs-news-caption">From left: Dr Robin Chan (rural generalist &amp; GP Liaison), Hannah Hickey (administration team lead &amp; Taupō medical student coordinator), Kiara Theron (house officer), and Ralston D’Souza (clinical lead).</p>
                                <p>Health New Zealand | Te Whatu Ora Lakes is very proud that Taupō Hospital will join the University of Auckland’s Rural Medical Immersion Programme (RMIP) in 2027, says Group Director Operations Alan Wilson.</p>
                                <p>Alan says the inclusion of Taupō into the programme is possible because of the outstanding commitment of Clinical Lead Dr Ralston D’Souza, local clinicians and other staff to growing the future rural medical workforce.</p>
                                <blockquote class="thhs-news-quote">“This is a fantastic acknowledgment of our staff and the clinical excellence that our Taupō community has available to it because of the commitment of local clinicians.”</blockquote>
                                <p>The University of Auckland’s year-long rural immersion model will see Year 5 medical students learning alongside Taupō Hospital doctors, local general practitioners, and multidisciplinary healthcare teams.</p>
                                <p>Taupō Hospital Clinical Lead Dr Ralston D’Souza says Taupō Hospital is very excited to join the programme, train and support students, and inspire them to choose careers in rural medicine.</p>
                                <p>“The team at Taupō Hospital has worked really hard to build a culture of training and pastoral care for both our students and resident doctors,” Ralston says.</p>
                                <p>“In the last three years, we have been supervising approximately 50 medical students per year across Years 4, 5 and 6. We’ve tried to ensure they have a great clinical experience both in the hospital and the community and offer a teaching programme that includes early exposure to point-of-care ultrasound training.”</p>
                                <p>Taupō will be the RMIP programme’s fifth long-placement site, joining the established RMIP locations of Hāwera, Hauraki/Thames, Te Kūiti, and Wellsford.</p>
                            </div>
                        </article>
                    </div>
                </div>
            </section>

            <section class="s_call_to_action thhs-section o_colored_level" data-snippet="s_call_to_action" data-name="Reports call to action">
                <div class="container">
                    <div class="row align-items-center g-4">
                        <div class="col-lg-8">
                            <div class="thhs-eyebrow">Reports and accountability</div>
                            <h2 class="display-5">See our work in context</h2>
                            <p class="thhs-intro">Explore annual reports and updates from Taupo Hospital &amp; Health Society.</p>
                        </div>
                        <div class="col-lg-4 text-lg-end"><a class="btn btn-primary btn-lg" href="/annual-report">View annual reports</a></div>
                    </div>
                </div>
            </section>
        </div>
    </t>
</t>"""

etree.fromstring(news_arch.encode("utf-8"))
news_view.write({"arch_db": news_arch})
news_page = env["website.page"].search(  # noqa: F821
    [("view_id", "=", news_view.id), ("website_id", "=", WEBSITE_ID)], limit=1
)
if news_page:
    news_page.write({"name": "News"})
print(f"Updated editable news view {news_view.id}")
print(f"News attachments: {ngaire.id}, {maaike.id}, {rmip.id}")

env.cr.commit()  # noqa: F821
print("Board and news refresh committed")
