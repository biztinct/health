/* CareJiyo public home: menu, role tabs, gentle reveal, motion switch.
   No trackers, no external requests, no patient data. */
(() => {
    'use strict';
    document.body.classList.add('js');

    // Motion switch: pauses the floating cards; follows the system "reduce motion" setting.
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const motionButton = document.querySelector('.motion-toggle');
    let paused = reduced.matches;
    const paintMotion = () => {
        document.body.classList.toggle('motion-paused', paused);
        if (!motionButton) return;
        motionButton.setAttribute('aria-pressed', String(paused));
        motionButton.querySelector('.motion-label').textContent = paused ? 'Play motion' : 'Pause motion';
        motionButton.querySelector('.motion-symbol').textContent = paused ? '▷' : 'Ⅱ';
    };
    paintMotion();
    motionButton?.addEventListener('click', () => { paused = !paused; paintMotion(); });
    reduced.addEventListener('change', event => { paused = event.matches; paintMotion(); });

    // Header border once the page scrolls.
    const header = document.querySelector('.site-header');
    const onScroll = () => header?.classList.toggle('scrolled', scrollY > 8);
    addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // Mobile menu.
    const menu = document.querySelector('.menu-toggle');
    const nav = document.getElementById('main-nav');
    if (menu && nav) {
        const close = () => { menu.setAttribute('aria-expanded', 'false'); nav.classList.remove('is-open'); };
        menu.addEventListener('click', () => {
            const open = menu.getAttribute('aria-expanded') !== 'true';
            menu.setAttribute('aria-expanded', String(open));
            nav.classList.toggle('is-open', open);
        });
        nav.addEventListener('click', event => { if (event.target.closest('a')) close(); });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') { close(); menu.focus(); }
        });
        matchMedia('(min-width: 961px)').addEventListener('change', close);
    }

    // Role tabs: click, arrow keys, Home/End.
    document.querySelectorAll('[role="tablist"]').forEach(list => {
        const tabs = [...list.querySelectorAll('[role="tab"]')];
        const select = (tab, focus) => {
            tabs.forEach(other => {
                const on = other === tab;
                other.setAttribute('aria-selected', String(on));
                other.tabIndex = on ? 0 : -1;
                document.getElementById(other.getAttribute('aria-controls')).hidden = !on;
            });
            if (focus) tab.focus();
        };
        tabs.forEach((tab, index) => {
            tab.addEventListener('click', () => select(tab, false));
            tab.addEventListener('keydown', event => {
                const last = tabs.length - 1;
                const next = { ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1, ArrowUp: index - 1, Home: 0, End: last }[event.key];
                if (next === undefined) return;
                event.preventDefault();
                select(tabs[(next + tabs.length) % tabs.length], true);
            });
        });
    });

    // Gentle reveal as sections scroll into view.
    const items = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) {
        items.forEach(item => item.classList.add('is-visible'));
        return;
    }
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    }), { rootMargin: '0px 0px -8% 0px', threshold: .08 });
    items.forEach(item => observer.observe(item));
})();
