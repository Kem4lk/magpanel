#ifndef MATRIX_H
#define MATRIX_H

#include <driver/gpio.h>
#include <esp_log.h>
#include <esp_task_wdt.h>

#include <iostream>

#include "Arduino.h"
#include "app_constants.hpp"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lcd_dma_parallel16.hpp"
#include "sdkconfig.h"
#include <array>
#include <GFX_Lite.h>

#ifndef _swap_int16_t
#define _swap_int16_t(a, b) \
  {                         \
    int16_t t = a;          \
    a = b;                  \
    b = t;                  \
  }
#endif

/*
  FM6363C S-PWM driver - command summary (FM6363 Control & Programming Guide v0.1)

  Commands are encoded by the number of DCLK rising edges while LE is high:
    DATA_LATCH=1, WR_DBG=2, VSYNC=3, WR_CFG1=4, WR_CFG2=6, WR_CFG3=8,
    WR_CFG4=10, EN_OP=12, DIS_OP=13, PRE_ACT=14, MBIST=15

  Init sequence per guide:
    PRE_ACT -> EN_OP -> PRE_ACT -> WR_CFG1 -> PRE_ACT -> WR_CFG2
            -> PRE_ACT -> WR_CFG3 -> PRE_ACT -> WR_CFG4

  Display timing:
    VSYNC -> 4 GCLK frame header -> 74 GCLKs per line (dual-edge counting),
    fixed 8x refresh multiplication (S-PWM).
*/

static const char *TAG = "Matrix.h";

// CIE - Lookup table for converting between perceived LED brightness and PWM
const uint16_t CIE[256] = {
    0,    0,    0,    0,    0,    1,    1,    1,    1,    1,    1,    1,    1,    1,    2,    2,
    2,    2,    2,    2,    2,    2,    2,    3,    3,    3,    3,    3,    3,    3,    3,    4,
    4,    4,    4,    4,    4,    5,    5,    5,    5,    5,    6,    6,    6,    6,    6,    7,
    7,    7,    7,    8,    8,    8,    8,    9,    9,    9,   10,   10,   10,   10,   11,   11,
   11,   12,   12,   12,   13,   13,   13,   14,   14,   15,   15,   15,   16,   16,   17,   17,
   17,   18,   18,   19,   19,   20,   20,   21,   21,   22,   22,   23,   23,   24,   24,   25,
   25,   26,   26,   27,   28,   28,   29,   29,   30,   31,   31,   32,   32,   33,   34,   34,
   35,   36,   37,   37,   38,   39,   39,   40,   41,   42,   43,   43,   44,   45,   46,   47,
   47,   48,   49,   50,   51,   52,   53,   54,   54,   55,   56,   57,   58,   59,   60,   61,
   62,   63,   64,   65,   66,   67,   68,   70,   71,   72,   73,   74,   75,   76,   77,   79,
   80,   81,   82,   83,   85,   86,   87,   88,   90,   91,   92,   94,   95,   96,   98,   99,
  100,  102,  103,  105,  106,  108,  109,  110,  112,  113,  115,  116,  118,  120,  121,  123,
  124,  126,  128,  129,  131,  132,  134,  136,  138,  139,  141,  143,  145,  146,  148,  150,
  152,  154,  155,  157,  159,  161,  163,  165,  167,  169,  171,  173,  175,  177,  179,  181,
  183,  185,  187,  189,  191,  193,  196,  198,  200,  202,  204,  207,  209,  211,  214,  216,
  218,  220,  223,  225,  228,  230,  232,  235,  237,  240,  242,  245,  247,  250,  252,  255,
};

class Matrix : public GFX {

 public:
  Matrix() : GFX (PANEL_PHY_RES_X, PANEL_PHY_RES_Y) {  }

  // v14 ROW-SLOT sablonuyla SIFIRDAN olculmeli: eski 18/4 degerleri, eski
  // sablonun kanal-sacilmasini kismen kompanse eden degerlerdi. drawCard
  // testiyle yeniden tara; buyuk ihtimalle iki yarim icin AYNI deger cikacak.
  int row_offset_top = 0;
  int row_offset_bottom = 0;
  // Global parlaklik (0-255). CIE'den ONCE uygulanir: karartma algisal
  // egriden gecer, kontrast korunur. Ic mekan icin ~110 iyi baslangic.
  uint8_t global_brightness = 110;
  // Beyaz nokta kalibrasyonu: kanal basina kazanc (0-255). Alici kartsiz
  // suruste panelin ham karakteri tipik olarak maviye kayar; once B'yi,
  // sonra G'yi indirerek beyazi notr yap. 0x06 komutuyla canli ayarlanir.
  uint8_t gain_r = 255, gain_g = 255, gain_b = 255;
  // Standart imaj ayarlari (128 = notr). Islem sirasi:
  // doygunluk -> kontrast -> kanal kazanci -> parlaklik -> CIE
  uint8_t img_contrast   = 128;
  uint8_t img_saturation = 128;

