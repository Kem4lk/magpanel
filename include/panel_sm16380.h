#pragma once
/*
  P1.86 172x86 1/43 modul surucusu: SM16380SH sutun surucu + SM5368 satir kaydirmali yazmac
  (YI YI STAR P1.86-INDOOR-Y52, etiket "16380SH-5368").

  FM6363C (P4, Matrix.h) ile FARKLARI:
  - DCLK hem veri saati hem PWM saatidir -> SUREKLI akmali. Surekli circular DMA
    modelimiz (tarama tamponu sonsuz dongude) bunu dogal olarak saglar.
  - Satir gecisi: her SLOT_WORDS DCLK'da bir satir; satir hatlari degisir, ardindan
    OE hattinda (HUB75 pin 15, eski GCLK biti d7) OE_WIDTH DCLK'lik tek darbe.
    Cip ic satir sayacini bu darbeyle ilerletir.
  - SM5368 ikili adres degil KAYDIRMALI yazmac: A = satir saati, B = BK
    (golge onleme), C = satir verisi. Satir 0'da C=1 itilir, her slotta A'nin
    yukselen kenari biti bir satir kaydirir. D/E kullanilmaz (0 tutulur).
  - Komutlar yine LE (LAT) genisligiyle: VSYNC=3, 11 ve 14 (on-aktivasyon).
    Register yazimi: 0x00AA, 0x01AA (kilit ac) -> deger -> 0x0055, 0x0155
    (kilitle); her kelime tum zincire, LE son 5 DCLK'da. Kelime = adres<<8 | deger.
  - Gri ton: kanal basina 16 bitlik kelime, MSB once; deger alt gs_bits bite
    (varsayilan 13) yazilir, ustteki bitler 0.

  Akis tamponu (PSRAM, tek DMA gonderimi):
    [PRE: 11 ve 14 LE komutlari] [satir yazmaci temizleme + satir0 + 12 DCLK OE
    "grup basi" + 88 bos] [SENKRON BOLGE: SCAN slotluk tam cevrimler; ustune
    register yazimi (1 cevrim) + 43 satirlik gri ton verisi]
  Senkron bolge tam cevrimlerle bittigi icin ardindan baslayan circular tarama
  tamponu (dahili RAM, 1 cevrim) satir fazini kesintisiz devralir.
  update() ayrica kucuk bir COMMIT akisi yollar (VSYNC + ayni on-ek): yeni kare
  gonderildigi AN gorunur (bir kare gecikme yok, eski kare yanip sonmez).

  Protokol bilgisi acik kaynak surucu calismalarindan (DMD_STM32 SPWM notlari,
  ESP32-HUB75-MatrixPanel-DMA SM5368 satir surucusu) ogrenildi; bu kod bagimsiz
  yazildi. Register degerleri alici kart profilinden (regtype6: "P1.86 -
  SM16380SH - 5368 - 1/43") alinmis donanim ayarlaridir.
*/

#include <Arduino.h>
#include <esp_heap_caps.h>
#include <esp_cache.h>
#include <GFX_Lite.h>
#include "app_constants.hpp"
#include "lcd_dma_parallel16.hpp"
#include "gamma16.h"

