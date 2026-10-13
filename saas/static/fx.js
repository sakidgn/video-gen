// Arayüz efektleri: 3D eğilen kartlar, kaydırınca beliren öğeler, sayı animasyonu, form yükleniyor durumu.
(function () {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = matchMedia('(pointer: fine)').matches;

  // 3D eğilme
  if (!reduce && fine) {
    document.querySelectorAll('[data-tilt]').forEach(el => {
      const max = parseFloat(el.dataset.tilt) || 8;
      el.addEventListener('pointermove', e => {
        const r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        el.style.transform = `perspective(900px) rotateX(${(0.5 - y) * max}deg) rotateY(${(x - 0.5) * max}deg) translateZ(0)`;
        el.style.setProperty('--mx', `${x * 100}%`); el.style.setProperty('--my', `${y * 100}%`);
      });
      el.addEventListener('pointerleave', () => { el.style.transform = ''; });
    });
  }

  // Kaydırınca belirme
  const io = 'IntersectionObserver' in window && !reduce ? new IntersectionObserver(es => es.forEach(en => {
    if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
  }), { threshold: 0.12 }) : null;
  document.querySelectorAll('.reveal').forEach((el, i) => {
    el.style.transitionDelay = `${(parseInt(el.dataset.delay || 0)) * 80}ms`;
    io ? io.observe(el) : el.classList.add('in');
  });

  // Sayı animasyonu
  document.querySelectorAll('[data-count]').forEach(el => {
    const end = parseInt(el.dataset.count, 10); if (reduce || !end) { el.textContent = end; return; }
    const t0 = performance.now(), dur = 900;
    (function step(t) { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = Math.round(end * e); if (k < 1) requestAnimationFrame(step); })(t0);
  });

  // Form gönderilirken buton
  document.querySelectorAll('form[data-loading]').forEach(f => f.addEventListener('submit', () => {
    const b = f.querySelector('button[type=submit],button:not([type])');
    if (b) { b.classList.add('loading'); b.dataset.label = b.textContent; b.textContent = f.dataset.loading; }
  }));

  // Seçim kartlarında canlı özet (kalite/kredi)
  const sum = document.getElementById('cost-summary');
  if (sum) {
    const upd = () => { const q = document.querySelector('input[name=quality]:checked');
      if (q) sum.textContent = `${q.dataset.credits} kredi`; };
    document.querySelectorAll('input[name=quality]').forEach(i => i.addEventListener('change', upd)); upd();
  }
})();