  ~Matrix() {
  }

  /***************************************** FM6363 STUFF  *****************************************/

  void initMatrix()
  {
    // Step 1) Allocate raw buffer space for greyscale / chip command / pixel memory
    // Satir basina kelime = 16 kanal * CHAIN_LEN IC * 16 bit (3 panel: 3840; tek panel: 1280)
    dma_grey_buffer_parallel_bit_length = ((size_t)PANEL_SCAN_LINES * PANEL_MBI_LED_CHANS * PANEL_MBI_CHAIN_LEN * 16);
    dma_grey_buffer_size = sizeof(ESP32_GREY_DMA_STORAGE_TYPE) * dma_grey_buffer_parallel_bit_length;
    ESP_LOGD(TAG, "Allocating greyscale DMA memory buffer. Size of memory required: %lu bytes.", dma_grey_buffer_size);

    dma_grey_gpio_data = (ESP32_GREY_DMA_STORAGE_TYPE *)heap_caps_malloc(dma_grey_buffer_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA);
    assert(dma_grey_gpio_data != nullptr);
    memset(dma_grey_gpio_data, 0, dma_grey_buffer_size);

    dma_cmd_buffer = (ESP32_GREY_DMA_STORAGE_TYPE *)heap_caps_malloc(CMD_BUF_WORDS * sizeof(ESP32_GREY_DMA_STORAGE_TYPE), MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA);
    assert(dma_cmd_buffer != nullptr);
    memset(dma_cmd_buffer, 0, CMD_BUF_WORDS * sizeof(ESP32_GREY_DMA_STORAGE_TYPE));

    // Padding line: 16 chans * 5 ICs * 16 bits of zeros, with DATA_LATCH (LE=1)
    // on the final bit of each 80-word chain pass - identical latch framing to
    // a real line, just black.
    dma_pad_line_size = sizeof(ESP32_GREY_DMA_STORAGE_TYPE) * PANEL_MBI_LED_CHANS * PANEL_MBI_CHAIN_LEN * 16;
    dma_pad_line = (ESP32_GREY_DMA_STORAGE_TYPE *)heap_caps_malloc(dma_pad_line_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA);
    assert(dma_pad_line != nullptr);
    memset(dma_pad_line, 0, dma_pad_line_size);
    for (int chan = 0; chan < PANEL_MBI_LED_CHANS; chan++) {
      int last_bit_of_chain = (chan * PANEL_MBI_CHAIN_LEN * 16) + (PANEL_MBI_CHAIN_LEN * 16) - 1;
      dma_pad_line[last_bit_of_chain] |= BIT_LAT;
    }

    // Setup LCD DMA and Output to GPIO - DCLK + 6 RGB data lines + LE/LAT
    // SINGLE-ENGINE ARCHITECTURE: the LCD peripheral now also drives GCLK and
    // the A..E address lines (d7..d12), so data, latches, GCLK and row address
    // are all generated from ONE buffer in perfect sync. This panel's FM6363C
    // (HUB75 mode, cfg1[5:4]=11) writes incoming line data into the SRAM line
    // selected by the CURRENT external address - asynchronous scanning sprayed
    // row-varying data across rows (row-uniform content was immune).
    auto bus_cfg = dma_bus.config();
    bus_cfg.pin_wr = MBI_DCLK;  // DCLK
    bus_cfg.invert_pclk = false;  // MUST be false: inverted phase makes LE pulse widths straddle
    // two DCLK rising edges, so VSYNC(3) intermittently reads as WR_CFG1(4)
    // and corrupts config registers with shift-register garbage (the mosaic).
    bus_cfg.pin_d0 = MBI_G1;
    bus_cfg.pin_d1 = MBI_B1;
    bus_cfg.pin_d2 = MBI_R1;
    bus_cfg.pin_d3 = MBI_G2;
    bus_cfg.pin_d4 = MBI_B2;
    bus_cfg.pin_d5 = MBI_R2;
    bus_cfg.pin_d6 = MBI_LAT;   // LE
    bus_cfg.pin_d7 = MBI_GCLK;  // GCLK now from LCD engine (was GPSPI2)
    bus_cfg.pin_d8 = ADDR_A_PIN;
    bus_cfg.pin_d9 = ADDR_B_PIN;
    bus_cfg.pin_d10 = ADDR_C_PIN;
    bus_cfg.pin_d11 = ADDR_D_PIN;
    bus_cfg.pin_d12 = ADDR_E_PIN;
    bus_cfg.pin_d13 = -1;
    bus_cfg.pin_d14 = -1;
    bus_cfg.pin_d15 = -1;

    dma_bus.config(bus_cfg);
    dma_bus.setup_lcd_dma_periph();

    build_frame_template();

    updateRegisters();

    initialized = true;

    // Two black warm-up frames: flush power-on junk from the chip's SRAM and
    // align the line write pointer before the first real frame.
    update();
    update();
  }

