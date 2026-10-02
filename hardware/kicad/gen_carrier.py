#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MagPanel Carrier — KiCad 8 proje ureticisi (sematik + PCB + uretim ciktilari).

Tasarim yaklasimi (enclosure/generate_case.py, hardware/gen_schematic.py ile ayni):
her sey bu dosyadaki tablolardan URETILIR, elle cizilmez. Pin atamalari
include/app_constants.hpp (HUB75), include/panel_sm16380.h (LAT2/LAT3) ve
include/sensors.h (sensorler) ile birebir ayni olmali.

Asamalar (KiCad 8'in python3'u ile: Linux /usr/bin/python3, macOS
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3):
  python3 gen_carrier.py sch      # .kicad_sch + .kicad_pro + kutuphaneler   (sadece stdlib)
  python3 gen_carrier.py pcb      # yerlesim + kart cercevesi + on-yonlendirme (pcbnew)
  python3 gen_carrier.py route    # Freerouting 2.1.0 (Java 21+, yoksa work/'e iner) + GND dokumu
  python3 gen_carrier.py fab      # ERC/DRC kapisi + gerber/drill/BOM/CPL/PDF (kicad-cli)
                                  # + gorseller (Chromium/Chrome; yol icin CHROME=...)
  python3 gen_carrier.py all      # hepsi sirayla
