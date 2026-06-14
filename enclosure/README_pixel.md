# MagPanel PİKSEL-IZGARA Kasası (görüntü/yazı paneli) — GÜNCEL

320×480 P4 panel için **her piksele bir kare göz**: 80×120 = **9600 hücre**, 4 mm adım.
Kapalı **0.7 mm difüzör ön yüz** → her piksel "dolu kare" olarak parlar; **0.8 mm
ızgara duvarları** pikselleri ayırır (kontrast + ışık bulaşması yok). Görüntü/yazı
için doğru mimari (kaba egg-crate değil). Üretici: `generate_pixel_case.py`.

> Eski `stl/` (kaba egg-crate difüzör kasası) dekoratif glow içindi; görüntü
> paneli için **bu pixel sürümü** kullanılmalı.

## Ölçüler
| | |
|---|---|
| Dış ölçü | **325.8 × 485.8 × 18.7 mm** |
| Aktif alan | 320 × 480 (80×120, **4.0 mm adım**, **3.2 mm kare hücre**) |
| Ön difüzör | **0.7 mm** (kapalı) |
| Izgara duvar | **0.8 mm**, derinlik 4 mm |
| Panel yuvası | 321 × 481 × 14 mm |
| Fayans (2×2) | **162.9 × 242.9 × 18.7 mm** |

## Dosyalar (`stl_pixel/`)
- `tile_BL / BR / TL / TR.stl` — 4 fayans (2×2). **Dikiş çizgileri bir ızgara
  duvarına denk geldiği için görünmez.**
- `saturn_plate_4tiles_standing.stl` — 4 fayans **DİK** dizilmiş, tek
  **Elegoo Saturn 3 Ultra** plakasına sığar (167.5 × 98.8 × 247.2 ≤ 218.88×122.88×260).
- `full_reference.stl` — bölünmemiş tam kasa (önizleme/büyük yazıcı için).

## Baskı (Saturn 3 Ultra, reçine)
- **DİK bas** (243 mm kenar Z'ye). Kapalı difüzör yüzü düz/tabana paralel
  BASMA → koca düz katman = peel/vakum başarısızlığı. Dik ya da ~20° eğik.
- 4 fayans tek plakaya dik sığar; Chitubox/Lychee'de destekleri **arka (ızgara)
  tarafına** ver, ön difüzör yüzü desteksiz/temiz kalsın.
- Difüzör için ön yüzü **mat** bırak (parlatma yok). Light-beige yarı opak →
  ışık geçer ama kremimsi; daha çok ışık için `t_front`'u 0.6'ya indirebilirsin.

## ⚠️ Kritik: hizalama
Izgara tam **4.0 mm adım / 320×480 aktif alan** varsayar; gözler LED'lere birebir
denk gelmeli. Panelin **gerçek pitch'ini ve ilk piksel offset'ini ÖLÇ** —
0.1 mm sapma × 80 göz = 8 mm kayma. Farklıysa `generate_pixel_case.py` içindeki
`pitch / nx / ny / clr`'yi güncelle.

## Kontrast notu (malzeme)
İdeal ızgara **siyah** olur (pikseller arası duvarlar yan ışığı yutar). Beige
duvarlar hafif aydınlanır → kontrast düşer. İstersen ızgarayı siyaha boya / siyah
reçine kullan.

## Montaj (kabaca)
Difüzör+ızgara fayansları LED panelinin önüne, gözler LED'lere denk gelecek
şekilde otur; panel arkadan yuvaya girer, kablo üst kenardan çıkar. Fayanslar
dikişte birbirine yapıştırılabilir ya da bir çevre çerçeve/panel ile sıkıştırılır.
(Hizalama pimi / çerçeve kelepçesi ekletmek istersen söyle.)

## Yeniden üret / ayarla
```bash
pip install trimesh manifold3d numpy
python3 generate_pixel_case.py     # stl_pixel/ üretir
```
Tüm ölçüler dosya başındaki `P` sözlüğünde (adım, duvar, difüzör, derinlik, bölme).
