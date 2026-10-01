# MagPanel Carrier — KiCad 8 şematik + PCB

ESP32-S3-DevKitC-1'i soketle taşıyan, üç HUB75E çıkışı (P4 tek panel ya da P1.86 1–3 modül)
ve beş JSUMO sensör başlığı olan iki katmanlı taşıyıcı kart. Kasa (`enclosure/generate_case.py`)
ve bağlantı şeması (`hardware/gen_schematic.py`) gibi her şey **koddan üretilir**:
[`gen_carrier.py`](gen_carrier.py). Pin, parça ya da yerleşim değişirse dosyanın başındaki
tabloları düzelt ve yeniden üret. KiCad'de elle yapılan değişiklik bir sonraki üretimde kaybolur.

![Kart üst yüz](img/pcb-top.png)

| | |
|---|---|
| Kart | 100 × 63.5 mm, 2 katman, 1.6 mm FR4, köşelerde 4× M3 |
| İz genişliği | sinyal 0.25 mm, 3V3 0.5 mm, 5 V / VIN 0.8–1.0 mm |
| Kurallar | boşluk ≥ 0.15 mm, via 0.6/0.3 mm, kenar 0.3 mm (JLCPCB standart 2 katman) |
| GND | iki katmanda döküm + dikiş via'ları |
| Doğrulama | ERC 0, DRC 0 ihlal, 0 bağlanmamış, şematik↔PCB farkı 0 |

Doğrulama satırı `fab` aşamasında her seferinde yeniden kontrol edilir. Biri sıfır değilse
gerber üretilmez.

## Dosyalar
| Yol | İçerik |
|---|---|
| `magpanel-carrier/` | KiCad 8 projesi: `.kicad_pro`, `.kicad_sch`, `.kicad_pcb`, `.kicad_dru` |
| `magpanel-carrier/MagPanel.kicad_sym`, `MagPanel.pretty/` | DevKit sembolü ve soket footprint'i |
| `fab/magpanel-carrier-gerber.zip` | gerber + delik dosyaları (doğrudan yüklenir) |
| `fab/magpanel-carrier-bom.csv` | tam malzeme listesi |
| `fab/magpanel-carrier-jlc-bom.csv`, `fab/magpanel-carrier-jlc-cpl.csv` | JLCPCB SMT montajı (yalnız SMD) |
| `fab/magpanel-carrier-schematic.pdf` | şematik (A3) |
| `img/` | şematik ve kart görselleri |

Şematik: [`img/schematic.png`](img/schematic.png) · Alt yüz: [`img/pcb-bottom.png`](img/pcb-bottom.png)

## Devre
1. **5 V giriş ve koruma.** Vida klemensi J1, 1.5 A PTC sigorta F1 ve SMAJ5.0A TVS D1'den
   geçer. Ters kutupta D1 iletir ve F1 açar. Ardından 470 µF + 10 µF ile DevKit'in **5V**
   pinine ve tamponlara gider. Panel gücü bu karttan geçmez: PSU'dan panele kalın kablo.
   Kartın kendi tüketimi 1 A'in altındadır.
2. **DevKit soketi U1.** İki adet 1×22 dişi soket. Sağ sıra iki konumludur: 0.9" (22.86 mm,
   resmi Espressif) ve 1.0" (25.40 mm, yaygın N16R8 klonları). Kartına uyan sıraya soket
   lehimle, diğeri boş kalır; iki sıra aynı netlere bağlıdır. Anten kartın üst kenarından
   dışarı taşar, USB alt kenardadır.
3. **Seviye dönüştürücü.** İki 74AHCT245, 3.3 V mantığı 5 V'a çevirir (DIR = 5 V, /OE = GND).
   Kanal sırası DevKit sol başlığının pin sırasını izler, böylece izler kesişmez.
   LAT, LAT2, LAT3 ve OE'de 10 kΩ pull-down var: açılışta GPIO'lar sürülmezken panel karanlık
   kalır. P4'te OE hattı GCLK taşır, P1.86'da aktif-yüksek OE darbesi.
