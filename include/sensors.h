#pragma once
// ============================================================================
//  MagPanel sensorler & fiziksel kontroller - DONANIM YAPISTIRICISI (ESP32-S3)
// ----------------------------------------------------------------------------
//  Tasarim ilkesi (apps.h ile ayni): her sey FIRMWARE tarafinda, tarayicisiz
//  calisir; ayarlar NVS'te ("sensors"), tarayici/iOS sadece WS ile ayarlar ve
//  1 Hz "S:" telemetrisini izler. Baglanmamis sensor ZARAR VERMEZ:
//    * dokunmatik pini pull-DOWN (TTP223B push-pull aktif-yuksek) -> bos pin LOW
//    * enkoder pinleri pull-UP, tam-adim tablo -> gurultu adim uretmez
//    * DHT11 cevap vermezse "yok" (—) gosterilir, 5 sn'de bir yeniden dener
//    * LDR/mikrofon acikta gurultu okur ama oto-parlaklik/alkis VARSAYILAN KAPALI
//  Dusuk heap: dinamik bellek YOK (ADC surucusunun ilk kurulumu haric), kutuphane
//  YOK (DHT protokolu burada ~40 satir), JSON snprintf ile.
//
//  Pinler (hardware/README.md + hardware/schematic.svg ile birebir; -D ile degisir):
//    GPIO1  ADC1_CH0  LDR karti AO          (ADC2 WiFi ile CAKISIR -> sadece ADC1 = GPIO1..10)
//    GPIO2  ADC1_CH1  Mikrofon karti AO
//    GPIO42           Mikrofon karti DO     (istege bagli; 3 pinli kartta tek cikis budur)
//    GPIO41/40/39     KY-040 CLK / DT / SW  (SW aktif dusuk, dahili pull-up)
//    GPIO47           DHT11 DATA            (open-drain + pull-up; kart ustunde 10k var)
//    GPIO21           TTP223B OUT           (aktif yuksek, dahili pull-down)
//  HUB75 (3..18) ve P1.86 LAT2/LAT3 (17/14) ile cakismaz; 19/20 USB, 33..37 OPI PSRAM,
//  0/45/46 strapping, 38/48 devkit RGB LED'i bos birakildi.
// ============================================================================
#include <Arduino.h>
#include <Preferences.h>
#include <math.h>
#include "sensor_logic.h"
// NOT: ISR'ler IRAM_ATTR DEGIL, bilincli. Arduino cekirdegi GPIO ISR servisini
// CONFIG_ARDUINO_ISR_IRAM olmadan kurar (bu SDK'da kapali) -> kesme flash yazimi
// sirasinda otomatik askiya alinir, IRAM sart degil. Ayrica IRAM_ATTR'li inline/
// sinif-ici fonksiyonlar xtensa'da "l32r: literal placed after use" link hatasi verir.

#ifndef SENS_PIN_LDR
#define SENS_PIN_LDR     1
#endif
#ifndef SENS_PIN_MIC
#define SENS_PIN_MIC     2
#endif
#ifndef SENS_PIN_MIC_DO
#define SENS_PIN_MIC_DO  42     // -1 = bagli degil
#endif
#ifndef SENS_PIN_ENC_A
#define SENS_PIN_ENC_A   41     // KY-040 CLK
#endif
#ifndef SENS_PIN_ENC_B
#define SENS_PIN_ENC_B   40     // KY-040 DT
#endif
#ifndef SENS_PIN_ENC_SW
#define SENS_PIN_ENC_SW  39     // KY-040 SW
#endif
#ifndef SENS_PIN_DHT
#define SENS_PIN_DHT     47
#endif
#ifndef SENS_PIN_TOUCH
#define SENS_PIN_TOUCH   21
#endif
#ifndef SENS_DHT22
#define SENS_DHT22       0      // 1 = DHT22/AM2302 takili (ayni pin, ayni protokol)
#endif

