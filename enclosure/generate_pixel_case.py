#!/usr/bin/env python3
"""
MagPanel PIKSEL-IZGARA kasası — 320x480 P4, 80x120 piksel.

Görüntü/yazı paneli için: her LED kendi kare gözünde (80x120 = 9600 hücre),
P4 = 4mm adım. Kapalı ince difüzör ön yüz → her piksel "dolu kare" olarak parlar,
0.8mm ızgara duvarları pikselleri ayırır (kontrast + bulaşma yok).

Bölme: 2x2 fayans. Dikiş çizgileri tam bir ızgara duvarına denk gelir → GÖRÜNMEZ.
Çıktı Elegoo Saturn 3 Ultra'ya (218.88 x 122.88 x 260) DİK basıldığında sığar;
4 fayans tek plakaya dizilir (saturn_plate_4tiles_standing.stl).

Gereksinim:  pip install trimesh manifold3d numpy
Kullanım:    python3 generate_pixel_case.py     # stl_pixel/ üretir

Tüm ölçüler mm. Z=0 ön difüzör yüzü, +Z arkaya (LED/duvar) doğru.
⚠️ HİZALAMA: ızgara tam 4.0mm adım / 320x480 aktif alan varsayar; gözler
   LED'lere birebir denk gelmeli. Panelin gerçek pitch'ini ÖLÇ/DOĞRULA.
"""
import os
import time
import numpy as np
import trimesh

# ----------------------------------------------------------------------------
P = dict(
    pitch=4.0, nx=80, ny=120,   # P4, 80x120 piksel  -> aktif 320x480
    wall=0.8,                   # ızgara duvarı (delik/hücre = 4.0-0.8 = 3.2mm kare)
    t_front=0.7,                # kapalı ön difüzör kalınlığı
    grid_d=4.0,                 # hücre derinliği (difüzör <-> LED boşluğu)
    pocket_d=14.0,              # panel gövdesi yuvası
    clr=0.5, w_out=2.4,         # panel boşluğu / dış duvar
    cable_w=16.0,               # üst kenar kablo çıkışı
    split_x=2, split_y=2,       # fayans ızgarası
)


def deriv(P):
    d = dict(P)
    d['AW'] = P['nx'] * P['pitch']
    d['AH'] = P['ny'] * P['pitch']
    d['pocket_W'] = d['AW'] + 2 * P['clr']
    d['pocket_H'] = d['AH'] + 2 * P['clr']
    d['OW'] = d['pocket_W'] + 2 * P['w_out']
    d['OH'] = d['pocket_H'] + 2 * P['w_out']
    d['total'] = P['t_front'] + P['grid_d'] + P['pocket_d']
    return d


def box(ex, ey, ez, cx=0, cy=0, cz=0):
    b = trimesh.creation.box(extents=[ex, ey, ez])
    b.apply_translation([cx, cy, cz])
    return b


def bx(x0, x1, y0, y1, z0, z1):
    return box(x1 - x0, y1 - y0, z1 - z0, (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)


def build_full(P):
    d = deriv(P)
    AW, AH, OW, OH, T = d['AW'], d['AH'], d['OW'], d['OH'], d['total']
    wo, tf, gd, wall = P['w_out'], P['t_front'], P['grid_d'], P['wall']
    gz = tf + gd
    parts = [box(OW, OH, tf, cz=tf / 2)]                                    # kapalı difüzör ön
    parts.append(box(OW, OH, T, cz=T / 2).difference(
        box(d['pocket_W'], d['pocket_H'], T + 1, cz=T / 2)))               # çerçeve
    for x in np.linspace(-AW / 2, AW / 2, P['nx'] + 1):                    # ızgara duvarları (X)
        parts.append(box(wall, d['pocket_H'] + 1.6 * wo, gz, x, 0, gz / 2))
    for y in np.linspace(-AH / 2, AH / 2, P['ny'] + 1):                    # ızgara duvarları (Y)
        parts.append(box(d['pocket_W'] + 1.6 * wo, wall, gz, 0, y, gz / 2))
    case = trimesh.boolean.union(parts)
    case = case.difference(box(P['cable_w'], wo * 3, P['pocket_d'] + 2,
                               cy=OH / 2 - wo / 2, cz=gz + P['pocket_d'] / 2 + 1))   # kablo çıkışı
    return case, d


def split_tiles(case, d):
    """2x2 çeyrek kesim — dikiş x=0,y=0 (ızgara duvarına denk, görünmez)."""
    T = d['total']
    tiles = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, x1 = (-4000, 0) if sx < 0 else (0, 4000)
            y0, y1 = (-4000, 0) if sy < 0 else (0, 4000)
            tiles[(sx, sy)] = case.intersection(bx(x0, x1, y0, y1, -2, T + 2))
    return tiles


def saturn_layout(tiles, d):
    """4 fayansı DİK durur şekilde tek Saturn plakasına diz (218.88x122.88x260)."""
    Rx = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
    plate = []
    for i, k in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1)]):
        m = tiles[k].copy()
        m.apply_translation(-tiles[k].centroid)
        m.apply_transform(Rx)                              # 243mm yükseklik -> Z
        m.apply_translation([0, i * (d['total'] + 8), 0])  # kalınlık yönünde diz
        plate.append(m)
    layout = trimesh.util.concatenate(plate)
    c = layout.bounds.mean(0)
    layout.apply_translation([-c[0], -c[1], -layout.bounds[0][2]])
    return layout


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stl_pixel')
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    case, d = build_full(P)
    assert case.is_watertight
    case.export(os.path.join(out, 'full_reference.stl'))
    tiles = split_tiles(case, d)
    nm = {(-1, -1): 'tile_BL', (1, -1): 'tile_BR', (-1, 1): 'tile_TL', (1, 1): 'tile_TR'}
    for k, t in tiles.items():
        assert t.is_watertight, f"{nm[k]} watertight degil"
        t.export(os.path.join(out, nm[k] + '.stl'))
    lay = saturn_layout(tiles, d)
    lay.export(os.path.join(out, 'saturn_plate_4tiles_standing.stl'))
    print(f"OK ({time.time()-t0:.0f}s) -> {out}")
    print(f"Dis olcu : {d['OW']:.1f} x {d['OH']:.1f} x {d['total']:.1f} mm")
    print(f"Aktif    : {d['AW']:.0f} x {d['AH']:.0f}  ({P['nx']}x{P['ny']}={P['nx']*P['ny']} hucre, "
          f"{P['pitch']}mm adim, {P['pitch']-P['wall']:.1f}mm kare)")
    print(f"On difuzor {P['t_front']}mm | izgara duvar {P['wall']}mm | derinlik {P['grid_d']}mm")
    print(f"Fayans (2x2): {tiles[(-1,-1)].extents[0]:.1f} x {tiles[(-1,-1)].extents[1]:.1f} x {d['total']:.1f} mm")
    print(f"Saturn dizilim: {lay.extents[0]:.1f} x {lay.extents[1]:.1f} x {lay.extents[2]:.1f}  "
          f"(plaka 218.88 x 122.88 x 260) -> DIK bas")


if __name__ == '__main__':
    main()