namespace sm16380 {

constexpr int W          = 172;
constexpr int H          = 86;
constexpr int SCAN       = 43;              // 1/43 tarama, yari basina 43 satir
constexpr int CHANS      = 16;              // SM16380SH kanal sayisi
constexpr int CHIPS      = (W + 15) / 16;   // renk hatti basina zincir: 11 cip (176 kanal)
constexpr int PASS_WORDS = CHIPS * 16;      // bir latch gecisi = 176 DCLK
constexpr int LINE_WORDS = CHANS * PASS_WORDS;  // tarama satiri basina veri: 2816
constexpr int SLOT_WORDS = 128;             // satir basina DCLK (satir gecisi + OE)
constexpr int CYCLE_WORDS = SLOT_WORDS * SCAN;  // 5504 = bir tam tarama cevrimi
constexpr int ROW_SW_WORDS = 4;             // slot basinda satir-gecis kelimeleri
constexpr int OE_POS     = 28;              // slot icinde OE darbesinin yeri
constexpr int OE_WIDTH   = 4;               // OE darbe genisligi (DCLK)
constexpr int ROWREG_LEN = 48;              // SM5368 zinciri: 6 cip x 8 cikis

// Veri bolgesini tam cevrime yuvarla (11 cip icin 121088 = tam 22 cevrim)
constexpr int DATA_WORDS   = LINE_WORDS * SCAN;
constexpr int DATA_CYCLES  = (DATA_WORDS + CYCLE_WORDS - 1) / CYCLE_WORDS;
constexpr int CFG_CYCLES   = 1;             // register yazimi (5 x 176 kelime) 1 cevrime sigar
constexpr int SYNC_WORDS   = (CFG_CYCLES + DATA_CYCLES) * CYCLE_WORDS;

// LE komut genislikleri
constexpr int LE_VSYNC   = 3;
constexpr int LE_CMD11   = 11;
constexpr int LE_PREACT  = 14;
constexpr int LE_REGWR   = 5;
constexpr int LE_DATA    = 1;

// Bus bitleri (Matrix.h ile ayni pin eslemesi: d7 = HUB75 OE pini, d8..d12 = A..E)
constexpr uint16_t B_OE = (1 << 7);
constexpr uint16_t B_A  = (1 << 8);
constexpr uint16_t B_B  = (1 << 9);
constexpr uint16_t B_C  = (1 << 10);
constexpr uint16_t B_D  = (1 << 11);
constexpr uint16_t B_E  = (1 << 12);
constexpr uint16_t B_ROWLINES = B_A | B_B | B_C | B_D | B_E;

// Alici kart profilleri (1/43 SM16380SH). Her biri R, G, B hatlari icin ayri
// 32 register kelimesi. [0] = regtype6: tam bu modul (SM16380SH + 5368).
struct RegProfile { const char *name; uint16_t v[3][32]; };
static const RegProfile REG_PROFILES[] = {
  { "rt6 P1.86 SM16380SH-5368 (etiket eslesmesi)", {
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x074c,0x0800,0x0900,0x0a02,0x0b0c,0x0c08,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1308,0x1414,0x1500,0x1630,0x1700,0x1803,0x1907,0x1a03,0x1b14,0x1c12,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 },
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x074c,0x0800,0x0900,0x0a02,0x0b0c,0x0c18,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1308,0x1402,0x1500,0x1630,0x1700,0x1802,0x1905,0x1a01,0x1b14,0x1c8f,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 },
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x074c,0x0800,0x0900,0x0a02,0x0b0c,0x0c30,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1308,0x1422,0x1500,0x1630,0x1700,0x1803,0x1905,0x1a01,0x1b14,0x1c8f,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 } } },
  { "rt9 P1.86 SM16380SH", {
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x074c,0x0800,0x0900,0x0a02,0x0b0c,0x0c08,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1308,0x1414,0x1500,0x163b,0x1700,0x1801,0x1904,0x1a03,0x1b14,0x1c12,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 },
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x074c,0x0800,0x0900,0x0a02,0x0b0c,0x0c18,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1308,0x1422,0x1500,0x163b,0x1700,0x1801,0x1903,0x1a01,0x1b14,0x1c8f,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 },
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x074c,0x0800,0x0900,0x0a02,0x0b0c,0x0c30,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1308,0x1432,0x1500,0x163b,0x1700,0x1801,0x1903,0x1a01,0x1b14,0x1c8f,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 } } },
  { "rt54 P1.86 SM16380SH", {
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x0748,0x0800,0x0900,0x0a02,0x0b0c,0x0c08,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1300,0x1414,0x1500,0x1633,0x1700,0x1801,0x1904,0x1a03,0x1b14,0x1c12,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 },
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x0748,0x0800,0x0900,0x0a02,0x0b0c,0x0c18,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1300,0x1422,0x1500,0x1630,0x1700,0x1801,0x1903,0x1a01,0x1b14,0x1c8f,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 },
    { 0x022a,0x0300,0x0400,0x0500,0x0600,0x0749,0x0800,0x0900,0x0a02,0x0b0c,0x0c30,0x0d00,0x0e05,0x0f00,0x1000,0x1100,
      0x1200,0x1300,0x1432,0x1500,0x1631,0x1700,0x1801,0x1903,0x1a01,0x1b14,0x1c8f,0x1d00,0x1e00,0x1f0c,0x2000,0x2200 } } },
};
constexpr int REG_PROFILE_COUNT = sizeof(REG_PROFILES) / sizeof(REG_PROFILES[0]);
constexpr int REG_COUNT = 32;

