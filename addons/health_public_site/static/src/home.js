/* Public illustrations only: no clinical data, trackers or external requests. */
(() => {
    'use strict';
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let paused = reduced.matches;
    const motionButton = document.querySelector('.motion-toggle');
    const vi = document.documentElement.lang === 'vi';
    const paintMotionState = () => {
        document.body.classList.toggle('motion-paused', paused);
        if (motionButton) {
            motionButton.setAttribute('aria-pressed', String(paused));
            motionButton.querySelector('.motion-label').textContent = paused
                ? (vi ? 'Bật chuyển động' : 'Play motion')
                : (vi ? 'Tạm dừng chuyển động' : 'Pause motion');
            motionButton.querySelector('.motion-symbol').textContent = paused ? '▷' : 'Ⅱ';
        }
    };
    paintMotionState();
    motionButton?.addEventListener('click', () => { paused = !paused; paintMotionState(); });
    reduced.addEventListener('change', event => { paused = event.matches; paintMotionState(); });
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
        matchMedia('(min-width: 901px)').addEventListener('change', close);
    }
    // A lightweight projected 3D network. All points are procedural decoration.
    document.querySelectorAll('.network-scene').forEach(scene => {
        const canvas = scene.querySelector('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        let width = 0, height = 0, visible = true, frame = 0, elapsed = 0, last = 0;
        const ratio = Math.min(devicePixelRatio || 1, 1.5);
        const resize = () => {
            width = scene.clientWidth; height = scene.clientHeight;
            canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
            ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
            draw(elapsed);
        };
        const project = (x, y, z, angle) => {
            const ry = x * Math.sin(angle) + z * Math.cos(angle);
            const rx = x * Math.cos(angle) - z * Math.sin(angle);
            const scale = 550 / (550 + ry);
            return [width * .49 + rx * scale, height * .49 + y * scale, scale];
        };
        const draw = time => {
            ctx.clearRect(0, 0, width, height);
            const radius = Math.min(width * .40, height * .34);
            const rotation = time * .000055;
            for (let ring = 0; ring < 8; ring++) {
                const tilt = ring * Math.PI / 8;
                ctx.beginPath();
                for (let i = 0; i <= 96; i++) {
                    const a = i / 96 * Math.PI * 2;
                    const x = Math.cos(a) * radius;
                    const y = Math.sin(a) * radius * Math.cos(tilt);
                    const z = Math.sin(a) * radius * Math.sin(tilt);
                    const point = project(x, y, z, rotation);
                    i ? ctx.lineTo(point[0], point[1]) : ctx.moveTo(point[0], point[1]);
                }
                ctx.strokeStyle = ring % 2 ? 'rgba(100,207,216,.16)' : 'rgba(112,156,255,.21)';
                ctx.lineWidth = .7; ctx.stroke();
                // Travelling lights make the connections visibly flow.
                for (let p = 0; p < 3; p++) {
                    const a = rotation * (ring % 2 ? 2 : -2) + p * Math.PI * 2 / 3 + ring;
                    const point = project(Math.cos(a) * radius, Math.sin(a) * radius * Math.cos(tilt), Math.sin(a) * radius * Math.sin(tilt), rotation);
                    ctx.beginPath(); ctx.arc(point[0], point[1], 1.6 * point[2], 0, Math.PI * 2);
                    ctx.fillStyle = ring % 2 ? '#79e5d3' : '#8bb7ff';
                    ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 11; ctx.fill(); ctx.shadowBlur = 0;
                }
            }
            for (let i = 0; i < 30; i++) {
                const a = i * 2.39996 + rotation * .3;
                const r = radius * (1.1 + (i % 7) * .06);
                const x = width * .49 + Math.cos(a) * r;
                const y = height * .49 + Math.sin(a) * r * .92;
                ctx.beginPath(); ctx.arc(x, y, i % 4 ? .8 : 1.5, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(137,179,234,${.15 + (Math.sin(time * .001 + i) + 1) * .13})`; ctx.fill();
            }
        };
        const tick = time => {
            frame = requestAnimationFrame(tick);
            if (!visible || paused || document.hidden) { last = time; return; }
            if (time - last < 33) return;
            elapsed += Math.min(time - last, 66); last = time; draw(elapsed);
        };
        new ResizeObserver(resize).observe(scene);
        new IntersectionObserver(entries => { visible = entries[0].isIntersecting; }).observe(scene);
        resize(); frame = requestAnimationFrame(tick);
        window.addEventListener('pagehide', () => cancelAnimationFrame(frame), {once:true});
        scene.addEventListener('pointermove', event => {
            if (paused || event.pointerType === 'touch') return;
            const r = scene.getBoundingClientRect();
            scene.style.setProperty('--ry', `${((event.clientX-r.left)/r.width-.5)*7}deg`);
            scene.style.setProperty('--rx', `${-((event.clientY-r.top)/r.height-.5)*5}deg`);
        });
        scene.addEventListener('pointerleave', () => {scene.style.setProperty('--rx','0deg');scene.style.setProperty('--ry','0deg');});
    });
})();

// The explorer is a keyboard-accessible tab set, with no account data involved.
document.querySelectorAll('[role="tablist"]').forEach(list => {
  const tabs = [...list.querySelectorAll('[role="tab"]')];
  function select(tab) {
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute('aria-selected', String(active));
      item.tabIndex = active ? 0 : -1;
      document.getElementById(item.getAttribute('aria-controls')).hidden = !active;
    });
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); select(tabs[next]); tabs[next].focus(); }
    });
  });
});
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const reveals = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) { entry.target.classList.remove('pending'); reveals.unobserve(entry.target); }
  }), {threshold: .08});
  document.querySelectorAll('.reveal').forEach(element => { element.classList.add('pending'); reveals.observe(element); });
}