"""
import os
import sys
import json
import math
import shutil
import argparse
import collections
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sexp                                  # noqa: E402
import schlib                                # noqa: E402
from sexp import Sym                         # noqa: E402
from schlib import uid, r4                   # noqa: E402

PROJ = 'magpanel-carrier'
OUT = HERE / PROJ
REV = '1.2'
DATE = '2026-10-02'
DIY = False      # --diy: ev yapimi cift yuz surum (dry film + MSLA ekran pozlama); set_variant_diy() tablolari degistirir
G = 2.54                                     # sematik izgara (100 mil)

# =============================================================================
#  ELEKTRIKSEL TASARIM (tek kaynak)
# =============================================================================
# ESP32-S3-DevKitC-1 basliklari (Espressif v1.1 dokumani + resmi DXF ile dogrulandi).
# Sembol/footprint pin no: J1 pin n -> n, J3 pin n -> 22+n.
DEVKIT_J1 = ['3V3', '3V3', 'RST', 'IO4', 'IO5', 'IO6', 'IO7', 'IO15', 'IO16', 'IO17', 'IO18',
             'IO8', 'IO3', 'IO46', 'IO9', 'IO10', 'IO11', 'IO12', 'IO13', 'IO14', '5V', 'GND']
DEVKIT_J3 = ['GND', 'IO43/TX', 'IO44/RX', 'IO1', 'IO2', 'IO42', 'IO41', 'IO40', 'IO39', 'IO38',
             'IO37', 'IO36', 'IO35', 'IO0', 'IO45', 'IO48', 'IO47', 'IO21', 'IO20', 'IO19', 'GND', 'GND']
DEVKIT_ROW_09 = 22.86      # resmi Espressif karti (0.9")
DEVKIT_ROW_10 = 25.40      # yaygin N16R8 klonlari (1.0"; YD-ESP32-S3 tipi, 2x USB-C)
# Sag soket sira(lar)i. Eldeki kart 1.0" (1:1 baski testinde dogrulandi, 2026-10-02).
# Resmi Espressif karti icin [DEVKIT_ROW_09], ikisi birden icin [DEVKIT_ROW_09, DEVKIT_ROW_10].
DEVKIT_RIGHT_ROWS = [DEVKIT_ROW_10]
DEVKIT_ROW_IN = min(DEVKIT_RIGHT_ROWS)      # sol siraya en yakin sag sira (yerlesim icin)

def devkit_pin(name):
    """'IO10' -> sembol pin numarasi (str)."""
    if name in DEVKIT_J1:
        return str(DEVKIT_J1.index(name) + 1)
    return str(DEVKIT_J3.index(name) + 23)

# HUB75: ESP GPIO -> sinyal (include/app_constants.hpp; LAT2/LAT3 panel_sm16380.h)
HUB_GPIO = {
    'R1': 'IO4', 'G1': 'IO5', 'B1': 'IO6', 'R2': 'IO7', 'G2': 'IO15', 'B2': 'IO16',
    'ADDR_A': 'IO18', 'ADDR_B': 'IO8', 'ADDR_C': 'IO3', 'ADDR_D': 'IO9', 'ADDR_E': 'IO13',
    'CLK': 'IO12', 'LAT': 'IO10', 'OE': 'IO11', 'LAT2': 'IO17', 'LAT3': 'IO14',
}
# 74HCT245 kanal eslemesi (PCB'de tamponlar 180 derece donuk: A pinleri DevKit'e,
# B pinleri HUB75'e bakar; sira DevKit J1 pin sirasini izler -> kesisimsiz yonlendirme).
# pin 2..9 = A0..A7, pin 18..11 = B0..B7 (Ai <-> Bi).
BUF_CH = {
    'U2': ['ADDR_A', 'LAT2', 'B2', 'G2', 'R2', 'B1', 'G1', 'R1'],          # A0..A7
    'U3': ['LAT3', 'ADDR_E', 'CLK', 'OE', 'LAT', 'ADDR_D', 'ADDR_C', 'ADDR_B'],
}
# Seri 33R: her hatta tek 0805 (el lehimi; 4x0603 dizi ince uc ister). PCB'de tek sutun, her direnc
# kendi B pininin satirinda: R10..R17 = U2 B7..B0 (satir 2..9), R18..R25 = U3 B7..B0 (satir 13..20).
# pin 1 tampon tarafi (*_5V), pin 2 konnektor tarafi (HUB_*). (ref, sinyal, DevKit satiri)
SERIES_R = ([('R%d' % (10 + k), sig, 2 + k) for k, sig in enumerate(reversed(BUF_CH['U2']))] +
            [('R%d' % (18 + k), sig, 13 + k) for k, sig in enumerate(reversed(BUF_CH['U3']))])
# HUB75E konnektor pinleri (standart). 14 = LAT (panel basina ayri).
HUB_PINS = {1: 'R1', 2: 'G1', 3: 'B1', 4: 'GND', 5: 'R2', 6: 'G2', 7: 'B2', 8: 'ADDR_E',
            9: 'ADDR_A', 10: 'ADDR_B', 11: 'ADDR_C', 12: 'ADDR_D', 13: 'CLK', 14: None,
            15: 'OE', 16: 'GND'}
HUB_CONN = [('J2', 'LAT', 'PANEL 1', 'LAT = IO10 (P4 ve P1.86)'),
            ('J3', 'LAT2', 'PANEL 2', 'LAT2 = IO17 (yalniz coklu P1.86)'),
            ('J4', 'LAT3', 'PANEL 3', 'LAT3 = IO14 (yalniz coklu P1.86)')]
# Acilista (GPIO henuz surulmezken) paneli karanlik tutan pull-down'lar
PULLDOWNS = [('R2', 'LAT'), ('R3', 'LAT2'), ('R4', 'LAT3'), ('R5', 'OE')]

# Sensor / genisleme basliklari: pin sirasi ELDEKI JSUMO modullerinin baskisiyla birebir
# (fotograflardan, 2026-10-02) -> duz 3'lu/5'li kablo caprazlamaz; her pin PCB'de etiketli.
# LDR ve mikrofon modulleri YALNIZ DIJITAL cikisli (LM393 karsilastirici + trimpot):
#   LDR DO -> IO1 (firmware analog okur: 0 / %100 -> oto parlaklik iki kademe)
#   MIC OUT -> IO42 (firmware 'DO' kesmesi = yuksek ses); IO2 (analog mikrofon girisi) R7 ile GND'ye.
SENSOR_HDRS = [
    # ref, ad, [(pin etiketi, net)], aciklama
    ('J5', 'LDR', [('3V3', '+3V3'), ('GND', 'GND'), ('DO', 'LDR_OUT')], 'LDR karti (JSUMO 16067) - VCC/GND/DO; DO -> IO1'),
    ('J6', 'MIC', [('DO', 'MIC_DO'), ('GND', 'GND'), ('3V3', '+3V3')], 'Mikrofon (JSUMO 15771) - OUT/GND/VCC; OUT -> IO42'),
    ('J7', 'ENC', [('CLK', 'ENC_CLK'), ('DT', 'ENC_DT'), ('SW', 'ENC_SW'), ('3V3', '+3V3'), ('GND', 'GND')], 'Enkoder KY-040 (JSUMO) - CLK/DT/SW -> IO41/40/39'),
    ('J8', 'DHT', [('GND', 'GND'), ('DAT', 'DHT_DATA'), ('3V3', '+3V3')], 'DHT11 (JSUMO 15579) - -/OUT/+; OUT -> IO47'),
    ('J9', 'TOUCH', [('OUT', 'TOUCH_OUT'), ('3V3', '+3V3'), ('GND', 'GND')], 'TTP223B (JSUMO 17538) - SIG/VCC/GND; SIG -> IO21'),
    ('J10', 'EXP', [('3V3', '+3V3'), ('GND', 'GND'), ('IO43', 'EXP_IO43'), ('IO44', 'EXP_IO44'), ('IO38', 'EXP_IO38')], 'Genisleme (UART0/I2C) - IO43, IO44, IO38'),
]
SENSOR_GPIO = {'LDR_OUT': 'IO1', 'MIC_AO': 'IO2', 'MIC_DO': 'IO42', 'ENC_CLK': 'IO41', 'ENC_DT': 'IO40',
               'ENC_SW': 'IO39', 'DHT_DATA': 'IO47', 'TOUCH_OUT': 'IO21', 'EXP_IO43': 'IO43/TX',
               'EXP_IO44': 'IO44/RX', 'EXP_IO38': 'IO38'}
ENC_CAPS = [('C5', 'ENC_CLK'), ('C6', 'ENC_DT'), ('C7', 'ENC_SW')]

# SMD'ler el lehimi pedli (HandSolder: ped disari uzun, havya ucu sigar); en kucugu 0805.
FP = {
    'TB2': 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
    'PTC': 'Fuse:Fuse_1812_4532Metric_Pad1.30x3.40mm_HandSolder',
    'SMA': 'Diode_SMD:D_SMA_Handsoldering',
    'CP8': 'Capacitor_THT:CP_Radial_D8.0mm_P3.50mm',
    'C0805': 'Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder',
    'R0805': 'Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder',
    'LED0805': 'LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm_HandSolder',
    'DIP20': 'Package_DIP:DIP-20_W7.62mm_Socket_LongPads',   # CD74HCT245E (PDIP-20), soketle; uzun ped
    'IDC16': 'Connector_IDC:IDC-Header_2x08_P2.54mm_Vertical',
    'H3': 'Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical',
    'H4': 'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',
    'H5': 'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical',
    'MH': 'MountingHole:MountingHole_3.2mm_M3',
    'DEVKIT': 'MagPanel:ESP32-S3-DevKitC-1_Socket',
}

# SMT montaj tedariki (Robotistan / JLCPCB). LCSC numaralari ve stok LCSC urun API'sinden dogrulandi
# (2026-10-02). anahtar -> (BOM 'Comment', uretici, MPN, LCSC, kilif, teknik aciklama)
# R7 10k: 100k (C17407, '(SMT)' kaydi) Robotistan'da stok yok cikti; IO2 bos girisi icin deger onemsiz.
SMT_PARTS = {
    '33R': ('33R 1% SMD Resistor', 'UNI-ROYAL', '0805W8F330JT5E', 'C17634', '0805',
            '0805 33 Ohms 1% 1/8W'),
    '10k': ('10k 1% SMD Resistor', 'UNI-ROYAL', '0805W8F1002T5E', 'C17414', '0805',
            '0805 10K Ohms 1% 1/8W'),
    '2.2k': ('2.2k 1% SMD Resistor', 'UNI-ROYAL', '0805W8F2201T5E', 'C17520', '0805',
             '0805 2.2K Ohms 1% 1/8W'),
    '100nF': ('100nF 50V X7R Ceramic Capacitor', 'YAGEO', 'CC0805KRX7R9BB104', 'C49678', '0805',
              '100nF 50VDC ±10% X7R'),
    '10uF': ('10uF 25V X5R Ceramic Capacitor', 'Samsung', 'CL21A106KAYNNNE', 'C15850', '0805',
             '10uF 25VDC ±10% X5R'),
    'LED': ('Green LED 0805', 'Hubei KENTO', 'KT-0805G', 'C2297', '0805',
            'Green LED 525nm'),
    'PTC': ('PTC Resettable Fuse 6V 1.5A', 'BOURNS', 'MF-MSMF150-2', 'C89648', '1812',
            'PTC Resettable Fuse 6V 1.5A hold 3A trip'),
    'TVS': ('TVS Diode 5V 400W Unidirectional', 'Littelfuse', 'SMAJ5.0A', 'C83329', 'SMA (DO-214AC)',
            'TVS Diode 5V 400W Unidirectional'),
}
SMT_BY_MPN = {v[2]: v for v in SMT_PARTS.values()}

def smt(key):
    """SMD parcanin sematik alanlari (uretici, MPN, LCSC). BOM/CPL ciktilari buradan okur."""
    _, mfr, mpn, lcsc, _, _ = SMT_PARTS[key]
    return {'MPN': mpn, 'Manufacturer': mfr, 'LCSC': lcsc}

# =============================================================================
#  OZEL KUTUPHANE: ESP32-S3-DevKitC-1 sembolu
# =============================================================================
def devkit_symbol_lib():
    """MagPanel.kicad_sym icerigi (S-ifadesi)."""
    name = 'ESP32-S3-DevKitC-1'
    def fx(size=1.27, hide=False, justify=None):
        e = [Sym('effects'), [Sym('font'), [Sym('size'), size, size]]]
        if justify:
            e.append([Sym('justify')] + [Sym(j) for j in justify])
        if hide:
            e.append([Sym('hide'), Sym('yes')])
        return e
    def prop(k, v, x, y, hide=False, justify=None):
        return [Sym('property'), k, v, [Sym('at'), x, y, 0], fx(hide=hide, justify=justify)]
    pins = []
    for i, nm in enumerate(DEVKIT_J1):
        typ = {'3V3': 'power_out' if i == 0 else 'passive', '5V': 'power_in', 'GND': 'power_in', 'RST': 'input'}.get(nm, 'bidirectional')
        pins.append([Sym('pin'), Sym(typ), Sym('line'), [Sym('at'), -15.24, r4(26.67 - i * G), 0], [Sym('length'), 2.54],
                     [Sym('name'), nm, fx()], [Sym('number'), str(i + 1), fx()]])
    for i, nm in enumerate(DEVKIT_J3):
        typ = 'power_in' if nm == 'GND' else 'bidirectional'
        pins.append([Sym('pin'), Sym(typ), Sym('line'), [Sym('at'), 15.24, r4(26.67 - i * G), 180], [Sym('length'), 2.54],
                     [Sym('name'), nm, fx()], [Sym('number'), str(i + 23), fx()]])
    body = [Sym('symbol'), name + '_0_1',
            [Sym('rectangle'), [Sym('start'), -12.7, 29.21], [Sym('end'), 12.7, -29.21],
             [Sym('stroke'), [Sym('width'), 0.254], [Sym('type'), Sym('default')]], [Sym('fill'), [Sym('type'), Sym('background')]]],
            [Sym('text'), 'J1', [Sym('at'), -10.16, 30.48, 0], fx(1.27)],
            [Sym('text'), 'J3', [Sym('at'), 10.16, 30.48, 0], fx(1.27)],
            [Sym('text'), 'ANT', [Sym('at'), 0, 26.67, 0], fx(1.27)],
            [Sym('text'), 'USB', [Sym('at'), 0, -26.67, 0], fx(1.27)]]
    sym = [Sym('symbol'), name,
           [Sym('pin_names'), [Sym('offset'), 1.016]],
           [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')],
           prop('Reference', 'U', 0, 31.75), prop('Value', name, 0, -31.75),
           prop('Footprint', FP['DEVKIT'], 0, -34.29, hide=True),
           prop('Datasheet', 'https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html', 0, 0, hide=True),
           prop('Description', 'ESP32-S3-DevKitC-1 uyumlu gelistirme karti (eldeki: N16R8 klon, 2x USB-C); 2x22 disi soket. Sag sira 1.0in (25.4 mm); resmi Espressif karti 0.9in.', 0, 0, hide=True),
           prop('ki_keywords', 'ESP32 ESP32-S3 DevKitC devkit module socket', 0, 0, hide=True),
           body, [Sym('symbol'), name + '_1_1'] + pins]
    return [Sym('kicad_symbol_lib'), [Sym('version'), 20231120], [Sym('generator'), 'magpanel_gen'],
            [Sym('generator_version'), REV], sym]

# =============================================================================
#  SEMATIK YAZICI
# =============================================================================
def fx(size=1.27, hide=False, justify=None, bold=False, italic=False):
    f = [Sym('font'), [Sym('size'), size, size]]
    if bold:
        f.append([Sym('bold'), Sym('yes')])
    if italic:
        f.append([Sym('italic'), Sym('yes')])
    e = [Sym('effects'), f]
    just = [j for j in (justify or ()) if j != 'center']   # KiCad: ortalama varsayilan, 'center' anahtari yok
    if just:
        e.append([Sym('justify')] + [Sym(j) for j in just])
    if hide:
        e.append([Sym('hide'), Sym('yes')])
    return e

class Inst:
    def __init__(self, sch, lib_id, ref, x, y, rot, mirror):
        self.sch, self.lib_id, self.ref, self.x, self.y, self.rot, self.mirror = sch, lib_id, ref, x, y, rot, mirror
        self.pins = sch.libs.pins(lib_id)

    def pin(self, num):
        p = self.pins[str(num)]
        px, py = schlib.xform(p['x'], p['y'], (self.x, self.y), self.rot, self.mirror)
        d = schlib.dir_vec(p['ang'], self.rot, self.mirror)
        return px, py, (-d[0], -d[1])          # nokta, disari yon

class Schematic:
    def __init__(self, libs, root, title_block):
        self.libs, self.root, self.tb = libs, root, title_block
        self.items, self.symbols, self.lib_ids = [], [], []
        self.parts = {}
        self.netmap = {}                       # (ref, pin) -> net
        self.n_pwr = 0
        self.n_flg = 0
        self.n = 0

    def _u(self, *k):
        self.n += 1
        return uid(PROJ, 'sch', self.n, *k)

    # ---- semboller ----
    def place(self, lib_id, ref, value, x, y, rot=0, mirror=None, footprint='', fields=None,
              ref_at=None, val_at=None, hide_ref=False, hide_val=False, desc=None, datasheet=None,
              power=False, justify=('left',), in_bom=True):
        if lib_id not in self.lib_ids:
            self.lib_ids.append(lib_id)
        inst = Inst(self, lib_id, ref, r4(x), r4(y), rot, mirror)
        flat = self.libs.flat(lib_id)
        lprops = {p[1]: p for p in sexp.find_all(flat, 'property')}
        # gorunen alanlar yatay okunsun: saklanan aci = (0 - donus) mod 180
        fang = (-rot) % 180

        flip = (fang + rot) % 360 == 180          # KiCad 180 derecelik yaziyi okunur cevirir, hizalama da doner
        def fixj(j):
            if not flip or not j:
                return j
            return tuple({'left': 'right', 'right': 'left'}.get(t, t) for t in j)

        def field_at(key, override):
            if override is not None:
                return r4(x + override[0]), r4(y + override[1]), fang, fixj(override[2] if len(override) > 2 else justify)
            lp = sexp.find(lprops[key], 'at')
            fx_, fy_ = schlib.xform(lp[1], lp[2], (x, y), rot, mirror)
            return fx_, fy_, fang, None
        s = [Sym('symbol'), [Sym('lib_id'), lib_id], [Sym('at'), r4(x), r4(y), rot]]
        if mirror:
            s.append([Sym('mirror'), Sym(mirror)])
        s += [[Sym('unit'), 1], [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('no' if (power or not in_bom) else 'yes')],
              [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('no')], [Sym('uuid'), uid(PROJ, 'sym', ref)]]
        rx, ry, ra, rj = field_at('Reference', ref_at)
        s.append([Sym('property'), 'Reference', ref, [Sym('at'), rx, ry, ra], fx(hide=hide_ref or power, justify=rj)])
        vx, vy, va, vj = field_at('Value', val_at)
        s.append([Sym('property'), 'Value', value, [Sym('at'), vx, vy, va], fx(hide=hide_val, justify=vj)])
        s.append([Sym('property'), 'Footprint', footprint, [Sym('at'), r4(x), r4(y), 0], fx(hide=True)])
        ds = datasheet if datasheet is not None else (lprops['Datasheet'][2] if 'Datasheet' in lprops else '')
        s.append([Sym('property'), 'Datasheet', ds, [Sym('at'), r4(x), r4(y), 0], fx(hide=True)])
        de = desc if desc is not None else (lprops['Description'][2] if 'Description' in lprops else '')
        s.append([Sym('property'), 'Description', de, [Sym('at'), r4(x), r4(y), 0], fx(hide=True)])
        for k, v in (fields or {}).items():
            s.append([Sym('property'), k, v, [Sym('at'), r4(x), r4(y), 0], fx(hide=True)])
        for num in sorted(inst.pins, key=lambda t: (len(t), t)):
            s.append([Sym('pin'), num, [Sym('uuid'), uid(PROJ, 'pin', ref, num)]])
        s.append([Sym('instances'), [Sym('project'), PROJ,
                  [Sym('path'), '/' + self.root, [Sym('reference'), ref], [Sym('unit'), 1]]]])
        self.symbols.append(s)
        if not power:
            self.parts[ref] = dict(lib_id=lib_id, value=value, footprint=footprint, fields=fields or {},
                                   desc=de, inst=inst, uuid=uid(PROJ, 'sym', ref), in_bom=in_bom)
        return inst

    # govdenin bakacagi yon -> (donus, deger yazisi konumu)
    _GND_DIR = {(0, 1): (0, (0, 3.81, ('center',))), (-1, 0): (270, (-3.3, 0, ('right',))),
                (1, 0): (90, (3.3, 0, ('left',))), (0, -1): (180, (0, -3.81, ('center',)))}
    _VCC_DIR = {(0, -1): (0, (0, -3.56, ('center',))), (-1, 0): (90, (-3.3, 0, ('right',))),
                (1, 0): (270, (3.3, 0, ('left',))), (0, 1): (180, (0, 3.56, ('center',)))}

    def power_sym(self, kind, x, y, rot=None, toward=None):
        """Guc sembolu. toward: govdenin uzanacagi ekran yonu (varsayilan GND asagi, +V yukari)."""
        table = self._GND_DIR if kind == 'GND' else self._VCC_DIR
        if toward is None:
            toward = (0, 1) if kind == 'GND' else (0, -1)
        r, vat = table[toward]
        if rot is not None:
            r, vat = rot, None
        if kind == 'PWR_FLAG':
            self.n_flg += 1
            ref = '#FLG%02d' % self.n_flg
        else:
            self.n_pwr += 1
            ref = '#PWR%03d' % self.n_pwr
        return self.place('power:' + kind, ref, kind, x, y, rot=r, power=True, val_at=vat)

    # ---- cizim ogeleri ----
    def wire(self, *pts):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            self.items.append([Sym('wire'), [Sym('pts'), [Sym('xy'), r4(x1), r4(y1)], [Sym('xy'), r4(x2), r4(y2)]],
                               [Sym('stroke'), [Sym('width'), 0], [Sym('type'), Sym('default')]], [Sym('uuid'), self._u('w')]])

    def junction(self, x, y):
        self.items.append([Sym('junction'), [Sym('at'), r4(x), r4(y)], [Sym('diameter'), 0],
                           [Sym('color'), 0, 0, 0, 0], [Sym('uuid'), self._u('j')]])

    def label(self, name, x, y, out):
        ang, just = {(1, 0): (0, ('left', 'bottom')), (-1, 0): (180, ('right', 'bottom')),
                     (0, -1): (90, ('left', 'bottom')), (0, 1): (270, ('right', 'bottom'))}[out]
        self.items.append([Sym('label'), name, [Sym('at'), r4(x), r4(y), ang], [Sym('fields_autoplaced'), Sym('yes')],
                           fx(justify=just), [Sym('uuid'), self._u('l', name)]])

    def text(self, s, x, y, size=1.27, bold=False, italic=False, justify=('left', 'bottom')):
        self.items.append([Sym('text'), s, [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), r4(x), r4(y), 0],
                           fx(size=size, bold=bold, italic=italic, justify=justify), [Sym('uuid'), self._u('t')]])

    def frame(self, x0, y0, x1, y1, title):
        self.items.append([Sym('rectangle'), [Sym('start'), r4(x0), r4(y0)], [Sym('end'), r4(x1), r4(y1)],
                           [Sym('stroke'), [Sym('width'), 0.254], [Sym('type'), Sym('dash')], [Sym('color'), 72, 72, 72, 1]],
                           [Sym('fill'), [Sym('type'), Sym('none')]], [Sym('uuid'), self._u('r')]])
        self.text(title, x0 + 1.27, y0 + 3.81, size=2.0, bold=True)

    def nc(self, inst, num):
        x, y, _ = inst.pin(num)
        self.items.append([Sym('no_connect'), [Sym('at'), x, y], [Sym('uuid'), self._u('nc')]])

    # ---- baglanti yardimcilari (net kaydi da tutar) ----
    def assign(self, inst, num, net):
        key = (inst.ref, str(num))
        if self.netmap.get(key, net) != net:
            raise ValueError('pin iki farkli nette: %s %s/%s' % (key, self.netmap[key], net))
        self.netmap[key] = net

    def stub(self, inst, num, net, length=2 * G):
        """Pinden disari kisa tel + yerel etiket."""
        x, y, (ox, oy) = inst.pin(num)
        ex, ey = r4(x + ox * length), r4(y + oy * length)
        self.wire((x, y), (ex, ey))
        self.label(net, ex, ey, (ox, oy))
        self.assign(inst, num, net)
        return ex, ey

    def pwr(self, inst, num, kind, length=G):
        """Pinden disari tel + guc sembolu (GND govdesi asagi, +V govdesi yukari)."""
        x, y, (ox, oy) = inst.pin(num)
        ex, ey = r4(x + ox * length), r4(y + oy * length)
        if length:
            self.wire((x, y), (ex, ey))
        self.power_sym(kind, ex, ey, toward=(ox, oy))
        self.assign(inst, num, kind)
        return ex, ey

    # ---- yazdir ----
    def document(self):
        tb = [Sym('title_block'), [Sym('title'), self.tb['title']], [Sym('date'), self.tb['date']],
              [Sym('rev'), self.tb['rev']], [Sym('company'), self.tb['company']]]
        for i, c in enumerate(self.tb.get('comments', []), 1):
            tb.append([Sym('comment'), i, c])
        return ([Sym('kicad_sch'), [Sym('version'), 20231120], [Sym('generator'), 'eeschema'],
                 [Sym('generator_version'), '8.0'], [Sym('uuid'), self.root], [Sym('paper'), 'A3'], tb,
                 [Sym('lib_symbols')] + [self.libs.flat(l) for l in self.lib_ids]]
                + self.items + self.symbols
                + [[Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]]])

# =============================================================================
#  SEMATIK ICERIGI
# =============================================================================
def build_schematic(libs):
    root = uid(PROJ, 'root')
    sch = Schematic(libs, root, dict(
        title='MagPanel Carrier - ESP32-S3 + 3x HUB75E + sensorler',
        date=DATE, rev=REV, company='MagPanel (github.com/Kem4lk/magpanel)',
        comments=['Seviye donusturucu: 2x 74HCT245 DIP (3.3 V -> 5 V), seri 33R, LAT/OE pull-down',
                  'Pinler: include/app_constants.hpp, include/panel_sm16380.h, include/sensors.h',
                  'hardware/kicad/gen_carrier.py ile uretildi - elle duzenleme yerine ureticiyi degistir']))
    P = lambda gx, gy: (r4(gx * G), r4(gy * G))   # izgara birimi -> mm

    # ------------------------------------------------------------ 1) 5V GIRIS
    sch.frame(*P(6, 6), *P(54, 31), '1  5 V GIRIS / KORUMA')
    x, y = P(12, 14)
    j1 = sch.place('Connector:Screw_Terminal_01x02', 'J1', '5V IN', x, y, mirror='y',
                   footprint=FP['TB2'], ref_at=(-2.54, -3.81, ('right',)), val_at=(-2.54, 6.35, ('right',)),
                   fields={'MPN': 'Phoenix MKDS 1,5/2-5,08 (1714955) ya da esdegeri'},
                   desc='5 V DC giris (PSU). Panel gucu PSU -> panel dogrudan; bu kart <= 1 A ceker.')
    f1 = sch.place('Device:Polyfuse', 'F1', '1.5A', *P(20, 14), rot=90, footprint=FP['PTC'],
                   ref_at=(0, -3.81, ('center',)), val_at=(0, 3.81, ('center',)),
                   fields=smt('PTC'),
                   desc='Kendini sifirlayan sigorta: asiri akim / ters kutupta (D1 iletir) acar')
    p1x, p1y, _ = j1.pin(1)
    p2x, p2y, _ = j1.pin(2)
    fa = f1.pin(1)
    fb = f1.pin(2)
    sch.wire((p1x, p1y), (P(16, 14)[0], p1y))
    sch.wire((P(16, 14)[0], p1y), (fa[0], fa[1]))
    sch.label('VIN', P(16, 14)[0], p1y, (1, 0))
    sch.assign(j1, 1, 'VIN'); sch.assign(f1, 1, 'VIN')
    sch.wire((p2x, p2y), (p2x, P(0, 17)[1]), (p2x, P(0, 19)[1]))
    sch.power_sym('GND', p2x, P(0, 19)[1])
    sch.power_sym('PWR_FLAG', p2x, P(0, 17)[1], toward=(1, 0))
    sch.assign(j1, 2, 'GND')
    rail_y = fb[1]
    xs = [P(24, 0)[0], P(31, 0)[0], P(38, 0)[0], P(45, 0)[0], P(49, 0)[0], P(52, 0)[0]]
    sch.wire((fb[0], rail_y), *[(xx, rail_y) for xx in xs])
    sch.assign(f1, 2, '+5V')
    sch.power_sym('+5V', xs[-1], rail_y)
    sch.power_sym('PWR_FLAG', xs[-2], rail_y)   # +5V'u ERC icin surulmus say
    for xx in xs[:-1]:
        sch.junction(xx, rail_y)
    # D1 TVS (katot +5V)
    d1 = sch.place('Diode:SMAJ5.0A', 'D1', 'SMAJ5.0A', xs[0], P(0, 17)[1], rot=270, footprint=FP['SMA'],
                   ref_at=(2.54, -1.27), val_at=(2.54, 1.27),
                   fields=smt('TVS'),
                   desc='TVS: ters kutup/asiri gerilimde iletir -> F1 acar')
    k = d1.pin(1)
    sch.wire((xs[0], rail_y), (k[0], k[1])); sch.assign(d1, 1, '+5V')
    sch.pwr(d1, 2, 'GND', length=0)
    c1 = sch.place('Device:C_Polarized', 'C1', '470uF 10V', xs[1], P(0, 17)[1], footprint=FP['CP8'],
                   ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields={'MPN': 'Elektrolitik 470 uF 10 V, D8 P3.5 (low ESR)'},
                   desc='5 V giris tamponu (kablo enduktansi, tampon anahtarlama akimlari)')
    t = c1.pin(1); sch.wire((xs[1], rail_y), (t[0], t[1])); sch.assign(c1, 1, '+5V')
    sch.pwr(c1, 2, 'GND', length=0)
    c2 = sch.place('Device:C', 'C2', '10uF', xs[2], P(0, 17)[1], footprint=FP['C0805'],
                   ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields=smt('10uF'),
                   desc='5 V giris seramik dekuplaj')
    t = c2.pin(1); sch.wire((xs[2], rail_y), (t[0], t[1])); sch.assign(c2, 1, '+5V')
    sch.pwr(c2, 2, 'GND', length=0)
    r1 = sch.place('Device:R', 'R1', '2.2k', xs[3], P(0, 16.5)[1], footprint=FP['R0805'],
                   ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields=smt('2.2k'),
                   desc='PWR LED akim siniri (~1 mA)')
    t = r1.pin(1); sch.wire((xs[3], rail_y), (t[0], t[1])); sch.assign(r1, 1, '+5V')
    d2 = sch.place('Device:LED', 'D2', 'PWR (yesil)', xs[3], P(0, 21)[1], rot=90, footprint=FP['LED0805'],
                   ref_at=(4.45, -1.27), val_at=(4.45, 1.27), fields=smt('LED'),
                   desc='5 V var gostergesi')
    ra = r1.pin(2); la = d2.pin(2)
    sch.wire((ra[0], ra[1]), (la[0], la[1]))
    sch.label('LED_PWR', ra[0], ra[1], (-1, 0))
    sch.assign(r1, 2, 'LED_PWR'); sch.assign(d2, 2, 'LED_PWR')
    sch.pwr(d2, 1, 'GND', length=0)
    sch.text('PSU 5 V -> bu kart (<= 1 A: ESP32 + tamponlar + sensorler).\n'
             'Panel gucu PSU -> panel DOGRUDAN (kalin kablo), bu karttan gecmez.\n'
             'Ters kutup / asiri gerilim: D1 iletir -> F1 (PTC) acar, kendini sifirlar.',
             *P(7, 26), size=1.27)

    # ------------------------------------------------------------ 2) DEVKIT
    sch.frame(*P(6, 33), *P(54, 80), '2  ESP32-S3-DevKitC-1 (soket)')
    u1 = sch.place('MagPanel:ESP32-S3-DevKitC-1', 'U1', 'ESP32-S3-DevKitC-1', *P(30, 57), footprint=FP['DEVKIT'],
                   ref_at=(0, -31.75, ('center',)), val_at=(0, 31.75, ('center',)),
                   fields={'MPN': 'ESP32-S3 N16R8 klon (YD-ESP32-S3 tipi, siralar arasi 1.0in) + 2x 1x22 disi soket (2.54 mm)'})
    gpio_net = {v: k for k, v in HUB_GPIO.items()}
    gpio_net.update({v: k for k, v in SENSOR_GPIO.items()})
    # yan yana ayni-net pin ciftleri: kisa tel + dikey birlestirme + tek guc sembolu
    for (pa, pb, net) in (('1', '2', '+3V3'), ('43', '44', 'GND')):
        ax, ay, (aox, _) = u1.pin(pa)
        bx, by, _ = u1.pin(pb)
        ex = r4(ax + aox * G)
        sch.wire((ax, ay), (ex, ay))
        sch.wire((bx, by), (ex, by))
        sch.wire((ex, ay), (ex, by))
        if net == 'GND':
            sch.wire((ex, by), (ex, r4(by + G)))
            sch.power_sym('GND', ex, r4(by + G))
        else:
            sch.wire((ex, ay), (ex, r4(ay - G)))
            sch.power_sym('+3V3', ex, r4(ay - G))
        sch.junction(ex, by if net != 'GND' else ay)
        sch.junction(ex, ay if net != 'GND' else by)
        sch.assign(u1, pa, net); sch.assign(u1, pb, net)
    for i, nm in enumerate(DEVKIT_J1 + DEVKIT_J3):
        num = str(i + 1)
        if num in ('1', '2', '43', '44'):
            continue
        if nm == '3V3':
            sch.pwr(u1, num, '+3V3', length=G)
        elif nm == '5V':
            sch.pwr(u1, num, '+5V', length=G)
        elif nm == 'GND':
            sch.pwr(u1, num, 'GND', length=G)
        elif nm in gpio_net:
            sch.stub(u1, num, gpio_net[nm], length=2 * G)
        else:
            sch.nc(u1, num)
    sch.text('Sag soket 1.0in (25.4 mm; YD-ESP32-S3 tipi N16R8 klon). Resmi kart: 0.9in.\n'
             'Anten (ust) kart kenarindan tasar; USB (alt) kart kenarinda.\n'
             'Kullanilmayan: IO0/45/46 strapping, IO35-37 OPI PSRAM, IO19/20 USB, IO48 (klon RGB LED).',
             *P(7, 76.5), size=1.27)

    # ------------------------------------------------------------ 3) TAMPONLAR
    sch.frame(*P(57, 6), *P(104, 80), '3  SEVIYE DONUSTURUCU 3.3 V -> 5 V (2x 74HCT245)')
    for ref, gy, cref in (('U2', 23, 'C3'), ('U3', 56, 'C4')):
        u = sch.place('74xx:74HC245', ref, '74HCT245', *P(80, gy), footprint=FP['DIP20'],
                      ref_at=(2.54, -21.59, ('left',)), val_at=(2.54, 21.59, ('left',)),
                      fields={'MPN': 'CD74HCT245E (PDIP-20) + 20 pin DIP soket'},
                      desc='Octal bus transceiver, HCT = TTL girisli (3.3 V mantik 5 V beslemede gecerli); DIR=+5V (A->B), /OE=GND',
                      datasheet='https://www.ti.com/lit/ds/symlink/cd74hct245.pdf')
        for i, sig in enumerate(BUF_CH[ref]):
            sch.stub(u, str(2 + i), sig, length=2 * G)               # A0..A7 (3.3 V tarafi)
            sch.stub(u, str(18 - i), sig + '_5V', length=2 * G)      # B0..B7
        sch.pwr(u, '1', '+5V', length=2 * G)                         # DIR = A->B
        sch.pwr(u, '19', 'GND', length=2 * G)                        # /OE
        sch.pwr(u, '20', '+5V', length=0)
        sch.pwr(u, '10', 'GND', length=0)
        c = sch.place('Device:C', cref, '100nF', *P(98, gy - 6), footprint=FP['C0805'],
                      ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields=smt('100nF'),
                      desc='74HCT245 VCC dekuplaj (pin 20 yaninda)')
        sch.pwr(c, '1', '+5V', length=0)
        sch.pwr(c, '2', 'GND', length=0)
    c8 = sch.place('Device:C', 'C8', '10uF', *P(98, 37), footprint=FP['C0805'],
                   ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields=smt('10uF'),
                   desc='Tamponlar icin yerel 5 V yigin kapasitesi')
    sch.pwr(c8, '1', '+5V', length=0)
    sch.pwr(c8, '2', 'GND', length=0)
    for i, (ref, net) in enumerate(PULLDOWNS):
        r = sch.place('Device:R', ref, '10k', *P(63 + i * 7, 72.5), footprint=FP['R0805'],
                      ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields=smt('10k'),
                      desc='Pull-down: acilista GPIO surulmezken LAT/OE dusuk -> panel karanlik')
        x0, y0, _ = r.pin('1')
        sch.wire((x0, y0), (x0, y0 - G))
        sch.label(net, x0, y0 - G, (1, 0))
        sch.assign(r, '1', net)
        sch.pwr(r, '2', 'GND', length=0)
    sch.text('Kanal sirasi DevKit J1 pin sirasini izler (PCB: kesisimsiz).\n'
             'Pull-down (R2-R5): acilista LAT/LAT2/LAT3/OE dusuk -> panel karanlik kalir.',
             *P(58, 77.5), size=1.27)

    # ------------------------------------------------------------ 4) HUB75 CIKISLARI
    sch.frame(*P(107, 6), *P(161, 80), '4  HUB75E CIKISLARI (seri 33R, 3 panel)')
    for i, (ref, sig, _) in enumerate(SERIES_R):
        gy = 10 + i * 3.5 + (1.5 if i >= 8 else 0)                    # U2 grubu ust, U3 grubu alt
        r = sch.place('Device:R', ref, '33R', *P(117, gy), rot=90, footprint=FP['R0805'],
                      ref_at=(0, -2.54, ('center',)), val_at=(0, 2.54, ('center',)),
                      fields=smt('33R'),
                      desc='Seri sonlandirma: kablo yansimalarini/zil (ringing) bastirir')
        sch.stub(r, '1', sig + '_5V', length=2 * G)                    # tampon tarafi
        sch.stub(r, '2', 'HUB_' + sig, length=2 * G)                   # konnektor tarafi
    sch.text('R10-R25: her hatta 33R seri (0805).\nPCB: tek sutun, her direnc kendi\ntampon pininin satirinda.',
             *P(108, 70), size=1.27)
    for i, (ref, latnet, title, note) in enumerate(HUB_CONN):
        gy = 18 + i * 20
        j = sch.place('Connector_Generic:Conn_02x08_Odd_Even', ref, 'HUB75E ' + title, *P(144, gy),
                      footprint=FP['IDC16'], ref_at=(1.27, -12.7, ('center',)), val_at=(1.27, 15.24, ('center',)),
                      fields={'MPN': 'Kutu baslik (box header) 2x8 2.54 mm, duz'},
                      desc='HUB75E panel cikisi: ' + note)
        for pin, sig in HUB_PINS.items():
            if sig == 'GND':
                sch.pwr(j, str(pin), 'GND', length=G)
            elif sig is None:
                sch.stub(j, str(pin), 'HUB_' + latnet, length=2 * G)
            else:
                sch.stub(j, str(pin), 'HUB_' + sig, length=2 * G)
        sch.text(title + ': ' + note, *P(131, gy - 7.5), size=1.27, bold=True)
    sch.text('HUB75E: 1 R1  2 G1  3 B1  4 GND  5 R2  6 G2  7 B2  8 E\n'
             '9 A  10 B  11 C  12 D  13 CLK  14 LAT  15 OE  16 GND\n'
             'Coklu P1.86: tum hatlar paralel, LAT panel basina ayri.',
             *P(108, 75), size=1.27)

    # ------------------------------------------------------------ 5) SENSORLER
    sch.frame(*P(6, 83), *P(118, 112), '5  SENSOR / KONTROL BASLIKLARI (3.3 V)')
    for i, (ref, name, pins, desc) in enumerate(SENSOR_HDRS):
        n = len(pins)
        j = sch.place('Connector_Generic:Conn_01x%02d' % n, ref, name, *P(19 + i * 17, 90), footprint=FP['H%d' % n],
                      ref_at=(2.54, -1.27, ('left',)), val_at=(2.54, 1.27, ('left',)),
                      fields={'MPN': 'Pin header 1x%d 2.54 mm erkek (Dupont)' % n}, desc=desc)
        for k, (lbl, net) in enumerate(pins, 1):
            if net in ('+3V3', 'GND'):
                sch.pwr(j, str(k), net, length=8 * G)    # sinyal etiketlerinin otesinde (cakismasin)
            else:
                sch.stub(j, str(k), net, length=3 * G)
        sch.text(desc.split(' - ')[0], *P(9 + i * 17, 97), size=1.0)
        if ' - ' in desc:
            sch.text(desc.split(' - ')[1], *P(9 + i * 17, 98.3), size=1.0)
    for i, (ref, net) in enumerate(ENC_CAPS):
        c = sch.place('Device:C', ref, '100nF', *P(42 + i * 6, 107), footprint=FP['C0805'],
                      ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields=smt('100nF'),
                      desc='Enkoder RC debounce (modul 10k + 100nF ~ 1 ms)')
        x0, y0, _ = c.pin('1')
        sch.wire((x0, y0), (x0, y0 - G))
        sch.label(net, x0, y0 - G, (0, -1))
        sch.assign(c, '1', net)
        sch.pwr(c, '2', 'GND', length=0)
    r7 = sch.place('Device:R', 'R7', '10k', *P(30, 105), footprint=FP['R0805'],
                   ref_at=(2.54, -1.27), val_at=(2.54, 1.27), fields=smt('10k'),
                   desc='IO2 (analog mikrofon girisi) bosta gurultu okumasin: eldeki mikrofon modulu yalniz dijital')
    x0, y0, _ = r7.pin('1')
    sch.wire((x0, y0), (x0, y0 - G))
    sch.label('MIC_AO', x0, y0 - G, (1, 0))
    sch.assign(r7, '1', 'MIC_AO')
    sch.pwr(r7, '2', 'GND', length=0)
    r6 = sch.place('Device:R', 'R6', '10k', *P(64, 107), rot=90, footprint=FP['R0805'],
                   ref_at=(0, -2.54, ('center',)), val_at=(0, 2.54, ('center',)), fields=smt('10k'),
                   desc='DHT11 DATA pull-up (ciplak sensor icin; modul uzerindekiyle paralel sorun degil)')
    sch.pwr(r6, '1', '+3V3', length=G)
    sch.stub(r6, '2', 'DHT_DATA', length=2 * G)
    sch.text('Pin sirasi eldeki modullerin baskisiyla ayni; PCB uzerinde her pin etiketli.\n'
             'LDR ve mikrofon modulleri yalniz dijital cikisli. Baglanmamis sensor zararsiz.',
             *P(76, 104), size=1.27)

    # ------------------------------------------------------------ 6) MEKANIK
    sch.frame(*P(121, 83), *P(161, 96), '6  MEKANIK')
    for i in range(4):
        sch.place('Mechanical:MountingHole', 'H%d' % (i + 1), 'M3', *P(126 + i * 8, 91), footprint=FP['MH'],
                  ref_at=(0, -3.81, ('center',)), val_at=(0, 3.81, ('center',)),
                  desc='M3 montaj deligi (izole, NPTH) - panel arkasina M3 aralik/miknatis', in_bom=False)
    return sch

# =============================================================================
#  PROJE DOSYALARI
# =============================================================================
POWER_NETS = ('+5V', '+3V3', 'GND')     # guc sembolleri (global); digerleri yerel etiket -> '/AD'

def pcb_net(n):
    return n if n in POWER_NETS else '/' + n

NETCLASSES = [
    # ad, iz, aciklik, via cap, via delik, desenler
    ('Default', 0.25, 0.2, 0.6, 0.3, []),
    ('Power', 0.8, 0.25, 0.8, 0.4, ['+5V', '/VIN']),
    ('Power3V3', 0.5, 0.2, 0.6, 0.3, ['+3V3']),
    ('GND', 0.5, 0.2, 0.6, 0.3, ['GND']),
]

def write_project_files():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'MagPanel.pretty').mkdir(exist_ok=True)
    (OUT / 'sym-lib-table').write_text(
        '(sym_lib_table\n  (version 7)\n'
        '  (lib (name "MagPanel")(type "KiCad")(uri "${KIPRJMOD}/MagPanel.kicad_sym")(options "")(descr "MagPanel proje sembolleri"))\n)\n')
    (OUT / 'fp-lib-table').write_text(
        '(fp_lib_table\n  (version 7)\n'
        '  (lib (name "MagPanel")(type "KiCad")(uri "${KIPRJMOD}/MagPanel.pretty")(options "")(descr "MagPanel proje footprintleri"))\n)\n')
    (OUT / 'MagPanel.kicad_sym').write_text(sexp.dumps(devkit_symbol_lib()) + '\n')
    pro = OUT / (PROJ + '.kicad_pro')
    data = json.loads(pro.read_text()) if pro.exists() else {}
    data.setdefault('meta', {'filename': PROJ + '.kicad_pro', 'version': 1})
    classes = []
    for name, tw, cl, vd, vdr, _ in sorted(NETCLASSES, key=lambda nc: (nc[0] != 'Default', nc[0])):   # KiCad sirasi
        classes.append({'name': name, 'track_width': tw, 'clearance': cl, 'via_diameter': vd, 'via_drill': vdr,
                        'bus_width': 12, 'wire_width': 6, 'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25,
                        'diff_pair_width': 0.2, 'line_style': 0, 'microvia_diameter': 0.3, 'microvia_drill': 0.1,
                        'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)'})
    data['net_settings'] = {
        'classes': classes, 'meta': {'version': 3}, 'net_colors': None, 'netclass_assignments': None,
        'netclass_patterns': [{'netclass': nc[0], 'pattern': p} for nc in NETCLASSES for p in nc[5]]}
    data.setdefault('text_variables', {})
    data['text_variables'].update({'REV': REV, 'DATE': DATE})
    pro.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')

def stage_sch():
    write_project_files()
    libs = schlib.SymbolLibs(extra={'MagPanel': str(OUT / 'MagPanel.kicad_sym')})
    sch = build_schematic(libs)
    (OUT / (PROJ + '.kicad_sch')).write_text(sexp.dumps(sch.document()) + '\n')
    # PCB asamasi icin parca + net tablosu (sematikle tek kaynak)
    parts = {}
    for ref, p in sch.parts.items():
        parts[ref] = dict(value=p['value'], footprint=p['footprint'], uuid=p['uuid'], fields=p['fields'],
                          desc=p['desc'], in_bom=p['in_bom'],
                          pins={num: sch.netmap.get((ref, num)) for num in p['inst'].pins})
    (OUT / 'netlist.json').write_text(json.dumps(parts, indent=1, sort_keys=True) + '\n')
    print('sematik: %d parca, %d net' % (len(parts), len(set(sch.netmap.values()))))
    return sch

# =============================================================================
#  PCB (pcbnew python API; KiCad 8)
# =============================================================================
BOARD_W, BOARD_H = 100.0, 63.5
ORIGIN = (50.0, 50.0)            # kartin sol-ust kosesi (KiCad sayfa koordinati, mm)
PLACE_ORIGIN = (0.0, BOARD_H)    # gerber/delik/yerlesim dosyasi orijini: kartin sol-alt kosesi (yerel mm, Y yukari)
J1X, PIN1Y = 56.5, 1.6           # DevKit J1 pin 1: ust kenara 1.6 mm -> anten kartin DISINDA kalir
XA = 51.0                        # 74HCT245 A sutunu (pin 1..10; B sutunu XA - 7.62)
XR = J1X + DEVKIT_ROW_IN         # DevKit sag sira (sensorlere en yakin)
# El lehimi: tum courtyard'lar arasi >= 0.5 mm (DRU kurali 'el_lehim_aralik'), 0805 en kucuk parca.
RCOL = 39.4                      # seri 33R sutunu (+ C3/C4/C8): DIP soket courtyard'ina 0.5 mm
HUB_X0, HUB_PITCH, HUB_Y = 5.1, 12.8, 13.2   # J2..J4 pin 1; govdeler arasi 3.8 mm (eskiden 2.4)
DEV_OFF = 4.5                    # DevKit altindaki SMD'ler: soket sirasina uzaklik (govdeye 1.6 mm bosluk)

def pin_y(n):
    """DevKit baslik pin n (1..22) y konumu (yerel mm); kesirli n iki pinin arasi."""
    return PIN1Y + (n - 1) * G

# DIP-20'ler 180 derece: A pinleri saga (DevKit'e), B pinleri sola (seri dizilere). 2.54 mm adim DevKit ile
# ayni: U2 pin 1 = satir 11 (pin 10 = satir 2), U3 pin 1 = satir 22 (pin 10 = satir 13).
# A girisleri DevKit satirindan 1-2 satir asagi kayar (paralel kisa izler, kesisim yok).
U2_ROW1, U3_ROW1 = 11, 22

# ref -> (x, y, donus derece, katman)
PLACE = {
    'U1': (J1X, PIN1Y, 0, 'F'),
    'J2': (HUB_X0, HUB_Y, 0, 'F'), 'J3': (HUB_X0 + HUB_PITCH, HUB_Y, 0, 'F'),
    'J4': (HUB_X0 + 2 * HUB_PITCH, HUB_Y, 0, 'F'),
    'U2': (XA, pin_y(U2_ROW1), 180, 'F'), 'U3': (XA, pin_y(U3_ROW1), 180, 'F'),
    # seri 33R (R10..R25): SERIES_R'den asagida eklenir (her biri kendi B pininin satirinda)
    # dekuplaj: VCC (pin 20) B sutununun en altinda, direnc sutununda bos kalan satirlarda
    'C3': (RCOL, pin_y(U2_ROW1), 180, 'F'), 'C4': (RCOL, pin_y(U3_ROW1), 180, 'F'),
    'C8': (RCOL, pin_y(U3_ROW1) + 2.7, 180, 'F'),
    # DevKit altinda (soketler 8.5 mm: kart ustte kalir); once bunlar lehimlenir, sonra soketler
    'R2': (J1X + DEV_OFF, pin_y(16), 0, 'F'), 'R3': (J1X + DEV_OFF, pin_y(10), 0, 'F'),
    'R4': (J1X + DEV_OFF, pin_y(20), 0, 'F'), 'R5': (J1X + DEV_OFF, pin_y(17), 0, 'F'),
    'C5': (XR - DEV_OFF, pin_y(7), 180, 'F'), 'C6': (XR - DEV_OFF, pin_y(8), 180, 'F'),
    'C7': (XR - DEV_OFF, pin_y(9), 180, 'F'), 'R6': (XR - DEV_OFF, pin_y(17), 0, 'F'),
    'R7': (XR - DEV_OFF, pin_y(5), 180, 'F'),
    # 5V giris blogu (sol-alt; vida klemensi kablo girisi sol kenara bakar). D1 (TVS) dogrudan
    # J1 GND'sine kalin izle baglanir; C2 ve R1 +5V ana hattina (x = C1+) kisa kolla.
    'J1': (5.5, 43.5, 270, 'F'), 'F1': (15.2, 43.5, 0, 'F'), 'D1': (16.5, 48.58, 180, 'F'),
    'C1': (24.3, 45.0, 0, 'F'), 'C2': (21.3, 53.0, 180, 'F'), 'R1': (21.3, 56.0, 180, 'F'),
    'D2': (16.8, 56.0, 0, 'F'),
    # sensor basliklari: sutun A (x=89.5) LDR/MIC/ENC, sutun B (x=96) EXP/DHT/TOUCH
    'J5': (89.5, 10.0, 0, 'F'), 'J6': (89.5, 20.16, 0, 'F'), 'J7': (89.5, 32.86, 0, 'F'),
    'J10': (96.0, 10.0, 0, 'F'), 'J8': (96.0, 25.24, 0, 'F'), 'J9': (96.0, 35.4, 0, 'F'),
    'H1': (3.5, 3.5, 0, 'F'), 'H2': (96.5, 3.5, 0, 'F'), 'H3': (3.5, 60.0, 0, 'F'), 'H4': (96.5, 60.0, 0, 'F'),
}
# 180 derece: ped 1 (*_5V) saga, tampon B pinine; ped 2 (HUB_*) sola, konnektorlere
PLACE.update({ref: (RCOL, pin_y(row), 180, 'F') for ref, _, row in SERIES_R})
# SMD/DIP GND pedlerinin yanina sabit via (alt GND dokumune kisa yol). (ref, ped): (dx, dy) ped merkezinden
# Via kenari ped kenarindan >= 0.6 mm (maskeli via; lehim via'ya akmaz).
GND_VIAS = {
    ('U2', '10'): (-2.15, 0), ('U2', '19'): (2.25, 0), ('U3', '10'): (-2.15, 0), ('U3', '19'): (2.25, 0),
    ('C3', '2'): (0, 1.6), ('C4', '2'): (-1.65, 0), ('C8', '2'): (-1.65, 0),
    ('R2', '2'): (1.65, 0), ('R3', '2'): (1.65, 0), ('R4', '2'): (1.65, 0), ('R5', '2'): (1.65, 0),
    ('C5', '2'): (-1.65, 0), ('C6', '2'): (-1.65, 0), ('C7', '2'): (-1.65, 0), ('R7', '2'): (-1.65, 0),
    ('C2', '2'): (-1.65, 0), ('D2', '1'): (-1.65, 0),
}
TRUNK_W = 1.0          # +5V ana hat (mm)
TRUNK_Y = 60.8         # ana hat tamponlarin ALTINDAN gecer (alt serit)
TRUNK_X = J1X + 2.8    # DevKit 5V pinine sagdan (DevKit altindan) girer

def mm(v):
    import pcbnew
    return pcbnew.FromMM(v)

def V(x, y):
    import pcbnew
    return pcbnew.VECTOR2I(pcbnew.FromMM(ORIGIN[0] + x), pcbnew.FromMM(ORIGIN[1] + y))

def make_devkit_footprint():
    """MagPanel:ESP32-S3-DevKitC-1_Socket: sol sira + DEVKIT_RIGHT_ROWS'taki sag sira(lar) (ayni pin no)."""
    import pcbnew
    pcbnew.KIID.SeedGenerator(0x4D50)          # sabit UUID'ler: ayni girdi -> ayni dosya (git farki yok)
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPIDAsString('ESP32-S3-DevKitC-1_Socket')
    fp.SetReference('REF**')
    rows = DEVKIT_RIGHT_ROWS
    xin, xout = min(rows), max(rows)
    fp.SetLibDescription('ESP32-S3-DevKitC-1 icin 2x 1x22 disi soket (2.54 mm). Sag sira(lar): %s mm '
                         '(22.86 = resmi Espressif 0.9in, 25.40 = yaygin N16R8 klonu 1.0in). '
                         'Pin 1 (3V3) anten tarafinda.' % ', '.join('%.2f' % r for r in rows))
    fp.SetKeywords('ESP32-S3 DevKitC-1 devkit socket 2x22 0.9in 1.0in')
    fp.SetAttributes(pcbnew.FP_THROUGH_HOLE)
    for i in range(22):
        for x, num in [(0.0, i + 1)] + [(r, i + 23) for r in rows]:
            pad = pcbnew.PAD(fp)
            pad.SetNumber(str(num))
            pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            pad.SetShape(pcbnew.PAD_SHAPE_RECT if i == 0 else pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pcbnew.VECTOR2I(mm(1.7), mm(1.7)))
            pad.SetDrillSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
            pad.SetLayerSet(pad.PTHMask())
            pad.SetPosition(pcbnew.VECTOR2I(mm(x), mm(i * G)))
            fp.Add(pad)
    def line(layer, x1, y1, x2, y2, w=0.15):
        sh = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); sh.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        sh.SetLayer(layer); sh.SetWidth(mm(w)); fp.Add(sh)
    def rect(layer, x1, y1, x2, y2, w=0.1):
        for a, b, c, d in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)):
            line(layer, a, b, c, d, w)
    def text(layer, s, x, y, size=0.8, angle=0, th=0.15):
        t = pcbnew.PCB_TEXT(fp)
        t.SetText(s); t.SetLayer(layer)
        t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(th))
        t.SetTextAngleDegrees(angle)
        fp.Add(t)
    last = 21 * G
    xc = xout / 2
    # kart govdesi (resmi v1.1: pin1 kenardan 1.565, son pin USB kenarina 7.96; genislik sira + 2x1.27)
    rect(pcbnew.F_Fab, -1.27, -1.565, xout + 1.27, last + 7.96)
    rect(pcbnew.F_Fab, xc - 9.0, -1.565 - 6.3, xc + 9.0, -1.565)              # anten (kartin disina tasar)
    rect(pcbnew.F_CrtYd, -1.9, -1.55, 1.9, last + 1.9, 0.05)                    # sol soket
    rect(pcbnew.F_CrtYd, xin - 1.9, -1.55, xout + 1.9, last + 1.9, 0.05)        # sag soket(ler)
    # serigrafi: sol cizgi, sag cizgi (dis siranin disinda), alt (USB) cizgi
    line(pcbnew.F_SilkS, -1.6, 1.4, -1.6, last + 7.96)
    line(pcbnew.F_SilkS, xout + 1.6, 1.4, xout + 1.6, last + 7.96)
    line(pcbnew.F_SilkS, -1.6, last + 7.96, xout + 1.6, last + 7.96)
    line(pcbnew.F_SilkS, -1.6, 1.4, -0.9, 1.4)                                 # pin 1 isareti
    text(pcbnew.F_SilkS, 'USB', xc, last + 6.2, 1.0)
    for r in rows:
        text(pcbnew.F_SilkS, '%.1f"' % (r / 25.4), r, last + 2.6, 0.8, 90)
    text(pcbnew.F_Fab, 'ESP32-S3-DevKitC-1', xc, 30.0, 1.0, 90)
    fp.Reference().SetPosition(pcbnew.VECTOR2I(mm(xc), mm(last + 4.3)))
    fp.Reference().SetLayer(pcbnew.F_SilkS)
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0))); fp.Reference().SetTextThickness(mm(0.15))
    fp.Value().SetText('ESP32-S3-DevKitC-1'); fp.Value().SetLayer(pcbnew.F_Fab)
    fp.Value().SetPosition(pcbnew.VECTOR2I(mm(xc), mm(last + 9.2)))
    lib = OUT / 'MagPanel.pretty'
    lib.mkdir(exist_ok=True)
    pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(str(lib), fp)   # (FootprintSave() bos klasoru taniyamiyor)
    return fp

