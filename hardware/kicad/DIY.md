# Ev yapımı çift yüz kart: Elegoo Saturn 3 Ultra + negatif dry film

Aynı şematiğin evde yapılacak sürümü. Kart çizimi ayrı bir KiCad projesidir
(`magpanel-carrier-diy/`), çıktılar `fab-diy/` altındadır. Hepsi `gen_carrier.py --diy` ile
üretilir, fabrika kartının dosyalarına dokunmaz. Pozlama dosyaları Saturn 3 Ultra içindir (12K
ekran, 11520 × 5120 piksel). Düz Saturn 3 için bkz. 1. adım.

Tek yüz plaket için ayrı, daha büyük bir kart var: 150 × 100 mm, tek pozlama, 3 tel. Bkz.
[TEK-YUZ.md](TEK-YUZ.md).

![Ev yapımı kart, üst yüz](img/diy-top.png)

## Fabrika kartından farkı
| | Fabrika kartı (`fab/`) | Ev yapımı kart (`fab-diy/`) |
|---|---|---|
| Delik kaplaması | var | yok, her via'ya tel |
| Delikli parça pedleri | iki yüzde | yalnız altta, lehim alttan |
| SMD parçalar | üstte | altta |
| Üst katman | sinyal ve GND | yalnız via'lar arası köprü izleri |
| Sinyal izi / boşluk | 0.25 / 0.2 mm | 0.25 / 0.2 mm |
| Güç ve GND | 0.5–1.0 mm | 0.5–1.0 mm, boşluk 0.3 mm |
| Via | 0.6 / 0.3 mm | 1.6 / 0.8 mm, 33 adet |
| GND dökümü | iki yüzde | yalnız altta |
| Lehim maskesi, serigrafi | var | yok, montaj için 1:1 çizim |

Delikler kaplamasız olduğu için soket ve başlık pinleri yalnız alttan lehimlenir. Bu yüzden
delikli pedlerin bakırı sadece alttadır. Üst katmandaki izler iki via arasında köprü kurar,
parça pinine dokunmaz. Her via bir tel parçasıdır ve iki yüzden lehimlenir.

Üç HUB75 başlığı aynı yönde yan yana durur. Ortak hatlar başlık pinlerinin arasından geçmek
zorundadır, via'ların çoğu bu bölgededir. 0.3 mm iz ve 0.25 mm boşlukla aynı kart 40–45 via
istiyordu. Üst katmanda montaj deliklerinin çevresinde hizalama halkaları ve köşede "ÜST v1.2",
altta "ALT v1.2" yazısı var. Yazılar pozlamanın yönünü doğrular.

## Dosyalar
| Dosya | İçerik |
|---|---|
| `fab-diy/saturn3/*.goo` | yazıcıya hazır pozlama dosyaları, tablo 1. adımda |
| `fab-diy/magpanel-carrier-diy-gerber.zip` | gerber ve delik dosyaları, tablo aşağıda |
| `fab-diy/magpanel-carrier-diy-assembly-bottom.pdf` | alt yüz 1:1, alttan bakış: SMD'ler ve izler |
| `fab-diy/magpanel-carrier-diy-assembly-top.pdf` | üst yüz 1:1: delikli parçalar, köprü izleri, via'lar |
| `fab-diy/magpanel-carrier-diy-bom.csv` | malzeme listesi |
| `img/diy-top.png`, `img/diy-bottom.png` | görseller |

Zip içindekiler:
| Dosya | Ne için |
|---|---|
| `…-B_Cu.gbl` | alt bakır |
| `…-F_Cu.gtl` | üst bakır |
| `…-Edge_Cuts.gko` | kart dış hattı. UVtools kartın yerini bundan bulur, ışık vermez |
| `…-Hizalama.gbr` | hizalama çerçevesi: kart kenarından 0.5 mm dışarıda 3 mm ışıklı bant |
| `…-PTH.drl`, `…-NPTH.drl` | delikler. PTH.drl pozlamada pedlere matkap merkez noktası da koyar |
| `…-B_Mask.gbs`, `…-F_Mask.gts` | isteğe bağlı UV lehim maskesi |

## Malzemeler
| Malzeme | Not |
|---|---|
| Çift yüz bakır plaket | FR4 1.6 mm, 35 µm |
| Negatif dry film | mavi fotorezist film, iki yüz için |
| Laminatör ya da ütü | 100–110 °C |
| Sodyum karbonat (çamaşır sodası) | banyo: litrede 10 g, 25–30 °C |
| Sodyum persülfat ya da demir 3 klorür | aşındırma |
| Sodyum hidroksit (kostik) | film sökme: litrede 30–50 g |
| Matkap uçları | tablodaki çaplar, matkap standı |
| Via teli | 0.6 mm kalaylı bakır tel ya da kesilmiş direnç bacağı |
| Koruma | UV gözlük, eldiven, plastik kaplar |

