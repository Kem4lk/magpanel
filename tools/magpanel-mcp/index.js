#!/usr/bin/env node
'use strict';
/*
 * MagPanel Deploy - MCP server (sifir bagimlilik, Node 18+)
 *
 * Amac: "yukle" dediginde firmware guncellemesini internete bagli TUM panellere
 * otomatik ulastirmak. Mekanizma projenin mevcut mimarisini kullanir:
 *   1) deploy_update  -> GitHub Actions 'build.yml' is akisini tetikler (workflow_dispatch).
 *   2) CI firmware.bin + version.txt uretip 'latest' release'e koyar.
 *   3) Her panel GITHUB_AUTO_OTA ile version.txt'i yoklar; build numarasi artmissa
 *      firmware.bin'i indirir, kurar (panelde dolan piksel loading ekrani gosterir),
 *      yeniden baslar. Boylece NAT arkasindaki cihazlara "push" gerekmeden ulasir.
 *
 * Ortam degiskenleri:
 *   GITHUB_TOKEN  (zorunlu) - Actions: read/write yetkili PAT (fine-grained veya classic repo+workflow)
 *   GITHUB_REPO   (varsayilan "Kem4lk/magpanel")
 *   GITHUB_WORKFLOW_FILE (varsayilan "build.yml")
 *   DEPLOY_REF    (varsayilan "main") - deploy_update icin varsayilan dal/etiket
 */

const REPO     = process.env.GITHUB_REPO || 'Kem4lk/magpanel';
const TOKEN    = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || '';
const WORKFLOW = process.env.GITHUB_WORKFLOW_FILE || 'build.yml';
const DEF_REF  = process.env.DEPLOY_REF || 'main';
const API      = 'https://api.github.com';
const UA       = 'magpanel-deploy-mcp';

// ---------- JSON-RPC (newline-delimited, MCP stdio transport) ----------
function send(msg){ process.stdout.write(JSON.stringify(msg) + '\n'); }
function ok(id, res){ if(id !== undefined && id !== null) send({ jsonrpc: '2.0', id, result: res }); }
function rpcError(id, code, message){ if(id !== undefined && id !== null) send({ jsonrpc: '2.0', id, error: { code, message } }); }

