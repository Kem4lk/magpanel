// Host testi: g++ -std=c++17 -I include tools/test_sensor_logic.cpp -o /tmp/tsl && /tmp/tsl
// include/sensor_logic.h'daki saf durum makinelerini Arduino olmadan dogrular.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include "sensor_logic.h"
using namespace senslogic;

static int fails = 0;
#define CHECK(c) do{ if(!(c)){ printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); fails++; } }while(0)

static void testEncoder(){
  EncoderDecoder e;
  // KY-040: bekleme A=B=1 (pull-up). Bir yonde tam cevrim 11 -> 01 -> 00 -> 10 -> 11
  const uint8_t cw[]  = {0b11, 0b01, 0b00, 0b10, 0b11};   // (bit0=A, bit1=B) A once duser
  const uint8_t ccw[] = {0b11, 0b10, 0b00, 0b01, 0b11};   // B once duser
  int cwN=0, ccwN=0;
  for(int k=0;k<5;k++) for(uint8_t s: cw){ uint8_t d=e.step(s); if(d==ENC_CW)cwN++; if(d==ENC_CCW)ccwN++; }
  CHECK(cwN + ccwN == 5);                        // her tam cevrim tek olay
  int dirA = cwN ? 1 : -1;
  int cw2=0, ccw2=0;
  for(int k=0;k<5;k++) for(uint8_t s: ccw){ uint8_t d=e.step(s); if(d==ENC_CW)cw2++; if(d==ENC_CCW)ccw2++; }
  CHECK(cw2 + ccw2 == 5);
  int dirB = cw2 ? 1 : -1;
  CHECK(dirA == -dirB);                          // ters cevrim ters yon
  // Sicrama: yarim yolda geri don, olay uretmemeli
  EncoderDecoder f; int ev=0;
  for(uint8_t s: {0b11,0b01,0b11,0b01,0b11,0b01,0b00,0b01,0b00,0b10,0b00,0b10,0b11}){ if(f.step(s)) ev++; }
  CHECK(ev == 1);                                // sonunda tek gecerli adim
  // Detent'te sicrama (11 <-> 10) yeni olay uretmemeli
  for(uint8_t s: {0b10,0b11,0b10,0b11}){ if(f.step(s)) ev++; }
  CHECK(ev == 1);
  printf("encoder: ok (cw=%d ccw=%d)\n", cwN, ccwN);
}

static void testButton(){
  ButtonFsm b; b.debounceMs=30; b.longMs=700;
  uint32_t t=0; uint8_t r=0; int shorts=0, longs=0;
  auto run=[&](bool lvl, uint32_t until){ for(; t<until; t+=5){ r=b.feed(lvl,t); if(r==BTN_SHORT)shorts++; if(r==BTN_LONG)longs++; } };
  run(false,100);
  run(true,300);             // 200 ms basili
  run(false,500);            // birak -> kisa
  CHECK(shorts==1 && longs==0);
  run(true,1400);            // 900 ms basili -> uzun (bir kez)
  run(false,1600);           // birakinca kisa UYUYMAMALI
  CHECK(shorts==1 && longs==1);
  // 10 ms'lik glitch yok sayilmali
  run(true,1610); run(false,1800);
  CHECK(shorts==1 && longs==1);
  // basar basmaz tetikleme (dokunmatik)
  ButtonFsm tch; tch.fireOnPress=true; int n=0;
  for(uint32_t k=0;k<200;k+=5){ if(tch.feed(k>=50 && k<150, k)==BTN_SHORT) n++; }
  CHECK(n==1);
  printf("button: ok\n");
}

static void testDht(){
  // DHT11 ornek karesi: nem 45%, sicaklik 23.4 C
  uint8_t src[5] = {45, 0, 23, 4, 0}; src[4]=(uint8_t)(src[0]+src[1]+src[2]+src[3]);
  uint16_t hi[40];
  for(int i=0;i<40;i++){ bool one = src[i>>3] & (0x80>>(i&7)); hi[i] = one ? 70 : 27; }
  uint8_t out[5];
  CHECK(dhtDecode(hi,out));
  CHECK(memcmp(out,src,5)==0);
  DhtReading r = dhtParse(out,false);
  CHECK(r.ok && r.hum10==450 && r.temp10==234);
  hi[0] = 70;                                 // 0 olan MSB biti boz -> checksum tutmamali
  CHECK(!dhtDecode(hi,out));
  // DHT22 ornegi: 65.2% / -3.5 C
  uint8_t d22[5] = {0x02,0x8C,0x80,0x23,0}; d22[4]=(uint8_t)(d22[0]+d22[1]+d22[2]+d22[3]);
  DhtReading q = dhtParse(d22,true);
  CHECK(q.ok && q.hum10==652 && q.temp10==-35);
  printf("dht: ok (%d.%d C, %d%%)\n", r.temp10/10, r.temp10%10, r.hum10/10);
}

static void testEnvelopeClap(){
  Envelope env; env.winMs=20;
  // 2 kHz ornekleme, sessizlik: 2048 +- 20; alkis: +- 1500 (10 pencere = 60 ms)
  ClapDetector cd; cd.threshold=40;
  uint32_t us=0; int ev1=0, ev2=0;
  auto sample=[&](uint32_t untilMs, int swing){
    for(; us/1000 < untilMs; us += 500){
      int v = 2048 + ((rand()%(2*swing+1)) - swing);
      if(env.feed((uint16_t)v, us/1000)){
        uint8_t amp = (uint8_t)((uint32_t)env.lastAmp*100/4095);
        uint8_t e = cd.feed(amp, us/1000);
        if(e==1) ev1++;
        if(e==2) ev2++;
      }
    }
  };
  sample(2000, 20);           // sessizlik: taban oturur
  CHECK(ev1==0 && ev2==0);
  sample(2060, 1500);         // 1. alkis (60 ms)
  sample(2360, 20);           // 300 ms bosluk
  sample(2420, 1500);         // 2. alkis
  sample(3500, 20);
  CHECK(ev2==1 && ev1==0);    // cift alkis algilandi
  sample(3560, 1500);         // tek alkis
  sample(5000, 20);
  CHECK(ev1==1 && ev2==1);    // zaman asimi -> tek
  sample(5600, 1500);         // 600 ms surekli gurultu = alkis degil
  sample(7000, 20);
  CHECK(ev1==1 && ev2==1);
  // esik altinda kalan orta gurultu tetiklememeli (genlik ~%20)
  sample(8000, 400);
  sample(9000, 20);
  CHECK(ev1==1 && ev2==1);
  printf("envelope/clap: ok (smoothed=%u)\n", env.smoothed());
}

static void testAutoBri(){
  CHECK(autoBrightness(0,200,10)==10);
  CHECK(autoBrightness(100,200,10)==200);
  CHECK(autoBrightness(50,200,10)==105);
  CHECK(autoBrightness(120,200,10)==200);      // >100 kirpilir
  CHECK(autoBrightness(50,5,10)==5);           // kullanici min'in altinda -> kullanici
  CHECK(lightPercent(4095,false)==100 && lightPercent(0,false)==0 && lightPercent(4095,true)==0);
  CHECK(lightPercent(2048,false)==50 && lightPercent(2048,true)==50);
  printf("autobri: ok\n");
}

int main(){
  testEncoder(); testButton(); testDht(); testEnvelopeClap(); testAutoBri();
  if(fails){ printf("%d FAIL\n", fails); return 1; }
  printf("ALL OK\n"); return 0;
}