def footprint_lib_dirs():
    for d in [os.environ.get('KICAD8_FOOTPRINT_DIR', ''), '/usr/share/kicad/footprints',
              '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints']:
        if d and os.path.isdir(d):
            yield d

def load_fp(fpid):
    import pcbnew
    lib, name = fpid.split(':', 1)
    if lib == 'MagPanel':
        path = str(OUT / 'MagPanel.pretty')
    else:
        path = next(os.path.join(d, lib + '.pretty') for d in footprint_lib_dirs()
                    if os.path.isdir(os.path.join(d, lib + '.pretty')))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise FileNotFoundError(fpid)
    fp.SetFPIDAsString(fpid)
    return fp

def silk_text(board, s, x, y, size=1.0, layer=None, angle=0, align='center', th=None, bold=False):
    import pcbnew
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer if layer is not None else pcbnew.F_SilkS)
    t.SetPosition(V(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(th if th else max(0.15, size * 0.15)))
    t.SetBold(bold)
    t.SetTextAngleDegrees(angle)
    t.SetHorizJustify({'center': pcbnew.GR_TEXT_H_ALIGN_CENTER, 'left': pcbnew.GR_TEXT_H_ALIGN_LEFT,
                       'right': pcbnew.GR_TEXT_H_ALIGN_RIGHT}[align])
    if t.GetLayer() in (pcbnew.B_SilkS, pcbnew.B_Cu):
        t.SetMirrored(True)
    board.Add(t)
    return t

def edge_outline(board, w, h, r=2.0):
    import pcbnew
    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
    def arc(cx, cy, sx, sy, ex, ey):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        mx = cx + ((sx + ex) / 2 - cx) / math.hypot((sx + ex) / 2 - cx, (sy + ey) / 2 - cy) * r
        my = cy + ((sy + ey) / 2 - cy) / math.hypot((sx + ex) / 2 - cx, (sy + ey) / 2 - cy) * r
        s.SetArcGeometry(V(sx, sy), V(mx, my), V(ex, ey)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)
    seg(r, 0, w - r, 0); seg(w, r, w, h - r); seg(w - r, h, r, h); seg(0, h - r, 0, r)
    arc(w - r, r, w - r, 0, w, r); arc(w - r, h - r, w, h - r, w - r, h)
    arc(r, h - r, r, h, 0, h - r); arc(r, r, 0, r, r, 0)

def add_track(board, net, pts, width, layer=None, lock=True):
    import pcbnew
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2)); t.SetWidth(mm(width))
        t.SetLayer(layer if layer is not None else pcbnew.F_Cu); t.SetNet(net); t.SetLocked(lock)
        board.Add(t)

