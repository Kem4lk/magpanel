#pragma once
// ============================================================================
//  MagPanel sensor mantigi - SAF C++ (Arduino/ESP-IDF bagimsiz)
// ----------------------------------------------------------------------------
//  sensors.h (donanim yapistiricisi) bu dosyayi kullanir; tools/test_sensor_logic.cpp
//  ayni kodu HOST'ta (g++) test eder. Burada pinMode/analogRead/millis YOK:
//  her sey "ornek degeri + zaman damgasi" alir, saf durum makinesidir.
//    * EncoderDecoder : KY-040 quadrature, tam-adim, sicrama (bounce) toleransli
//    * ButtonFsm      : debounce + kisa/uzun basma (enkoder dugmesi, TTP223B)
//    * dhtDecode/Parse: DHT11 (ve DHT22) 40 bitlik karesi -> sicaklik/nem
//    * Envelope       : mikrofon ADC orneklerinden 20 ms'lik pencere genligi
//    * ClapDetector   : genlik zarfindan tek/cift alkis
//    * autoBrightness : LDR yuzdesi -> parlaklik (min..kullanici) eslemesi
// ============================================================================
#include <stdint.h>

// Enkoder cozucu GPIO ISR'inden cagrilir. Arduino cekirdegi GPIO kesmesini IRAM'siz
// kurdugundan (flash yazimi sirasinda askiya alinir) ozel bellek niteligi gerekmez;
// istenirse buradan IRAM_ATTR/DRAM_ATTR verilebilir (host derlemesinde bos).
#ifndef SENSLOGIC_IRAM_ATTR
#define SENSLOGIC_IRAM_ATTR
#endif
#ifndef SENSLOGIC_DRAM_ATTR
#define SENSLOGIC_DRAM_ATTR
#endif

namespace senslogic {

// ---------------------------------------------------------------- enkoder
// Buxton tam-adim durum tablosu: her detent'te (A=B=1 konumuna donuste) TEK
// yon olayi uretir; ara sicramalar durumu geri sarar, sahte adim uretmez.
enum : uint8_t { ENC_NONE = 0x00, ENC_CW = 0x10, ENC_CCW = 0x20 };

struct EncoderDecoder {
  uint8_t state = 0;
  // ab: bit0 = A (CLK) seviyesi, bit1 = B (DT) seviyesi. Donus: ENC_CW/ENC_CCW/ENC_NONE
  SENSLOGIC_IRAM_ATTR uint8_t step(uint8_t ab) {
    enum { R_START, R_CW_FINAL, R_CW_BEGIN, R_CW_NEXT, R_CCW_BEGIN, R_CCW_FINAL, R_CCW_NEXT };
    static const SENSLOGIC_DRAM_ATTR uint8_t T[7][4] = {
      {R_START,    R_CW_BEGIN,  R_CCW_BEGIN, R_START},            // R_START
      {R_CW_NEXT,  R_START,     R_CW_FINAL,  R_START | ENC_CW},   // R_CW_FINAL
      {R_CW_NEXT,  R_CW_BEGIN,  R_START,     R_START},            // R_CW_BEGIN
      {R_CW_NEXT,  R_CW_BEGIN,  R_CW_FINAL,  R_START},            // R_CW_NEXT
      {R_CCW_NEXT, R_START,     R_CCW_BEGIN, R_START},            // R_CCW_BEGIN
      {R_CCW_NEXT, R_CCW_FINAL, R_START,     R_START | ENC_CCW},  // R_CCW_FINAL
      {R_CCW_NEXT, R_CCW_FINAL, R_CCW_BEGIN, R_START},            // R_CCW_NEXT
    };
    state = T[state & 0x0F][ab & 0x03];
    return state & 0x30;
  }
};

// ------------------------------------------------------------------ buton
// level: true = basili (polarite disarida normalize edilir).
//   fireOnPress = false : kisa basma BIRAKINCA (uzun basmayla ayirt etmek icin),
//                         uzun basma esik dolunca bir kez (basili tutarken)
//   fireOnPress = true  : basar basmaz 1 (dokunmatik icin: uzun basma yok)
enum : uint8_t { BTN_NONE = 0, BTN_SHORT = 1, BTN_LONG = 2 };

struct ButtonFsm {
  uint16_t debounceMs = 30;
  uint16_t longMs     = 700;
  bool     fireOnPress = false;
  // durum
  bool     raw = false, stable = false, longFired = false;
  uint32_t rawSince = 0, pressAt = 0;

