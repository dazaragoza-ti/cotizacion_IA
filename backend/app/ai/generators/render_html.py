"""Genera un render 3D HTML interactivo determinista (estilo profesional).

A partir del GLB que produce modelo_3d.py (ya viene en convención Y-arriba,
ver modelo_3d._mesh_para_glb -- este archivo ya no necesita reorientarlo):
  - Embebido en HTML autónomo con Three.js (CDN, import map).
  - Panel lateral PROFESIONAL: tabla de medidas en metros, info del proyecto.
  - Cotas fuera del bounding box (estilo plano arquitectónico), en metros.
  - Cargas/tarimas configurable: por default OFF, botón "Llenar rack".
  - 5 vistas predefinidas + OrbitControls (rotación libre).

Notas técnicas:
  - El template usa placeholders __MAYÚSCULAS__ con `.replace()` para no
    confundirse con las llaves `{}` de JS/JSON.
  - Trimesh usa per-vertex colors sin material GLB → activamos vertexColors
    explícitamente.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>__TITULO__</title>
<style>
  :root {
    --bg: #f4f6f9;
    --panel: rgba(255, 255, 255, 0.94);
    --panel-border: rgba(28, 31, 38, 0.10);
    --accent: #c66a1a;
    --accent-soft: #e88a3a;
    --text: #1c2026;
    --muted: #6b7280;
    --green: #1e8449;
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; height:100%; overflow:hidden;
               font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
               background: var(--bg); color: var(--text); }
  canvas { display:block; }

  /* ── Panel lateral profesional (desplegable) ── */
  #panel {
    position: absolute; top:0; left:0; bottom:0;
    width: 320px;
    background: var(--panel);
    backdrop-filter: blur(8px);
    border-right: 1px solid var(--panel-border);
    padding: 22px 20px;
    overflow-y: auto;
    z-index: 10;
    transition: transform 0.25s ease-out, width 0.25s ease-out;
  }
  #panel.collapsed { transform: translateX(-100%); }
  /* Botón para abrir/cerrar el panel */
  #panel-toggle {
    position: absolute; top: 14px; left: 14px;
    width: 38px; height: 38px;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; color: var(--text);
    z-index: 11;
    transition: left 0.25s ease-out;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  #panel-toggle:hover { background: rgba(28,31,38,0.06); border-color: var(--accent-soft); }
  /* Cuando el panel está abierto, el toggle se mueve dentro del panel */
  body:not(.panel-collapsed) #panel-toggle {
    left: calc(320px - 52px);
  }
  #panel header { margin-bottom: 18px; padding-bottom: 14px;
                  border-bottom: 1px solid var(--panel-border); }
  #panel h1 { margin:0; font-size:15px; font-weight:600; color:var(--accent);
              letter-spacing:.2px; line-height:1.35; }
  #panel h1 small { display:block; font-weight:400; color:var(--muted);
                    font-size:11px; margin-top:4px; letter-spacing:.4px;
                    text-transform: uppercase; }
  #panel section { margin-bottom: 22px; }
  #panel section h2 { font-size:10px; color:var(--muted);
                      letter-spacing:1.2px; text-transform:uppercase;
                      margin:0 0 8px 0; font-weight:600; }
  .row { display:flex; justify-content:space-between; align-items:baseline;
         padding:6px 0; font-size:12.5px;
         border-bottom: 1px solid rgba(28,31,38,0.06); }
  .row:last-child { border-bottom: none; }
  .row .k { color:var(--muted); }
  .row .v { font-weight:600; color:var(--text);
            font-variant-numeric: tabular-nums; }
  .badge {
    display:inline-block; padding:3px 8px; border-radius:10px;
    background: rgba(30,132,73,0.10); color: var(--green);
    font-size:10px; font-weight:700; letter-spacing:.4px;
    text-transform:uppercase;
  }

  /* ── Controles flotantes ── */
  #controls {
    position:absolute; bottom:18px;
    left: 50%; transform: translateX(-50%);
    background: var(--panel); backdrop-filter: blur(8px);
    border: 1px solid var(--panel-border);
    padding: 10px 14px; border-radius:10px;
    display:flex; gap:6px; flex-wrap:wrap;
    max-width: calc(100vw - 360px);
    z-index: 10;
  }
  #controls .group { display:flex; gap:4px; align-items:center;
                     padding:0 8px; border-right: 1px solid var(--panel-border); }
  #controls .group:last-child { border-right:none; }
  #controls button {
    background: rgba(28,31,38,0.04); color: var(--text);
    border: 1px solid rgba(28,31,38,0.10);
    padding: 7px 12px; border-radius:6px;
    font-size:11.5px; font-weight:600; cursor:pointer;
    transition: all .15s;
  }
  #controls button:hover { background: rgba(28,31,38,0.08);
                            border-color: var(--accent-soft); }
  #controls button.active { background: var(--accent); color:#ffffff;
                             border-color: var(--accent); }
  #controls .label { font-size:10px; color:var(--muted);
                     text-transform:uppercase; letter-spacing:.6px;
                     margin-right:6px; }

  /* ── Loader ── */
  #loader {
    position:absolute; top:50%; left:calc(50% + 160px);
    transform: translate(-50%, -50%);
    color: var(--text); font-size:13px;
    background: #ffffff; border: 1px solid var(--panel-border);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    padding: 12px 22px; border-radius: 8px;
    z-index: 20;
  }
  #loader .spinner {
    display:inline-block; width:14px; height:14px;
    border: 2px solid var(--accent-soft); border-top-color: transparent;
    border-radius:50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-right: 10px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ── Responsive: en móvil el panel se vuelve pestaña arriba ── */
  @media (max-width: 760px) {
    #panel { width:100%; height: 38vh; bottom:auto; right:0;
             border-right:none; border-bottom: 1px solid var(--panel-border); }
    #controls { left:0; right:0; transform:none; bottom:8px;
                margin: 0 8px; max-width: none; justify-content:center; }
    #loader { left:50%; top:60%; }
  }
</style>
</head>
<body>

<!-- ═══════ Botón de toggle para el panel ═══════ -->
<button id="panel-toggle" onclick="togglePanel()" title="Mostrar/ocultar info">☰</button>

<!-- ═══════ Panel lateral profesional (desplegable) ═══════ -->
<div id="panel">
  <header>
    <h1>__PROYECTO__<small>__CLIENTE__</small></h1>
  </header>

  <section>
    <h2>📐 Medidas del proyecto</h2>
    __TABLA_MEDIDAS__
  </section>

  <section>
    <h2>📊 Configuración</h2>
    __TABLA_CONFIG__
  </section>

  <section>
    <h2>⚙️ Capacidad</h2>
    __TABLA_CAPACIDAD__
  </section>

  <section style="margin-top:18px;">
    <span class="badge">✅ Geometría 100% fabricable</span>
    <p style="font-size:11px; color:var(--muted); margin:10px 0 0 0; line-height:1.4;">
      Render generado desde el modelo 3D real (mismo OBJ/DAE/GLB que el despiece).
      Lo que ves es exactamente lo que se fabrica.
    </p>
  </section>
</div>

<!-- ═══════ Controles flotantes ═══════ -->
<div id="controls">
  <div class="group">
    <span class="label">Vista</span>
    <button onclick="setView('iso')" id="btn-iso">Iso</button>
    <button onclick="setView('top')">Planta</button>
    <button onclick="setView('front')">Frontal</button>
    <button onclick="setView('side')">Lateral</button>
    <button onclick="setView('interior')">Interior</button>
  </div>
  <div class="group">
    <span class="label">Capas</span>
    <button onclick="toggleCotas()" id="btn-cotas">Cotas</button>
    <button onclick="toggleCargas()" id="btn-cargas">Llenar rack</button>
  </div>
  <div class="group">
    <button onclick="resetCamera()" title="Reset cámara">↺</button>
  </div>
</div>

<div id="loader"><span class="spinner"></span>Cargando modelo 3D…</div>

<script type="importmap">
{
  "imports": {
    "three":          "https://cdn.jsdelivr.net/npm/three@0.160/build/three.module.js",
    "three/addons/":  "https://cdn.jsdelivr.net/npm/three@0.160/examples/jsm/"
  }
}
</script>

<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ═══════ Datos del proyecto (inyectados desde Python) ═══════
const GLB_B64 = "__GLB_BASE64__";
const LAYOUT  = __LAYOUT_JSON__;

// ═══════ Setup escena ═══════
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf4f6f9);
scene.fog = new THREE.Fog(0xf4f6f9, 50000, 250000);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth - 320, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.domElement.style.position = 'absolute';
renderer.domElement.style.top = '0';
renderer.domElement.style.left = '320px';
document.body.appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(
  35, (window.innerWidth - 320) / window.innerHeight, 1, 1000000
);

// ═══════ Iluminación profesional ═══════
// Estrategia: mucha luz ambiental + hemisférica para que las CARAS PLANAS de
// los postes/largueros se vean planas. Sombras suaves para no engañar la forma.
scene.add(new THREE.AmbientLight(0xffffff, 0.85));
scene.add(new THREE.HemisphereLight(0xd0e0ff, 0xc8c8c0, 0.6));
const sun = new THREE.DirectionalLight(0xffffff, 0.55);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0005;
sun.shadow.radius = 4;  // sombras MÁS SUAVES para no exagerar las aristas
scene.add(sun);
scene.add(sun.target);
// Luz de relleno desde atrás (cancela las sombras duras)
const back = new THREE.DirectionalLight(0xffffff, 0.4);
scene.add(back);
// Luz lateral (suaviza los lados del poste)
const side = new THREE.DirectionalLight(0xffffff, 0.3);
scene.add(side);

// ═══════ Piso ═══════
const pisoGeom = new THREE.PlaneGeometry(100000, 100000);
const pisoMat = new THREE.MeshStandardMaterial({
  color: 0xe6e9ee, roughness: 0.92, metalness: 0.0
});
const piso = new THREE.Mesh(pisoGeom, pisoMat);
piso.rotation.x = -Math.PI / 2;
piso.receiveShadow = true;
scene.add(piso);

// Grid sutil sobre el piso (líneas claras para fondo blanco)
const grid = new THREE.GridHelper(100000, 100, 0xb0b6bf, 0xd0d4da);
grid.material.opacity = 0.6;
grid.material.transparent = true;
scene.add(grid);

// ═══════ Grupos para cotas y cargas ═══════
const cargasGroup = new THREE.Group();
const cotasGroup = new THREE.Group();
scene.add(cargasGroup);
scene.add(cotasGroup);

// ═══════ Helpers ═══════
function base64ToArrayBuffer(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
}

function mToText(mm) {
  // Formatea milímetros a texto en metros con 2 decimales.
  return (mm / 1000).toFixed(2) + ' m';
}

// ═══════ Cargar modelo GLB ═══════
const loader = new GLTFLoader();
loader.parse(base64ToArrayBuffer(GLB_B64), '', (gltf) => {
  const model = gltf.scene;

  // El GLB ya viene en convención Y-arriba (modelo_3d.py._mesh_para_glb lo
  // rota al exportar) -- antes se compensaba aquí mismo con esta rotación,
  // pero hacerlo dos veces (fuente + aquí) dejaría el modelo mal otra vez.
  model.updateMatrixWorld(true);

  // ── Colores per-vertex (trimesh no exporta materiales GLB) ──
  // metalness bajo + roughness alto = look mate, sin reflejos brillantes que
  // hagan parecer redondas las caras planas.
  model.traverse(child => {
    if (child.isMesh) {
      child.castShadow = true;
      child.receiveShadow = true;
      if (child.material) {
        child.material.vertexColors = true;
        child.material.metalness = 0.05;
        child.material.roughness = 0.85;
        child.material.flatShading = true;  // resalta caras planas
        child.material.needsUpdate = true;
      }
    }
  });

  scene.add(model);

  // ── Calcular bbox YA con orientación correcta ──
  const bbox = new THREE.Box3().setFromObject(model);
  const center = bbox.getCenter(new THREE.Vector3());
  const size = bbox.getSize(new THREE.Vector3());
  const diag = Math.sqrt(size.x*size.x + size.y*size.y + size.z*size.z);
  window._modelBox = { bbox, center, size, diag };

  // ── Piso debajo del modelo ──
  piso.position.y = bbox.min.y - 5;
  grid.position.y = bbox.min.y - 4.5;
  // Mover grid al centro horizontal
  grid.position.x = center.x;
  grid.position.z = center.z;

  // ── Reposicionar luces según escala real del modelo ──
  sun.position.set(center.x + diag, center.y + diag * 1.2, center.z + diag * 0.6);
  sun.target.position.copy(center);
  sun.shadow.camera.left = -diag * 0.8;
  sun.shadow.camera.right = diag * 0.8;
  sun.shadow.camera.top = diag * 0.8;
  sun.shadow.camera.bottom = -diag * 0.8;
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = diag * 3;
  sun.shadow.camera.updateProjectionMatrix();
  back.position.set(center.x - diag * 0.5, center.y + diag * 0.7, center.z - diag * 0.4);
  side.position.set(center.x, center.y + diag * 0.4, center.z - diag);

  // ── Construir cotas y cargas (no se muestran por default) ──
  construirCotas(bbox, size, center);
  construirCargas(bbox, size);
  cotasGroup.visible = false;
  cargasGroup.visible = false;

  // ── Vista inicial ──
  document.getElementById('loader').style.display = 'none';
  setView('iso');

}, (err) => {
  console.error('GLB parse error:', err);
  document.getElementById('loader').innerHTML = '❌ Error cargando modelo 3D';
});

// ═══════ Cotas estilo plano arquitectónico (FUERA del bbox) ═══════
function construirCotas(bbox, size, center) {
  const matLinea = new THREE.LineBasicMaterial({ color: 0xff9933 });
  // Distancia a la que dibujamos las líneas de cota, fuera del bbox
  const off = Math.max(size.x, size.y, size.z) * 0.06;

  // ── Cota: LARGO total (eje X) — debajo del rack, frente ──
  cotaLineal(
    new THREE.Vector3(bbox.min.x, bbox.min.y - off, bbox.max.z + off),
    new THREE.Vector3(bbox.max.x, bbox.min.y - off, bbox.max.z + off),
    `Largo ${(size.x/1000).toFixed(2)} m`, 0x4caf50
  );

  // ── Cota: FONDO total (eje Z) — derecha del rack, frente ──
  cotaLineal(
    new THREE.Vector3(bbox.max.x + off, bbox.min.y - off, bbox.min.z),
    new THREE.Vector3(bbox.max.x + off, bbox.min.y - off, bbox.max.z),
    `Fondo ${(size.z/1000).toFixed(2)} m`, 0x29b6f6
  );

  // ── Cota: ALTURA total (eje Y) — izquierda del rack, atrás ──
  cotaLineal(
    new THREE.Vector3(bbox.min.x - off, bbox.min.y, bbox.min.z - off),
    new THREE.Vector3(bbox.min.x - off, bbox.max.y, bbox.min.z - off),
    `Alto ${(size.y/1000).toFixed(2)} m`, 0xff9933
  );

  // ── Cotas por nivel (alturas internas) — al lado derecho atrás ──
  if (LAYOUT.niveles && LAYOUT.niveles.length > 1) {
    const xCotas = bbox.max.x + off * 1.8;
    const zCotas = bbox.min.z - off * 0.5;
    let prev = 0;
    for (let i = 1; i < LAYOUT.niveles.length; i++) {
      const h = LAYOUT.niveles[i];
      const delta = h - prev;
      cotaLineal(
        new THREE.Vector3(xCotas, bbox.min.y + prev, zCotas),
        new THREE.Vector3(xCotas, bbox.min.y + h,    zCotas),
        `N${i} · ${(delta/1000).toFixed(2)} m`, 0xff9933
      );
      prev = h;
    }
  }
}

function cotaLineal(p1, p2, texto, color) {
  // Línea principal
  const mat = new THREE.LineBasicMaterial({ color: color });
  const geom = new THREE.BufferGeometry().setFromPoints([p1, p2]);
  cotasGroup.add(new THREE.Line(geom, mat));

  // Marcas de extremos (pequeñas líneas perpendiculares)
  const len = p1.distanceTo(p2);
  const tickSize = len * 0.02;
  // Tick en p1 y p2 (en plano XZ, vertical Y)
  function tick(p) {
    const t = new THREE.Mesh(
      new THREE.SphereGeometry(tickSize, 8, 6),
      new THREE.MeshBasicMaterial({ color: color })
    );
    t.position.copy(p);
    cotasGroup.add(t);
  }
  tick(p1); tick(p2);

  // Etiqueta de texto (sprite con canvas)
  const label = makeLabel(texto, color, len);
  const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
  label.position.copy(mid);
  cotasGroup.add(label);
}

function makeLabel(text, color, refLen) {
  const canvas = document.createElement('canvas');
  const W = 280, H = 56;  // más compacto
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');

  // Fondo blanco con borde de color (legible sobre fondo claro)
  ctx.fillStyle = 'rgba(255, 255, 255, 0.96)';
  ctx.strokeStyle = '#' + color.toString(16).padStart(6, '0');
  ctx.lineWidth = 3;
  const rad = 8;
  roundRect(ctx, 3, 3, W-6, H-6, rad);
  ctx.fill();
  ctx.stroke();

  // Texto en color (no negro)
  ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
  ctx.font = 'bold 28px -apple-system, "Segoe UI", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, W/2, H/2);

  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  // Tamaño en escena: 6% del largo de referencia, mínimo 400 mm (más chico que antes)
  const scale = Math.max(refLen * 0.06, 400);
  sprite.scale.set(scale * (W/H), scale, 1);
  return sprite;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y,     x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x,     y + h, r);
  ctx.arcTo(x,     y + h, x,     y,     r);
  ctx.arcTo(x,     y,     x + w, y,     r);
  ctx.closePath();
}

// ═══════ Cargas/tarimas (TODOS los bays, configurable por usuario) ═══════
function construirCargas(bbox, size) {
  if (!LAYOUT.niveles || LAYOUT.niveles.length <= 1) return;
  const matCarga = new THREE.MeshStandardMaterial({
    color: 0xc97a3e, opacity: 0.6, transparent: true,
    roughness: 0.85, metalness: 0.1
  });
  const fr = LAYOUT.frente_mm || 1294;
  const fo = LAYOUT.fondo_mm || 1232;
  const mx = LAYOUT.modulos_x || 1;
  const my = LAYOUT.modulos_y || 1;
  const pasillo = LAYOUT.pasillo_mm || 1200;

  // Dimensiones de tarima representativa (un poco menor que el bay)
  const sx = fr * 0.85;
  const sy = 1000;  // alto típico de tarima cargada (1 m)
  const sz = fo * 0.85;

  // X990 viene rotado: largo en X, fondo en Z, altura en Y
  // bay 0 empieza en bbox.min.x
  for (let cy = 0; cy < my; cy++) {
    for (let bx = 0; bx < mx; bx++) {
      const xCenter = bbox.min.x + (bx + 0.5) * fr;
      const zCenter = bbox.min.z + (cy * (fo + pasillo)) + fo/2;
      for (let i = 1; i < LAYOUT.niveles.length; i++) {
        const y0 = bbox.min.y + LAYOUT.niveles[i];
        const geom = new THREE.BoxGeometry(sx, sy, sz);
        const mesh = new THREE.Mesh(geom, matCarga);
        mesh.position.set(xCenter, y0 + sy/2 + 80, zCenter);
        mesh.castShadow = true;
        cargasGroup.add(mesh);
      }
    }
  }
}

// ═══════ Cámara con OrbitControls ═══════
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 500;
controls.maxDistance = 200000;

window.setView = function(v) {
  if (!window._modelBox) return;
  const { center, size, diag } = window._modelBox;

  // Distancia base que mete todo el modelo en la cámara con FOV de 35°
  const d = diag * 1.4;

  // Quitar el "active" de todos los botones de vista
  ['btn-iso'].forEach(id => {
    const b = document.getElementById(id);
    if (b) b.classList.remove('active');
  });
  document.querySelectorAll('#controls .group:first-child button')
    .forEach(b => b.classList.remove('active'));
  const btn = Array.from(document.querySelectorAll('#controls .group:first-child button'))
    .find(b => b.textContent.toLowerCase().includes(
      v === 'iso' ? 'iso' : v === 'top' ? 'planta' : v === 'front' ? 'frontal' : v === 'side' ? 'lateral' : 'interior'
    ));
  if (btn) btn.classList.add('active');

  if (v === 'iso') {
    camera.position.set(
      center.x + size.x * 0.6,
      center.y + size.y * 1.2 + size.x * 0.3,
      center.z + d * 0.7
    );
  } else if (v === 'top') {
    camera.position.set(center.x, center.y + d, center.z + 0.001);
  } else if (v === 'front') {
    camera.position.set(center.x, center.y + size.y * 0.5, center.z + d);
  } else if (v === 'side') {
    camera.position.set(center.x + d, center.y + size.y * 0.5, center.z);
  } else if (v === 'interior') {
    // Cámara dentro del rack, mirando a lo largo del pasillo
    camera.position.set(
      center.x - size.x * 0.4,
      center.y + size.y * 0.4,
      center.z + size.z * 0.6
    );
  }
  controls.target.copy(center);
  controls.update();
};

window.resetCamera = function() { setView('iso'); };

window.toggleCotas = function() {
  cotasGroup.visible = !cotasGroup.visible;
  document.getElementById('btn-cotas').classList.toggle('active', cotasGroup.visible);
};
window.toggleCargas = function() {
  cargasGroup.visible = !cargasGroup.visible;
  document.getElementById('btn-cargas').classList.toggle('active', cargasGroup.visible);
};

// ═══════ Panel desplegable ═══════
window.togglePanel = function() {
  const panel = document.getElementById('panel');
  panel.classList.toggle('collapsed');
  document.body.classList.toggle('panel-collapsed', panel.classList.contains('collapsed'));
  // Esperar a que termine la animación CSS antes de redimensionar
  setTimeout(resize, 260);
};

// ═══════ Resize + animate ═══════
function resize() {
  const panelOpen = !document.getElementById('panel').classList.contains('collapsed');
  const desktop = window.innerWidth > 760;
  const panelW = desktop && panelOpen ? 320 : 0;
  const w = window.innerWidth - panelW;
  const h = desktop ? window.innerHeight :
            (panelOpen ? window.innerHeight * 0.62 : window.innerHeight);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  renderer.domElement.style.left = panelW + 'px';
  renderer.domElement.style.top = (!desktop && panelOpen ? '38vh' : '0');
}
window.addEventListener('resize', resize);
resize();

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
</script>
</body>
</html>
"""


