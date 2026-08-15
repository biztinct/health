const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

const reveal = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) entry.target.classList.add('is-visible');
  });
}, { threshold: 0.12 });

document.querySelectorAll('[data-reveal]').forEach((el) => reveal.observe(el));

if (!reduced) {
  document.addEventListener('pointermove', (event) => {
    document.documentElement.style.setProperty('--mx', `${event.clientX}px`);
    document.documentElement.style.setProperty('--my', `${event.clientY}px`);
  });
}

document.querySelectorAll('[data-tilt]').forEach((card) => {
  if (reduced) return;
  card.addEventListener('pointermove', (event) => {
    const r = card.getBoundingClientRect();
    const x = (event.clientX - r.left) / r.width - .5;
    const y = (event.clientY - r.top) / r.height - .5;
    card.style.transform = `perspective(900px) rotateX(${-y * 5}deg) rotateY(${x * 6}deg) translateY(-5px)`;
  });
  card.addEventListener('pointerleave', () => card.style.transform = '');
});

document.querySelectorAll('[data-menu]').forEach((button) => {
  button.addEventListener('click', () => document.body.classList.toggle('menu-open'));
});