  uint8_t feed(bool level, uint32_t ms) {
    if (level != raw) { raw = level; rawSince = ms; }
    if (raw == stable) {
      if (stable && !fireOnPress && !longFired && (uint32_t)(ms - pressAt) >= longMs) {
        longFired = true; return BTN_LONG;
      }
      return BTN_NONE;
    }
    if ((uint32_t)(ms - rawSince) < debounceMs) return BTN_NONE;   // henuz kararli degil
    stable = raw;
    if (stable) {                     // basildi
      pressAt = ms; longFired = false;
      return fireOnPress ? BTN_SHORT : BTN_NONE;
    }
    // birakildi
    if (fireOnPress || longFired) return BTN_NONE;
    return BTN_SHORT;
  }
  bool held() const { return stable; }
};

// ------------------------------------------------------------------ DHT11
// highUs[40]: her bitin YUKSEK suresi (us). DHT11/22: "0" ~26-28 us, "1" ~70 us.
// Donus: checksum dogruysa true, out[5] dolar.
inline bool dhtDecode(const uint16_t* highUs, uint8_t out[5], uint16_t thresholdUs = 45) {
  for (int i = 0; i < 5; i++) out[i] = 0;
  for (int i = 0; i < 40; i++)
    if (highUs[i] > thresholdUs) out[i >> 3] |= (uint8_t)(0x80 >> (i & 7));
  uint8_t sum = (uint8_t)(out[0] + out[1] + out[2] + out[3]);
  return sum == out[4];
}

struct DhtReading { int16_t temp10 = 0; uint16_t hum10 = 0; bool ok = false; };  // 0.1 birim

// DHT11: b0 nem tam, b1 nem ondalik, b2 sicaklik tam, b3 sicaklik ondalik (bit7 = eksi, bazi klonlar)
// DHT22: b0b1 nem x10, b2b3 sicaklik x10 (b2 bit7 = eksi)
inline DhtReading dhtParse(const uint8_t b[5], bool dht22 = false) {
  DhtReading r;
  if (dht22) {
    r.hum10  = (uint16_t)((b[0] << 8) | b[1]);
    int16_t t = (int16_t)(((b[2] & 0x7F) << 8) | b[3]);
    r.temp10 = (b[2] & 0x80) ? (int16_t)-t : t;
  } else {
    r.hum10  = (uint16_t)(b[0] * 10 + (b[1] < 10 ? b[1] : 0));
    int16_t t = (int16_t)(b[2] * 10 + ((b[3] & 0x7F) < 10 ? (b[3] & 0x7F) : 0));
    r.temp10 = (b[3] & 0x80) ? (int16_t)-t : t;
  }
  // makul aralik kontrolu (bozuk okumayi ele)
  r.ok = (r.hum10 <= 1000) && (r.temp10 >= -400) && (r.temp10 <= 850);
  return r;
}

// -------------------------------------------------------------- zarf (mic)
// Pencere icinde min/max tutar; pencere kapaninca genlik (max-min) hazir olur.
struct Envelope {
  uint16_t winMs = 20;
  uint16_t mn = 0xFFFF, mx = 0;
  uint32_t winStart = 0;
  bool     started = false;
  uint16_t lastAmp = 0;     // son kapanan pencerenin ham genligi
  uint32_t smooth = 0;      // gosterim icin EMA (x16 sabit nokta)

