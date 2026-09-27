/* MagPanel P1.86 TEST firmware (SM16380SH + SM5368, 172x86, 1/43)
   ---------------------------------------------------------------
   Ayri PlatformIO env'i: `pio run -e p186-test -t upload` (USB) ya da mevcut
   P4 firmware'inin http://<ip>/update sayfasindan .pio/build/p186-test/firmware.bin.
   P4 (FM6363C) firmware'i hic degismedi: geri donmek icin bu firmware'in
   /update sayfasindan P4 firmware.bin'i yukle (ya da USB ile P4 env'ini flash'la).

   Web arayuzu: http://<ip>/  -> desenler, parlaklik, DCLK, satir surme modu,
   OE polaritesi, register profili, eslem (ayna/offset) ayarlari. Ayarlar NVS'e
   ("p186cfg") kaydedilir. Seri port + /log sayfasi durum loglarini gosterir.
   GitHub otomatik OTA bu firmware'de YOK (P4 CI build'i bunun ustune yazilmasin).

   WiFi: NVS ("wificfg", P4 ile ortak) > wifi_config.h. Ikisi de baglanamazsa
   panel "MagPanel-Setup" acik agini yayinlar: telefondan baglanip
   http://192.168.4.1 -> test sayfasi + "WiFi ayari" (NVS'e kaydeder, restart).
   Acilista gorunen aglar ve baglanti hatasi nedeni loga yazilir.
*/
#include <stdarg.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoOTA.h>
#include <Update.h>
#include <Preferences.h>
#include "esp_wifi.h"
#include "esp_task_wdt.h"
#include "wifi_config.h"
#include "panel_sm16380.h"

#ifndef FW_VERSION
#define FW_VERSION "lokal"
#endif

using namespace sm16380;

static PanelSM16380 panel;
static bool apMode = false;
static volatile uint8_t lastDiscReason = 0;
static volatile bool pendingRestart = false;
static AsyncWebServer server(80);
static Preferences prefs;
static volatile bool otaActive = false;

// ---------------- log (seri + halka tampon, /log ile okunur) ----------------
#define LOG_LINES 40
#define LOG_LEN   110
static char logBuf[LOG_LINES][LOG_LEN];
static uint8_t logHead = 0, logCount = 0;
static uint32_t logSeq = 0;
static void logf(const char *fmt, ...) {
  char line[LOG_LEN];
  va_list ap; va_start(ap, fmt); vsnprintf(line, sizeof(line), fmt, ap); va_end(ap);
  printf("%s\n", line);
  fflush(stdout);
  strncpy(logBuf[logHead], line, LOG_LEN - 1); logBuf[logHead][LOG_LEN - 1] = 0;
  logHead = (logHead + 1) % LOG_LINES;
  if (logCount < LOG_LINES) logCount++;
  logSeq++;
}

// ---------------- ayarlar ----------------
struct Settings {
  uint8_t brightness = 64;
  uint8_t dclk_div   = 16;    // 160 MHz / div  (16 = 10 MHz)
  uint8_t pattern    = 12;    // acilista otomatik dizi
};
static Settings st;

static void saveSettings() {
  prefs.begin("p186cfg", false);
  prefs.putBytes("opt", &panel.opt, sizeof(panel.opt));
  prefs.putBytes("st", &st, sizeof(st));
  prefs.end();
}
static void loadSettings() {
  prefs.begin("p186cfg", false);
  if (prefs.getBytesLength("opt") == sizeof(panel.opt)) prefs.getBytes("opt", &panel.opt, sizeof(panel.opt));
  if (prefs.getBytesLength("st") == sizeof(st)) prefs.getBytes("st", &st, sizeof(st));
  prefs.end();
  if (st.dclk_div < 8) st.dclk_div = 8;
  if (panel.opt.reg_profile >= REG_PROFILE_COUNT) panel.opt.reg_profile = 0;
  if (panel.opt.gs_bits < 12 || panel.opt.gs_bits > 16) panel.opt.gs_bits = 13;
  if (panel.opt.row_offset >= SCAN) panel.opt.row_offset = 0;
  if (panel.opt.x_offset > 4) panel.opt.x_offset = 0;
}

