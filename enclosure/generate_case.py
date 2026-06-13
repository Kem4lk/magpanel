#!/usr/bin/env python3
"""
MagPanel difüzör kasası — parametrik üretici (320x480 mm / P4 / 80x120px).

Orijinal "case20mm.stl" (162x162x32 mm, kare, ince kabuk difüzör + egg-crate
takviye) tasarım dilini koruyarak 320x480 mm panele uyarlanmış; aspect-ratio
1:1 -> 2:3 değiştiği için basit ölçekleme yerine PARAMETRİK olarak yeniden
üretilir. Çıktı: 2x2 fayans (baskı yatağına sığsın) + 5 ek plaka (splice).

Gereksinim:  pip install trimesh manifold3d numpy
Kullanım:    python3 generate_case.py            # STL'leri ./stl/ içine üretir

Tüm ölçüler mm. Z=0 ön difüzör yüzü, +Z arkaya (duvara) doğru.
"""
import os
import numpy as np
import trimesh

# ----------------------------------------------------------------------------
# PARAMETRELER  (panel/yazıcı değiştikçe burayı düzenle)
# ----------------------------------------------------------------------------
P = dict(
    panel_W=320.0, panel_H=480.0,   # LED modül dış ölçüsü (= aktif alan kabul edildi)
    clr=0.75,                       # panel çevresi boşluk (kenar başına)
    w_out=2.4,                      # dış çevre duvar kalınlığı
    t_front=1.2,                    # kapalı ön difüzör kabuğu (ışık süzülür)
    egg_h=16.0,                     # egg-crate yüksekliği = difüzör<->LED ışık boşluğu
    pocket_d=14.0,                  # panel gövdesini tutan yuva derinliği
    rib_t=1.2,                      # egg-crate kaburga kalınlığı
    n_cells_x=16,                   # genişlik boyunca hücre sayısı (orijinal görünüm)
    cable_w=16.0, cable_h=12.0,     # üst kenar kablo çıkış yuvası
    # --- bölme / birleşim ---
    split_x=2, split_y=2,           # fayans ızgarası (şu an 2x2 varsayılır)
    plate_th=3.0,                   # ek plaka kalınlığı
    boss_r=5.0,                     # vida bossu yarıçapı (Ø10)
    pilot_r=1.25,                   # M3 kendinden kılavuz delik Ø2.5
    clr_r=1.7,                      # M3 geçme Ø3.4
    head_r=3.0, head_d=2.0,         # M3 baş havşası Ø6 x 2
)


def derived(P):
    d = dict(P)
    d['pocket_W'] = P['panel_W'] + 2 * P['clr']
    d['pocket_H'] = P['panel_H'] + 2 * P['clr']
    d['OW'] = d['pocket_W'] + 2 * P['w_out']
    d['OH'] = d['pocket_H'] + 2 * P['w_out']
    d['total_d'] = P['t_front'] + P['egg_h'] + P['pocket_d']
    d['rest'] = P['t_front'] + P['egg_h']          # panelin oturduğu düzlem (kaburga üstü)
    d['pitch'] = d['pocket_W'] / P['n_cells_x']
    return d


# --- küçük yardımcılar (eksen hizalı kutu / silindir) -----------------------
def box(ex, ey, ez, cx=0, cy=0, cz=0):
    b = trimesh.creation.box(extents=[ex, ey, ez])
    b.apply_translation([cx, cy, cz])
    return b


def bx(x0, x1, y0, y1, z0, z1):
    return box(x1 - x0, y1 - y0, z1 - z0, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)


def vcyl(r, z0, z1, cx, cy, sec=32):
    c = trimesh.creation.cylinder(radius=r, height=z1 - z0, sections=sec)
    c.apply_translation([cx, cy, (z0 + z1) / 2])
    return c


# ----------------------------------------------------------------------------
# 1) TAM (tek parça) kasa
# ----------------------------------------------------------------------------
def build_full(P):
    d = derived(P)
    OW, OH, T = d['OW'], d['OH'], d['total_d']
    tf, eh, wo = P['t_front'], P['egg_h'], P['w_out']
    pW, pH = d['pocket_W'], d['pocket_H']
    ztop = tf + eh
    parts = []
    parts.append(box(OW, OH, tf, cz=tf / 2))                                   # ön difüzör kabuğu
    ring = box(OW, OH, T, cz=T / 2).difference(box(OW - 2 * wo, OH - 2 * wo, T + 1, cz=T / 2))
    parts.append(ring)                                                          # dış duvar çerçevesi
    rt = P['rib_t']
    for x in np.linspace(-pW / 2, pW / 2, P['n_cells_x'] + 1):                  # X kaburgalar
        parts.append(box(rt, pH + 1.2 * wo, ztop, cx=x, cz=ztop / 2))
    ny = int(round(pH / d['pitch']))
    for y in np.linspace(-pH / 2, pH / 2, ny + 1):                             # Y kaburgalar
        parts.append(box(pW + 1.2 * wo, rt, ztop, cy=y, cz=ztop / 2))
    case = trimesh.boolean.union(parts)
    notch = box(P['cable_w'], wo * 3, P['pocket_d'] + 2,
                cy=OH / 2 - wo / 2, cz=ztop + P['pocket_d'] / 2 + 1)            # kablo çıkışı
    return case.difference(notch), d


