#!/usr/bin/env python3
"""
Download public-domain paintings from Wikimedia Commons,
resize to 80x120 (W x H), and emit C array bytes for gallery.h.
"""

import urllib.request
import io
import sys
from PIL import Image

# (name_for_C_array, display_name, wikimedia_direct_url)
PAINTINGS = [
    ("Buyuk_Dalga",  "Buyuk Dalga",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Tsunami_by_hokusai_19th_century.jpg/800px-Tsunami_by_hokusai_19th_century.jpg"),
    ("Kiz_Kupeyle",  "Kiz Kupeyle",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Meisje_met_de_parel.jpg/800px-Meisje_met_de_parel.jpg"),
    ("Son_Aksam_Yemegi", "Son Aksam Yemegi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/%C3%9Cltima_Cena_-_Da_Vinci_5.jpg/800px-%C3%9Cltima_Cena_-_Da_Vinci_5.jpg"),
    ("Venüsün_Dogumu", "Venusun Dogumu",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Sandro_Botticelli_046.jpg/800px-Sandro_Botticelli_046.jpg"),
    ("Athena_Okulu", "Athena Okulu",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/%22The_School_of_Athens%22_by_Raffaello_Sanzio_da_Urbino.jpg/800px-%22The_School_of_Athens%22_by_Raffaello_Sanzio_da_Urbino.jpg"),
    ("Ozgurluk_Rehberi", "Ozgurluk Rehberi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Eug%C3%A8ne_Delacroix_-_La_libert%C3%A9_guidant_le_peuple.jpg/800px-Eug%C3%A8ne_Delacroix_-_La_libert%C3%A9_guidant_le_peuple.jpg"),
    ("Gece_Nobeti",   "Gece Nobeti",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Rembrandt_van_Rijn_-_De_Nachtwacht.jpg/800px-Rembrandt_van_Rijn_-_De_Nachtwacht.jpg"),
    ("Doga_Anasi",   "Doga Anasi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg/402px-Mona_Lisa%2C_by_Leonardo_da_Vinci%2C_from_C2RMF_retouched.jpg"),
    ("Sacre_Coeur",  "Sacre Coeur",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/VanGogh-starry_night_ballance1.jpg/800px-VanGogh-starry_night_ballance1.jpg"),
    ("Sistin_Tavanı","Sistin Tavani",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg/800px-Michelangelo_-_Creation_of_Adam_%28cropped%29.jpg"),
    ("Uyuyan_Venus", "Uyuyan Venus",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Giorgione_-_Sleeping_Venus_-_Google_Art_Project_2.jpg/800px-Giorgione_-_Sleeping_Venus_-_Google_Art_Project_2.jpg"),
    ("Goya_Kronos",  "Goya Kronos",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Francisco_de_Goya%2C_Saturno_devorando_a_su_hijo_%281819-1823%29.jpg/800px-Francisco_de_Goya%2C_Saturno_devorando_a_su_hijo_%281819-1823%29.jpg"),
    ("Olympia",      "Olympia",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Edouard_Manet_-_Olympia_-_Google_Art_Project_3.jpg/800px-Edouard_Manet_-_Olympia_-_Google_Art_Project_3.jpg"),
    ("Nilüfer_Havuzu","Nilufer Havuzu",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/Claude_Monet_-_Water_Lilies_-_1906%2C_Ryerson.jpg/800px-Claude_Monet_-_Water_Lilies_-_1906%2C_Ryerson.jpg"),
    ("Saman_Arabası", "Saman Arabasi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Constable_The_Hay_Wain.jpg/800px-Constable_The_Hay_Wain.jpg"),
    ("Büyük_Banyo",  "Buyuk Banyo",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/A_Sunday_on_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.png/800px-A_Sunday_on_La_Grande_Jatte%2C_Georges_Seurat%2C_1884.png"),
    ("Dans_Dersi",   "Dans Dersi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Dance_at_Le_moulin_de_la_Galette.jpg/800px-Dance_at_Le_moulin_de_la_Galette.jpg"),
    ("Persistans",   "Persistans",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/The_Persistence_of_Memory_1931_Salvador_Dali.jpg/800px-The_Persistence_of_Memory_1931_Salvador_Dali.jpg"),
    ("Guernica",     "Guernica",
     "https://upload.wikimedia.org/wikipedia/en/7/74/PicassoGuernica.jpg"),
    ("Amerikan_Gotiği","Amerikan Gotigi",
     "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg/800px-Grant_Wood_-_American_Gothic_-_Google_Art_Project.jpg"),
]

W, H = 80, 120

def fetch_and_convert(url, name):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img = img.resize((W, H), Image.LANCZOS)
    pixels = list(img.getdata())
    return pixels

def emit_array(var_name, pixels, f):
    f.write(f"const uint8_t {var_name}[{W*H*3}] PROGMEM = {{")
    flat = []
    for r, g, b in pixels:
        flat += [r, g, b]
    f.write(",".join(str(v) for v in flat))
    f.write("};\n")

def main():
    results = []
    for var, display, url in PAINTINGS:
        print(f"  Fetching: {display} ...", end=" ", flush=True)
        try:
            pixels = fetch_and_convert(url, var)
            results.append((var, display, pixels))
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")

    if not results:
        print("No paintings fetched!", file=sys.stderr)
        sys.exit(1)

    out_path = "/home/user/magpanel/include/gallery_new.h"
    with open(out_path, "w") as f:
        f.write("// Public domain klasik tablolar (ek 20) - 80x120 RGB888 PROGMEM\n")
        f.write("#pragma once\n")
        f.write("#include <pgmspace.h>\n\n")
        for var, display, pixels in results:
            f.write(f"// {display}\n")
            emit_array(f"gallery_new_{var}", pixels, f)
            f.write("\n")
        f.write(f"#define GALLERY_NEW_COUNT {len(results)}\n")
        names = ", ".join(f'"{d}"' for _, d, _ in results)
        f.write(f"const char* const GALLERY_NEW_NAMES[GALLERY_NEW_COUNT] PROGMEM = {{{names}}};\n")
        vars_ = ", ".join(f"gallery_new_{v}" for v, _, _ in results)
        f.write(f"const uint8_t* const GALLERY_NEW_PTRS[GALLERY_NEW_COUNT] PROGMEM = {{{vars_}}};\n")

    print(f"\nWrote {len(results)} paintings to {out_path}")

if __name__ == "__main__":
    main()