// ---------------- desenler ----------------
enum Pattern : uint8_t {
  P_OFF = 0, P_RED, P_GREEN, P_BLUE, P_WHITE, P_ROWWALK, P_COLWALK, P_HALVES,
  P_ORIENT, P_CHIPS, P_GRADIENT, P_GRID, P_AUTO, P_COUNT
};
static const char *PAT_NAMES[P_COUNT] = {
  "kapali", "kirmizi", "yesil", "mavi", "beyaz", "satir yuruyen", "sutun yuruyen",
  "yarilar (ust K / alt M)", "yon testi", "cip bloklari", "gradyan", "izgara 8px", "otomatik dizi"
};
static const uint8_t AUTO_SEQ[] = { P_RED, P_GREEN, P_BLUE, P_WHITE, P_HALVES, P_ORIENT, P_CHIPS, P_GRADIENT, P_GRID };
static uint8_t autoIdx = 0;
static uint32_t autoT = 0, walkT = 0;
static int walkPos = 0;

static void fill(uint8_t r, uint8_t g, uint8_t b) {
  for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) panel.setPixel(x, y, r, g, b);
}

static void drawPattern(uint8_t p) {
  panel.global_brightness = st.brightness;
  switch (p) {
    case P_OFF:   fill(0, 0, 0); break;
    case P_RED:   fill(255, 0, 0); break;
    case P_GREEN: fill(0, 255, 0); break;
    case P_BLUE:  fill(0, 0, 255); break;
    case P_WHITE: fill(255, 255, 255); break;
    case P_ROWWALK:
      fill(0, 0, 0);
      for (int x = 0; x < W; x++) panel.setPixel(x, walkPos % H, 255, 255, 255);
      break;
    case P_COLWALK:
      fill(0, 0, 0);
      for (int y = 0; y < H; y++) panel.setPixel(walkPos % W, y, 255, 255, 255);
      break;
    case P_HALVES:
      for (int y = 0; y < H; y++) for (int x = 0; x < W; x++)
        panel.setPixel(x, y, y < H / 2 ? 255 : 0, 0, y < H / 2 ? 0 : 255);
      break;
    case P_ORIENT:
      fill(0, 0, 0);
      for (int x = 0; x < W; x++) { panel.setPixel(x, 0, 255, 255, 255); panel.setPixel(x, H - 1, 255, 255, 255); }
      for (int y = 0; y < H; y++) { panel.setPixel(0, y, 255, 255, 255); panel.setPixel(W - 1, y, 255, 255, 255); }
      for (int y = 2; y < 12; y++) for (int x = 2; x < 12; x++) {
        panel.setPixel(x, y, 255, 0, 0);                 // sol-ust: kirmizi
        panel.setPixel(W - 1 - x, y, 0, 255, 0);         // sag-ust: yesil
        panel.setPixel(x, H - 1 - y, 0, 0, 255);         // sol-alt: mavi
      }
      panel.setTextColor(0xFFE0); panel.setTextSize(2);
      panel.setCursor(W / 2 - 42, H / 2 - 8); panel.print("P1.86");
      break;
    case P_CHIPS: {
      static const uint8_t pal[6][3] = {{255,0,0},{0,255,0},{0,0,255},{255,255,0},{0,255,255},{255,0,255}};
      for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
        int blk = x / 16;
        const uint8_t *c = pal[blk % 6];
        if (x % 16 == 0) panel.setPixel(x, y, 255, 255, 255);            // blok basi beyaz
        else if (y < blk * 4 + 4) panel.setPixel(x, y, c[0], c[1], c[2]); // blok no = yukseklik
        else panel.setPixel(x, y, c[0] / 8, c[1] / 8, c[2] / 8);
      }
      break;
    }
    case P_GRADIENT:
      for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
        uint8_t v = (uint8_t)(x * 255 / (W - 1));
        int band = y * 4 / H;
        panel.setPixel(x, y, band == 0 || band == 3 ? v : 0, band == 1 || band == 3 ? v : 0, band == 2 || band == 3 ? v : 0);
      }
      break;
    case P_GRID:
      for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
        bool on = (x % 8 == 0) || (y % 8 == 0);
        panel.setPixel(x, y, on ? 255 : 0, on ? 255 : 0, on ? 255 : 0);
      }
      break;
  }
  panel.update();
}

