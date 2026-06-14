/* FM6363C 80x120 v17 - WiFi + WebSocket sunucu
   Protokol (binary WS, ilk bayt opcode):
     0x04 + 1B     : global parlaklik (0-255)
     0x05 + 1B     : gomulu galeri tablosu (0..GALLERY_COUNT-1)
     0x06 + 3B     : kanal kazanclari R,G,B (beyaz nokta kalibrasyonu)
     0x07 + 2B     : kontrast, doygunluk (128 = notr)
     0x08 + 1B     : mozaik blok boyutu (1=kapali, 2..40)
     0x01 + 28800B : tam kare RGB888 (satir-major, y0:x0..79)
     0x02 + N*5B   : piksel paketi (x,y,r,g,b)
     0x03          : temizle
   Acilista Mona gosterilir; IP seri porta yazilir; http://magpanel.local
   uzerinden gomulu test sayfasi acilir (iOS app ayni protokolu konusur). */
#include <stdarg.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoOTA.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include "esp_wifi.h"
#include "esp_log.h"
#include <Update.h>
#include <Preferences.h>
#include <Matrix.h>
#include "gallery.h"
#include "wifi_config.h"
#include "web_page.h"

Matrix matrix;
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

// ---- AP-modu WiFi Provisioning (USB'siz kablosuz kurulum) ----
// WiFi baglanamazsa panel 'MagPanel-Setup' adli acik bir WiFi agi yayinlar.
// Telefon/laptop o aga baglanir, http://192.168.4.1 acar, yeni SSID+sifre girer.
// Kimlik NVS'e kaydedilir; panel yeniden baslar ve yeni agla baglanir. App gerekmez.
static Preferences prefs;
static volatile bool apSaved = false;
static const char PROV_HTML[] =
  "<!DOCTYPE html><html><head><meta charset=utf-8>"
  "<meta name=viewport content='width=device-width,initial-scale=1'>"
  "<title>MagPanel WiFi Kurulum</title><style>"
  "body{font-family:sans-serif;max-width:420px;margin:32px auto;padding:0 16px}"
  "input{width:100%;padding:11px;margin:6px 0;box-sizing:border-box;font-size:16px}"
  "button{width:100%;padding:13px;margin-top:8px;font-size:16px;background:#06f;color:#fff;border:0;border-radius:8px}"
  "</style></head><body><h2>MagPanel WiFi Kurulum</h2>"
  "<form method=POST action=/save>"
  "<label>WiFi Adi (SSID)</label><input name=ssid required>"
  "<label>Sifre</label><input name=pass type=password>"
  "<button type=submit>Kaydet ve Baglan</button></form></body></html>";

static void runAPProvisioning(){
  Serial.println("WiFi yok - AP modu: 'MagPanel-Setup' agina baglanip http://192.168.4.1 acin");
  for(int y=0;y<PANEL_PHY_RES_Y;y++) for(int x=0;x<80;x++) matrix.drawPixel(x,y,0,0,60);
  matrix.update();

  WiFi.mode(WIFI_AP);
  WiFi.softAP("MagPanel-Setup");
  Serial.printf("AP IP: %s\n", WiFi.softAPIP().toString().c_str());

  static AsyncWebServer apsrv(80);
  apsrv.on("/", HTTP_GET, [](AsyncWebServerRequest *r){
    r->send(200, "text/html", PROV_HTML);
  });
  apsrv.on("/save", HTTP_POST, [](AsyncWebServerRequest *r){
    String ssid, pass;
    if(r->hasParam("ssid", true)) ssid = r->getParam("ssid", true)->value();
    if(r->hasParam("pass", true)) pass = r->getParam("pass", true)->value();
    if(ssid.length()){
      prefs.begin("wificfg", false);
      prefs.putString("ssid", ssid);
      prefs.putString("pass", pass);
      prefs.end();
      r->send(200, "text/html",
        "<meta charset=utf-8><h2>Kaydedildi. Panel yeniden baslatiliyor...</h2>");
      apSaved = true;
    } else r->send(400, "text/plain", "SSID bos olamaz");
  });
  apsrv.begin();

  while(true){                       // kayit gelene kadar AP'de bekle (panel mavi)
    matrix.refresh(); delay(20);
    if(apSaved){ delay(1000); ESP.restart(); }
  }
}