def add_via(board, net, x, y, size=0.6, drill=0.3, lock=True):
    import pcbnew
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y)); v.SetWidth(mm(size)); v.SetDrill(mm(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net); v.SetLocked(lock)
    board.Add(v)
    return v

def pad_xy(fp, num):
    import pcbnew
    for p in fp.Pads():
        if p.GetNumber() == num:
            pos = p.GetPosition()
            return pcbnew.ToMM(pos.x) - ORIGIN[0], pcbnew.ToMM(pos.y) - ORIGIN[1]
    raise KeyError((fp.GetReference(), num))

# ref -> (dx, dy, aci, boyut) serigrafi ref konumu (parca merkezine gore); None = gizle
REF_POS = {
    'U2': (-3.81, -11.43, 90, 1.0), 'U3': (-3.81, -11.43, 90, 1.0),      # DIP govde ortasi (pin 1 = konum)
    'C3': (0, -1.65, 0, 0.8), 'C4': (0, -1.65, 0, 0.8), 'C8': (0, 1.65, 0, 0.8),
    'R2': (0, -1.45, 0, 0.8), 'R3': (0, -1.45, 0, 0.8), 'R4': (0, 1.45, 0, 0.8), 'R5': (0, 1.45, 0, 0.8),
    'C5': (-4.2, 0, 0, 0.8), 'C6': (-4.2, 0, 0, 0.8), 'C7': (-4.2, 0, 0, 0.8), 'R6': (-3.2, 0, 0, 0.8),
    'R7': (-4.2, 0, 0, 0.8),
    'F1': (0, -2.6, 0, 0.8), 'D1': (0, 2.45, 0, 0.8), 'C1': (1.75, 5.0, 0, 0.8), 'C2': (0, -1.65, 0, 0.8),
    'R1': (0, 1.75, 0, 0.8), 'D2': (0, 1.75, 0, 0.8),
    'J1': None, 'J2': None, 'J3': None, 'J4': None, 'J5': None, 'J6': None, 'J7': None, 'J8': None,
    'J9': None, 'J10': None, 'H1': None, 'H2': None, 'H3': None, 'H4': None,
}
REF_POS.update({ref: None for ref, _, _ in SERIES_R})     # 2.54 mm adimda yer yok: grup etiketi (serigrafi)

def silk_bbox(fp):
    """Footprint'in F.Silkscreen cizimlerinin kutusu (yerel mm, kart koordinati)."""
    import pcbnew
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() != 'PCB_TEXT':
            bb = g.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    return min(xs) - ORIGIN[0], min(ys) - ORIGIN[1], max(xs) - ORIGIN[0], max(ys) - ORIGIN[1]

def layout_silkscreen(board, fps):
    import pcbnew
    for ref, fp in fps.items():
        fp.Value().SetVisible(False)                      # degerler F.Fab'da; serigrafi sade kalsin
        r = fp.Reference()
        pos = REF_POS.get(ref, 'keep')
        if pos is None:
            r.SetVisible(False)
        elif pos != 'keep':
            dx, dy, ang, size = pos
            x, y, _, _ = PLACE[ref]
            r.SetPosition(V(x + dx, y + dy))
            r.SetTextAngleDegrees(ang)
            r.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
            r.SetTextThickness(mm(max(0.15, size * 0.15)))
    # HUB75 basliklari
    for ref, lat, title, note in HUB_CONN:
        x, y, _, _ = PLACE[ref]
        silk_text(board, '%s %s' % (ref, title), x + 1.27, y - 6.6, 0.9)
        silk_text(board, lat + '=' + HUB_GPIO[lat], x + 1.27, y + 24.2, 0.8)
    # sensor basliklari: ad ustte, pin etiketleri solda
    for ref, name, pins, _ in SENSOR_HDRS:
        x, y, _, _ = PLACE[ref]
        silk_text(board, '%s %s' % (ref, name), x + 1.0, y - 2.3, 0.8, align='right')   # sag kolon etiketlerine degmesin
        for k, (lbl, net) in enumerate(pins):
            silk_text(board, lbl, x - 1.6, y + k * G, 0.8, align='right')
    # 5V giris
    x0, y0, x1, y1 = silk_bbox(fps['J1'])
    silk_text(board, '+5V IN', x0 + 0.1, y0 - 0.9, 0.8, align='left')      # pin 1 (ust)
    silk_text(board, 'GND', x0 + 0.1, y1 + 0.9, 0.8, align='left')         # pin 2 (alt)
    smd_silk = pcbnew.B_SilkS if DIY else None       # DIY: SMD'ler alt yuzde
    silk_text(board, 'PWR', PLACE['D2'][0] - 3.2, PLACE['D2'][1], 0.8, align='left' if DIY else 'right',
              layer=smd_silk)                         # aynali yazida hizalama ters doner
    # seri direnc sutunu: grup basinda ilk-son ref (ust U2 grubu, satir 12'de U3 grubu)
    for refs, row in ((SERIES_R[:8], 1), (SERIES_R[8:], 12)):
        silk_text(board, '%s-%s' % (refs[0][0], refs[-1][0][1:]), RCOL, pin_y(row) + (0.15 if row == 1 else 0), 0.8,
                  layer=smd_silk)
    # baslik / surum: on yuzde sag-alt bos alanda kisa, arka yuzde tam
    silk_text(board, 'MagPanel', 92.0, 48.6, 1.2, bold=True)
    silk_text(board, 'Carrier v' + REV, 92.0, 50.6, 1.0)
    silk_text(board, 'MagPanel Carrier v%s  %s  github.com/Kem4lk/magpanel' % (REV, DATE), 30.0, 61.6, 0.9,
              layer=pcbnew.B_SilkS)
    silk_text(board, 'ANT', J1X + max(DEVKIT_RIGHT_ROWS) / 2, 1.9, 0.8)

# =============================================================================
#  EV YAPIMI CIFT YUZ (--diy): dry film + MSLA ekran pozlama (Elegoo Saturn 3), kaplamasiz delik
# =============================================================================
DIY_VIA = (1.6, 0.8)          # via capi / delik: elle tel (0.6 mm bakir tel ya da direnc bacagi), iki yuzden lehim
DIY_HOLE_KEEP = 0.35          # ust katmanda iz/via delik kenarindan en az bu kadar uzak (delik yalniz altta bakirli)
DIY_POUR_CLEARANCE = 0.5      # GND dokumu ile diger bakir arasi (maskesiz lehimde kopru riski az)
DIY_VIA_COST = int(os.environ.get('DIY_VIA_COST', 50))    # Freerouting via maliyeti: 80 ve ustunde cogu deneme takiliyor
DIY_RING = (2.1, 0.25)        # hizalama halkasi yaricap / genislik (montaj deliklerinin cevresi, iki yuzde)
DIY_RING_EDGE = PLACE['H1'][0] - DIY_RING[0] - DIY_RING[1] / 2 + 0.03   # ust kenar seridi: halkalarin disina bakir yok
DIY_FRAME = (0.5, 3.0)        # hizalama cercevesi: kart kenarindan bosluk / isikli bant genisligi (mm)

def set_variant_diy():
    """Ev yapimi surum. Ayni sematik, ayri KiCad projesi (magpanel-carrier-diy/) ve ciktilar (fab-diy/).
    - SMD'ler alt yuzde; delikli pedlerin bakiri yalniz altta (soket pinleri ustten lehimlenemez)
    - ust katman yalniz via'lar arasi gecis; via = elle delinip telle iki yuzden lehimlenir
    - sinyal 0.25/0.2 mm (fabrika ile ayni): 2.54 mm adimli pinlerin 0.84 mm arasindan bir iz gecer.
      Uc HUB75 basligi ayni yonde: ortak hatlar pin aralarindan gecmezse her basligi via'yla atlar
      (0.3/0.25 mm ile 40-45 via, 0.25/0.2 ile ~30). Guc ve GND hatlari 0.3 mm aralik.
    - GND dokumu yalniz altta, dikis viasi yok"""
    global DIY, PROJ, OUT, FAB, PREROUTE, NETCLASSES, GND_VIAS
    DIY = True
    PROJ = 'magpanel-carrier-diy'
    OUT = HERE / PROJ
    FAB = HERE / 'fab-diy'
    PREROUTE = WORK / (PROJ + '-preroute.kicad_pcb')
    NETCLASSES = [(n, tw, cl if n == 'Default' else max(cl, 0.3), DIY_VIA[0], DIY_VIA[1], pats)
                  for n, tw, cl, vd, vdr, pats in NETCLASSES]
    GND_VIAS = {}                                     # SMD GND pedleri alt yuzde, dokume dogrudan baglanir
    RULES.update({'min_clearance': 0.2, 'min_track_width': 0.25, 'min_copper_edge_clearance': 0.5,
                  'min_via_diameter': DIY_VIA[0], 'min_through_hole_diameter': 0.8, 'min_hole_to_hole': 0.5,
                  'min_hole_clearance': 0.3, 'min_via_annular_width': 0.3})   # via 0.5, delikli ped >= 0.35

def circle_pts(cx, cy, r, n=24):
    """Cembere disaridan teget cokgen (yasak bolge gercek cemberden kucuk kalmasin)."""
    R = r / math.cos(math.pi / n)
    return [(cx + R * math.cos(2 * math.pi * k / n), cy + R * math.sin(2 * math.pi * k / n)) for k in range(n)]

def add_keepout(board, layer, pts):
    """Kural alani: iz, via ve dokum yasak (Freerouting'e 'keepout' olarak gider)."""
    import pcbnew
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayer(layer)
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        v = V(x, y)
        ol.Append(v.x, v.y)
    board.Add(z)
    return z

def diy_footprint(fp):
    """Delikli pedlerin bakiri yalniz altta: kaplamasiz delikte ust yuze iz gelmesin. DevKit soketi oval ped
    (2.4 x 1.7 mm): 44 delik, elle delmede kayan delige halka payi. Sensor basliklari yuvarlak kalir (sik bolge)."""
    import pcbnew
    oval = fp.GetReference() == 'U1'
    for p in fp.Pads():
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
            continue
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.B_Cu)
        ls.AddLayer(pcbnew.B_Mask)
        p.SetLayerSet(ls)
        if oval:
            if p.GetShape() != pcbnew.PAD_SHAPE_RECT:
                p.SetShape(pcbnew.PAD_SHAPE_OVAL)
            p.SetSize(pcbnew.VECTOR2I(mm(2.4), mm(1.7)))

