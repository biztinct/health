/** @odoo-module **/

function initializeTestimonialStrips() {
    if (document.body.classList.contains('editor_enable')) {
        document.querySelectorAll('[data-film-copy]').forEach((copy) => copy.remove());
        return;
    }
    document.querySelectorAll('.thhs26-film').forEach((strip) => {
        if (strip.dataset.ready) return;
        strip.dataset.ready = '1';
        const viewport = strip.querySelector('.thhs26-film-window');
        const track = strip.querySelector('.thhs26-film-track');
        const cards = Array.from(track.children);
        const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
        let hovering = false;
        let focused = false;
        let previous = 0;
        let position = 0;
        let seam = 0;
        const copies = [];
        const rebuild = () => {
            copies.splice(0).forEach((copy) => copy.remove());
            if (!cards.length || motion.matches) return;
            const gap = parseFloat(getComputedStyle(track).gap) || 0;
            seam = cards.reduce((sum, card) => sum + card.getBoundingClientRect().width + gap, 0);
            for (let group = 0; group < Math.ceil(viewport.clientWidth / seam) + 1; group++) {
                cards.forEach((card) => {
                    const copy = card.cloneNode(true);
                    copy.setAttribute('data-film-copy', '1');
                    copy.setAttribute('aria-hidden', 'true');
                    copy.setAttribute('tabindex', '-1');
                    track.append(copy);
                    copies.push(copy);
                });
            }
        };
        strip.addEventListener('mouseenter', () => { hovering = true; });
        strip.addEventListener('mouseleave', () => { hovering = false; });
        strip.addEventListener('focusin', () => { focused = true; });
        strip.addEventListener('focusout', (event) => { focused = strip.contains(event.relatedTarget); });
        viewport.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                event.preventDefault();
                viewport.scrollBy({left: event.key === 'ArrowRight' ? 234 : -234});
                position = viewport.scrollLeft;
            }
        });
        viewport.addEventListener('scroll', () => { if (focused) position = viewport.scrollLeft; });
        const resize = new ResizeObserver(rebuild);
        resize.observe(viewport);
        motion.addEventListener('change', rebuild);
        const step = (time) => {
            if (!strip.isConnected) { resize.disconnect(); return; }
            if (document.body.classList.contains('editor_enable')) return;
            const delta = previous ? Math.min(time - previous, 50) : 0;
            previous = time;
            if (!motion.matches && !hovering && !focused && !document.hidden && seam) {
                position = (position + delta * .035) % seam;
                viewport.scrollLeft = position;
            }
            requestAnimationFrame(step);
        };
        rebuild();
        requestAnimationFrame(step);
    });
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeTestimonialStrips, {once: true});
else initializeTestimonialStrips();
new MutationObserver(initializeTestimonialStrips).observe(document.documentElement, {childList: true, subtree: true});
new MutationObserver(initializeTestimonialStrips).observe(document.body, {attributes: true, attributeFilter: ['class']});
