"""Native, editable Odoo carousels shared by content build and scoped migration."""
from html import escape
from lxml import etree


def carousel(profiles, identifier, *, successes=False):
    slides = []
    indicators = []
    for index, (name, content) in enumerate(profiles):
        active = 'active' if index == 0 else ''
        if not successes:
            content = f'<div class="container oe_unremovable"><div class="carousel-content">{content}</div></div>'
        slides.append(f'<div class="carousel-item {active} pt24 pb64 o_colored_level" data-name="{escape(name)}">{content}</div>')
        indicators.append(f'<button type="button" data-bs-target="#{identifier}" data-bs-slide-to="{index}" class="{active}" aria-label="{escape(name)}" title="{escape(name)}"/>')
    kind = 'slide' if successes else 'profile'
    style = 'thhs26-slideshow' if successes else 'thhs26-profiles'
    # Without Bootstrap's `slide` class transitions complete synchronously.
    # Bootstrap otherwise ignores next/previous clicks during its 600ms animation.
    return f'''<section class="s_carousel_wrapper {style} p-0" data-snippet="s_carousel" data-name="Editable {'successes' if successes else 'board profiles'}" data-vxml="001" data-vcss="001"><div id="{identifier}" class="s_carousel s_carousel_default carousel" data-bs-interval="false"><div class="carousel-inner">{''.join(slides)}</div><button type="button" class="carousel-control-prev o_not_editable" contenteditable="false" data-bs-target="#{identifier}" data-bs-slide="prev" aria-label="Previous {kind}"><span class="carousel-control-prev-icon" aria-hidden="true"/><span class="visually-hidden">Previous</span></button><button type="button" class="carousel-control-next o_not_editable" contenteditable="false" data-bs-target="#{identifier}" data-bs-slide="next" aria-label="Next {kind}"><span class="carousel-control-next-icon" aria-hidden="true"/><span class="visually-hidden">Next</span></button><div class="carousel-indicators o_not_editable">{''.join(indicators)}</div></div></section>'''


def upgrade_carousels(arch, url):
    """Wrap live content, never replace it with a stale copy of the client import."""
    root = etree.fromstring(arch.encode())
    identifiers = {'/our-board': 'thhsBoard', '/our-patrons': 'thhsPatrons',
                   '/associate-members': 'thhsAssociates', '/successes': 'thhsSuccesses'}
    identifier = identifiers[url]
    if url == '/successes' and not root.xpath(f'.//*[@id="{identifier}"]'):
        wraps = root.xpath('.//*[@id="wrap"]')
        if len(wraps) != 1:
            raise ValueError('Expected exactly one Successes content wrapper')
        wrap = wraps[0]
        sections = [wrap.xpath('./section[contains(concat(" ", @class, " "), " '+cls+' ")]')
                    for cls in ('thhs26-successes', 'thhs26-success-photo')]
        if any(len(group) != 1 for group in sections):
            raise ValueError('Expected the two original Successes sections; review live edits')
        first, second = (group[0] for group in sections)
        markup = carousel([
            ('Grants and purchases', etree.tostring(first, encoding='unicode', with_tail=False)),
            ('Cheque presentation', etree.tostring(second, encoding='unicode', with_tail=False)),
        ], identifier, successes=True)
        wrap.insert(wrap.index(first), etree.fromstring(markup.encode()))
        wrap.remove(first)
        wrap.remove(second)
    targets = root.xpath(f'.//*[@id="{identifier}"]')
    if len(targets) != 1:
        raise ValueError(f'Expected one carousel {identifier}; review live edits')
    target = targets[0]
    target.set('class', ' '.join(c for c in target.get('class', '').split() if c != 'slide'))
    for button in target.xpath('./button[@data-bs-slide]'):
        button.set('type', 'button')
    return etree.tostring(root, encoding='unicode')