  void refreshMatrixConfig() {
    fm_send_all_config_regs();
  }

  void update() {
    assert(initialized);
    // LAutour (ICN2053/FM6353) order: shadow-SRAM DATA first, THEN the vsync
    // command group, then immediate scanning so the buffer swap executes.
    dma_bus.send_stuff_once(dma_grey_gpio_data, dma_grey_buffer_size, true);
    fm_pre_active_dma();
    fm_en_op_dma();
    fm_v_sync_dma();
    fm_pre_active_dma();
    // Post-VSYNC GCLKs: two scan cycles so the swap is clocked through even if
    // the caller delays before the next refresh().
    dma_bus.send_stuff_once(dma_scan_buffer, dma_scan_buffer_size, true);
    dma_bus.send_stuff_once(dma_scan_buffer, dma_scan_buffer_size, true);
  }

  // DCLK bolenini calisma aninda degistir (flicker tuner). div sadece kaydirma
  // hizini degistirir; 1/20 scan yapisi (20 satir,74 GCLK) sabit kalir.
  void setClockDiv(uint32_t div) { dma_bus.set_clock_divider(div); }

  // Keep the panel scanning/lit: call this continuously from loop().
  // Sends ONE scan cycle (GCLK + addresses, no data latches) per call.
  void refresh() {
    assert(initialized);
    dma_bus.send_stuff_once(dma_scan_buffer, dma_scan_buffer_size, true);
  }

  // Clear only RGB data bits; the GCLK/ADDR/LAT template stays intact.
  void clear_pixels() {
    for (size_t i = 0; i < dma_grey_buffer_parallel_bit_length; i++)
        dma_grey_gpio_data[i] &= ~(uint16_t)BIT_ALL_RGB;
  }

  void updateRegisters()
  {
    fm_send_all_config_regs();
  }


  /***************************************** GFX STUFF  *****************************************/

  void setBrightness(uint8_t newBrightness) {}

  uint8_t getBrightness() const {
    return 255;
  }

  uint8_t getXResolution() {
    return PANEL_PHY_RES_X;
  }

  uint8_t getYResolution() {
    return PANEL_PHY_RES_Y;
  }

  void drawPixel(int16_t x, int16_t y, CRGB color) {
    fm_set_pixel(x, y, color.red, color.green, color.blue);
  }

  void drawPixel(uint8_t x, uint8_t y, uint8_t r_data, uint8_t g_data, uint8_t b_data) {
    fm_set_pixel(x, y, r_data, g_data, b_data);
  }

  // includes 565 to 888 conversion
  void drawPixel(int16_t x, int16_t y, uint16_t color) {
    uint8_t r   = (color >> 8) & 0xf8;
    uint8_t  g  = (color >> 3) & 0xfc;
    uint8_t b   = (color << 3);
    r |= r >> 5;
    g |= g >> 6;
    b |= b >> 5;

    fm_set_pixel(x, y, r, g, b);
  }

  void writePixel(uint8_t x, uint8_t y, uint8_t r_data, uint8_t g_data, uint8_t b_data) {
    fm_set_pixel(x, y, r_data, g_data, b_data);
  }

 protected:

  bool initialized = false;

  /***************************************** DMA STUFF  *****************************************/

  Bus_Parallel16 dma_bus;

  ESP32_GREY_DMA_STORAGE_TYPE *dma_grey_gpio_data;

