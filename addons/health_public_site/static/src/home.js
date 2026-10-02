/* The public homepage has no analytics, remote scripts or patient-data requests. */
(() => {
    'use strict';
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
            if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') {
                close(); menu.focus();
            }
        });
        window.matchMedia('(min-width: 901px)').addEventListener('change', close);
    }
    const tabs = [...document.querySelectorAll('[data-demo-tab]')];
    const activate = (selected, focus = false) => {
        tabs.forEach(tab => {
            const active = tab === selected;
            tab.setAttribute('aria-selected', String(active));
            tab.tabIndex = active ? 0 : -1;
            document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
        });
        if (focus) selected.focus();
    };
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => activate(tab));
        tab.addEventListener('keydown', event => {
            const targets = {ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1};
            if (Object.prototype.hasOwnProperty.call(targets, event.key)) {
                event.preventDefault(); activate(tabs[targets[event.key]], true);
            }
        });
    });
})();
