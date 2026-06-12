/* FM6363C 80x120 v17 - WiFi + WebSocket sunucu
   Protokol (binary WS, ilk bayt opcode):
     0x04 + 1B     : global parlaklik (0-255)
     0x05 + 1B     : gomulu galeri tablosu (0..GALLERY_COUNT-1)
     0x06 + 3B     : kanal kazanclari R,G,B (beyaz nokta kalibrasyonu)
     0x07 + 2B     : kontrast, doygunluk (128 = notr)
     0x01 + 28800B : tam kare RGB888 (satir-major, y0:x0..79)
     0x02 + N*5B   : piksel paketi (x,y,r,g,b)
     0x03          : temizle
   Acilista Mona gosterilir; IP seri porta yazilir; http://magpanel.local
   uzerinden gomulu test sayfasi acilir (iOS app ayni protokolu konusur). */
#include <WiFi.h>
#include <ESPmDNS.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoOTA.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <Update.h>
#include <Matrix.h>
#include "gallery.h"
#include "wifi_config.h"
#include "web_page.h"

Matrix matrix;
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");
static int8_t lastGallery = 0;   // kazanc degisince yeniden cizim icin
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
  const uint8_t *p=framebuf;
  for(int y=0;y<PANEL_PHY_RES_Y;y++)for(int x=0;x<80;x++,p+=3)
    matrix.drawPixel((uint8_t)x,(uint8_t)y,p[0],p[1],p[2]);
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
  const uint8_t *art=GALLERY_DATA[idx];
  matrix.clear_pixels();
  for(int y=0;y<PANEL_PHY_RES_Y;y++)for(int x=0;x<80;x++){
    int i=(y*80+x)*3;
    matrix.drawPixel((uint8_t)x,(uint8_t)y,art[i],art[i+1],art[i+2]);
  }
  matrix.update();
  Serial.printf("Galeri: %s\n", GALLERY_NAMES[idx]);
}

void onWsEvent(AsyncWebSocket*, AsyncWebSocketClient *client, AwsEventType type,
               void *arg, uint8_t *data, size_t len){
  if(type==WS_EVT_CONNECT){ Serial.printf("WS istemci #%u baglandi\n", client->id()); return; }
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
  }
}

void setup(){
  Serial.begin(115200); delay(1000);
  esp_task_wdt_deinit();
  matrix.initMatrix(); delay(10);
  drawGallery(0);                                // acilis ekrani (Mona Lisa)

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  WiFi.setSleep(false);                          // guc tasarrufu kapali: 200ms ping ve gecikme duzelir
  Serial.print("WiFi baglaniyor");
  for(int i=0;i<60 && WiFi.status()!=WL_CONNECTED;i++){ delay(500); Serial.print("."); }
  if(WiFi.status()==WL_CONNECTED){
    Serial.printf("\nMagPanel %s (build %d) | IP: %s\n", FW_VERSION, FW_BUILD, WiFi.localIP().toString().c_str());
    if(MDNS.begin(MDNS_HOSTNAME)){
      MDNS.addService("http","tcp",80);
      MDNS.addService("magpanel","tcp",80);      // iOS Bonjour kesfi icin
      Serial.printf("mDNS: http://%s.local\n", MDNS_HOSTNAME);
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
    Serial.println("HTTP + WS sunucu hazir");

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
  } else Serial.println("\nWiFi BASARISIZ - wifi_config.h kontrol et");
}

// GitHub'taki son CI build'ini kontrol et; daha yeniyse indir, kur, yeniden basla.
void checkGithubOTA(){
  if(String(GITHUB_OTA_BASE).indexOf("KULLANICI")>=0) return;  // repo henuz ayarlanmamis
  WiFiClientSecure cl; cl.setInsecure();
  HTTPClient http; http.setFollowRedirects(HTTPC_STRICT_FOLLOW_REDIRECTS);
  http.setConnectTimeout(8000);
  if(!http.begin(cl, String(GITHUB_OTA_BASE) + "/version.txt")) return;
  if(http.GET()!=200){ http.end(); return; }
  int remote = http.getString().toInt();
  http.end();
  if(remote <= FW_BUILD) return;

  Serial.printf("GitHub OTA: build %d -> %d, indiriliyor...\n", FW_BUILD, remote);
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
  Serial.println(ok ? "GitHub OTA tamam, yeniden baslatiliyor" : "GitHub OTA basarisiz");
  delay(300); ESP.restart();   // basarisizsa da restart: sunucu kapali, temiz baslangic
}

void loop(){
  if(otaActive){            // OTA sirasinda SADECE OTA calisir:
    ArduinoOTA.handle();    // panel taramasi ve WS islemleri durur,
    return;                 // flash yazimi kesintisiz tamamlanir
  }
  matrix.refresh();
  ArduinoOTA.handle();
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
     && WiFi.status()==WL_CONNECTED && ESP.getFreeHeap()>60000){
    lastChk=up; checkGithubOTA();
  }
#endif
}