// Calisma aninda degistirilebilir kalibrasyon/teshis ayarlari (web UI'dan).
// Degisiklik sonrasi rebuild() cagrilmali (sablon + tarama tamponu yeniden kurulur).
struct Options {
  uint8_t row_mode    = 0;  // 0 = SM5368 kaydirma (A clk, B BK, C veri), 1 = ikili ABCDE adres
  uint8_t bk_mode     = 0;  // 0 = B sadece satir-gecis kelimelerinde 1, 1 = hep 1, 2 = hep 0
  bool    oe_invert   = false;  // OE darbesi aktif-dusuk ise
  uint8_t reg_profile = 0;
  uint8_t gs_bits     = 13;     // gri ton MSB konumu (12..16)
  bool    mirror_x    = false;  // cip + kanal sirasi ters
  bool    chan_rev    = false;  // sadece cip-ici kanal sirasi ters
  uint8_t col_layout  = 1;      // 0 = dogrusal (x_offset ile), 1 = P1.86-Y52: 172 piksel 176 kanala,
                                //     cip 0,1,9,10'un 0. kanali BOS (15+15+7x16+15+15). Izgara fotografiyla olculdu.
  uint8_t x_offset    = 0;      // sadece col_layout=0: bastaki bos kanal sayisi (0..4)
  bool    swap_halves = false;  // ust yari <- R2 grubu
  bool    flip_y      = false;  // yari-ici satir sirasi ters
  uint8_t row_offset  = 0;      // veri satiri <-> fiziksel satir kaymasi (0..42)
};

}  // namespace sm16380

class PanelSM16380 : public GFX {
 public:
  PanelSM16380() : GFX(sm16380::W, sm16380::H) {}

  // Matrix.h ile ayni imaj isleme alanlari (ileride ana uygulamaya takilabilsin)
  uint8_t global_brightness = 40;   // TEST varsayilani DUSUK: guc/isi guvenligi
  uint8_t gain_r = 255, gain_g = 255, gain_b = 255;
  sm16380::Options opt;

