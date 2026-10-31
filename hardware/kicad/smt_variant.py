"""MagPanel taşıyıcı kart: yalnız SMD, tek yüz, ev yapımı (--smt).

gen_carrier.py ile aynı şematik ve netler; yalnız ayak izleri, yerleşim ve üretim çıktıları farklı.
Kart hiç delik içermez: bakır Saturn 3 Ultra ile pozitif lakla pozlanır, UV lehim maskesi de aynı yazıcıyla
pozlanır, macun reçine stencil ile sürülür, parçalar yerleştirme şablonuyla dizilir, ısıtıcı tablada tek
seferde lehimlenir.

Bakır katman F.Cu (parça yüzü = bakır yüzü). Üretim: gen_carrier.py --smt sch|pcb|route|fab|all
"""
import collections
import json
import os
import shutil
from pathlib import Path

gc = None          # gen_carrier modülü (setup() bağlar)

# =============================================================================
#  KART VE YERLEŞİM (yerel mm: kartın sol-üst köşesi, y aşağı, parça yüzünden bakış)
# =============================================================================
REV = '1.3'
DATE = '2026-10-31'
SIZE = (150.0, 100.0)
DK_X = 97.0                 # DevKit sol sıra (J1 pin 1 x); sağ sıra DK_X + 25.4
U_X = 82.0                  # 74HCT245 (SOIC-20W) merkez x; 180 derece: A pinleri (1-10) sağda, DevKit'e bakar
RX, RP, RY0 = 64.0, 3.3, 3.2  # seri 33R sütunu: merkez x, satır aralığı, ilk satır y (1206, 180 derece: ped 1 sağda)
LANE = 0.4                  # direnç gövdesi altındaki geçiş: iki şerit, sütun ekseninden +-0.4 mm
HX = {'J2': 42.2, 'J3': 26.6, 'J4': 11.0}   # HUB75 başlık merkez x (J2 tamponlara en yakın = PANEL 1)
HY1 = 19.11                 # J2 pin 1 y; J3, J4 1.27 mm basamaklı aşağıda (başlıklar arası izler düz)
HUB_PI, HUB_PO = 2.3, 6.5   # SMD kutu başlık pedleri: iç / dış uç (merkezden); kütüphanede iç uç 1.3
SENS_X = 142.6              # sensör başlıkları (dikey, pin 1 üstte); sağlarında GND hattı
GND_BUS_X = 148.4           # sensör GND hattı (kart kenarı boyunca)
IO38_X = 107.5              # IO38'in DevKit altındaki dikey yolu; +3V3 bunun üstünden JP1 (0 ohm) ile geçer
V33_X = 106.75              # +3V3 DevKit altı dikey hattı (pull-down'larla IO38 arasında)
JP1_POS = (107.5, 12.0)     # 0 ohm köprü: IO38 gövdesinin altından geçer
W = 0.25                    # sinyal izi
STEP = 0.8                  # merdiven yelpazesinde dikey izler arası
CH = 0.5                    # köşe pahı (45 derece)

# Seri dirençlerin satır sırası (yukarıdan aşağı). Tampon tarafı (ped 1) tampon B pin sırasını izler; konnektör
# tarafı (ped 2) başlık sırasına (1 R1 ... 16 GND) gövde altı şeritlerle geçer:
#   E: U3 gövdesinin altından yukarı, sütunun sağ şeridinden 7. satıra (tampon tarafı)
#   CLK: sağ şeritten 13. satıra (tampon tarafı)
#   LAT2: sol şeritten CLK ile LAT arasına, LAT3: sol şeritten LAT ile OE arasına (konnektör tarafı)
R_ORDER = ['R1', 'G1', 'B1', 'R2', 'G2', 'B2', 'ADDR_E', 'LAT2', 'ADDR_A', 'ADDR_B', 'ADDR_C', 'ADDR_D',
           'CLK', 'LAT', 'OE', 'LAT3']

# SMD karşılıkları. 1206: büyük ped, gövde altından iki iz geçer (köprü yerine).
FP_SMT = {
    'TB2': 'MagPanel:BarrelJack_PJ-036AH-SMT',
    'PTC': 'Fuse:Fuse_1812_4532Metric',
    'SMA': 'Diode_SMD:D_SMA',
    'CP8': 'Capacitor_SMD:CP_Elec_8x10.5',
    'C0805': 'Capacitor_SMD:C_1206_3216Metric',
    'R0805': 'Resistor_SMD:R_1206_3216Metric',
    'LED0805': 'LED_SMD:LED_1206_3216Metric',
    'DIP20': 'Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm',
    'IDC16': 'MagPanel:IDC-Header_2x08_P2.54mm_Vertical_SMD',
    'H3': 'MagPanel:PinHeader_1x03_P2.54mm_SMD',
    'H4': 'MagPanel:PinHeader_1x04_P2.54mm_SMD',
    'H5': 'MagPanel:PinHeader_1x05_P2.54mm_SMD',
    'MH': 'MagPanel:MountMark_M3',
    'DEVKIT': 'MagPanel:ESP32-S3-DevKitC-1_SMD',
}

# Parça bilgisi (BOM): anahtar -> (açıklama, kılıf, üstündeki kod, Komponentci araması, not)
PARTS = {
    '33R': ('Direnç 33 Ω %5', '1206', '330', 'SMD direnç 1206 33R', ''),
    '10k': ('Direnç 10 kΩ %5', '1206', '103', 'SMD direnç 1206 10K', ''),
    '2.2k': ('Direnç 2,2 kΩ %5', '1206', '222', 'SMD direnç 1206 2K2', ''),
    '100nF': ('Seramik kondansatör 100 nF 50 V X7R', '1206', 'yok', 'SMD kondansatör 1206 100nF', ''),
    '10uF': ('Seramik kondansatör 10 µF 25 V X5R', '1206', 'yok', 'SMD kondansatör 1206 10uF', ''),
    'LED': ('LED yeşil', '1206', 'katot işareti (üreticiye göre)', 'SMD LED 1206 yeşil',
            'katodu ölçü aletinin diyot kademesiyle doğrula'),
    'PTC': ('PTC sigorta 1,5 A tutma (6 V)', '1812', '—', 'SMD PTC sigorta 1812 1.5A', 'MF-MSMF150 ya da eşi'),
    'TVS': ('TVS diyot SMAJ5.0A', 'SMA (DO-214AC)', 'çizgi = katot', 'SMAJ5.0A', 'tek yönlü (A sonu)'),
    'C470': ('Elektrolitik 470 µF 16 V (SMD, V-chip)', '8 × 10,5 mm', 'siyah kenar = eksi', 'SMD elektrolitik 470uF 16V 8x10',
             'fırına dayanıklı (V-chip)'),
    '245': ('74HCT245 (HCT olmalı, HC değil)', 'SOIC-20 geniş (7,5 mm)', '74HCT245 / HCT245',
            '74HCT245 SOIC-20', 'SN74HCT245DWR, 74HCT245D ya da eşi; nokta = pin 1'),
    'IDC': ('Kutu başlık 2x8 erkek, SMD, düz', '2,54 mm, SMD', 'çentik', 'SMD box header 16 pin 2.54',
            'yüksek sıcaklık plastik; alt tırnak varsa kes'),
    'DEVSOCK': ('Dişi pin başlık 1x22, SMD, düz', '2,54 mm, SMD', '—', 'SMD dişi pin header 1x22 2.54',
                '2 adet; 1x40 kesilebilir. Yüksek sıcaklık plastik'),
    'H3': ('Erkek pin başlık 1x3, SMD, düz', '2,54 mm, SMD', '—', 'SMD erkek pin header 2.54',
           '1x40 SMD erkek başlıktan kesilebilir'),
    'H5': ('Erkek pin başlık 1x5, SMD, düz', '2,54 mm, SMD', '—', 'SMD erkek pin header 2.54',
           '1x40 SMD erkek başlıktan kesilebilir'),
    'JACK': ('DC jak 5,5 × 2,1 mm, SMD', 'PJ-036AH-SMT ayak izi', '—', 'SMD DC jak 5.5x2.1',
             'orta pin +5 V. Alt pim varsa kes (delik yok)'),
    'DEVKIT': ('ESP32-S3 DevKitC-1 N16R8 klon (sıralar arası 1,0")', 'modül', '—', 'ESP32-S3 N16R8 devkit',
               'sokete takılır, lehimlenmez'),
    '0R': ('Direnç 0 Ω (köprü)', '1206', '0 ya da 000', 'SMD direnç 1206 0R',
           'JP1: şematikte yok, +3V3 IO38 izinin üstünden geçer'),
}

# =============================================================================
#  VARYANT KURULUMU
# =============================================================================
def setup(mod):
    """gen_carrier modül değişkenlerini SMD varyantına çevir (şematik aynı netlerle üretilir)."""
    global gc
    gc = mod
    gc.SMT = True
    gc.REV, gc.DATE = REV, DATE
    gc.PROJ = 'magpanel-carrier-smt'
    gc.OUT = gc.HERE / gc.PROJ
    gc.FAB = gc.HERE / 'fab-smt'
    gc.PREROUTE = gc.WORK / (gc.PROJ + '-preroute.kicad_pcb')
    gc.BOARD_W, gc.BOARD_H = SIZE
    gc.PLACE_ORIGIN = (0.0, SIZE[1])
    gc.FP.update(FP_SMT)
    gc.J1X, gc.XR = DK_X, DK_X + gc.DEVKIT_ROW_IN
    gc.PLACE = place()
    gc.NETCLASSES = [('Default', W, 0.25, 0.8, 0.4, []),
                     ('Power', 0.6, 0.25, 0.8, 0.4, ['+5V', '/VIN']),
                     ('Power3V3', 0.4, 0.25, 0.8, 0.4, ['+3V3']),
                     ('GND', 0.4, 0.25, 0.8, 0.4, ['GND'])]
    gc.RULES.update({'min_clearance': 0.25, 'min_track_width': W, 'min_copper_edge_clearance': 0.5,
                     'min_via_diameter': 0.8, 'min_through_hole_diameter': 0.4})
    sm = lambda key, mpn, mfr='UNI-ROYAL': {'MPN': mpn, 'Manufacturer': mfr, 'LCSC': ''}
    ov = {}
    for ref, _, _ in gc.SERIES_R:
        ov[ref] = {'fields': sm('33R', '1206W4J0330T5E')}
    for ref in ('R2', 'R3', 'R4', 'R5', 'R6', 'R7'):
        ov[ref] = {'fields': sm('10k', '1206W4J0103T5E')}
    ov['R1'] = {'fields': sm('2.2k', '1206W4J0222T5E')}
    for ref in ('C3', 'C4', 'C5', 'C6', 'C7'):
        ov[ref] = {'fields': sm('100nF', 'CC1206KRX7R9BB104', 'YAGEO')}
    for ref in ('C2', 'C8'):
        ov[ref] = {'fields': sm('10uF', 'CL31A106KAHNNNE', 'Samsung')}
    ov['D2'] = {'fields': sm('LED', 'KT-1206G', 'Hubei KENTO')}
    ov['C1'] = {'value': '470uF 16V', 'fields': {'MPN': 'SMD elektrolitik 470 uF 16 V, 8 x 10.5 mm (V-chip, reflow)'}}
    ov['J1'] = {'fields': {'MPN': 'DC jak 5.5 x 2.1 mm SMD (CUI PJ-036AH-SMT ayak izi), orta pin +'},
                'desc': '5 V DC giris (adaptor fisi, orta pin +). Panel gucu PSU -> panel dogrudan; bu kart <= 1 A ceker.'}
    for ref in ('U2', 'U3'):
        ov[ref] = {'fields': {'MPN': 'SN74HCT245DWR / 74HCT245D (SOIC-20W)'}}
    for ref in ('J2', 'J3', 'J4'):
        ov[ref] = {'fields': {'MPN': 'SMD kutu baslik (box header) 2x8 2.54 mm, duz, reflow'}}
    for ref, _, pins, _ in gc.SENSOR_HDRS:
        ov[ref] = {'fields': {'MPN': 'SMD pin header 1x%d 2.54 mm erkek' % len(pins)}}
    ov['U1'] = {'fields': {'MPN': 'ESP32-S3 N16R8 klon (siralar arasi 1.0in) + 2x 1x22 SMD disi soket (2.54 mm)'}}
    gc.PART_OVERRIDE.update(ov)
    gc.TEXT_SUB[:] = [('2x 74HCT245 DIP', '2x 74HCT245 SOIC-20'), ('(0805)', '(1206)')]

def pin_y(n):
    return gc.PIN1Y + (n - 1) * gc.G

def row_of(sig):
    """HUB sinyalinin DevKit sol sıra pin numarası (= satır)."""
    return int(gc.devkit_pin(gc.HUB_GPIO[sig]))

def u_center_y(u):
    """SOIC 180 derece: pin k (1..10) y = merkez + 5.715 - 1.27 (k - 1); pin 2..9 ortalaması merkez."""
    rows = [row_of(s) for s in gc.BUF_CH[u]]
    return sum(pin_y(r) for r in rows) / len(rows)