// ---------- GitHub helpers ----------
async function gh(path, opts = {}){
  if(!TOKEN) throw new Error("GITHUB_TOKEN tanimli degil. PAT'i ortam degiskeni olarak verin (.mcp.json env).");
  const res = await fetch(API + path, {
    method: opts.method || 'GET',
    headers: {
      'Authorization': `Bearer ${TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': UA,
      ...(opts.body ? { 'Content-Type': 'application/json' } : {})
    },
    body: opts.body
  });
  const text = await res.text();
  let data; try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if(!res.ok) throw new Error(`GitHub API ${res.status}: ${(data && data.message) || text || res.statusText}`);
  return data;
}

async function fetchText(url){
  const res = await fetch(url, { headers: { 'User-Agent': UA } });
  if(!res.ok) throw new Error(`${url} -> HTTP ${res.status}`);
  return (await res.text()).trim();
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function latestRun(){
  const runs = await gh(`/repos/${REPO}/actions/workflows/${encodeURIComponent(WORKFLOW)}/runs?per_page=1`);
  return (runs.workflow_runs && runs.workflow_runs[0]) || null;
}

// ---------- Tools ----------
async function deployUpdate(args){
  const ref = (args && args.ref) || DEF_REF;
  const before = await latestRun().catch(() => null);
  await gh(`/repos/${REPO}/actions/workflows/${encodeURIComponent(WORKFLOW)}/dispatches`, {
    method: 'POST', body: JSON.stringify({ ref })
  }); // 204 No Content

  let out = `🚀 Deploy tetiklendi: ${REPO} @ ${ref} (workflow: ${WORKFLOW}).\n` +
            `CI firmware.bin'i derleyip 'latest' release'e koyacak. Internete bagli tum paneller, ` +
            `GITHUB_AUTO_OTA yoklamasinda (~5 dk icinde) yeni build'i otomatik indirip kurar; ` +
            `kurulum sirasinda panelde tum piksellerden olusan dolan loading ekrani gosterilir.`;

  if(args && args.wait){
    out += `\n\n⏳ CI bekleniyor...`;
    const run = await waitForNewRun(before && before.id, 8 * 60 * 1000);
    if(!run)              out += `\nUyari: yeni CI calismasi zamaninda gorunmedi. deployment_status ile kontrol edin.`;
    else if(run.conclusion === 'success'){
      let ver = '?'; try { ver = await fetchText(`https://github.com/${REPO}/releases/latest/download/version.txt`); } catch {}
      out += `\n✅ CI #${run.run_number} basarili. Yayinlanan build: ${ver}. ${run.html_url}\nPaneller bir sonraki yoklamada guncellenecek.`;
    } else
      out += `\n❌ CI #${run.run_number} ${run.status}/${run.conclusion}. ${run.html_url}`;
  } else {
    out += `\n\nDurumu görmek için 'deployment_status' aracını çağırın (veya bu aracı wait:true ile çağırın).`;
  }
  return out;
}

async function waitForNewRun(beforeId, timeoutMs){
  const deadline = Date.now() + timeoutMs;
  let run = null;
  // yeni calismanin gorunmesini bekle
  while(Date.now() < deadline){
    const r = await latestRun().catch(() => null);
    if(r && r.id !== beforeId){ run = r; break; }
    await sleep(5000);
  }
  if(!run) return null;
  // tamamlanmasini bekle
  while(Date.now() < deadline){
    if(run.status === 'completed') return run;
    await sleep(7000);
    run = await gh(`/repos/${REPO}/actions/runs/${run.id}`).catch(() => run);
  }
  return run;
}

async function deploymentStatus(){
  let out = `📦 ${REPO}\n`;
  let rel = null; try { rel = await gh(`/repos/${REPO}/releases/latest`); } catch {}
  out += rel ? `Release: ${rel.name} (tag ${rel.tag_name}, ${rel.published_at})\n` : `Release: yok\n`;
  try { out += `Cihazlarin gordugu build (version.txt): ${await fetchText(`https://github.com/${REPO}/releases/latest/download/version.txt`)}\n`; } catch {}
  const run = await latestRun().catch(() => null);
  if(run) out += `Son CI: #${run.run_number} ${run.status}/${run.conclusion || '-'} (${run.event}@${run.head_branch})\n${run.html_url}\n`;
  out += `\nNot: Paneller NAT arkasinda olabilir; "push" yerine her cihaz periyodik olarak version.txt'i yoklar ve daha yeni build'i kendi indirir.`;
  return out;
}

const TOOLS = [
  {
    name: 'deploy_update',
    description: "MagPanel firmware guncellemesini internete bagli TUM panellere yayinlar. CI build.yml'i tetikler; " +
                 "firmware 'latest' release'e konur ve cihazlar GITHUB_AUTO_OTA ile otomatik kurar (panelde loading ekrani). " +
                 "Kullanici 'yukle' / 'deploy' / 'guncellemeyi gonder' dediginde bu araci kullan.",
    inputSchema: {
      type: 'object',
      properties: {
        ref:  { type: 'string',  description: "Derlenecek dal veya etiket (varsayilan: " + DEF_REF + "). Merge'den once test icin PR dalini verebilirsiniz." },
        wait: { type: 'boolean', description: 'CI tamamlanana kadar bekle ve sonucu dondur (varsayilan false).' }
      }
    }
  },
  {
    name: 'deployment_status',
    description: "Yayinlanan firmware build'ini (release + version.txt) ve son CI calismasinin durumunu dondurur. " +
                 "Guncellemenin yayinlanip yayinlanmadigini kontrol etmek icin kullan.",
    inputSchema: { type: 'object', properties: {} }
  }
];

async function callTool(name, args){
  if(name === 'deploy_update')       return await deployUpdate(args || {});
  if(name === 'deployment_status')   return await deploymentStatus();
  throw new Error('bilinmeyen arac: ' + name);
}

// ---------- stdio message loop ----------
async function handle(line){
  let msg; try { msg = JSON.parse(line); } catch { return; }
  const { id, method, params } = msg;
  switch(method){
    case 'initialize':
      ok(id, {
        protocolVersion: (params && params.protocolVersion) || '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'magpanel-deploy', version: '1.0.0' }
      });
      return;
    case 'notifications/initialized':
    case 'initialized':
      return; // bildirim - yanit yok
    case 'ping':
      ok(id, {});
      return;
    case 'tools/list':
      ok(id, { tools: TOOLS });
      return;
    case 'tools/call': {
      const name = params && params.name;
      const args = (params && params.arguments) || {};
      try {
        const text = await callTool(name, args);
        ok(id, { content: [{ type: 'text', text }] });
      } catch(e){
        ok(id, { content: [{ type: 'text', text: '❌ ' + (e && e.message ? e.message : String(e)) }], isError: true });
      }
      return;
    }
    default:
      rpcError(id, -32601, 'method not found: ' + method);
  }
}

let buf = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  buf += chunk;
  let nl;
  while((nl = buf.indexOf('\n')) >= 0){
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if(line) handle(line);
  }
});
process.stdin.on('end', () => process.exit(0));
process.on('SIGINT', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));
// stderr'e baslangic notu (stdout sadece JSON-RPC icindir)
process.stderr.write(`[magpanel-deploy] hazir; repo=${REPO} workflow=${WORKFLOW} token=${TOKEN ? 'var' : 'YOK'}\n`);
