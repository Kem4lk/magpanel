#!/usr/bin/env python3
"""
Gerçek Wikimedia resimlerini indir, 80x120'ye yeniden boyutlandır,
gallery.h için C uint8_t dizileri oluştur.

Kullanım (Mac/Linux terminalde):
    pip3 install Pillow requests
    python3 tools/gen_gallery_real.py
    # Oluşan include/gallery.h'ı commitle:
    git add include/gallery.h
    git commit -m "feat: gerçek tablo görselleri"
    git push
"""

import sys, io, pathlib, requests
from PIL import Image

W, H = 80, 120
OUT = pathlib.Path(__file__).parent.parent / "include" / "gallery.h"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://en.wikipedia.org/",
}

# (değişken_adı, görünen_ad, Wikimedia doğrudan URL)
PAINTINGS = [
    ("Mona_Lisa",          "Mona Lisa",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/"
     "Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg/"
     "402px-Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg"),

    ("Yildizli_Gece",      "Yildizli Gece",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/"
     "Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/"
     "800px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg"),

    ("Ciglik",             "Ciglik",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/"
     "Edvard_Munch%2C_1893%2C_The_Scream%2C_oil%2C_tempera_and_pastel_on_cardboard%2C_91_x_73_cm%2C_National_Gallery_of_Norway.jpg/"
     "400px-Edvard_Munch%2C_1893%2C_The_Scream%2C_oil%2C_tempera_and_pastel_on_cardboard%2C_91_x_73_cm%2C_National_Gallery_of_Norway.jpg"),

    ("Gemi_Enkazi",        "Gemi Enkazi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/"
     "Turner_-_Rain%2C_Steam_and_Speed_-_National_Gallery_file.jpg/"
     "800px-Turner_-_Rain%2C_Steam_and_Speed_-_National_Gallery_file.jpg"),

    ("Buyuk_Dalga",        "Buyuk Dalga",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/"
     "Tsunami_by_hokusai_19th_century.jpg/"
     "800px-Tsunami_by_hokusai_19th_century.jpg"),

    ("Kiz_Kupeyle",        "Kiz Kupeyle",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/"
     "Meisje_met_de_parel.jpg/"
     "800px-Meisje_met_de_parel.jpg"),

    ("Son_Aksam_Yemegi",   "Son Aksam Yemegi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/"
     "%C3%9Cltima_Cena_-_Da_Vinci_5.jpg/"
     "800px-%C3%9Cltima_Cena_-_Da_Vinci_5.jpg"),

    ("Venus_Dogumu",       "Venus Dogumu",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/"
     "Sandro_Botticelli_046.jpg/"
     "800px-Sandro_Botticelli_046.jpg"),

    ("Athena_Okulu",       "Athena Okulu",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/"
     "%22The_School_of_Athens%22_by_Raffaello_Sanzio_da_Urbino.jpg/"
     "800px-%22The_School_of_Athens%22_by_Raffaello_Sanzio_da_Urbino.jpg"),

    ("Ozgurluk_Rehberi",   "Ozgurluk Rehberi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/"
     "Eug%C3%A8ne_Delacroix_-_La_libert%C3%A9_guidant_le_peuple.jpg/"
     "800px-Eug%C3%A8ne_Delacroix_-_La_libert%C3%A9_guidant_le_peuple.jpg"),

    ("Gece_Nobeti",        "Gece Nobeti",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/"
     "Rembrandt_van_Rijn_-_De_Nachtwacht.jpg/"
     "800px-Rembrandt_van_Rijn_-_De_Nachtwacht.jpg"),

    ("Uyuyan_Venus",       "Uyuyan Venus",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/"
     "Giorgione_-_Sleeping_Venus_-_Google_Art_Project_2.jpg/"
     "800px-Giorgione_-_Sleeping_Venus_-_Google_Art_Project_2.jpg"),

    ("Goya_Kronos",        "Goya Kronos",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/"
     "Francisco_de_Goya%2C_Saturno_devorando_a_su_hijo_%281819-1823%29.jpg/"
     "800px-Francisco_de_Goya%2C_Saturno_devorando_a_su_hijo_%281819-1823%29.jpg"),

    ("Olympia",            "Olympia",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/"
     "Edouard_Manet_-_Olympia_-_Google_Art_Project_3.jpg/"
     "800px-Edouard_Manet_-_Olympia_-_Google_Art_Project_3.jpg"),

    ("Nilufer_Havuzu",     "Nilufer Havuzu",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/"
     "Claude_Monet_-_Water_Lilies_-_1906%2C_Ryerson.jpg/"
     "800px-Claude_Monet_-_Water_Lilies_-_1906%2C_Ryerson.jpg"),

    ("Saman_Arabasi",      "Saman Arabasi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/"
     "Constable_The_Hay_Wain.jpg/"
     "800px-Constable_The_Hay_Wain.jpg"),

    ("Buyuk_Jatte",        "Buyuk Jatte",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/"
     "A_Sunday_on_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.png/"
     "800px-A_Sunday_on_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.png"),

    ("Dans_Dersi",         "Dans Dersi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/"
     "Dance_at_Le_moulin_de_la_Galette.jpg/"
     "800px-Dance_at_Le_moulin_de_la_Galette.jpg"),

    ("Persistans",         "Persistans",
     "https://upload.wikimedia.org/wikipedia/en/d/dd/"
     "The_Persistence_of_Memory_1931_Salvador_Dali.jpg"),

    ("Guernica",           "Guernica",
     "https://upload.wikimedia.org/wikipedia/en/7/74/"
     "PicassoGuernica.jpg"),

    ("Amerikan_Gotigi",    "Amerikan Gotigi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/"
     "Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg/"
     "800px-Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg"),

    ("Sistine_Yaratilis",  "Sistine Yaratilis",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/"
     "Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg/"
     "800px-Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg"),

    ("Bahar_Bahcesi",      "Bahar Bahcesi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/"
     "William-Adolphe_Bouguereau_%281825-1905%29_-_The_Birth_of_Venus_%281879%29.jpg/"
     "533px-William-Adolphe_Bouguereau_%281825-1905%29_-_The_Birth_of_Venus_%281879%29.jpg"),

    ("Iki_Frida",          "Iki Frida",
     "https://upload.wikimedia.org/wikipedia/en/c/c5/"
     "Las_dos_Fridas_-_Frida_Kahlo.jpg"),
]


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    return img.resize((W, H), Image.LANCZOS)


