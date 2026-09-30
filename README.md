# FM6363C 80x40 1/20-scan HUB75E panel - ESP32-S3 driver (deneysel port)

mrcodetastic'in **ESP32-PWM-MatrixPanel-DMA** (MBI5153, ESP32-S3) implementasyonunun
FM6363C cipine portu. Panel: P4 indoor 80x40, 1/20 scan, 74HC138 satir decode,
FM6363C S-PWM surucu. Register degerleri panelin fabrika .ssx profilinden alindi.

## Mimari
- **LCD peripheral (DMA)**: DCLK + 6 RGB SDI hatti + LE/LAT -> grayscale verisi ve komutlar
- **GPSPI2 octal (DMA, sonsuz dongu)**: GCLK + A..E adres hatlari (satir tarama)

## Kablolama (mevcut HUB75 baglantin korunuyor)
| HUB75 | Islev | GPIO |
|-------|-------|------|
| R1 G1 B1 | ust yari SDI | 4, 5, 6 |
| R2 G2 B2 | alt yari SDI | 7, 15, 16 |
| A B C D E | satir adresi | 18, 8, 3, 9, 13 |
| CLK | DCLK | 12 |
| LAT | LE (komut) | 10 |
| OE | **GCLK** | 11 |

## Sensörler ve tam bağlantı şeması
`hardware/` klasöründe koddan üretilen şema (`gen_schematic.py` → `schematic.svg/png`) ve
pin tablosu var: [hardware/README.md](hardware/README.md). HUB75 kablolaması değişmedi;
beş JSUMO modülü ESP'nin SAĞ başlığına takılır (hepsi 3V3 ile beslenir):

| Modül | Pin | GPIO |
|-------|-----|------|
| LDR Sensor Board | AO | 1 (ADC1) |
| Microphone Sound Sensor | AO / DO | 2 (ADC1) / 42 (isteğe bağlı) |
| KY-040 Mechanic Encoder | CLK / DT / SW | 41 / 40 / 39 |
| DHT11 Temperature & Humidity | DATA | 47 |
| TTP223B Digital Touch | I/O | 21 |

Firmware tarafı (`include/sensors.h`, `include/sensor_logic.h`): enkoder = parlaklık,
enkoder/dokunmatik/çift alkış → uyku-uyan / sonraki uygulama / sonraki galeri / oto parlaklık
(web UI "Sensörler & kontroller" kartından eşlenir, NVS'te kalır); LDR ile oto parlaklık;
"Oda" (sıcaklık/nem/ışık/saat) ve "Ses" (VU) uygulamaları; 1 Hz `S:` telemetri + `/api/sensors`.

## Derleme
VS Code + PlatformIO eklentisi. Proje klasorunu ac -> Build -> Upload.
(`platformio.ini` ESP32-S3 DevKitC-1 icin hazir.)

## Test asamalari ve sorun giderme
1. **Duz kirmizi/yesil/mavi dolgular**: Temizse config + veri yolu calisiyor demektir.
   - Panel tamamen karanliksa: once `FM_GCLKS_PER_ROW`'u 148 yap (cift-kenar sayim ihtimali),
     olmadi GCLK frekansini dusur (spi_dma_seg_tx_loop.c).
   - Renkler yer degistirmisse: app_constants.hpp'de R/G/B pinlerini duzelt.
2. **Kose pikselleri**: Dort kose dogru yerde ve dogru renkteyse haritalama tamam.
   - Ust/alt yarilar ters ise R1<->R2 gruplarini degistir.
   - Satirlar 2'serli atliyorsa D ve E pinlerini degistir.
3. **Piksel yurutme**: x=0..79 duzgun soldan saga akmiyorsa izledigi sirayi not et:
   - 16'sarlik bloklar ters siradaysa: `FM6363_REVERSE_CHANNEL_ORDER 1` yap.
   - Daha karmasik bir desen varsa fabrika .ssx LookUpTab remap'ini ekleyecegiz (bende cozumu hazir).

## Bilinen belirsizlikler (ilk testte netlesecek)
- GCLK cift-kenar sayimi: 74 vs 148 GCLK/satir denemesi gerekebilir.
- VSYNC sirasinda GCLK duraklatma zamanlamasi hassas olabilir.
- Kanal sirasi (ch15 ilk mi) panel PCB'sine bagli.

## Guncelleme (OTA) ve tek komutla deploy
- Her panel `GITHUB_AUTO_OTA` ile `releases/latest`'teki `version.txt`'i yoklar; build
  numarasi artmissa `firmware.bin`'i indirip kurar. Kurulum sirasinda panelde **tum
  piksellerden olusan, alttan dolan loading ekrani** gosterilir (`drawOtaLoading`).
- "Yukle/deploy" demek icin: `tools/magpanel-mcp/` altindaki MCP sunucusu (repo kokundeki
  `.mcp.json` ile otomatik kayitli). Claude'a **"yukle"** dediginizde `deploy_update` araci
  CI'yi tetikler; firmware `latest` release'e gider ve internete bagli tum paneller otomatik
  guncellenir. Kurulum: [tools/magpanel-mcp/README.md](tools/magpanel-mcp/README.md).
