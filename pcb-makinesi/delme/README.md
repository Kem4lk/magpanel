# PCB delme makinesi v0

Sabit spindle ve altında hareket eden çapraz tabla. Alt eksen Y, üst eksen X. Eksenler 28BYJ-48 motor ve GT2 kayışla,
Z ekseni 28BYJ-48 ve T8 trapez milli. Spindle 775 DC motor ve JT0 mandren, kontrol ESP32-S3 ile 3 adet ULN2003.
Yalnız delme yapar, frezeleme yok. Tek kaynak `gen_delme.py`: ölçüleri değiştirince betiği yeniden çalıştır.

```
pip install trimesh manifold3d numpy matplotlib shapely
python3 gen_delme.py          # stl/, cizim.svg/png, onizleme.html, olculer.txt
python3 gen_delme.py --png    # + onizleme.png (Chromium headless)
```

Betik tabla ve Z'yi 18 uç konumda (X ±80/0, Y ±50/0, Z alt/üst) gezdirip her parça çiftinin kesişim hacmini
hesaplar. Bir çakışma varsa hata kodu döner. Bilerek iç içe olan çiftler `ALLOW` listesinde: mil–rulman, uç–plaket
gibi. Kontrolün kendisi de sınandı: tabla 80 mm'yi geçince uç bloğa çarpıyor, betik bunu yakalıyor.

