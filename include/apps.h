#pragma once
// ============================================================================
//  MagPanel "Uygulamalar" - FIRMWARE TARAFI (server-side) render
// ----------------------------------------------------------------------------
//  Panel verileri KENDISI ceker (NTP saat, HTTPS hava/skor) ve GFX_Lite ile
//  cizer; tarayici GEREKMEZ. Tarayici sadece WS ile hangi uygulamanin acik
//  oldugunu ve konum / timer suresi / spotify-token gibi ayarlari bildirir.
//  Son secilen uygulama NVS'e ("appcfg") kaydedilir -> reboot'ta panel
//  tarayicisiz ayni uygulamayla geri gelir.
//
//  NOT (dusuk-heap / DMA): ana dal'da panel SUREKLI DMA ile taranmiyor; bir
//  HTTPS fetch (1-3 sn, bloklar) sirasinda loop() refresh() cagiramadigindan
//  panel KISA SURE kararir. Bu yuzden fetch'ler seyrektir (hava 10 dk, skor
//  5 dk). Surekli-DMA dali merge edilince bu blackout tamamen kalkar.
//
//  Cizim: Panel (Matrix ya da PanelSM16380) : public GFX (GFX_Lite) ->
//  setCursor/setTextColor/setTextSize/print + clear_pixels()/update().
//  Yerlesim: P4 80x120 dikey; P1.86 172x86 yatay -> L(p4, genis) ile secilir.
// ============================================================================
#include <Arduino.h>
#include <time.h>
#include <math.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include "panel.h"
#include "sensors.h"

// Dunya Kupasi icin TheSportsDB lig ID'si (server-side fetch, CORS sorunu yok).
// "4429" = FIFA World Cup (TheSportsDB). Veri gelmezse web LOG'da uyari cikar;
// dogru ID'yi https://www.thesportsdb.com lig sayfasindan dogrulayip degistir.
#ifndef WORLDCUP_LEAGUE_ID
#define WORLDCUP_LEAGUE_ID "4429"
#endif
// TheSportsDB ucretsiz test anahtari ("3"; premium icin Patreon anahtari).
#ifndef THESPORTSDB_KEY
#define THESPORTSDB_KEY "3"
#endif

enum AppMode : uint8_t {
  APP_NONE     = 0,   // uygulama kapali (galeri/kare modu)
  APP_CLOCK    = 1,
  APP_TIMER    = 2,
  APP_WEATHER  = 3,
  APP_WORLDCUP = 4,
  APP_SPOTIFY  = 5,
  APP_ROOM     = 6,   // ic mekan: DHT11 sicaklik/nem + LDR isik + saat (sensors.h)
  APP_SOUND    = 7,   // ses seviyesi (VU) - mikrofon zarfi
  APP_MAX      = 7,
};

class Apps {
 public:
  void begin(Panel* m) {
    M = m;
    // Kayitli konum + son uygulamayi geri yukle (tarayicisiz standalone calisma)
    cfg.begin("appcfg", true);
    _lat = cfg.getFloat("lat", NAN);
    _lon = cfg.getFloat("lon", NAN);
    { String c = cfg.getString("city", ""); strlcpy(_city, c.c_str(), sizeof(_city)); }
    uint8_t saved = cfg.getUChar("app", APP_NONE);
    cfg.end();
    if (saved >= APP_CLOCK && saved <= APP_MAX) {
      _app = (AppMode)saved;          // boot'ta son uygulamayi ac
      _lastRender = 0; _lastFetch = 0;
    }
  }

  AppMode mode() const { return _app; }
  bool active() const { return _app != APP_NONE; }
  // Sensor okumalari (Oda/Ses uygulamalari, Hava'daki ic mekan satiri). nullptr = sensor yok.
  void setSensors(const Sensors* s) { _sens = s; }
  // Bir sonraki loop()'ta hemen yeniden ciz (uykudan uyaninca / parlaklik degisince)
  void redraw() { _lastRender = 0; }
  static const char* name(uint8_t id) {
    static const char* N[APP_MAX + 1] = { "kapat", "saat", "timer", "hava", "dunya kupasi", "spotify", "oda", "ses" };
    return id <= APP_MAX ? N[id] : "?";
  }

