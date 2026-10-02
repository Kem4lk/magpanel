# MagPanel — Çalışma Notları (Claude)

ESP32-S3 (8MB PSRAM, 16MB flash) tabanlı 80×120 HUB75E LED matris panel.
FM6363C sürücü. PlatformIO + Arduino. WiFi + AsyncWebServer + WebSocket ile
tarayıcı/iOS app'ten kontrol; GitHub Actions CI → OTA.

## ⚠️ Güvenlik / sırlar (ÖNEMLİ — repoya sır yazma)
- `include/wifi_config.h` **gitignore'da** ve öyle KALMALI. Gerçek WiFi
  kimlik bilgilerini içerir; geçmişten `git filter-repo` ile temizlendi.
  Repoda sadece `include/wifi_config.example.h` (şablon) bulunur.
- CI, GitHub Secrets kullanır: `WIFI_SSID`, `WIFI_PASS`, `OTA_PASSWORD`.
  Build adımı bunlardan `wifi_config.h` üretir (bkz. `.github/workflows/build.yml`).
- Gerçek şifreleri (WiFi, OTA) **commit'lere, CLAUDE.md'ye, koda yazma.**
- Geliştirme dalı: `claude/sweet-babbage-bjbdk3`. Push: `git push -u origin <dal>`.

## Donanım / build gerçekleri
- `platformio.ini`: `board_build.arduino.memory_type = qio_opi` (PSRAM şart),
  `-DBOARD_HAS_PSRAM`. Build env: `esp32-s3-devkitc-1` (USB), `esp32-s3-ota`
  (espota, `upload_port` = panelin IP'si, `--auth` = OTA_PASSWORD).
- `CONFIG_ESP32S3_SPIRAM_SUPPORT redefined` uyarısı zararsız (SDK vs flag).
- **Düşük heap kısıtı:** çalışırken boş heap ~15.8KB, en büyük blok **~7KB**.
  Matris DMA + WiFi + AsyncWebServer dahili RAM'i sonuna kadar kullanır.
  Büyük (>7KB) tek parça `malloc`/`String` ayırmaları BAŞARISIZ olur.

## Çözülen hatalar
1. **OTA boot-loop:** Local USB build'leri (FW_BUILD=0) eski/yanlış şifreli
   CI firmware'ine otomatik OTA yapıp WiFi'ye bağlanamıyordu → 60sn'de restart
   döngüsü. Düzeltme: `checkGithubOTA()` başında `if(FW_BUILD==0) return;`.
   `FW_BUILD` wifi_config.h'da tanımsız → main.cpp `#ifndef`'i 0 yapar.
2. **BLE provisioning matris DMA crash'i:** BLE kütüphanesi yeterince dahili
   RAM ayırınca `Matrix::initMatrix()` içinde `dma_grey_gpio_data` ayrılamıyor,
   `assert failed ... Matrix.h:104` → boot loop. **BLE + WiFi + büyük LED DMA
   bu çipte BİRLİKTE sığmaz.** Çözüm: BLE tamamen çıkarıldı, yerine **WiFi
   AP-modu provisioning** (sadece WiFi kullanır, ekstra RAM yok).
3. **AP-modu provisioning:** WiFi bağlanamazsa panel `MagPanel-Setup` açık ağı
   yayınlar; kullanıcı `http://192.168.4.1` → SSID+şifre girer → NVS'e kaydedilir
   → restart. Kimlik önceliği: NVS > derlenmiş wifi_config.h > AP modu.
   (`Preferences` ile NVS "wificfg" namespace.) App gerekmez.

## 🔴 AÇIK SORUN — GIF sayfası JS hatası (öncelik)
- Web arayüzüne GIF kare-kare animasyon eklendi (`include/web_page.h`:
  `playGif`/`stopGif`, `ImageDecoder` ile; commit `bd4aeb6`). Firmware **derlendi**.
- Ama tarayıcıda: `Uncaught ReferenceError: art is not defined` /
  `ws is not defined` → `<script>` bloğunun TAMAMI tanımsız. İki hipotez:
  1. JS sözdizimi hatası (göz taramasıyla bulunamadı — gerçek tarayıcıda test et).
  2. **Düşük heap:** `/` handler'ı `String page = FPSTR(INDEX_HTML)` ile ~10KB
     sayfayı tek parça heap'e kopyalıyor; en büyük blok ~7KB olduğundan kopya
     başarısız/eksik olup script'i kesiyor olabilir.
- **Teşhis adımı:** sayfayı aç → "Sayfa kaynağını göster" → HTML `</html>` ile
  bitiyor mu? Bitmiyorsa = kesilme (heap/sunum sorunu). Bitiyorsa = JS sözdizimi.
- **Önerilen düşük-heap-dayanıklı düzeltme:** `/` sayfasını String'e kopyalamadan
  PROGMEM'den akıtarak gönder. `%VAR%` template-processor CSS'teki `%` (örn.
  `width:100%`) yüzünden riskli; bunun yerine ya `beginChunkedResponse` ile elle
  akıt + {{VER}} değiştir, YA da sürümü ayrı küçük endpoint'ten (örn. `/ver`)
  JS ile çek ve `INDEX_HTML`'i `send_P` ile değiştirmeden gönder.

## Flash yöntemleri (lokal Mac)
Lokal kaynak güncel değilse: dalı curl'le çek, sonra derle/yükle. Örn:
`curl -fsSL -o src/main.cpp "https://raw.githubusercontent.com/Kem4lk/magpanel/claude/sweet-babbage-bjbdk3/src/main.cpp"`
- **USB:** `~/.platformio/penv/bin/pio run -e esp32-s3-devkitc-1 --target upload`
  - `pio` PATH'te değil → tam yol kullan (yukarıdaki). Yeni terminalde yok.
  - Port meşgulse: `lsof /dev/cu.usbmodem*` → `kill -9 <PID>`.
  - **Auto-detect yanlış portu seçebilir** (örn. `/dev/cu.BoseRevolveSoundLink`).
    Zorla: `--upload-port /dev/cu.usbmodem2101` (önce `ls /dev/cu.usb*` ile doğrula).
- **espota (kablosuz):** `pio run -e esp32-s3-ota --target upload`. "Host Not
  Found" → panelin IP'si değişmiş ya da ArduinoOTA cevapsız (port 3232 UDP).
- **Web /update (en güvenilir, HTTP/80):** `http://<panelIP>/update`, kullanıcı
  `admin`, şifre = OTA_PASSWORD. Yerel `firmware.bin`'i seç (GitHub'da DEĞİL;
  `.pio/build/<env>/firmware.bin`). Dosyayı `~/Desktop`'a kopyalayıp seçmek kolay.

