#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H5 sureci: adim adim gercekci (PBR) gorseller. Plaket desen/delikleri kullanicinin tek yuz kartindan
(hardware/kicad/img/ss-bottom.png), SMD konumlari magpanel-carrier-ss.kicad_pcb'den.
Cikti: surec-1..6.png + surec.png (6'li pano) + surec-N.html (dondurulebilir).   python3 surec.py
"""
import base64
import io
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import gen_delme as g   # noqa: E402
import kule as ku      # noqa: E402
import h5              # noqa: E402

box, cyl, tube = g.box, g.cyl, g.tube
PX = 12                                     # px/mm (kaynak goruntu 1800x1200 = 150x100 mm)
BW, BH = 160.0, 100.0                       # ham plaket

# ----------------------------------------------------------------------------- plaket dokulari
SRC = os.path.join(REPO, 'hardware', 'kicad', 'img', 'ss-bottom.png')
PCB_FILE = os.path.join(REPO, 'hardware', 'kicad', 'magpanel-carrier-ss', 'magpanel-carrier-ss.kicad_pcb')


def masks():
    rgba = np.asarray(Image.open(SRC).convert('RGBA')).astype(int)
    a, alpha = rgba[..., :3], rgba[..., 3]
    tan = np.array([200, 186, 138])
    cu = (np.abs(a - tan).sum(axis=2) < 45) | (np.abs(a - [200, 192, 144]).sum(axis=2) < 30)
    hole = alpha < 128                      # delikler PNG'de saydam
    W, H = int(BW * PX), int(BH * PX)
    off = int(5 * PX)
    CU = np.zeros((H, W), bool)
    HO = np.zeros((H, W), bool)
    CU[:, off:off + a.shape[1]] = cu
    HO[:, off:off + a.shape[1]] = hole
    yy, xx = np.mgrid[0:H, 0:W]
    for px in (BW / 2 - 76, BW / 2 + 76):                                  # pim delikleri (Ø3)
        HO |= (xx - px * PX) ** 2 + (yy - BH / 2 * PX) ** 2 < (1.5 * PX) ** 2
    return CU, HO


def hole_centers(HO):
    """Basit bilesen etiketleme (4-komsu, kaba izgara uzerinde)."""
    s = 3
    m = HO[::s, ::s]
    lab = np.zeros(m.shape, int)
    cur, out = 0, []
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        cur += 1
        st, pts = [(y0, x0)], []
        lab[y0, x0] = cur
        while st:
            y, x = st.pop()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v, u = y + dy, x + dx
                if 0 <= v < m.shape[0] and 0 <= u < m.shape[1] and m[v, u] and not lab[v, u]:
                    lab[v, u] = cur
                    st.append((v, u))
        if len(pts) >= 3:
            p = np.array(pts) * s
            out.append((p[:, 1].mean() / PX - BW / 2, BH / 2 - p[:, 0].mean() / PX))   # yerel mm (x sag, y yukari)
    return out


def tex(kind, CU, HO, drilled=1.0):
    H, W = CU.shape
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 1, (H, W)).astype(np.float32)
    noise = np.asarray(Image.fromarray(((noise * 20) + 128).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) - 128
    brushed = np.repeat(rng.normal(0, 1, (H, 1)), W, axis=1) * 6
    copper = np.dstack([np.full((H, W), 196.), np.full((H, W), 118.), np.full((H, W), 74.)]) + (noise * .5 + brushed)[..., None]
    fr4 = np.dstack([np.full((H, W), 205.), np.full((H, W), 192.), np.full((H, W), 128.)]) + noise[..., None] * .4
    resist = np.dstack([np.full((H, W), 40.), np.full((H, W), 112.), np.full((H, W), 120.)]) + noise[..., None] * .3
    if kind == 'ham':
        img = copper
    elif kind == 'lak':
        img = copper * .35 + resist * .65
    elif kind == 'poz':                    # pozlama: desen disi alan UV aliyor (mor parilti)
        base = copper * .35 + resist * .65
        uv = np.dstack([np.full((H, W), 150.), np.full((H, W), 90.), np.full((H, W), 255.)])
        img = np.where(CU[..., None], base, base * .45 + uv * .55)
    elif kind == 'banyo':                  # banyodan sonra: lak yalniz desende
        img = np.where(CU[..., None], copper * .35 + resist * .65, copper)
    else:                                  # 'asindi' / 'montaj'
        img = np.where(CU[..., None], copper * 1.05, fr4)
    if drilled > 0:
        cols = np.arange(W)[None, :] < drilled * W
        hm = HO & cols
        img = np.where(hm[..., None], np.array([30., 28., 25.]), img)
        ring = np.asarray(Image.fromarray((hm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
        img = np.where((ring & ~hm)[..., None], img * .8, img)
    img = Image.fromarray(img.clip(0, 255).astype(np.uint8)).resize((W // 2, H // 2), Image.LANCZOS)
    b = io.BytesIO()
    img.save(b, 'JPEG', quality=88)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


def smd_parts():
    s = open(PCB_FILE, encoding='utf-8').read()
    out = []
    for name, layer, x, y, r, ref in re.findall(
            r'\(footprint "([^"]+)"\s*\(layer "([^"]+)"\)(?:.|\n)*?\(at ([\d.\-]+) ([\d.\-]+)(?: ([\d.\-]+))?\)(?:.|\n)*?\(property "Reference" "([^"]+)"', s):
        if layer != 'B.Cu':
            continue
        lx, ly = 125 - float(x), 100 - float(y)             # alttan gorunus (ayna) -> yerel
        rot = float(r or 0)
        if 'SMA' in name:
            w, d, h, c = 4.3, 2.6, 2.1, '#1b1b1b'
        elif '1812' in name:
            w, d, h, c = 4.5, 3.2, 1.6, '#d8c39a'
        elif name.startswith('Capacitor'):
            w, d, h, c = 2.0, 1.25, 1.0, '#b49a6a'
        elif name.startswith('LED'):
            w, d, h, c = 2.0, 1.25, 0.8, '#e8e8e0'
        else:
            w, d, h, c = 2.0, 1.25, 0.5, '#151515'
        if abs(rot) % 180 == 90:
            w, d = d, w
        out.append((lx, ly, w, d, h, c, ref))
    return out


# ----------------------------------------------------------------------------- malzeme eslemesi
MAT = {'#b8bcc4': 'metal', '#c7ccd1': 'alu', '#9aa3ad': 'alu', '#8d949c': 'frame', '#e8833a': 'plastic',
       '#d98c4a': 'plastic', '#c8a46e': 'wood', '#3d6fb6': 'motor', '#7b3fa0': 'elec', '#222': 'black',
       '#222222': 'black', '#333': 'black', '#2b2b2b': 'rubber', '#444444': 'black', '#cfe8ff': 'glass',
       '#9fd3ff': 'glass', '#e8f4ff': 'glass', '#1d2733': 'lcd', '#7a3cff': 'uv', '#b03a2e': 'heater',
       '#d5d9de': 'hotal', '#efe9d8': 'insul', '#e8e2d0': 'insul', '#c44': 'silicone', '#e5c100': 'brass',
       '#777': 'metal', '#c9a227': 'brass', '#ff9f1c': 'amber', '#555': 'hose', '#e0e0e0': 'metal',
       '#1f7a3f': 'greenpcb', '#c9ced4': 'alu', '#d0312d': 'red', '#0b0d10': 'screen', '#3a3f45': 'darkplastic',
       '#d9c49a': 'mdf', '#2a2a2a': 'black', '#5c6670': 'darkplastic'}


def mesh_entry(m, c, o, extra=None):
    e = dict(v=[round(float(x), 2) for x in m.vertices.flatten()], f=[int(i) for i in m.faces.flatten()],
             c=c, o=o, m=MAT.get(c, 'plastic'))
    if extra:
        e.update(extra)
    return e


# ----------------------------------------------------------------------------- sahneler
def machine(yc, theta, zup, uv=False, hot=None, board=None, cut=True):
    """H5 sahnesi; yc = disk merkezi y, theta = disk acisi (derece), zup = spindle yukari ofseti (mm),
    board = (doku, yer) yer: 'disk' | 'hot'."""
    P, L, lay, z = h5.H5()
    a, b = z['mov']
    ys = lay['y_s']
    d = yc - z['yc']
    out = []
    spindle_ids = []
    for i, (m, c, o) in enumerate(P):
        bb = m.bounds
        # varsayilan plaket/pimler/dayamayi gizle (yerine dokulu plaket)
        if a <= i < b and c in (ku.PCB, '#333') or (a <= i < b and c == ku.ALU and m.extents[2] < 3):
            continue
        if cut and c in ('#9aa3ad', ku.AMBER) and o < 0.5:
            continue
        if cut and c == ku.PROF and bb[0][1] < lay['Y0'] + 1 and (m.extents[2] > 100 or bb[0][2] > 50):
            continue
        m = m.copy()
        if a <= i < b:
            if c in ('#d98c4a', '#222') or (c == ku.ALU and m.extents[2] < 3):
                m.apply_translation([0, -z['yc'], 0])
                m.apply_transform(g.trimesh.transformations.rotation_matrix(math.radians(theta), [0, 0, 1]))
                m.apply_translation([0, z['yc'], 0])
            m.apply_translation([0, d, 0])
        # spindle hareketli kismi: x~0, y~ys, z>tip
        cx, cy = (bb[0][0] + bb[1][0]) / 2, (bb[0][1] + bb[1][1]) / 2
        if c in ('#e0e0e0', ku.ALU, ku.MOT, ku.PRINT) and abs(cx) < 45 and abs(cy - (ys - 6)) < 30 and 20 < bb[0][2] < 150 \
                and m.extents[2] < 120 and not (c == ku.ALU and m.extents[0] < 10 and m.extents[2] > 100):
            m.apply_translation([0, 0, zup])
        extra = None
        if c == '#d5d9de' and hot:
            extra = dict(hot=hot)
        if c == ku.UV:
            extra = dict(on=bool(uv))
        out.append(mesh_entry(m, c, o, extra))
    boards = []
    top_hp = max(m.bounds[1][2] for m, c, o in P if c == '#d5d9de')
    if board:
        t, where = board
        if where == 'disk':
            boards.append(dict(cx=0, cy=yc, z=24.0, rot=theta, tex=t))
        else:
            boards.append(dict(cx=0, cy=0, z=top_hp, rot=0, tex=t))
    return out, boards, lay, z, top_hp


def pins_fence(yc, theta):
    out = []
    for sx in (-1, 1):
        x, y = sx * 76 * math.cos(math.radians(theta)), sx * 76 * math.sin(math.radians(theta))
        out.append(mesh_entry(cyl('z', (x, yc + y), 1.5, 24, 25.5, seg=16), '#e0e0e0', 1))
    return out


def chips(x, y, z, n=60, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        r, a = abs(rng.normal(0, 7)) + 2, rng.uniform(0, 2 * math.pi)
        px, py = x + r * math.cos(a), y + r * math.sin(a)
        s = rng.uniform(.2, .6)
        out.append(box(px - s, px + s, py - s, py + s, z, z + s * .6))
    m = g.trimesh.util.concatenate(out)
    return mesh_entry(m, '#d9b27a', 1)


def comps(cx, cy, z, parts, paste=False):
    out = []
    for lx, ly, w, d, h, c, ref in parts:
        x, y = cx + lx, cy + ly
        out.append(mesh_entry(box(x - w / 2, x + w / 2, y - d / 2, y + d / 2, z, z + h), c, 1))
        for s in (-1, 1):
            if w >= d:
                ex = box(x + s * w / 2 - .25, x + s * w / 2 + .25, y - d / 2, y + d / 2, z, z + h * .9)
            else:
                ex = box(x - w / 2, x + w / 2, y + s * d / 2 - .25, y + s * d / 2 + .25, z, z + h * .9)
            out.append(mesh_entry(ex, '#d9dde2', 1))
    return out


def tanks(cx, cy, z):
    """Islak istasyon: 3 kap (banyo NaOH, asindirma CuCl2, sokme), isitici, hava tasi."""
    out, L = [], []
    liq = [('#9fc9ff', 'Banyo (NaOH 7 g/L)'), ('#2f9a5f', 'Aşındırma (kupri klorür, 45 °C)'), ('#d9e6f2', 'Sökme (aseton)')]
    for i, (col, name) in enumerate(liq):
        x = cx + (i - 1) * 165
        wall = []
        for m in (box(x - 75, x + 75, cy - 55, cy - 53, z, z + 230), box(x - 75, x + 75, cy + 53, cy + 55, z, z + 230),
                  box(x - 75, x - 73, cy - 55, cy + 55, z, z + 230), box(x + 73, x + 75, cy - 55, cy + 55, z, z + 230),
                  box(x - 75, x + 75, cy - 55, cy + 55, z, z + 2)):
            wall.append(m)
        out.append(mesh_entry(g.trimesh.util.concatenate(wall), '#f4f7fb', 0.22, dict(m='tank')))
        out.append(mesh_entry(box(x - 73, x + 73, cy - 53, cy + 53, z + 2, z + 170), col, 0.45, dict(m='liquid')))
        L.append((name, (x, cy - 55, z + 232)))
        if i == 1:
            out.append(mesh_entry(cyl('z', (x - 55, cy + 35), 9, z + 30, z + 240), '#e8f4ff', 0.6, dict(m='glass')))
            out.append(mesh_entry(cyl('z', (x - 55, cy + 35), 6, z + 40, z + 150), '#d0312d', 1))
            rng = np.random.default_rng(3)
            bub = [g.trimesh.creation.icosphere(1, rng.uniform(1, 2.5)).apply_translation(
                [x + rng.uniform(-60, 60), cy + rng.uniform(-40, 40), z + rng.uniform(10, 165)]) for _ in range(70)]
            out.append(mesh_entry(g.trimesh.util.concatenate(bub), '#ffffff', 0.5, dict(m='glass')))
            L.append(('Isıtıcı + hava kabarcığı', (x - 55, cy + 35, z + 240)))
    return out, L


VIEW = r'''<!doctype html><html><head><meta charset="utf-8"><title>surec</title>
<style>html,body{margin:0;height:100%;background:#e9e6e1;overflow:hidden;font:600 17px system-ui,sans-serif}
.lb{position:absolute;transform:translate(-50%,-150%);background:#ffffffee;border-radius:6px;padding:3px 8px;white-space:nowrap;color:#111;box-shadow:0 1px 4px #0004}
.lb:after{content:'';position:absolute;left:50%;top:100%;width:1.5px;height:16px;background:#222}
.hot{background:#c0392b;color:#fff}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script></head><body>
<script type="module">
import * as THREE from 'three';import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
const S=__S__;const sc=new THREE.Scene();sc.background=new THREE.Color('#e9e6e1');
const cam=new THREE.PerspectiveCamera(28,innerWidth/innerHeight,5,8000);cam.up.set(0,0,1);cam.position.set(...S.cam);
const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});r.setPixelRatio(devicePixelRatio);r.setSize(innerWidth,innerHeight);
r.toneMapping=THREE.ACESFilmicToneMapping;r.toneMappingExposure=1.05;r.outputColorSpace=THREE.SRGBColorSpace;
r.shadowMap.enabled=true;r.shadowMap.type=THREE.PCFSoftShadowMap;document.body.appendChild(r.domElement);
const pm=new THREE.PMREMGenerator(r);sc.environment=pm.fromScene(new RoomEnvironment(),0.04).texture;
sc.add(new THREE.HemisphereLight(0xffffff,0x8a7f72,0.35));
const sun=new THREE.DirectionalLight(0xfff4e6,2.2);sun.position.set(S.tg[0]+350,S.tg[1]-250,S.tg[2]+700);sun.target.position.set(...S.tg);
sun.castShadow=true;sun.shadow.mapSize.set(4096,4096);const sh=sun.shadow.camera;sh.left=-520;sh.right=520;sh.top=520;sh.bottom=-520;sh.near=10;sh.far=2500;
sun.shadow.bias=-0.0004;sun.shadow.radius=4;sc.add(sun);sc.add(sun.target);
const fill=new THREE.DirectionalLight(0xdfe8ff,0.6);fill.position.set(S.tg[0]-500,S.tg[1]-300,S.tg[2]+200);sc.add(fill);
const gnd=new THREE.Mesh(new THREE.PlaneGeometry(6000,6000),new THREE.MeshStandardMaterial({color:'#cfc6b8',roughness:.92}));
gnd.position.z=S.floor;gnd.receiveShadow=true;sc.add(gnd);
function mat(p){const c=new THREE.Color(p.c);const M=THREE.MeshStandardMaterial,P=THREE.MeshPhysicalMaterial;
switch(p.m){case'metal':return new M({color:'#d6dade',metalness:1,roughness:.22});
case'alu':return new M({color:'#c9ced4',metalness:.9,roughness:.35});
case'frame':return new M({color:'#6f767e',metalness:.8,roughness:.45});
case'wood':return new M({color:'#b98d5a',roughness:.75});case'mdf':return new M({color:'#c9ab7c',roughness:.85});
case'motor':return new M({color:'#c4c9cf',metalness:.75,roughness:.35});
case'elec':return new M({color:'#2c3138',roughness:.6});case'black':case'rubber':return new M({color:'#1d1f22',roughness:.7});
case'darkplastic':return new M({color:'#33383f',roughness:.55});case'screen':return new M({color:'#0a1622',roughness:.15,emissive:'#123455',emissiveIntensity:.6});
case'glass':return new P({color:c,roughness:.05,metalness:0,transmission:.85,thickness:2,transparent:true,opacity:Math.max(p.o,.25)});
case'tank':return new M({color:'#ffffff',roughness:.1,transparent:true,opacity:.12,depthWrite:false});
case'liquid':return new M({color:c,roughness:.05,metalness:0,transparent:true,opacity:.22,depthWrite:false});
case'lcd':return new M({color:'#0d1218',roughness:.2,metalness:.2});
case'uv':return p.on?new M({color:'#7a3cff',emissive:'#8a4dff',emissiveIntensity:2.2,transparent:true,opacity:.28,depthWrite:false,blending:THREE.AdditiveBlending}):new M({color:'#7a3cff',transparent:true,opacity:.04,depthWrite:false});
case'heater':return new M({color:'#7c2a22',roughness:.6});
case'hotal':return p.hot?new M({color:'#c8cdd2',metalness:.8,roughness:.4,emissive:p.hot>150?'#ff5a1a':'#ff8a3a',emissiveIntensity:p.hot>150?.55:.18}):new M({color:'#c8cdd2',metalness:.85,roughness:.38});
case'insul':return new M({color:'#ebe5d4',roughness:.95});case'silicone':return new M({color:'#b3322b',roughness:.7});
case'brass':return new M({color:'#c9a227',metalness:1,roughness:.3});case'hose':return new M({color:'#3a3d42',roughness:.5,transparent:true,opacity:.85});
case'amber':return new P({color:'#ff9f1c',transmission:.6,transparent:true,opacity:.35,roughness:.1});
case'greenpcb':return new M({color:'#1f6b3a',roughness:.5});case'red':return new M({color:'#c9241f',roughness:.4});
default:return new M({color:c,roughness:.5,transparent:p.o<1,opacity:p.o});}}
for(const p of S.meshes){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(p.v,3));g.setIndex(p.f);
g.computeVertexNormals();const mm=mat(p);const m=new THREE.Mesh(g,mm);const tr=mm.transparent;m.castShadow=!tr;m.receiveShadow=true;if(tr)m.renderOrder=2;sc.add(m);}
const TL=new THREE.TextureLoader();
for(const b of S.boards){const t=TL.load(S.tex[b.tex]);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=8;
const grp=new THREE.Group();const top=new THREE.Mesh(new THREE.PlaneGeometry(160,100),new THREE.MeshStandardMaterial({map:t,metalness:0.3,roughness:0.5,envMapIntensity:0.35}));
top.position.z=1.61;top.receiveShadow=true;grp.add(top);
const edge=new THREE.Mesh(new THREE.BoxGeometry(160,100,1.6),new THREE.MeshStandardMaterial({color:'#c9b77a',roughness:.7}));edge.position.z=.8;edge.castShadow=true;edge.receiveShadow=true;grp.add(edge);
grp.position.set(b.cx,b.cy,b.z);grp.rotation.z=b.rot*Math.PI/180;if(b.vert){grp.rotation.x=Math.PI/2;}sc.add(grp);}
for(const l of S.lights){const pl=new THREE.PointLight(l.c,l.i,l.d,2);pl.position.set(...l.p);sc.add(pl);}
const ctl=new OrbitControls(cam,r.domElement);ctl.target.set(...S.tg);ctl.update();
const els=S.labels.map(l=>{const d=document.createElement('div');d.className='lb'+(l.hot?' hot':'');d.textContent=l.t;document.body.appendChild(d);return [d,new THREE.Vector3(...l.p)];});
(function a(){requestAnimationFrame(a);r.render(sc,cam);for(const [d,v] of els){const q=v.clone().project(cam);d.style.left=((q.x+1)/2*innerWidth)+'px';d.style.top=((1-q.y)/2*innerHeight)+'px';}})();
</script></body></html>'''


def render(name, meshes, boards, texd, labels, cam, tg, lights=(), floor=-16.0):
    S = dict(meshes=meshes, boards=boards, tex=texd, labels=[dict(t=t, p=list(p), hot=h) for t, p, h in labels],
             cam=cam, tg=tg, lights=list(lights), floor=floor)
    html = os.path.join(HERE, name + '.html')
    page = VIEW.replace('__S__', json.dumps(S, separators=(',', ':'), ensure_ascii=False))
    page = page.replace("import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';",
                        "import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';")
    open(html, 'w', encoding='utf-8').write(page)
    png = os.path.join(HERE, name + '.png')
    shot(html, png)
    return png


def shot(html, png):
    """gen_delme.screenshot'in genisletilmis hali: RoomEnvironment de yerel kopyalanir, 1600x1100."""
    import functools
    import http.server
    import shutil
    import subprocess
    import tempfile
    import threading
    import urllib.request
    base = 'https://cdn.jsdelivr.net/npm/three@0.160.0/'
    tmp = tempfile.mkdtemp()
    try:
        for rel in ('build/three.module.js', 'examples/jsm/controls/OrbitControls.js',
                    'examples/jsm/environments/RoomEnvironment.js'):
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with urllib.request.urlopen(base + rel, timeout=60) as r, open(dst, 'wb') as f:
                f.write(r.read())
        open(os.path.join(tmp, 'v.html'), 'w', encoding='utf-8').write(open(html, encoding='utf-8').read().replace(base, './'))

        class Q(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Q, directory=tmp))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        chrome = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        subprocess.run([chrome, '--headless=new', '--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                        '--hide-scrollbars', '--window-size=1600,1100', '--virtual-time-budget=60000',
                        '--screenshot=' + png, 'http://127.0.0.1:%d/v.html' % srv.server_address[1]],
                       check=False, capture_output=True, timeout=600)
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    CU, HO = masks()
    holes = hole_centers(HO)
    parts = smd_parts()
    print('delik', len(holes), 'SMD', len(parts))
    lay = h5.layout()
    ys, yl = lay['y_s'], lay['y_l']
    steps = []

    # 1 ham plaket + pim delikleri
    th = -90.0
    yc = ys + 76
    T = {'t': tex('ham', CU, HO, drilled=0.0)}
    M, B, _, z, top = machine(yc, th, 0, board=('t', 'disk'))
    M += pins_fence(yc, th)[:0] + [chips(0, ys, 25.6, 40)]
    steps.append(('surec-1', '1 · Ham plaket + pim delikleri', 'Ham bakır plaket köşe dayamasına yaslanır; sabit delici iki Ø3 pim deliğini açar, sonra pimler takılır.',
                  M, B, T, [('Ham bakır plaket (160 × 100)', (60, yc, 26), False), ('Sabit delici', (0, ys, 140), False)],
                  [-330, -470, 230], [0, ys + 40, 40]))
    # 2 delme
    hx, hy = sorted(holes, key=lambda p: p[0])[int(len(holes) * .55)]
    phi = math.degrees(math.atan2(hy, hx))
    th = -90 - phi
    yc = ys + math.hypot(hx, hy)
    yc = min(max(yc, ys), yl)
    T = {'t': tex('ham', CU, HO, drilled=0.58)}
    M, B, _, z, top = machine(yc, th, 0, board=('t', 'disk'))
    M += pins_fence(yc, th) + [chips(0, ys, 25.6, 80, 2)]
    steps.append(('surec-2', '2 · Delme (R-θ)', 'Çekmece (R) ve disk (θ) her deliği sabit delicinin altına getirir; vakum talaşı emer. %d delik.' % len(holes),
                  M, B, T, [('Delinen delikler', (-40, yc - 20, 26), False), ('Vakum ağzı', (0, ys - 17, 45), False),
                            ('Disk (θ)', (90, yc + 30, 22), False)],
                  [-280, -380, 190], [0, ys + 25, 32]))
    # 3 lak + kurutma (hot plate 70 °C)
    T = {'t': tex('lak', CU, HO, drilled=1.0)}
    M, B, _, z, top = machine(ys, 0, 30, hot=70, board=('t', 'hot'), cut=False)
    can = [mesh_entry(cyl('z', (230, -60), 26, -6 + 0, 190), '#d0312d', 1), mesh_entry(cyl('z', (230, -60), 12, 190, 205), '#e8e8e8', 1)]
    M += can
    steps.append(('surec-3', '3 · Lak + kurutma', 'Delinmiş plaket temizlenir, Positiv 20 püskürtülür ve çatıdaki hot plate\'te 70 °C\'de kurutulur.',
                  M, B, T, [('Positiv 20 lak (kurutuluyor)', (40, 30, top + 2), False), ('70 °C', (-70, -40, top + 2), True),
                            ('Positiv 20 sprey', (230, -60, 206), False)],
                  [520, -640, top + 260], [20, 0, top - 30]))
    # 4 pozlama
    T = {'t': tex('poz', CU, HO, drilled=1.0)}
    M, B, _, z, top = machine(yl, 0, 30, uv=True, board=('t', 'disk'))
    M += pins_fence(yl, 0)
    lights = [dict(p=[0, yl, 60], c='#8a4dff', i=40000, d=400)]
    steps.append(('surec-4', '4 · UV pozlama', 'Plaket aynı pimlerle diske döner; çekmece en arkada, 6.6" LCD deseni 0,5 mm yukarıdan 405 nm ile pozlar.',
                  M, B, T, [('6.6" LCD + 405 nm ışık', (0, yl - 40, 80), False), ('Plaket (pozlanıyor)', (70, yl - 45, 26), False)],
                  [-470, -260, 150], [0, yl - 10, 45], lights))
    # 5 islak islem
    T = {'t': tex('banyo', CU, HO, drilled=1.0)}
    M, L5 = tanks(0, 0, 0)
    B = [dict(cx=0, cy=0, z=120, rot=0, tex='t', vert=True)]
    labels = [(t, p, False) for t, p in L5]
    steps.append(('surec-5', '5 · Banyo → aşındırma → sökme', 'Islak istasyon (makineden ayrı): lak banyosu, ısıtılmış kupri klorürde aşındırma, asetonla lak sökme.',
                  M, B, T, labels, [380, -900, 420], [0, 0, 120]))
    # 6 montaj + reflow
    T = {'t': tex('asindi', CU, HO, drilled=1.0)}
    M, B, _, z, top = machine(ys, 0, 30, hot=220, board=('t', 'hot'), cut=False)
    M += comps(0, 0, top + 1.6, parts)
    steps.append(('surec-6', '6 · Montaj + reflow', 'Aşınmış karta krem lehim ve SMD parçalar (%d adet, gerçek konumlar) konur; hot plate 220 °C\'de lehimler.' % len(parts),
                  M, B, T, [('220 °C reflow', (-70, -40, top + 2), True), ('SMD parçalar', (5, 20, top + 4), False)],
                  [330, -420, top + 170], [-5, 5, top]))

    pngs = []
    for name, title, desc, M, B, T, labels, cam, tg, *rest in steps:
        lights = rest[0] if rest else []
        png = render(name, M, B, T, labels, cam, tg, lights)
        pngs.append((png, title, desc))
        print(name)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import textwrap
    fig = plt.figure(figsize=(24, 27))
    for k, (png, title, desc) in enumerate(pngs):
        r, c = divmod(k, 2)
        ax = fig.add_axes([0.01 + c * 0.495, 0.69 - r * 0.33, 0.485, 0.262])
        ax.imshow(Image.open(png))
        ax.axis('off')
        fig.text(0.012 + c * 0.495, 0.985 - r * 0.33, title, fontsize=22, fontweight='bold', va='top')
        fig.text(0.012 + c * 0.495, 0.972 - r * 0.33, '\n'.join(textwrap.wrap(desc, 100)), fontsize=14, va='top')
    fig.savefig(os.path.join(HERE, 'surec.png'), dpi=70)
    print('->', os.path.join(HERE, 'surec.png'))


if __name__ == '__main__':
    main()
