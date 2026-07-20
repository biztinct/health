document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-select-group]').forEach(group => {
    group.addEventListener('click', event => {
      const item = event.target.closest('[data-selectable]');
      if (!item) return;
      group.querySelectorAll('[data-selectable]').forEach(node => node.classList.remove('active'));
      item.classList.add('active');
      const name = item.dataset.name;
      const target = document.querySelector('[data-selected-name]');
      if (name && target) target.textContent = name;
    });
  });

  document.querySelectorAll('[data-toggle]').forEach(button => {
    button.addEventListener('click', () => {
      const target = document.querySelector(button.dataset.toggle);
      if (!target) return;
      target.classList.toggle('hidden');
      button.setAttribute('aria-expanded', String(!target.classList.contains('hidden')));
    });
  });

  document.querySelectorAll('[data-dismiss]').forEach(button => {
    button.addEventListener('click', () => {
      const target = button.closest(button.dataset.dismiss || '.dismissable');
      if (target) target.classList.add('hidden');
    });
  });

  document.querySelectorAll('[data-toast]').forEach(button => {
    button.addEventListener('click', () => {
      let toast = document.querySelector('.demo-toast');
      if (!toast) {
        toast = document.createElement('div');
        toast.className = 'demo-toast';
        Object.assign(toast.style, {
          position: 'fixed', right: '20px', top: '20px', zIndex: 999,
          color: '#fff', background: '#111827', padding: '12px 16px', borderRadius: '10px',
          boxShadow: '0 16px 36px rgba(16,24,40,.24)', fontSize: '13px', fontWeight: '700'
        });
        document.body.appendChild(toast);
      }
      toast.textContent = button.dataset.toast;
      toast.classList.remove('hidden');
      window.clearTimeout(window.__careToast);
      window.__careToast = window.setTimeout(() => toast.classList.add('hidden'), 2200);
    });
  });

  document.querySelectorAll('[data-tablist]').forEach(tablist => {
    tablist.addEventListener('click', event => {
      const tab = event.target.closest('[data-tab]');
      if (!tab) return;
      const root = tablist.closest('[data-tabs-root]') || document;
      tablist.querySelectorAll('[data-tab]').forEach(node => node.classList.remove('active'));
      root.querySelectorAll('[data-tab-panel]').forEach(node => node.classList.add('hidden'));
      tab.classList.add('active');
      const panel = root.querySelector(`[data-tab-panel="${tab.dataset.tab}"]`);
      if (panel) panel.classList.remove('hidden');
    });
  });
});