  // Gecici kapat (kullanici resim/video/galeri gonderince). SADECE bellekte;
  // NVS'teki "home" uygulama korunur -> reboot'ta panel ona geri doner.
  // (Akan video her karede cagirir; NVS yazimi YOK -> asinma yok.)
  void off() { _app = APP_NONE; }

  // Tarayicidan WS 0x0B ile uygulama secimi (+ opsiyonel parametre).
  void select(uint8_t id, const uint8_t* p, size_t n) {
    if (id > APP_MAX) return;
    _app = (AppMode)id;
    _lastRender = 0;                  // hemen ciz
    if (_app == APP_TIMER && n >= 2) {
      uint32_t dur = ((uint32_t)p[0] << 8) | p[1];   // saniye (big-endian)
      _timerDur = dur;
      _timerEndMs = millis() + dur * 1000UL;
      _timerRunning = (dur > 0);
    }
    if (_app == APP_WEATHER || _app == APP_WORLDCUP || _app == APP_SPOTIFY)
      _lastFetch = 0;                 // secince ilk fetch'i tetikle
    // Secimi kalici yap (reboot'ta geri gelsin)
    cfg.begin("appcfg", false); cfg.putUChar("app", _app); cfg.end();
  }

  // WS 0x0C: konum (tarayici sehir adini lat/lon'a cozer, buraya yollar).
  void setLocation(float lat, float lon, const char* name) {
    _lat = lat; _lon = lon;
    strlcpy(_city, name ? name : "", sizeof(_city));
    _wxOk = false;                    // yeni konum -> yeniden fetch
    cfg.begin("appcfg", false);
    cfg.putFloat("lat", lat); cfg.putFloat("lon", lon); cfg.putString("city", _city);
    cfg.end();
  }

  // WS 0x0D: Spotify access token (tarayici PKCE ile alir, buraya yollar).
  void setSpotifyToken(const char* tok) {
    strlcpy(_spToken, tok ? tok : "", sizeof(_spToken));
    _lastFetch = 0;
  }

  // loop()'tan her turda cagrilir; zamani gelince fetch + render yapar.
  void loop() {
    if (_app == APP_NONE || M == nullptr) return;
    uint32_t now = millis();

    // ---- periyodik veri cekme (bloklar; seyrek tutuldu) ----
    if (_app == APP_WEATHER  && (now - _lastFetch > 600000UL || (_lastFetch == 0))) { _lastFetch = now ? now : 1; fetchWeather(); }
    if (_app == APP_WORLDCUP && (now - _lastFetch > 300000UL || (_lastFetch == 0))) { _lastFetch = now ? now : 1; fetchWorldCup(); }
    if (_app == APP_SPOTIFY  && (now - _lastFetch > 5000UL   || (_lastFetch == 0))) { _lastFetch = now ? now : 1; fetchSpotify(); }

    // ---- render hizi ----
    uint32_t interval = (_app == APP_CLOCK || _app == APP_TIMER) ? 500
                      : (_app == APP_SOUND ? 50 : (_app == APP_ROOM ? 1000 : 2000));
    if (_lastRender != 0 && now - _lastRender < interval) return;
    _lastRender = now ? now : 1;
    switch (_app) {
      case APP_CLOCK:    renderClock();    break;
      case APP_TIMER:    renderTimer();    break;
      case APP_WEATHER:  renderWeather();  break;
      case APP_WORLDCUP: renderWorldCup(); break;
      case APP_SPOTIFY:  renderSpotify();  break;
      case APP_ROOM:     renderRoom();     break;
      case APP_SOUND:    renderSound();    break;
      default: break;
    }
  }

 private:
  Panel*      M = nullptr;
  const Sensors* _sens = nullptr;
  AppMode     _app = APP_NONE;
  Preferences cfg;
  uint32_t    _lastRender = 0;
  uint32_t    _lastFetch  = 0;

  // timer
  uint32_t _timerEndMs = 0, _timerDur = 0;
  bool     _timerRunning = false;

  // weather
  float _lat = NAN, _lon = NAN;
  char  _city[24] = "";
  float _temp = NAN;
  int   _wcode = -1;
  bool  _wxOk = false;

  // world cup
  char _wcL1[20] = "", _wcL2[20] = "", _wcL3[20] = "";
  bool _wcOk = false;

