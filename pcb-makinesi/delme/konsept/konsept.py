#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kucuk/kup PCB delme makinesi icin 4 yerlesim konsepti (kaba eskiz modelleri).
Hepsi ayni is alani (160 x 100 mm ham plaket) ve ayni parca ailesi (Ø8 mil, LM8UU, 28BYJ-48, 775 spindle).
Dis olculer modelden hesaplanir. Cikti: konseptler.png (2x2) + her konsept icin 3B html.

python3 konsept.py      (gen_delme.py ile ayni gereksinimler + Chromium)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import gen_delme as g  # noqa: E402

box, cyl, tube, union, m28byj, C = g.box, g.cyl, g.tube, g.union, g.m28byj, g.C
WOOD, PRINT, ROD, MOT, BEAR, PCB, BELT, ALU, EL = (C['wood'], C['print'], C['rod'], C['motor'], C['bear'],
                                                  C['pcb'], C['belt'], C['alu'], C['elec'])
PROF = '#8d949c'


def spindle_v(x, y, tip_z, parts):
    """Dikey 775 + mandren + uc; uc ucu tip_z'de."""
    nose = tip_z + 28
    parts += [(cyl('z', (x, y), 0.4, tip_z, nose + 10, seg=12), '#e0e0e0'),
              (cyl('z', (x, y), 9.5, nose, nose + 32), ALU),
              (cyl('z', (x, y), 21, nose + 36, nose + 103), MOT)]
    return nose + 103


def profile_frame(x0, x1, y0, y1, z0, z1, parts, s=20):
    for (xa, ya) in ((x0, y0), (x1 - s, y0), (x0, y1 - s), (x1 - s, y1 - s)):
        parts.append((box(xa, xa + s, ya, ya + s, z0, z1), PROF))
    for z in (z0, z1 - s):
        parts += [(box(x0, x1, y0, y0 + s, z, z + s), PROF), (box(x0, x1, y1 - s, y1, z, z + s), PROF),
                  (box(x0, x0 + s, y0, y1, z, z + s), PROF), (box(x1 - s, x1, y0, y1, z, z + s), PROF)]


def table_fixed(z0, parts, w=180, d=120):
    parts += [(box(-w / 2, w / 2, -d / 2, d / 2, z0, z0 + 9), WOOD),
              (box(-82, 82, -52, 52, z0 + 9, z0 + 12), '#d9c49a'),
              (box(-80, 80, -50, 50, z0 + 12, z0 + 13.6), PCB)]
    return z0 + 13.6


# ----------------------------------------------------------------------------- 1 portal kup
def k1():
    P = []
    profile_frame(-140, 140, -105, 105, 0, 215, P)
    P.append((box(-140, 140, -105, 105, -6, 0), WOOD))
    top = table_fixed(20, P)
    zr = 150.0                       # Y milleri ust kenarda
    for sx in (-1, 1):
        P.append((cyl('y', (sx * 118, zr), 4, -85, 85, seg=20), ROD))
        P.append((box(sx * 118 - 12, sx * 118 + 12, -25, 25, zr - 12, zr + 12), PRINT))
        P.append((m28byj((sx * 118, -96, zr + 22), (0, 1, 0), (0, 0, 1)), MOT))          # Y motorlari (2)
        P.append((box(sx * 118 - 3, sx * 118 + 3, -92, 92, zr + 18, zr + 19.4), BELT))
    for dz in (-14, 14):
        P.append((cyl('x', (-22, zr + dz), 4, -106, 106, seg=20), ROD))               # X milleri koprude
    P.append((box(-30, 30, -38, -8, zr - 26, zr + 26), PRINT))                        # X/Z arabasi
    P.append((m28byj((106, -22, zr + 34), (0, 0, 1), (1, 0, 0)), MOT))               # X motoru
    P.append((box(-104, 104, -6, -4.6, zr + 30, zr + 36), BELT))
    for sx in (-1, 1):
        P.append((cyl('z', (sx * 18, -50), 4, top + 40, zr + 30, seg=20), ROD))
    P.append((box(-24, 24, -72, -42, 95, 135), PRINT))
    spindle_v(0, -55, top - 2.2, P)
    P.append((m28byj((0, -50, zr + 50), (0, 0, -1), (0, -1, 0)), MOT))
    P.append((box(40, 130, -100, -60, 0, 14), EL))
    return P, dict(
        ad='1. Portal küp', alt='Sabit tabla, köprü Y\'de, araba X\'te, Z arabada',
        arti=['Plaket hiç hareket etmez: pimle hizalama en kolay',
              'İş alanı + araba kadar yer: en dengeli küp',
              '3018 sınıfında kanıtlanmış düzen'],
        eksi=['Köprü iki yandan sürülmeli (2 Y motoru ya da ortak mil)',
              '775 ve Z köprüde: 28BYJ ağır yük taşır']), (430, -470, 330)


