# PCB üretim makinesi: prototip v0 BOM

Satılacak masaüstü PCB üretim makinesinin (UV LCD maske pozlama + CNC delme + ıslak istasyon + reflow
hot plate) ilk prototipi için Türkiye'den alınabilecek parçalar.

- `bom-v0.xlsx`: Özet (modül toplamları), BOM (77 kalem), Alternatifler (hazır CNC kitleri vb.),
  Yurt dışı (Türkiye'de bulunamayanlar), Uyarılar.
- `bom_v0.py`: tek kaynak. Satırı burada düzelt, `python3 bom_v0.py` ile xlsx'i yeniden üret
  (`pip install openpyxl`).

Fiyatlar 2026-10-04'te satıcı sayfasında görülen KDV dahil TL fiyatlarıdır. "Doğrulandı = hayır"
satırları yalnız arama özetinden alındı (pazaryerleri sayfa açmayı engelliyor); siparişten önce kontrol et.

| Modül | Toplam (TL) |
|---|---|
| 1 Pozlama (Phrozen 4K mono LCD, Anycubic UV modülü + Fresnel, ESP32-P4) | 23.341 |
| 2 CNC portal (HGR15 ray, SFU1204, TMC5160, 400 W ER11 mil) | 37.854 |
| 3 Islak istasyon (tanklar, ısıtıcı, ORP, peristaltik pompa, kimyasallar, plaket, KKD) | 17.677 |
| 4 Hot plate (kendin yap; ısıtıcı plaka fiyatı yok) | 3.577 |
| 5 Ortak elektronik (ESP32-S3, güç kaynakları, MOSFET, konnektör, acil stop) | 9.523 |
| **Toplam** (4 kalem fiyatsız; kargo, cıvata, plakalar hariç) | **~92.000** |