def pixels_to_array(img, var):
    flat = []
    for r, g, b in img.getdata():
        flat += [r, g, b]
    return f"const uint8_t {var}[{W*H*3}] PROGMEM = {{{','.join(map(str,flat))}}};\n"


def main():
    results = []
    for var, name, url in PAINTINGS:
        print(f"  {name:25s} ... ", end="", flush=True)
        try:
            img = fetch(url)
            results.append((var, name, img))
            print("OK")
        except Exception as e:
            print(f"HATA: {e}")

    if not results:
        print("Hiç resim indirilemedi!", file=sys.stderr)
        sys.exit(1)

    lines = [
        "// Public domain klasik tablolar - 80x120 RGB888\n",
        "#pragma once\n",
        "#include <stdint.h>\n",
        "#include <pgmspace.h>\n",
        f"#define GALLERY_COUNT {len(results)}\n",
    ]

    names_str = ",".join(f'"{n}"' for _, n, _ in results)
    lines.append(f'const char* const GALLERY_NAMES[GALLERY_COUNT] = {{{names_str}}};\n')

    for var, name, img in results:
        lines.append(f"// {name}\n")
        lines.append(pixels_to_array(img, f"gallery_{var}"))

    ptrs = ",".join(f"gallery_{v}" for v, _, _ in results)
    lines.append(f"const uint8_t* const GALLERY_DATA[GALLERY_COUNT] = {{{ptrs}}};\n")

    OUT.write_text("".join(lines))
    print(f"\n✓ {len(results)} tablo → {OUT}")
    print("\nSonraki adım:")
    print("  git add include/gallery.h")
    print("  git commit -m 'feat: gerçek tablo görselleri (Wikimedia)'")
    print("  git push origin claude/gallery-20-paintings")


if __name__ == "__main__":
    main()