// Fiziksel kontrol -> eylem eslemesi (web UI "Sensorler" karti, NVS)
enum SensAction : uint8_t {
  ACT_NONE     = 0,   // yok
  ACT_SLEEP    = 1,   // uyku / uyan (panel karanlik, icerik korunur)
  ACT_NEXT_APP = 2,   // sonraki uygulama (saat -> hava -> oda -> ses -> kapat)
  ACT_NEXT_GAL = 3,   // sonraki galeri tablosu
  ACT_AUTOBRI  = 4,   // oto parlaklik ac/kapat
  ACT_COUNT    = 5
};
enum SensEvent : uint8_t { EV_NONE = 0, EV_ENC_PRESS, EV_ENC_LONG, EV_TOUCH, EV_CLAP2, EV_CLAP1 };

struct SensConfig {
  uint8_t autoBri  = 0;            // 1 = LDR ile otomatik parlaklik (kullanici degeri = tavan)
  uint8_t briMin   = 10;           // oto parlaklik tabani (karanlik oda)
  uint8_t ldrInv   = 0;            // 1 = LDR karti isikta DUSEN gerilim veriyor
  uint8_t actPress = ACT_SLEEP;    // enkoder kisa basma
  uint8_t actLong  = ACT_NEXT_APP; // enkoder uzun basma (>= 0.7 sn)
  uint8_t actTouch = ACT_SLEEP;    // dokunmatik
  uint8_t actClap  = ACT_NONE;     // cift alkis (varsayilan kapali: mikrofon ayarina bagli)
  uint8_t clapThr  = 40;           // alkis esigi (% tam olcek, taban ustu)
  uint8_t encStep  = 8;            // detent basina parlaklik adimi
  uint8_t encInv   = 0;            // enkoder yonu ters
};

class Sensors {
 public:
  SensConfig cfg;
  bool micWanted = false;   // main: alkis acik / Ses uygulamasi / WS istemci varsa ornekle

  void begin() {
    load();
    pinMode(SENS_PIN_TOUCH,  INPUT_PULLDOWN);
    pinMode(SENS_PIN_ENC_A,  INPUT_PULLUP);
    pinMode(SENS_PIN_ENC_B,  INPUT_PULLUP);
    pinMode(SENS_PIN_ENC_SW, INPUT_PULLUP);
    // DHT: open-drain + pull-up; LOW = hatti cek, HIGH = birak (kart 10k ile yukari ceker)
    pinMode(SENS_PIN_DHT, OUTPUT_OPEN_DRAIN | PULLUP);
    digitalWrite(SENS_PIN_DHT, HIGH);
    analogReadResolution(12);
    analogSetPinAttenuation(SENS_PIN_LDR, ADC_11db);   // 0..~3.1 V tam olcek
    analogSetPinAttenuation(SENS_PIN_MIC, ADC_11db);
    _touch.fireOnPress = true; _touch.debounceMs = 20;
    _encBtn.debounceMs = 30;   _encBtn.longMs = 700;
    instRef() = this;
    _enc.step(encAB());
    attachInterrupt(digitalPinToInterrupt(SENS_PIN_ENC_A), encIsr, CHANGE);
    attachInterrupt(digitalPinToInterrupt(SENS_PIN_ENC_B), encIsr, CHANGE);
#if SENS_PIN_MIC_DO >= 0
    pinMode(SENS_PIN_MIC_DO, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(SENS_PIN_MIC_DO), micDoIsr, CHANGE);
#endif
    _dhtNext = millis() + 1500;  // DHT11 acilista ~1 sn ister
    _ldrNext = millis() + 200;
  }