  // Separate scratch buffer for LE commands + config writes. Commands used to
  // reuse dma_grey_gpio_data, overwriting the first ~600 words of PIXEL data
  // every frame since v5 (commands are sent before the frame data) - the likely
  // cause of the corrupted patch at the top of the panel.
  ESP32_GREY_DMA_STORAGE_TYPE *dma_cmd_buffer;
  static const int CMD_BUF_WORDS = 1024;

  // Scan-only regeneration buffer (LAutour's "suffix"): one full scan cycle of
  // GCLK pulses + row addresses, with NO data latches. Looped by refresh() to
  // keep the display alive WITHOUT re-latching data into the shadow SRAM
  // (re-sent latches drift the shadow write pointer and corrupt the next swap).
  ESP32_GREY_DMA_STORAGE_TYPE *dma_scan_buffer = nullptr;
  size_t dma_scan_buffer_size = 0;

  size_t dma_grey_buffer_parallel_bit_length;
  size_t dma_grey_buffer_size;

  // One zero-data line (16 latches) used to pad each frame out to the chip's
  // full 64-line SRAM space. FM6363 Table 3: grayscale loading order spans all
  // 64 lines regardless of CFG1 SCAN_LINE, so a frame must contain 64 lines of
  // latches or the SRAM write pointer drifts by 20 lines every frame.
  ESP32_GREY_DMA_STORAGE_TYPE *dma_pad_line;
  size_t dma_pad_line_size;
  static const int FM_SRAM_LINES = 64;

  /***************************************** FM6363 PROTOCOL *****************************************/

  // LCD upper-bit layout (single-engine): d7=GCLK, d8..d12 = A..E
  static const uint16_t SBIT_GCLK = (1 << 7);
  #define SADDR(row) ((uint16_t)(((row) & 0x1F) << 8))

  /*
    Synchronous frame buffer, per scan line L (HUB75-style):
      1280 words = 16 latch groups x (5 ICs x 16 bits) of grayscale data.
      - Address lines hold L for the WHOLE slot, so the FM6363C (HUB75 mode)
        stores the latched data into SRAM line L - no async spraying.
      - 74 evenly spaced GCLK pulses ride along (first FM_GCLK_DEAD_TIME
        pulse slots suppressed for row-change settle).
      - DATA_LATCH (LE=1) on the final word of each 80-word chain pass.
    Total: 20 x 1280 words = 51200 bytes.
  */
  /*
    LAutour-style synchronous frame (ported from ESP32-HUB75-MatrixPanel-DMA-ICN2053):
    - A continuous SCAN pattern (row address + GCLK pulse bursts) runs underneath
      the data stream, phase-coherent, never resetting mid-frame.
    - Scan slot per displayed row: 160 words = 6 dead + 74 GCLK pulses as
      [high,low] word pairs (148) + 6 pause. GCLK instantaneous rate = DCLK/2,
      satisfying the ">20% of DCLK" grayscale-save rule (the old sparse-GCLK
      template was at ~6% - the cause of the colour-scrambled segments).
    - Full scan cycle = 20*160 = 3200 words; frame = 25600 words = exactly 8
      scan cycles, so every frame starts AND ends at row0/phase0 and the VSYNC
      between frames always lands on a row boundary (LAutour's splice rule).
    - Grayscale data + DATA_LATCH ride on top, latch-counted into the chip's
      shadow SRAM independently of the scan (double-buffered architecture).
  */
  static const int SCAN_SLOT_WORDS = 160;
  static const int SCAN_DEAD_HEAD  = 6;   // GCLKDeadTime(3 pulses) * 2 words