def ry(sig):
    return RY0 + R_ORDER.index(sig) * RP

def hub_y(ref, r):
    """Başlık pin satırı r (0..7) y."""
    k = ['J2', 'J3', 'J4'].index(ref)
    return HY1 + k * gc.G / 2 + r * gc.G

def place():
    rx = DK_X + gc.DEVKIT_ROW_IN
    p = {
        'U1': (DK_X, gc.PIN1Y, 0, 'F'),
        'U2': (U_X, u_center_y('U2'), 180, 'F'), 'U3': (U_X, u_center_y('U3'), 180, 'F'),
        # tampon dekuplajı: C3 U2-U3 arasında (+5V U3 gövdesi altından gelir), C4/C8 U3'ün altında
        'C3': (86.0, 28.6, 0, 'F'), 'C4': (79.6, 50.0, 180, 'F'), 'C8': (79.6, 54.2, 180, 'F'),
        # pull-down'lar DevKit altında, sol sıranın iç tarafında (ped 1 pine); R5 (OE, satır 17) R2'nin
        # altına kayık (şablon duvarı)
        'R3': (DK_X + 7.0, pin_y(10), 0, 'F'), 'R2': (DK_X + 7.0, pin_y(16), 0, 'F'),
        'R5': (DK_X + 7.0, 45.5, 0, 'F'), 'R4': (DK_X + 7.0, pin_y(20), 0, 'F'),
        # sağ sıranın iç tarafı (IO38 halkasının içinde): IO2 pull-down, enkoder RC (ped 1 pine)
        'R7': (rx - 6.4, pin_y(5), 180, 'F'),
        'C5': (rx - 6.4, pin_y(7), 180, 'F'), 'C6': (rx - 12.2, pin_y(8), 180, 'F'), 'C7': (rx - 6.4, pin_y(9), 180, 'F'),
        # DHT pull-up: dış tarafta, DHT ile J8 3V3 hatlarının üstünde (pedler hatların üzerinde)
        'R6': (SENS_X - 7.5, 61.81, 90, 'F'),
        # 5 V girişi: DC jak alt kenarda (fiş aşağıdan), PTC, TVS, 470 uF
        'J1': (80.0, SIZE[1] - 10.1, 0, 'F'), 'F1': (80.7, 77.0, 90, 'F'),
        'D1': (88.0, 74.8625, 0, 'F'), 'C1': (68.0, 74.8625, 180, 'F'), 'C2': (75.6, 66.0, 180, 'F'),
        'R1': (94.5, 64.0, 270, 'F'), 'D2': (94.5, 70.5, 90, 'F'),
        # sensörler: J3 pin sırasıyla yukarıdan aşağı
        'J10': (SENS_X, 4.6, 0, 'F'), 'J5': (SENS_X, 20.0, 0, 'F'), 'J6': (SENS_X, 30.5, 0, 'F'),
        'J7': (SENS_X, 41.0, 0, 'F'), 'J8': (SENS_X, 58.0, 0, 'F'), 'J9': (SENS_X, 68.5, 0, 'F'),
        'H1': (3.5, 3.5, 0, 'F'), 'H2': (SIZE[0] - 3.5, 80.0, 0, 'F'), 'H3': (3.5, SIZE[1] - 3.5, 0, 'F'),
        'H4': (SIZE[0] - 3.5, SIZE[1] - 3.5, 0, 'F'),
    }
    for ref in ('J2', 'J3', 'J4'):
        p[ref] = (HX[ref], hub_y(ref, 0) + 3.5 * gc.G, 0, 'F')
    for ref, sig, _ in gc.SERIES_R:
        p[ref] = (RX, ry(sig), 180, 'F')
    return p

# =============================================================================
#  AYAK İZLERİ (MagPanel.pretty)
# =============================================================================
def _save(fp):
    import pcbnew
    lib = gc.OUT / 'MagPanel.pretty'
    lib.mkdir(parents=True, exist_ok=True)
    pcbnew.PCB_IO_KICAD_SEXPR().FootprintSave(str(lib), fp)

def _line(fp, layer, x1, y1, x2, y2, w=0.12):
    import pcbnew
    sh = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
    sh.SetStart(pcbnew.VECTOR2I(gc.mm(x1), gc.mm(y1))); sh.SetEnd(pcbnew.VECTOR2I(gc.mm(x2), gc.mm(y2)))
    sh.SetLayer(layer); sh.SetWidth(gc.mm(w)); fp.Add(sh)

def _rect(fp, layer, x1, y1, x2, y2, w=0.12):
    for a, b, c, d in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)):
        _line(fp, layer, a, b, c, d, w)

def _pad(fp, num, x, y, sx, sy, layers, shape=None):
    import pcbnew
    p = pcbnew.PAD(fp)
    p.SetNumber(num)
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetShape(shape if shape is not None else pcbnew.PAD_SHAPE_RECT)
    p.SetSize(pcbnew.VECTOR2I(gc.mm(sx), gc.mm(sy)))
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    p.SetLayerSet(ls)
    p.SetPosition(pcbnew.VECTOR2I(gc.mm(x), gc.mm(y)))
    fp.Add(p)
    return p

def _new_fp(name, descr, keywords):
    import pcbnew
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPIDAsString(name)
    fp.SetReference('REF**')
    fp.SetLibDescription(descr)
    fp.SetKeywords(keywords)
    fp.SetAttributes(pcbnew.FP_SMD)
    return fp

def universal_row(fp, n, x0, num0, length, leg, paste, pin1_rect=True):
    """Tek sıra SMD başlık/soket: bacaklar üreticiye göre sola ya da sağa açılır (Pin1Left/Pin1Right). Ped iki
    yöne de uzanır: hangi tip alınırsa alınsın oturur. Macun yalnız iki bacak bölgesinde (gövde altında lehim
    yok: dişi sokette lehim kontağa kaçmaz)."""
    import pcbnew
    cu = (pcbnew.F_Cu, pcbnew.F_Mask)
    for i in range(n):
        y = i * gc.G
        _pad(fp, str(num0 + i), x0, y, length, 1.0, cu,
             pcbnew.PAD_SHAPE_RECT if (i == 0 and pin1_rect) else pcbnew.PAD_SHAPE_ROUNDRECT)
        for s in (-1, 1):
            _pad(fp, '', x0 + s * leg, y, paste[0], paste[1], (pcbnew.F_Paste,))

def make_footprints():
    import pcbnew
    lib = gc.OUT / 'MagPanel.pretty'                  # her seferinde boş kütüphane: KIID dizisi aynı kalsın
    for f in lib.glob('*.kicad_mod'):
        f.unlink()
    lib.mkdir(parents=True, exist_ok=True)
    pcbnew.KIID.SeedGenerator(0x4D70)
    # --- DevKit: 2x 1x22 SMD dişi soket ---
    rows = gc.DEVKIT_RIGHT_ROWS
    fp = _new_fp('ESP32-S3-DevKitC-1_SMD',
                 'ESP32-S3-DevKitC-1 icin 2x 1x22 SMD disi soket (2.54 mm). Ped iki yone uzanir (Pin1Left ve '
                 'Pin1Right soketler oturur, bukulmus duz soket de olur). Sag sira %s mm.' %
                 ', '.join('%.2f' % r for r in rows), 'ESP32-S3 DevKitC-1 socket SMD 2x22')
    universal_row(fp, 22, 0.0, 1, 5.2, 1.75, (1.4, 0.8))
    for r in rows:
        universal_row(fp, 22, r, 23, 5.2, 1.75, (1.4, 0.8), pin1_rect=False)
    last, xout = 21 * gc.G, max(rows)
    xc = xout / 2
    _rect(fp, pcbnew.F_Fab, -1.27, -1.565, xout + 1.27, last + 7.96, 0.1)
    _rect(fp, pcbnew.F_Fab, xc - 9.0, -1.565 - 6.3, xc + 9.0, -1.565, 0.1)       # anten (kartın dışına taşar)
    for x in [0.0] + rows:
        _rect(fp, pcbnew.F_Fab, x - 1.27, -1.27, x + 1.27, last + 1.27, 0.1)        # soket gövdesi
        _rect(fp, pcbnew.F_CrtYd, x - 3.1, -1.05, x + 3.1, last + 1.05, 0.05)
    _line(fp, pcbnew.F_SilkS, -3.0, -1.0, -3.0, 1.0)                                 # pin 1 işareti
    fp.Reference().SetPosition(pcbnew.VECTOR2I(gc.mm(xc), gc.mm(last + 4.3)))
    fp.Value().SetText('ESP32-S3-DevKitC-1'); fp.Value().SetLayer(pcbnew.F_Fab)
    fp.Value().SetPosition(pcbnew.VECTOR2I(gc.mm(xc), gc.mm(last + 9.2)))
    _save(fp)
    # --- 1xN SMD erkek başlık ---
    for n in (3, 4, 5):
        fp = _new_fp('PinHeader_1x%02d_P2.54mm_SMD' % n,
                     '1x%d SMD erkek pin baslik 2.54 mm; ped iki yone uzanir (Pin1Left / Pin1Right)' % n,
                     'pin header SMD 2.54')
        universal_row(fp, n, 0.0, 1, 5.8, 1.8, (1.6, 0.8))
        _rect(fp, pcbnew.F_Fab, -1.27, -1.27, 1.27, (n - 1) * gc.G + 1.27, 0.1)
        _rect(fp, pcbnew.F_CrtYd, -3.4, -1.05, 3.4, (n - 1) * gc.G + 1.05, 0.05)
        _line(fp, pcbnew.F_SilkS, -3.3, -1.0, -3.3, 1.0)
        fp.Reference().SetPosition(pcbnew.VECTOR2I(0, gc.mm(-2.2)))
        fp.Value().SetLayer(pcbnew.F_Fab)
        _save(fp)
    # --- SMD kutu başlık: kütüphanedeki, pedlerin iç ucu 1 mm kısaltılmış (gövde ortasından 4 iz geçer) ---
    fp = gc.load_fp('Connector_IDC:IDC-Header_2x08_P2.54mm_Vertical_SMD')
    fp.SetFPIDAsString('IDC-Header_2x08_P2.54mm_Vertical_SMD')
    fp.SetLibDescription('SMD IDC kutu baslik 2x08 2.54 mm (kutuphaneden). Pedlerin ic ucu %.1f mm: bacagin '
                         'disa bukulen kismi ped uzerinde kalir, govde altindan HUB75 seridi gecer.' % HUB_PI)
    for p in fp.Pads():
        s = 1 if p.GetPosition().x > 0 else -1
        p.SetSize(pcbnew.VECTOR2I(gc.mm(HUB_PO - HUB_PI), p.GetSize().y))
        p.SetPosition(pcbnew.VECTOR2I(gc.mm(s * (HUB_PO + HUB_PI) / 2), p.GetPosition().y))
    _save(fp)
    # --- DC jak: kütüphanedeki, plastik pim deliği yok, anahtar pedi (3) GND'ye ---
    fp = gc.load_fp('Connector_BarrelJack:BarrelJack_CUI_PJ-036AH-SMT_Horizontal')
    fp.SetFPIDAsString('BarrelJack_PJ-036AH-SMT')
    fp.SetLibDescription('DC jak 5.5x2.1 SMD (CUI PJ-036AH-SMT ayak izi). Plastik konum pimi icin delik yok '
                         '(pim varsa kesilir). Ped 3 (anahtar) GND (ped 2 ile ayni), mekanik saglamlik icin.')
    for p in list(fp.Pads()):
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            fp.Remove(p)
        elif p.GetNumber() == '3':
            p.SetNumber('2')
    _save(fp)
    # --- 0 ohm köprü: iki bakır parçalı TEK ped (KiCad 8 iki ucu bağlı sayar; altından iz geçer) ---
    fp = _new_fp('Bridge_0R_1206', '0 ohm 1206 kopru (tek yuz kartta iz gecisi). Iki ped tek ped numarasi: KiCad '
                 'baglantiyi direncin icinden sayar. Govde altindan bir iz gecer.', 'jumper bridge 0R 1206')
    for s in (-1, 1):
        _pad(fp, str(1 + (s > 0)), s * 1.4625, 0, 1.125, 1.75, (pcbnew.F_Cu, pcbnew.F_Mask))
    for s in (-1, 1):
        _pad(fp, '', s * 1.4625, 0, 1.0, 1.6, (pcbnew.F_Paste,))
    _rect(fp, pcbnew.F_Fab, -1.6, -0.8, 1.6, 0.8, 0.1)
    _rect(fp, pcbnew.F_CrtYd, -2.28, -1.12, 2.28, 1.12, 0.05)
    fp.Reference().SetPosition(pcbnew.VECTOR2I(0, gc.mm(-1.8)))
    fp.Value().SetText('0R'); fp.Value().SetLayer(pcbnew.F_Fab)
    _save(fp)
    # --- montaj işareti: delik yok, bakır halka + merkez (istenirse sonradan delinir) ---
    fp = _new_fp('MountMark_M3', 'M3 montaj yeri isareti: delik YOK. Bakir halka ve merkez noktasi; istenirse '
                 '3.2 mm delinir.', 'mounting mark no hole')
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
    for r, w in ((1.6, 0.3), (0.25, 0.5)):
        c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(gc.mm(r), 0))
        c.SetLayer(pcbnew.F_Cu); c.SetWidth(gc.mm(w)); c.SetFilled(False)
        fp.Add(c)
    c = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    c.SetCenter(pcbnew.VECTOR2I(0, 0)); c.SetEnd(pcbnew.VECTOR2I(gc.mm(2.2), 0))
    c.SetLayer(pcbnew.F_CrtYd); c.SetWidth(gc.mm(0.05)); c.SetFilled(False)
    fp.Add(c)
    fp.Value().SetLayer(pcbnew.F_Fab)
    _save(fp)

