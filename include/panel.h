#pragma once
// ============================================================================
//  Panel secimi (DERLEME ZAMANI): ana MagPanel firmware'i hangi panel surucusuyle
//  derlenecek. Her env tek bir panel tipini surer; ikisi ayni anda linklenmez
//  (P4 surucusu dahili RAM'in neredeyse tamamini kullanir).
//    varsayilan         : P4 80x120 (3x FM6363C 80x40)  -> Matrix.h
//    -DPANEL_P186       : P1.86 172x86 (SM16380SH+SM5368) -> panel_sm16380.h
//  main.cpp / apps.h sadece Panel, PANEL_W, PANEL_H ve asagidaki sabitleri kullanir.
// ============================================================================

#if defined(PANEL_P186)
  #include "panel_sm16380.h"
  typedef PanelSM16380 Panel;
  #define PANEL_W            172
  #define PANEL_H            86
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
  #define PANEL_NAME         "P4"
  #define PANEL_CFG_NS       "panelcfg"
  #define PANEL_DEFAULT_DIV  64              // 2.5 MHz (derlenmis varsayilan)
  #ifndef OTA_FW_FILE
  #define OTA_FW_FILE        "firmware.bin"
  #endif
#endif

// Yatay (genis) panelde uygulama/test yerlesimleri farkli
#define PANEL_WIDE (PANEL_W > PANEL_H)
