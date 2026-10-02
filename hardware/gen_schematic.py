#!/usr/bin/env python3
"""
MagPanel baglanti semasi ureticisi (parametrik, sadece stdlib).
  python3 hardware/gen_schematic.py            -> hardware/schematic.svg
  PNG onizleme: bkz. hardware/README.md ("Yeniden uretmek").

Tasarim yaklasimi enclosure/generate_case.py ile ayni: tum olculer/pinler bastaki
sozluklerde; sema koddan uretilir, elle cizilmez. Pin atamalari include/sensors.h ve
include/app_constants.hpp ile BIREBIR ayni olmali (README'deki tablo da buradan gelir).

Duzen: solda HUB75E konektoru + 5 V guc, ortada ESP32-S3-DevKitC-1 (iki baslik), sagda
bes sensor. HUB75 tarafinda her sinyal ESP'nin SOL basligina, sensorler ESP'nin SAG
basligina duser -> kablolar carpismaz. Sensor hatlari kanal yontemiyle (en uzun yol
ESP'ye en yakin kanal) yonlendirilir; crossings() carpisma olursa uyari basar.
"""
import os, sys

# ============================ PIN / NET TANIMLARI ============================
# ESP32-S3-DevKitC-1 baslik sirasi (USB alta bakarken, yukaridan asagi)
LEFT_HDR  = ["3V3","3V3","RST","4","5","6","7","15","16","17","18","8","3","46","9","10","11","12","13","14","5V","GND"]
RIGHT_HDR = ["GND","TX","RX","1","2","42","41","40","39","38","37","36","35","0","45","48","47","21","20","19","GND","GND"]

# HUB75E (app_constants.hpp): sinyal -> (GPIO, HUB75 pin no)
HUB75 = [  # (ad, gpio, hub75 pin, renk, istege bagli aciklama)
  ("R1", "4",  1,  "#d33",    None),
  ("G1", "5",  2,  "#2a9d3a", None),
  ("B1", "6",  3,  "#2b6fd6", None),
  ("R2", "7",  5,  "#d33",    None),
  ("G2", "15", 6,  "#2a9d3a", None),
  ("B2", "16", 7,  "#2b6fd6", None),
  ("LAT2","17",14, "#8a5a00", "P1.86 2. modul (pin 14)"),
  ("A",  "18", 9,  "#444",    None),
  ("B",  "8",  10, "#444",    None),
  ("C",  "3",  11, "#444",    None),
  ("GND","-",  4,  "#000",    "pin 4, 16"),        # ESP'ye kablo yok: toprak sembolu
  ("D",  "9",  12, "#444",    None),
  ("LAT", "10",14, "#8a5a00", None),
  ("OE",  "11",15, "#8a5a00", "GCLK (P4) / OE (P1.86)"),
  ("CLK", "12",13, "#8a5a00", "DCLK"),
  ("E",   "13", 8, "#444",    None),
  ("LAT3","14",14, "#8a5a00", "P1.86 3. modul (pin 14)"),
]

