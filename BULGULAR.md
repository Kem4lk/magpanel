# FM6363C 80x40 1/20 Panel + ESP32-S3 — Teknik Bulgular ve Durum

## Panel kimliği
- KingColor P4-2121-80x40-2S, FM6363C S-PWM sürücü (DriveChipType=51074), 74HC138 satır decode
- Renk başına 10 çip (UR1-10/UG/UB): yarı başına 5'li zincir, 16 kanal/çip
- Konnektör: standart HUB75E pinout (serigrafiyle doğrulandı)
- Fabrika .ssx profili çözüldü: CFG1 R/G/B=0x13F0/0x13B0/0x13B0, CFG2=0xF39D/0xE79D/0xD79D,
  CFG3=0x60B6, CFG4(default)=0x5A00/0x5A70/0x5A70; GCLKMaxNum=73 (74 GCLK/satır),
  GCLKDeadTime=3, VSYNC LE=3, PRE_ACT=14; LookUpTab = birebir kimlik (remap yok)

## Kanıtlanmış protokol bilgisi
- LE komutları: DATA_LATCH=1, VSYNC=3, WR_CFG1/2/3/4=4/6/8/10, EN_OP=12, DIS_OP=13, PRE_ACT=14
- Init: PRE_ACT, EN_OP, sonra her register öncesi PRE_ACT (calismasi dogrulandi)
- Frame başı (gerçek kontrolcü kaydı): LE=14,12,3 (PRE_ACT, EN_OP, VSYNC)
- KRİTİK KEŞİF: HUB75 modunda (cfg1[5:4]=11) çip, gelen satır verisini O ANKİ HARİCİ
  ADRESİN seçtiği SRAM satırına yazıyor (adres-eşzamanlı yazım). Asenkron tarama+veri
  mimarisi bu yüzden satır-değişken içeriği dağıtıyor; satır-sabit içerik (dolgular) etkilenmiyor.
  Gerçek alıcı kartlar her satırın verisini o satırın tarama dilimi içinde gönderir.

## Ölçülmüş eşleme (kalibrasyonla)
- X tam aynalı: x' = 79 - x (blok sırası b→4-b VE blok içi kanal c→15-c, ikisi de ters)
- Yarılar takaslı: fiziksel ÜST yarı ← R2/G2/B2, ALT yarı ← R1/G1/B1
- Satır eşleme: senkron motorda kimlik + ofset (runtime row_offset ile taranabilir)

## Donanım notları
- Ortak GND şart; 2 GND bağlı. Jumper'larla DCLK ≤ 2.5MHz güvenli; 7MHz sınırda
- HUB75 OE pini = GCLK; CLK = DCLK; LAT = LE

## Yazılım mimarileri
1. v13 (çift motor: LCD=veri, GPSPI2=GCLK+adres): Dolgu/RGB döngüsü/satır-sabit içerik KUSURSUZ.
   Satır-değişken içerik adres-eşzamanlı yazım yüzünden dağılıyor. Yedeği: include/Matrix_v13_backup.h
2. syncengine (tek motor: LCD d0-d6=veri/LAT, d7=GCLK, d8-12=A-E): Yatay içerik artık
   görünüyor; satır hizası (row_offset) ve segment-içi renk karışması (veri/GCLK bit zamanlaması)
   henüz çözülmedi. Mevcut kod bu mimaride.

## Kalan iş ve önerilen yol
- Logic analyzer ile DCLK/LE/GCLK dalga biçimini kılavuz Şekil/Tablolarıyla karşılaştırmak
  (en hızlı bitirme yolu). Şüpheliler: LE kenarının DCLK fazına göre konumu, GCLK'nın
  latch anındaki durumu, satır dilimi içinde veri→GCLK sıralaması.
- Alternatif: HD-R500 benzeri alıcı kart (garanti çözüm, .ssx hazır).
- Topluluk: mrcodetastic/ESP32-PWM-MatrixPanel-DMA issue'larında FM6363 portu açıkça davet
  edilmiş durumda; bu bulgular oraya taşınabilir.
