"""Install the Option B editorial design below the saved Welcome section.

The first homepage section is preserved as an unchanged XML node. Header,
navigation, logo, Welcome text, background and Welcome presentation remain
outside the scope of this refresh.
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
if not sections or sections[0].get("data-name") != "Home hero":
    raise RuntimeError("The saved Welcome snippet was not found in first position")

welcome = deepcopy(sections[0])

editorial = etree.fromstring(
    """<root>
<section class="thhs-editorial-intro o_colored_level" data-name="People-powered introduction">
    <div class="thhs-editorial-shell">
        <div class="thhs-editorial-overline"><span>People-powered health</span><span>Taupō / Aotearoa</span></div>
        <h2 class="thhs-editorial-display"><span class="thhs-editorial-serif">People</span> make<br/><span class="thhs-editorial-coral">health</span> happen.<span class="thhs-editorial-stamp">Local care<br/>since 1963</span></h2>
        <div class="thhs-editorial-mosaic">
            <div class="thhs-editorial-tile thhs-editorial-image"><img src="/web/image/867-c1651a7a/Taupo-Hospital__FocusFillWyItMC4zMSIsIjAuMDkiLDEwNzEsNzQ3XQ_ExtRewriteWyJqcGciLCJ3ZWJwIl0.webp" alt="Taupō Hospital" loading="lazy"/></div>
            <div class="thhs-editorial-tile thhs-editorial-quote"><p>Care is more than a service. It is how a community holds one another.</p></div>
            <div class="thhs-editorial-tile thhs-editorial-stat"><div><strong>42.7k</strong><span>people call our region home</span></div></div>
            <div class="thhs-editorial-tile thhs-editorial-message"><p><strong>We back the people, ideas and services creating a healthier Taupō.</strong><br/>Local knowledge meets practical action—and everybody has a place in the story.</p></div>
        </div>
    </div>
</section>

<section class="thhs-editorial-ticker o_colored_level" data-name="Community message ticker" aria-label="Community commitments">
    <div><span>Local care</span><b>✦</b><span>Community voice</span><b>✦</b><span>Healthier futures</span><b>✦</b><span>Taupō together</span><b>✦</b><span>Local care</span><b>✦</b><span>Community voice</span><b>✦</b><span>Healthier futures</span><b>✦</b><span>Taupō together</span><b>✦</b></div>
</section>

<section class="thhs-editorial-stories o_colored_level" data-name="Community impact stories">
    <div class="thhs-editorial-wrap">
        <div class="thhs-editorial-section-head thhs-editorial-reveal">
            <h2>Real people.<br/><span>Real impact.</span></h2>
            <p>Our work lives in the everyday moments made possible when local people choose to act together.</p>
        </div>
        <div class="thhs-editorial-cards">
            <article class="thhs-editorial-card thhs-editorial-reveal">
                <div class="thhs-editorial-card-image"><img src="/web/image/867-c1651a7a/Taupo-Hospital__FocusFillWyItMC4zMSIsIjAuMDkiLDEwNzEsNzQ3XQ_ExtRewriteWyJqcGciLCJ3ZWJwIl0.webp" alt="Taupō Hospital entrance" loading="lazy"/></div>
                <div class="thhs-editorial-card-copy"><small>Care close to home</small><h3>Backing local clinical capability.</h3><p>Resources and partnerships that help more people receive quality care in their own region.</p></div>
                <a class="thhs-editorial-circle-link" href="/our-hospital" aria-label="Learn about our hospital">↗</a>
            </article>
            <article class="thhs-editorial-card thhs-editorial-reveal">
                <div class="thhs-editorial-card-image"><img src="/web/image/780-6211f87d/Maunga%20only%20%281%29.webp" alt="Mountains of the Taupō region" loading="lazy"/></div>
                <div class="thhs-editorial-card-copy"><small>Community-led</small><h3>Listening first. Acting together.</h3><p>Local voices and lived experience shape priorities that matter to our whānau.</p></div>
                <a class="thhs-editorial-circle-link" href="/what-we-do" aria-label="Learn what we do">↗</a>
            </article>
        </div>
    </div>
</section>

<section class="thhs-editorial-care o_colored_level" data-name="Community call to action">
    <div class="thhs-editorial-wrap thhs-editorial-care-grid thhs-editorial-reveal">
        <div class="thhs-editorial-care-label">A future worth backing</div>
        <div><h2>What if the best healthcare system was a community that <em>cared?</em></h2><a class="thhs-editorial-cta" href="/how-can-i-help">See how you can help ↗</a></div>
    </div>
</section>
</root>""".encode("utf-8")
)

for child in list(wrap):
    wrap.remove(child)
wrap.append(welcome)
for child in editorial:
    wrap.append(deepcopy(child))

new_arch = etree.tostring(root, encoding="unicode")
etree.fromstring(new_arch.encode("utf-8"))
view.write({"arch_db": new_arch})
env.cr.commit()  # noqa: F821
print("Option B installed below Welcome; Welcome node preserved")