def diy_features(board, fps):
    """Ust katmanda delik yasak bolgeleri; iki yuzde ayni yerde hizalama halkalari (montaj delikleri) ve
    UST/ALT yazisi (yazilar dogru okunuyorsa pozlama aynalamasi dogru)."""
    import pcbnew
    for fp in fps.values():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                x, y = pad_xy(fp, p.GetNumber())
                r = pcbnew.ToMM(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2 + DIY_HOLE_KEEP
                add_keepout(board, pcbnew.F_Cu, circle_pts(x, y, r, 16))
    # Ust katman kenar seritleri: UVtools 'Mirror' cizimi kendi sinir kutusunun ortasindan aynalar. Ustteki en dis
    # bakir hizalama halkalari (kosegen simetrik) olunca eksen kart ortasina duser; alttaki dokum de simetrik.
    e = DIY_RING_EDGE
    for x0, y0, x1, y1 in ((0, 0, e, BOARD_H), (BOARD_W - e, 0, BOARD_W, BOARD_H),
                           (0, 0, BOARD_W, e), (0, BOARD_H - e, BOARD_W, BOARD_H)):
        add_keepout(board, pcbnew.F_Cu, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    rr, rw = DIY_RING
    for ref in ('H1', 'H2', 'H3', 'H4'):
        x, y, _, _ = PLACE[ref]
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            c = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
            c.SetCenter(V(x, y)); c.SetEnd(V(x + rr, y))
            c.SetLayer(layer); c.SetWidth(mm(rw)); c.SetFilled(False)
            board.Add(c)
            add_keepout(board, layer, circle_pts(x, y, rr + rw / 2 + 0.6))
    for s, x, y, layer in (('ÜST v%s' % REV, 91.5, 53.5, pcbnew.F_Cu), ('ALT v%s' % REV, 11.0, 60.0, pcbnew.B_Cu)):
        t = silk_text(board, s, x, y, 1.2, layer=layer, th=0.25)
        bb = t.GetBoundingBox()
        x0, y0 = pcbnew.ToMM(bb.GetLeft()) - ORIGIN[0] - 0.6, pcbnew.ToMM(bb.GetTop()) - ORIGIN[1] - 0.6
        x1, y1 = pcbnew.ToMM(bb.GetRight()) - ORIGIN[0] + 0.6, pcbnew.ToMM(bb.GetBottom()) - ORIGIN[1] + 0.6
        add_keepout(board, layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])

def kicad_netlist():
    """kicad-cli ile sematikten KiCad netlist'i: {(ref, pin): (net, pinfunction, pintype)}.
    PCB'ye 'Update PCB from Schematic' ile ayni ad/tur bilgisi yazilir (parity temiz)."""
    WORK.mkdir(exist_ok=True)
    out = WORK / (PROJ + '.net')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', str(out),
                    str(OUT / (PROJ + '.kicad_sch'))], check=True, capture_output=True)
    doc = sexp.parse(out.read_text())
    res = {}
    for net in sexp.find_all(sexp.find(doc, 'nets'), 'net'):
        name = sexp.find(net, 'name')[1]
        for node in sexp.find_all(net, 'node'):
            g = lambda k: (sexp.find(node, k) or [None, ''])[1]
            res[(g('ref'), g('pin'))] = (name, g('pinfunction'), g('pintype'))
    return res

def stage_pcb():
    import pcbnew
    nl = json.loads((OUT / 'netlist.json').read_text())
    knl = kicad_netlist()
    for ref, p in nl.items():                 # uretec tablosu == KiCad netlist (tek kaynak dogrulamasi)
        for num, net in p['pins'].items():
            kn = knl[(ref, num)][0]
            assert (pcb_net(net) == kn) if net else kn.startswith('unconnected-('), (ref, num, net, kn)
    make_devkit_footprint()
    pcbnew.KIID.SeedGenerator(0x4D51)
    path = OUT / (PROJ + '.kicad_pcb')
    if path.exists():
        path.unlink()
    board = pcbnew.NewBoard(str(path))
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.m_CopperEdgeClearance = mm(RULES['min_copper_edge_clearance'])
    ds.m_TrackMinWidth = mm(RULES['min_track_width'])
    ds.m_ViasMinSize = mm(RULES['min_via_diameter'])
    ds.m_MinThroughDrill = mm(RULES['min_through_hole_diameter'])
    ds.m_HoleToHoleMin = mm(RULES['min_hole_to_hole'])
    ds.m_HoleClearance = mm(RULES['min_hole_clearance'])
    ds.m_SolderMaskMinWidth = mm(0)
    ds.SetAuxOrigin(V(*PLACE_ORIGIN))      # montaj servisleri sol-alt kose orijini bekler (pozitif koordinat)
    tb = board.GetTitleBlock()
    tb.SetTitle('MagPanel Carrier' + (' DIY' if DIY else '')); tb.SetRevision(REV); tb.SetDate(DATE)
    tb.SetCompany('MagPanel (github.com/Kem4lk/magpanel)')
    tb.SetComment(0, 'ESP32-S3-DevKitC-1 + 2x 74HCT245 + 3x HUB75E + sensorler')
    tb.SetComment(1, 'hardware/kicad/gen_carrier.py ile uretildi')
    # netler
    nets = {}                                  # KiCad net adi -> NETINFO_ITEM
    for n in sorted({v[0] for v in knl.values()}):
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni
    for n in list(nets):                       # uretec adlariyla da erisim ('GND', 'VIN', ...)
        nets.setdefault(n.lstrip('/'), nets[n])
    # parcalar
    fps = {}
    for ref, p in sorted(nl.items()):
        x, y, rot, side = PLACE[ref]
        fp = load_fp(p['footprint'])
        fp.SetReference(ref)
        fp.SetValue(p['value'])
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH('/' + p['uuid']))
        fp.SetSheetname('/')
        fp.SetSheetfile(PROJ + '.kicad_sch')
        board.Add(fp)
        if side == 'B' or (DIY and fp.GetAttributes() & pcbnew.FP_SMD):     # DIY: SMD'ler alt yuzde
            fp.Flip(fp.GetPosition(), False)      # karta eklendikten sonra (KiCad 8: kartsiz Flip cokuyor)
        for pad in fp.Pads():
            k = knl.get((ref, pad.GetNumber()))
            if k:
                pad.SetNet(nets[k[0]])
                pad.SetPinFunction(k[1])
                pad.SetPinType(k[2])
        if DIY:
            diy_footprint(fp)
        fps[ref] = fp
    edge_outline(board, BOARD_W, BOARD_H)
    layout_silkscreen(board, fps)
    # +5V ana hat (kalin, kilitli): C1+ -> alt serit (tamponlarin altindan) -> DevKit altindan 5V pinine.
    # DIY: delikli pedlerin bakiri yalniz altta -> sabit izler de altta.
    cu = pcbnew.B_Cu if DIY else pcbnew.F_Cu
    c1p = pad_xy(fps['C1'], '1')
    u5v = pad_xy(fps['U1'], devkit_pin('5V'))
    f1a, f1b = pad_xy(fps['F1'], '1'), pad_xy(fps['F1'], '2')
    d1k, d1a = pad_xy(fps['D1'], '1'), pad_xy(fps['D1'], '2')
    c2p, r1p = pad_xy(fps['C2'], '1'), pad_xy(fps['R1'], '1')
    add_track(board, nets['VIN'], [pad_xy(fps['J1'], '1'), f1a], TRUNK_W, layer=cu)
    add_track(board, nets['+5V'], [f1b, (c1p[0] - 2.0, f1b[1]), c1p], TRUNK_W, layer=cu)
    # TVS: F1 cikisi -> katot; anot dogrudan J1 GND'sine (ters kutupta F1'i acan akim yolu kisa ve kalin)
    add_track(board, nets['+5V'], [f1b, (f1b[0], d1k[1]), d1k], TRUNK_W, layer=cu)
    add_track(board, nets['GND'], [d1a, pad_xy(fps['J1'], '2')], TRUNK_W, layer=cu)
    add_track(board, nets['+5V'], [c1p, (c1p[0], c2p[1]), (c1p[0], r1p[1]), (c1p[0], TRUNK_Y), (TRUNK_X, TRUNK_Y),
                                   (TRUNK_X, u5v[1]), u5v], TRUNK_W, layer=cu)
    add_track(board, nets['+5V'], [c2p, (c1p[0], c2p[1])], 0.8, layer=cu)          # C2 ve R1: ana hatta T kol
    add_track(board, nets['+5V'], [r1p, (c1p[0], r1p[1])], 0.5, layer=cu)
    # U3 kollari: ana hat -> C8+ -> C4+ -> VCC (pin 20); ana hat -> DIR (pin 1)
    c8p, c4p = pad_xy(fps['C8'], '1'), pad_xy(fps['C4'], '1')
    u3vcc, u3dir = pad_xy(fps['U3'], '20'), pad_xy(fps['U3'], '1')
    assert abs(c8p[0] - c4p[0]) < 1e-6 and abs(c4p[1] - u3vcc[1]) < 1e-6
    add_track(board, nets['+5V'], [(c8p[0], TRUNK_Y), c8p, c4p, u3vcc], 0.8, layer=cu)
    add_track(board, nets['+5V'], [(u3dir[0], TRUNK_Y), u3dir], 0.8, layer=cu)
    # SMD GND pedleri -> kisa iz + via
    for (ref, num), (dx, dy) in GND_VIAS.items():
        px, py = pad_xy(fps[ref], num)
        assert nl[ref]['pins'][num] == 'GND', (ref, num)
        add_track(board, nets['GND'], [(px, py), (px + dx, py + dy)], 0.4)
        add_via(board, nets['GND'], px + dx, py + dy)
    if DIY:
        diy_features(board, fps)
    pcbnew.SaveBoard(str(path), board, True)          # True: proje ayarlarina dokunma
    WORK.mkdir(exist_ok=True)
    shutil.copyfile(path, PREROUTE)
    patch_rules()
    print('pcb: %d footprint, %d net -> %s' % (len(fps), board.GetNetCount() - 1, path.name))
    return board, fps

# JLCPCB standart 2 katman yeteneklerinin rahat ustunde
RULES = {'min_clearance': 0.15, 'min_track_width': 0.15, 'min_copper_edge_clearance': 0.3,
         'min_via_diameter': 0.5, 'min_through_hole_diameter': 0.3, 'min_hole_to_hole': 0.25,
         'min_hole_clearance': 0.25, 'min_via_annular_width': 0.1, 'min_text_height': 0.8,
         'min_text_thickness': 0.15, 'min_silk_clearance': 0.0, 'solder_mask_to_copper_clearance': 0.0}

DRU = '''(version 1)
# gen_carrier.py uretir. 2.54 mm baslik GND pinleri iz arasinda kalinca termal kollarin bir kismi
# baglanamiyor; tek kol (0.45 mm, iki katmanda) sensor akimlari icin fazlasiyla yeterli.
(rule "termal_tek_kol"
  (constraint min_resolved_spokes 1))
# El lehimi: parca courtyard'lari arasinda en az 0.5 mm (havya ucu ve cimbiz icin pay).
(rule "el_lehim_aralik"
  (constraint courtyard_clearance (min 0.5mm)))
'''

def patch_rules():
    (OUT / (PROJ + '.kicad_dru')).write_text(DRU)
    pro = OUT / (PROJ + '.kicad_pro')
    data = json.loads(pro.read_text())
    dsets = data.setdefault('board', {}).setdefault('design_settings', {})
    dsets.setdefault('rules', {}).update(RULES)
    dsets['track_widths'] = [0.0, 0.25, 0.4, 0.5, 0.8, 1.0]
    dsets['via_dimensions'] = [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.6, 'drill': 0.3}, {'diameter': 0.8, 'drill': 0.4}]
    if DIY:
        dsets['track_widths'] = [0.0, 0.25, 0.5, 0.8, 1.0]
        dsets['via_dimensions'] = [{'diameter': 0.0, 'drill': 0.0}, {'diameter': DIY_VIA[0], 'drill': DIY_VIA[1]}]
        # delikli pedlerin bakiri bilerek yalniz altta: kutuphane kopyasindan farkli olmalari beklenen durum
        dsets.setdefault('rule_severities', {})['lib_footprint_mismatch'] = 'ignore'
    pro.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')

