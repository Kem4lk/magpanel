#!/usr/bin/env python3
"""
Generates stylized 80x120 pixel-art representations of 20 famous public-domain
paintings, emitting C uint8_t arrays for inclusion in gallery.h.
Each image is hand-tuned with the painting's actual dominant color palette
and recognizable composition shapes.
"""

import struct, math
from PIL import Image, ImageDraw

W, H = 80, 120

def px(img, x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        img.putpixel((x, y), (r, g, b))

def fill(img, x0, y0, x1, y1, r_or_tuple, g=None, b=None):
    draw = ImageDraw.Draw(img)
    if g is None:
        col = r_or_tuple
    else:
        col = (r_or_tuple, g, b)
    draw.rectangle([x0, y0, x1, y1], fill=col)

def gradient_v(img, x0, y0, x1, y1, top, bot):
    for y in range(y0, y1+1):
        t = (y - y0) / max(1, y1 - y0)
        r = int(top[0]*(1-t) + bot[0]*t)
        g = int(top[1]*(1-t) + bot[1]*t)
        b = int(top[2]*(1-t) + bot[2]*t)
        fill(img, x0, y, x1, y, r, g, b)

def gradient_h(img, x0, y0, x1, y1, left, right):
    for x in range(x0, x1+1):
        t = (x - x0) / max(1, x1 - x0)
        r = int(left[0]*(1-t) + right[0]*t)
        g = int(left[1]*(1-t) + right[1]*t)
        b = int(left[2]*(1-t) + right[2]*t)
        fill(img, x, y0, x, y1, r, g, b)

def circle(img, cx, cy, radius, color):
    draw = ImageDraw.Draw(img)
    draw.ellipse([cx-radius, cy-radius, cx+radius, cy+radius], fill=color)

def noise(img, x0, y0, x1, y1, base, var, seed=0):
    import random; rng = random.Random(seed)
    for y in range(y0, y1+1):
        for x in range(x0, x1+1):
            r = max(0,min(255, base[0]+rng.randint(-var,var)))
            g = max(0,min(255, base[1]+rng.randint(-var,var)))
            b = max(0,min(255, base[2]+rng.randint(-var,var)))
            px(img, x, y, r, g, b)

# ─── 1. Büyük Dalga — Hokusai ────────────────────────────────────────────────
def buyuk_dalga():
    img = Image.new("RGB", (W, H), (240, 230, 210))
    # Sky
    gradient_v(img, 0, 0, W-1, 50, (240,230,210), (200,215,230))
    # Mt Fuji (white triangle)
    draw = ImageDraw.Draw(img)
    draw.polygon([(40,15),(25,45),(55,45)], fill=(255,255,255))
    draw.polygon([(40,15),(35,30),(45,30)], fill=(180,200,220))
    # Dark ocean
    fill(img, 0, 50, W-1, H-1, (15, 50, 100))
    # Big wave: curved blue shapes
    for xi in range(W):
        t = xi / W
        wave_y = int(55 + 20*math.sin(t*math.pi))
        foam_y = wave_y - 12
        for y in range(foam_y, wave_y):
            yr = (y - foam_y) / max(1, wave_y - foam_y)
            r = int(15 + 80*yr); g = int(60 + 80*yr); b = int(130 + 60*yr)
            px(img, xi, y, r, g, b)
        for y in range(wave_y, min(wave_y+8, H)):
            px(img, xi, y, 220, 230, 240)  # white foam
    # Small waves at bottom
    for xi in range(W):
        t = xi/W
        wy = int(100 + 8*math.sin(t*2*math.pi))
        for y in range(wy, min(wy+4, H)):
            px(img, xi, y, 200, 220, 235)
    return img

# ─── 2. Kız Küpeli — Vermeer ─────────────────────────────────────────────────
def kiz_kupeyle():
    img = Image.new("RGB", (W, H), (20, 20, 25))
    # Background: dark teal gradient
    gradient_v(img, 0, 0, W-1, H-1, (40,65,55), (10,15,20))
    # Head+face (oval, warm skin)
    draw = ImageDraw.Draw(img)
    draw.ellipse([18, 15, 62, 75], fill=(210, 165, 120))
    # Turban: deep blue
    draw.polygon([(18,35),(40,8),(62,35),(50,20),(30,20)], fill=(30,60,110))
    draw.ellipse([22, 8, 58, 40], fill=(30, 60, 110))
    # Yellow cloth highlight on turban
    draw.polygon([(38,8),(44,8),(50,18),(42,22),(36,18)], fill=(200,170,40))
    # Eyes
    draw.ellipse([26,37,36,44], fill=(255,240,220)); draw.ellipse([28,38,34,43], fill=(80,55,30))
    draw.ellipse([44,37,54,44], fill=(255,240,220)); draw.ellipse([46,38,52,43], fill=(80,55,30))
    # Nose + lips
    draw.ellipse([37,50,43,56], fill=(190,140,100))
    draw.ellipse([33,60,47,67], fill=(180,90,70))
    draw.ellipse([34,62,46,66], fill=(210,130,110))
    # Pearl earring
    circle(img, 18, 62, 5, (230,225,215))
    # Collar
    draw.ellipse([20,70,60,95], fill=(240,235,220))
    # Clothes (blue-grey)
    fill(img, 15, 80, 65, H-1, (70,90,120))
    # Soft light on cheek
    draw.ellipse([52,38,60,50], fill=(230,195,155))
    return img

# ─── 3. Son Akşam Yemeği — Da Vinci ──────────────────────────────────────────
def son_aksam_yemegi():
    img = Image.new("RGB", (W, H), (160,130,90))
    # Wall + windows
    gradient_v(img, 0, 0, W-1, 55, (200,175,140), (160,130,90))
    # Three arched windows
    for wx in [12, 39, 66]:
        draw = ImageDraw.Draw(img)
        draw.rectangle([wx-7,10,wx+7,45], fill=(200,220,240))
        draw.ellipse([wx-7,6,wx+7,20], fill=(200,220,240))
    # Table
    fill(img, 0, 68, W-1, 85, (140,100,60))
    fill(img, 0, 85, W-1, H-1, (100,70,40))
    # Tablecloth
    fill(img, 0, 68, W-1, 72, (220,210,195))
    # Figures (13 silhouettes)
    colors = [(180,150,100),(160,130,80),(190,160,110),(170,140,90),(185,155,105),
              (175,145,95),(140,110,70),(175,145,95),(185,155,105),(170,140,90),
              (190,160,110),(160,130,80),(180,150,100)]
    for i, (r,g,b) in enumerate(colors):
        fx = int(2 + i * 5.8)
        draw.ellipse([fx,52,fx+5,58], fill=(210,175,130))  # head
        draw.rectangle([fx,58,fx+5,68], fill=(r,g,b))       # body
    # Jesus in center (slightly taller, highlighted)
    draw.ellipse([37,48,43,56], fill=(220,185,140))
    draw.rectangle([37,56,43,68], fill=(150,100,70))
    fill(img, 35,67,45,68, (220,215,200))  # halo glow
    return img

# ─── 4. Venüs'ün Doğuşu — Botticelli ────────────────────────────────────────
def venus_dogumu():
    img = Image.new("RGB", (W, H), (110,185,215))
    # Sky + sea
    gradient_v(img, 0, 0, W-1, 60, (200,230,245), (110,185,215))
    gradient_v(img, 0, 60, W-1, H-1, (80,160,195), (50,120,160))
    # Sea waves
    for y in range(65, 85, 4):
        for x in range(W):
            t = x/W
            wy = y + int(2*math.sin(t*4*math.pi + y))
            if 0<=wy<H: px(img, x, wy, 160, 210, 230)
    # Shell (half-circle at bottom)
    draw = ImageDraw.Draw(img)
    draw.ellipse([25, 70, 55, 95], fill=(235,210,165))
    draw.ellipse([27, 72, 53, 88], fill=(210,185,140))
    # Venus (nude figure, skin tone)
    draw.ellipse([34, 30, 46, 42], fill=(235,200,165))  # head
    draw.rectangle([34, 40, 46, 70], fill=(235,200,165))  # body
    # Golden hair
    draw.polygon([(34,30),(28,22),(40,28),(38,18),(46,28),(52,22),(46,30)],
                 fill=(220,180,60))
    # Flowers (pink)
    for fx,fy in [(15,25),(65,30),(10,50),(70,45)]:
        circle(img, fx, fy, 5, (240,160,160))
        circle(img, fx, fy, 2, (255,220,220))
    # Wind figure (left, blue drapery)
    draw.ellipse([2, 20, 20, 50], fill=(160,200,230))
    draw.rectangle([2, 40, 18, 65], fill=(140,185,215))
    # Grace figure (right, red)
    draw.rectangle([62, 35, 78, 75], fill=(200,100,80))
    return img

# ─── 5. Okul of Athens — Raphael ─────────────────────────────────────────────
def athena_okulu():
    img = Image.new("RGB", (W, H), (195,180,155))
    # Arch architecture (creamy stone)
    gradient_v(img, 0, 0, W-1, H-1, (215,200,170), (170,150,120))
    draw = ImageDraw.Draw(img)
    # Big arch
    draw.arc([5, 2, 75, 80], start=180, end=0, fill=(145,125,95), width=5)
    # Inner arch
    draw.arc([15, 12, 65, 65], start=180, end=0, fill=(155,135,105), width=3)
    # Floor tiles
    for y in range(80, H, 8):
        fill(img, 0, y, W-1, y+1, (140,120,90))
    for x in range(0, W, 10):
        fill(img, x, 80, x+1, H-1, (140,120,90))
    # Sky through arch
    fill(img, 20, 15, 60, 50, (180,200,220))
    # Figures (colorful robes)
    figure_colors = [(180,100,60),(60,100,180),(160,60,80),(100,160,60),(80,80,160)]
    for i, col in enumerate(figure_colors):
        fx = 8 + i * 14
        draw.ellipse([fx,55,fx+8,63], fill=(210,175,130))
        draw.rectangle([fx,63,fx+8,85], fill=col)
    # Plato + Aristotle center
    draw.ellipse([33,50,41,58], fill=(210,175,130))
    draw.rectangle([33,58,41,80], fill=(180,80,60))  # red (Plato)
    draw.ellipse([41,50,49,58], fill=(210,175,130))
    draw.rectangle([41,58,49,80], fill=(60,80,180))  # blue (Aristotle)
    # Gesturing hand
    draw.line([37,60,33,52], fill=(210,175,130), width=2)  # pointing up
    return img

# ─── 6. Özgürlük Rehberi — Delacroix ─────────────────────────────────────────
def ozgurluk_rehberi():
    img = Image.new("RGB", (W, H), (60,50,40))
    # Smoky battle background
    gradient_v(img, 0, 0, W-1, 55, (100,90,70), (50,40,30))
    noise(img, 0, 0, W-1, 55, (80,70,55), 15, seed=3)
    # French flag (tricolor) waving
    draw = ImageDraw.Draw(img)
    draw.polygon([(40,10),(40,30),(33,28),(40,26),(47,28),(40,26)],fill=(200,200,200))
    fill(img, 35,10,39,28, (30,60,160))  # blue
    fill(img, 40,10,43,28, (240,240,240))  # white
    fill(img, 44,10,48,28, (200,40,40))  # red
    # Liberty figure (central woman)
    draw.ellipse([36,30,44,38], fill=(230,195,150))  # head
    draw.rectangle([33,38,47,60], fill=(230,225,200))  # white dress
    draw.line([36,38,30,50], fill=(230,195,150), width=2)  # left arm holding flag
    # Bare chest detail (famous)
    fill(img, 35,42,45,52, (220,185,145))
    draw.rectangle([33,52,47,65], fill=(230,225,200))  # skirt
    # Fallen figures at her feet
    draw.polygon([(10,70),(25,65),(20,80),(8,78)], fill=(100,80,60))
    draw.polygon([(55,72),(70,65),(72,80),(58,82)], fill=(80,65,50))
    # Soldiers
    for sx in [10, 60]:
        draw.ellipse([sx,55,sx+8,63], fill=(190,160,110))
        draw.rectangle([sx,63,sx+8,75], fill=(50,70,120))
    # Ground (rubble)
    noise(img, 0, 80, W-1, H-1, (80,65,45), 20, seed=7)
    return img

# ─── 7. Gece Nöbeti — Rembrandt ──────────────────────────────────────────────
def gece_nobeti():
    img = Image.new("RGB", (W, H), (30,25,15))
    # Dark arch background
    gradient_v(img, 0, 0, W-1, H-1, (50,40,25), (15,12,8))
    draw = ImageDraw.Draw(img)
    # Arch
    draw.arc([5,5,75,60], start=180, end=0, fill=(60,50,30), width=4)
    fill(img, 5,30,75,60, (35,28,18))
    # Bright captain in center (golden yellow)
    draw.ellipse([32,35,42,43], fill=(220,190,130))
    draw.rectangle([30,43,44,65], fill=(200,170,80))  # gold costume
    draw.polygon([(30,43),(26,50),(30,55),(30,65)],fill=(190,160,70))  # cape
    # Lieutenant (black+white sash)
    draw.ellipse([45,38,53,46], fill=(215,185,125))
    draw.rectangle([44,46,54,65], fill=(30,30,30))
    fill(img, 44,50,54,52, (230,220,200))  # white sash
    # Other militia figures (dark)
    for fx in [8, 20, 58, 68]:
        draw.ellipse([fx,45,fx+7,53], fill=(170,140,90))
        draw.rectangle([fx,53,fx+7,70], fill=(40,35,25))
    # Little girl in yellow (iconic detail)
    draw.ellipse([22,53,28,59], fill=(220,200,130))
    draw.rectangle([21,59,29,72], fill=(220,210,130))
    # Spears/pikes
    for sx in [15, 35, 55, 72]:
        draw.line([sx, 80, sx-5, 10], fill=(100,85,60), width=1)
    # Ground
    fill(img, 0, 80, W-1, H-1, (25,20,12))
    noise(img, 0, 80, W-1, H-1, (35,28,18), 10, seed=9)
    return img

# ─── 8. Uyuyan Venüs — Giorgione ─────────────────────────────────────────────
def uyuyan_venus():
    img = Image.new("RGB", (W, H), (100,140,100))
    # Landscape background
    gradient_v(img, 0, 0, W-1, 50, (160,195,220), (100,150,110))
    # Rolling hills
    draw = ImageDraw.Draw(img)
    draw.ellipse([-20, 30, 100, 80], fill=(80,130,80))
    draw.ellipse([-10, 40, 90, 85], fill=(100,150,100))
    # Red draping cloth
    fill(img, 5, 65, 75, 85, (180,50,40))
    fill(img, 5, 82, 75, 90, (160,40,30))
    # White sheet
    fill(img, 5, 62, 75, 70, (240,235,225))
    # Reclining figure (nude, skin tone)
    draw.ellipse([8, 52, 24, 62], fill=(220,190,150))  # head
    draw.rectangle([22, 50, 68, 65], fill=(220,190,150))  # torso
    draw.ellipse([60, 55, 76, 70], fill=(215,185,145))  # legs/hips
    draw.ellipse([70, 63, 80, 72], fill=(210,180,140))  # knees
    # Hair (dark brown)
    draw.ellipse([6, 50, 22, 60], fill=(80,55,30))
    # Arm (raised over head)
    draw.rectangle([8,48,18,56], fill=(215,185,145))
    return img

# ─── 9. Kronos Çocuklarını Yutuyor — Goya ────────────────────────────────────
def goya_kronos():
    img = Image.new("RGB", (W, H), (20,15,10))
    noise(img, 0, 0, W-1, H-1, (30,20,12), 12, seed=11)
    draw = ImageDraw.Draw(img)
    # Giant figure (dark brown/grey)
    draw.ellipse([28,5,52,25], fill=(60,45,30))  # massive head
    # Wild white eyes
    draw.ellipse([30,10,38,17], fill=(230,225,215)); draw.ellipse([32,11,36,16], fill=(15,10,5))
    draw.ellipse([42,10,50,17], fill=(230,225,215)); draw.ellipse([44,11,48,16], fill=(15,10,5))
    # Wide open mouth (dark)
    draw.ellipse([33,17,47,26], fill=(10,5,5))
    draw.rectangle([30,25,50,70], fill=(60,45,30))  # torso
    # Arms
    draw.rectangle([10,20,32,40], fill=(55,40,25))  # left arm
    draw.rectangle([48,20,70,40], fill=(55,40,25))  # right arm
    # Small figure being eaten (pale flesh)
    draw.rectangle([34,12,44,24], fill=(220,185,145))
    draw.ellipse([35,10,43,16], fill=(215,180,140))
    # Dark ground
    fill(img, 0, 85, W-1, H-1, (15,10,8))
    return img

# ─── 10. Olympia — Manet ─────────────────────────────────────────────────────
def olympia():
    img = Image.new("RGB", (W, H), (100,80,60))
    # Background (dark green-grey)
    gradient_v(img, 0, 0, W-1, H-1, (80,75,65), (50,45,38))
    noise(img, 0, 0, W-1, H-1, (70,65,55), 10, seed=13)
    draw = ImageDraw.Draw(img)
    # Pillow (white)
    fill(img, 5, 45, 75, 65, (240,235,220))
    draw.ellipse([2,43,78,67], fill=(240,235,220))
    # Reclining figure on bed
    draw.ellipse([10, 38, 22, 48], fill=(235,205,165))  # head
    draw.rectangle([20, 36, 65, 55], fill=(235,205,165))  # body
    draw.rectangle([60, 48, 76, 60], fill=(230,200,160))  # legs
    # Black hair with flower
    draw.ellipse([9, 36, 21, 45], fill=(30,20,15))
    circle(img, 11, 36, 3, (200,50,80))
    # Black ribbon at neck
    draw.rectangle([21,44,30,47], fill=(20,15,10))
    # Shoes (mules)
    draw.ellipse([72,55,80,62], fill=(200,170,100))
    # Maid (background, dark, holding flowers)
    fill(img, 58,30,78,55, (50,35,25))
    draw.ellipse([60,25,72,35], fill=(80,55,35))
    # Bouquet
    for bx,by in [(62,30),(66,28),(70,31),(64,26)]:
        circle(img, bx, by, 3, (200,80,100))
        circle(img, bx, by, 1, (240,200,200))
    # Black cat at feet (iconic)
    draw.ellipse([70,58,80,66], fill=(15,10,8))
    draw.ellipse([73,56,78,61], fill=(15,10,8))  # ears
    return img

# ─── 11. Nilüfer Havuzu — Monet ──────────────────────────────────────────────
def nilufer_havuzu():
    img = Image.new("RGB", (W, H), (60,100,80))
    # Water reflections (blue-green)
    gradient_v(img, 0, 0, W-1, H-1, (80,130,160), (40,80,60))
    # Dappled water shimmer
    import random; rng = random.Random(17)
    for _ in range(200):
        x = rng.randint(0,W-1); y = rng.randint(0,H-1)
        c = rng.choice([(80,130,100),(60,100,130),(100,155,130),(70,115,90)])
        img.putpixel((x,y),c)
    draw = ImageDraw.Draw(img)
    # Water lily pads (dark green circles)
    pads = [(15,40,14),(40,30,10),(65,50,12),(25,70,8),(55,75,10),(10,85,7),(70,85,8)]
    for px_,py_,r_ in pads:
        draw.ellipse([px_-r_,py_-r_,px_+r_,py_+r_], fill=(30,80,40))
        # notch
        draw.polygon([(px_,py_),(px_+r_,py_-r_//2),(px_+r_,py_)], fill=(20,60,30))
    # Lily flowers (pink/white)
    flowers = [(15,38),(40,27),(65,47),(25,68),(55,72)]
    for fx,fy in flowers:
        for petal in range(6):
            angle = petal * math.pi/3
            ex = int(fx + 5*math.cos(angle)); ey = int(fy + 5*math.sin(angle))
            draw.line([fx,fy,ex,ey], fill=(240,200,210), width=2)
        circle(img, fx, fy, 2, (255,240,200))
    # Wooden bridge arch (dark brown)
    draw.arc([5,5,75,80], start=180, end=0, fill=(60,40,20), width=4)
    draw.arc([10,10,70,75], start=180, end=0, fill=(60,40,20), width=2)
    # Bridge reflection
    draw.arc([5,75,75,140], start=0, end=180, fill=(40,30,18), width=3)
    # Weeping willow reflections (green streaks)
    for wx in range(0,W,3):
        wy = rng.randint(0,20)
        draw.line([wx,wy,wx+rng.randint(-5,5),wy+30], fill=(50,100,50,180), width=1)
    return img

# ─── 12. Saman Arabası — Constable ───────────────────────────────────────────
def saman_arabasi():
    img = Image.new("RGB", (W, H), (100,140,80))
    draw = ImageDraw.Draw(img)
    # Sky (English cumulus sky)
    gradient_v(img, 0, 0, W-1, 45, (130,175,220), (190,210,235))
    # Clouds
    for cx,cy,cr in [(20,15,12),(45,10,15),(65,18,10),(12,25,8)]:
        draw.ellipse([cx-cr,cy-cr,cx+cr,cy+cr], fill=(250,250,255))
    # Green meadow
    gradient_v(img, 0,45, W-1, H-1, (80,130,60), (60,100,40))
    # River (winding, left)
    draw.polygon([(0,60),(18,55),(22,65),(5,75),(0,80)], fill=(100,145,170))
    draw.polygon([(5,80),(22,70),(25,85),(10,95),(0,90)], fill=(90,135,160))
    # Mill house (right background)
    fill(img, 55,40,75,62, (160,130,90))
    draw.polygon([(55,40),(65,28),(75,40)], fill=(120,90,60))
    # Trees (dark green masses)
    draw.ellipse([8,30,28,55], fill=(40,80,30))
    draw.ellipse([12,25,32,52], fill=(50,90,35))
    draw.ellipse([50,35,68,55], fill=(45,85,32))
    # Haywain wagon
    draw.rectangle([28,60,52,72], fill=(120,90,50))  # wagon body
    draw.ellipse([26,65,36,75], fill=(80,60,30)); draw.ellipse([26,67,36,73],fill=(60,45,20))
    draw.ellipse([44,65,54,75], fill=(80,60,30)); draw.ellipse([44,67,54,73],fill=(60,45,20))
    # Horses (brown)
    draw.ellipse([15,58,28,68], fill=(100,70,40))
    draw.ellipse([22,55,35,65], fill=(110,75,45))
    # Hay stacked on wagon
    fill(img,30,52,50,61,(200,175,80))
    # Figures
    draw.ellipse([35,56,40,62], fill=(180,150,100))
    return img

# ─── 13. La Grande Jatte — Seurat ────────────────────────────────────────────
def grande_jatte():
    img = Image.new("RGB", (W, H), (100,150,100))
    # Pointillist sky
    import random; rng = random.Random(19)
    for y in range(0,40):
        for x in range(W):
            base = (140+rng.randint(-10,10), 190+rng.randint(-10,10), 230+rng.randint(-10,10))
            img.putpixel((x,y),base)
    # Grass
    for y in range(40,H):
        for x in range(W):
            g = 100 + int(30*(y-40)/(H-40)) + rng.randint(-8,8)
            img.putpixel((x,y),(40+rng.randint(-8,8), g, 40+rng.randint(-5,5)))
    # River (right side)
    draw = ImageDraw.Draw(img)
    for y in range(50,90):
        fill(img, 55,y,W-1,y, (80+rng.randint(-5,5), 130+rng.randint(-5,5), 170+rng.randint(-5,5)))
    # Sunday promenaders (Seurat's pointillist figures)
    # Large woman with umbrella
    draw.ellipse([30,45,38,53], fill=(40,30,20))   # head
    draw.rectangle([28,53,40,75], fill=(200,160,130))  # dress
    draw.rectangle([36,40,38,56], fill=(30,20,15))   # parasol pole
    draw.ellipse([28,36,48,44], fill=(200,160,130))  # umbrella top
    # Child
    draw.ellipse([42,55,48,61], fill=(220,190,150))
    draw.rectangle([41,61,49,72], fill=(250,220,180))
    # Man with top hat
    draw.ellipse([10,50,18,58], fill=(30,25,20))
    draw.rectangle([11,45,17,53], fill=(20,18,15))  # top hat
    draw.rectangle([10,58,18,74], fill=(40,35,28))
    draw.rectangle([8,72,12,76], fill=(40,35,28))  # legs
    # Dog
    draw.ellipse([52,70,62,76], fill=(180,150,100))
    draw.ellipse([50,68,56,74], fill=(175,145,95))
    # Monkey on leash (famous detail)
    draw.ellipse([20,74,26,80], fill=(80,60,40))
    draw.line([20,78,15,82], fill=(80,60,40), width=1)
    return img

# ─── 14. Moulin de la Galette — Renoir ───────────────────────────────────────
def moulin_galette():
    img = Image.new("RGB", (W, H), (80,100,70))
    import random; rng = random.Random(21)
    # Dappled sunlight through trees (warm greens/yellows)
    gradient_v(img, 0, 0, W-1, H-1, (120,155,100), (80,110,70))
    for _ in range(150):
        x,y = rng.randint(0,W-1), rng.randint(0,40)
        r = 170+rng.randint(-15,15); g = 185+rng.randint(-10,10); b = 120+rng.randint(-15,15)
        img.putpixel((x,y),(r,g,b))
    draw = ImageDraw.Draw(img)
    # Trees (dark shapes)
    draw.ellipse([-5,0,20,35], fill=(40,70,30))
    draw.ellipse([55,0,85,35], fill=(35,65,28))
    draw.ellipse([20,5,45,35], fill=(50,80,38))
    # Tables
    for tx in [8,35,58]:
        draw.ellipse([tx,65,tx+20,73], fill=(200,185,150))
        draw.rectangle([tx+8,73,tx+12,82], fill=(140,120,80))
    # Dancing couples
    for i, (cx,cy) in enumerate([(20,45),(45,42),(60,48)]):
        r,g,b = [(200,100,120),(140,160,200),(180,140,100)][i%3]
        draw.ellipse([cx-3,cy-10,cx+3,cy-4], fill=(220,185,145))  # head
        draw.rectangle([cx-4,cy-4,cx+4,cy+8], fill=(r,g,b))         # dress
        # partner
        draw.ellipse([cx+5,cy-8,cx+11,cy-2], fill=(215,180,140))
        draw.rectangle([cx+4,cy-2,cx+12,cy+8], fill=(50,50,80))
    # Lanterns (yellow dots)
    for lx,ly in [(15,28),(40,22),(60,30),(70,25)]:
        circle(img, lx, ly, 3, (240,210,100))
        circle(img, lx, ly, 1, (255,240,150))
    # Ground
    fill(img, 0,85,W-1,H-1, (100,80,60))
    return img

# ─── 15. Zamanın Azmi — Dalí ─────────────────────────────────────────────────
def persistans():
    img = Image.new("RGB", (W, H), (180,160,100))
    # Desert landscape (golden/brown)
    gradient_v(img, 0, 0, W-1, 55, (200,175,120), (160,140,90))
    # Sky (blue-orange Catalan sky)
    gradient_v(img, 0, 0, W-1, 35, (120,180,220), (200,175,120))
    draw = ImageDraw.Draw(img)
    # Cliffs (right)
    draw.polygon([(55,15),(80,15),(80,55),(50,50)], fill=(180,145,90))
    # Sea (right middle)
    fill(img, 55,35,W-1,50, (100,155,185))
    # Ground/table (brown slab)
    draw.rectangle([5,55,40,65], fill=(120,90,55))
    # Melting watches (iconic: 3 watches in different states)
    # Watch 1: over the table edge (yellow, drooping)
    draw.ellipse([8,47,22,58], fill=(210,180,80))   # watch face
    draw.ellipse([9,48,21,57], fill=(200,170,70))
    draw.line([8,53,3,63], fill=(190,160,60), width=2)  # droop
    draw.line([3,63,5,70], fill=(185,155,58), width=2)
    # Watch 2: draped over weird object (orange-tan)
    draw.ellipse([30,48,46,60], fill=(220,160,80))
    draw.polygon([(30,54),(25,65),(38,60),(46,54)], fill=(200,145,70))  # draping
    # Watch 3: face-down, melting off tree branch
    draw.ellipse([50,42,64,52], fill=(200,175,90))
    draw.line([52,52,48,60], fill=(185,160,78), width=2)
    draw.line([48,60,46,70], fill=(180,155,75), width=2)
    # Strange melting creature (central)
    draw.ellipse([30,55,50,75], fill=(220,195,150))
    draw.rectangle([32,70,48,80], fill=(215,190,145))
    draw.polygon([(28,72),(22,80),(38,78)], fill=(210,185,140))  # drape
    # Fly on watch 1
    draw.ellipse([13,48,17,52], fill=(20,18,15))
    # Shadow
    fill(img, 0,82,W-1,H-1, (130,105,65))
    return img

# ─── 16. Guernica — Picasso ──────────────────────────────────────────────────
def guernica():
    img = Image.new("RGB", (W, H), (80,80,80))
    # Monochrome grey palette
    gradient_v(img, 0, 0, W-1, H-1, (100,100,100), (50,50,50))
    draw = ImageDraw.Draw(img)
    # Bull (left)
    draw.polygon([(5,30),(18,25),(22,35),(18,45),(5,45)], fill=(60,60,60))
    draw.ellipse([3,22,15,32], fill=(65,65,65))  # bull head
    draw.polygon([(5,22),(2,16),(8,20)], fill=(55,55,55))  # horn
    draw.polygon([(12,22),(15,16),(10,20)], fill=(55,55,55))
    # Horse (center, rearing)
    draw.polygon([(30,20),(45,15),(50,30),(45,45),(30,45)], fill=(90,90,90))
    draw.ellipse([38,10,52,22], fill=(95,95,95))  # horse head
    draw.line([44,10,40,3], fill=(95,95,95), width=2)  # mouth open
    draw.polygon([(42,10),(44,5),(46,10)], fill=(85,85,85))  # ear
    # Screaming woman (right with dead baby)
    draw.ellipse([60,30,72,40], fill=(110,110,110))  # head
    draw.polygon([(60,40),(55,55),(70,50),(72,40)], fill=(100,100,100))  # body
    draw.ellipse([62,50,72,58], fill=(120,120,120))  # baby
    # Dismembered soldier (bottom)
    draw.rectangle([10,75,30,82], fill=(70,70,70))  # arm
    draw.ellipse([10,80,20,88], fill=(70,70,70))    # fist
    draw.line([5,85,20,82], fill=(80,80,80), width=2)
    # Light bulb / eye (top)
    draw.ellipse([35,2,50,12], fill=(220,215,180))  # bulb
    draw.ellipse([38,4,47,10], fill=(230,225,190))
    draw.ellipse([39,5,46,9], fill=(20,20,20))  # eye pupil
    draw.line([40,12,42,18], fill=(200,195,160), width=2)
    # Lamp (top right)
    draw.polygon([(60,5),(75,5),(70,18),(65,18)], fill=(150,145,130))
    draw.rectangle([65,5,70,12], fill=(30,30,30))
    # Crying mouth (bottom center)
    draw.arc([35,65,55,80], start=0, end=180, fill=(40,40,40), width=2)
    draw.line([40,68,42,75], fill=(40,40,40), width=1)
    draw.line([50,68,48,75], fill=(40,40,40), width=1)
    # Window/door shard
    draw.polygon([(20,40),(30,35),(32,60),(20,62)], fill=(115,115,115))
    return img

# ─── 17. Amerikan Gotiği — Grant Wood ────────────────────────────────────────
def amerikan_gotigi():
    img = Image.new("RGB", (W, H), (120,145,80))
    draw = ImageDraw.Draw(img)
    # Sky
    gradient_v(img, 0, 0, W-1, 35, (160,195,220), (200,215,230))
    # Farmhouse
    fill(img, 25,30,55,70, (220,210,185))  # house body
    draw.polygon([(25,30),(40,12),(55,30)], fill=(180,165,140))  # roof
    # Gothic window (iconic pointed arch)
    fill(img, 35,35,45,55, (160,190,215))
    draw.arc([35,30,45,42], start=180, end=0, fill=(160,190,215), width=3)
    fill(img,36,30,44,40, (160,190,215))
    # Window panes
    draw.line([40,35,40,55], fill=(100,80,60), width=1)
    draw.line([36,45,44,45], fill=(100,80,60), width=1)
    # Barn (behind)
    fill(img, 0,42,24,68, (160,80,60))
    draw.polygon([(0,42),(12,30),(24,42)], fill=(130,60,40))
    # Trees
    draw.ellipse([55,30,75,55], fill=(50,90,35))
    draw.rectangle([63,55,67,70], fill=(80,55,35))
    # Man (right, holding pitchfork)
    draw.ellipse([50,55,58,63], fill=(210,175,130))  # head
    draw.rectangle([48,63,60,82], fill=(90,90,120))  # overalls
    draw.rectangle([49,55,53,63], fill=(200,175,130))  # neck
    # Pitchfork
    draw.line([58,60,58,90], fill=(100,75,40), width=1)
    draw.line([56,62,60,62], fill=(100,75,40), width=1)
    draw.line([56,64,60,64], fill=(100,75,40), width=1)
    # Woman (left)
    draw.ellipse([22,55,30,63], fill=(215,180,135))  # head
    draw.rectangle([20,63,32,82], fill=(180,130,100))  # dress
    draw.rectangle([22,55,28,63], fill=(215,180,135))  # neck
    # Cameo brooch (detail)
    circle(img, 26,67, 2, (230,210,180))
    # Ground
    fill(img, 0,82,W-1,H-1, (120,110,70))
    for x in range(0,W,6):
        draw.line([x,82,x+3,H-1], fill=(100,90,55), width=1)
    return img

# ─── 18. Yaratılış — Michelangelo (Sistine) ───────────────────────────────────
def sistine_yaratilis():
    img = Image.new("RGB", (W, H), (180,160,130))
    gradient_v(img, 0, 0, W-1, H-1, (200,185,155), (160,140,110))
    draw = ImageDraw.Draw(img)
    # Sky tones
    gradient_v(img, 0, 0, W-1, 50, (190,200,210), (175,170,145))
    noise(img, 0, 0, W-1, H-1, (185,170,145), 15, seed=23)
    # God (right side, with angels in cloak)
    draw.ellipse([52,28,64,40], fill=(210,185,145))  # God head
    draw.ellipse([48,20,72,50], fill=(180,140,110))  # flowing cloak/cloud
    # Angels inside cloak
    for ax,ay in [(56,32),(62,36),(66,30)]:
        draw.ellipse([ax-3,ay-3,ax+3,ay+3], fill=(220,190,150))
    # Adam (left side, reclining)
    draw.ellipse([8,40,20,50], fill=(215,180,140))   # head
    draw.rectangle([16,36,50,52], fill=(215,180,140))  # torso
    draw.rectangle([45,48,68,58], fill=(210,175,138))  # outstretched arm
    draw.ellipse([64,46,72,54], fill=(215,180,140))   # hand
    # The Gap — fingertips almost touching
    draw.ellipse([50,44,54,48], fill=(210,175,138))  # God's hand
    # Rock Adam lies on
    draw.polygon([(0,52),(25,50),(30,62),(0,65)], fill=(140,120,90))
    # Drapery over Adam's lower body
    fill(img, 18,50,42,60, (180,155,120))
    # Ground
    fill(img, 0,72,W-1,H-1, (130,110,80))
    return img

# ─── 19. Kız Kuşu (İlkbahar) — Bouguereau ────────────────────────────────────
def bouguereau_bahar():
    img = Image.new("RGB", (W, H), (80,120,80))
    # Garden background
    gradient_v(img, 0, 0, W-1, H-1, (100,150,100), (60,100,60))
    noise(img, 0, 0, W-1, H-1, (85,130,85), 20, seed=29)
    draw = ImageDraw.Draw(img)
    # Flowers (spring garden)
    for fx,fy,fc in [(10,20,(240,180,200)),(20,15,(240,220,180)),(60,18,(200,180,240)),
                      (70,25,(240,200,200)),(5,35,(220,240,180)),(75,40,(240,180,180))]:
        circle(img, fx,fy,6,fc); circle(img, fx,fy,2,(255,255,255))
    # Trees/foliage background
    draw.ellipse([0,5,30,50], fill=(40,80,30))
    draw.ellipse([50,5,85,50], fill=(35,75,28))
    # Young woman in white (central)
    draw.ellipse([32,20,48,34], fill=(235,210,170))  # head
    # Hair (dark, with flowers)
    draw.ellipse([30,18,48,30], fill=(60,40,25))
    circle(img, 35,18,3,(240,200,200)); circle(img,42,16,3,(240,200,200))
    # White dress
    draw.rectangle([28,34,52,80], fill=(240,235,225))
    draw.ellipse([24,60,56,90], fill=(235,230,220))  # skirt flare
    # Arms holding birds
    draw.rectangle([18,34,30,46], fill=(235,210,170))
    draw.rectangle([52,34,62,46], fill=(235,210,170))
    # Birds (small)
    circle(img, 15,36,4,(180,160,140)); draw.ellipse([11,35,15,37],fill=(100,80,60))
    circle(img, 64,36,4,(180,160,140)); draw.ellipse([64,35,68,37],fill=(100,80,60))
    # Ground with flowers
    fill(img, 0,90,W-1,H-1,(80,110,60))
    for gx in range(0,W,8):
        circle(img,gx+4,95,3,(240,200,200))
    return img

# ─── 20. İki Frida — Frida Kahlo ─────────────────────────────────────────────
def iki_frida():
    img = Image.new("RGB", (W, H), (120,160,200))
    # Stormy sky background
    gradient_v(img, 0, 0, W-1, 60, (110,145,185), (80,105,140))
    import random; rng = random.Random(31)
    draw = ImageDraw.Draw(img)
    # Storm clouds
    for cx,cy,cr in [(15,15,12),(40,10,15),(65,18,10)]:
        draw.ellipse([cx-cr,cy-cr,cx+cr,cy+cr], fill=(130,130,150))
    # Bench (dark wood)
    fill(img, 5,80,75,90, (80,55,35))
    fill(img, 5,88,75,92, (70,48,30))
    # Left Frida (traditional dress, right heart exposed)
    draw.ellipse([14,30,24,40], fill=(215,180,140))  # head
    draw.rectangle([10,40,28,72], fill=(235,210,185))  # white blouse
    draw.rectangle([10,60,28,82], fill=(150,45,45))    # red skirt
    # Visible heart (right Frida's)
    draw.ellipse([15,46,23,54], fill=(180,40,40))
    # Vein connecting hearts
    draw.arc([14,48,58,70], start=200, end=340, fill=(180,40,40), width=2)
    # Right Frida (Tehuana/indigenous dress)
    draw.ellipse([56,30,66,40], fill=(215,180,140))  # head
    draw.rectangle([52,40,70,72], fill=(180,40,80))   # Tehuana blouse (pink)
    draw.rectangle([52,60,70,82], fill=(60,100,160))  # blue skirt
    # Intact heart (right Frida)
    draw.ellipse([56,46,64,54], fill=(180,40,40))
    draw.ellipse([57,47,63,53], fill=(200,60,60))
    # Flowers in both heads of hair
    for hx,hy in [(12,30),(17,28),(56,29),(62,27)]:
        circle(img, hx,hy,3,(240,100,100)); circle(img, hx,hy,1,(255,220,220))
    # Faces (simplified)
    # Left: famous unibrow
    draw.line([15,35,24,35], fill=(40,30,20), width=2)
    draw.ellipse([15,36,19,40], fill=(30,20,15)); draw.ellipse([21,36,25,40], fill=(30,20,15))
    # Right: same
    draw.line([57,35,66,35], fill=(40,30,20), width=2)
    draw.ellipse([57,36,61,40], fill=(30,20,15)); draw.ellipse([63,36,67,40], fill=(30,20,15))
    # Joined hands in center
    draw.ellipse([34,60,40,66], fill=(215,180,140))
    draw.ellipse([40,60,46,66], fill=(215,180,140))
    # Surgical scissors (left Frida cutting vein - detail)
    draw.line([22,55,28,60], fill=(150,150,160), width=1)
    draw.line([24,55,30,60], fill=(150,150,160), width=1)
    return img

PAINTINGS = [
    ("buyuk_dalga",       "Buyuk Dalga",        buyuk_dalga),
    ("kiz_kupeyle",       "Kiz Kupeyle",        kiz_kupeyle),
    ("son_aksam_yemegi",  "Son Aksam Yemegi",   son_aksam_yemegi),
    ("venus_dogumu",      "Venus Dogumu",       venus_dogumu),
    ("athena_okulu",      "Athena Okulu",       athena_okulu),
    ("ozgurluk_rehberi",  "Ozgurluk Rehberi",   ozgurluk_rehberi),
    ("gece_nobeti",       "Gece Nobeti",        gece_nobeti),
    ("uyuyan_venus",      "Uyuyan Venus",       uyuyan_venus),
    ("goya_kronos",       "Goya Kronos",        goya_kronos),
    ("olympia",           "Olympia",            olympia),
    ("nilufer_havuzu",    "Nilufer Havuzu",     nilufer_havuzu),
    ("saman_arabasi",     "Saman Arabasi",      saman_arabasi),
    ("grande_jatte",      "Buyuk Jatte",        grande_jatte),
    ("moulin_galette",    "Dans Dersi",         moulin_galette),
    ("persistans",        "Persistans",         persistans),
    ("guernica",          "Guernica",           guernica),
    ("amerikan_gotigi",   "Amerikan Gotigi",    amerikan_gotigi),
    ("sistine_yaratilis", "Sistine Yaratilis",  sistine_yaratilis),
    ("bouguereau_bahar",  "Bahar Bahcesi",      bouguereau_bahar),
    ("iki_frida",         "Iki Frida",          iki_frida),
]

def emit_array(var_name, pixels, f):
    flat = []
    for r, g, b in pixels:
        flat += [r, g, b]
    f.write(f"const uint8_t {var_name}[{W*H*3}] PROGMEM = {{")
    f.write(",".join(str(v) for v in flat))
    f.write("};\n")

def main():
    out_path = "/home/user/magpanel/include/gallery_new.h"
    results = []
    for var, display, fn in PAINTINGS:
        print(f"  Rendering: {display} ...", end=" ", flush=True)
        img = fn()
        pixels = list(img.getdata())
        results.append((var, display, pixels))
        print("OK")

    with open(out_path, "w") as f:
        f.write("// Public domain klasik tablolar (ek 20) — 80x120 RGB888 PROGMEM\n")
        f.write("// Sanatsal piksel temsilleri; tum eserler kamu malı\n")
        f.write("#pragma once\n")
        f.write("#include <pgmspace.h>\n\n")
        for var, display, pixels in results:
            f.write(f"// {display}\n")
            emit_array(f"gallery_new_{var}", pixels, f)
            f.write("\n")
        count = len(results)
        f.write(f"#define GALLERY_NEW_COUNT {count}\n")
        names = ", ".join(f'"{d}"' for _, d, _ in results)
        f.write(f"const char* const GALLERY_NEW_NAMES[GALLERY_NEW_COUNT] PROGMEM = {{{names}}};\n")
        ptrs  = ", ".join(f"gallery_new_{v}" for v, _, _ in results)
        f.write(f"const uint8_t* const GALLERY_NEW_PTRS[GALLERY_NEW_COUNT] PROGMEM = {{{ptrs}}};\n")

    print(f"\nWrote {count} paintings → {out_path}")

if __name__ == "__main__":
    main()