static uint8_t shownPattern() { return st.pattern == P_AUTO ? AUTO_SEQ[autoIdx] : st.pattern; }

// ---------------- web komutlari (async gorevden -> loop'a) ----------------
static volatile bool pendingRedraw = true, pendingRebuild = false, pendingSave = false, pendingRegs = false;

static bool applySetting(const String &k, int v) {
  auto &o = panel.opt;
  if (k == "pat")      { if (v < 0 || v >= P_COUNT) return false; st.pattern = v; autoIdx = 0; autoT = millis(); walkPos = 0; }
  else if (k == "bri") { st.brightness = constrain(v, 0, 255); }
  else if (k == "div") { st.dclk_div = constrain(v, 8, 200); panel.setClockDiv(st.dclk_div); }
  else if (k == "row") { o.row_mode = constrain(v, 0, 1); pendingRebuild = true; }
  else if (k == "bk")  { o.bk_mode = constrain(v, 0, 2); pendingRebuild = true; }
  else if (k == "oe")  { o.oe_invert = v != 0; pendingRebuild = true; }
  else if (k == "reg") { o.reg_profile = constrain(v, 0, REG_PROFILE_COUNT - 1); pendingRegs = true; }
  else if (k == "gs")  { o.gs_bits = constrain(v, 12, 16); }
  else if (k == "mx")  { o.mirror_x = v != 0; }
  else if (k == "cr")  { o.chan_rev = v != 0; }
  else if (k == "xo")  { o.x_offset = constrain(v, 0, 4); }
  else if (k == "sw")  { o.swap_halves = v != 0; }
  else if (k == "fy")  { o.flip_y = v != 0; }
  else if (k == "ro")  { o.row_offset = constrain(v, 0, SCAN - 1); }
  else return false;
  pendingRedraw = true; pendingSave = true;
  return true;
}

static String stateJson() {
  const auto &o = panel.opt;
  char b[420];
  snprintf(b, sizeof(b),
    "{\"pat\":%u,\"bri\":%u,\"div\":%u,\"row\":%u,\"bk\":%u,\"oe\":%u,\"reg\":%u,\"gs\":%u,"
    "\"mx\":%u,\"cr\":%u,\"xo\":%u,\"sw\":%u,\"fy\":%u,\"ro\":%u,\"ver\":\"%s\",\"prof\":\"%s\",\"shown\":\"%s\"}",
    st.pattern, st.brightness, st.dclk_div, o.row_mode, o.bk_mode, o.oe_invert, o.reg_profile, o.gs_bits,
    o.mirror_x, o.chan_rev, o.x_offset, o.swap_halves, o.flip_y, o.row_offset, FW_VERSION,
    panel.profileName(), PAT_NAMES[shownPattern()]);
  return String(b);
}

