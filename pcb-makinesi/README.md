# PCB üretim makinesi: prototip v0 BOM

Satılacak masaüstü PCB üretim makinesinin (UV LCD maske pozlama + CNC delme + ıslak istasyon + reflow
hot plate) ilk prototipi için Türkiye'den alınabilecek parçalar.

- `bom-v0.xlsx`: Özet (modül toplamları), Kesim karşılaştırma (CNC / diyot / CO2 / fiber / UV lazer), BOM (79 kalem), Alternatifler (hazır CNC kitleri vb.),
  Yurt dışı (Türkiye'de bulunamayanlar), Uyarılar.
- `bom_v0.py`: tek kaynak. Satırı burada düzelt, `python3 bom_v0.py` ile xlsx'i yeniden üret
  (`pip install openpyxl`).

Fiyatlar 2026-10-04'te satıcı sayfasında görülen KDV dahil TL fiyatlarıdır. "Doğrulandı = hayır"
satırları yalnız arama özetinden alındı (pazaryerleri sayfa açmayı engelliyor); siparişten önce kontrol et.

| Modül | Toplam (TL) |
|---|---|
| 1 Pozlama (Aptus 10.3" 8K mono LCD + HDMI kartı (teklif), Raspberry Pi 5, Anycubic UV modülü + Fresnel) | 22.013 + Aptus |
| 2 CNC portal (HGR15 ray, SFU1204, TMC5160, 400 W ER11 mil) | 37.854 |
| 3 Islak istasyon (tanklar, ısıtıcı, ORP, peristaltik pompa, kimyasallar, plaket, KKD) | 17.677 |
| 4 Hot plate (kendin yap; ısıtıcı plaka fiyatı yok) | 3.577 |
| 5 Ortak elektronik (ESP32-S3, güç kaynakları, MOSFET, konnektör, acil stop) | 9.523 |
| **Toplam** (6 kalem fiyatsız: Aptus panel+kart, ısıtıcı plaka, pimler, akrilik, bidon; kargo, cıvata, plakalar hariç) | **~90.600** |

Kesim ve delme: CNC freze. Lazerler (diyot/CO2) FR4'ü temiz kesemez ve bromlu zehirli duman çıkarır; fiber lazer
yalnız kimyasalsız bakır izolasyonu için (v2) anlamlı, UV lazer ürün maliyetine uymaz.