Delikler:
| Çap | Adet | Nerede |
|---|---|---|
| 0.8 mm | 75 | 33 via, iki DIP soket, C1 |
| 1.0 mm | 114 | DevKit soketleri, HUB75 başlıkları, sensör başlıkları |
| 1.3 mm | 2 | klemens J1 |
| 3.2 mm | 4 | montaj delikleri |

## 1. Pozlama dosyaları
`fab-diy/saturn3/` içindeki dosyalar USB belleğe kopyalanıp doğrudan basılır.

| Dosya | Ne yapar | Süre |
|---|---|---|
| `pozlama-testi.goo` | 6 şerit: 60, 65 … 85 s. 5 s'lik eşit pozlamalar birikir | 120 s + 17 × 5 s |
| `alt-60s.goo` … `alt-85s.goo` | alt bakır + çerçeve + pedlerde matkap merkez noktası | 120 s + adındaki süre |
| `ust-60s.goo` … `ust-85s.goo` | üst bakır, aynalı + çerçeve | 120 s + adındaki süre |
| `cerceve.goo` | yalnız hizalama çerçevesi: yerleştirmeyi denemek için, şart değil | 120 s |

Her dosyanın ilk katmanı 2 dakika yalnız hizalama çerçevesini yakar. Kart bu sürede yerleştirilir,
pozlama sonra kendiliğinden başlar. Dosyayı durdurup yenisini başlatmak gerekmez, kart kaymaz.
Bakır dosyaları testteki altı süre için ayrı ayrı var: testte en iyi şerit hangisiyse aynı süreli
dosyayı bas. Bu filmle Saturn 3 Ultra'da 70–80 s iyi sonuç veriyor, test bu aralığı ortalar. Başka bir süre için: `DIY_EXPOSURE=25 $PY gen_carrier.py --diy fab` (virgülle birden
çok süre), ya da [UVtools](https://github.com/sn4k3/UVtools)'ta dosyayı aç, **Tools → Edit print
parameters**, yalnız Exposure time'ı değiştir. Bottom exposure time yerleştirme süresidir.

**Yazıcı modeli.** Dosyaların başlığındaki makine adı `ELEGOO Saturn 3 Ultra`. Yazıcı başka modelin
dosyasını format hatasıyla reddedebilir. Ekran iki modelde aynıdır. Düz Saturn 3 için:
`GOO_MACHINE='ELEGOO Saturn 3' $PY gen_carrier.py --diy fab`.

**Kendi dosyanı yapmak istersen** ya da yazıcı dosyayı açmazsa: Chitubox ya da Lychee'de kendi
yazıcın için küçük bir küp dilimle, `.goo` olarak kaydet, UVtools 7'de aç ve **Tools → PCB
exposure** aracını seç. Araç dosyanın katmanlarını silip pozlama görüntüsünü koyar. Bu dosyada
yerleştirme katmanı olmaz: kartı önce `cerceve.goo` ile yerleştir, durdur, sonra bakır dosyasını
başlat.

| Kaydet | Eklenecek dosyalar | Mirror |
|---|---|---|
| `cerceve.goo` | Edge_Cuts.gko, Hizalama.gbr | kapalı |
| `alt.goo` | Edge_Cuts.gko, B_Cu.gbl, Hizalama.gbr, PTH.drl | kapalı |
| `ust.goo` | Edge_Cuts.gko, F_Cu.gtl, Hizalama.gbr | açık |

| Ayar | Değer | Neden |
|---|---|---|
| Merge files into a single layer | açık | bakır, çerçeve ve delik noktaları tek pozlamada |
| Invert color | kapalı | negatif film: ışık alan yer sertleşir, altındaki bakır kalır |
| Anchor | Middle center | kart ekranın ortasına gelir, ışık orada en düzgün |
| Offset X / Y | 0 | |
| Exposure time | test süresi, `cerceve.goo` için 120 s | |
| Flip vertically | açık | varsayılan |
| Enable anti-aliasing | kapalı | |
| PTH.drl satırı | Size scale 0.4, Invert polarity işaretsiz | UVtools delikleri zaten karanlık çizer: pedin ortasında bakırsız nokta kalır |
| Edge_Cuts.gko satırı | board outline işaretli | `.gko` uzantısını kendisi tanır. Kartın yeri bu dosyadan hesaplanır |

Çerçeve simetriktir. Mirror görüntüyü çerçevenin, yani kartın tam ortasından aynalar. Bu ayarlarla
üç dosyada çerçeve aynı yere, ekranın ortasına düşer: UVtools 7.0.1 komut satırıyla üretilip
ölçüldü.

## 2. Kâğıtla prova
Hazneyi ve tablayı çıkar. Ekrana beyaz kâğıt koy, `alt-60s.goo`'yu ve `ust-60s.goo`'yu sırayla
başlat: her biri 2 dakika çerçeve, sonra 60 s desen. Telefon kamerasıyla yukarıdan bak. 405 nm
ışığa çıplak gözle uzun bakma.
- Çerçevenin tamamı ekranda görünmeli.
- `alt-60s.goo`'da "ALT v1.2", `ust-60s.goo`'da "ÜST v1.2" yazısı **ters** görünmeli. Bakır yüz
  ekrana bakar, yukarıdan kartın sırtını görürsün. Bir dosyada yazı düz görünüyorsa o dosyanın
  Mirror ayarını değiştir.
- İki yazı çerçevenin aynı köşesinde olmalı. Öyleyse kart 5. adımda sağdan sola çevrilir.
  Farklı köşelerdeyse yazıcı dikey aynalıyor: kartı çevirirken ön ve arka kenar yer değiştirsin.
- Yazıcı başlarken kolunu aşağı indirir. Tabla takılı değilken kol ekrana inmez, ama kolun nereye
  kadar indiğine bu provada bak. Kartın üstüne koyacağın ağırlık ondan alçak olsun.

## 3. Pozlama süresi testi
Filmin hassasiyeti markadan markaya değişir. `pozlama-testi.goo` altı süreyi tek seferde dener.
1. Yaklaşık 100 × 28 mm'lik bir plaket şeridine film lamine et (4. adımdaki gibi).
2. Dosyayı başlat. İlk 2 dakika yalnız çerçeve yanar, iç boşluğu 101 × 29 mm. Bu sürede şeridi
   film yüzü aşağıda çerçevenin ortasına koy, üstüne cam ve ağırlık. Altı şeridin tamamı
   plaketin altında kalmalı (96 × 24 mm). Pozlama sonra kendiliğinden başlar.
3. Banyo et (6. adım). Etiketler film yüzünde düz okunur, yukarıdan bakınca terstir.
4. Doğru süre: film kalkmayan şeritler içinde 0.2 mm çizgi aralıkları açık kalan ve pedlerin
   arasından geçen iz pedlere değmeyen en kısa süre. Uzun süre aralıkları kapatır, kısa süre
   filmi banyoda kaldırır.

## 4. Kartı hazırla
1. Plaketi 100.0 × 63.5 mm kes. Kenarları zımparala: çapak ekranı çizer.
2. Bakırı ince bulaşık teli ve deterjanla parlayana kadar temizle, durula, kurula.
   Parmak izi bırakma.
3. Sarı ışıkta ya da loş odada iki yüze film lamine et. Filmin yumuşak iç koruyucusunu soy,
   sert dış koruyucu üstte kalsın. Kabarcık bırakma.
4. Kartın bir uzun kenarının kalınlık yüzüne keçeli kalemle çizgi çek. Bu ön kenardır, iki
   pozlamada da yazıcının önüne bakar.

## 5. Hizala ve pozla
1. Hazne ve tabla takılı değil. Ekranı alkolle sil.
2. Testte seçtiğin sürenin alt dosyasını başlat, örneğin `alt-75s.goo`. İlk 2 dakika yalnız
   çerçeve yanar. Kartı film yüzü aşağıda, ön kenarı öne bakacak şekilde çerçevenin içine koy.
   Dört kenarda da eşit, ince karanlık boşluk kalsın (0.5 mm). Telefonla yakından bak.
3. Üstüne düz bir cam ve hafif bir ağırlık koy. Kart ekrana tam otursun ve kaymasın. 2 dakika
   dolunca bakır kendiliğinden pozlanır, bitmesini bekle. Yetişemezsen dosyayı durdur, baştan başlat.
4. Kartı kitap sayfası çevirir gibi çevir: sol ve sağ kenar yer değiştirir, ön kenar yine önde.
5. Aynı süreli üst dosyasını başlat, örneğin `ust-75s.goo`, ve kartı aynı şekilde ortala.

Sağ ve sol boşluğun eşitliği önemlidir. Çevirme yüzünden sağ-sol kayma iki yüz arasında iki
katına çıkar: 0.1 mm kayma via'larda 0.2 mm kaçıklık yapar. Via halkası 0.4 mm, buna dayanır.
Ön-arka kayma iki yüzü birlikte kaydırır, hizalamayı bozmaz.

## 6. Banyo, aşındırma, film sökme
1. Pozlamadan sonra 15 dakika beklet. İki yüzün dış koruyucusunu soy.
2. Banyo: litrede 10 g sodyum karbonat, 25–30 °C. Yumuşak fırçayla 1–3 dakika. Işık almamış film
   erir, altındaki bakır parlar. Bol suyla durula.
3. Kontrol: iki yazı da kendi yüzünde düz okunmalı. Kopuk izi asetat kalemiyle tamamla,
   köprüyü maket bıçağıyla kazı.
4. Aşındır: sodyum persülfat 40–50 °C'de 10–20 dakika, kabı salla. İki yüz birlikte aşınır.
5. Filmi sök: sodyum hidroksit çözeltisinde 1–2 dakika, sonra durula.
6. Bakır çabuk kararır. Hemen lehimlenmeyecekse kimyasal kalay ya da ince lak sür.

## 7. Delme
- Alt yüzden, pedlerin ortasından del. Merkez noktaları ucu ortalar.
- Önce bütün delikleri 0.8 mm ile aç, sonra büyükleri büyüt. Kayma azalır.
- Montaj delikleri hizalama halkalarının tam ortasındadır.

## 8. Via telleri ve montaj
1. **Via telleri ilk iş.** Teli geçir, iki yüzden lehimle, iki yüzde de dibinden kes. 12 via
   HUB75 başlıklarının, biri U3 soketinin altında kalır. Üstteki lehimi yassı bırak, başlık düz
   otursun.
2. **SMD'ler alt yüze.** `assembly-bottom.pdf` alttan bakıştır. D1 ve D2'nin katot bandı
   çizimdeki kapalı uca gelir.
3. **Delikli parçalar** üstten takılır, alttan lehimlenir: DIP soketler, sensör başlıkları,
   HUB75 başlıkları, klemens, C1. DevKit soketleri en son.
4. **Ölçüm.** Her via'nın iki pedi arasında süreklilik olmalı. HUB75 başlıklarında komşu pinler
   arasında kısa devre olmamalı. Sonra [README](README.md)'deki ilk açılış adımları.

## Tek yüz sürüm
Tek yüz plaketle yapılacak sürüm ayrı bir karttır: 150 × 100 mm, tek pozlama, bakır yüzde 3 tel,
DevKit pin adları bakırda yazılı. Anlatım ve dosyalar: [TEK-YUZ.md](TEK-YUZ.md).

## İsteğe bağlı: UV lehim maskesi
Delmeden önce alt yüze UV lehim maskesi sür. UVtools'ta Edge_Cuts.gko ve B_Mask.gbs ile yeni dosya
yap: **Invert color açık**, Invert area "Inside the board outline only". Ped açıklıkları karanlık
kalır, gerisi sertleşir. Pozlamadan sonra sertleşmeyen maskeyi alkolle sil.

## Yeniden üretmek
```bash
cd hardware/kicad
$PY gen_carrier.py --diy sch     # aynı şematik, ayrı proje
$PY gen_carrier.py --diy pcb     # SMD'ler alta, delikli pedler yalnız altta, üstte delik yasakları
$PY gen_carrier.py --diy route   # 6 deneme, DRC temiz olanlardan en az vialı kalır
$PY gen_carrier.py --diy fab     # gerber + çerçeve + delik + montaj çizimleri + .goo + görseller
```

- `fab` aşaması ERC/DRC sıfır değilse durur. Ayrıca iki bakır katmanın sınır kutusunun kartın
  tam ortasında olduğunu denetler: çerçeve eklenmese de aynalama ekseni kartın ortasında kalır.
- `.goo` dosyaları için UVtools 7 komut satırı gerekir (`UVtoolsCmd`, PATH'te ya da
  `UVTOOLS_CMD=/yol`). Yoksa bu adım atlanır, gerber'ler yine üretilir.
- Freerouting 2.1.0 komut satırında geçiş sınırını uygulamıyor. Bu yüzden her çalıştırmaya süre
  sınırı verilir (4 dakika, tamamlama turu 2 dakika). Takılan deneme elenir.