# ----------------------------------------------------------------------------- 2 CoreXY kup
def k2():
    P = []
    profile_frame(-135, 135, -100, 115, 0, 220, P)
    P.append((box(-135, 135, -100, 115, -6, 0), WOOD))
    top = table_fixed(20, P)
    zr = 175.0
    for sx in (-1, 1):
        P.append((cyl('y', (sx * 112, zr), 4, -80, 95, seg=20), ROD))
        P.append((box(sx * 112 - 12, sx * 112 + 12, -12, 28, zr - 10, zr + 10), PRINT))
        P.append((m28byj((sx * 112, 100, zr + 28), (0, 0, 1), (0, 1, 0)), MOT))       # sabit motorlar arkada
    P.append((cyl('x', (8, zr), 4, -100, 100, seg=20), ROD))
    P.append((box(-28, 28, -10, 26, zr - 14, zr + 14), PRINT))                         # hafif kafa
    # H/CoreXY kayislari (ust duzlemde iki kat)
    for zz, col in ((zr + 30, BELT), (zr + 36, '#555555')):
        P += [(box(-112, -110.6, -80, 100, zz, zz + 6), col), (box(110.6, 112, -80, 100, zz, zz + 6), col),
              (box(-112, 112, 8, 9.4, zz, zz + 6), col)]
    for sx in (-1, 1):
        P.append((cyl('z', (sx * 18, 8), 4, top + 45, zr - 14, seg=20), ROD))
    P.append((box(-24, 24, -40, 22, 100, 140), PRINT))
    spindle_v(0, -18, top - 2.2, P)
    P.append((m28byj((0, 8, zr + 18), (0, 0, -1), (0, -1, 0)), MOT))
    P.append((box(40, 125, -95, -60, 0, 14), EL))
    return P, dict(
        ad='2. CoreXY küp', alt='Sabit tabla, motorlar sabit köşelerde, kafa H kayışla',
        arti=['Motorlar hareket etmez: hareketli kütle en düşük (28BYJ için iyi)',
              'Kapalı profil kutu: rijit, kapak/toz kabını takmak kolay',
              '3D yazıcı (CoreXY) bilgisi doğrudan kullanılır'],
        eksi=['Uzun kayış yolu: kayış gerginliği ve esnemesi doğruluğu etkiler',
              'İki motor birlikte çalışır: yazılım biraz daha karmaşık']), (430, -470, 340)


