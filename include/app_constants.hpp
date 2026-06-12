/******************************************************************************************
 * @file        app_constants.hpp
 * @brief       ESP32-S3 driver for FM6363C (S-PWM) based 80x40 1/20 scan HUB75E panel
 *              Ported from mrcodetastic's MBI5153 implementation (ESP32-PWM-MatrixPanel-DMA)
 *              Panel profile source: p4_indoor 1001 seri kodu FM6363 138 çip (.ssx)
 ******************************************************************************************/

#pragma once
#include "hal/gpio_types.h"

// =========================================================================
// KEMAL'S HUB75E WIRING (ESP32-S3 DevKitC) - matches existing Arduino sketch
// =========================================================================
// HUB75 connector pin -> FM6363 function:
//   CLK -> DCLK (data clock), LAT -> LE (command/latch), OE -> GCLK (grayscale clock)

#define ADDR_A_PIN              GPIO_NUM_18
#define ADDR_B_PIN              GPIO_NUM_8
#define ADDR_C_PIN              GPIO_NUM_3
#define ADDR_D_PIN              GPIO_NUM_9    // <-- if rows look interleaved/wrong, swap D and E
#define ADDR_E_PIN              GPIO_NUM_13

#define MBI_GCLK                GPIO_NUM_11   // HUB75 "OE" pin carries GCLK on S-PWM panels
#define MBI_LAT                 GPIO_NUM_10   // HUB75 "LAT" = LE (command line)
#define MBI_DCLK                GPIO_NUM_12   // HUB75 "CLK" = DCLK
#define MBI_SRCLK               GPIO_NUM_NC   // not used on this panel (74HC138 row decode)

// RGB data lines - this panel is a standard HUB75 "two scan": 2 RGB groups
#define MBI_R1                  GPIO_NUM_4    // top half  (rows  0..19)
#define MBI_G1                  GPIO_NUM_5
#define MBI_B1                  GPIO_NUM_6
#define MBI_R2                  GPIO_NUM_7    // bottom half (rows 20..39)
#define MBI_G2                  GPIO_NUM_15
#define MBI_B2                  GPIO_NUM_16

// -------------------------------------------------------
// Internals specific to code and hardware.
// -------------------------------------------------------

#define ESP32_GREY_DMA_STORAGE_TYPE uint16_t  // DMA output of one uint16_t at a time.

// For DMA GCLK and Address Line Data (GPSPI2 octal output bit positions)
#define BIT_GCLK  (1 << 0)
#define BIT_A     (1 << 1)
#define BIT_B     (1 << 2)
#define BIT_C     (1 << 3)
#define BIT_D     (1 << 4)
#define BIT_E     (1 << 5)

// For DMA Greyscale / command data (LCD peripheral parallel bit positions)
// Two RGB groups only (standard HUB75 two-scan panel)
#define BIT_G1   (1 << 0)
#define BIT_B1   (1 << 1)
#define BIT_R1   (1 << 2)
#define BIT_RGB1_CLR (0b111 << 0)
#define BIT_G2   (1 << 3)
#define BIT_B2   (1 << 4)
#define BIT_R2   (1 << 5)
#define BIT_RGB2_CLR (0b111 << 3)
#define BIT_LAT  (1 << 6)

#define BIT_ALL_RGB    (BIT_G1 | BIT_B1 | BIT_R1 | BIT_G2 | BIT_B2 | BIT_R2)
#define BIT_ALL_R      (BIT_R1 | BIT_R2)
#define BIT_ALL_G      (BIT_G1 | BIT_G2)
#define BIT_ALL_B      (BIT_B1 | BIT_B2)

// =========================================================================
// PANEL GEOMETRY: 80x40 pixels, 1/20 scan, FM6363C, 74HC138 row decoding
// =========================================================================
#define PANEL_SCAN_LINES        20  // 1/20 scan
#define PANEL_MBI_LED_CHANS     16  // channels per FM6363C

// ===== ZINCIR (v15): dikey istif, HUB75 OUT->IN, hepsi ayni yonde =====
#ifndef PANEL_CHAIN_PANELS
#define PANEL_CHAIN_PANELS       3  // 1 yaparsan tek-panel v14c davranisina doner
#endif
#define PANEL_MBI_CHAIN_LEN     (5 * PANEL_CHAIN_PANELS)  // renk hatti basina IC

#define PANEL_PHY_RES_X 80
#define PANEL_PHY_RES_Y (40 * PANEL_CHAIN_PANELS)   // 120 (portrait istif)

#define PANEL_MBI_RES_X 80
#define PANEL_MBI_RES_Y PANEL_PHY_RES_Y

// Panel-kimlik testinde kirmizi/yesil/mavi ASAGIDAN yukari cikiyorsa
// kablo sirasi terstir -> bunu 1 yap.
#ifndef FM_CHAIN_REVERSE
#define FM_CHAIN_REVERSE 0
#endif

// If the image is horizontally scrambled in 16px blocks, toggle this:
// FM6363 guide: "first 16-bit data is for channel 15" -> channel order may be reversed
#define FM6363_REVERSE_CHANNEL_ORDER 0

// =========================================================================
// FM6363C CONFIG REGISTER VALUES
// Extracted from the panel's own factory .ssx profile - per colour channel!
// =========================================================================
#define FM_CFG1_R  0x13F0   // 5104  : scan=20 (bits13:8=19), 74-GCLK mode, cfg1[5:4]=11
#define FM_CFG1_G  0x13B0   // 5040
#define FM_CFG1_B  0x13B0   // 5040

#define FM_CFG2_R  0xF39D   // 62365 : blanking + IGAIN per factory profile
#define FM_CFG2_G  0xE79D   // 59293
#define FM_CFG2_B  0xD79D   // 55197

#define FM_CFG3_R  0x60B6   // 24758
#define FM_CFG3_G  0x60B6
#define FM_CFG3_B  0x60B6

#define FM_CFG4_R  0x5A00   // 23040 : factory default reg4
#define FM_CFG4_G  0x5A70   // 23152
#define FM_CFG4_B  0x5A70

// FM6363 LE command widths (number of DCLK rising edges while LE high)
#define FM_LE_DATA_LATCH  1
#define FM_LE_WR_DBG      2
#define FM_LE_VSYNC       3
#define FM_LE_WR_CFG1     4
#define FM_LE_WR_CFG2     6
#define FM_LE_WR_CFG3     8
#define FM_LE_WR_CFG4    10
#define FM_LE_EN_OP      12
#define FM_LE_DIS_OP     13
#define FM_LE_PRE_ACT    14
#define FM_LE_MBIST      15

// GCLK timing (from FM6363 programming guide + .ssx: GCLKMaxNum=73, GCLKDeadTime=3)
#define FM_GCLKS_PER_ROW        74
// Per-wrap header GCLKs cause the chip's internal line counter (which advances
// every 74 GCLKs, locked to OE per board707's FM6363 analysis) to drift 4 GCLKs
// on every loop wrap between VSYNCs. .ssx confirms GCLKPreNum=0/GCLKBackNum=0.
#define FM_GCLK_FRAME_HEADER     0
#define FM_GCLK_DEAD_TIME        3
