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
        document.querySelectorAll('svg.route-map').forEach(svg => {
            try { paused ? svg.pauseAnimations() : svg.unpauseAnimations(); } catch (error) { /* decoration only */ }
        });
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

    // Book a demo: a native dialog; the form posts to the CareJiyo intake.
    const dialog = document.getElementById('book-demo');
    if (dialog && typeof dialog.showModal === 'function') {
        const form = dialog.querySelector('.demo-form');
        const done = dialog.querySelector('.demo-done');
        const formError = form.querySelector('.form-error');
        const submit = form.querySelector('.demo-submit');
        let opener = null;
        const clearErrors = () => {
            formError.hidden = true;
            form.querySelectorAll('.field-error').forEach(node => { node.textContent = ''; });
            form.querySelectorAll('[aria-invalid]').forEach(node => node.removeAttribute('aria-invalid'));
        };
        const open = trigger => {
            opener = trigger || null;
            if (done.hidden === false) { form.reset(); form.hidden = false; done.hidden = true; }
            clearErrors();
            form.elements.started.value = String(Date.now());
            if (!dialog.open) dialog.showModal();
            form.elements.name.focus();
        };
        const close = () => { if (dialog.open) dialog.close(); };
        dialog.addEventListener('close', () => {
            if (location.hash === '#book-demo') history.replaceState(null, '', location.pathname + location.search);
            opener?.focus();
        });
        document.addEventListener('click', event => {
            const trigger = event.target.closest('[data-demo="open"], a[href="#book-demo"]');
            if (trigger) { event.preventDefault(); open(trigger); return; }
            if (event.target.closest('[data-demo="close"]')) { event.preventDefault(); close(); return; }
            if (event.target === dialog) close(); // backdrop
        });
        if (location.hash === '#book-demo') open(null);
        form.addEventListener('submit', async event => {
            event.preventDefault();
            clearErrors();
            submit.disabled = true;
            const label = submit.textContent;
            submit.textContent = 'Sending…';
            try {
                const response = await fetch(form.action, {
                    method: 'POST', body: new FormData(form), credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const result = await response.json().catch(() => ({}));
                if (response.ok && result.ok) {
                    form.hidden = true;
                    done.hidden = false;
                    done.focus();
                    return;
                }
                const errors = result.errors || {};
                let first = null;
                Object.entries(errors).forEach(([field, message]) => {
                    const slot = form.querySelector(`.field-error[data-for="${field}"]`);
                    const input = form.elements[field];
                    if (slot && input) {
                        slot.textContent = message;
                        input.setAttribute('aria-invalid', 'true');
                        first = first || input;
                    }
                });
                if (errors.form || !first) {
                    formError.textContent = errors.form || 'Something went wrong. Please try again, or email hello@carejiyo.com.';
                    formError.hidden = false;
                }
                first?.focus();
            } catch (error) {
                formError.textContent = 'We could not send your request. Please check your connection and try again.';
                formError.hidden = false;
            } finally {
                submit.disabled = false;
                submit.textContent = label;
            }
        });
    }

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