// ---- Kablosuz log: seri + WebSocket'e ayni anda yazar, son satirlari tamponlar ----
#define LOG_LINES 50
#define LOG_LINE_LEN 120
static char     logBuf[LOG_LINES][LOG_LINE_LEN];
static uint8_t  logHead = 0;     // siradaki yazilacak slot
static uint8_t  logCount = 0;    // dolu slot sayisi
static void logf(const char *fmt, ...){
  char line[LOG_LINE_LEN];
  va_list ap; va_start(ap, fmt);
  vsnprintf(line, sizeof(line), fmt, ap);
  va_end(ap);
  Serial.println(line);                                  // her zaman seri porta
  strncpy(logBuf[logHead], line, LOG_LINE_LEN-1);
  logBuf[logHead][LOG_LINE_LEN-1]=0;
  logHead = (logHead+1) % LOG_LINES;
  if(logCount < LOG_LINES) logCount++;
  // canli izleyenlere yayinla (metin frame, "L:" onekli)
  if(ws.count()){
    String msg = "L:"; msg += line;
    ws.textAll(msg);
  }
}
// Yeni baglanan istemciye gecmis loglari sirayla gonder
static void sendLogHistory(AsyncWebSocketClient *c){
  uint8_t idx = (logHead + LOG_LINES - logCount) % LOG_LINES;
  for(uint8_t i=0;i<logCount;i++){
    String msg = "L:"; msg += logBuf[idx];
    c->text(msg);
    idx = (idx+1) % LOG_LINES;
  }
}
static int8_t lastGallery = 0;   // kazanc degisince yeniden cizim icin
static uint8_t mosaicBlock = 1;  // 1 = tam cozunurluk; N = NxN blok mozaik
static volatile bool otaActive = false;
static volatile uint32_t lastOtaActivity = 0;   // OTA ilerleme zaman damgasi (takilma kurtarma icin)
static volatile bool otaNowRequested = false;    // 0x09 WS opcode: manuel GitHub OTA tetikle
#ifndef FW_BUILD
#define FW_BUILD 0
#endif
void drawGallery(uint8_t idx);
void renderFrame();
void redrawCurrent();

static const size_t FRAME_BYTES = (size_t)PANEL_PHY_RES_X * PANEL_PHY_RES_Y * 3;  // 28800
static uint8_t rxbuf[1 + FRAME_BYTES];
static uint8_t framebuf[FRAME_BYTES];           // son gosterilen kare (ayar degisiminde yeniden cizim)
static bool    haveFrame = false;
static volatile size_t  msgLen   = 0;
static volatile bool    msgReady = false;

void renderFrame(){
  uint8_t b = mosaicBlock < 1 ? 1 : mosaicBlock;
  if(b == 1){
    const uint8_t *p=framebuf;
    // Doldurma (drawPixel) saf CPU ve hizli (~1ms). Araya refresh() koymak
    // onceki kareyi parlak gosterip update()'in 30ms'lik dim sweep'iyle KONTRAST
    // yaratiyordu (flicker'i artiriyordu) + kare hizini dusuruyordu. Kaldirildi:
    // sadece doldur, sonra tek update().
    for(int y=0;y<PANEL_PHY_RES_Y;y++)
      for(int x=0;x<80;x++,p+=3)
        matrix.drawPixel((uint8_t)x,(uint8_t)y,p[0],p[1],p[2]);
  } else {
    // NxN bloklara bol, her blogun ortalama rengini tum bloga yaz
    for(int by=0; by<PANEL_PHY_RES_Y; by+=b){
      for(int bx=0; bx<80; bx+=b){
        uint32_t sr=0,sg=0,sb=0,cnt=0;
        for(int dy=0; dy<b && by+dy<PANEL_PHY_RES_Y; dy++)
          for(int dx=0; dx<b && bx+dx<80; dx++){
            const uint8_t *q = framebuf + ((by+dy)*80 + (bx+dx))*3;
            sr+=q[0]; sg+=q[1]; sb+=q[2]; cnt++;
          }
        uint8_t r=sr/cnt, g=sg/cnt, bl=sb/cnt;
        for(int dy=0; dy<b && by+dy<PANEL_PHY_RES_Y; dy++)
          for(int dx=0; dx<b && bx+dx<80; dx++)
            matrix.drawPixel((uint8_t)(bx+dx),(uint8_t)(by+dy),r,g,bl);
      }
    }
  }
  matrix.update();                                     // tek latch: dim sweep'i bir kez yap
}
// Parlaklik/kazanc/kontrast degisince panel kendi icerigini yeniden cizer -
// istemcinin (bos olabilecek) kanvasini yeniden gondermesine gerek kalmaz.
void redrawCurrent(){
  if(lastGallery>=0) drawGallery((uint8_t)lastGallery);
  else if(haveFrame) renderFrame();
}
void drawGallery(uint8_t idx){
  if(idx>=GALLERY_COUNT) return;
  memcpy(framebuf, GALLERY_DATA[idx], FRAME_BYTES);  // galeriyi framebuf'a al
  haveFrame = true;
  renderFrame();                                     // mozaik dahil ortak render
  logf("Galeri: %s", GALLERY_NAMES[idx]);
}