# ----------------------------------------------------------------------------- 3 dikey plaka
def k3():
    P = []
    P.append((box(-140, 140, -150, 30, -6, 0), WOOD))
    P.append((box(-140, 140, 12, 30, 0, 200), WOOD))                                  # arka duvar
    P += [(box(-90, 90, 3, 12, 40, 160), WOOD), (box(-82, 82, 0, 3, 48, 152), '#d9c49a'),
          (box(-80, 80, -1.6, 0, 50, 150), PCB)]                                      # dik plaket (XZ)
    for zz in (20, 185):
        P.append((cyl('x', (-115, zz), 4, -130, 130, seg=20), ROD))                    # X milleri (alt/ust)
    for sx in (-1, 1):                                                                # X arabasi: acik cerceve
        P.append((box(sx * 30 - 6, sx * 30 + 6, -128, -102, 10, 195), PRINT))
        P.append((cyl('z', (sx * 30, -95), 4, 25, 180, seg=20), ROD))                  # Z (dikey) milleri
    P += [(box(-36, 36, -128, -102, 10, 28), PRINT), (box(-36, 36, -128, -102, 177, 195), PRINT)]
    P.append(((union([box(-38, 38, -102, -86, 80, 120), tube('y', (0, 100), 26, 21.2, -102, -86)])), PRINT))  # Z arabasi + kelepce
    # yatay spindle (eksen +y, plakete bakar)
    P += [(cyl('y', (0, 100), 21, -175, -108), MOT), (cyl('y', (0, 100), 9.5, -104, -72), ALU),
          (cyl('y', (0, 100), 0.4, -72, -2), '#e0e0e0')]
    P.append((m28byj((128, -115, 30), (0, 0, 1), (1, 0, 0)), MOT))
    P.append((m28byj((0, -95, 185), (0, 0, -1), (0, 1, 0)), MOT))
    P.append((box(-125, -40, -145, -125, 0, 14), EL))
    P.append((box(-100, 100, -20, 8, 0, 18), '#bbbbbb'))                               # talas haznesi
    return P, dict(
        ad='3. Dikey plaket', alt='Plaket dik duvarda, yatay spindle X ve Z\'de gezer, Y = delme ilerlemesi',
        arti=['Talaş ve toz aşağı düşer: plaket temiz, uç soğur',
              'Derinlik en az: ince kutu, rafa/duvara yaslanır',
              'Plaket pozlama aparatıyla aynı dik konumda takılabilir'],
        eksi=['Dikey eksen spindle ağırlığını taşır: yay/karşı ağırlık şart',
              'Alışılmadık düzen: yatay delmede uç sapması ölçülmeli']), (420, -520, 300)


# ----------------------------------------------------------------------------- 4 doner tabla (R-theta)
def k4():
    P = []
    P.append((box(-120, 120, -125, 125, -6, 0), WOOD))
    P.append((box(-60, 60, 105, 125, 0, 225), WOOD))                                  # arka kolon
    P.append((cyl('z', (0, 0), 30, 0, 16), '#777777'))                               # rulmanli tabla (lazy susan)
    P.append((cyl('z', (0, 0), 101, 16, 25, seg=96), PRINT))                          # doner disk, kenari GT2 disli
    P.append((tube('z', (0, 0), 101.6, 100.4, 17, 23), BELT))                         # kenarda kayis
    P += [(box(-82, 82, -52, 52, 25, 28), '#d9c49a'), (box(-80, 80, -50, 50, 28, 29.6), PCB)]
    P.append((m28byj((-108, -40, 14), (0, 0, 1), (1, 0, 0)), MOT))                   # theta motoru (15.7:1)
    for sx in (-1, 1):
        P.append((cyl('y', (sx * 20, 175), 4, -105, 115, seg=20), ROD))                # R milleri (radyal)
    P.append((box(-60, 60, 95, 115, 160, 190), PRINT))                                # kol baglantisi
    P.append((box(-34, 34, -70, -36, 160, 190), PRINT))                               # R arabasi
    P.append((m28byj((40, 108, 195), (0, 0, 1), (0, 1, 0)), MOT))
    P.append((box(-3, 3, -95, 105, 196, 197.4), BELT))
    for sx in (-1, 1):
        P.append((cyl('z', (sx * 18, -60), 4, 60, 160, seg=20), ROD))
    P.append((box(-24, 24, -80, -40, 100, 140), PRINT))
    spindle_v(0, -50, 29.6 - 2.2, P)
    P.append((m28byj((0, -55, 205), (0, 0, -1), (0, -1, 0)), MOT))
    P.append((box(30, 110, -122, -95, 0, 14), EL))
    return P, dict(
        ad='4. Döner tabla (R-θ)', alt='Plaket dönen diskte, spindle tek radyal eksende (R), Z',
        arti=['En küçük: tabla yalnız döner, süpürme alanı = plaket köşegeni (Ø190)',
              'Disk kenarı dev kasnak (≈16:1): 28BYJ boşluğu ~16 kat küçülür, ~0,02 mm/adım',
              'Yalnız 2 hareket ekseni + Z, 4 doğrusal mil'],
        eksi=['Kutupsal koordinat: yazılımda dönüşüm (basit ama şart)',
              'Disk düzlemselliği ve merkez kaçıklığı kalibre edilmeli']), (420, -480, 360)