def _row(k: str, v: str) -> str:
    return f'<div class="row"><span class="k">{k}</span><span class="v">{v}</span></div>'


def _tabla_medidas(datos: dict) -> str:
    layout = datos.get("layout", {})
    rows = []
    if layout.get("modulos_x") and layout.get("frente_mm"):
        largo_total = layout["modulos_x"] * layout["frente_mm"]
        rows.append(_row("Largo total", f"{largo_total/1000:.2f} m"))
    if layout.get("fondo_mm"):
        rows.append(_row("Fondo", f"{layout['fondo_mm']/1000:.2f} m"))
    if layout.get("altura_total_mm"):
        rows.append(_row("Alto total", f"{layout['altura_total_mm']/1000:.2f} m"))
    if layout.get("frente_mm"):
        rows.append(_row("Frente del bay", f"{layout['frente_mm']/1000:.2f} m"))
    if layout.get("pasillo_mm"):
        rows.append(_row("Pasillo", f"{layout['pasillo_mm']/1000:.2f} m"))
    if layout.get("peralte_larguero_mm"):
        rows.append(_row("Peralte larguero", f"{layout['peralte_larguero_mm']} mm"))
    return "\n".join(rows) or '<div class="row"><span class="k">—</span></div>'


def _tabla_config(datos: dict) -> str:
    layout = datos.get("layout", {})
    rows = []
    if layout.get("tipo"):
        rows.append(_row("Tipo", layout["tipo"]))
    if layout.get("modulos_x") and layout.get("modulos_y"):
        rows.append(_row(
            "Corridas × bays",
            f'{layout["modulos_y"]} × {layout["modulos_x"]}',
        ))
        rows.append(_row(
            "Módulos totales",
            str(layout["modulos_x"] * layout["modulos_y"]),
        ))
    if layout.get("niveles"):
        rows.append(_row("Niveles de carga", str(len(layout["niveles"]) - 1)))
        # Mostrar la altura de cada nivel
        for i, h in enumerate(layout["niveles"][1:], 1):
            rows.append(_row(f"Nivel {i}", f"{h/1000:.2f} m"))
    return "\n".join(rows) or '<div class="row"><span class="k">—</span></div>'