  // ===================== ROW-SLOT senkron sablon (v14) =====================
  // TESHIS: FM6363C HUB75 modunda (cfg1[5:4]=11) latch'lenen veriyi O ANKI
  // HARICI ADRESIN sectigi SRAM satirina yazar (BULGULAR: adres-eszamanli
  // yazim). Eski sablonda adres her 160 kelimede ilerliyordu ama bir veri
  // satiri 1280 kelime suruyordu -> veri satiri y'nin kanal grubu g,
  // SRAM satiri ((8y + g/2) mod 20)'ye yaziliyordu: 16 kanal 8 farkli
  // satira sacildi. Satir-sabit icerik (dolgular/bantlar) bundan etkilenmez,
  // satir-degisken icerik (Mona Lisa) tam bu desende dagilir. top=18/bottom=4
  // gibi tuhaf ofsetler de bu sacilmanin yan urunuydu.
  //
  // COZUM (gercek alici kart davranisi): adres, o satirin 1280 kelimelik
  // veri blogu boyunca SABIT tutulur; tum 16 latch dogru SRAM satirina
  // gider. Dahili satir sayaci kilidi icin satir basina yine tam
  // FM_ROWSLOT_GCLKS GCLK gonderilir (sayac her 74 GCLK'da ilerler).
  //
  // Test sirasi:
  //   1) FM_GCLK_SPREAD=1, FM_ROWSLOT_GCLKS=74  (varsayilan)
  //   2) Segment-ici renk karismasi donerse: FM_GCLK_SPREAD=0 (yogun patlama)
  //   3) Satirlar 2x atliyorsa: FM_ROWSLOT_GCLKS=148 (cift-kenar sayim)
  #ifndef FM_ROWSLOT_GCLKS
  #define FM_ROWSLOT_GCLKS  FM_GCLKS_PER_ROW  // 74; satirlar 2x atlarsa 148
  #endif
  #ifndef FM_GCLK_SPREAD
  #define FM_GCLK_SPREAD    1  // 1 = slota esit yayilmis tek-kelime darbeler
                               // 0 = slot basinda DCLK/2 yogun patlama
  #endif
  void build_frame_template() {
      const int SCAN_CYCLE = SCAN_SLOT_WORDS * PANEL_SCAN_LINES;     // scan-only buffer icin
      const int ROW_SLOT = PANEL_MBI_LED_CHANS * PANEL_MBI_CHAIN_LEN * 16;  // 3 panel: 3840, tek panel: 1280
      const size_t total = dma_grey_buffer_parallel_bit_length;      // 3 panel: 76800 kelime (153.6 KB)

      // GCLK darbe pozisyonlarini slot icinde bir kez hesapla
      static bool gclk_word[PANEL_MBI_LED_CHANS * PANEL_MBI_CHAIN_LEN * 16];
      memset(gclk_word, 0, sizeof(gclk_word));
  #if FM_GCLK_SPREAD
      // TAM FM_ROWSLOT_GCLKS darbe gonderilmeli (dahili sayac her 74 GCLK'da
      // ilerler; eksik darbe satir basina kayma biriktirir). Dead time bir
      // GECIKMEDIR: darbeler slot basindaki olu bolgeden SONRA esit yayilir.
      {
          const int dead = SCAN_DEAD_HEAD;               // satir degisimi otursun
          const int span = ROW_SLOT - dead;
          for (int k = 0; k < FM_ROWSLOT_GCLKS; k++) {
              int w = dead + (k * span) / FM_ROWSLOT_GCLKS;
              // LAT kelimesine denk gelirse bir kelime kaydir: latch aninda GCLK
              // kenari, logic-analyzer suphelilerinden biriydi - cakismayi onle.
              if ((w % (PANEL_MBI_CHAIN_LEN * 16)) == (PANEL_MBI_CHAIN_LEN * 16 - 1)) w++;
              if (w < ROW_SLOT) gclk_word[w] = true;
          }
      }
  #else
      // Yogun mod: [high,low] ciftleri DCLK/2 hizinda, slot basinda
      for (int k = 0; k < FM_ROWSLOT_GCLKS; k++) {
          int w = SCAN_DEAD_HEAD + k * 2;  // cift indeks -> LAT (79. kelime, tek) ile cakismaz
          if (w < ROW_SLOT) gclk_word[w] = true;
      }
  #endif

      for (size_t i = 0; i < total; i++) {
          int row  = (int)(i / ROW_SLOT);   // veri satiri == adreslenen satir
          int slot = (int)(i % ROW_SLOT);
          uint16_t v = SADDR(row);
          if (gclk_word[slot]) v |= SBIT_GCLK;
          if ((slot % (PANEL_MBI_CHAIN_LEN * 16)) == (PANEL_MBI_CHAIN_LEN * 16 - 1)) {
              v |= BIT_LAT;
          }
          dma_grey_gpio_data[i] = v;
      }

      // Scan-only buffer: one scan cycle (3200 words), GCLK+addr only, no LAT.
      if (dma_scan_buffer == nullptr) {
          dma_scan_buffer_size = sizeof(ESP32_GREY_DMA_STORAGE_TYPE) * SCAN_CYCLE;
          dma_scan_buffer = (ESP32_GREY_DMA_STORAGE_TYPE *)heap_caps_malloc(dma_scan_buffer_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA);
          assert(dma_scan_buffer != nullptr);
      }
      for (int i = 0; i < SCAN_CYCLE; i++) {
          int srow = i / SCAN_SLOT_WORDS;
          int slot = i % SCAN_SLOT_WORDS;
          uint16_t v = SADDR(srow);
          if (slot >= SCAN_DEAD_HEAD && slot < SCAN_DEAD_HEAD + FM_GCLKS_PER_ROW * 2) {
              if (((slot - SCAN_DEAD_HEAD) & 1) == 0) v |= SBIT_GCLK;
          }
          dma_scan_buffer[i] = v;
      }
  }

