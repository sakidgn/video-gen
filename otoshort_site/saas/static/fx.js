// Arayüz etkileşimleri: menü, kaydırınca belirme, 3D eğilme, yazma animasyonu, canlı önizleme, kopyala.
(function () {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = matchMedia('(pointer: fine)').matches;
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // Üst menü: kaydırınca cam arka plan
  const nav = $('#nav');
  if (nav) { const f = () => nav.classList.toggle('scrolled', scrollY > 8); f(); addEventListener('scroll', f, { passive: true }); }

  // Mobil menü (yaylı açılış, arka plan bulanıklığı, Esc ve dışarı tıklayınca kapanır)
  const burger = $('[data-burger]'), mm = $('[data-mobile-menu]'), scrim = $('[data-menu-scrim]');
  if (burger && mm) {
    const setMenu = open => {
      mm.classList.toggle('open', open); scrim && scrim.classList.toggle('open', open);
      burger.setAttribute('aria-expanded', open); mm.setAttribute('aria-hidden', !open);
      document.body.classList.toggle('menu-open', open); if (open) nav.classList.add('scrolled');
      if (navigator.vibrate && open) try { navigator.vibrate(8); } catch (e) {}
    };
    burger.addEventListener('click', () => setMenu(!mm.classList.contains('open')));
    scrim && scrim.addEventListener('click', () => setMenu(false));
    addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });
    $$('a', mm).forEach(a => a.addEventListener('click', () => setMenu(false)));
  }

  // Kaydırınca belirme
  const io = !reduce && 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }), { threshold: .12, rootMargin: '0px 0px -40px 0px' }) : null;
  $$('.reveal').forEach(el => { el.style.transitionDelay = `${(+el.dataset.delay || 0) * 90}ms`; io ? io.observe(el) : el.classList.add('in'); });

  // 3D eğilme + ışık
  if (!reduce && fine) $$('[data-tilt]').forEach(el => {
    const max = parseFloat(el.dataset.tilt) || 6; let raf;
    el.addEventListener('pointermove', e => {
      cancelAnimationFrame(raf); raf = requestAnimationFrame(() => {
        const r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        el.style.transform = `perspective(1000px) rotateX(${(.5 - y) * max}deg) rotateY(${(x - .5) * max}deg)`;
        el.style.setProperty('--mx', x * 100 + '%'); el.style.setProperty('--my', y * 100 + '%');
      });
    });
    el.addEventListener('pointerleave', () => { cancelAnimationFrame(raf); el.style.transform = ''; });
  });

  // Hero yüzen kartları: fareyle hafif paralaks
  const chips = $$('.float-chip[data-depth]');
  if (chips.length && !reduce && fine) addEventListener('pointermove', e => {
    const x = e.clientX / innerWidth - .5, y = e.clientY / innerHeight - .5;
    chips.forEach(c => { const d = +c.dataset.depth; c.style.translate = `${-x * d}px ${-y * d}px`; });
  }, { passive: true });

  // Sayı animasyonu
  $$('[data-count]').forEach(el => {
    const end = parseInt(el.dataset.count, 10) || 0; if (reduce || end < 2) { el.textContent = end; return; }
    const t0 = performance.now(), dur = 1100;
    (function step(t) { const k = Math.min(1, (t - t0) / dur), v = 1 - Math.pow(1 - k, 4); el.textContent = Math.round(end * v).toLocaleString('tr-TR');
      if (k < 1) requestAnimationFrame(step); })(t0);
  });

  // Yazma animasyonu (ana sayfa maketi)
  $$('[data-type]').forEach(el => {
    let list; try { list = JSON.parse(el.dataset.type); } catch (e) { return; }
    if (reduce) { el.textContent = list[0]; return; }
    let i = 0, n = 0, del = false;
    (function tick() {
      const s = list[i]; n += del ? -1 : 1; el.textContent = s.slice(0, n);
      let wait = del ? 18 : 42 + Math.random() * 40;
      if (!del && n >= s.length) { del = true; wait = 1900; }
      else if (del && n <= 0) { del = false; i = (i + 1) % list.length; wait = 350; }
      setTimeout(tick, wait);
    })();
  });
  $$('[data-ticker]').forEach(el => { if (reduce) return; let v = 12;
    setInterval(() => { v = v >= 99 ? 8 : v + 1 + Math.floor(Math.random() * 3); el.textContent = Math.min(v, 99) + '%'; }, 140); });

  // Form gönderilirken buton yükleniyor
  $$('form').forEach(f => f.addEventListener('submit', () => {
    const b = f.querySelector('button[type=submit]'); if (b && f.checkValidity()) b.classList.add('is-loading');
  }));

  // Kopyala butonları
  $$('[data-copy]').forEach(b => b.addEventListener('click', async () => {
    const src = document.getElementById(b.dataset.copy); if (!src) return;
    try { await navigator.clipboard.writeText(src.innerText.trim()); } catch (e) { return; }
    const old = b.innerHTML; b.classList.add('done'); if (b.dataset.label) b.innerHTML = b.dataset.label;
    setTimeout(() => { b.classList.remove('done'); b.innerHTML = old; }, 1600);
  }));

  // Stüdyo: canlı önizleme ve özet
  const studio = $('[data-studio]');
  if (studio) {
    const bal = +studio.dataset.balance;
    const upd = () => {
      const st = $('input[name=style]:checked', studio), lg = $('input[name=language]:checked', studio), q = $('input[name=quality]:checked', studio);
      const sw = $('#pv-swatch'); if (sw && st) sw.className = 'swatch sw-' + st.value;
      const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
      if (st) set('#pv-style', st.dataset.label);
      if (lg) { set('#pv-lang', lg.dataset.label); set('#pv-code', lg.value.toUpperCase()); }
      if (q) { const c = +q.dataset.credits; set('#pv-quality', q.dataset.label); set('#pv-cost', c);
        const left = $('#pv-left'); if (left) { left.textContent = bal - c; left.style.color = bal - c < 0 ? 'var(--err)' : ''; }
        const go = $('#pv-go'); if (go) go.disabled = false; }
      const per = $('#pv-per'), times = $('input[name=times]', studio);
      if (per && times && q) { const n = times.value.split(/[\s,]+/).filter(x => /^\d{1,2}:\d{2}$/.test(x)).length;
        per.textContent = `${n} video × ${q.dataset.credits} = ${n * q.dataset.credits} kredi / gün`; }
    };
    studio.addEventListener('change', upd); studio.addEventListener('input', upd); upd();
    // Fikir önerileri
    $$('[data-idea]', studio).forEach(b => b.addEventListener('click', () => { const ta = $('textarea[name=idea],textarea[name=topic]', studio);
      if (ta) { ta.value = b.dataset.idea; ta.focus(); upd(); } }));
    // Saat çipleri
    const timesIn = $('input[name=times]', studio);
    if (timesIn) {
      const sync = () => { const cur = timesIn.value.split(/[\s,]+/).filter(Boolean); $$('[data-time]', studio).forEach(b => b.classList.toggle('on', cur.includes(b.dataset.time))); };
      $$('[data-time]', studio).forEach(b => b.addEventListener('click', () => {
        let cur = timesIn.value.split(/[\s,]+/).filter(Boolean); const t = b.dataset.time;
        cur = cur.includes(t) ? cur.filter(x => x !== t) : [...cur, t];
        cur.sort((a, c) => a.localeCompare(c, undefined, { numeric: true })); timesIn.value = cur.join(' '); sync(); upd();
      }));
      timesIn.addEventListener('input', sync); sync();
    }
  }
})();