  // ses (VU): seviye gecmisi (sutun basina 50 ms) + tepe tutucu
  uint8_t  _hist[256] = {0};
  uint16_t _histHead = 0;
  uint8_t  _vuPeak = 0;
  uint32_t _vuPeakAt = 0;

  // spotify (iskelet)
  char _spToken[300] = "";
  char _spTrack[40] = "", _spArtist[40] = "";
  bool _spOk = false;

  // ----------------------------------------------------------------- render
  void clear() { M->clear_pixels(); }

  // Yerlesim: iki tasarim var - dikey (80x120 icin) ve genis (172x86 icin). Kanvas
  // bunlardan buyukse (coklu P1.86) y konumlari boya gore olceklenir, yazi boyutu
  // tam sayi katsayiyla buyur. P4 80x120 ve tek P1.86'da sonuc tasarimla birebir ayni.
  static int L(int p4, int wide) { return PANEL_WIDE ? wide * PANEL_H / 86 : p4 * PANEL_H / 120; }
  static int S(int p4, int wide) {
    int k = PANEL_WIDE ? min(PANEL_W / 172, PANEL_H / 86) : min(PANEL_W / 80, PANEL_H / 120);
    return (PANEL_WIDE ? wide : p4) * (k < 1 ? 1 : k);
  }

  // Varsayilan GFX font: 6px (5+1) genis, 8px yuksek; size ile carpilir.
  void centerText(const char* s, int y, uint8_t size, CRGB col) {
    int w = (int)strlen(s) * 6 * size;
    int x = (PANEL_W - w) / 2; if (x < 0) x = 0;
    uint16_t c565 = ((uint16_t)(col.r >> 3) << 11) | ((uint16_t)(col.g >> 2) << 5) | (col.b >> 3);
    M->setTextSize(size);
    M->setTextColor(c565);
    M->setCursor(x, y);
    M->print(s);
  }

  void renderClock() {
    struct tm t;
    clear();
    if (!getLocalTime(&t, 30)) {
      centerText("SAAT", L(30, 26), S(1, 1), CRGB(150, 150, 150));
      centerText("senkron", L(70, 46), S(1, 1), CRGB(255, 180, 80));
      M->update();
      return;
    }
    char hm[6];  snprintf(hm, sizeof(hm), "%02d:%02d", t.tm_hour, t.tm_min);
    char ss[4];  snprintf(ss, sizeof(ss), "%02d", t.tm_sec);
    char dt[8];  snprintf(dt, sizeof(dt), "%02d.%02d", t.tm_mday, t.tm_mon + 1);
    static const char* days[7] = {"Pazar","Pzt","Sali","Cars","Pers","Cuma","Cmt"};
    centerText(hm, L(30, 10), S(2, 4), CRGB(255, 180, 80));   // buyuk saat HH:MM
    centerText(ss, L(54, 48), S(1, 1), CRGB(160, 160, 160));  // saniye
    if (PANEL_WIDE) {                                         // yatay: gun.ay + gun tek satir
      char dl[16]; snprintf(dl, sizeof(dl), "%s %s", dt, days[t.tm_wday % 7]);
      centerText(dl, L(0, 66), S(1, 1), CRGB(120, 170, 255));
    } else {
      centerText(dt, L(74, 0), S(1, 1), CRGB(120, 170, 255));   // gun.ay
      centerText(days[t.tm_wday % 7], L(88, 0), S(1, 1), CRGB(120, 170, 255));
    }
    M->update();
  }

  void renderTimer() {
    clear();
    long rem = (long)_timerEndMs - (long)millis();
    if (!_timerRunning) rem = (long)_timerDur * 1000L;
    if (rem < 0) rem = 0;
    int s = rem / 1000;
    char buf[8]; snprintf(buf, sizeof(buf), "%02d:%02d", s / 60, s % 60);
    centerText("TIMER", L(26, 8), S(1, 1), CRGB(150, 150, 150));
    CRGB col = (_timerRunning && rem <= 10000) ? CRGB(255, 80, 80) : CRGB(120, 255, 140);
    centerText(buf, L(50, 24), S(2, 4), col);
    if (_timerRunning && rem == 0) {
      centerText("BITTI", L(82, 66), S(1, 1), CRGB(255, 80, 80));
      _timerRunning = false;
    }
    M->update();
  }

