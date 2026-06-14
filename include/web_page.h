#pragma once
#include <pgmspace.h>
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html lang=tr><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>MagPanel</title><style>
:root{--bg:#0b0d10;--card:#15181d;--line:#262b33;--txt:#e8eaed;--mut:#9aa0a8;
--acc:#ffb454;--ok:#4ade80;--err:#f87171}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);
color:var(--txt);max-width:440px;margin:0 auto;padding:16px 16px 40px}
header{display:flex;align-items:baseline;gap:10px;margin:4px 2px 14px}
h1{font-size:22px;margin:0;letter-spacing:.3px}
h1 b{color:var(--acc)}
.ver{color:var(--mut);font-size:13px}
.dot{width:9px;height:9px;border-radius:50%;background:var(--err);display:inline-block;
margin-left:auto;align-self:center;transition:.3s}
.dot.on{background:var(--ok);box-shadow:0 0 8px var(--ok)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:14px;margin:12px 0}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:1.2px;
color:var(--mut);margin:0 0 12px;font-weight:600}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
button{font:inherit;font-size:14px;padding:11px 12px;border-radius:11px;cursor:pointer;
border:1px solid var(--line);background:#1c2027;color:var(--txt);transition:.15s}
button:active{transform:scale(.97)}
button.acc{background:var(--acc);border-color:var(--acc);color:#1a1206;font-weight:600}
.zone{border:2px dashed var(--line);border-radius:14px;padding:14px;text-align:center;
transition:.2s;margin-bottom:10px}
.zone.over{border-color:var(--acc);background:rgba(255,180,84,.07)}
canvas{width:200px;height:300px;background:#000;border-radius:8px;
image-rendering:pixelated;touch-action:none;display:block;margin:0 auto 8px}
.hint{color:var(--mut);font-size:12px;margin:6px 0 0}
.row{display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap}
.row button{flex:1}
input[type=color]{width:46px;height:40px;border:1px solid var(--line);border-radius:10px;
background:none;padding:2px}
label{display:flex;align-items:center;gap:10px;margin:10px 0;font-size:14px}
label span{width:74px;color:var(--mut)}
label output{width:34px;text-align:right;color:var(--acc);font-variant-numeric:tabular-nums}
input[type=range]{flex:1;accent-color:var(--acc)}
details summary{cursor:pointer;font-size:13px;text-transform:uppercase;
letter-spacing:1.2px;color:var(--mut);font-weight:600;margin-bottom:6px;list-style:none}
details summary::after{content:' +';color:var(--acc)}
details[open] summary::after{content:' \2212'}
.loghdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.loghdr span{font-size:13px;text-transform:uppercase;letter-spacing:1.2px;color:#9aa}
.logbtn{padding:5px 14px;font-size:12px;font-weight:600;border-radius:8px;
 background:var(--card);border:1px solid var(--line);color:var(--acc);cursor:pointer}
.logbtn.paused{background:var(--acc);border-color:var(--acc);color:#1a1206}
.logbox{margin:0;max-height:180px;overflow-y:auto;background:#0a0e14;
 border:1px solid var(--line);border-radius:10px;padding:10px;
 font-family:ui-monospace,Menlo,monospace;font-size:11px;line-height:1.5;
 color:#8fa;white-space:pre-wrap;word-break:break-word}
footer{text-align:center;margin-top:18px;display:flex;justify-content:center;align-items:center;gap:14px}
footer a{color:var(--mut);font-size:12px;text-decoration:none}
.ghbtn{font-size:12px;padding:6px 14px;border-radius:8px;background:var(--acc);
 border:none;color:#1a1206;font-weight:600;cursor:pointer}
.dclk{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0}
.dclk button{flex:1 1 auto;min-width:52px;padding:6px 4px;font-size:13px}
.dclk button.on{background:var(--acc);border-color:var(--acc);color:#1a1206;font-weight:700}
.tuneh{font-size:13px;color:var(--mut);margin:6px 0 2px}
.hint2{font-size:11px;color:var(--mut);margin-top:3px;line-height:1.35}
</style></head><body>
<header><h1>Mag<b>Panel</b></h1><span class=ver>{{VER}} &middot; 80&times;120</span>
<span class=dot id=dot></span></header>

<div class=card><h2>Galeri</h2>
<div class=grid id=galGrid><span style="color:var(--hint);font-size:12px">Yükleniyor…</span></div></div>

<div class=card id=recentCard style="display:none"><h2>Son Gönderilenler</h2>
<div id=recentGrid style="display:flex;flex-wrap:wrap;gap:8px"></div></div>

<div class=card><h2>Uygulamalar</h2>
<div class=grid>
<button onclick="appSel(1)">Saat</button>
<button onclick="appTimer()">Timer</button>
<button onclick="appWeather()">Hava</button>
<button onclick="appSel(4)">Dünya Kupası</button>
</div>
<div class=row>
<input id=timermin type=number min=0 max=99 value=5 title="Timer dakika"
 style="flex:0 0 70px;padding:9px;border-radius:10px;border:1px solid var(--line);background:#1c2027;color:var(--txt)">
<input id=weathercity placeholder="şehir (Hava için)"
 style="flex:1;padding:9px;border-radius:10px;border:1px solid var(--line);background:#1c2027;color:var(--txt)">
</div>
<div class=row>
<button onclick="appSpotify()">Spotify</button>
<button onclick="appSel(0)">Kapat</button>
</div>
<div class=hint>Panelde firmware tarafında çalışır; veriyi panel kendisi çeker, tarayıcı kapanabilir. Hava için şehir yazıp "Hava"ya bas. Son açık uygulama reboot'ta geri gelir.</div>
</div>

<div class=card><h2>Görsel &amp; Çizim</h2>
<div class=zone id=zone>
<canvas id=c width=80 height=120></canvas>
<div class=hint>Görsel veya video sürükle, yapıştır (&#8984;V) ya da dosya seç &middot; parmağınla/fareyle çiz</div>
</div>
<div class=row>
<input type=color id=col value="#ffb454">
<button onclick="f.click()">Dosya seç</button>
<button class=acc onclick="sendFrame()">Panele gönder</button>
</div>
<div class=row><button onclick="clr()">Paneli temizle</button></div>
<input type=file id=f accept="image/*,video/mp4,video/webm,video/quicktime,video/x-m4v" hidden>
</div>

<div class=card><details><summary>Görüntü ayarları</summary>
<label><span>Parlaklık</span><input type=range id=br min=10 max=255 value=110
 oninput="brv.value=this.value" onchange="ws.send(new Uint8Array([4,this.value]))"><output id=brv>110</output></label>
<label><span>Kontrast</span><input type=range id=ct min=60 max=200 value=128 oninput="setImg()"><output id=ctv>128</output></label>
<label><span>Doygunluk</span><input type=range id=sa min=0 max=220 value=128 oninput="setImg()"><output id=sav>128</output></label>
<label><span>Blur</span><input type=range id=bl min=0 max=3 value=0 oninput="setBlur()"><output id=blv>Kapalı</output></label>
<label><span>Mozaik</span><input type=range id=mz min=1 max=20 value=1 oninput="setMosaic()"><output id=mzv>1</output></label>
<label><span>R kazanç</span><input type=range id=gr min=60 max=255 value=255 oninput="setGain()"><output id=grv>255</output></label>
<label><span>G kazanç</span><input type=range id=gg min=60 max=255 value=255 oninput="setGain()"><output id=ggv>255</output></label>
<label><span>B kazanç</span><input type=range id=gb min=60 max=255 value=255 oninput="setGain()"><output id=gbv>255</output></label>
<div class=tuneh>DCLK / flicker — en yüksek MOZAİKSİZ hız</div>
<div class=dclk>
<button data-d=80 onclick="setDclk(80,this)">2.0</button>
<button data-d=64 onclick="setDclk(64,this)">2.5</button>
<button data-d=53 onclick="setDclk(53,this)">3.0</button>
<button data-d=46 onclick="setDclk(46,this)">3.5</button>
<button data-d=40 onclick="setDclk(40,this)">4.0</button>
<button data-d=36 onclick="setDclk(36,this)">4.5</button>
<button data-d=32 onclick="setDclk(32,this)">5.0</button>
<button data-d=27 onclick="setDclk(27,this)">6.0</button>
<button data-d=23 onclick="setDclk(23,this)">7.0</button>
<button data-d=20 onclick="setDclk(20,this)">8.0</button>
<button data-d=18 onclick="setDclk(18,this)">8.9</button>
<button data-d=16 onclick="setDclk(16,this)">10.0</button>
</div>
<div class=hint2>Hızı kademe kademe artır. Panelde 16px mozaik/bozulma görürsen bir alt kademeye in — en yüksek temiz hız flicker'ı en aza indirir. Seçim panele kaydedilir (reboot'ta kalır).</div>
<div class=row>
<button onclick="testW()">Beyaz test</button>
<button onclick="testRamp()">Gri merdiven</button>
</div></details></div>

<div class=card><div class=loghdr><span>LOG</span>
<button id=logbtn class=logbtn onclick="toggleLog()">Durdur</button></div>
<pre id=logbox class=logbox></pre></div>
<footer>
<a href=/update>firmware güncelle</a>
<button class=ghbtn onclick="otaCheck()">&#8593; GitHub'dan Güncelle</button>
</footer>
<script>
let ws,otaPending=false;
function connect(){
 ws=new WebSocket(`ws://${location.host}/ws`);ws.binaryType='arraybuffer';
 ws.onopen=()=>{
  dot.classList.add('on');
  if(otaPending){otaPending=false;setGhBtn(false,'&#8593; GitHub\'dan Güncelle');addLog('OTA: Baglandi - yeni firmware aktif!');}
 };
 ws.onclose=()=>{
  dot.classList.remove('on');
  if(otaPending)setGhBtn(true,'Güncelleniyor...');
  setTimeout(connect,2000);
 };
 ws.onmessage=e=>{if(typeof e.data==='string'&&e.data.startsWith('L:'))addLog(e.data.slice(2));};
}
connect();
function setGhBtn(disabled,html){const b=document.querySelector('.ghbtn');if(b){b.disabled=disabled;b.innerHTML=html;}}
const ctx=c.getContext('2d',{willReadFrequently:true});
ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);

let gifStop=false,gifTimer=null,gifIsRaf=false;
function stopGif(){
 gifStop=true;
 if(gifTimer){gifIsRaf?cancelAnimationFrame(gifTimer):clearTimeout(gifTimer);gifTimer=null;}
 gifIsRaf=false;
}

async function playVideo(file){
 addLog('DBG VID: basliyor type='+file.type+' size='+file.size);
 const url=URL.createObjectURL(file);
 const vid=document.createElement('video');
 vid.src=url;vid.muted=true;vid.loop=true;vid.playsInline=true;
 try{await new Promise((res,rej)=>{vid.onloadedmetadata=res;vid.onerror=rej;});}
 catch(e){URL.revokeObjectURL(url);addLog('DBG VID: metadata hatasi: '+e);return false;}
 addLog('DBG VID: metadata OK '+vid.videoWidth+'x'+vid.videoHeight+' sure='+vid.duration.toFixed(1)+'s');
 try{await vid.play();}catch(e){addLog('DBG VID: play() hatasi: '+e);URL.revokeObjectURL(url);return false;}
 addLog('DBG VID: oynatma basladi, RAF dongusu kuruluyor');
 gifStop=false;
 let frameCount=0,lastSend=0;
 function step(){
  if(gifStop){vid.pause();vid.src='';URL.revokeObjectURL(url);addLog('DBG VID: durduruldu, toplam kare='+frameCount);return;}
  if(vid.readyState>=2){
   drawScaled(vid,vid.videoWidth,vid.videoHeight);            // yüksek kaliteli küçültme
   // ~15fps gonderim: panel ve WiFi 60fps'i kaldiramaz; fazlasi heap/banding yapar
   const now=performance.now();
   if(now-lastSend>=66 && ws&&ws.readyState===1&&ws.bufferedAmount<40000){
    const d=ctx.getImageData(0,0,80,120),b=new Uint8Array(1+28800);b[0]=1;
    for(let p=0,j=1;p<d.data.length;p+=4){b[j++]=d.data[p];b[j++]=d.data[p+1];b[j++]=d.data[p+2];}
    ws.send(b);lastSend=now;frameCount++;
    if(frameCount===1||frameCount===30)addLog('DBG VID: kare gonderildi #'+frameCount+' bufAmt='+ws.bufferedAmount);
   }
  } else if(frameCount===0){addLog('DBG VID: readyState='+vid.readyState+' (bekleniyor)');}
  gifIsRaf=true;gifTimer=requestAnimationFrame(step);
 }
 gifIsRaf=true;gifTimer=requestAnimationFrame(step);
 return true;
}

// GIF: kareleri ImageDecoder ile ayristir, 80x120'ye olcekle, sirayla panele
// gonder (gercek animasyon). Tek kareli/desteksiz ise false doner -> statik yol.
async function playGif(file){
 let buf,dec;
 try{buf=await file.arrayBuffer();dec=new ImageDecoder({data:buf,type:'image/gif'});}
 catch(e){addLog('DBG GIF: decoder olusturulamadi: '+e);return false;}
 try{await dec.tracks.ready;}catch(e){addLog('DBG GIF: tracks.ready hata: '+e);}
 try{await dec.completed;}catch(e){addLog('DBG GIF: completed hata: '+e);}
 const track=dec.tracks&&dec.tracks.selectedTrack;
 const n=track?track.frameCount:0;
 addLog('DBG GIF: track='+(track?'var':'yok')+' frameCount='+n);
 if(!n||n<2){dec.close();return false;}
 const frames=[];                              // her kare: {onizleme, gonderim, gecikme}
 for(let i=0;i<n;i++){
  let r;try{r=await dec.decode({frameIndex:i});}catch(e){break;}
  const im=r.image;
  ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);
  const s=Math.max(80/im.displayWidth,120/im.displayHeight),
   w=im.displayWidth*s,h=im.displayHeight*s;
  ctx.drawImage(im,(80-w)/2,(120-h)/2,w,h);
  const d=ctx.getImageData(0,0,80,120),b=new Uint8Array(1+28800);b[0]=1;
  for(let p=0,j=1;p<d.data.length;p+=4){b[j++]=d.data[p];b[j++]=d.data[p+1];b[j++]=d.data[p+2];}
  frames.push({img:d,buf:b,delay:Math.max((im.duration||100000)/1000,50)});
  im.close();
 }
 dec.close();
 if(frames.length<2)return false;
 gifStop=false;let i=0;
 (function step(){
  if(gifStop)return;
  const fr=frames[i];
  ctx.putImageData(fr.img,0,0);                // tarayicida da onizle
  if(ws&&ws.readyState===1&&ws.bufferedAmount<60000)ws.send(fr.buf);  // birikme olmadan gonder
  i=(i+1)%frames.length;
  gifTimer=setTimeout(step,fr.delay);
 })();
 return true;
}

// === Minimal GIF89a cozucu (Safari/Firefox'ta ImageDecoder yok) ===
// DOM disi <img>+canvas hilesi GIF animasyonunu ILERLETMEZ (hep 0. kare
// yakalanir) -> Safari/iOS'ta animasyon olmamasinin sebebi buydu. Cozum:
// GIF'i JS'te LZW + disposal kompoziti ile gercekten coz, kare listesi cikar.
function gifDeinterlace(h){const r=[];for(let i=0;i<h;i+=8)r.push(i);for(let i=4;i<h;i+=8)r.push(i);for(let i=2;i<h;i+=4)r.push(i);for(let i=1;i<h;i+=2)r.push(i);return r;}
function gifLZW(minCode,data,pixelCount){
 const out=new Uint8Array(pixelCount);
 const clearCode=1<<minCode,eoiCode=clearCode+1;
 let codeSize=minCode+1,next=eoiCode+1,dict=[];
 const reset=()=>{dict=[];for(let i=0;i<clearCode;i++)dict[i]=[i];dict[clearCode]=[];dict[eoiCode]=[];next=eoiCode+1;codeSize=minCode+1;};
 reset();
 let bitPos=0,outPos=0,prev=null;
 const readCode=()=>{let code=0;for(let i=0;i<codeSize;i++){const bi=bitPos>>3;if(bi>=data.length)return eoiCode;if(data[bi]&(1<<(bitPos&7)))code|=(1<<i);bitPos++;}return code;};
 while(outPos<pixelCount){
  const code=readCode();
  if(code===eoiCode)break;
  if(code===clearCode){reset();prev=null;continue;}
  let entry;
  if(code<next&&dict[code])entry=dict[code];
  else if(prev)entry=prev.concat(prev[0]);
  else break;
  for(let i=0;i<entry.length&&outPos<pixelCount;i++)out[outPos++]=entry[i];
  if(prev){dict[next++]=prev.concat(entry[0]);if(next===(1<<codeSize)&&codeSize<12)codeSize++;}
  prev=entry;
 }
 return out;
}
function decodeGif(buf){
 const d=new Uint8Array(buf);let p=0;
 const rd=()=>d[p++],rd16=()=>{const v=d[p]|(d[p+1]<<8);p+=2;return v;};
 if(rd()!==0x47||rd()!==0x49||rd()!==0x46)return null;   // "GIF"
 p+=3;                                                    // surum (87a/89a)
 const W=rd16(),H=rd16(),pk0=rd();rd();rd();              // mantiksal ekran + bg + en-boy
 let gct=null;const gctSize=2<<(pk0&7);
 if(pk0&0x80){gct=new Uint8Array(gctSize*3);for(let i=0;i<gctSize*3;i++)gct[i]=rd();}
 const cc=document.createElement('canvas');cc.width=W;cc.height=H;
 const cx=cc.getContext('2d',{willReadFrequently:true});
 const frames=[];let delay=10,tIndex=-1,disposal=0,prevImg=null;
 while(p<d.length){
  const b=rd();
  if(b===0x3B)break;                                      // trailer
  if(b===0x21){const label=rd();                          // uzanti blogu
   if(label===0xF9){rd();const f=rd();delay=rd16();tIndex=rd();rd();disposal=(f>>2)&7;if(!(f&1))tIndex=-1;}
   else{let s;while((s=rd()))p+=s;}                        // diger uzantilari atla
   continue;}
  if(b!==0x2C)continue;                                    // sadece goruntu blogu
  const ix=rd16(),iy=rd16(),iw=rd16(),ih=rd16(),ipk=rd();
  let ct=gct;
  if(ipk&0x80){const ls=2<<(ipk&7);ct=new Uint8Array(ls*3);for(let i=0;i<ls*3;i++)ct[i]=rd();}
  const interlaced=ipk&0x40,minCode=rd();
  const dat=[];let s;while((s=rd())){for(let i=0;i<s;i++)dat.push(rd());}
  const idx=gifLZW(minCode,dat,iw*ih);
  if(disposal===3)prevImg=cx.getImageData(0,0,W,H);        // disposal=3: kareden once durumu sakla
  const fi=cx.getImageData(0,0,W,H),fd=fi.data,rows=interlaced?gifDeinterlace(ih):null;
  for(let row=0;row<ih;row++){const sy=interlaced?rows[row]:row;
   for(let col=0;col<iw;col++){const ci=idx[row*iw+col];if(ci===tIndex)continue;
    const px=((iy+sy)*W+(ix+col))*4;fd[px]=ct[ci*3];fd[px+1]=ct[ci*3+1];fd[px+2]=ct[ci*3+2];fd[px+3]=255;}}
  cx.putImageData(fi,0,0);
  frames.push({img:cx.getImageData(0,0,W,H),delay:Math.max(delay*10,50)});
  if(disposal===2)cx.clearRect(ix,iy,iw,ih);              // disposal=2: arka plana don
  else if(disposal===3&&prevImg)cx.putImageData(prevImg,0,0);
  tIndex=-1;disposal=0;delay=10;
 }
 return {W,H,frames};
}

// GIF fallback (Safari/Firefox): gercek JS cozucu -> kare kare animasyon
async function playGifFallback(file){
 let buf;try{buf=await file.arrayBuffer();}catch(e){addLog('DBG GIF: okunamadi '+e);return false;}
 let g;try{g=decodeGif(buf);}catch(e){addLog('DBG GIF: cozme hatasi '+e);return false;}
 if(!g||!g.frames||g.frames.length<2){addLog('DBG GIF: '+(g&&g.frames?g.frames.length:0)+' kare (animasyon yok)');return false;}
 addLog('DBG GIF cozuldu: '+g.W+'x'+g.H+' '+g.frames.length+' kare');
 // her kareyi 80x120'ye olcekle + gonderim buffer'i hazirla (oynatma sirasinda is yok)
 const tmp=document.createElement('canvas');tmp.width=g.W;tmp.height=g.H;
 const tc=tmp.getContext('2d',{willReadFrequently:true});
 const out=[];
 for(const fr of g.frames){
  tc.putImageData(fr.img,0,0);
  drawScaled(tmp,g.W,g.H);
  const dd=ctx.getImageData(0,0,80,120),b=new Uint8Array(1+28800);b[0]=1;
  for(let pp=0,j=1;pp<dd.data.length;pp+=4){b[j++]=dd.data[pp];b[j++]=dd.data[pp+1];b[j++]=dd.data[pp+2];}
  out.push({img:dd,buf:b,delay:fr.delay});
 }
 gifStop=false;
 // Gercek-zamanli oynatma (video yolu gibi): kumulatif zaman cizelgesi kur,
 // en fazla ~15fps (66ms) gonder, panel/WS yetisemezse kare DUSUR ki animasyon
 // YAVASLAMASIN. Eski setTimeout(delay) yolu, hizli GIF'lerde WS buffer'ini
 // tasirip duzensiz atlamaya yol aciyordu -> "cok yavas/takilarak" oynuyordu.
 let total=0;for(const fr of out){fr.t=total;total+=fr.delay;}
 const t0=performance.now();let lastShown=-1,lastSend=0;
 (function step(){
  if(gifStop)return;
  const el=(performance.now()-t0)%total;                   // dongusel gecen sure
  let idx=0;for(let k=0;k<out.length;k++){if(el>=out[k].t)idx=k;else break;}
  const now=performance.now();
  if(idx!==lastShown&&now-lastSend>=66&&ws&&ws.readyState===1&&ws.bufferedAmount<40000){
   ctx.putImageData(out[idx].img,0,0);                     // onizleme + panel ayni karede
   ws.send(out[idx].buf);lastShown=idx;lastSend=now;
  }
  gifIsRaf=true;gifTimer=requestAnimationFrame(step);
 })();
 return true;
}

// Yüksek kaliteli küçültme: büyük resmi 80x120'ye indirirken çok adımlı yarılama
// kullanır (her adımda boyut yarıya iner). Tek adımlı drawImage'dan çok daha keskin.
function hqScale(src, sw, sh){
 let tmp=document.createElement('canvas'),tc=tmp.getContext('2d');
 tmp.width=sw;tmp.height=sh;tc.drawImage(src,0,0,sw,sh);
 while(tmp.width>160||tmp.height>240){
  const nw=Math.max(Math.floor(tmp.width/2),80),nh=Math.max(Math.floor(tmp.height/2),120);
  const s2=document.createElement('canvas');s2.width=nw;s2.height=nh;
  const c2=s2.getContext('2d');c2.imageSmoothingEnabled=true;c2.imageSmoothingQuality='high';
  c2.drawImage(tmp,0,0,nw,nh);tmp=s2;
 }
 return tmp;
}
function drawScaled(src,srcW,srcH){
 const s=Math.max(80/srcW,120/srcH),sw=Math.round(srcW*s),sh=Math.round(srcH*s);
 const scaled=hqScale(src,sw,sh);
 ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);
 ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
 ctx.drawImage(scaled,Math.round((80-sw)/2),Math.round((120-sh)/2),sw,sh);
}
async function loadImg(file){
 if(!file)return;
 stopGif();                                    // onceki animasyonu/videoyu durdur
 if(file.type.startsWith('video/')){await playVideo(file);return;}
 if(!file.type.startsWith('image/'))return;
 if(file.type==='image/gif'){
  if('ImageDecoder'in window && await playGif(file))return;   // Chrome/Edge: hizli yol
  addLog('DBG GIF: JS cozucu deneniyor');                      // Safari/Firefox veya playGif basarisiz
  if(await playGifFallback(file))return;
  addLog('DBG GIF: animasyon yok, statik gosteriliyor');
 } const img=new Image();
 img.onload=()=>{
  drawScaled(img,img.naturalWidth,img.naturalHeight);sendFrame();
  URL.revokeObjectURL(img.src);};
 img.src=URL.createObjectURL(file);
}
f.onchange=e=>loadImg(e.target.files[0]);
zone.ondragover=e=>{e.preventDefault();zone.classList.add('over');};
zone.ondragleave=()=>zone.classList.remove('over');
zone.ondrop=e=>{e.preventDefault();zone.classList.remove('over');
 loadImg(e.dataTransfer.files[0]);};
window.onpaste=e=>{for(const it of e.clipboardData.items)
 if(it.type.startsWith('image/')){loadImg(it.getAsFile());break;}};

function sendFrame(){const d=ctx.getImageData(0,0,80,120).data,
 b=new Uint8Array(1+28800);b[0]=1;
 for(let i=0,j=1;i<d.length;i+=4){b[j++]=d[i];b[j++]=d[i+1];b[j++]=d[i+2];}
 ws.send(b);
 saveRecent(d);}
function clr(){stopGif();ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);
 ws.send(new Uint8Array([3]));}
function art(i){stopGif();ws.send(new Uint8Array([5,i]));}

// ---- Galeri butonlarini sunucudan çek (GALLERY_COUNT degisirse otomatik guncellenir) ----
fetch('/api/gallery').then(r=>r.json()).then(names=>{
 const g=document.getElementById('galGrid');g.innerHTML='';
 names.forEach((n,i)=>{const b=document.createElement('button');
  b.textContent=n;b.onclick=()=>art(i);g.appendChild(b);});
}).catch(()=>{});

// ---- Son Gönderilenler (localStorage) ----
const RECENT_KEY='mpRecent',RECENT_MAX=8;
function saveRecent(imgData){
 const tmp=document.createElement('canvas');tmp.width=80;tmp.height=120;
 tmp.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(imgData),80,120),0,0);
 const url=tmp.toDataURL('image/png');
 let lst=JSON.parse(localStorage.getItem(RECENT_KEY)||'[]');
 lst.unshift(url);if(lst.length>RECENT_MAX)lst=lst.slice(0,RECENT_MAX);
 try{localStorage.setItem(RECENT_KEY,JSON.stringify(lst));}catch(e){}
 renderRecent(lst);}
function renderRecent(lst){
 const card=document.getElementById('recentCard');
 const grid=document.getElementById('recentGrid');
 if(!lst||!lst.length){card.style.display='none';return;}
 card.style.display='';grid.innerHTML='';
 lst.forEach((url,idx)=>{
  const wrap=document.createElement('div');wrap.style.cssText='position:relative;display:inline-block;';
  const img=document.createElement('img');
  img.src=url;img.style.cssText='width:40px;height:60px;image-rendering:pixelated;border-radius:4px;cursor:pointer;border:2px solid var(--line);';
  img.title='Panele gönder';
  img.onclick=()=>{stopGif();
   const tmp=document.createElement('canvas');tmp.width=80;tmp.height=120;
   const ti=tmp.getContext('2d');const image=new Image();
   image.onload=()=>{ti.drawImage(image,0,0);
    const d2=ti.getImageData(0,0,80,120).data;
    const b=new Uint8Array(1+28800);b[0]=1;
    for(let i=0,j=1;i<d2.length;i+=4){b[j++]=d2[i];b[j++]=d2[i+1];b[j++]=d2[i+2];}
    ws.send(b);};image.src=url;};
  const del=document.createElement('span');
  del.textContent='×';del.title='Sil';
  del.style.cssText='position:absolute;top:1px;right:1px;background:#e53;color:#fff;border-radius:50%;width:14px;height:14px;display:flex;align-items:center;justify-content:center;font-size:10px;cursor:pointer;line-height:14px;';
  del.onclick=(e)=>{e.stopPropagation();
   let lst2=JSON.parse(localStorage.getItem(RECENT_KEY)||'[]');
   lst2.splice(idx,1);localStorage.setItem(RECENT_KEY,JSON.stringify(lst2));
   renderRecent(lst2);};
  wrap.appendChild(img);wrap.appendChild(del);grid.appendChild(wrap);});
}
renderRecent(JSON.parse(localStorage.getItem(RECENT_KEY)||'[]'));

let gT=null;
function setGain(){grv.value=gr.value;ggv.value=gg.value;gbv.value=gb.value;
 clearTimeout(gT);gT=setTimeout(()=>ws.send(new Uint8Array([6,gr.value,gg.value,gb.value])),150);}
let iT=null;
function setImg(){ctv.value=ct.value;sav.value=sa.value;
 clearTimeout(iT);iT=setTimeout(()=>ws.send(new Uint8Array([7,ct.value,sa.value])),150);}
const blurLabels=['Kapalı','3×3','5×5','7×7'];
let blT=null;
function setBlur(){const v=parseInt(bl.value);blv.value=blurLabels[v]||v;
 clearTimeout(blT);blT=setTimeout(()=>ws.send(new Uint8Array([0x0E,v])),150);}
let mT=null;
function setMosaic(){mzv.value=mz.value;
 clearTimeout(mT);mT=setTimeout(()=>ws.send(new Uint8Array([8,parseInt(mz.value)])),150);}
function setDclk(d,btn){                          // canli DCLK ayari (opcode 0x0A)
 if(ws&&ws.readyState===1)ws.send(new Uint8Array([10,d]));
 document.querySelectorAll('.dclk button').forEach(b=>b.classList.remove('on'));
 btn.classList.add('on');
 addLog('DCLK: ~'+Math.round(160000/d)+' kHz secildi (bolen '+d+')');}

// ====== Uygulamalar (firmware tarafi render; opcode 0x0B/0x0C/0x0D) ======
function appSel(id){stopGif();ws.send(new Uint8Array([0x0B,id]));
 addLog('Uygulama: '+['kapat','saat','timer','hava','dunya kupasi','spotify'][id]);}
function appTimer(){stopGif();
 const mn=parseInt(document.getElementById('timermin').value)||0;
 const sec=Math.max(0,Math.min(5999,mn*60));
 ws.send(new Uint8Array([0x0B,2,(sec>>8)&255,sec&255]));
 addLog('Timer: '+mn+' dk baslatildi');}
async function appWeather(){stopGif();
 const city=(document.getElementById('weathercity').value||'').trim();
 if(!city){addLog('Hava: once sehir yaz');return;}
 try{
  const r=await fetch('https://geocoding-api.open-meteo.com/v1/search?count=1&name='+encodeURIComponent(city));
  const j=await r.json();
  if(!j.results||!j.results.length){addLog('Hava: "'+city+'" bulunamadi');return;}
  const o=j.results[0];
  const nm=new TextEncoder().encode((o.name||city).substring(0,20));
  const b=new Uint8Array(9+nm.length),dv=new DataView(b.buffer);
  b[0]=0x0C;dv.setFloat32(1,o.latitude,true);dv.setFloat32(5,o.longitude,true);b.set(nm,9);
  ws.send(b);                                  // konumu firmware'e yolla (panel kendisi cekecek)
  ws.send(new Uint8Array([0x0B,3]));           // hava uygulamasini ac
  addLog('Hava: '+o.name+' ('+o.latitude.toFixed(2)+','+o.longitude.toFixed(2)+')');
 }catch(e){addLog('Hava hata: '+e);}}

// ---- Spotify (ISKELET) -------------------------------------------------
// KURULUM: 1) developer.spotify.com -> Create app. 2) Client ID'yi asagidaki
// SPOTIFY_CLIENT_ID'e yaz. 3) Uygulamanin "Redirect URIs" listesine panelin
// adresini ekle: bu sayfayi hangi adresle aciyorsan onu (or. http://magpanel.local/
// veya http://<panel-ip>/). IP DHCP'den degisirse Redirect URI kirilir -> routerda
// panele sabit IP rezervasyonu onerilir. Akis: PKCE ile tarayicida token alinir,
// WS 0x0D ile firmware'e yollanir; panel her 5 sn 'currently-playing'i ceker.
const SPOTIFY_CLIENT_ID='BURAYA_CLIENT_ID';    // <-- DOLDUR
const SPOTIFY_REDIRECT=location.origin+'/';
function spTok(t){const e=new TextEncoder().encode(t);const b=new Uint8Array(1+e.length);b[0]=0x0D;b.set(e,1);return b;}
function spVerifier(){const a=new Uint8Array(48);crypto.getRandomValues(a);
 return btoa(String.fromCharCode(...a)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');}
async function spChallenge(v){const d=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(v));
 return btoa(String.fromCharCode(...new Uint8Array(d))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=/g,'');}
async function appSpotify(){stopGif();
 if(SPOTIFY_CLIENT_ID==='BURAYA_CLIENT_ID'){
  addLog('Spotify: once web_page.h icinde SPOTIFY_CLIENT_ID doldur (yorumdaki kuruluma bak)');return;}
 const tok=sessionStorage.getItem('sp_token');
 if(tok){ws.send(spTok(tok));ws.send(new Uint8Array([0x0B,5]));addLog('Spotify: token gonderildi');return;}
 const v=spVerifier();sessionStorage.setItem('sp_verifier',v);
 const ch=await spChallenge(v);
 location.href='https://accounts.spotify.com/authorize?client_id='+SPOTIFY_CLIENT_ID+
  '&response_type=code&redirect_uri='+encodeURIComponent(SPOTIFY_REDIRECT)+
  '&scope='+encodeURIComponent('user-read-currently-playing')+
  '&code_challenge_method=S256&code_challenge='+ch;}
(async function(){                              // Spotify redirect geri donusu (?code=...)
 const code=new URLSearchParams(location.search).get('code');
 if(!code||SPOTIFY_CLIENT_ID==='BURAYA_CLIENT_ID')return;
 const v=sessionStorage.getItem('sp_verifier');if(!v)return;
 try{
  const r=await fetch('https://accounts.spotify.com/api/token',{method:'POST',
   headers:{'Content-Type':'application/x-www-form-urlencoded'},
   body:new URLSearchParams({client_id:SPOTIFY_CLIENT_ID,grant_type:'authorization_code',
    code,redirect_uri:SPOTIFY_REDIRECT,code_verifier:v})});
  const j=await r.json();
  if(j.access_token){sessionStorage.setItem('sp_token',j.access_token);
   history.replaceState({},'',location.pathname);
   addLog('Spotify: baglandi - "Spotify"ya tekrar bas');}
 }catch(e){addLog('Spotify token hata: '+e);}})();
function testW(){stopGif();ctx.fillStyle='#fff';ctx.fillRect(0,0,80,120);sendFrame();}
function testRamp(){stopGif();for(let i=0;i<6;i++){const v=40+i*43;
 ctx.fillStyle=`rgb(${v},${v},${v})`;ctx.fillRect(0,i*20,80,20);}sendFrame();}

let drawing=false;
function px(e){const r=c.getBoundingClientRect(),
 x=Math.floor((e.clientX-r.left)/r.width*80),
 y=Math.floor((e.clientY-r.top)/r.height*120);
 if(x<0||x>79||y<0||y>119)return;
 const cv=col.value,rr=parseInt(cv.substr(1,2),16),
 g=parseInt(cv.substr(3,2),16),bb=parseInt(cv.substr(5,2),16);
 ctx.fillStyle=cv;ctx.fillRect(x,y,2,2);
 const m=new Uint8Array(1+4*5);m[0]=2;let k=1;
 for(const[dx,dy]of[[0,0],[1,0],[0,1],[1,1]]){
  m[k++]=Math.min(x+dx,79);m[k++]=Math.min(y+dy,119);m[k++]=rr;m[k++]=g;m[k++]=bb;}
 ws.send(m);}
c.onpointerdown=e=>{stopGif();drawing=true;c.setPointerCapture(e.pointerId);px(e);};
c.onpointermove=e=>{if(drawing)px(e);};
c.onpointerup=c.onpointercancel=()=>drawing=false;
let logPaused=false;
function addLog(line){
 if(logPaused)return;
 const b=logbox;const atBottom=b.scrollHeight-b.scrollTop-b.clientHeight<30;
 b.textContent+=line+"\n";
 // en fazla 200 satir tut
 const lines=b.textContent.split("\n");
 if(lines.length>200)b.textContent=lines.slice(-200).join("\n");
 if(atBottom)b.scrollTop=b.scrollHeight;
}
function otaCheck(){
 if(!ws||ws.readyState!==1){addLog('OTA: WebSocket bagli degil');return;}
 setGhBtn(true,'Kontrol ediliyor...');
 otaPending=true;
 ws.send(new Uint8Array([9]));
 // 12 sn icinde WS kapanmazsa guncel demektir
 setTimeout(()=>{if(otaPending&&ws.readyState===1){otaPending=false;setGhBtn(false,'&#8593; GitHub\'dan Güncelle');addLog('OTA: Guncel, guncelleme yok.');}},12000);
}
function toggleLog(){
 logPaused=!logPaused;
 logbtn.textContent=logPaused?"Devam":"Durdur";
 logbtn.classList.toggle('paused',logPaused);
}
</script></body></html>
)rawliteral";