# =============================================================================
#  SABİT İZLER
# =============================================================================
def stair(x0, y0, xv, y1, x1, ch=CH):
    """Sola giden iz: (x0, y0) -> yatay -> xv'de dikey -> y1'de yatay -> (x1, y1); köşeler 45 derece pahlı."""
    dy = y1 - y0
    if abs(dy) < 1e-6:
        return [(x0, y0), (x1, y1)]
    s = 1 if dy > 0 else -1
    if abs(dy) <= 2 * ch:
        h = abs(dy) / 2
        return [(x0, y0), (xv + h, y0), (xv - h, y1), (x1, y1)]
    return [(x0, y0), (xv + ch, y0), (xv, y0 + s * ch), (xv, y1 - s * ch), (xv - ch, y1), (x1, y1)]

def fan(lines, xs_first, step=STEP):
    """Merdiven yelpaze: lines = [(ad, (x0, y0), (x1, y1), son noktalar...)] yukarıdan aşağı sıralı, hepsi sola.
    Aşağı inenlerde alttaki, yukarı çıkanlarda üstteki önce (kaynağa yakın) döner: kesişme yok.
    Dönüş: {ad: nokta listesi}."""
    out = {}
    down = [l for l in lines if l[2][1] > l[1][1] + 1e-6]
    up = [l for l in lines if l[2][1] < l[1][1] - 1e-6]
    flat = [l for l in lines if abs(l[2][1] - l[1][1]) <= 1e-6]
    for k, l in enumerate(reversed(down)):
        out[l[0]] = stair(l[1][0], l[1][1], xs_first - k * step, l[2][1], l[2][0]) + list(l[3:])
    for k, l in enumerate(up):
        out[l[0]] = stair(l[1][0], l[1][1], xs_first - k * step, l[2][1], l[2][0]) + list(l[3:])
    for l in flat:
        out[l[0]] = [l[1], l[2]] + list(l[3:])
    return out

def hub_paths():
    """HUB75 şeridi: 33R ped 2 -> J2 -> J3 -> J4. Başlık içi geçiş: tek pin sağ sütun aralığından girip gövde
    ortasından tek pedin iç ucuna, çift pin pedin iç ucundan gövde ortasından sol aralığa (SS kartı gibi; burada
    aralıklar 1.52 mm: iki şerit). LAT2/LAT3: J2'de 13-14 ve 14-15 aralıklarının ikinci şeritlerinden, J2'nin sol
    13-15 aralığından (iki şerit) J3'e; LAT3 J3'ü aynı yoldan geçer. GND 16 başlıklara alttan (dökümden) bağlanır;
    GND 4 başlıklar arası zincir, J4'ün ötesinden J4 pin 16'ya döner. Dönüş: [(net, noktalar)]."""
    G = gc.G
    PI, PO = HUB_PI, HUB_PO
    L1, L2 = 0.885, 1.655           # 1.52 mm aralıkta iki şerit (aralık ortası 1.27)
    hubs = ['J2', 'J3', 'J4']
    X = HX
    y = lambda h, r: hub_y(h, r)
    net = lambda p: 'GND' if gc.HUB_PINS[p] == 'GND' else 'HUB_' + gc.HUB_PINS[p]
    paths = []
    ent = lambda h: X[h] + PO + 0.7          # başlığa sağdan giriş noktası x

    def odd_in(h, r, yin):                     # sağ aralıktan (yin) gövde ortasından tek pedin iç ucuna
        return [(ent(h), yin), (X[h] + PI, yin), (X[h] - PI, y(h, r)), (X[h] - PI - 0.5, y(h, r))]

    def even_in(h, r, yin):                    # sağ sütun pedinin dış ucuna
        return [(ent(h), yin), (X[h] + PO - 0.5, y(h, r))] if abs(yin - y(h, r)) > 1e-6 else \
            [(ent(h), yin), (X[h] + PO - 0.5, yin)]

    def even_out(h, r, yout):                  # çift pedin iç ucundan gövde ortasından sol aralığa (yout)
        return [(X[h] + PI + 0.5, y(h, r)), (X[h] + PI, y(h, r)), (X[h] - PI, yout)]

    # --- 1) J2'ye sağdan varış noktaları (yelpaze hedefleri) ---
    y6 = y('J2', 6)
    tgt = {}
    for p in range(1, 17):
        sig = gc.HUB_PINS[p]
        if sig in (None, 'GND'):
            continue
        r = (p - 1) // 2
        tgt[sig] = y('J2', r) - G / 2 if p % 2 else y('J2', r)
    tgt.update({'CLK': y6 - L2, 'LAT2': y6 - L1, 'LAT': y6, 'LAT3': y6 + L1, 'OE': y6 + L2})
    # --- 2) 33R ped 2 -> J2 yelpazesi (LAT2/LAT3 direnç gövdesi altındaki sol şeritten çıkar) ---
    order = ['R1', 'G1', 'B1', 'R2', 'G2', 'B2', 'ADDR_E', 'ADDR_A', 'ADDR_B', 'ADDR_C', 'ADDR_D', 'CLK', 'LAT2',
             'LAT', 'LAT3', 'OE']
    gap = lambda a, b: (ry(a) + ry(b)) / 2
    src, pre = {}, {}
    for sig in order:
        src[sig] = (RX - 1.4625, ry(sig))
    pre['LAT2'] = [(RX - 1.4625, ry('LAT2')), (RX - LANE, ry('LAT2')), (RX - LANE, gap('CLK', 'LAT'))]
    pre['LAT3'] = [(RX - 1.4625, ry('LAT3')), (RX - LANE, ry('LAT3')), (RX - LANE, gap('LAT', 'OE'))]
    src['LAT2'] = (RX - LANE, gap('CLK', 'LAT'))
    src['LAT3'] = (RX - LANE, gap('LAT', 'OE'))
    lines = [(s, src[s], (ent('J2'), tgt[s])) for s in order]
    f = fan(lines, RX - 1.4625 - 1.5)
    fanpts = {s: pre.get(s, [])[:-1] + f[s] for s in order}
    # --- 3) J2 içi ---
    c = X['J2']
    j2 = {}
    for p in range(1, 16, 2):                  # tek pinler
        r, sig = (p - 1) // 2, gc.HUB_PINS[p]
        j2[sig] = odd_in('J2', r, tgt[sig])
    for p in range(2, 17, 2):
        r, sig = (p - 1) // 2, gc.HUB_PINS[p]
        if sig not in (None, 'GND'):
            j2[sig] = even_in('J2', r, tgt[sig])
    j2['LAT'] = even_in('J2', 6, y6)
    j2['CLK'] = [(ent('J2'), y6 - L2), (c + 0.7, y6 - L2), (c - 0.705, y6 - 0.25), (c - PI - 0.5, y6 - 0.25)]
    j2['LAT2'] = [(ent('J2'), y6 - L1), (c + 1.0, y6 - L1), (c + 1.0, y6 + L1)]
    j2['LAT3'] = [(ent('J2'), y6 + L1), (c + 1.75, y6 + L1), (c + 0.98, y6 + L2)]
    j2['OE'] = [(ent('J2'), y6 + L2), (c + 1.9, y6 + L2), (c + 1.255, y6 + 2.3), (c - PI - 0.5, y6 + 2.3)]
    for sig in order:
        pts = fanpts[sig][:-1] + j2[sig]
        paths.append(('HUB_' + sig, pts))
    # --- 4) başlıklar arası + J3/J4 içi ---
    for a, b in zip(hubs, hubs[1:]):
        for p in range(1, 17):
            sig = gc.HUB_PINS[p]
            if sig is None or (p == 16):
                continue
            r = (p - 1) // 2
            n = net(p)
            if p % 2:                                           # tek: a'nın tek pedinin dış ucundan b'ye
                yin = y(a, r)
                inner = odd_in(b, r, yin)
                if sig == 'OE' and b == 'J3':                   # J3'te 15-16 aralığının alt şeridi (LAT3 üstte)
                    yb = y('J3', 6)
                    inner = [(ent(b) + 0.9, yin), (ent(b), yb + L2), (X[b] + 1.9, yb + L2),
                             (X[b] + 1.255, yb + 2.3), (X[b] - PI - 0.5, yb + 2.3)]
                paths.append((n, [(X[a] - PO + 0.5, yin)] + inner))
            else:                                               # çift: a'nın çift pedinden gövde ortasından b'ye
                yout = y(a, r) + G / 2
                if a == 'J2' and sig == 'ADDR_D':
                    yout = y6 - L2                              # J2'de 11-13 aralığının üst şeridi (CLK'ye yer)
                paths.append((n, even_out(a, r, yout) + even_in(b, r, yout)))
        # LAT hatları
        if a == 'J2':
            yl = y('J2', 6)
            paths.append(('HUB_LAT2', [(X['J2'] + 1.0, yl + L1), (X['J3'] + PO - 0.6, yl + L1)]))
            yb = y('J3', 6)
            paths.append(('HUB_LAT3', [(X['J2'] + 0.98, yl + L2), (ent('J3') + 0.9, yl + L2),
                                       (ent('J3') + 0.4, yb + L1), (X['J3'] + 1.5, yb + L1),
                                       (X['J3'] + 1.115, yb + G / 2)]))
        else:
            yb = y('J3', 6)
            paths.append(('HUB_LAT3', [(X['J3'] + 1.115, yb + G / 2), (X['J4'] + PO - 0.5, yb + G / 2)]))
    # --- 5) GND 4: zincir J4'ün ötesinden aşağı ve J4 pin 16'ya döner ---
    y4 = y('J4', 1) + G / 2
    yb = hub_y('J4', 7) + 14.08 - 3.5 * gc.G + 2.6               # J4 gövdesinin altı
    x16 = X['J4'] + PO
    y16 = y('J4', 7)
    paths.append(('GND', even_out('J4', 1, y4) + [(2.6, y4), (2.6, yb), (x16 + 1.5, yb), (x16 + 1.5, y16),
                                                  (x16 - 0.5, y16)]))
    return paths