void onWsEvent(AsyncWebSocket*, AsyncWebSocketClient *client, AwsEventType type,
               void *arg, uint8_t *data, size_t len){
  if(type==WS_EVT_CONNECT){ logf("WS istemci #%u baglandi", client->id()); sendLogHistory(client); return; }
  if(type==WS_EVT_DISCONNECT){ Serial.printf("WS istemci #%u ayrildi\n", client->id()); return; }
  if(type!=WS_EVT_DATA) return;
  AwsFrameInfo *info=(AwsFrameInfo*)arg;
  if(info->opcode!=WS_BINARY) return;
  if(msgReady) return;                          // onceki mesaj islenmeden geleni dusur (akis kontrolu)
  static size_t acc=0;
  if(info->index==0 && info->num==0) acc=0;     // yeni mesaj basliyor
  if(acc+len <= sizeof(rxbuf)){ memcpy(rxbuf+acc, data, len); acc+=len; }
  if(info->final && (info->index+len)==info->len){ msgLen=acc; msgReady=true; }
}

void handleMessage(const uint8_t *buf, size_t len){
  if(len<1) return;
  switch(buf[0]){
    case 0x01:
      if(len==1+FRAME_BYTES){
        lastGallery = -1; haveFrame = true;
        memcpy(framebuf, buf+1, FRAME_BYTES);
        renderFrame();
      }
      break;
    case 0x02: {
      size_t n=(len-1)/5; const uint8_t *p=buf+1;
      for(size_t i=0;i<n;i++,p+=5)
        if(p[0]<80 && p[1]<PANEL_PHY_RES_Y)
          matrix.drawPixel(p[0],p[1],p[2],p[3],p[4]);
      matrix.update();
      break; }
    case 0x03:
      matrix.clear_pixels(); matrix.update();
      break;
    case 0x04:                                   // parlaklik (0-255)
      if(len>=2){ matrix.global_brightness = buf[1]; redrawCurrent(); }
      break;
    case 0x05:                                   // gomulu galeri tablosu sec
      if(len>=2){ lastGallery = buf[1]; drawGallery(buf[1]); }
      break;
    case 0x06:                                   // kanal kazanclari R,G,B (beyaz nokta)
      if(len>=4){
        matrix.gain_r=buf[1]; matrix.gain_g=buf[2]; matrix.gain_b=buf[3];
        Serial.printf("Kazanc R=%u G=%u B=%u\n", buf[1], buf[2], buf[3]);
        redrawCurrent();
      }
      break;
    case 0x07:                                   // kontrast, doygunluk (128 = notr)
      if(len>=3){
        matrix.img_contrast   = buf[1];
        matrix.img_saturation = buf[2];
        redrawCurrent();
      }
      break;
    case 0x08:                                   // mozaik blok boyutu (1=kapali, 2..40)
      if(len>=2){
        mosaicBlock = buf[1] < 1 ? 1 : (buf[1] > 40 ? 40 : buf[1]);
        logf("Mozaik blok: %u", mosaicBlock);
        redrawCurrent();
      }
      break;
    case 0x09:                                   // manuel GitHub OTA tetikle
      otaNowRequested = true;
      logf("GitHub OTA: manuel kontrol istendi...");
      break;
  }
}

