// Arayüz etkileşimleri: menü, kaydırınca belirme, 3D eğilme, yazma animasyonu, canlı önizleme, kopyala.
(function () {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = matchMedia('(pointer: fine)').matches;
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // Üst menü: kaydırınca cam arka plan
  const nav = $('#nav');
  if (nav) { const f = () => nav.classList.toggle('scrolled', scrollY > 8); f(); addEventListener('scroll', f, { passive: true }); }

  // Görünüm: Koyu | Açık | Sistem çubuğu ve renkler. Sayfa yenilenmeden değişir, seçim çereze yazılır
  // (JS yoksa bağlantı /tema/ adresine gider). Her mod için son seçilen renk tarayıcıda hatırlanır.
  const store = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; };
  document.addEventListener('click', e => {
    const a = e.target.closest('[data-theme-set]'); if (!a) return;
    e.preventDefault();
    let name = a.dataset.themeSet, mode = a.dataset.mode;
    if (a.dataset.modeSet && mode !== 'auto') {  // mod çubuğu: o modda en son seçilen renge dön
      const last = store('zaply-tema-' + mode), sw = last && $('[data-swatches="' + mode + '"] [data-theme-set="' + last + '"]');
      if (sw) name = last;
    }
    const root = document.documentElement;
    root.dataset.theme = name; root.dataset.mode = mode;
    if (mode !== 'auto') store('zaply-tema-' + mode, name);
    document.cookie = 'tema=' + name + '; path=/; max-age=31536000; samesite=lax' + (location.protocol === 'https:' ? '; secure' : '');
    $$('[data-swatches] [data-theme-set]').forEach(x => x.classList.toggle('on', x.dataset.themeSet === name));
    $$('[data-mode-set]').forEach(x => x.classList.toggle('on', x.dataset.modeSet === mode));
    $$('[data-swatches]').forEach(x => { x.hidden = x.dataset.swatches !== mode; });
    const sel = $('[data-swatches] [data-theme-set="' + name + '"]') || a;
    const meta = $('meta[name=theme-color]'); if (meta) meta.content = sel.dataset.color;
  });

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
    // veri tasarrufu açık ya da bağlantı yavaşsa film indirilmez, kapak resmi kalır
    const conn = navigator.connection || {}, slow = conn.saveData || /(^|-)2g|3g/.test(conn.effectiveType || '');
    const pick = () => {
      const mob = mq.matches; hv.poster = mob ? hv.dataset.posterM : hv.dataset.poster;
      if (reduce || slow) return;
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

  // Hero metni aşağı inerken hafifçe soluklaşır (yalnızca opaklık ve transform: bulanıklık filtresi her karede
  // yeniden çizim istediği için hızlı kaydırmada takılma yapıyordu)
  const hfc = $('.hf-copy');
  if (!reduce && hfc) {
    let raf = 0;
    const run = () => { raf = 0; const p = Math.min(1, Math.max(0, (scrollY - innerHeight * .15) / (innerHeight * .85)));
      hfc.style.opacity = p > .002 ? (1 - p * .7).toFixed(3) : ''; hfc.style.transform = p > .002 ? `translateY(${(p * -30).toFixed(1)}px)` : ''; };
    addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(run); }, { passive: true }); run();
  }

  // Sayfa içi bağlantılar (menüdeki Nasıl çalışır, Fiyatlar, SSS…): bölüme yumuşakça kayarak gider
  const navH = () => (nav ? nav.getBoundingClientRect().height : 0) + 12;
  const easeInOut = t => t < .5 ? 16 * t ** 5 : 1 - Math.pow(-2 * t + 2, 5) / 2;  // yavaş başla, hızlan, yumuşak dur
  const glideTo = el => {
    const top = el.getBoundingClientRect().top + scrollY - navH();
    if (reduce) { scrollTo(0, top); return; }
    const dist = Math.abs(top - scrollY), duration = Math.min(1.8, Math.max(.7, dist / 2600));
    const from = scrollY, t0 = performance.now();
    document.documentElement.style.scrollBehavior = 'auto';  // kendi animasyonumuz; tarayıcınınkiyle çakışmasın
    (function step(t) {
      const k = Math.min(1, (t - t0) / (duration * 1000));
      scrollTo(0, from + (top - from) * easeInOut(k));
      if (k < 1) requestAnimationFrame(step); else document.documentElement.style.scrollBehavior = '';
    })(t0);
  };
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href*="#"]');
    if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || a.target === '_blank') return;
    const url = new URL(a.href, location.href);
    if (url.pathname !== location.pathname || url.origin !== location.origin || !url.hash) return;
    const el = document.getElementById(decodeURIComponent(url.hash.slice(1)));
    if (!el) return;
    e.preventDefault();
    history.replaceState(null, '', url.hash);
    glideTo(el);
  });
  // Başka sayfadan /#fiyat gibi bir bağlantıyla gelinince bölüm başlığı menünün altında kalmasın
  if (location.hash && document.body.classList.contains('home')) {
    const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (el) addEventListener('load', () => setTimeout(() => glideTo(el), 120));
  }

  // Menüde o an bulunulan bölümün altı çizili
  const spy = $$('.nav-links a[href*="#"]').map(a => [a, document.getElementById(a.hash.slice(1))]).filter(x => x[1]);
  if (spy.length && 'IntersectionObserver' in window) {
    const vis = new Map();
    const so = new IntersectionObserver(es => {
      es.forEach(e => vis.set(e.target, e.isIntersecting ? e.intersectionRatio : 0));
      let best = null, r = 0; spy.forEach(([a, sec]) => { if ((vis.get(sec) || 0) > r) { r = vis.get(sec); best = a; } });
      spy.forEach(([a]) => a.classList.toggle('on', a === best));
    }, { threshold: [0, .15, .3, .5], rootMargin: '-30% 0px -40% 0px' });
    spy.forEach(([, sec]) => so.observe(sec));
  }

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

  // Sayı animasyonu: oturumda ilk görüşte 0'dan sayar; sonraki sayfalarda sayı doğrudan görünür,
  // değiştiyse (ör. kredi harcandı) eski değerden yenisine kısaca sayar
  const seen = (() => { try { return JSON.parse(sessionStorage.getItem('counts') || '{}'); } catch (e) { return {}; } })();
  const next = { ...seen };
  $$('[data-count]').forEach((el, i) => {
    const end = parseInt(el.dataset.count, 10) || 0, key = el.dataset.countKey || location.pathname + '#' + i;
    const from = key in seen ? seen[key] : 0; next[key] = end;
    const fmt = n => Math.round(n).toLocaleString(document.documentElement.lang === 'en' ? 'en-US' : 'tr-TR');
    if (reduce || from === end || Math.abs(end - from) < 2) { el.textContent = fmt(end); return; }
    const t0 = performance.now(), dur = key in seen ? 650 : 1100;
    (function step(t) { const k = Math.min(1, (t - t0) / dur), v = 1 - Math.pow(1 - k, 4); el.textContent = fmt(from + (end - from) * v);
      if (k < 1) requestAnimationFrame(step); })(t0);
  });
  try { sessionStorage.setItem('counts', JSON.stringify(next)); } catch (e) {}

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
  $$('form:not([data-trial]):not([data-ktool-form]):not([data-gtool-form])').forEach(f => f.addEventListener('submit', () => {  // fetch'li formlar kendi yönetir
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
    try { await navigator.clipboard.writeText(url); const old = b.innerHTML; b.textContent = b.dataset.copied || '✓'; setTimeout(() => { b.innerHTML = old; }, 1600); } catch (e) {}
  }));

  // Metin kalıpları şablondan (sayfanın dilinde) gelir: "{n} video" → fill(kalıp, {n: 3})
  const fill = (tpl, vals) => (tpl || '').replace(/\{(\w+)\}/g, (m, k) => (k in vals ? vals[k] : m));
  const locale = document.documentElement.lang === 'en' ? 'en-US' : 'tr-TR';

  // Kayıtsız deneme: zar fikir yazar, "Deneme senaryosu" yapay zekâya kısa senaryo yazdırır (video üretmez)
  const im = $('[data-idea-machine]');
  if (im) {
    const ideas = JSON.parse(im.dataset.ideas || '[]'), box = $('[data-trial-idea]', im), form = $('[data-trial]', im),
      out = $('[data-trial-out]', im), err = $('[data-trial-err]', im), btn = $('[data-trial-go]', im);
    let bag = [];
    $('[data-im-roll]', im).addEventListener('click', () => {
      if (!bag.length) bag = ideas.map((_, i) => i).sort(() => Math.random() - .5);
      const it = ideas[bag.pop()];
      box.value = it.t; box.focus();
    });
    form.addEventListener('submit', async e => {
      e.preventDefault();
      if (btn.classList.contains('is-loading')) return;
      btn.classList.add('is-loading'); err.hidden = true;
      try {
        const r = await fetch('/api/deneme-senaryo', { method: 'POST', body: new FormData(form) }), d = await r.json();
        if (!r.ok) throw new Error(d.error || '');
        const p = d.preview;
        $('[data-t-title]', out).textContent = p.title;
        $('[data-t-scene]', out).textContent = p.scene;
        const ul = $('[data-t-lines]', out); ul.innerHTML = '';
        p.lines.forEach(l => { const li = document.createElement('li'), b = document.createElement('b');
          b.textContent = l.who + ': '; li.append(b, document.createTextNode(l.text)); ul.appendChild(li); });
        $('[data-t-tags]', out).textContent = p.hashtags.map(h => '#' + h).join(' ');
        $('[data-t-start]', out).href = d.start;
        const sb = $('[data-t-sharebtn]', out), share = $('.t-share', out);
        if (share) share.hidden = !d.share;
        if (sb && d.share) { sb.dataset.shareUrl = d.share;
          const msg = encodeURIComponent(sb.dataset.shareText + ' ' + d.share);
          $('[data-t-wa]', out).href = 'https://wa.me/?text=' + msg; $('[data-t-x]', out).href = 'https://x.com/intent/post?text=' + msg; }
        const ph = $('[data-tphone]', out); if (ph) playScript(ph, p);
        out.hidden = false; out.classList.remove('im-pop'); void out.offsetWidth; out.classList.add('im-pop');
      } catch (x) { err.textContent = x.message || err.dataset.fallback || ''; err.hidden = false; }
      btn.classList.remove('is-loading');
    });
  }

  // Viral format kartları: video yalnızca ekrandayken yüklenir ve oynar (veri tasarrufu açıksa sadece kapak)
  const vfs = $$('video[data-vf]'), saveData = navigator.connection && navigator.connection.saveData;
  if (vfs.length && 'IntersectionObserver' in window && !reduce && !saveData) {
    const io = new IntersectionObserver(es => es.forEach(e => {
      const v = e.target;
      if (e.isIntersecting) { if (!v.src) v.src = v.dataset.vf; v.play().catch(() => {}); } else if (v.src) v.pause();
    }), { threshold: 0.35 });
    // akan şeritte kartlar sürekli yer değiştirir: şerit görünürken içindeki videoların hepsi oynar
    const marquee = $('[data-vf-marquee]');
    if (marquee) {
      const inMq = $$('video[data-vf]', marquee);
      new IntersectionObserver(es => es.forEach(e => inMq.forEach(v => {
        if (e.isIntersecting) { if (!v.src) v.src = v.dataset.vf; v.play().catch(() => {}); } else if (v.src) v.pause();
      })), { threshold: 0.2 }).observe(marquee);
    }
    vfs.filter(v => !v.closest('[data-vf-marquee]')).forEach(v => io.observe(v));
  }

  // Senaryo oynatıcı: telefon ekranında diyalog kelime kelime (viral altyazı gibi) akar, konuşan karakter zıplar
  function playScript(el, p) {
    clearTimeout(el._tp);
    const lines = (p.lines || []).filter(l => l.text); if (!lines.length) return;
    const title = $('[data-tp-title]', el); if (title) title.textContent = p.title || '';
    let h = 0; for (const ch of (p.title || '')) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    el.style.setProperty('--tp-h', h % 360);
    const side = {}; let k = 0; lines.forEach(l => { if (!(l.who in side)) side[l.who] = (k++) % 2; });
    const lineEl = $('[data-tp-line]', el), whoEl = $('[data-tp-who]', el), prog = $('[data-tp-prog]', el);
    const words = lines.map(l => l.text.split(/\s+/).filter(Boolean)), total = words.reduce((n, w) => n + w.length, 0);
    let li = 0, wi = 0, done = 0;
    const draw = () => {
      whoEl.textContent = lines[li].who; el.dataset.talk = side[lines[li].who];
      lineEl.textContent = '';
      words[li].forEach((w, i) => { const sp = document.createElement('span'); sp.textContent = w;
        if (reduce || i < wi) sp.className = 'done'; if (!reduce && i === wi) sp.className = 'on';
        lineEl.append(sp, ' '); });
      if (prog) prog.style.width = Math.min(100, (done / total) * 100) + '%';
    };
    const step = () => {
      if (reduce) { draw(); li = (li + 1) % lines.length; el._tp = setTimeout(step, 2600); return; }
      draw(); done++;
      if (++wi < words[li].length) { el._tp = setTimeout(step, 300 + Math.min(260, words[li][wi - 1].length * 22)); return; }
      wi = 0; li++;
      if (li >= lines.length) { li = 0; done = 0; el._tp = setTimeout(step, 1800); return; }
      el._tp = setTimeout(step, 750);
    };
    step();
  }
  $$('[data-tphone][data-preview]').forEach(el => { try { playScript(el, JSON.parse(el.dataset.preview)); } catch (e) {} });

  // Ücretsiz kanal kurucu: konudan kanal adı, açıklama, karakter, ilk 5 video ve saatler
  const kt = $('[data-ktool]');
  if (kt) {
    const form = $('[data-ktool-form]', kt), out = $('[data-ktool-out]', kt), err = $('[data-ktool-err]', kt),
      btn = $('[data-ktool-go]', kt), topic = $('[data-ktool-topic]', kt);
    $$('[data-ktool-pick]', kt).forEach(b => b.addEventListener('click', () => { topic.value = b.dataset.ktoolPick; topic.focus(); }));
    const fillList = (box, items, tag) => { box.textContent = ''; items.forEach(t => { const e = document.createElement(tag); e.textContent = t; box.appendChild(e); }); };
    form.addEventListener('submit', async e => {
      e.preventDefault();
      if (btn.classList.contains('is-loading')) return;
      btn.classList.add('is-loading'); err.hidden = true;
      try {
        const r = await fetch('/api/kanal-plani', { method: 'POST', body: new FormData(form) }), d = await r.json();
        if (!r.ok) throw new Error(d.error || '');
        const p = d.plan;
        fillList($('[data-ko-names]', out), p.names, 'span');
        $('[data-ko-bio]', out).textContent = p.bio; $('[data-ko-char]', out).textContent = p.character;
        fillList($('[data-ko-ideas]', out), p.ideas, 'li'); fillList($('[data-ko-times]', out), p.times, 'span');
        $('[data-ko-tags]', out).textContent = p.hashtags.map(h => '#' + h).join(' ');
        $('[data-ko-start]', out).href = d.start;
        out.hidden = false; out.classList.remove('im-pop'); void out.offsetWidth; out.classList.add('im-pop');
      } catch (x) { err.textContent = x.message || ''; err.hidden = false; }
      btn.classList.remove('is-loading');
    });
  }

  // Ücretsiz kanca / başlık üretici: konudan kancalar ya da başlık + açıklama + hashtag
  const gt = $('[data-gtool]');
  if (gt) {
    const form = $('[data-gtool-form]', gt), out = $('[data-gtool-out]', gt), err = $('[data-gtool-err]', gt),
      btn = $('[data-gtool-go]', gt), topic = $('[data-gtool-topic]', gt);
    $$('[data-gtool-pick]', gt).forEach(b => b.addEventListener('click', () => { topic.value = b.dataset.gtoolPick; topic.focus(); }));
    const copyBtn = (text, label) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-ghost btn-sm'; b.textContent = label;
      b.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(text); } catch (e) { return; }
        b.textContent = gt.dataset.copied; b.classList.add('done');
        setTimeout(() => { b.textContent = label; b.classList.remove('done'); }, 1600);
      });
      return b;
    };
    const row = (list, text, tag, link) => {
      const li = document.createElement('li'), t = document.createElement('span'), acts = document.createElement('span');
      t.className = 'hl-t'; t.textContent = text; acts.className = 'hl-acts';
      if (tag) { const k = document.createElement('small'); k.textContent = tag; li.appendChild(k); }
      li.appendChild(t); acts.appendChild(copyBtn(text, list.dataset.copyLabel));
      if (link) { const a = document.createElement('a'); a.className = 'btn btn-text btn-sm'; a.href = link; a.textContent = list.dataset.make + ' →'; acts.appendChild(a); }
      li.appendChild(acts); list.appendChild(li);
    };
    form.addEventListener('submit', async e => {
      e.preventDefault();
      if (btn.classList.contains('is-loading')) return;
      btn.classList.add('is-loading'); err.hidden = true;
      try {
        const r = await fetch(gt.dataset.gtool, { method: 'POST', body: new FormData(form) }), d = await r.json();
        if (!r.ok) throw new Error(d.error || '');
        const hooks = $('[data-go-hooks]', out), titles = $('[data-go-titles]', out);
        if (hooks) { hooks.textContent = ''; d.hooks.forEach(h => row(hooks, h.text, h.type, h.start)); }
        if (titles) {
          titles.textContent = ''; d.titles.forEach(t => row(titles, t));
          $('[data-go-caption]', out).textContent = d.caption;
          $('[data-go-tags]', out).textContent = d.hashtags.map(h => '#' + h).join(' ');
          $('[data-go-start]', out).href = d.start;
        }
        out.hidden = false; out.classList.remove('im-pop'); void out.offsetWidth; out.classList.add('im-pop');
      } catch (x) { err.textContent = x.message || ''; err.hidden = false; }
      btn.classList.remove('is-loading');
    });
  }

  // Telefonda sabit çağrı çubuğu: tanıtım filmi geçilince görünür, son çağrı/erken erişim bölümünde gizlenir
  const mcta = $('[data-mcta]'), heroSec = $('.hero-film');
  if (mcta && heroSec && 'IntersectionObserver' in window) {
    let pastHero = false, nearEnd = false;
    const sync = () => { const on = pastHero && !nearEnd; mcta.classList.toggle('on', on); mcta.setAttribute('aria-hidden', !on); };
    new IntersectionObserver(([e]) => { pastHero = !e.isIntersecting; sync(); }).observe(heroSec);
    const seen = new Set();
    const endObs = new IntersectionObserver(es => {
      es.forEach(e => (e.isIntersecting ? seen.add(e.target) : seen.delete(e.target)));
      nearEnd = seen.size > 0; sync();
    });
    $$('#erken, .cta, .footer').forEach(el => endObs.observe(el));
  }

  // Ana sayfa: otomatik kanal maliyet hesaplayıcı
  const calc = $('[data-calc]');
  if (calc) {
    const packs = JSON.parse(calc.dataset.packages || '[]'), big = packs[packs.length - 1];
    const fmt = n => n.toLocaleString(locale);
    const upd = () => {
      const sr = $('[data-calc-secs]', calc), secs = sr ? +sr.value : 8, base = sr ? +sr.dataset.base : 10;
      const priceOf = el => +el.value + (+el.dataset.perSec || 0) * Math.max(0, secs - base);
      $$('input[name=calc-q]', calc).forEach(el => { const c = el.closest('label').querySelector('[data-calc-price]'); if (c) c.textContent = priceOf(el); });
      if (sr) { $('[data-calc-s-out]', calc).textContent = secs; sr.style.setProperty('--v', ((secs - sr.min) / (sr.max - sr.min) * 100) + '%'); }
      const n = +$('[data-calc-range]', calc).value, q = priceOf($('input[name=calc-q]:checked', calc)), day = n * q;
      $('[data-calc-n]', calc).textContent = n; $('[data-calc-day]', calc).textContent = fmt(day);
      $('[data-calc-month]', calc).textContent = fmt(day * 30);
      const r = $('[data-calc-range]', calc); r.style.setProperty('--v', ((n - r.min) / (r.max - r.min) * 100) + '%');
      const hint = $('[data-calc-hint]', calc);
      if (big) hint.textContent = fill(hint.dataset.tpl, { tl: fmt(big[0]), cr: fmt(big[1]), days: Math.max(1, Math.floor(big[1] / day)) });
    };
    calc.addEventListener('input', upd); calc.addEventListener('change', upd); upd();
  }

  // Referans görsel: seçilince küçük önizleme
  // Kayıtlı karakter seçimi: en fazla N karakter
  $$('[data-cast]').forEach(box => {
    const max = +box.dataset.max || 3, inputs = $$('input[name=cast]', box);
    const sync = () => { const n = inputs.filter(i => i.checked).length; inputs.forEach(i => { i.disabled = !i.checked && n >= max; }); };
    inputs.forEach(i => i.addEventListener('change', sync)); sync();
  });

  $$('[data-ref-input]').forEach(inp => inp.addEventListener('change', () => {
    const f = inp.files && inp.files[0], th = inp.closest('.ref-drop').querySelector('[data-ref-thumb]');
    if (!f || !th) return;
    th.innerHTML = ''; const img = document.createElement('img'); img.alt = ''; img.src = URL.createObjectURL(f); th.appendChild(img);
  }));

  // Keşfet: karta tıklayınca video yerinde oynar (aynı anda tek video)
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-play]'); if (!b) return;
    $$('.gthumb video').forEach(v => { if (!b.contains(v)) v.pause(); });
    if (b.querySelector('video')) return;
    const v = document.createElement('video');
    Object.assign(v, { src: b.dataset.play, autoplay: true, loop: true, playsInline: true, controls: true });
    b.appendChild(v); b.classList.add('playing');
  });

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
      const fm = $('input[name=format]:checked', studio), fmt = fm ? fm.value : '';
      studio.dataset.fmt = fmt || 'video';
      const dr = $('[data-dur-range]', studio), dw = $('[data-dur]', studio);
      if (dr) { const lo = fmt ? +studio.dataset.formatMin || 15 : 4; dr.min = lo; if (+dr.value < lo) dr.value = lo; }
      const secs = dr ? +dr.value : 8;
      const cost = fmt ? +studio.dataset.formatCredits
        : q ? +q.dataset.credits + (+q.dataset.perSec || 0) * Math.max(0, secs - (dw ? +dw.dataset.base : 10)) : 0;
      if (dw) { const base = +dw.dataset.base, extra = Math.max(0, secs - base), scenes = Math.ceil(secs / 8);
        $$('[data-dur-out]').forEach(el => { el.textContent = secs; }); set('[data-dur-price]', cost);
        dr.style.setProperty('--fill', ((secs - dr.min) * 100 / (dr.max - dr.min)) + '%');
        let note = fmt ? fill(dw.dataset.tplFormat || '', { n: cost }) : extra ? fill(dw.dataset.tplExtra, { base, x: extra, p: q ? q.dataset.perSec : 0 }) : fill(dw.dataset.tplFlat, { base });
        if (scenes > 1 && !fmt) note += ' · ' + fill(dw.dataset.tplScenes, { n: scenes });
        set('[data-dur-note]', note); }
      if (q || fmt) { const c = cost; set('#pv-quality', fmt ? fm.dataset.label : q.dataset.label); set('#pv-cost', c);
        const left = $('#pv-left'); if (left) { left.textContent = bal - c; left.style.color = bal - c < 0 ? 'var(--err)' : ''; }
        const go = $('#pv-go'); if (go) go.disabled = false; }
      const per = $('#pv-per'), times = $('input[name=times]', studio);
      if (per && times && (q || fmt)) { const n = times.value.split(/[\s,]+/).filter(x => /^\d{1,2}:\d{2}$/.test(x)).length;
        per.textContent = fill(per.dataset.tpl, { n, c: cost, total: n * cost }); }
    };
    studio.addEventListener('change', upd); studio.addEventListener('input', upd); upd();
    // Korku formatı seçilince (arka planı kendisi değiştirmediyse) karanlık sis arka planı gelsin
    let bgTouched = false;
    studio.addEventListener('change', e => {
      if (e.target.name === 'background') { bgTouched = true; return; }
      if (e.target.name !== 'format' || bgTouched) return;
      const dark = $('input[name=background][value=karanlik]', studio), soft = $('input[name=background][value=parkur]', studio);
      const want = e.target.value === 'korku' ? dark : soft; if (want) want.checked = true;
    });
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
        if (!r.ok) throw new Error(d.error || aiBtn.dataset.errText || 'Error');
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
