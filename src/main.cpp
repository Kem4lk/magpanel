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
    for(int y=0;y<PANEL_PHY_RES_Y;y++)for(int x=0;x<80;x++,p+=3)
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
  matrix.update();
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
  }
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
    server.on("/",HTTP_GET,[](AsyncWebServerRequest *r){
      String page = FPSTR(INDEX_HTML);
      page.replace("{{VER}}", FW_VERSION);
      r->send(200,"text/html",page);
    });

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
        if(index==0){ Serial.printf("OTA basliyor: %s\n", fn.c_str());
                      Update.begin(UPDATE_SIZE_UNKNOWN); }
        if(len) Update.write(data, len);
        if(final){ Update.end(true); Serial.println("OTA bitti"); }
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
    ArduinoOTA.onEnd([](){ Serial.println("OTA tamam, restart"); });
    ArduinoOTA.onError([](ota_error_t e){ Serial.printf("OTA hata: %u\n", e); });
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
  if(remote <= FW_BUILD) return;

  logf("GitHub OTA: build %d -> %d, indiriliyor...", FW_BUILD, remote);
  otaActive = true;            // panel taramasi ve sunucu durur (espota ile ayni disiplin)
  ws.closeAll(); ws.enable(false); server.end();

  WiFiClientSecure c2; c2.setInsecure();
  HTTPClient h2; h2.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  h2.setConnectTimeout(8000);
  bool ok=false;
  if(h2.begin(c2, String(GITHUB_OTA_BASE) + "/firmware.bin") && h2.GET()==200){
    int len = h2.getSize();
    if(Update.begin(len>0 ? (size_t)len : UPDATE_SIZE_UNKNOWN)){
      Update.writeStream(*h2.getStreamPtr());
      ok = Update.end(true);
    }
  }
  logf(ok ? "GitHub OTA tamam, yeniden baslatiliyor" : "GitHub OTA basarisiz");
  delay(300); ESP.restart();   // basarisizsa da restart: sunucu kapali, temiz baslangic
}

void loop(){
  if(otaActive){            // OTA sirasinda SADECE OTA calisir:
    ArduinoOTA.handle();    // panel taramasi ve WS islemleri durur,
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

#if GITHUB_AUTO_OTA
  static uint32_t lastChk=0;
  uint32_t up=millis();
  if(((lastChk==0 && up>30000) || (lastChk && up-lastChk>300000))
     && WiFi.status()==WL_CONNECTED && ESP.getFreeHeap()>15000){
    lastChk=up; checkGithubOTA();
  }
#endif
}