  // loop()'tan her turda; bloklamaz (DHT okumasi 2 fazli, ~4 ms kritik bolge 3 sn'de bir)
  void loop() {
    uint32_t now = millis();
    // --- butonlar ---
    uint8_t r = _encBtn.feed(digitalRead(SENS_PIN_ENC_SW) == LOW, now);
    if (r == senslogic::BTN_SHORT) push(EV_ENC_PRESS); else if (r == senslogic::BTN_LONG) push(EV_ENC_LONG);
    if (_touch.feed(digitalRead(SENS_PIN_TOUCH) == HIGH, now) == senslogic::BTN_SHORT) push(EV_TOUCH);
    // --- LDR (10 Hz, EMA ~1 sn) ---
    if ((int32_t)(now - _ldrNext) >= 0) {
      _ldrNext = now + 100;
      int32_t v = (int32_t)analogRead(SENS_PIN_LDR) << 4;
      if (_ldrEma < 0) _ldrEma = v; else _ldrEma += (v - _ldrEma) >> 3;
      _light = senslogic::lightPercent((uint16_t)(_ldrEma >> 4), cfg.ldrInv != 0);
    }
    // --- mikrofon (<= 2 kHz ornek, 20 ms pencere) ---
    if (micWanted) {
      uint32_t us = micros();
      if (us - _micLastUs >= 500) {
        _micLastUs = us;
        if (_env.feed(analogRead(SENS_PIN_MIC), now)) {
          uint32_t amp = (uint32_t)_env.lastAmp * 100 / 4095;
#if SENS_PIN_MIC_DO >= 0
          uint16_t e = _doEdges; _doEdges = 0;          // komparator tetiklediyse "yuksek" say
          if (e && amp < 100) amp = 100;
#endif
          _soundPk = (uint8_t)amp;
          _sound = (uint8_t)((uint32_t)_env.smoothed() * 100 / 4095);
          _clap.threshold = cfg.clapThr;
          uint8_t c = _clap.feed((uint8_t)amp, now);
          if (c == 2) push(EV_CLAP2); else if (c == 1) push(EV_CLAP1);
        }
      }
    } else { _sound = 0; _soundPk = 0; }
    // --- DHT11: faz 0 = hatti cek (>= 18 ms), faz 1 = birak ve 40 biti oku ---
    if (_dhtPhase == 0) {
      if ((int32_t)(now - _dhtNext) >= 0) { digitalWrite(SENS_PIN_DHT, LOW); _dhtT0 = now; _dhtPhase = 1; }
    } else if (now - _dhtT0 >= 20) {
      bool ok = dhtRead();
      _dhtPhase = 0;
      _dhtNext = now + (ok ? 3000 : 5000);
    }
  }

  SensEvent poll() {
    if (_qh == _qt) return EV_NONE;
    SensEvent e = (SensEvent)_q[_qt]; _qt = (_qt + 1) & 7; return e;
  }
  // Son cagridan beri enkoder detent sayisi (isaretli; yon ayari uygulanmis)
  int16_t takeEncoderDelta() {
    noInterrupts(); int16_t d = _encAcc; _encAcc = 0; interrupts();
    return cfg.encInv ? (int16_t)-d : d;
  }

  // ---- okumalar ----
  bool     dhtOk()  const { return _dhtOk; }
  int16_t  temp10() const { return _temp10; }        // 0.1 C
  uint16_t hum10()  const { return _hum10; }         // 0.1 %
  uint8_t  light()  const { return _light; }         // 0..100 %
  uint16_t lightRaw() const { return _ldrEma < 0 ? 0 : (uint16_t)(_ldrEma >> 4); }
  uint8_t  sound()  const { return _sound; }         // 0..100 yumusatilmis (VU)
  uint8_t  soundPeak() const { return _soundPk; }    // son 20 ms pencere
  bool     touchHeld() const { return _touch.held(); }
  bool     encHeld()   const { return _encBtn.held(); }
  uint32_t dhtFails()  const { return _dhtFailTotal; }