## Lokal ortam tuhaflıkları (kullanıcının Mac'i)
- Proje klasörü: `~/Documents/Documents - Kemal's MacBook Pro/Environments/MagPanel Git`
  (boşluk + KIVRIK apostrof '). Yollar Finder/terminalde sorun çıkarır; dosyayı
  `~/Desktop`'a kopyalayarak apostrof derdinden kaçın.
- **Bozuk git:** Bu lokal klasörün kendi `.git`'i yok; ev klasöründe yanlışlıkla
  oluşmuş `~/.git` (remote = `Hood-Landing-Page`, yanlış repo) tüm ev dizinini
  repo sanıyor. `git status` ev klasörünü tarıyor. Lokalde `git pull` ile
  magpanel güncellenmez → curl ile dosya çek veya temiz `git clone` yap. Bu
  yüzden değişiklikler curl ile aktarılıyor. (İleride: `~/.git`'i temizle / temiz
  clone'a geç.)
- **IP zıplaması:** Panel her reboot'ta DHCP'den farklı IP alıyor (.73→.86→.33→…).
  MAC `e0:72:a1:f6:0a:28` (router'da `esp32s3-F60A28`). **Yapılacak: router'da
  (ZTE ZXHN H298A, 192.168.1.1) bu MAC'e DHCP rezervasyonu** ile sabit IP. IP
  değişince espota/web hep kırılıyor; bu kalıcı çözüm.
- Boot anında IP'yi görmek: USB takılıyken `pio device monitor -b 115200`.
- `[NET] heap=.. min=.. blok=.. RSSI=..` satırı loop()'tan; panelin online +
  WiFi bağlı olduğunu kanıtlar (geçici teşhis logu, sonra kaldırılabilir).

## Sürümleme notu
- `FW_VERSION` (wifi_config.h) sadece kozmetik etiket; lokalde elle ayarlı
  (örn. `v24-ble`). CI build'leri `build-<run_number>` + `FW_BUILD=<n>`. İkisi
  KIYASLANAMAZ; önemli olan kod içeriği. AP-modu ve GIF build'leri aynı
  `v24-ble` etiketini gösterir → etiket güncellemeyi doğrulamaz; GIF'i test et.
- Ayırt etmek istersen wifi_config.h'da FW_VERSION'ı her anlamlı değişimde elle
  bump et (örn. `v25-gif`).

## Panel seçimi — ana firmware P4 VE P1.86'yı sürer (derleme zamanı)
- `include/panel.h`: `-DPANEL_P186` yoksa `Panel = Matrix` (P4 80×120), varsa `Panel = PanelSM16380`
  (P1.86 172×86). `main.cpp`/`apps.h` sadece `Panel`, `PANEL_W/H`, `PANEL_NAME`, `PANEL_CFG_NS`,
  `PANEL_DEFAULT_DIV`, `OTA_FW_FILE` kullanır. İki sürücü aynı ikilide YOK (P4 dahili RAM'i dolduruyor).
- Env'ler: P4 = `esp32-s3-devkitc-1` / `esp32-s3-ota` (değişmedi). P1.86 = `p186` / `p186-ota`
  (aynı main.cpp). Test/kalibrasyon firmware'i ayrıca `p186-test` olarak duruyor.
- CI iki ikiliyi de derler: `firmware.bin` (P4) + `firmware-p186.bin`; `version.txt` ortak. Cihaz
  GitHub OTA'da kendi `OTA_FW_FILE`'ını çeker → P4 cihazına asla P1.86 ikilisi gelmez.
- P1.86'da `rxbuf`/`framebuf` (~44 KB ×2) PSRAM'de; dahili RAM kullanımı ~%18 (P4 ~%36).
  DCLK NVS'i ayrı namespace: `panelcfg186` (varsayılan bölen 16 = 10 MHz). Açılış parlaklığı 110.
- Web sayfası boyutu `{{PW}}`/`{{PH}}`/`{{PN}}` yer tutucularıyla alır (handleIndex parça listesi);
  kanvas/kare/önizleme/kayıtlar buna göre. localStorage anahtarları P4'te aynı, diğer boyutta `_WxH` ekli.
  WS bağlanınca firmware `D:WxH:P1.86:N:düzen` metin mesajı yollar (iOS app kare boyutunu buradan almalı).
- Galeri 80×120 saklanır; P1.86'da en-boy korunarak 57×86'ya ölçeklenir, ortada, kenarlar siyah.
  Uygulamalar (saat/timer/hava/…) yatay panelde `L(p4, genis)` ile ayrı yerleşim + büyük font.
- **Çoklu P1.86 (1..3 modül, tek ESP32):** modülde OUT yok → tüm paneller RGB/DCLK/OE/ABCDE hattını
  PAYLAŞIR, sadece LAT (HUB75 pin 14) panel başına ayrı: P1 GPIO10 (d6), P2 **GPIO17** (d13),
  P3 **GPIO14** (d14). Veri akışta panel panel ardışık (panel başına 22 çevrim); veri latch'i yalnız
  o panelin LAT'ında, komutlar (VSYNC/11/14/register) tüm LAT'larda yayın. Düzen: dikey (alt alta,
  P1 üstte → 172×86N) / yatay (yan yana, P1 solda → 172N×86). NVS `panelcfg186`: `npanels`, `layout`;
  web UI "Görüntü ayarları → Panel düzeni" (WS `0x10 n ly` → kaydet + restart) ve "Panel numaraları"
  testi (her panele numara + sarı sol-üst işaret). 3 panel: akış ~720 KB PSRAM, kare ~37 ms @10 MHz.
  `PANEL_W/H` P1.86'da çalışma anında (`sm16380::g_w/g_h`); uygulamalar `L()/S()` ile ölçeklenir.
  Host simülasyonu: her panel yalnız kendi 688 veri latch'ini görür, komut genişlikleri tüm panellerde aynı.
- Breadboard/uzun jumper'da 10 MHz DCLK sinyal bozulması (çip sınırlı renk blokları, satır bantları)
  görüldü → iki GND teli (HUB75 pin 4 + 16), kısa CLK, gerekirse DCLK 5–8 MHz. Ürün: 74HCT245 tampon.
- Açık: iOS app hâlâ sabit 28800 B kare yolluyor (P1.86'da 44376 B gerekir → `D:` mesajını kullanmalı);
  güç sınırlayıcı (ABL) yok — P1.86 tam beyaz/parlaklık 255 ≈ 31 W/modül.

## P1.86 172×86 panel (SM16380SH + SM5368) — TEST firmware (P4 korunuyor)
- Modül: YI YI STAR `P1.86-INDOOR-Y52`, etiket/QR `16380SH-5368`, 1/43 tarama,
  tek HUB75 **giriş** (OUT yok → zincir yok; çoklu panel = ortak hat + panel başına ayrı LAT planı).
- **P4 (FM6363C) firmware'i aynen duruyor** (varsayılan env'ler, CI, GitHub OTA). P1.86 ayrı env:
  `pio run -e p186-test -t upload` (USB) / `-e p186-test-ota` (espota). Kaynak: `src/p186_test.cpp`
  + `include/panel_sm16380.h`. `build_src_filter` ile P4 env'i test dosyasını, test env'i `main.cpp`'yi derlemez.
- Geri dönüş: test firmware'inin `http://<ip>/update` sayfasından P4 `firmware.bin` yükle (ya da USB).
  Test firmware'inde GitHub OTA yok.
- Kablolama P4 ile AYNI (GPIO eşlemesi değişmedi). Protokol farkları:
  DCLK = veri + PWM saati (sürekli akar); her 128 DCLK'da satır geçişi + OE (pin 15, eski GCLK biti)
  4 DCLK darbe; SM5368: A = satır saati, B = BK, C = satır verisi (D/E = 0);
  LE komutları VSYNC=3, 11, 14; register yazımı `00AA,01AA,değer,0055,0155` (LE son 5 DCLK);
  gri ton 16 bit/kanal, değer alt 13 bitte. Register profili: `regtype6 P1.86-SM16380SH-5368-1/43`.
- Akış tamponu ~248 KB **PSRAM**'de (dahili RAM'e sığmaz); `send_stuff_once` PSRAM kaynağında
  64 B hizalı 4032'lik parçalar kullanır (dahili RAM davranışı değişmedi). `esp_cache_msync` şart.
- Web UI (`/`): desenler, parlaklık (varsayılan 64 — güç!), DCLK, satır modu (SM5368/ikili),
  BK modu, OE polaritesi, register profili, gri ton bitleri, eşlem (X ayna, kanal ters, yarı takas,
  Y ters, X/satır ofseti). Ayarlar NVS `p186cfg`.
- **İlk donanım testi (2026-09-27): ilk denemede ÇALIŞTI.** rt6 profili + varsayılan ayarlar
  (SM5368 kaydırma, OE aktif-yüksek, BK darbe, 13 bit, 10 MHz) ile düz renkler, yarılar (üst K/alt M),
  yön testi (K sol-üst, Y sağ-üst, M sol-alt, "P1.86" düz), çip blokları (soldan sağa 11 blok,
  merdiven doğru) ve 8px ızgara doğru. Eşlem ayarı gerekmedi. Açık: beyaz hafif mor/mavi (kazanç
  kalibrasyonu), gradyanın koyu ucu parlaklık 64'te tam siyah görünüyor (düşük gri ton testi yapılacak).
- **Sütun düzeni (ızgara fotoğrafıyla ölçüldü):** 172 sütun 176 kanala dağılır; boş (LED'e gitmeyen)
  zincir konumları **0, 16, 144, 160** = çip 0/1/9/10'un 0. kanalı (15+15+7×16+15+15). Doğrusal
  eşlemde bu sol kenar çizgisini yutuyor, sağdaki 4 sütunu karartıyor ve sütun yürüyende "atlama"
  yapıyordu. `Options::col_layout=1` (varsayılan) LUT ile düzeltir; X ofset artık sadece doğrusal modda.
- Seri log: HWCDC `Serial`, monitör açılıştan sonra bağlanınca susabiliyor (ESP_LOG satırları
  geliyordu, `Serial.println` gelmiyordu) → test firmware'i `printf` kullanır. Web /log her zaman çalışır.
- WiFi yoksa test firmware'i `MagPanel-Setup` açık ağını yayınlar → http://192.168.4.1 (test sayfası
  + /wifi formu, NVS "wificfg"e yazar). Açılışta görünen ağlar + bağlantı hatası nedeni loglanır.
- Lisans notu: protokol bilgisi DMD_STM32 (GPLv3) ve ESP32-HUB75-MatrixPanel-DMA (MIT)
  incelenerek öğrenildi; kod bağımsız yazıldı, register değerleri donanım ayarı olarak alındı.
  Ticari ürün öncesi hukuki kontrol önerilir.

## main.cpp WS protokolü (ilk bayt = opcode)
0x01+W·H·3 B tam kare RGB888 (P4 28800, P1.86 44376) · 0x02 piksel paketi · 0x03 temizle · 0x04 parlaklık
· 0x05 galeri · 0x06 RGB kazanç · 0x07 kontrast/doygunluk · 0x08 mozaik blok
· 0x09 GitHub OTA · 0x0A canlı DCLK bölen · 0x0B uygulama seç (0 kapat,1 saat,2 timer,3 hava,4 dünya kupası,
5 spotify,**6 oda,7 ses**) · 0x0C hava konumu · 0x0D Spotify token · 0x0E blur · **0x0F flicker self-test**
· 0x10 (P1.86) panel düzeni · **0x11 sensör/kontrol ayarı** (alt komut 1 oto parlaklık `on,min,LDRters`;
2 eylemler `bas,uzun,dokun,alkış`; 3 alkış eşiği; 4 enkoder `adım,ters`) · **0x12 uyku** (0 uyan, 1 uyu, 2 değiştir).
Firmware→istemci metin frame'leri: `L:` log, `G:` galeri, `D:` boyut, **`C:` sensör ayarları+parlaklık+uyku
(bağlanınca ve her değişimde), `S:` 1 Hz telemetri, `B:` parlaklık değişti (enkoder)**. HTTP: `/api/sensors`.
GIF animasyonu istemci tarafında: kareler 0x01 olarak sırayla yollanır
(firmware durum tutmaz; `if(msgReady)return;` ile hızlı kareler düşürülür).

## Sensörler & fiziksel kontroller (2026-09-29, dal `ccr-f127ab41-6drmx9`)
- **Şema:** `hardware/gen_schematic.py` → `hardware/schematic.svg/png` (kasa gibi parametrik; pinler
  değişirse script'i düzelt, yeniden üret; script kesişim kontrolü yapar). Pin tablosu + modül notları +
  kasa yerleşimi `hardware/README.md`. PNG: Chromium headless + Pillow crop (README'de komut).
- **Pinler** (`include/sensors.h`, `-DSENS_PIN_*` ile değişir): LDR AO **GPIO1**, mikrofon AO **GPIO2**
  (DO **42** isteğe bağlı), KY-040 CLK/DT/SW **41/40/39**, DHT11 DATA **47**, TTP223B OUT **21**. Hepsi 3V3.
  Analog SADECE ADC1 (GPIO1–10): ADC2 WiFi ile çakışır. HUB75 (3–18) ve P1.86 LAT2/3 (17/14) ile çakışmaz;
  19/20 USB, 33–37 OPI PSRAM, 0/45/46 strapping, 38/48 devkit RGB LED boş bırakıldı.
- **Dosyalar:** `include/sensor_logic.h` saf C++ (enkoder Buxton tam-adım tablosu, buton FSM, DHT 40-bit
  çözme, zarf, alkış, oto parlaklık) → `g++ -std=c++17 -I include tools/test_sensor_logic.cpp && ./a.out`
  host testi. `include/sensors.h` donanım: DHT11 iki fazlı bloklamayan okuma (20 ms LOW loop'ta, sonra ~4 ms
  kritik bölge, 3 sn'de bir; kütüphane yok), LDR 10 Hz EMA, mikrofon ≤2 kHz örnek/20 ms pencere
  (`micWanted` = alkış açık ‖ Ses uygulaması ‖ WS istemci var), enkoder GPIO kesmesi (IRAM_ATTR **değil**:
  Arduino ISR servisi IRAM'sız; inline IRAM fonksiyon xtensa'da "l32r literal placed after use" link hatası
  verir), NVS `sensors`. `Sensors::loop()` OTA sırasında çağrılmaz.
- **Davranış (main.cpp `sensorTick`):** enkoder çevirme = `userBri` (oto modda tavan) → `matrix.global_brightness`
  → redraw; `B:` yayını; 3 sn debounce ile NVS `PANEL_CFG_NS/bri` (boot'ta geri yüklenir — artık parlaklık
  kalıcı). Eylemler NVS'ten: enkoder bas=uyku/uyan, uzun bas=sonraki uygulama (saat→hava→oda→ses→kapat),
  dokunmatik=uyku/uyan, çift alkış=kapalı (varsayılanlar). **Uyku:** `clear_pixels+update`, `redrawCurrent()`
  ve `apps.loop()` uykuda çalışmaz; dokunmatik/enkoder/alkış ya da WS 0x01/02/05/0B/0F uyandırır. Oto
  parlaklık: `min + (userBri-min)*ışık%`, 1 sn'de bir, ±3 histerezis. Tek alkış eylem üretmez.
- **Bağlı olmayan sensör zararsız:** dokunmatik pull-down, enkoder pull-up, DHT 3 hatada "yok", oto
  parlaklık/alkış varsayılan kapalı. Web kartı "Sensörler & kontroller" (`<details>`): canlı değerler, ses
  çubuğu+eşik çizgisi, eylem select'leri, uyku butonu. JS `node --check` + headless Chromium yüklemesi temiz.
- **Bellek:** P4 RAM %36.6→%37.0 (+1.4 KB), flash +27 KB; P1.86 RAM %18.3. Her iki env derlendi (pio 6.2, lokal).
- **Donanımda doğrulanacak (henüz panelde test edilmedi):** LDR yönü ("LDR ters"; eldeki kart DO'lu →
  2 kademe), mikrofon kartı 3 pin dijital (OUT→42), enkoder yönü ("Enkoder ters"), DHT11 zamanlaması (log: `Sensorler:` satırı,
  telemetride `d:1`), alkış eşiği. İlk testte web LOG'da `Kontrol: ... -> ...` satırlarını izle.
- **Açık:** kasaya sensör delikleri (`enclosure/generate_case.py`) eklenmedi; iOS app `S:/C:/B:` frame'lerini
  henüz kullanmıyor (bilinmeyen metin frame'lerini yok saymalı).

## KiCad taşıyıcı kart (2026-10-01, `hardware/kicad/`)
- `gen_carrier.py` tek kaynak: `sch` → `pcb` → `route` → `fab` (`all` hepsi). KiCad 8'in python'u ile
  çalışır (Linux `/usr/bin/python3`, macOS KiCad.app içindeki python). `sch` yalnız stdlib: `sexp.py`
  (S-ifade okuma/yazma), `schlib.py` (KiCad sembol kütüphanesi; dönüşüm sırası: önce döndür, sonra ayna).
- Kart v1.1, 100×63.5 mm, 2 katman. DevKit dişi soket: sağ sıra `DEVKIT_RIGHT_ROWS` (eldeki N16R8 klon,
  2× USB-C = 1.0" / 25.4 mm; 1:1 baskıyla doğrulandı; resmi kart 0.9"). Tampon **2× CD74HCT245E DIP-20
  soketli** (HCT şart: düz HC 5 V'ta 3.3 V girişi garanti okumaz); A pinleri DevKit adımında
  (U2 pin1 = satır 11, U3 pin1 = satır 22, 180°), 4×33R dizi, LAT/LAT2/LAT3/OE 10k pull-down
  (OE=GCLK/aktif-yüksek → düşük = karanlık), 3× IDC 2×8 HUB75E (LAT IO10/IO17/IO14), 5 V klemens + PTC
  1.5 A + SMAJ5.0A + 470 µF; 5 V ana hat tamponların altından (alt şerit) DevKit 5V pinine sağdan girer.
- Eldeki modüller (foto 2026-10-02), başlıklar bu sırada: LDR 16067 VCC/GND/DO, MIC 15771 OUT/GND/VCC,
  KY-040 CLK/DT/SW/+/GND, DHT11 15579 −/OUT/+, TTP223B 17538 SIG/VCC/GND. **LDR ve MIC yalnız dijital**
  (LM393): LDR DO→IO1 (analog okunur → oto parlaklık iki kademe), MIC OUT→IO42 (kesme); IO2 R7 100k GND.
- Netler PCB'ye KiCad'in kendi netlist'inden yazılır (`kicad-cli sch export netlist`): yerel etiket
  `/AD`, NC pin `unconnected-(U1-…)` + pintype `…+no_connect` → şematik↔PCB farkı 0. Net sınıfları ve
  tasarım kuralları `.kicad_pro` JSON'una yazılır (`SaveBoard(..., True)` API'den ayarlanan kuralları
  kaydetmiyor); `.kicad_dru`: `min_resolved_spokes 1`.
- `route`: Freerouting 2.1.0 (Java 21; `-inc` ile net sınıfı dışlama ÇALIŞMIYOR). GND de iz olarak
  çekilir, sonra iki katman GND dökümü + dikiş via'ları (serigrafi altına konmaz). Yalnız döküme
  güvenince IDC GND pinleri (4/16) veri yolu izleri arasında yalıtılıyordu. Freerouting deterministik
  değil ve ara sıra KiCad'in bağlanmamış saydığı parça bırakıyor → DRC temiz olana kadar ≤10 deneme;
  her deneme `work/…-preroute.kicad_pcb`'den başlar.
- **KiCad 8 SWIG tuzağı:** `board.Remove(x)` sonrası Python vekili çöp toplanırsa tip tablosu bozuluyor
  (`board.Zones()` / `GetConnectivity()` ham `SwigPyObject` döner) → silinen öğeye referans tut
  (`board_remove()`).
- `fab`: ERC/DRC/parity sıfır değilse durur. Gerber zip (sabit tarih), BOM (işleve göre gruplu),
  JLC BOM/CPL (yalnız SMD, LCSC boş), şematik PDF, **1:1 yerleşim PDF'i** (A4, yalnız ped+delik, 100 mm
  ölçek çubuğu; kullanıcı tablette/kâğıtta gerçek parçalarla denedi), görseller (`kicad-cli pcb export svg`
  katmanları → Chromium → PIL; headless pencere görüntüden yüksek olmalı, yoksa alt kenar kesilir).
- Açık: pasifler SMD varsayıldı (0805, 4×0603 dizi, 1812 PTC, SMA), klemens 5.08 mm, C1 Ø8/3.5 mm;
  kasaya taşıyıcı ayakları + sensör delikleri; LCSC numaraları.

## Flicker self-test (0x0F) — teşhis/kalibrasyon
Web UI "Görüntü ayarları" → **Flicker testi (panele)** butonu (ya da WS `[0x0F]`)
firmware-tarafı otomatik bir desen dizisini başlatır (`main.cpp` `FT_SEQ`/`ftLoop`).
33 faz, ~87 sn; her faz panelin sol-üstüne `Pxx kod` etiketi çizer (videoda fazı
okumak için) ve web LOG'a `FT Pxx ...` yazar. Statik fazlar TEK kare çizilir
(sürekli DMA → saf refresh/PWM flicker'i + güç çökmesi görünür); hareketli fazlar
(`SCROLL`/`PULSE`) ~25fps yeniden çizilir (update() dim-sweep = animasyon flicker'i);
`d80..d8` fazları DCLK bölenini gezer (2→20 MHz; kalibrasyon: videodan en az flicker +
mozaiksiz kademeyi seç → UI'daki DCLK butonuyla kalıcı yap). DCLK clamp `set_clock_divider`/
0x0A/NVS-boot'ta **8..200** (160/8=20MHz tavan; >10MHz deneysel, jumper bus ring→mozaik
olabilir). İlk videoda d16=10MHz temiz çıktı, d18→d16'da flicker genliği ~%30 düştü. Test sırasında görüntü
hattı nötr'e çekilir, bitince tüm ayarlar + DCLK böleni geri yüklenir. Test'i
herhangi başka bir WS komutu da durdurur. Reboot'ta uygulama NVS'ten geri gelmez —
test bittikten sonra istenen uygulama yeniden seçilmeli.
