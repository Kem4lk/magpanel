#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Butunlesik PCB makinesi: pozlama (UV LED + sogutucu/fan + Fresnel + 6.6" mono LCD) + delme + hot plate,
4 yerlesim eskizi. Olculer modelden hesaplanir; isik motoru yuksekligi Fresnel odak uzakligina (F) baglidir.
Cikti: entegre.png (2x2, etiketli) + her konsept icin 3B html.   python3 entegre.py
"""
import json
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import gen_delme as g  # noqa: E402
import konsept as k   # noqa: E402

box, cyl, union = g.box, g.cyl, g.union
F = 120.0            # Fresnel odak uzakligi (varsayim; secilen mercege gore degisir)
UV, FRES, LCD, GLASS, HP, ALU, DARK, AMBER, SHELL = ('#7a3cff', '#9fd3ff', '#1d2733', '#cfe8ff', '#b03a2e', '#c7ccd1',
                                                     '#444444', '#ff9f1c', '#9aa3ad')


def add(P, m, c, o=1.0):
    P.append((m, c, o))


def frustum(a, b):
    """a, b: (cx, cy, z, w, d) dikdortgenleri; isik konisi."""
    v = []
    for cx, cy, z, w, d in (a, b):
        v += [(cx - w / 2, cy - d / 2, z), (cx + w / 2, cy - d / 2, z), (cx + w / 2, cy + d / 2, z), (cx - w / 2, cy + d / 2, z)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6),
         (3, 0, 4), (3, 4, 7)]
    m = trimesh.Trimesh(np.array(v), np.array(f), process=False)

    return m


def light_engine(P, L, cx, cy, z0, up=True):
    """up=True: fan altta, LCD ustte (recine yazici gibi). up=False: ters (LCD altta, asagi bakar). Ust z doner."""
    s = 1 if up else -1
    zz = lambda h: z0 + s * h
    seg = lambda a, b: (min(zz(a), zz(b)), max(zz(a), zz(b)))
    add(P, box(cx - 46, cx + 46, cy - 46, cy + 46, *seg(0, 25)), DARK)                       # fan
    for i in range(9):
        x = cx - 40 + i * 10
        add(P, box(x - 1, x + 1, cy - 45, cy + 45, *seg(25, 39)), ALU)                       # kanatlar (fana bakar)
    add(P, box(cx - 45, cx + 45, cy - 45, cy + 45, *seg(39, 45)), ALU)                       # sogutucu taban
    add(P, box(cx - 12.5, cx + 12.5, cy - 12.5, cy + 12.5, *seg(45, 47)), UV)                # COB LED
    zl, zf = zz(47), zz(47 + F)
    add(P, frustum((cx, cy, zl, 25, 25), (cx, cy, zf, 165, 115)), UV, 0.16)                   # isik
    add(P, box(cx - 82.5, cx + 82.5, cy - 57.5, cy + 57.5, *seg(47 + F, 49 + F)), FRES, 0.5)  # Fresnel
    add(P, box(cx - 77, cx + 77, cy - 49.5, cy + 49.5, *seg(59 + F, 60.3 + F)), LCD)         # LCD 154x99
    add(P, box(cx - 80, cx + 80, cy - 52.5, cy + 52.5, *seg(60.3 + F, 63.3 + F)), GLASS, 0.55)  # koruma cami
    L += [('UV LED 405 nm', (cx, cy, zz(46))), ('Soğutucu + fan', (cx - 46, cy - 46, zz(12))),
          ('Fresnel mercek', (cx + 82, cy + 57, zz(48 + F))), ('6.6" mono LCD', (cx - 77, cy - 50, zz(61 + F)))]
    return zz(63.3 + F)


def hot_plate(P, L, cx, cy, z0):
    for sx in (-1, 1):
        for sy in (-1, 1):
            add(P, cyl('z', (cx + sx * 90, cy + sy * 65), 4, z0, z0 + 18, seg=12), ALU)
    add(P, box(cx - 105, cx + 105, cy - 80, cy + 80, z0 + 18, z0 + 24), '#e8e2d0')            # yalitim
    add(P, box(cx - 100, cx + 100, cy - 75, cy + 75, z0 + 24, z0 + 30), HP)                  # 500 W plaka rezistans
    add(P, box(cx - 100, cx + 100, cy - 75, cy + 75, z0 + 30, z0 + 36), '#d5d9de')            # 6 mm Al
    L.append(('Hot plate 500 W', (cx + 100, cy - 75, z0 + 33)))
    return z0 + 36


def shell(P, x0, x1, y0, y1, z0, z1, front=False):
    t = 4
    for m in (box(x0, x0 + t, y0, y1, z0, z1), box(x1 - t, x1, y0, y1, z0, z1), box(x0, x1, y1 - t, y1, z0, z1)):
        add(P, m, SHELL, 0.13)
    if front:
        add(P, box(x0, x1, y0, y0 + t, z0, z1), SHELL, 0.13)


def drill(P, L, ox, oy, oz, base=True, table=True):
    """konsept 1 (portal) delme modulu, elektronik haric."""
    parts, _, _ = k.k1()
    for m, c in parts:
        if c == k.EL or (not base and c == k.WOOD and m.extents[2] < 7):
            continue
        if not table and c in (k.WOOD, '#d9c49a', k.PCB) and m.bounds[0][2] >= 19 and m.bounds[1][2] <= 35:
            continue
        m = m.copy()
        m.apply_translation([ox, oy, oz])
        add(P, m, c)
    L += [('Delme (portal)', (ox + 140, oy - 105, oz + 200)), ('775 spindle', (ox, oy - 55, oz + 120))]


def electronics(P, L, x0, x1, y0, y1, z0):
    add(P, box(x0, x1, y0, y1, z0, z0 + 30), k.EL)
    L.append(('Kontrol + güç (ESP32, RPi, 12 V)', ((x0 + x1) / 2, y0, z0 + 30)))


# ----------------------------------------------------------------------------- konseptler
def e1():   # kule
    P, L = [], []
    add(P, box(-140, 140, -115, 115, -6, 0), k.WOOD)
    top = light_engine(P, L, 0, 0, 2)
    add(P, box(-95, 95, -150, 75, top + 1, top + 6), k.PRINT)                               # cekmece (pozlama)
    add(P, box(-80, 80, -130, -30, top + 6, top + 7.6), k.PCB)
    L.append(('Pozlama çekmecesi (pimli)', (95, -150, top + 4)))
    shell(P, -140, 140, -115, 115, 0, top + 12)
    floor = top + 14
    add(P, box(-140, 140, -115, 115, floor - 2, floor), k.WOOD)
    drill(P, L, 0, 0, floor, base=False)
    hz = floor + 227
    hot_plate(P, L, 0, 0, hz)
    electronics(P, L, 95, 135, -105, 105, 2)
    return P, L, dict(
        ad='A. Kule', alt='Alt kat pozlama (LED yukarı bakar), orta çekmece, üst kat delme, çatıda hot plate',
        arti=['En küçük taban (280 × 230, çekmece kapalı): masada az yer', 'Isı yukarı: hot plate LCD\'den en uzak noktada',
              'Pozlama çekmecesi UV\'yi kendiliğinden kapatır'],
        eksi=['Uzun kule (~470 mm): devrilmeye karşı ağır taban', 'Delme talaşı çekmeceye düşmemeli (ara tabla şart)']), \
        (620, -760, 520)


def e2():   # yan yana
    P, L = [], []
    add(P, box(-335, 140, -115, 115, -6, 0), k.WOOD)
    top = light_engine(P, L, -240, 0, 2)
    add(P, box(-330, -150, -110, 110, top + 1, top + 3), '#2a2a2a', 0.6)
    lid = trimesh.creation.box(extents=[180, 4, 120])
    lid.apply_translation([-240, 110, top + 63])
    add(P, lid, AMBER, 0.45)
    L.append(('UV kapak (turuncu akrilik)', (-240, 110, top + 120)))
    shell(P, -335, -145, -115, 115, 0, top)
    drill(P, L, 0, 0, 0, base=False)
    hot_plate(P, L, 0, 0, 228)
    electronics(P, L, -330, -150, -112, -82, 2)
    return P, L, dict(
        ad='B. Yan yana', alt='Solda pozlama (LCD üstte, açılır UV kapak), sağda delme, delme çatısında hot plate',
        arti=['Alçak (~265 mm, kapak kapalı): ağırlık merkezi düşük', 'Pozlama reçine yazıcı gibi: tanıdık kullanım',
              'Bölmeler ayrı: talaş LCD\'ye ulaşmaz'],
        eksi=['Geniş taban (~470 × 230)', 'Plaket istasyonlar arasında elle taşınır (pimler hizayı korur)']), \
        (520, -820, 520)


def e3():   # mekik: ortak tasiyici, ustten pozlama
    P, L = [], []
    add(P, box(-140, 140, -115, 330, -6, 0), k.WOOD)
    drill(P, L, 0, 0, 0, base=False, table=False)
    for sx in (-1, 1):
        add(P, cyl('y', (sx * 100, 25), 4, -100, 320, seg=20), k.ROD)                       # uzun tasiyici raylari
    add(P, box(-95, 95, 165, 290, 30, 39), k.WOOD)                                          # tasiyici (pozlama konumunda)
    add(P, box(-80, 80, 178, 278, 39, 40.6), k.PCB)
    L.append(('Ortak pimli taşıyıcı (Y rayında)', (95, 165, 35)))
    zl = 40.6 + 2 + 63.3 + F
    light_engine(P, L, 0, 228, zl, up=False)
    hot_plate(P, L, 0, 228, zl + 4)
    shell(P, -140, 140, 115, 330, 0, zl + 2)
    electronics(P, L, 108, 136, 125, 320, 2)
    return P, L, dict(
        ad='C. Mekik (tek taşıyıcı)', alt='Plaket bir kez pimlere takılır; taşıyıcı arkada pozlamaya, önde delmeye gider',
        arti=['Tek hizalama: pozlama ile delik ofseti bir kez kalibre edilir', 'Plakete elle dokunma en az; otomasyona açık',
              'Pozlama yukarıdan (LCD aşağı bakar), bakır hep üstte'],
        eksi=['En uzun taban (~280 × 445)', 'LCD plakete indirilmeli (temas için küçük kaldırma mekanizması)']), \
        (720, -620, 560)


def e4():   # moduler kupler
    P, L = [], []
    gap = 12
    # pozlama kupu
    add(P, box(-140, 140, -115, 115, -6, 0), k.WOOD)
    top = light_engine(P, L, 0, 0, 2)
    shell(P, -140, 140, -115, 115, 0, top, front=False)
    lid = box(-140, 140, -115, 115, top + 1, top + 5)
    add(P, lid, AMBER, 0.45)
    L.append(('UV kapak', (140, -115, top + 3)))
    # delme kupu (sagda)
    drill(P, L, 280 + gap, 0, 0)
    # hot plate modulu (delme kupunun ustunde degil, solda alcak)
    add(P, box(-140 - 280 - gap, -gap - 140, -115, 115, -6, 0), k.WOOD)
    hot_plate(P, L, -280 - gap, 0, 0)
    electronics(P, L, 280 + gap + 40, 280 + gap + 130, -100, -60, 0)
    return P, L, dict(
        ad='D. Modüler küpler', alt='Üç ayrı modül, ortak kontrol/güç kablosu: pozlama küpü, delme küpü, hot plate',
        arti=['Her modül ayrı satılabilir/geliştirilir (ürün ailesi)', 'Isı, UV ve talaş tamamen ayrı',
              'Modül arızasında diğerleri çalışır'],
        eksi=['Toplam masa yeri en fazla (~870 × 230)', 'Üç kasa, üç kapak: maliyet ve montaj artar']), \
        (420, -1350, 640)


VIEW = r'''<!doctype html><html><head><meta charset="utf-8"><title>entegre</title>
<style>html,body{margin:0;height:100%;background:#f4f1ec;overflow:hidden;font:600 15px system-ui,sans-serif}
.lb{position:absolute;transform:translate(-50%,-140%);background:#ffffffe6;border:1px solid #333;border-radius:5px;padding:2px 6px;white-space:nowrap;color:#111}
.lb:after{content:'';position:absolute;left:50%;top:100%;width:1px;height:14px;background:#333}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script></head><body>
<script type="module">
import * as THREE from 'three';import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const D=__DATA__,LB=__LB__,CAM=__CAM__,TG=__TG__;const sc=new THREE.Scene();sc.background=new THREE.Color('#f4f1ec');
const cam=new THREE.PerspectiveCamera(30,innerWidth/innerHeight,1,8000);cam.up.set(0,0,1);cam.position.set(...CAM);
const r=new THREE.WebGLRenderer({antialias:true});r.setPixelRatio(devicePixelRatio);r.setSize(innerWidth,innerHeight);document.body.appendChild(r.domElement);
sc.add(new THREE.HemisphereLight(0xffffff,0x777777,1.7));const dl=new THREE.DirectionalLight(0xffffff,1.4);dl.position.set(300,-400,700);sc.add(dl);
for(const p of D){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(p.v,3));g.setIndex(p.f);g.computeVertexNormals();
const tr=p.o<1;const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:p.c,roughness:.75,transparent:tr,opacity:p.o,depthWrite:!tr,side:tr?THREE.DoubleSide:THREE.FrontSide}));
if(tr)m.renderOrder=2;sc.add(m);if(!tr||p.o>0.3)sc.add(new THREE.LineSegments(new THREE.EdgesGeometry(g,30),new THREE.LineBasicMaterial({color:0x333333,transparent:tr,opacity:tr?0.5:1})));}
const ctl=new OrbitControls(cam,r.domElement);ctl.target.set(...TG);ctl.update();
const els=LB.map(l=>{const d=document.createElement('div');d.className='lb';d.textContent=l.t;document.body.appendChild(d);return [d,new THREE.Vector3(...l.p)];});
(function a(){requestAnimationFrame(a);r.render(sc,cam);for(const [d,v] of els){const q=v.clone().project(cam);
d.style.left=((q.x+1)/2*innerWidth)+'px';d.style.top=((1-q.y)/2*innerHeight)+'px';}})();
</script></body></html>'''


def export(name, P, L, cam, tg):
    data = [dict(v=[round(float(x), 2) for x in m.vertices.flatten()], f=[int(i) for i in m.faces.flatten()], c=c, o=o)
            for m, c, o in P]
    html = os.path.join(HERE, name + '.html')
    with open(html, 'w', encoding='utf-8') as fh:
        fh.write(VIEW.replace('__DATA__', json.dumps(data, separators=(',', ':')))
                 .replace('__LB__', json.dumps([dict(t=t, p=[round(float(c), 1) for c in p]) for t, p in L], ensure_ascii=False))
                 .replace('__CAM__', json.dumps(cam)).replace('__TG__', json.dumps(tg)))
    png = os.path.join(HERE, name + '.png')
    g.screenshot(html, png)
    return png


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image

    out = []
    for i, f in enumerate((e1, e2, e3, e4), 1):
        P, L, info, cam = f()
        lo = np.min([m.bounds[0] for m, c, o in P], axis=0)
        hi = np.max([m.bounds[1] for m, c, o in P], axis=0)
        tg = [float(v) for v in (lo + hi) / 2]
        cam = [tg[0] + cam[0], tg[1] + cam[1], tg[2] + cam[2] * 0.6]
        png = export('entegre%d' % i, P, L, cam, tg)
        out.append((png, info, hi - lo))
        print(info['ad'], '%.0f x %.0f x %.0f mm' % tuple(hi - lo))

    fig = plt.figure(figsize=(20, 23))
    for n, (png, info, ext) in enumerate(out):
        ax = fig.add_axes([0.02 + (n % 2) * 0.49, 0.585 - (n // 2) * 0.48, 0.47, 0.355])
        im = Image.open(png).convert('RGB')
        a = np.asarray(im).astype(int)
        ys, xs = np.where(np.abs(a - np.array([244, 241, 236])).sum(axis=2) > 30)
        im = im.crop((max(xs.min() - 20, 0), max(ys.min() - 20, 0), min(xs.max() + 20, im.width), min(ys.max() + 20, im.height)))
        ax.imshow(im)
        ax.axis('off')
        ax.set_title('%s  —  %.0f × %.0f × %.0f mm' % (info['ad'], *ext), fontsize=17, fontweight='bold', loc='left')
        tx = fig.add_axes([0.02 + (n % 2) * 0.49, 0.475 - (n // 2) * 0.48, 0.47, 0.10])
        tx.axis('off')
        lines = [info['alt'], ''] + ['+ ' + s for s in info['arti']] + ['− ' + s for s in info['eksi']]
        tx.text(0, 1, '\n'.join(lines), va='top', fontsize=12.5)
    fig.suptitle('Bütünleşik PCB makinesi: pozlama (UV LED, soğutucu, Fresnel, 6.6" LCD) + delme + hot plate — 4 yerleşim\n'
                 '(ışık motoru yüksekliği Fresnel odak uzaklığına bağlı; burada F = %.0f mm varsayıldı)' % F,
                 fontsize=18, y=0.99)
    fig.savefig(os.path.join(HERE, 'entegre.png'), dpi=80)
    print('->', os.path.join(HERE, 'entegre.png'))


if __name__ == '__main__':
    main()
