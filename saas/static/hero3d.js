// Ana sayfadaki 3D sahne: süzülen telefonlar ve şekiller. WebGL yoksa CSS telefonlar kalır.
(function () {
  const host = document.getElementById('hero3d');
  if (!host || !window.THREE) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch (e) { return; }
  document.documentElement.classList.add('has-3d');
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  camera.position.set(0, 0, 14);

  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(4, 6, 8); scene.add(key);
  const pink = new THREE.PointLight(0xff5c8a, 40, 30); pink.position.set(-6, 2, 5); scene.add(pink);
  const amber = new THREE.PointLight(0xffb35c, 40, 30); amber.position.set(6, -3, 5); scene.add(amber);

  function roundedRect(w, h, r) {
    const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    return s;
  }

  function screenTexture(emoji, title, tags, c1, c2) {
    const cv = document.createElement('canvas'); cv.width = 360; cv.height = 640;
    const g = cv.getContext('2d');
    const grd = g.createLinearGradient(0, 0, 360, 640); grd.addColorStop(0, c1); grd.addColorStop(1, c2);
    g.fillStyle = grd; g.fillRect(0, 0, 360, 640);
    g.font = '150px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif';
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(emoji, 180, 250);
    g.fillStyle = 'rgba(0,0,0,.35)'; g.fillRect(0, 470, 360, 170);
    g.fillStyle = '#fff'; g.font = 'bold 28px Inter, sans-serif'; g.textAlign = 'left';
    title.split('\n').forEach((line, i) => g.fillText(line, 22, 515 + i * 34));
    g.fillStyle = 'rgba(255,255,255,.7)'; g.font = '22px Inter, sans-serif'; g.fillText(tags, 22, 610);
    // sağdaki ikonlar
    g.fillStyle = 'rgba(255,255,255,.85)';
    [300, 360, 420].forEach(y => { g.beginPath(); g.arc(325, y, 16, 0, Math.PI * 2); g.fill(); });
    const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
    return t;
  }

  const body = new THREE.ExtrudeGeometry(roundedRect(2.4, 4.6, 0.38), { depth: 0.22, bevelEnabled: true,
    bevelThickness: 0.06, bevelSize: 0.06, bevelSegments: 4, curveSegments: 16 });
  body.center();
  const screenGeo = new THREE.ShapeGeometry(roundedRect(2.2, 4.4, 0.3), 16);
  // ShapeGeometry UV'lerini 0..1 aralığına getir
  const pos = screenGeo.attributes.position, uv = screenGeo.attributes.uv;
  for (let i = 0; i < pos.count; i++) uv.setXY(i, (pos.getX(i) + 1.1) / 2.2, (pos.getY(i) + 2.2) / 4.4);

  const phonesData = [
    ['🍊', 'Portakal markette\nolay çıkardı 😭', '#komik #shorts', '#ff7a59', '#7a2b5c', -2.9, -0.2, 0.35],
    ['🦖', 'Dinozor metrobüse\nbindi 💀', '#viral #reels', '#5c7cff', '#2a1a5e', 0, 0.55, 0],
    ['👵', 'Babaanne yapay\nzekâyı trolledi 😂', '#tiktok #ai', '#ff5c8a', '#3b1d5c', 2.9, -0.3, -0.35],
  ];
  const phones = phonesData.map(([e, t, tags, c1, c2, x, y, ry], i) => {
    const grp = new THREE.Group();
    const m = new THREE.Mesh(body, new THREE.MeshPhysicalMaterial({ color: 0x15151f, metalness: 0.6, roughness: 0.25,
      clearcoat: 1, clearcoatRoughness: 0.15 }));
    const scr = new THREE.Mesh(screenGeo, new THREE.MeshBasicMaterial({ map: screenTexture(e, t, tags, c1, c2) }));
    scr.position.z = 0.18;
    grp.add(m, scr);
    grp.position.set(x, y, i === 1 ? 0.6 : 0);
    grp.rotation.y = ry; grp.userData = { baseY: y, phase: i * 1.7, ry };
    scene.add(grp);
    return grp;
  });

  // Süs şekilleri
  const shapes = [];
  const mats = [0xff5c8a, 0xffb35c, 0x8a7dff].map(c => new THREE.MeshStandardMaterial({ color: c, metalness: 0.3,
    roughness: 0.35, emissive: c, emissiveIntensity: 0.15 }));
  [[new THREE.TorusGeometry(0.45, 0.17, 24, 48), -5.4, 2.1], [new THREE.IcosahedronGeometry(0.5, 0), 5.3, 2.2],
   [new THREE.OctahedronGeometry(0.42, 0), -4.9, -2.3], [new THREE.SphereGeometry(0.32, 32, 16), 5.1, -2.0],
   [new THREE.TorusKnotGeometry(0.3, 0.1, 80, 12), 1.9, 3.0]].forEach(([g, x, y], i) => {
    const m = new THREE.Mesh(g, mats[i % 3]); m.position.set(x, y, -1 - (i % 2));
    m.userData = { baseY: y, phase: i }; scene.add(m); shapes.push(m);
  });

  let mx = 0, my = 0, tx = 0, ty = 0;
  addEventListener('pointermove', e => { tx = (e.clientX / innerWidth - 0.5) * 2; ty = (e.clientY / innerHeight - 0.5) * 2; });

  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    renderer.setSize(w, h, false); camera.aspect = w / h;
    camera.position.z = 12.5 * Math.max(1, 1.2 / camera.aspect); camera.updateProjectionMatrix();
  }
  addEventListener('resize', resize); resize();

  let visible = true;
  new IntersectionObserver(([en]) => { visible = en.isIntersecting; }).observe(host);
  const clock = new THREE.Clock();
  (function frame() {
    requestAnimationFrame(frame);
    if (!visible) return;
    const t = reduce ? 0 : clock.getElapsedTime();
    mx += (tx - mx) * 0.05; my += (ty - my) * 0.05;
    phones.forEach(p => {
      const d = p.userData;
      p.position.y = d.baseY + Math.sin(t * 0.9 + d.phase) * 0.18;
      p.rotation.y = d.ry + Math.sin(t * 0.5 + d.phase) * 0.12 + mx * 0.25;
      p.rotation.x = Math.sin(t * 0.6 + d.phase) * 0.05 + my * 0.12;
    });
    shapes.forEach(s => { s.rotation.x = t * 0.6 + s.userData.phase; s.rotation.y = t * 0.8;
      s.position.y = s.userData.baseY + Math.sin(t + s.userData.phase) * 0.25; });
    camera.position.x = mx * 0.6; camera.position.y = -my * 0.4; camera.lookAt(0, 0.2, 0);
    renderer.render(scene, camera);
  })();
})();