  // ---- NVS ("sensors") ----
  void load() {
    Preferences p; p.begin("sensors", false);       // RW: ilk acilista "namespace yok" logu olmasin
    cfg.autoBri  = p.getUChar("ab",   cfg.autoBri);
    cfg.briMin   = p.getUChar("bmin", cfg.briMin);
    cfg.ldrInv   = p.getUChar("linv", cfg.ldrInv);
    cfg.actPress = p.getUChar("pa",   cfg.actPress);
    cfg.actLong  = p.getUChar("la",   cfg.actLong);
    cfg.actTouch = p.getUChar("ta",   cfg.actTouch);
    cfg.actClap  = p.getUChar("ca",   cfg.actClap);
    cfg.clapThr  = p.getUChar("thr",  cfg.clapThr);
    cfg.encStep  = p.getUChar("step", cfg.encStep);
    cfg.encInv   = p.getUChar("einv", cfg.encInv);
    p.end();
    sanitize();
  }
  void save() {
    sanitize();
    Preferences p; p.begin("sensors", false);
    p.putUChar("ab", cfg.autoBri);  p.putUChar("bmin", cfg.briMin);  p.putUChar("linv", cfg.ldrInv);
    p.putUChar("pa", cfg.actPress); p.putUChar("la", cfg.actLong);   p.putUChar("ta", cfg.actTouch);
    p.putUChar("ca", cfg.actClap);  p.putUChar("thr", cfg.clapThr);  p.putUChar("step", cfg.encStep);
    p.putUChar("einv", cfg.encInv);
    p.end();
  }
  void sanitize() {
    if (cfg.actPress >= ACT_COUNT) cfg.actPress = ACT_NONE;
    if (cfg.actLong  >= ACT_COUNT) cfg.actLong  = ACT_NONE;
    if (cfg.actTouch >= ACT_COUNT) cfg.actTouch = ACT_NONE;
    if (cfg.actClap  >= ACT_COUNT) cfg.actClap  = ACT_NONE;
    if (cfg.clapThr < 5) cfg.clapThr = 5; if (cfg.clapThr > 100) cfg.clapThr = 100;
    if (cfg.encStep < 1) cfg.encStep = 1; if (cfg.encStep > 64) cfg.encStep = 64;
    cfg.autoBri = cfg.autoBri ? 1 : 0; cfg.ldrInv = cfg.ldrInv ? 1 : 0; cfg.encInv = cfg.encInv ? 1 : 0;
  }

  // ---- JSON parcalari (suslu parantezsiz; main.cpp sarar) ----
  // okumalar: t/h (DHT yoksa null), d = DHT var, l = isik %, s = ses (VU) %, p = ses tepe %,
  // tc = dokunmatik basili, eh = enkoder dugmesi basili
  int jsonReadings(char* b, size_t n) const {
    int k;
    if (_dhtOk) k = snprintf(b, n, "\"t\":%d.%d,\"h\":%u,\"d\":1", _temp10 / 10, abs(_temp10 % 10), (unsigned)((_hum10 + 5) / 10));
    else        k = snprintf(b, n, "\"t\":null,\"h\":null,\"d\":0");
    if (k < 0 || (size_t)k >= n) return k;
    k += snprintf(b + k, n - k, ",\"l\":%u,\"s\":%u,\"p\":%u,\"tc\":%d,\"eh\":%d",
                  _light, _sound, _soundPk, _touch.held() ? 1 : 0, _encBtn.held() ? 1 : 0);
    return k;
  }
  int jsonConfig(char* b, size_t n) const {
    return snprintf(b, n, "\"ab\":%u,\"bmin\":%u,\"linv\":%u,\"pa\":%u,\"la\":%u,\"ta\":%u,\"ca\":%u,\"thr\":%u,\"step\":%u,\"einv\":%u",
                    cfg.autoBri, cfg.briMin, cfg.ldrInv, cfg.actPress, cfg.actLong, cfg.actTouch, cfg.actClap,
                    cfg.clapThr, cfg.encStep, cfg.encInv);
  }

  static const char* actionName(uint8_t a) {
    static const char* N[ACT_COUNT] = { "yok", "uyku/uyan", "sonraki uygulama", "sonraki galeri", "oto parlaklik" };
    return a < ACT_COUNT ? N[a] : "?";
  }
  static const char* eventName(SensEvent e) {
    switch (e) {
      case EV_ENC_PRESS: return "enkoder bas";
      case EV_ENC_LONG:  return "enkoder uzun bas";
      case EV_TOUCH:     return "dokunmatik";
      case EV_CLAP2:     return "cift alkis";
      case EV_CLAP1:     return "tek alkis";
      default:           return "-";
    }
  }

