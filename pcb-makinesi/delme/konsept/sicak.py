#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pozlama + hot plate urunu: 3 yerlesim (eskiz, olculer modelden). Termal kural: LCD <= 70 °C, hot plate ~250 °C.
  H1 Ustten pozlama kupu: kaset cekmecesi altta (bakir yukari), LCD asagi bakar, isik motoru ustte, catida hot plate
  H2 Alcak yan yana: solda matris LED pozlama (LCD ustte, UV kapak), sagda hot plate, arada yalitimli duvar
  H3 Alcak kup: matris LED + cekmece, yalitim + fanli hava boslugu, catida hot plate
Cikti: sicak1..3.html/png, sicak-detay-1..3.png, sicak.png.   python3 sicak.py
"""
import os
import sys
import textwrap

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import gen_delme as g   # noqa: E402
import kule as ku      # noqa: E402

box, cyl = g.box, g.cyl
add, F = ku.add, ku.F
INS = '#efe9d8'          # seramik elyaf / kalsiyum silikat yalitim


def insul(P, L, x0, x1, y0, y1, z0, t=10, label='Yalıtım (kalsiyum silikat 10 mm)'):
    add(P, box(x0, x1, y0, y1, z0, z0 + t), INS)
    if label:
        L.append((label, (x1, y0, z0 + t)))
    return z0 + t


def gap_fan(P, L, x0, x1, y0, y1, z0, h=25):
    """Fanli hava boslugu: yandan iki 60 mm fan, karsi yanda cikis."""
    for sy in (-1, 1):
        add(P, box(x1 - 3, x1, sy * 45 - 30, sy * 45 + 30, z0, z0 + h), ku.DARK)
    for i in range(6):
        y = y0 + 25 + i * (y1 - y0 - 50) / 5
        add(P, box(x0, x0 + 3, y - 3, y + 3, z0 + 3, z0 + h - 3), ku.RUB)
    L.append(('Fanlı hava boşluğu', (x1, y0 + 30, z0 + h)))
    return z0 + h


def H1():
    P, L = [], []
    X0, X1, Y0, Y1 = -140, 140, -115, 115
    ku.feet(P, X0, X1, Y0, Y1, -6)
    add(P, box(X0, X1, Y0, Y1, -6, 0), ku.WOOD)
    ku.drawer(P, L, 0, -15, 4, label='Kaset çekmecesi (bakır yukarı)')
    add(P, box(-100, -90, -170, -150, 4, 40), ku.RED)
    L.append(('Kaldırma kolu (kaset LCD\'ye değer)', (-90, -170, 40)))
    lcd_bottom = 34.0
    z0 = lcd_bottom + 63.3 + F
    ku.light_engine(P, L, 0, -15, z0, up=False)
    ku.electronics_back(P, L, 0, Y1, 40)
    top = z0 + 6
    ku.frame(P, X0, X1, Y0, Y1, 0, top)
    ku.panels(P, X0, X1, Y0, Y1, 0, top)
    ku.vents(P, X0, -70, 40, top - 40, side=-1)
    ku.vents(P, X1, -70, 40, top - 40)
    L.append(('Fan çıkışı (yanlar)', (X1, 40, top - 5)))
    ku.control_panel(P, L, X1, -40, 50)
    add(P, box(X0, X1, Y0, Y1, top, top + 4), ku.WOOD)
    zi = insul(P, L, -105, 105, -80, 80, top + 4)
    ht = ku.hotplate(P, L, 0, 0, zi)
    info = dict(
        ad='H1. Üstten pozlama küpü', mesafe='LCD ↔ hot plate ≈ %.0f mm (arada ışık motoru)' % (zi + 24 - lcd_bottom),
        floors=[('Ayak + taban', 16), ('Kaset çekmecesi', lcd_bottom), ('Işık motoru (LCD aşağı)', z0 - lcd_bottom),
                ('Çatı + yalıtım + hot plate', ht - z0)],
        akış=['1  Plaketi kasete pimlerle tak (bakır YUKARI), çekmeceyi kapat, kolu indir → kaset LCD\'ye değer → pozlama',
              '2  Islak işlem (ayrı) → delme (ayrı modül, aynı pimler, bakır yine yukarı)',
              '3  Montaj → çatıdaki hot plate ile reflow'],
        arti=['Isı yukarı, LCD en altta: aralarında ~230 mm ve ışık motoru var (termal olarak en güvenli)',
              'Bakır her adımda yukarı: kaset, delme ve hot plate aynı yönde',
              'Gerçek küpe en yakın: 280 × 230 × ~290 mm'],
        eksi=['Kaseti LCD\'ye bastıran kaldırma mekanizması gerekir (kam/kol)',
              'LED soğutucusu sıcak havayı hot plate\'e doğru verir: fan çıkışı yana alınmalı'])
    return P, L, info, (640, -780, 420)


def H2():
    P, L = [], []
    ku.feet(P, -330, 140, -115, 115, -6)
    add(P, box(-330, 140, -115, 115, -6, 0), ku.WOOD)
    # sol: matris LED pozlama
    top = ku.matrix_light(P, L, -190, -5, 2)
    ku.frame(P, -330, -50, -115, 115, 0, top + 2)
    ku.panels(P, -330, -50, -115, 115, 0, top + 2)
    lid = box(-320, -60, 112, 115, top + 2, top + 180)
    add(P, lid, ku.AMBER, 0.45)
    L.append(('UV kapak (açık)', (-190, 115, top + 180)))
    # orta yalitimli duvar
    add(P, box(-50, -38, -115, 115, 0, top + 2), INS)
    L.append(('Yalıtımlı ara duvar', (-44, -115, top + 2)))
    # sag: hot plate kutusu (icinde PSU + SSR + elektronik)
    ku.frame(P, -38, 140, -115, 115, 0, top + 2)
    ku.panels(P, -38, 140, -115, 115, 0, top + 2)
    add(P, box(0, 129, 40, 110, 4, 34), ku.SIL)
    add(P, box(-30, 120, -110, -60, 4, 30), ku.EL)
    L.append(('PSU + SSR + ESP32 + RPi', (120, -110, 30)))
    add(P, box(-38, 140, -115, 115, top + 2, top + 6), ku.WOOD)
    zi = insul(P, [], -10, 100, -80, 80, top + 6)
    ht = ku.hotplate(P, L, 50, 0, zi)
    ku.control_panel(P, L, 140, -40, 10)
    info = dict(
        ad='H2. Alçak yan yana', mesafe='LCD ↔ hot plate yatay ≈ 120 mm + yalıtımlı duvar',
        floors=[('Ayak + taban', 16), ('Pozlama (matris LED)', top), ('Hot plate (gövde üstü)', ht - top)],
        akış=['1  Plaketi LCD\'ye bakır aşağı koy, kapağı kapat → pozlama (reçine yazıcı gibi)',
              '2  Islak işlem → delme (ayrı)', '3  Sağdaki hot plate ile reflow'],
        arti=['Isı kaynağı ile LCD yan yana, üst üste değil: termal ayrım kolay',
              'Alçak (~150 mm): masada "ocak" gibi, ağırlık merkezi düşük',
              'Kaldırma mekanizması yok, en basit mekanik'],
        eksi=['Geniş taban (~470 × 230)', 'Küp değil; matris LED (lens dizisi) tedariki gerekir'])
    return P, L, info, (560, -900, 520)


def H3():
    P, L = [], []
    X0, X1, Y0, Y1 = -140, 140, -115, 115
    ku.feet(P, X0, X1, Y0, Y1, -6)
    add(P, box(X0, X1, Y0, Y1, -6, 0), ku.WOOD)
    top = ku.matrix_light(P, L, 0, -20, 2)
    add(P, box(30, 159, Y1 - 35, Y1 - 3, 2, 34), ku.SIL)
    add(P, box(-135, 25, Y1 - 30, Y1 - 3, 2, 30), ku.EL)
    L.append(('PSU + SSR + ESP32 + RPi (arka)', (95, Y1 - 35, 34)))
    ku.drawer(P, L, 0, -20, top + 1)
    zsep = top + 8
    add(P, box(X0, X1, Y0, Y1, zsep, zsep + 4), ku.WOOD)
    zi = insul(P, L, X0 + 5, X1 - 5, Y0 + 5, Y1 - 5, zsep + 4, t=10)
    zg = gap_fan(P, L, X0 + 5, X1 - 5, Y0, Y1, zi, h=25)
    ku.frame(P, X0, X1, Y0, Y1, 0, zg)
    ku.panels(P, X0, X1, Y0, Y1, 0, zg)
    ku.control_panel(P, L, X1, -40, 5)
    add(P, box(X0, X1, Y0, Y1, zg, zg + 4), ku.WOOD)
    zi2 = insul(P, [], -105, 105, -80, 80, zg + 4, t=6, label='')
    ht = ku.hotplate(P, L, 0, 0, zi2)
    info = dict(
        ad='H3. Alçak küp (matris LED)', mesafe='LCD ↔ hot plate ≈ %.0f mm (yalıtım + fanlı boşluk)' % (zi2 + 24 - top),
        floors=[('Ayak + taban', 16), ('Pozlama (matris LED)', top), ('Çekmece + ayırıcı', zsep + 4 - top),
                ('Yalıtım + fanlı boşluk', zg - zsep - 4), ('Çatı + hot plate', ht - zg)],
        akış=['1  Kasetle pozlama (çekmece, bakır aşağı)', '2  Islak işlem → delme (ayrı)', '3  Çatıdaki hot plate ile reflow'],
        arti=['En küçük: 280 × 230 × ~190 mm', 'Matris LED: Fresnel yok, alçak', 'Tek kutu, tek kapak'],
        eksi=['LCD hot plate\'e ~80 mm: yalıtım + fan + LCD sıcaklık sensörü ve kilit şart, prototipte ölçülmeli',
              'Pozlama ve reflow aynı anda yapılamaz (LCD ısınır)'])
    return P, L, info, (860, -1000, 520)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image

    res = []
    for i, f in enumerate((H1, H2, H3), 1):
        P, L, info, cam = f()
        lo = np.min([m.bounds[0] for m, c, o in P], axis=0)
        hi = np.max([m.bounds[1] for m, c, o in P], axis=0)
        tg = [float(v) for v in (lo + hi) / 2]
        base = P[[n for n, (m, c, o) in enumerate(P) if c == ku.WOOD][0]][0]
        zt = max(m.bounds[1][2] for m, c, o in P if c not in (ku.CLEAR, ku.AMBER))
        ext = (base.extents[0], base.extents[1], zt - lo[2])
        cam = [tg[0] + cam[0], tg[1] + cam[1], tg[2] + cam[2] * 0.55]
        png = ku.export('sicak%d' % i, P, L, cam, tg)
        res.append((png, info, ext))
        print(info['ad'], 'taban %.0f x %.0f, yukseklik %.0f mm |' % ext, info['mesafe'])

        fig = plt.figure(figsize=(20, 11.5))
        ax = fig.add_axes([0.0, 0.0, 0.6, 0.93])
        ax.imshow(ku.crop(Image.open(png)))
        ax.axis('off')
        fig.text(0.01, 0.965, '%s  —  taban %.0f × %.0f mm, yükseklik %.0f mm (kapalı, ayaklar dahil)' % (info['ad'], *ext),
                 fontsize=19, fontweight='bold')
        y = 0.88
        fig.text(0.62, y, info['mesafe'], fontsize=14, fontweight='bold', color='#b03a2e')
        y -= 0.05
        fig.text(0.62, y, 'Katlar (aşağıdan yukarı)', fontsize=15, fontweight='bold')
        y -= 0.035
        for n, h in info['floors']:
            fig.text(0.63, y, '%-28s %4.0f mm' % (n, h), fontsize=13, family='DejaVu Sans Mono')
            y -= 0.03
        for title, items, mark in (('Kullanım akışı', info['akış'], ''), ('Artılar', info['arti'], '+ '),
                                   ('Eksiler', info['eksi'], '− ')):
            y -= 0.02
            fig.text(0.62, y, title, fontsize=15, fontweight='bold')
            y -= 0.035
            for s in items:
                for ln in textwrap.wrap(mark + s, 68, subsequent_indent='   '):
                    fig.text(0.63, y, ln, fontsize=12.5)
                    y -= 0.027
                y -= 0.004
        fig.savefig(os.path.join(HERE, 'sicak-detay-%d.png' % i), dpi=80)
        plt.close(fig)


if __name__ == '__main__':
    main()
