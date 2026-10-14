// Ana sayfa 3D sahnesi: ekranlarında canlı (çizimle üretilen) kısa videolar oynayan üç telefon.
// WebGL yoksa CSS telefonlar görünür kalır.
(function () {
  const host = document.getElementById('hero3d');
  if (!host || !window.THREE) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' }); }
  catch (e) { return; }
  if (!renderer.getContext()) return;
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  host.appendChild(renderer.domElement);
  document.documentElement.classList.add('has-3d');

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);

  // --- Yansımalar için yumuşak stüdyo ortamı ---
  (function studio() {
    const env = new THREE.Scene();
    env.add(new THREE.Mesh(new THREE.SphereGeometry(20, 32, 16),
      new THREE.MeshBasicMaterial({ color: 0x0b0b10, side: THREE.BackSide })));
    const panel = (color, w, h, x, y, z, ry) => {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
      m.position.set(x, y, z); m.lookAt(0, 0, 0); if (ry) m.rotation.z = ry; env.add(m);
    };
    panel(0xffffff, 10, 3, 0, 9, 6);
    panel(0xff2bd6, 6, 8, -10, 2, 4);
    panel(0x00e5ff, 6, 8, 10, -1, 4);
    panel(0x8a7dff, 8, 4, 0, -8, -6);
    const pm = new THREE.PMREMGenerator(renderer);
    scene.environment = pm.fromScene(env, 0.035).texture;
  })();

  scene.add(new THREE.AmbientLight(0xffffff, 0.25));
  const key = new THREE.DirectionalLight(0xffffff, 1.2); key.position.set(3, 6, 8); scene.add(key);

  // --- Telefon gövdesi ---
  function rr(w, h, r) {
    const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    return s;
  }
  const W = 2.5, H = 5.25;
  const bodyGeo = new THREE.ExtrudeGeometry(rr(W, H, 0.42), { depth: 0.2, bevelEnabled: true, bevelThickness: 0.07,
    bevelSize: 0.07, bevelSegments: 6, curveSegments: 24 });
  bodyGeo.center();
  const scrGeo = new THREE.ShapeGeometry(rr(W - 0.16, H - 0.16, 0.36), 24);
  { const p = scrGeo.attributes.position, uv = scrGeo.attributes.uv;
    for (let i = 0; i < p.count; i++) uv.setXY(i, (p.getX(i) + (W - 0.16) / 2) / (W - 0.16), (p.getY(i) + (H - 0.16) / 2) / (H - 0.16)); }
  const bodyMat = new THREE.MeshPhysicalMaterial({ color: 0x170d26, metalness: 0.85, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.12, envMapIntensity: 1.4 });

  // --- Ekran içerikleri (canvas ile çizilen sahneler) ---
  const CW = 360, CH = 756;
  const FONT = '"Plus Jakarta Sans", system-ui, sans-serif';
  function heart(g, x, y, s) {
    g.beginPath(); g.moveTo(x, y + s * .3);
    g.bezierCurveTo(x, y, x - s * .5, y, x - s * .5, y + s * .3); g.bezierCurveTo(x - s * .5, y + s * .6, x, y + s * .8, x, y + s);
    g.bezierCurveTo(x, y + s * .8, x + s * .5, y + s * .6, x + s * .5, y + s * .3); g.bezierCurveTo(x + s * .5, y, x, y, x, y + s * .3); g.fill();
  }
  function eyes(g, x, y, gap, r, look, blink) {
    [-1, 1].forEach(sd => {
      g.fillStyle = '#fff'; g.beginPath(); g.ellipse(x + sd * gap, y, r, r * (blink ? .12 : 1.12), 0, 0, 7); g.fill();
      if (!blink) { g.fillStyle = '#1b1b24'; g.beginPath(); g.arc(x + sd * gap + look * r * .35, y + r * .15, r * .55, 0, 7); g.fill();
        g.fillStyle = '#fff'; g.beginPath(); g.arc(x + sd * gap + look * r * .35 + r * .2, y - r * .1, r * .18, 0, 7); g.fill(); }
    });
  }
  function mouth(g, x, y, w, open) {
    g.fillStyle = '#4a1420'; g.beginPath(); g.ellipse(x, y, w, Math.max(2, w * .55 * open), 0, 0, Math.PI); g.fill();
    if (open > .3) { g.fillStyle = '#ff7a8a'; g.beginPath(); g.ellipse(x, y + w * .35 * open, w * .5, w * .18 * open, 0, 0, 7); g.fill(); }
  }
  function blush(g, x, y, gap) { g.fillStyle = 'rgba(255,110,140,.45)'; [-1, 1].forEach(s => { g.beginPath(); g.ellipse(x + s * gap, y, 14, 8, 0, 0, 7); g.fill(); }); }
  function ui(g, handle, cap, likes, t) {
    const grd = g.createLinearGradient(0, CH * .55, 0, CH); grd.addColorStop(0, 'rgba(0,0,0,0)'); grd.addColorStop(1, 'rgba(0,0,0,.55)');
    g.fillStyle = grd; g.fillRect(0, CH * .55, CW, CH * .45);
    g.fillStyle = '#000'; g.beginPath(); g.roundRect(CW / 2 - 44, 16, 88, 26, 13); g.fill(); // dinamik ada
    const ax = CW - 34;
    g.fillStyle = 'rgba(255,255,255,.95)'; heart(g, ax, CH - 300, 34);
    g.font = `600 15px ${FONT}`; g.textAlign = 'center'; g.fillText(likes, ax, CH - 248);
    g.beginPath(); g.roundRect(ax - 17, CH - 222, 34, 28, 10); g.fill(); g.beginPath(); g.moveTo(ax - 8, CH - 196); g.lineTo(ax - 14, CH - 184); g.lineTo(ax + 2, CH - 196); g.fill();
    g.fillText('1,2B', ax, CH - 160);
    g.beginPath(); g.moveTo(ax - 16, CH - 122); g.lineTo(ax + 16, CH - 136); g.lineTo(ax + 8, CH - 104); g.closePath(); g.fill();
    g.save(); g.translate(ax, CH - 58); g.rotate(t * 1.5); g.fillStyle = '#222'; g.beginPath(); g.arc(0, 0, 18, 0, 7); g.fill();
    g.fillStyle = '#ff7d6c'; g.beginPath(); g.arc(0, 0, 7, 0, 7); g.fill(); g.restore();
    g.textAlign = 'left'; g.fillStyle = '#fff'; g.font = `600 19px ${FONT}`; g.fillText(handle, 20, CH - 98);
    g.font = `400 16px ${FONT}`; g.fillStyle = 'rgba(255,255,255,.9)'; g.fillText(cap, 20, CH - 72);
    g.fillStyle = 'rgba(255,255,255,.25)'; g.fillRect(0, CH - 6, CW, 6);
    g.fillStyle = '#fff'; g.fillRect(0, CH - 6, CW * ((t * .12) % 1), 6);
  }

  const scenes = [
    { // Market: konuşan portakal
      handle: '@komikmeyveler', cap: 'Son indirim benim! 🍊', likes: '48B',
      draw(g, t) {
        const bg = g.createLinearGradient(0, 0, 0, CH); bg.addColorStop(0, '#9fe3d8'); bg.addColorStop(1, '#4fb3ad'); g.fillStyle = bg; g.fillRect(0, 0, CW, CH);
        const cols = ['#ff8a7a', '#ffd166', '#7aa7ff', '#ffffff', '#b28dff', '#6fdc8c'];
        for (let r = 0; r < 3; r++) { const y = 120 + r * 120; g.fillStyle = 'rgba(255,255,255,.55)'; g.fillRect(0, y + 70, CW, 10);
          for (let i = 0; i < 7; i++) { g.fillStyle = cols[(i + r * 2) % 6]; g.beginPath(); g.roundRect(14 + i * 50, y + 14, 38, 56, 6); g.fill();
            g.fillStyle = 'rgba(255,255,255,.5)'; g.fillRect(20 + i * 50, y + 30, 26, 8); } }
        g.fillStyle = '#e9e1d0'; g.fillRect(0, 480, CW, CH - 480);
        const by = 470 + Math.abs(Math.sin(t * 3)) * -26, sq = 1 + Math.sin(t * 6) * .03;
        g.fillStyle = 'rgba(0,0,0,.18)'; g.beginPath(); g.ellipse(180, 560, 70, 14, 0, 0, 7); g.fill();
        g.save(); g.translate(180, by); g.scale(1 / sq, sq);
        const og = g.createRadialGradient(-30, -30, 10, 0, 0, 90); og.addColorStop(0, '#ffb347'); og.addColorStop(1, '#f07818');
        g.fillStyle = og; g.beginPath(); g.arc(0, 0, 82, 0, 7); g.fill();
        g.fillStyle = '#3fa34d'; g.beginPath(); g.ellipse(18, -86, 24, 10, -.5, 0, 7); g.fill();
        g.strokeStyle = '#3a2a1a'; g.lineWidth = 7; g.lineCap = 'round';
        g.beginPath(); g.moveTo(-46, -36); g.lineTo(-14, -26); g.moveTo(46, -36); g.lineTo(14, -26); g.stroke();
        eyes(g, 0, -6, 30, 17, Math.sin(t * 1.3), (t % 3.2) < .12); blush(g, 0, 26, 50);
        mouth(g, 0, 36, 22, .5 + .5 * Math.abs(Math.sin(t * 9))); g.restore();
      } },
    { // Gece şehir: metrobüsteki dinozor
      handle: '@dinozorgunlugu', cap: 'İlk metrobüs deneyimim 🦖', likes: '126B',
      draw(g, t) {
        const bg = g.createLinearGradient(0, 0, 0, CH); bg.addColorStop(0, '#2a1f6e'); bg.addColorStop(.6, '#7a4fd6'); bg.addColorStop(1, '#ff8fb1'); g.fillStyle = bg; g.fillRect(0, 0, CW, CH);
        g.fillStyle = '#fff6d6'; g.beginPath(); g.arc(270, 150, 34, 0, 7); g.fill();
        for (let L = 0; L < 2; L++) { const sp = L ? 70 : 35, base = L ? 560 : 520, col = L ? '#1c1640' : '#33296b';
          for (let i = -1; i < 7; i++) { const w = 70 + ((i * 37) % 30), x = ((i * 80 - t * sp) % 560 + 560) % 560 - 100, h = 120 + ((i * 53) % 90) + L * 40;
            g.fillStyle = col; g.fillRect(x, base - h, w, h + 300);
            g.fillStyle = L ? 'rgba(255,214,120,.8)' : 'rgba(255,214,120,.45)';
            for (let yy = base - h + 14; yy < base - 10; yy += 22) for (let xx = x + 10; xx < x + w - 10; xx += 18) if ((xx * 7 + yy) % 5 > 1) g.fillRect(xx, yy, 8, 10); } }
        g.fillStyle = 'rgba(255,255,255,.12)'; g.fillRect(0, 0, CW, 70); g.fillRect(0, 0, 18, CH); g.fillRect(CW - 18, 0, 18, CH);
        g.fillStyle = '#c9c6e8'; g.fillRect(0, 600, CW, CH - 600);
        const by = 520 + Math.sin(t * 2.4) * 8;
        g.save(); g.translate(170, by); g.rotate(Math.sin(t * 1.2) * .05);
        g.fillStyle = '#3fbf74';
        for (let i = 0; i < 5; i++) { g.beginPath(); g.moveTo(-70 + i * 26, -92 + Math.abs(i - 2) * 8); g.lineTo(-58 + i * 26, -122 + Math.abs(i - 2) * 10); g.lineTo(-46 + i * 26, -92 + Math.abs(i - 2) * 8); g.fill(); }
        const dg = g.createLinearGradient(0, -110, 0, 90); dg.addColorStop(0, '#63e08f'); dg.addColorStop(1, '#2f9e5f'); g.fillStyle = dg;
        g.beginPath(); g.roundRect(-92, -100, 184, 190, 80); g.fill();
        g.fillStyle = '#c8f5d6'; g.beginPath(); g.ellipse(0, 40, 56, 44, 0, 0, 7); g.fill();
        eyes(g, 0, -34, 34, 19, Math.sin(t * .9 + 1), (t % 4) < .12); blush(g, 0, 0, 58);
        mouth(g, 0, 6, 26, .35 + .65 * Math.abs(Math.sin(t * 7))); g.restore();
      } },
    { // Ev ofisi: toplantıdaki kedi
      handle: '@kedikonusuyor', cap: 'Toplantıya ben katıldım 😼', likes: '73B',
      draw(g, t) {
        const bg = g.createLinearGradient(0, 0, 0, CH); bg.addColorStop(0, '#ffd9e8'); bg.addColorStop(1, '#f3b4cf'); g.fillStyle = bg; g.fillRect(0, 0, CW, CH);
        g.fillStyle = 'rgba(255,255,255,.6)'; g.beginPath(); g.roundRect(30, 90, 130, 160, 10); g.fill();
        g.fillStyle = '#9fd3ff'; g.beginPath(); g.roundRect(42, 102, 106, 136, 6); g.fill();
        g.fillStyle = '#5fbf62'; g.beginPath(); g.ellipse(270, 200, 40, 60, 0, 0, 7); g.fill(); g.fillStyle = '#c86b4a'; g.fillRect(250, 240, 40, 50);
        g.fillStyle = '#8b5e3c'; g.fillRect(0, 560, CW, CH - 560);
        g.fillStyle = '#2b2b33'; g.beginPath(); g.roundRect(70, 470, 220, 120, 10); g.fill();
        g.fillStyle = '#5a7cff'; g.beginPath(); g.roundRect(82, 482, 196, 96, 6); g.fill();
        g.fillStyle = 'rgba(255,255,255,.7)'; for (let i = 0; i < 3; i++) { g.beginPath(); g.roundRect(92 + i * 64, 492, 56, 40, 4); g.fill(); }
        const hy = 380 + Math.sin(t * 2) * 5, tilt = Math.sin(t * 1.1) * .08;
        g.save(); g.translate(180, hy); g.rotate(tilt);
        g.fillStyle = '#9aa0ad';
        [-1, 1].forEach(s => { g.beginPath(); g.moveTo(s * 70, -40); g.lineTo(s * 84, -120); g.lineTo(s * 26, -78); g.fill(); });
        g.fillStyle = '#ffb3c8'; [-1, 1].forEach(s => { g.beginPath(); g.moveTo(s * 66, -56); g.lineTo(s * 76, -104); g.lineTo(s * 40, -78); g.fill(); });
        const cg = g.createRadialGradient(-20, -30, 10, 0, 0, 100); cg.addColorStop(0, '#c3c8d4'); cg.addColorStop(1, '#8c92a0');
        g.fillStyle = cg; g.beginPath(); g.ellipse(0, 0, 96, 84, 0, 0, 7); g.fill();
        g.fillStyle = '#f2f2f5'; g.beginPath(); g.ellipse(0, 34, 48, 36, 0, 0, 7); g.fill();
        eyes(g, 0, -10, 34, 18, Math.sin(t * .7) * .8, (t % 2.8) < .12);
        g.fillStyle = '#ff8fa8'; g.beginPath(); g.moveTo(-8, 16); g.lineTo(8, 16); g.lineTo(0, 25); g.fill();
        g.strokeStyle = 'rgba(60,60,70,.6)'; g.lineWidth = 2.5;
        [-1, 1].forEach(s => { for (let k = -1; k <= 1; k++) { g.beginPath(); g.moveTo(s * 40, 28 + k * 8); g.lineTo(s * 92, 22 + k * 14); g.stroke(); } });
        mouth(g, 0, 32, 12, .3 + .7 * Math.abs(Math.sin(t * 6))); g.restore();
      } },
  ];

  // Telefonların arkasındaki neon parıltı
  function glowTexture(color) {
    const cv = document.createElement('canvas'); cv.width = 512; cv.height = 1024;
    const g = cv.getContext('2d'); g.strokeStyle = color; g.shadowColor = color; g.lineWidth = 14;
    for (const blur of [80, 40, 16]) { g.shadowBlur = blur; g.beginPath(); g.roundRect(70, 70, 372, 884, 64); g.stroke(); }
    const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
  }
  const glowGeo = new THREE.PlaneGeometry(W * 1.38, H * 1.16);
  const GLOWS = ['#ff2bd6', '#00e5ff', '#b6ff3b'];

  const phones = scenes.map((sc, i) => {
    const cv = document.createElement('canvas'); cv.width = CW; cv.height = CH;
    const g = cv.getContext('2d');
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    const grp = new THREE.Group();
    grp.add(new THREE.Mesh(bodyGeo, bodyMat));
    const scr = new THREE.Mesh(scrGeo, new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
    scr.position.z = 0.172; grp.add(scr);
    const gloss = new THREE.Mesh(scrGeo, new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.06, roughness: 0.05, metalness: 0, envMapIntensity: 2 }));
    gloss.position.z = 0.176; grp.add(gloss);
    const glow = new THREE.Mesh(glowGeo, new THREE.MeshBasicMaterial({ map: glowTexture(GLOWS[i]), transparent: true,
      blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false, opacity: 0.95 }));
    glow.position.z = -0.05; grp.add(glow);
    const lay = [[-2.75, -0.15, -0.9, 0.42, 0.92], [0, 0.15, 0.3, 0, 1.06], [2.75, -0.25, -0.9, -0.42, 0.92]][i];
    grp.position.set(lay[0], lay[1], lay[2]); grp.rotation.y = lay[3]; grp.scale.setScalar(lay[4]);
    grp.userData = { base: lay, phase: i * 1.9 };
    scene.add(grp);
    return { grp, g, tex, sc, phase: i * 2.3 };
  });

  // --- Süs şekilleri ---
  const shapes = [];
  const glossy = (c) => new THREE.MeshPhysicalMaterial({ color: c, metalness: 0.15, roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.08, envMapIntensity: 1.2, emissive: c, emissiveIntensity: 0.35 });
  [[new THREE.TorusGeometry(0.42, 0.16, 32, 64), 0xff2bd6, -3.9, 2.0, -1.2],
   [new THREE.SphereGeometry(0.3, 48, 24), 0xffb800, 4.3, 2.4, -1.4],
   [new THREE.IcosahedronGeometry(0.36, 0), 0x00e5ff, 4.1, -2.4, -0.6],
   [new THREE.CapsuleGeometry ? new THREE.CapsuleGeometry(0.16, 0.42, 8, 24) : new THREE.CylinderGeometry(.16, .16, .7, 24), 0xb6ff3b, -4.0, -2.3, -0.4]]
    .forEach(([geo, c, x, y, z], i) => { const m = new THREE.Mesh(geo, glossy(c)); m.position.set(x, y, z);
      m.userData = { y, phase: i * 1.3 }; scene.add(m); shapes.push(m); });

  // --- Yumuşak gölge ---
  (function shadow() {
    const cv = document.createElement('canvas'); cv.width = cv.height = 256;
    const g = cv.getContext('2d'); const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    gr.addColorStop(0, 'rgba(0,0,0,.55)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(11, 2.2), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false }));
    m.rotation.x = -Math.PI / 2; m.position.set(0, -3.25, -0.3); scene.add(m);
  })();

  let tx = 0, ty = 0, mx = 0, my = 0;
  addEventListener('pointermove', e => { tx = (e.clientX / innerWidth - .5) * 2; ty = (e.clientY / innerHeight - .5) * 2; }, { passive: true });

  function resize() {
    const w = host.clientWidth, h = host.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h, false); camera.aspect = w / h;
    camera.position.set(0, 0.2, 15.2 * Math.max(1, 1.08 / camera.aspect)); camera.updateProjectionMatrix();
  }
  addEventListener('resize', resize); resize();

  let visible = true, last = 0;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(host);
  const clock = new THREE.Clock();
  const start = () => (function frame(now) {
    requestAnimationFrame(frame);
    if (!visible || document.hidden) return;
    const t = reduce ? 1.5 : clock.getElapsedTime();
    if (now - last > 33) { // ekranları ~30 fps çiz
      last = now;
      phones.forEach(p => { p.sc.draw(p.g, t + p.phase); ui(p.g, p.sc.handle, p.sc.cap, p.sc.likes, t + p.phase); p.tex.needsUpdate = true; });
    }
    mx += (tx - mx) * .045; my += (ty - my) * .045;
    phones.forEach(({ grp }) => { const b = grp.userData.base, ph = grp.userData.phase;
      grp.position.y = b[1] + Math.sin(t * .8 + ph) * .14;
      grp.rotation.y = b[3] + mx * .22 + Math.sin(t * .4 + ph) * .04;
      grp.rotation.x = my * .1 + Math.sin(t * .5 + ph) * .03; });
    shapes.forEach(s => { s.rotation.x = t * .5 + s.userData.phase; s.rotation.y = t * .7;
      s.position.y = s.userData.y + Math.sin(t * .9 + s.userData.phase) * .22; });
    camera.position.x = mx * .5; camera.lookAt(0, -0.1, 0);
    renderer.render(scene, camera);
  })(0);
  (document.fonts && document.fonts.load ? Promise.all([document.fonts.load(`700 19px "Plus Jakarta Sans"`), document.fonts.load(`500 16px "Plus Jakarta Sans"`)]).catch(() => {}) : Promise.resolve()).then(start);
})();
