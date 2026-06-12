#!/bin/bash
# MagPanel: derle + WiFi'dan panele yukle (cift tikla calisir)
cd "$(dirname "$0")"
echo "=== MagPanel derleniyor ve panele gonderiliyor ==="
~/.platformio/penv/bin/pio run -e esp32-s3-ota --target upload && \
  echo "=== TAMAM - panel yeniden basliyor, sayfadan surumu kontrol et ===" || \
  echo "=== HATA - ciktiyi kontrol et ==="
read -p "Kapatmak icin Enter..."