static const char INDEX_HTML[] PROGMEM = R"HTML(<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>MagPanel P1.86 test</title>
<style>body{font-family:system-ui,sans-serif;max-width:680px;margin:0 auto;padding:12px;background:#111;color:#eee}
h1{font-size:20px}h2{font-size:15px;margin:18px 0 6px;color:#9cf}button{margin:3px;padding:9px 12px;border:0;border-radius:6px;background:#333;color:#eee;font-size:14px}
button.on{background:#06f}label{display:block;margin:6px 0}select,input{font-size:14px}pre{background:#000;padding:8px;font-size:12px;max-height:260px;overflow:auto;white-space:pre-wrap}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}small{color:#999}</style></head><body>
<h1>MagPanel P1.86 test <small id=ver></small></h1>
<div id=shown></div>
<h2>Desen</h2><div id=pats></div>
<h2>Parlaklik <span id=briv></span></h2><input type=range min=0 max=255 id=bri style="width:100%" onchange="s('bri',this.value)">
<small>Test icin dusuk tut (varsayilan 64). Tam beyaz + yuksek parlaklik modul basina ~30 W cekebilir.</small>
<h2>Surme</h2>
<label>DCLK <select id=div onchange="s('div',this.value)"><option value=64>2.5 MHz</option><option value=32>5 MHz</option><option value=20>8 MHz</option><option value=16>10 MHz</option><option value=12>13 MHz</option><option value=10>16 MHz</option></select></label>
<label>Satir surme <select id=row onchange="s('row',this.value)"><option value=0>SM5368 kaydirma (A saat, B BK, C veri)</option><option value=1>Ikili ABCDE adres</option></select></label>
<label>BK (B hatti) <select id=bk onchange="s('bk',this.value)"><option value=0>satir gecisinde darbe</option><option value=1>hep 1</option><option value=2>hep 0</option></select></label>
<label>OE darbesi <select id=oe onchange="s('oe',this.value)"><option value=0>aktif-yuksek</option><option value=1>aktif-dusuk (ters)</option></select></label>
<label>Register profili <select id=reg onchange="s('reg',this.value)"><option value=0>rt6 SM16380SH-5368 (etiket)</option><option value=1>rt9</option><option value=2>rt54</option></select></label>
<label>Gri ton bitleri <select id=gs onchange="s('gs',this.value)"><option>12</option><option>13</option><option>14</option><option>15</option><option>16</option></select></label>
<h2>Eslem (goruntu duzeldikten sonra)</h2>
<div class=row><label><input type=checkbox id=mx onchange="s('mx',+this.checked)"> X ayna</label>
<label><input type=checkbox id=cr onchange="s('cr',+this.checked)"> kanal ters</label>
<label><input type=checkbox id=sw onchange="s('sw',+this.checked)"> yarilar takas</label>
<label><input type=checkbox id=fy onchange="s('fy',+this.checked)"> yari-ici Y ters</label></div>
<label>X ofset (bos kanal) <select id=xo onchange="s('xo',this.value)"><option>0</option><option>1</option><option>2</option><option>3</option><option>4</option></select></label>
<label>Satir ofseti <input type=number id=ro min=0 max=42 style="width:60px" onchange="s('ro',this.value)"></label>
<h2>Log</h2><pre id=log></pre>
<p><a href=/wifi style="color:#9cf">WiFi ayari</a></p>
<p><a href=/update style="color:#9cf">Firmware yukle (/update)</a> <small>- P4'e donmek icin P4 firmware.bin'i buradan yukle</small></p>
<script>
const P=["kapali","kirmizi","yesil","mavi","beyaz","satir yuruyen","sutun yuruyen","yarilar","yon testi","cip bloklari","gradyan","izgara","otomatik"];
let pats=document.getElementById('pats');P.forEach((n,i)=>{let b=document.createElement('button');b.textContent=n;b.id='p'+i;b.onclick=()=>s('pat',i);pats.appendChild(b)});
function s(k,v){fetch('/set?k='+k+'&v='+v).then(r=>r.json()).then(show)}
function show(j){for(const k of['bri','div','row','bk','oe','reg','gs','xo','ro']){let e=document.getElementById(k);if(e)e.value=j[k]}
for(const k of['mx','cr','sw','fy'])document.getElementById(k).checked=!!j[k];
document.getElementById('briv').textContent=j.bri;document.getElementById('ver').textContent=j.ver;
document.getElementById('shown').textContent='Gosterilen: '+j.shown+' | profil: '+j.prof;
P.forEach((n,i)=>document.getElementById('p'+i).className=(i==j.pat?'on':''))}
function poll(){fetch('/state').then(r=>r.json()).then(show);fetch('/log').then(r=>r.text()).then(t=>{let l=document.getElementById('log');l.textContent=t;l.scrollTop=1e9})}
poll();setInterval(poll,2000);
</script></body></html>)HTML";

static const char *reasonText(uint8_t r) {
  switch (r) {
    case 15: case 204: return "sifre yanlis olabilir (4-way handshake)";
    case 201: return "ag bulunamadi (SSID yanlis ya da 2.4 GHz yok)";
    case 202: return "kimlik dogrulama basarisiz (sifre?)";
    case 203: return "iliskilendirme basarisiz";
    case 205: return "baglanti zaman asimi";
    case 210: case 211: return "guvenlik modu uyumsuz (WPA3-only?)";
    case 0: return "-";
    default: return "diger";
  }
}
static const char *authText(wifi_auth_mode_t a) {
  switch (a) {
    case WIFI_AUTH_OPEN: return "acik";
    case WIFI_AUTH_WEP: return "WEP";
    case WIFI_AUTH_WPA_PSK: return "WPA";
    case WIFI_AUTH_WPA2_PSK: return "WPA2";
    case WIFI_AUTH_WPA_WPA2_PSK: return "WPA/WPA2";
    case WIFI_AUTH_WPA3_PSK: return "WPA3";
    case WIFI_AUTH_WPA2_WPA3_PSK: return "WPA2/WPA3";
    default: return "?";
  }
}

// Acilista gorunen 2.4 GHz aglari logla (hedef SSID gorunuyor mu, guvenlik tipi ne)
static void scanNetworks(const char *target) {
  WiFi.mode(WIFI_STA);
  int n = WiFi.scanNetworks();
  logf("WiFi tarama: %d ag goruldu", n);
  bool found = false;
  for (int i = 0; i < n && i < 12; i++) {
    bool t = WiFi.SSID(i) == target;
    found |= t;
    logf("  %s%s  RSSI %d  kanal %d  %s", t ? ">> " : "", WiFi.SSID(i).c_str(), WiFi.RSSI(i), WiFi.channel(i),
         authText(WiFi.encryptionType(i)));
  }
  if (!found) logf("  UYARI: '%s' taramada YOK", target);
  WiFi.scanDelete();
}

static const char WIFI_HTML[] PROGMEM = R"HTML(<!DOCTYPE html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>MagPanel WiFi</title>
<style>body{font-family:system-ui,sans-serif;max-width:420px;margin:24px auto;padding:0 16px;background:#111;color:#eee}
input{width:100%;padding:11px;margin:6px 0;box-sizing:border-box;font-size:16px}
button{width:100%;padding:13px;margin-top:8px;font-size:16px;background:#06f;color:#fff;border:0;border-radius:8px}a{color:#9cf}</style></head><body>
<h2>MagPanel WiFi ayari</h2><p>Sadece 2.4 GHz aglar. Kaydedince panel yeniden baslar.</p>
<form method=POST action=/wifisave><label>WiFi adi (SSID)</label><input name=ssid required>
<label>Sifre</label><input name=pass type=password><button type=submit>Kaydet ve baglan</button></form>
<p><a href=/>Test sayfasina don</a></p></body></html>)HTML";

static void setupWeb() {
  server.on("/wifi", HTTP_GET, [](AsyncWebServerRequest *r) {
    r->send(200, "text/html; charset=utf-8", (const uint8_t *)WIFI_HTML, strlen_P(WIFI_HTML));
  });
  server.on("/wifisave", HTTP_POST, [](AsyncWebServerRequest *r) {
    String ssid, pass;
    if (r->hasParam("ssid", true)) ssid = r->getParam("ssid", true)->value();
    if (r->hasParam("pass", true)) pass = r->getParam("pass", true)->value();
    if (!ssid.length()) { r->send(400, "text/plain", "SSID bos olamaz"); return; }
    prefs.begin("wificfg", false);
    prefs.putString("ssid", ssid);
    prefs.putString("pass", pass);
    prefs.end();
    logf("WiFi kaydedildi: %s - yeniden baslatiliyor", ssid.c_str());
    r->send(200, "text/html; charset=utf-8", "<meta charset=utf-8><h2>Kaydedildi. Panel yeniden baslatiliyor...</h2>");
    pendingRestart = true;
  });
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *r) {
    AsyncWebServerResponse *res = r->beginResponse(200, "text/html; charset=utf-8", (const uint8_t *)INDEX_HTML, strlen_P(INDEX_HTML));
    res->addHeader("Cache-Control", "no-store");
    r->send(res);
  });
  server.on("/state", HTTP_GET, [](AsyncWebServerRequest *r) { r->send(200, "application/json", stateJson()); });
  server.on("/set", HTTP_GET, [](AsyncWebServerRequest *r) {
    if (!r->hasParam("k") || !r->hasParam("v")) { r->send(400, "text/plain", "k,v gerekli"); return; }
    String k = r->getParam("k")->value();
    int v = r->getParam("v")->value().toInt();
    if (!applySetting(k, v)) { r->send(400, "text/plain", "bilinmeyen ayar"); return; }
    r->send(200, "application/json", stateJson());
  });
  server.on("/log", HTTP_GET, [](AsyncWebServerRequest *r) {
    String out; out.reserve(LOG_LINES * 60);
    uint8_t idx = (logHead + LOG_LINES - logCount) % LOG_LINES;
    for (uint8_t i = 0; i < logCount; i++) { out += logBuf[idx]; out += '\n'; idx = (idx + 1) % LOG_LINES; }
    r->send(200, "text/plain; charset=utf-8", out);
  });

  // Tarayicidan OTA (kullanici admin / OTA_PASSWORD) - P4'e donus yolu
  server.on("/update", HTTP_GET, [](AsyncWebServerRequest *r) {
    if (!r->authenticate("admin", OTA_PASSWORD)) return r->requestAuthentication();
    r->send(200, "text/html",
      "<form method=POST enctype=multipart/form-data><h3>Firmware yukle - mevcut: P1.86 test " FW_VERSION "</h3>"
      "<input type=file name=fw accept=.bin> <input type=submit value=Yukle></form>");
  });
  server.on("/update", HTTP_POST,
    [](AsyncWebServerRequest *r) {
      bool ok = !Update.hasError();
      AsyncWebServerResponse *res = r->beginResponse(200, "text/plain", ok ? "OK - yeniden baslatiliyor" : "HATA");
      res->addHeader("Connection", "close");
      r->send(res);
      if (ok) { delay(300); ESP.restart(); }
    },
    [](AsyncWebServerRequest *r, String fn, size_t index, uint8_t *data, size_t len, bool final) {
      if (!r->authenticate("admin", OTA_PASSWORD)) return;
      if (index == 0) { otaActive = true; Serial.printf("OTA basliyor: %s\n", fn.c_str()); Update.begin(UPDATE_SIZE_UNKNOWN); }
      if (len) Update.write(data, len);
      if (final) { bool ok = Update.end(true); Serial.println(ok ? "OTA bitti" : "OTA HATA"); if (!ok) otaActive = false; }
    });
  server.begin();
}

// Belirtilen kimlikle baglanmayi dene; basarisizsa nedeni logla
static bool tryConnect(const char *ssid, const char *pass, int halfSeconds) {
  lastDiscReason = 0;
  logf("WiFi baglaniyor: '%s'", ssid);
  WiFi.begin(ssid, pass);
  for (int i = 0; i < halfSeconds && WiFi.status() != WL_CONNECTED; i++) { panel.refresh(); delay(500); }
  if (WiFi.status() == WL_CONNECTED) return true;
  logf("  basarisiz: neden %u (%s)", lastDiscReason, reasonText(lastDiscReason));
  WiFi.disconnect(true); delay(200);
  return false;
}

static bool connectWifi() {
  WiFi.onEvent([](arduino_event_id_t e, arduino_event_info_t info) {
    if (e == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) lastDiscReason = info.wifi_sta_disconnected.reason;
  });
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  esp_wifi_set_ps(WIFI_PS_NONE);
  prefs.begin("wificfg", false);
  String ssid = prefs.getString("ssid", ""), pass = prefs.getString("pass", "");
  prefs.end();
  scanNetworks(ssid.length() ? ssid.c_str() : WIFI_SSID);
  if (ssid.length() && tryConnect(ssid.c_str(), pass.c_str(), 30)) return true;
  if (ssid != WIFI_SSID && tryConnect(WIFI_SSID, WIFI_PASS, 40)) return true;
  return false;
}

// Baglanti yoksa kurulum agi: test sayfasi + /wifi formu 192.168.4.1'de
static void startSetupAP() {
  WiFi.disconnect(true);
  WiFi.mode(WIFI_AP);
  WiFi.softAP("MagPanel-Setup");
  apMode = true;
  logf("Kurulum agi acik: 'MagPanel-Setup' -> http://%s  (WiFi ayari: /wifi)", WiFi.softAPIP().toString().c_str());
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 20 && !Serial; i++) delay(100);   // USB monitor aciksa ilk satirlari kacirma
  delay(300);
  esp_task_wdt_deinit();
  esp_log_level_set("task_wdt", ESP_LOG_NONE);   // AsyncTCP'nin "TWDT was never initialized" spam'i (P4 ile ayni)
  logf("MagPanel P1.86 TEST %s", FW_VERSION);
  logf("PSRAM: %u KB toplam, %u KB bos", ESP.getPsramSize() / 1024, ESP.getFreePsram() / 1024);
  loadSettings();
  if (!panel.initMatrix()) {
    logf("HATA: panel tamponlari ayrilamadi (PSRAM?)");
  } else {
    panel.setClockDiv(st.dclk_div);
    logf("Panel: %dx%d 1/%d, %d cip/hat, akis %u KB (PSRAM), DCLK %u kHz",
         W, H, SCAN, CHIPS, (unsigned)(panel.streamBytes() / 1024), (unsigned)(160000 / st.dclk_div));
    logf("Profil: %s | satir modu: %s", panel.profileName(), panel.opt.row_mode ? "ikili" : "SM5368 kaydirma");
  }
  logf("Dahili heap bos: %u, en buyuk blok: %u", ESP.getFreeHeap(), ESP.getMaxAllocHeap());
  drawPattern(shownPattern());

  bool wifiOk = connectWifi();
  if (wifiOk) {
    logf("WiFi OK - http://%s  (mDNS: %s.local)", WiFi.localIP().toString().c_str(), MDNS_HOSTNAME);
    if (MDNS.begin(MDNS_HOSTNAME)) MDNS.addService("http", "tcp", 80);
  } else {
    startSetupAP();
  }
  {
    setupWeb();
    ArduinoOTA.setHostname(MDNS_HOSTNAME);
    ArduinoOTA.setPassword(OTA_PASSWORD);
    ArduinoOTA.onStart([]() { otaActive = true; server.end(); });
    ArduinoOTA.onError([](ota_error_t e) { otaActive = false; Serial.printf("OTA hata %u\n", e); });
    ArduinoOTA.begin();
  }
  autoT = walkT = millis();
}

