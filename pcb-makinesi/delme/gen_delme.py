#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCB delme makinesi v0, parametrik tasarim (tek kaynak).

Mimari: sabit spindle + hareketli capraz tabla (alt eksen Y, ust eksen X), 28BYJ-48 + GT2 kayis,
Z = 28BYJ-48 + T8 trapez mil, spindle = 775 DC motor + JT0 mandren, kontrol ESP32-S3 + 3x ULN2003.
Calisma alani = 160 x 100 mm (Eurocard ham plaket). 6.6" pozlama ekrani 143.4 x 89.6 mm: desen bunun
icinde kalir, hizalama pimleri (Ø3, x = ±76) ham plaketin kenarlarinda.

Kullanim:  pip install trimesh manifold3d numpy matplotlib shapely
           python3 gen_delme.py            # stl/, cizim.svg/png, onizleme.html, olculer.txt
           python3 gen_delme.py --png      # ayrica onizleme.png (Chromium headless)
Koordinatlar mm. Orijin: taban ust yuzeyi, spindle ekseninin altinda. +X sag, +Y arka, +Z yukari.
"""
import json
import math
import os
import subprocess
import sys
import warnings

import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

warnings.filterwarnings('ignore', category=RuntimeWarning)
HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------- parametreler
P = dict(
    TX=160.0, TY=100.0,          # hareket = ham plaket (Eurocard 160 x 100)
    LCD=(143.43, 89.60),         # Aptus DBM066M4K01 aktif alan (desen siniri, bilgi)
    PIN_X=76.0, PIN_D=3.0,       # hizalama pimleri (x = ±PIN_X, y = 0)
    ROD=8.0, LM_D=15.0, LM_L=24.0, BORE_LM=15.2, BORE_ROD=8.2,
    BASE_T=18.0, BASE_M=12.0,    # taban kontrplak kalinligi, kenar payi
    zY=14.0,                     # Y mil ekseni yuksekligi
    EB_W=24.0,                   # uc blok genisligi (x)
    XS=90.0,                     # X milleri arasi (y)
    zX=34.0,                     # X mil ekseni yuksekligi
    PX=180.0, PY=120.0, PT=9.0,  # tabla (kontrplak) olculeri
    GAP=3.0,                     # hareketli/sabit parcalar arasi dusey bosluk
    SAC=3.0, PCB=1.6,            # feda MDF + plaket
    GT2_T=20, BELT_W=6.0,        # baski kasnak dis sayisi, kayis genisligi
    BIT_L=38.1, BIT_GRIP=10.0,   # karbur uc boyu ve mandrende kalan kismi
    DRILL_UNDER=0.6,             # ucun feda tahtaya girmesi
    Z_STROKE=30.0,
    M775_D=42.0, M775_L=67.0, M775_BOSS=(17.5, 4.0),
    CHUCK=(19.0, 32.0),          # JT0 mandren (cap, boy)
    ROD_Y_L=250.0,               # Y milleri (kullanicinin 250 mm milleri)
)
SEG = 48


def derived(P):
    d = dict(P)
    d['XH_L'] = 2 * P['LM_L'] + 6 + 2 * 3                      # tabla rulman yuvasi boyu (x)
    d['YX'] = (P['TX'] + P['EB_W'] + d['XH_L']) / 2            # Y millerinin x konumu
    d['EB_Y'] = P['XS'] / 2 + 12                               # uc blok yari boyu (y)
    d['ROD_X_L'] = 2 * (d['YX'] + P['EB_W'] / 2 - 3)           # X mil boyu
    d['zP0'] = P['zX'] + P['LM_D'] / 2 + 3 + P['GAP']          # tabla alti
    d['zP1'] = d['zP0'] + P['PT']
    d['zSAC'] = d['zP1'] + P['SAC']
    d['zPCB'] = d['zSAC'] + P['PCB']
    d['PD'] = P['GT2_T'] * 2.0 / math.pi                        # kasnak hatve capi
    d['zBX'] = 36.5                                            # X kayis merkezi
    d['zBYc'] = 15.5                                           # Y kasnak ekseni (yatay)
    d['tip_dn'] = d['zPCB'] - P['PCB'] - P['DRILL_UNDER']
    d['nose_dn'] = d['tip_dn'] + P['BIT_L'] - P['BIT_GRIP']
    d['m775_z0'] = d['nose_dn'] + P['CHUCK'][1] + P['M775_BOSS'][1]
    d['YBELT'] = d['ROD_Y_L'] / 2 + 14                         # Y kasnak/avara y konumu
    return d


D = derived(P)

# ----------------------------------------------------------------------------- geometri yardimcilari
def box(x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return b


def cyl(axis, c, r, a0, a1, seg=SEG):
    """axis 'x'|'y'|'z'; c = diger iki eksendeki merkez; a0..a1 eksen boyunca."""
    m = trimesh.creation.cylinder(radius=r, height=a1 - a0, sections=seg)
    if axis == 'x':
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
        m.apply_translation([(a0 + a1) / 2, c[0], c[1]])
    elif axis == 'y':
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
        m.apply_translation([c[0], (a0 + a1) / 2, c[1]])
    else:
        m.apply_translation([c[0], c[1], (a0 + a1) / 2])
    return m


def tube(axis, c, r_out, r_in, a0, a1):
    return diff(cyl(axis, c, r_out, a0, a1), [cyl(axis, c, r_in, a0 - 1, a1 + 1)])


def union(ms):
    ms = [m for m in ms if m is not None]
    return ms[0] if len(ms) == 1 else trimesh.boolean.union(ms, engine='manifold')


def diff(a, bs):
    return trimesh.boolean.difference([a] + list(bs), engine='manifold')


def inter_vol(a, b):
    if np.any(a.bounds[1] < b.bounds[0]) or np.any(b.bounds[1] < a.bounds[0]):
        return 0.0
    r = trimesh.boolean.intersection([a, b], engine='manifold')
    return float(r.volume) if r is not None and len(r.faces) else 0.0


def d_bore(axis, c, a0, a1):
    """28BYJ-48 mili: Ø5, iki duzlem arasi 3 mm (D-D). Kasnak deligi Ø5.15 / 3.15."""
    r = cyl(axis, c, 5.15 / 2, a0, a1)
    if axis == 'z':
        slab = box(c[0] - 1.575, c[0] + 1.575, c[1] - 3, c[1] + 3, a0, a1)
    elif axis == 'x':
        slab = box(a0, a1, c[0] - 3, c[0] + 3, c[1] - 1.575, c[1] + 1.575)
    else:
        slab = box(c[0] - 3, c[0] + 3, a0, a1, c[1] - 1.575, c[1] + 1.575)
    return trimesh.boolean.intersection([r, slab], engine='manifold')


def gt2_pulley(axis, c, a0, teeth, bore=True):
    """Baski GT2 kasnak: flans 1 + dis 7 + flans 1 mm, D deligi. Dis profili yaklasik (yariçap 0.555 oluk)."""
    pd = teeth * 2.0 / math.pi
    od = pd - 0.508
    body = cyl(axis, c, od / 2, a0 + 1, a0 + 8, seg=teeth * 6)
    cuts = []
    rc = od / 2 - 0.75 + 0.555
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        u, v = rc * math.cos(a), rc * math.sin(a)
        cuts.append(cyl(axis, (c[0] + u, c[1] + v), 0.555, a0 + 0.9, a0 + 8.1, seg=16))
    body = diff(body, cuts)
    fl = [cyl(axis, c, od / 2 + 1.6, a0, a0 + 1), cyl(axis, c, od / 2 + 1.6, a0 + 8, a0 + 9)]
    p = union([body] + fl)
    if bore:
        p = diff(p, [d_bore(axis, c, a0 - 1, a0 + 10)])
    return p


def idler(axis, c, a0):
    """Baski avara: 2x 623ZZ (Ø10x4) yuvasi, flansli; M3 civata ekseni."""
    pd = D['PD']
    body = union([cyl(axis, c, pd / 2 - 0.25, a0 + 1, a0 + 8),
                  cyl(axis, c, pd / 2 + 1.35, a0, a0 + 1), cyl(axis, c, pd / 2 + 1.35, a0 + 8, a0 + 9)])
    return diff(body, [cyl(axis, c, 5.1, a0 - 1, a0 + 10)])


def m28byj(origin, zdir, ydir):
    """28BYJ-48: yerel cercevede mil +z (flans duzlemi z=0), govde Ø28x19 z<0, merkezi +y'de 8 mm,
    kulaklar x = ±17.5 (Ø7, 1 mm), boss Ø9x1.5, mil Ø5x9. origin = mil ekseninin flans duzlemini kestigi nokta,
    zdir = milin baktigi yon, ydir = govde merkezinin mile gore yonu."""
    z, y = np.array(zdir, float), np.array(ydir, float)
    x = np.cross(y, z)
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = x, y, z, origin
    m = union([cyl('z', (0, 8), 14, -19, 0), cyl('z', (-17.5, 8), 3.5, -1, 0, seg=24),
               cyl('z', (17.5, 8), 3.5, -1, 0, seg=24), box(-17.5, 17.5, 4.5, 11.5, -1, 0),
               cyl('z', (0, 0), 4.5, 0, 1.5, seg=24), cyl('z', (0, 0), 2.5, 1.5, 10.5, seg=24)])
    m.apply_transform(T)
    return m


# ----------------------------------------------------------------------------- parcalar
# grup: 'S' sabit, 'Y' Y arabasi, 'X' tabla (X+Y), 'Z' Z arabasi
# tur: 'baski' (STL), 'ahsap' (kesim listesi), 'hazir' (satin alinan)
PARTS = []


def add(name, mesh, group, kind, color, qty_key=None, note=''):
    PARTS.append(dict(name=name, mesh=mesh, group=group, kind=kind, color=color, key=qty_key or name, note=note))


C = dict(print='#e8833a', wood='#c8a46e', rod='#b8bcc4', bear='#6d7a8c', motor='#3d6fb6', belt='#222222',
         pcb='#2f8f4e', alu='#9aa3ad', elec='#7b3fa0', brass='#c9a227', sw='#d23c3c')


def build():
    PARTS.clear()
    YX, EBY, zY, zX = D['YX'], D['EB_Y'], P['zY'], P['zX']
    R, LMR, BLM, BR = P['ROD'] / 2, P['LM_D'] / 2, P['BORE_LM'] / 2, P['BORE_ROD'] / 2
    BT = P['BASE_T']

    # --- taban ve Y ekseni (sabit) ---
    ext = dict(x0=-185.0, x1=185.0, y0=-172.0, y1=185.0)
    add('Taban (kontrplak 18 mm)', box(ext['x0'], ext['x1'], ext['y0'], ext['y1'], -BT, 0), 'S', 'ahsap', C['wood'])
    LY = P['ROD_Y_L']
    for sx in (-1, 1):
        add('Y mili Ø8', cyl('y', (sx * YX, zY), R, -LY / 2, LY / 2, seg=24), 'S', 'hazir', C['rod'], 'mil_y')
        for sy in (-1, 1):
            y0, y1 = (LY / 2 - 12, LY / 2) if sy > 0 else (-LY / 2, -LY / 2 + 12)
            h = union([box(sx * YX - 12, sx * YX + 12, y0, y1, 0, zY + 9),
                       box(sx * YX - 21, sx * YX + 21, y0, y1, 0, 5)])
            h = diff(h, [cyl('y', (sx * YX, zY), BR, y0 - 1, y1 + 1),
                         cyl('z', (sx * YX - 16.5, (y0 + y1) / 2), 2.2, -1, 6, seg=16),
                         cyl('z', (sx * YX + 16.5, (y0 + y1) / 2), 2.2, -1, 6, seg=16),
                         box(sx * YX - 0.75, sx * YX + 0.75, y0 - 1, y1 + 1, zY, zY + 10)])
            add('Mil tutucu (Y)', h, 'S', 'baski', C['print'], 'mil_tutucu')

    # Y motoru (on, mil +x), Y avara (arka)
    yb, zc = D['YBELT'], D['zBYc']
    add('Y kasnak GT2-20', gt2_pulley('x', (-yb, zc), -4.5, P['GT2_T']), 'S', 'baski', C['print'], 'kasnak')
    add('Y motoru 28BYJ-48', m28byj((-7.0, -yb, zc), (1, 0, 0), (0, 0, 1)), 'S', 'hazir', C['motor'], '28byj')
    ymb = diff(union([box(-7, -4, -yb - 22, -yb + 22, 0, zc + 26), box(-30, -4, -yb - 22, -yb + 22, 0, 4)]),
               [cyl('x', (-yb, zc), 9.0, -8, -3), cyl('x', (-yb - 17.5, zc + 8), 2.1, -8, -3, seg=16),
                cyl('x', (-yb + 17.5, zc + 8), 2.1, -8, -3, seg=16)])
    add('Y motor braketi', ymb, 'S', 'baski', C['print'], 'y_motor_braketi')
    add('Y avara', idler('x', (yb, zc), -4.5), 'S', 'baski', C['print'], 'avara')
    yib = diff(union([box(-12, -6, yb - 12, yb + 12, 0, zc + 8), box(6, 12, yb - 12, yb + 12, 0, zc + 8),
                      box(-12, 12, yb - 12, yb + 12, 0, 4)]), [cyl('x', (yb, zc), 1.65, -13, 13, seg=16)])
    add('Y avara braketi', yib, 'S', 'baski', C['print'], 'y_avara_braketi')
    # Y kayisi: kasnaktan avaraya iki kol (ust kol tablaya kelepçeli)
    pr = D['PD'] / 2
    for zz in (zc - pr, zc + pr):
        add('GT2 kayis (Y)', box(-3, 3, -yb, yb, zz - 0.7, zz + 0.7), 'S', 'hazir', C['belt'], 'kayis_y')

    # --- Y arabasi: iki uc blok + X milleri + capraz lata + X motoru/avarasi ---
    xb_slot = lambda sx: box(sx * YX - 13, sx * YX + 13, -12, 12, D['zBX'] - 5, 60)
    for sx in (-1, 1):
        x0, x1 = sx * YX - P['EB_W'] / 2, sx * YX + P['EB_W'] / 2
        eb = box(x0, x1, -EBY, EBY, 3, 42)
        cuts = [cyl('y', (sx * YX, zY), BLM, -EBY - 1, EBY + 1), xb_slot(sx)]
        for sy in (-1, 1):
            xa, xbb = (sx * YX - 12 - 0.01, sx * YX + 9) if sx > 0 else (sx * YX - 9, sx * YX + 12 + 0.01)
            cuts.append(cyl('x', (sy * P['XS'] / 2, zX), BR, xa, xbb, seg=24))
            cuts.append(cyl('z', (sx * YX, sy * P['XS'] / 2), 1.6, zX, 43, seg=12))       # M3 mil sikma
        add('Uç blok (sol)' if sx < 0 else 'Uç blok (sağ)', diff(eb, cuts), 'Y', 'baski', C['print'],
            'uc_blok_sol' if sx < 0 else 'uc_blok_sag')
        for sy in (-1, 1):
            yc = sy * (EBY - 4 - P['LM_L'] / 2)
            add('LM8UU (Y)', tube('y', (sx * YX, zY), LMR, R, yc - 12, yc + 12), 'Y', 'hazir', C['bear'], 'lm8uu')
    LX = D['ROD_X_L']
    for sy in (-1, 1):
        add('X mili Ø8', cyl('x', (sy * P['XS'] / 2, zX), R, -LX / 2, LX / 2, seg=24), 'Y', 'hazir', C['rod'], 'mil_x')
    add('Çapraz lata (kontrplak 8 mm)', box(-YX + 12, YX - 12, -20, 20, 23, 31), 'Y', 'ahsap', C['wood'])
    ybc = diff(box(-8, 8, -10, 10, zc + pr - 3.6, 23), [box(-3.4, 3.4, -11, 11, zc + pr - 0.9, zc + pr + 0.9)])
    add('Y kayis kelepcesi', ybc, 'Y', 'baski', C['print'], 'y_kayis_kelepcesi')
    # X motoru: sag uc blogun disinda, mil yukari; X avara: sol blogun disinda
    xm = YX + P['EB_W'] / 2 + 11
    zb = D['zBX']
    add('X kasnak GT2-20', gt2_pulley('z', (xm, 0), zb - 4.5, P['GT2_T']), 'Y', 'baski', C['print'], 'kasnak')
    add('X motoru 28BYJ-48', m28byj((xm, 0, zb - 6.5), (0, 0, 1), (1, 0, 0)), 'Y', 'hazir', C['motor'], '28byj')
    xmb = diff(box(YX + 12, xm + 28, -24, 24, zb - 6.5, zb - 3.5),
               [cyl('z', (xm, 0), 9.0, zb - 8, zb), cyl('z', (xm + 8, -17.5), 2.1, zb - 8, zb, seg=16),
                cyl('z', (xm + 8, 17.5), 2.1, zb - 8, zb, seg=16)])
    add('X motor braketi', xmb, 'Y', 'baski', C['print'], 'x_motor_braketi')
    add('X avara', idler('z', (-xm, 0), zb - 4.5), 'Y', 'baski', C['print'], 'avara')
    xib = diff(union([box(-xm - 9, -YX - 12, -10, 10, zb - 6.5, zb - 4.5),
                      box(-xm - 9, -YX - 12, -10, 10, zb + 4.5, zb + 6.5),
                      box(-YX - 14, -YX - 12, 8, 10, zb - 6.5, zb + 6.5),
                      box(-YX - 14, -YX - 12, -10, -8, zb - 6.5, zb + 6.5)]),
               [cyl('z', (-xm, 0), 1.65, zb - 8, zb + 8, seg=16)])
    add('X avara braketi', xib, 'Y', 'baski', C['print'], 'x_avara_braketi')
    for yy in (-pr, pr):
        add('GT2 kayis (X)', box(-xm, xm, yy - 0.7, yy + 0.7, zb - 3, zb + 3), 'Y', 'hazir', C['belt'], 'kayis_x')

    # --- tabla (X+Y) ---
    zP0, zP1 = D['zP0'], D['zP1']
    pins = [cyl('z', (sx * P['PIN_X'], 0), P['PIN_D'] / 2 + 0.05, zP1 - 1, D['zSAC'] + 6, seg=16) for sx in (-1, 1)]
    add('Tabla (kontrplak 9 mm)', diff(box(-P['PX'] / 2, P['PX'] / 2, -P['PY'] / 2, P['PY'] / 2, zP0, zP1), pins),
        'X', 'ahsap', C['wood'])
    add('Feda MDF 3 mm', diff(box(-82, 82, -52, 52, zP1, D['zSAC']), pins), 'X', 'ahsap', '#d9c49a')
    add('Plaket 160x100', diff(box(-80, 80, -50, 50, D['zSAC'], D['zPCB']), pins), 'X', 'hazir', C['pcb'], 'plaket')
    for sx in (-1, 1):
        add('Hizalama pimi Ø3', cyl('z', (sx * P['PIN_X'], 0), P['PIN_D'] / 2, zP1 - 1, D['zSAC'] + 5, seg=16),
            'X', 'hazir', C['alu'], 'pim')
    L2 = D['XH_L'] / 2
    for sy in (-1, 1):
        yc = sy * P['XS'] / 2
        hs = box(-L2, L2, yc - 11.5, yc + 11.5, zX - LMR - 3, zP0)
        hs = diff(hs, [cyl('x', (yc, zX), BLM, -L2 + 3, L2 - 3), cyl('x', (yc, zX), R + 1.5, -L2 - 1, L2 + 1),
                       box(-L2 - 1, L2 + 1, yc - 1, yc + 1, zX - LMR - 4, zX)])
        add('Tabla rulman yuvası', hs, 'X', 'baski', C['print'], 'tabla_yuvasi')
        for xc in (-15, 15):
            add('LM8UU (X)', tube('x', (yc, zX), LMR, R, xc - 12, xc + 12), 'X', 'hazir', C['bear'], 'lm8uu')
    xbc = diff(box(-10, 10, 2, 12, zb - 4.5, zP0), [box(-11, 11, pr - 0.9, pr + 0.9, zb - 3.4, zb + 3.4)])
    add('X kayis kelepcesi', xbc, 'X', 'baski', C['print'], 'x_kayis_kelepcesi')

    # --- spindle, Z (Z grubu) ---
    tip, nose, mz0 = D['tip_dn'], D['nose_dn'], D['m775_z0']
    add('Karbür uç (PCB)', cyl('z', (0, 0), 0.4, tip, nose + P['BIT_GRIP'], seg=12), 'Z', 'hazir', '#e0e0e0', 'uc')
    add('JT0 mandren', cyl('z', (0, 0), P['CHUCK'][0] / 2, nose, nose + P['CHUCK'][1]), 'Z', 'hazir', C['alu'], 'mandren')
    add('775 motor', union([cyl('z', (0, 0), P['M775_BOSS'][0] / 2, mz0 - P['M775_BOSS'][1], mz0),
                            cyl('z', (0, 0), P['M775_D'] / 2, mz0, mz0 + P['M775_L'])]), 'Z', 'hazir', C['motor'], '775')
    zr_y, zr_x = 40.0, 25.0
    c0 = mz0 + 7
    c1 = c0 + 2 * P['LM_L'] + 4
    car = union([cyl('z', (0, 0), P['M775_D'] / 2 + 4, c0, c1),
                 box(-zr_x - 11, zr_x + 11, 14, zr_y + 11.5, c0, c1)])
    car = diff(car, [cyl('z', (0, 0), P['M775_D'] / 2 + 0.2, c0 - 1, c1 + 1),
                     box(-1, 1, -30, -10, c0 - 1, c1 + 1),
                     cyl('z', (zr_x, zr_y), BLM, c0 - 1, c1 + 1), cyl('z', (-zr_x, zr_y), BLM, c0 - 1, c1 + 1),
                     cyl('z', (0, zr_y), 5.5, c0 - 1, c1 + 1)])
    add('Z arabası (spindle kelepçeli)', car, 'Z', 'baski', C['print'], 'z_arabasi')
    for sx in (-1, 1):
        for k in range(2):
            z0 = c0 + 2 + k * P['LM_L']
            add('LM8UU (Z)', tube('z', (sx * zr_x, zr_y), LMR, R, z0, z0 + P['LM_L']), 'Z', 'hazir', C['bear'], 'lm8uu')
    add('T8 somun (pirinç)', union([tube('z', (0, zr_y), 5.0, 4.0, c0 - 3.5, c0 + 12),
                                     tube('z', (0, zr_y), 11.0, 4.0, c0 - 3.5, c0)]), 'Z', 'hazir', C['brass'], 't8_somun')

    zb0 = c0 - 14           # alt braket
    zt1 = c1 + P['Z_STROKE'] + 14
    zt0 = zt1 - 12
    zplate_y = zr_y + 15
    br = lambda z0, z1, hole: diff(box(-zr_x - 12, zr_x + 12, zr_y - 12, zplate_y, z0, z1),
                                   [cyl('z', (zr_x, zr_y), BR if not hole else BR, z0 - 1, z1 + 1),
                                    cyl('z', (-zr_x, zr_y), BR, z0 - 1, z1 + 1),
                                    cyl('z', (0, zr_y), 5.5, z0 - 1, z1 + 1)])
    add('Z alt braket', br(zb0, zb0 + 10, False), 'S', 'baski', C['print'], 'z_alt_braket')
    add('Z üst braket', br(zt0, zt1, True), 'S', 'baski', C['print'], 'z_ust_braket')
    for sx in (-1, 1):
        add('Z mili Ø8', cyl('z', (sx * zr_x, zr_y), R, zb0, zt1, seg=24), 'S', 'hazir', C['rod'], 'mil_z')
    cpl0 = zt1 + 3
    add('Kaplin 5x8', cyl('z', (0, zr_y), 9.5, cpl0, cpl0 + 25), 'S', 'hazir', C['alu'], 'kaplin')
    ls_top = cpl0 + 12.5
    add('T8 trapez mil', cyl('z', (0, zr_y), 4.0, ls_top - 150, ls_top, seg=24), 'S', 'hazir', C['alu'], 't8_mil')
    zface = cpl0 + 27.5                 # 28BYJ flans duzlemi; mil asagi, 8 mm kaplinde
    add('Z motoru 28BYJ-48', m28byj((0, zr_y, zface), (0, 0, -1), (0, -1, 0)), 'S', 'hazir', C['motor'], '28byj')
    zmb = diff(union([box(-26, 26, zr_y - 12, zplate_y, zface - 3, zface),
                      box(-26, -20, zr_y - 12, zplate_y, zt1, zface - 3),
                      box(20, 26, zr_y - 12, zplate_y, zt1, zface - 3)]),
               [cyl('z', (0, zr_y), 10.5, zface - 4, zface + 1), cyl('z', (-17.5, zr_y - 8), 2.1, zface - 4, zface + 1, seg=16),
                cyl('z', (17.5, zr_y - 8), 2.1, zface - 4, zface + 1, seg=16)])
    add('Z motor köprüsü', zmb, 'S', 'baski', C['print'], 'z_motor_koprusu')

    # --- kolon (kontrplak) ---
    t = 18.0
    zp0, zp1 = zb0 - 12, zface + 22
    add('Z plakası (kontrplak 18)', box(-55, 55, zplate_y, zplate_y + t, zp0, zp1), 'S', 'ahsap', C['wood'])
    ycol = 160.0
    for sx in (-1, 1):
        add('Yanak (kontrplak 18)', box(sx * 55 - (t if sx < 0 else 0), sx * 55 + (t if sx > 0 else 0),
                                        zplate_y, ycol, zp0, zp1), 'S', 'ahsap', C['wood'], 'yanak')
    add('Kolon (kontrplak 18)', box(-80, 80, ycol, ycol + t, 0, zp1), 'S', 'ahsap', C['wood'])

    # --- elektronik + switchler (yaklasik) ---
    add('Elektronik (ESP32-S3 + 3x ULN2003 + MOSFET)', box(40, 175, -168, -132, 0, 22), 'S', 'hazir', C['elec'], 'elektronik')
    add('X limit switch', box(YX - 12 - 6, YX - 12, 36, 44, 26, 34), 'Y', 'hazir', C['sw'], 'switch')
    add('Y limit switch', box(-YX + 6, -YX + 12, -LY / 2 + 13, -LY / 2 + 19, 0, 9), 'S', 'hazir', C['sw'], 'switch')
    add('Z limit switch', box(zr_x + 1, zr_x + 9, zr_y + 4.5, zr_y + 12.5, zt0 - 8, zt0), 'S', 'hazir', C['sw'], 'switch')
    return ext


def placed(part, X=0.0, Y=0.0, Z=0.0):
    m = part['mesh'].copy()
    g = part['group']
    if g in ('Y', 'X'):
        m.apply_translation([X if g == 'X' else 0.0, Y, 0])
    if g == 'Z':
        m.apply_translation([0, 0, Z])
    return m


# ----------------------------------------------------------------------------- kontroller
ALLOW = [  # temas eden / ic ice gecen tasarim ciftleri (anahtar kumeleri)
    ('mil_y', 'lm8uu'), ('mil_x', 'lm8uu'), ('mil_z', 'lm8uu'), ('kasnak', '28byj'), ('t8_mil', 't8_somun'),
    ('t8_mil', 'kaplin'), ('kaplin', '28byj'), ('kayis_y', 'kasnak'), ('kayis_y', 'avara'), ('kayis_x', 'kasnak'),
    ('kayis_x', 'avara'), ('kayis_y', 'y_kayis_kelepcesi'), ('kayis_x', 'x_kayis_kelepcesi'),
    ('uc', 'mandren'), ('uc', 'plaket'), ('uc', 'Feda MDF 3 mm'), ('pim', 'Tabla (kontrplak 9 mm)'),
    ('pim', 'Feda MDF 3 mm'), ('pim', 'plaket'), ('775', 'mandren'), ('775', 'z_arabasi'),
    ('mil_z', 'z_alt_braket'), ('mil_z', 'z_ust_braket'), ('t8_mil', 'z_alt_braket'), ('t8_mil', 'z_ust_braket'),
    ('t8_somun', 'z_arabasi'), ('lm8uu', 'z_arabasi'), ('lm8uu', 'tabla_yuvasi'), ('lm8uu', 'uc_blok_sol'),
    ('lm8uu', 'uc_blok_sag'), ('mil_x', 'uc_blok_sol'), ('mil_x', 'uc_blok_sag'), ('mil_y', 'mil_tutucu'),
    ('switch', '*'), ('kayis_x', 'uc_blok_sol'), ('kayis_x', 'uc_blok_sag'),
]


def allowed(a, b):
    for p, q in ALLOW:
        if (p in (a['key'], a['name']) and (q == '*' or q in (b['key'], b['name']))) or \
           (p in (b['key'], b['name']) and (q == '*' or q in (a['key'], a['name']))):
            return True
    return False


def check():
    """Uc noktalarda carpisma (kesisim hacmi > 1 mm3) ve yapisik tasarim kontrolleri."""
    probs = []
    poses = [(x, y, z) for x in (-P['TX'] / 2, 0, P['TX'] / 2) for y in (-P['TY'] / 2, 0, P['TY'] / 2)
             for z in (0.0, P['Z_STROKE'])]
    seen = set()
    for (X, Y, Z) in poses:
        ms = [placed(p, X, Y, Z) for p in PARTS]
        for i in range(len(PARTS)):
            for j in range(i + 1, len(PARTS)):
                a, b = PARTS[i], PARTS[j]
                if a['group'] == b['group'] or allowed(a, b):
                    continue
                if a['group'] == 'S' and b['group'] == 'S':
                    continue
                v = inter_vol(ms[i], ms[j])
                if v > 1.0:
                    k = (a['name'], b['name'])
                    if k not in seen:
                        seen.add(k)
                        probs.append('ÇARPIŞMA %s <-> %s  %.0f mm3 @ X=%g Y=%g Z+%g' % (a['name'], b['name'], v, X, Y, Z))
    # ayni gruptaki parcalar (sabit montaj) de birbirine girmemeli
    for g in ('S', 'Y', 'X', 'Z'):
        gp = [p for p in PARTS if p['group'] == g]
        for i in range(len(gp)):
            for j in range(i + 1, len(gp)):
                if allowed(gp[i], gp[j]):
                    continue
                v = inter_vol(gp[i]['mesh'], gp[j]['mesh'])
                if v > 1.0:
                    probs.append('İÇ İÇE %s <-> %s  %.0f mm3 (grup %s)' % (gp[i]['name'], gp[j]['name'], v, g))
    return probs


# ----------------------------------------------------------------------------- cikti
def stl_out():
    d = os.path.join(HERE, 'stl')
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        if f.endswith('.stl'):
            os.remove(os.path.join(d, f))
    done, best = {}, {}
    for p in PARTS:                       # ayni anahtarli parcalardan en basik olani (baski yonu) yazilir
        if p['kind'] != 'baski':
            continue
        done[p['key']] = done.get(p['key'], 0) + 1
        if p['key'] not in best or p['mesh'].extents[2] < best[p['key']].extents[2]:
            best[p['key']] = p['mesh']
    for key, mesh in best.items():
        m = mesh.copy()
        m.apply_translation(-m.bounds[0])
        m.export(os.path.join(d, key + '.stl'))
    return done


def counts():
    c = {}
    for p in PARTS:
        k = (p['kind'], p['key'], p['name'])
        c[k] = c.get(k, 0) + 1
    return c


def proj_poly(mesh, ax):
    v = mesh.vertices[:, ax]
    polys = []
    for f in mesh.faces:
        t = v[f]
        a = (t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1])
        if abs(a) > 1e-6:
            polys.append(Polygon(t))
    return unary_union(polys).buffer(0.01)


def drawing(ext):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path

    def patch(ax, geom, fc, ec='#333', lw=0.4, ls='-', alpha=1.0):
        geoms = getattr(geom, 'geoms', [geom])
        for g in geoms:
            if g.is_empty or g.geom_type != 'Polygon':
                continue
            verts, codes = [], []
            for ring in [g.exterior] + list(g.interiors):
                xy = list(ring.coords)
                verts += xy
                codes += [Path.MOVETO] + [Path.LINETO] * (len(xy) - 2) + [Path.CLOSEPOLY]
            ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec=ec, lw=lw, ls=ls, alpha=alpha))

    views = [('Üstten (XY)', (0, 1), lambda m: m.bounds[1][2]),
             ('Önden (XZ)', (0, 2), lambda m: -m.bounds[0][1]),
             ('Yandan, sağdan (YZ)', (1, 2), lambda m: m.bounds[1][0])]
    fig, axs = plt.subplots(1, 3, figsize=(24, 9.5), gridspec_kw=dict(width_ratios=[1, 1, 1]))
    for ax, (title, idx, depth) in zip(axs, views):
        order = sorted(PARTS, key=lambda p: depth(p['mesh']))
        for p in order:
            if p['kind'] == 'hazir' and p['key'] in ('kayis_x', 'kayis_y') and idx != (0, 1):
                pass
            patch(ax, proj_poly(p['mesh'], list(idx)), p['color'])
        # tabla suprume alani (kesikli)
        tb = PARTS[[p['name'] for p in PARTS].index('Tabla (kontrplak 9 mm)')]['mesh']
        sw = [tb.copy() for _ in range(4)]
        for m, (X, Y) in zip(sw, [(-80, -50), (80, -50), (-80, 50), (80, 50)]):
            m.apply_translation([X, Y, 0])
        env = unary_union([proj_poly(m, list(idx)) for m in sw]).convex_hull
        patch(ax, env, 'none', ec='#c0392b', lw=1.2, ls='--')
        ax.set_title(title, fontsize=13)
        ax.set_aspect('equal')
        ax.grid(True, lw=0.3, alpha=0.5)
        ax.autoscale_view()
    W, Dp = ext['x1'] - ext['x0'], ext['y1'] - ext['y0']
    H = max(p['mesh'].bounds[1][2] for p in PARTS) + P['BASE_T']
    axs[0].annotate('', xy=(ext['x0'], ext['y0'] - 18), xytext=(ext['x1'], ext['y0'] - 18),
                    arrowprops=dict(arrowstyle='<->', lw=1))
    axs[0].text(0, ext['y0'] - 28, '%.0f mm' % W, ha='center', va='top')
    axs[0].annotate('', xy=(ext['x1'] + 15, ext['y0']), xytext=(ext['x1'] + 15, ext['y1']),
                    arrowprops=dict(arrowstyle='<->', lw=1))
    axs[0].text(ext['x1'] + 22, 0, '%.0f mm' % Dp, rotation=90, va='center')
    axs[1].annotate('', xy=(ext['x1'] + 15, -P['BASE_T']), xytext=(ext['x1'] + 15, H - P['BASE_T']),
                    arrowprops=dict(arrowstyle='<->', lw=1))
    axs[1].text(ext['x1'] + 22, H / 2, '%.0f mm' % H, rotation=90, va='center')
    for ax in axs:
        ax.relim()
        ax.autoscale_view()
        ax.margins(0.08)
    fig.suptitle('PCB delme makinesi v0  |  taban %.0f x %.0f mm, yükseklik %.0f mm  |  hareket %g x %g mm, Z %g mm  |  '
                 'kesikli kırmızı: tabla süpürme alanı' % (W, Dp, H, P['TX'], P['TY'], P['Z_STROKE']), fontsize=13)
    from matplotlib.patches import Patch
    leg = [Patch(fc=C['print'], ec='#333', label='3D baskı'), Patch(fc=C['wood'], ec='#333', label='Kontrplak'),
           Patch(fc=C['rod'], ec='#333', label='Ø8 mil'), Patch(fc=C['bear'], ec='#333', label='LM8UU'),
           Patch(fc=C['motor'], ec='#333', label='Motor'), Patch(fc=C['pcb'], ec='#333', label='Plaket'),
           Patch(fc=C['elec'], ec='#333', label='Elektronik')]
    fig.legend(handles=leg, loc='lower center', ncol=7, fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(os.path.join(HERE, 'cizim.svg'))
    fig.savefig(os.path.join(HERE, 'cizim.png'), dpi=110)
    plt.close(fig)
    return W, Dp, H


VIEWER = r'''<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Delme makinesi v0</title>
<style>:root{--bg:#f4f1ec;--fg:#222;--pn:#ffffffcc}@media (prefers-color-scheme:dark){:root{--bg:#1b1d21;--fg:#eee;--pn:#2a2d33cc}}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;overflow:hidden}
#ui{position:absolute;left:12px;top:12px;background:var(--pn);padding:10px 12px;border-radius:8px;max-width:calc(100% - 48px)}
#ui label{display:flex;gap:8px;align-items:center;margin:4px 0}#ui input{flex:1;min-width:120px}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script></head><body>
<div id="ui"><b>PCB delme makinesi v0</b><br>
<label>X <input id="X" type="range" min="-80" max="80" value="0"></label>
<label>Y <input id="Y" type="range" min="-50" max="50" value="0"></label>
<label>Z <input id="Z" type="range" min="0" max="30" value="30"></label></div>
<script type="module">
import * as THREE from 'three';import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const D=__DATA__;const sc=new THREE.Scene();const cam=new THREE.PerspectiveCamera(35,innerWidth/innerHeight,1,5000);
cam.up.set(0,0,1);cam.position.set(420,-560,420);const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
sc.background=new THREE.Color(getComputedStyle(document.body).backgroundColor);r.setPixelRatio(devicePixelRatio);r.setSize(innerWidth,innerHeight);document.body.appendChild(r.domElement);
sc.add(new THREE.HemisphereLight(0xffffff,0x666666,1.6));const dl=new THREE.DirectionalLight(0xffffff,1.6);dl.position.set(300,-400,600);sc.add(dl);
const G={S:new THREE.Group(),Y:new THREE.Group(),X:new THREE.Group(),Z:new THREE.Group()};for(const k in G)sc.add(G[k]);
for(const p of D){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(p.v,3));
g.setIndex(p.f);g.computeVertexNormals();const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:p.c,roughness:.7,metalness:p.k=='hazir'?.25:0}));
G[p.g].add(m);}
const ctl=new OrbitControls(cam,r.domElement);ctl.target.set(0,0,90);ctl.update();
function upd(){const X=+document.getElementById('X').value,Y=+document.getElementById('Y').value,Z=+document.getElementById('Z').value;
G.Y.position.set(0,Y,0);G.X.position.set(X,Y,0);G.Z.position.set(0,0,Z);}
for(const id of['X','Y','Z'])document.getElementById(id).oninput=upd;upd();
addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();r.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);r.render(sc,cam);})();
</script></body></html>'''


def viewer():
    data = []
    for p in PARTS:
        m = p['mesh']
        data.append(dict(v=[round(float(x), 2) for x in m.vertices.flatten()], f=[int(i) for i in m.faces.flatten()],
                         c=p['color'], g=p['group'], k=p['kind']))
    path = os.path.join(HERE, 'onizleme.html')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(VIEWER.replace('__DATA__', json.dumps(data, separators=(',', ':'))))
    return path


def screenshot(html, png):
    """onizleme.png: three.js yerel kopyasi + yerel HTTP sunucu (headless Chromium CDN'e cikamayabilir)."""
    import functools
    import http.server
    import shutil
    import tempfile
    import threading
    import urllib.request
    base = 'https://cdn.jsdelivr.net/npm/three@0.160.0/'
    tmp = tempfile.mkdtemp()
    try:
        for rel in ('build/three.module.js', 'examples/jsm/controls/OrbitControls.js'):
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with urllib.request.urlopen(base + rel, timeout=60) as r, open(dst, 'wb') as f:
                f.write(r.read())
        page = open(html, encoding='utf-8').read().replace(base, './')
        page = page.replace('<body>', '<body style="background:#f4f1ec">')
        open(os.path.join(tmp, 'v.html'), 'w', encoding='utf-8').write(page)
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        h = functools.partial(Quiet, directory=tmp)
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        chrome = os.environ.get('CHROME', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        subprocess.run([chrome, '--headless=new', '--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                        '--hide-scrollbars', '--window-size=1400,1000', '--virtual-time-budget=20000',
                        '--screenshot=' + png, 'http://127.0.0.1:%d/v.html' % srv.server_address[1]],
                       check=False, capture_output=True, timeout=180)
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ext = build()
    probs = check()
    nprint = stl_out()
    W, Dp, H = drawing(ext)
    html = viewer()
    if '--png' in sys.argv:
        screenshot(html, os.path.join(HERE, 'onizleme.png'))
    c = counts()
    lines = ['PCB delme makinesi v0 - olculer ve parca sayilari (gen_delme.py)', '',
             'Taban: %.0f x %.0f x %.0f mm (kontrplak), toplam yukseklik %.0f mm' % (W, Dp, P['BASE_T'], H),
             'Hareket: X %g, Y %g, Z %g mm | ham plaket 160x100, desen <= %.1f x %.1f (6.6" LCD)'
             % (P['TX'], P['TY'], P['Z_STROKE'], *P['LCD']),
             'Y milleri x = ±%.1f, z = %.1f, boy %.0f | X milleri y = ±%.1f, z = %.1f, boy %.0f | Z milleri 2 x %.0f'
             % (D['YX'], P['zY'], P['ROD_Y_L'], P['XS'] / 2, P['zX'], D['ROD_X_L'],
                [p for p in PARTS if p['key'] == 'mil_z'][0]['mesh'].extents[2]),
             'Tabla ust %.1f, plaket ust %.1f mm | uc asagi %.1f, mandren burnu asagi %.1f (yukari +%g)'
             % (D['zP1'], D['zPCB'], D['tip_dn'], D['nose_dn'], P['Z_STROKE']),
             'Kayis: X %.0f mm, Y %.0f mm (kasnak hatve capi %.2f, 20 dis -> %.0f mm/tur)'
             % (2 * 2 * (D['YX'] + P['EB_W'] / 2 + 11) + math.pi * D['PD'], 2 * 2 * D['YBELT'] + math.pi * D['PD'],
                D['PD'], P['GT2_T'] * 2), '']
    for kind, title in (('baski', '3D baski (stl/)'), ('ahsap', 'Kontrplak / MDF'), ('hazir', 'Satin alinan')):
        lines.append(title + ':')
        for (k, key, name), n in sorted(c.items()):
            if k == kind:
                m = [p for p in PARTS if p['key'] == key and p['name'] == name][0]['mesh']
                e = m.extents
                lines.append('  %2d x %-42s %6.1f x %6.1f x %6.1f' % (n, name, e[0], e[1], e[2]))
        lines.append('')
    lines.append('Kontrol: ' + ('temiz (cakisma yok)' if not probs else '%d sorun' % len(probs)))
    lines += ['  ' + s for s in probs]
    txt = '\n'.join(lines)
    open(os.path.join(HERE, 'olculer.txt'), 'w', encoding='utf-8').write(txt + '\n')
    print(txt)
    return 1 if probs else 0


if __name__ == '__main__':
    sys.exit(main())