def _tabla_capacidad(datos: dict) -> str:
    mem = datos.get("memoria", {}) or {}
    rows = []
    if mem.get("tipo_carga"):
        rows.append(_row("Tipo de carga", mem["tipo_carga"]))
    if mem.get("tarima_lxa"):
        rows.append(_row("Tarima", mem["tarima_lxa"]))
    if mem.get("peso_tarima_kg") is not None:
        rows.append(_row("Peso tarima", f"{mem['peso_tarima_kg']:,} kg"))
    if mem.get("tarimas_nivel") is not None:
        rows.append(_row("Tarimas / nivel", str(mem["tarimas_nivel"])))
    if mem.get("carga_modulo_kg") is not None:
        rows.append(_row("Carga / módulo", f"{mem['carga_modulo_kg']:,} kg"))
    if mem.get("cap_marco_kg") is not None:
        rows.append(_row("Capacidad marco", f"{mem['cap_marco_kg']} kg"))
    fs = mem.get("factor_seguridad")
    if fs is not None:
        rows.append(_row("Factor seguridad", str(fs)))
    return "\n".join(rows) or '<div class="row"><span class="k">—</span></div>'


def generar_html(datos: dict, glb_path: Path, out_path: Path) -> Path:
    """Toma un GLB ya generado por modelo_3d.py y lo embebe en HTML interactivo."""
    glb_b64 = base64.b64encode(Path(glb_path).read_bytes()).decode("ascii")
    layout = datos.get("layout", {})

    html = (HTML_TEMPLATE
            .replace("__TITULO__", datos.get("proyecto", "Proyecto PM"))
            .replace("__PROYECTO__", datos.get("proyecto", "Proyecto PM"))
            .replace("__CLIENTE__", datos.get("cliente", ""))
            .replace("__TABLA_MEDIDAS__", _tabla_medidas(datos))
            .replace("__TABLA_CONFIG__", _tabla_config(datos))
            .replace("__TABLA_CAPACIDAD__", _tabla_capacidad(datos))
            .replace("__GLB_BASE64__", glb_b64)
            .replace("__LAYOUT_JSON__", json.dumps(layout, ensure_ascii=False)))

    out_path = Path(out_path)
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python render_html.py datos.json modelo.glb salida.html")
        sys.exit(1)
    datos = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = generar_html(datos, Path(sys.argv[2]), Path(sys.argv[3]))
    print(f"HTML: {out} ({out.stat().st_size//1024} KB)")
