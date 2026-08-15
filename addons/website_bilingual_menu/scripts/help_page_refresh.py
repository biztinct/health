"""Refresh the How You Can Help page while preserving its saved title section.

All giving cards are ordinary HTML links inside Odoo website sections, so the
link destinations and card copy remain editable with Website Edit.
"""

from copy import deepcopy

from lxml import etree


view = env["ir.ui.view"].search(  # noqa: F821 - supplied by Odoo shell
    [("key", "=", "website.how-can-i-help"), ("website_id", "=", 1)], limit=1
).with_context(lang="en_US")
if not view:
    raise RuntimeError("How You Can Help page was not found")

root = etree.fromstring(view.arch_db.encode("utf-8"))
wrap = root.xpath("//div[@id='wrap']")[0]
sections = [child for child in wrap if isinstance(child.tag, str)]
if not sections:
    raise RuntimeError("Page title section was not found")

page_title = deepcopy(sections[0])

content = etree.fromstring(
    """<root>
<section class="s_image_text thhs-help-intro o_colored_level" data-snippet="s_image_text" data-name="Ways to help introduction">
    <div class="container">
        <div class="row align-items-center g-5">
            <div class="col-lg-7 o_colored_level">
                <div class="thhs-help-eyebrow">Local generosity. Lasting impact.</div>
                <h2>Choose how you want to make a difference.</h2>
                <p class="thhs-help-lead">Every contribution—large or small—helps strengthen healthcare services and healthier futures across our region.</p>
                <p>Support the Society in the way that feels right for you. Select an option below to begin, or talk with us about creating something more personal.</p>
            </div>
            <div class="col-lg-5 o_colored_level">
                <div class="thhs-help-illustration">
                    <span class="thhs-help-orbit"/>
                    <img src="/html_editor/shape/illustration/hands-buying-apple-fruit-money-cash-transaction-product-abstract-banknotesvg-927?c2=%23003163&amp;c1=%2388AD59&amp;unique=d6950217" alt="A gift creating community wellbeing" loading="lazy"/>
                    <div class="thhs-help-note"><strong>One community</strong><span>Many ways to help</span></div>
                </div>
            </div>
        </div>
    </div>
</section>

<section class="s_three_columns thhs-help-options o_colored_level" data-snippet="s_three_columns" data-name="Linked ways to help">
    <div class="container">
        <div class="thhs-help-options-head">
            <div><span>Ways to contribute</span><h2>Make your impact.</h2></div>
            <p>Each path supports stronger local health. Choose the one that best reflects how you want to contribute.</p>
        </div>
        <div class="row g-4">
            <div class="col-lg-4 o_colored_level">
                <a class="thhs-help-card thhs-help-card-membership" href="/contactus">
                    <span class="thhs-help-card-number">01</span>
                    <span class="thhs-help-card-icon"><i class="fa fa-refresh"/></span>
                    <span class="thhs-help-card-label">Regular support</span>
                    <h3>Membership donation</h3>
                    <p>Join a community of ongoing supporters helping local health initiatives grow with confidence.</p>
                    <span class="thhs-help-card-action">Become a supporter <i class="fa fa-arrow-right"/></span>
                </a>
            </div>
            <div class="col-lg-4 o_colored_level">
                <a class="thhs-help-card thhs-help-card-philanthropy" href="/contactus">
                    <span class="thhs-help-card-number">02</span>
                    <span class="thhs-help-card-icon"><i class="fa fa-diamond"/></span>
                    <span class="thhs-help-card-label">Transformative giving</span>
                    <h3>Philanthropy</h3>
                    <p>Create lasting impact through a significant gift, legacy or partnership shaped around your vision.</p>
                    <span class="thhs-help-card-action">Start a conversation <i class="fa fa-arrow-right"/></span>
                </a>
            </div>
            <div class="col-lg-4 o_colored_level">
                <a class="thhs-help-card thhs-help-card-givealittle" href="/contactus">
                    <span class="thhs-help-card-number">03</span>
                    <span class="thhs-help-card-icon"><i class="fa fa-heart"/></span>
                    <span class="thhs-help-card-label">Give today</span>
                    <h3>Givealittle</h3>
                    <p>Make a simple one-off contribution and help turn community generosity into practical support.</p>
                    <span class="thhs-help-card-action">Give now <i class="fa fa-arrow-right"/></span>
                </a>
            </div>
        </div>
    </div>
</section>

<section class="s_call_to_action thhs-help-guidance o_colored_level" data-snippet="s_call_to_action" data-name="Giving guidance">
    <div class="container">
        <div class="thhs-help-guidance-panel">
            <div><span>Not sure where to begin?</span><h2>Let’s find the right way to help—together.</h2></div>
            <a class="btn thhs-help-contact" href="/contactus">Talk with us <i class="fa fa-arrow-right"/></a>
        </div>
    </div>
</section>
</root>""".encode("utf-8")
)

for child in list(wrap):
    wrap.remove(child)
wrap.append(page_title)
for child in content:
    wrap.append(deepcopy(child))

new_arch = etree.tostring(root, encoding="unicode")
etree.fromstring(new_arch.encode("utf-8"))
view.write({"arch_db": new_arch})
env.cr.commit()  # noqa: F821
print("How You Can Help page refreshed with editable linked cards")