  // Clear only RGB data bits; GCLK/ADDR/LAT template stays intact.
  // (public version lives next to update()/refresh())

  void fm_set_pixel(uint8_t x, uint8_t y, uint8_t _r_data, uint8_t _g_data, uint8_t _b_data) {

    if (x >= PANEL_PHY_RES_X || y >= PANEL_PHY_RES_Y) {
      return;
    }

    // CIE perceptual->PWM mapping. For already-gamma'd photo content this can
    // double-apply and wash out highlights; set FM_APPLY_CIE 0 to send raw.
#ifndef FM_APPLY_CIE
#define FM_APPLY_CIE 1
#endif
    // Doygunluk: griye olan mesafeyi olcekle (BT.601 agirliklari)
    if(img_saturation != 128){
      int gray = (_r_data*77 + _g_data*150 + _b_data*29) >> 8;
      int sr = gray + (((int)_r_data - gray) * img_saturation >> 7);
      int sg = gray + (((int)_g_data - gray) * img_saturation >> 7);
      int sb = gray + (((int)_b_data - gray) * img_saturation >> 7);
      _r_data = (uint8_t)(sr<0?0:(sr>255?255:sr));
      _g_data = (uint8_t)(sg<0?0:(sg>255?255:sg));
      _b_data = (uint8_t)(sb<0?0:(sb>255?255:sb));
    }
    // Kontrast: orta griden uzaklastir/yaklastir
    if(img_contrast != 128){
      int cr = 128 + (((int)_r_data - 128) * img_contrast >> 7);
      int cg = 128 + (((int)_g_data - 128) * img_contrast >> 7);
      int cb = 128 + (((int)_b_data - 128) * img_contrast >> 7);
      _r_data = (uint8_t)(cr<0?0:(cr>255?255:cr));
      _g_data = (uint8_t)(cg<0?0:(cg>255?255:cg));
      _b_data = (uint8_t)(cb<0?0:(cb>255?255:cb));
    }
    // Kanal kazanci (beyaz nokta) + parlaklik olcekleme (CIE oncesi)
    uint16_t _bs = (uint16_t)global_brightness + 1;
    _r_data = (uint8_t)((((uint16_t)_r_data * (gain_r+1)) >> 8) * _bs >> 8);
    _g_data = (uint8_t)((((uint16_t)_g_data * (gain_g+1)) >> 8) * _bs >> 8);
    _b_data = (uint8_t)((((uint16_t)_b_data * (gain_b+1)) >> 8) * _bs >> 8);
#if FM_APPLY_CIE
    uint8_t r_data = CIE[_r_data];
    uint8_t g_data = CIE[_g_data];
    uint8_t b_data = CIE[_b_data];
#else
    uint8_t r_data = _r_data;
    uint8_t g_data = _g_data;
    uint8_t b_data = _b_data;
#endif

    // ===== PANEL MAPPING (v15: dikey istif + zincir) =====
    // Fiziksel (x: 0..79, y: 0..PANEL_PHY_RES_Y-1) -> panel + panel-ici yerel koordinat.
    // Adres hatlari ortak: tarama hala 20 satir; zincir, satir slotunu uzatir.
    // Tum kalibre donusumler (X aynasi, yari takasi, yari-ici dikey ayna)
    // PANEL-YERELDIR cunku her panelin ic kablolamasi ayni.
    int panel_idx = y / 40;       // 0 = en ust panel (fiziksel)
    int yl = y % 40;              // panel-ici yerel y
    int xl = x;                   // panel-ici yerel x

#ifndef FM_MIRROR_X
#define FM_MIRROR_X 1        // measured: block AND channel order reversed
#endif
#ifndef FM_SWAP_HALVES
#define FM_SWAP_HALVES 1     // measured: physical top half <- R2 group
#endif

#if FM_MIRROR_X
    xl = 79 - xl;
#endif
    int phys_half = yl / PANEL_SCAN_LINES;
#if FM_SWAP_HALVES
    uint16_t _colourbitsoffset = (phys_half == 0) ? 3 : 0;
#else
    uint16_t _colourbitsoffset = (phys_half == 0) ? 0 : 3;
#endif
    uint16_t _colourbitsclear  = ~(0b111 << _colourbitsoffset);

    uint16_t g_gpio_bitmask = BIT_G1 << _colourbitsoffset;
    uint16_t b_gpio_bitmask = BIT_B1 << _colourbitsoffset;
    uint16_t r_gpio_bitmask = BIT_R1 << _colourbitsoffset;

    int p = yl % PANEL_SCAN_LINES;
    // Diyagonal testi ZIKZAK gosterirse: panel yari-icinde dikey aynali
    // (180 derece cevrik kablolama, X aynasiyla tutarli) -> bu bayragi 1 yap,
    // offsetleri 0 birak. Diyagonal AYNI YONDE ama kaymis gorunurse: bayrak 0,
    // row_offset_top=3, row_offset_bottom=17 yap.
#ifndef FM_FLIP_Y_IN_HALF
#define FM_FLIP_Y_IN_HALF 0
#endif
#if FM_FLIP_Y_IN_HALF
    p = (PANEL_SCAN_LINES - 1) - p;
#endif
    int _ro = (phys_half == 0) ? row_offset_top : row_offset_bottom;
    int y_normalised = (p + _ro) % PANEL_SCAN_LINES;

#if FM6363_REVERSE_CHANNEL_ORDER
    // FM6363 guide: first 16-bit word goes to channel 15
    int chan = 15 - (xl % 16);
#else
    int chan = (xl % 16);
#endif

    // Zincir slotu: kabloya ILK baglanan panelin zincir basinda mi sonunda mi
    // oldugu panel-kimlik testiyle belirlenir (FM_CHAIN_REVERSE).
#if FM_CHAIN_REVERSE
    int chain_slot = (PANEL_CHAIN_PANELS - 1) - panel_idx;
#else
    int chain_slot = panel_idx;
#endif
    int ic = (xl / 16) + 5 * chain_slot;   // 0..PANEL_MBI_CHAIN_LEN-1

    // Satir slotu: 16 kanal * CHAIN_LEN IC * 16 bit kelime
    const int ROW_WORDS  = PANEL_MBI_LED_CHANS * PANEL_MBI_CHAIN_LEN * 16;
    const int CHAN_WORDS = PANEL_MBI_CHAIN_LEN * 16;
    int bit_start_pos = (ROW_WORDS * y_normalised) + (chan * CHAN_WORDS) + (ic * 16);

    // 8-bit colour placed in the high bits of the 16-bit greyscale word.
    // FM6363 expects 16-bit data per channel (S-PWM, dual-edge GCLK).
    int subpixel_colour_bit = 8;
    uint8_t mask;
    while (subpixel_colour_bit > 0)
    {
      subpixel_colour_bit--;
      dma_grey_gpio_data[bit_start_pos] &= _colourbitsclear;

      mask = 1 << subpixel_colour_bit;

      if (g_data & mask) {
        dma_grey_gpio_data[bit_start_pos] |= g_gpio_bitmask;
      }

      if (b_data & mask) {
        dma_grey_gpio_data[bit_start_pos] |= b_gpio_bitmask;
      }

      if (r_data & mask) {
        dma_grey_gpio_data[bit_start_pos] |= r_gpio_bitmask;
      }

      bit_start_pos++;
    }

  }  // fm_set_pixel