- `onizleme.html`: tarayıcıda açılan 3B model. X/Y/Z sürgüleriyle tablayı ve spindle'ı hareket ettirebilirsin
  (three.js CDN'den yüklenir, internet gerekir).
- `cizim.png/svg`: üst, ön ve yan görünüş. Kesikli kırmızı çizgi tablanın süpürme alanı.

## Ölçüler

| | |
|---|---|
| Taban | 370 × 357 mm, 18 mm kontrplak; toplam yükseklik 296 mm |
| Hareket | X 160, Y 100, Z 30 mm. Ham plaket 160 × 100 (Eurocard) |
| Desen sınırı | 6.6" ekranın 143.4 × 89.6 mm aktif alanı |
| Hizalama pimleri | Ø3, x = ±76, y = 0. Plaketin kenarına delinir; pozlama aparatı da aynı 152 mm aralığı kullanır |
| Y milleri | x = ±122, z = 14, 2 × 250 mm (senin milin) |
| X milleri | y = ±45, z = 34, 2 × 262 mm |
| Z milleri | 2 × 110 mm |
| Kayış | X 620 + Y 596 mm. **2 m GT2-6 al**; 1 m yetmez |
| Kasnak | Baskı GT2, 20 diş, 40 mm/tur. 28BYJ ile ~2048 adım/tur, 0,02 mm/adım |
| Yükseklikler | Tabla üstü 56,5; plaket üstü 61,1; uç en altta 58,9 (feda MDF'ye 0,6 mm girer) |

**220 × 180 mm neden olmadı:** Spindle sabit, tabla hareket ediyorsa, tabla her eksende kendi boyu kadar daha
yer süpürür. X'te 180 mm tabla + 160 mm hareket = 340 mm, Y'de 120 + 100 = 220 mm eder. Bunun üstüne motorlar,
kolon ve elektronik eklenince taban 370 × 357 mm oluyor. Daha küçük bir gövde ancak tablanın sabit, spindle'ın
hareketli olduğu bir düzenle (portal) mümkün.

## Taslağından farklar

- **LM8UU 6 değil 12 adet.** Her eksende iki mil, her milde iki rulman var; tek rulmanlı mil sallanır.
- **Y ekseni ortadan çekiliyor.** İki uç blok bir kontrplak lata ile bağlı, Y kayışı bu latanın ortasına bağlanıyor.
  Kayış bir yandan çekseydi tabla yanlamasına sıkışırdı.
- **Z ekseni:** üçüncü 28BYJ, T8 mil, 2 Z mili ve 4 LM8UU. DVD mekanizması yerine bu kullanıldı.
- **Spindle:** 775 motor (5 mm mil) ve 5 mm mile takılan pens seti (0,5–3,2 mm). MAN02 mandren 3,175 mm saplı
  karbür uçları tutmaz (en fazla 3 mm alıyor). Modeldeki "JT0 mandren" bu pens setinin yerini tutuyor.

## Parçalar

**3D baskı (`stl/`, PETG, %40 doluluk):** 4 Y mil tutucu, 2 uç blok (sol/sağ), 2 tabla rulman yuvası,
2 GT2-20 kasnak (X/Y), 2 avara, motor braketleri (X/Y), Y avara braketi, X avara braketi, 2 kayış kelepçesi,
Z arabası (spindle kelepçeli), Z alt ve üst braket, Z motor köprüsü.
- Rulman yuvaları Ø15,2, sıkı geçmeli. Mil delikleri Ø8,2; milleri M3 vida sıkıştırır.
- Kasnak dişi yaklaşık bir profil. Önce tek kasnak basıp kayışla dene; dişler oturmazsa betikte `GT2_T` ve
  oluk ölçüsünü ayarla.

**Kontrplak / MDF:**

| Parça | Ölçü (mm) |
|---|---|
| Taban (18 mm) | 370 × 357 |
| Kolon | 160 × 278 |
| Z plakası | 110 × 175 |
| 2 yanak | 105 × 175 |
| Tabla (9 mm) | 180 × 120 |
| Çapraz lata (8 mm) | 220 × 40 |
| Feda MDF (3 mm) | 164 × 104 |

**Satın alınacak:** fiyatlı liste `../bom-v0.xlsx`, "Delme makinesi v0" sayfasında. Toplam ~3.400 TL (KDV dahil,
2026-10-04). Kargo, filament, kontrplak ve pimler bu toplama dahil değil.
- 3 × 28BYJ-48 ve ULN2003 (RobitShop, tanesi 54 TL)
- 12 × LM8UU
- 5 × 300 mm krom mil. Kesilecek boylar: X 2 × 262, Y 2 × 250, Z 2 × 110 mm. 250 mm'lik mil
  Türkiye'de bulunamadı.
- 2 m GT2-6 kayış
- 2 hazır dişsiz GT2 avara (3 mm rulmanlı). 623ZZ Türkiye'de bulunamadı; baskı avara yedek.
- T8x8 400 mm mil ve somun (150 mm'ye kesilecek), 5×8 kaplin
- RS775 motor ve 5 mm mile takılan pens seti
- 3 mikro switch
- 2 × Ø3 pim (hırdavattan)
- 12 V 3 A adaptör ve LM2596 5 V düşürücü (28BYJ 5 V'luk)
- MOSFET kartı ve 1N5819 diyot
- M3/M4 vida ve somun

## Elektronik ve yazılım

- Pinler: 3 × 4 pin ULN2003, 1 PWM pin MOSFET'e (spindle), 3 pin switch'lere. ESP32-S3'te bunlar için yeterli pin var.
- Delme döngüsü: switch'lerle sıfırlama → pim deliklerini del → Excellon (.drl) dosyasındaki delikleri uç
  çapına göre gruplayıp en yakın komşu sırasıyla del. Uç değişiminde makine bekler, devam için düğmeye basılır.
  Dosyayı bilgisayar okur, ESP32'ye koordinatları gönderir.
- **Boşluk telafisi şart:** 28BYJ redüktöründe dişli boşluğu var. Her deliğe aynı yönden yaklaş: hedefin 0,5 mm
  ötesine git, sonra geri gel.
- **Z ekseni:** Delikler arasında uç plaketin 2 mm üstünde bekler; 30 mm'lik tam strok yalnız uç değişiminde
  kullanılır. Delik başına Z hareketi ~4 mm aşağı + 4 mm yukarı ≈ 4 sn. 100 delik + XY hareketleri ≈ 10 dk.
- **Z torku sınırda:** 28BYJ ~34 mN·m verir. T8 milin 8 mm'lik adımıyla bu, ~8 N itme kuvveti eder. Spindle'ın
  ağırlığını bir yayla dengele ki motor yalnız delme kuvvetini karşılasın. Yetmezse T8×2 mil kullan: kuvvet
  4 katına çıkar, hız 4'te birine düşer.

## Henüz doğrulanmadı

- Baskı toleransları (rulman sıkı geçmesi, kasnak dişi)
- 775 motor ve pens setinin salgısı: 0,6 mm altındaki karbür uçlar için kritik
- Spindle devri: Türkiye'de bulunan tek 5 mm milli 12 V 775 "3000 rpm" etiketli. Karbür uçlar ~10.000 rpm
  ister; bu motorla yavaş ilerle ya da daha hızlı bir 775 bul.
- 28BYJ'nin gerçek boşluğu ve kaçırdığı adım
- Taban ve kolonun rijitliği

Tasarım donanımda henüz denenmedi.