// ---- OTA "loading" ekrani: tum paneli kullanan, alttan dolan piksel ilerleme cubugu ----
// Panel surekli DMA ile taranmiyor; her kare update() ile cipin SRAM'ine yazilir ve
// gorunur kalmasi icin refresh() (GCLK) gerekir. Bu yuzden bu fonksiyon kareyi update()
// ile yazar; OTA donguleri arada matrix.refresh() cagirarak paneli yanik tutar.
//   pct 0..100 : dolu turuncu (alt), beyaz ilerleme cizgisi, koyu bos (ust)
static void drawOtaLoading(uint8_t pct){
  if(pct > 100) pct = 100;
  const int W = PANEL_PHY_RES_X, H = PANEL_PHY_RES_Y;   // 80 x 120
  const int fill  = (H * (int)pct) / 100;               // alttan dolu satir sayisi
  const int edgeY = H - fill - 1;                        // ilerleme kenari (parlak)
  for(int y = 0; y < H; y++){
    uint8_t r, g, b;
    if(y >= H - fill){       r = 255; g = 150; b = 30; } // dolu (turuncu)
    else if(y == edgeY){     r = 255; g = 255; b = 255; }// ilerleme cizgisi (beyaz)
    else {                   r = 4;   g = 4;   b = 10; } // bos (koyu)
    for(int x = 0; x < W; x++) matrix.drawPixel((uint8_t)x, (uint8_t)y, r, g, b);
  }
  matrix.update();
  lastOtaActivity = millis();
}

// ---- Index sayfasi: PROGMEM'den parça parça (akitilarak) gönderilir ----
// Eski yöntem (FPSTR ile ~9 KB'lik tek heap String ayirip replace + send) bellek
// baskisi/parçalanma altinda yarim gönderilebiliyordu: gövde (butonlar) görünüyor
// ama sondaki <script> bloğu kesiliyor -> JS parse hatasi -> hiçbir global tanimlanmiyor
// -> "art is not defined", "ws is not defined" gibi inline handler hatalari.
// Burada sayfa dogrudan flash'tan, Content-Length ile, küçük tamponlar halinde
// akitilir (büyük heap ayrimi yok); {{VER}} yer tutucusu uçuşta degistirilir.
static void handleIndex(AsyncWebServerRequest *r){
  const size_t htmlLen = strlen_P(INDEX_HTML);
  size_t phPos = htmlLen;                          // {{VER}} ofseti (bulunamazsa = htmlLen)
  for(size_t i=0; i+7<=htmlLen; i++){
    if(pgm_read_byte(INDEX_HTML+i)  =='{' && pgm_read_byte(INDEX_HTML+i+1)=='{' &&
       pgm_read_byte(INDEX_HTML+i+2)=='V' && pgm_read_byte(INDEX_HTML+i+3)=='E' &&
       pgm_read_byte(INDEX_HTML+i+4)=='R' && pgm_read_byte(INDEX_HTML+i+5)=='}' &&
       pgm_read_byte(INDEX_HTML+i+6)=='}'){ phPos=i; break; }
  }
  const bool   found    = (phPos < htmlLen);
  const size_t verLen   = found ? strlen(FW_VERSION) : 0;         // yer tutucu yoksa ekleme yapma
  const size_t headLen  = phPos;                                  // {{VER}} öncesi
  const size_t tailSrc  = found ? phPos+7 : htmlLen;             // {{VER}} sonrasi kaynak
  const size_t tailLen  = htmlLen - tailSrc;
  const size_t totalLen = headLen + verLen + tailLen;

  AsyncWebServerResponse *res = r->beginResponse("text/html; charset=utf-8", totalLen,
    [headLen,verLen,tailSrc,tailLen,totalLen](uint8_t *buf, size_t maxLen, size_t index) -> size_t {
      if(index >= totalLen) return 0;
      if(index < headLen){                                        // bölge 1: head (flash)
        size_t n = headLen - index; if(n>maxLen) n=maxLen;
        memcpy_P(buf, INDEX_HTML + index, n); return n;
      }
      if(index < headLen + verLen){                              // bölge 2: versiyon (RAM)
        size_t off = index - headLen, n = verLen - off; if(n>maxLen) n=maxLen;
        memcpy(buf, FW_VERSION + off, n); return n;
      }
      size_t off = index - headLen - verLen, n = tailLen - off;  // bölge 3: tail (flash)
      if(n>maxLen) n=maxLen;
      memcpy_P(buf, INDEX_HTML + tailSrc + off, n); return n;
    });
  res->addHeader("Cache-Control", "no-store");
  r->send(res);
}