 private:
  // --- enkoder (ISR) ---
  static Sensors*& instRef() { static Sensors* p = nullptr; return p; }
  senslogic::EncoderDecoder _enc;
  volatile int16_t _encAcc = 0;
  static inline uint8_t encAB() {
    return (uint8_t)((digitalRead(SENS_PIN_ENC_B) << 1) | digitalRead(SENS_PIN_ENC_A));
  }
  static void encIsr() {
    Sensors* s = instRef(); if (!s) return;
    uint8_t d = s->_enc.step(encAB());
    if (d == senslogic::ENC_CW) s->_encAcc++; else if (d == senslogic::ENC_CCW) s->_encAcc--;
  }
#if SENS_PIN_MIC_DO >= 0
  volatile uint16_t _doEdges = 0;
  static void micDoIsr() { Sensors* s = instRef(); if (s) s->_doEdges++; }
#endif

  // --- butonlar / olay kuyrugu ---
  senslogic::ButtonFsm _encBtn, _touch;
  uint8_t _q[8]; uint8_t _qh = 0, _qt = 0;
  void push(SensEvent e) { uint8_t n = (_qh + 1) & 7; if (n == _qt) return; _q[_qh] = e; _qh = n; }

  // --- LDR ---
  int32_t  _ldrEma = -1;          // x16
  uint32_t _ldrNext = 0;
  uint8_t  _light = 0;

  // --- mikrofon ---
  senslogic::Envelope     _env;
  senslogic::ClapDetector _clap;
  uint32_t _micLastUs = 0;
  uint8_t  _sound = 0, _soundPk = 0;

  // --- DHT ---
  portMUX_TYPE _mux = portMUX_INITIALIZER_UNLOCKED;
  uint8_t  _dhtPhase = 0;
  uint32_t _dhtT0 = 0, _dhtNext = 0, _dhtFailTotal = 0;
  uint8_t  _dhtFails = 0;
  bool     _dhtOk = false;
  int16_t  _temp10 = 0; uint16_t _hum10 = 0;

  static inline bool waitLevel(int lvl, uint32_t timeoutUs) {
    uint32_t t0 = micros();
    while (digitalRead(SENS_PIN_DHT) != lvl) { if ((uint32_t)(micros() - t0) > timeoutUs) return false; }
    return true;
  }
  // Hat >= 18 ms LOW tutulmus durumda cagrilir: birak, cevabi + 40 biti oku.
  // Zamanlama icin ~4 ms kritik bolge (bu cekirdekte kesmeler kapali; DMA/WiFi etkilenmez).
  bool dhtRead() {
    uint16_t hi[40];
    bool ok = true;
    portENTER_CRITICAL(&_mux);
    digitalWrite(SENS_PIN_DHT, HIGH);            // birak -> pull-up yukari ceker
    delayMicroseconds(5);
    ok = waitLevel(HIGH, 60);                    // hat serbest kaldi
    if (ok) ok = waitLevel(LOW, 100);            // sensor cevabi: 80 us LOW
    if (ok) ok = waitLevel(HIGH, 120);
    if (ok) ok = waitLevel(LOW, 120);            // 80 us HIGH bitti -> ilk bitin LOW'u
    for (int i = 0; ok && i < 40; i++) {
      ok = waitLevel(HIGH, 100);                 // 50 us LOW
      if (!ok) break;
      uint32_t t0 = micros();
      ok = waitLevel(LOW, 120);                  // 26-28 us = 0, ~70 us = 1
      hi[i] = (uint16_t)(micros() - t0);
    }
    portEXIT_CRITICAL(&_mux);
    uint8_t b[5];
    if (ok) ok = senslogic::dhtDecode(hi, b);
    senslogic::DhtReading rd;
    if (ok) { rd = senslogic::dhtParse(b, SENS_DHT22 != 0); ok = rd.ok; }
    if (!ok) {
      _dhtFailTotal++;
      if (_dhtFails < 255) _dhtFails++;
      if (_dhtFails >= 3) _dhtOk = false;        // 3 ardisik hata: sensor yok/koptu
      return false;
    }
    _temp10 = rd.temp10; _hum10 = rd.hum10; _dhtOk = true; _dhtFails = 0;
    return true;
  }
};