VIEW = r'''<!doctype html><html><head><meta charset="utf-8"><title>konsept</title>
<style>html,body{margin:0;height:100%;background:#f4f1ec;overflow:hidden}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script></head><body>
<script type="module">
import * as THREE from 'three';import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const D=__DATA__,CAM=__CAM__;const sc=new THREE.Scene();sc.background=new THREE.Color('#f4f1ec');
const cam=new THREE.PerspectiveCamera(30,innerWidth/innerHeight,1,5000);cam.up.set(0,0,1);cam.position.set(...CAM);
const r=new THREE.WebGLRenderer({antialias:true});r.setPixelRatio(devicePixelRatio);r.setSize(innerWidth,innerHeight);document.body.appendChild(r.domElement);
sc.add(new THREE.HemisphereLight(0xffffff,0x777777,1.7));const dl=new THREE.DirectionalLight(0xffffff,1.5);dl.position.set(300,-400,600);sc.add(dl);
for(const p of D){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(p.v,3));g.setIndex(p.f);g.computeVertexNormals();
const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:p.c,roughness:.75}));sc.add(m);
const e=new THREE.LineSegments(new THREE.EdgesGeometry(g,30),new THREE.LineBasicMaterial({color:0x333333}));sc.add(e);}
const ctl=new OrbitControls(cam,r.domElement);ctl.target.set(0,0,95);ctl.update();
(function a(){requestAnimationFrame(a);r.render(sc,cam);})();
</script></body></html>'''


def export(name, parts, cam):
    data = [dict(v=[round(float(x), 2) for x in m.vertices.flatten()], f=[int(i) for i in m.faces.flatten()], c=c)
            for m, c in parts]
    html = os.path.join(HERE, name + '.html')
    with open(html, 'w', encoding='utf-8') as fh:
        fh.write(VIEW.replace('__DATA__', json.dumps(data, separators=(',', ':'))).replace('__CAM__', json.dumps(cam)))
    png = os.path.join(HERE, name + '.png')
    g.screenshot(html, png)
    return png


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image

    out = []
    for i, f in enumerate((k1, k2, k3, k4), 1):
        parts, info, cam = f()
        lo = np.min([m.bounds[0] for m, _ in parts], axis=0)
        hi = np.max([m.bounds[1] for m, _ in parts], axis=0)
        ext = hi - lo
        png = export('konsept%d' % i, parts, cam)
        out.append((png, info, ext))
        print(info['ad'], '%.0f x %.0f x %.0f mm' % tuple(ext))

    fig = plt.figure(figsize=(20, 23))
    for k, (png, info, ext) in enumerate(out):
        ax = fig.add_axes([0.02 + (k % 2) * 0.49, 0.585 - (k // 2) * 0.48, 0.47, 0.355])
        im = Image.open(png).convert('RGB')
        a = np.asarray(im).astype(int)
        mask = np.abs(a - np.array([244, 241, 236])).sum(axis=2) > 30
        ys, xs = np.where(mask)
        pad = 20
        im = im.crop((max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad, im.width), min(ys.max() + pad, im.height)))
        ax.imshow(im)
        ax.axis('off')
        ax.set_title('%s  —  %.0f × %.0f × %.0f mm' % (info['ad'], *ext), fontsize=17, fontweight='bold', loc='left')
        tx = fig.add_axes([0.02 + (k % 2) * 0.49, 0.475 - (k // 2) * 0.48, 0.47, 0.10])
        tx.axis('off')
        lines = [info['alt'], ''] + ['+ ' + a for a in info['arti']] + ['− ' + e for e in info['eksi']]
        tx.text(0, 1, '\n'.join(lines), va='top', fontsize=12.5, family='DejaVu Sans')
    fig.suptitle('Küçük / küp PCB delme makinesi: 4 yerleşim fikri  (hepsi 160 × 100 mm iş alanı; ölçüler modelden)',
                 fontsize=19, y=0.985)
    fig.savefig(os.path.join(HERE, 'konseptler.png'), dpi=80)
    print('->', os.path.join(HERE, 'konseptler.png'))


if __name__ == '__main__':
    main()