void setup(){
  Serial.begin(115200); delay(1000);
  esp_task_wdt_deinit();
  esp_log_level_set("task_wdt", ESP_LOG_NONE);   // seri portu bogan TWDT spam'ini sustur
  // PSRAM durumu
  if(psramFound()){
    logf("PSRAM bulundu: %u KB toplam, %u KB bos", ESP.getPsramSize()/1024, ESP.getFreePsram()/1024);
  } else {
    logf("UYARI: PSRAM bulunamadi!");
  }
  esp_log_level_set("task_wdt", ESP_LOG_NONE);   // seri portu bogan TWDT spam'ini sustur
  matrix.initMatrix(); delay(10);
  drawGallery(0);                                // acilis ekrani (Mona Lisa)

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  esp_wifi_set_ps(WIFI_PS_NONE);
  // Oncelik: NVS (AP modunda kaydedilmis) → derlenmis sabit → AP provisioning
  prefs.begin("wificfg", true);
  String nvsSsid = prefs.getString("ssid", "");
  String nvsPass = prefs.getString("pass", "");
  prefs.end();
  bool wifiOk = false;
  if(nvsSsid.length() > 0){
    Serial.printf("NVS: %s deneniyor\n", nvsSsid.c_str());
    WiFi.begin(nvsSsid.c_str(), nvsPass.c_str());
    for(int i=0;i<30&&WiFi.status()!=WL_CONNECTED;i++) delay(500);
    wifiOk = WiFi.status()==WL_CONNECTED;
    if(!wifiOk){ WiFi.disconnect(true); delay(200); }
  }
  if(!wifiOk){
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    for(int i=0;i<60&&WiFi.status()!=WL_CONNECTED;i++){ delay(500); Serial.print("."); }
    wifiOk = WiFi.status()==WL_CONNECTED;
  }
  if(!wifiOk) runAPProvisioning();   // NVS'e kaydeder, ESP.restart() yapar, geri donmez
  if(wifiOk){
    logf("MagPanel %s (build %d) | IP: %s", FW_VERSION, FW_BUILD, WiFi.localIP().toString().c_str());
    if(MDNS.begin(MDNS_HOSTNAME)){
      MDNS.addService("http","tcp",80);
      MDNS.addService("magpanel","tcp",80);      // iOS Bonjour kesfi icin
      logf("mDNS: http://%s.local", MDNS_HOSTNAME);
    }
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);
    server.on("/", HTTP_GET, handleIndex);   // PROGMEM'den akitilir (truncation'a karşi sağlam)

    // ---- Tarayicidan OTA: http://magpanel.local/update (kullanici: admin) ----
    server.on("/update", HTTP_GET, [](AsyncWebServerRequest *r){
      if(!r->authenticate("admin", OTA_PASSWORD)) return r->requestAuthentication();
      r->send(200,"text/html",
        "<form method=POST enctype=multipart/form-data>"
        "<h3>MagPanel firmware guncelle - mevcut: " FW_VERSION "</h3>"
        "<input type=file name=fw accept=.bin> <input type=submit value=Yukle></form>");
    });
    server.on("/update", HTTP_POST,
      [](AsyncWebServerRequest *r){
        bool ok = !Update.hasError();
        AsyncWebServerResponse *res = r->beginResponse(200,"text/plain",
            ok ? "OK - yeniden baslatiliyor" : "HATA");
        res->addHeader("Connection","close");
        r->send(res);
        if(ok){ delay(300); ESP.restart(); }
      },
      [](AsyncWebServerRequest *r, String fn, size_t index, uint8_t *data, size_t len, bool final){
        if(!r->authenticate("admin", OTA_PASSWORD)) return;
        static int lastPct = -1;
        if(index==0){
          Serial.printf("OTA basliyor: %s\n", fn.c_str());
          otaActive = true;                 // ana dongu paneli birsin; ekrani biz surecegiz
          ws.closeAll(); ws.enable(false);
          Update.begin(UPDATE_SIZE_UNKNOWN);
          lastPct = -1; drawOtaLoading(0);
        }
        if(len) Update.write(data, len);
        size_t total = r->contentLength();              // multipart toplam (firmware'den biraz buyuk)
        int pct = total ? (int)((uint64_t)(index+len) * 100 / total) : 0;
        if(pct != lastPct){ drawOtaLoading((uint8_t)pct); for(int k=0;k<6;k++) matrix.refresh(); lastPct = pct; }
        if(final){
          bool ok = Update.end(true);
          Serial.println(ok ? "OTA bitti" : "OTA HATA");
          if(ok){ drawOtaLoading(100); for(int k=0;k<40;k++) matrix.refresh(); }
          else  { otaActive = false; }                  // basarisizsa paneli geri ver
        }
      });

    server.begin();
    delay(300);
    // AsyncTCP gorevi dogdu mu? (dahili RAM sikisikliginda basarisiz olabiliyor)
    if(xTaskGetHandle("async_tcp")==NULL){
      Serial.println("HATA: AsyncTCP gorevi baslamadi - 2sn sonra yeniden deneniyor");
      delay(2000); ESP.restart();
    }
    logf("HTTP + WS sunucu hazir");

    // ---- PlatformIO OTA (espota) ----
    ArduinoOTA.setHostname(MDNS_HOSTNAME);
    ArduinoOTA.setPassword(OTA_PASSWORD);
    ArduinoOTA.onStart([](){
      Serial.println("OTA (espota) basliyor - panel ve sunucu duraklatiliyor");
      otaActive = true;
      ws.closeAll();        // async WS trafigi OTA'yi bozar (broken pipe nedeni)
      ws.enable(false);
      server.end();         // async sunucuyu tamamen durdur
    });
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total){
      uint8_t pct = total ? (uint8_t)((uint64_t)progress * 100 / total) : 0;
      drawOtaLoading(pct);
      for(int k=0;k<10;k++) matrix.refresh();   // kareyi kisa sure goster
    });
    ArduinoOTA.onEnd([](){ Serial.println("OTA tamam, restart"); });
    ArduinoOTA.onError([](ota_error_t e){ otaActive=false; Serial.printf("OTA hata: %u\n", e); });
    ArduinoOTA.begin();
  } else Serial.println("\nWiFi BASARISIZ");
}

