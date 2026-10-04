#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H5 = H4'un gelistirilmis/sadelestirilmis hali: ustten pozlama + doner kaset (R-θ) + sabit delici + catida hot plate.
Yerlesim kisitlardan hesaplanir:
  - delme: disk merkezi y_c = y_s + r, r = 0..R_MAX (plaket kosegeni/2) ; theta 360°
  - pozlama: LCD merkezi = R ekseninin sonu (y_l = y_s + R_MAX) -> ek hareket yok
  - spindle bolgesi Fresnel/LCD bolgesine girmez ; kaset hicbir konumda kutudan cikmaz
  - kaldirma yok: plaket ile LCD cami arasinda sabit GAP (kolimasyon 5° -> kenar bulaniklik = GAP*tan5°)
Cikti: h5.html/png, h5-detay.png.   python3 h5.py
"""
import math
import os
import sys
import textwrap

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import gen_delme as g   # noqa: E402
import kule as ku      # noqa: E402
import sicak as si     # noqa: E402

box, cyl, tube, add, F = g.box, g.cyl, g.tube, ku.add, ku.F

BW, BD = 160.0, 100.0                       # ham plaket
R_MAX = math.hypot(BW / 2, BD / 2)          # 94.3
DISC_R = R_MAX + 3.5                        # pimler ve kenar payi
GAP = 0.5                                   # plaket ust yuzu - LCD cami
COLL = 5.0                                  # isik acisi (Elegoo Saturn 3 Ultra degeri, derece)
SPZ = 30.0                                  # spindle bolgesi yari genisligi (y)
FRES_HALF = 57.5                            # Fresnel yari derinligi (y)
WALL = 3.0


def layout():
    y_s = 0.0
    y_l = y_s + R_MAX
    assert y_l - FRES_HALF >= y_s + SPZ - 25, 'spindle bolgesi Fresnel ile cakisiyor'
    Y0 = y_s - DISC_R - 17                  # 15 mm profil + 2 mm pay
    Y1 = y_l + DISC_R + 17
    sh = -(Y0 + Y1) / 2                     # kutuyu y'de ortala
    return dict(y_s=y_s + sh, y_l=y_l + sh, Y0=Y0 + sh, Y1=Y1 + sh)


def H5():
    P, L = [], []
    lay = layout()
    ys, yl, Y0, Y1 = lay['y_s'], lay['y_l'], lay['Y0'], lay['Y1']
    X0, X1 = -150.0, 150.0
    ku.feet(P, X0, X1, Y0, Y1, -6)
    add(P, box(X0, X1, Y0, Y1, -6, 0), ku.WOOD)

    # R ekseni: iki Ø8 mil + LM8UU, kayis ortada
    for sx in (-1, 1):
        add(P, cyl('y', (sx * 105, 8), 4, Y0 + WALL + 2, Y1 - WALL - 2, seg=20), ku.ROD)
    # R ekseni: T8 vidali mil ortada (arabanin altinda), motor arka panelin DISINDA
    add(P, cyl('y', (0, 6), 4, Y0 + 20, Y1 + 2, seg=20), ku.ALU)
    add(P, cyl('y', (0, 6), 9.5, Y1 + 2, Y1 + 27), ku.ALU)                                  # kaplin
    add(P, g.m28byj((0, Y1 + 37.5, 6), (0, -1, 0), (0, 0, 1)), ku.MOT)
    add(P, box(-26, 26, Y1, Y1 + 37.5, -6, -3), ku.PRINT)
    L.append(('R ekseni: T8 vida + 28BYJ (motor arkada, dışarıda)', (0, Y1 + 30, 34)))
    MOV0 = len(P)

    yc = ys + 40.0                           # gosterim: delme sirasinda
    add(P, box(-108, 108, yc - DISC_R - 1, yc + DISC_R + 1, 12, 15), ku.PRINT)           # araba
    add(P, tube('z', (0, yc), 75, 68, 15, 18), '#777')                                    # lazy susan rulmani
    add(P, cyl('z', (0, yc), DISC_R, 18, 24, seg=96), '#d98c4a')                          # disk
    add(P, tube('z', (0, yc), DISC_R + 0.6, DISC_R - 0.6, 19, 23), '#222')                # kenar kayisi
    add(P, box(-BW / 2, BW / 2, yc - BD / 2, yc + BD / 2, 24, 25.6), ku.PCB)
    for sx in (-1, 1):
        add(P, cyl('z', (sx * 76, yc), 1.5, 24, 25.5, seg=12), ku.ALU)                     # gomme pim (LCD'ye degmez)
    add(P, box(-82, -40, yc - 54, yc - 50, 24, 25.5), '#333')                              # kose dayamasi (plaketten alcak)
    add(P, g.m28byj((-(DISC_R + 8), yc - 40, 26), (0, 0, -1), (-1, 0, 0)), ku.MOT)        # θ motoru, mil asagi
    add(P, g.diff(box(-12, 12, yc - 10, yc + 10, 1, 12), [cyl('y', (0, 6), 6.2, yc - 11, yc + 11)]), ku.PRINT)  # T8 somun yuvasi
    add(P, g.tube('y', (0, 6), 6, 4.05, yc - 8, yc + 8), '#c9a227')
    MOV1 = len(P)
    L += [('Döner disk: lazy susan + kenar kayışı (16:1)', (DISC_R, yc, 22)),
          ('Pimler + köşe dayaması', (-82, yc - 52, 27))]

    # isik motoru (asagi bakar), LCD alti = plaket ustu + GAP
    lcd_bottom = 25.6 + GAP
    z0 = lcd_bottom + 63.3 + F
    ku.light_engine(P, L, 0, yl, z0, up=False)
    add(P, box(-88, 88, yl - FRES_HALF - 6, yl - FRES_HALF - 3, lcd_bottom, lcd_bottom + 6), '#222')   # firca dudagi
    L.append(('Fırça dudağı (LCD önü)', (88, yl - FRES_HALF - 4, lcd_bottom + 6)))
    add(P, box(-79, 79, yl - 51, yl + 51, lcd_bottom - 0.1, lcd_bottom), '#e8f4ff', 0.5)  # degisir koruma filmi

    # sabit delici
    tip = 25.6 - 2.2
    nose = tip + 28
    add(P, cyl('z', (0, ys), 0.4, tip, nose + 10, seg=12), '#e0e0e0')
    add(P, cyl('z', (0, ys), 9.5, nose, nose + 32), ku.ALU)
    add(P, cyl('z', (0, ys), 21, nose + 36, nose + 103), ku.MOT)
    for sx in (-1, 1):
        add(P, cyl('z', (sx * 30, ys - 22), 4, nose + 20, nose + 125, seg=20), ku.ROD)
    add(P, box(-40, 40, ys - 32, ys - 12, nose + 50, nose + 95), ku.PRINT)
    add(P, box(-45, 45, Y0 + WALL, ys - 12, nose + 125, nose + 135), ku.PRINT)
    zm = nose + 150
    add(P, g.m28byj((0, ys - 22, zm), (0, 0, -1), (0, -1, 0)), ku.MOT)
    add(P, tube('z', (0, ys), 17, 14, tip + 4, nose - 2), '#555', 0.7)                    # vakum agzi
    add(P, cyl('x', (ys, nose - 10), 6, -90, 0, seg=20), '#555', 0.6)                      # vakum hortumu: sola
    add(P, cyl('y', (-90, nose - 10), 6, ys, Y1 - WALL, seg=20), '#555', 0.6)              # ... ve arkaya (Fresnel disi)
    L += [('Sabit delici (yalnız Z)', (40, ys - 32, nose + 95)), ('Vakum ağzı → arka bağlantı', (-90, ys + 40, nose - 4))]

    # elektronik + panel
    add(P, box(110, 146, Y1 - 110, Y1 - 20, 30, 110), ku.EL)
    L.append(('Elektronik (sağ arka)', (110, Y1 - 110, 110)))
    top = max(z0, zm + 19) + 6
    ku.frame(P, X0, X1, Y0, Y1, 0, top)
    ku.panels(P, X0, X1, Y0, Y1, 0, top, front=False, op=0.10)
    add(P, box(X0 + 15, X1 - 15, Y0 - 1, Y0 + 2, 15, top - 15), ku.AMBER, 0.14)            # turuncu on kapak
    L.append(('Tek kapak (turuncu PC) + kilit anahtarı', (X1 - 15, Y0, top - 15)))
    ku.control_panel(P, L, X1, Y0 + 60, 40)
    ku.vents(P, X0, yl - 40, yl + 40, top - 45, side=-1)
    ku.vents(P, X1, yl - 40, yl + 40, top - 45)
    add(P, box(X0, X1, Y0, Y1, top, top + 4), ku.WOOD)
    zi = si.insul(P, [], -105, 105, -80, 80, top + 4, label='')
    ht = ku.hotplate(P, L, 0, 0, zi)
    L = [l for l in L if l[0] not in ('Soğutucu + fan', 'Fresnel mercek', 'Dokunmatik ekran + acil stop')]
    return P, L, lay, dict(top=top, ht=ht, lcd_bottom=lcd_bottom, z0=z0, mov=(MOV0, MOV1), yc=yc)


DEGISIKLIK = [
    ('Kaset dışarı taşıyordu', 'Yerleşim kısıtlardan hesaplanıyor; kaset hiçbir konumda kutudan çıkmıyor, ön tek kapak kapalı çalışır'),
    ('Pozlama için ayrı konum', 'LCD, R ekseninin tam sonunda: pozlama = R en arkada, ek hareket/eksen yok'),
    ('Kaldırma kolu/mekanizması', 'Kaldırılır: plaket ile LCD arasında sabit %.1f mm boşluk (5° ışıkta kenar bulanıklığı ~%.2f mm)' % (GAP, GAP * math.tan(math.radians(COLL)))),
    ('Talaş LCD altına taşınıyordu', 'Önce delme, sonra lak + pozlama. Delici vakum ağzı + LCD önünde fırça dudağı + değişir koruma filmi'),
    ('Pim delikleri ön koşuldu', 'Ham plaket köşe dayamasına yaslanır, makine 2 pim deliğini kendisi deler, sonra pimler takılır'),
    ('Lak kurutma için ayrı fırın', 'Hot plate 70 °C\'de Positiv 20 kurutur (aynı cihaz, iki iş)'),
    ('R ekseni kayışlı, motor kutunun içinde', 'T8 vida arabanın altında, motor arka panelin dışında: iç hacim tamamen kasete kalır, 0,004 mm/adım, kendiliğinden kilitli'),
    ('Disk mili ve yataklama', 'Lazy susan rulmanı + merkez pim: ucuz, düz, geniş taban'),
    ('Pim/dayama LCD\'ye çarpabilirdi', 'Pimler ve köşe dayaması plaket yüzeyinin altında (gömme): 0,5 mm boşlukta hiçbir şey çıkıntı yapmaz'),
]
AKIS = ['1  Ham plaketi diske, köşe dayamasına yasla → makine 2 pim deliğini deler → pimleri tak',
        '2  Excellon dosyası: delikler (R-θ), vakum açık',
        '3  Plaketi çıkar, temizle, Positiv 20 sprey → çatıdaki hot plate\'te 70 °C kurut',
        '4  Pimlere geri tak → R en arkaya → LCD pozlama (aynı pimler, delik ↔ ped ofseti bir kez kalibre)',
        '5  Banyo / aşındırma / sökme (ıslak, ayrı) → montaj → hot plate reflow']
RISK = ['R hızı ~2 mm/s (T8×8): delikler önce r\'ye sonra θ\'ya göre sıralanmalı; 100 delik ≈ 10 dk','Plaket eğriliği 0,5 mm boşluğu kapatabilir: koruma filmi sarf, gerekirse 1 mm boşluk (~0,09 mm bulanıklık)',
        'R-θ yazılımı + disk merkez/indeks kalibrasyonu (θ sıfırı için optik/hall sensörü)',
        'Delici titreşimi: delici braketi çerçeveye, ışık motoru ayrı askıya']


def plan(ax, lay):
    from matplotlib.patches import Circle, Rectangle
    Y0, Y1, ys, yl = lay['Y0'], lay['Y1'], lay['y_s'], lay['y_l']
    ax.add_patch(Rectangle((-150, Y0), 300, Y1 - Y0, fill=False, lw=1.5))
    ax.add_patch(Rectangle((-82.5, yl - FRES_HALF), 165, 2 * FRES_HALF, fc='#9fd3ff', alpha=.4, ec='#357'))
    ax.add_patch(Rectangle((-77, yl - 49.5), 154, 99, fc='#1d2733', alpha=.6))
    for yc, ls, col in ((ys, '--', '#c0392b'), (yl, '-', '#d98c4a')):
        ax.add_patch(Circle((0, yc), DISC_R, fill=False, ls=ls, ec=col, lw=1.4))
    ax.add_patch(Circle((0, ys), 21, fc='#3d6fb6'))
    ax.annotate('', xy=(0, ys), xytext=(0, yl), arrowprops=dict(arrowstyle='<->', lw=1.2))
    ax.text(4, (ys + yl) / 2, 'R %.0f mm' % (yl - ys), fontsize=10)
    ax.text(-146, Y1 - 14, 'Üstten plan: %.0f × %.0f mm' % (300, Y1 - Y0), fontsize=10)
    ax.text(26, ys - 6, 'delici', fontsize=9, color='#3d6fb6')
    ax.text(-75, yl + 52, 'LCD + Fresnel', fontsize=9)
    ax.text(-150, Y0 - 16, 'kesikli: delme başı (r = 0)   düz: pozlama (r = R)', fontsize=9)
    ax.set_xlim(-160, 160)
    ax.set_ylim(Y0 - 22, Y1 + 5)
    ax.set_aspect('equal')
    ax.axis('off')


def check(P, lay, z):
    """Kaset grubunu R boyunca 13 konumda gezdirip sabit parcalarla kesisim hacmine bakar (seffaf paneller haric)."""
    a, b = z['mov']
    bad = []
    for yc in np.linspace(lay['y_s'], lay['y_l'], 13):
        d = yc - z['yc']
        for i in range(a, b):
            m = P[i][0].copy()
            m.apply_translation([0, d, 0])
            for j, (s, c, o) in enumerate(P):
                if a <= j < b or o < 0.9 or c in ('#e0e0e0',):
                    continue
                v = g.inter_vol(m, s)
                if v > 0.5:
                    bad.append((i, P[i][1], j, c, round(yc, 1), round(v, 1)))
    return bad


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image

    P, L, lay, z = H5()
    bad = check(P, lay, z)
    print('carpisma kontrolu:', 'temiz' if not bad else bad[:10])
    lo = np.min([m.bounds[0] for m, c, o in P], axis=0)
    hi = np.max([m.bounds[1] for m, c, o in P], axis=0)
    zt = max(m.bounds[1][2] for m, c, o in P if c not in (ku.CLEAR, ku.AMBER))
    ext = (300.0, lay['Y1'] - lay['Y0'], zt - lo[2])
    tg = [float(v) for v in (lo + hi) / 2]
    png = ku.export('h5', P, L, [tg[0] + 760, tg[1] - 900, tg[2] + 260], tg)
    print('H5 taban %.0f x %.0f, yukseklik %.0f mm | y_s %.1f y_l %.1f | LCD-hot plate %.0f mm'
          % (ext[0], ext[1], ext[2], lay['y_s'], lay['y_l'], z['top'] + 4 + 10 + 24 - z['lcd_bottom']))

    fig = plt.figure(figsize=(20, 14))
    ax = fig.add_axes([0.0, 0.30, 0.56, 0.63])
    ax.imshow(ku.crop(Image.open(png)))
    ax.axis('off')
    fig.text(0.01, 0.962, 'H5 (H4 geliştirilmiş)  —  taban %.0f × %.0f mm, yükseklik %.0f mm (kapalı, ayaklar dahil)' % ext,
             fontsize=19, fontweight='bold')
    y = 0.90
    fig.text(0.575, y, 'H4 → H5', fontsize=15, fontweight='bold')
    y -= 0.032
    for eski, yeni in DEGISIKLIK:
        lines = textwrap.wrap('• %s → %s' % (eski, yeni), 82, subsequent_indent='   ')
        for ln in lines:
            fig.text(0.58, y, ln, fontsize=11.5)
            y -= 0.024
        y -= 0.004
    for title, items in (('Kullanım akışı', AKIS), ('Açık riskler', RISK)):
        y -= 0.015
        fig.text(0.575, y, title, fontsize=15, fontweight='bold')
        y -= 0.032
        for s in items:
            for ln in textwrap.wrap(s, 82, subsequent_indent='   '):
                fig.text(0.58, y, ln, fontsize=11.5)
                y -= 0.024
            y -= 0.004
    pax = fig.add_axes([0.08, 0.0, 0.40, 0.29])
    plan(pax, lay)
    fig.savefig(os.path.join(HERE, 'h5-detay.png'), dpi=80)
    print('->', os.path.join(HERE, 'h5-detay.png'))


if __name__ == '__main__':
    main()