# Sensorler (include/sensors.h): kutu adi, model, pin listesi (ad, tip, gpio|None, not)
#   tip: "sig" (ESP'ye kablo), "vcc" (3V3 bayragi), "gnd" (toprak), "opt" (kesikli, istege bagli)
SENSORS = [
  ("U2", "LDR Sensor Board (JSUMO 16067)", [
      ("VCC", "vcc", None, None),
      ("GND", "gnd", None, None),
      ("DO",  "sig", "1",  "dijital cikis, ADC1 ile okunur")],
   "LDR panelin kendi isigini GORMEMELI (oto-parlaklik salinir):\nust kenarda one/yukari bakan 3-4 mm delik, isik siperi."),
  ("U3", "Microphone Sound Sensor (JSUMO 15771)", [
      ("OUT", "sig", "42", "dijital cikis, kesme ile sayilir"),
      ("GND", "gnd", None, None),
      ("VCC", "vcc", None, None)],
   "Kart potansiyometresi + web'deki 'Alkis esigi' birlikte ayarlanir;\nkasada 2-3 mm ses deligi yeterli."),
  ("U4", "Mechanic Encoder Module KY-040 (JSUMO)", [
      ("CLK", "sig", "41", "A fazi (kart ustu 10 k pull-up)"),
      ("DT",  "sig", "40", "B fazi"),
      ("SW",  "sig", "39", "buton, aktif DUSUK (dahili pull-up)"),
      ("+",   "vcc", None, None),
      ("GND", "gnd", None, None)],
   "Titreme icin CLK/DT/SW - GND arasina 100 nF onerilir\n(yazilim tablosu zaten toleransli). Mil kasa yan duvarindan disari."),
  ("U5", "DHT11 Temperature & Humidity Board (JSUMO 15579)", [
      ("-",    "gnd", None, None),
      ("OUT",  "sig", "47", "kart ustu 10 k pull-up"),
      ("+",    "vcc", None, None)],
   "Kasa ICINE koyma (LED isisi olcumu bozar): ust kenardaki\nhavalandirma yuvasina, dis havada."),
  ("U6", "TTP223B Digital Touch Sensor (JSUMO 17538)", [
      ("SIG", "sig", "21", "aktif YUKSEK; dahili pull-down"),
      ("VCC", "vcc", None, None),
      ("GND", "gnd", None, None)],
   "Ped kasa duvarinin IC yuzune yapistirilir (<= 3 mm plastikten\nalgilar): on yuz temiz kalir, gorunur dugme yok."),
]

# Kullanilmayan / ozel pin notlari (gri)
PIN_NOTES = {
  "TX":"UART0 (43)", "RX":"UART0 (44)", "38":"bos (v1.1 RGB LED)", "37":"OPI PSRAM - kullanma",
  "36":"OPI PSRAM - kullanma", "35":"OPI PSRAM - kullanma", "0":"BOOT / strapping",
  "45":"strapping - kullanma", "46":"strapping - kullanma", "48":"bos (v1.0 RGB LED)",
  "20":"USB D+", "19":"USB D-", "RST":"reset", "GND":"", "3V3":"", "5V":"",
}

# ================================ GEOMETRI ==================================
W, H = 1700, 1190
PITCH = 26
ESP_X0, ESP_X1, ESP_Y0 = 640, 940, 200          # ESP kutusu
STUB = 40                                        # pin cubugu uzunlugu
HUB_X0, HUB_X1 = 330, 470                        # HUB75 sembolu
SENS_X0, SENS_X1, SENS_Y0 = 1290, 1560, 118      # sensor kutulari
CHAN_X0, CHAN_DX = 1130, 16                      # sensor kanal baslangici / araligi (ESP pin notlarindan sonra)
FONT = "DejaVu Sans Mono, Menlo, Consolas, monospace"
SANS = "DejaVu Sans, Helvetica, Arial, sans-serif"

out = []
def esc(t): return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def text(x, y, s, size=12, anchor="start", color="#111", weight="normal", family=FONT, extra=""):
    out.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" text-anchor="{anchor}" '
               f'fill="{color}" font-weight="{weight}" {extra}>{esc(s)}</text>')
def line(x1, y1, x2, y2, color="#222", w=1.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}" stroke-linecap="round"{d}/>')
def rect(x, y, w, h, fill="#fff", stroke="#222", sw=1.6, rx=4):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
def wire(pts, color="#222", w=1.8, dash=None):
    for (x1,y1),(x2,y2) in zip(pts, pts[1:]): line(x1,y1,x2,y2,color,w,dash)
def dot(x, y, color="#222", r=3.2):
    out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')
def gnd(x, y, color="#000"):        # toprak sembolu (asagi bakar)
    line(x, y, x, y+10, color, 1.6)
    line(x-9, y+10, x+9, y+10, color, 1.8); line(x-6, y+14, x+6, y+14, color, 1.8); line(x-3, y+18, x+3, y+18, color, 1.8)
