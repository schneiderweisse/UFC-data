"""
Gera os "personagens" 8-bit dos lutadores a partir das fotos oficiais da ESPN.

Para cada lutador de Fighter data/ranked_fighters.csv:
  1. baixa a foto (headshot) do CDN da ESPN;
  2. recorta cabeça + ombros num quadrado;
  3. reduz para uma grade de SPRITE_PX x SPRITE_PX pixels com paleta limitada;
  4. aplica contorno preto na silhueta (visual de sprite de fliperama);
  5. amplia sem suavização e salva em assets/sprites/<espn_id>.png.

Lutadores sem foto ganham uma silhueta genérica.

Uso:
  py build_sprites.py           # gera só os que ainda não existem
  py build_sprites.py --force   # refaz todos
"""

import csv
import io
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "Fighter data"
SPRITE_DIR = HERE / "assets" / "sprites"

HEADSHOT_URL = "https://a.espncdn.com/i/headshots/mma/players/full/{id}.png"
SPRITE_PX = 36      # resolução "8-bit" do sprite
SCALE = 6           # ampliação final (nearest neighbor)
COLORS = 18         # tamanho da paleta
OUTLINE = (12, 8, 24, 255)


def head_square(img):
    """Recorta um quadrado de cabeça + ombros a partir da foto com fundo transparente."""
    alpha = img.getchannel("A")
    left, top, right, bottom = alpha.getbbox()
    w, h = img.size

    # centro horizontal da cabeça = média das colunas opacas no topo da silhueta
    band = alpha.crop((0, top, w, min(top + 90, h))).point(lambda a: 255 if a > 128 else 0)
    cols = [x for x in range(w) for y in range(band.height) if band.getpixel((x, y))]
    cx = sum(cols) / len(cols) if cols else w / 2

    side = int(h * 0.78)
    x0 = int(cx - side / 2)
    y0 = max(top - int(side * 0.06), 0)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img.crop((x0, y0, x0 + side, y0 + side)), (0, 0))
    return canvas


def pixelate(img):
    small = img.resize((SPRITE_PX, SPRITE_PX), Image.BOX)

    # alpha duro (sem semitransparência) e paleta reduzida, sem dithering
    alpha = small.getchannel("A").point(lambda a: 255 if a > 110 else 0)
    rgb = small.convert("RGB").quantize(COLORS, method=Image.MEDIANCUT, dither=Image.NONE)
    sprite = rgb.convert("RGBA")
    sprite.putalpha(alpha)

    # contorno de 1 px em volta da silhueta
    out = sprite.copy()
    px, opx = sprite.load(), out.load()
    for x in range(SPRITE_PX):
        for y in range(SPRITE_PX):
            if px[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < SPRITE_PX and 0 <= ny < SPRITE_PX and px[nx, ny][3]:
                    opx[x, y] = OUTLINE
                    break
    return out.resize((SPRITE_PX * SCALE, SPRITE_PX * SCALE), Image.NEAREST)


def placeholder():
    """Silhueta genérica para quem não tem foto."""
    s = Image.new("RGBA", (SPRITE_PX, SPRITE_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    body, shade = (70, 64, 110, 255), (48, 42, 82, 255)
    d.ellipse((11, 5, 24, 21), fill=body, outline=OUTLINE)            # cabeça
    d.rectangle((15, 20, 20, 24), fill=body)                           # pescoço
    d.rounded_rectangle((3, 23, 32, 40), 6, fill=body, outline=OUTLINE)  # ombros
    d.text((15, 8), "?", fill=shade)
    return s.resize((SPRITE_PX * SCALE, SPRITE_PX * SCALE), Image.NEAREST)


def main():
    force = "--force" in sys.argv
    SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "ranked_fighters.csv", encoding="utf-8-sig") as f:
        ids = list(dict.fromkeys(r["espn_id"] for r in csv.DictReader(f) if r["espn_id"]))

    placeholder().save(SPRITE_DIR / "unknown.png")
    session = requests.Session()
    for i, espn_id in enumerate(ids, 1):
        path = SPRITE_DIR / f"{espn_id}.png"
        if path.exists() and not force:
            continue
        r = session.get(HEADSHOT_URL.format(id=espn_id), timeout=30)
        if r.status_code == 200:
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            pixelate(head_square(img)).save(path)
            status = "ok"
        else:
            placeholder().save(path)
            status = f"sem foto ({r.status_code}), silhueta genérica"
        print(f"[{i}/{len(ids)}] {espn_id}: {status}")
        time.sleep(0.3)


if __name__ == "__main__":
    main()