void loop() {
  ArduinoOTA.handle();
  if (otaActive) { delay(2); return; }
  panel.refresh();

  if (pendingRebuild) {
    pendingRebuild = false; pendingRegs = true;
    panel.rebuild();
    logf("Ayar: satir=%u bk=%u oe_ters=%u", panel.opt.row_mode, panel.opt.bk_mode, panel.opt.oe_invert);
  }
  if (pendingRegs) {
    pendingRegs = false;
    drawPattern(shownPattern());      // guncel veri + tum register'lar
    panel.rewriteAllRegisters();
    logf("Register'lar yazildi: %s", panel.profileName());
  }
  if (pendingSave) { pendingSave = false; saveSettings(); }
  if (pendingRestart) { delay(800); ESP.restart(); }

  uint32_t now = millis();
  if (st.pattern == P_AUTO && now - autoT > 3500) {
    autoT = now; autoIdx = (autoIdx + 1) % sizeof(AUTO_SEQ);
    pendingRedraw = true;
  }
  uint8_t sp = shownPattern();
  if ((sp == P_ROWWALK || sp == P_COLWALK) && now - walkT > 300) {
    walkT = now; walkPos++;
    pendingRedraw = true;
    if (sp == P_ROWWALK) logf("satir %d", walkPos % H);
  }
  if (pendingRedraw) {
    pendingRedraw = false;
    drawPattern(sp);
    if (sp != P_ROWWALK && sp != P_COLWALK) logf("Desen: %s", PAT_NAMES[sp]);
  }

  static uint32_t netT = 0;
  if (now - netT > 30000) {
    netT = now;
    if (apMode) {
      logf("[NET] kurulum agi 'MagPanel-Setup' acik, istemci %d - http://192.168.4.1", WiFi.softAPgetStationNum());
    } else {
      wl_status_t ws = WiFi.status();
      logf("[NET] heap=%u blok=%u RSSI=%d durum=%d", ESP.getFreeHeap(), ESP.getMaxAllocHeap(), WiFi.RSSI(), (int)ws);
      if (ws == WL_DISCONNECTED || ws == WL_CONNECTION_LOST || ws == WL_CONNECT_FAILED || ws == WL_NO_SSID_AVAIL)
        WiFi.reconnect();
    }
  }
  delay(2);
}
