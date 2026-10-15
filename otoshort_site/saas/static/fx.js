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
    if (e.isIntersecting) { const t = e.target; t.classList.add('in'); io.unobserve(t); setTimeout(() => { t.classList.add('done'); dispatchEvent(new Event('scroll')); }, 950 + (+t.dataset.delay || 0) * 90); }
  }), { threshold: .12, rootMargin: '0px 0px -40px 0px' }) : null;
  $$('.reveal').forEach(el => { el.style.transitionDelay = `${(+el.dataset.delay || 0) * 90}ms`; io ? io.observe(el) : el.classList.add('in', 'done'); });

  // Tanıtım filmi: telefonda dikey, masaüstünde yatay sürüm
  const hv = $('[data-hero-video]');
  if (hv) {
    const mq = matchMedia('(max-width: 700px), (max-aspect-ratio: 4/5)');  // telefon ya da dikey tablet
    const go = () => { const p = hv.play(); if (p) p.catch(() => {}); };
    const pick = () => {
      const mob = mq.matches; hv.poster = mob ? hv.dataset.posterM : '/static/hero/hero.jpg';
      if (reduce) return;
      const src = mob ? hv.dataset.srcM : hv.dataset.src;
      if (hv.getAttribute('src') !== src) { hv.muted = true; hv.playsInline = true; hv.src = src; go(); }
    };
    pick(); mq.addEventListener ? mq.addEventListener('change', pick) : mq.addListener(pick);
    addEventListener('touchstart', go, { once: true, passive: true });  // iOS bazen ilk dokunuşu bekler
  }

  // Başlıkları kelimelere böl: bölüm göründüğünde kelime kelime belirsin
  if (!reduce) $$('.home .sec-head h2, .home .auto-copy h2, .home .cta h2').forEach(h => {
    let i = 0; const out = document.createDocumentFragment();
    const word = node => { const w = document.createElement('span'); w.className = 'wd'; w.style.setProperty('--wi', i++); w.appendChild(node); return w; };
    [...h.childNodes].forEach(n => {
      if (n.nodeType === 3) n.textContent.split(/(\s+)/).forEach(t => { if (!t) return; out.appendChild(/^\s+$/.test(t) ? document.createTextNode(t) : word(document.createTextNode(t))); });
      else out.appendChild(n.nodeName === 'BR' ? n : word(n));
    });
    h.textContent = ''; h.appendChild(out);
  });

  // Aşağı inerken geride kalan bölümler bulanıklaşıp geri çekilir
  const outs = $$('.home main .reveal, .home main .marquee, .home [data-showcase]').filter(el => !el.parentElement.closest('.reveal'));
  const hfc = $('.hf-copy'), hfv = $('.hf-video');
  if (!reduce && (outs.length || hfc)) {
    const maxB = fine ? 6 : 4; let raf = 0;
    outs.forEach(el => el.setAttribute('data-out', ''));
    const apply = (el, p) => {
      if (p <= .002) { if (el._o) { el.style.filter = el.style.opacity = el.style.scale = ''; el._o = 0; } return; }
      const e = Math.pow(p, 1.6); el._o = 1;
      el.style.filter = `blur(${(e * maxB).toFixed(2)}px)`; el.style.opacity = (1 - e * .6).toFixed(3); el.style.scale = (1 - e * .03).toFixed(4);
    };
    const run = () => {
      raf = 0; const vh = innerHeight;
      // öğenin alt kenarı ekranın üst üçte birine girince başlar, menünün altına varınca tamamlanır
      outs.forEach(el => { if (el.classList.contains('reveal') && !el.classList.contains('done')) return;
        const r = el.getBoundingClientRect(); apply(el, Math.min(1, Math.max(0, (vh * .3 + 70 - r.bottom) / (vh * .3)))); });
      if (hfc) { const p = Math.min(1, Math.max(0, (scrollY - vh * .15) / (vh * .85))); apply(hfc, p);
        if (hfv) { hfv.style.scale = (1 + p * .05).toFixed(4); hfv.style.filter = p > .005 ? `blur(${(p * p * 7).toFixed(1)}px) brightness(${(1 - p * .4).toFixed(3)})` : ''; } }
    };
    addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(run); }, { passive: true }); addEventListener('resize', run); run();
  }

  // Masaüstünde yumuşak, ataletli kaydırma
  if (!reduce && fine) addEventListener('DOMContentLoaded', () => {
    if (!window.Lenis || !document.body.classList.contains('home')) return;
    try { new Lenis({ autoRaf: true, lerp: .09, anchors: true }); } catch (e) {}
  });

  // Ürün vitrini: kaydırdıkça 3D açıdan düzleşir
  const sc = $('[data-showcase]');
  if (sc) {
    if (reduce) sc.style.setProperty('--p', 1);
    else { let raf; const f = () => { raf = 0; const r = sc.getBoundingClientRect(), vh = innerHeight;
        const p = Math.min(1, Math.max(0, (vh - r.top) / (vh * .75))); sc.style.setProperty('--p', p.toFixed(3)); };
      f(); addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(f); }, { passive: true }); addEventListener('resize', f); }
  }

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

  // Onay isteyen formlar (satır içi script yok: güvenlik politikası buna izin vermez)
  $$('form[data-confirm]').forEach(f => f.addEventListener('submit', e => { if (!confirm(f.dataset.confirm)) { e.preventDefault(); e.stopImmediatePropagation(); } }, true));
  // Yüklenemeyen küçük resimleri gizle
  $$('img[data-hide-broken]').forEach(img => { const h = () => img.remove(); if (img.complete && !img.naturalWidth) h(); else img.addEventListener('error', h); });
  // Video üretilirken durumu yokla, aşama değişince sayfayı yenile
  const poll = $('[data-poll]');
  if (poll) setInterval(async () => {
    try { const d = await (await fetch(poll.dataset.poll)).json(); poll.textContent = d.label; if (d.stage !== poll.dataset.stage) location.reload(); } catch (e) {}
  }, 4000);

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

  // Video dosyasını paylaş (telefonda TikTok/Instagram uygulamasına doğrudan gönderir). Destek yoksa buton gizli kalır.
  const sf = $('[data-share-file]');
  if (sf && navigator.canShare) {
    let file = null;
    try { if (navigator.canShare({ files: [new File([''], 'x.mp4', { type: 'video/mp4' })] })) sf.hidden = false; } catch (e) {}
    if (!sf.hidden) {
      // dosya önceden indirilir: tarayıcı paylaşımı ancak dokunuştan hemen sonra açar
      fetch(sf.dataset.shareFile).then(r => r.blob()).then(b => { file = new File([b], sf.dataset.shareName || 'video.mp4', { type: 'video/mp4' }); }).catch(() => {});
      sf.addEventListener('click', async () => {
        if (!file) { location.href = sf.dataset.shareFile + '?indir=1'; return; }
        try { await navigator.share({ files: [file], text: sf.dataset.shareText || '' }); } catch (e) {}
      });
    }
  }

  // Paylaş butonları: telefonda yerel paylaşım menüsü, yoksa bağlantıyı kopyalar
  $$('[data-share-url]').forEach(b => b.addEventListener('click', async () => {
    const url = b.dataset.shareUrl, text = b.dataset.shareText || '';
    if (navigator.share) { try { await navigator.share({ title: document.title, text, url }); } catch (e) {} return; }
    try { await navigator.clipboard.writeText(url); const old = b.innerHTML; b.textContent = 'Bağlantı kopyalandı'; setTimeout(() => { b.innerHTML = old; }, 1600); } catch (e) {}
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
    // Fikir önerileri (yapay zekânın getirdikleri de dahil: olay yakalama kapsayıcıda)
    studio.addEventListener('click', e => { const b = e.target.closest('[data-idea]'); if (!b) return;
      const ta = $('textarea[name=idea],textarea[name=topic]', studio); if (ta) { ta.value = b.dataset.idea; ta.focus(); upd(); } });
    const aiBtn = $('[data-ai-ideas]', studio), box = $('[data-ideas]', studio);
    if (aiBtn && box) aiBtn.addEventListener('click', async () => {
      if (aiBtn.classList.contains('is-loading')) return;
      aiBtn.classList.add('is-loading');
      const fd = new FormData(); fd.append('csrf', $('input[name=csrf]', studio).value);
      const ta = $('textarea[name=idea]', studio), lg = $('input[name=language]:checked', studio);
      fd.append('topic', ta ? ta.value : ''); fd.append('language', lg ? lg.value : 'tr');
      try {
        const r = await fetch('/api/fikirler', { method: 'POST', body: fd }), d = await r.json();
        if (!r.ok) throw new Error(d.error || 'Fikir üretilemedi');
        $$('[data-idea]', box).forEach(x => x.remove());
        d.ideas.forEach((idea, i) => { const b = document.createElement('button'); b.type = 'button'; b.dataset.idea = idea;
          b.className = 'idea-new'; b.style.animationDelay = (i * 70) + 'ms'; b.textContent = idea; box.appendChild(b); });
      } catch (e) { aiBtn.dataset.err = e.message; aiBtn.title = e.message; }
      aiBtn.classList.remove('is-loading');
    });
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
