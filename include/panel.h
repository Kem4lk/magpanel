#pragma once
// ============================================================================
//  Panel secimi (DERLEME ZAMANI): ana MagPanel firmware'i hangi panel surucusuyle
//  derlenecek. Her env tek bir panel tipini surer; ikisi ayni anda linklenmez
//  (P4 surucusu dahili RAM'in neredeyse tamamini kullanir).
//    varsayilan         : P4 80x120 (3x FM6363C 80x40)  -> Matrix.h
//    -DPANEL_P186       : P1.86 172x86 (SM16380SH+SM5368) -> panel_sm16380.h
//                         1..3 modul (ayni ESP32, panel basina LAT), dikey/yatay;
//                         sayi + duzen NVS'ten okunur -> PANEL_W/H CALISMA ANINDA belli olur
//  main.cpp / apps.h sadece Panel, PANEL_W, PANEL_H ve asagidaki sabitleri kullanir.
// ============================================================================

#if defined(PANEL_P186)
  #include "panel_sm16380.h"
  typedef PanelSM16380 Panel;
  #define PANEL_W            (sm16380::g_w)      // 172 x panel sayisi (yatay) ya da 172
  #define PANEL_H            (sm16380::g_h)      // 86 x panel sayisi (dikey) ya da 86
  #define PANEL_COUNT        (sm16380::g_panels)
  #define PANEL_LAYOUT       (sm16380::g_layout) // 0 = dikey (alt alta), 1 = yatay (yan yana)
  #define PANEL_NAME         "P1.86"
  #define PANEL_CFG_NS       "panelcfg186"   // DCLK vb. ayarlar P4'unkilerle karismasin
  #define PANEL_DEFAULT_DIV  16              // 10 MHz (flicker videosunda temiz)
  #ifndef OTA_FW_FILE
  #define OTA_FW_FILE        "firmware-p186.bin"
  #endif
#else
  #include <Matrix.h>
  typedef Matrix Panel;
  #define PANEL_W            PANEL_PHY_RES_X   // 80
  #define PANEL_H            PANEL_PHY_RES_Y   // 120
  #define PANEL_COUNT        1                 // (fiziksel 3 modul tek mantiksal zincir)
  #define PANEL_LAYOUT       0
  #define PANEL_NAME         "P4"
  #define PANEL_CFG_NS       "panelcfg"
  #define PANEL_DEFAULT_DIV  64              // 2.5 MHz (derlenmis varsayilan)
  #ifndef OTA_FW_FILE
  #define OTA_FW_FILE        "firmware.bin"
  #endif
#endif

// Genis (en >= 1.5 x boy) kanvasta uygulama yerlesimleri farkli (yatay tasarim)
#define PANEL_WIDE (PANEL_W * 2 >= PANEL_H * 3)
