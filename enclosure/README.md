> **Görüntü/yazı paneli mi yapıyorsun?** Bu dosya kaba egg-crate **dekoratif glow**
> kasasıdır. Her piksele kare göz veren GÜNCEL **piksel-ızgara** sürümü için
> → [`README_pixel.md`](README_pixel.md) + `stl_pixel/` + `generate_pixel_case.py`.

# MagPanel Difüzör Kasası — 320×480 mm (P4 / 80×120 px)

`case20mm.stl` (162×162×32 mm, **kare**, ince kabuk difüzör + egg-crate takviye)
tasarımının **32×48 cm** panele uyarlanmış hâli. Aspect-ratio 1:1 → 2:3
değiştiği ve duvarlar baskıya uygun kalınlaştırıldığı için basit ölçekleme
yerine **parametrik olarak yeniden üretildi** (`generate_case.py`).

Seçimler: **kapalı difüzör ön** · **2×2 fayans** (yatağa sığsın) · **duvar montaj özelliği yok**.

## Ölçüler
| | |
|---|---|
| Dış ölçü | **326.3 × 486.3 × 31.2 mm** |
| Panel yuvası (iç) | **321.5 × 481.5 mm**, derinlik **14 mm** (panel 320×480 + 0.75 mm boşluk/kenar) |
| Ön difüzör kabuğu | 1.2 mm (ışık süzülür) |
| Egg-crate / ışık boşluğu | 16 mm, hücre adımı ~20 mm (16 hücre/genişlik) |
| Dış duvar | 2.4 mm |
| Fayans (×4) | **163.1 × 243.1 × 31.2 mm** → en az ~**245 × 170 mm** yatak gerekir |

## Parçalar (`stl/`)
- `tile_top_left/right`, `tile_bottom_left/right` — 4 fayans
- `splice_center` (4 vida) + `splice_Vtop/Vbot/Hrt/Hlf` (2'şer vida) — 5 ek plaka
- `full_case_1piece.stl` — referans tek parça (büyük yatak / CNC / dış üretim için)
- **Vida:** ~12 × **M3 kendinden kılavuzlu (self-tapping) × 12 mm**, silindir/düz baş

## Baskı
- **Yön:** her fayansı **ön yüz (difüzör) yatağa dönük** bas → düz, pürüzsüz ön; kaburgalar yukarı, destek gerekmez.
- **Difüzör için yarı saydam malzeme** (natürel/beyaz PLA, ya da "ışık geçiren" filament). Işığı eşit dağıtmak için ön kabuk dolu (%100) basılmalı; ön yüzde 4-5 katı düz tut.
- Duvarlar 1.2–2.4 mm → 0.4 mm nozül, **3–6 duvar (perimeter)** yeterli, iç dolgu ~%10.
- Plakalar düz, desteksiz basılır.

## Montaj
1. 4 fayansı ön yüz aşağı, masaya diz (egg-crate yukarı).
2. Ek plakaları arka (egg-crate) tarafından dikişlerin üstüne yerleştir; plakalar yuvalara gömülür, üstü kaburga düzlemiyle aynı hizada kalır. `splice_center` ortadaki 4'lü kavşağı, diğer 4 plaka dikiş ortalarını kenetler.
3. M3 vidaları plakadan boss'lara sık (kendinden kılavuz). Vida başları gömülü kalır, **panel düzlemini engellemez.**
4. LED paneli **LED yüzü öne (difüzöre) bakacak** şekilde yuvaya yatır; kaburga üstüne oturur. Kabloyu üst kenardaki yuvadan çıkar.

## ⚠️ Bilmen gerekenler / seçenekler
- **Ağırlık/süre:** ~**616 cm³ ≈ 764 g** plastik, toplam baskı uzun. Hafifletmek için `generate_case.py` içinde `n_cells_x`'i azalt (örn. 10 → daha seyrek ızgara), `t_front`/`rib_t`'yi 1.0'a indir.
- **Egg-crate ışık yolunda:** orijinaldeki gibi kaburgalar difüzör ile LED arasında → difüzörde **hafif ızgara/gölge deseni** olur (dekoratif "glow" görünümü). **Net görüntü** istiyorsan kaburgaları ışık yolundan çıkaran **"temiz ışık odası"** varyantını üretebilirim (söyle, yaparım).
- **Dikiş çizgisi:** fayanslar düz birleşir (butt); ön yüzde çok ince bir dikiş izi görülebilir. İstersen ışık sızdırmaz bindirme (ship-lap) eklerim.
- **Panel tutuşu:** yuvanın arkası açık; duvara asılınca panel duvarla tutulur. Taşımada düşmemesi için köşelere küçük tutucu tırnak/bant eklenebilir.
- **Panel ölçüsünü doğrula:** yuva, modülün **fiziksel dış ölçüsü 320×480 mm** ve **≤14 mm kalınlık** varsayımıyla yapıldı. Seninki farklıysa `panel_W/H`, `pocket_d`, `clr`'yi güncelle.

## Yeniden üretmek / ayarlamak
```bash
pip install trimesh manifold3d numpy
python3 generate_case.py        # stl/ klasörünü üretir
```
Tüm ölçüler `generate_case.py` başındaki `P` sözlüğünde. Panel boyutu, duvar,
derinlik, hücre sıklığı, bölme ve vida ölçüleri oradan değiştirilir.
