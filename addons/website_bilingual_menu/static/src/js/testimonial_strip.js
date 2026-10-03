/** @odoo-module **/

function initializeTestimonialStrips() {
    // Keep Website Builder content static and editable.
    if (document.body.classList.contains('editor_enable')) return;
    document.querySelectorAll('.thhs26-film').forEach((strip) => {
        if (strip.dataset.ready) return;
        strip.dataset.ready = '1';
        const viewport = strip.querySelector('.thhs26-film-window');
        const toggle = strip.querySelector('[data-film="pause"]');
        const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
        let paused = motion.matches;
        let hovering = false;
        let focused = false;
        let previous = 0;
        const update = () => {
            toggle.textContent = paused ? 'Play testimonials' : 'Pause testimonials';
            toggle.setAttribute('aria-pressed', String(paused));
        };
        toggle.addEventListener('click', () => { paused = !paused; update(); });
        strip.addEventListener('mouseenter', () => { hovering = true; });
        strip.addEventListener('mouseleave', () => { hovering = false; });
        strip.addEventListener('focusin', () => { focused = true; });
        strip.addEventListener('focusout', (event) => { focused = strip.contains(event.relatedTarget); });
        motion.addEventListener('change', () => { paused = motion.matches; update(); });
        for (const direction of ['previous', 'next']) {
            strip.querySelector(`[data-film="${direction}"]`).addEventListener('click', () => {
                paused = true;
                update();
                viewport.scrollBy({left: direction === 'next' ? 234 : -234, behavior: motion.matches ? 'instant' : 'smooth'});
            });
        }
        viewport.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                event.preventDefault();
                paused = true;
                update();
                viewport.scrollBy({left: event.key === 'ArrowRight' ? 234 : -234});
            }
        });
        const step = (time) => {
            if (!strip.isConnected) return;
            const delta = previous ? Math.min(time - previous, 50) : 0;
            previous = time;
            if (!paused && !hovering && !focused && !document.hidden) {
                const end = viewport.scrollWidth - viewport.clientWidth;
                viewport.scrollLeft = viewport.scrollLeft >= end - 1 ? 0 : viewport.scrollLeft + delta * .035;
            }
            requestAnimationFrame(step);
        };
        update();
        requestAnimationFrame(step);
    });
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeTestimonialStrips, {once: true});
else initializeTestimonialStrips();