# =============================================================================
#  YONLENDIRME (Freerouting) + GND DOKUMU
# =============================================================================
FREEROUTING_JAR = os.environ.get('FREEROUTING_JAR', str(HERE / 'work' / 'freerouting-2.1.0.jar'))
WORK = HERE / 'work'
PREROUTE = WORK / (PROJ + '-preroute.kicad_pcb')     # 'pcb' asamasi ciktisi (yonlendirilmemis)
FREEROUTING_URL = 'https://github.com/freerouting/freerouting/releases/download/v2.1.0/freerouting-2.1.0.jar'

def ensure_freerouting():
    """Freerouting 2.1.0 (Java 21+). Yoksa work/ altina indirilir (~67 MB)."""
    jar = Path(FREEROUTING_JAR)
    if not jar.exists():
        import urllib.request
        jar.parent.mkdir(parents=True, exist_ok=True)
        print('freerouting indiriliyor:', FREEROUTING_URL)
        urllib.request.urlretrieve(FREEROUTING_URL, str(jar) + '.part')
        os.replace(str(jar) + '.part', jar)
    return jar

def add_gnd_zones(board):
    """Iki katmanda kart boyu GND dokumu (dolgusuz). Freerouting bunlari 'plane' gorur ve GND'yi
    iz olarak cekmez; pedler dokumle baglanir, kopuk adaciklar dikis vialariyla birlesir."""
    import pcbnew
    gnd = board.FindNet('GND')
    for layer in ((pcbnew.B_Cu,) if DIY else (pcbnew.F_Cu, pcbnew.B_Cu)):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetAssignedPriority(0)
        z.SetZoneName('GND_' + board.GetLayerName(layer).replace('.', ''))
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)):
            ol.Append(V(x, y).x, V(x, y).y)
        z.SetLocalClearance(mm(DIY_POUR_CLEARANCE if DIY else 0.3))
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.4))
        z.SetThermalReliefSpokeWidth(mm(0.45))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(z)

def fill_zones(board, zones):
    import pcbnew
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(zones)
    board.BuildConnectivity()

STITCH_PITCH = 1.27       # aday izgarasi (mm)
STITCH_MIN_D = 7.0        # dikis vialari arasi en az (mm)

def silk_boxes(board, grow):
    """Iki yuzdeki tum serigrafi ogelerinin kutulari (yerel mm, 'grow' kadar buyutulmus)."""
    import pcbnew
    layers = (pcbnew.F_SilkS, pcbnew.B_SilkS)
    items = [d for d in board.GetDrawings() if d.GetLayer() in layers]
    for fp in board.GetFootprints():
        items += [g for g in fp.GraphicalItems() if g.GetLayer() in layers]
        items += [t for t in (fp.Reference(), fp.Value()) if t.IsVisible() and t.GetLayer() in layers]
    out = []
    for it in items:
        bb = it.GetBoundingBox()
        out.append((pcbnew.ToMM(bb.GetLeft()) - ORIGIN[0] - grow, pcbnew.ToMM(bb.GetTop()) - ORIGIN[1] - grow,
                    pcbnew.ToMM(bb.GetRight()) - ORIGIN[0] + grow, pcbnew.ToMM(bb.GetBottom()) - ORIGIN[1] + grow))
    return out

def add_stitching_vias(board, zones):
    """Iki katmanin GND dolgusunun ORTAK oldugu yerlere 0.6/0.3 via (aralarinda >= STITCH_MIN_D).
    Via kenari dolgu sinirindan >= 0.35 mm iceride -> baska netlere >= 0.65 mm."""
    import pcbnew
    fills = [z.GetFilledPolysList(z.GetLayer()) for z in zones if z.GetNetname() == 'GND']
    near = []                                 # mevcut via + ped merkezleri (>= 2 mm uzak dur)
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            pos = t.GetPosition()
            near.append((pcbnew.ToMM(pos.x) - ORIGIN[0], pcbnew.ToMM(pos.y) - ORIGIN[1]))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pos = pad.GetPosition()
            near.append((pcbnew.ToMM(pos.x) - ORIGIN[0], pcbnew.ToMM(pos.y) - ORIGIN[1]))
    ring = [(0.0, 0.0)] + [(0.65 * math.cos(k * math.pi / 6), 0.65 * math.sin(k * math.pi / 6)) for k in range(12)]
    silk = silk_boxes(board, 0.5)              # delik serigrafi yazisini/cizgisini bolmesin
    gnd = board.FindNet('GND')
    placed = []
    nx, ny = int(BOARD_W / STITCH_PITCH), int(BOARD_H / STITCH_PITCH)
    for j in range(1, ny):
        for i in range(1, nx):
            x, y = i * STITCH_PITCH, j * STITCH_PITCH
            if any((x - px) ** 2 + (y - py) ** 2 < STITCH_MIN_D ** 2 for px, py in placed):
                continue
            if any((x - px) ** 2 + (y - py) ** 2 < 2.0 ** 2 for px, py in near):
                continue
            if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in silk):
                continue
            if all(f.Contains(V(x + dx, y + dy)) for f in fills for dx, dy in ring):
                add_via(board, gnd, x, y, lock=False)
                placed.append((x, y))
    n = len(placed)
    return n

_REMOVED = []      # KiCad 8 SWIG: Remove() edilen ogenin Python vekili toplanirsa tip tablosu bozuluyor
                   # (board.Zones()/GetConnectivity() ham SwigPyObject doner) -> referansi tut

def board_remove(board, item):
    board.Remove(item)
    _REMOVED.append(item)

def remove_dangling(board):
    """Freerouting'in biraktigi bos uclu kisa parcalari temizle. Her aday tek tek denenir:
    silmek baglanmamis sayisini artiriyorsa (T-birlesimi vb.) geri eklenir."""
    total = 0
    while True:
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        base = conn.GetUnconnectedCount(False)
        dead = [t for t in board.GetTracks()
                if t.GetClass() == 'PCB_TRACK' and not t.IsLocked() and conn.TestTrackEndpointDangling(t, False)]
        removed = 0
        for t in dead:
            board_remove(board, t)
            board.BuildConnectivity()
            if board.GetConnectivity().GetUnconnectedCount(False) > base:
                board.Add(t)                       # gerekliymis
            else:
                removed += 1
        if not removed:
            return total
        total += removed

def run_freerouting(dsn, ses, passes, minutes=20):
    """Freerouting 2.1.0 CLI'da gecis sinirini ('-mp') uygulamiyor: tamamlayamayinca binlerce gecis surer.
    Sure siniri (router.job_timeout) calisiyor ve o ana kadarki en iyi sonucu SES'e yaziyor."""
    if ses.exists():
        ses.unlink()
    cmd = ['java', '-jar', str(ensure_freerouting()), '-de', str(dsn), '-do', str(ses), '-mp', str(passes),
           '-da', '--gui.enabled=false', '--router.job_timeout=%02d:%02d:00' % divmod(minutes, 60),
           '--usage_and_diagnostic_data.disable_analytics=true', '--profile.allow_telemetry=false']
    if DIY:
        cmd.append('--router.scoring.via_costs=%d' % DIY_VIA_COST)
    print('freerouting:', ' '.join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    log = r.stdout + r.stderr
    (WORK / 'freerouting.log').write_text(log)
    if not ses.exists():
        print(log[-3000:])
        raise RuntimeError('Freerouting SES uretmedi')
    for line in log.splitlines():
        if 'Auto-router pass' in line or 'incomplete' in line:
            print('  ' + line.split('] ')[-1].strip())

def route_once(passes, gnd_plane=False):
    import pcbnew
    path = OUT / (PROJ + '.kicad_pcb')
    # her deneme 'pcb' asamasinin yonlendirilmemis kopyasindan baslar (tekrarlanabilir baslangic)
    if not PREROUTE.exists():
        stage_pcb()
    shutil.copyfile(PREROUTE, path)
    board = pcbnew.LoadBoard(str(path))
    pcbnew.KIID.SeedGenerator(0x4D52)          # Freerouting deterministik degil ama ayni SES -> ayni dosya
    if gnd_plane:
        add_gnd_zones(board)                   # once dokum: GND 'plane' -> Freerouting GND izi cekmez
    zones = board.Zones()                      # kartin kendi listesine referans
    WORK.mkdir(exist_ok=True)
    dsn, ses = WORK / (PROJ + '.dsn'), WORK / (PROJ + '.ses')
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        raise RuntimeError('DSN disa aktarilamadi')
    run_freerouting(dsn, ses, passes, 4 if DIY else 20)
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        raise RuntimeError('SES ice aktarilamadi')
    for k in range(3):
        # Freerouting 'tamam' dese de SES'te bazi ust katman parcalari eksik kalabiliyor (via'dan cikan iz yok).
        # Mevcut izlerle yeniden DSN -> Freerouting yalniz eksikleri ceker.
        board.BuildConnectivity()
        n = board.GetConnectivity().GetUnconnectedCount(False)
        if not n:
            break
        print('route: %d baglanmamis -> tamamlama turu %d' % (n, k + 1))
        if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
            raise RuntimeError('DSN disa aktarilamadi')
        run_freerouting(dsn, ses, 10, 2)
        if not pcbnew.ImportSpecctraSES(board, str(ses)):
            raise RuntimeError('SES ice aktarilamadi')
    if not gnd_plane:
        add_gnd_zones(board)                   # GND izleri cekildi; dokum sonradan
    print('route: %d bos uclu parca silindi' % remove_dangling(board))
    fill_zones(board, zones)
    if not DIY:                                # DIY: her via elle tel, dikis viasi yok
        print('route: %d GND dikis viasi' % add_stitching_vias(board, zones))
        fill_zones(board, zones)
    pcbnew.SaveBoard(str(path), board, True)
    return board

def stage_route(passes=40, attempts=10):
    """Freerouting deterministik degil ve ara sira KiCad'in baglanmamis saydigi bir parca birakiyor.
    DRC (ihlal + baglanmamis + sematik farki) sifir olana kadar yeniden dene.
    GND de iz olarak cekilir (gnd_plane=False): yalniz dokume guvenince IDC GND pinleri (4/16)
    veri yolu izleri arasinda yalitilabiliyordu; izler dokumle birlesir, gorselde kaybolur."""
    if DIY:
        return stage_route_diy(passes)
    for k in range(1, attempts + 1):
        print('route: deneme %d/%d' % (k, attempts))
        route_once(passes)
        n = drc_counts()
        print('route: DRC %d ihlal, %d baglanmamis, %d sematik farki' % n)
        if not any(n):
            print('route: tamam ->', PROJ + '.kicad_pcb')
            return
    raise RuntimeError('route: %d denemede temiz sonuc yok (work/drc.json)' % attempts)

DIY_ROUTE_TRIES = int(os.environ.get('DIY_ROUTE_TRIES', 6))

def stage_route_diy(passes):
    """DIY: her via elle delinip telle iki yuzden lehimlenir. Freerouting deterministik degil ve via sayisi
    denemeden denemeye oynuyor -> DIY_ROUTE_TRIES deneme, DRC temiz olanlardan en az vialisi (esitse ust
    katmanda en kisa izlisi) kalir."""
    import pcbnew
    path = OUT / (PROJ + '.kicad_pcb')
    best, keep = None, WORK / (PROJ + '-best.kicad_pcb')
    for k in range(1, DIY_ROUTE_TRIES + 1):
        print('route: deneme %d/%d' % (k, DIY_ROUTE_TRIES))
        board = route_once(passes)
        n = drc_counts()
        tracks = list(board.GetTracks())
        score = (sum(1 for t in tracks if t.GetClass() == 'PCB_VIA'),
                 round(sum(pcbnew.ToMM(t.GetLength()) for t in tracks
                           if t.GetClass() == 'PCB_TRACK' and t.GetLayer() == pcbnew.F_Cu), 1))
        print('route: DRC %d ihlal, %d baglanmamis, %d sematik farki | %d via, ust iz %.1f mm' % (n + score))
        if not any(n) and (best is None or score < best):
            best = score
            shutil.copyfile(path, keep)
    if best is None:
        raise RuntimeError('route: %d denemede temiz sonuc yok (work/drc.json)' % DIY_ROUTE_TRIES)
    shutil.copyfile(keep, path)
    print('route: tamam -> %s (%d via, ust iz %.1f mm)' % ((PROJ + '.kicad_pcb',) + best))


# =============================================================================
#  URETIM CIKTILARI (kicad-cli) + GORSELLER
# =============================================================================
FAB = HERE / 'fab'
IMG = HERE / 'img'

def kcli(*args):
    r = subprocess.run(['kicad-cli'] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('kicad-cli %s:\n%s' % (' '.join(str(a) for a in args[:3]), (r.stdout + r.stderr)[-2000:]))
    return r.stdout

def find_chrome():
    for c in (os.environ.get('CHROME'), 'chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable',
              '/opt/pw-browsers/chromium', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
              '/Applications/Chromium.app/Contents/MacOS/Chromium'):
        if c and (shutil.which(c) or os.path.exists(c)):
            return shutil.which(c) or c
    return None

def svg_to_png(svg, png, width):
    """SVG -> PNG (Chromium headless, viewBox en-boy oraniyla). Donus: (w, h)."""
    import re
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg.read_text()[:4000]).group(1).split()]
    height = int(round(width * vb[3] / vb[2]))
    html = svg.with_suffix('.html')
    html.write_text('<html><body style="margin:0;background:#fff"><img src="%s" '
                    'style="display:block;width:%dpx;height:%dpx"></body></html>' % (svg.name, width, height))
    # pencere goruntuden yuksek olmali (headless pencere yuksekliginin bir kismini kendine ayiriyor)
    subprocess.run([find_chrome(), '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                    '--user-data-dir=' + str(WORK / 'chrome'), '--window-size=%d,%d' % (width, height + 400),
                    '--screenshot=' + str(png), html.as_uri()], check=True, capture_output=True, timeout=300)
    from PIL import Image
    Image.open(png).crop((0, 0, width, height)).save(png)
    return width, height

def drc_counts():
    """kicad-cli DRC (+ sematik esligi) -> (ihlal, baglanmamis, sematik farki)."""
    WORK.mkdir(exist_ok=True)
    kcli('pcb', 'drc', '--schematic-parity', '--severity-all', '--format', 'json', '-o', WORK / 'drc.json',
         OUT / (PROJ + '.kicad_pcb'))
    drc = json.loads((WORK / 'drc.json').read_text())
    return tuple(len(drc.get(k, [])) for k in ('violations', 'unconnected_items', 'schematic_parity'))

def check_erc_drc():
    """ERC + DRC (+ sematik/PCB esligi). Herhangi bir bulgu -> hata (uretim dosyasi cikmaz)."""
    WORK.mkdir(exist_ok=True)
    sch = OUT / (PROJ + '.kicad_sch')
    kcli('sch', 'erc', '--severity-all', '--format', 'json', '-o', WORK / 'erc.json', sch)
    erc = json.loads((WORK / 'erc.json').read_text())
    n_erc = sum(len(sh['violations']) for sh in erc['sheets'])
    n_drc = drc_counts()
    print('ERC: %d bulgu | DRC: %d ihlal, %d baglanmamis, %d sematik farki' % (n_erc, *n_drc))
    if n_erc or any(n_drc):
        raise RuntimeError('ERC/DRC temiz degil: work/erc.json, work/drc.json')

def zip_dir(src, dst):
    """Tekrarlanabilir zip (sabit tarih, sirali)."""
    import zipfile
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src.iterdir()):
            zi = zipfile.ZipInfo(f.name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, f.read_bytes())

def write_frame_gerber(path):
    """DIY hizalama cercevesi: kart dis hattinin DISINDA isikli bant (koordinatlar gerber orijinine gore: kartin
    sol-alt kosesi). Ic kenari kart kenarindan DIY_FRAME[0] uzakta: ekranda yanarken kart, dort kenarda esit
    karanlik bosluk kalacak sekilde bandin ortasina oturtulur. Simetrik: aynalamadan etkilenmez, bakir pozlamasina
    eklenince UVtools'un 'Mirror' eksenini kart ortasina sabitler."""
    g, f = DIY_FRAME
    x0, y0, x1, y1 = -g, -g, BOARD_W + g, BOARD_H + g             # ic kenar
    rects = [(x0 - f, y0 - f, x0, y1 + f), (x1, y0 - f, x1 + f, y1 + f), (x0, y0 - f, x1, y0), (x0, y1, x1, y1 + f)]
    c = lambda v: '%d' % round(v * 1e6)
    lines = ['G04 MagPanel Carrier v%s DIY - hizalama cercevesi: kart kenarindan %.1f mm bosluk, %.1f mm bant*'
             % (REV, g, f),
             '%FSLAX46Y46*%', '%MOMM*%', '%LPD*%', 'G01*']
    for x0, y0, x1, y1 in rects:
        lines += ['G36*', 'X%sY%sD02*' % (c(x0), c(y0))]
        lines += ['X%sY%sD01*' % (c(x), c(y)) for x, y in ((x1, y0), (x1, y1), (x0, y1), (x0, y0))]
        lines.append('G37*')
    lines.append('M02*')
    path.write_text('\n'.join(lines) + '\n')

