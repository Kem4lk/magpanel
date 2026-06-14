#!/usr/bin/env python3
"""
Wikimedia Commons API üzerinden orijinal dosya URL'lerini alır,
80x120'ye küçültür, gallery.h için C dizileri oluşturur.

Kullanım:
    source /tmp/mgpvenv/bin/activate
    python3 tools/gen_gallery_real.py
"""

import sys, io, pathlib, requests
from PIL import Image

W, H = 80, 120
# Bu betiği çalıştırdığın dizin neresi olursa olsun include/ klasörünü bul
SCRIPT_DIR = pathlib.Path(__file__).parent
OUT = SCRIPT_DIR.parent / "include" / "gallery.h"

HEADERS = {
    "User-Agent": "MagPanel/1.0 (https://github.com/Kem4lk/magpanel; kemalkamiloglu@gmail.com)",
}

# (değişken_adı, görünen_ad, Commons_dosya_adı)
# Wikimedia API bu adlardan güncel orijinal URL'yi otomatik alır
PAINTINGS = [
    ("Mona_Lisa",         "Mona Lisa",
     "Mona Lisa, by Leonardo da Vinci, from C2RMF retouched.jpg"),

    ("Yildizli_Gece",     "Yildizli Gece",
     "Van Gogh - Starry Night - Google Art Project.jpg"),

    ("Ciglik",            "Ciglik",
     "Edvard Munch, 1893, The Scream, oil, tempera and pastel on cardboard, 91 x 73 cm, National Gallery of Norway.jpg"),

    ("Gemi_Enkazi",       "Gemi Enkazi",
     "Turner - Rain, Steam and Speed - National Gallery file.jpg"),

    ("Buyuk_Dalga",       "Buyuk Dalga",
     "Tsunami by hokusai 19th century.jpg"),

    ("Kiz_Kupeyle",       "Kiz Kupeyle",
     "Meisje met de parel.jpg"),

    ("Son_Aksam_Yemegi",  "Son Aksam Yemegi",
     "Ultima Cena - Da Vinci 5.jpg"),

    ("Venus_Dogumu",      "Venus Dogumu",
     "Sandro Botticelli 046.jpg"),

    ("Athena_Okulu",      "Athena Okulu",
     "The School of Athens by Raffaello Sanzio da Urbino.jpg"),

    ("Ozgurluk_Rehberi",  "Ozgurluk Rehberi",
     "Eugène Delacroix - La liberté guidant le peuple.jpg"),

    ("Gece_Nobeti",       "Gece Nobeti",
     "Rembrandt van Rijn - De Nachtwacht.jpg"),

    ("Uyuyan_Venus",      "Uyuyan Venus",
     "Giorgione - Sleeping Venus - Google Art Project 2.jpg"),

    ("Goya_Kronos",       "Goya Kronos",
     "Francisco de Goya, Saturno devorando a su hijo (1819-1823).jpg"),

    ("Olympia",           "Olympia",
     "Edouard Manet - Olympia - Google Art Project 3.jpg"),

    ("Nilufer_Havuzu",    "Nilufer Havuzu",
     "Claude Monet - Water Lilies - 1906, Ryerson.jpg"),

    ("Saman_Arabasi",     "Saman Arabasi",
     "Constable The Hay Wain.jpg"),

    ("Buyuk_Jatte",       "Buyuk Jatte",
     "A Sunday on La Grande Jatte, Georges Seurat, 1884.png"),

    ("Dans_Dersi",        "Dans Dersi",
     "Dance at Le moulin de la Galette.jpg"),

    ("Persistans",        "Persistans",
     "The Persistence of Memory (1931) Salvador Dali.jpg"),

    ("Guernica",          "Guernica",
     "PicassoGuernica.jpg"),

    ("Amerikan_Gotigi",   "Amerikan Gotigi",
     "Grant Wood - American Gothic - Google Art Project.jpg"),

    ("Sistine_Yaratilis", "Sistine Yaratilis",
     "Michelangelo - Creation of Adam (cropped).jpg"),

    ("Bahar_Bahcesi",     "Bahar Bahcesi",
     "William-Adolphe Bouguereau (1825-1905) - The Birth of Venus (1879).jpg"),

    ("Iki_Frida",         "Iki Frida",
     "Las dos Fridas.jpg"),
]