def buffer_paths(fps):
    """Tampon B pinleri -> 33R ped 1 (merdiven), E: U3 gövdesi altından yukarı + sütunun sağ şeridi, CLK: sağ
    şerit. DevKit sol sıra -> tampon A pinleri (merdiven). +5V: jak -> PTC -> DevKit 5V, U3 ve (U3 gövdesi
    altından) U2 besleme pinleri. Dönüş: [(net, noktalar, genişlik)]."""
    out = []
    pad = lambda ref, num: gc.pad_xy(fps[ref], num)
    p1x = RX + 1.4625
    gap = lambda a, b: (ry(a) + ry(b)) / 2
    for u in ('U2', 'U3'):
        sigs = gc.BUF_CH[u]                                    # A0..A7 -> pin 2..9, B0..B7 -> pin 18..11
        lines = []
        for i, sig in enumerate(sigs):
            if sig == 'ADDR_E':
                continue
            bx, by = pad(u, str(18 - i))
            if sig == 'CLK':
                yt = gap('OE', 'LAT3')
                lines.append((sig, (bx, by), (RX + LANE, yt), (RX + LANE, ry('CLK')), (p1x, ry('CLK'))))
            else:
                lines.append((sig, (bx, by), (p1x, ry(sig))))
        lines.sort(key=lambda l: l[1][1])
        f = fan(lines, bx - 2.75)            # ilk dikey pede 1.6 mm: arada GND dökümü geçer
        for sig, pts in f.items():
            out.append((sig + '_5V', pts, W))
    # E: pin 17'nin iç ucundan U3 gövdesi altından yukarı, A ile B satırları arasından sütunun sağ şeridine
    ex, ey = pad('U3', '17')
    xe = ex + 1.85
    ye = gap('ADDR_A', 'ADDR_B')
    out.append(('ADDR_E_5V', [(ex, ey), (xe, ey), (xe, ye), (RX + LANE, ye), (RX + LANE, ry('ADDR_E')),
                              (p1x, ry('ADDR_E'))], W))
    # DevKit sol sıra -> A pinleri
    for u in ('U2', 'U3'):
        lines = []
        for i, sig in enumerate(gc.BUF_CH[u]):
            dy = pin_y(row_of(sig))
            ax, ay = pad(u, str(2 + i))
            lines.append((sig, (DK_X - 2.0, dy), (ax + 0.35, ay)))
        lines.sort(key=lambda l: l[1][1])
        f = fan(lines, DK_X - 3.4)
        for sig, pts in f.items():
            out.append((sig, pts, W))
    # pull-down'lar ve sağ sıra iç parçaları: pedin iç ucundan direnç/kondansatör ped 1'e (R6: ped 2)
    for ref, sig in gc.PULLDOWNS:
        y0 = pin_y(row_of(sig))
        px, py = pad(ref, '1')
        pts = [(DK_X + 2.0, y0), (px, py)] if abs(py - y0) < 1e-6 else \
            [(DK_X + 2.0, y0), (px, y0 + (px - DK_X - 2.0)), (px, py)]
        out.append((sig, pts, W))
    rx = DK_X + gc.DEVKIT_ROW_IN
    for ref, num, row, n in (('R7', '1', 5, 'MIC_AO'), ('C5', '1', 7, 'ENC_CLK'), ('C6', '1', 8, 'ENC_DT'),
                             ('C7', '1', 9, 'ENC_SW')):
        out.append((n, [(rx - 2.0, pin_y(row)), pad(ref, num)], W))
    # dekuplaj ve LED: +5V kısa kollar ana hatta
    xc = U_X + 1.0
    for ref in ('C3', 'C4', 'C8'):
        px, py = pad(ref, '1')
        out.append(('+5V', [(px, py), (xc, py)], 0.6))
    c2 = pad('C2', '1')
    out.append(('+5V', [c2, (pad('F1', '2')[0], c2[1])], 0.6))
    r1a, r1b, d2a = pad('R1', '1'), pad('R1', '2'), pad('D2', '2')
    out.append(('+5V', [r1a, (r1a[0], 59.0), (r1a[0] - 1.0, 58.0), (DK_X - 5.0, 58.0)], 0.4))
    out.append(('LED_PWR', [r1b, d2a], 0.4))
    # 5 V girişi (kalın): jak -> PTC -> düğüm; TVS ve 470 uF kısa; GND dönüşleri jakın gövde pedlerine
    j1a = pad('J1', '1')
    f1a, f1b = pad('F1', '1'), pad('F1', '2')
    d1k, d1a = pad('D1', '1'), pad('D1', '2')
    c1p, c1n = pad('C1', '1'), pad('C1', '2')
    jg = [(p.GetPosition().x, p.GetPosition().y) for p in fps['J1'].Pads() if p.GetNumber() == '2']
    import pcbnew
    jg = sorted((pcbnew.ToMM(x) - gc.ORIGIN[0], pcbnew.ToMM(y) - gc.ORIGIN[1]) for x, y in jg)   # sol, sağ
    out.append(('VIN', [j1a, f1a], 1.2))
    out.append(('+5V', [f1b, d1k], 1.0))
    out.append(('+5V', [f1b, c1p], 1.0))
    out.append(('GND', [d1a, (d1a[0], jg[1][1] - 5.0), (jg[1][0] + 0.6, jg[1][1] - 2.4)], 1.0))
    out.append(('GND', [c1n, (c1n[0], jg[0][1] - 5.0), (jg[0][0] - 1.4, jg[0][1] - 2.4)], 1.0))
    # +5V ana hat: F1 çıkışı -> yukarı -> DevKit 5V (sol sıra pin 21); U3 kolu: U3 gövdesi altından U2'ye
    ytr = 58.0
    u5 = pin_y(int(gc.devkit_pin('5V')))
    out.append(('+5V', [f1b, (f1b[0], ytr), (DK_X - 5.0, ytr), (DK_X - 5.0, u5), (DK_X - 2.0, u5)], 1.0))
    u3v, u3d = pad('U3', '20'), pad('U3', '1')
    u2v, u2d = pad('U2', '20'), pad('U2', '1')
    xc = U_X + 1.0
    out.append(('+5V', [(xc, ytr), (xc, u3v[1])], 0.6))
    out.append(('+5V', [(u3v[0] + 0.4, u3v[1]), (u3d[0] - 0.4, u3d[1])], 0.6))
    out.append(('+5V', [(xc, u3v[1]), (xc, u2v[1])], 0.6))
    out.append(('+5V', [(u2v[0] + 0.4, u2v[1]), (u2d[0] - 0.4, u2d[1])], 0.6))
    return out

def fan_right(lines, xs_first, step=0.6, wide=(), wide_step=1.4):
    """Sağa giden merdiven (kaynak solda), hepsi aşağı iner: alttaki önce (kaynağa yakın) döner. wide: altındaki
    hatla arasında GND dökümü geçmesi gereken hatların sırası (dikeyler arası wide_step)."""
    xs, x = {}, xs_first
    for k in range(len(lines) - 1, -1, -1):
        xs[k] = x
        x += wide_step if (k - 1) in wide else step
    return {n: [(-px, py) for px, py in stair(-a[0], a[1], -xs[k], b[1], -b[0])] for k, (n, a, b) in enumerate(lines)}

def sensor_paths(fps):
    """Sensör tarafı (tamamı sabit iz):
    - +3V3: DevKit sol sıra pin 1-2 -> üst hat (sağ sıra 1-2 aralığı) -> J10.1; DevKit altında dikey hat (V33_X),
      sağ sıranın 12-13, 17-18, 18-19 aralıklarından J7.4, J8.3, J9.2'ye.
    - IO38 (satır 10) DevKit altından yukarı, sağ sıranın 3-4 aralığından J10.5'e: tek katmanda kesişmesiz tek yol.
      Halkanın içinde kalan J5.1 ve J6.3'ün +3V3'ü JP1 (0 ohm 1206) ile IO38'in üstünden geçer.
    - GND: başlıkların sağında kenar boyunca hat, her GND pinine kısa kol (sinyaller ve 3V3 soldan).
    Dönüş: [(net, noktalar, genişlik)]."""
    out = []
    pad = lambda ref, num: gc.pad_xy(fps[ref], num)
    rx = DK_X + gc.DEVKIT_ROW_IN
    xo = rx + 2.0                              # sağ sıra pedinin dış ucu içinde
    xi = rx - 2.4                              # iç ucu içinde
    g = lambda r: (pin_y(r) + pin_y(r + 1)) / 2
    lo, hi = 0.385, 0.385                      # 1.54 mm aralıkta iki şerit
    y34a, y34b = g(3) - lo, g(3) + hi          # IO38 üstte, J5 3V3 altta
    # +3V3 kaynak ve üst hat
    out.append(('+3V3', [(DK_X + 2.0, pin_y(1)), (DK_X + 2.0, pin_y(2))], 0.4))
    out.append(('+3V3', [(DK_X + 2.0, pin_y(1)), (DK_X + 2.0 + g(1) - pin_y(1), g(1)), (xo, g(1))], 0.4))
    # DevKit altı dikey hat ve kolları
    yb = [g(12), g(17), g(18)]
    out.append(('+3V3', [(V33_X, g(1)), (V33_X, yb[-1])], 0.3))
    for y in yb:
        out.append(('+3V3', [(V33_X, y), (xo, y)], 0.25))
    # JP1: dış ped dikey hatta, iç ped halkanın içindeki dağıtıma
    j1, j2 = (JP1_POS[0] - 1.4625, JP1_POS[1]), (JP1_POS[0] + 1.4625, JP1_POS[1])
    xin = 112.6
    out.append(('+3V3', [j1, (V33_X, j1[1])], 0.3))
    out.append(('+3V3', [j2, (xin, j2[1])], 0.25))
    out.append(('+3V3', [(xin, y34b), (xin, g(6) - 0.17)], 0.25))
    for y in (y34b, g(6) - 0.17):
        out.append(('+3V3', [(xin, y), (xo, y)], 0.25))
    # IO38 halkası
    out.append(('EXP_IO38', [(xi, pin_y(10)), (IO38_X, pin_y(10)), (IO38_X, y34a), (xo, y34a)], W))
    # dış taraf: sağ sıra -> başlıklar (merdiven, sağa)
    hp = lambda ref, k: pad(ref, str(k))
    tx = SENS_X - 2.3
    sens = [('+3V3', g(1), hp('J10', 1)), ('EXP_IO43', pin_y(2), hp('J10', 3)), ('EXP_IO44', pin_y(3), hp('J10', 4)),
            ('EXP_IO38', y34a, hp('J10', 5)), ('+3V3', y34b, hp('J5', 1)), ('LDR_OUT', pin_y(4), hp('J5', 3)),
            ('MIC_DO', pin_y(6), hp('J6', 1)), ('+3V3', g(6) - 0.17, hp('J6', 3)), ('ENC_CLK', pin_y(7), hp('J7', 1)),
            ('ENC_DT', pin_y(8), hp('J7', 2)), ('ENC_SW', pin_y(9), hp('J7', 3)), ('+3V3', yb[0], hp('J7', 4)),
            ('DHT_DATA', pin_y(17), hp('J8', 2)), ('+3V3', yb[1], hp('J8', 3)), ('TOUCH_OUT', pin_y(18), hp('J9', 1)),
            ('+3V3', yb[2], hp('J9', 2))]
    lines = [('%d' % k, (xo, y), (tx, t[1])) for k, (n, y, t) in enumerate(sens)]
    # LDR-MIC, CLK-DT, DT-SW, SW-3V3 arasında döküm geçer: IO38 halkasının içindeki R7, C5-C7 GND'si buradan
    f = fan_right(lines, rx + 3.8, wide=(5, 8, 9, 10))
    for k, (n, y, t) in enumerate(sens):
        out.append((n, f['%d' % k], 0.25))
    # DevKit sağ sıra pin 1 (GND): üst hattın üstünde kalan pedi dış taraftaki döküme bağla
    out.append(('GND', [(xo, pin_y(1)), (xo + 5.0, pin_y(1))], 0.4))
    # GND hattı
    gp = [hp(r, k) for r, k in (('J10', 2), ('J5', 2), ('J6', 2), ('J7', 5), ('J8', 1), ('J9', 3))]
    out.append(('GND', [(GND_BUS_X, gp[0][1]), (GND_BUS_X, gp[-1][1])], 0.4))
    for x, y in gp:
        out.append(('GND', [(SENS_X + 2.3, y), (GND_BUS_X, y)], 0.4))
    return out

def add_fixed_tracks(board, fps, nets):
    import pcbnew
    n = 0
    for name, pts in hub_paths():
        gc.add_track(board, nets[name.lstrip('/')], pts, W, layer=pcbnew.F_Cu)
        n += len(pts) - 1
    for name, pts, w in buffer_paths(fps) + sensor_paths(fps):
        gc.add_track(board, nets[name.lstrip('/')], pts, w, layer=pcbnew.F_Cu)
        n += len(pts) - 1
    return n


# =============================================================================
#  PCB AŞAMASI
# =============================================================================
LABELS = [  # (yazı, x, y, boyut) bakırda, parça yüzünden düz okunur; çevresi yasak bölge
    ('PANEL 1', HX['J2'], 11.0, 1.6), ('PANEL 2', HX['J3'], 12.3, 1.6), ('PANEL 3', HX['J4'], 13.6, 1.6),
    ('MagPanel Carrier SMT v' + REV, 30.0, 93.0, 1.6), ('github.com/Kem4lk/magpanel', 30.0, 96.0, 1.1),
    ('+5V IN', 97.0, 93.0, 1.2),
]
DRU = """(version 1)
# gen_carrier.py --smt uretir. Tek yuz, yalniz SMD: termal kollarin bir kismi iz arasinda kalabilir.
(rule "termal_tek_kol"
  (constraint min_resolved_spokes 1))
# Yerlestirme sablonu: parca yuvalari arasinda >= 1 mm duvar (courtyard'lar arasi >= 1.0 mm)
(rule "sablon_duvari"
  (constraint courtyard_clearance (min 1.0mm)))
"""

def patch_rules():
    (gc.OUT / (gc.PROJ + '.kicad_dru')).write_text(DRU)
    pro = gc.OUT / (gc.PROJ + '.kicad_pro')
    data = json.loads(pro.read_text())
    ds = data.setdefault('board', {}).setdefault('design_settings', {})
    ds.setdefault('rules', {}).update(gc.RULES)
    ds['track_widths'] = [0.0, W, 0.4, 0.6, 1.0, 1.2]
    ds['via_dimensions'] = [{'diameter': 0.0, 'drill': 0.0}]
    sev = ds.setdefault('rule_severities', {})
    sev['lib_footprint_mismatch'] = 'ignore'       # kutuphane kopyasindan bilerek farkli (kisa ped, deliksiz jak)
    sev['lib_footprint_issues'] = 'ignore'
    sev['padstack_invalid'] = 'ignore'             # yalniz JP1: 0 ohm kopru bilerek iki parcali tek ped (KiCad 8'de
                                                   # 'jumper' ped yok); gerber'de iki ped olarak cizilir (fab denetler)
    for k in ('silk_overlap', 'silk_over_copper', 'silk_edge_clearance', 'text_height', 'text_thickness'):
        sev[k] = 'ignore'                          # serigrafi basilmiyor (ev yapimi); yerlesim haritasi ayri
    pro.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')