def vcc(x, y, label="3V3", color="#c1121f"):   # guc bayragi (yukari bakar)
    line(x, y, x, y-12, color, 1.6)
    out.append(f'<polygon points="{x-6},{y-12} {x+6},{y-12} {x},{y-20}" fill="{color}"/>')
    text(x, y-24, label, 11, "middle", color, "bold")

def row_y(i): return ESP_Y0 + i*PITCH + PITCH//2

# ================================= CIZIM ====================================
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
out.append(f'<rect width="{W}" height="{H}" fill="#fbfaf6"/>')
out.append(f'<rect x="20" y="20" width="{W-40}" height="{H-40}" fill="none" stroke="#333" stroke-width="2"/>')
text(W//2, 52, "MagPanel — bağlantı şeması: ESP32-S3-DevKitC-1 + HUB75E LED panel + sensörler", 22, "middle", "#111", "bold", SANS)
text(W//2, 74, "P4 80×120 (3× FM6363C 80×40) ya da P1.86 172×86 (SM16380SH, 1–3 modül) — aynı kablolama; sensör pinleri include/sensors.h", 12, "middle", "#555", family=SANS)

# ---- ESP32-S3 kutusu ----
esp_h = len(LEFT_HDR)*PITCH
rect(ESP_X0, ESP_Y0, ESP_X1-ESP_X0, esp_h, "#f2f5fb", "#1d3557", 2.2, 8)
text((ESP_X0+ESP_X1)//2, ESP_Y0-22, "U1  ESP32-S3-DevKitC-1 (N8R8: 8 MB OPI PSRAM, 16 MB flash)", 13, "middle", "#1d3557", "bold", SANS)
text((ESP_X0+ESP_X1)//2, ESP_Y0-6, "USB-C aşağıda; J1 sol / J3 sağ başlık, üstten alta", 11, "middle", "#555", family=SANS)
used_left  = {g for _,g,_,_,_ in HUB75}
used_right = {p[2] for _,_,pins,_ in SENSORS for p in pins if p[2]}
for i, name in enumerate(LEFT_HDR):
    y = row_y(i)
    line(ESP_X0-STUB, y, ESP_X0, y, "#1d3557", 1.6)
    text(ESP_X0+8, y+4, name, 12, "start", "#1d3557" if name in used_left or name in ("3V3","5V","GND") else "#8a8f98", "bold")
    if name not in used_left and name not in ("46",) and PIN_NOTES.get(name) and name not in ("3V3","5V","GND","RST"):
        text(ESP_X0-STUB-6, y+4, PIN_NOTES[name], 10, "end", "#9aa0a8")
for i, name in enumerate(RIGHT_HDR):
    y = row_y(i)
    line(ESP_X1, y, ESP_X1+STUB, y, "#1d3557", 1.6)
    text(ESP_X1-8, y+4, name, 12, "end", "#1d3557" if name in used_right or name in ("GND",) else "#8a8f98", "bold")
    if name not in used_right and PIN_NOTES.get(name):
        text(ESP_X1+STUB+6, y+4, PIN_NOTES[name], 10, "start", "#9aa0a8")
# ESP guc sembolleri: 3V3 (sol ust 2 pin), GND'ler
vcc(ESP_X0-STUB, row_y(0)); vcc(ESP_X0-STUB, row_y(1))
text(ESP_X0-STUB-14, row_y(0)+4, "3V3 → sensörler (≤ 500 mA)", 9.5, "end", "#c1121f", family=SANS)
gnd(ESP_X1+STUB, row_y(0)); gnd(ESP_X1+STUB, row_y(20)); gnd(ESP_X1+STUB, row_y(21))
line(ESP_X1+STUB, row_y(20), ESP_X1+STUB, row_y(21), "#000", 1.6)
text((ESP_X0+ESP_X1)//2, ESP_Y0+esp_h+16, "USB-C (programlama/seri) — 5 V PSU takılıyken de bağlanabilir (kart üstünde diyot)", 10, "middle", "#666", family=SANS)

# ---- HUB75E konektor sembolu (J2): satirlar ESP sol basligiyla AYNI y -> duz kablolar ----
hub_rows = {}   # gpio -> satir indeksi
for i, name in enumerate(LEFT_HDR): hub_rows[name] = i
first_i = hub_rows["4"]; last_i = hub_rows["14"]
hy0 = row_y(first_i) - PITCH//2; hy1 = row_y(last_i) + PITCH//2
rect(HUB_X0, hy0, HUB_X1-HUB_X0, hy1-hy0, "#f7f3ea", "#5c4a1e", 2, 8)
text((HUB_X0+HUB_X1)//2, hy0-24, "J2  HUB75E (IDC 2×8, panel girişi)", 13, "middle", "#5c4a1e", "bold", SANS)
text((HUB_X0+HUB_X1)//2, hy0-8, "sembol sırası = ESP başlığı; fiziksel pinout sol üstte", 10, "middle", "#666", family=SANS)
hub_slot = {"4":0,"5":1,"6":2,"7":3,"15":4,"16":5,"17":6,"18":7,"8":8,"3":9,"46":10,"9":11,"10":12,"11":13,"12":14,"13":15,"14":16}
for (nm, gpio, pin, col, note) in HUB75:
    if gpio == "-":
        i = hub_rows["46"]          # bos ESP satirina denk gelen yer: GND
        y = row_y(i)
        text(HUB_X0+10, y+4, f"GND  (pin 4,16)", 12, "start", "#000", "bold")
        line(HUB_X1, y, HUB_X1+22, y, "#000", 1.6); gnd(HUB_X1+22, y)
        continue
    i = hub_rows[gpio]; y = row_y(i)
    opt = nm in ("LAT2","LAT3")
    text(HUB_X0+10, y+4, f"{nm:<4} pin {pin}", 12, "start", col if not opt else "#8a5a00", "bold")
    # konektor cubugu + ESP'ye duz kablo
    dash = "6,5" if opt else None
    line(HUB_X1, y, ESP_X0-STUB, y, col, 1.8, dash)
    text((HUB_X1+ESP_X0-STUB)//2, y-4, f"GPIO{gpio}" + (" *" if opt else ""), 10, "middle", col)
    # (OE = P4'te GCLK, P1.86'da OE; CLK = DCLK -> README'de)

# ---- HUB75E fiziksel pinout (inset, sol ust) ----
ix, iy = 40, 90
rect(ix, iy, 240, 160, "#fff", "#5c4a1e", 1.4, 6)
text(ix+120, iy+18, "HUB75E dişi konektör (panel IN), üstten", 10, "middle", "#5c4a1e", "bold", SANS)
phys = [("R1",1,"G1",2),("B1",3,"GND",4),("R2",5,"G2",6),("B2",7,"E",8),("A",9,"B",10),("C",11,"D",12),("CLK",13,"LAT",14),("OE",15,"GND",16)]
for r,(a,pa,b,pb) in enumerate(phys):
    yy = iy+36+r*15
    text(ix+70, yy, f"{a:>3} {pa:>2}", 11, "end", "#222")
    out.append(f'<rect x="{ix+86}" y="{yy-9}" width="10" height="10" fill="#ddd" stroke="#555" stroke-width="0.8"/>')
    out.append(f'<rect x="{ix+104}" y="{yy-9}" width="10" height="10" fill="#ddd" stroke="#555" stroke-width="0.8"/>')
    text(ix+130, yy, f"{pb:<2} {b}", 11, "start", "#222")
text(ix+120, iy+152, "pin 1 = çentik yanı (kabloda kırmızı damar)", 9, "middle", "#666", family=SANS)

# ---- 5 V guc: PSU + panel guc konektoru + ESP 5V ----
px, py = 60, 800
rect(px, py, 200, 90, "#fff3f3", "#c1121f", 2, 8)
text(px+100, py+22, "PSU  5 V DC", 14, "middle", "#c1121f", "bold", SANS)
text(px+100, py+40, "≥ 20 A (tepe, tam beyaz)", 10.5, "middle", "#c1121f", family=SANS)
text(px+100, py+56, "tipik yük 3–6 A", 10.5, "middle", "#666", family=SANS)
text(px+100, py+74, "220 V girişi izole/topraklı", 9.5, "middle", "#666", family=SANS)
yp, yg = py+28, py+62
line(px+200, yp, px+220, yp, "#c1121f", 3); text(px+226, yp+4, "+", 13, "start", "#c1121f", "bold")
line(px+200, yg, px+220, yg, "#000", 3);    text(px+226, yg+4, "−", 13, "start", "#000", "bold")
# panel guc konektoru J4
jx = 380
rect(jx, py, 190, 90, "#fff", "#c1121f", 1.6, 6)
text(jx+95, py+20, "J4  panel güç (VH3.96 ×3)", 11, "middle", "#c1121f", "bold", SANS)
text(jx+95, py+36, "her modüle VCC + GND", 10, "middle", "#666", family=SANS)
text(jx+95, py+52, "kalın kablo ≥ 1.5 mm², kısa", 10, "middle", "#666", family=SANS)
text(jx+95, py+68, "P4: ~30 W/modül tepe  P1.86: ~31 W", 9.5, "middle", "#666", family=SANS)
wire([(px+240, yp), (jx, yp)], "#c1121f", 3.2)
wire([(px+240, yg), (jx, yg)], "#000", 3.2)
# ESP 5V / GND (sol baslik alt) beslemesi: dallar
y5v, ygnd = row_y(hub_rows["5V"]), row_y(hub_rows["GND"])
bx1, bx2 = 300, 322
dot(bx1, yp, "#c1121f", 4); wire([(bx1, yp), (bx1, y5v), (ESP_X0-STUB, y5v)], "#c1121f", 2.2)
dot(bx2, yg, "#000", 4);    wire([(bx2, yg), (bx2, ygnd), (ESP_X0-STUB, ygnd)], "#000", 2.2)
text((bx2+ESP_X0-STUB)//2, y5v-5, "5V (VIN) — kart regülatörü 3V3 üretir", 10, "middle", "#c1121f")
text((bx2+ESP_X0-STUB)//2, ygnd+14, "ORTAK GND: PSU − = panel GND = ESP GND (zorunlu)", 10, "middle", "#000", "bold")

# ---- Sensorler (sag) ----
right_rows = {}
for i, name in enumerate(RIGHT_HDR): right_rows.setdefault(name, i)
nets = []   # (gpio, x_sens_pin, y_sens_pin, color, dash)
y = SENS_Y0
for (ref, title, pins, note) in SENSORS:
    h = len(pins)*PITCH + 6
    rect(SENS_X0, y, SENS_X1-SENS_X0, h, "#eef8f0", "#1b5e20", 2, 8)
    text(SENS_X0+10, y-6, f"{ref}  {title}", 11.5, "start", "#1b5e20", "bold", SANS)
    for k, (pn, kind, gpio, pnote) in enumerate(pins):
        yy = y + 3 + k*PITCH + PITCH//2
        line(SENS_X0-STUB, yy, SENS_X0, yy, "#1b5e20", 1.6)
        text(SENS_X0+10, yy+4, pn, 12, "start", "#1b5e20", "bold")
        if pnote: text(SENS_X0+58, yy+4, pnote, 9.5, "start", "#555")
        # guc pinleri yatay net etiketi: modul pin sirasi ne olursa olsun komsu sinyal hatlarina degmez
        if kind == "vcc": text(SENS_X0-STUB-4, yy+4, "3V3", 11, "end", "#c1121f", "bold")
        elif kind == "gnd": text(SENS_X0-STUB-4, yy+4, "GND", 11, "end", "#000", "bold")
        else:
            nets.append((gpio, SENS_X0-STUB, yy, "#1b5e20" if kind=="sig" else "#6b8f71", None if kind=="sig" else "6,5"))
    for li, ln in enumerate(note.split("\n")):
        text(SENS_X0+10, y+h+13+li*13, ln, 9.5, "start", "#4a6b4f", family=SANS)
    y += h + 58
# Kanal atamasi (carpismasiz): yukari giden hatlarda EN USTTEKI ESP pini ESP'ye en yakin
# kanali alir, asagi gidenlerde EN ALTTAKI. Iki grup y'de kesismez -> ayni x'leri paylasir.
def esp_y(g): return row_y(right_rows[g])
up   = sorted([n for n in nets if n[2] <  esp_y(n[0])], key=lambda n:  esp_y(n[0]))
down = sorted([n for n in nets if n[2] >= esp_y(n[0])], key=lambda n: -esp_y(n[0]))
chan = {}
for grp in (up, down):
    for k, n in enumerate(grp): chan[n[0]] = CHAN_X0 + k*CHAN_DX
segs = []
for (gpio, xs, ys, col, dash) in nets:
    ye = esp_y(gpio); xc = chan[gpio]
    pts = [(ESP_X1+STUB, ye), (xc, ye), (xc, ys), (xs, ys)]
    wire(pts, col, 1.8, dash)
    segs.append((gpio, pts))
    text(xc+4 if ys < ye else xc+4, (ys+ye)//2 + 4, f"G{gpio}", 9.5, "start", col)
# carpisma kontrolu (yatay-dikey kesisim, farkli netler)
def crossings():
    n = 0
    hs, vs = [], []
    for g, pts in segs:
        for (x1,y1),(x2,y2) in zip(pts, pts[1:]):
            if y1 == y2: hs.append((g, min(x1,x2), max(x1,x2), y1))
            else: vs.append((g, x1, min(y1,y2), max(y1,y2)))
    for (g1,xa,xb,yh) in hs:
        for (g2,xv,ya,yb) in vs:
            if g1 != g2 and xa < xv < xb and ya < yh < yb: n += 1; print(f"UYARI: {g1} yatay x {g2} dikey kesisiyor", file=sys.stderr)
    return n

# ---- Notlar ----
nx, ny = 40, 905
rect(nx, ny, W-80, 180, "#fff", "#333", 1.4, 6)
text(nx+12, ny+20, "NOTLAR", 12, "start", "#111", "bold", SANS)
NOTES = [
 "1. Tüm sensörler ESP'nin 3V3 pininden beslenir. ESP32-S3 GPIO'ları 5 V toleranslı DEĞİLDİR; sensörleri 5 V'a bağlama.",
 "2. LDR kartı (16067) yalnız dijital: DO → GPIO1 (ADC1) analog okunur, 0/%100 → oto parlaklık iki kademe. ADC2 WiFi'de kullanılamaz.",
 "3. Ortak toprak zorunlu: PSU −, panel GND ve ESP GND aynı düğüm. Panel güç kablosu kalın ve kısa; HUB75 şeridinde ≥ 2 GND.",
 "4. DHT11 kartında 10 kΩ pull-up var; çıplak sensörde DATA–3V3 arasına 4.7–10 kΩ ekle. Okuma 3 sn'de bir, firmware kütüphanesiz.",
 "5. TTP223B: A/B pedleri boş → anlık mod, aktif YÜKSEK. Ped kasa duvarının iç yüzüne yapıştırılırsa ≤ 3 mm plastikten algılar.",
 "6. KY-040: CLK/DT kart üstünde 10 kΩ pull-up; SW için ESP dahili pull-up. Yön ters gelirse web'den 'Enkoder ters' ya da CLK↔DT.",
 "7. LDR panel ışığını görmemeli (oto-parlaklık geri besleme → salınım); mikrofon ve LDR için ön/üst kenarda küçük delik.",
 "8. Mikrofon kartı (15771) 3 pinli, yalnız dijital: OUT → GPIO42. GPIO2 (analog mikrofon girişi) boşta: 10 kΩ ile GND'ye çek.",
 "9. GPIO 33–37 OPI PSRAM, 19/20 USB, 0/45/46 strapping, 43/44 UART0: sensör için kullanma. 38/48 = bazı kartlarda RGB LED.",
 "10. Boş bırakılan sensör zararsızdır: dokunmatik pull-down, enkoder pull-up, DHT 'yok' gösterir; oto-parlaklık ve alkış varsayılan kapalı.",
 "11. Güç: P4 modül tepe ~30 W (tam beyaz, parlaklık 255) → 3 modül ≤ 90 W; P1.86 ≈ 31 W/modül. Firmware varsayılanı (110/255) bunu ~yarıya indirir.",
 "12. LAT2/LAT3 (kesikli): yalnız çoklu P1.86 — 2./3. modülün HUB75 pin 14'ü. R/G/B, CLK, OE, A–E tüm modüllere paralel; tek P4/P1.86'da boş.",
 "13. Modül pin sırası (eldeki kartların yazısı): KY-040 CLK·DT·SW·+·GND | TTP223B SIG·VCC·GND | DHT11 −·OUT·+ | LDR VCC·GND·DO | Mikrofon OUT·GND·VCC.",
]
for r, s in enumerate(NOTES):
    col, row = (0, r) if r < 7 else (1, r-7)
    text(nx+12 + col*800, ny+40+row*19, s, 9.6, "start", "#222", family=SANS)

# ---- Baslik blogu ----
tx, ty = 1230, 1098
rect(tx, ty, 430, 66, "#fff", "#333", 1.6, 4)
text(tx+10, ty+20, "MagPanel — bağlantı şeması", 13, "start", "#111", "bold", SANS)
text(tx+10, ty+38, "Rev 1 · 2026-09-29 · hardware/gen_schematic.py ile üretildi", 10, "start", "#555", family=SANS)
text(tx+10, ty+52, "Kaynak: include/sensors.h, include/app_constants.hpp, include/panel_sm16380.h", 9, "start", "#777", family=SANS)
# lejant
lx, ly = 60, 1112
text(lx, ly, "Lejant:", 11, "start", "#333", "bold", SANS)
line(lx+60, ly-4, lx+100, ly-4, "#1b5e20", 1.8); text(lx+106, ly, "sinyal", 10, "start", "#333", family=SANS)
line(lx+160, ly-4, lx+200, ly-4, "#6b8f71", 1.8, "6,5"); text(lx+206, ly, "isteğe bağlı", 10, "start", "#333", family=SANS)
line(lx+300, ly-4, lx+340, ly-4, "#c1121f", 3.2); text(lx+346, ly, "5 V güç", 10, "start", "#333", family=SANS)
vcc(lx+430, ly+2); text(lx+444, ly, "3V3 bayrağı", 10, "start", "#333", family=SANS)
gnd(lx+540, ly-10); text(lx+556, ly, "toprak", 10, "start", "#333", family=SANS)
text(lx, ly+22, "HUB75 renkleri: kırmızı/yeşil/mavi = R/G/B verisi, kahverengi = saat/latch/OE, gri = satır adresi A–E. Sensör pinleri: include/sensors.h (−D ile değiştirilebilir).", 10, "start", "#555", family=SANS)

out.append("</svg>")
n = crossings()
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schematic.svg")
open(path, "w", encoding="utf-8").write("\n".join(out))
print(f"yazildi: {path} ({len(out)} eleman, {n} kesisim)")
