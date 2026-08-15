"""Refresh only the homepage content below the saved Welcome snippet.

Run inside ``odoo-bin shell``. The first section is deliberately preserved
byte-for-byte at the XML-node level. Every new section is a normal Odoo
snippet and remains editable with Website Edit.
"""

from copy import deepcopy

from lxml import etree


view = env["ir.ui.view"].search(  # noqa: F821 - supplied by Odoo shell
    [("key", "=", "website.homepage"), ("website_id", "=", 1)], limit=1
).with_context(lang="en_US")
if not view:
    raise RuntimeError("Website homepage view was not found")

root = etree.fromstring(view.arch_db.encode("utf-8"))
wrap = root.xpath("//div[@id='wrap']")[0]
sections = [child for child in wrap if isinstance(child.tag, str)]
if not sections:
    raise RuntimeError("The saved Welcome snippet was not found")

welcome = deepcopy(sections[0])

content = etree.fromstring(
    """<root>
<section class="s_text_block thhs-wow-ribbon o_colored_level pt0 pb0" data-snippet="s_text_block" data-name="Community commitments">
    <div class="container">
        <div class="thhs-wow-ribbon-inner">
            <div class="thhs-wow-ribbon-item o_colored_level"><i class="fa fa-map-marker"/><div><strong>Local care</strong><span>Backing services close to home</span></div></div>
            <div class="thhs-wow-ribbon-item o_colored_level"><i class="fa fa-users"/><div><strong>Community-led</strong><span>Guided by local voices</span></div></div>
            <div class="thhs-wow-ribbon-item o_colored_level"><i class="fa fa-heartbeat"/><div><strong>Equitable access</strong><span>Health support for everyone</span></div></div>
        </div>
    </div>
</section>

<section class="s_image_text thhs-wow-story thhs-section o_colored_level" data-snippet="s_image_text" data-name="Community story">
    <div class="container">
        <div class="row align-items-center g-5 g-xl-6">
            <div class="col-lg-6 o_colored_level">
                <div class="thhs-wow-image-frame">
                    <img src="/web/image/867-c1651a7a/Taupo-Hospital__FocusFillWyItMC4zMSIsIjAuMDkiLDEwNzEsNzQ3XQ_ExtRewriteWyJqcGciLCJ3ZWJwIl0.webp" class="img img-fluid w-100" alt="Taupō Hospital and local health services" loading="lazy"/>
                    <div class="thhs-wow-image-note o_colored_level"><i class="fa fa-heart"/><span>For our people.<br/>For our place.</span></div>
                </div>
            </div>
            <div class="col-lg-6 o_colored_level">
                <div class="thhs-eyebrow">Rooted in community</div>
                <h2 class="display-3">Local people creating healthier futures</h2>
                <p class="thhs-intro">We connect local generosity, knowledge and partnerships with the places they can make the greatest difference.</p>
                <p>From strengthening hospital capability to supporting practical community initiatives, our focus is simple: better care, closer to home.</p>
                <a class="btn btn-primary btn-lg mt-3" href="/background">Discover our story <i class="fa fa-arrow-right ms-2"/></a>
            </div>
        </div>
    </div>
</section>

<section class="s_three_columns thhs-wow-focus thhs-section o_colored_level" data-snippet="s_three_columns" data-name="Our focus">
    <div class="container">
        <div class="row align-items-end mb-5 g-4">
            <div class="col-lg-8 o_colored_level"><div class="thhs-eyebrow">What drives us</div><h2 class="display-3">Three commitments.<br/>One healthier region.</h2></div>
            <div class="col-lg-4 o_colored_level"><p class="thhs-wow-focus-intro">Practical action shaped by the people who live, work and care here.</p></div>
        </div>
        <div class="row g-4">
            <div class="col-lg-4 o_colored_level"><div class="thhs-wow-focus-card"><span class="thhs-wow-number">01</span><i class="fa fa-hospital-o"/><h3>Support local care</h3><p>Helping Taupō Hospital and local services build capability where it matters most.</p><a href="/our-hospital">Our hospital <i class="fa fa-arrow-right"/></a></div></div>
            <div class="col-lg-4 o_colored_level"><div class="thhs-wow-focus-card"><span class="thhs-wow-number">02</span><i class="fa fa-handshake-o"/><h3>Strengthen community</h3><p>Listening to local voices and backing initiatives that improve wellbeing.</p><a href="/what-we-do">What we do <i class="fa fa-arrow-right"/></a></div></div>
            <div class="col-lg-4 o_colored_level"><div class="thhs-wow-focus-card"><span class="thhs-wow-number">03</span><i class="fa fa-compass"/><h3>Champion equity</h3><p>Working toward fair access to physical, mental and spiritual health support.</p><a href="/our-vision">Our vision <i class="fa fa-arrow-right"/></a></div></div>
        </div>
    </div>
</section>

<section class="s_call_to_action thhs-wow-cta thhs-section o_colored_level" data-snippet="s_call_to_action" data-name="Community call to action">
    <div class="container">
        <div class="thhs-wow-cta-panel">
            <div class="row align-items-center g-4">
                <div class="col-lg-8 o_colored_level"><div class="thhs-eyebrow">Together for Taupō</div><h2 class="display-4">Your support can shape what healthcare looks like tomorrow.</h2><p>Partnership, participation and generosity turn local ideas into practical support.</p></div>
                <div class="col-lg-4 text-lg-end o_colored_level"><a class="btn btn-light btn-lg" href="/how-can-i-help">Make a difference <i class="fa fa-arrow-right ms-2"/></a></div>
            </div>
        </div>
    </div>
</section>
</root>""".encode("utf-8")
)

for child in list(wrap):
    wrap.remove(child)
wrap.append(welcome)
for child in content:
    wrap.append(deepcopy(child))

new_arch = etree.tostring(root, encoding="unicode")
etree.fromstring(new_arch.encode("utf-8"))
view.write({"arch_db": new_arch})
env.cr.commit()  # noqa: F821
print("Homepage refreshed; saved Welcome snippet preserved")