4. **HUB75E çıkışları J2–J4.** 4×33 Ω seri direnç dizileri (RN1–RN4) kablo yansımalarını
   bastırır. Bütün hatlar paraleldir, yalnız LAT panel başına ayrıdır:

   | Konnektör | LAT | Kullanım |
   |---|---|---|
   | J2 PANEL 1 | IO10 | P4 ve P1.86 |
   | J3 PANEL 2 | IO17 | yalnız çoklu P1.86 |
   | J4 PANEL 3 | IO14 | yalnız çoklu P1.86 |

5. **Sensör başlıkları (3.3 V).** J5 LDR, J6 MIC, J7 ENC, J8 DHT, J9 TOUCH ve J10 genişleme
   (IO43, IO44, IO38). Pinler `include/sensors.h` ile aynıdır ve her pin serigrafide yazılıdır.
   C5–C7 enkoder için RC filtre, R6 DHT11 veri hattı pull-up'ıdır.

GPIO tablosu ve modül notları: [`../README.md`](../README.md).

## Yeniden üretmek
Gerekenler: KiCad 8 (`pcbnew` python modülü ve `kicad-cli`), Java 21+ (Freerouting için),
görseller için Chromium ya da Chrome (`CHROME=/yol` ile verilebilir).

```bash
cd hardware/kicad
PY=/usr/bin/python3        # Linux: KiCad'in python'u
# macOS: PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$PY gen_carrier.py sch     # şematik + proje + semboller (yalnız stdlib)
$PY gen_carrier.py pcb     # yerleşim, kart çerçevesi, kilitli 5 V ana hat, SMD GND via'ları
$PY gen_carrier.py route   # Freerouting 2.1.0 + GND dökümü + dikiş via'ları
$PY gen_carrier.py fab     # ERC/DRC kapısı + gerber/delik/BOM/CPL/PDF + görseller
$PY gen_carrier.py all     # hepsi sırayla
```

- `route` Freerouting jar'ını yoksa `work/` altına indirir (yaklaşık 67 MB).
- Freerouting deterministik değildir: her çalıştırma farklı ama eşdeğer bir yönlendirme
  verir. Aşama, DRC temiz çıkana kadar en çok 10 kez dener.
- `work/` ara dosyalar içindir ve git'e girmez.

## Sipariş ve montaj
- **PCB:** `fab/magpanel-carrier-gerber.zip` yükle. 2 katman, 1.6 mm, HASL ya da ENIG.
- **SMT montaj (isteğe bağlı):** `jlc-bom` ve `jlc-cpl` dosyaları. LCSC numaraları boştur,
  sipariş ekranında değer ve MPN'e göre eşleştir. Önizlemede U2/U3 (SOIC-20W), D1, D2 ve
  dizi dirençlerin dönüşünü kontrol et; JLC kütüphanesi bazen 90° ya da 180° farklıdır.
- **Elle lehim:** 0805 pasifler, SOIC-20W, 1812 PTC ve SMA diyot kolaydır. 4×0603 dizi direnç
  ince uç ister. Delikli parçalar: üç kutu başlık, altı pin başlık, klemens, elektrolitik ve
  iki 1×22 dişi soket.

## Açık sorular
1. DevKit resmi kart mı (0.9") yoksa klon mu (1.0")? Soketi lehimlemeden önce iki başlık
   arasını ölç.
2. Sensör modüllerinin pin sırası yaygın baskıya göre seçildi:

   | Başlık | Sıra |
   |---|---|
   | J5 LDR | 3V3, GND, AO |
   | J6 MIC | AO, GND, 3V3, DO |
   | J7 ENC | CLK, DT, SW, 3V3, GND |
   | J8 DHT | 3V3, DAT, GND |
   | J9 TOUCH | GND, 3V3, OUT |

   Modülündeki yazı farklıysa jumper'ı yazıya göre bağla ya da `SENSOR_HDRS` tablosunu
   değiştirip yeniden üret.
3. Kasa: `enclosure/generate_case.py` henüz bu kart için ayak ve sensör deliği içermiyor.
   Montaj delikleri köşelerden 3.5 mm içeride.
4. Yönlendirme otomatiktir ve 10–20 MHz HUB75 için yeterlidir. KiCad'de elle güzelleştirme
   yapılabilir ama `route` yeniden çalışınca kaybolur.