def fab_gerbers(layers='F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'):
    pcb = OUT / (PROJ + '.kicad_pcb')
    gd = WORK / 'gerber'
    shutil.rmtree(gd, ignore_errors=True)
    gd.mkdir(parents=True)
    # DIY: UVtools Gerber okuyucusu icin sade dosya (yuvarlak koseli ped = cokgen, X2/net ozniteligi yok;
    # oznitelik satirlarindaki 'D1' gibi parca adlari D-kodu sanilabiliyor)
    extra = ['--disable-aperture-macros', '--no-x2', '--no-netlist'] if DIY else []
    kcli('pcb', 'export', 'gerbers', '--layers', layers, *extra,
         '--subtract-soldermask', '--use-drill-file-origin', '-o', str(gd) + os.sep, pcb)
    kcli('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '-u', 'mm',
         '--drill-origin', 'plot', '-o', str(gd) + os.sep, pcb)
    import re
    for f in gd.iterdir():                     # KiCad'in yazdigi uretim zamani -> DATE (ayni kart -> ayni zip)
        f.write_text(re.sub(r'\d{4}-\d\d-\d\d([T ])\d\d:\d\d:\d\d', lambda m: DATE + m.group(1) + '00:00:00',
                            f.read_text()))
    if DIY:                                    # UVtools PCB exposure kart dis hattini .gko uzantisiyla taniyor
        for f in gd.glob('*-Edge_Cuts.gm1'):
            shutil.copyfile(f, f.with_suffix('.gko'))
        write_frame_gerber(gd / (PROJ + '-Hizalama.gbr'))
    zip_dir(gd, FAB / (PROJ + '-gerber.zip'))
    return sorted(f.name for f in gd.iterdir())

def place_xy(fp):
    """Footprint merkezi kartin sol-alt kosesine gore (mm, Y yukari): gerber ve delik dosyalariyla ayni orijin."""
    import pcbnew
    pos = fp.GetPosition()
    return (pcbnew.ToMM(pos.x) - ORIGIN[0] - PLACE_ORIGIN[0], PLACE_ORIGIN[1] - (pcbnew.ToMM(pos.y) - ORIGIN[1]))

