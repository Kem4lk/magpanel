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

## main.cpp WS protokolü (ilk bayt = opcode)
0x01+28800B tam kare RGB888 · 0x02 piksel paketi · 0x03 temizle · 0x04 parlaklık
· 0x05 galeri · 0x06 RGB kazanç · 0x07 kontrast/doygunluk · 0x08 mozaik blok.
GIF animasyonu istemci tarafında: kareler 0x01 olarak sırayla yollanır
(firmware durum tutmaz; `if(msgReady)return;` ile hızlı kareler düşürülür).