  void renderWeather() {
    clear();
    centerText("HAVA", L(16, 6), S(1, 1), CRGB(150, 150, 150));
    if (isnan(_lat)) {
      centerText("konum", L(46, 32), S(1, 1), CRGB(255, 180, 80));
      centerText("gerekli", L(60, 46), S(1, 1), CRGB(255, 180, 80));
      M->update();
      return;
    }
    if (!_wxOk || isnan(_temp)) {
      centerText("...", L(50, 28), S(2, 3), CRGB(160, 160, 160));
    } else {
      char tb[8]; snprintf(tb, sizeof(tb), "%dC", (int)lroundf(_temp));
      centerText(tb, L(36, 20), S(2, 3), CRGB(255, 200, 90));
      centerText(wmoText(_wcode), L(64, 50), S(1, 1), CRGB(120, 200, 255));
    }
    if (_sens && _sens->dhtOk()) {                             // ic mekan (DHT11): "ic 24C %45"
      char ib[20]; snprintf(ib, sizeof(ib), "ic %dC %%%u", _sens->temp10() / 10, (unsigned)((_sens->hum10() + 5) / 10));
      centerText(ib, L(78, 59), S(1, 1), CRGB(150, 220, 150));
    }
    if (_city[0]) centerText(_city, L(92, 68), S(1, 1), CRGB(140, 140, 140));
    M->update();
  }

  // Oda: DHT11 sicaklik (buyuk) + nem + LDR isik + saat. DHT yoksa "DHT11 yok".
  void renderRoom() {
    clear();
    centerText("ODA", L(14, 6), S(1, 1), CRGB(150, 150, 150));
    if (!_sens || !_sens->dhtOk()) {
      centerText("DHT11", L(40, 26), S(1, 1), CRGB(255, 180, 80));
      centerText("yok", L(54, 40), S(1, 1), CRGB(255, 180, 80));
    } else {
      char tb[10]; snprintf(tb, sizeof(tb), "%d.%dC", _sens->temp10() / 10, abs(_sens->temp10() % 10));
      centerText(tb, L(30, 18), S(2, 3), CRGB(255, 200, 90));    // 5 kr x 12 px = 60 px (P4) / x 18 = 90 px (genis)
      char hb[12]; snprintf(hb, sizeof(hb), "nem %%%u", (unsigned)((_sens->hum10() + 5) / 10));
      centerText(hb, L(56, 48), S(1, 1), CRGB(120, 200, 255));
    }
    if (_sens) {
      char lb[14]; snprintf(lb, sizeof(lb), "isik %%%u", _sens->light());
      centerText(lb, L(72, 60), S(1, 1), CRGB(200, 200, 120));
    }
    struct tm t;
    if (getLocalTime(&t, 10)) {
      char hm[6]; snprintf(hm, sizeof(hm), "%02d:%02d", t.tm_hour, t.tm_min);
      centerText(hm, L(96, 72), S(1, 1), CRGB(140, 140, 140));
    }
    M->update();
  }