  /* Generic LE command: LE held high for 'le_width' DCLK rising edges, no data */
  void fm_send_le_command(int le_width) {
    const uint16_t park = SADDR(31);  // no row selected on a 20-scan panel, GCLK low
    int payload_length = 0;
    for (int i = 0; i < le_width; i++) {
      dma_cmd_buffer[payload_length] = BIT_LAT | park;
      payload_length++;
    }
    /* LE must return low for at least a couple of DCLKs */
    for (int i = 0; i < 2; i++) {
      dma_cmd_buffer[payload_length] = park;
      payload_length++;
    }
    dma_bus.send_stuff_once(dma_cmd_buffer, payload_length * sizeof(ESP32_GREY_DMA_STORAGE_TYPE), false);
  }

  /* PRE_ACT (LE=14): write-enable, must precede EN_OP and every register write */
  void fm_pre_active_dma() {
    ESP_LOGD(TAG, "Send FM6363 PRE_ACT.");
    fm_send_le_command(FM_LE_PRE_ACT);
  }

  /* EN_OP (LE=12): enable all output channels - sent once at start of each frame/init */
  void fm_en_op_dma() {
    ESP_LOGD(TAG, "Send FM6363 EN_OP.");
    fm_send_le_command(FM_LE_EN_OP);
  }