  bool initMatrix() {
    using namespace sm16380;
    // Akis tamponu: PSRAM, 64 B hizali (GDMA harici bellek kurali)
    pre_words_ = computePreWords();
    stream_words_ = pre_words_ + SYNC_WORDS;
    stream_bytes_ = ((stream_words_ * 2 + 63) / 64) * 64;
    stream_ = (uint16_t *)heap_caps_aligned_alloc(64, stream_bytes_, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    commit_words_ = commitWords();
    commit_ = (uint16_t *)heap_caps_malloc(((commit_words_ * 2 + 3) & ~3), MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA);
    scan_ = (uint16_t *)heap_caps_malloc(CYCLE_WORDS * 2, MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA);
    if (!stream_ || !commit_ || !scan_) {
      Serial.printf("[P186] bellek ayrilamadi: stream=%p commit=%p scan=%p\n", stream_, commit_, scan_);
      return false;
    }
    memset(stream_, 0, stream_bytes_);

    auto bus_cfg = bus_.config();
    bus_cfg.pin_wr = MBI_DCLK;
    bus_cfg.invert_pclk = false;
    bus_cfg.pin_d0 = MBI_G1;  bus_cfg.pin_d1 = MBI_B1;  bus_cfg.pin_d2 = MBI_R1;
    bus_cfg.pin_d3 = MBI_G2;  bus_cfg.pin_d4 = MBI_B2;  bus_cfg.pin_d5 = MBI_R2;
    bus_cfg.pin_d6 = MBI_LAT;
    bus_cfg.pin_d7 = MBI_GCLK;      // HUB75 OE pini
    bus_cfg.pin_d8 = ADDR_A_PIN;  bus_cfg.pin_d9 = ADDR_B_PIN;  bus_cfg.pin_d10 = ADDR_C_PIN;
    bus_cfg.pin_d11 = ADDR_D_PIN; bus_cfg.pin_d12 = ADDR_E_PIN;
    bus_cfg.pin_d13 = -1; bus_cfg.pin_d14 = -1; bus_cfg.pin_d15 = -1;
    bus_.config(bus_cfg);
    bus_.setup_lcd_dma_periph();
    bus_.set_clock_divider(16);     // 10 MHz baslangic (P4'te dogrulanan kademe)

    initialized_ = true;
    rebuild();
    rewriteAllRegisters();
    return true;
  }

  // Tum register'lari sirayla yaz (her update() bir register tasir). Profil ya da
  // surme ayari degisince cagrilir; mevcut goruntu verisi her seferinde yeniden gider.
  void rewriteAllRegisters() {
    for (int i = 0; i < sm16380::REG_COUNT; i++) { update(); delay(2); }
  }

  // Sablon/tarama tamponlarini ayarlara gore yeniden kur. RGB verisi korunur.
  void rebuild() {
    if (!initialized_) return;
    buildTemplate(true);
    buildCommit();
    buildScan();
  }

  void setClockDiv(uint32_t div) { bus_.set_clock_divider(div); }

  // Yeni kareyi gonder: akis (PRE + register + veri) -> COMMIT (VSYNC) -> surekli tarama
  void update() {
    using namespace sm16380;
    if (!initialized_) return;
    writeRegisterPasses(reg_index_);
    reg_index_ = (reg_index_ + 1) % REG_COUNT;
    esp_cache_msync(stream_, stream_bytes_, ESP_CACHE_MSYNC_FLAG_DIR_C2M);
    bus_.stop_dma();
    bus_.send_stuff_once(stream_, stream_words_ * 2, true);
    bus_.send_stuff_once(commit_, commit_words_ * 2, false);
    bus_.start_circular(scan_, CYCLE_WORDS * 2);
  }

  // Tarama dongusu durmussa yeniden baslat (loop()'tan guvenle cagrilir)
  void refresh() {
    if (initialized_ && !bus_.dma_is_running()) bus_.start_circular(scan_, sm16380::CYCLE_WORDS * 2);
  }

  void clear_pixels() {
    using namespace sm16380;
    uint16_t *d = stream_ + pre_words_ + CFG_CYCLES * CYCLE_WORDS;
    for (int i = 0; i < DATA_WORDS; i++) d[i] &= ~(uint16_t)BIT_ALL_RGB;
  }

  // Ham 16-bit PWM degerleriyle piksel (kalibrasyon testleri icin, gamma/parlaklik yok)
  void setPixelRaw(int x, int y, uint16_t r16, uint16_t g16, uint16_t b16) {
    using namespace sm16380;
    if (x < 0 || y < 0 || x >= W || y >= H) return;
    int half = y / SCAN;
    int line = y % SCAN;
    if (opt.flip_y) line = SCAN - 1 - line;
    line = (line + opt.row_offset) % SCAN;
    int lane = ((half == 0) != opt.swap_halves) ? 0 : 3;   // 0 = R1G1B1, 3 = R2G2B2

    int xx = opt.mirror_x ? (W - 1 - x) : x;
    if (opt.col_layout == 1) {
      xx = colLut(xx);
    } else {
      xx += opt.x_offset;
      if (xx >= CHIPS * 16) return;
    }
    int chip = xx / 16;
    int ch   = xx % 16;
    if (opt.chan_rev) ch = 15 - ch;

    const uint16_t rm = BIT_R1 << lane, gm = BIT_G1 << lane, bm = BIT_B1 << lane;
    const uint16_t clr = ~(uint16_t)(rm | gm | bm);
    const int sh = 16 - opt.gs_bits;   // 13 bit: ust 3 bit 0
    r16 >>= sh; g16 >>= sh; b16 >>= sh;
    uint16_t *w = stream_ + pre_words_ + CFG_CYCLES * CYCLE_WORDS
                + line * LINE_WORDS + ch * PASS_WORDS + chip * 16;
    for (int bit = 15; bit >= 0; bit--) {
      uint16_t v = *w & clr;
      if ((r16 >> bit) & 1) v |= rm;
      if ((g16 >> bit) & 1) v |= gm;
      if ((b16 >> bit) & 1) v |= bm;
      *w++ = v;
    }
  }

  // sRGB 8-bit piksel: kanal kazanci + parlaklik + gamma 2.2
  void setPixel(int x, int y, uint8_t r, uint8_t g, uint8_t b) {
    uint16_t bs = (uint16_t)global_brightness + 1;
    r = (uint8_t)((((uint16_t)r * (gain_r + 1)) >> 8) * bs >> 8);
    g = (uint8_t)((((uint16_t)g * (gain_g + 1)) >> 8) * bs >> 8);
    b = (uint8_t)((((uint16_t)b * (gain_b + 1)) >> 8) * bs >> 8);
    setPixelRaw(x, y, GAMMA16[r], GAMMA16[g], GAMMA16[b]);
  }

  // GFX (yazi/cizim) icin
  void drawPixel(int16_t x, int16_t y, uint16_t c565) override {
    uint8_t r = (c565 >> 8) & 0xf8, g = (c565 >> 3) & 0xfc, b = (c565 << 3);
    r |= r >> 5; g |= g >> 6; b |= b >> 5;
    setPixel(x, y, r, g, b);
  }
  void drawPixel(int16_t x, int16_t y, CRGB c) { setPixel(x, y, c.red, c.green, c.blue); }

  size_t streamBytes() const { return stream_bytes_; }

  // P1.86-Y52 sutun duzeni: fiziksel sutun -> zincir konumu. Bos konumlar (hic LED'e
  // gitmeyen kanallar): 0, 16, 144, 160 = cip 0/1/9/10'un 0. kanali.
  static int colLut(int px) {
    static uint8_t lut[sm16380::W];
    static bool built = false;
    if (!built) {
      int n = 0;
      for (int p = 0; p < sm16380::CHIPS * 16 && n < sm16380::W; p++) {
        if (p == 0 || p == 16 || p == 144 || p == 160) continue;
        lut[n++] = (uint8_t)p;
      }
      built = true;
    }
    return lut[px];
  }
  const char *profileName() const { return sm16380::REG_PROFILES[opt.reg_profile % sm16380::REG_PROFILE_COUNT].name; }

 private:
  Bus_Parallel16 bus_;
  bool initialized_ = false;
  uint16_t *stream_ = nullptr;   // PSRAM
  uint16_t *commit_ = nullptr;   // dahili DMA RAM
  uint16_t *scan_   = nullptr;   // dahili DMA RAM, 1 tarama cevrimi
  int pre_words_ = 0, stream_words_ = 0, commit_words_ = 0;
  size_t stream_bytes_ = 0;
  int reg_index_ = 0;

  // ---- satir hatti / OE desenleri ----
  uint16_t oeIdle() const { return opt.oe_invert ? sm16380::B_OE : 0; }
  uint16_t oeOn()   const { return opt.oe_invert ? 0 : sm16380::B_OE; }
  uint16_t bkBase() const { return opt.bk_mode == 1 ? sm16380::B_B : 0; }
  uint16_t bkPulse() const { return opt.bk_mode == 2 ? 0 : sm16380::B_B; }
  uint16_t idle() const { return oeIdle() | bkBase(); }

  static uint16_t binAddr(int row) { return (uint16_t)((row & 0x1F) << 8); }

  // Bir tarama slotunun k. kelimesi (RGB/LAT haric): satir gecisi + OE
  uint16_t slotWord(int row, int k) const {
    using namespace sm16380;
    uint16_t v = oeIdle() | bkBase();
    if (opt.row_mode == 1) {
      v |= binAddr(row);
    } else if (k < ROW_SW_WORDS) {
      // k=0: veri kur, k=1..2: A yuksek (yukselen kenar), k=3: A dusuk
      v |= bkPulse();
      if (row == 0 && k < 3) v |= B_C;
      if (k == 1 || k == 2) v |= B_A;
    }
    if (k >= OE_POS && k < OE_POS + OE_WIDTH) v = (v & ~B_OE) | oeOn();
    return v;
  }

  // ---- PRE / COMMIT on-ekleri ----
  // Kelime sayilari rebuild'lar arasinda SABIT kalmali (pre_words_ akis
  // yerlesimini belirler) -> uzunluklar ayarlardan bagimsiz.
  static constexpr int FLUSH_WORDS = sm16380::ROWREG_LEN * 2 + 1;
  static constexpr int INIT_WORDS  = 4 + 12 + 88;     // satir0 + OE12 + 88 bos
  static constexpr int CMD_WORDS   = 8 + sm16380::LE_CMD11 + 8 + sm16380::LE_PREACT + 8;

  int computePreWords() const {
    int n = CMD_WORDS + FLUSH_WORDS + INIT_WORDS;
    // Toplam akis 32 kelimenin (64 B) kati olsun: dolgu PRE'nin basina bos DCLK olarak
    int total = n + sm16380::SYNC_WORDS;
    int pad = (32 - (total % 32)) % 32;
    return n + pad;
  }
  int commitWords() const { return 1 + sm16380::LE_VSYNC + CMD_WORDS + FLUSH_WORDS + INIT_WORDS; }

  int emitIdle(uint16_t *b, int n) const { for (int i = 0; i < n; i++) b[i] = idle(); return n; }
  int emitLE(uint16_t *b, int n) const { for (int i = 0; i < n; i++) b[i] = idle() | BIT_LAT; return n; }
  int emitCmds(uint16_t *b) const {
    int p = 0;
    p += emitIdle(b + p, 8);
    p += emitLE(b + p, sm16380::LE_CMD11);
    p += emitIdle(b + p, 8);
    p += emitLE(b + p, sm16380::LE_PREACT);
    p += emitIdle(b + p, 8);
    return p;
  }
  // SM5368 zincirini sifirla (C=0 ile ROWREG_LEN saat), sonra satir 0'i sec,
  // 12 DCLK'lik OE "veri grubu basi" darbesi ve 88 bos DCLK.
  int emitFlushInit(uint16_t *b) const {
    using namespace sm16380;
    int p = 0;
    const bool sh = (opt.row_mode == 0);
    for (int i = 0; i < ROWREG_LEN; i++) {
      b[p++] = idle() | (sh ? bkPulse() : 0);
      b[p++] = idle() | (sh ? (bkPulse() | B_A) : 0);
    }
    b[p++] = idle();
    // satir 0
    if (sh) {
      b[p++] = idle() | bkPulse() | B_C;
      b[p++] = idle() | bkPulse() | B_C | B_A;
      b[p++] = idle() | bkPulse() | B_C | B_A;
      b[p++] = idle() | bkPulse();
    } else {
      for (int i = 0; i < 4; i++) b[p++] = idle() | binAddr(0);
    }
    const uint16_t a0 = sh ? 0 : binAddr(0);
    for (int i = 0; i < 12; i++) b[p++] = ((idle() & ~B_OE) | oeOn()) | a0;
    for (int i = 0; i < 88; i++) b[p++] = idle() | a0;
    return p;
  }

  void buildCommit() {
    int p = 0;
    commit_[p++] = idle();
    p += emitLE(commit_ + p, sm16380::LE_VSYNC);
    p += emitCmds(commit_ + p);
    p += emitFlushInit(commit_ + p);
  }

  // Surekli tarama tamponu: slot sirasi satir 1,2,...,42,0 (INIT satir 0'i actiktan sonra)
  void buildScan() {
    using namespace sm16380;
    for (int s = 0; s < SCAN; s++) {
      int row = (s + 1) % SCAN;
      for (int k = 0; k < SLOT_WORDS; k++) scan_[s * SLOT_WORDS + k] = slotWord(row, k);
    }
  }

  // Akis tamponunun kontrol bitlerini (OE, satir hatlari, LAT) yeniden yaz;
  // keepRgb ise mevcut RGB bitleri korunur.
  void buildTemplate(bool keepRgb) {
    using namespace sm16380;
    uint16_t *s = stream_;
    int n = computePreWords() - (CMD_WORDS + FLUSH_WORDS + INIT_WORDS);  // hizalama dolgusu
    int p = 0;
    for (int i = 0; i < n; i++) s[p++] = idle();
    p += emitCmds(s + p);
    p += emitFlushInit(s + p);
    // Senkron bolge
    for (int i = 0; i < SYNC_WORDS; i++) {
      int slot = i / SLOT_WORDS, k = i % SLOT_WORDS;
      int row = (slot + 1) % SCAN;
      uint16_t rgb = keepRgb ? (s[p + i] & BIT_ALL_RGB) : 0;
      uint16_t v = slotWord(row, k) | rgb;
      // Veri bolgesi: her 176 kelimelik gecisin son kelimesinde DATA_LATCH
      int d = i - CFG_CYCLES * CYCLE_WORDS;
      if (d >= 0 && d < DATA_WORDS && (d % PASS_WORDS) == PASS_WORDS - 1) v |= BIT_LAT;
      s[p + i] = v;
    }
  }

  // Register yazimi: senkron bolgenin ilk cevrimine 5 gecis (kilit ac, deger, kilitle)
  void writeRegisterPasses(int idx) {
    using namespace sm16380;
    const RegProfile &prof = REG_PROFILES[opt.reg_profile % REG_PROFILE_COUNT];
    uint16_t *base = stream_ + pre_words_;
    const uint16_t seq_r[5] = { 0x00aa, 0x01aa, prof.v[0][idx], 0x0055, 0x0155 };
    const uint16_t seq_g[5] = { 0x00aa, 0x01aa, prof.v[1][idx], 0x0055, 0x0155 };
    const uint16_t seq_b[5] = { 0x00aa, 0x01aa, prof.v[2][idx], 0x0055, 0x0155 };
    for (int pass = 0; pass < 5; pass++) {
      uint16_t *w = base + pass * PASS_WORDS;
      for (int c = 0; c < PASS_WORDS; c++) {
        int bit = 15 - (c & 15);
        uint16_t v = w[c] & ~(uint16_t)(BIT_ALL_RGB | BIT_LAT);
        if ((seq_r[pass] >> bit) & 1) v |= BIT_ALL_R;
        if ((seq_g[pass] >> bit) & 1) v |= BIT_ALL_G;
        if ((seq_b[pass] >> bit) & 1) v |= BIT_ALL_B;
        if (c >= PASS_WORDS - LE_REGWR) v |= BIT_LAT;
        w[c] = v;
      }
    }
  }
};