  // Ses (VU): seviye gecmisi soldan saga akar (sutun = 50 ms), sag kenarda anlik seviye
  // cubugu + kirmizi tepe tutucu (1.5 sn). Renk yukseklige gore yesil -> sari -> kirmizi.
  // Spektrum degil, zarf: FFT yok (dusuk heap), mikrofon karti AO genligi.
  void renderSound() {
    clear();
    uint8_t lvl = _sens ? _sens->sound() : 0;
    uint8_t pk  = _sens ? _sens->soundPeak() : 0;
    _hist[_histHead] = pk > lvl ? pk : lvl; _histHead = (_histHead + 1) & 255;
    uint32_t now = millis();
    if (pk >= _vuPeak || now - _vuPeakAt > 1500) { _vuPeak = pk; _vuPeakAt = now; }
    const int W = PANEL_W, H = PANEL_H;
    const int barW = W >= 160 ? 6 : 4;             // sag kenar: anlik seviye
    const int gw = (W - barW - 2) > 256 ? 256 : (W - barW - 2);
    const int top = 9, hh = H - top - 1;
    for (int x = 0; x < gw; x++) {
      uint8_t v = _hist[(_histHead + 256 - gw + x) & 255];
      int h = (int)v * hh / 100;
      for (int y = 0; y < h; y++) {
        int q = y * 100 / (hh > 0 ? hh : 1);
        uint8_t r = q < 60 ? (uint8_t)(q * 255 / 60) : 255;
        uint8_t g = q < 60 ? 200 : (q < 85 ? 180 : 40);
        M->drawPixel((int16_t)x, (int16_t)(H - 1 - y), r, g, (uint8_t)20);
      }
    }
    int lh = (int)lvl * hh / 100;
    for (int y = 0; y < lh; y++)
      for (int x = W - barW; x < W; x++) M->drawPixel((int16_t)x, (int16_t)(H - 1 - y), (uint8_t)255, (uint8_t)255, (uint8_t)255);
    int ph = (int)_vuPeak * hh / 100;
    if (ph > 0) for (int x = W - barW; x < W; x++) M->drawPixel((int16_t)x, (int16_t)(H - 1 - ph), (uint8_t)255, (uint8_t)80, (uint8_t)80);
    char lb[12]; snprintf(lb, sizeof(lb), "SES %u", lvl);
    M->setTextSize(1); M->setTextColor(0x8410); M->setCursor(1, 0); M->print(lb);
    M->update();
  }

  void renderWorldCup() {
    clear();
    if (PANEL_WIDE) centerText("D.KUPASI 2026", L(0, 6), S(1, 1), CRGB(255, 180, 80));
    else {
      centerText("D.KUPASI", L(12, 0), S(1, 1), CRGB(255, 180, 80));
      centerText("2026", L(26, 0), S(1, 1), CRGB(255, 180, 80));
    }
    if (!_wcOk) {
      centerText("mac", L(56, 34), S(1, 1), CRGB(150, 150, 150));
      centerText("yok", L(70, 48), S(1, 1), CRGB(150, 150, 150));
    } else {
      if (_wcL1[0]) centerText(_wcL1, L(50, 26), S(1, 1), CRGB(230, 230, 230));
      if (_wcL2[0]) centerText(_wcL2, L(66, 42), S(1, 1), CRGB(120, 255, 140));
      if (_wcL3[0]) centerText(_wcL3, L(84, 64), S(1, 1), CRGB(140, 140, 140));
    }
    M->update();
  }

  void renderSpotify() {
    clear();
    centerText("SPOTIFY", L(14, 8), S(1, 1), CRGB(80, 230, 120));
    if (!_spOk) {
      centerText("baglanti", L(50, 34), S(1, 1), CRGB(160, 160, 160));
      centerText("gerekli", L(64, 48), S(1, 1), CRGB(160, 160, 160));
    } else {
      if (_spTrack[0])  centerText(_spTrack, L(48, 34), S(1, 1), CRGB(235, 235, 235));
      if (_spArtist[0]) centerText(_spArtist, L(70, 54), S(1, 1), CRGB(150, 200, 150));
    }
    M->update();
  }

  // ------------------------------------------------------------------ fetch
  String httpsGet(const String& url, const char* authHeader = nullptr) {
    WiFiClientSecure cl; cl.setInsecure();
    HTTPClient http;
    http.setConnectTimeout(6000);
    http.setTimeout(6000);
    String body;
    if (http.begin(cl, url)) {
      if (authHeader) http.addHeader("Authorization", authHeader);
      int code = http.GET();
      if (code == 200) body = http.getString();
      else Serial.printf("[apps] HTTP %d: %s\n", code, url.c_str());
      http.end();
    }
    return body;
  }

  // Basit JSON yardimcilari (ArduinoJson yok; kucuk/duz alanlar icin yeterli).
  // key ornek: "\"temperature_2m\":"  -> sayisal degeri dondurur.
  static float jnum(const String& s, const char* key, int from = 0) {
    int i = s.indexOf(key, from); if (i < 0) return NAN;
    i += strlen(key);
    while (i < (int)s.length() && (s[i] == ' ' || s[i] == '"')) i++;
    return atof(s.c_str() + i);
  }
  static String jstr(const String& s, const char* key, int from = 0) {
    int i = s.indexOf(key, from); if (i < 0) return String();
    i += strlen(key);
    while (i < (int)s.length() && (s[i] == ' ')) i++;
    if (i < (int)s.length() && s[i] == '"') i++;
    int j = i; while (j < (int)s.length() && s[j] != '"') j++;
    return s.substring(i, j);
  }

