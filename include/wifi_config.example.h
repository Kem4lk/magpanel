// Lokal derleme icin bu dosyayi wifi_config.h olarak kopyala ve doldur.
// CI derlemeleri bu dosyayi kullanmaz; GitHub Secrets'tan uretir.
#pragma once
#define WIFI_SSID     "SSID"
#define WIFI_PASS     "SIFRE"
#define MDNS_HOSTNAME "magpanel"
#define OTA_PASSWORD  "magpanel"
#define FW_VERSION    "lokal"
#define GITHUB_OTA_BASE "https://github.com/KULLANICI/REPO/releases/latest/download"
#define GITHUB_AUTO_OTA 1
