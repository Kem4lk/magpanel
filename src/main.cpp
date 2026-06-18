/* FM6363C 80x120 v17 - WiFi + WebSocket sunucu
   Protokol (binary WS, ilk bayt opcode):
     0x04 + 1B     : global parlaklik (0-255)
     0x05 + 1B     : gomulu galeri tablosu (0..GALLERY_COUNT-1)
     0x06 + 3B     : kanal kazanclari R,G,B (beyaz nokta kalibrasyonu)
     0x07 + 2B     : kontrast, doygunluk (128 = notr)
     0x0E + 1B     : blur kademesi (0=kapalı, 1=2x2, idx≥2 → (2*idx-1) kenarlı box blur, maks 12 = 23x23)
     0x08 + 1B     : mozaik blok boyutu (1=kapali, 2..40)
     0x01 + 28800B : tam kare RGB888 (satir-major, y0:x0..79)
     0x02 + N*5B   : piksel paketi (x,y,r,g,b)
     0x03          : temizle
     0x0A + 1B     : canli DCLK bolen (flicker tuner)
     0x0B + 1B[+N] : uygulama sec (0=kapat,1=saat,2=timer[+2B sn],3=hava,4=dunyakupasi,5=spotify)
     0x0C + 8B[+s] : hava konumu lat(f32 LE),lon(f32 LE),sehir
     0x0D + s      : Spotify access token (tarayici PKCE)
     0x0F          : flicker self-test baslat/durdur (panelde otomatik desen dizisi)
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
#include "apps.h"

Matrix matrix;
Apps   apps;                       // firmware-tarafi uygulamalar (saat/timer/hava/dunya kupasi/spotify)
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
// Galeri isimlerini WS metin frame'i olarak gonder ("G:" onekli JSON dizi).
// Boylece tarayici ayri bir /api/gallery HTTP baglantisi acmaz (dusuk heap'te
// yeni TCP soketi ayrilamayip ERR_TIMED_OUT olmasini onler); zaten acik olan
// WebSocket uzerinden gelir.
static void sendGallery(AsyncWebSocketClient *c){
  String j = "G:[";
  for(int i=0; i<GALLERY_COUNT; i++){
    if(i) j += ",";
    j += "\""; j += GALLERY_NAMES[i]; j += "\"";
  }
  j += "]";
  c->text(j);
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

// framebuf'tan (x,y) pikselinin blur uygulanmis rengini dondurur.
// img_blur bir kademe indeksidir: 0=kapalı, 1=2x2, idx≥2 → yarıçap=idx-1
// simetrik box blur ((2*idx-1) kenarlı). Maks 12 (23x23). 2x2 asimetrik
// (piksel + sağ + alt + sağ-alt), digerleri simetrik box blur.
static inline void blurredPixel(int x, int y, uint8_t &ro, uint8_t &go, uint8_t &bo){
  int idx = matrix.img_blur;
  if(idx == 0){
    const uint8_t *p = framebuf + (y*80+x)*3;
    ro=p[0]; go=p[1]; bo=p[2]; return;
  }
  int x0,x1,y0,y1;
  if(idx == 1){                 // 2x2: piksel + sağ + alt + sağ-alt
    x0 = x;     x1 = x+1;
    y0 = y;     y1 = y+1;
  } else {                      // simetrik box blur, yarıçap = idx-1
    int r = idx - 1;
    x0 = x-r;   x1 = x+r;
    y0 = y-r;   y1 = y+r;
  }
  uint32_t sr=0,sg=0,sb=0,cnt=0;
  for(int ny=y0; ny<=y1; ny++){
    int cy = ny<0 ? 0 : (ny>=PANEL_PHY_RES_Y ? PANEL_PHY_RES_Y-1 : ny);
    for(int nx=x0; nx<=x1; nx++){
      int cx = nx<0 ? 0 : (nx>=80 ? 79 : nx);
      const uint8_t *q = framebuf + (cy*80+cx)*3;
      sr+=q[0]; sg+=q[1]; sb+=q[2]; cnt++;
    }
  }
  ro=(uint8_t)(sr/cnt); go=(uint8_t)(sg/cnt); bo=(uint8_t)(sb/cnt);
}

void renderFrame(){
  uint8_t b = mosaicBlock < 1 ? 1 : mosaicBlock;
  if(b == 1){
    // Doldurma (drawPixel) saf CPU ve hizli (~1ms). Araya refresh() koymak
    // onceki kareyi parlak gosterip update()'in 30ms'lik dim sweep'iyle KONTRAST
    // yaratiyordu (flicker'i artiriyordu) + kare hizini dusuruyordu. Kaldirildi:
    // sadece doldur, sonra tek update().
    for(int y=0;y<PANEL_PHY_RES_Y;y++)
      for(int x=0;x<80;x++){
        uint8_t r,g,bl; blurredPixel(x,y,r,g,bl);
        matrix.drawPixel((uint8_t)x,(uint8_t)y,r,g,bl);
      }
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

// ===================== FLICKER SELF-TEST (opcode 0x0F) =====================
// Panelin flicker karakterini bir VIDEO ile teshis/kalibre etmek icin otomatik
// desen dizisi. Her faz panelin SOL-UST kosesine "Pxx kod" etiketi cizer (videoda
// hangi fazda oldugumuzu okuruz) ve web LOG'a faz adini yazar.
//   * STATIK fazlar TEK kare cizilir: surekli circular-DMA paneli flicker'siz
//     tutar -> goz/kamera SADECE saf refresh / PWM (dusuk-duty) flicker'ini ve
//     guc cokmesini gorur (update() basina olusan dim-sweep KARISMAZ).
//   * HAREKETLI fazlar her tik (~25fps) yeniden cizilir -> her update()'in
//     dim-sweep'i, yani ANIMASYON flicker'i gorunur.
//   * DCLK-SWEEP fazlari boleni 80..16 gezer (UI tuner kademeleri). Videodan
//     en az flicker + henuz mozaik/bozulma BASLAMAMIS kademe secilir = kalibrasyon.
// Test sirasinda goruntu hatti notr'e cekilir (kontrast/doygunluk/kazanc/mozaik/
// blur sifirlanir) ki sonuc kalintı ayarlardan etkilenmesin; bitince hepsi +
// DCLK boleni geri yuklenir.
enum { FT_SOLID, FT_HGRAD, FT_VGRAD, FT_HALVES, FT_HLINES, FT_VLINES,
       FT_CHECKER, FT_DIAG, FT_BLINK, FT_SCROLL, FT_PULSE };
struct FtPhase { uint16_t dur; uint8_t kind; uint8_t bright; uint8_t div;
                 uint8_t a, b, c; const char *code; };
// dur(ms), kind, bright(0=baz 160), div(0=baz/NVS), a,b,c(renk/param), etiket
static const FtPhase FT_SEQ[] = {
  {4000, FT_BLINK,   0,   0, 255,255,255, "BLINK2Hz"},  // zaman referansi (videodaki fps dogrulama)
  {2500, FT_SOLID,   0,   0, 255,255,255, "WHT"},       // saf beyaz (refresh + guc)
  {2500, FT_SOLID,   0,   0, 255,  0,  0, "RED"},
  {2500, FT_SOLID,   0,   0,   0,255,  0, "GRN"},
  {2500, FT_SOLID,   0,   0,   0,  0,255, "BLU"},
  {2500, FT_SOLID,   0,   0, 128,128,128, "GRY128"},
  {2500, FT_SOLID,   0,   0,  48, 48, 48, "GRY48"},     // dusuk-duty PWM flicker
  {2500, FT_SOLID,   0,   0,  16, 16, 16, "GRY16"},     // cok dusuk-duty (en zor)
  {2500, FT_SOLID, 255,   0, 255,255,255, "WHT-MAX"},   // tam guc -> brownout/sag testi
  {2500, FT_HGRAD,   0,   0,   0,  0,  0, "HGRAD"},      // yatay gradyan -> kolon/DCLK bant
  {2500, FT_VGRAD,   0,   0,   0,  0,  0, "VGRAD"},      // dikey gradyan -> satir bant
  {2500, FT_HALVES,  0,   0,   0,  0,  0, "HALVES"},     // ust/alt yari (iki-tarama siniri)
  {2500, FT_HLINES,  0,   0,   1,  0,  0, "HLINES"},     // 1px yatay cizgi -> satir flicker yukseltici
  {2500, FT_VLINES,  0,   0,   1,  0,  0, "VLINES"},     // 1px dikey cizgi -> DCLK yukseltici
  {2500, FT_CHECKER, 0,   0,   2,  0,  0, "CHECK2"},
  {2500, FT_DIAG,    0,  80,   0,  0,  0, "d80"},        // ---- DCLK sweep: ~2.0 MHz
  {2500, FT_DIAG,    0,  64,   0,  0,  0, "d64"},        //      ~2.5 MHz (varsayilan)
  {2500, FT_DIAG,    0,  53,   0,  0,  0, "d53"},        //      ~3.0
  {2500, FT_DIAG,    0,  46,   0,  0,  0, "d46"},        //      ~3.5
  {2500, FT_DIAG,    0,  40,   0,  0,  0, "d40"},        //      ~4.0
  {2500, FT_DIAG,    0,  36,   0,  0,  0, "d36"},        //      ~4.5
  {2500, FT_DIAG,    0,  32,   0,  0,  0, "d32"},        //      ~5.0
  {2500, FT_DIAG,    0,  27,   0,  0,  0, "d27"},        //      ~6.0
  {2500, FT_DIAG,    0,  23,   0,  0,  0, "d23"},        //      ~7.0
  {2500, FT_DIAG,    0,  20,   0,  0,  0, "d20"},        //      ~8.0
  {2500, FT_DIAG,    0,  18,   0,  0,  0, "d18"},        //      ~8.9
  {2500, FT_DIAG,    0,  16,   0,  0,  0, "d16"},        //      ~10.0 MHz (videoda temiz cikti)
  {2500, FT_DIAG,    0,  14,   0,  0,  0, "d14"},        //      ~11.4 (deneysel >10MHz)
  {2500, FT_DIAG,    0,  12,   0,  0,  0, "d12"},        //      ~13.3
  {2500, FT_DIAG,    0,  10,   0,  0,  0, "d10"},        //      ~16.0
  {2500, FT_DIAG,    0,   8,   0,  0,  0, "d8"},         //      ~20.0 MHz (mozaik beklenir = ust sinir)
  {4000, FT_SCROLL,  0,   0,   0,  0,  0, "SCROLL"},     // ---- hareket: kayan cubuk
  {4000, FT_PULSE,   0,   0,   0,  0,  0, "PULSE"},      //      ekran nabzi (update dim-sweep)
};
static const int     FT_COUNT       = sizeof(FT_SEQ)/sizeof(FT_SEQ[0]);
static const uint8_t FT_BASE_BRIGHT = 160;             // sweep/desenler icin sabit parlaklik

static bool     ftActive     = false;
static int      ftPhase      = 0;
static uint32_t ftPhaseStart = 0;
static bool     ftDrawn      = false;                  // mevcut faz cizildi mi (statik = bir kez)
static uint32_t ftLastTick   = 0;                      // hareketli faz son cizim ms
static uint32_t ftBlinkSub   = 0;                      // BLINK 500ms alt-faz sayaci
// bitince geri yuklenecek anlik ayarlar
static uint8_t  ftSvBr, ftSvGr, ftSvGg, ftSvGb, ftSvCon, ftSvSat, ftSvBlur, ftSvMz;
static uint32_t ftSvDiv = 64;

static void ftLabel(int idx){
  char lab[16]; snprintf(lab, sizeof(lab), "P%02d %s", idx, FT_SEQ[idx].code);
  int w = (int)strlen(lab)*6 + 2; if(w > 80) w = 80;
  for(int y=0;y<9;y++) for(int x=0;x<w;x++) matrix.drawPixel((uint8_t)x,(uint8_t)y,0,0,0); // okunur kalsin diye siyah kutu
  matrix.setTextSize(1);
  matrix.setTextColor(0xFFFF);                         // beyaz (565)
  matrix.setCursor(1,1);
  matrix.print(lab);
}

static void ftDraw(int idx, uint32_t elapsed){
  const FtPhase &ph = FT_SEQ[idx];
  const int H = PANEL_PHY_RES_Y;                       // 120
  switch(ph.kind){
    case FT_SOLID:
      for(int y=0;y<H;y++) for(int x=0;x<80;x++) matrix.drawPixel(x,y,ph.a,ph.b,ph.c);
      break;
    case FT_HGRAD:
      for(int y=0;y<H;y++) for(int x=0;x<80;x++){ uint8_t v=(uint8_t)(x*255/79); matrix.drawPixel(x,y,v,v,v); }
      break;
    case FT_VGRAD:
      for(int y=0;y<H;y++){ uint8_t v=(uint8_t)(y*255/(H-1)); for(int x=0;x<80;x++) matrix.drawPixel(x,y,v,v,v); }
      break;
    case FT_HALVES:
      for(int y=0;y<H;y++){ uint8_t v=(y<H/2)?255:0; for(int x=0;x<80;x++) matrix.drawPixel(x,y,v,v,v); }
      break;
    case FT_HLINES:
      for(int y=0;y<H;y++){ uint8_t v=(y&1)?0:255; for(int x=0;x<80;x++) matrix.drawPixel(x,y,v,v,v); }
      break;
    case FT_VLINES:
      for(int y=0;y<H;y++) for(int x=0;x<80;x++){ uint8_t v=(x&1)?0:255; matrix.drawPixel(x,y,v,v,v); }
      break;
    case FT_CHECKER:{ int s=ph.a<1?1:ph.a;
      for(int y=0;y<H;y++) for(int x=0;x<80;x++){ uint8_t v=(((x/s)+(y/s))&1)?255:0; matrix.drawPixel(x,y,v,v,v); }
      break; }
    case FT_DIAG:                                      // kosegen gradyan: hem satir hem kolon degiskeni
      for(int y=0;y<H;y++) for(int x=0;x<80;x++){       // -> mozaik (16px blok) ANINDA gorunur, ortalama parlak -> flicker da gorunur
        uint8_t v=(uint8_t)(((x*255/79)+(y*255/(H-1)))/2); matrix.drawPixel(x,y,v,v,v); }
      break;
    case FT_BLINK:{ bool on=((elapsed/500)&1)==0;
      uint8_t r=on?ph.a:0,g=on?ph.b:0,b=on?ph.c:0;
      for(int y=0;y<H;y++) for(int x=0;x<80;x++) matrix.drawPixel(x,y,r,g,b);
      break; }
    case FT_SCROLL:{ int bar=(int)((elapsed/40)%H);    // 8px parlak cubuk asagi kayar
      for(int y=0;y<H;y++){ int d=y-bar; if(d<0)d+=H; uint8_t v=(d<8)?255:8;
        for(int x=0;x<80;x++) matrix.drawPixel(x,y,v,v,v); }
      break; }
    case FT_PULSE:{ uint32_t t=elapsed%2000;           // 2sn ucgen nabiz 20..250 (float yok)
      int tri = t<1000 ? (int)(t*230/1000) : (int)((2000-t)*230/1000);
      uint8_t v=(uint8_t)(20+tri);
      for(int y=0;y<H;y++) for(int x=0;x<80;x++) matrix.drawPixel(x,y,v,v,v);
      break; }
  }
  ftLabel(idx);
  matrix.update();
}

static void ftStop(){
  if(!ftActive) return;
  ftActive = false;
  matrix.global_brightness = ftSvBr;                   // anlik ayarlari geri yukle
  matrix.gain_r = ftSvGr; matrix.gain_g = ftSvGg; matrix.gain_b = ftSvGb;
  matrix.img_contrast = ftSvCon; matrix.img_saturation = ftSvSat; matrix.img_blur = ftSvBlur;
  mosaicBlock = ftSvMz;
  matrix.setClockDiv(ftSvDiv);                         // DCLK boleni geri (sweep'ten cikis)
  logf("FLICKER-TEST bitti (DCLK bolen=%lu geri yuklendi)", (unsigned long)ftSvDiv);
  redrawCurrent();                                     // test oncesi icerige don
}

static void ftStart(){
  apps.off();                                          // uygulama testi ezmesin
  ftSvBr=matrix.global_brightness;
  ftSvGr=matrix.gain_r; ftSvGg=matrix.gain_g; ftSvGb=matrix.gain_b;
  ftSvCon=matrix.img_contrast; ftSvSat=matrix.img_saturation; ftSvBlur=matrix.img_blur;
  ftSvMz=mosaicBlock;
  prefs.begin("panelcfg", true); ftSvDiv = prefs.getUInt("dclkdiv", 64); prefs.end();
  if(ftSvDiv<8 || ftSvDiv>200) ftSvDiv=64;
  // goruntu hattini notr'e cek (kalinti ayarlar testi bozmasin)
  matrix.img_contrast=128; matrix.img_saturation=128; matrix.img_blur=0; mosaicBlock=1;
  matrix.gain_r=255; matrix.gain_g=255; matrix.gain_b=255;
  matrix.global_brightness=FT_BASE_BRIGHT;
  ftActive=true; ftPhase=0; ftPhaseStart=millis(); ftDrawn=false; ftLastTick=0; ftBlinkSub=0;
  logf("FLICKER-TEST basladi: %d faz, ~87sn. Paneli videoya cek; sol-ust 'Pxx' etiketi fazi soyler.", FT_COUNT);
  logf("FT P00 %s", FT_SEQ[0].code);
}

// loop()'tan cagrilir; aktifse fazlari millis() ile ilerletir.
static void ftLoop(){
  if(!ftActive) return;
  const FtPhase &ph = FT_SEQ[ftPhase];
  uint32_t now = millis();
  uint32_t elapsed = now - ftPhaseStart;
  if(!ftDrawn){                                        // faz girisi: override'lari uygula + ciz
    matrix.global_brightness = ph.bright ? ph.bright : FT_BASE_BRIGHT;
    matrix.setClockDiv(ph.div ? ph.div : ftSvDiv);
    ftDraw(ftPhase, elapsed);
    ftDrawn=true; ftLastTick=now; ftBlinkSub=elapsed/500;
  } else if(ph.kind==FT_SCROLL || ph.kind==FT_PULSE){  // hareket: ~25fps yeniden ciz (update dim-sweep gorunsun)
    if(now-ftLastTick >= 40){ ftDraw(ftPhase, elapsed); ftLastTick=now; }
  } else if(ph.kind==FT_BLINK){                        // sadece 500ms gecisinde yeniden ciz (temiz blink)
    uint32_t sub=elapsed/500;
    if(sub != ftBlinkSub){ ftBlinkSub=sub; ftDraw(ftPhase, elapsed); }
  }
  if(elapsed >= ph.dur){                               // sonraki faz
    ftPhase++;
    if(ftPhase >= FT_COUNT){ logf("FT dizi tamam"); ftStop(); return; }
    ftPhaseStart=now; ftDrawn=false;
    logf("FT P%02d %s", ftPhase, FT_SEQ[ftPhase].code);
  }
}

void onWsEvent(AsyncWebSocket*, AsyncWebSocketClient *client, AwsEventType type,
               void *arg, uint8_t *data, size_t len){
  if(type==WS_EVT_CONNECT){ logf("WS istemci #%u baglandi", client->id()); sendLogHistory(client); sendGallery(client); return; }
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
  if(ftActive && buf[0]!=0x0F) ftStop();   // flicker testi aktifken baska komut gelirse testi durdur
  switch(buf[0]){
    case 0x01:
      if(len==1+FRAME_BYTES){
        apps.off();                              // gelen kare uygulamayi gecici kapatir
        lastGallery = -1; haveFrame = true;
        memcpy(framebuf, buf+1, FRAME_BYTES);
        renderFrame();
      }
      break;
    case 0x02: {
      apps.off();
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
      if(len>=2){ apps.off(); lastGallery = buf[1]; drawGallery(buf[1]); }
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
    case 0x0A:                                   // canli DCLK bolen ayari (flicker tuner)
      if(len>=2){
        uint32_t div = buf[1]; if(div<8) div=8; if(div>200) div=200;
        matrix.setClockDiv(div);                 // hemen uygula (loop context, transferler arasi)
        prefs.begin("panelcfg", false); prefs.putUInt("dclkdiv", div); prefs.end();  // reboot'ta kalsin
        logf("DCLK: bolen=%lu -> ~%lu kHz (NVS'e kaydedildi)", div, 160000UL/div);
        redrawCurrent();                         // yeni hizda yeniden ciz
      }
      break;
    case 0x0B:                                   // uygulama sec (0=kapat,1=saat,2=timer,3=hava,4=dunyakupasi,5=spotify)
      if(len>=2){
        apps.select(buf[1], len>2 ? buf+2 : nullptr, len-2);
        if(buf[1]==0) redrawCurrent();           // kapatilinca son icerige don
        logf("Uygulama: %u secildi", buf[1]);
      }
      break;
    case 0x0C:                                   // hava konumu: lat(f32),lon(f32),sehir
      if(len>=9){
        float lat, lon; memcpy(&lat, buf+1, 4); memcpy(&lon, buf+5, 4);
        char city[24]={0}; size_t cl=len-9; if(cl>sizeof(city)-1) cl=sizeof(city)-1;
        memcpy(city, buf+9, cl);
        apps.setLocation(lat, lon, city);
        logf("Konum: %.3f,%.3f (%s)", lat, lon, city);
      }
      break;
    case 0x0D:                                   // Spotify access token (tarayici PKCE'den)
      if(len>=2){
        char tok[300]={0}; size_t tl=len-1; if(tl>sizeof(tok)-1) tl=sizeof(tok)-1;
        memcpy(tok, buf+1, tl);
        apps.setSpotifyToken(tok);
        logf("Spotify token alindi (%u bayt)", (unsigned)tl);
      }
      break;
    case 0x0E:                                   // blur kademesi (0=kapalı, 1=2x2, idx≥2 → (2*idx-1) kenarlı box blur, maks 12 = 23x23)
      if(len>=2){
        matrix.img_blur = buf[1] > 12 ? 12 : buf[1];
        logf("Blur: r=%u", matrix.img_blur);
        redrawCurrent();
      }
      break;
    case 0x0F:                                   // flicker self-test baslat/durdur
      if(ftActive) ftStop(); else ftStart();
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
  // Web UI'daki DCLK tuner ile bulunan flicker ayari NVS'te ise uygula
  // (donanima ozgu en yuksek mozaiksiz hiz). Yoksa derlenmis varsayilan (2.5MHz).
  prefs.begin("panelcfg", true);
  uint32_t nvsDiv = prefs.getUInt("dclkdiv", 0);
  prefs.end();
  if(nvsDiv >= 8 && nvsDiv <= 200){ matrix.setClockDiv(nvsDiv); logf("DCLK NVS ayari: bolen=%lu (~%lu kHz)", nvsDiv, 160000UL/nvsDiv); }
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
    // NTP saat senkronu (Turkiye UTC+3, DST yok) - Saat uygulamasi icin
    configTime(3*3600, 0, "pool.ntp.org", "time.google.com", "time.cloudflare.com");
    apps.begin(&matrix);                       // kayitli "home" uygulamasini geri yukle (varsa)
    if(MDNS.begin(MDNS_HOSTNAME)){
      MDNS.addService("http","tcp",80);
      MDNS.addService("magpanel","tcp",80);      // iOS Bonjour kesfi icin
      logf("mDNS: http://%s.local", MDNS_HOSTNAME);
    }
    ws.onEvent(onWsEvent);
    server.addHandler(&ws);
    server.on("/", HTTP_GET, handleIndex);   // PROGMEM'den akitilir (truncation'a karşi sağlam)

    // /api/gallery — galeri tablo isimlerini JSON olarak döndürür
    server.on("/api/gallery", HTTP_GET, [](AsyncWebServerRequest *r){
      String j = "[";
      for(int i=0; i<GALLERY_COUNT; i++){
        if(i) j += ",";
        j += "\"";
        // GALLERY_NAMES PROGMEM degil, dogrudan erisim
        j += GALLERY_NAMES[i];
        j += "\"";
      }
      j += "]";
      r->send(200, "application/json", j);
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
  if(ftActive) ftLoop();        // flicker self-test aktifse fazlari ilerlet (apps yerine)
  else apps.loop();             // uygulama aciksa zamani gelince fetch+render (kendi throttle'i var)
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