  void fetchWeather() {
    if (isnan(_lat)) return;
    char url[160];
    snprintf(url, sizeof(url),
      "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
      "&current=temperature_2m,weather_code&timezone=auto", _lat, _lon);
    String b = httpsGet(url);
    if (b.length() == 0) { _wxOk = false; return; }
    float t = jnum(b, "\"temperature_2m\":");
    float c = jnum(b, "\"weather_code\":");
    if (!isnan(t)) { _temp = t; _wcode = isnan(c) ? -1 : (int)c; _wxOk = true; }
    else _wxOk = false;
    Serial.printf("[apps] hava: %.1fC code=%d ok=%d\n", _temp, _wcode, _wxOk);
  }

  void fetchWorldCup() {
    String url = "https://www.thesportsdb.com/api/v1/json/" THESPORTSDB_KEY
                 "/eventsnextleague.php?id=" WORLDCUP_LEAGUE_ID;
    String b = httpsGet(url);
    bool ok = false;
    if (b.length() > 0 && b.indexOf("strHomeTeam") >= 0) {
      String home = jstr(b, "\"strHomeTeam\":");
      String away = jstr(b, "\"strAwayTeam\":");
      String date = jstr(b, "\"dateEvent\":");
      String tm   = jstr(b, "\"strTime\":");
      if (home.length()) {
        home = home.substring(0, 12); away = away.substring(0, 12);
        strlcpy(_wcL1, home.c_str(), sizeof(_wcL1));
        strlcpy(_wcL2, away.c_str(), sizeof(_wcL2));
        // tarih: YYYY-MM-DD -> DD.MM + saat (HH:MM)
        char l3[20] = "";
        if (date.length() >= 10)
          snprintf(l3, sizeof(l3), "%s.%s %s",
                   date.substring(8, 10).c_str(), date.substring(5, 7).c_str(),
                   tm.length() >= 5 ? tm.substring(0, 5).c_str() : "");
        strlcpy(_wcL3, l3, sizeof(_wcL3));
        ok = true;
      }
    }
    _wcOk = ok;
    Serial.printf("[apps] worldcup ok=%d (%s vs %s)\n", ok, _wcL1, _wcL2);
  }

  void fetchSpotify() {
    // ISKELET: token tarayicidan (PKCE) WS 0x0D ile gelir; burada sadece
    // su an calan parcayi sorgular. Token ~1 saatte dolar; yenileme YOK
    // (iskelet). Kurulum: web UI'daki "Spotify" bolumune bak.
    _spOk = false;
    if (_spToken[0] == 0) return;
    char auth[320]; snprintf(auth, sizeof(auth), "Bearer %s", _spToken);
    String b = httpsGet("https://api.spotify.com/v1/me/player/currently-playing", auth);
    if (b.length() == 0) return;
    String track = jstr(b, "\"name\":");                  // ilk "name" = parca
    String artist = jstr(b, "\"name\":", b.indexOf("artists"));  // artists icindeki ilk name
    if (track.length()) {
      strlcpy(_spTrack, track.substring(0, 18).c_str(), sizeof(_spTrack));
      strlcpy(_spArtist, artist.substring(0, 18).c_str(), sizeof(_spArtist));
      _spOk = true;
    }
  }

  // WMO hava kodu -> kisa Turkce metin (Open-Meteo weather_code)
  static const char* wmoText(int c) {
    if (c < 0) return "";
    if (c == 0) return "Acik";
    if (c <= 3) return "Bulutlu";
    if (c == 45 || c == 48) return "Sisli";
    if (c >= 51 && c <= 57) return "Ciseleme";
    if (c >= 61 && c <= 67) return "Yagmur";
    if (c >= 71 && c <= 77) return "Kar";
    if (c >= 80 && c <= 82) return "Saganak";
    if (c >= 85 && c <= 86) return "Kar yag.";
    if (c >= 95) return "Firtina";
    return "?";
  }
};