def features(board):
    """Bakır yazılar; yazıların ve montaj işaretlerinin çevresi yasak bölge (döküm girmez)."""
    import pcbnew
    for s, x, y, size in LABELS:
        t = gc.silk_text(board, s, x, y, size, layer=pcbnew.F_Cu, th=size * 0.16)
        gc.keepout_box(board, pcbnew.F_Cu, gc.text_box(t), 0.5)
    for ref in ('H1', 'H2', 'H3', 'H4'):
        x, y, _, _ = gc.PLACE[ref]
        gc.add_keepout(board, pcbnew.F_Cu, gc.circle_pts(x, y, 2.4, 16))


def stage_pcb():
    import pcbnew
    nl = json.loads((gc.OUT / 'netlist.json').read_text())
    knl = gc.kicad_netlist()
    for ref, p in nl.items():
        for num, net in p['pins'].items():
            kn = knl[(ref, num)][0]
            assert (gc.pcb_net(net) == kn) if net else kn.startswith('unconnected-('), (ref, num, net, kn)
    make_footprints()
    pcbnew.KIID.SeedGenerator(0x4D71)
    path = gc.OUT / (gc.PROJ + '.kicad_pcb')
    if path.exists():
        path.unlink()
    board = pcbnew.NewBoard(str(path))
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    R = gc.RULES
    ds.m_CopperEdgeClearance = gc.mm(R['min_copper_edge_clearance'])
    ds.m_TrackMinWidth = gc.mm(R['min_track_width'])
    ds.m_ViasMinSize = gc.mm(R['min_via_diameter'])
    ds.m_MinThroughDrill = gc.mm(R['min_through_hole_diameter'])
    ds.m_SolderMaskExpansion = gc.mm(0.1)          # UV maske hizalama payi
    ds.m_SolderMaskMinWidth = gc.mm(0)
    ds.SetAuxOrigin(gc.V(*gc.PLACE_ORIGIN))
    tb = board.GetTitleBlock()
    tb.SetTitle('MagPanel Carrier SMT (tek yuz, deliksiz)')
    tb.SetRevision(REV); tb.SetDate(DATE)
    tb.SetCompany('MagPanel (github.com/Kem4lk/magpanel)')
    tb.SetComment(0, 'ESP32-S3-DevKitC-1 + 2x 74HCT245 SOIC + 3x HUB75E SMD + sensorler')
    tb.SetComment(1, 'hardware/kicad/gen_carrier.py --smt ile uretildi')
    nets = {}
    for n in sorted({v[0] for v in knl.values()}):
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni
    for n in list(nets):
        nets.setdefault(n.lstrip('/'), nets[n])
    fps = {}
    for ref, p in sorted(nl.items()):
        x, y, rot, _ = gc.PLACE[ref]
        fp = gc.load_fp(p['footprint'])
        fp.SetReference(ref)
        fp.SetValue(p['value'])
        fp.SetPosition(gc.V(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH('/' + p['uuid']))
        fp.SetSheetname('/')
        fp.SetSheetfile(gc.PROJ + '.kicad_sch')
        board.Add(fp)
        for pad in fp.Pads():
            k = knl.get((ref, pad.GetNumber()))
            if k:
                pad.SetNet(nets[k[0]])
                pad.SetPinFunction(k[1])
                pad.SetPinType(k[2])
        fp.Value().SetVisible(False)
        fps[ref] = fp
    # JP1: 0 ohm 1206 köprü (şematikte yok: 'yalnız kart' parçası, şematik eşliği etkilenmez)
    fp = gc.load_fp('MagPanel:Bridge_0R_1206')
    fp.SetReference('JP1')
    fp.SetValue('0R')
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY)
    fp.SetPosition(gc.V(*JP1_POS))
    board.Add(fp)
    for pad in fp.Pads():
        pad.SetNet(nets['+3V3'])
    fp.Value().SetVisible(False)
    fps['JP1'] = fp
    gc.edge_outline(board, *SIZE)
    n = add_fixed_tracks(board, fps, nets)

    features(board)
    pcbnew.SaveBoard(str(path), board, True)
    gc.WORK.mkdir(exist_ok=True)
    shutil.copyfile(path, gc.PREROUTE)
    patch_rules()
    print('pcb: %d footprint, %d net, %d sabit iz parcasi -> %s' % (len(fps), board.GetNetCount() - 1, n, path.name))
    return board, fps

POUR_CLEARANCE = 0.4