# ----------------------------------------------------------------------------
# 2) Vida noktaları + ek plaka ayak izleri  (2x2 için)
# ----------------------------------------------------------------------------
def screw_points(d):
    OW, OH, cc = d['OW'], d['OH'], 8.0
    return {
        'center': [(sx * cc, sy * cc) for sx in (-1, 1) for sy in (-1, 1)],
        'Vtop':   [(-cc,  OH / 4), (cc,  OH / 4)],
        'Vbot':   [(-cc, -OH / 4), (cc, -OH / 4)],
        'Hrt':    [(OW / 4, -cc), (OW / 4,  cc)],
        'Hlf':    [(-OW / 4, -cc), (-OW / 4,  cc)],
    }


def plate_footprints(d):
    OW, OH = d['OW'], d['OH']
    return {
        'center': (-18, 18, -18, 18),
        'Vtop':   (-18, 18,  OH / 4 - 12,  OH / 4 + 12),
        'Vbot':   (-18, 18, -OH / 4 - 12, -OH / 4 + 12),
        'Hrt':    (OW / 4 - 12, OW / 4 + 12, -18, 18),
        'Hlf':    (-OW / 4 - 12, -OW / 4 + 12, -18, 18),
    }


# ----------------------------------------------------------------------------
# 3) 2x2 fayanslar  (çeyrek kesim + plaka yuvası + bosslar + kılavuz delik)
# ----------------------------------------------------------------------------
def build_tiles(P):
    case, d = build_full(P)
    rz = d['rest'] - P['plate_th']
    pts, foot = screw_points(d), plate_footprints(d)
    BIG = 4000.0
    tiles = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, x1 = (-BIG, 0) if sx < 0 else (0, BIG)
            y0, y1 = (-BIG, 0) if sy < 0 else (0, BIG)
            t = case.intersection(bx(x0, x1, y0, y1, -2, d['total_d'] + 2))
            subs = []
            for (fx0, fx1, fy0, fy1) in foot.values():                          # plaka yuvaları
                rx0, rx1 = max(fx0, x0), min(fx1, x1)
                ry0, ry1 = max(fy0, y0), min(fy1, y1)
                if rx1 - rx0 > 0.5 and ry1 - ry0 > 0.5:
                    subs.append(bx(rx0, rx1, ry0, ry1, rz, d['total_d'] + 2))
            if subs:
                t = trimesh.boolean.difference([t] + subs)
            adds = [vcyl(P['boss_r'], 0, rz, px, py)                            # bosslar
                    for pl in pts.values() for (px, py) in pl if x0 <= px <= x1 and y0 <= py <= y1]
            if adds:
                t = trimesh.boolean.union([t] + adds)
            holes = [vcyl(P['pilot_r'], 2.0, rz + 0.2, px, py)                  # kılavuz delikler
                     for pl in pts.values() for (px, py) in pl if x0 <= px <= x1 and y0 <= py <= y1]
            if holes:
                t = trimesh.boolean.difference([t] + holes)
            tiles[(sx, sy)] = t
    return tiles, d


# ----------------------------------------------------------------------------
# 4) Ek plakalar (arkadan dikey vidayla fayansları birbirine kenetler)
# ----------------------------------------------------------------------------
def build_plates(d, P):
    rz = d['rest'] - P['plate_th']
    pts, foot = screw_points(d), plate_footprints(d)
    plates = {}
    for name, (fx0, fx1, fy0, fy1) in foot.items():
        pl = bx(fx0, fx1, fy0, fy1, rz, d['rest'])
        subs = []
        for (px, py) in pts[name]:
            subs.append(vcyl(P['clr_r'], rz - 1, d['rest'] + 1, px, py))
            subs.append(vcyl(P['head_r'], d['rest'] - P['head_d'], d['rest'] + 1, px, py))
        plates[name] = trimesh.boolean.difference([pl] + subs)
    return plates


# ----------------------------------------------------------------------------
def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stl')
    os.makedirs(out, exist_ok=True)
    full, d = build_full(P)
    full.export(os.path.join(out, 'full_case_1piece.stl'))
    tiles, d = build_tiles(P)
    plates = build_plates(d, P)
    names = {(-1, -1): 'tile_bottom_left', (1, -1): 'tile_bottom_right',
             (-1, 1): 'tile_top_left', (1, 1): 'tile_top_right'}
    vol = full.volume * 0
    for k, t in tiles.items():
        t.export(os.path.join(out, names[k] + '.stl'))
        vol += t.volume
        assert t.is_watertight, f"{names[k]} watertight degil!"
    for nm, p in plates.items():
        p.export(os.path.join(out, 'splice_' + nm + '.stl'))
        vol += p.volume
    print(f"OK -> {out}")
    print(f"Dis olcu : {d['OW']:.1f} x {d['OH']:.1f} x {d['total_d']:.1f} mm")
    print(f"Fayans   : {tiles[(-1,-1)].extents[0]:.1f} x {tiles[(-1,-1)].extents[1]:.1f} mm  (2x2)")
    print(f"Panel yuvasi: {d['pocket_W']:.1f} x {d['pocket_H']:.1f} x {P['pocket_d']:.1f} mm")
    print(f"Plastik  : ~{vol/1000:.0f} cm3  (~{vol/1000*1.24:.0f} g PLA)")


if __name__ == '__main__':
    main()