def fab_bom_cpl(board, smt=True):
    """Tam BOM (insan) + SMT montaj dosyalari: JLCPCB BOM/CPL (csv), Robotistan BOM/PnP (xlsx).
    Montaj dosyalarinda yalniz SMD parcalar var (hepsi ust yuzde); delikli parcalar elle lehimlenir."""
    import csv
    import pcbnew
    import xlsx
    nl = json.loads((OUT / 'netlist.json').read_text())
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    def is_smd(ref):
        return bool(fps[ref].GetAttributes() & pcbnew.FP_SMD)
    def refkey(r):
        return (r.rstrip('0123456789'), int(''.join(c for c in r if c.isdigit()) or 0))
    def grouped(with_desc):
        groups = {}
        for ref in sorted(nl, key=refkey):
            p = nl[ref]
            if not p.get('in_bom', True):
                continue
            key = (p['value'], p['footprint'], p['fields'].get('MPN', '')) + ((p['desc'],) if with_desc else ())
            groups.setdefault(key, []).append(ref)
        return sorted(groups.items(), key=lambda kv: refkey(kv[1][0]))
    rows = grouped(True)                      # insan BOM'u: ayni deger, farkli gorev -> ayri satir
    with open(FAB / (PROJ + '-bom.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Ref', 'Adet', 'Deger', 'Footprint', 'Montaj', 'Uretici', 'Parca / MPN', 'LCSC', 'Not'])
        for (val, fpn, mpn, desc), refs in rows:
            fl = nl[refs[0]]['fields']
            w.writerow([' '.join(refs), len(refs), val, fpn.split(':')[1], 'SMD' if is_smd(refs[0]) else 'THT',
                        fl.get('Manufacturer', ''), mpn, fl.get('LCSC', ''), desc])
    if not smt:                               # ev yapimi: montaj servisi dosyalari gerekmez
        return len(rows)
    smt_rows = []                             # (Comment, refs, kilif, LCSC, MPN, uretici, aciklama); adet kart basina
    for (val, fpn, mpn), refs in grouped(False):
        if is_smd(refs[0]):
            assert mpn in SMT_BY_MPN, ('SMT_PARTS tablosunda yok', refs, mpn)
            comment, mfr, _, lcsc, pkg, spec = SMT_BY_MPN[mpn]
            smt_rows.append((comment, refs, pkg, lcsc, mpn, mfr, spec))
    with open(FAB / (PROJ + '-jlc-bom.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for comment, refs, pkg, lcsc, mpn, mfr, spec in smt_rows:
            w.writerow([comment, ','.join(refs), pkg, lcsc])
    xlsx.write(FAB / (PROJ + '-robotistan-bom.xlsx'),
               [['Comment', 'Designator', 'Footprint', 'RobotistanPro Part', 'Manufacturer Part Number (MPN)', 'Quantity']]
               + [[comment, ','.join(refs), pkg, lcsc, mpn, len(refs)] for comment, refs, pkg, lcsc, mpn, _, _ in smt_rows],
               widths=[34, 44, 18, 22, 34, 12])
    # Turkce "default_bomlist" sablonu (Fabrika Kodu = MPN; sade Calibri, sayfa adi 'Worksheet')
    xlsx.write(FAB / (PROJ + '-bomlist.xlsx'),
               [['Fabrika Kodu', 'Açıklama', 'Designatör', 'Malzeme Kılıfı', 'Adet']]
               + [[mpn, '%s (%s)' % (spec, mfr), ','.join(refs), pkg, len(refs)]
                  for comment, refs, pkg, lcsc, mpn, mfr, spec in smt_rows],
               widths=[22, 50, 60, 16, 8], sheet='Worksheet', plain=True)
    place = []                                # (ref, x, y, alt yuz, aci)
    for ref in sorted(fps, key=refkey):
        if is_smd(ref) and nl.get(ref, {}).get('in_bom', True):
            fp = fps[ref]
            x, y = place_xy(fp)
            place.append((ref, x, y, fp.IsFlipped(), int(round(fp.GetOrientationDegrees())) % 360))
    with open(FAB / (PROJ + '-jlc-cpl.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for ref, x, y, back, rot in place:
            w.writerow([ref, '%.4fmm' % x, '%.4fmm' % y, 'Bottom' if back else 'Top', rot])
    xlsx.write(FAB / (PROJ + '-robotistan-pnp.xlsx'),
               [['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation']]
               + [[ref, '%.4fmm' % x, '%.4fmm' % y, 'B' if back else 'T', rot] for ref, x, y, back, rot in place],
               widths=[18, 22, 22, 14, 14])
    return len(rows), len(smt_rows), len(place)

# kart gorseli renkleri (yesil maske, ENIG gorunumu)
RENDER_COL = {'fr4_masked': (22, 84, 48, 255), 'cu_masked': (38, 118, 66, 255), 'fr4_bare': (196, 176, 122, 255),
              'finish': (214, 172, 82, 255), 'silk': (244, 244, 240, 255),
              'fr4_diy': (204, 190, 142, 255), 'cu_diy': (196, 112, 58, 255)}   # DIY: maskesiz, serigrafisiz

def board_render(brd, side, out_png, width=4000, final=1800):
    """Katman SVG'lerinden (kicad-cli) gercekci 2B kart gorseli: alt taraf aynalanir (alttan bakis).
    DIY: lehim maskesi ve serigrafi yok, ciplak FR4 uzerinde bakir."""
    from PIL import Image, ImageChops, ImageDraw
    import pcbnew
    pcb = OUT / (PROJ + '.kicad_pcb')
    rd = WORK / 'render'
    rd.mkdir(parents=True, exist_ok=True)
    pre = 'F' if side == 'top' else 'B'
    m = {}
    for k, layer in (('edge', 'Edge.Cuts'), ('cu', pre + '.Cu'), ('mask', pre + '.Mask'), ('silk', pre + '.Silkscreen')):
        svg = rd / ('%s_%s.svg' % (side, k))
        kcli('pcb', 'export', 'svg', '--layers', layer, '--black-and-white', '--exclude-drawing-sheet',
             '--page-size-mode', '2', '--drill-shape-opt', '0', '-o', svg, pcb)
        png = svg.with_suffix('.png')
        svg_to_png(svg, png, width)
        m[k] = Image.open(png).convert('L').point(lambda v: 255 if v < 128 else 0)
    W, H = m['edge'].size
    l, t, r, b = m['edge'].getbbox()
    sx = (r - l) / (BOARD_W + 0.1)                      # kenar cizgisi 0.1 mm
    def px(x, y):
        return l + (x + 0.05) * sx, t + (y + 0.05) * sx
    board = m['edge'].copy()
    cx, cy = px(BOARD_W / 2, BOARD_H / 2)
    ImageDraw.floodfill(board, (int(cx), int(cy)), 255)
    holes = Image.new('L', (W, H), 0)
    hd = ImageDraw.Draw(holes)
    pts = [(p.GetPosition(), p.GetDrillSize().x) for fp in brd.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    pts += [(v.GetPosition(), v.GetDrillValue()) for v in brd.GetTracks() if v.GetClass() == 'PCB_VIA']
    for pos, d in pts:
        x, y = px(pcbnew.ToMM(pos.x) - ORIGIN[0], pcbnew.ToMM(pos.y) - ORIGIN[1])
        rr = pcbnew.ToMM(d) / 2 * sx
        hd.ellipse((x - rr, y - rr, x + rr, y + rr), fill=255)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    mul = ImageChops.multiply
    def paint(col, mask):
        img.paste(Image.new('RGBA', (W, H), col), (0, 0), mask)
    if DIY:
        paint(RENDER_COL['fr4_diy'], board)
        paint(RENDER_COL['cu_diy'], mul(m['cu'], board))
    else:
        paint(RENDER_COL['fr4_masked'], board)
        paint(RENDER_COL['cu_masked'], mul(m['cu'], board))
        paint(RENDER_COL['fr4_bare'], mul(m['mask'], board))
        paint(RENDER_COL['finish'], mul(mul(m['mask'], m['cu']), board))
        paint(RENDER_COL['silk'], mul(mul(m['silk'], ImageChops.invert(m['mask'])), board))
    img.putalpha(mul(mul(img.getchannel('A'), board), ImageChops.invert(holes)))
    if side == 'bottom':
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    img = img.crop(img.getbbox())
    img = img.resize((final, int(round(final * img.size[1] / img.size[0]))), Image.LANCZOS)
    img.quantize(colors=96, method=Image.Quantize.FASTOCTREE).save(out_png, optimize=True)   # az renk -> kucuk PNG
    return img.size

def fab_print(brd, out_pdf):
    """1:1 yerlesim testi (A4 yatay): yalniz pedler + delikler, govdeler (F.Fab), serigrafi, 100 mm olcek.
    Basip kopuge yapistir, gercek parcalarin bacaklarini deliklerden gecir (siparis oncesi en ucuz kontrol)."""
    import pcbnew
    tmp = WORK / 'print'
    tmp.mkdir(parents=True, exist_ok=True)
    b = pcbnew.LoadBoard(str(OUT / (PROJ + '.kicad_pcb')))
    for t in list(b.GetTracks()):                     # izler/dokum yok: pedlerin beyaz delikleri gorunsun
        board_remove(b, t)
    for z in list(b.Zones()):
        board_remove(b, z)
    L = pcbnew.Dwgs_User
    def seg(x1, y1, x2, y2):
        sh = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(V(x1, y1)); sh.SetEnd(V(x2, y2)); sh.SetLayer(L); sh.SetWidth(mm(0.3)); b.Add(sh)
    def txt(t, x, y, size=2.0, center=False):
        o = pcbnew.PCB_TEXT(b); o.SetText(t); o.SetLayer(L); o.SetPosition(V(x, y))
        o.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); o.SetTextThickness(mm(size * 0.15))
        o.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER if center else pcbnew.GR_TEXT_H_ALIGN_LEFT)
        b.Add(o)
    y0 = BOARD_H + 8                                   # olcek cubugu: kart genisligi kadar (100 mm)
    seg(0, y0, 100, y0)
    for k in range(11):
        seg(10 * k, y0 - (3 if k % 5 == 0 else 1.8), 10 * k, y0)
        if k % 5 == 0:
            txt('%d' % (10 * k), 10 * k, y0 + 3.2, 1.8, center=True)
    txt('Bu çizgi 100 mm olmalı. Tutmuyorsa yazıcıda ölçek %100 / "gerçek boyut" seç.', 0, y0 + 7.5)
    txt('MagPanel Carrier v%s - 1:1 yerleşim testi (üst yüz)' % REV, 0, -22, 3.0)
    txt('Kâğıdı köpük ya da kartona yapıştır, parça bacaklarını pedlerin ortasındaki beyaz deliklerden geçir.',
        0, -17)
    txt('DevKit: sol sıra + sağda %s sırası; 74HCT245: DIP-20 soket.' %
        ' / '.join('%.1f" (%.2f mm)' % (r / 25.4, r) for r in DEVKIT_RIGHT_ROWS), 0, -13)
    path = tmp / 'print.kicad_pcb'
    pcbnew.SaveBoard(str(path), b)
    kcli('pcb', 'export', 'pdf', '--layers', 'Edge.Cuts,F.Cu,F.Fab,F.Silkscreen,Dwgs.User', '--black-and-white',
         '--drill-shape-opt', '2', '-o', out_pdf, path)

def schematic_png(out_png, width=4200, final=2400):
    from PIL import Image
    sd = WORK / 'schsvg'
    shutil.rmtree(sd, ignore_errors=True)
    sd.mkdir(parents=True)
    kcli('sch', 'export', 'svg', '-o', sd, OUT / (PROJ + '.kicad_sch'))
    svg = sd / (PROJ + '.svg')
    png = sd / (PROJ + '.png')
    svg_to_png(svg, png, width)
    im = Image.open(png).convert('RGB')
    im = im.resize((final, int(round(final * im.size[1] / im.size[0]))), Image.LANCZOS)
    im.quantize(colors=64, method=Image.Quantize.MEDIANCUT).save(out_png, optimize=True)
    return im.size

def fab_diy_sheets(brd):
    """Ev yapimi montaj cizimleri (A4, 1:1): ust yuz (delikli parcalar + ust katman gecisleri + via'lar) ve
    alt yuz (alttan bakis, aynali: SMD'ler + izler). Via'lar iki cizimde de: her birine tel gecip iki yuzden lehim."""
    import pcbnew
    tmp = WORK / 'print'
    tmp.mkdir(parents=True, exist_ok=True)
    nvia = sum(1 for t in brd.GetTracks() if t.GetClass() == 'PCB_VIA')
    out = []
    for side, layers, mirror, title in (
            ('top', 'Edge.Cuts,F.Cu,F.Fab,F.Silkscreen,Dwgs.User', False,
             'ÜST YÜZ (üstten bakış): delikli parçalar, üst katman geçişleri, %d via' % nvia),
            ('bottom', 'Edge.Cuts,B.Cu,B.Fab,B.Silkscreen,Dwgs.User', True,
             'ALT YÜZ (alttan bakış): SMD parçalar ve lehim tarafı, %d via' % nvia)):
        b = pcbnew.LoadBoard(str(OUT / (PROJ + '.kicad_pcb')))
        for z in list(b.Zones()):                      # dokum ve yasak bolgeler yok: izler okunsun
            board_remove(b, z)
        t = pcbnew.PCB_TEXT(b)
        t.SetText('MagPanel Carrier v%s DIY - %s' % (REV, title)); t.SetLayer(pcbnew.Dwgs_User)
        t.SetPosition(V(0, -8)); t.SetTextSize(pcbnew.VECTOR2I(mm(2.2), mm(2.2)))
        t.SetTextThickness(mm(0.3))
        # aynali sayfada kart sayfanin sagina duser: baslik kartin sag kenarinda biter, sola uzar (sayfadan tasmaz)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if mirror else pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetMirrored(mirror)                          # PDF aynalaninca okunur
        b.Add(t)
        for k in range(11):                            # 100 mm olcek cubugu
            sh = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
            sh.SetStart(V(10 * k, BOARD_H + 6 - (3 if k % 5 == 0 else 1.8))); sh.SetEnd(V(10 * k, BOARD_H + 6))
            sh.SetLayer(pcbnew.Dwgs_User); sh.SetWidth(mm(0.3)); b.Add(sh)
        sh = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(V(0, BOARD_H + 6)); sh.SetEnd(V(100, BOARD_H + 6)); sh.SetLayer(pcbnew.Dwgs_User)
        sh.SetWidth(mm(0.3)); b.Add(sh)
        path = tmp / ('diy-%s.kicad_pcb' % side)
        pcbnew.SaveBoard(str(path), b)
        pdf = FAB / ('%s-assembly-%s.pdf' % (PROJ, side))
        args = ['pcb', 'export', 'pdf', '--layers', layers, '--black-and-white', '--drill-shape-opt', '2']
        if mirror:
            args.append('--mirror')
        kcli(*args, '-o', pdf, path)
        out.append(pdf.name)
    return out

# --- Elegoo Saturn 3 / 3 Ultra pozlama dosyalari (.goo). UVtools 7 komut satiri (UVtoolsCmd) varsa uretilir ---
UVTOOLS = os.environ.get('UVTOOLS_CMD') or shutil.which('UVtoolsCmd')
SATURN3 = {'display_width': 218.88, 'display_height': 122.88, 'display_pixels_x': 11520, 'display_pixels_y': 5120}
DIY_EXPOSURE = float(os.environ.get('DIY_EXPOSURE', 30))   # s, yer tutucu: pozlama testinden sonra degistirilir
DIY_TEST = (6, 10)            # pozlama testi: 6 serit, serit basina 10 s -> 10, 20 ... 60 s

def uvtools(*args):
    r = subprocess.run([UVTOOLS] + [str(a) for a in args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('UVtoolsCmd %s:\n%s' % (args[0], (r.stdout + r.stderr)[-2000:]))

def goo_fix_date(path):
    """Goo basligindaki uretim zamani -> DATE (ayni kart -> ayni dosya). Basligin saglama toplami yok."""
    import re
    data = bytearray(path.read_bytes())
    m = re.search(rb'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d', bytes(data[:512]))
    if m:
        data[m.start():m.end()] = (DATE + ' 00:00:00').encode()
    path.write_bytes(bytes(data))

def saturn3_goo(path, layers, exposure):
    """Ekran cozunurlugundeki katman goruntulerinden (PIL 'L') Saturn 3 .goo dosyasi. UVtools PrusaSlicer SL1
    arsivini okuyup Goo'ya cevirir; ekran degerleri UVtools'un Saturn 3 profiliyle ayni (display_mirror_x = 1)."""
    import io
    import zipfile
    sl1 = WORK / (path.stem + '.sl1')
    cfg = ('action = print\njobDir = magpanel\nexpTime = %g\nexpTimeFirst = %g\nlayerHeight = 0.05\nnumFade = 0\n'
           'numFast = %d\nnumSlow = 0\nprinterModel = SL1\nprinterProfile = Elegoo Saturn 3\nprinterVariant = default\n'
           % (exposure, exposure, len(layers)))
    ini = ''.join('%s = %s\n' % kv for kv in SATURN3.items()) + (
        'display_orientation = landscape\ndisplay_mirror_x = 1\ndisplay_mirror_y = 0\nmax_print_height = 250\n'
        'printer_model = SL1\nprinter_settings_id = Elegoo Saturn 3\n')
    with zipfile.ZipFile(sl1, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('config.ini', cfg)
        z.writestr('prusaslicer.ini', ini)
        for k, im in enumerate(layers):
            b = io.BytesIO()
            im.save(b, 'PNG')
            z.writestr('magpanel%05d.png' % k, b.getvalue())
    uvtools('convert', sl1, 'GooFile', path)
    uvtools('set-properties', path, 'BottomLayerCount=1', 'TransitionLayerCount=0',
            'BottomExposureTime=%g' % exposure, 'ExposureTime=%g' % exposure)
    goo_fix_date(path)

def pcb_exposure_goo(base, out, files, mirror, exposure):
    """UVtools 'PCB exposure' islemi (ayarlar DIY.md tablosuyla ayni). files: [(yol, kart_dis_hatti, boyut_olcegi)].
    Delik dosyasi varsayilan olarak karanlik cizilir: kucultulunce pedin ortasinda bakirsiz merkez noktasi kalir."""
    from xml.sax.saxutils import escape
    items = ''.join('<PCBExposureFile><FilePath>%s</FilePath><InvertPolarity>false</InvertPolarity>'
                    '<IsBoardOutline>%s</IsBoardOutline><SizeScale>%g</SizeScale></PCBExposureFile>'
                    % (escape(str(f)), str(outline).lower(), scale) for f, outline, scale in files)
    op = WORK / (out.stem + '.uvtop')
    op.write_text('<?xml version="1.0" encoding="utf-8"?>\n<OperationPCBExposure '
                  'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
                  '<Files>%s</Files><MergeFiles>true</MergeFiles><LayerHeight>0.05</LayerHeight>'
                  '<ExposureTime>%g</ExposureTime><SizeMidpointRounding>AwayFromZero</SizeMidpointRounding>'
                  '<OffsetX>0</OffsetX><OffsetY>0</OffsetY><Mirror>%s</Mirror><InvertColor>false</InvertColor>'
                  '<EnableAntiAliasing>false</EnableAntiAliasing><FlipVertically>true</FlipVertically>'
                  '<Anchor>MiddleCenter</Anchor><FillPlate>false</FillPlate></OperationPCBExposure>\n'
                  % (items, exposure, str(mirror).lower()))
    uvtools('run', base, op, '-o', out)
    goo_fix_date(out)

SEG7 = {'0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg', '5': 'acdfg', '6': 'acdefg',
        '7': 'abc', '8': 'abcdefg', '9': 'abcdfg'}

def exposure_test_layers():
    """Pozlama testi: ekran ortasinda DIY_TEST[0] serit. Katman k seritleri k..son yakar, serit k toplam (k+1) adim
    isik alir. Her seritte sure etiketi (film yuzunden duz okunsun diye aynali), 0.2 / 0.25 / 0.3 mm cizgi-bosluk
    (iki yonde: ekran pikseli 19 x 24 um) ve HUB75 pin araligi ornegi: 1.7 mm pedler arasindan 0.25 mm iz."""
    from PIL import Image, ImageDraw
    n, step = DIY_TEST
    W, H = SATURN3['display_pixels_x'], SATURN3['display_pixels_y']
    sx, sy = W / SATURN3['display_width'], H / SATURN3['display_height']
    bw, bh = 16.0, 24.0                                   # serit (mm)
    x0 = SATURN3['display_width'] / 2 - n * bw / 2
    y0 = SATURN3['display_height'] / 2 - bh / 2

    def rect(d, x1, y1, x2, y2):
        d.rectangle((round(x1 * sx), round(y1 * sy), round(x2 * sx) - 1, round(y2 * sy) - 1), fill=255)

    def disc(d, x, y, r):
        d.ellipse((round((x - r) * sx), round((y - r) * sy), round((x + r) * sx) - 1, round((y + r) * sy) - 1), fill=255)

    def digit(d, ch, x, y, w=2.4, h=4.4, t=0.5):      # 7 bolumlu rakam, sol-ust (x, y), yatay aynali
        segs = {'a': (0, 0, w, t), 'b': (0, 0, t, h / 2), 'c': (0, h / 2, t, h / 2), 'd': (0, h - t, w, t),
                'e': (w - t, h / 2, t, h / 2), 'f': (w - t, 0, t, h / 2), 'g': (0, h / 2 - t / 2, w, t)}
        for s in SEG7[ch]:
            dx, dy, sw, sh = segs[s]
            rect(d, x + dx, y + dy, x + dx + sw, y + dy + sh)

    def band(d, k):
        bx = x0 + k * bw
        label = '%d' % ((k + 1) * step)
        for j, ch in enumerate(reversed(label)):         # aynali: sondan basa, soldan saga
            digit(d, ch, bx + 2.0 + j * 3.2, y0 + 1.5)
        for g, gw in enumerate((0.2, 0.25, 0.3)):        # dikey cizgiler (x yonunde bosluk)
            gx = bx + 1.5 + g * 4.6
            for m in range(4):
                rect(d, gx + 2 * m * gw, y0 + 7.5, gx + (2 * m + 1) * gw, y0 + 13.5)
        for g, gw in enumerate((0.2, 0.25, 0.3)):        # yatay cizgiler (y yonunde bosluk)
            gy = y0 + 15.0 + g * 2.6
            for m in range(4):
                rect(d, bx + 1.5, gy + 2 * m * gw, bx + 8.0, gy + (2 * m + 1) * gw)
        for m in range(3):                               # HUB75 ornegi: 2.54 mm adimli pedler, aradan iz
            disc(d, bx + 11.5, y0 + 15.0 + m * 2.54, 0.85)
        for m in range(2):
            rect(d, bx + 9.5, y0 + 15.0 + (m + 0.5) * 2.54 - 0.125, bx + 15.0, y0 + 15.0 + (m + 0.5) * 2.54 + 0.125)

    layers = []
    for i in range(n):
        im = Image.new('L', (W, H), 0)
        d = ImageDraw.Draw(im)
        g, f = 2.5, DIY_FRAME[1]                          # yerlestirme cercevesi: ~100 x 28 mm serit sigar
        rect(d, x0 - g - f, y0 - g - f, x0 + n * bw + g + f, y0 - g)
        rect(d, x0 - g - f, y0 + bh + g, x0 + n * bw + g + f, y0 + bh + g + f)
        rect(d, x0 - g - f, y0 - g, x0 - g, y0 + bh + g)
        rect(d, x0 + n * bw + g, y0 - g, x0 + n * bw + g + f, y0 + bh + g)
        for k in range(i, n):
            band(d, k)
        layers.append(im)
    return layers

def fab_saturn3(gd):
    """fab-diy/saturn3/: cerceve.goo (yerlestirme), alt.goo, ust.goo, pozlama-testi.goo. UVtoolsCmd yoksa atlanir."""
    if not UVTOOLS:
        print('saturn3: UVtoolsCmd bulunamadi (UVTOOLS_CMD=... ile verilebilir), .goo dosyalari atlandi')
        return
    out = FAB / 'saturn3'
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    from PIL import Image
    base = WORK / 'saturn3-base.goo'
    saturn3_goo(base, [Image.new('L', (SATURN3['display_pixels_x'], SATURN3['display_pixels_y']), 0)], DIY_EXPOSURE)
    f = lambda suffix: gd / (PROJ + suffix)
    outline, frame = (f('-Edge_Cuts.gko'), True, 1), (f('-Hizalama.gbr'), False, 1)
    pcb_exposure_goo(base, out / 'cerceve.goo', [outline, frame], False, 120)
    pcb_exposure_goo(base, out / 'alt.goo', [outline, (f('-B_Cu.gbl'), False, 1), frame, (f('-PTH.drl'), False, 0.4)],
                     False, DIY_EXPOSURE)
    pcb_exposure_goo(base, out / 'ust.goo', [outline, (f('-F_Cu.gtl'), False, 1), frame], True, DIY_EXPOSURE)
    saturn3_goo(out / 'pozlama-testi.goo', exposure_test_layers(), DIY_TEST[1])
    return sorted(p.name for p in out.iterdir())

def copper_bbox(board, layer):
    """Bir bakir katmandaki her seyin sinir kutusu (yerel mm): iz, via, ped, dokum dolgusu, cizim."""
    import pcbnew
    boxes = [t.GetBoundingBox() for t in board.GetTracks() if t.IsOnLayer(layer)]
    boxes += [p.GetBoundingBox() for fp in board.GetFootprints() for p in fp.Pads() if p.IsOnLayer(layer)]
    boxes += [d.GetBoundingBox() for d in board.GetDrawings() if d.GetLayer() == layer]
    boxes += [z.GetFilledPolysList(layer).BBox() for z in board.Zones()
              if not z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetFilledPolysList(layer).OutlineCount()]
    x0 = min(pcbnew.ToMM(b.GetLeft()) for b in boxes) - ORIGIN[0]
    y0 = min(pcbnew.ToMM(b.GetTop()) for b in boxes) - ORIGIN[1]
    x1 = max(pcbnew.ToMM(b.GetRight()) for b in boxes) - ORIGIN[0]
    y1 = max(pcbnew.ToMM(b.GetBottom()) for b in boxes) - ORIGIN[1]
    return x0, y0, x1, y1

def stage_fab_diy():
    """Ev yapimi ciktilari (fab-diy/): UVtools PCB exposure icin gerber + delik (orijin kartin sol-alt kosesi),
    iki yuzun 1:1 montaj cizimi, BOM ve gorseller."""
    check_erc_drc()
    import pcbnew
    board = pcbnew.LoadBoard(str(OUT / (PROJ + '.kicad_pcb')))
    if board.GetDesignSettings().GetAuxOrigin() != V(*PLACE_ORIGIN):
        raise RuntimeError('yerlesim orijini kartin sol-alt kosesinde degil: pcb ve route asamalarini yeniden calistir')
    for fp in board.GetFootprints():              # soket pinleri ustten lehimlenemez: ustte delikli ped bakiri yok
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pad.IsOnLayer(pcbnew.F_Cu):
                raise RuntimeError('ustte delikli ped bakiri: %s %s' % (fp.GetReference(), pad.GetNumber()))
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):      # UVtools 'Mirror' cizimi bakir sinir kutusunun ortasindan aynalar
        x0, y0, x1, y1 = copper_bbox(board, layer)
        dx, dy = (x0 + x1 - BOARD_W) / 2, (y0 + y1 - BOARD_H) / 2
        if max(abs(dx), abs(dy)) > 0.02:
            raise RuntimeError('%s bakir sinir kutusu kart ortasinda degil (%.2f, %.2f mm): aynalama ekseni kayar'
                               % (board.GetLayerName(layer), dx, dy))
    vias = [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']
    top = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetLayer() == pcbnew.F_Cu]
    holes = collections.Counter(round(pcbnew.ToMM(v.GetDrillValue()), 2) for v in vias)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                holes[round(pcbnew.ToMM(min(p.GetDrillSize().x, p.GetDrillSize().y)), 2)] += 1
    FAB.mkdir(exist_ok=True)
    files = fab_gerbers('F.Cu,B.Cu,F.Mask,B.Mask,Edge.Cuts')
    print('gerber: %d dosya -> %s/%s-gerber.zip (+ hizalama cercevesi)' % (len(files), FAB.name, PROJ))
    print('bom: %d satir -> %s/%s-bom.csv' % (fab_bom_cpl(board, smt=False), FAB.name, PROJ))
    print('montaj cizimleri:', ', '.join(fab_diy_sheets(board)))
    print('via (elle tel): %d | ust katman: %d iz parcasi, %.0f mm' % (
        len(vias), len(top), sum(pcbnew.ToMM(t.GetLength()) for t in top)))
    print('delikler:', ', '.join('%g mm x %d' % (d, n) for d, n in sorted(holes.items())))
    goo = fab_saturn3(WORK / 'gerber')
    if goo:
        print('saturn3: %s -> %s/saturn3/ (alt/ust %g s, yer tutucu)' % (', '.join(goo), FAB.name, DIY_EXPOSURE))
    if find_chrome() is None:
        print('gorseller atlandi: Chromium/Chrome bulunamadi (CHROME=... ile verilebilir)')
        return
    IMG.mkdir(exist_ok=True)
    print('gorsel: diy-top.png', board_render(board, 'top', IMG / 'diy-top.png'))
    print('gorsel: diy-bottom.png', board_render(board, 'bottom', IMG / 'diy-bottom.png'))

def stage_fab():
    if DIY:
        return stage_fab_diy()
    check_erc_drc()
    import pcbnew
    board = pcbnew.LoadBoard(str(OUT / (PROJ + '.kicad_pcb')))
    if board.GetDesignSettings().GetAuxOrigin() != V(*PLACE_ORIGIN):
        raise RuntimeError('yerlesim orijini kartin sol-alt kosesinde degil: pcb ve route asamalarini yeniden calistir')
    FAB.mkdir(exist_ok=True)
    files = fab_gerbers()
    print('gerber: %d dosya -> fab/%s-gerber.zip (orijin: kartin sol-alt kosesi)' % (len(files), PROJ))
    print('bom: %d satir, montaj: %d satir / %d parca -> fab/%s-bom.csv, jlc-bom/cpl, robotistan-bom/pnp'
          % (*fab_bom_cpl(board), PROJ))
    kcli('sch', 'export', 'pdf', '-o', FAB / (PROJ + '-schematic.pdf'), OUT / (PROJ + '.kicad_sch'))
    fab_print(board, FAB / (PROJ + '-1to1.pdf'))
    print('baski: fab/%s-1to1.pdf (A4, %%100 olcek)' % PROJ)
    if find_chrome() is None:
        print('gorseller atlandi: Chromium/Chrome bulunamadi (CHROME=... ile verilebilir)')
        return
    IMG.mkdir(exist_ok=True)
    print('gorsel: schematic.png', schematic_png(IMG / 'schematic.png'))
    print('gorsel: pcb-top.png', board_render(board, 'top', IMG / 'pcb-top.png'))
    print('gorsel: pcb-bottom.png', board_render(board, 'bottom', IMG / 'pcb-bottom.png'))


# =============================================================================
if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['sch', 'pcb', 'route', 'fab', 'all'])
    ap.add_argument('--diy', action='store_true', help='ev yapimi cift yuz surum (magpanel-carrier-diy/, fab-diy/)')
    a = ap.parse_args()
    if a.diy:
        set_variant_diy()
    if a.stage in ('sch', 'all'):
        stage_sch()
    if a.stage in ('pcb', 'all'):
        stage_pcb()
    if a.stage in ('route', 'all'):
        stage_route()
    if a.stage in ('fab', 'all'):
        stage_fab()
