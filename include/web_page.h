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
</style></head><body>
<header><h1>Mag<b>Panel</b></h1><span class=ver>{{VER}} &middot; 80&times;120</span>
<span class=dot id=dot></span></header>

<div class=card><h2>Galeri</h2>
<div class=grid>
<button onclick="art(0)">Mona Lisa</button>
<button onclick="art(1)">Yıldızlı Gece</button>
<button onclick="art(2)">Çığlık</button>
<button onclick="art(3)">Gemi Enkazı</button>
</div></div>

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
<label><span>Mozaik</span><input type=range id=mz min=1 max=20 value=1 oninput="setMosaic()"><output id=mzv>1</output></label>
<label><span>R kazanç</span><input type=range id=gr min=60 max=255 value=255 oninput="setGain()"><output id=grv>255</output></label>
<label><span>G kazanç</span><input type=range id=gg min=60 max=255 value=255 oninput="setGain()"><output id=ggv>255</output></label>
<label><span>B kazanç</span><input type=range id=gb min=60 max=255 value=255 oninput="setGain()"><output id=gbv>255</output></label>
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
 let frameCount=0;
 function step(){
  if(gifStop){vid.pause();vid.src='';URL.revokeObjectURL(url);addLog('DBG VID: durduruldu, toplam kare='+frameCount);return;}
  if(vid.readyState>=2){
   const s=Math.max(80/vid.videoWidth,120/vid.videoHeight),
    w=vid.videoWidth*s,h=vid.videoHeight*s;
   ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);
   ctx.drawImage(vid,(80-w)/2,(120-h)/2,w,h);
   const d=ctx.getImageData(0,0,80,120),b=new Uint8Array(1+28800);b[0]=1;
   for(let p=0,j=1;p<d.data.length;p+=4){b[j++]=d.data[p];b[j++]=d.data[p+1];b[j++]=d.data[p+2];}
   ctx.putImageData(d,0,0);
   if(ws&&ws.readyState===1&&ws.bufferedAmount<60000)ws.send(b);
   frameCount++;
   if(frameCount===1||frameCount===10)addLog('DBG VID: kare gonderildi #'+frameCount+' bufAmt='+ws.bufferedAmount);
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

// GIF fallback (Safari/Firefox): <img> ile native animasyon, RAF ile kare yakala
async function playGifFallback(file){
 const url=URL.createObjectURL(file);
 const img=new Image();
 try{await new Promise((res,rej)=>{img.onload=res;img.onerror=rej;img.src=url;});}
 catch(e){URL.revokeObjectURL(url);addLog('DBG GIF fallback: yuklenemedi: '+e);return false;}
 addLog('DBG GIF fallback: '+img.naturalWidth+'x'+img.naturalHeight+' - animasyon basladi');
 gifStop=false;
 function step(){
  if(gifStop){URL.revokeObjectURL(url);return;}
  const s=Math.max(80/img.naturalWidth,120/img.naturalHeight),
   w=img.naturalWidth*s,h=img.naturalHeight*s;
  ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);
  ctx.drawImage(img,(80-w)/2,(120-h)/2,w,h);
  const d=ctx.getImageData(0,0,80,120),b=new Uint8Array(1+28800);b[0]=1;
  for(let p=0,j=1;p<d.data.length;p+=4){b[j++]=d.data[p];b[j++]=d.data[p+1];b[j++]=d.data[p+2];}
  ctx.putImageData(d,0,0);
  if(ws&&ws.readyState===1&&ws.bufferedAmount<60000)ws.send(b);
  gifIsRaf=true;gifTimer=requestAnimationFrame(step);
 }
 gifIsRaf=true;gifTimer=requestAnimationFrame(step);
 return true;
}

async function loadImg(file){
 if(!file)return;
 stopGif();                                    // onceki animasyonu/videoyu durdur
 if(file.type.startsWith('video/')){await playVideo(file);return;}
 if(!file.type.startsWith('image/'))return;
 if(file.type==='image/gif'){
  if('ImageDecoder'in window){
   if(await playGif(file))return;
   addLog('DBG GIF: playGif false dondu (kare<2 veya decode hatasi)');
  } else {
   addLog('DBG GIF: ImageDecoder yok, img fallback kullaniliyor');
   if(await playGifFallback(file))return;
  }
 } const img=new Image();
 img.onload=()=>{const s=Math.max(80/img.width,120/img.height),
  w=img.width*s,h=img.height*s;
  ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);
  ctx.drawImage(img,(80-w)/2,(120-h)/2,w,h);sendFrame();
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
 ws.send(b);}
function clr(){stopGif();ctx.fillStyle='#000';ctx.fillRect(0,0,80,120);
 ws.send(new Uint8Array([3]));}
function art(i){stopGif();ws.send(new Uint8Array([5,i]));}

let gT=null;
function setGain(){grv.value=gr.value;ggv.value=gg.value;gbv.value=gb.value;
 clearTimeout(gT);gT=setTimeout(()=>ws.send(new Uint8Array([6,gr.value,gg.value,gb.value])),150);}
let iT=null;
function setImg(){ctv.value=ct.value;sav.value=sa.value;
 clearTimeout(iT);iT=setTimeout(()=>ws.send(new Uint8Array([7,ct.value,sa.value])),150);}
let mT=null;
function setMosaic(){mzv.value=mz.value;
 clearTimeout(mT);mT=setTimeout(()=>ws.send(new Uint8Array([8,parseInt(mz.value)])),150);}
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