def add_gnd_zone(board):
    """Parça yüzünde kart boyu GND dökümü (dolgu yönlendirmeden sonra)."""
    import pcbnew
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(board.FindNet('GND'))
    z.SetAssignedPriority(0)
    z.SetZoneName('GND_FCu')
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((0, 0), (SIZE[0], 0), (SIZE[0], SIZE[1]), (0, SIZE[1])):
        v = gc.V(x, y)
        ol.Append(v.x, v.y)
    z.SetLocalClearance(gc.mm(POUR_CLEARANCE))
    z.SetMinThickness(gc.mm(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(gc.mm(0.4))
    z.SetThermalReliefSpokeWidth(gc.mm(0.4))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)

def kicad_drc(out, *sev):
    gc.kcli('pcb', 'drc', '--schematic-parity', *sev, '--format', 'json', '-o', out, gc.OUT / (gc.PROJ + '.kicad_pcb'))
    return json.loads(Path(out).read_text())

def exclude_jp1():
    """JP1 (0 ohm) şematikte yok; KiCad 8 iki pedini bakırla bağlı görmez ('jumper' ped KiCad 9'da). Yalnız bu iki
    ped arasındaki eksik bağlantı projeye DRC istisnası olarak yazılır; başka her bulgu hata kalır."""
    pro = gc.OUT / (gc.PROJ + '.kicad_pro')
    data = json.loads(pro.read_text())
    data['board']['design_settings']['drc_exclusions'] = []
    pro.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    r = kicad_drc(gc.WORK / 'drc-all.json', '--severity-all')
    jp = [(round(JP1_POS[0] + s * 1.4625 + gc.ORIGIN[0], 3), round(JP1_POS[1] + gc.ORIGIN[1], 3)) for s in (-1, 1)]
    ex = []
    for u in r['unconnected_items']:
        a, b = u['items']
        at = sorted((round(i['pos']['x'], 3), round(i['pos']['y'], 3)) for i in (a, b))
        if at == jp and all('+3V3' in i['description'] for i in (a, b)):
            ex.append('unconnected_items|%d|%d|%s|%s' % (round(a['pos']['x'] * 1e6), round(a['pos']['y'] * 1e6),
                                                         a['uuid'], b['uuid']))
    if len(ex) != 1:
        raise RuntimeError('JP1 baglantisi bulunamadi: %s' % ex)
    data['board']['design_settings']['drc_exclusions'] = ex
    pro.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    r = kicad_drc(gc.WORK / 'drc-excl.json', '--severity-exclusions')
    if len(r['unconnected_items']) != 1 or r['violations']:
        raise RuntimeError('JP1 istisnasi tutmadi')

def drc_counts():
    """DRC (+ şematik eşliği), istisnalar hariç: (ihlal, bağlanmamış, şematik farkı)."""
    r = kicad_drc(gc.WORK / 'drc.json', '--severity-error', '--severity-warning')
    return tuple(len(r.get(k, [])) for k in ('violations', 'unconnected_items', 'schematic_parity'))

def stage_route():
    """Bütün izler 'pcb' aşamasında sabit: burada yalnız parça yüzü GND dökümü. Belirlenimci (her seferinde aynı
    dosya); Freerouting gerekmez. DRC/eşlik temiz olmalı."""
    import pcbnew
    path = gc.OUT / (gc.PROJ + '.kicad_pcb')
    if not gc.PREROUTE.exists():
        stage_pcb()
    shutil.copyfile(gc.PREROUTE, path)
    board = pcbnew.LoadBoard(str(path))
    pcbnew.KIID.SeedGenerator(0x4D72)
    zones = board.Zones()
    add_gnd_zone(board)
    gc.fill_zones(board, zones)
    pcbnew.SaveBoard(str(path), board, True)
    exclude_jp1()
    n = drc_counts()
    tr = list(board.GetTracks())
    back = sum(1 for t in tr if t.GetClass() == 'PCB_VIA' or t.GetLayer() != pcbnew.F_Cu)
    print('route: DRC %d ihlal, %d baglanmamis, %d sematik farki | alt katman/via %d | kopru 1 (JP1)' % (n + (back,)))
    if any(n) or back:
        raise RuntimeError('route: DRC temiz degil (work/drc.json)')

# =============================================================================
#  ÜRETİM ÇIKTILARI (fab-smt/)
# =============================================================================
COPPER_TEST = (6, 10, 200)       # Bungard pozitif lak: 200, 210 ... 250 s (kullanıcı: 230 s iyi)
COPPER_MAIN = 230
MASK_TEST = (6, 60, 60)          # UV lehim maskesi: 60, 120 ... 360 s (mürekkebe göre çok değişir)

def check_clean():
    gc.WORK.mkdir(exist_ok=True)
    gc.kcli('sch', 'erc', '--severity-all', '--format', 'json', '-o', gc.WORK / 'erc.json',
            gc.OUT / (gc.PROJ + '.kicad_sch'))
    erc = json.loads((gc.WORK / 'erc.json').read_text())
    n_erc = sum(len(sh['violations']) for sh in erc['sheets'])
    n = drc_counts()
    ex = kicad_drc(gc.WORK / 'drc-excl.json', '--severity-exclusions')
    print('ERC: %d | DRC: %d ihlal, %d baglanmamis, %d sematik farki | istisna: %d (JP1 0 ohm kopru)'
          % ((n_erc,) + n + (len(ex['unconnected_items']) + len(ex['violations']),)))
    if n_erc or any(n) or len(ex['unconnected_items']) != 1 or ex['violations']:
        raise RuntimeError('ERC/DRC temiz degil: work/erc.json, work/drc.json')

def fab_gerbers():
    """Yalnız parça (bakır) yüzü: F.Cu, F.Mask, F.Paste, Edge.Cuts (+ .gko kopyası, hizalama çerçevesi). Delik yok."""
    import re
    pcb = gc.OUT / (gc.PROJ + '.kicad_pcb')
    gd = gc.WORK / 'gerber'
    shutil.rmtree(gd, ignore_errors=True)
    gd.mkdir(parents=True)
    gc.kcli('pcb', 'export', 'gerbers', '--layers', 'F.Cu,F.Mask,F.Paste,Edge.Cuts', '--disable-aperture-macros',
            '--no-x2', '--no-netlist', '--subtract-soldermask', '--use-drill-file-origin', '-o', str(gd) + os.sep, pcb)
    for f in gd.iterdir():
        f.write_text(re.sub(r'\d{4}-\d\d-\d\d([T ])\d\d:\d\d:\d\d', lambda m: DATE + m.group(1) + '00:00:00',
                            f.read_text()))
    for f in gd.glob('*-Edge_Cuts.gm1'):
        shutil.copyfile(f, f.with_suffix('.gko'))
    gc.write_frame_gerber(gd / (gc.PROJ + '-Hizalama.gbr'))
    gc.zip_dir(gd, gc.FAB / (gc.PROJ + '-gerber.zip'))
    return gd

def fab_saturn3(gd):
    """Saturn 3 Ultra .goo: bakır (Bungard pozitif lak) ve UV lehim maskesi, ikisi de parça yüzü (F) aynalı.
    Her dosyanın ilk katmanı DIY_PLACE s yalnız çerçeve (plaket bu sürede yerleştirilir). Pozitif: kart içinde
    renkler ters (ışık alan lak çözülür). Maske: pedlerin açıklığı karanlık, kalan her yer ışıklı (UV maske ışık
    alınca sertleşir)."""
    if not gc.UVTOOLS:
        print('saturn3: UVtoolsCmd bulunamadi (UVTOOLS_CMD=...), .goo atlandi')
        return []
    from PIL import Image, ImageChops
    out = gc.FAB / 'saturn3'
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    W, H = gc.SATURN3['display_pixels_x'], gc.SATURN3['display_pixels_y']
    base = gc.WORK / 'saturn3-base.goo'
    gc.saturn3_goo(base, [Image.new('L', (W, H), 0)], gc.DIY_PLACE)
    f = lambda suffix: gd / (gc.PROJ + suffix)
    outline, frame = (f('-Edge_Cuts.gko'), True, 1), (f('-Hizalama.gbr'), False, 1)
    place = gc.pcb_exposure_image(base, [outline, frame], False, 'smt-cerceve')
    x0, y0, x1, y1 = place.getbbox()
    if abs(x0 + x1 - W) > 2 or abs(y0 + y1 - H) > 2:
        raise RuntimeError('cerceve ekranin ortasinda degil')
    gc.saturn3_goo(out / 'cerceve.goo', [place], gc.DIY_PLACE)
    gx = round(sum(gc.DIY_FRAME) * W / gc.SATURN3['display_width'])
    gy = round(sum(gc.DIY_FRAME) * H / gc.SATURN3['display_height'])
    board = (x0 + gx + 3, y0 + gy + 3, x1 - gx - 3, y1 - gy - 3)
    imgs = {}
    for name, layer in (('bakir', '-F_Cu.gtl'), ('maske', '-F_Mask.gts')):
        neg = gc.pcb_exposure_image(base, [outline, (f(layer), False, 1), frame], True, 'smt-' + name)
        pos = gc.pcb_exposure_image(base, [outline, (f(layer), False, 1), frame], True, 'smt-' + name + '-ters',
                                    invert=True)
        for im in (neg, pos):
            if ImageChops.subtract(place, im).getbbox():
                raise RuntimeError('%s: cerceve yerlestirme katmaniyla ayni yerde degil' % name)
        if ImageChops.invert(ImageChops.difference(neg, pos).crop(board)).getbbox():
            raise RuntimeError('%s: ters goruntu kart icinde tam ters degil' % name)
        imgs[name] = pos
    n, step, first = COPPER_TEST
    for t in [first + k * step for k in range(n)]:
        gc.saturn3_goo(out / ('bakir-%ds.goo' % t), [place, imgs['bakir']], t, first=gc.DIY_PLACE)
    n, step, first = MASK_TEST
    for t in [first + k * step for k in range(n)]:
        gc.saturn3_goo(out / ('maske-%ds.goo' % t), [place, imgs['maske']], t, first=gc.DIY_PLACE)
    old = gc.DIY_TEST
    try:
        gc.DIY_TEST = COPPER_TEST
        gc.saturn3_goo(out / 'bakir-pozlama-testi.goo', gc.exposure_test_layers(True), COPPER_TEST[1],
                       first=gc.DIY_PLACE)
        gc.DIY_TEST = MASK_TEST
        gc.saturn3_goo(out / 'maske-pozlama-testi.goo', gc.exposure_test_layers(True), MASK_TEST[1],
                       first=gc.DIY_PLACE)
    finally:
        gc.DIY_TEST = old
    for name, im in imgs.items():                     # önizleme (ekranda nasıl yanacağı, kart bölgesi)
        im.crop((x0, y0, x1, y1)).resize(((x1 - x0) // 4, (y1 - y0) // 4)).save(gc.WORK / ('onizleme-%s.png' % name))
    return sorted(p.name for p in out.iterdir())

# --- Reçine stencil ve yerleştirme şablonu (STL). Koordinat: X = kart x, Y = kart y (aşağı), Z = kullanımdaki üst
#     yüzden derinlik. Bu, parçanın X ekseni etrafında 180 derece çevrilmiş hâli (ayna değil): STL'deki Z = 0 yüzü
#     baskı tablasına gelir (düz, sıyırma yüzü), çerçeve dudağı yukarı büyür. Basınca ters çevirip karta oturt.
STENCIL_T = float(os.environ.get('SMT_STENCIL_T', 0.2))    # macun plakası kalınlığı (mm)
APERTURE_GROW = float(os.environ.get('SMT_APERTURE', 0.0))  # macun açıklığı büyütme (+) / küçültme (-), kenar başına
FIT = 0.15            # dudak ile kart kenarı arası boşluk
FRAME = 5.0           # kartın dışındaki çerçeve genişliği
LIP = 1.2             # stencil dudağı: kart kenarını saran, aşağı inen kısım (kart 1.6 mm, masaya değmez)
JIG_T, JIG_GAP, JIG_LIP = 1.5, 0.15, 1.0   # şablon: plaka kalınlığı, karttan yükseklik (ayaklar), dudak
ENGRAVE = 0.4         # oyma yazı derinliği

def _poly_pts(chain):
    import numpy as np
    from pcbnew import ToMM
    pts = np.array([(ToMM(chain.CPoint(k).x) - gc.ORIGIN[0], ToMM(chain.CPoint(k).y) - gc.ORIGIN[1])
                    for k in range(chain.PointCount())], dtype=float)
    a = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    return pts, a

def polyset_cs(ps):
    """KiCad SHAPE_POLY_SET -> manifold CrossSection (dış hatlar + delikler)."""
    from manifold3d import CrossSection, FillRule
    contours = []
    for i in range(ps.OutlineCount()):
        pts, a = _poly_pts(ps.Outline(i))
        contours.append(pts if a > 0 else pts[::-1])
        for h in range(ps.HoleCount(i)):
            hp, ha = _poly_pts(ps.Hole(i, h))
            contours.append(hp if ha < 0 else hp[::-1])
    return CrossSection(contours, FillRule.NonZero) if contours else CrossSection()

def rect_cs(x0, y0, x1, y1):
    from manifold3d import CrossSection
    return CrossSection([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]])

def outline_cs(grow):
    from manifold3d import CrossSection, JoinType
    w, h = SIZE
    r = 2.0
    return CrossSection.square((w - 2 * r, h - 2 * r)).translate((r, r)).offset(r + grow, JoinType.Round,
                                                                             circular_segments=48)

def text_cs(board, s, x, y, size, angle=0, th=None):
    """Yazı -> CrossSection, (x, y) ortada, büyük harf yüksekliği ~size mm. KiCad 8 Python'unda yazıyı çokgene
    çeviren çağrılar açık değil (ERROR_LOC): DejaVu ile 40 px/mm çizilip satır satır dikdörtgenlere çevrilir
    (25 um basamak, yazıcı pikseli ~20 um)."""
    from PIL import Image, ImageDraw
    k = 40.0
    font = gc.ui_font(int(round(size * k * 1.35)), bold=True)
    tmp = ImageDraw.Draw(Image.new('L', (1, 1)))
    l, t, r, b = tmp.textbbox((0, 0), s, font=font)
    im = Image.new('L', (r - l + 4, b - t + 4), 0)
    ImageDraw.Draw(im).text((2 - l, 2 - t), s, font=font, fill=255)
    W, H = im.size
    px = im.load()
    rects, open_ = [], {}
    for yy in range(H + 1):
        runs, xx = set(), 0
        while yy < H and xx < W:
            if px[xx, yy] > 127:
                x0 = xx
                while xx < W and px[xx, yy] > 127:
                    xx += 1
                runs.add((x0, xx))
            xx += 1
        for run in list(open_):
            if run not in runs:
                rects.append((run[0], open_.pop(run), run[1], yy))
        for run in runs:
            open_.setdefault(run, yy)
    from manifold3d import CrossSection
    if not rects:
        return CrossSection()
    cx, cy = W / 2, H / 2
    cs = CrossSection([[((a - cx) / k + x, (c - cy) / k + y), ((b2 - cx) / k + x, (c - cy) / k + y),
                        ((b2 - cx) / k + x, (d - cy) / k + y), ((a - cx) / k + x, (d - cy) / k + y)]
                       for a, c, b2, d in rects])
    return cs

def pad_cs(pad, layer, grow=0.0):
    import pcbnew
    ps = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(ps, layer, gc.mm(grow) if grow > 0 else 0, gc.mm(0.005))
    cs = polyset_cs(ps)
    if grow < 0:
        from manifold3d import JoinType
        cs = cs.offset(grow, JoinType.Miter)
    return cs

def courtyard_box(fp):
    import pcbnew
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.F_CrtYd:
            bb = g.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    return (min(xs) - gc.ORIGIN[0], min(ys) - gc.ORIGIN[1], max(xs) - gc.ORIGIN[0], max(ys) - gc.ORIGIN[1])

def slab(cs, z0, z1):
    """CrossSection'ı Z = z0..z1 arasında katı yap."""
    from manifold3d import Manifold
    if cs.is_empty():
        return Manifold()
    return Manifold.extrude(cs, z1 - z0).translate((0, 0, z0))

def write_stl(m, path):
    """İkili STL (sabit başlık: aynı model -> aynı dosya)."""
    import numpy as np
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    t = np.asarray(mesh.tri_verts, dtype=np.int64)
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(t), dtype=[('n', '<f4', 3), ('a', '<f4', 3), ('b', '<f4', 3), ('c', '<f4', 3),
                                  ('x', '<u2')])
    rec['n'], rec['a'], rec['b'], rec['c'] = n, a, b, c
    with open(path, 'wb') as f:
        f.write(b'MagPanel Carrier SMT (gen_carrier.py --smt)'.ljust(80, b' '))
        f.write(np.uint32(len(t)).tobytes())
        f.write(rec.tobytes())
    return len(t)

JIG_EXCLUDE = ('U1', 'J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8', 'J9', 'J10')   # sonra takılan büyük parçalar
CODE = {'33R': '330', '10k': '103', '2.2k': '222', '100nF': '100n', '10uF': '10µ', '0R': '0R'}

def jig_label(fp):
    v = fp.GetValue()
    ref = fp.GetReference()
    if ref.startswith('U'):
        return '245'
    if ref == 'D1':
        return 'TVS'
    if ref == 'D2':
        return 'LED'
    if ref == 'F1':
        return 'PTC'
    if ref == 'C1':
        return '470µ'
    return CODE.get(v, v)

def fab_stl(board):
    """Macun stencil'i, yerleştirme şablonu ve SOIC/1206 deneme stencil'i (STL)."""
    import pcbnew
    from manifold3d import CrossSection, JoinType
    out = gc.FAB / 'stencil'
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    paste = [pad_cs(p, pcbnew.F_Paste, APERTURE_GROW) for fp in fps.values() for p in fp.Pads()
             if p.IsOnLayer(pcbnew.F_Paste)]
    paste_u = CrossSection.batch_boolean(paste, pcbnew_op_add())
    res = {}
    # ---------- 1) macun stencil'i ----------
    plate = outline_cs(FRAME)
    ring = outline_cs(FRAME) - outline_cs(FIT)
    w, h = SIZE
    txt = (text_cs(board, 'MagPanel SMT macun v%s - BU YÜZ ÜSTTE' % REV, w / 2, -FRAME / 2, 2.0) +
           text_cs(board, 'DC JAK BU KENARDA', w / 2, h + FRAME / 2, 2.0))
    m = (slab(plate - paste_u, 0, STENCIL_T) + slab(ring, STENCIL_T, STENCIL_T + LIP)) - \
        slab(txt, 0, ENGRAVE)
    res['macun-stencil.stl'] = write_stl(m, out / 'macun-stencil.stl')
    # ---------- 2) yerleştirme şablonu ----------
    pockets, opens = [], []
    for ref, fp in sorted(fps.items()):
        if not fp.Pads() or ref.startswith('H'):
            continue
        x0, y0, x1, y1 = courtyard_box(fp)
        if ref in JIG_EXCLUDE:                            # sonra takılır: yalnız pedlerin çevresi açık (macuna değmesin)
            opens += [pad_cs(p, pcbnew.F_Cu, 0.8) for p in fp.Pads()]
            continue
        pk = rect_cs(x0, y0, x1, y1)
        if ref == 'C1':                                   # kutuplu: gövdenin pahlı köşeleri yuvada da var
            pk = fab_outline_cs(fp).offset(0.3, JoinType.Miter)
            for p in fp.Pads():
                pk = pk + pad_cs(p, pcbnew.F_Cu, 0.3)
        pockets.append((ref, fp, pk, (x0, y0, x1, y1)))
    holes = CrossSection.batch_boolean([pk for _, _, pk, _ in pockets] + opens, pcbnew_op_add())
    # her macun açıklığı bir yuvanın içinde olmalı (şablon macuna değmez)
    if not (paste_u - holes).is_empty():
        raise RuntimeError('sablon: bazi macun aciklilari yuva disinda')
    # yazılar: yuvanın yanında, yuvalara ve öteki yazılara değmeyen ilk yer (gerekirse küçük harf)
    taken = holes.offset(0.4, JoinType.Miter)
    inside = outline_cs(-1.0)
    jt = []

    def put(s, bounds, near=None):
        nonlocal taken
        x0, y0, x1, y1 = bounds
        for size in (1.3, 1.1, 0.9):
            t0 = text_cs(board, s, 0, 0, size)
            bx0, by0, bx1, by1 = t0.bounds()
            hw, hh = (bx1 - bx0) / 2, (by1 - by0) / 2
            cx, cy = near if near else ((x0 + x1) / 2, (y0 + y1) / 2)
            g = 0.9
            cands = [(x0 - g - hw, cy), (x1 + g + hw, cy), (cx, y0 - g - hh), (cx, y1 + g + hh),
                     (x0 - g - hw, y0 - g - hh), (x1 + g + hw, y0 - g - hh), (x0 - g - hw, y1 + g + hh),
                     (x1 + g + hw, y1 + g + hh)]
            if near:
                cands.sort(key=lambda q: (q[0] - near[0]) ** 2 + (q[1] - near[1]) ** 2)
            for tx, ty in cands:
                t = t0.translate((tx, ty))
                box = t.offset(0.3, JoinType.Miter)
                if (box ^ taken).is_empty() and (box - inside).is_empty():
                    taken = taken + box
                    jt.append(t)
                    return
        t = text_cs(board, s, 0, 0, 0.9)
        bx0, by0, bx1, by1 = t.bounds()
        t = t.translate(((x0 + x1) / 2, y0 - 0.9 - (by1 - by0) / 2)).offset(0.3, JoinType.Miter)
        raise RuntimeError('sablon: "%s" yazisina yer yok (%s; ust aday cakisma %s, bound %s)'
                           % (s, bounds, (t ^ taken).bounds(), t.bounds()))

    for ref, fp, pk, bb in pockets:
        put(jig_label(fp), pk.bounds())
        if ref.startswith('U'):                           # kutup işaretleri
            put('1', pk.bounds(), pad_center(fp, '1'))
        elif ref in ('D1', 'D2'):
            put('K', pk.bounds(), pad_center(fp, '1'))
        elif ref == 'C1':
            put('+', pk.bounds(), pad_center(fp, '1'))
    jt.append(text_cs(board, 'MagPanel SMT yerleştirme v%s - BU YÜZ ÜSTTE' % REV, w / 2, -FRAME / 2, 2.0))
    jt.append(text_cs(board, 'DC JAK BU KENARDA', w / 2, h + FRAME / 2, 2.0))
    jtxt = CrossSection.batch_boolean(jt, pcbnew_op_add())
    # ayaklar: montaj işaretlerinin üstü (bakır halka, macun yok) + boş yerler
    cand = [gc.PLACE[r][:2] for r in ('H1', 'H2', 'H3', 'H4')] + [
        (25.0, 70.0), (55.0, 85.0), (110.0, 85.0), (130.0, 90.0), (50.0, 2.5), (30.0, 3.0), (100.0, 62.0),
        (75.0, 3.0), (52.0, 50.0), (130.0, 45.0)]
    block = holes.offset(0.8, JoinType.Miter)
    feet_xy = [(x, y) for x, y in cand if (rect_cs(x - 1.5, y - 1.5, x + 1.5, y + 1.5) ^ block).is_empty()]
    if len(feet_xy) < 8:
        raise RuntimeError('sablon: yeterli ayak yeri yok: %s' % feet_xy)
    feet = CrossSection.batch_boolean([rect_cs(x - 1.5, y - 1.5, x + 1.5, y + 1.5) for x, y in feet_xy],
                                      pcbnew_op_add())
    jring = outline_cs(FRAME) - outline_cs(0.2)
    m = (slab(outline_cs(FRAME) - holes, 0, JIG_T) + slab(feet - holes, JIG_T, JIG_T + JIG_GAP) +
         slab(jring, JIG_T, JIG_T + JIG_GAP + JIG_LIP)) - slab(jtxt, 0, ENGRAVE)
    res['yerlestirme-sablonu.stl'] = write_stl(m, out / 'yerlestirme-sablonu.stl')
    # ---------- 3) deneme: U2 + 4 direncin açıklıkları, 36 x 26 mm ----------
    refs = ['U2', 'R10', 'R11', 'R12', 'R13']
    ux, uy = gc.PLACE['U2'][:2]
    parts = []
    for k, ref in enumerate(refs):
        for p in fps[ref].Pads():
            if p.IsOnLayer(pcbnew.F_Paste):
                c = pad_cs(p, pcbnew.F_Paste, APERTURE_GROW)
                if ref == 'U2':
                    c = c.translate((-ux + 10.0, -uy + 13.0))
                else:
                    rx_, ry_ = gc.PLACE[ref][:2]
                    c = c.translate((-rx_ + 26.0, -ry_ + 5.0 + (k - 1) * 5.0))
                parts.append(c)
    ap = CrossSection.batch_boolean(parts, pcbnew_op_add())
    body = rect_cs(0, 0, 34, 26)
    rim = body - rect_cs(1.5, 1.5, 32.5, 24.5)
    m = (slab(body - ap, 0, STENCIL_T) + slab(rim, STENCIL_T, STENCIL_T + 1.0)) - \
        slab(text_cs(board, 'TEST %.2f' % STENCIL_T, 26.0, 23.0, 1.6).translate((0, 0)), 0, 0.1)
    res['deneme-soic-1206.stl'] = write_stl(m, out / 'deneme-soic-1206.stl')
    return res

def pcbnew_op_add():
    from manifold3d import OpType
    return OpType.Add

def pad_center(fp, num):
    return gc.pad_xy(fp, num)

def fab_outline_cs(fp):
    """F.Fab çizgilerinden gövde dış hattı (CP_Elec: pahlı kare) -> kapalı çokgen (dışbükey zarf)."""
    import pcbnew
    from manifold3d import CrossSection
    pts = []
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.F_Fab and g.GetClass() == 'PCB_SHAPE' and g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            for q in (g.GetStart(), g.GetEnd()):
                pts.append((pcbnew.ToMM(q.x) - gc.ORIGIN[0], pcbnew.ToMM(q.y) - gc.ORIGIN[1]))
    return CrossSection.hull_points(pts)

# --- Renkli SMD yerleşim haritası ve BOM ---
KIND_COL = {   # tür -> (gövde rengi, yazı rengi, ad)
    'R': ((74, 144, 217), (255, 255, 255), 'direnç'),
    'C': ((240, 160, 60), (0, 0, 0), 'seramik kondansatör (kodsuz)'),
    'CP': ((128, 88, 170), (255, 255, 255), 'elektrolitik (kutuplu)'),
    'LED': ((60, 175, 75), (255, 255, 255), 'LED (kutuplu)'),
    'D': ((150, 60, 150), (255, 255, 255), 'TVS diyot (kutuplu)'),
    'F': ((240, 200, 30), (0, 0, 0), 'PTC sigorta'),
    'U': ((60, 60, 60), (255, 255, 255), '74HCT245 (pin 1 noktası)'),
    'JP': ((25, 25, 25), (255, 255, 255), '0 Ω köprü'),
    'J': ((205, 205, 205), (0, 0, 0), 'konnektör (şablondan sonra)'),
}

SENS_NAMES = {}      # J5..J10 -> pin adları (render_map doldurur)

def part_kind(ref):
    if ref == 'C1':
        return 'CP'
    if ref == 'D2':
        return 'LED'
    if ref == 'JP1':
        return 'JP'
    for k in ('LED', 'JP', 'R', 'C', 'D', 'F', 'U', 'J'):
        if ref.startswith(k):
            return k
    return 'J'

def part_code(fp):
    ref, v = fp.GetReference(), fp.GetValue()
    return {'U1': 'ESP32-S3', 'J1': 'DC 5V'}.get(ref) or ({'J2': 'PANEL 1', 'J3': 'PANEL 2', 'J4': 'PANEL 3'}.get(ref)) \
        or (v if ref.startswith('J') else jig_label(fp))

def fab_box(fp, layer=None):
    import pcbnew
    layer = pcbnew.F_Fab if layer is None else layer
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer and g.GetClass() == 'PCB_SHAPE':
            bb = g.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    if not xs:
        return None
    return (min(xs) - gc.ORIGIN[0], min(ys) - gc.ORIGIN[1], max(xs) - gc.ORIGIN[0], max(ys) - gc.ORIGIN[1])

def render_map(board, s, region=None, labels=True):
    """Parça yüzünden bakış (kart nasıl görünüyorsa). s: px/mm."""
    import pcbnew
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = region or (0, 0) + SIZE
    W, H = int((x1 - x0) * s) + 1, int((y1 - y0) * s) + 1
    im = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    P = lambda x, y: ((x - x0) * s, (y - y0) * s)
    mmxy = lambda v: (pcbnew.ToMM(v.x) - gc.ORIGIN[0], pcbnew.ToMM(v.y) - gc.ORIGIN[1])
    d.rounded_rectangle([P(0, 0), P(*SIZE)], radius=2 * s, fill=(232, 240, 228), outline=(60, 90, 60), width=max(1, int(0.3 * s)))
    for t in board.GetTracks():                      # izler soluk: yön bulmak için
        if t.GetClass() == 'PCB_TRACK' and t.GetLayer() == pcbnew.F_Cu:
            d.line([P(*mmxy(t.GetStart())), P(*mmxy(t.GetEnd()))], fill=(196, 214, 192),
                   width=max(1, int(pcbnew.ToMM(t.GetWidth()) * s)))
    SENS_NAMES.update({ref: [l for l, _ in pins] for ref, _, pins, _ in gc.SENSOR_HDRS})
    fps = sorted(board.GetFootprints(), key=lambda f: f.GetReference())
    for fp in fps:                                    # pedler
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.F_Cu):
                for poly in pad_cs(p, pcbnew.F_Cu).to_polygons():
                    d.polygon([P(x, y) for x, y in poly], fill=(214, 178, 96))
    big = []
    for fp in fps:
        ref = fp.GetReference()
        if ref.startswith('H'):
            x, y = gc.PLACE[ref][:2]
            d.ellipse([P(x - 1.6, y - 1.6), P(x + 1.6, y + 1.6)], outline=(150, 150, 150), width=max(1, int(0.2 * s)))
            continue
        k = part_kind(ref)
        col, tcol, _ = KIND_COL[k]
        if ref == 'U1':                               # DevKit: modülün dış hattı kesikli, soketler gri
            bx = fab_box(fp)
            for i in range(int(bx[0]), int(bx[2]), 3):
                d.line([P(i, bx[1]), P(min(i + 1.5, bx[2]), bx[1])], fill=(120, 120, 120), width=max(1, int(0.25 * s)))
                d.line([P(i, bx[3]), P(min(i + 1.5, bx[2]), bx[3])], fill=(120, 120, 120), width=max(1, int(0.25 * s)))
            for j in range(int(bx[1]), int(bx[3]), 3):
                d.line([P(bx[0], j), P(bx[0], min(j + 1.5, bx[3]))], fill=(120, 120, 120), width=max(1, int(0.25 * s)))
                d.line([P(bx[2], j), P(bx[2], min(j + 1.5, bx[3]))], fill=(120, 120, 120), width=max(1, int(0.25 * s)))
            for xr in [DK_X] + gc.DEVKIT_RIGHT_ROWS:
                xr = xr if xr == DK_X else DK_X + xr
                d.rectangle([P(xr - 1.27, gc.PIN1Y - 1.27), P(xr + 1.27, pin_y(22) + 1.27)], outline=(90, 90, 90),
                            width=max(1, int(0.25 * s)))
                d.rectangle([P(xr - 1.27, gc.PIN1Y - 1.27), P(xr - 0.3, gc.PIN1Y - 0.3)], fill=(200, 30, 30))
            big.append((fp, bx))
            continue
        bx = fab_box(fp) or courtyard_box(fp)
        if k == 'J':
            d.rectangle([P(bx[0], bx[1]), P(bx[2], bx[3])], outline=(90, 90, 90), width=max(1, int(0.25 * s)))
            big.append((fp, bx))
        else:
            d.rectangle([P(bx[0], bx[1]), P(bx[2], bx[3])], fill=col, outline=(30, 30, 30), width=max(1, int(0.12 * s)))
        # kutup işaretleri
        if k in ('LED', 'D'):
            kx, ky = gc.pad_xy(fp, '1')
            cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
            if abs(kx - cx) > abs(ky - cy):              # yatay: katot çizgisi dikey
                xb = bx[0] + 0.25 * (bx[2] - bx[0]) if kx < cx else bx[2] - 0.25 * (bx[2] - bx[0])
                d.line([P(xb, bx[1]), P(xb, bx[3])], fill=(255, 255, 255), width=max(2, int(0.35 * s)))
            else:
                yb = bx[1] + 0.25 * (bx[3] - bx[1]) if ky < cy else bx[3] - 0.25 * (bx[3] - bx[1])
                d.line([P(bx[0], yb), P(bx[2], yb)], fill=(255, 255, 255), width=max(2, int(0.35 * s)))
        if k == 'CP':                                     # eksi tarafı koyu bant, artı tarafı '+'
            nx = gc.pad_xy(fp, '2')[0]
            xb = (bx[0], bx[0] + 0.22 * (bx[2] - bx[0])) if nx < (bx[0] + bx[2]) / 2 else \
                (bx[2] - 0.22 * (bx[2] - bx[0]), bx[2])
            d.rectangle([P(xb[0], bx[1]), P(xb[1], bx[3])], fill=(40, 20, 60))
        if k == 'U':
            px_, py_ = gc.pad_xy(fp, '1')
            cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
            dx, dy = (1 if px_ > cx else -1), (1 if py_ > cy else -1)
            r = 0.6
            d.ellipse([P(cx + dx * (cx - bx[0] - 1.2) - r, cy + dy * (cy - bx[1] - 1.2) - r),
                       P(cx + dx * (cx - bx[0] - 1.2) + r, cy + dy * (cy - bx[1] - 1.2) + r)], fill=(255, 255, 255))
    # konnektör ayrıntıları: pin 1 üçgeni, kutu başlık çentiği
    for fp, bx in big:
        ref = fp.GetReference()
        if ref == 'U1':
            continue
        px_, py_ = gc.pad_xy(fp, '1')
        tri = [(px_ - 0.9, py_ - 0.9), (px_ + 0.9, py_), (px_ - 0.9, py_ + 0.9)]
        if ref in ('J2', 'J3', 'J4'):
            xn = bx[0]
            cy = (bx[1] + bx[3]) / 2
            d.rectangle([P(xn - 0.4, cy - 2.0), P(xn + 1.2, cy + 2.0)], fill=(200, 30, 30))      # çentik (sol)
            tri = [(px_ - 3.0, py_ - 0.9), (px_ - 1.5, py_), (px_ - 3.0, py_ + 0.9)]
        if ref != 'J1':
            d.polygon([P(x, y) for x, y in tri], fill=(200, 30, 30))
    if labels:
        for fp in fps:
            ref = fp.GetReference()
            if ref.startswith('H'):
                continue
            k = part_kind(ref)
            bx = fab_box(fp) or courtyard_box(fp)
            code = part_code(fp)
            col, tcol, _ = KIND_COL[k]
            w_, h_ = (bx[2] - bx[0]) * s, (bx[3] - bx[1]) * s
            cx, cy = P((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
            if ref == 'U1':
                fnt = gc.ui_font(int(2.4 * s), bold=True)
                d.text((cx, P(0, 30)[1]), 'ESP32-S3 DevKit\n(sokete takılır)', font=fnt, fill=(110, 110, 110),
                       anchor='mm', align='center')
                continue
            vert = h_ > w_ * 1.3
            fsize = max(8, int(min(min(w_, h_) * 0.62, (max(w_, h_) * 0.9) / max(2.2, len(code) * 0.62))))
            if k == 'J':
                fsize = max(8, int(1.6 * s))
            fnt = gc.ui_font(fsize, bold=True)
            if vert and k != 'J':
                tmp = Image.new('RGBA', (int(h_) + 4, int(w_) + 4), (0, 0, 0, 0))
                ImageDraw.Draw(tmp).text((tmp.size[0] / 2, tmp.size[1] / 2), code, font=fnt, fill=tcol + (255,),
                                         anchor='mm')
                tmp = tmp.rotate(90, expand=True)
                im.paste(tmp, (int(cx - tmp.size[0] / 2), int(cy - tmp.size[1] / 2)), tmp)
            elif k == 'J' and ref in SENS_NAMES:              # sensör: ad üstte, pin adları sağda
                d.text((cx, P(0, bx[1])[1] - 1.2 * s), code, font=fnt, fill=(70, 70, 70), anchor='md')
                fp_ = gc.ui_font(max(7, int(0.95 * s)), bold=True)
                for num, lbl in enumerate(SENS_NAMES[ref], 1):
                    px_, py_ = gc.pad_xy(fp, str(num))
                    d.text((P(px_ + 3.2, 0)[0], P(0, py_)[1]), lbl, font=fp_, fill=(40, 40, 40), anchor='lm')
                continue
            elif k == 'J':
                d.text((cx, cy), code, font=fnt, fill=(70, 70, 70), anchor='mm')
            else:
                d.text((cx, cy), code, font=fnt, fill=tcol, anchor='mm')
            # ref: gövdenin hemen üstü / solu, küçük
            fr = gc.ui_font(max(7, int(0.75 * s)))
            if k == 'J':
                d.text((cx, P(0, bx[1])[1] - 0.2 * s), ref, font=fr, fill=(60, 60, 60), anchor='md')
            elif ref.startswith('R') and abs(gc.PLACE.get(ref, (0,))[0] - RX) < 0.01:
                d.text((P(bx[2], 0)[0] + 0.3 * s, cy), ref, font=fr, fill=(60, 60, 60), anchor='lm')
            else:
                d.text((cx, P(0, bx[1])[1] - 0.15 * s), ref, font=fr, fill=(60, 60, 60), anchor='md')
    return im

def legend_lines():
    return [('R', 'Direnç (1206, %5): kod 330 = 33 Ω, 103 = 10 kΩ, 222 = 2,2 kΩ.'),
            ('R', '  %1 direnç alırsan kod 4 hanelidir: 33R0, 1002, 2201.'),
            ('C', 'Seramik kondansatörde yazı yok: 100n ve 10µ karışmasın, ayrı tut.'),
            ('CP', 'Elektrolitik: koyu bant/çizgi = eksi. Gövdenin pahlı köşeleri artı tarafta.'),
            ('LED', "LED: beyaz çizgi = katot (K). LED'in kendi işareti üreticiye göre değişir: ölçü aletinin diyot kademesiyle dene."),
            ('D', 'TVS: beyaz çizgi = katot, diyotun üstündeki gri bantla aynı taraf.'),
            ('U', '74HCT245: beyaz nokta = pin 1 (çipteki nokta/çentik).'),
            ('JP', '0 Ω köprü (JP1): yönsüz.'),
            ('J', 'Kırmızı üçgen = pin 1. Kutu başlıkta kırmızı = çentik (sol).'),
            ('F', 'PTC sigorta: yönsüz.')]

def fab_map(board):
    """A4 PDF: sayfa 1 kartın tamamı 1:1 (yatay), sayfa 2-3 sol / sağ yarı 2 kat (dikey). PNG: img/smt-yerlesim.png."""
    import time
    from PIL import Image, ImageDraw
    dpi = 300
    k = dpi / 25.4
    pages = []
    # sayfa 1
    pg = Image.new('RGB', (round(297 * k), round(210 * k)), (255, 255, 255))
    d = ImageDraw.Draw(pg)
    m = render_map(board, k)
    pg.paste(m, (round(10 * k), round(24 * k)))
    d.text((round(10 * k), round(8 * k)), 'MagPanel Carrier SMT v%s - parça yerleşimi (parça yüzü, 1:1)' % REV,
           font=gc.ui_font(round(4.5 * k), bold=True), fill=(0, 0, 0))
    d.text((round(10 * k), round(15 * k)), 'Yazdırırken ölçek %100. Altta 100 mm çizgi: cetvelle doğrula.',
           font=gc.ui_font(round(2.8 * k)), fill=(60, 60, 60))
    yb = round((24 + SIZE[1] + 7) * k)
    d.line((round(10 * k), yb, round(110 * k), yb), fill=(0, 0, 0), width=round(0.3 * k))
    for i in range(11):
        hh = (3 if i % 5 == 0 else 1.8) * k
        d.line((round((10 + 10 * i) * k), yb - hh, round((10 + 10 * i) * k), yb), fill=(0, 0, 0), width=round(0.3 * k))
    lx, ly = round(166 * k), round(26 * k)
    d.text((lx, ly - round(2 * k)), 'Renkler ve işaretler', font=gc.ui_font(round(3.4 * k), bold=True), fill=(0, 0, 0))
    fl = gc.ui_font(round(2.4 * k))
    y = ly + round(4 * k)
    for kk, txt in legend_lines():
        col = KIND_COL[kk][0]
        if not txt.startswith('  '):
            d.rectangle((lx, y + round(0.3 * k), lx + round(5 * k), y + round(3.0 * k)), fill=col, outline=(30, 30, 30))
        for line in wrap(txt.strip(), 52):
            d.text((lx + round(7 * k), y), line, font=fl, fill=(0, 0, 0))
            y += round(3.6 * k)
        y += round(1.0 * k)
    y += round(2 * k)
    for line in ['Sıra: macun stencil -> şablonu oturt, küçük parçalar', '(değer yazısına bak) -> şablonu dik kaldır ->',
                 'büyük parçalar (kutu başlık, soketler, DC jak, pin',
                 'başlıklar) -> ısıtıcı tabla. Ayrıntı: SMT.md']:
        d.text((lx, y), line, font=fl, fill=(0, 0, 0))
        y += round(3.6 * k)
    pages.append(pg)
    # sayfa 2-3: yarılar 2 kat
    for name, reg in (('SOL YARI', (0, 0, 78, SIZE[1])), ('SAĞ YARI', (72, 0, SIZE[0], SIZE[1]))):
        pg = Image.new('RGB', (round(210 * k), round(297 * k)), (255, 255, 255))
        d = ImageDraw.Draw(pg)
        m = render_map(board, 2 * k, reg)
        pg.paste(m, (round(12 * k), round(24 * k)))
        d.text((round(12 * k), round(8 * k)), 'MagPanel Carrier SMT v%s - %s, 2 kat büyük' % (REV, name),
               font=gc.ui_font(round(4.2 * k), bold=True), fill=(0, 0, 0))
        d.text((round(12 * k), round(15 * k)), 'x = %d ... %d mm (sol üst köşe 0, 0). Ölçek dışı.' % reg[::2],
               font=gc.ui_font(round(2.8 * k)), fill=(60, 60, 60))
        y = round((24 + 2 * SIZE[1] + 8) * k)
        for kk, txt in legend_lines():
            if txt.startswith('  '):
                continue
            d.rectangle((round(12 * k), y + round(0.3 * k), round(16 * k), y + round(2.6 * k)), fill=KIND_COL[kk][0],
                        outline=(30, 30, 30))
            d.text((round(18 * k), y), txt, font=gc.ui_font(round(2.3 * k)), fill=(0, 0, 0))
            y += round(3.4 * k)
        pages.append(pg)
    when = time.strptime(DATE, '%Y-%m-%d')
    out = gc.FAB / (gc.PROJ + '-yerlesim.pdf')
    pages[0].save(out, 'PDF', resolution=dpi, save_all=True, append_images=pages[1:], title='MagPanel SMT yerlesim',
                  creationDate=when, modDate=when)
    gc.IMG.mkdir(exist_ok=True)
    png = render_map(board, 14)
    png.quantize(colors=128, method=Image.Quantize.FASTOCTREE).save(gc.IMG / 'smt-yerlesim.png', optimize=True)
    return out.name

def wrap(txt, n):
    out, cur = [], ''
    for w_ in txt.split():
        if len(cur) + len(w_) + 1 > n:
            out.append(cur)
            cur = w_
        else:
            cur = (cur + ' ' + w_).strip()
    return out + [cur]

def fab_bom(board):
    """BOM (csv + xlsx): kart başına adet, kılıf, üstündeki kod, Komponentci'de aranacak ad."""
    import csv
    import xlsx
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    groups = collections.OrderedDict()
    def add(key, ref, n=1):
        g = groups.setdefault(key, [[], 0])
        g[0].append(ref)
        g[1] += n
    order = lambda r: (r.rstrip('0123456789'), int(''.join(c for c in r if c.isdigit()) or 0))
    for ref in sorted(fps, key=order):
        v = fps[ref].GetValue()
        if ref.startswith('H'):
            continue
        if ref == 'U1':
            add('DEVSOCK', ref, 2); add('DEVKIT', ref)
        elif ref.startswith('U'):
            add('245', ref)
        elif ref == 'JP1':
            add('0R', ref)
        elif ref.startswith('R'):
            add(v, ref)
        elif ref == 'C1':
            add('C470', ref)
        elif ref.startswith('C'):
            add(v, ref)
        elif ref == 'D1':
            add('TVS', ref)
        elif ref == 'D2':
            add('LED', ref)
        elif ref == 'F1':
            add('PTC', ref)
        elif ref == 'J1':
            add('JACK', ref)
        elif ref in ('J2', 'J3', 'J4'):
            add('IDC', ref)
        else:
            add('H%d' % len([p for p in fps[ref].Pads() if p.GetNumber()]), ref)
    head = ['No', 'Parça', 'Kılıf', 'Adet', 'Referans', 'Üstündeki kod', "Komponentci'de ara", 'Not']
    rows = []
    for i, (key, (refs, n)) in enumerate(groups.items(), 1):
        desc, pkg, code, search, note = PARTS[key]
        rows.append([i, desc, pkg, n, ' '.join(refs), code, search, note])
    with open(gc.FAB / (gc.PROJ + '-bom.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    xlsx.write(gc.FAB / (gc.PROJ + '-bom.xlsx'), [head] + rows, widths=[5, 44, 22, 6, 30, 16, 34, 48],
               sheet='BOM', plain=True)
    return len(rows)

def stage_fab():
    import pcbnew
    check_clean()
    board = pcbnew.LoadBoard(str(gc.OUT / (gc.PROJ + '.kicad_pcb')))
    gc.FAB.mkdir(exist_ok=True)
    gd = fab_gerbers()
    print('gerber: %s/%s-gerber.zip (F.Cu, F.Mask, F.Paste, kenar, hizalama; delik yok)' % (gc.FAB.name, gc.PROJ))
    goo = fab_saturn3(gd)
    print('saturn3: %d dosya -> %s/saturn3/' % (len(goo), gc.FAB.name))
    for name, n in fab_stl(board).items():
        print('stl: %s/stencil/%s (%d ucgen)' % (gc.FAB.name, name, n))
    print('harita:', fab_map(board), '+ img/smt-yerlesim.png')
    print('bom: %d satir -> %s/%s-bom.csv, .xlsx' % (fab_bom(board), gc.FAB.name, gc.PROJ))