# İlk 4 tablo (orijinal gallery_0..3) — bunlar zaten gerçek
ORIGINALS = [
    ("gallery_0", "Mona Lisa"),
    ("gallery_1", "Yildizli Gece"),
    ("gallery_2", "Ciglik"),
    ("gallery_3", "Gemi Enkazi"),
]


def get_wikimedia_url(filename):
    """Wikimedia Commons API'si üzerinden dosyanın orijinal URL'sini alır."""
    api = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
        "iiurlwidth": 1280,   # 1280px thumbnail iste (API bunu üretir)
    }
    r = requests.get(api, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    pages = r.json()["query"]["pages"]
    for page in pages.values():
        info = page.get("imageinfo", [{}])[0]
        thumb = info.get("thumburl")
        orig  = info.get("url")
        return thumb or orig
    return None


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    # cover-fit: en-boy oranını koru, 80x120'yi doldur
    s = max(W / img.width, H / img.height)
    nw, nh = int(img.width * s + 0.5), int(img.height * s + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - W) // 2
    top  = (nh - H) // 2
    return img.crop((left, top, left + W, top + H))


def pixels_to_c(img, var):
    flat = []
    for r, g, b in img.getdata():
        flat += [r, g, b]
    return f"const uint8_t {var}[{W*H*3}] PROGMEM = {{{','.join(map(str,flat))}}};\n"


def main():
    results = []
    for var, name, filename in PAINTINGS:
        print(f"  {name:25s} ... ", end="", flush=True)
        try:
            url = get_wikimedia_url(filename)
            if not url:
                print("URL bulunamadı")
                continue
            img = fetch(url)
            results.append((var, name, img))
            print("OK")
        except Exception as e:
            print(f"HATA: {e}")

    if not results:
        print("Hiç resim indirilemedi!", file=sys.stderr)
        sys.exit(1)

    # Mevcut gallery.h'dan orijinal 4 diziyi oku
    existing_h = OUT.read_text() if OUT.exists() else ""
    orig_arrays = {}
    for ovar, _ in ORIGINALS:
        import re
        m = re.search(rf"(const uint8_t {ovar}\[28800\][^;]*;)", existing_h, re.DOTALL)
        if m:
            orig_arrays[ovar] = m.group(1)

    all_names = [n for _, n, _ in PAINTINGS]
    all_vars  = [f"gallery_{v}" for v, _, _ in PAINTINGS]

    lines = [
        "// Public domain klasik tablolar - 80x120 RGB888\n",
        "#pragma once\n",
        "#include <stdint.h>\n",
        "#include <pgmspace.h>\n",
        f"#define GALLERY_COUNT {len(results)}\n",
        f"const char* const GALLERY_NAMES[GALLERY_COUNT] = "
        f"{{{','.join(chr(34)+n+chr(34) for _,n,_ in results)}}};\n",
    ]
    for var, name, img in results:
        lines.append(f"// {name}\n")
        lines.append(pixels_to_c(img, f"gallery_{var}"))
    ptrs = ",".join(f"gallery_{v}" for v, _, _ in results)
    lines.append(f"const uint8_t* const GALLERY_DATA[GALLERY_COUNT] = {{{ptrs}}};\n")

    OUT.write_text("".join(lines))
    print(f"\n✓ {len(results)} tablo → {OUT}")
    print("\nSonraki adımlar:")
    print("  git add include/gallery.h")
    print("  git commit -m 'feat: gerçek tablo görselleri (Wikimedia API)'")
    print("  git push origin claude/gallery-20-paintings")


if __name__ == "__main__":
    main()
