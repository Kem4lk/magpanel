# MagPanel Deploy — MCP sunucusu

Claude'a **"yükle"** (veya "deploy") dediğinde firmware güncellemesini **internete bağlı
tüm panellere** otomatik ulaştıran küçük bir MCP sunucusu. Sıfır bağımlılık (sadece Node 18+).

## Nasıl çalışır?

Push mimarisi yerine, projenin mevcut **auto-OTA** akışını sürer:

1. `deploy_update` → GitHub Actions `build.yml` iş akışını tetikler (`workflow_dispatch`).
2. CI `firmware.bin` + `version.txt` üretir ve `latest` release'e koyar.
3. Her panel `GITHUB_AUTO_OTA` ile periyodik olarak `version.txt`'i yoklar. Build numarası
   artmışsa `firmware.bin`'i indirir, kurar ve yeniden başlar. Kurulum sırasında panelde
   **tüm piksellerden oluşan, alttan dolan loading ekranı** gösterilir.

Böylece NAT arkasındaki cihazlara doğrudan bağlanmaya gerek kalmaz; her cihaz güncellemeyi
kendisi çeker. Tipik gecikme: bir sonraki yoklama (~5 dk).

## Araçlar

| Araç | Açıklama |
|------|----------|
| `deploy_update` | CI'yı tetikler → tüm cihazlara dağıtır. `ref` (varsayılan `main`) ve `wait` (CI bitene kadar bekle) parametreleri. |
| `deployment_status` | Yayınlanan build'i (release + `version.txt`) ve son CI çalışmasının durumunu döndürür. |

## Kurulum

1. **GitHub token**: Actions `read/write` yetkili bir PAT oluşturun
   (fine-grained: bu repoya *Actions: Read and write*; veya classic: `repo` + `workflow`).
   Ortam değişkeni olarak verin:
   ```bash
   export GITHUB_TOKEN=ghp_xxx
   ```
2. Sunucu repodaki `.mcp.json` ile **otomatik kayıtlıdır**. Claude Code projeyi açtığında
   `magpanel-deploy` sunucusunu onaylamanızı ister. Token `${GITHUB_TOKEN}` ile ortamdan okunur
   (repoya secret yazılmaz).
3. Hazır. Artık Claude'a **"yükle"** / **"güncellemeyi gönder"** deyin → `deploy_update` çalışır.

### Manuel kayıt (alternatif)

```bash
claude mcp add magpanel-deploy -- node tools/magpanel-mcp/index.js
# GITHUB_TOKEN ortamda tanımlı olmalı
```

## Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `GITHUB_TOKEN` | — (zorunlu) | Actions read/write yetkili PAT |
| `GITHUB_REPO` | `Kem4lk/magpanel` | `sahip/repo` |
| `GITHUB_WORKFLOW_FILE` | `build.yml` | Tetiklenecek iş akışı dosyası |
| `DEPLOY_REF` | `main` | `deploy_update` için varsayılan dal/etiket |

## Notlar

- `deployment_status` token olmadan da (genel repo) çalışır; `deploy_update` token ister.
- Merge'den önce bir dalı test etmek için: `deploy_update` çağrısına `ref: "<dal-adı>"` verin.
  CI o dalı derleyip `latest`'e koyar ve cihazlar onu çeker.