  // true = pencere kapandi, lastAmp/smooth guncellendi
  bool feed(uint16_t sample, uint32_t ms) {
    if (!started) { started = true; winStart = ms; mn = mx = sample; return false; }
    if (sample < mn) mn = sample;
    if (sample > mx) mx = sample;
    if ((uint32_t)(ms - winStart) < winMs) return false;
    lastAmp = (uint16_t)(mx - mn);
    // hizli yukselis, yavas dusus (VU hissi)
    uint32_t a16 = (uint32_t)lastAmp << 4;
    if (a16 > smooth) smooth = a16; else smooth -= (smooth - a16) >> 2;
    winStart = ms; mn = mx = sample;
    return true;
  }
  uint16_t smoothed() const { return (uint16_t)(smooth >> 4); }
};

// ------------------------------------------------------------------ alkis
// amp: 0..100 (tam olcek yuzdesi), her pencere (20 ms) bir kez cagrilir.
// Donus: 0 yok, 1 = tek alkis (ikincisi gelmedi, zaman asimi), 2 = cift alkis.
struct ClapDetector {
  uint8_t  threshold = 40;     // baseline ustu yuzde
  uint16_t minGapMs  = 120;    // iki alkis arasi en az (ayni alkisin kuyrugu sayilmasin)
  uint16_t maxGapMs  = 700;    // en fazla (yoksa tek alkis)
  uint16_t maxClapMs = 160;    // daha uzun suren gurultu alkis degil
  // durum
  uint16_t base16 = 0;         // sessizlik tabani (x16)
  bool     inBurst = false;
  uint32_t burstStart = 0, firstClapAt = 0;
  uint8_t  count = 0;

  uint8_t feed(uint8_t amp, uint32_t ms) {
    uint8_t base = (uint8_t)(base16 >> 4);
    uint16_t on  = (uint16_t)base + threshold;
    uint16_t off = (uint16_t)base + (threshold >> 1);
    uint8_t ev = 0;
    if (!inBurst) {
      if (amp >= on) { inBurst = true; burstStart = ms; }
      else {
        // taban: sadece sessizken, yavas takip (pencere ~20 ms -> ~1.3 s zaman sabiti)
        uint16_t a16 = (uint16_t)amp << 4;
        if (a16 > base16) base16 += (a16 - base16) >> 6; else base16 -= (base16 - a16) >> 6;
      }
    } else if (amp < off) {
      inBurst = false;
      uint32_t dur = ms - burstStart;
      if (dur <= maxClapMs) {
        if (count == 0) { count = 1; firstClapAt = burstStart; }
        else {
          uint32_t gap = burstStart - firstClapAt;
          if (gap >= minGapMs && gap <= maxGapMs) { count = 0; ev = 2; }
          else { count = 1; firstClapAt = burstStart; }   // cok erken/gec -> yeni ilk alkis
        }
      } else count = 0;            // uzun gurultu: diziyi boz
    }
    if (count == 1 && !inBurst && (uint32_t)(ms - firstClapAt) > maxGapMs) { count = 0; ev = 1; }
    return ev;
  }
};

// ---------------------------------------------------------- oto parlaklik
// light 0..100 (%). Donus: minB .. userMax arasinda dogrusal.
inline uint8_t autoBrightness(uint8_t light, uint8_t userMax, uint8_t minB) {
  if (light > 100) light = 100;
  if (userMax <= minB) return userMax;
  return (uint8_t)(minB + (uint16_t)(userMax - minB) * light / 100);
}

// LDR ADC (0..4095) -> yuzde; invert: kart isikta dusen gerilim veriyorsa
inline uint8_t lightPercent(uint16_t adc, bool invert) {
  uint32_t p = (uint32_t)adc * 100 / 4095;
  if (p > 100) p = 100;
  return (uint8_t)(invert ? 100 - p : p);
}

} // namespace senslogic