  /* DIS_OP (LE=13): disable all output channels */
  void fm_dis_op_dma() {
    ESP_LOGD(TAG, "Send FM6363 DIS_OP.");
    fm_send_le_command(FM_LE_DIS_OP);
  }

  /* VSYNC (LE=3): update display data. GCLK must be stopped around this. */
  void fm_v_sync_dma() {
    ESP_LOGV(TAG, "Send FM6363 VSYNC.");

    int payload_length = 600;
    const uint16_t park = SADDR(31);
    for (int i = 0; i < payload_length; i++) dma_cmd_buffer[i] = park;

    int start_pos = payload_length - (payload_length/2);
    for (int i = 0; i < FM_LE_VSYNC; i++) {
      dma_cmd_buffer[start_pos++] = BIT_LAT | park;
    }
    dma_cmd_buffer[start_pos++] = park;

    dma_bus.send_stuff_once(dma_cmd_buffer, payload_length * sizeof(ESP32_GREY_DMA_STORAGE_TYPE), false);
  }

  /*
    Write one 16-bit config register, with PER-COLOUR values.
    The FM6363C chips on the R lines get r_val, G lines g_val, B lines b_val.
    The command is identified by asserting LE for the last 'le_width' DCLKs
    of the final chained IC's 16-bit word.
  */
  void fm_set_config_dma(unsigned int &dma_output_pos, uint16_t r_val, uint16_t g_val, uint16_t b_val,
                         int le_width, bool latch) {

    for (int bit = 15; bit >= 0; bit--) {

      uint16_t sdi_val = SADDR(31);  // parked address, GCLK low
      if ((r_val >> bit) & 1) sdi_val |= BIT_ALL_R;
      if ((g_val >> bit) & 1) sdi_val |= BIT_ALL_G;
      if ((b_val >> bit) & 1) sdi_val |= BIT_ALL_B;

      if ((bit < le_width) && (latch == true)) {
        sdi_val |= BIT_LAT;
      }

      dma_cmd_buffer[dma_output_pos++] = sdi_val;
    }
  }

  void fm_send_config_reg(uint16_t r_val, uint16_t g_val, uint16_t b_val, int le_width) {
    unsigned int dma_output_pos = 0;
    for (int i = 0; i < PANEL_MBI_CHAIN_LEN; i++) {
      // LE asserted only during the last IC's word
      fm_set_config_dma(dma_output_pos, r_val, g_val, b_val, le_width, (i == (PANEL_MBI_CHAIN_LEN - 1)));
    }
    dma_bus.send_stuff_once(dma_cmd_buffer, dma_output_pos * sizeof(ESP32_GREY_DMA_STORAGE_TYPE), false);
  }

  /* Full FM6363 init sequence per programming guide:
     PRE_ACT -> EN_OP -> (PRE_ACT -> WR_CFGn) for n = 1..4 */
  void fm_send_all_config_regs() {
    ESP_LOGD(TAG, "Send FM6363 full config (factory .ssx values).");

    fm_pre_active_dma();
    fm_en_op_dma();

    fm_pre_active_dma();
    fm_send_config_reg(FM_CFG1_R, FM_CFG1_G, FM_CFG1_B, FM_LE_WR_CFG1);

    fm_pre_active_dma();
    fm_send_config_reg(FM_CFG2_R, FM_CFG2_G, FM_CFG2_B, FM_LE_WR_CFG2);

    fm_pre_active_dma();
    fm_send_config_reg(FM_CFG3_R, FM_CFG3_G, FM_CFG3_B, FM_LE_WR_CFG3);

    fm_pre_active_dma();
    fm_send_config_reg(FM_CFG4_R, FM_CFG4_G, FM_CFG4_B, FM_LE_WR_CFG4);
  }

};

#endif  // MATRIX_H