// GitHub'taki son CI build'ini kontrol et; daha yeniyse indir, kur, yeniden basla.
void checkGithubOTA(){
  if(FW_BUILD == 0) return;  // local build (USB flash) - OTA atlandi
  if(String(GITHUB_OTA_BASE).indexOf("KULLANICI")>=0) return;  // repo henuz ayarlanmamis
  WiFiClientSecure cl; cl.setInsecure();
  HTTPClient http; http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  http.setConnectTimeout(8000);
  if(!http.begin(cl, String(GITHUB_OTA_BASE) + "/version.txt")) return;
  if(http.GET()!=200){ http.end(); return; }
  int remote = http.getString().toInt();
  http.end();
  if(remote <= FW_BUILD){ logf("GitHub OTA: guncel (build %d)", FW_BUILD); return; }

  logf("GitHub OTA: build %d -> %d, indiriliyor...", FW_BUILD, remote);
  otaActive = true;            // panel taramasi ve sunucu durur (espota ile ayni disiplin)
  ws.closeAll(); ws.enable(false); server.end();

  WiFiClientSecure c2; c2.setInsecure();
  HTTPClient h2; h2.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  h2.setConnectTimeout(8000);
  bool ok=false;
  if(h2.begin(c2, String(GITHUB_OTA_BASE) + "/firmware.bin") && h2.GET()==200){
    int total = h2.getSize();
    if(Update.begin(total>0 ? (size_t)total : UPDATE_SIZE_UNKNOWN)){
      // Akarken yaz: her parcada ilerleme cubugunu guncelle, arada refresh() ile
      // paneli yanik tut (writeStream tek blokta yazip ekrani karanlik birakirdi).
      WiFiClient *stream = h2.getStreamPtr();
      uint8_t  buf[1024];
      size_t   written = 0;
      int      lastPct = -1;
      uint32_t lastData = millis();
      drawOtaLoading(0);                                   // bos cubuk + panel yanik
      while(h2.connected() && (total<=0 || written < (size_t)total)){
        size_t avail = stream->available();
        if(avail){
          int n = stream->readBytes(buf, avail > sizeof(buf) ? sizeof(buf) : avail);
          if(n > 0){
            Update.write(buf, (size_t)n);
            written += (size_t)n;
            lastData = millis();
            int pct = total>0 ? (int)(written * 100 / (size_t)total)
                              : (int)((millis()/40) % 101);   // boyut bilinmiyorsa sweep
            if(pct != lastPct){ drawOtaLoading((uint8_t)pct); lastPct = pct; }
          }
        }
        matrix.refresh();                                  // her dongude GCLK -> panel yanik
        if(millis() - lastData > 15000) break;             // 15 sn veri yoksa iptal
        yield();                                           // TCP/WiFi yiginina nefes aldir
      }
      ok = (total<=0 || written == (size_t)total) && Update.end(true);
      if(ok){ drawOtaLoading(100); for(int k=0;k<40;k++) matrix.refresh(); }
    }
  }
  logf(ok ? "GitHub OTA tamam, yeniden baslatiliyor" : "GitHub OTA basarisiz");
  delay(300); ESP.restart();   // basarisizsa da restart: sunucu kapali, temiz baslangic
}

