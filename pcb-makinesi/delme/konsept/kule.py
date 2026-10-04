#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"Kule" butunlesik PCB makinesi: 4 detay konsepti (eskiz seviyesinde, olculer modelden).
  K1 Portal + pozlama cekmecesi (COB + Fresnel)        K2 Doner tabla (R-theta) ile ince kule
  K3 Ters kule: delme altta, pozlama ustte, hot plate alt cekmecede
  K4 Alcak kule: matris LED + lens dizisi (Fresnel yok)
Cikti: kule1..4.html/png (etiketli 3B), kule-detay-1..4.png (gorsel + aciklama), kule.png (2x2 ozet).
python3 kule.py
"""
import json
import math
import os
import sys
import textwrap

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import gen_delme as g   # noqa: E402
import konsept as k    # noqa: E402
import entegre as e    # noqa: E402

box, cyl, union, tube = g.box, g.cyl, g.union, g.tube
add, frustum, light_engine, shell = e.add, e.frustum, e.light_engine, e.shell
F = e.F
WOOD, PRINT, ROD, MOT, PCB, EL, PROF = k.WOOD, k.PRINT, k.ROD, k.MOT, k.PCB, k.EL, k.PROF
UV, FRES, LCDC, GLASS, HP, ALU, DARK, AMBER, CLEAR = (e.UV, e.FRES, e.LCD, e.GLASS, e.HP, e.ALU, e.DARK, e.AMBER,
                                                      '#bfe3ff')
GRN, SIL, RED, RUB = '#1f7a3f', '#c9ced4', '#d0312d', '#2b2b2b'


def frame(P, x0, x1, y0, y1, z0, z1, s=15):
    parts = []
    k.profile_frame(x0, x1, y0, y1, z0, z1, parts, s=s)
    for m, c in parts:
        add(P, m, c)


def panels(P, x0, x1, y0, y1, z0, z1, front=False, op=0.12, col='#9aa3ad'):
    t = 3
    for m in (box(x0, x0 + t, y0, y1, z0, z1), box(x1 - t, x1, y0, y1, z0, z1), box(x0, x1, y1 - t, y1, z0, z1)):
        add(P, m, col, op)
    if front:
        add(P, box(x0, x1, y0, y0 + t, z0, z1), col, op)


def vents(P, x, y0, y1, z0, n=6, side=1):
    for i in range(n):
        y = y0 + (y1 - y0) * (i + 0.5) / n
        add(P, box(x - 1 if side > 0 else x, x + 1 if side > 0 else x + 2, y - 2, y + 2, z0, z0 + 35), RUB)


def feet(P, x0, x1, y0, y1, z):
    for x in (x0 + 18, x1 - 18):
        for y in (y0 + 18, y1 - 18):
            add(P, cyl('z', (x, y), 10, z - 10, z, seg=24), RUB)


def electronics_back(P, L, x0, y_wall, z0, flip=False):
    """Arka duvarda dikey: Mean Well PSU, Raspberry Pi (HDMI -> LCD karti), ESP32-S3 + 3x ULN2003, MOSFET/SSR."""
    s = -1 if flip else 1
    yb = y_wall - 3
    add(P, box(x0, x0 + 129, yb - 32, yb, z0, z0 + 97), SIL)                                # PSU (dik)
    xr = x0 - 100 if not flip else x0 + 140
    add(P, box(xr, xr + 85, yb - 18, yb - 2, z0 + 10, z0 + 66), GRN)                         # RPi
    add(P, box(xr + 5, xr + 57, yb - 14, yb - 2, z0 + 80, z0 + 108), '#222')                 # ESP32-S3
    for i in range(3):
        add(P, box(xr + i * 36, xr + i * 36 + 32, yb - 15, yb - 2, z0 + 115, z0 + 150), GRN)  # ULN2003
    L.append(('Elektronik (arka duvar): PSU, RPi, ESP32, 3× ULN2003', (x0 + 64, yb - 32, z0 + 97)))


def control_panel(P, L, x, y, z):
    """Sag yan yuzde (x = govde sag kenari): dokunmatik ekran + acil stop."""
    add(P, box(x, x + 6, y - 30, y + 30, z, z + 80), '#3a3f45')
    add(P, box(x + 6, x + 7, y - 24, y + 24, z + 30, z + 74), '#0b0d10')
    add(P, cyl('x', (y, z + 14), 9, x + 6, x + 16, seg=32), RED)
    L.append(('Dokunmatik ekran + acil stop', (x + 7, y, z + 74)))


def hotplate(P, L, cx, cy, z0, handles=True):
    top = e.hot_plate(P, [], cx, cy, z0)
    add(P, box(cx - 104, cx + 104, cy - 79, cy - 75, top - 6, top + 4), '#c44')
    add(P, box(cx - 104, cx + 104, cy + 75, cy + 79, top - 6, top + 4), '#c44')
    add(P, box(cx - 104, cx - 100, cy - 75, cy + 75, top - 6, top + 4), '#c44')
    add(P, box(cx + 100, cx + 104, cy - 75, cy + 75, top - 6, top + 4), '#c44')              # silikon kenar
    if handles:
        for sx in (-1, 1):
            add(P, box(cx + sx * 104, cx + sx * 116, cy - 30, cy + 30, top - 12, top - 6), RUB)
    add(P, cyl('x', (cy + 40, top - 9), 2, cx + 100, cx + 125, seg=12), '#e5c100')              # termokupl
    L.append(('Hot plate 500 W (PID, K-tip)', (cx + 100, cy - 75, top + 2)))
    return top + 4


def drawer(P, L, cx, cy, z0, out=70, w=190, d=150, label='Pozlama çekmecesi (pimli kaset)'):
    """Plaket bakir asagi, pimli kasette; cekmece 'out' mm disari cekik."""
    y0 = cy - d / 2 - out
    add(P, box(cx - w / 2, cx + w / 2, y0, y0 + d, z0, z0 + 4), PRINT)
    add(P, box(cx - w / 2, cx + w / 2, y0 - 4, y0, z0, z0 + 22), '#3a3f45')                  # on panel
    add(P, box(cx - 30, cx + 30, y0 - 12, y0 - 4, z0 + 8, z0 + 14), RUB)                       # kulp
    add(P, box(cx - 80, cx + 80, y0 + 20, y0 + 120, z0 + 4, z0 + 5.6), PCB)
    for sx in (-1, 1):
        add(P, cyl('z', (cx + sx * 76, y0 + 70), 1.5, z0 + 4, z0 + 9, seg=12), ALU)
    L.append((label, (cx + w / 2, y0, z0 + 12)))


def chip_tray(P, L, x0, x1, y0, y1, z0, label=True):
    add(P, box(x0, x1, y0, y1, z0, z0 + 2), '#5c6670')
    for m in (box(x0, x0 + 2, y0, y1, z0, z0 + 10), box(x1 - 2, x1, y0, y1, z0, z0 + 10),
              box(x0, x1, y0, y0 + 2, z0, z0 + 10), box(x0, x1, y1 - 2, y1, z0, z0 + 10)):
        add(P, m, '#5c6670')
    if label:
        L.append(('Talaş tepsisi / ayırıcı', (x1, y0, z0 + 10)))


def door(P, L, x_h, y_h, z0, z1, w, ang_deg, label='Şeffaf kapı (PC)'):
    m = box(0, w, -3, 0, z0, z1)
    m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(-ang_deg), [0, 0, 1], [0, 0, 0]))
    m.apply_translation([x_h, y_h, 0])
    add(P, m, CLEAR, 0.28)
    a = math.radians(ang_deg)
    L.append((label, (x_h + w * 0.5 * math.cos(a), y_h - w * 0.5 * math.sin(a), z1)))


def drill_portal(P, L, oz, table=True):
    parts, _, _ = k.k1()
    for m, c in parts:
        if c == k.EL or (c == WOOD and m.extents[2] < 7):
            continue
        if not table and c in (WOOD, '#d9c49a', PCB) and 19 <= m.bounds[0][2] and m.bounds[1][2] <= 35:
            continue
        m = m.copy()
        m.apply_translation([0, 0, oz])
        add(P, m, c)
    L += [('Delme portalı (X/Y 28BYJ)', (140, -105, oz + 200)), ('775 spindle + pens', (0, -55, oz + 120)),
          ('Delme tablası (aynı pimler)', (-90, -60, oz + 30))]
    return oz + 215


def drill_polar(P, L, oz):
    parts, _, _ = k.k4()
    for m, c in parts:
        if c == k.EL or (c == WOOD and m.extents[2] < 7):
            continue
        m = m.copy()
        m.apply_translation([0, 0, oz])
        add(P, m, c)
    L += [('Döner tabla (θ, disk kenarı 16:1)', (100, -40, oz + 22)), ('Radyal eksen (R)', (60, 0, oz + 190)),
          ('775 spindle + pens', (0, -50, oz + 120))]
    return oz + 231


def matrix_light(P, L, cx, cy, z0):
    """Matris LED isik motoru: 2x 60 mm fan, kanatli sogutucu, 4x6 LED + lens dizisi, 25 mm sonra LCD."""
    for sx in (-1, 1):
        add(P, box(cx + sx * 40 - 30, cx + sx * 40 + 30, cy - 30, cy + 30, z0, z0 + 15), DARK)
    for i in range(15):
        x = cx - 80 + i * 11.4
        add(P, box(x - 1, x + 1, cy - 58, cy + 58, z0 + 15, z0 + 29), ALU)
    add(P, box(cx - 85, cx + 85, cy - 60, cy + 60, z0 + 29, z0 + 35), ALU)
    add(P, box(cx - 80, cx + 80, cy - 55, cy + 55, z0 + 35, z0 + 37), GRN)
    zl = z0 + 37
    for ix in range(6):
        for iy in range(4):
            x, y = cx - 62.5 + ix * 25, cy - 37.5 + iy * 25
            add(P, box(x - 2.5, x + 2.5, y - 2.5, y + 2.5, zl, zl + 1.5), UV)
            add(P, cyl('z', (x, y), 9, zl + 6, zl + 11, seg=24), '#e8f4ff', 0.6)               # lens
            add(P, frustum((x, y, zl + 11, 18, 18), (x, y, zl + 36, 26, 26)), UV, 0.10)
    add(P, box(cx - 77, cx + 77, cy - 49.5, cy + 49.5, zl + 36, zl + 37.3), LCDC)
    add(P, box(cx - 80, cx + 80, cy - 52.5, cy + 52.5, zl + 37.3, zl + 40.3), GLASS, 0.55)
    L += [('Matris UV LED 4×6 (405 nm)', (cx + 62, cy - 37, zl + 1)), ('Lens dizisi', (cx - 62, cy - 37, zl + 11)),
          ('Soğutucu + 2 fan', (cx - 85, cy - 60, z0 + 20)), ('6.6" mono LCD', (cx - 77, cy - 50, zl + 37))]
    return zl + 40.3


# ----------------------------------------------------------------------------- konseptler
def K1():
    P, L = [], []
    X0, X1, Y0, Y1 = -140, 140, -115, 115
    feet(P, X0, X1, Y0, Y1, -6)
    add(P, box(X0, X1, Y0, Y1, -6, 0), WOOD)
    top = light_engine(P, L, 0, -15, 2)
    electronics_back(P, L, 0, Y1, 2)
    frame(P, X0, X1, Y0, Y1, 0, top + 12)
    panels(P, X0, X1, Y0, Y1, 0, top + 12)
    vents(P, X0, -70, 40, 2, side=-1)
    vents(P, X1, -70, 40, 2)
    drawer(P, L, 0, -15, top + 1)
    control_panel(P, L, X1, -40, 50)
    fl = top + 12
    chip_tray(P, L, X0 + 15, X1 - 15, Y0 + 15, Y1 - 15, fl)
    dz = drill_portal(P, L, fl)
    door(P, L, X0, Y0, fl, dz, 280, 70)
    add(P, box(X0, X1, Y0, Y1, dz, dz + 4), WOOD)
    ht = hotplate(P, L, 0, 0, dz + 4)
    floors = [('Ayak + taban', 16), ('Pozlama katı (fan → LCD)', top), ('Çekmece + ayırıcı', 12), ('Delme katı', dz - fl),
              ('Çatı + hot plate', ht - dz)]
    return P, L, dict(
        ad='K1. Portal + pozlama çekmecesi', floors=floors,
        akış=['1  Plaketi pimli kasete tak (bakır aşağı), çekmeceyi kapat → UV pozlama',
              '2  Kaseti çıkar → banyo / aşındırma / sökme (ıslak istasyon ayrı)',
              '3  Aynı pimlerle delme tablasına koy (bakır yukarı) → delme',
              '4  Montaj → çatıdaki hot plate ile reflow'],
        arti=['Önceki temel tasarım: delme portalı ve ışık motoru doğrudan kullanılır',
              'Çekmece kapanınca UV dışarı sızmaz; kapak kilidi basit', 'Isı çatıda, LCD en altta: termal ayrım en iyi'],
        eksi=['Yüksek (~470 mm) ve üst ağır: taban ağır olmalı', 'Hot plate için makinenin üstüne uzanmak gerekir']), \
        (680, -820, 470)


def K2():
    P, L = [], []
    X0, X1, Y0, Y1 = -120, 120, -125, 125
    feet(P, X0, X1, Y0, Y1, -6)
    add(P, box(X0, X1, Y0, Y1, -6, 0), WOOD)
    top = light_engine(P, L, 0, -30, 2)
    electronics_back(P, L, -10, Y1, 2)
    frame(P, X0, X1, Y0, Y1, 0, top + 12)
    panels(P, X0, X1, Y0, Y1, 0, top + 12)
    vents(P, X0, -90, 30, 2, side=-1)
    vents(P, X1, -90, 30, 2)
    drawer(P, L, 0, -30, top + 1, w=180)
    fl = top + 12
    chip_tray(P, L, X0 + 12, X1 - 12, Y0 + 12, Y1 - 12, fl, label=False)
    dz = drill_polar(P, L, fl)
    frame(P, X0, X1, Y0, Y1, fl, dz)
    panels(P, X0, X1, Y0, Y1, fl, dz, op=0.10)
    door(P, L, X0, Y0, fl, dz, 240, 65)
    control_panel(P, L, X1, -40, fl + 60)
    add(P, box(X0, X1, Y0, Y1, dz, dz + 4), WOOD)
    ht = hotplate(P, L, 0, 0, dz + 4, handles=False)
    floors = [('Ayak + taban', 16), ('Pozlama katı', top), ('Çekmece + ayırıcı', 12), ('Delme katı (döner)', dz - fl),
              ('Çatı + hot plate', ht - dz)]
    return P, L, dict(
        ad='K2. Döner tabla ile ince kule', floors=floors,
        akış=['1  Kasetle pozlama (çekmece)', '2  Islak işlem', '3  Kaseti döner diske pimlerle tak → R-θ delme',
              '4  Çatıda reflow'],
        arti=['En dar taban (240 × 250): bir A4 kâğıttan biraz büyük',
              'Disk kenarı 16:1 redüksiyon: 28BYJ boşluğu en az, ~0,02 mm/adım',
              'Delme katında yalnız 4 doğrusal mil'],
        eksi=['Yüksek (~490 mm), dar taban: devrilmeye dikkat', 'Kutupsal koordinat ve disk merkez kalibrasyonu yazılım işi']), \
        (640, -820, 500)


def K3():
    P, L = [], []
    X0, X1, Y0, Y1 = -140, 140, -115, 115
    feet(P, X0, X1, Y0, Y1, -6)
    add(P, box(X0, X1, Y0, Y1, -6, 0), WOOD)
    # alt cekmece: hot plate (disari cekik)
    frame(P, X0, X1, Y0, Y1, 0, 70)
    panels(P, X0, X1, Y0, Y1, 0, 70)
    add(P, box(-110, 110, -195, 35, 2, 6), '#3a3f45')                                         # kizak tepsisi
    hotplate(P, L, 0, -80, 6, handles=False)
    add(P, box(-110, 110, -199, -195, 2, 30), '#3a3f45')
    add(P, box(-30, 30, -207, -199, 12, 20), RUB)
    L.append(('Hot plate çekmecesi (dışarı çekik)', (110, -195, 30)))
    for i in range(5):
        add(P, box(-100 + i * 50, -80 + i * 50, Y1 - 3, Y1, 20, 60), RUB)                     # arka sicak hava cikisi
    L.append(('Arka sıcak hava çıkışı', (0, Y1, 60)))
    add(P, box(X0, X1, Y0, Y1, 70, 74), WOOD)
    fl = 74
    chip_tray(P, L, X0 + 15, X1 - 15, Y0 + 15, Y1 - 15, fl, label=False)
    dz = drill_portal(P, L, fl)
    door(P, L, X0, Y0, fl, dz, 280, 70)
    control_panel(P, L, X1, -40, fl + 60)
    add(P, box(X0, X1, Y0, Y1, dz, dz + 6), WOOD)
    L.append(('Isı yalıtımlı ayırıcı', (X0, Y0, dz + 6)))
    top = light_engine(P, L, 0, -10, dz + 8)
    electronics_back(P, L, 0, Y1, dz + 8)
    frame(P, X0, X1, Y0, Y1, dz, top + 2)
    panels(P, X0, X1, Y0, Y1, dz, top + 2, front=True)
    lid = box(-100, 100, -3, 0, 0, 150)
    lid.apply_transform(trimesh.transformations.rotation_matrix(math.radians(-70), [1, 0, 0]))
    lid.apply_translation([0, 60, top + 3])
    add(P, lid, AMBER, 0.45)
    L.append(('UV kapak (turuncu, menteşeli)', (0, 60, top + 140)))
    floors = [('Ayak + taban', 16), ('Hot plate çekmecesi', 74), ('Delme katı', dz - fl), ('Pozlama katı (LCD üstte)', top + 2 - dz)]
    return P, L, dict(
        ad='K3. Ters kule (pozlama üstte)', floors=floors,
        akış=['1  Plaketi üstteki LCD\'ye bakır aşağı koy, UV kapağı kapat → pozlama (reçine yazıcı gibi)',
              '2  Islak işlem', '3  Orta kattaki delme tablasına pimlerle tak → delme',
              '4  Alt çekmeceyi çek → hot plate ile reflow'],
        arti=['Ağır parçalar (spindle, delme) altta: devrilmez', 'Talaş aşağı düşer, LCD\'ye asla ulaşmaz',
              'Hot plate çekmecesi bel hizasında, üstten uzanmak yok'],
        eksi=['Hot plate ısısı yukarı çıkar: delme katı ısınır, LCD için yalıtımlı ayırıcı + arka hava çıkışı şart',
              'LCD en üstte: kapak açıkken ışık sızmasın diye kapak anahtarı şart']), \
        (700, -860, 450)


def K4():
    P, L = [], []
    X0, X1, Y0, Y1 = -140, 140, -115, 115
    feet(P, X0, X1, Y0, Y1, -6)
    add(P, box(X0, X1, Y0, Y1, -6, 0), WOOD)
    top = matrix_light(P, L, 0, -20, 2)
    add(P, box(30, 159, Y1 - 35, Y1 - 3, 2, 34), SIL)                                         # PSU yatay
    L.append(('Güç + kontrol (arka şerit)', (95, Y1 - 35, 34)))
    add(P, box(-135, 25, Y1 - 30, Y1 - 3, 2, 30), EL)
    frame(P, X0, X1, Y0, Y1, 0, top + 12)
    panels(P, X0, X1, Y0, Y1, 0, top + 12)
    vents(P, X0, -80, 40, 0, side=-1)
    vents(P, X1, -80, 40, 0)
    drawer(P, L, 0, -20, top + 1)
    fl = top + 12
    chip_tray(P, L, X0 + 15, X1 - 15, Y0 + 15, Y1 - 15, fl, label=False)
    dz = drill_portal(P, L, fl)
    door(P, L, X0, Y0, fl, dz, 280, 70)
    control_panel(P, L, X1, -40, fl + 60)
    add(P, box(X0, X1, Y0, Y1, dz, dz + 4), WOOD)
    ht = hotplate(P, L, 0, 0, dz + 4)
    floors = [('Ayak + taban', 16), ('Pozlama katı (matris LED)', top), ('Çekmece + ayırıcı', 12), ('Delme katı', dz - fl),
              ('Çatı + hot plate', ht - dz)]
    return P, L, dict(
        ad='K4. Alçak kule (matris LED)', floors=floors,
        akış=['K1 ile aynı akış; yalnız ışık motoru farklı'],
        arti=['Fresnel ve 120 mm ışık mesafesi yok: kule K1\'den ~105 mm kısa',
              'LED başına lens: kenar bölgeler de dik ışık alır (Anycubic M7 tarzı)',
              'Isı geniş alana yayılır: tek büyük COB\'tan daha soğuk'],
        eksi=['24 LED + lens dizisi: daha fazla parça ve lens tedariki',
              'Düzgünlük (homojenlik) ölçülüp LED akımları ayarlanmalı']), \
        (680, -820, 430)


def export(name, P, L, cam, tg):
    data = [dict(v=[round(float(x), 2) for x in m.vertices.flatten()], f=[int(i) for i in m.faces.flatten()], c=c, o=o)
            for m, c, o in P]
    html = os.path.join(HERE, name + '.html')
    with open(html, 'w', encoding='utf-8') as fh:
        fh.write(e.VIEW.replace('__DATA__', json.dumps(data, separators=(',', ':')))
                 .replace('__LB__', json.dumps([dict(t=t, p=[round(float(c), 1) for c in p]) for t, p in L], ensure_ascii=False))
                 .replace('__CAM__', json.dumps(cam)).replace('__TG__', json.dumps(tg)))
    png = os.path.join(HERE, name + '.png')
    g.screenshot(html, png)
    return png


def crop(im):
    a = np.asarray(im.convert('RGB')).astype(int)
    ys, xs = np.where(np.abs(a - np.array([244, 241, 236])).sum(axis=2) > 30)
    return im.crop((max(xs.min() - 20, 0), max(ys.min() - 20, 0), min(xs.max() + 20, im.width), min(ys.max() + 20, im.height)))


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image

    res = []
    for i, f in enumerate((K1, K2, K3, K4), 1):
        P, L, info, cam = f()
        lo = np.min([m.bounds[0] for m, c, o in P], axis=0)
        hi = np.max([m.bounds[1] for m, c, o in P], axis=0)
        tg = [float(v) for v in (lo + hi) / 2]
        base = P[[i for i, (m, c, o) in enumerate(P) if c == WOOD][0]][0]
        zt = max(m.bounds[1][2] for m, c, o in P if c not in (CLEAR, AMBER))
        closed = (base.extents[0], base.extents[1], zt - lo[2])
        cam = [tg[0] + cam[0], tg[1] + cam[1], tg[2] + cam[2] * 0.55]
        png = export('kule%d' % i, P, L, cam, tg)
        ext = hi - lo
        ext = closed
        res.append((png, info, ext))
        print(info['ad'], 'taban %.0f x %.0f, yukseklik %.0f mm' % tuple(ext))

        fig = plt.figure(figsize=(20, 11.5))
        ax = fig.add_axes([0.0, 0.0, 0.6, 0.93])
        ax.imshow(crop(Image.open(png)))
        ax.axis('off')
        fig.text(0.01, 0.965, '%s  —  taban %.0f × %.0f mm, yükseklik %.0f mm (kapalı, ayaklar dahil)' % (info['ad'], *ext),
                 fontsize=19, fontweight='bold')
        y = 0.88
        fig.text(0.62, y, 'Katlar (aşağıdan yukarı)', fontsize=15, fontweight='bold')
        y -= 0.035
        for n, h in info['floors']:
            fig.text(0.63, y, '%-28s %4.0f mm' % (n, h), fontsize=13, family='DejaVu Sans Mono')
            y -= 0.03
        y -= 0.02
        fig.text(0.62, y, 'Kullanım akışı', fontsize=15, fontweight='bold')
        y -= 0.035
        for s in info['akış']:
            for ln in textwrap.wrap(s, 68, subsequent_indent='   '):
                fig.text(0.63, y, ln, fontsize=12.5)
                y -= 0.027
            y -= 0.004
        y -= 0.02
        for title, items, mark in (('Artılar', info['arti'], '+'), ('Eksiler', info['eksi'], '−')):
            fig.text(0.62, y, title, fontsize=15, fontweight='bold')
            y -= 0.035
            for s in items:
                for ln in textwrap.wrap(mark + ' ' + s, 68, subsequent_indent='   '):
                    fig.text(0.63, y, ln, fontsize=12.5)
                    y -= 0.027
                y -= 0.004
            y -= 0.02
        fig.savefig(os.path.join(HERE, 'kule-detay-%d.png' % i), dpi=80)
        plt.close(fig)

    fig = plt.figure(figsize=(20, 22))
    for n, (png, info, ext) in enumerate(res):
        ax = fig.add_axes([0.02 + (n % 2) * 0.49, 0.50 - (n // 2) * 0.48, 0.47, 0.44])
        ax.imshow(crop(Image.open(png)))
        ax.axis('off')
        ax.set_title('%s  —  %.0f × %.0f × %.0f mm' % (info['ad'], *ext), fontsize=16, fontweight='bold', loc='left')
        ax.text(0, -0.02, 'taban G × D × yükseklik, kapalı', transform=ax.transAxes, fontsize=11, va='top')
    fig.suptitle('Kule: 4 detay konsepti (pozlama + delme + hot plate tek gövdede)', fontsize=20, y=0.99)
    fig.savefig(os.path.join(HERE, 'kule.png'), dpi=80)
    print('->', os.path.join(HERE, 'kule.png'))


if __name__ == '__main__':
    main()