void loop(){
  if(otaActive){            // OTA sirasinda SADECE OTA calisir:
    ArduinoOTA.handle();    // panel taramasi ve WS islemleri durur,
    // Async (web/espota) OTA yarida kesilirse takilip kalmasin: 30 sn ilerleme
    // yoksa paneli geri al. (checkGithubOTA senkron calisir, restart ile biter.)
    if(lastOtaActivity && millis()-lastOtaActivity > 30000){ otaActive=false; ws.enable(true); redrawCurrent(); }
    return;                 // flash yazimi kesintisiz tamamlanir
  }
  matrix.refresh();
  yield();                  // WiFi/TCP-IP yiginina CPU birak (ARP/ping cevaplari icin sart)
  ArduinoOTA.handle();
  // ---- gecici ag teshisi: 5 sn'de bir baglanti durumu ----
  static uint32_t dbg=0;
  if(millis()-dbg>5000){
    dbg=millis();
    logf("[NET] heap=%u min=%u blok=%u RSSI=%d",
      ESP.getFreeHeap(), ESP.getMinFreeHeap(), ESP.getMaxAllocHeap(), WiFi.RSSI());
  }
  if(msgReady){ handleMessage(rxbuf,(size_t)msgLen); msgReady=false; }
  static uint32_t t=0;
  if(millis()-t>2000){ ws.cleanupClients(); t=millis(); }
  // WiFi bekcisi: kopussa yeniden bagla, 60sn duzelmezse temiz baslangic
  static uint32_t wifiDownSince=0;
  if(WiFi.status()!=WL_CONNECTED){
    if(!wifiDownSince) wifiDownSince=millis();
    static uint32_t lastTry=0;
    if(millis()-lastTry>10000){ lastTry=millis(); WiFi.reconnect(); }
    if(millis()-wifiDownSince>60000) ESP.restart();
  } else wifiDownSince=0;

  if(otaNowRequested && WiFi.status()==WL_CONNECTED && !otaActive){
    otaNowRequested=false; checkGithubOTA();
  }
}
